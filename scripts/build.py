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
        end_ = r.get("endDate") or ""          # ★追加
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
<link rel="stylesheet" href="style.css">
{head_ogp}
</head>
<body>
<header class="topbar"><h1 class="logo">宮城の子どもイベント</h1></header>
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


from PIL import Image, ImageDraw, ImageFont

def generate_weekend_ogp(sat_str: str, sun_str: str, out_path: Path) -> None:
    """
    週末日付入りのOGP画像（1200x630 png）を生成して out_path に保存
    """
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), (245, 247, 250))  # 薄いグレー
    draw = ImageDraw.Draw(img)

    # 角丸のカード風背景
    pad = 60
    card = (pad, pad, W - pad, H - pad)
    draw.rounded_rectangle(card, radius=36, fill=(255, 255, 255), outline=(225, 230, 236), width=3)

    # Windowsの日本語フォント（環境によってある/ないがあるのでフォールバック）
    font_paths = [
        r"C:\Windows\Fonts\YuGothM.ttc",  # 游ゴシック
        r"C:\Windows\Fonts\meiryo.ttc",   # メイリオ
        r"C:\Windows\Fonts\msgothic.ttc", # MS ゴシック
    ]

    def load_font(size: int):
        for fp in font_paths:
            try:
                return ImageFont.truetype(fp, size=size)
            except Exception:
                pass
        return ImageFont.load_default()

    font_title = load_font(64)
    font_sub = load_font(40)
    font_small = load_font(30)

    # テキスト内容
    title = "今週末の子どもイベント"
    date_line = f"{sat_str} 〜 {sun_str}"
    brand = "miyagi-kids"

    # 配置
    left = pad + 70
    top = pad + 90

    draw.text((left, top), title, fill=(24, 32, 44), font=font_title)
    draw.text((left, top + 90), date_line, fill=(50, 60, 74), font=font_sub)

    # 下部に説明（小さめ）
    draw.text((left, H - pad - 120), "おすすめ3選・無料もチェックできます", fill=(70, 80, 96), font=font_small)

    # 右下にブランド
    draw.text((W - pad - 260, H - pad - 90), brand, fill=(24, 32, 44), font=font_small)

    # 保存
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG", optimize=True)


def build_site(con):
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "style.css").write_text(CSS, encoding="utf-8")

    today = dt.date.today().isoformat()
    updated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    # 列取得
    cols = [r[1] for r in con.execute("PRAGMA table_info(events)").fetchall()]

    url_candidates = [
        "detailedUrl", "detailUrl",
        "detailed_url", "detail_url",
        "url", "event_url", "link", "source_url"
    ]
    url_col = next((c for c in url_candidates if c in cols), None)

    # SELECT（tags_json + kid_score も取得）
    if url_col:
        sql = f"SELECT title, summary, start_at, end_at, venue_name, tags_json, kid_score, {url_col} FROM events"
    else:
        sql = "SELECT title, summary, start_at, end_at, venue_name, tags_json, kid_score, '' as url FROM events"

    rows = con.execute(sql).fetchall()

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

    generate_weekend_ogp(sat_str, sun_str, SITE_DIR / "ogp-weekend.png")

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
            "宮城の子どもイベント",
            body,
            description="宮城（仙台周辺）の子ども向けイベントを検索・絞り込み（今週末/無料）できます。",
            path="index.html",
        ),
        encoding="utf-8"
    )


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

            title_html = escape(t)
            if url:
                title_html = f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">{escape(t)}</a>'

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
            "今週末のイベント | miyagi-kids",
            weekend_body,
            description=f"今週末（{sat_str}〜{sun_str}）の子ども向けイベントまとめ。おすすめ3選・無料件数つき。",
            path="weekend.html",
            og_image="ogp-weekend.png",   # ★これ
        ),
        encoding="utf-8"
    )

def main():
    con = connect_db()
    import_sendai_events(con)
    build_site(con)
    con.close()

if __name__ == "__main__":
    main()
