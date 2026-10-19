"""검수 화면 서버 (FastAPI).

브라우저에서 기사 목록을 보고 [승인] [반려] 버튼을 누른다.
실행:  python run_server.py  →  http://localhost:8000
"""
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from collector import collect, store

app = FastAPI(title="부캉이 안전 기사 검수")

KST = timezone(timedelta(hours=9))
CATEGORY_LABELS = {"safety": "안전", "other": "기타", "popular": "인기"}
STATUS_LABELS = {"pending": "검수 전", "approved": "승인", "rejected": "반려"}


def _kst(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(KST).strftime("%m-%d %H:%M")


def _link(label: str, current: bool, **params) -> str:
    cls = ' class="on"' if current else ""
    return f'<a{cls} href="/?{urlencode({k: v for k, v in params.items() if v})}">{label}</a>'


def _row(a: dict, back: str) -> str:
    tags = ", ".join(t.split(":")[1] for t in a["tags"][:4])
    buttons = "".join(
        f'<button name="status" value="{s}" class="{s}">{label}</button>'
        for s, label in (("approved", "승인"), ("rejected", "반려"), ("pending", "되돌리기"))
        if s != a["status"]
    )
    return f"""
    <li class="card {a['category']}">
      <div class="meta">
        <span class="badge {a['category']}">{CATEGORY_LABELS.get(a['category'], a['category'])}</span>
        <span class="badge st-{a['status']}">{STATUS_LABELS[a['status']]}</span>
        #{a['id']} · {_kst(a['published_at'])} · {escape(a['press'] or '')}
      </div>
      <a class="title" href="{escape(a['url'])}" target="_blank" rel="noopener">{escape(a['title'])}</a>
      {f'<div class="tags">근거 단어: {escape(tags)}</div>' if tags else ''}
      <form method="post" action="/articles/{a['id']}/status">
        <input type="hidden" name="back" value="{escape(back)}">{buttons}
      </form>
    </li>"""


@app.get("/", response_class=HTMLResponse)
def review_page(status: str = "pending", category: str = "", msg: str = ""):
    conn = store.connect()
    try:
        rows = store.list_articles(conn, status=status or None, category=category or None)
        counts = store.count_by_status(conn)
    finally:
        conn.close()

    back = "/?" + urlencode({k: v for k, v in {"status": status, "category": category}.items() if v})
    status_tabs = " ".join(
        _link(f"{label} {counts.get(s, 0)}", status == s, status=s, category=category)
        for s, label in STATUS_LABELS.items())
    category_tabs = " ".join(
        [_link("전체", not category, status=status)]
        + [_link(label, category == c, status=status, category=c) for c, label in CATEGORY_LABELS.items()])
    items = "".join(_row(a, back) for a in rows) or '<li class="empty">기사가 없어요.</li>'
    notice = f'<p class="msg">{escape(msg)}</p>' if msg else ""

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>부캉이 기사 검수</title>
<style>
  :root {{ --bg:#f6f7f9; --card:#fff; --text:#1d2433; --muted:#6b7280; --line:#e5e7eb;
          --safety:#16a34a; --other:#6b7280; --popular:#2563eb; --reject:#dc2626; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#111418; --card:#1b1f26; --text:#e5e7eb; --muted:#9ca3af; --line:#2d333b; }} }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
         font-family:system-ui,"Malgun Gothic",sans-serif; }}
  main {{ max-width:860px; margin:0 auto; padding:16px; }}
  h1 {{ font-size:20px; margin:4px 0 12px; }}
  nav {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px; }}
  nav a {{ padding:6px 12px; border:1px solid var(--line); border-radius:999px;
          color:var(--text); text-decoration:none; font-size:14px; background:var(--card); }}
  nav a.on {{ background:var(--text); color:var(--bg); }}
  .bar {{ display:flex; justify-content:space-between; align-items:center; gap:8px; margin:12px 0; }}
  .bar button {{ padding:8px 14px; border-radius:8px; border:0; background:var(--text);
                color:var(--bg); cursor:pointer; font-size:14px; }}
  .msg {{ background:var(--card); border-left:4px solid var(--safety); padding:8px 12px; }}
  ul {{ list-style:none; padding:0; margin:0; display:grid; gap:10px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-left:4px solid var(--other);
          border-radius:10px; padding:12px 14px; }}
  .card.safety {{ border-left-color:var(--safety); }}
  .card.popular {{ border-left-color:var(--popular); }}
  .meta {{ font-size:13px; color:var(--muted); display:flex; flex-wrap:wrap; gap:6px; align-items:center; }}
  .badge {{ font-size:12px; padding:1px 8px; border-radius:999px; color:#fff; background:var(--other); }}
  .badge.safety {{ background:var(--safety); }} .badge.popular {{ background:var(--popular); }}
  .badge.st-pending {{ background:transparent; color:var(--muted); border:1px solid var(--line); }}
  .badge.st-approved {{ background:var(--safety); }} .badge.st-rejected {{ background:var(--reject); }}
  .title {{ display:block; margin:6px 0; color:var(--text); font-weight:600; text-decoration:none; }}
  .title:hover {{ text-decoration:underline; }}
  .tags {{ font-size:13px; color:var(--muted); }}
  form {{ display:flex; gap:6px; margin-top:8px; }}
  form button {{ padding:6px 14px; border-radius:8px; border:1px solid var(--line);
                background:var(--card); color:var(--text); cursor:pointer; font-size:14px; }}
  form button.approved {{ background:var(--safety); color:#fff; border:0; }}
  form button.rejected {{ background:var(--reject); color:#fff; border:0; }}
  .empty {{ color:var(--muted); padding:24px; text-align:center; }}
</style></head>
<body><main>
  <h1>🦈 부캉이 안전 기사 검수</h1>
  <nav>{status_tabs}</nav>
  <nav>{category_tabs}</nav>
  <div class="bar">
    <span>{len(rows)}건</span>
    <form method="post" action="/collect"><button>지금 새 기사 모으기</button></form>
  </div>
  {notice}
  <ul>{items}</ul>
</main></body></html>"""


@app.post("/articles/{article_id}/status")
def change_status(article_id: int, status: str = Form(...), back: str = Form("/")):
    if status not in store.STATUSES:
        raise HTTPException(400, "잘못된 상태")
    conn = store.connect()
    try:
        if not store.set_status(conn, article_id, status):
            raise HTTPException(404, "기사가 없어요")
    finally:
        conn.close()
    return RedirectResponse(back if back.startswith("/") else "/", status_code=303)


API_FIELDS = ("id", "title", "url", "press", "published_at", "category", "tags", "reviewed_at")


@app.get("/api/approved")
def approved_articles(since: str = "", limit: int = 50):
    """승인된 기사 목록 (부캉이 사이트가 가져가는 창구).

    - since: 이 시각 이후에 승인된 기사만 (예: 2026-10-19T00:00:00+00:00). 비우면 전부.
    - limit: 최대 몇 건 (기본 50, 최대 200)
    최신 승인 순으로 돌려준다.
    """
    if since:
        try:
            since = datetime.fromisoformat(since).astimezone(timezone.utc).isoformat()
        except ValueError:
            raise HTTPException(400, "since는 ISO 시각이어야 해요 (예: 2026-10-19T00:00:00+00:00)")
    conn = store.connect()
    try:
        rows = store.list_approved(conn, since=since or None, limit=max(1, min(limit, 200)))
    finally:
        conn.close()
    return {"count": len(rows), "articles": [{k: r[k] for k in API_FIELDS} for r in rows]}


@app.post("/collect")
def collect_now():
    articles = collect()
    conn = store.connect()
    try:
        new = store.save(conn, articles)
    finally:
        conn.close()
    return RedirectResponse("/?" + urlencode({"msg": f"새 기사 {new}건을 장부에 넣었어요."}), status_code=303)
