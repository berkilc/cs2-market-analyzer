# 📈 CS2 Market Analyzer & Cloud Price Tracker

Counter-Strike 2 Steam Topluluk Pazarı için otomatik fiyat takip, karşılaştırma ve **Neon Console (PostgreSQL)** bulut veritabanı entegreli piyasa analiz sistemi.

## 🚀 Özellikler
- **Gerçek Zamanlı Steam Verisi:** En güncel pazar fiyatını ve 24 saatlik satış hacmini Steam API üzerinden çeker.
- **Neon Cloud PostgreSQL Entegrasyonu:** Tüm fiyat geçmişini bulutta güvenli ve sayısal formatta saklar.
- **Piyasa İstatistik & Analiz Motoru (`analiz.py`):** Arbitraj, aşınma tutarsızlıkları ve likidite analizleri yapar.
- **🐦 Canlı CS2 Tweets & Haber Akışı:** `@CounterStrike` resmi X tweetleri ve Valve Release Notes bültenleri anlık olarak fotoğraflı ve filtrelenebilir listelenir.
- **🚨 Yatırımcı Alarmı & Windows Yerel Bildirimleri:** Yeni tweet veya güncelleme geldiğinde sesli alarm çalar ve sağ altta fotoğraflı Windows yerel bildirimi (Toast) gösterir.
- **Steam 429 Koruması:** Otomatik bekleme ve tekrar deneme mekanizması.

## 🛠️ Teknolojiler
- **Python 3**
- **CustomTkinter**
- **Neon Serverless Postgres (psycopg2)**
- **win11toast** & **Pillow**
- **Requests**


## ⚙️ Kurulum ve Çalıştırma

1. **Gereksinimleri Yükleyin:**
   ```bash
   pip install -r requirements.txt
   ```

2. **`.env` Dosyasını Oluşturun:**
   Proje ana dizininde `.env` dosyası oluşturup Neon bağlantı linkinizi ekleyin:
   ```env
   DATABASE_URL="postgresql://kullanici:sifre@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require"
   ```

3. **Pazar Botunu Çalıştırın:**
   ```bash
   python main.py
   ```

4. **Veritabanı Analizini Başlatın:**
   ```bash
   python analiz.py
   ```

