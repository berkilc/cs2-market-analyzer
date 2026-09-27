import requests
import urllib.parse
import time

def get_price(item_name):
    # Steam CS2 App ID ve Dolar para birimi
    url = f"https://steamcommunity.com/market/priceoverview/?appid=730&currency=1&market_hash_name={urllib.parse.quote(item_name)}"
    
    # Steam'in bizi bot sanıp engellememesi için tarayıcı kimliği gönderiyoruz
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return f"Fiyat: {data.get('lowest_price')} | Hacim: {data.get('volume')}"
        elif response.status_code == 429:
            return "Hata: Steam çok hızlı istek attığımız için kısa süreli engelledi."
        return "Veri çekilemedi."
    except Exception as e:
        return f"Sistemsel Hata: {e}"

# Takip edilecek eşyalar
items = [
    "AK-47 | Redline (Field-Tested)",
    "Gallery Case"
]

print("CS2 Pazar Botu Çalışıyor...\n")
for item in items:
    print(f"[{item}] fiyatı çekiliyor...")
    print(get_price(item))
    print("-" * 40)
    time.sleep(3) # Steam arka arkaya istek atınca engellediği için 3 saniye bekletiyoruz