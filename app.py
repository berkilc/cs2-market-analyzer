import os
import sys
from dotenv import load_dotenv

# Windows konsolunda UTF-8 ve emoji desteğini sağla
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# EXE olarak paketlendiğinde .env dosyasının EXE ile aynı klasörde bulunmasını sağla
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(base_dir, '.env')
load_dotenv(env_path)

import main
import analiz


def baglanti_testi():
    """Neon veritabanı bağlantısını test eder."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("\n❌ .env dosyası veya DATABASE_URL bulunamadı!")
        print(f"Lütfen şu konumda bir .env dosyası olduğundan emin olun:\n{env_path}")
        return False
    try:
        conn = analiz.get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM pazar_verileri;")
            adet = cur.fetchone()[0]
        conn.close()
        print(f"\n✅ Neon Bulut Veritabanı Bağlantısı Aktif! (Toplam {adet} kayıt)")
        return True
    except Exception as e:
        print(f"\n❌ Veritabanı bağlantı hatası: {e}")
        return False


def bot_modu():
    """main.py bot tarama döngüsünü başlatır."""
    main.veritabani_hazirla()
    wear_levels = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]
    
    print("\n" + "═" * 60)
    print("🔍 CS2 FİYAT TARAMA VE BULUTA KAYDETME BOTU")
    print("Çıkıp ana menüye dönmek için 'q' yazın.")
    print("═" * 60)

    while True:
        user_input = input("\nEşya adını girin (Örn: 'awp worm god' veya 'gallery case'): ").strip()
        if user_input.lower() == 'q':
            break
        if not user_input:
            continue

        base_name = main.format_item_name(user_input)
        esya_listesi = [base_name] if "|" not in base_name else [f"{base_name} ({wear})" for wear in wear_levels]

        if len(esya_listesi) > 1:
            print(f"\n--- {base_name} İçin Tüm Aşınma Seviyeleri Taranıyor ---")

        for esya in esya_listesi:
            print(f"[{esya}] çekiliyor... ", end="", flush=True)
            fiyat, hacim = main.get_price(esya)

            if fiyat:
                if main.veriyi_buluta_yaz(esya, fiyat, hacim):
                    print(f"Fiyat: {fiyat} | Hacim: {hacim} ( Buluta Kaydedildi)")
            else:
                print(hacim)

            main.time.sleep(2.5)
        print("-" * 50)


def ana_program():
    while True:
        print("\n" + "╔" + "═" * 58 + "╗")
        print("║        🎮 CS2 MARKET ANALYZER & CLOUD TRACKER            ║")
        print("╠" + "═" * 58 + "╣")
        print("║  1. 🔍 CS2 Pazar Fiyatı Tara ve Buluta Kaydet (Bot)      ║")
        print("║  2. 📊 Neon Veritabanı Piyasa & Fiyat Analiz Paneli     ║")
        print("║  3. ⚡ Neon Veritabanı Bağlantısını Test Et              ║")
        print("║  0. 🚪 Çıkış                                             ║")
        print("╚" + "═" * 58 + "╝")

        secim = input("Seçiminiz (0-3): ").strip()

        if secim == "1":
            bot_modu()
        elif secim == "2":
            analiz.ana_analiz_menu()
        elif secim == "3":
            baglanti_testi()
        elif secim in ["0", "q", "exit"]:
            print("\nİyi oyunlar! Uygulama kapatılıyor...")
            break
        else:
            print("⚠️ Geçersiz seçim! Lütfen 0 ile 3 arasında bir değer girin.")


if __name__ == "__main__":
    try:
        ana_program()
    except KeyboardInterrupt:
        print("\n\nProgram kullanıcı tarafından sonlandırıldı.")
    except Exception as e:
        print(f"\n❌ Beklenmedik bir hata oluştu: {e}")
    finally:
        # EXE penceresi hemen kapanmasın diye bekle
        if getattr(sys, 'frozen', False):
            input("\nKapatmak için Enter'a basın...")

