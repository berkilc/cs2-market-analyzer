import sys
import requests
import urllib.parse
import time
import psycopg2
from datetime import datetime

# Windows konsolunda Türkçe karakter ve emoji desteği
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import os
from dotenv import load_dotenv

# .env dosyasındaki ortam değişkenlerini yükle
load_dotenv()

# --- VERİTABANI BAĞLANTISI ---
# Güvenlik için bağlantı adresi .env dosyasından çekilir
DB_LINK = os.getenv("DATABASE_URL")


def veritabani_hazirla():
    # Bot ilk çalıştığında buluta bağlanıp tablosu yoksa otomatik oluşturur
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
                hacim VARCHAR(50)
            );
        """)
        baglanti.commit()
        imlec.close()
        baglanti.close()
        print("✅ Bulut Veritabanı Bağlantısı Başarılı! Sistem Hazır.\n")
    except Exception as e:
        print(f"❌ Veritabanı Hatası: {e}")
        print("Lütfen DB_LINK adresini doğru yapıştırdığınızdan emin olun.")
        exit()

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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get('lowest_price'), data.get('volume', 'Yok')
        elif response.status_code == 429:
            return None, "Hata: Engellendik (429)"
        return None, "Pazarda bulunamadı."
    except Exception as e:
        return None, f"Sistemsel Hata: {e}"

def veriyi_buluta_yaz(esya, fiyat, hacim):
    try:
        zaman = datetime.now()
        tarih = zaman.strftime("%Y-%m-%d")
        saat = zaman.strftime("%H:%M:%S")
        
        baglanti = psycopg2.connect(DB_LINK)
        imlec = baglanti.cursor()
        
        # Güvenli SQL sorgusu ile veriyi buluta fırlatıyoruz
        sorgu = "INSERT INTO pazar_verileri (tarih, saat, esya, fiyat, hacim) VALUES (%s, %s, %s, %s, %s)"
        imlec.execute(sorgu, (tarih, saat, esya, fiyat, hacim))
        
        baglanti.commit()
        imlec.close()
        baglanti.close()
        return True
    except Exception as e:
        print(f"Veri kaydedilemedi: {e}")
        return False

if __name__ == "__main__":
    # Program başlangıcı
    veritabani_hazirla()
    print("CS2 Bulut Tabanlı Pazar Botuna Hoş Geldiniz (Çıkmak için 'q' tuşuna basın)\n")


    wear_levels = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]

    while True:
        user_input = input("Eşya adını girin: ")
        if user_input.lower() == 'q':
            break
        if not user_input.strip():
            continue

        base_name = format_item_name(user_input)
        esya_listesi = [base_name] if "|" not in base_name else [f"{base_name} ({wear})" for wear in wear_levels]
        
        if len(esya_listesi) > 1:
            print(f"\n--- {base_name} İçin Tüm Aşınma Seviyeleri Taranıyor ---")
            
        for esya in esya_listesi:
            print(f"[{esya}] çekiliyor... ", end="", flush=True)
            fiyat, hacim = get_price(esya)
            
            if fiyat:
                if veriyi_buluta_yaz(esya, fiyat, hacim):
                    print(f"Fiyat: {fiyat} | Hacim: {hacim} ( Buluta Kaydedildi)")
            else:
                print(hacim)
                
            time.sleep(3)
        print("-" * 40)