import os
import re
import sys
import threading
import time
import urllib.parse
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import requests
import katalog_yoneticisi as ky

# Windows konsolunda UTF-8 desteği
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# .env ve dosya konumunu tespit et (EXE veya normal çalışma)
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(base_dir, '.env')
load_dotenv(env_path)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# HAZIR PRESET LİSTELERİ
CASES_PRESET = [
    "Gallery Case",
    "Kilowatt Case",
    "Revolution Case",
    "Dreams & Nightmares Case",
    "Recoil Case",
    "Snakebite Case",
    "Fracture Case",
    "Prisma 2 Case",
    "Danger Zone Case",
    "Horizon Case",
    "Spectrum 2 Case",
    "Clutch Case",
    "Glove Case"
]

POPULAR_SKINS_PRESET = [
    "AK-47 | Redline",
    "AK-47 | Slate",
    "AWP | Asiimov",
    "AWP | Atheris",
    "M4A1-S | Printstream",
    "M4A4 | The Emperor",
    "Desert Eagle | Printstream",
    "USP-S | The Traitor",
    "Glock-18 | Water Elemental"
]


class CS2MarketApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CS2 Market Analyzer & Cloud Tracker")
        self.geometry("1100x800")
        self.minsize(980, 680)

        self.is_scanning = False
        self.stop_requested = False
        self._search_timer = None
        self._wl_search_timer = None

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
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS takip_listesi (
                        id SERIAL PRIMARY KEY,
                        esya VARCHAR(255) UNIQUE NOT NULL,
                        hedef_fiyat NUMERIC(10, 2),
                        ekleme_tarihi TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute("SELECT COUNT(*) FROM pazar_verileri;")
                count = cur.fetchone()[0]

                katalog_count = 0
                try:
                    cur.execute("SELECT COUNT(*) FROM esya_katalogu;")
                    katalog_count = cur.fetchone()[0]
                except Exception:
                    conn.rollback()

                conn.commit()
            conn.close()

            status_text = f"🟢 Neon Cloud Bağlı ({count} Kayıt | {katalog_count} Katalog)" if katalog_count else f"🟢 Neon Cloud Bağlı ({count} Kayıt)"
            self.after(0, lambda: self.status_badge.configure(text=status_text, text_color="#2ecc71"))
            self.after(0, self.refresh_database_table)
            self.after(0, self.refresh_watchlist_table)
        except Exception as e:
            self.after(0, lambda: self.status_badge.configure(
                text="🔴 Neon Bağlantı Hatası", text_color="#e74c3c"
            ))

    # ------------------ STEAM API & FORMATLAMA ------------------
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
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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
        header_frame = ctk.CTkFrame(self, fg_color="#1e1e24", corner_radius=0, height=65)
        header_frame.pack(fill="x", side="top")

        title_label = ctk.CTkLabel(
            header_frame, 
            text="🎮 CS2 Market Analyzer & Portfolio", 
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

        # Sekmeli Görünüm (Tabview) - 4 TANE SEKME
        self.tabview = ctk.CTkTabview(self, corner_radius=12)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(15, 20))

        self.tab_scan = self.tabview.add("🔍 Eşya Tarama & Paketler")
        self.tab_watchlist = self.tabview.add("📌 Takip Listem (Portföy)")
        self.tab_database = self.tabview.add("📋 Neon Pazar Tablosu")
        self.tab_analytics = self.tabview.add("🧠 Piyasa Analizleri")

        self.setup_scan_tab()
        self.setup_watchlist_tab()
        self.setup_database_tab()
        self.setup_analytics_tab()

    # ------------------ SEKME 1: EŞYA TARAMA & PAKETLER ------------------
    # ------------------ SEKME 1: EŞYA TARAMA & PAKETLER ------------------
    def setup_scan_tab(self):
        # Arama kutusu alanı
        search_card = ctk.CTkFrame(self.tab_scan, fg_color="#2b2d42", corner_radius=10)
        search_card.pack(fill="x", padx=10, pady=(10, 6))

        input_container = ctk.CTkFrame(search_card, fg_color="transparent")
        input_container.pack(fill="x", padx=15, pady=(12, 6))

        self.item_entry = ctk.CTkEntry(
            input_container,
            placeholder_text="Eşya adını yazın (Örn: AWP Worm God, AK-47 Redline, Gallery Case)...",
            height=40,
            font=ctk.CTkFont(size=14)
        )
        self.item_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.item_entry.bind("<Return>", lambda e: self.start_single_scan())
        self.item_entry.bind("<KeyRelease>", self._on_search_key_release)

        self.wear_checkbox = ctk.CTkCheckBox(
            input_container, 
            text="Aşınmaları Tara (FN..BS)", 
            font=ctk.CTkFont(size=12)
        )
        self.wear_checkbox.pack(side="left", padx=10)
        self.wear_checkbox.select()

        self.scan_btn = ctk.CTkButton(
            input_container,
            text="🚀 Tara & Kaydet",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            width=150,
            command=self.start_single_scan
        )
        self.scan_btn.pack(side="right")

        # Katalog Otomatik Öneri Paneli (Arama sonuçları için)
        self.suggestions_frame = ctk.CTkFrame(search_card, fg_color="#181a24", corner_radius=8)

        # HIZLI PAKETLER VE KATEGORİ ÇUBUĞU
        self.preset_card = ctk.CTkFrame(search_card, fg_color="transparent")
        self.preset_card.pack(fill="x", padx=15, pady=(0, 10))

        # Satır 1: Hazır Paketler
        row1 = ctk.CTkFrame(self.preset_card, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 6))

        preset_lbl = ctk.CTkLabel(row1, text="⚡ Hızlı Paketler:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#a5adcb")
        preset_lbl.pack(side="left", padx=(0, 8))

        btn_cases = ctk.CTkButton(
            row1, text="📦 Popüler Kasalar", height=30, fg_color="#3a0ca3", hover_color="#4361ee",
            font=ctk.CTkFont(size=12), command=lambda: self.start_batch_scan(CASES_PRESET, scan_wears=False)
        )
        btn_cases.pack(side="left", padx=3)

        btn_skins = ctk.CTkButton(
            row1, text="🔫 Popüler Skinler", height=30, fg_color="#3a0ca3", hover_color="#4361ee",
            font=ctk.CTkFont(size=12), command=lambda: self.start_batch_scan(POPULAR_SKINS_PRESET, scan_wears=True)
        )
        btn_skins.pack(side="left", padx=3)

        btn_steam = ctk.CTkButton(
            row1, text="🔥 Top 50 Trend (Hızlı)", height=30, fg_color="#d90429", hover_color="#ef233c",
            font=ctk.CTkFont(size=12), command=self.scan_steam_trends_fast
        )
        btn_steam.pack(side="left", padx=3)

        btn_file = ctk.CTkButton(
            row1, text="📁 items.txt", height=30, fg_color="#2b9348", hover_color="#55a630",
            font=ctk.CTkFont(size=12), command=self.scan_from_file
        )
        btn_file.pack(side="left", padx=3)

        self.stop_btn = ctk.CTkButton(
            row1, text="⏹️ Durdur", height=30, width=80, fg_color="#7209b7", hover_color="#b5179e",
            font=ctk.CTkFont(size=12, weight="bold"), command=self.stop_scan, state="disabled"
        )
        self.stop_btn.pack(side="right", padx=3)

        # Satır 2: 9,468 Eşyalık Katalogdan Kategori Tarama
        row2 = ctk.CTkFrame(self.preset_card, fg_color="transparent")
        row2.pack(fill="x", pady=(2, 2))

        cat_lbl = ctk.CTkLabel(row2, text="📚 9,468'lik Katalog:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#a5adcb")
        cat_lbl.pack(side="left", padx=(0, 8))

        self.cat_combobox = ctk.CTkComboBox(
            row2,
            values=[
                "Kategori Seçin...",
                "📦 Kasa & Kapsül (479)",
                "🔪 Bıçaklar (1714)",
                "🧤 Eldivenler (470)",
                "🔫 Tüfekler (2302)",
                "💥 Tabancalar (2023)",
                "⚡ Hafif Makineliler (1433)",
                "🛡️ Ağır Silahlar (1012)"
            ],
            width=210,
            height=30,
            font=ctk.CTkFont(size=12)
        )
        self.cat_combobox.pack(side="left", padx=3)

        self.cat_limit_combobox = ctk.CTkComboBox(
            row2,
            values=["20 Eşya", "50 Eşya", "100 Eşya"],
            width=100,
            height=30,
            font=ctk.CTkFont(size=12)
        )
        self.cat_limit_combobox.pack(side="left", padx=3)

        btn_cat_scan = ctk.CTkButton(
            row2, text="🚀 Kategoriyi Tara", height=30, width=130, fg_color="#4361ee", hover_color="#3a0ca3",
            font=ctk.CTkFont(size=12, weight="bold"), command=self.scan_selected_category
        )
        btn_cat_scan.pack(side="left", padx=4)

        btn_sync_catalog = ctk.CTkButton(
            row2, text="🔄 Kataloğu Güncelle", height=30, width=140, fg_color="#343a40", hover_color="#495057",
            font=ctk.CTkFont(size=12), command=self.sync_catalog_from_api
        )
        btn_sync_catalog.pack(side="right", padx=3)

        # Durum çubuğu
        self.progress_bar = ctk.CTkProgressBar(self.tab_scan, mode="indeterminate", height=4)
        self.scan_status_label = ctk.CTkLabel(
            self.tab_scan, 
            text="İster arama çubuğuna yazıp önerileri seçin, ister 9,468 eşyalık katalogdan kategori taratın.",
            font=ctk.CTkFont(size=13),
            text_color="#8d99ae"
        )
        self.scan_status_label.pack(anchor="w", padx=15, pady=(4, 4))

        # Sonuç Kartları Alanı
        self.results_scroll = ctk.CTkScrollableFrame(
            self.tab_scan, 
            fg_color="#1a1a24",
            corner_radius=10,
            label_text="📊 Tarama Sonuçları",
            label_font=ctk.CTkFont(size=14, weight="bold")
        )
        self.results_scroll.pack(fill="both", expand=True, padx=10, pady=(6, 10))

    # ------------------ KATALOG OTOMATİK TAMAMLAMA ------------------
    def _on_search_key_release(self, event):
        if event.keysym in ("Return", "Up", "Down", "Escape"):
            if event.keysym == "Escape":
                self.suggestions_frame.pack_forget()
            return
        if self._search_timer:
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(250, self._do_catalog_search)

    def _do_catalog_search(self):
        text = self.item_entry.get().strip()
        if len(text) < 2:
            self.suggestions_frame.pack_forget()
            return
        threading.Thread(target=self._fetch_suggestions_thread, args=(text,), daemon=True).start()

    def _fetch_suggestions_thread(self, query):
        results = ky.katalog_ara(query, limit=5)
        self.after(0, lambda: self._show_suggestions(results))

    def _show_suggestions(self, results):
        for widget in self.suggestions_frame.winfo_children():
            widget.destroy()

        if not results:
            self.suggestions_frame.pack_forget()
            return

        self.suggestions_frame.pack(fill="x", padx=15, pady=(0, 8), before=self.preset_card)

        header = ctk.CTkLabel(
            self.suggestions_frame,
            text="💡 Katalog Önerileri (Seçmek için tıklayın):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#8d99ae"
        )
        header.pack(anchor="w", padx=8, pady=(4, 2))

        for item in results:
            name = item['esya_adi']
            cat = item.get('kategori', '')
            btn = ctk.CTkButton(
                self.suggestions_frame,
                text=f"🎯 {name}  [{cat}]",
                anchor="w",
                height=26,
                fg_color="#24273a",
                hover_color="#3a0ca3",
                font=ctk.CTkFont(size=12),
                command=lambda n=name: self._select_suggestion(n)
            )
            btn.pack(fill="x", padx=6, pady=2)

    def _select_suggestion(self, name):
        self.item_entry.delete(0, 'end')
        self.item_entry.insert(0, name)
        self.suggestions_frame.pack_forget()

    # ------------------ KATEGORİ VE HIZLI STEAM TARAMASI ------------------
    def scan_selected_category(self):
        if self.is_scanning:
            return
        val = self.cat_combobox.get()
        if "Kategori Seçin" in val:
            messagebox.showwarning("Seçim Yapın", "Lütfen önce bir kategori seçin!")
            return

        cat_name = val.split("(")[0].strip()
        for emoji in ["📦", "🔪", "🧤", "🔫", "💥", "⚡", "🛡️"]:
            cat_name = cat_name.replace(emoji, "").strip()

        limit_str = self.cat_limit_combobox.get()
        limit = 20
        if "50" in limit_str:
            limit = 50
        elif "100" in limit_str:
            limit = 100

        items = ky.kategori_esyalarini_al(cat_name, limit=limit)
        if not items:
            messagebox.showinfo("Boş Kategori", f"'{cat_name}' kategorisinde eşya bulunamadı.")
            return

        self.start_batch_scan(items, scan_wears=False)

    def sync_catalog_from_api(self):
        if messagebox.askyesno("Kataloğu Güncelle", "CS2 API üzerinden ~9.500 eşya indirilip Neon Bulut veritabanı güncellenecek. Devam edilsin mi?"):
            self.scan_status_label.configure(text="🌐 Eşya kataloğu indiriliyor...")
            self.progress_bar.pack(fill="x", padx=10, pady=(0, 5))
            self.progress_bar.start()

            def _thread():
                def cb(msg, pct):
                    self.after(0, lambda m=msg: self.scan_status_label.configure(text=m))
                total, msg = ky.katalogu_indir_ve_yukle(cb)
                self.after(0, lambda: self.progress_bar.stop())
                self.after(0, lambda: self.progress_bar.pack_forget())
                self.after(0, lambda: messagebox.showinfo("Katalog Güncellendi", f"Toplam {total} eşya Neon veritabanına kaydedildi!"))
                self.after(0, self.check_initial_db_status)

            threading.Thread(target=_thread, daemon=True).start()

    def scan_steam_trends_fast(self):
        if self.is_scanning:
            return
        self.is_scanning = True
        self.stop_requested = False
        self.scan_btn.configure(state="disabled", text="⏳ Taranıyor...")
        self.stop_btn.configure(state="normal")
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 5))
        self.progress_bar.start()

        for widget in self.results_scroll.winfo_children():
            widget.destroy()

        threading.Thread(target=self._run_steam_popular_thread, daemon=True).start()

    def _run_steam_popular_thread(self):
        def cb(msg, pct):
            self.after(0, lambda m=msg: self.scan_status_label.configure(text=m))

        self.after(0, lambda: self.scan_status_label.configure(text="🔥 Steam'in en çok satan 50 eşyası toplu çekiliyor..."))
        count, items = ky.steam_populer_tara_ve_kaydet(50, cb)

        for it in items:
            prev_price, prev_time = self.get_previous_price(it['esya'])
            curr_price = it.get('fiyat_sayisal')
            self.after(0, lambda e=it['esya'], f=it['fiyat'], h=it['hacim'], cp=curr_price, pp=prev_price, pt=prev_time:
                self._add_result_card(e, f, h, cp, pp, pt, saved=True)
            )

        self.after(0, self._scan_finished)

    def stop_scan(self):
        if self.is_scanning:
            self.stop_requested = True
            self.scan_status_label.configure(text="⏹️ Durdurma isteği alındı, mevcut eşyadan sonra duracak...")

    def start_batch_scan(self, raw_items, scan_wears=False):
        if self.is_scanning:
            return
        self.is_scanning = True
        self.stop_requested = False
        self.scan_btn.configure(state="disabled", text="⏳ Taranıyor...")
        self.stop_btn.configure(state="normal")
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 5))
        self.progress_bar.start()

        for widget in self.results_scroll.winfo_children():
            widget.destroy()

        threading.Thread(target=self._run_batch_thread, args=(raw_items, scan_wears), daemon=True).start()

    def _run_batch_thread(self, raw_items, scan_wears):
        wear_levels = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]
        full_scan_list = []

        for raw in raw_items:
            base_name = self.format_item_name(raw)
            if scan_wears and "|" in base_name and not any(f"({w})" in base_name for w in wear_levels):
                for w in wear_levels:
                    full_scan_list.append(f"{base_name} ({w})")
            else:
                full_scan_list.append(base_name)

        total = len(full_scan_list)
        for idx, esya in enumerate(full_scan_list, 1):
            if self.stop_requested:
                self.after(0, lambda: self.scan_status_label.configure(text="⏹️ Tarama kullanıcı tarafından durduruldu."))
                break

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
        card.pack(fill="x", padx=10, pady=5)

        left_frame = ctk.CTkFrame(card, fg_color="transparent")
        left_frame.pack(side="left", padx=15, pady=8)

        name_label = ctk.CTkLabel(left_frame, text=esya, font=ctk.CTkFont(size=14, weight="bold"), text_color="#ffffff")
        name_label.pack(anchor="w")

        hacim_display = f"24s Hacim: {hacim_str}" if hacim_str else "Hacim: Yok"
        detail_label = ctk.CTkLabel(left_frame, text=hacim_display, font=ctk.CTkFont(size=11), text_color="#a5adcb")
        detail_label.pack(anchor="w")

        right_frame = ctk.CTkFrame(card, fg_color="transparent")
        right_frame.pack(side="right", padx=15, pady=8)

        price_label = ctk.CTkLabel(right_frame, text=f"{fiyat_str}", font=ctk.CTkFont(size=17, weight="bold"), text_color="#4cc9f0")
        price_label.pack(anchor="e")

        if prev_price is not None and curr_price is not None:
            fark = curr_price - prev_price
            if fark < -0.001:
                yuzde = abs(fark / prev_price) * 100
                badge_text = f"📉 %{yuzde:.2f} DÜŞTÜ (Önceki: ${prev_price:.2f})"
                badge_color = "#2ecc71"
            elif fark > 0.001:
                yuzde = (fark / prev_price) * 100
                badge_text = f"📈 %{yuzde:.2f} ARTTI (Önceki: ${prev_price:.2f})"
                badge_color = "#e74c3c"
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
        card.pack(fill="x", padx=10, pady=5)
        lbl = ctk.CTkLabel(card, text=f"❌ {esya} - {err_msg}", font=ctk.CTkFont(size=12), text_color="#e63946")
        lbl.pack(padx=15, pady=8, anchor="w")

    def _scan_finished(self):
        self.is_scanning = False
        self.stop_requested = False
        self.scan_btn.configure(state="normal", text="🚀 Tara & Kaydet")
        self.stop_btn.configure(state="disabled")
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.scan_status_label.configure(text="✅ Tarama tamamlandı ve Neon Bulut veritabanına kaydedildi.")
        self.refresh_database_table()

    # ------------------ SEKME 2: TAKİP LİSTEM (PORTFÖY) ------------------
    def setup_watchlist_tab(self):
        add_bar = ctk.CTkFrame(self.tab_watchlist, fg_color="#2b2d42", corner_radius=10)
        add_bar.pack(fill="x", padx=10, pady=10)

        c = ctk.CTkFrame(add_bar, fg_color="transparent")
        c.pack(fill="x", padx=15, pady=12)

        self.wl_item_entry = ctk.CTkEntry(
            c, placeholder_text="Takip etmek istediğiniz eşya (Örn: AWP Asiimov (Field-Tested))...",
            height=38, font=ctk.CTkFont(size=13)
        )
        self.wl_item_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.wl_item_entry.bind("<KeyRelease>", self._on_wl_search_key_release)

        self.wl_target_entry = ctk.CTkEntry(
            c, placeholder_text="Hedef Fiyat $ (Opsiyonel)", width=160, height=38, font=ctk.CTkFont(size=13)
        )
        self.wl_target_entry.pack(side="left", padx=(0, 10))

        add_btn = ctk.CTkButton(
            c, text="➕ Listeme Ekle", height=38, width=130, font=ctk.CTkFont(weight="bold"),
            command=self.add_to_watchlist
        )
        add_btn.pack(side="left")

        # Takip Listesi Katalog Öneri Paneli
        self.wl_suggestions_frame = ctk.CTkFrame(add_bar, fg_color="#181a24", corner_radius=8)

        btn_bar = ctk.CTkFrame(self.tab_watchlist, fg_color="transparent")
        btn_bar.pack(fill="x", padx=10, pady=(0, 6))

        scan_wl_btn = ctk.CTkButton(
            btn_bar, text="🚀 Takip Listemdekileri Tara", height=36, fg_color="#3a0ca3", hover_color="#4361ee",
            font=ctk.CTkFont(weight="bold"), command=self.scan_watchlist_items
        )
        scan_wl_btn.pack(side="left", padx=(0, 8))

        del_btn = ctk.CTkButton(
            btn_bar, text="🗑️ Seçileni Sil", height=36, width=120, fg_color="#d90429", hover_color="#ef233c",
            command=self.delete_from_watchlist
        )
        del_btn.pack(side="left", padx=4)

        refresh_wl_btn = ctk.CTkButton(
            btn_bar, text="🔄 Yenile", height=36, width=100, command=self.refresh_watchlist_table
        )
        refresh_wl_btn.pack(side="left", padx=4)

        self.wl_count_label = ctk.CTkLabel(btn_bar, text="", font=ctk.CTkFont(size=12), text_color="#8d99ae")
        self.wl_count_label.pack(side="right", padx=10)

        table_frame = ctk.CTkFrame(self.tab_watchlist, fg_color="#1e1e24", corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        columns = ("id", "esya", "hedef", "tarih")
        self.wl_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.wl_tree.heading("id", text="ID")
        self.wl_tree.heading("esya", text="Takip Edilen Eşya Adı")
        self.wl_tree.heading("hedef", text="Hedef Fiyat ($)")
        self.wl_tree.heading("tarih", text="Eklenme Tarihi")

        self.wl_tree.column("id", width=50, anchor="center")
        self.wl_tree.column("esya", width=480, anchor="w")
        self.wl_tree.column("hedef", width=140, anchor="center")
        self.wl_tree.column("tarih", width=180, anchor="center")

        scrollbar_wl = ttk.Scrollbar(table_frame, orient="vertical", command=self.wl_tree.yview)
        self.wl_tree.configure(yscrollcommand=scrollbar_wl.set)
        scrollbar_wl.pack(side="right", fill="y")
        self.wl_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def add_to_watchlist(self):
        esya = self.wl_item_entry.get().strip()
        if not esya:
            messagebox.showwarning("Eksik", "Lütfen takip edilecek eşya adını yazın!")
            return
        target_str = self.wl_target_entry.get().strip().replace("$", "").replace(",", ".")
        target_val = float(target_str) if target_str else None

        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO takip_listesi (esya, hedef_fiyat) 
                    VALUES (%s, %s)
                    ON CONFLICT (esya) DO UPDATE SET hedef_fiyat = EXCLUDED.hedef_fiyat;
                """, (esya, target_val))
                conn.commit()
            conn.close()

            self.wl_item_entry.delete(0, "end")
            self.wl_target_entry.delete(0, "end")
            self.wl_suggestions_frame.pack_forget()
            self.refresh_watchlist_table()
            messagebox.showinfo("Başarılı", f"'{esya}' takip listenize eklendi!")
        except Exception as e:
            messagebox.showerror("Hata", f"Listeye eklenemedi: {e}")

    # ------------------ TAKİP LİSTESİ KATALOG ÖNERİLERİ ------------------
    def _on_wl_search_key_release(self, event):
        if event.keysym in ("Return", "Up", "Down", "Escape"):
            if event.keysym == "Escape":
                self.wl_suggestions_frame.pack_forget()
            return
        if self._wl_search_timer:
            self.after_cancel(self._wl_search_timer)
        self._wl_search_timer = self.after(250, self._do_wl_catalog_search)

    def _do_wl_catalog_search(self):
        text = self.wl_item_entry.get().strip()
        if len(text) < 2:
            self.wl_suggestions_frame.pack_forget()
            return
        threading.Thread(target=self._fetch_wl_suggestions_thread, args=(text,), daemon=True).start()

    def _fetch_wl_suggestions_thread(self, query):
        results = ky.katalog_ara(query, limit=5)
        self.after(0, lambda: self._show_wl_suggestions(results))

    def _show_wl_suggestions(self, results):
        for widget in self.wl_suggestions_frame.winfo_children():
            widget.destroy()

        if not results:
            self.wl_suggestions_frame.pack_forget()
            return

        self.wl_suggestions_frame.pack(fill="x", padx=15, pady=(0, 8))
        header = ctk.CTkLabel(
            self.wl_suggestions_frame,
            text="💡 Katalog Önerileri (Seçmek için tıklayın):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#8d99ae"
        )
        header.pack(anchor="w", padx=8, pady=(4, 2))

        for item in results:
            name = item['esya_adi']
            cat = item.get('kategori', '')
            btn = ctk.CTkButton(
                self.wl_suggestions_frame,
                text=f"🎯 {name}  [{cat}]",
                anchor="w",
                height=26,
                fg_color="#24273a",
                hover_color="#3a0ca3",
                font=ctk.CTkFont(size=12),
                command=lambda n=name: self._select_wl_suggestion(n)
            )
            btn.pack(fill="x", padx=6, pady=2)

    def _select_wl_suggestion(self, name):
        self.wl_item_entry.delete(0, 'end')
        self.wl_item_entry.insert(0, name)
        self.wl_suggestions_frame.pack_forget()

    def delete_from_watchlist(self):
        selected = self.wl_tree.selection()
        if not selected:
            messagebox.showwarning("Seçim Yok", "Lütfen silmek istediğiniz eşyayı tablodan seçin!")
            return
        item_vals = self.wl_tree.item(selected[0])['values']
        item_id = item_vals[0]

        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM takip_listesi WHERE id = %s;", (item_id,))
                conn.commit()
            conn.close()
            self.refresh_watchlist_table()
        except Exception as e:
            messagebox.showerror("Hata", f"Silinemedi: {e}")

    def refresh_watchlist_table(self):
        threading.Thread(target=self._fetch_watchlist_thread, daemon=True).start()

    def _fetch_watchlist_thread(self):
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, esya, hedef_fiyat, ekleme_tarihi FROM takip_listesi ORDER BY id DESC;")
                rows = cur.fetchall()
            conn.close()

            self.after(0, lambda: self._update_wl_tree(rows))
        except Exception as e:
            print("Takip Listesi Çekme Hatası:", e)

    def _update_wl_tree(self, rows):
        self.wl_tree.delete(*self.wl_tree.get_children())
        for r in rows:
            t_str = f"${r['hedef_fiyat']:.2f}" if r['hedef_fiyat'] else "-"
            dt_str = r['ekleme_tarihi'].strftime('%d.%m.%Y %H:%M') if r['ekleme_tarihi'] else "-"
            self.wl_tree.insert("", "end", values=(r['id'], r['esya'], t_str, dt_str))
        self.wl_count_label.configure(text=f"Takip Edilen: {len(rows)} eşya")

    def scan_watchlist_items(self):
        items = [self.wl_tree.item(child)['values'][1] for child in self.wl_tree.get_children()]
        if not items:
            messagebox.showinfo("Liste Boş", "Takip listenizde henüz taranacak eşya bulunmuyor. Önce yukarıdan eşya ekleyin!")
            return
        self.tabview.set("🔍 Eşya Tarama & Paketler")
        self.start_batch_scan(items, scan_wears=False)

    # ------------------ SEKME 3: NEON VERİTABANI TABLOSU ------------------
    def setup_database_tab(self):
        top_bar = ctk.CTkFrame(self.tab_database, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(10, 5))

        self.table_search_entry = ctk.CTkEntry(
            top_bar, placeholder_text="Eşya adıyla anlık filtrele...", width=320, height=36
        )
        self.table_search_entry.pack(side="left", padx=(0, 10))
        self.table_search_entry.bind("<KeyRelease>", lambda e: self.filter_table())

        refresh_btn = ctk.CTkButton(
            top_bar, text="🔄 Yenile", width=100, height=36, command=self.refresh_database_table
        )
        refresh_btn.pack(side="left", padx=5)

        self.table_count_label = ctk.CTkLabel(top_bar, text="", font=ctk.CTkFont(size=13), text_color="#8d99ae")
        self.table_count_label.pack(side="right", padx=10)

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
        self.tree.heading("tarama", text="Tarama")

        self.tree.column("esya", width=340, anchor="w")
        self.tree.column("guncel", width=100, anchor="center")
        self.tree.column("min", width=90, anchor="center")
        self.tree.column("max", width=90, anchor="center")
        self.tree.column("hacim", width=110, anchor="center")
        self.tree.column("zaman", width=150, anchor="center")
        self.tree.column("tarama", width=80, anchor="center")

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

        self.table_count_label.configure(text=f"Listelenen: {filtered_count} eşya")

    # ------------------ SEKME 4: PİYASA ANALİZLERİ ------------------
    def setup_analytics_tab(self):
        control_bar = ctk.CTkFrame(self.tab_analytics, fg_color="transparent")
        control_bar.pack(fill="x", padx=10, pady=(10, 5))

        anomali_btn = ctk.CTkButton(
            control_bar, text="🧠 Aşınma & Arbitraj Analizi Yap", font=ctk.CTkFont(weight="bold"),
            command=self.run_anomali_analysis
        )
        anomali_btn.pack(side="left", padx=(0, 10))

        likidite_btn = ctk.CTkButton(
            control_bar, text="💧 Likidite & Risk Analizi Yap", font=ctk.CTkFont(weight="bold"),
            command=self.run_likidite_analysis
        )
        likidite_btn.pack(side="left", padx=5)

        self.analytics_textbox = ctk.CTkTextbox(
            self.tab_analytics, font=ctk.CTkFont(family="Consolas", size=13),
            fg_color="#1e1e24", corner_radius=10
        )
        self.analytics_textbox.pack(fill="both", expand=True, padx=10, pady=10)
        self.analytics_textbox.insert("1.0", "Yukarıdaki butonlara basarak veritabanınızdaki pazar analizlerini anında çalıştırabilirsiniz.\n\n"
                                             "• Aşınma & Arbitraj: Well-Worn > Field-Tested gibi fiyat tutarsızlıklarını yakalar.\n"
                                             "• Likidite & Risk: 24 saatlik işlem hacmine göre alım/satım risk kategorilerini belirler.")

    def run_anomali_analysis(self):
        threading.Thread(target=self._anomali_thread, daemon=True).start()

    def _anomali_thread(self):
        wear_order = {"Factory New": 1, "Minimal Wear": 2, "Field-Tested": 3, "Well-Worn": 4, "Battle-Scarred": 5}
        try:
            conn = self.get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT DISTINCT ON (esya) esya, fiyat_sayisal, hacim_sayisal
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
                    gruplar[skin][w] = {'fiyat': float(r['fiyat_sayisal']), 'hacim': r['hacim_sayisal']}

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

            self.after(0, lambda: self._update_analytics_text("\n".join(out)))
        except Exception as e:
            self.after(0, lambda: self._update_analytics_text(f"Hata oluştu: {e}"))

    def run_likidite_analysis(self):
        threading.Thread(target=self._likidite_thread, daemon=True).start()

    def _likidite_thread(self):
        try:
            conn = self.get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT DISTINCT ON (esya) esya, fiyat_sayisal, hacim_sayisal
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

            self.after(0, lambda: self._update_analytics_text("\n".join(out)))
        except Exception as e:
            self.after(0, lambda: self._update_analytics_text(f"Hata oluştu: {e}"))

    def _update_analytics_text(self, content):
        self.analytics_textbox.delete("1.0", "end")
        self.analytics_textbox.insert("1.0", content)


if __name__ == "__main__":
    app = CS2MarketApp()
    app.mainloop()
