# 📈 CS2 Market Analyzer & Cloud Price Tracker

Counter-Strike 2 Steam Topluluk Pazarı için otomatik fiyat takip, karşılaştırma, grafik arayüzlü (GUI) ve **Neon Console (PostgreSQL)** bulut veritabanı entegreli masaüstü piyasa analiz sistemi.

## 🚀 Özellikler
- 🖥️ **Modern Masaüstü Grafik Arayüzü (GUI):** Siyah konsol ekranı yerine modern, koyu temalı pencereli masaüstü uygulaması.
- 🔍 **Canlı Steam Taraması:** Eşya adını yazıp tek tıkla tüm aşınma seviyelerini tarama ve değişim rozetlerini (📉 DÜŞTÜ / 📈 ARTTI) görme.
- 📋 **Neon Cloud Veritabanı Tablosu:** Tüm taranan eşyaları filtreleme, min/maks/güncel fiyatları ve son kayıt tarih/saatini listeleme.
- 🧠 **Piyasa Analiz Motoru:** Aşınma arbitrajı ve likidite risk analizleri.
- 📦 **Taşınabilir Standalone EXE:** Python kurulumu gerektirmeden çift tıkla çalışan `.exe` sürümü.

## 🛠️ Teknolojiler
- **Python 3**
- **CustomTkinter** (Modern Dark Mode Masaüstü Arayüzü)
- **Neon Serverless PostgreSQL**
- **psycopg2** & **python-dotenv**
- **Requests**

## ⚙️ Kurulum ve Çalıştırma

### 1. Masaüstü Uygulamasını (EXE) Çalıştırma
`dist` klasöründeki **`CS2_Market_Analyzer.exe`** dosyasına çift tıklamanız yeterlidir!

### 2. Kaynak Koddan Çalıştırma
```bash
pip install -r requirements.txt
python gui_app.py
```
*(Konsol sürümünü çalıştırmak isterseniz: `python app.py`)*
