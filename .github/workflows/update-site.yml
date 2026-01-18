import sqlite3
import csv
import urllib.request
import json
import datetime as dt
from datetime import datetime, date
from pathlib import Path
from html import escape

print("RUNNING:", __file__)

# ===== 設定 =====
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"
DB_PATH = DATA_DIR / "data.db"

# ★ あなたのCSV直リンク
SENDAI_EVENTS_CSV_URL = "https://data.city.sendai.jp/datastore/dump/2314f2dc-da9e-4800-aae9-355a67649968?bom=True"

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
  area TEXT,
  venue_name TEXT,
  price_band TEXT,
  tags_json TEXT,
  kid_score INTEGER
);
"""

def connect_db():
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
        except:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")

    if "<html" in text.lower():
        raise RuntimeError("CSVではなくHTMLを取得しています")

    return list(csv.DictReader(text.splitlines()))

# ===== 取り込み =====
def import_sendai_events(con):
    rows = download_csv(SENDAI_EVENTS_CSV_URL)
    print("CSV columns:", rows[0].keys())

    cur = con.cursor()
    cur.execute("DELETE FROM events")

    count = 0
    for r in rows:
        title = (r.get("name") or "").strip()
        if not title:
            continue

        summary = r.get("summary") or ""
        start = r.get("startDate") or ""
        venue = r.get("locationName") or ""
        url = r.get("detailedUrl") or ""
        source_id = r.get("entity_id") or r.get("_id") or title + start

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
            INSERT INTO events
            (source, source_id, title, summary, url, start_at, area, venue_name, price_band, tags_json, kid_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "sendai_csv",
                source_id,
                title,
                summary,
                url,
                start,
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

# ===== HTML =====
from datetime import datetime

def html(title, body):
    v = datetime.now().strftime("%Y%m%d%H%M")  # 毎回変わる

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<link rel="stylesheet" href="style.css?v={v}">
</head>
<body>
<header><h1>宮城の子どもイベント</h1></header>
<div class="container">
{body}
</div>
<footer>© miyagi-kids</footer>
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

    print("ENTER build_site")

    CSS = """
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Hiragino Kaku Gothic ProN","Meiryo",sans-serif;
         background:#f7f7f7;margin:0;color:#333}
    header{background:#4CAF50;color:#fff;padding:16px}
    header h1{margin:0;font-size:22px}
    .container{max-width:900px;margin:0 auto;padding:16px}
    nav{margin:12px 0}
    nav a{margin-right:12px;text-decoration:none;color:#2e7d32;font-weight:600}
    .card{background:#fff;border-radius:10px;padding:14px;margin:12px 0;
          box-shadow:0 2px 6px rgba(0,0,0,.06)}
    .card h3{margin:0 0 6px;font-size:18px}
    .meta{font-size:13px;color:#666;margin-bottom:8px}
    .badge{display:inline-block;padding:2px 8px;margin-right:6px;border-radius:12px;font-size:12px;background:#e0e0e0}
    .badge.free{background:#ffeb3b}
    footer{text-align:center;font-size:12px;color:#888;padding:16px}
    """

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "style.css").write_text(CSS, encoding="utf-8")

    SITE_DIR.mkdir(exist_ok=True)

    rows = con.execute(
        "SELECT title, summary, start_at, venue_name FROM events"
    ).fetchall()

    events = []
    body = ""

import datetime as dt

def build_site(con):
    # site/ を必ず作る
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    today = dt.date.today().isoformat()
    updated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    # DBから取る（あなたの sample に合わせている）
    rows = con.execute(
        "SELECT title, summary, start_at, venue_name FROM events"
    ).fetchall()

    future = []
    past = []

    for t, s, start_at, venue in rows:
        start_day = (start_at or "")[:10]  # 'YYYY-MM-DD'
        if start_day.count("-") != 2:
            continue

        if start_day >= today:
            future.append((t, s, start_day, venue))
        else:
            past.append((t, s, start_day, venue))

    show = future if future else past[-20:]

    body = f"<p class='meta'>更新: {updated}</p>"

    if future:
        body += "<h2>これからのイベント</h2>"
    else:
        body += "<h2>直近のイベント（過去）</h2>"

    # ★ ここが 0 ならカードが出ない。確認用に一時的に残す
    body += f"<p class='meta'>表示件数: {len(show)}</p>"

    for t, s, start_day, venue in show:
        desc = (s or "").replace("\n", " ").replace("\r", " ").strip()
        if len(desc) > 140:
            desc = desc[:140] + "…"

        body += f"""
<div class="card">
  <h3>{escape(t)}</h3>
  <div class="meta">{escape(start_day)} / {escape(venue or "")}</div>
  <div>{escape(desc)}</div>
</div>
"""

    (SITE_DIR / "index.html").write_text(
        html("宮城の子どもイベント", body),
        encoding="utf-8"
    )

def main():
    con = connect_db()
    import_sendai_events(con)
    build_site(con)
    con.close()

if __name__ == "__main__":
    main()
