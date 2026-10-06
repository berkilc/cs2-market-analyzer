import os
import io
import sys
import hashlib
import threading
import requests
from PIL import Image
import customtkinter as ctk
from dotenv import load_dotenv

# Temel dizin ve cache klasörü
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(env_path)

CACHE_DIR = os.path.join(BASE_DIR, "cache", "images")
os.makedirs(CACHE_DIR, exist_ok=True)

# Bellek içi önbellek (Bellekte hazır bekleyen CTkImage nesneleri)
_MEMORY_CACHE = {}
_LOCK = threading.Lock()


def esya_gorsel_url_bul(esya_adi: str) -> str:
    """
    Veritabanındaki esya_katalogu tablosundan eşyaya ait Steam CDN görsel URL'sini bulur.
    Aşınma (Field-Tested vb.) veya StatTrak durumlarında otomatik ana eşya görselini eşleştirir.
    """
    if not esya_adi:
        return None
    try:
        import re
        import psycopg2
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return None
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cur:
            # 1. Tam eşleşme
            cur.execute("SELECT gorsel_url FROM esya_katalogu WHERE esya_adi = %s AND gorsel_url IS NOT NULL LIMIT 1;", (esya_adi,))
            row = cur.fetchone()
            if row and row[0]:
                conn.close()
                return row[0]

            # 2. Aşınma durumlarını ve özel işaretleri temizleyerek dene (AK-47 | Redline (Field-Tested) -> AK-47 | Redline)
            clean = re.sub(r'\(.*?\)', '', esya_adi).replace("StatTrak™", "").replace("StatTrak", "").replace("★", "").strip()
            if clean:
                cur.execute("SELECT gorsel_url FROM esya_katalogu WHERE esya_adi ILIKE %s AND gorsel_url IS NOT NULL LIMIT 1;", (f"%{clean}%",))
                row = cur.fetchone()
                if row and row[0]:
                    conn.close()
                    return row[0]
        conn.close()
    except Exception as e:
        print("Görsel arama hatası:", e)
    return None


def _get_cache_path(url: str) -> str:
    """URL için yerel dosya yolu üretir (MD5 hash kullanarak)."""
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.png")


def varsayilan_placeholder(boyut=(200, 150)):
    """Görsel yüklenirken veya bulunamadığında gösterilecek modern placeholder."""
    cache_key = f"placeholder_{boyut[0]}_{boyut[1]}"
    with _LOCK:
        if cache_key in _MEMORY_CACHE:
            return _MEMORY_CACHE[cache_key]

    img = Image.new("RGBA", boyut, (24, 26, 36, 255))
    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=boyut)
    with _LOCK:
        _MEMORY_CACHE[cache_key] = ctk_img
    return ctk_img


def gorsel_getir_async(url: str, boyut=(220, 160), callback=None):
    """
    Verilen URL'deki eşya görselini asenkron (arkaplanda) indirir veya yerel önbellekten alır.
    Arayüzün kilitlenmesini kesinlikle engeller.
    
    :param url: Steam Akamai CDN görsel bağlantısı
    :param boyut: (genişlik, yükseklik) tuple'ı
    :param callback: Görsel hazır olduğunda çağrılacak fonksiyon: callback(ctk_image)
    """
    if not url:
        if callback:
            callback(varsayilan_placeholder(boyut))
        return

    cache_key = f"{url}_{boyut[0]}_{boyut[1]}"

    # 1. Bellek önbelleğinde var mı?
    with _LOCK:
        if cache_key in _MEMORY_CACHE:
            if callback:
                callback(_MEMORY_CACHE[cache_key])
            return

    # 2. Disk önbelleğinde var mı?
    disk_path = _get_cache_path(url)
    if os.path.exists(disk_path):
        try:
            img = Image.open(disk_path).convert("RGBA")
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=boyut)
            with _LOCK:
                _MEMORY_CACHE[cache_key] = ctk_img
            if callback:
                callback(ctk_img)
            return
        except Exception:
            pass

    # 3. Arka planda web'den indir
    def _download_worker():
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                raw_bytes = resp.content
                img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
                # Diske kaydet (gelecekte internet olmadan da hızlıca açılsın)
                try:
                    img.save(disk_path, format="PNG")
                except Exception:
                    pass

                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=boyut)
                with _LOCK:
                    _MEMORY_CACHE[cache_key] = ctk_img
                if callback:
                    callback(ctk_img)
            else:
                if callback:
                    callback(varsayilan_placeholder(boyut))
        except Exception as e:
            print(f"Görsel indirme hatası: {e}")
            if callback:
                callback(varsayilan_placeholder(boyut))

    thread = threading.Thread(target=_download_worker, daemon=True)
    thread.start()
