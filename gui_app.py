import os
import re
import sys
import threading
import time
import urllib.parse
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import requests

# Windows konsolunda UTF-8 desteği
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# .env konumunu tespit et (EXE veya normal çalışma)
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(base_dir, '.env')
load_dotenv(env_path)

# CustomTkinter Teması
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class CS2MarketApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CS2 Market Analyzer & Cloud Tracker")
        self.geometry("1060x720")
        self.minsize(920, 620)

        self.is_scanning = False
        self.stop_requested = False

        self.db_link = os.getenv("DATABASE_URL")

        self.build_ui()
        self.check_initial_db_status()

    # ------------------ VERİTABANI YARDIMCILARI ------------------
    def get_db_connection(self):
        if not self.db_link:
            return None
        return psycopg2.connect(self.db_link)

    def check_initial_db_status(self):
        threading.Thread(target=self._check_db_thread, daemon=True).start()

    def _check_db_thread(self):
        try:
            conn = self.get_db_connection()
            if not conn:
                self.after(0, lambda: self.status_badge.configure(text="⚠️ Veritabanı Ayarı Yok", text_color="#f39c12"))
                return
            with conn.cursor() as cur:
                # Tablo ve sütunları hazırla
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pazar_verileri (
                        id SERIAL PRIMARY KEY,
                        tarih DATE,
                        saat TIME,
                        esya VARCHAR(255) NOT NULL,
                        fiyat VARCHAR(50),
                        hacim VARCHAR(50),
                        fiyat_sayisal NUMERIC(10, 2),
                        hacim_sayisal INTEGER,
                        para_birimi VARCHAR(10) DEFAULT 'USD',
                        kayit_tarihi TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute("SELECT COUNT(*) FROM pazar_verileri;")
                count = cur.fetchone()[0]
                conn.commit()
            conn.close()

            self.after(0, lambda: self.status_badge.configure(
                text=f"🟢 Neon Cloud Bağlı ({count} Kayıt)", text_color="#2ecc71"
            ))
            # İlk veritabanı tablosunu yükle
            self.after(0, self.refresh_database_table)
        except Exception as e:
            self.after(0, lambda: self.status_badge.configure(
                text="🔴 Neon Bağlantı Hatası", text_color="#e74c3c"
            ))

    # ------------------ STEAM API ------------------
    def format_item_name(self, user_input):
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

    def get_steam_price(self, item_name, currency=1):
        url = f"https://steamcommunity.com/market/priceoverview/?appid=730&currency={currency}&market_hash_name={urllib.parse.quote(item_name)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("success"):
                    return data.get("lowest_price"), data.get("volume", "Yok")
                return None, "Pazarda listeleme yok."
            elif res.status_code == 429:
                return None, "Rate Limit (429)"
            return None, f"Hata ({res.status_code})"
        except Exception as e:
            return None, str(e)

    def parse_numbers(self, fiyat_str, hacim_str):
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

    def get_previous_price(self, esya):
        try:
            conn = self.get_db_connection()
            if not conn:
                return None, None
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT fiyat_sayisal, kayit_tarihi
                    FROM pazar_verileri
                    WHERE esya = %s AND fiyat_sayisal IS NOT NULL
                    ORDER BY id DESC LIMIT 1;
                """, (esya,))
                row = cur.fetchone()
            conn.close()
            if row:
                return float(row[0]), row[1]
        except Exception:
            pass
        return None, None

    def save_price_to_db(self, esya, fiyat_str, hacim_str):
        try:
            p_val, v_val = self.parse_numbers(fiyat_str, hacim_str)
            now = datetime.now()
            tarih = now.strftime("%Y-%m-%d")
            saat = now.strftime("%H:%M:%S")

            conn = self.get_db_connection()
            if not conn:
                return False
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pazar_verileri 
                    (tarih, saat, esya, fiyat, hacim, fiyat_sayisal, hacim_sayisal, para_birimi, kayit_tarihi)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
                """, (tarih, saat, esya, fiyat_str, hacim_str, p_val, v_val, 'USD'))
                conn.commit()
            conn.close()
            return True
        except Exception as e:
            print("DB Kayıt Hatası:", e)
            return False

    # ------------------ ARAYÜZ (UI) TASARIMI ------------------
    def build_ui(self):
        # Üst Başlık Çubuğu
        header_frame = ctk.CTkFrame(self, fg_color="#1e1e24", corner_radius=0, height=65)
        header_frame.pack(fill="x", side="top")

        title_label = ctk.CTkLabel(
            header_frame, 
            text="🎮 CS2 Market Analyzer", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#ffffff"
        )
        title_label.pack(side="left", padx=25, pady=15)

        self.status_badge = ctk.CTkLabel(
            header_frame,
            text="⏳ Neon Bağlantısı Kontrol Ediliyor...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#f39c12"
        )
        self.status_badge.pack(side="right", padx=25, pady=15)

        # Sekmeli Görünüm (Tabview)
        self.tabview = ctk.CTkTabview(self, corner_radius=12)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(15, 20))

        self.tab_scan = self.tabview.add("🔍 Canlı Eşya Tarama")
        self.tab_database = self.tabview.add("📋 Neon Pazar Tablosu")
        self.tab_analytics = self.tabview.add("🧠 Piyasa Analizleri")

        self.setup_scan_tab()
        self.setup_database_tab()
        self.setup_analytics_tab()

    # ------------------ SEKME 1: CANLI TARAMA ------------------
    def setup_scan_tab(self):
        # Arama kutusu alanı
        search_card = ctk.CTkFrame(self.tab_scan, fg_color="#2b2d42", corner_radius=10)
        search_card.pack(fill="x", padx=10, pady=10)

        input_container = ctk.CTkFrame(search_card, fg_color="transparent")
        input_container.pack(fill="x", padx=15, pady=15)

        self.item_entry = ctk.CTkEntry(
            input_container,
            placeholder_text="Eşya adını yazın (Örn: AWP Worm God, AK-47 Redline, Gallery Case)...",
            height=42,
            font=ctk.CTkFont(size=14)
        )
        self.item_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.item_entry.bind("<Return>", lambda e: self.start_scan())

        self.wear_checkbox = ctk.CTkCheckBox(
            input_container, 
            text="Tüm Aşınmaları Tara (FN, MW, FT, WW, BS)", 
            font=ctk.CTkFont(size=12)
        )
        self.wear_checkbox.pack(side="left", padx=10)
        self.wear_checkbox.select()

        self.scan_btn = ctk.CTkButton(
            input_container,
            text="🚀 Fiyatı Tara & Kaydet",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42,
            width=180,
            command=self.start_scan
        )
        self.scan_btn.pack(side="right")

        # Tarama durum çubuğu
        self.progress_bar = ctk.CTkProgressBar(self.tab_scan, mode="indeterminate", height=4)
        self.scan_status_label = ctk.CTkLabel(
            self.tab_scan, 
            text="Aramak istediğiniz eşyayı yukarı yazıp 'Tara & Kaydet' butonuna basın.",
            font=ctk.CTkFont(size=13),
            text_color="#8d99ae"
        )
        self.scan_status_label.pack(anchor="w", padx=15, pady=(5, 5))

        # Sonuç Kartları Alanı
        self.results_scroll = ctk.CTkScrollableFrame(
            self.tab_scan, 
            fg_color="#1a1a24",
            corner_radius=10,
            label_text="📊 Tarama Sonuçları",
            label_font=ctk.CTkFont(size=14, weight="bold")
        )
        self.results_scroll.pack(fill="both", expand=True, padx=10, pady=10)

    def start_scan(self):
        if self.is_scanning:
            return
        item_text = self.item_entry.get().strip()
        if not item_text:
            messagebox.showwarning("Eksik Bilgi", "Lütfen bir eşya adı girin!")
            return

        self.is_scanning = True
        self.scan_btn.configure(state="disabled", text="⏳ Taranıyor...")
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 5))
        self.progress_bar.start()

        # Eski sonuçları temizle
        for widget in self.results_scroll.winfo_children():
            widget.destroy()

        scan_wears = bool(self.wear_checkbox.get())
        threading.Thread(target=self._run_scan_thread, args=(item_text, scan_wears), daemon=True).start()

    def _run_scan_thread(self, user_input, scan_wears):
        base_name = self.format_item_name(user_input)
        wear_levels = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]
        items_to_scan = [base_name] if (not scan_wears or "|" not in base_name) else [f"{base_name} ({w})" for w in wear_levels]

        total = len(items_to_scan)
        for idx, esya in enumerate(items_to_scan, 1):
            self.after(0, lambda e=esya, i=idx, t=total: self.scan_status_label.configure(
                text=f"[{i}/{t}] {e} çekiliyor..."
            ))

            prev_price, prev_time = self.get_previous_price(esya)
            fiyat_str, hacim_str = self.get_steam_price(esya)

            if fiyat_str:
                curr_price, _ = self.parse_numbers(fiyat_str, hacim_str)
                saved = self.save_price_to_db(esya, fiyat_str, hacim_str)
                self.after(0, lambda e=esya, f=fiyat_str, h=hacim_str, cp=curr_price, pp=prev_price, pt=prev_time, s=saved: 
                    self._add_result_card(e, f, h, cp, pp, pt, s)
                )
            else:
                self.after(0, lambda e=esya, err=hacim_str: self._add_error_card(e, err))

            time.sleep(2.2)

        self.after(0, self._scan_finished)

    def _add_result_card(self, esya, fiyat_str, hacim_str, curr_price, prev_price, prev_time, saved):
        card = ctk.CTkFrame(self.results_scroll, fg_color="#24273a", corner_radius=8)
        card.pack(fill="x", padx=10, pady=6)

        left_frame = ctk.CTkFrame(card, fg_color="transparent")
        left_frame.pack(side="left", padx=15, pady=10)

        name_label = ctk.CTkLabel(left_frame, text=esya, font=ctk.CTkFont(size=15, weight="bold"), text_color="#ffffff")
        name_label.pack(anchor="w")

        hacim_display = f"24s Hacim: {hacim_str}" if hacim_str else "Hacim: Yok"
        detail_label = ctk.CTkLabel(left_frame, text=hacim_display, font=ctk.CTkFont(size=12), text_color="#a5adcb")
        detail_label.pack(anchor="w")

        right_frame = ctk.CTkFrame(card, fg_color="transparent")
        right_frame.pack(side="right", padx=15, pady=10)

        price_label = ctk.CTkLabel(right_frame, text=f"{fiyat_str}", font=ctk.CTkFont(size=18, weight="bold"), text_color="#4cc9f0")
        price_label.pack(anchor="e")

        # Değişim Rozeti
        if prev_price is not None and curr_price is not None:
            fark = curr_price - prev_price
            if fark < -0.001:
                yuzde = abs(fark / prev_price) * 100
                badge_text = f"📉 %{yuzde:.2f} DÜŞTÜ (Önceki: ${prev_price:.2f})"
                badge_color = "#2ecc71"  # Yeşil (Fırsat)
            elif fark > 0.001:
                yuzde = (fark / prev_price) * 100
                badge_text = f"📈 %{yuzde:.2f} ARTTI (Önceki: ${prev_price:.2f})"
                badge_color = "#e74c3c"  # Kırmızı
            else:
                badge_text = "➡️ Fiyat Sabit"
                badge_color = "#95a5a6"
        else:
            badge_text = "✨ İlk Kayıt"
            badge_color = "#9b59b6"

        badge = ctk.CTkLabel(right_frame, text=badge_text, font=ctk.CTkFont(size=11, weight="bold"), text_color=badge_color)
        badge.pack(anchor="e")

    def _add_error_card(self, esya, err_msg):
        card = ctk.CTkFrame(self.results_scroll, fg_color="#2d1e2f", corner_radius=8)
        card.pack(fill="x", padx=10, pady=6)
        lbl = ctk.CTkLabel(card, text=f"❌ {esya} - {err_msg}", font=ctk.CTkFont(size=13), text_color="#e63946")
        lbl.pack(padx=15, pady=10, anchor="w")

    def _scan_finished(self):
        self.is_scanning = False
        self.scan_btn.configure(state="normal", text="🚀 Fiyatı Tara & Kaydet")
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.scan_status_label.configure(text="✅ Tarama tamamlandı ve Neon Bulut veritabanına kaydedildi.")
        self.refresh_database_table()

    # ------------------ SEKME 2: NEON VERİTABANI TABLOSU ------------------
    def setup_database_tab(self):
        top_bar = ctk.CTkFrame(self.tab_database, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(10, 5))

        self.table_search_entry = ctk.CTkEntry(
            top_bar,
            placeholder_text="Eşya adıyla filtrele...",
            width=300,
            height=36
        )
        self.table_search_entry.pack(side="left", padx=(0, 10))
        self.table_search_entry.bind("<KeyRelease>", lambda e: self.filter_table())

        refresh_btn = ctk.CTkButton(
            top_bar,
            text="🔄 Yenile",
            width=100,
            height=36,
            command=self.refresh_database_table
        )
        refresh_btn.pack(side="left", padx=5)

        self.table_count_label = ctk.CTkLabel(top_bar, text="", font=ctk.CTkFont(size=13), text_color="#8d99ae")
        self.table_count_label.pack(side="right", padx=10)

        # Ağaç Tablosu (Treeview)
        table_frame = ctk.CTkFrame(self.tab_database, fg_color="#1e1e24", corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        columns = ("esya", "guncel", "min", "max", "hacim", "zaman", "tarama")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("esya", text="Eşya Adı")
        self.tree.heading("guncel", text="Güncel ($)")
        self.tree.heading("min", text="Min ($)")
        self.tree.heading("max", text="Maks ($)")
        self.tree.heading("hacim", text="24s Hacim")
        self.tree.heading("zaman", text="Son Güncelleme")
        self.tree.heading("tarama", text="Kayıt")

        self.tree.column("esya", width=340, anchor="w")
        self.tree.column("guncel", width=100, anchor="center")
        self.tree.column("min", width=90, anchor="center")
        self.tree.column("max", width=90, anchor="center")
        self.tree.column("hacim", width=110, anchor="center")
        self.tree.column("zaman", width=150, anchor="center")
        self.tree.column("tarama", width=80, anchor="center")

        # Treeview Koyu Tema Stili
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#24273a",
            foreground="#cad3f5",
            rowheight=30,
            fieldbackground="#24273a",
            font=("Segoe UI", 10)
        )
        style.configure(
            "Treeview.Heading",
            background="#1e2030",
            foreground="#ffffff",
            font=("Segoe UI", 11, "bold")
        )
        style.map("Treeview", background=[('selected', '#3b82f6')])

        # Scrollbar
        scrollbar_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar_y.set)
        scrollbar_y.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)

        self.all_table_data = []

    def refresh_database_table(self):
        threading.Thread(target=self._fetch_table_thread, daemon=True).start()

    def _fetch_table_thread(self):
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    WITH son_kayitlar AS (
                        SELECT DISTINCT ON (esya)
                            esya,
                            fiyat_sayisal as guncel_fiyat,
                            hacim_sayisal as guncel_hacim,
                            tarih as son_tarih,
                            saat as son_saat
                        FROM pazar_verileri
                        ORDER BY esya, id DESC
                    ),
                    istatistikler AS (
                        SELECT 
                            esya,
                            COUNT(*) as kayit_adet,
                            MIN(fiyat_sayisal) as min_f,
                            MAX(fiyat_sayisal) as max_f
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
                        i.kayit_adet,
                        s.son_tarih,
                        s.son_saat
                    FROM son_kayitlar s
                    JOIN istatistikler i ON s.esya = i.esya
                    ORDER BY s.guncel_fiyat DESC NULLS LAST;
                """)
                rows = cur.fetchall()
            conn.close()

            self.all_table_data = rows
            self.after(0, self.filter_table)
        except Exception as e:
            print("Tablo Veri Çekme Hatası:", e)

    def filter_table(self):
        query = self.table_search_entry.get().strip().lower()
        self.tree.delete(*self.tree.get_children())

        filtered_count = 0
        for r in self.all_table_data:
            if query and query not in r['esya'].lower():
                continue

            filtered_count += 1
            hacim_str = f"{r['guncel_hacim']:,}" if r['guncel_hacim'] is not None else "-"
            zaman_str = f"{r['son_tarih'].strftime('%d.%m.%Y')} {r['son_saat'].strftime('%H:%M')}" if (r['son_tarih'] and r['son_saat']) else "-"

            self.tree.insert("", "end", values=(
                r['esya'],
                f"${r['guncel_fiyat']:.2f}" if r['guncel_fiyat'] else "-",
                f"${r['min_f']:.2f}" if r['min_f'] else "-",
                f"${r['max_f']:.2f}" if r['max_f'] else "-",
                hacim_str,
                zaman_str,
                f"{r['kayit_adet']} kez"
            ))

        self.table_count_label.configure(text=f"Listelenen Eşya: {filtered_count}")

    # ------------------ SEKME 3: PİYASA ANALİZLERİ ------------------
    def setup_analytics_tab(self):
        control_bar = ctk.CTkFrame(self.tab_analytics, fg_color="transparent")
        control_bar.pack(fill="x", padx=10, pady=(10, 5))

        anomali_btn = ctk.CTkButton(
            control_bar,
            text="🧠 Aşınma & Arbitraj Analizi Yap",
            font=ctk.CTkFont(weight="bold"),
            command=self.run_anomali_analysis
        )
        anomali_btn.pack(side="left", padx=(0, 10))

        likidite_btn = ctk.CTkButton(
            control_bar,
            text="💧 Likidite & Risk Analizi Yap",
            font=ctk.CTkFont(weight="bold"),
            command=self.run_likidite_analysis
        )
        likidite_btn.pack(side="left", padx=5)

        # Analiz Sonuç Kutusu
        self.analytics_textbox = ctk.CTkTextbox(
            self.tab_analytics,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color="#1e1e24",
            corner_radius=10
        )
        self.analytics_textbox.pack(fill="both", expand=True, padx=10, pady=10)
        self.analytics_textbox.insert("1.0", "Yukarıdaki butonlara basarak veritabanınızdaki pazar analizlerini anında çalıştırabilirsiniz.\n\n"
                                             "• Aşınma & Arbitraj: Well-Worn > Field-Tested gibi fiyat tutarsızlıklarını yakalar.\n"
                                             "• Likidite & Risk: 24 saatlik işlem hacmine göre alım/satım risk kategorilerini belirler.")

    def run_anomali_analysis(self):
        threading.Thread(target=self._anomali_thread, daemon=True).start()

    def _anomali_thread(self):
        wear_order = {
            "Factory New": 1,
            "Minimal Wear": 2,
            "Field-Tested": 3,
            "Well-Worn": 4,
            "Battle-Scarred": 5
        }
        try:
            conn = self.get_db_connection()
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
            conn.close()

            gruplar = {}
            for r in rows:
                m = re.match(r'^(.*?)\s*\((Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)\)$', r['esya'])
                if m:
                    skin = m.group(1).strip()
                    w = m.group(2)
                    if skin not in gruplar:
                        gruplar[skin] = {}
                    gruplar[skin][w] = {
                        'fiyat': float(r['fiyat_sayisal']),
                        'hacim': r['hacim_sayisal']
                    }

            out = ["═" * 70, "🧠 AŞINMA SEVİYESİ & FİYAT ANOMALİ / ARBİTRAJ ANALİZİ", "═" * 70, ""]
            anomali_var = False

            for skin, data in gruplar.items():
                out.append(f"🔫 {skin}:")
                sirali = sorted(data.keys(), key=lambda w: wear_order.get(w, 99))
                for w in sirali:
                    f = data[w]['fiyat']
                    h = data[w]['hacim']
                    h_str = f"{h:,}" if h is not None else "Yok"
                    out.append(f"   • {w:<15}: ${f:<7.2f} (24s Hacim: {h_str})")

                for i in range(len(sirali)):
                    for j in range(i + 1, len(sirali)):
                        iyi = sirali[i]
                        kotu = sirali[j]
                        f_iyi = data[iyi]['fiyat']
                        f_kotu = data[kotu]['fiyat']
                        if f_kotu > f_iyi:
                            anomali_var = True
                            fark = f_kotu - f_iyi
                            out.append(f"\n   ⚠️ DİKKAT (Piyasa Anomalisi): '{kotu}' (${f_kotu:.2f}), daha temiz olan '{iyi}' (${f_iyi:.2f}) sürümünden ${fark:.2f} daha pahalı!")
                            out.append(f"      💡 Yorum: '{kotu}' sürümünde stok azlığı veya yapay şişirme olabilir. Alıcılar için '{iyi}' çok daha avantajlı!\n")
                out.append("")

            if not anomali_var:
                out.append("✅ Tüm aşınma sıralamaları piyasa normlarına uygun görünüyor.")

            text_result = "\n".join(out)
            self.after(0, lambda: self._update_analytics_text(text_result))
        except Exception as e:
            self.after(0, lambda: self._update_analytics_text(f"Hata oluştu: {e}"))

    def run_likidite_analysis(self):
        threading.Thread(target=self._likidite_thread, daemon=True).start()

    def _likidite_thread(self):
        try:
            conn = self.get_db_connection()
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
            conn.close()

            out = ["═" * 70, "💧 LİKİDİTE VE TİCARET RİSK ANALİZİ (24s Satış Hacmi)", "═" * 70, ""]
            cok_yuksek = [r for r in rows if r['hacim_sayisal'] >= 1000]
            orta = [r for r in rows if 100 <= r['hacim_sayisal'] < 1000]
            dusuk = [r for r in rows if r['hacim_sayisal'] < 100]

            out.append("🟢 YÜKSEK LİKİDİTE (Hızlı Alınıp Satılanlar - Düşük Risk):")
            for r in sorted(cok_yuksek, key=lambda x: x['hacim_sayisal'], reverse=True):
                out.append(f"   • {r['esya']:<36} | Hacim: {r['hacim_sayisal']:,} adet | Fiyat: ${r['fiyat_sayisal']}")

            out.append("\n🟡 ORTA LİKİDİTE (Dengeli Piyasa):")
            for r in sorted(orta, key=lambda x: x['hacim_sayisal'], reverse=True):
                out.append(f"   • {r['esya']:<36} | Hacim: {r['hacim_sayisal']:,} adet | Fiyat: ${r['fiyat_sayisal']}")

            out.append("\n🔴 DÜŞÜK LİKİDİTE (Yavaş Satılanlar - Fiyat Manipülasyonuna Açık):")
            for r in sorted(dusuk, key=lambda x: x['hacim_sayisal'], reverse=True):
                out.append(f"   • {r['esya']:<36} | Hacim: {r['hacim_sayisal']:,} adet | Fiyat: ${r['fiyat_sayisal']}")

            text_result = "\n".join(out)
            self.after(0, lambda: self._update_analytics_text(text_result))
        except Exception as e:
            self.after(0, lambda: self._update_analytics_text(f"Hata oluştu: {e}"))

    def _update_analytics_text(self, content):
        self.analytics_textbox.delete("1.0", "end")
        self.analytics_textbox.insert("1.0", content)


if __name__ == "__main__":
    app = CS2MarketApp()
    app.mainloop()

