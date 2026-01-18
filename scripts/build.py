import sqlite3
import csv
import urllib.request
import json
import datetime as dt
from datetime import datetime, date
from pathlib import Path
from html import escape

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

footer {
  text-align: center;
  font-size: 12px;
  color: #888;
  padding: 16px;
}
"""

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
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "style.css").write_text(CSS, encoding="utf-8")

    today = dt.date.today().isoformat()
    updated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    # events列名を取得（URL列を自動検出する）
    cols = [r[1] for r in con.execute("PRAGMA table_info(events)").fetchall()]

    # URL列候補を優先順位で探す
    url_candidates = [
        "detailedUrl", "detailUrl",
        "detailed_url", "detail_url",
        "url", "event_url", "link", "source_url"
    ]
    url_col = next((c for c in url_candidates if c in cols), None)

    # SELECT文を組み立て（URL列が無ければ空文字を入れる）
    if url_col:
        sql = f"SELECT title, summary, start_at, venue_name, {url_col} FROM events"
    else:
        sql = "SELECT title, summary, start_at, venue_name, '' as url FROM events"

    rows = con.execute(sql).fetchall()

    future, past = [], []

    for t, s, start_at, venue, url in rows:
        start_day = (start_at or "")[:10]
        if start_day.count("-") != 2:
            continue

        item = (t, s, start_day, venue, url)

        if start_day >= today:
            future.append(item)
        else:
            past.append(item)

    show = future if future else past[-20:]

    body = f"<p class='meta'>更新: {updated}</p>"
    body += "<h2>これからのイベント</h2>" if future else "<h2>直近のイベント（過去）</h2>"

    for t, s, start_day, venue, url in show:
        desc = (s or "").replace("\n", " ").replace("\r", " ").strip()
        if len(desc) > 140:
            desc = desc[:140] + "…"

        title_html = escape(t)
        if url:
            title_html = f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">{escape(t)}</a>'

        body += f"""
<div class="card">
  <h3>{title_html}</h3>
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
