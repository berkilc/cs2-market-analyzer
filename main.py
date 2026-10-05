import os
import re
import sys
import time
import urllib.parse
from datetime import datetime
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Windows konsolunda Türkçe karakter ve emoji desteği
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# .env dosyasındaki ortam değişkenlerini yükle
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, '.env')
load_dotenv(env_path)

# --- VERİTABANI BAĞLANTISI ---
DB_LINK = os.getenv("DATABASE_URL")

# --- HAZIR KATEGORİ LİSTELERİ ---
CASES_PRESET = [
    "Gallery Case",
    "Kilowatt Case",
    "Revolution Case",
    "Dreams & Nightmares Case",
    "Recoil Case",
    "Snakebite Case",
    "Fracture Case",
    "Prisma 2 Case",
    "Danger Zone Case",
    "Horizon Case",
    "Spectrum 2 Case",
    "Clutch Case",
    "Glove Case"
]

POPULAR_SKINS_PRESET = [
    "AK-47 | Redline",
    "AK-47 | Slate",
    "AWP | Asiimov",
    "AWP | Atheris",
    "M4A1-S | Printstream",
    "M4A4 | The Emperor",
    "Desert Eagle | Printstream",
    "USP-S | The Traitor",
    "Glock-18 | Water Elemental"
]


def veritabani_hazirla():
    """Bot ilk çalıştığında buluta bağlanıp tablolar yoksa otomatik oluşturur."""
    try:
        baglanti = psycopg2.connect(DB_LINK)
        imlec = baglanti.cursor()
        imlec.execute("""
            CREATE TABLE IF NOT EXISTS pazar_verileri (
                id SERIAL PRIMARY KEY,
                tarih DATE,
                saat TIME,
                esya VARCHAR(255),
                fiyat VARCHAR(50),
                hacim VARCHAR(50),
                fiyat_sayisal NUMERIC(10, 2),
                hacim_sayisal INTEGER,
                para_birimi VARCHAR(10) DEFAULT 'USD',
                kayit_tarihi TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        imlec.execute("""
            CREATE TABLE IF NOT EXISTS takip_listesi (
                id SERIAL PRIMARY KEY,
                esya VARCHAR(255) UNIQUE NOT NULL,
                hedef_fiyat NUMERIC(10, 2),
                ekleme_tarihi TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        baglanti.commit()
        imlec.close()
        baglanti.close()
        print("✅ Neon Bulut Veritabanı Bağlantısı Başarılı! Sistem Hazır.\n")
    except Exception as e:
        print(f"❌ Veritabanı Hatası: {e}")
        print("Lütfen .env dosyasındaki DATABASE_URL adresini kontrol edin.")
        sys.exit(1)


def format_item_name(user_input):
    text = user_input.lower().strip().replace(" | ", " ").replace("|", " ")
    weapons = {
        "ak-47": "AK-47", "ak 47": "AK-47", "ak47": "AK-47", 
        "m4a1-s": "M4A1-S", "m4a1s": "M4A1-S", "m4a4": "M4A4", "awp": "AWP", 
        "usp-s": "USP-S", "glock-18": "Glock-18", "desert eagle": "Desert Eagle", 
        "deagle": "Desert Eagle", "p2000": "P2000", "cz75-auto": "CZ75-Auto",
        "mac-10": "MAC-10", "mp9": "MP9", "ump-45": "UMP-45", "p90": "P90", 
        "famas": "FAMAS", "galil ar": "Galil AR", "aug": "AUG", 
        "sg 553": "SG 553", "ssg 08": "SSG 08", "p250": "P250", 
        "tec-9": "Tec-9", "five-seven": "Five-SeveN"
    }
    for w_lower, w_correct in weapons.items():
        if text.startswith(w_lower):
            skin_name = text[len(w_lower):].strip().title()
            if skin_name:
                return f"{w_correct} | {skin_name}"
            return w_correct
    return user_input.strip().title()


def get_price(item_name):
    url = f"https://steamcommunity.com/market/priceoverview/?appid=730&currency=1&market_hash_name={urllib.parse.quote(item_name)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get('lowest_price'), data.get('volume', 'Yok')
        elif response.status_code == 429:
            return None, "Hata: Engellendik (429 Rate Limit)"
        return None, "Pazarda bulunamadı."
    except Exception as e:
        return None, f"Sistemsel Hata: {e}"


def parse_numbers(fiyat_str, hacim_str):
    p_val = None
    if fiyat_str:
        p_match = re.search(r'[\d.,]+', fiyat_str)
        if p_match:
            raw = p_match.group(0)
            if ',' in raw and '.' in raw:
                raw = raw.replace(',', '')
            elif ',' in raw and '.' not in raw:
                raw = raw.replace(',', '.')
            try:
                p_val = float(raw)
            except ValueError:
                pass

    v_val = None
    if hacim_str and hacim_str.lower() not in ['yok', 'none', '-']:
        cleaned = re.sub(r'[^\d]', '', hacim_str)
        if cleaned:
            v_val = int(cleaned)

    return p_val, v_val


def get_previous_price(esya):
    try:
        baglanti = psycopg2.connect(DB_LINK)
        imlec = baglanti.cursor()
        imlec.execute("""
            SELECT fiyat_sayisal, kayit_tarihi
            FROM pazar_verileri
            WHERE esya = %s AND fiyat_sayisal IS NOT NULL
            ORDER BY id DESC LIMIT 1;
        """, (esya,))
        row = imlec.fetchone()
        imlec.close()
        baglanti.close()
        if row:
            return float(row[0]), row[1]
    except Exception:
        pass
    return None, None


def veriyi_buluta_yaz(esya, fiyat, hacim):
    try:
        zaman = datetime.now()
        tarih = zaman.strftime("%Y-%m-%d")
        saat = zaman.strftime("%H:%M:%S")
        fiyat_sayisal, hacim_sayisal = parse_numbers(fiyat, hacim)

        baglanti = psycopg2.connect(DB_LINK)
        imlec = baglanti.cursor()
        
        sorgu = """
            INSERT INTO pazar_verileri 
            (tarih, saat, esya, fiyat, hacim, fiyat_sayisal, hacim_sayisal, para_birimi, kayit_tarihi)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """
        imlec.execute(sorgu, (tarih, saat, esya, fiyat, hacim, fiyat_sayisal, hacim_sayisal, 'USD'))
        
        baglanti.commit()
        imlec.close()
        baglanti.close()
        return True
    except Exception as e:
        print(f"Veri kaydedilemedi: {e}")
        return False


def tek_esya_tara(esya):
    print(f"[{esya}] çekiliyor... ", end="", flush=True)
    prev_price, prev_time = get_previous_price(esya)
    fiyat, hacim = get_price(esya)

    if fiyat:
        if veriyi_buluta_yaz(esya, fiyat, hacim):
            curr_price, _ = parse_numbers(fiyat, hacim)
            if prev_price is not None and curr_price is not None:
                fark = curr_price - prev_price
                if fark < -0.001:
                    yuzde = abs(fark / prev_price) * 100
                    durum = f"📉 %{yuzde:.2f} DÜŞTÜ (Önceki: ${prev_price:.2f})"
                elif fark > 0.001:
                    yuzde = (fark / prev_price) * 100
                    durum = f"📈 %{yuzde:.2f} ARTTI (Önceki: ${prev_price:.2f})"
                else:
                    durum = "➡️ Sabit"
            else:
                durum = "✨ İlk Kayıt"

            print(f"Fiyat: {fiyat} | Hacim: {hacim} ({durum} - Buluta Kaydedildi)")
    else:
        print(hacim)


def toplu_esya_tara(esya_listesi, scan_wears=False):
    wear_levels = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]
    final_list = []

    for item in esya_listesi:
        base_name = format_item_name(item)
        if scan_wears and "|" in base_name and not any(f"({w})" in base_name for w in wear_levels):
            for w in wear_levels:
                final_list.append(f"{base_name} ({w})")
        else:
            final_list.append(base_name)

    total = len(final_list)
    print(f"\n🚀 Toplam {total} eşya taranmaya başlanıyor...\n" + "─" * 60)

    for idx, esya in enumerate(final_list, 1):
        print(f"({idx}/{total}) ", end="")
        tek_esya_tara(esya)
        time.sleep(2.5)

    print("─" * 60 + "\n✅ Toplu tarama tamamlandı!\n")


# 1. HIZLI KATEGORİ PAKETLERİ
def hizli_paketler_menusu():
    while True:
        print("\n" + "═" * 55)
        print("⚡ HIZLI KATEGORİ PAKETLERİ (TEK TIKLA TARAMA)")
        print("═" * 55)
        print("1. 📦 Tüm CS2 Kasalarını Tara (13+ Kasa)")
        print("2. 🔫 Popüler Yatırımlık Skinleri Tara (Tüm Aşınmalarla)")
        print("0. ↩️ Ana Menüye Dön")
        print("─" * 55)

        secim = input("Seçiminiz (0-2): ").strip()
        if secim == "1":
            print("\n📦 Tüm CS2 Kasaları taranıyor...")
            toplu_esya_tara(CASES_PRESET, scan_wears=False)
        elif secim == "2":
            print("\n🔫 Popüler Yatırımlık Skinler taranıyor...")
            toplu_esya_tara(POPULAR_SKINS_PRESET, scan_wears=True)
        elif secim in ["0", "q"]:
            break
        else:
            print("⚠️ Geçersiz seçim!")


# 2. KİŞİSEL TAKİP LİSTEM (PORTFÖY)
def takip_listesi_goruntule():
    try:
        baglanti = psycopg2.connect(DB_LINK)
        imlec = baglanti.cursor(cursor_factory=RealDictCursor)
        imlec.execute("SELECT id, esya, hedef_fiyat, ekleme_tarihi FROM takip_listesi ORDER BY id ASC;")
        rows = imlec.fetchall()
        imlec.close()
        baglanti.close()

        if not rows:
            print("\n📌 Takip listenizde henüz kayıtlı eşya yok.")
            return []

        print("\n" + "═" * 70)
        print(f"{'NO':<4} | {'EŞYA ADI':<40} | {'HEDEF ($)':<10} | {'EKLEME TARİHİ'}")
        print("─" * 70)
        for r in rows:
            hf = f"${r['hedef_fiyat']:.2f}" if r['hedef_fiyat'] else "-"
            dt = r['ekleme_tarihi'].strftime('%d.%m.%Y %H:%M') if r['ekleme_tarihi'] else "-"
            print(f"{r['id']:<4} | {r['esya']:<40} | {hf:<10} | {dt}")
        print("═" * 70)
        return rows
    except Exception as e:
        print(f"❌ Takip listesi okunamadı: {e}")
        return []


def takip_listesi_menusu():
    while True:
        print("\n" + "═" * 55)
        print("📌 KİŞİSEL TAKİP LİSTEM (PORTFÖY YÖNETİMİ)")
        print("═" * 55)
        print("1. 🚀 Takip Listemdeki Tüm Eşyaları Şimdi Tara")
        print("2. 📋 Takip Listemi Görüntüle")
        print("3. ➕ Listeye Yeni Eşya Ekle")
        print("4. 🗑️ Listeden Eşya Sil")
        print("0. ↩️ Ana Menüye Dön")
        print("─" * 55)

        secim = input("Seçiminiz (0-4): ").strip()

        if secim == "1":
            rows = takip_listesi_goruntule()
            if rows:
                esya_adlari = [r['esya'] for r in rows]
                toplu_esya_tara(esya_adlari, scan_wears=False)
        elif secim == "2":
            takip_listesi_goruntule()
        elif secim == "3":
            ad = input("\nTakip edilecek eşya adını yazın (Örn: AWP Asiimov (Field-Tested)): ").strip()
            if not ad:
                continue
            hedef = input("Hedef alış fiyatı $ (Opsiyonel, boş bırakabilirsiniz): ").strip()
            hedef_val = float(hedef.replace("$", "").replace(",", ".")) if hedef else None

            try:
                baglanti = psycopg2.connect(DB_LINK)
                imlec = baglanti.cursor()
                imlec.execute("""
                    INSERT INTO takip_listesi (esya, hedef_fiyat) 
                    VALUES (%s, %s)
                    ON CONFLICT (esya) DO UPDATE SET hedef_fiyat = EXCLUDED.hedef_fiyat;
                """, (ad, hedef_val))
                baglanti.commit()
                imlec.close()
                baglanti.close()
                print(f"✅ '{ad}' başarıyla takip listenize eklendi!")
            except Exception as e:
                print(f"❌ Eklenirken hata: {e}")

        elif secim == "4":
            takip_listesi_goruntule()
            esya_id = input("\nSilmek istediğiniz eşyanın 'NO' değerini girin: ").strip()
            if esya_id.isdigit():
                try:
                    baglanti = psycopg2.connect(DB_LINK)
                    imlec = baglanti.cursor()
                    imlec.execute("DELETE FROM takip_listesi WHERE id = %s;", (int(esya_id),))
                    baglanti.commit()
                    imlec.close()
                    baglanti.close()
                    print(f"🗑️ No: {esya_id} olan eşya takip listenizden silindi.")
                except Exception as e:
                    print(f"❌ Silinemedi: {e}")
        elif secim in ["0", "q"]:
            break
        else:
            print("⚠️ Geçersiz seçim!")


# 3. ITEMS.TXT DOSYASINDAN TOPLU YÜKLEME
def dosyadan_toplu_tara():
    dosya_yolu = os.path.join(base_dir, "items.txt")
    if not os.path.exists(dosya_yolu):
        print(f"\n❌ '{dosya_yolu}' dosyası bulunamadı!")
        return

    try:
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            esyalar = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

        if not esyalar:
            print(f"\n📌 '{dosya_yolu}' dosyası boş görünüyor.")
            return

        print(f"\n📄 items.txt dosyasında {len(esyalar)} adet eşya bulundu.")
        toplu_esya_tara(esyalar, scan_wears=False)
    except Exception as e:
        print(f"❌ Dosya okunurken hata: {e}")


# 4. STEAM TRENDLERİNİ TARA
def steam_trendlerini_tara():
    print("\n🌐 Steam Topluluk Pazarından güncel trendler çekiliyor...")
    url = "https://steamcommunity.com/market/search/render/?query=&start=0&count=15&search_descriptions=0&sort_column=popular&sort_dir=desc&appid=730&norender=1"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            sonuclar = res.json().get('results', [])
            trend_esyalar = [x['hash_name'] for x in sonuclar]
            print(f"🔥 Steam'de şu an en popüler {len(trend_esyalar)} eşya bulundu:")
            toplu_esya_tara(trend_esyalar, scan_wears=False)
        else:
            print(f"❌ Steam bağlantı hatası: {res.status_code}")
    except Exception as e:
        print(f"❌ Steam trendleri alınamadı: {e}")


# 5. MANUEL ARAMA MODU
def manuel_arama():
    wear_levels = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]
    print("\n🔍 Manuel Eşya Tarama Modu (Geri dönmek için 'q' tuşuna basın)\n")

    while True:
        user_input = input("Eşya adını girin: ").strip()
        if user_input.lower() == 'q':
            break
        if not user_input:
            continue

        base_name = format_item_name(user_input)
        esya_listesi = [base_name] if "|" not in base_name else [f"{base_name} ({wear})" for wear in wear_levels]
        
        if len(esya_listesi) > 1:
            print(f"\n--- {base_name} İçin Tüm Aşınma Seviyeleri Taranıyor ---")
            
        for esya in esya_listesi:
            tek_esya_tara(esya)
            time.sleep(2.5)
        print("-" * 50)


# ANA MENÜ
def ana_menu():
    veritabani_hazirla()

    while True:
        print("\n" + "╔" + "═" * 58 + "╗")
        print("║        🎮 CS2 PAZAR BOTU & FİYAT KONTROL MERKEZİ         ║")
        print("╠" + "═" * 58 + "╣")
        print("║  1. 🔍 Tek Bir Eşya Fiyatı Ara & Tara (Manuel Arama)     ║")
        print("║  2. ⚡ Hızlı Kategori Paketleri (Tüm Kasalar, Skinler)   ║")
        print("║  3. 📌 Kişisel Takip Listem (Portföy Yönetimi)          ║")
        print("║  4. 📁 items.txt Dosyasından Toplu Tara                 ║")
        print("║  5. 🔥 Steam'de En Çok Satan 15 Trend Eşyayı Tara        ║")
        print("║  0. 🚪 Çıkış                                             ║")
        print("╚" + "═" * 58 + "╝")

        secim = input("Seçiminiz (0-5): ").strip()

        if secim == "1":
            manuel_arama()
        elif secim == "2":
            hizli_paketler_menusu()
        elif secim == "3":
            takip_listesi_menusu()
        elif secim == "4":
            dosyadan_toplu_tara()
        elif secim == "5":
            steam_trendlerini_tara()
        elif secim in ["0", "q", "exit"]:
            print("\n👋 İyi oyunlar! Bot kapatılıyor.")
            break
        else:
            print("⚠️ Geçersiz seçim! Lütfen 0 ile 5 arasında bir sayı girin.")


if __name__ == "__main__":
    ana_menu()