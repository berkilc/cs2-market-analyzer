import os
import re
import sys
import json
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

# ==============================================================================
# 🎨 KİŞİSELLEŞTİRME VE RENK PALETLERİ
# ==============================================================================
THEMES = {
    "Cyberpunk Cyan": {
        "primary": "#00b4d8",
        "hover": "#0077b6",
        "accent": "#00f0ff",
        "card_bg": "#161b26",
        "card_border": "#1e293b",
        "text_accent": "#00f0ff",
        "badge_color": "#00b4d8",
        "ctk_theme": "blue"
    },
    "Nebula Purple": {
        "primary": "#7c3aed",
        "hover": "#6d28d9",
        "accent": "#a78bfa",
        "card_bg": "#1c192b",
        "card_border": "#2e284a",
        "text_accent": "#c4b5fd",
        "badge_color": "#8b5cf6",
        "ctk_theme": "dark-blue"
    },
    "Emerald Profit": {
        "primary": "#10b981",
        "hover": "#059669",
        "accent": "#34d399",
        "card_bg": "#13231c",
        "card_border": "#1d382c",
        "text_accent": "#6ee7b7",
        "badge_color": "#10b981",
        "ctk_theme": "green"
    },
    "Inferno Amber": {
        "primary": "#f59e0b",
        "hover": "#d97706",
        "accent": "#fbbf24",
        "card_bg": "#241d13",
        "card_border": "#3b2e1b",
        "text_accent": "#fde68a",
        "badge_color": "#f59e0b",
        "ctk_theme": "blue"
    },
    "Crimson Web": {
        "primary": "#ef4444",
        "hover": "#dc2626",
        "accent": "#f87171",
        "card_bg": "#241316",
        "card_border": "#3d1b22",
        "text_accent": "#fca5a5",
        "badge_color": "#ef4444",
        "ctk_theme": "blue"
    }
}

SETTINGS_FILE = os.path.join(base_dir, "settings.json")


def load_settings():
    defaults = {
        "accent_theme": "Cyberpunk Cyan",
        "appearance_mode": "Dark"
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**defaults, **data}
        except Exception:
            pass
    return defaults


def save_settings(settings_dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings_dict, f, indent=2)
    except Exception as e:
        print("Ayar kaydetme hatası:", e)


# ==============================================================================
# HAZIR PRESET LİSTELERİ
# ==============================================================================
CASES_PRESET = [
    "Gallery Case", "Kilowatt Case", "Revolution Case", "Dreams & Nightmares Case",
    "Recoil Case", "Snakebite Case", "Fracture Case", "Prisma 2 Case",
    "Danger Zone Case", "Horizon Case", "Spectrum 2 Case", "Clutch Case", "Glove Case"
]

POPULAR_SKINS_PRESET = [
    "AK-47 | Redline", "AK-47 | Slate", "AWP | Asiimov", "AWP | Atheris",
    "M4A1-S | Printstream", "M4A4 | The Emperor", "Desert Eagle | Printstream",
    "USP-S | The Traitor", "Glock-18 | Water Elemental"
]


# ==============================================================================
# ANA UYGULAMA SINIFI
# ==============================================================================
class CS2MarketApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Ayarları Yükle
        self.settings = load_settings()
        self.active_theme_name = self.settings.get("accent_theme", "Cyberpunk Cyan")
        if self.active_theme_name not in THEMES:
            self.active_theme_name = "Cyberpunk Cyan"
        self.theme = THEMES[self.active_theme_name]

        ctk.set_appearance_mode(self.settings.get("appearance_mode", "Dark"))
        ctk.set_default_color_theme(self.theme.get("ctk_theme", "blue"))

        self.title("🎮 CS2 Market Analyzer & Pro Dashboard")
        self.geometry("1160x820")
        self.minsize(1020, 700)

        self.is_scanning = False
        self.stop_requested = False
        self._search_timer = None
        self._wl_search_timer = None
        self._catalog_search_timer = None

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
            self.after(0, self.filter_catalog_table)
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
        # ÜST BAŞLIK BARI
        header_frame = ctk.CTkFrame(self, fg_color="#131620", corner_radius=0, height=65)
        header_frame.pack(fill="x", side="top")

        left_header = ctk.CTkFrame(header_frame, fg_color="transparent")
        left_header.pack(side="left", padx=20, pady=12)

        title_label = ctk.CTkLabel(
            left_header, 
            text="🎮 CS2 Market Analyzer & Pro Dashboard", 
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#ffffff"
        )
        title_label.pack(side="left")

        self.theme_indicator = ctk.CTkLabel(
            left_header,
            text=f"  🎨 {self.active_theme_name}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.theme["accent"]
        )
        self.theme_indicator.pack(side="left", padx=(10, 0))

        self.status_badge = ctk.CTkLabel(
            header_frame,
            text="⏳ Neon Bağlantısı Kontrol Ediliyor...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#f39c12"
        )
        self.status_badge.pack(side="right", padx=25, pady=15)

        # Sekmeli Görünüm (Tabview) - 5 TANE SEKME
        self.tabview = ctk.CTkTabview(self, corner_radius=12)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(12, 18))

        self.tab_scan = self.tabview.add("🔍 Eşya Tarama & Paketler")
        self.tab_watchlist = self.tabview.add("📌 Takip Listem (Portföy)")
        self.tab_catalog = self.tabview.add("📚 CS2 Eşya Kataloğu (20.663)")
        self.tab_database = self.tabview.add("📋 Pazar Tablosu & Analizler")
        self.tab_settings = self.tabview.add("🎨 Görünüm & Kişiselleştirme")

        self.setup_scan_tab()
        self.setup_watchlist_tab()
        self.setup_catalog_tab()
        self.setup_database_tab()
        self.setup_settings_tab()

    # ------------------ SEKME 1: EŞYA TARAMA & PAKETLER ------------------
    def setup_scan_tab(self):
        search_card = ctk.CTkFrame(self.tab_scan, fg_color=self.theme["card_bg"], corner_radius=12)
        search_card.pack(fill="x", padx=10, pady=(10, 6))

        input_container = ctk.CTkFrame(search_card, fg_color="transparent")
        input_container.pack(fill="x", padx=15, pady=(12, 6))

        self.item_entry = ctk.CTkEntry(
            input_container,
            placeholder_text="Eşya adını yazın (Örn: 2020 RMR Contenders, AWP Asiimov, Gallery Case)...",
            height=42,
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
            height=42,
            width=150,
            fg_color=self.theme["primary"],
            hover_color=self.theme["hover"],
            command=self.start_single_scan
        )
        self.scan_btn.pack(side="right")

        # Otomatik Arama Önerileri Kutusu
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
            font=ctk.CTkFont(size=12, weight="bold"), command=self.scan_steam_trends_fast
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

        # Satır 2: 20,663 Eşyalık Katalogdan Kategori Tarama
        row2 = ctk.CTkFrame(self.preset_card, fg_color="transparent")
        row2.pack(fill="x", pady=(2, 2))

        cat_lbl = ctk.CTkLabel(row2, text="📚 20,663'lük Katalog:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#a5adcb")
        cat_lbl.pack(side="left", padx=(0, 8))

        self.cat_combobox = ctk.CTkComboBox(
            row2,
            values=[
                "Kategori Seçin...",
                "📦 Kasa & Kapsül (479)",
                "🏷️ Çıkartmalar (11132)",
                "🔪 Bıçaklar (1714)",
                "🧤 Eldivenler (470)",
                "🔫 Tüfekler (2302)",
                "💥 Tabancalar (2023)",
                "⚡ Hafif Makineliler (1433)",
                "🛡️ Ağır Silahlar (1012)",
                "🕵️ Ajanlar (63)"
            ],
            width=220,
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
            row2, text="🚀 Kategoriyi Tara", height=30, width=130, fg_color=self.theme["primary"],
            hover_color=self.theme["hover"], font=ctk.CTkFont(size=12, weight="bold"),
            command=self.scan_selected_category
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
            text="İster tek bir eşya arayın, ister 20,663 eşyalık katalogdan dilediğiniz kategoriyi tarayın.",
            font=ctk.CTkFont(size=13),
            text_color="#8d99ae"
        )
        self.scan_status_label.pack(anchor="w", padx=15, pady=(4, 4))

        # Sonuç Kartları Alanı
        self.results_scroll = ctk.CTkScrollableFrame(
            self.tab_scan, 
            fg_color="#151722",
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
                fg_color="#202434",
                hover_color=self.theme["primary"],
                font=ctk.CTkFont(size=12),
                command=lambda n=name: self._select_suggestion(n)
            )
            btn.pack(fill="x", padx=6, pady=2)

    def _select_suggestion(self, name):
        self.item_entry.delete(0, 'end')
        self.item_entry.insert(0, name)
        self.suggestions_frame.pack_forget()

    # ------------------ TEK VE ÇOKLU TARAMA METOTLARI ------------------
    def start_single_scan(self):
        if self.is_scanning:
            return
        item_text = self.item_entry.get().strip()
        if not item_text:
            messagebox.showwarning("Eksik Bilgi", "Lütfen bir eşya adı girin!")
            return
        scan_wears = bool(self.wear_checkbox.get())
        self.start_batch_scan([item_text], scan_wears=scan_wears)

    def scan_from_file(self):
        if self.is_scanning:
            return
        file_path = os.path.join(base_dir, "items.txt")
        if not os.path.exists(file_path):
            file_path = filedialog.askopenfilename(
                title="Eşya Listesi Dosyasını Seçin",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
            )
            if not file_path:
                return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
            if not lines:
                messagebox.showinfo("Dosya Boş", f"{file_path} dosyasında taranacak eşya bulunamadı.")
                return
            self.start_batch_scan(lines, scan_wears=False)
        except Exception as e:
            messagebox.showerror("Hata", f"Dosya okunurken hata oluştu: {e}")

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

    def scan_selected_category(self):
        if self.is_scanning:
            return
        val = self.cat_combobox.get()
        if "Kategori Seçin" in val:
            messagebox.showwarning("Seçim Yapın", "Lütfen önce bir kategori seçin!")
            return

        cat_name = val.split("(")[0].strip()
        for emoji in ["📦", "🔪", "🧤", "🔫", "💥", "⚡", "🛡️", "🏷️", "🕵️"]:
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
        if messagebox.askyesno("Kataloğu Güncelle", "CS2 API üzerinden ~20.000 eşya indirilip Neon Bulut veritabanı güncellenecek. Devam edilsin mi?"):
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
        card = ctk.CTkFrame(self.results_scroll, fg_color=self.theme["card_bg"], corner_radius=8)
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

        price_label = ctk.CTkLabel(right_frame, text=f"{fiyat_str}", font=ctk.CTkFont(size=17, weight="bold"), text_color=self.theme["accent"])
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
        add_bar = ctk.CTkFrame(self.tab_watchlist, fg_color=self.theme["card_bg"], corner_radius=10)
        add_bar.pack(fill="x", padx=10, pady=10)

        c = ctk.CTkFrame(add_bar, fg_color="transparent")
        c.pack(fill="x", padx=15, pady=12)

        self.wl_item_entry = ctk.CTkEntry(
            c, placeholder_text="Takip etmek istediğiniz eşya (Örn: 2020 RMR Contenders, AWP Asiimov)...",
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
            fg_color=self.theme["primary"], hover_color=self.theme["hover"],
            command=self.add_to_watchlist
        )
        add_btn.pack(side="left")

        # Takip Listesi Katalog Öneri Paneli
        self.wl_suggestions_frame = ctk.CTkFrame(add_bar, fg_color="#181a24", corner_radius=8)

        btn_bar = ctk.CTkFrame(self.tab_watchlist, fg_color="transparent")
        btn_bar.pack(fill="x", padx=10, pady=(0, 6))

        scan_wl_btn = ctk.CTkButton(
            btn_bar, text="🚀 Takip Listemdekileri Tara", height=36, fg_color=self.theme["primary"],
            hover_color=self.theme["hover"], font=ctk.CTkFont(weight="bold"), command=self.scan_watchlist_items
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

        table_frame = ctk.CTkFrame(self.tab_watchlist, fg_color="#181924", corner_radius=10)
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
                fg_color="#202434",
                hover_color=self.theme["primary"],
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
        row = self.wl_tree.item(selected[0])['values']
        item_id = row[0]
        item_name = row[1]

        if messagebox.askyesno("Onay", f"'{item_name}' takip listenizden silinsin mi?"):
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
        for item in self.wl_tree.get_children():
            self.wl_tree.delete(item)

        try:
            conn = self.get_db_connection()
            if not conn:
                return
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, esya, hedef_fiyat, ekleme_tarihi
                    FROM takip_listesi
                    ORDER BY id DESC;
                """)
                rows = cur.fetchall()
            conn.close()

            for r in rows:
                hedef_str = f"${r['hedef_fiyat']:.2f}" if r['hedef_fiyat'] else "-"
                tarih_str = r['ekleme_tarihi'].strftime("%Y-%m-%d %H:%M") if r['ekleme_tarihi'] else "-"
                self.wl_tree.insert("", "end", values=(r['id'], r['esya'], hedef_str, tarih_str))

            self.wl_count_label.configure(text=f"Takip Edilen: {len(rows)} Eşya")
        except Exception as e:
            print("Takip Listesi Yükleme Hatası:", e)

    def scan_watchlist_items(self):
        if self.is_scanning:
            return
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT esya, hedef_fiyat FROM takip_listesi ORDER BY id ASC;")
                items = cur.fetchall()
            conn.close()
        except Exception as e:
            messagebox.showerror("Hata", f"Takip listesi okunamadı: {e}")
            return

        if not items:
            messagebox.showinfo("Liste Boş", "Takip listenizde taranacak eşya bulunmuyor.")
            return

        self.tabview.set("🔍 Eşya Tarama & Paketler")
        raw_names = [it['esya'] for it in items]
        self.start_batch_scan(raw_names, scan_wears=False)

    # ------------------ SEKME 3: CS2 EŞYA KATALOĞU (20.663 EŞYA) ------------------
    def setup_catalog_tab(self):
        filter_bar = ctk.CTkFrame(self.tab_catalog, fg_color=self.theme["card_bg"], corner_radius=10)
        filter_bar.pack(fill="x", padx=10, pady=10)

        f_inner = ctk.CTkFrame(filter_bar, fg_color="transparent")
        f_inner.pack(fill="x", padx=15, pady=10)

        self.catalog_search_entry = ctk.CTkEntry(
            f_inner, placeholder_text="Katalogda ara (Örn: 2020 rmr, karambit, printstream, case)...",
            height=38, font=ctk.CTkFont(size=13)
        )
        self.catalog_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.catalog_search_entry.bind("<KeyRelease>", self._on_catalog_filter_key_release)

        self.catalog_cat_filter = ctk.CTkComboBox(
            f_inner,
            values=[
                "Tüm Kategoriler (20.663)",
                "📦 Kasa & Kapsül",
                "🏷️ Çıkartmalar",
                "🔪 Bıçaklar",
                "🧤 Eldivenler",
                "🔫 Tüfekler",
                "💥 Tabancalar",
                "⚡ Hafif Makineliler",
                "🛡️ Ağır Silahlar",
                "🕵️ Ajanlar"
            ],
            width=210,
            height=38,
            command=lambda v: self.filter_catalog_table()
        )
        self.catalog_cat_filter.pack(side="left", padx=(0, 10))

        btn_filter = ctk.CTkButton(
            f_inner, text="🔍 Filtrele", width=90, height=38, fg_color=self.theme["primary"],
            hover_color=self.theme["hover"], command=self.filter_catalog_table
        )
        btn_filter.pack(side="left")

        # Tablo Alanı
        table_frame = ctk.CTkFrame(self.tab_catalog, fg_color="#181924", corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        columns = ("esya", "kategori", "alt_kat", "silah")
        self.catalog_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.catalog_tree.heading("esya", text="Eşya Adı")
        self.catalog_tree.heading("kategori", text="Kategori")
        self.catalog_tree.heading("alt_kat", text="Nadirlik / Tip")
        self.catalog_tree.heading("silah", text="Silah / Tür")

        self.catalog_tree.column("esya", width=420, anchor="w")
        self.catalog_tree.column("kategori", width=140, anchor="center")
        self.catalog_tree.column("alt_kat", width=140, anchor="center")
        self.catalog_tree.column("silah", width=120, anchor="center")

        scrollbar_cat = ttk.Scrollbar(table_frame, orient="vertical", command=self.catalog_tree.yview)
        self.catalog_tree.configure(yscrollcommand=scrollbar_cat.set)
        scrollbar_cat.pack(side="right", fill="y")
        self.catalog_tree.pack(fill="both", expand=True, padx=5, pady=5)

        # Alt Buton Çubuğu
        act_bar = ctk.CTkFrame(self.tab_catalog, fg_color="transparent")
        act_bar.pack(fill="x", padx=10, pady=(0, 8))

        btn_scan_selected = ctk.CTkButton(
            act_bar, text="🚀 Seçilenin Canlı Fiyatını Çek & Kaydet", height=36,
            fg_color=self.theme["primary"], hover_color=self.theme["hover"], font=ctk.CTkFont(weight="bold"),
            command=self.scan_selected_catalog_item
        )
        btn_scan_selected.pack(side="left", padx=(0, 10))

        btn_add_to_wl = ctk.CTkButton(
            act_bar, text="⭐ Takip Listeme Ekle", height=36,
            fg_color="#3a0ca3", hover_color="#4361ee", font=ctk.CTkFont(weight="bold"),
            command=self.add_selected_catalog_to_watchlist
        )
        btn_add_to_wl.pack(side="left", padx=4)

        self.catalog_count_lbl = ctk.CTkLabel(act_bar, text="Yükleniyor...", font=ctk.CTkFont(size=12), text_color="#8d99ae")
        self.catalog_count_lbl.pack(side="right", padx=10)

    def _on_catalog_filter_key_release(self, event):
        if self._catalog_search_timer:
            self.after_cancel(self._catalog_search_timer)
        self._catalog_search_timer = self.after(300, self.filter_catalog_table)

    def filter_catalog_table(self):
        query = self.catalog_search_entry.get().strip() if hasattr(self, 'catalog_search_entry') else ""
        cat = self.catalog_cat_filter.get() if hasattr(self, 'catalog_cat_filter') else "Tümü"

        threading.Thread(target=self._catalog_loader_thread, args=(query, cat), daemon=True).start()

    def _catalog_loader_thread(self, query, cat):
        count, rows = ky.katalog_filtrele(query, cat, limit=150)
        self.after(0, lambda: self._populate_catalog_tree(count, rows))

    def _populate_catalog_tree(self, count, rows):
        for item in self.catalog_tree.get_children():
            self.catalog_tree.delete(item)

        for r in rows:
            self.catalog_tree.insert("", "end", values=(
                r['esya_adi'],
                r['kategori'],
                r['alt_kategori'] or '-',
                r['silah'] or '-'
            ))

        self.catalog_count_lbl.configure(text=f"Listelenen: {len(rows)} / Toplam Eşleşen: {count:,}")

    def scan_selected_catalog_item(self):
        sel = self.catalog_tree.selection()
        if not sel:
            messagebox.showwarning("Seçim Yok", "Lütfen tablodan fiyatını çekmek istediğiniz eşyayı seçin!")
            return
        item_name = self.catalog_tree.item(sel[0])['values'][0]

        self.tabview.set("🔍 Eşya Tarama & Paketler")
        self.item_entry.delete(0, 'end')
        self.item_entry.insert(0, item_name)
        self.start_batch_scan([item_name], scan_wears=False)

    def add_selected_catalog_to_watchlist(self):
        sel = self.catalog_tree.selection()
        if not sel:
            messagebox.showwarning("Seçim Yok", "Lütfen takip listesine eklemek istediğiniz eşyayı tablodan seçin!")
            return
        item_name = self.catalog_tree.item(sel[0])['values'][0]

        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO takip_listesi (esya) 
                    VALUES (%s)
                    ON CONFLICT (esya) DO NOTHING;
                """, (item_name,))
                conn.commit()
            conn.close()
            self.refresh_watchlist_table()
            messagebox.showinfo("Başarılı", f"'{item_name}' takip listenize eklendi!")
        except Exception as e:
            messagebox.showerror("Hata", f"Eklenemedi: {e}")

    # ------------------ SEKME 4: NEON VERİTABANI TABLOSU & ANALİZLER ------------------
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

        anomali_btn = ctk.CTkButton(
            top_bar, text="🧠 Aşınma Arbitrajı", height=36, fg_color="#3a0ca3", hover_color="#4361ee",
            command=self.run_anomali_analysis
        )
        anomali_btn.pack(side="left", padx=5)

        likidite_btn = ctk.CTkButton(
            top_bar, text="💧 Likidite Riski", height=36, fg_color="#2b9348", hover_color="#55a630",
            command=self.run_likidite_analysis
        )
        likidite_btn.pack(side="left", padx=5)

        self.table_count_label = ctk.CTkLabel(top_bar, text="", font=ctk.CTkFont(size=13), text_color="#8d99ae")
        self.table_count_label.pack(side="right", padx=10)

        # Tablo Alanı
        table_frame = ctk.CTkFrame(self.tab_database, fg_color="#181924", corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=6)

        columns = ("esya", "guncel", "min", "max", "hacim", "zaman", "tarama")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("esya", text="Eşya Adı")
        self.tree.heading("guncel", text="Son Fiyat ($)")
        self.tree.heading("min", text="Min ($)")
        self.tree.heading("max", text="Maks ($)")
        self.tree.heading("hacim", text="24s Hacim")
        self.tree.heading("zaman", text="Son Güncelleme")
        self.tree.heading("tarama", text="Kayıt")

        self.tree.column("esya", width=340, anchor="w")
        self.tree.column("guncel", width=100, anchor="center")
        self.tree.column("min", width=90, anchor="center")
        self.tree.column("max", width=90, anchor="center")
        self.tree.column("hacim", width=120, anchor="center")
        self.tree.column("zaman", width=150, anchor="center")
        self.tree.column("tarama", width=80, anchor="center")

        scrollbar_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar_y.set)
        scrollbar_y.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)

        # Analiz Sonuç Kutusu (Gerektiğinde açılır)
        self.analytics_textbox = ctk.CTkTextbox(
            self.tab_database,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#131620",
            corner_radius=8,
            height=130
        )
        self.analytics_textbox.pack(fill="x", padx=10, pady=(0, 8))
        self.analytics_textbox.insert("1.0", "💡 'Aşınma Arbitrajı' veya 'Likidite Riski' butonlarına tıklayarak analiz raporlarını burada görüntüleyebilirsiniz.\n")

    def filter_table(self):
        query = self.table_search_entry.get().lower().strip()
        for item in self.tree.get_children():
            self.tree.delete(item)

        filtered = [r for r in getattr(self, "_cached_db_rows", []) if query in r['esya'].lower()]
        self._populate_table(filtered)

    def refresh_database_table(self):
        threading.Thread(target=self._db_loader_thread, daemon=True).start()

    def _db_loader_thread(self):
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    WITH son_kayitlar AS (
                        SELECT DISTINCT ON (esya) 
                            esya, fiyat_sayisal, hacim_sayisal, kayit_tarihi
                        FROM pazar_verileri
                        ORDER BY esya, id DESC
                    ),
                    istatistikler AS (
                        SELECT 
                            esya,
                            MIN(fiyat_sayisal) as min_fiyat,
                            MAX(fiyat_sayisal) as max_fiyat,
                            COUNT(*) as kayit_adet
                        FROM pazar_verileri
                        WHERE fiyat_sayisal IS NOT NULL
                        GROUP BY esya
                    )
                    SELECT 
                        s.esya,
                        s.fiyat_sayisal as son_fiyat,
                        s.hacim_sayisal as son_hacim,
                        s.kayit_tarihi as son_tarih,
                        i.min_fiyat,
                        i.max_fiyat,
                        i.kayit_adet
                    FROM son_kayitlar s
                    LEFT JOIN istatistikler i ON s.esya = i.esya
                    ORDER BY s.kayit_tarihi DESC;
                """)
                rows = cur.fetchall()
            conn.close()

            self._cached_db_rows = rows
            self.after(0, lambda: self._populate_table(rows))
        except Exception as e:
            print("Veritabanı Tablo Hatası:", e)

    def _populate_table(self, rows):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for r in rows:
            fiyat_str = f"${r['son_fiyat']:.2f}" if r['son_fiyat'] is not None else "-"
            min_str = f"${r['min_fiyat']:.2f}" if r['min_fiyat'] is not None else "-"
            max_str = f"${r['max_fiyat']:.2f}" if r['max_fiyat'] is not None else "-"
            hacim_str = f"{r['son_hacim']:,}" if r['son_hacim'] is not None else "Yok"
            zaman_str = r['son_tarih'].strftime("%Y-%m-%d %H:%M") if r['son_tarih'] else "-"

            self.tree.insert("", "end", values=(
                r['esya'],
                fiyat_str,
                min_str,
                max_str,
                hacim_str,
                zaman_str,
                f"{r['kayit_adet']} kez"
            ))

        self.table_count_label.configure(text=f"Listelenen Eşya: {len(rows)}")

    def _update_analytics_text(self, text):
        self.analytics_textbox.delete("1.0", "end")
        self.analytics_textbox.insert("1.0", text)

    def run_anomali_analysis(self):
        self._update_analytics_text("🧠 Veritabanındaki aşınma seviyeleri taranıyor ve arbitraj analizi yapılıyor...")
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
                m = re.match(r"^(.*?)\s*\((Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)\)$", r['esya'])
                if m:
                    skin = m.group(1).strip()
                    w = m.group(2)
                    if skin not in gruplar:
                        gruplar[skin] = {}
                    gruplar[skin][w] = {'fiyat': float(r['fiyat_sayisal']), 'hacim': r['hacim_sayisal']}

            out = ["═" * 70, "🧠 AŞINMA SEVİYESİ & FİYAT ANOMALİ / ARBİTRAJ ANALİZİ", "═" * 70, ""]
            anomali_var = False

            for skin, wears in gruplar.items():
                mevcut = [w for w in wear_order if w in wears]
                if len(mevcut) < 2:
                    continue

                for i in range(len(mevcut) - 1):
                    ust = mevcut[i]
                    alt = mevcut[i+1]
                    f_ust = wears[ust]['fiyat']
                    f_alt = wears[alt]['fiyat']

                    if f_ust < f_alt:
                        anomali_var = True
                        out.append(f"🚨 FİYAT ANOMALİSİ / ARBİTRAJ FIRSATI TESPİT EDİLDİ!")
                        out.append(f"   Skin: {skin}")
                        out.append(f"   Daha İyi Aşınma: {ust:<15} -> ${f_ust:.2f}")
                        out.append(f"   Daha Kötü Aşınma: {alt:<15} -> ${f_alt:.2f}")
                        out.append(f"   💡 Normalde {ust} daha pahalı olmalıdır! Mantıksız piyasa fiyatlaması var.\n")

            if not anomali_var:
                out.append("✅ Tüm aşınma sıralamaları piyasa normlarına uygun görünüyor.")

            self.after(0, lambda: self._update_analytics_text("\n".join(out)))
        except Exception as e:
            self.after(0, lambda: self._update_analytics_text(f"Hata oluştu: {e}"))

    def run_likidite_analysis(self):
        self._update_analytics_text("💧 Pazar verileri likidite ve hacim riskine göre analiz ediliyor...")
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

            yuksek = [r for r in rows if r['hacim_sayisal'] >= 1000]
            orta = [r for r in rows if 100 <= r['hacim_sayisal'] < 1000]
            dusuk = [r for r in rows if r['hacim_sayisal'] < 100]

            out = ["═" * 70, "💧 LİKİDİTE VE TİCARET RİSK ANALİZİ (24 SAATLİK HACİM)", "═" * 70, ""]
            out.append(f"🟢 Yüksek Likidite (1.000+ Adet/24s) : {len(yuksek)} eşya  -> Hızlı satılır, arbitraj için ideal")
            out.append(f"🟡 Orta Likidite   (100 - 1.000 Adet) : {len(orta)} eşya  -> Dengeli piyasa")
            out.append(f"🔴 Düşük / İllikit (< 100 Adet)       : {len(dusuk)} eşya  -> Satılması zor, sermaye bağlanabilir!\n")

            out.append("--- 🔥 EN ÇOK İŞLEM GÖREN İLK 5 LİKİT EŞYA ---")
            for r in sorted(yuksek, key=lambda x: x['hacim_sayisal'], reverse=True)[:5]:
                out.append(f"   • {r['esya']:<36} | Hacim: {r['hacim_sayisal']:,} adet | Fiyat: ${r['fiyat_sayisal']}")

            out.append("\n--- ⚠️ DÜŞÜK HACİMLİ (RİSKLİ) EŞYALAR ---")
            for r in sorted(dusuk, key=lambda x: x['hacim_sayisal'], reverse=True):
                out.append(f"   • {r['esya']:<36} | Hacim: {r['hacim_sayisal']:,} adet | Fiyat: ${r['fiyat_sayisal']}")

            self.after(0, lambda: self._update_analytics_text("\n".join(out)))
        except Exception as e:
            self.after(0, lambda: self._update_analytics_text(f"Hata oluştu: {e}"))

    # ------------------ SEKME 5: GÖRÜNÜM & KİŞİSELLEŞTİRME ------------------
    def setup_settings_tab(self):
        container = ctk.CTkScrollableFrame(self.tab_settings, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=15)

        # Kart 1: Renk Teması Seçimi
        theme_card = ctk.CTkFrame(container, fg_color=self.theme["card_bg"], corner_radius=12)
        theme_card.pack(fill="x", pady=(0, 15), padx=5)

        t_title = ctk.CTkLabel(theme_card, text="🎨 Renk Teması & Stil Tercihleri", font=ctk.CTkFont(size=16, weight="bold"))
        t_title.pack(anchor="w", padx=20, pady=(15, 6))

        t_desc = ctk.CTkLabel(
            theme_card, 
            text="Uygulamanın genel havasını ve vurgu renklerini dilediğiniz gibi kişiselleştirebilirsiniz.\nSeçiminiz otomatik olarak kaydedilir ve bir sonraki açılışta hatırlanır.",
            font=ctk.CTkFont(size=12), text_color="#8d99ae", justify="left"
        )
        t_desc.pack(anchor="w", padx=20, pady=(0, 12))

        theme_buttons_frame = ctk.CTkFrame(theme_card, fg_color="transparent")
        theme_buttons_frame.pack(fill="x", padx=20, pady=(0, 20))

        theme_list = [
            ("⚡ Cyberpunk Cyan", "Cyberpunk Cyan", "#00b4d8"),
            ("💜 Nebula Purple", "Nebula Purple", "#8b5cf6"),
            ("🟢 Emerald Profit", "Emerald Profit", "#10b981"),
            ("🔥 Inferno Amber", "Inferno Amber", "#f59e0b"),
            ("🔴 Crimson Web", "Crimson Web", "#ef4444")
        ]

        for label_text, t_key, col in theme_list:
            is_active = (t_key == self.active_theme_name)
            border_w = 2 if is_active else 0
            btn = ctk.CTkButton(
                theme_buttons_frame,
                text=label_text,
                height=38,
                fg_color=col,
                hover_color=col,
                border_width=border_w,
                border_color="#ffffff",
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda k=t_key: self.change_accent_theme(k)
            )
            btn.pack(side="left", padx=5, expand=True, fill="x")

        # Kart 2: Görünüm Modu (Koyu / Açık)
        mode_card = ctk.CTkFrame(container, fg_color=self.theme["card_bg"], corner_radius=12)
        mode_card.pack(fill="x", pady=(0, 15), padx=5)

        m_title = ctk.CTkLabel(mode_card, text="🌓 Görünüm Modu", font=ctk.CTkFont(size=16, weight="bold"))
        m_title.pack(anchor="w", padx=20, pady=(15, 6))

        m_inner = ctk.CTkFrame(mode_card, fg_color="transparent")
        m_inner.pack(fill="x", padx=20, pady=(0, 20))

        self.mode_menu = ctk.CTkOptionMenu(
            m_inner,
            values=["Dark", "Light", "System"],
            width=180,
            height=36,
            command=self.change_appearance_mode
        )
        self.mode_menu.set(self.settings.get("appearance_mode", "Dark"))
        self.mode_menu.pack(side="left")

        # Kart 3: Neon Bulut & Sistem Sağlığı
        db_card = ctk.CTkFrame(container, fg_color=self.theme["card_bg"], corner_radius=12)
        db_card.pack(fill="x", pady=(0, 15), padx=5)

        db_title = ctk.CTkLabel(db_card, text="⚡ Veritabanı ve Sistem Bilgileri", font=ctk.CTkFont(size=16, weight="bold"))
        db_title.pack(anchor="w", padx=20, pady=(15, 8))

        self.db_info_label = ctk.CTkLabel(
            db_card,
            text=f"• Bağlantı: Neon PostgreSQL Cloud Active\n• Toplam Eşya Kataloğu: 20,663 Eşya Hazır\n• Yapılandırma Dosyası: {SETTINGS_FILE}",
            font=ctk.CTkFont(size=12), text_color="#cad3f5", justify="left"
        )
        self.db_info_label.pack(anchor="w", padx=20, pady=(0, 12))

        btn_test_db = ctk.CTkButton(
            db_card, text="🔄 Veritabanı Durumunu Yeniden Kontrol Et", width=250, height=36,
            fg_color=self.theme["primary"], hover_color=self.theme["hover"], command=self.check_initial_db_status
        )
        btn_test_db.pack(anchor="w", padx=20, pady=(0, 18))

    def change_accent_theme(self, theme_name):
        if theme_name in THEMES:
            self.active_theme_name = theme_name
            self.theme = THEMES[theme_name]
            self.settings["accent_theme"] = theme_name
            save_settings(self.settings)

            # Temayı güncelle
            self.theme_indicator.configure(text=f"  🎨 {self.active_theme_name}", text_color=self.theme["accent"])
            self.scan_btn.configure(fg_color=self.theme["primary"], hover_color=self.theme["hover"])
            messagebox.showinfo("Tema Güncellendi", f"Tema '{theme_name}' olarak değiştirildi ve kaydedildi!")

    def change_appearance_mode(self, mode):
        ctk.set_appearance_mode(mode)
        self.settings["appearance_mode"] = mode
        save_settings(self.settings)


if __name__ == "__main__":
    app = CS2MarketApp()
    app.mainloop()
