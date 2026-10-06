import os
import sys
import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# .env yükle
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(env_path)


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    try:
        return psycopg2.connect(db_url)
    except Exception:
        return None


def esya_fiyat_gecmisi_al(esya_adi: str):
    """
    Neon veritabanındaki pazar_verileri tablosundan eşyaya ait tüm geçmiş fiyat ve hacim verilerini çeker.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return []

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, tarih, saat, esya, fiyat, hacim, fiyat_sayisal, hacim_sayisal, kayit_tarihi
                FROM pazar_verileri
                WHERE esya = %s AND fiyat_sayisal IS NOT NULL
                ORDER BY kayit_tarihi ASC;
            """, (esya_adi,))
            rows = cur.fetchall()

            # Tam eşleşme boşsa, benzer isimle (ILIKE) tekrar dene
            if not rows:
                cur.execute("""
                    SELECT id, tarih, saat, esya, fiyat, hacim, fiyat_sayisal, hacim_sayisal, kayit_tarihi
                    FROM pazar_verileri
                    WHERE esya ILIKE %s AND fiyat_sayisal IS NOT NULL
                    ORDER BY kayit_tarihi ASC;
                """, (f"%{esya_adi}%",))
                rows = cur.fetchall()

        conn.close()
        return rows
    except Exception as e:
        print("Fiyat Geçmişi Çekme Hatası:", e)
        return []


def grafik_istatistikleri_hesapla(rows):
    """Fiyat listesinden istatistikleri çıkarır."""
    if not rows:
        return {
            "toplam_kayit": 0,
            "guncel_fiyat": 0.0,
            "en_dusuk": 0.0,
            "en_yuksek": 0.0,
            "ortalama": 0.0,
            "degisim_yuzde": 0.0,
            "son_hacim": "Yok"
        }

    prices = [float(r['fiyat_sayisal']) for r in rows if r.get('fiyat_sayisal') is not None]
    if not prices:
        return {"toplam_kayit": 0, "guncel_fiyat": 0.0, "en_dusuk": 0.0, "en_yuksek": 0.0, "ortalama": 0.0, "degisim_yuzde": 0.0, "son_hacim": "Yok"}

    first_p = prices[0]
    last_p = prices[-1]
    change_pct = ((last_p - first_p) / first_p * 100) if first_p > 0 else 0.0
    son_hacim = rows[-1].get('hacim') or "Yok"

    return {
        "toplam_kayit": len(prices),
        "guncel_fiyat": last_p,
        "en_dusuk": min(prices),
        "en_yuksek": max(prices),
        "ortalama": sum(prices) / len(prices),
        "degisim_yuzde": change_pct,
        "son_hacim": son_hacim
    }


def fiyat_grafigi_ciz(rows, esya_adi: str, tema_rengi: str = "#00d26a", figsize=(7.2, 3.8)):
    """
    Modern koyu temalı Matplotlib figürü üretir.
    Tkinter içine gömülmeye hazır `fig` nesnesi döner.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=100)
    
    # Koyu arkaplan renkleri
    bg_color = "#131620"
    card_bg = "#181a26"
    text_color = "#9aa5b1"
    grid_color = "#252838"

    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(card_bg)

    if not rows or len(rows) == 0:
        # Kayıt bulunamadı durumu
        ax.text(
            0.5, 0.5, 
            "Veritabanında henüz kayıtlı fiyat verisi bulunmuyor.\n'Fiyatı Şimdi Güncelle' butonuna basarak ilk kaydı alabilirsiniz.",
            horizontalalignment='center', verticalalignment='center',
            transform=ax.transAxes, color="#8d99ae", fontsize=11, fontweight="bold"
        )
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color(grid_color)
        fig.tight_layout()
        return fig

    # Verileri hazırla
    dates = []
    prices = []
    for r in rows:
        d = r.get('kayit_tarihi')
        if not d:
            t = r.get('tarih')
            s = r.get('saat')
            if t:
                try:
                    d = datetime.datetime.combine(t, s if s else datetime.time())
                except Exception:
                    d = datetime.datetime.now()
            else:
                d = datetime.datetime.now()
        dates.append(d)
        prices.append(float(r['fiyat_sayisal']))

    # Tek kayıt varsa güzel bir nokta ve düz kılavuz çizgisi çiz
    if len(prices) == 1:
        single_p = prices[0]
        ax.axhline(single_p, color=tema_rengi, linestyle="--", linewidth=1.5, alpha=0.7)
        ax.plot(dates, prices, marker='o', markersize=9, color=tema_rengi, markerfacecolor='#ffffff', markeredgewidth=2)
        ax.text(
            dates[0], single_p * 1.01, f"  ${single_p:.2f} (Tek Kayıt)",
            color="#ffffff", fontsize=11, fontweight="bold", verticalalignment='bottom'
        )
        ax.set_ylim(single_p * 0.9, single_p * 1.1)
    else:
        # Çizgi grafiği ve yumuşak dolgu
        ax.plot(dates, prices, color=tema_rengi, linewidth=2.4, marker='o', markersize=5, markerfacecolor='#ffffff', markeredgewidth=1.5, label="Fiyat ($)")
        min_p = min(prices)
        ax.fill_between(dates, prices, min_p * 0.98, color=tema_rengi, alpha=0.18)

        # En Yüksek ve En Düşük Noktaları Vurgula
        max_idx = prices.index(max(prices))
        min_idx = prices.index(min(prices))

        ax.annotate(
            f"Zirve: ${prices[max_idx]:.2f}",
            (dates[max_idx], prices[max_idx]),
            textcoords="offset points", xytext=(0, 10), ha='center',
            fontsize=8.5, fontweight='bold', color='#2ecc71',
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#131620", edgecolor="#2ecc71", alpha=0.85)
        )

        if max_idx != min_idx:
            ax.annotate(
                f"Dip: ${prices[min_idx]:.2f}",
                (dates[min_idx], prices[min_idx]),
                textcoords="offset points", xytext=(0, -16), ha='center',
                fontsize=8.5, fontweight='bold', color='#e74c3c',
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#131620", edgecolor="#e74c3c", alpha=0.85)
            )

    # Eksen Biçimlendirme
    ax.tick_params(colors=text_color, labelsize=8.5)
    ax.yaxis.set_major_formatter('${x:,.2f}')

    if len(dates) > 1:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b %H:%M'))
        fig.autofmt_xdate(rotation=25)

    ax.grid(True, linestyle='--', alpha=0.35, color=grid_color)
    for spine in ax.spines.values():
        spine.set_color(grid_color)

    ax.set_title(f"{esya_adi} - Fiyat Değişim Grafiği ($)", color="#ffffff", fontsize=12, fontweight="bold", pad=12)
    fig.tight_layout()
    return fig

