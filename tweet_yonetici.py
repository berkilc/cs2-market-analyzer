"""
CS2 Tweet Yöneticisi & Yatırımcı Alarm Sistemi (tweet_yonetici.py)
---------------------------------------------------------------
Counter-Strike 2 resmi (@CounterStrike) tweetlerini ve resmi Valve CS2
güncelleme duyurularını canlı takip eder.
Yeni tweet veya kritik piyasa güncellemesi geldiğinde:
1. Ekranın sağ altında şık, modern bildirim kartı (Toast Popup) açar.
2. Yatırımcı için dikkat çekici sesli alarm çalar (Windows winsound).
3. Uygulama içerisindeki '🐦 CS2 Tweets & Akış' sayfasını anlık günceller.
"""

import os
import sys
import re
import json
import time
import threading
import webbrowser
from datetime import datetime
import requests
import customtkinter as ctk

# Windows ses desteği (Standart Python kütüphanesi)
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# Temel dizin ve önbellek
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
TWEETS_CACHE_FILE = os.path.join(CACHE_DIR, "cs2_tweets_cache.json")
TWEET_STATE_FILE = os.path.join(CACHE_DIR, "tweet_state.json")

# Piyasa & Yatırımcı Etki Anahtar Kelimeleri
CRITICAL_MARKET_KEYWORDS = [
    "release notes", "update", "case", "operation", "armory", "patch",
    "major", "capsule", "sticker", "skin", "weapon", "trade", "souvenir",
    "discount", "sale", "kilowatt", "gallery", "revolution", "recoil",
    "dreams & nightmares", "vertigo", "train", "mirage", "dust", "anubis",
    "inferno", "nuke", "ancient", "overpass", "anti-cheat", "vac", "ban",
    "key", "drop pool", "limited edition", "pass", "music kit"
]

HIGH_IMPACT_KEYWORDS = [
    "release notes", "operation", "the armory", "case", "update today",
    "major update", "capsule sale", "new case", "weapon overhaul", "discontinue"
]


def is_valid_english_content(text: str) -> bool:
    """
    Rusça (Kiril) veya yabancı dildeki üçüncü parti içerikleri engeller.
    Sadece İngilizce / Latin tabanlı resmi CS2 paylaşımlarını kabul eder.
    """
    if not text:
        return False
    # Kiril alfabesi (Rusça, Ukraynaca vb.) kontrolü
    if re.search(r'[\u0400-\u04FF]', text):
        return False
    # Asya ve Arapça alfabe kontrolleri
    if re.search(r'[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF\u0600-\u06FF]', text):
        return False
    return True


def clean_bbcode(text: str) -> str:
    """
    Steam duyurularındaki [b], [p], [list], [*], [/*] BBCode etiketlerini temizler
    ve düzgün, maddeli, profesyonel okunabilir metne dönüştürür.
    """
    if not text:
        return ""
    # Kaçış karakterli köşeli parantezleri düzelt (\[ -> [, \] -> ])
    text = text.replace(r'\[', '[').replace(r'\]', ']')
    # Başlıklar
    text = re.sub(r'\[h\d\](.*?)\[/h\d\]', r'\1\n', text, flags=re.IGNORECASE)
    # Kalın, italik ve altı çizili
    text = re.sub(r'\[b\](.*?)\[/b\]', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\[i\](.*?)\[/i\]', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\[u\](.*?)\[/u\]', r'\1', text, flags=re.IGNORECASE)
    # Bağlantılar
    text = re.sub(r'\[url=(.*?)\](.*?)\[/url\]', r'\2 (\1)', text, flags=re.IGNORECASE)
    text = re.sub(r'\[url\](.*?)\[/url\]', r'\1', text, flags=re.IGNORECASE)
    # Liste maddeleri ve sonlandırıcılar ([/*], [*], [p])
    text = re.sub(r'\[/\*\]', '', text)
    text = re.sub(r'\[\*\]\[p\]', '\n• ', text, flags=re.IGNORECASE)
    text = re.sub(r'\[\*\]', '\n• ', text)
    text = re.sub(r'\[/?list\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\[/?p\]', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'\[/?quote\]', '', text, flags=re.IGNORECASE)
    # Kalan tüm BBCode etiketlerini temizle
    text = re.sub(r'\[/?[^\]]+\]', '', text)
    # HTML etiketlerini temizle
    text = re.sub(r'<[^>]+>', '', text)
    # Satırları toparla
    lines = [line.strip() for line in text.split('\n')]
    cleaned = '\n'.join([l for l in lines if l])
    return cleaned.strip()



def play_tweet_alarm(is_critical=True):
    """
    Arka planda GUI'yi dondurmadan yatırımcı alarm sesi çalar.
    Yükselen harmonik arpej (G5 -> C6 -> E6).
    """
    def _beep():
        if not HAS_WINSOUND:
            return
        try:
            if is_critical:
                # Yatırımcı için dikkat çekici yükselen 3 tonlu borsa alarmı
                winsound.Beep(784, 110)
                time.sleep(0.03)
                winsound.Beep(1046, 130)
                time.sleep(0.03)
                winsound.Beep(1318, 220)
            else:
                # Hafif bildirim çanı
                winsound.Beep(1046, 100)
                time.sleep(0.04)
                winsound.Beep(1318, 160)
        except Exception:
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                pass

    threading.Thread(target=_beep, daemon=True).start()


def send_windows_notification(title: str, message: str, on_click_url: str = None, image_url: str = None):
    """
    Windows 10/11 yerel Bildirim Merkezi (Action Center) bildirimini tetikler.
    Kullanıcının ekranının sağ altında yerel Windows kartı olarak görünür.
    Eğer tweet veya güncellemede fotoğraf varsa, bildirimde zengin görsel (Hero Image) olarak çıkar.
    """
    def _send():
        try:
            import win11toast
            clean_msg = re.sub(r'https?://\S+', '', message).strip()
            # Satır sonlarını toparla
            clean_msg = re.sub(r'\n+', ' ', clean_msg)
            if len(clean_msg) > 140:
                clean_msg = clean_msg[:137] + "..."

            kwargs = {
                "title": title,
                "body": clean_msg,
                "on_click": on_click_url or "https://x.com/CounterStrike"
            }
            icon_path = os.path.join(BASE_DIR, "icon.png")
            if not os.path.exists(icon_path) and hasattr(sys, '_MEIPASS'):
                icon_path = os.path.join(sys._MEIPASS, "icon.png")
            if os.path.exists(icon_path):
                kwargs["icon"] = icon_path

            if image_url:
                kwargs["image"] = image_url

            win11toast.toast(**kwargs)

        except Exception as e:
            print("Windows yerel bildirim hatası:", e)


    threading.Thread(target=_send, daemon=True).start()



def analyze_market_impact(text: str) -> dict:

    """
    Tweet metnini analiz ederek CS2 yatırımcısı için piyasa etkisini belirler.
    """
    if not text:
        return {"level": "NORMAL", "label": "📢 CS2 Paylaşımı", "color": "#3b82f6", "badge": "BİLGİ"}
    
    text_lower = text.lower()
    
    # 1. En Yüksek Seviye: Güncelleme & Kasa & Operasyon
    for kw in HIGH_IMPACT_KEYWORDS:
        if kw in text_lower:
            return {
                "level": "CRITICAL",
                "label": "🚨 KRİTİK GÜNCELLEME (Piyasa Oynaklığı!)",
                "color": "#ef4444",
                "badge": "YÜKSEK ETKİ"
            }
            
    # 2. Orta Seviye: Genel CS2 Değişikliği / Major / Harita
    matched_kws = [kw for kw in CRITICAL_MARKET_KEYWORDS if kw in text_lower]
    if matched_kws:
        return {
            "level": "MEDIUM",
            "label": f"⚡ Piyasa Haberi ({matched_kws[0].title()})",
            "color": "#f59e0b",
            "badge": "DİKKAT"
        }
        
    return {
        "level": "LOW",
        "label": "💬 CS2 Duyurusu & Medya",
        "color": "#10b981",
        "badge": "STANDART"
    }


def parse_tweet_date(created_at_str: str) -> tuple[datetime, str]:
    """
    Tweet veya Steam haber tarihini datetime ve Türkçe okunabilir metne çevirir.
    """
    if not created_at_str:
        return datetime.min, "Bilinmeyen Tarih"
    try:
        dt = datetime.strptime(created_at_str, "%a %b %d %H:%M:%S %z %Y")
        readable = dt.strftime("%d.%m.%Y - %H:%M")
        return dt, readable
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        readable = dt.strftime("%d.%m.%Y - %H:%M")
        return dt, readable
    except Exception:
        return datetime.min, created_at_str


class CS2TweetManager:
    def __init__(self, screen_name="CounterStrike"):
        self.screen_name = screen_name
        self.last_seen_tweet_id = self._load_last_seen_id()
        self.cached_tweets = self._load_cached_tweets()
        self.is_monitoring = False
        self._monitor_thread = None
        self._stop_event = threading.Event()
        self.on_new_tweet_callback = None
        self.last_check_time = None
        self.active_sources = ["Twitter Syndication", "Steam CS2 News API"]

    def _load_last_seen_id(self) -> str:
        if os.path.exists(TWEET_STATE_FILE):
            try:
                with open(TWEET_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("last_seen_tweet_id")
            except Exception:
                pass
        return None

    def _save_last_seen_id(self, tweet_id: str):
        self.last_seen_tweet_id = tweet_id
        try:
            with open(TWEET_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump({"last_seen_tweet_id": tweet_id, "updated_at": datetime.now().isoformat()}, f, indent=2)
        except Exception:
            pass

    def _load_cached_tweets(self) -> list:
        if os.path.exists(TWEETS_CACHE_FILE):
            try:
                with open(TWEETS_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Eski önbellekte kalmış olabilecek Rusça veya üçüncü parti içerikleri temizle
                    clean_data = []
                    for item in data:
                        text = item.get("text", "")
                        user = item.get("user_name", "")
                        if is_valid_english_content(text) and is_valid_english_content(user):
                            # Metin içindeki BBCode kalıntılarını da temizle
                            item["text"] = clean_bbcode(text)
                            clean_data.append(item)
                    return clean_data
            except Exception:
                pass
        return []

    def _save_cached_tweets(self, tweets: list):
        # Yalnızca geçerli İngilizce içerikleri kaydet
        clean_tweets = [t for t in tweets if is_valid_english_content(t.get("text", ""))]
        self.cached_tweets = clean_tweets
        try:
            with open(TWEETS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(clean_tweets, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def fetch_tweets(self) -> tuple[bool, list]:
        """
        Twitter Syndication üzerinden en güncel @CounterStrike tweetlerini çeker.
        Ayrıca Steam News API üzerinden CS2 resmi güncelleme notlarını alıp birleştirir.
        Yalnızca İngilizce resmi içerikleri kabul eder.
        """
        self.last_check_time = datetime.now()
        collected_tweets = []

        # 1. Kaynak: Twitter Syndication
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{self.screen_name}"

        try:
            res = requests.get(url, headers=headers, timeout=8)
            if res.status_code == 200:
                match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', res.text, re.DOTALL)
                if match:
                    payload = json.loads(match.group(1))
                    page_props = payload.get("props", {}).get("pageProps", {})
                    entries = page_props.get("timeline", {}).get("entries", [])
                    
                    for entry in entries:
                        content = entry.get("content", {})
                        tweet_data = content.get("tweet", {})
                        if not tweet_data:
                            continue
                        
                        text = tweet_data.get("text", "")
                        # Kesinlikle sadece İngilizce / Latin tweetleri kabul et
                        if not is_valid_english_content(text):
                            continue

                        t_id = tweet_data.get("id_str")
                        created_at_raw = tweet_data.get("created_at", "")
                        dt, formatted_date = parse_tweet_date(created_at_raw)
                        
                        user_info = tweet_data.get("user", {})
                        user_name = user_info.get("name", "CS2")
                        screen_name = user_info.get("screen_name", "CounterStrike")
                        avatar_url = user_info.get("profile_image_url_https", "")
                        
                        fav_count = tweet_data.get("favorite_count", 0)
                        rt_count = tweet_data.get("retweet_count", 0)
                        
                        entities = tweet_data.get("entities", {})
                        media_urls = []
                        if "media" in entities:
                            for m in entities["media"]:
                                m_url = m.get("media_url_https")
                                if m_url:
                                    media_urls.append(m_url)
                        
                        urls = [u.get("expanded_url") for u in entities.get("urls", []) if u.get("expanded_url")]
                        tweet_url = f"https://x.com/{screen_name}/status/{t_id}"
                        impact = analyze_market_impact(text)

                        collected_tweets.append({
                            "id": t_id,
                            "timestamp": dt.timestamp() if dt else 0,
                            "date_str": formatted_date,
                            "user_name": user_name,
                            "screen_name": screen_name,
                            "avatar_url": avatar_url,
                            "text": text,
                            "likes": fav_count,
                            "retweets": rt_count,
                            "media_urls": media_urls,
                            "urls": urls,
                            "tweet_url": tweet_url,
                            "impact": impact,
                            "source": "Twitter / X"
                        })
        except Exception:
            pass

        # 2. Kaynak: Steam News API (Yalnızca Resmi Valve CS2 Güncellemeleri)
        steam_news = self.fetch_steam_cs2_news()
        if steam_news:
            collected_tweets.extend(steam_news)

        # 3. Önbellekteki geçmiş verilerle birleştir
        cached_valid = [t for t in (self.cached_tweets or []) if is_valid_english_content(t.get("text", ""))]
        combined_pool = collected_tweets + cached_valid
        unique_tweets = []
        seen_ids = set()

        for item in combined_pool:
            item_id = str(item.get("id"))
            item_text = item.get("text", "")
            if not is_valid_english_content(item_text):
                continue
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                unique_tweets.append(item)

        # Tarihe göre en yeniden eskiye doğru sırala
        unique_tweets.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        if unique_tweets:
            self._save_cached_tweets(unique_tweets)
            return True, unique_tweets

        return False, []

    def fetch_steam_cs2_news(self) -> list:
        """
        Yalnızca resmi Valve Steam CS2 güncelleme bültenlerini (Release Notes) getirir.
        Üçüncü parti haber sitelerini (Rusça vb.) kesinlikle filtreler.
        """
        try:
            url = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=730&count=25&feeds=steam_community_announcements"
            res = requests.get(url, timeout=8)
            if res.status_code == 200:
                data = res.json()
                items = data.get("appnews", {}).get("newsitems", [])
                news_list = []
                for item in items:
                    feedname = item.get("feedname", "")
                    feedlabel = item.get("feedlabel", "")
                    # Yalnızca Valve'ın resmi topluluk duyurularını al
                    if feedname != "steam_community_announcements" and feedlabel != "Community Announcements":
                        continue

                    title = item.get("title", "Counter-Strike 2 Update")
                    raw_contents = item.get("contents", "")

                    # Rusça / Kiril veya İngilizce dışı içerikleri kesinlikle reddet
                    if not is_valid_english_content(title) or not is_valid_english_content(raw_contents):
                        continue

                    t_id = f"steam_{item.get('gid')}"
                    # Görselleri yakala (Steam clan images ve cdn linkleri)
                    raw_media = re.findall(r'\[img\](.*?)\[/img\]', raw_contents, re.IGNORECASE)
                    media_urls = [m.replace('{STEAM_CLAN_IMAGE}', 'https://clan.fastly.steamstatic.com/images').strip() for m in raw_media if m.strip()]

                    cleaned_body = clean_bbcode(raw_contents)
                    
                    full_text = f"{title}\n\n{cleaned_body}" if cleaned_body else title
                    date_ts = item.get("date", 0)
                    dt = datetime.fromtimestamp(date_ts)
                    date_str = dt.strftime("%d.%m.%Y - %H:%M")
                    news_url = item.get("url", "https://store.steampowered.com/news/app/730")
                    impact = analyze_market_impact(full_text)

                    author = item.get("author", "Valve")
                    user_name = "Counter-Strike 2 (Valve)"

                    news_list.append({
                        "id": t_id,
                        "timestamp": date_ts,
                        "date_str": date_str,
                        "user_name": user_name,
                        "screen_name": "CounterStrike",
                        "avatar_url": "",
                        "text": full_text,
                        "likes": 0,
                        "retweets": 0,
                        "media_urls": media_urls,
                        "urls": [news_url],
                        "tweet_url": news_url,
                        "impact": impact,
                        "source": "Steam / Valve"
                    })

                return news_list
        except Exception:
            pass
        return []


    def check_for_new_tweets(self) -> list:
        """
        Yeni atılmış tweet veya güncelleme haberini tespit eder.
        Daha önce görülmemiş olanları döndürür.
        """
        success, tweets = self.fetch_tweets()
        if not success or not tweets:
            return []

        latest_tweet = tweets[0]
        latest_id = str(latest_tweet["id"])

        # İlk çalıştırma durumu: Eğer kayıtlı bir ID yoksa, en yeniyi kaydet ve başlangıçta alarm çalma
        if not self.last_seen_tweet_id:
            self._save_last_seen_id(latest_id)
            return []

        # Eğer en yeni tweet zaten görülmüşse yeni tweet yoktur
        if latest_id == self.last_seen_tweet_id:
            return []

        # Yeni gelen tweetleri topla
        new_tweets = []
        for t in tweets:
            if str(t["id"]) == self.last_seen_tweet_id:
                break
            new_tweets.append(t)

        # En son görülen ID'yi güncelle
        self._save_last_seen_id(latest_id)
        return new_tweets

    def start_background_monitor(self, on_new_tweet_callback, interval_seconds=60):
        """
        Belirlenen aralıklarla arka planda yeni tweetleri tarar.
        """
        if self.is_monitoring:
            return

        self.on_new_tweet_callback = on_new_tweet_callback
        self.is_monitoring = True
        self._stop_event.clear()

        def _monitor_loop():
            # İlk açılışta hemen bir kontrol yap
            time.sleep(3)
            while not self._stop_event.is_set():
                try:
                    new_tweets = self.check_for_new_tweets()
                    if new_tweets and self.on_new_tweet_callback:
                        for tw in reversed(new_tweets):
                            self.on_new_tweet_callback(tw)
                except Exception as e:
                    print(f"Tweet arka plan izleme hatası: {e}")

                # Interval süresince bekle (durdurulabilir şekilde)
                for _ in range(max(1, int(interval_seconds))):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)

        self._monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_background_monitor(self):
        self.is_monitoring = False
        self._stop_event.set()


def create_test_tweet() -> dict:
    """
    Kullanıcının alarm ve bildirimi anında test edebilmesi için simüle edilmiş örnek CS2 tweeti üretir.
    """
    now = datetime.now()
    return {
        "id": f"test_{int(time.time())}",
        "timestamp": now.timestamp(),
        "date_str": now.strftime("%d.%m.%Y - %H:%M"),
        "user_name": "CS2",
        "screen_name": "CounterStrike",
        "avatar_url": "",
        "text": "Release Notes for today are up: The Armory Update is live! Introducing new weapon charms, 3 new collections, and the Gallery Case.",
        "likes": 48200,
        "retweets": 7920,
        "media_urls": ["https://clan.fastly.steamstatic.com/images/3381077/4ccfe4f44119ac6ddd5cd39d24c907dd11f4c70a.png"],
        "urls": ["https://x.com/CounterStrike"],

        "tweet_url": "https://x.com/CounterStrike",
        "impact": {
            "level": "CRITICAL",
            "label": "🚨 KRİTİK GÜNCELLEME (Piyasa Oynaklığı!)",
            "color": "#ef4444",
            "badge": "YÜKSEK ETKİ"
        },
        "source": "Twitter / X (Test)"
    }


# ==============================================================================
# SAĞ ALT BİLDİRİM PENCERESİ (TOAST POPUP)
# ==============================================================================
class TweetToastNotification(ctk.CTkToplevel):
    """
    Ekranın sağ altında belirip yatırımcıya yeni tweet haberini veren şık popup.
    Windows masaüstünün sağ alt köşesinde (saatin hemen üzerinde) görünür.
    """
    def __init__(self, master_app, tweet_data, on_open_tab_callback=None, theme=None):
        super().__init__(master_app)

        self.tweet_data = tweet_data
        self.on_open_tab_callback = on_open_tab_callback
        self.theme = theme or {
            "primary": "#00b4d8",
            "hover": "#0077b6",
            "card_bg": "#141724",
            "card_border": "#00f0ff",
            "accent": "#00f0ff"
        }

        # Pencere ayarları
        self.overrideredirect(True)  # Kenarlıksız modern kart
        self.attributes("-topmost", True)  # Her zaman üstte
        try:
            self.attributes("-alpha", 0.97)  # Hafif saydamlık
        except Exception:
            pass

        # Boyutlar
        width = 440
        height = 205

        # Ekranın sağ alt köşesini hesapla (Görev çubuğunun hemen üstü)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(10, screen_w - width - 20)
        y = max(10, screen_h - height - 65)

        self.geometry(f"{width}x{height}+{x}+{y}")
        self.configure(fg_color="#090b10")

        self._remaining_seconds = 15
        self._build_content(width, height)
        self._start_countdown()

    def _build_content(self, width, height):
        impact = self.tweet_data.get("impact", {})
        border_color = impact.get("color", self.theme.get("primary", "#00b4d8"))

        main_box = ctk.CTkFrame(
            self,
            fg_color="#121520",
            corner_radius=12,
            border_width=2,
            border_color=border_color
        )
        main_box.pack(fill="both", expand=True, padx=2, pady=2)

        # Üst Başlık Satırı
        header = ctk.CTkFrame(main_box, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(10, 4))

        title_lbl = ctk.CTkLabel(
            header,
            text=f"🚨 YENİ CS2 TWEETİ! (@{self.tweet_data.get('screen_name', 'CounterStrike')})",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#ffffff"
        )
        title_lbl.pack(side="left")

        # Rozet
        badge_lbl = ctk.CTkLabel(
            header,
            text=f" {impact.get('badge', 'BİLGİ')} ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=impact.get("color", "#3b82f6"),
            text_color="#ffffff",
            corner_radius=6
        )
        badge_lbl.pack(side="left", padx=8)

        # Kapat 'X' Butonu
        btn_close = ctk.CTkButton(
            header,
            text="✕",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color="#ef4444",
            text_color="#94a3b8",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.destroy
        )
        btn_close.pack(side="right")

        # Zaman & Kaynak Satırı
        sub_bar = ctk.CTkFrame(main_box, fg_color="transparent")
        sub_bar.pack(fill="x", padx=14, pady=(0, 4))
        
        source = self.tweet_data.get("source", "X / Twitter")
        time_lbl = ctk.CTkLabel(
            sub_bar,
            text=f"🕒 {self.tweet_data.get('date_str', 'Şimdi')} • {source} • Yatırımcı Alarmı",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        time_lbl.pack(side="left")

        # Tweet Metni (Kısa özet)
        raw_text = self.tweet_data.get("text", "")
        # Linkleri temizle veya kısalt
        clean_text = re.sub(r'https?://\S+', '', raw_text).strip()
        if len(clean_text) > 140:
            clean_text = clean_text[:137] + "..."
        if not clean_text:
            clean_text = "(Görsel, Video veya Güncelleme Bağlantısı)"

        body_lbl = ctk.CTkLabel(
            main_box,
            text=clean_text,
            font=ctk.CTkFont(size=12),
            text_color="#e2e8f0",
            wraplength=400,
            justify="left"
        )
        body_lbl.pack(anchor="w", padx=14, pady=(2, 8))

        # Alt Butonlar Satırı
        footer = ctk.CTkFrame(main_box, fg_color="transparent")
        footer.pack(fill="x", padx=14, pady=(0, 10), side="bottom")

        btn_tweet = ctk.CTkButton(
            footer,
            text="🌐 Habere / X'e Git",
            height=30,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1d9bf0",
            hover_color="#0c7abf",
            command=self._open_tweet_in_browser
        )
        btn_tweet.pack(side="left", padx=(0, 6), expand=True, fill="x")

        btn_app = ctk.CTkButton(
            footer,
            text="📊 Akışı Uygulamada Gör",
            height=30,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=self.theme.get("primary", "#00b4d8"),
            hover_color=self.theme.get("hover", "#0077b6"),
            command=self._go_to_app
        )
        btn_app.pack(side="left", padx=6, expand=True, fill="x")

        self.lbl_timer = ctk.CTkLabel(
            footer,
            text=f"({self._remaining_seconds}s)",
            font=ctk.CTkFont(size=10),
            text_color="#64748b",
            width=32
        )
        self.lbl_timer.pack(side="right")

    def _start_countdown(self):
        if self._remaining_seconds <= 0:
            try:
                self.destroy()
            except Exception:
                pass
            return
        try:
            self.lbl_timer.configure(text=f"({self._remaining_seconds}s)")
            self._remaining_seconds -= 1
            self.after(1000, self._start_countdown)
        except Exception:
            pass

    def _open_tweet_in_browser(self):
        url = self.tweet_data.get("tweet_url", f"https://x.com/CounterStrike/status/{self.tweet_data.get('id')}")
        webbrowser.open(url)
        self.destroy()

    def _go_to_app(self):
        if self.master:
            try:
                self.master.deiconify()
                self.master.lift()
                self.master.focus_force()
            except Exception:
                pass
        if self.on_open_tab_callback:
            try:
                self.on_open_tab_callback()
            except Exception:
                pass
        self.destroy()

