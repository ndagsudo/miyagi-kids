import sqlite3
import csv
import urllib.request
import json
import datetime as dt
import re
import xml.etree.ElementTree as ET
from datetime import datetime, date
from pathlib import Path
from html import escape
from html.parser import HTMLParser

print("RUNNING:", __file__)

# ===== CSS定義 =====
CSS = """
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
               "Hiragino Kaku Gothic ProN", "Meiryo", sans-serif;
  background: #f3f4f6;
  margin: 0;
  color: #333;
}

header {
  background: #4caf50;
  color: white;
  padding: 16px;
}

header h1 {
  margin: 0;
  font-size: 22px;
}

.container {
  max-width: 900px;
  margin: 0 auto;
  padding: 16px;
}

.card {
  background: white;
  border-radius: 10px;
  padding: 14px;
  margin: 12px 0;
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}

.card h3 {
  margin: 0 0 6px 0;
  font-size: 18px;
}

.meta {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.card a {
  color: inherit;
  text-decoration: none;
}

.card a:hover {
  text-decoration: underline;
}

/* ===== 検索UI ===== */
.searchbar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin: 12px 0 18px;
}
.searchbar input {
  flex: 1;
  padding: 12px 14px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  font-size: 16px;
  outline: none;
}
.searchbar input:focus {
  border-color: #4caf50;
}
.resultcount {
  font-size: 13px;
  color: #666;
  white-space: nowrap;
}

footer {
  text-align: center;
  font-size: 12px;
  color: #888;
  padding: 16px;
}

/* ===== 検索UI ===== */
.searchbar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin: 12px 0 18px;
}
.searchbar input {
  flex: 1;
  padding: 12px 14px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  font-size: 16px;
}
.resultcount {
  font-size: 13px;
  color: #666;
  white-space: nowrap;
}

/* ===== フィルターチップ ===== */
.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.chip {
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 999px;
  background: #fff;
  font-size: 14px;
  cursor: pointer;
}
.chip.active {
  border-color: #4caf50;
  box-shadow: 0 0 0 2px rgba(76,175,80,0.20);
}

/* ===== バッジ ===== */
.badges {
  display: flex;
  gap: 6px;
  margin: 6px 0 2px;
}
.badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid #d1d5db;
  background: #fff;
}
.badge-free {
  border-color: #4caf50;
  background: #f0fff4;  /* うす緑背景 */
}

/* ===== カードヘッダー横並び ===== */
.cardhead {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;          /* 小さめ */
}

.cardhead h3 {
  flex: 1;           /* タイトルが伸びる */
}

.cardhead .badges {
  margin: 0;
}

h1 {
  font-size: 26px;
  margin: 10px 0 8px;
}
hr {
  border: none;
  border-top: 1px solid #e5e7eb;
  margin: 14px 0 14px;
}
"""

# ===== 設定 =====
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"
DB_PATH = DATA_DIR / "data.db"

# ★ あなたのCSV直リンク
SENDAI_EVENTS_CSV_URL = "https://data.city.sendai.jp/datastore/dump/2314f2dc-da9e-4800-aae9-355a67649968?bom=True"

SITE_URL = "https://ndagsudo.github.io/miyagi-kids"

# ===== DB =====
DDL = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT,
  source_id TEXT,
  title TEXT,
  summary TEXT,
  url TEXT,
  start_at TEXT,
  end_at TEXT,
  area TEXT,
  venue_name TEXT,
  price_band TEXT,
  tags_json TEXT,
  kid_score INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_source_sourceid
ON events(source, source_id);
"""

def connect_db():
    print("USING DB:", DB_PATH)
    DATA_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(DDL)
    return con

# ===== CSV取得 =====
def download_csv(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        raw = r.read()

    for enc in ("utf-8-sig", "utf-8", "cp932"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")

    if "<html" in text.lower():
        raise RuntimeError("CSVではなくHTMLを取得しています")

    rows = list(csv.DictReader(text.splitlines()))
    return rows

def download_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        raw = r.read()
    return raw.decode("utf-8", errors="replace")

def download_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        raw = r.read()
    return raw.decode("utf-8", errors="replace")

def debug_print_html_head(url: str, limit: int = 2000):
    html_text = download_html(url)
    print("DEBUG URL:", url)
    print(html_text[:limit])

def debug_print_links(url: str):
    html_text = download_html(url)
    links = re.findall(r'href=["\']([^"\']+)["\']', html_text, flags=re.I)
    print("DEBUG LINKS:", url)
    for link in sorted(set(links)):
        if "event" in link.lower():
            print(link)

def _japanese_dates_to_ymd_list(text: str):
    dates = []
    for y, m, d in re.findall(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text):
        dates.append(f"{int(y):04d}-{int(m):02d}-{int(d):02d}")
    return dates

def _wareki_to_seireki_year(y: int) -> int:
    # 令和n年 → 2018 + n
    return 2018 + y

def _museum_dates_to_ymd_list(text: str):
    dates = []

    # 令和8年4月18日 のような形式
    for y, m, d in re.findall(r"令和(\d+)年(\d{1,2})月(\d{1,2})日", text):
        yy = _wareki_to_seireki_year(int(y))
        dates.append(f"{yy:04d}-{int(m):02d}-{int(d):02d}")

    return dates

def _strip_tags(html_text: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html_text, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", html_text, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

# ===== 取り込み =====
def import_sendai_events(con):
    rows = download_csv(SENDAI_EVENTS_CSV_URL)
    print("CSV columns:", rows[0].keys())

    cur = con.cursor()
    cur.execute("DELETE FROM events WHERE source=?", ("sendai_csv",))

    count = 0
    for r in rows:
        title = (r.get("name") or "").strip()
        if not title:
            continue

        summary = r.get("summary") or ""
        start = r.get("startDate") or ""
        end_ = r.get("endDate") or ""
        venue = r.get("locationName") or ""
        url = r.get("detailedUrl") or ""

        base_id = r.get("entity_id") or r.get("_id") or title
        source_id = f"{base_id}|{start}|{end_}"

        text = title + summary
        tags = {}
        score = 60

        if any(x in text for x in ["小学生", "親子", "子ども", "体験", "工作"]):
            tags["elem"] = True
            score = 80
        if "無料" in text:
            tags["free"] = True

        cur.execute(
            """
            INSERT OR REPLACE INTO events
            (source, source_id, title, summary, url, start_at, end_at, area, venue_name, price_band, tags_json, kid_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "sendai_csv",
                source_id,
                title,
                summary,
                url,
                start,
                end_,  # ★追加
                "仙台市",
                venue,
                "free" if tags.get("free") else "unknown",
                json.dumps(tags, ensure_ascii=False),
                score,
            )
        )
        count += 1

    con.commit()
    print(f"Imported sendai events: {count}")

KAGAKUKAN_LIST_URL = "https://www.kagakukan.sendai-c.ed.jp/event/"

def import_kagakukan_events(con):
    links = set()

    # 最大10ページまで（空になったら途中で止める）
    for page in range(1, 11):
        if page == 1:
            url = KAGAKUKAN_LIST_URL
        else:
            # ★ WordPressの一般的なページング形式
            url = KAGAKUKAN_LIST_URL.rstrip("/") + f"/page/{page}/"

        print("Fetch list:", url)

        html_list = download_html(url)

        # デバッグ：最初だけ少し表示（多すぎると見づらいので）
        if page == 1:
            print(html_list[:800])

        # まずはこのページからイベント詳細URLを抽出
        abs_links = re.findall(
            r'https://www\.kagakukan\.sendai-c\.ed\.jp/event_/[\d]+/',
            html_list
        )

        rel_links = [
            "https://www.kagakukan.sendai-c.ed.jp" + p
            for p in re.findall(r'href="(/event_/[\d]+/)"', html_list)
        ]

        found = set(abs_links + rel_links)
        print("  found:", len(found))

        # ★ 空ページならここで終了
        if not found:
            break

        # ★ 既に集めたlinksに新規が無いなら終了（同じページを返す系対策）
        before = len(links)
        links.update(found)
        if len(links) == before:
            print("  no new links -> stop paging")
            break

    links = sorted(links)

    cur = con.cursor()
    cur.execute("DELETE FROM events WHERE source=?", ("kagakukan",))

    count = 0
    for url in links:
        try:
            detail_html = download_html(url)
            text = _strip_tags(detail_html)

            # title はHTMLから取る（今の方法でOK）
            m = re.search(r"<title>(.*?)</title>", detail_html, flags=re.I|re.S)
            title = (m.group(1) if m else "").strip()
            title = re.sub(r"\s+", " ", title)
            title = title.replace(
                "｜HOKUSHU仙台市科学館 -HOKUSHU  SENDAI CITY SCIENCE MUSEUM –", ""
            ).strip(" –-")

            ymds = _japanese_dates_to_ymd_list(text)
            print("DATE CHECK:", url, "->", ymds[:3])

            if not ymds:
                continue

            start_day = min(ymds)
            end_day = max(ymds)

            summary = text
            if len(summary) > 220:
                summary = summary[:220] + "…"

            tags = {}
            kid_score = 60
            combined = (title + " " + summary)

            if any(x in combined for x in ["小学生", "親子", "子ども", "体験", "工作"]):
                tags["elem"] = True
                kid_score = 80

            if any(x in combined for x in ["無料", "参加費 無料", "参加費無料"]):
                tags["free"] = True

            cur.execute(
                """
                INSERT OR REPLACE INTO events
                (source, source_id, title, summary, url, start_at, end_at, area, venue_name, price_band, tags_json, kid_score)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "kagakukan",
                    url,  # source_id
                    title or "仙台市科学館 イベント",
                    summary,
                    url,
                    start_day,
                    end_day,
                    "仙台市",
                    "仙台市科学館",
                    "free" if tags.get("free") else "unknown",
                    json.dumps(tags, ensure_ascii=False),
                    kid_score,
                )
            )
            count += 1

        except Exception as e:
            print("[kagakukan] skip:", url, "err=", repr(e))

    con.commit()
    print(f"Imported kagakukan events: {count}")

TOHOKU_SCIENCE_URL = "https://www.ip.eng.tohoku.ac.jp/campus/science/"

def import_tohoku_science_events(con):
    html_top = download_html(TOHOKU_SCIENCE_URL)

    links = sorted(set(
        re.findall(r'https://science-community\.jp/event/detail\.php\?event_id=\d+', html_top)
    ))

    print("Found tohoku science links:", len(links))

    cur = con.cursor()
    cur.execute("DELETE FROM events WHERE source=?", ("tohoku_science",))

    count = 0
    for url in links:
        try:
            detail_html = download_html(url)
            text = _strip_tags(detail_html)

            m = re.search(r"<title>(.*?)</title>", detail_html, flags=re.I | re.S)
            title = (m.group(1) if m else "").strip()
            title = re.sub(r"\s+", " ", title)

            ymds = _japanese_dates_to_ymd_list(text)
            print("TOHOKU DATE CHECK:", url, "->", ymds[:3])

            if not ymds:
                continue

            start_day = min(ymds)
            end_day = max(ymds)

            summary = text
            if len(summary) > 220:
                summary = summary[:220] + "…"

            tags = {}
            kid_score = 60
            combined = title + " " + summary

            if any(x in combined for x in ["小学生", "親子", "子ども", "体験", "工作", "科学", "実験"]):
                tags["elem"] = True
                kid_score = 80

            if "無料" in combined:
                tags["free"] = True

            cur.execute(
                """
                INSERT OR REPLACE INTO events
                (source, source_id, title, summary, url, start_at, end_at, area, venue_name, price_band, tags_json, kid_score)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "tohoku_science",
                    url,
                    title or "東北大学サイエンスキャンパス",
                    summary,
                    url,
                    start_day,
                    end_day,
                    "仙台市",
                    "東北大学サイエンスキャンパス",
                    "free" if tags.get("free") else "unknown",
                    json.dumps(tags, ensure_ascii=False),
                    kid_score,
                )
            )
            count += 1

        except Exception as e:
            print("[tohoku_science] skip:", url, "err=", repr(e))

    con.commit()
    print(f"Imported tohoku_science events: {count}")

SENDAI_ASTRO_ATOM_URL = "https://www.sendai-astro.jp/event/atom.xml"

def import_sendai_astro_events(con):
    xml_text = download_text(SENDAI_ASTRO_ATOM_URL)

    entries = re.findall(r"<entry>(.*?)</entry>", xml_text, flags=re.S)

    cur = con.cursor()
    cur.execute("DELETE FROM events WHERE source=?", ("sendai_astro",))

    count = 0

    for e in entries:

        # タイトル
        m = re.search(r"<title>(.*?)</title>", e, flags=re.S)
        title = m.group(1).strip() if m else "仙台市天文台イベント"

        # URL
        m = re.search(r'<link.*?href="(.*?)"', e)
        url = m.group(1) if m else ""

        # 本文HTML
        m = re.search(r"<content.*?>(.*?)</content>", e, flags=re.S)
        html = m.group(1) if m else ""

        text = _strip_tags(html)

        # ★ここが重要（本文から日本語日付を取得）
        ymds = _japanese_dates_to_ymd_list(text)

        if ymds:
            start_day = min(ymds)
            end_day = max(ymds)
        else:
            # fallback（記事公開日）
            m = re.search(r"<published>(.*?)</published>", e)
            start_day = m.group(1)[:10] if m else ""
            end_day = start_day

        summary = text[:220] + "…" if len(text) > 220 else text

        tags = {}
        kid_score = 60

        combined = title + " " + summary

        if any(x in combined for x in ["子ども", "親子", "小学生", "星", "宇宙", "観察"]):
            tags["kids"] = True
            kid_score = 80

        cur.execute(
            """
            INSERT OR REPLACE INTO events
            (source, source_id, title, summary, url, start_at, end_at, area, venue_name, price_band, tags_json, kid_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "sendai_astro",
                url,
                title,
                summary,
                url,
                start_day,
                end_day,
                "仙台市",
                "仙台市天文台",
                "unknown",
                json.dumps(tags, ensure_ascii=False),
                kid_score,
            )
        )

        count += 1

    con.commit()
    print(f"Imported sendai_astro events: {count}")

MIYAGI_LIBRARY_SCHEDULE_URL = "https://www.library.pref.miyagi.jp/events/schedule/index.html"
MIYAGI_LIBRARY_BASE = "https://www.library.pref.miyagi.jp"


class _HrefParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        for k, v in attrs:
            if k.lower() == "href" and v:
                self.hrefs.append(v)


def import_miyagi_library_events(con):
    html_list = download_html(MIYAGI_LIBRARY_SCHEDULE_URL)

    parser = _HrefParser()
    parser.feed(html_list)

    links = []
    for href in parser.hrefs:
        href = href.strip()

        # 絶対パス型
        if href.startswith("/events/schedule/") and href.endswith(".html"):
            # 2025 / 2026 だけ対象
            if "/events/schedule/2025/" in href or "/events/schedule/2026/" in href:
                links.append(MIYAGI_LIBRARY_BASE + href)

        # 相対パス型
        elif href.startswith("./") and href.endswith(".html"):
            full = "https://www.library.pref.miyagi.jp/events/schedule/" + href[2:]
            if "/events/schedule/2025/" in full or "/events/schedule/2026/" in full:
                links.append(full)

    links = sorted(set(links))

    print("Found miyagi_library links:", len(links))
    if links[:5]:
        print("Sample miyagi_library links:", links[:5])

    cur = con.cursor()
    cur.execute("DELETE FROM events WHERE source=?", ("miyagi_library",))

    count = 0
    for url in links:
        try:
            detail_html = download_html(url)
            text = _strip_tags(detail_html)

            m = re.search(r"<title>(.*?)</title>", detail_html, flags=re.I | re.S)
            title = (m.group(1) if m else "").strip()
            title = re.sub(r"\s+", " ", title)

            # 終了イベント除外
            if "終了しました" in title:
                continue

            # 日付抽出：西暦 + 和暦
            ymds = []
            ymds += _japanese_dates_to_ymd_list(text)
            ymds += _museum_dates_to_ymd_list(text)
            ymds = sorted(set(ymds))

            if not ymds:
                pass
                continue

            start_day = min(ymds)
            end_day = max(ymds)

            summary = text
            if len(summary) > 220:
                summary = summary[:220] + "…"

            tags = {}
            kid_score = 60
            combined = title + " " + summary

            if any(x in combined for x in ["子ども", "親子", "小学生", "おはなし", "工作", "展示", "わらべうた", "紙芝居"]):
                tags["kids"] = True
                kid_score = 80

            if "無料" in combined:
                tags["free"] = True

            cur.execute(
                """
                INSERT OR REPLACE INTO events
                (source, source_id, title, summary, url, start_at, end_at, area, venue_name, price_band, tags_json, kid_score)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "miyagi_library",
                    url,
                    title or "宮城県図書館イベント",
                    summary,
                    url,
                    start_day,
                    end_day,
                    "宮城県",
                    "宮城県図書館",
                    "free" if tags.get("free") else "unknown",
                    json.dumps(tags, ensure_ascii=False),
                    kid_score,
                )
            )
            count += 1

        except Exception as e:
            print("[miyagi_library] skip:", url, "err=", repr(e))

    con.commit()
    print(f"Imported miyagi_library events: {count}")

SENDAI_MUSEUM_EVENT_URL = "https://www.city.sendai.jp/museum/koza/event.html"

def import_sendai_museum_events(con):
    html_text = download_html(SENDAI_MUSEUM_EVENT_URL)
    text = _strip_tags(html_text)

    cur = con.cursor()
    cur.execute("DELETE FROM events WHERE source=?", ("sendai_museum",))

    blocks = []

    # 記事本文から、見出しっぽい単位でざっくり区切る
    candidates = re.split(r"(記念講演会|もしも博物館資料が人のように話したら？|ねこけし絵付け体験|変身タイム「.*?」)", text)

    if len(candidates) > 1:
        merged = []
        i = 1
        while i < len(candidates):
            title = candidates[i].strip()
            body = candidates[i + 1].strip() if i + 1 < len(candidates) else ""
            merged.append((title, body))
            i += 2
        blocks = merged

    count = 0

    for title, body in blocks:
        ymds = _museum_dates_to_ymd_list(body)
        if not ymds:
            continue

        start_day = min(ymds)
        end_day = max(ymds)

        summary = body[:220] + "…" if len(body) > 220 else body

        tags = {}
        kid_score = 60
        combined = title + " " + summary

        if any(x in combined for x in ["子ども", "親子", "工作", "体験", "お姫様", "変身", "猫"]):
            tags["kids"] = True
            kid_score = 80

        if "無料" in combined:
            tags["free"] = True

        source_id = f"{title}|{start_day}|{end_day}"

        cur.execute(
            """
            INSERT OR REPLACE INTO events
            (source, source_id, title, summary, url, start_at, end_at, area, venue_name, price_band, tags_json, kid_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "sendai_museum",
                source_id,
                title,
                summary,
                SENDAI_MUSEUM_EVENT_URL,
                start_day,
                end_day,
                "仙台市",
                "仙台市博物館",
                "free" if tags.get("free") else "unknown",
                json.dumps(tags, ensure_ascii=False),
                kid_score,
            )
        )
        count += 1

    con.commit()
    print(f"Imported sendai_museum events: {count}")

AEONMALL_NATORI_EVENT_URL = "https://natori-aeonmall.com/news/event/"
AEONMALL_NATORI_BASE_URL = "https://natori-aeonmall.com"

def _slash_dates_to_ymd_list(text: str):
    dates = []
    for y, m, d in re.findall(r"(\d{4})/(\d{1,2})/(\d{1,2})", text):
        dates.append(f"{int(y):04d}-{int(m):02d}-{int(d):02d}")
    return dates


def _extract_aeonmall_event_blocks(html_text: str):
    """
    一覧ページの本文から、イベントごとのテキスト塊をざっくり抽出する
    """
    text = _strip_tags(html_text)

    # 日付開始っぽい位置で分割
    chunks = re.split(r'(?=\d{4}/\d{1,2}/\d{1,2})', text)

    blocks = []
    for chunk in chunks:
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if len(chunk) < 20:
            continue
        if "開催" not in chunk:
            continue
        blocks.append(chunk)

    return blocks


def _extract_aeonmall_dates(text: str):
    """
    イオンモール名取の一覧本文に出る日付を YYYY-MM-DD の配列で返す
    例:
      2026/03/20
      2026/03/20〜2026/03/24
    """
    dates = []

    # 2026/03/20 形式
    for y, m, d in re.findall(r'(\d{4})/(\d{1,2})/(\d{1,2})', text):
        dates.append(f"{int(y):04d}-{int(m):02d}-{int(d):02d}")

    return sorted(set(dates))


def import_aeonmall_natori_events(con):
    html_list = download_html(AEONMALL_NATORI_EVENT_URL)

    # 一覧から詳細URLを拾う
    rel_links = re.findall(r'href=["\'](/event/[0-9a-f\-]+)["\']', html_list, flags=re.I)
    links = sorted(set(AEONMALL_NATORI_BASE_URL + p for p in rel_links))

    print("Found aeonmall_natori links:", len(links))

    # 一覧本文からイベントごとの塊を取る
    blocks = _extract_aeonmall_event_blocks(html_list)
    print("Found aeonmall_natori blocks:", len(blocks))

    cur = con.cursor()
    cur.execute("DELETE FROM events WHERE source=?", ("aeonmall_natori",))

    count = 0

    # 一覧の塊と詳細URLを順番対応でなるべく合わせる
    for i, url in enumerate(links):
        try:
            block = blocks[i] if i < len(blocks) else ""

            # 日付は一覧から取る
            ymds = _extract_aeonmall_dates(block)

            if not ymds:
                # block から取れない場合は詳細本文も試す
                detail_html = download_html(url)
                detail_text = _strip_tags(detail_html)
                ymds = _extract_aeonmall_dates(detail_text)

                if not ymds:
                    print("[aeonmall_natori] no date:", url)
                    continue
            else:
                detail_html = download_html(url)
                detail_text = _strip_tags(detail_html)

            start_day = min(ymds)
            end_day = max(ymds)

            # タイトルは詳細ページの <title> を優先
            m = re.search(r"<title>(.*?)</title>", detail_html, flags=re.I | re.S)
            title = (m.group(1) if m else "").strip()
            title = re.sub(r"\s+", " ", title)

            # 「終了しました」を除外
            if "終了しました" in title or "【終了しました】" in title:
                print("[miyagi_library] skip ended:", url)
                continue

            # サイト名除去
            title = title.replace("｜イオンモール名取", "").strip()
            title = title.replace("| イオンモール名取", "").strip()
            title = title.replace(" - イオンモール名取", "").strip()

            if not title:
                # 保険：一覧塊から仮タイトル
                lines = [x.strip() for x in re.split(r"\s+", block) if x.strip()]
                for line in lines:
                    if len(line) < 4:
                        continue
                    if any(bad in line for bad in [
                        "開催", "時間", "場所", "料金", "アクセス",
                        "イベント情報", "該当するイベントがありません"
                    ]):
                        continue
                    title = line
                    break

            if not title:
                title = "イオンモール名取イベント"

            summary = "イオンモール名取で開催されるイベントです。詳細は公式ページをご確認ください。"

            tags = {}
            kid_score = 60
            combined = title + " " + summary

            if any(x in combined for x in [
                "子ども", "親子", "小学生", "ワークショップ", "工作",
                "体験", "キャラクター", "ショー", "バルーン",
                "サイエンス", "撮影会", "キッズ"
            ]):
                tags["kids"] = True
                kid_score = 80

            if "無料" in combined:
                tags["free"] = True

            cur.execute(
                """
                INSERT OR REPLACE INTO events
                (source, source_id, title, summary, url, start_at, end_at, area, venue_name, price_band, tags_json, kid_score)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "aeonmall_natori",
                    url,
                    title,
                    summary,
                    url,
                    start_day,
                    end_day,
                    "名取市",
                    "イオンモール名取",
                    "free" if tags.get("free") else "unknown",
                    json.dumps(tags, ensure_ascii=False),
                    kid_score,
                )
            )
            count += 1

        except Exception as e:
            print("[aeonmall_natori] skip:", url, "err=", repr(e))

    con.commit()
    print(f"Imported aeonmall_natori events: {count}")

AEONMALL_KAMISUGI_NEWS_URL = "https://sendaikamisugi.aeonmall.com/news"
AEONMALL_KAMISUGI_BASE_URL = "https://sendaikamisugi.aeonmall.com"

def import_aeonmall_kamisugi_events(con):
    html_list = download_html(AEONMALL_KAMISUGI_NEWS_URL)

    # /news/detail/123 や /news/detail/123?t=event_news を拾う
    rel_links = re.findall(
        r'href=["\'](/news/detail/\d+\?t=event_news)["\']',
        html_list,
        flags=re.I
    )
    links = sorted(set(AEONMALL_KAMISUGI_BASE_URL + p for p in rel_links))
    links = [u for u in links if "?t=event_news" in u]

    print("Found aeonmall_kamisugi event links:", len(links))

    cur = con.cursor()
    cur.execute("DELETE FROM events WHERE source=?", ("aeonmall_kamisugi",))

    count = 0

    for url in links:
        try:
            detail_html = download_html(url)
            detail_text = _strip_tags(detail_html)

            # タイトル
            m = re.search(r"<title>(.*?)</title>", detail_html, flags=re.I | re.S)
            title = (m.group(1) if m else "").strip()
            title = re.sub(r"\s+", " ", title)
            title = title.replace("イオンモール仙台上杉公式ホームページ | NEWS |", "").strip()

            # サイト名除去
            title = title.replace("｜イオンモール仙台上杉", "").strip()
            title = title.replace("| イオンモール仙台上杉", "").strip()
            title = title.replace(" - イオンモール仙台上杉", "").strip()
            title = re.sub(r"\s+", " ", title).strip()

            if not title:
                continue

            # 日付候補
            ymds = []
            ymds += _extract_aeonmall_dates(detail_text)      # 2026/03/20 形式
            ymds += _japanese_dates_to_ymd_list(detail_text) # 2026年3月20日 形式
            ymds = sorted(set(ymds))

            if not ymds:
                print("[aeonmall_kamisugi] no date:", url)
                continue

            start_day = min(ymds)
            end_day = max(ymds)

            # summary
            summary = re.sub(r"\s+", " ", detail_text).strip()
            if title and summary.startswith(title):
                summary = summary[len(title):].strip()

            for noise in [
                "イオンモール仙台上杉",
                "営業時間",
                "アクセス",
                "フロアガイド",
                "ショップニュース",
                "ニュース一覧",
                "請求時5%OFF", 
                "お客さま感謝デー", 
                "新規入会", 
                "専門店限定"
            ]:
                summary = summary.replace(noise, "")

            summary = re.sub(r"\s+", " ", summary).strip()
            if len(summary) > 180:
                summary = summary[:180] + "…"

            if not summary:
                summary = "イオンモール仙台上杉で開催されるイベントです。詳細は公式ページをご確認ください。"

            # 販促系ニュースをざっくり除外
            ng_words = [
                "請求時", "5%OFF", "セール", "キャンペーン", "入会",
                "ノベルティ", "新商品", "期間限定ショップ"
            ]
            if any(x in title for x in ng_words):
                print("[aeonmall_kamisugi] skip non-event:", title)
                continue

            tags = {}
            kid_score = 60
            combined = title + " " + summary

            if any(x in combined for x in [
                "子ども", "親子", "小学生", "ワークショップ", "工作",
                "体験", "キャラクター", "ショー", "撮影会",
                "キッズ", "イベント", "茶道", "無料"
            ]):
                tags["kids"] = True
                kid_score = 80

            if "無料" in combined:
                tags["free"] = True

            cur.execute(
                """
                INSERT OR REPLACE INTO events
                (source, source_id, title, summary, url, start_at, end_at, area, venue_name, price_band, tags_json, kid_score)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "aeonmall_kamisugi",
                    url,
                    title,
                    summary,
                    url,
                    start_day,
                    end_day,
                    "仙台市",
                    "イオンモール仙台上杉",
                    "free" if tags.get("free") else "unknown",
                    json.dumps(tags, ensure_ascii=False),
                    kid_score,
                )
            )
            count += 1

        except Exception as e:
            print("[aeonmall_kamisugi] skip:", url, "err=", repr(e))

    con.commit()
    print(f"Imported aeonmall_kamisugi events: {count}")

MITSUI_OUTLET_SENDAI_EVENT_URL = "https://mitsui-shopping-park.com/mop/sendai/event/"
MITSUI_OUTLET_SENDAI_BASE_URL = "https://mitsui-shopping-park.com"

def import_mitsui_outlet_sendai_events(con):
    html_list = download_html(MITSUI_OUTLET_SENDAI_EVENT_URL)

    rel_links = re.findall(r'href=["\'](/mop/sendai/event/\d+\.html)["\']', html_list, flags=re.I)
    links = sorted(set(MITSUI_OUTLET_SENDAI_BASE_URL + p for p in rel_links))

    print("Found mitsui_outlet_sendai links:", len(links))

    cur = con.cursor()
    cur.execute("DELETE FROM events WHERE source=?", ("mitsui_outlet_sendai",))

    count = 0
    for url in links:
        try:
            detail_html = download_html(url)
            text = _strip_tags(detail_html)

            # タイトル
            m = re.search(r"<title>(.*?)</title>", detail_html, flags=re.I | re.S)
            title = (m.group(1) if m else "").strip()
            title = re.sub(r"\s+", " ", title)

            # サイト名を削る
            title = title.replace(" | 三井アウトレットパーク 仙台港", "").strip()
            title = title.replace("｜三井アウトレットパーク 仙台港", "").strip()
            title = title.replace(" | 三井アウトレットパーク", "").strip()

            # 日付候補を集める
            ymds = []
            ymds += _japanese_dates_to_ymd_list(text)
            ymds += _slash_dates_to_ymd_list(text)
            try:
                ymds += _museum_dates_to_ymd_list(text)
            except Exception:
                pass

            ymds = sorted(set(ymds))
            if not ymds:
                print("[mitsui_outlet_sendai] no date:", url)
                continue

            start_day = min(ymds)
            end_day = max(ymds)

            # summary は本文から
            summary = re.sub(r"\s+", " ", text).strip()
            if title and summary.startswith(title):
                summary = summary[len(title):].strip()

            # ノイズ軽減
            for noise in [
                "三井アウトレットパーク 仙台港",
                "営業時間",
                "アクセス",
                "フロアガイド",
                "ショップ検索",
            ]:
                summary = summary.replace(noise, "")

            summary = re.sub(r"\s+", " ", summary).strip()
            if len(summary) > 180:
                summary = summary[:180] + "…"

            if not summary:
                summary = "三井アウトレットパーク仙台港で開催されるイベントです。詳細は公式ページをご確認ください。"

            tags = {}
            kid_score = 60
            combined = title + " " + summary

            if any(x in combined for x in [
                "子ども", "親子", "小学生", "ワークショップ", "工作",
                "体験", "キャラクター", "ショー", "撮影会",
                "キッズ", "ふわふわ", "イベント"
            ]):
                tags["kids"] = True
                kid_score = 80

            if "無料" in combined:
                tags["free"] = True

            cur.execute(
                """
                INSERT OR REPLACE INTO events
                (source, source_id, title, summary, url, start_at, end_at, area, venue_name, price_band, tags_json, kid_score)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "mitsui_outlet_sendai",
                    url,
                    title or "三井アウトレットパーク仙台港イベント",
                    summary,
                    url,
                    start_day,
                    end_day,
                    "仙台市",
                    "三井アウトレットパーク仙台港",
                    "free" if tags.get("free") else "unknown",
                    json.dumps(tags, ensure_ascii=False),
                    kid_score,
                )
            )
            count += 1

        except Exception as e:
            print("[mitsui_outlet_sendai] skip:", url, "err=", repr(e))

    con.commit()
    print(f"Imported mitsui_outlet_sendai events: {count}")

# ===== 仙台泉プレミアムアウトレット =====

SENDai_IZUMI_OUTLET_URL = "https://www.premiumoutlets.co.jp/sendaiizumi/events/"
SENDai_IZUMI_OUTLET_BASE = "https://www.premiumoutlets.co.jp"

def import_sendai_izumi_outlet_events(con):

    html_list = download_html(SENDai_IZUMI_OUTLET_URL)

    # hrefから拾う
    rel_links = re.findall(
        r'href=["\'](/sendaiizumi/events/news\d+\.html)["\']',
        html_list,
        flags=re.I
    )

    # hrefに出ていない場合の保険
    raw_links = re.findall(
        r'/sendaiizumi/events/news\d+\.html',
        html_list,
        flags=re.I
    )

    all_rel = sorted(set(rel_links + raw_links))
    links = sorted(set(SENDai_IZUMI_OUTLET_BASE + p for p in all_rel))

    print("Found izumi_outlet links:", len(links))

    if not links:
        print("DEBUG izumi_outlet html head:")
        print(html_list[:2000])

    cur = con.cursor()
    cur.execute("DELETE FROM events WHERE source=?", ("izumi_outlet",))

    count = 0

    for url in links:
        try:
            detail_html = download_html(url)
            text = _strip_tags(detail_html)

            m = re.search(r"<title>(.*?)</title>", detail_html, flags=re.I | re.S)
            title = (m.group(1) if m else "").strip()
            title = re.sub(r"\s+", " ", title)

            title = title.replace(" | 仙台泉プレミアム・アウトレット", "")
            title = title.replace("｜仙台泉プレミアム・アウトレット", "")
            title = title.replace(" - 最新情報", "")
            title = title.strip()

            ymds = []
            ymds += _japanese_dates_to_ymd_list(text)
            ymds += _slash_dates_to_ymd_list(text)
            ymds = sorted(set(ymds))

            if not ymds:
                print("[izumi_outlet] no date:", url)
                continue

            start_day = min(ymds)
            end_day = max(ymds)

            summary = re.sub(r"\s+", " ", text).strip()
            if title and summary.startswith(title):
                summary = summary[len(title):].strip()

            for noise in [
                "NEWS一覧を見る",
                "イベントカレンダーを見る",
                "プレミアム・ アウトレット ニュース",
                "ショップ ニュース",
                "期間限定 ショップ",
                "SENDAI-IZUMI",
                "PREMIUM OUTLETS®",
            ]:
                summary = summary.replace(noise, "")

            summary = re.sub(r"\s+", " ", summary).strip()
            if len(summary) > 180:
                summary = summary[:180] + "…"

            if not summary:
                summary = "仙台泉プレミアムアウトレットで開催されるイベントです。詳細は公式ページをご確認ください。"

            tags = {}
            kid_score = 60
            combined = title + " " + summary

            if any(x in combined for x in [
                "子ども", "親子", "小学生", "キッズ", "ワークショップ",
                "工作", "体験", "撮影会", "イベント", "バスツアー"
            ]):
                tags["kids"] = True
                kid_score = 80

            if "無料" in combined:
                tags["free"] = True

            cur.execute(
                """
                INSERT OR REPLACE INTO events
                (source, source_id, title, summary, url, start_at, end_at, area, venue_name, price_band, tags_json, kid_score)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "izumi_outlet",
                    url,
                    title or "仙台泉プレミアムアウトレットイベント",
                    summary,
                    url,
                    start_day,
                    end_day,
                    "仙台市泉区",
                    "仙台泉プレミアムアウトレット",
                    "free" if tags.get("free") else "unknown",
                    json.dumps(tags, ensure_ascii=False),
                    kid_score,
                )
            )

            count += 1

        except Exception as e:
            print("[izumi_outlet] skip:", url, "err=", repr(e))

    con.commit()
    print(f"Imported izumi_outlet events: {count}")



# ===== HTML =====
from datetime import datetime

def html(title: str, body: str, *, description: str = "", path: str = "index.html", og_image: str = "ogp.png") -> str:
    """
    title: ページタイトル
    body:  <body>内HTML
    description: OGP説明文
    path: そのページのパス（index.html / weekend.html）
    og_image: OGP画像ファイル（site/ 配下に置く想定）
    """
    site_url = (SITE_URL or "").rstrip("/")
    page_url = f"{site_url}/{path.lstrip('/')}" if site_url else ""
    og_img_url = f"{site_url}/{og_image.lstrip('/')}" if site_url else ""

    depth = path.count("/")
    asset_prefix = "../" * depth

    # description が空なら title を流用
    desc = description.strip() or title.strip()

    head_ogp = ""
    if site_url:
        head_ogp = f"""
<meta property="og:type" content="website">
<meta property="og:site_name" content="miyagi-kids">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:url" content="{escape(page_url)}">
<meta property="og:image" content="{escape(og_img_url)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{escape(title)}">
<meta name="twitter:description" content="{escape(desc)}">
<meta name="twitter:image" content="{escape(og_img_url)}">
<link rel="canonical" href="{escape(page_url)}">
""".strip()

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<link rel="stylesheet" href="{asset_prefix}style.css">
{head_ogp}
</head>
<body>
<header class="topbar"><h1 class="logo">仙台・宮城の子どもイベント</h1></header>
<main class="container">
{body}
</main>
<footer class="footer">© miyagi-kids</footer>
</body>
</html>
"""

def _is_weekend(start_at: str) -> bool:
    # start_at: "YYYY-MM-DD..." を想定（T区切りでもOK）
    if not start_at:
        return False
    s = start_at.strip().replace("T", " ")
    try:
        d = datetime.fromisoformat(s[:19] if len(s) >= 19 else s[:10] + " 00:00:00")
        return d.weekday() in (5, 6)  # 土日
    except:
        return False

def build_site(con):
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "style.css").write_text(CSS, encoding="utf-8")

    today = dt.date.today().isoformat()
    updated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    # 列取得
    sql = "SELECT title, summary, start_at, end_at, venue_name, tags_json, kid_score, url FROM events"
    rows = con.execute(sql).fetchall()

    # ==============================
    # ★ 個別イベントページ生成
    # ==============================
    for t, s, start_day, end_day, venue, tags_json, kid_score, url in rows:

        slug = re.sub(r'[^a-zA-Z0-9]', '-', t)[:50]

        detail_body = f"""
    <h1>{escape(t)}</h1>
    <p>{escape(start_day)}〜{escape(end_day)}</p>
    <p>{escape(venue or "")}</p>
    <p>{escape(s or "")}</p>
    <p><a href="{escape(url)}" target="_blank">公式サイト</a></p>
    <p><a href="../index.html">←一覧に戻る</a></p>
    """

        detail_path = SITE_DIR / "events" / f"{slug}.html"
        detail_path.parent.mkdir(parents=True, exist_ok=True)

        detail_path.write_text(
            html(
                f"{t}｜仙台の子どもイベント",
                detail_body,
                description=(s or "")[:120],
                path=f"events/{slug}.html",
            ),
            encoding="utf-8"
        )

    future, past = [], []

    # item = (t, s, start_day, end_day, venue, tags_json, kid_score, url)
    for t, s, start_at, end_at, venue, tags_json, kid_score, url in rows:
        start_day = (start_at or "")[:10]
        if start_day.count("-") != 2:
            continue

        end_day = (end_at or "")[:10]
        if end_day.count("-") != 2:
            end_day = start_day

        # kid_score が None の時に備える
        if kid_score is None:
            kid_score = 0

        item = (t, s, start_day, end_day, venue, tags_json, kid_score, url)

        # ★ 開催中も未来扱い（終了日が今日以降）
        if end_day >= today:
            future.append(item)
        else:
            past.append(item)

    show = future[:200] if future else past[-200:]

    # ===== 今週末の土日を計算 =====
    today_date = dt.date.today()
    dow = today_date.weekday()  # 0=月,5=土,6=日
    days_until_sat = (5 - dow) % 7
    sat = today_date + dt.timedelta(days=days_until_sat)
    sun = sat + dt.timedelta(days=1)

    sat_str = sat.isoformat()
    sun_str = sun.isoformat()

    # show の中から「今週末に重なる」ものだけ
    weekend_items = [
        item for item in show
        if item[2] <= sun_str and item[3] >= sat_str
    ]

    # 今週末の無料件数
    weekend_free_count = 0
    for item in weekend_items:
        tags_json = item[5]
        try:
            tags = json.loads(tags_json or "{}")
            if tags.get("free"):
                weekend_free_count += 1
        except Exception:
            pass

    body = f"<p class='meta'>更新: {updated}</p>"
    body += "<p>仙台・宮城で開催される子ども向けイベントをまとめています。親子で楽しめる今週末のお出かけ、図書館イベント、科学館イベント、無料イベントを探せます。</p>"
    body += '<p><a href="weekend.html">▶ 今週末まとめページを見る</a></p>'

    # --- 検索バー + ボタン ---
    body += """
<div class="searchbar">
  <input id="searchBox" type="search"
         placeholder="キーワード検索（例：無料 / 工作 / 親子）"
         aria-label="キーワード検索">
  <div class="chips">
    <button id="btnWeekend" class="chip" type="button">今週末</button>
    <button id="btnFree" class="chip" type="button">無料</button>
  </div>
  <div class="resultcount"><span id="countShown">0</span>/<span id="countAll">0</span>件</div>
</div>
"""

    def ymd_with_wday(ymd: str) -> str:
        try:
            y, m, d = ymd.split("-")
            dtobj = dt.date(int(y), int(m), int(d))
            w = "月火水木金土日"[dtobj.weekday()]
            return f"{ymd}（{w}）"
        except Exception:
            return ymd

    body += "<h2>これからのイベント</h2>" if future else "<h2>直近のイベント（過去）</h2>"

    # ===== index.html のカード描画 =====
    for t, s, start_day, end_day, venue, tags_json, kid_score, url in show:
        desc = (s or "").replace("\n", " ").replace("\r", " ").strip()
        if len(desc) > 140:
            desc = desc[:140] + "…"

        title_html = escape(t)
        if url:
            title_html = f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">{escape(t)}</a>'

        # free判定
        is_free = 0
        try:
            tags = json.loads(tags_json or "{}")
            is_free = 1 if tags.get("free") else 0
        except Exception:
            is_free = 0

        badges_html = ""
        if is_free:
            badges_html = '<div class="badges"><span class="badge badge-free">無料</span></div>'

        search_text = f"{t} {desc} {venue or ''} {start_day} {end_day}"

        # 曜日・連日表示
        start_label = ymd_with_wday(start_day)
        if end_day and end_day != start_day:
            end_label = ymd_with_wday(end_day)
            date_label = f"{start_label}〜{end_label}"
        else:
            date_label = start_label

        body += f"""
<div class="card"
     data-search="{escape(search_text)}"
     data-date="{escape(start_day)}"
     data-end="{escape(end_day)}"
     data-free="{is_free}">
  <div class="cardhead">
    <h3>{title_html}</h3>
    {badges_html}
  </div>
  <div class="meta">{escape(date_label)} / {escape(venue or "")}</div>
  <div>{escape(desc)}</div>
</div>
"""

    # --- index の JS（検索 + 今週末 + 無料） ---
    body += """
<script>
(() => {
  const input = document.getElementById("searchBox");
  const btnWeekend = document.getElementById("btnWeekend");
  const btnFree = document.getElementById("btnFree");
  const cards = Array.from(document.querySelectorAll(".card"));
  const countShown = document.getElementById("countShown");
  const countAll = document.getElementById("countAll");

  let weekendMode = false;
  let freeMode = false;

  function toYMD(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function getNextWeekendRange() {
    const now = new Date();
    const dow = now.getDay();
    const daysUntilSat = (6 - dow + 7) % 7;
    const sat = new Date(now);
    sat.setHours(0,0,0,0);
    sat.setDate(sat.getDate() + daysUntilSat);
    const sun = new Date(sat);
    sun.setDate(sun.getDate() + 1);
    return [toYMD(sat), toYMD(sun)];
  }

  function update() {
    const raw = (input.value || "").trim().toLowerCase();
    const terms = raw.replace(/\\u3000/g," ").split(/\\s+/).filter(Boolean);

    const [satYMD, sunYMD] = getNextWeekendRange();

    let shown = 0;

    for (const card of cards) {
      const text = (card.dataset.search || "").toLowerCase();
      const start = card.dataset.date || "";
      const end = card.dataset.end || start;
      const isFree = card.dataset.free === "1";

      const okText = terms.length === 0 || terms.every(t => text.includes(t));
      const okWeekend = !weekendMode || (start <= sunYMD && end >= satYMD);
      const okFree = !freeMode || isFree;

      const ok = okText && okWeekend && okFree;

      card.style.display = ok ? "" : "none";
      if (ok) shown++;
    }

    countShown.textContent = shown;
    countAll.textContent = cards.length;
  }

  btnWeekend.addEventListener("click", () => {
    weekendMode = !weekendMode;
    btnWeekend.classList.toggle("active", weekendMode);
    update();
  });

  btnFree.addEventListener("click", () => {
    freeMode = !freeMode;
    btnFree.classList.toggle("active", freeMode);
    update();
  });

  input.addEventListener("input", update);
  update();
})();
</script>
"""

    (SITE_DIR / "index.html").write_text(
        html(
            "仙台の子どもイベントまとめ｜今週末・親子で楽しめるお出かけ情報",
            body,
            description="仙台・宮城の子ども向けイベントをまとめたサイトです。今週末の親子イベント、図書館、科学館、体験イベント、無料イベントを検索できます。",
            path="index.html",
        ),
        encoding="utf-8"
    )

    # sitemap.xml を生成
    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://ndagsudo.github.io/miyagi-kids/</loc>
      </url>
      <url>
        <loc>https://ndagsudo.github.io/miyagi-kids/weekend.html</loc>
      </url>
    </urlset>
    """

    (SITE_DIR / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    # ===== 今週末ページ生成（おすすめ3選つき） =====
    weekend_title = f"今週末（{sat_str}〜{sun_str}）のイベント"

    # おすすめ上位3件（kid_score降順、同点はタイトルで安定化）
    weekend_sorted = sorted(
        weekend_items,
        key=lambda it: ((it[6] if it[6] is not None else 0), (it[0] or "")),
        reverse=True
    )
    weekend_top = weekend_sorted[:3]

    weekend_body = f"""
<h1>{escape(weekend_title)}</h1>
<p class="meta">更新: {escape(updated)} / 件数: {len(weekend_items)}件（無料: {weekend_free_count}件）</p>
<p>仙台市周辺の子ども向けイベントを、今週末に重なるものだけまとめました。気になるものはタイトルから公式ページへ。</p>
<hr>
"""

    # --- おすすめ3選 ---
    weekend_body += "<h2>おすすめ3選</h2>"

    if weekend_top:
        for t, s, start_day, end_day, venue, tags_json, kid_score, url in weekend_top:
            desc = (s or "").replace("\n", " ").replace("\r", " ").strip()
            if len(desc) > 120:
                desc = desc[:120] + "…"

            slug = re.sub(r'[^a-zA-Z0-9]', '-', t)[:50]

            title_html = f'<a href="events/{slug}.html">{escape(t)}</a>'

            start_label = ymd_with_wday(start_day)
            if end_day and end_day != start_day:
                end_label = ymd_with_wday(end_day)
                date_label = f"{start_label}〜{end_label}"
            else:
                date_label = start_label

            # 無料バッジ（weekend側にも表示）
            is_free_badge = ""
            try:
                tags = json.loads(tags_json or "{}")
                if tags.get("free"):
                    is_free_badge = '<span class="badge badge-free">無料</span>'
            except Exception:
                pass

            weekend_body += f"""
<div class="card">
  <div class="cardhead">
    <h3>⭐ {title_html}</h3>
    <div class="badges">{is_free_badge}</div>
  </div>
  <div class="meta">{escape(date_label)} / {escape(venue or "")} / おすすめ度: {kid_score}</div>
  <div>{escape(desc)}</div>
</div>
"""
    else:
        weekend_body += "<p>今週末に該当するイベントがありませんでした。</p>"

    weekend_body += "<hr><h2>一覧</h2>"

    # --- 一覧（全件） ---
    for t, s, start_day, end_day, venue, tags_json, kid_score, url in weekend_items:
        desc = (s or "").replace("\n", " ").replace("\r", " ").strip()
        if len(desc) > 140:
            desc = desc[:140] + "…"

        title_html = escape(t)
        if url:
            title_html = f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">{escape(t)}</a>'

        start_label = ymd_with_wday(start_day)
        if end_day and end_day != start_day:
            end_label = ymd_with_wday(end_day)
            date_label = f"{start_label}〜{end_label}"
        else:
            date_label = start_label

        weekend_body += f"""
<div class="card">
  <h3>{title_html}</h3>
  <div class="meta">{escape(date_label)} / {escape(venue or "")}</div>
  <div>{escape(desc)}</div>
</div>
"""

    (SITE_DIR / "weekend.html").write_text(
        html(
            "今週末の仙台 子どもイベント｜親子で行けるおすすめお出かけ情報",
            weekend_body,
            description=f"今週末（{sat_str}〜{sun_str}）に仙台・宮城で開催される子ども向けイベントをまとめました。親子で楽しめる体験イベント、図書館、科学館、無料イベントを掲載。",
            path="weekend.html",
            og_image="ogp-g4.png",
        ),
        encoding="utf-8"
    )

def main():
    con = connect_db()
    import_sendai_events(con)
    import_kagakukan_events(con)
    import_tohoku_science_events(con)
    import_sendai_astro_events(con)
    import_sendai_museum_events(con)
    import_miyagi_library_events(con)
    import_aeonmall_kamisugi_events(con)
    # import_aeonmall_natori_events(con)   # ←一旦保留でもOK
    import_mitsui_outlet_sendai_events(con)
    # import_sendai_izumi_outlet_events(con)   # ←ここを一旦止める
    build_site(con)
    con.close()


if __name__ == "__main__":
    main()
