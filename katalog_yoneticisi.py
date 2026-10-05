import os
import sys
import time
import requests
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# .env yükle
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(base_dir, '.env')
load_dotenv(env_path)


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    return psycopg2.connect(db_url)


def tabloyu_hazirla():
    """Neon veritabanında esya_katalogu tablosunu ve indekslerini oluşturur."""
    conn = get_db_connection()
    if not conn:
        print("❌ Veritabanı bağlantısı kurulamadı!")
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS esya_katalogu (
                    id SERIAL PRIMARY KEY,
                    esya_adi VARCHAR(255) UNIQUE NOT NULL,
                    kategori VARCHAR(100),
                    alt_kategori VARCHAR(100),
                    silah VARCHAR(100),
                    nadir_mi BOOLEAN DEFAULT FALSE,
                    gorsel_url TEXT,
                    ekleme_tarihi TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_katalog_esya ON esya_katalogu(esya_adi);
                CREATE INDEX IF NOT EXISTS idx_katalog_kategori ON esya_katalogu(kategori);
                CREATE INDEX IF NOT EXISTS idx_katalog_silah ON esya_katalogu(silah);
            """)
            conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Tablo oluşturma hatası: {e}")
        if conn:
            conn.close()
        return False


def katalogu_indir_ve_yukle(progress_callback=None):
    """
    ByMykel CSGO-API üzerinden tüm CS2 eşyalarını (skinler, aşınmalar, kasalar, eldivenler, bıçaklar)
    çeker ve Neon veritabanına toplu (batch) olarak kaydeder.
    """
    if not tabloyu_hazirla():
        return 0, "Veritabanı tablosu hazırlanamadı."

    if progress_callback:
        progress_callback("🌐 CS2 API üzerinden eşya verileri indiriliyor...", 10)

    try:
        # 1. Skinler (Silahlar, Bıçaklar, Eldivenler)
        skins_url = 'https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en/skins.json'
        res_skins = requests.get(skins_url, timeout=25).json()

        # 2. Kasalar ve Kapsüller
        crates_url = 'https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en/crates.json'
        res_crates = requests.get(crates_url, timeout=25).json()

        if progress_callback:
            progress_callback(f"📦 {len(res_skins)} skin ve {len(res_crates)} kasa işleniyor...", 40)

        kayitlar_dict = {}

        # Kasaları ekle
        for c in res_crates:
            c_name = c.get('name')
            if not c_name:
                continue
            c_type = c.get('type') or 'Kasa'
            kayitlar_dict[c_name.strip()] = (
                c_name.strip(),
                'Kasa & Kapsül',
                c_type,
                'Kasa',
                False,
                c.get('image')
            )

        # Skinleri ve tüm aşınma seviyelerini ekle
        for s in res_skins:
            base_name = s.get('name')
            if not base_name:
                continue

            wears = s.get('wears', [])
            weapon = s.get('weapon', {}).get('name') if isinstance(s.get('weapon'), dict) else str(s.get('weapon') or '')
            raw_cat = s.get('category', {}).get('name') if isinstance(s.get('category'), dict) else str(s.get('category') or 'Skin')
            
            # Kategori Türkçeleştirme & Düzenleme
            kategori_map = {
                'Rifles': 'Tüfekler',
                'Pistols': 'Tabancalar',
                'Knives': 'Bıçaklar',
                'Gloves': 'Eldivenler',
                'SMGs': 'Hafif Makineliler',
                'Heavy': 'Ağır Silahlar',
                'Sniper Rifles': 'Keskin Nişancı'
            }
            kategori = kategori_map.get(raw_cat, raw_cat)

            rarity = s.get('rarity', {}).get('name') if isinstance(s.get('rarity'), dict) else 'Normal'
            image = s.get('image')
            is_rare = 'Covert' in rarity or 'Extraordinary' in rarity or 'Knives' in raw_cat or 'Gloves' in raw_cat

            if wears:
                for w in wears:
                    w_name = w.get('name')
                    full_name = f"{base_name} ({w_name})"
                    kayitlar_dict[full_name.strip()] = (
                        full_name.strip(),
                        kategori,
                        rarity,
                        weapon,
                        is_rare,
                        image
                    )
            else:
                kayitlar_dict[base_name.strip()] = (
                    base_name.strip(),
                    kategori,
                    rarity,
                    weapon,
                    is_rare,
                    image
                )

        kayitlar = list(kayitlar_dict.values())

        if progress_callback:
            progress_callback(f"💾 {len(kayitlar)} adet tekil eşya Neon Bulut veritabanına yazılıyor...", 70)

        # Neon DB'ye Toplu Ekleme (execute_values ile tek transaction)
        conn = get_db_connection()
        with conn.cursor() as cur:
            query = """
                INSERT INTO esya_katalogu 
                (esya_adi, kategori, alt_kategori, silah, nadir_mi, gorsel_url)
                VALUES %s
                ON CONFLICT (esya_adi) DO UPDATE SET
                    kategori = EXCLUDED.kategori,
                    alt_kategori = EXCLUDED.alt_kategori,
                    silah = EXCLUDED.silah,
                    nadir_mi = EXCLUDED.nadir_mi,
                    gorsel_url = EXCLUDED.gorsel_url;
            """
            execute_values(cur, query, kayitlar, page_size=1000)
            conn.commit()

            cur.execute("SELECT COUNT(*) FROM esya_katalogu;")
            toplam = cur.fetchone()[0]

        conn.close()

        if progress_callback:
            progress_callback(f"✅ Başarılı! Toplam {toplam} eşya kataloğa kaydedildi.", 100)

        return toplam, "Başarılı"

    except Exception as e:
        if progress_callback:
            progress_callback(f"❌ Hata: {e}", 0)
        return 0, str(e)


def katalog_ara(arama_metni, limit=15):
    """Veritabanındaki katalogdan eşya arar (Çoklu kelime ve otomatik tamamlama desteği)."""
    if not arama_metni or len(arama_metni.strip()) < 2:
        return []
    
    kelimeler = [k.strip() for k in arama_metni.replace("|", " ").split() if k.strip()]
    if not kelimeler:
        return []

    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        where_clauses = ["esya_adi ILIKE %s" for _ in kelimeler]
        where_sql = " AND ".join(where_clauses)
        params = [f"%{k}%" for k in kelimeler]
        params.append(limit)

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT esya_adi, kategori, alt_kategori, silah, gorsel_url
                FROM esya_katalogu
                WHERE {where_sql}
                ORDER BY esya_adi ASC
                LIMIT %s;
            """, tuple(params))
            sonuclar = cur.fetchall()
        conn.close()
        return sonuclar
    except Exception as e:
        print("Arama Hatası:", e)
        return []


def kategori_istatistikleri():
    """Katalogdaki kategorileri ve eşya sayılarını döner."""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT kategori, COUNT(*) as adet
                FROM esya_katalogu
                GROUP BY kategori
                ORDER BY adet DESC;
            """)
            stats = cur.fetchall()
        conn.close()
        return stats
    except Exception:
        return []


def kategori_esyalarini_al(kategori_adi, limit=500):
    """Belirli bir kategorideki eşyaların isimlerini döner."""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT esya_adi
                FROM esya_katalogu
                WHERE kategori = %s
                ORDER BY esya_adi ASC
                LIMIT %s;
            """, (kategori_adi, limit))
            rows = [r[0] for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def parse_price_str(raw):
    """Fiyat metninden sayısal değeri ayıklar ($1.49 -> 1.49)."""
    if not raw:
        return None
    import re
    match = re.search(r'[\d.,]+', raw)
    if not match:
        return None
    val = match.group(0)
    if ',' in val and '.' in val:
        val = val.replace(',', '')
    elif ',' in val and '.' not in val:
        val = val.replace(',', '.')
    try:
        return float(val)
    except ValueError:
        return None


def steam_populer_esyalar(adet=50, progress_callback=None):
    """
    Steam Pazar Arama motorundan en popüler eşyaları tek seferde 10'arlı paketler halinde çeker.
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    esyalar = []
    start = 0
    count_per_req = 10

    while len(esyalar) < adet:
        url = f"https://steamcommunity.com/market/search/render/?query=&start={start}&count={count_per_req}&search_descriptions=0&sort_column=popular&sort_dir=desc&appid=730&norender=1"
        try:
            res = requests.get(url, headers=headers, timeout=12)
            if res.status_code != 200:
                break
            data = res.json()
            results = data.get("results", [])
            if not results:
                break

            for item in results:
                name = item.get("hash_name") or item.get("name")
                price_text = item.get("sell_price_text") or item.get("sale_price_text")
                num_listings = item.get("sell_listings")
                icon_url = item.get("asset_description", {}).get("icon_url")
                img = f"https://community.cloudflare.steamstatic.com/economy/image/{icon_url}" if icon_url else None

                p_val = parse_price_str(price_text)
                esyalar.append({
                    "esya": name,
                    "fiyat": price_text,
                    "fiyat_sayisal": p_val,
                    "hacim": f"{num_listings:,} adet" if num_listings else "Bilinmiyor",
                    "hacim_sayisal": num_listings,
                    "gorsel": img
                })
                if len(esyalar) >= adet:
                    break

            start += len(results)
            if progress_callback:
                progress_callback(f"🔥 {len(esyalar)}/{adet} popüler eşya çekildi...", int((len(esyalar) / adet) * 100))
            time.sleep(0.8)  # Nazik bekleme
        except Exception as e:
            print("Steam Çekme Hatası:", e)
            break

    return esyalar


def steam_populer_tara_ve_kaydet(adet=50, progress_callback=None):
    """
    Steam'deki en popüler eşyaları çeker ve Neon pazar_verileri tablosuna kaydeder.
    """
    esyalar = steam_populer_esyalar(adet, progress_callback)
    if not esyalar:
        return 0, []

    kayit_tarihi = time.strftime("%Y-%m-%d")
    kayit_saati = time.strftime("%H:%M:%S")

    conn = get_db_connection()
    if not conn:
        return len(esyalar), esyalar

    try:
        with conn.cursor() as cur:
            insert_rows = [
                (
                    kayit_tarihi,
                    kayit_saati,
                    e['esya'],
                    e['fiyat'],
                    e['hacim'],
                    e['fiyat_sayisal'],
                    e['hacim_sayisal'],
                    'USD'
                )
                for e in esyalar if e.get('fiyat')
            ]
            query = """
                INSERT INTO pazar_verileri 
                (tarih, saat, esya, fiyat, hacim, fiyat_sayisal, hacim_sayisal, para_birimi)
                VALUES %s;
            """
            execute_values(cur, query, insert_rows)
            conn.commit()
        conn.close()
    except Exception as e:
        print("DB Kayıt Hatası:", e)
        if conn:
            conn.close()

    return len(esyalar), esyalar


if __name__ == "__main__":
    print("🚀 CS2 Eşya Kataloğu İndirici Başlatılıyor...")
    def yazdir(mesaj, yuzde):
        print(f"[{yuzde}%] {mesaj}")

    adet, mesaj = katalogu_indir_ve_yukle(yazdir)
    print(f"\nİşlem Tamamlandı: {adet} eşya eklendi. Mesaj: {mesaj}")
    print("\n--- Kategori İstatistikleri ---")
    for s in kategori_istatistikleri():
        print(f" • {s['kategori']}: {s['adet']} adet")
