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
import webbrowser
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import katalog_yoneticisi as ky
import gorsel_yonetici
import grafik_yonetici
import tweet_yonetici


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
        self._analytics_search_timer = None
        self.chart_canvas_widget = None
        self.current_analytics_item = "AK-47 | Redline (Field-Tested)"
        self.selected_timeframe = "1M"
        self.timeframe_buttons = {}
        self.theme_picker_buttons = {}

        # Otomatik takip değişkenleri
        self.auto_scan_active = self.settings.get("auto_scan_active", False)
        self.auto_scan_interval_minutes = int(self.settings.get("auto_scan_interval_minutes", 15))
        self._auto_scan_thread = None
        self._auto_scan_stop_event = threading.Event()

        # CS2 Tweet ve Yatırımcı Alarm Değişkenleri
        self.tweet_manager = tweet_yonetici.CS2TweetManager()
        self.tweet_monitor_active = self.settings.get("tweet_monitor_active", True)
        self.tweet_sound_alert = self.settings.get("tweet_sound_alert", True)
        self.tweet_toast_notification = self.settings.get("tweet_toast_notification", True)
        self.tweet_check_interval = int(self.settings.get("tweet_check_interval", 60))
        self.displayed_tweets = []
        self.tweets_display_limit = 15
        self.active_tweet_filter = "ALL"
        self.active_toast_popup = None
        self._tweet_search_timer = None


        self.db_link = os.getenv("DATABASE_URL")

        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_app_close)
        self.check_initial_db_status()
        self.after(500, self.init_tweets_system)


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
            self.after(300, lambda: self.load_item_analytics(self.current_analytics_item))
            if self.auto_scan_active:
                self.after(2000, self._start_auto_tracker)
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

    # ------------------ TREEVIEW & TEMA STİLLERİ ------------------
    def setup_treeview_styles(self):
        self.tree_style = ttk.Style()
        try:
            self.tree_style.theme_use("clam")
        except Exception:
            pass

        self.tree_style.configure(
            "Treeview",
            background="#141724",
            foreground="#e2e8f0",
            fieldbackground="#141724",
            rowheight=32,
            font=("Segoe UI", 10),
            borderwidth=0
        )

        self.tree_style.configure(
            "Treeview.Heading",
            background="#1e2235",
            foreground="#cad3f5",
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
            relief="flat",
            padding=(8, 8)
        )

        self.tree_style.map(
            "Treeview",
            background=[("selected", self.theme["primary"])],
            foreground=[("selected", "#ffffff")]
        )

        self.tree_style.map(
            "Treeview.Heading",
            background=[("active", "#282e46")],
            foreground=[("active", self.theme["accent"])]
        )

        self.tree_style.configure(
            "Vertical.TScrollbar",
            background="#1e2235",
            troughcolor="#141724",
            arrowcolor="#a5adcb",
            bordercolor="#141724",
            lightcolor="#1e2235",
            darkcolor="#1e2235"
        )

    def _apply_tree_tags(self, tree):
        if tree:
            tree.tag_configure("odd", background="#141724", foreground="#e2e8f0")
            tree.tag_configure("even", background="#1b1f31", foreground="#e2e8f0")

    # ------------------ ARAYÜZ (UI) TASARIMI ------------------
    def build_ui(self):
        self.setup_treeview_styles()

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

        # Sekmeli Görünüm (Tabview) - 6 TANE SEKME
        self.tabview = ctk.CTkTabview(
            self, 
            corner_radius=12,
            segmented_button_selected_color=self.theme["primary"],
            segmented_button_selected_hover_color=self.theme["hover"],
            segmented_button_unselected_color="#181a26",
            segmented_button_unselected_hover_color="#222536",
            text_color="#ffffff"
        )
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(12, 18))

        self.tab_scan = self.tabview.add("🔍 Eşya Tarama & Paketler")
        self.tab_analytics = self.tabview.add("📈 Fiyat Grafiği & Görsel")
        self.tab_watchlist = self.tabview.add("📌 Takip Listem (Portföy)")
        self.tab_tweets = self.tabview.add("🐦 CS2 Tweets & Akış")
        self.tab_catalog = self.tabview.add("📚 CS2 Eşya Kataloğu (20.663)")
        self.tab_database = self.tabview.add("📋 Pazar Tablosu & Analizler")
        self.tab_settings = self.tabview.add("🎨 Görünüm & Kişiselleştirme")

        self.setup_scan_tab()
        self.setup_analytics_tab()
        self.setup_watchlist_tab()
        self.setup_tweets_tab()
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

        self.btn_cat_scan = ctk.CTkButton(
            row2, text="🚀 Kategoriyi Tara", height=30, width=130, fg_color=self.theme["primary"],
            hover_color=self.theme["hover"], font=ctk.CTkFont(size=12, weight="bold"),
            command=self.scan_selected_category
        )
        self.btn_cat_scan.pack(side="left", padx=4)

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
        self._show_onboarding_card()

    def _show_onboarding_card(self):
        card = ctk.CTkFrame(self.results_scroll, fg_color="#181b26", corner_radius=12)
        card.pack(fill="x", padx=15, pady=15)

        title = ctk.CTkLabel(
            card,
            text="✨ CS2 Market Analyzer & Pro Dashboard'a Hoş Geldiniz!",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff"
        )
        title.pack(anchor="w", padx=20, pady=(15, 8))

        desc = ctk.CTkLabel(
            card,
            text=(
                "• 🔍 Yukarıdaki arama kutusuna eşya adı yazıp 'Tara & Kaydet' ile anlık fiyatları çekebilirsiniz.\n"
                "• ⚡ 'Hızlı Paketler' butonlarıyla popüler kasaları veya trend olan eşyaları tek tıkla listeleyebilirsiniz.\n"
                "• 📈 'Fiyat Grafiği & Görsel' sekmesinden 20.663 eşyanın 1 Gün - 2 Yıl arası fiyat geçmişini inceleyebilirsiniz.\n"
                "• 📌 'Takip Listem' sekmesinde portföyünüzü oluşturabilir ve Otomatik Düzenli Takip'i aktif edebilirsiniz.\n"
                "• 🎨 'Görünüm & Kişiselleştirme' sekmesinden dilediğiniz canlı renk temasını seçebilirsiniz."
            ),
            font=ctk.CTkFont(size=12),
            text_color="#cad3f5",
            justify="left"
        )
        desc.pack(anchor="w", padx=20, pady=(0, 15))

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

        # Minik Görsel Önizleme
        thumb_label = ctk.CTkLabel(card, text="", width=60, height=45)
        thumb_label.pack(side="left", padx=(10, 0), pady=6)
        
        g_url = gorsel_yonetici.esya_gorsel_url_bul(esya)
        if g_url:
            gorsel_yonetici.gorsel_getir_async(
                g_url, (60, 45),
                lambda img, lbl=thumb_label: self.after(0, lambda: lbl.configure(image=img))
            )
        else:
            thumb_label.configure(image=gorsel_yonetici.varsayilan_placeholder((60, 45)))

        left_frame = ctk.CTkFrame(card, fg_color="transparent")
        left_frame.pack(side="left", padx=12, pady=8)

        name_label = ctk.CTkLabel(left_frame, text=esya, font=ctk.CTkFont(size=14, weight="bold"), text_color="#ffffff")
        name_label.pack(anchor="w")

        hacim_display = f"24s Hacim: {hacim_str}" if hacim_str else "Hacim: Yok"
        detail_label = ctk.CTkLabel(left_frame, text=hacim_display, font=ctk.CTkFont(size=11), text_color="#a5adcb")
        detail_label.pack(anchor="w")

        right_frame = ctk.CTkFrame(card, fg_color="transparent")
        right_frame.pack(side="right", padx=15, pady=8)

        # Grafik Butonu
        chart_btn = ctk.CTkButton(
            right_frame, text="📈 Grafik", width=70, height=28,
            font=ctk.CTkFont(size=11, weight="bold"), fg_color="#202434", hover_color=self.theme["primary"],
            command=lambda n=esya: self.open_analytics_for_item(n)
        )
        chart_btn.pack(side="right", padx=(10, 0), pady=4)

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

    # ------------------ SEKME 2: FİYAT GRAFİĞİ & GÖRSEL (ANALYTICS) ------------------
    def setup_analytics_tab(self):
        # 1. ÜST ARAMA VE HIZLI SEÇİM ÇUBUĞU
        top_bar = ctk.CTkFrame(self.tab_analytics, fg_color=self.theme["card_bg"], corner_radius=10)
        top_bar.pack(fill="x", padx=10, pady=(10, 6))

        t_inner = ctk.CTkFrame(top_bar, fg_color="transparent")
        t_inner.pack(fill="x", padx=15, pady=10)

        self.analytics_search_entry = ctk.CTkEntry(
            t_inner,
            placeholder_text="Fotoğrafını ve fiyat grafiğini görmek istediğiniz eşyayı yazın (Örn: AK-47 | Redline, AWP | Asiimov)...",
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.analytics_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.analytics_search_entry.bind("<Return>", lambda e: self.do_analytics_search())
        self.analytics_search_entry.bind("<KeyRelease>", self._on_analytics_search_key_release)

        btn_inspect = ctk.CTkButton(
            t_inner, text="🔍 İncele & Çiz", width=120, height=40,
            fg_color=self.theme["primary"], hover_color=self.theme["hover"],
            font=ctk.CTkFont(weight="bold"), command=self.do_analytics_search
        )
        btn_inspect.pack(side="left", padx=(0, 8))

        # Hızlı Popüler Eşya Seçici
        self.analytics_quick_combo = ctk.CTkComboBox(
            t_inner,
            values=[
                "⚡ Popüler Eşyalar...",
                "AK-47 | Redline (Field-Tested)",
                "AWP | Asiimov (Field-Tested)",
                "M4A1-S | Printstream (Field-Tested)",
                "Desert Eagle | Printstream (Field-Tested)",
                "Gallery Case",
                "Kilowatt Case",
                "Revolution Case",
                "Dreams & Nightmares Case",
                "2020 RMR Contenders"
            ],
            width=230,
            height=40,
            command=self._on_quick_combo_selected
        )
        self.analytics_quick_combo.pack(side="left", padx=(0, 8))

        btn_detach = ctk.CTkButton(
            t_inner, text="🪟 Ayrı Pencere", width=110, height=40,
            fg_color="#343a40", hover_color="#495057",
            font=ctk.CTkFont(size=12), command=self.open_detached_analytics_window
        )
        btn_detach.pack(side="left")

        # Otomatik Tamamlama Kutusu
        self.analytics_suggestions_frame = ctk.CTkFrame(top_bar, fg_color="#181a24", corner_radius=8)

        # 2. ANA PANEL: SPLIT VIEW (SOL: GÖRSEL & DETAY | SAĞ: MATPLOTLIB GRAFİĞİ)
        split_frame = ctk.CTkFrame(self.tab_analytics, fg_color="transparent")
        split_frame.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        # SOL PANEL (Görsel ve Eşya Kartı)
        left_panel = ctk.CTkFrame(split_frame, fg_color=self.theme["card_bg"], corner_radius=12, width=330)
        left_panel.pack(side="left", fill="y", padx=(0, 10))
        left_panel.pack_propagate(False)

        # Görsel Alanı (Koyu çerçeve)
        img_container = ctk.CTkFrame(left_panel, fg_color="#12141c", corner_radius=10, height=210)
        img_container.pack(fill="x", padx=12, pady=(12, 8))
        img_container.pack_propagate(False)

        self.analytics_image_label = ctk.CTkLabel(
            img_container, text="Görsel Yükleniyor...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#8d99ae"
        )
        self.analytics_image_label.pack(expand=True, fill="both", padx=5, pady=5)

        # Eşya Başlığı
        self.analytics_title_label = ctk.CTkLabel(
            left_panel, text="AK-47 | Redline (Field-Tested)",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#ffffff", wraplength=300, justify="center"
        )
        self.analytics_title_label.pack(fill="x", padx=10, pady=(4, 2))

        # Kategori & Silah Bilgisi
        self.analytics_cat_label = ctk.CTkLabel(
            left_panel, text="Kategori: Tüfekler | Silah: AK-47",
            font=ctk.CTkFont(size=11), text_color="#a5adcb"
        )
        self.analytics_cat_label.pack(fill="x", padx=10, pady=(0, 8))

        # Fiyat & Hacim Kartı
        price_card = ctk.CTkFrame(left_panel, fg_color="#181b26", corner_radius=8)
        price_card.pack(fill="x", padx=12, pady=(0, 10))

        self.analytics_price_val = ctk.CTkLabel(
            price_card, text="$--.--",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.theme["accent"]
        )
        self.analytics_price_val.pack(pady=(8, 2))

        self.analytics_volume_val = ctk.CTkLabel(
            price_card, text="24s Hacim: --",
            font=ctk.CTkFont(size=12),
            text_color="#cad3f5"
        )
        self.analytics_volume_val.pack(pady=(0, 8))

        # Eylem Butonları
        self.analytics_btn_update = ctk.CTkButton(
            left_panel, text="🔄 Canlı Fiyatı Çek & Kaydet",
            height=36, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.theme["primary"], hover_color=self.theme["hover"],
            command=self.refresh_analytics_live_price
        )
        self.analytics_btn_update.pack(fill="x", padx=12, pady=4)

        btn_add_wl = ctk.CTkButton(
            left_panel, text="📌 Takip Listeme Ekle",
            height=34, font=ctk.CTkFont(size=12),
            fg_color="#3a0ca3", hover_color="#4361ee",
            command=self.add_current_analytics_to_watchlist
        )
        btn_add_wl.pack(fill="x", padx=12, pady=4)

        btn_steam_open = ctk.CTkButton(
            left_panel, text="🌐 Steam Pazarında Aç",
            height=34, font=ctk.CTkFont(size=12),
            fg_color="#1f2430", hover_color="#2b3242",
            command=self.open_current_analytics_in_steam
        )
        btn_steam_open.pack(fill="x", padx=12, pady=4)

        self.analytics_status_label = ctk.CTkLabel(
            left_panel, text="", font=ctk.CTkFont(size=11),
            text_color="#00d26a", wraplength=300
        )
        self.analytics_status_label.pack(fill="x", padx=10, pady=(6, 8))

        # SAĞ PANEL (Fiyat Grafiği ve İstatistikler)
        right_panel = ctk.CTkFrame(split_frame, fg_color="transparent")
        right_panel.pack(side="right", fill="both", expand=True)

        # 6'lı İstatistik Kartları Çubuğu
        stats_bar = ctk.CTkFrame(right_panel, fg_color="transparent")
        stats_bar.pack(fill="x", pady=(0, 8))

        self.stat_widgets = {}
        stat_configs = [
            ("guncel", "🟢 Son Fiyat", "$0.00"),
            ("zirve", "📈 En Yüksek", "$0.00"),
            ("dip", "📉 En Düşük", "$0.00"),
            ("ortalama", "⚖️ Ortalama", "$0.00"),
            ("degisim", "📊 Net Değişim", "%0.00"),
            ("kayit", "🕒 Kayıt Sayısı", "0")
        ]

        for key, title, def_val in stat_configs:
            c = ctk.CTkFrame(stats_bar, fg_color=self.theme["card_bg"], corner_radius=8)
            c.pack(side="left", fill="both", expand=True, padx=3)

            l_t = ctk.CTkLabel(c, text=title, font=ctk.CTkFont(size=11), text_color="#8d99ae")
            l_t.pack(pady=(6, 1))

            l_v = ctk.CTkLabel(c, text=def_val, font=ctk.CTkFont(size=13, weight="bold"), text_color="#ffffff")
            l_v.pack(pady=(0, 6))
            self.stat_widgets[key] = l_v

        # Zaman Aralığı Seçim Çubuğu (1 Gün, 1 Hafta, 1 Ay, 3 Ay, 6 Ay, 1 Yıl, 2 Yıl, Tümü)
        tf_bar = ctk.CTkFrame(right_panel, fg_color=self.theme["card_bg"], corner_radius=8, height=36)
        tf_bar.pack(fill="x", pady=(0, 6))

        tf_lbl = ctk.CTkLabel(tf_bar, text="🕒 Zaman Aralığı:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#8d99ae")
        tf_lbl.pack(side="left", padx=(12, 8), pady=4)

        self.timeframe_buttons = {}
        tf_options = [
            ("1 Gün", "1D"),
            ("1 Hafta", "1W"),
            ("1 Ay", "1M"),
            ("3 Ay", "3M"),
            ("6 Ay", "6M"),
            ("1 Yıl", "1Y"),
            ("2 Yıl", "2Y"),
            ("Tümü", "ALL")
        ]

        for label_text, tf_code in tf_options:
            is_active = (tf_code == self.selected_timeframe)
            bg_col = self.theme["primary"] if is_active else "#202434"
            btn = ctk.CTkButton(
                tf_bar, text=label_text, width=66, height=28,
                fg_color=bg_col, hover_color=self.theme["hover"],
                font=ctk.CTkFont(size=11, weight="bold" if is_active else "normal"),
                command=lambda c=tf_code: self.change_analytics_timeframe(c)
            )
            btn.pack(side="left", padx=2, pady=4)
            self.timeframe_buttons[tf_code] = btn

        # Grafik Alanı
        self.chart_container = ctk.CTkFrame(right_panel, fg_color="#131620", corner_radius=10)
        self.chart_container.pack(fill="both", expand=True, pady=(0, 8))

        # Geçmiş Kayıt Tablosu
        hist_frame = ctk.CTkFrame(right_panel, fg_color=self.theme["card_bg"], corner_radius=8, height=140)
        hist_frame.pack(fill="x")
        hist_frame.pack_propagate(False)

        h_cols = ("tarih", "saat", "fiyat", "hacim")
        self.analytics_history_tree = ttk.Treeview(hist_frame, columns=h_cols, show="headings", height=4)
        self.analytics_history_tree.heading("tarih", text="Tarih")
        self.analytics_history_tree.heading("saat", text="Saat")
        self.analytics_history_tree.heading("fiyat", text="Fiyat ($)")
        self.analytics_history_tree.heading("hacim", text="24s Hacim")

        self.analytics_history_tree.column("tarih", width=120, anchor="center")
        self.analytics_history_tree.column("saat", width=100, anchor="center")
        self.analytics_history_tree.column("fiyat", width=120, anchor="center")
        self.analytics_history_tree.column("hacim", width=140, anchor="center")

        sb = ttk.Scrollbar(hist_frame, orient="vertical", command=self.analytics_history_tree.yview)
        self.analytics_history_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.analytics_history_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self._apply_tree_tags(self.analytics_history_tree)

    # ------------------ ANALYTICS ARAMA VE ÖNERİLER ------------------
    def _on_analytics_search_key_release(self, event):
        if event.keysym in ("Return", "Up", "Down", "Escape"):
            if event.keysym == "Escape":
                self.analytics_suggestions_frame.pack_forget()
            return
        if self._analytics_search_timer:
            self.after_cancel(self._analytics_search_timer)
        self._analytics_search_timer = self.after(250, self._do_analytics_search_suggestions)

    def _do_analytics_search_suggestions(self):
        text = self.analytics_search_entry.get().strip()
        if len(text) < 2:
            self.analytics_suggestions_frame.pack_forget()
            return
        threading.Thread(target=self._fetch_analytics_suggestions_thread, args=(text,), daemon=True).start()

    def _fetch_analytics_suggestions_thread(self, query):
        results = ky.katalog_ara(query, limit=5)
        self.after(0, lambda: self._show_analytics_suggestions(results))

    def _show_analytics_suggestions(self, results):
        for widget in self.analytics_suggestions_frame.winfo_children():
            widget.destroy()

        if not results:
            self.analytics_suggestions_frame.pack_forget()
            return

        self.analytics_suggestions_frame.pack(fill="x", padx=15, pady=(0, 8))
        header = ctk.CTkLabel(
            self.analytics_suggestions_frame,
            text="💡 Katalogdan Seçin:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#8d99ae"
        )
        header.pack(anchor="w", padx=8, pady=(4, 2))

        for item in results:
            name = item['esya_adi']
            cat = item.get('kategori', '')
            btn = ctk.CTkButton(
                self.analytics_suggestions_frame,
                text=f"🎯 {name}  [{cat}]",
                anchor="w",
                height=26,
                fg_color="#202434",
                hover_color=self.theme["primary"],
                font=ctk.CTkFont(size=12),
                command=lambda n=name: self._select_analytics_suggestion(n)
            )
            btn.pack(fill="x", padx=6, pady=2)

    def _select_analytics_suggestion(self, name):
        self.analytics_search_entry.delete(0, 'end')
        self.analytics_search_entry.insert(0, name)
        self.analytics_suggestions_frame.pack_forget()
        self.load_item_analytics(name)

    def _on_quick_combo_selected(self, val):
        if "Popüler Eşyalar" not in val:
            self.load_item_analytics(val)

    def do_analytics_search(self):
        item_text = self.analytics_search_entry.get().strip()
        if not item_text:
            messagebox.showwarning("Eksik", "Lütfen incelenecek eşya adını girin!")
            return
        self.analytics_suggestions_frame.pack_forget()
        self.load_item_analytics(item_text)

    def open_analytics_for_item(self, item_name):
        self.tabview.set("📈 Fiyat Grafiği & Görsel")
        self.load_item_analytics(item_name)

    def open_selected_catalog_in_analytics(self):
        selected = self.catalog_tree.selection()
        if not selected:
            messagebox.showwarning("Seçim Yok", "Lütfen incelemek istediğiniz eşyayı tablodan seçin!")
            return
        row = self.catalog_tree.item(selected[0])['values']
        item_name = row[0]
        self.open_analytics_for_item(item_name)

    def open_selected_wl_in_analytics(self):
        selected = self.wl_tree.selection()
        if not selected:
            messagebox.showwarning("Seçim Yok", "Lütfen incelemek istediğiniz eşyayı tablodan seçin!")
            return
        row = self.wl_tree.item(selected[0])['values']
        item_name = row[1]
        self.open_analytics_for_item(item_name)

    def open_selected_db_in_analytics(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Seçim Yok", "Lütfen incelemek istediğiniz eşyayı tablodan seçin!")
            return
        row = self.tree.item(selected[0])['values']
        item_name = row[0]
        self.open_analytics_for_item(item_name)

    # ------------------ ANALYTICS VERİ VE GÖRSEL YÜKLEME ------------------
    def load_item_analytics(self, item_name, timeframe=None):
        if not item_name or not item_name.strip():
            return
        if timeframe:
            self.selected_timeframe = timeframe
        self.current_analytics_item = item_name.strip()
        if hasattr(self, 'analytics_search_entry'):
            self.analytics_search_entry.delete(0, 'end')
            self.analytics_search_entry.insert(0, self.current_analytics_item)
            self.analytics_suggestions_frame.pack_forget()
            self.analytics_title_label.configure(text=self.current_analytics_item)
            self.analytics_status_label.configure(text=f"⏳ {self.selected_timeframe} verileri yükleniyor...", text_color="#f39c12")

        threading.Thread(target=self._load_item_analytics_thread, args=(self.current_analytics_item,), daemon=True).start()

    def change_analytics_timeframe(self, tf_code):
        self.selected_timeframe = tf_code
        for code, btn in self.timeframe_buttons.items():
            if code == tf_code:
                btn.configure(fg_color=self.theme["primary"], font=ctk.CTkFont(size=11, weight="bold"))
            else:
                btn.configure(fg_color="#202434", font=ctk.CTkFont(size=11, weight="normal"))

        if self.current_analytics_item:
            self.load_item_analytics(self.current_analytics_item)

    def _load_item_analytics_thread(self, item_name):
        # 1. Görsel URL'sini bul
        img_url = gorsel_yonetici.esya_gorsel_url_bul(item_name)
        if img_url:
            def _on_img(img):
                if hasattr(self, 'analytics_image_label'):
                    self.after(0, lambda: self.analytics_image_label.configure(image=img, text=""))
            gorsel_yonetici.gorsel_getir_async(img_url, (260, 195), _on_img)
        else:
            ph = gorsel_yonetici.varsayilan_placeholder((260, 195))
            if hasattr(self, 'analytics_image_label'):
                self.after(0, lambda: self.analytics_image_label.configure(image=ph, text="🖼️ Görsel Kataloğu Yok"))

        # 2. Katalogdan silah ve kategori bilgisini çek
        cat_info = "Kategori: CS2 Eşyası"
        try:
            conn = self.get_db_connection()
            if conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT kategori, alt_kategori, silah FROM esya_katalogu WHERE esya_adi = %s LIMIT 1;", (item_name,))
                    crow = cur.fetchone()
                    if crow:
                        k = crow.get('kategori') or 'Genel'
                        s = crow.get('silah') or ''
                        a = crow.get('alt_kategori') or ''
                        parts = [p for p in [k, s, a] if p]
                        cat_info = " | ".join(parts)
                conn.close()
        except Exception:
            pass

        if hasattr(self, 'analytics_cat_label'):
            self.after(0, lambda: self.analytics_cat_label.configure(text=cat_info))

        # 3. Fiyat geçmişini ve seçili zaman aralığı (1D..2Y) verilerini üret
        rows = grafik_yonetici.esya_fiyat_gecmisi_al(item_name)
        dates, prices, stats = grafik_yonetici.zaman_araligina_gore_veri_uret(rows, item_name, self.selected_timeframe)

        # 4. Figür oluştur
        fig = grafik_yonetici.zamanli_fiyat_grafigi_ciz(dates, prices, item_name, self.selected_timeframe, tema_rengi=self.theme["accent"])

        # 5. UI güncelle
        self.after(0, lambda: self._apply_analytics_results(rows, stats, fig))

    def _apply_analytics_results(self, rows, stats, fig):
        if not hasattr(self, 'analytics_price_val'):
            return

        # Fiyat ve hacim kartı
        if stats['guncel_fiyat'] > 0:
            self.analytics_price_val.configure(text=f"${stats['guncel_fiyat']:.2f}")
            self.analytics_volume_val.configure(text=f"24s Hacim: {stats['son_hacim']}")
        else:
            self.analytics_price_val.configure(text="$--.--")
            self.analytics_volume_val.configure(text="Kayıt bulunamadı")

        # Üst istatistik kartları
        self.stat_widgets["guncel"].configure(text=f"${stats['guncel_fiyat']:.2f}" if stats['guncel_fiyat'] else "-")
        self.stat_widgets["zirve"].configure(text=f"${stats['en_yuksek']:.2f}" if stats['en_yuksek'] else "-")
        self.stat_widgets["dip"].configure(text=f"${stats['en_dusuk']:.2f}" if stats['en_dusuk'] else "-")
        self.stat_widgets["ortalama"].configure(text=f"${stats['ortalama']:.2f}" if stats['ortalama'] else "-")

        chg = stats['degisim_yuzde']
        chg_color = "#2ecc71" if chg > 0 else ("#e74c3c" if chg < 0 else "#ffffff")
        self.stat_widgets["degisim"].configure(text=f"%{chg:+.2f}", text_color=chg_color)
        self.stat_widgets["kayit"].configure(text=str(stats['toplam_kayit']))

        # Grafiği göm
        self._embed_chart_figure(fig)

        # Tabloyu doldur
        self._fill_analytics_history_table(rows)

        count = stats['toplam_kayit']
        self.analytics_status_label.configure(
            text=f"✅ {count} adet pazar kaydı analiz edildi." if count else "💡 Veritabanında kayıt yok. 'Canlı Fiyatı Çek' ile ilk veriyi ekleyebilirsiniz.",
            text_color="#00d26a" if count else "#f39c12"
        )

    def _embed_chart_figure(self, fig):
        if not hasattr(self, 'chart_container'):
            return

        if self.chart_canvas_widget:
            try:
                self.chart_canvas_widget.get_tk_widget().destroy()
            except Exception:
                pass
            plt.close('all')

        canvas = FigureCanvasTkAgg(fig, master=self.chart_container)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.pack(fill="both", expand=True, padx=4, pady=4)
        self.chart_canvas_widget = canvas

    def _fill_analytics_history_table(self, rows):
        if not hasattr(self, 'analytics_history_tree'):
            return

        for item in self.analytics_history_tree.get_children():
            self.analytics_history_tree.delete(item)

        for i, r in enumerate(reversed(rows)):
            t_str = str(r.get('tarih') or '-')
            s_str = str(r.get('saat') or '-')
            p_str = f"${float(r['fiyat_sayisal']):.2f}" if r.get('fiyat_sayisal') is not None else str(r.get('fiyat') or '-')
            h_str = str(r.get('hacim') or '-')
            tag = "even" if i % 2 == 0 else "odd"
            self.analytics_history_tree.insert("", "end", values=(t_str, s_str, p_str, h_str), tags=(tag,))

    def refresh_analytics_live_price(self):
        item_name = self.current_analytics_item
        if not item_name:
            return
        self.analytics_status_label.configure(text="🌐 Steam pazarından güncel fiyat çekiliyor...", text_color="#f39c12")
        self.analytics_btn_update.configure(state="disabled", text="⏳ Çekiliyor...")

        def _thread():
            fiyat_str, hacim_str = self.get_steam_price(item_name)
            if fiyat_str:
                self.save_price_to_db(item_name, fiyat_str, hacim_str)
                self.after(0, lambda: self.analytics_status_label.configure(text="✅ Yeni fiyat kaydedildi, grafik yenileniyor...", text_color="#2ecc71"))
                self.after(300, lambda: self.load_item_analytics(item_name))
                self.after(300, self.refresh_database_table)
            else:
                self.after(0, lambda: self.analytics_status_label.configure(text=f"❌ Fiyat alınamadı: {hacim_str}", text_color="#e74c3c"))

            self.after(0, lambda: self.analytics_btn_update.configure(state="normal", text="🔄 Canlı Fiyatı Çek & Kaydet"))

        threading.Thread(target=_thread, daemon=True).start()

    def add_current_analytics_to_watchlist(self):
        item_name = self.current_analytics_item
        if not item_name:
            return
        try:
            conn = self.get_db_connection()
            if not conn:
                return
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
            messagebox.showerror("Hata", f"Listeye eklenemedi: {e}")

    def open_current_analytics_in_steam(self):
        item_name = self.current_analytics_item
        if not item_name:
            return
        encoded = urllib.parse.quote(item_name)
        url = f"https://steamcommunity.com/market/listings/730/{encoded}"
        webbrowser.open(url)

    def open_detached_analytics_window(self):
        item_name = self.current_analytics_item
        if not item_name:
            return

        win = ctk.CTkToplevel(self)
        win.title(f"📈 {item_name} - Ayrı Grafik & Detay Penceresi")
        win.geometry("880x620")
        win.minsize(750, 500)

        # Üst başlık ve bilgi
        top_bar = ctk.CTkFrame(win, fg_color=self.theme["card_bg"], corner_radius=0, height=60)
        top_bar.pack(fill="x")

        lbl = ctk.CTkLabel(top_bar, text=f"🎮 {item_name}", font=ctk.CTkFont(size=16, weight="bold"))
        lbl.pack(side="left", padx=20, pady=12)

        # Ana içerik
        content = ctk.CTkFrame(win, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=15, pady=15)

        # Sol resim alanı
        left = ctk.CTkFrame(content, fg_color=self.theme["card_bg"], corner_radius=10, width=280)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        img_box = ctk.CTkLabel(left, text="Görsel Yükleniyor...", font=ctk.CTkFont(size=12))
        img_box.pack(expand=True, fill="both", padx=10, pady=10)

        img_url = gorsel_yonetici.esya_gorsel_url_bul(item_name)
        if img_url:
            gorsel_yonetici.gorsel_getir_async(img_url, (240, 180), lambda img: win.after(0, lambda: img_box.configure(image=img, text="")))
        else:
            img_box.configure(image=gorsel_yonetici.varsayilan_placeholder((240, 180)), text="Görsel Yok")

        # Sağ grafik alanı
        right = ctk.CTkFrame(content, fg_color="#131620", corner_radius=10)
        right.pack(side="right", fill="both", expand=True)

        rows = grafik_yonetici.esya_fiyat_gecmisi_al(item_name)
        fig = grafik_yonetici.fiyat_grafigi_ciz(rows, item_name, tema_rengi=self.theme["accent"], figsize=(6.5, 4.2))

        cv = FigureCanvasTkAgg(fig, master=right)
        cv.draw()
        cv.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

    # ------------------ SEKME 3: TAKİP LİSTEM (PORTFÖY) ------------------
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

        self.wl_add_btn = ctk.CTkButton(
            c, text="➕ Listeme Ekle", height=38, width=130, font=ctk.CTkFont(weight="bold"),
            fg_color=self.theme["primary"], hover_color=self.theme["hover"],
            command=self.add_to_watchlist
        )
        self.wl_add_btn.pack(side="left")

        # Takip Listesi Katalog Öneri Paneli
        self.wl_suggestions_frame = ctk.CTkFrame(add_bar, fg_color="#181a24", corner_radius=8)

        btn_bar = ctk.CTkFrame(self.tab_watchlist, fg_color="transparent")
        btn_bar.pack(fill="x", padx=10, pady=(0, 6))

        self.wl_scan_btn = ctk.CTkButton(
            btn_bar, text="🚀 Takip Listemdekileri Tara", height=36, fg_color=self.theme["primary"],
            hover_color=self.theme["hover"], font=ctk.CTkFont(weight="bold"), command=self.scan_watchlist_items
        )
        self.wl_scan_btn.pack(side="left", padx=(0, 8))

        chart_wl_btn = ctk.CTkButton(
            btn_bar, text="📈 Grafiği & Görseli Gör", height=36, fg_color="#00b4d8", hover_color="#0096c7",
            font=ctk.CTkFont(weight="bold"), command=self.open_selected_wl_in_analytics
        )
        chart_wl_btn.pack(side="left", padx=4)

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

        # Otomatik Düzenli Fiyat Takip Çubuğu
        auto_bar = ctk.CTkFrame(self.tab_watchlist, fg_color=self.theme["card_bg"], corner_radius=8)
        auto_bar.pack(fill="x", padx=10, pady=(0, 6))

        ab_inner = ctk.CTkFrame(auto_bar, fg_color="transparent")
        ab_inner.pack(fill="x", padx=12, pady=6)

        self.auto_scan_switch = ctk.CTkSwitch(
            ab_inner, text="⏰ Otomatik Düzenli Takip",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.toggle_auto_scan
        )
        self.auto_scan_switch.pack(side="left", padx=(0, 15))
        if self.auto_scan_active:
            self.auto_scan_switch.select()

        self.auto_interval_combo = ctk.CTkComboBox(
            ab_inner,
            values=["5 Dakika", "15 Dakika", "30 Dakika", "1 Saat", "3 Saat"],
            width=130, height=32,
            command=self._on_auto_interval_change
        )
        int_text = f"{self.auto_scan_interval_minutes} Dakika" if self.auto_scan_interval_minutes < 60 else f"{self.auto_scan_interval_minutes // 60} Saat"
        self.auto_interval_combo.set(int_text)
        self.auto_interval_combo.pack(side="left", padx=(0, 15))

        self.auto_scan_status_badge = ctk.CTkLabel(
            ab_inner,
            text=f"🟢 Otomatik Takip Devrede (Her {self.auto_scan_interval_minutes} dk)" if self.auto_scan_active else "💤 Düzenli takip kapalı",
            font=ctk.CTkFont(size=12),
            text_color="#2ecc71" if self.auto_scan_active else "#8d99ae"
        )
        self.auto_scan_status_badge.pack(side="left", padx=5)

        self.auto_scan_countdown_lbl = ctk.CTkLabel(
            ab_inner, text="", font=ctk.CTkFont(size=12, weight="bold"), text_color=self.theme["accent"]
        )
        self.auto_scan_countdown_lbl.pack(side="right", padx=10)

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
        self._apply_tree_tags(self.wl_tree)
        self.wl_tree.bind("<Double-1>", lambda e: self.open_selected_wl_in_analytics())

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

            for i, r in enumerate(rows):
                hedef_str = f"${r['hedef_fiyat']:.2f}" if r['hedef_fiyat'] else "-"
                tarih_str = r['ekleme_tarihi'].strftime("%Y-%m-%d %H:%M") if r['ekleme_tarihi'] else "-"
                tag = "even" if i % 2 == 0 else "odd"
                self.wl_tree.insert("", "end", values=(r['id'], r['esya'], hedef_str, tarih_str), tags=(tag,))

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

    # ------------------ OTOMATİK TAKİP LİSTESİ TARAYICISI ------------------
    def toggle_auto_scan(self):
        is_on = bool(self.auto_scan_switch.get())
        self.auto_scan_active = is_on
        self.settings["auto_scan_active"] = is_on
        save_settings(self.settings)

        if is_on:
            self.auto_scan_status_badge.configure(
                text=f"🟢 Otomatik Takip Devrede (Her {self.auto_scan_interval_minutes} dk)", 
                text_color="#2ecc71"
            )
            self._start_auto_tracker()
        else:
            self.auto_scan_status_badge.configure(text="💤 Düzenli takip kapalı", text_color="#8d99ae")
            self.auto_scan_countdown_lbl.configure(text="")
            self._stop_auto_tracker()

    def _on_auto_interval_change(self, val):
        mins = 15
        if "5 Dakika" in val:
            mins = 5
        elif "15 Dakika" in val:
            mins = 15
        elif "30 Dakika" in val:
            mins = 30
        elif "1 Saat" in val:
            mins = 60
        elif "3 Saat" in val:
            mins = 180

        self.auto_scan_interval_minutes = mins
        self.settings["auto_scan_interval_minutes"] = mins
        save_settings(self.settings)

        if self.auto_scan_active:
            self.auto_scan_status_badge.configure(
                text=f"🟢 Otomatik Takip Devrede (Her {self.auto_scan_interval_minutes} dk)", 
                text_color="#249f57"
            )

    def _start_auto_tracker(self):
        self._auto_scan_stop_event.clear()
        if self._auto_scan_thread and self._auto_scan_thread.is_alive():
            return
        self._auto_scan_thread = threading.Thread(target=self._auto_tracker_worker, daemon=True)
        self._auto_scan_thread.start()

    def _stop_auto_tracker(self):
        self._auto_scan_stop_event.set()

    def _auto_tracker_worker(self):
        while not self._auto_scan_stop_event.is_set():
            # İlk veya periyodik taramayı çalıştır
            self._run_auto_scan_cycle()

            interval_sec = max(self.auto_scan_interval_minutes * 60, 60)
            for sec_left in range(interval_sec, 0, -1):
                if self._auto_scan_stop_event.is_set():
                    break
                mins = sec_left // 60
                secs = sec_left % 60
                cd_text = f"⏱️ Sonraki Tarama: {mins:02d}:{secs:02d}"
                self.after(0, lambda t=cd_text: self.auto_scan_countdown_lbl.configure(text=t))
                time.sleep(1)

    def _run_auto_scan_cycle(self):
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT esya, hedef_fiyat FROM takip_listesi ORDER BY id ASC;")
                items = cur.fetchall()
            conn.close()
        except Exception:
            return

        if not items:
            return

        self.after(0, lambda: self.auto_scan_status_badge.configure(
            text=f"🔄 Takip listesi taranıyor ({len(items)} eşya)...", text_color="#f39c12"
        ))

        updated_count = 0
        for it in items:
            if self._auto_scan_stop_event.is_set():
                break
            esya = it['esya']
            target = float(it['hedef_fiyat']) if it.get('hedef_fiyat') else None

            fiyat_str, hacim_str = self.get_steam_price(esya)
            if not fiyat_str:
                # Steam 429 veya hata durumunda Skinport yedeği
                sp_item = grafik_yonetici.get_skinport_sales_history().get(esya)
                if sp_item:
                    avg_p = sp_item.get('last_24_hours', {}).get('avg') or sp_item.get('last_7_days', {}).get('avg')
                    if avg_p:
                        fiyat_str = f"${avg_p:.2f}"
                        hacim_str = str(sp_item.get('last_24_hours', {}).get('volume') or "Skinport")

            if fiyat_str:
                self.save_price_to_db(esya, fiyat_str, hacim_str)
                curr_price, _ = self.parse_numbers(fiyat_str, hacim_str)
                updated_count += 1

                # Hedef fiyat uyarısı kontrolü
                if target is not None and curr_price is not None and curr_price <= target:
                    self.after(0, lambda e=esya, c=curr_price, t=target: 
                        messagebox.showinfo("🎯 Hedef Fiyat Alarmı!", f"'{e}' hedef fiyat seviyesine ulaştı!\nGüncel: ${c:.2f}\nHedef: ${t:.2f}")
                    )

            time.sleep(2.5)  # Steam dostu bekleme süresi

        now_str = datetime.now().strftime("%H:%M")
        self.after(0, lambda: self.auto_scan_status_badge.configure(
            text=f"✅ Son Otomatik Tarama: {now_str} ({updated_count} eşya)", text_color="#2ecc71"
        ))
        self.after(0, self.refresh_watchlist_table)
        self.after(0, self.refresh_database_table)

    def on_app_close(self):
        self._auto_scan_stop_event.set()
        if hasattr(self, 'tweet_manager'):
            try:
                self.tweet_manager.stop_background_monitor()
            except Exception:
                pass
        if hasattr(self, 'active_toast_popup') and self.active_toast_popup:
            try:
                self.active_toast_popup.destroy()
            except Exception:
                pass
        self.destroy()

    # ------------------ SEKME: 🐦 CS2 TWEETS & AKIŞ (YATIRIMCI ALARMI) ------------------
    def setup_tweets_tab(self):
        # 1. Üst Kontrol & Durum Kartı
        header_card = ctk.CTkFrame(self.tab_tweets, fg_color=self.theme["card_bg"], corner_radius=12)
        header_card.pack(fill="x", padx=10, pady=(10, 6))

        h_inner = ctk.CTkFrame(header_card, fg_color="transparent")
        h_inner.pack(fill="x", padx=16, pady=12)

        # Sol Bilgiler
        left_info = ctk.CTkFrame(h_inner, fg_color="transparent")
        left_info.pack(side="left", fill="y")

        lbl_title = ctk.CTkLabel(
            left_info,
            text="🐦 Counter-Strike 2 Resmi Akışı (@CounterStrike & Valve)",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff"
        )
        lbl_title.pack(anchor="w")

        info_sub = ctk.CTkFrame(left_info, fg_color="transparent")
        info_sub.pack(anchor="w", pady=(4, 0))

        self.tweet_status_badge = ctk.CTkLabel(
            info_sub,
            text="🟢 Canlı Takip Aktif (Her 60s)" if self.tweet_monitor_active else "⚪ Takip Duraklatıldı",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#2ecc71" if self.tweet_monitor_active else "#94a3b8"
        )
        self.tweet_status_badge.pack(side="left", padx=(0, 10))

        self.tweet_last_check_lbl = ctk.CTkLabel(
            info_sub,
            text="🕒 Son Kontrol: Bekleniyor...",
            font=ctk.CTkFont(size=11),
            text_color="#a5adcb"
        )
        self.tweet_last_check_lbl.pack(side="left", padx=(0, 10))

        self.tweet_count_lbl = ctk.CTkLabel(
            info_sub,
            text="📊 0 Paylaşım",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.theme["accent"]
        )
        self.tweet_count_lbl.pack(side="left")

        # Sağ Aksiyon Butonları
        right_actions = ctk.CTkFrame(h_inner, fg_color="transparent")
        right_actions.pack(side="right")

        self.tweet_refresh_btn = ctk.CTkButton(
            right_actions,
            text="🔄 Akışı Yenile",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            width=115,
            fg_color=self.theme["primary"],
            hover_color=self.theme["hover"],
            command=self.refresh_tweets_manual
        )
        self.tweet_refresh_btn.pack(side="left", padx=4)

        self.tweet_test_btn = ctk.CTkButton(
            right_actions,
            text="🔔 Alarm & Bildirim Testi",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            fg_color="#e63946",
            hover_color="#d62828",
            command=self.test_tweet_notification
        )
        self.tweet_test_btn.pack(side="left", padx=4)

        btn_x_web = ctk.CTkButton(
            right_actions,
            text="🌐 X'te Aç",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            width=85,
            fg_color="#1d9bf0",
            hover_color="#0c7abf",
            command=lambda: webbrowser.open("https://x.com/CounterStrike")
        )
        btn_x_web.pack(side="left", padx=4)

        self.tweet_monitor_switch = ctk.CTkSwitch(
            right_actions,
            text="Oto Alarm",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.toggle_tweet_monitor
        )
        if self.tweet_monitor_active:
            self.tweet_monitor_switch.select()
        else:
            self.tweet_monitor_switch.deselect()
        self.tweet_monitor_switch.pack(side="left", padx=(8, 0))

        # 2. Filtre & Arama Kartı
        filter_card = ctk.CTkFrame(self.tab_tweets, fg_color=self.theme["card_bg"], corner_radius=10)
        filter_card.pack(fill="x", padx=10, pady=(0, 6))

        f_inner = ctk.CTkFrame(filter_card, fg_color="transparent")
        f_inner.pack(fill="x", padx=14, pady=8)

        self.tweet_search_entry = ctk.CTkEntry(
            f_inner,
            placeholder_text="🔍 Tweet veya güncelleme ara (Release Notes, Case, Armory, Update, Train, Vertigo...)",
            height=36,
            font=ctk.CTkFont(size=13)
        )
        self.tweet_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.tweet_search_entry.bind("<KeyRelease>", self._on_tweet_search_key_release)

        # Filtre Butonları
        filter_btns_frame = ctk.CTkFrame(f_inner, fg_color="transparent")
        filter_btns_frame.pack(side="right")

        self.tweet_filter_buttons = {}
        filters = [
            ("ALL", "Tümü"),
            ("CRITICAL", "🔥 Kritik Güncellemeler"),
            ("TWITTER", "🐦 Sadece X / Twitter"),
            ("STEAM", "⚡ Sadece Steam")
        ]
        for f_key, f_label in filters:
            btn = ctk.CTkButton(
                filter_btns_frame,
                text=f_label,
                height=32,
                font=ctk.CTkFont(size=11, weight="bold" if f_key == "ALL" else "normal"),
                fg_color=self.theme["primary"] if f_key == "ALL" else "#222536",
                hover_color=self.theme["hover"] if f_key == "ALL" else "#2d3248",
                command=lambda k=f_key: self.set_tweet_filter(k)
            )
            btn.pack(side="left", padx=3)
            self.tweet_filter_buttons[f_key] = btn

        # 3. Tweet Akışı Scrollable Alanı
        self.tweets_scroll_frame = ctk.CTkScrollableFrame(
            self.tab_tweets,
            fg_color="transparent",
            corner_radius=0
        )
        self.tweets_scroll_frame.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self.tweet_loading_lbl = ctk.CTkLabel(
            self.tweets_scroll_frame,
            text="⏳ Counter-Strike 2 tweetleri ve güncellemeleri yükleniyor...",
            font=ctk.CTkFont(size=14),
            text_color="#a5adcb"
        )
        self.tweet_loading_lbl.pack(pady=40)

    def init_tweets_system(self):
        """
        Uygulama açılışında tweetleri arka planda çeker ve otomatik izleyiciyi başlatır.
        """
        def _bg_init():
            success, tweets = self.tweet_manager.fetch_tweets()
            if success and tweets:
                self.displayed_tweets = tweets
            else:
                self.displayed_tweets = self.tweet_manager.cached_tweets or []

            now_str = datetime.now().strftime("%H:%M:%S")
            self.after(0, lambda: self._apply_initial_tweets(now_str))

            if self.tweet_monitor_active:
                self.tweet_manager.start_background_monitor(
                    self.on_new_tweet_detected,
                    interval_seconds=self.tweet_check_interval
                )

        threading.Thread(target=_bg_init, daemon=True).start()

    def _apply_initial_tweets(self, check_time_str):
        if hasattr(self, 'tweet_last_check_lbl'):
            self.tweet_last_check_lbl.configure(text=f"🕒 Son Kontrol: {check_time_str}")
        self.filter_and_display_tweets()

    def refresh_tweets_manual(self):
        """
        Kullanıcı 'Akışı Yenile' butonuna bastığında anlık kontrol yapar.
        """
        if hasattr(self, 'tweet_refresh_btn'):
            self.tweet_refresh_btn.configure(text="⏳ Çekiliyor...", state="disabled")

        def _bg_refresh():
            success, tweets = self.tweet_manager.fetch_tweets()
            if success and tweets:
                self.displayed_tweets = tweets
            now_str = datetime.now().strftime("%H:%M:%S")

            def _done():
                if hasattr(self, 'tweet_refresh_btn'):
                    self.tweet_refresh_btn.configure(text="🔄 Akışı Yenile", state="normal")
                if hasattr(self, 'tweet_last_check_lbl'):
                    self.tweet_last_check_lbl.configure(text=f"🕒 Son Kontrol: {now_str}")
                self.filter_and_display_tweets()

            self.after(0, _done)

        threading.Thread(target=_bg_refresh, daemon=True).start()

    def set_tweet_filter(self, filter_key):
        self.active_tweet_filter = filter_key
        for k, btn in getattr(self, 'tweet_filter_buttons', {}).items():
            if k == filter_key:
                btn.configure(fg_color=self.theme["primary"], hover_color=self.theme["hover"], font=ctk.CTkFont(size=11, weight="bold"))
            else:
                btn.configure(fg_color="#222536", hover_color="#2d3248", font=ctk.CTkFont(size=11, weight="normal"))
        self.filter_and_display_tweets()

    def _on_tweet_search_key_release(self, event):
        if self._tweet_search_timer:
            self.after_cancel(self._tweet_search_timer)
        self._tweet_search_timer = self.after(250, self.filter_and_display_tweets)

    def filter_and_display_tweets(self):
        query = ""
        if hasattr(self, 'tweet_search_entry'):
            query = self.tweet_search_entry.get().strip().lower()

        filtered = []
        for tw in self.displayed_tweets:
            # Filtreleme
            if self.active_tweet_filter == "CRITICAL":
                impact_lvl = tw.get("impact", {}).get("level", "LOW")
                if impact_lvl != "CRITICAL":
                    continue
            elif self.active_tweet_filter == "TWITTER":
                if "Twitter" not in tw.get("source", ""):
                    continue
            elif self.active_tweet_filter == "STEAM":
                if "Steam" not in tw.get("source", ""):
                    continue

            # Arama sorgusu kontrolü
            if query:
                txt = tw.get("text", "").lower()
                user = tw.get("user_name", "").lower()
                source = tw.get("source", "").lower()
                badge = tw.get("impact", {}).get("badge", "").lower()
                if query not in txt and query not in user and query not in source and query not in badge:
                    continue

            filtered.append(tw)

        if hasattr(self, 'tweet_count_lbl'):
            self.tweet_count_lbl.configure(text=f"📊 {len(filtered)} Paylaşım")

        self.render_tweet_cards(filtered)

    def render_tweet_cards(self, tweet_list):
        for widget in self.tweets_scroll_frame.winfo_children():
            widget.destroy()

        if not tweet_list:
            empty_card = ctk.CTkFrame(self.tweets_scroll_frame, fg_color=self.theme["card_bg"], corner_radius=10)
            empty_card.pack(fill="x", padx=10, pady=20)
            lbl = ctk.CTkLabel(
                empty_card,
                text="📭 Gösterilecek tweet veya CS2 güncellemesi bulunamadı.\n(Arama filtrenizi temizleyebilir veya 'Akışı Yenile' yapabilirsiniz.)",
                font=ctk.CTkFont(size=13),
                text_color="#a5adcb",
                justify="center"
            )
            lbl.pack(padx=20, pady=25)
            return

        # Performans: Çok fazla kartın arayüzü kasmasını önlemek için parçalı (pagination) yükleme
        displayed_chunk = tweet_list[:self.tweets_display_limit]

        for tw in displayed_chunk:
            impact = tw.get("impact", {})
            impact_level = impact.get("level", "LOW")
            card_border = impact.get("color") if impact_level == "CRITICAL" else self.theme.get("card_border", "#1e293b")
            border_w = 2 if impact_level == "CRITICAL" else 1

            card = ctk.CTkFrame(
                self.tweets_scroll_frame,
                fg_color=self.theme["card_bg"],
                corner_radius=10,
                border_width=border_w,
                border_color=card_border
            )
            card.pack(fill="x", padx=6, pady=6)

            # Üst Başlık Satırı
            head_row = ctk.CTkFrame(card, fg_color="transparent")
            head_row.pack(fill="x", padx=14, pady=(10, 4))

            source_icon = "🐦" if "Twitter" in tw.get("source", "") else "⚡"
            author_text = f"{source_icon} {tw.get('user_name', 'Counter-Strike')} (@{tw.get('screen_name', 'CounterStrike')})"
            author_lbl = ctk.CTkLabel(
                head_row,
                text=author_text,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#ffffff"
            )
            author_lbl.pack(side="left")

            time_lbl = ctk.CTkLabel(
                head_row,
                text=f"• 🕒 {tw.get('date_str', '')}",
                font=ctk.CTkFont(size=11),
                text_color="#94a3b8"
            )
            time_lbl.pack(side="left", padx=8)

            badge_color = impact.get("color", "#3b82f6")
            badge_lbl = ctk.CTkLabel(
                head_row,
                text=f" {impact.get('label', 'BİLGİ')} ",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=badge_color,
                text_color="#ffffff",
                corner_radius=6
            )
            badge_lbl.pack(side="right")

            # Gövde Metni (BBCode ve Rusça içerikten arındırılmış temiz metin)
            raw_body = tweet_yonetici.clean_bbcode(tw.get("text", ""))
            if not tweet_yonetici.is_valid_english_content(raw_body):
                continue

            body_lbl = ctk.CTkLabel(
                card,
                text=raw_body,
                font=ctk.CTkFont(size=12),
                text_color="#e2e8f0",
                wraplength=980,
                justify="left"
            )
            body_lbl.pack(anchor="w", padx=14, pady=(4, 8))

            # Fotoğraf / Medya Eki (Arka planda asenkron indirilip gösterilir)
            media_urls = tw.get("media_urls", [])
            if media_urls and media_urls[0]:
                first_img_url = media_urls[0]
                img_box = ctk.CTkFrame(card, fg_color="#10131d", corner_radius=8, height=210)
                img_box.pack(fill="x", padx=14, pady=(2, 8))
                img_box.pack_propagate(False)

                lbl_img = ctk.CTkLabel(img_box, text="🖼️ Görsel yükleniyor...", font=ctk.CTkFont(size=11), text_color="#64748b")
                lbl_img.pack(expand=True)

                def _make_img_cb(target_lbl, target_box):
                    def _cb(ctk_img):
                        def _ui_upd():
                            try:
                                if target_lbl.winfo_exists():
                                    target_box.configure(height=ctk_img._size[1] + 12)
                                    target_lbl.configure(image=ctk_img, text="")
                            except Exception:
                                pass
                        try:
                            target_lbl.after(0, _ui_upd)
                        except Exception:
                            pass
                    return _cb

                gorsel_yonetici.gorsel_getir_async(first_img_url, boyut=(460, 210), callback=_make_img_cb(lbl_img, img_box))

            # Alt Aksiyon ve İstatistik Çubuğu
            foot_row = ctk.CTkFrame(card, fg_color="transparent")
            foot_row.pack(fill="x", padx=14, pady=(0, 10))

            if "Twitter" in tw.get("source", "") and (tw.get("likes") or tw.get("retweets")):
                stat_str = f"❤️ {tw.get('likes', 0):,} Beğeni   🔁 {tw.get('retweets', 0):,} Retweet"
            else:
                stat_str = f"🎮 {tw.get('source', 'Resmi Duyuru')}"

            stat_lbl = ctk.CTkLabel(
                foot_row,
                text=stat_str,
                font=ctk.CTkFont(size=11),
                text_color="#94a3b8"
            )
            stat_lbl.pack(side="left")

            btn_box = ctk.CTkFrame(foot_row, fg_color="transparent")
            btn_box.pack(side="right")

            btn_open = ctk.CTkButton(
                btn_box,
                text="🌐 Habere / Tweet'e Git",
                height=26,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#1d9bf0",
                hover_color="#0c7abf",
                command=lambda url=tw.get("tweet_url"): webbrowser.open(url)
            )
            btn_open.pack(side="left", padx=4)

            btn_chart = ctk.CTkButton(
                btn_box,
                text="📈 Piyasa Grafiğine Git",
                height=26,
                font=ctk.CTkFont(size=11),
                fg_color="#2b2d42",
                hover_color="#3d405b",
                command=self.switch_to_analytics_tab
            )
            btn_chart.pack(side="left", padx=4)

        # Daha Fazla Yükle Butonu (Kasmayı önleyen akıllı yükleme)
        if len(tweet_list) > self.tweets_display_limit:
            load_more_btn = ctk.CTkButton(
                self.tweets_scroll_frame,
                text=f"⬇️ Daha Fazla Tweet Göster (+15)  [ {min(self.tweets_display_limit, len(tweet_list))} / {len(tweet_list)} ]",
                height=36,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=self.theme["primary"],
                hover_color=self.theme["hover"],
                command=self._load_more_tweets
            )
            load_more_btn.pack(fill="x", padx=10, pady=(8, 16))

    def _load_more_tweets(self):
        self.tweets_display_limit += 15
        self.filter_and_display_tweets()

    def switch_to_tweets_tab(self):
        try:
            self.tabview.set("🐦 CS2 Tweets & Akış")
        except Exception:
            pass

    def switch_to_analytics_tab(self):
        try:
            self.tabview.set("📈 Fiyat Grafiği & Görsel")
        except Exception:
            pass

    def on_new_tweet_detected(self, tweet):
        """
        Arka plan thread'inden gelen yeni tweet sinyali.
        Thread-safe olarak ana arayüze aktarılır.
        """
        self.after(0, lambda tw=tweet: self._handle_new_tweet(tw))

    def _handle_new_tweet(self, tweet):
        """
        Yeni tweet geldiğinde:
        1. Sesli borsa alarmı çalar.
        2. Sağ altta Windows 10/11 yerel bildirimi gönderir.
        3. Akışa ve başlığa ekler.
        """
        # 1. Sesli Alarm
        if self.tweet_sound_alert:
            is_crit = (tweet.get("impact", {}).get("level") == "CRITICAL")
            tweet_yonetici.play_tweet_alarm(is_critical=is_crit)

        # 2. Windows 10/11 Yerel Bildirimi (Fotoğraf Eki Dahil)
        if self.tweet_toast_notification:
            tweet_title = f"🚨 CS2: {tweet.get('user_name', 'Counter-Strike')} (@{tweet.get('screen_name', 'CounterStrike')})"
            tweet_body = tweet.get('text', '')
            tweet_url = tweet.get('tweet_url', 'https://x.com/CounterStrike')
            media_urls = tweet.get('media_urls', [])
            first_img = media_urls[0] if (media_urls and media_urls[0]) else None

            tweet_yonetici.send_windows_notification(
                title=tweet_title,
                message=tweet_body,
                on_click_url=tweet_url,
                image_url=first_img
            )


        # 3. Akışa ekle
        tweet_id = str(tweet.get("id"))
        exists = any(str(t.get("id")) == tweet_id for t in self.displayed_tweets)
        if not exists:
            self.displayed_tweets.insert(0, tweet)
            self.filter_and_display_tweets()

        # 4. Üst bildirim rozeti
        try:
            self.status_badge.configure(
                text=f"🚨 YENİ CS2 DUYURUSU! ({tweet.get('date_str')})",
                text_color="#ef4444"
            )
        except Exception:
            pass

    def test_tweet_notification(self):
        """
        Kullanıcının alarm ve Windows yerel bildirimini test edebilmesi için simülasyon çalıştırır.
        """
        sample_tw = tweet_yonetici.create_test_tweet()
        self._handle_new_tweet(sample_tw)
        messagebox.showinfo("Windows Bildirim Testi", "✅ Sağ altta Windows yerel bildirimi gönderildi ve borsa alarmı çalındı!")


    def toggle_tweet_monitor(self):
        self.tweet_monitor_active = not self.tweet_monitor_active
        self.settings["tweet_monitor_active"] = self.tweet_monitor_active
        save_settings(self.settings)

        if self.tweet_monitor_active:
            self.tweet_status_badge.configure(text="🟢 Canlı Takip Aktif (Her 60s)", text_color="#2ecc71")
            self.tweet_manager.start_background_monitor(
                self.on_new_tweet_detected,
                interval_seconds=self.tweet_check_interval
            )
            messagebox.showinfo("Canlı Takip Başlatıldı", "CS2 Twitter & Güncelleme takibi arka planda başlatıldı.")
        else:
            self.tweet_status_badge.configure(text="⚪ Takip Duraklatıldı", text_color="#94a3b8")
            self.tweet_manager.stop_background_monitor()
            messagebox.showinfo("Canlı Takip Duraklatıldı", "Tweet takibi duraklatıldı.")


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

        self.catalog_filter_btn = ctk.CTkButton(
            f_inner, text="🔍 Filtrele", width=90, height=38, fg_color=self.theme["primary"],
            hover_color=self.theme["hover"], command=self.filter_catalog_table
        )
        self.catalog_filter_btn.pack(side="left")

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
        self._apply_tree_tags(self.catalog_tree)
        self.catalog_tree.bind("<Double-1>", lambda e: self.open_selected_catalog_in_analytics())

        # Alt Buton Çubuğu
        act_bar = ctk.CTkFrame(self.tab_catalog, fg_color="transparent")
        act_bar.pack(fill="x", padx=10, pady=(0, 8))

        btn_view_analytics = ctk.CTkButton(
            act_bar, text="📈 Görsel & Fiyat Grafiği", height=36,
            fg_color="#00b4d8", hover_color="#0096c7", font=ctk.CTkFont(weight="bold"),
            command=self.open_selected_catalog_in_analytics
        )
        btn_view_analytics.pack(side="left", padx=(0, 6))

        self.catalog_scan_btn = ctk.CTkButton(
            act_bar, text="🚀 Seçilenin Canlı Fiyatını Çek & Kaydet", height=36,
            fg_color=self.theme["primary"], hover_color=self.theme["hover"], font=ctk.CTkFont(weight="bold"),
            command=self.scan_selected_catalog_item
        )
        self.catalog_scan_btn.pack(side="left", padx=4)

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

        for i, r in enumerate(rows):
            tag = "even" if i % 2 == 0 else "odd"
            self.catalog_tree.insert("", "end", values=(
                r['esya_adi'],
                r['kategori'],
                r['alt_kategori'] or '-',
                r['silah'] or '-'
            ), tags=(tag,))

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

        chart_db_btn = ctk.CTkButton(
            top_bar, text="📈 Grafiği Gör", height=36, fg_color="#00b4d8", hover_color="#0096c7",
            font=ctk.CTkFont(weight="bold"), command=self.open_selected_db_in_analytics
        )
        chart_db_btn.pack(side="left", padx=5)

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
        self._apply_tree_tags(self.tree)
        self.tree.bind("<Double-1>", lambda e: self.open_selected_db_in_analytics())

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

        for i, r in enumerate(rows):
            fiyat_str = f"${r['son_fiyat']:.2f}" if r['son_fiyat'] is not None else "-"
            min_str = f"${r['min_fiyat']:.2f}" if r['min_fiyat'] is not None else "-"
            max_str = f"${r['max_fiyat']:.2f}" if r['max_fiyat'] is not None else "-"
            hacim_str = f"{r['son_hacim']:,}" if r['son_hacim'] is not None else "Yok"
            zaman_str = r['son_tarih'].strftime("%Y-%m-%d %H:%M") if r['son_tarih'] else "-"
            tag = "even" if i % 2 == 0 else "odd"

            self.tree.insert("", "end", values=(
                r['esya'],
                fiyat_str,
                min_str,
                max_str,
                hacim_str,
                zaman_str,
                f"{r['kayit_adet']} kez"
            ), tags=(tag,))

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

        self.theme_picker_buttons = {}
        for label_text, t_key, col in theme_list:
            is_active = (t_key == self.active_theme_name)
            border_w = 3 if is_active else 0
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
            self.theme_picker_buttons[t_key] = btn

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

        self.btn_test_db = ctk.CTkButton(
            db_card, text="🔄 Veritabanı Durumunu Yeniden Kontrol Et", width=250, height=36,
            fg_color=self.theme["primary"], hover_color=self.theme["hover"], command=self.check_initial_db_status
        )
        self.btn_test_db.pack(anchor="w", padx=20, pady=(0, 18))

        # Kart 4: 🐦 CS2 Canlı Tweet Takip & Yatırımcı Alarm Ayarları
        tweet_card = ctk.CTkFrame(container, fg_color=self.theme["card_bg"], corner_radius=12)
        tweet_card.pack(fill="x", pady=(0, 15), padx=5)

        tw_title = ctk.CTkLabel(tweet_card, text="🐦 CS2 Canlı Tweet Takip & Yatırımcı Alarm Ayarları", font=ctk.CTkFont(size=16, weight="bold"))
        tw_title.pack(anchor="w", padx=20, pady=(15, 6))

        tw_desc = ctk.CTkLabel(
            tweet_card,
            text="@CounterStrike resmi X hesabı veya Valve güncelleme yayınladığında anında sağ altta bildirim açar\nve yatırımcının pazar hareketlerini ve operasyon/kasa güncellemelerini kaçırmaması için sesli borsa alarmı çalar.",
            font=ctk.CTkFont(size=12), text_color="#8d99ae", justify="left"
        )
        tw_desc.pack(anchor="w", padx=20, pady=(0, 12))

        tw_controls = ctk.CTkFrame(tweet_card, fg_color="transparent")
        tw_controls.pack(fill="x", padx=20, pady=(0, 16))

        # Switch 1: Canlı Takip
        self.setting_tweet_mon_switch = ctk.CTkSwitch(
            tw_controls, text="Canlı Tweet & Güncelleme Takibi (Arka Planda Dinle)", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._setting_toggle_tweet_monitor
        )
        if self.tweet_monitor_active:
            self.setting_tweet_mon_switch.select()
        else:
            self.setting_tweet_mon_switch.deselect()
        self.setting_tweet_mon_switch.pack(anchor="w", pady=4)

        # Switch 2: Sesli Alarm
        self.setting_tweet_sound_switch = ctk.CTkSwitch(
            tw_controls, text="Sesli Yatırımcı Alarmı (Windows Çanı / Borsa Tonu)", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._setting_toggle_tweet_sound
        )
        if self.tweet_sound_alert:
            self.setting_tweet_sound_switch.select()
        else:
            self.setting_tweet_sound_switch.deselect()
        self.setting_tweet_sound_switch.pack(anchor="w", pady=4)

        # Switch 3: Sağ Alt Toast Popup
        self.setting_tweet_toast_switch = ctk.CTkSwitch(
            tw_controls, text="Ekranın Sağ Altında Bildirim Kartı Aç (Toast Popup)", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._setting_toggle_tweet_toast
        )
        if self.tweet_toast_notification:
            self.setting_tweet_toast_switch.select()
        else:
            self.setting_tweet_toast_switch.deselect()
        self.setting_tweet_toast_switch.pack(anchor="w", pady=4)

        # Butonlar satırı
        tw_btn_row = ctk.CTkFrame(tw_controls, fg_color="transparent")
        tw_btn_row.pack(fill="x", pady=(12, 0))

        btn_test_sound = ctk.CTkButton(
            tw_btn_row, text="🔔 Alarm Sesini Çal", width=160, height=34,
            fg_color="#f59e0b", hover_color="#d97706",
            command=lambda: tweet_yonetici.play_tweet_alarm(True)
        )
        btn_test_sound.pack(side="left", padx=(0, 10))

        self.btn_test_toast_setting = ctk.CTkButton(
            tw_btn_row, text="🧪 Sağ Alt Bildirimi Test Et", width=200, height=34,
            fg_color=self.theme["primary"], hover_color=self.theme["hover"],
            command=self.test_tweet_notification
        )
        self.btn_test_toast_setting.pack(side="left")

    def _setting_toggle_tweet_monitor(self):
        self.tweet_monitor_active = bool(self.setting_tweet_mon_switch.get())
        self.settings["tweet_monitor_active"] = self.tweet_monitor_active
        save_settings(self.settings)
        if hasattr(self, 'tweet_monitor_switch'):
            if self.tweet_monitor_active:
                self.tweet_monitor_switch.select()
                self.tweet_status_badge.configure(text="🟢 Canlı Takip Aktif (Her 60s)", text_color="#2ecc71")
                self.tweet_manager.start_background_monitor(self.on_new_tweet_detected, interval_seconds=self.tweet_check_interval)
            else:
                self.tweet_monitor_switch.deselect()
                self.tweet_status_badge.configure(text="⚪ Takip Duraklatıldı", text_color="#94a3b8")
                self.tweet_manager.stop_background_monitor()

    def _setting_toggle_tweet_sound(self):
        self.tweet_sound_alert = bool(self.setting_tweet_sound_switch.get())
        self.settings["tweet_sound_alert"] = self.tweet_sound_alert
        save_settings(self.settings)

    def _setting_toggle_tweet_toast(self):
        self.tweet_toast_notification = bool(self.setting_tweet_toast_switch.get())
        self.settings["tweet_toast_notification"] = self.tweet_toast_notification
        save_settings(self.settings)

    def change_accent_theme(self, theme_name):
        if theme_name in THEMES:
            self.active_theme_name = theme_name
            self.theme = THEMES[theme_name]
            self.settings["accent_theme"] = theme_name
            save_settings(self.settings)

            # 1. Başlık çubuğu göstergesi
            if hasattr(self, 'theme_indicator'):
                self.theme_indicator.configure(text=f"  🎨 {self.active_theme_name}", text_color=self.theme["accent"])

            # 2. CTkTabview sekme butonları
            if hasattr(self, 'tabview'):
                self.tabview.configure(
                    segmented_button_selected_color=self.theme["primary"],
                    segmented_button_selected_hover_color=self.theme["hover"]
                )

            # 3. Treeview seçili satır & başlık hover rengi
            if hasattr(self, 'tree_style'):
                self.tree_style.map(
                    "Treeview",
                    background=[("selected", self.theme["primary"])],
                    foreground=[("selected", "#ffffff")]
                )
                self.tree_style.map(
                    "Treeview.Heading",
                    foreground=[("active", self.theme["accent"])]
                )

            # 4. Aksiyon butonları
            for btn_attr in ['scan_btn', 'btn_cat_scan', 'analytics_btn_update', 'wl_add_btn', 'wl_scan_btn', 'catalog_filter_btn', 'catalog_scan_btn', 'btn_test_db', 'tweet_refresh_btn', 'btn_test_toast_setting']:
                btn = getattr(self, btn_attr, None)
                if btn:
                    try:
                        btn.configure(fg_color=self.theme["primary"], hover_color=self.theme["hover"])
                    except Exception:
                        pass

            if hasattr(self, 'tweet_filter_buttons') and hasattr(self, 'active_tweet_filter'):
                for k, btn in self.tweet_filter_buttons.items():
                    if k == self.active_tweet_filter:
                        try:
                            btn.configure(fg_color=self.theme["primary"], hover_color=self.theme["hover"])
                        except Exception:
                            pass


            # 5. Zaman aralığı butonları
            if hasattr(self, 'timeframe_buttons') and hasattr(self, 'selected_timeframe'):
                for tf_code, btn in self.timeframe_buttons.items():
                    if tf_code == self.selected_timeframe:
                        btn.configure(fg_color=self.theme["primary"], hover_color=self.theme["hover"])

            # 6. Tema seçici butonların çerçeveleri
            if hasattr(self, 'theme_picker_buttons'):
                for k, btn in self.theme_picker_buttons.items():
                    bw = 3 if k == theme_name else 0
                    btn.configure(border_width=bw)

            # 7. Vurgu metinleri & Sayaç
            if hasattr(self, 'analytics_price_val'):
                self.analytics_price_val.configure(text_color=self.theme["accent"])
            if hasattr(self, 'auto_scan_countdown_lbl'):
                self.auto_scan_countdown_lbl.configure(text_color=self.theme["accent"])

            # 8. Açık olan grafiği yeni tema rengiyle tazele
            if hasattr(self, 'current_analytics_item') and self.current_analytics_item:
                self.load_item_analytics(self.current_analytics_item)

            messagebox.showinfo("Tema Güncellendi", f"Tema '{theme_name}' olarak değiştirildi ve uygulandı!")

    def change_appearance_mode(self, mode):
        ctk.set_appearance_mode(mode)
        self.settings["appearance_mode"] = mode
        save_settings(self.settings)


if __name__ == "__main__":
    app = CS2MarketApp()
    app.mainloop()
