import os
import sys
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Windows konsolunda UTF-8 / Emoji karakter desteğini sağla
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# .env dosyasından DATABASE_URL al
load_dotenv()
DB_LINK = os.getenv("DATABASE_URL")

if not DB_LINK:
    print("❌ HATA: DATABASE_URL .env dosyasında bulunamadı!")
    print("Lütfen .env dosyanızı kontrol edin.")
    sys.exit(1)


def get_db_connection():
    return psycopg2.connect(DB_LINK)


def veritabani_senkronize_et(conn):
    """
    Eğer ana scriptten sayısal olmayan eski/yeni kayıtlar girildiyse
    fiyat_sayisal ve hacim_sayisal sütunlarını otomatik senkronize eder.
    """
    import re
    with conn.cursor() as cur:
        cur.execute("SELECT id, fiyat, hacim FROM pazar_verileri WHERE fiyat_sayisal IS NULL OR hacim_sayisal IS NULL;")
        rows = cur.fetchall()
        for rid, f_str, h_str in rows:
            p_match = re.search(r'[\d.,]+', f_str or '')
            p_val = None
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
            if h_str and h_str.lower() not in ['yok', 'none', '-']:
                clean_v = re.sub(r'[^\d]', '', h_str)
                v_val = int(clean_v) if clean_v else None

            cur.execute("""
                UPDATE pazar_verileri 
                SET fiyat_sayisal = COALESCE(fiyat_sayisal, %s),
                    hacim_sayisal = COALESCE(hacim_sayisal, %s),
                    kayit_tarihi = COALESCE(kayit_tarihi, CURRENT_TIMESTAMP)
                WHERE id = %s;
            """, (p_val, v_val, rid))
        conn.commit()


def genel_ozet(conn):
    """Veritabanındaki genel pazar durumunu ve istatistikleri özetler."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                COUNT(*) as toplam_kayit,
                COUNT(DISTINCT esya) as benzersiz_esya,
                MIN(fiyat_sayisal) as en_ucuz_fiyat,
                MAX(fiyat_sayisal) as en_pahali_fiyat,
                ROUND(AVG(fiyat_sayisal), 2) as genel_ortalama_fiyat,
                SUM(hacim_sayisal) as toplam_hacim
            FROM pazar_verileri
            WHERE fiyat_sayisal IS NOT NULL;
        """)
        stats = cur.fetchone()

        cur.execute("SELECT esya, fiyat_sayisal FROM pazar_verileri WHERE fiyat_sayisal IS NOT NULL ORDER BY fiyat_sayisal DESC LIMIT 1;")
        en_pahali = cur.fetchone()

        cur.execute("SELECT esya, fiyat_sayisal FROM pazar_verileri WHERE fiyat_sayisal IS NOT NULL ORDER BY fiyat_sayisal ASC LIMIT 1;")
        en_ucuz = cur.fetchone()


        cur.execute("SELECT esya, hacim_sayisal FROM pazar_verileri ORDER BY hacim_sayisal DESC NULLS LAST LIMIT 1;")
        en_likit = cur.fetchone()

        print("\n" + "═" * 70)
        print("📊 NEON BULUT VERİTABANI - GENEL PİYASA ÖZETİ")
        print("═" * 70)
        print(f"📦 Toplam Fiyat Kaydı : {stats['toplam_kayit']} adet")
        print(f"🎯 Takip Edilen Eşya   : {stats['benzersiz_esya']} farklı eşya")
        print(f"💰 Ortalama Fiyat      : ${stats['genel_ortalama_fiyat']}")
        print(f"💎 En Pahalı Eşya      : {en_pahali['esya']} (${en_pahali['fiyat_sayisal']})")
        print(f"🪙 En Ucuz Eşya        : {en_ucuz['esya']} (${en_ucuz['fiyat_sayisal']})")
        if en_likit:
            print(f"🔥 En Çok İşlem Gören  : {en_likit['esya']} (24s Hacim: {en_likit['hacim_sayisal']} adet)")
        print("═" * 70)


def tum_esyalar_tablosu(conn):
    """Her eşya için en güncel fiyat, ortalama ve hacim tablosunu listeler."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            WITH son_kayitlar AS (
                SELECT DISTINCT ON (esya)
                    esya,
                    fiyat_sayisal as guncel_fiyat,
                    hacim_sayisal as guncel_hacim,
                    kayit_tarihi as son_tarih,
                    saat as son_saat
                FROM pazar_verileri
                ORDER BY esya, id DESC
            ),
            istatistikler AS (
                SELECT 
                    esya,
                    COUNT(*) as kayit_adet,
                    MIN(fiyat_sayisal) as min_f,
                    MAX(fiyat_sayisal) as max_f,
                    ROUND(AVG(fiyat_sayisal), 2) as avg_f
                FROM pazar_verileri
                WHERE fiyat_sayisal IS NOT NULL
                GROUP BY esya
            )
            SELECT 
                s.esya,
                s.guncel_fiyat,
                s.guncel_hacim,
                i.min_f,
                i.max_f,
                i.avg_f,
                i.kayit_adet,
                s.son_tarih,
                s.son_saat
            FROM son_kayitlar s
            JOIN istatistikler i ON s.esya = i.esya
            ORDER BY s.guncel_fiyat DESC NULLS LAST;
        """)
        rows = cur.fetchall()

        print("\n" + "═" * 90)
        print(f"{'EŞYA ADI':<38} | {'GÜNCEL':<8} | {'MİN':<8} | {'MAKS':<8} | {'HACİM (24S)':<11} | {'KAYIT'}")
        print("─" * 90)

        for r in rows:
            hacim_str = f"{r['guncel_hacim']:,}" if r['guncel_hacim'] is not None else "Yok"
            ad = (r['esya'][:35] + '...') if len(r['esya']) > 38 else r['esya']
            print(f"{ad:<38} | ${r['guncel_fiyat']:<7} | ${r['min_f']:<7} | ${r['max_f']:<7} | {hacim_str:<11} | {r['kayit_adet']} adet")
        print("═" * 90)


def anomali_ve_arbitraj_analizi(conn):
    """
    Aşınma seviyeleri arasındaki fiyat tutarsızlıklarını tespit eder.
    Örn: Well-Worn > Field-Tested veya Battle-Scarred > Minimal Wear.
    """
    wear_order = {
        "Factory New": 1,
        "Minimal Wear": 2,
        "Field-Tested": 3,
        "Well-Worn": 4,
        "Battle-Scarred": 5
    }

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT ON (esya)
                esya,
                fiyat_sayisal,
                hacim_sayisal
            FROM pazar_verileri
            WHERE fiyat_sayisal IS NOT NULL AND esya LIKE '%(%)%'
            ORDER BY esya, id DESC;
        """)
        rows = cur.fetchall()

    gruplar = {}
    import re
    for r in rows:
        m = re.match(r'^(.*?)\s*\((Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)\)$', r['esya'])
        if m:
            base_skin = m.group(1).strip()
            wear = m.group(2)
            if base_skin not in gruplar:
                gruplar[base_skin] = {}
            gruplar[base_skin][wear] = {
                'fiyat': float(r['fiyat_sayisal']),
                'hacim': r['hacim_sayisal']
            }

    print("\n" + "═" * 80)
    print("🧠 AŞINMA SEVİYESİ & FİYAT ANOMALİ / ARBİTRAJ ANALİZİ")
    print("═" * 80)
    anomali_var = False

    for skin, weardata in gruplar.items():
        print(f"\n🔫 {skin}:")
        sirali_wearlar = sorted(weardata.keys(), key=lambda w: wear_order.get(w, 99))
        for w in sirali_wearlar:
            f = weardata[w]['fiyat']
            h = weardata[w]['hacim']
            h_str = f"{h:,}" if h is not None else "Yok"
            print(f"   • {w:<15}: ${f:<7} (24s Hacim: {h_str})")

        for i in range(len(sirali_wearlar)):
            for j in range(i + 1, len(sirali_wearlar)):
                iyi_wear = sirali_wearlar[i]
                kotu_wear = sirali_wearlar[j]
                fiyat_iyi = weardata[iyi_wear]['fiyat']
                fiyat_kotu = weardata[kotu_wear]['fiyat']

                if fiyat_kotu > fiyat_iyi:
                    anomali_var = True
                    fark = fiyat_kotu - fiyat_iyi
                    print(f"   ⚠️  DİKKAT (Piyasa Anomalisi): '{kotu_wear}' (${fiyat_kotu:.2f}), daha temiz olan '{iyi_wear}' (${fiyat_iyi:.2f}) sürümünden ${fark:.2f} daha pahalı!")
                    print(f"       💡 Yorum: '{kotu_wear}' sürümünde pazar stoğu azlığı veya yapay şişirme olabilir. Alıcılar için '{iyi_wear}' çok daha avantajlı!")

    if not anomali_var:
        print("✅ Fiyat sıralamalarında bariz bir tutarsızlık bulunamadı (Tüm aşınmalar normal oranlarda).")
    print("═" * 80)


def likidite_analizi(conn):
    """
    Eşyaları 24 saatlik işlem hacimlerine göre risk ve likidite kategorilerine ayırır.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT ON (esya)
                esya,
                fiyat_sayisal,
                hacim_sayisal
            FROM pazar_verileri
            WHERE hacim_sayisal IS NOT NULL
            ORDER BY esya, id DESC;
        """)
        rows = cur.fetchall()

    print("\n" + "═" * 80)
    print("💧 LİKİDİTE VE TİCARET RİSK ANALİZİ (24s Satış Hacmi)")
    print("═" * 80)

    cok_yuksek = []
    orta = []
    dusuk = []

    for r in rows:
        h = r['hacim_sayisal']
        if h >= 1000:
            cok_yuksek.append(r)
        elif h >= 100:
            orta.append(r)
        else:
            dusuk.append(r)

    print("\n🟢 YÜKSEK LİKİDİTE (Hızlı Alınıp Satılanlar - Düşük Risk):")
    for r in sorted(cok_yuksek, key=lambda x: x['hacim_sayisal'], reverse=True):
        print(f"   • {r['esya']:<38} | Hacim: {r['hacim_sayisal']:,} adet | Fiyat: ${r['fiyat_sayisal']}")

    print("\n🟡 ORTA LİKİDİTE (Dengeli Piyasa):")
    for r in sorted(orta, key=lambda x: x['hacim_sayisal'], reverse=True):
        print(f"   • {r['esya']:<38} | Hacim: {r['hacim_sayisal']:,} adet | Fiyat: ${r['fiyat_sayisal']}")

    print("\n🔴 DÜŞÜK LİKİDİTE (Yavaş Satılanlar - Fiyat Dalgalanmasına Açık):")
    for r in sorted(dusuk, key=lambda x: x['hacim_sayisal'], reverse=True):
        print(f"   • {r['esya']:<38} | Hacim: {r['hacim_sayisal']:,} adet | Fiyat: ${r['fiyat_sayisal']}")

    print("═" * 80)


def tek_esya_gecmisi(conn):
    """İstenen bir eşyanın tüm geçmiş kayıtlarını ve fiyat değişimini listeler."""
    ad = input("\n🔍 Geçmişini görmek istediğiniz eşya adını yazın: ").strip()
    if not ad:
        return

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, esya, fiyat_sayisal, hacim_sayisal, tarih, saat, kayit_tarihi
            FROM pazar_verileri
            WHERE esya ILIKE %s
            ORDER BY id ASC;
        """, (f"%{ad}%",))
        rows = cur.fetchall()

        if not rows:
            print(f"❌ '{ad}' için veritabanında geçmiş kayıt bulunamadı.")
            return

        print("\n" + "═" * 80)
        print(f"📈 FİYAT GEÇMİŞİ: {rows[0]['esya']}")
        print("═" * 80)
        print(f"{'KAYIT ID':<10} | {'TARİH':<12} | {'SAAT':<10} | {'FİYAT ($)':<12} | {'HACİM'}")
        print("─" * 80)

        for r in rows:
            h_str = f"{r['hacim_sayisal']:,}" if r['hacim_sayisal'] is not None else "-"
            print(f"{r['id']:<10} | {str(r['tarih']):<12} | {str(r['saat']):<10} | ${r['fiyat_sayisal']:<11} | {h_str}")
        print("═" * 80)


def ana_analiz_menu():
    print("⏳ Neon Bulut Veritabanına Bağlanılıyor...")
    try:
        conn = get_db_connection()
        veritabani_senkronize_et(conn)
        print("✅ Bağlantı ve Veri Senkronizasyonu Tamamlandı!\n")
    except Exception as e:
        print(f"❌ Veritabanı bağlantı hatası: {e}")
        return

    while True:
        print("\n" + "╔" + "═" * 58 + "╗")
        print("║       📊 NEON VERİTABANI CS2 PİYASA ANALİZ PANELİ        ║")
        print("╠" + "═" * 58 + "╣")
        print("║  1. 📌 Genel Piyasa Özeti (Özet İstatistikler)           ║")
        print("║  2. 📋 Tüm Eşyaların Fiyat & Hacim Tablosu              ║")
        print("║  3. 🧠 Aşınma & Anomali Analizi (Fiyat Tutarsızlıkları)  ║")
        print("║  4. 💧 Likidite Analizi (En Çok / En Az Satılanlar)     ║")
        print("║  5. 🔍 Belirli Bir Eşyanın Geçmiş Kayıtlarını İncele    ║")
        print("║  0. 🚪 Çıkış                                             ║")
        print("╚" + "═" * 58 + "╝")

        secim = input("Seçiminiz (0-5): ").strip()

        if secim == "1":
            genel_ozet(conn)
        elif secim == "2":
            tum_esyalar_tablosu(conn)
        elif secim == "3":
            anomali_ve_arbitraj_analizi(conn)
        elif secim == "4":
            likidite_analizi(conn)
        elif secim == "5":
            tek_esya_gecmisi(conn)
        elif secim in ["0", "q", "exit"]:
            print("\n👋 Analiz panelinden çıkıldı.")
            break
        else:
            print("⚠️ Geçersiz seçim! Lütfen 0 ile 5 arasında bir sayı girin.")

    conn.close()


if __name__ == "__main__":
    ana_analiz_menu()
