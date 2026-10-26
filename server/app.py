"""검수 화면 서버 (FastAPI).

브라우저에서 기사 목록을 보고 [승인] [반려] 버튼을 누른다.
서버가 켜져 있는 동안 scheduler가 정해진 간격마다 기사를 모은다.
검수 화면은 관리자 열쇠(ADMIN_TOKEN)로 로그인해야 들어갈 수 있다 (server/auth.py).
실행:  python run_server.py  →  http://localhost:8000
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from collector import store
from server import auth, scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    auth.check_configured()
    task = asyncio.create_task(scheduler.loop()) if scheduler.INTERVAL_MIN > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="부캉이 안전 기사 검수", lifespan=lifespan)

KST = timezone(timedelta(hours=9))
CATEGORY_LABELS = {"safety": "안전", "other": "기타", "popular": "인기"}
STATUS_LABELS = {"pending": "검수 전", "approved": "승인", "rejected": "반려"}
PRIORITY_LABELS = {1: "1순위 사람 안전", 2: "2순위 상어 안전"}


def _kst(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(KST).strftime("%m-%d %H:%M")


def _category_label(a: dict) -> str:
    if a["category"] == "safety":
        return PRIORITY_LABELS.get(a.get("priority"), "안전")
    return CATEGORY_LABELS.get(a["category"], a["category"])


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
        <span class="badge {a['category']} p{a.get('priority') or ''}">{_category_label(a)}</span>
        <span class="badge st-{a['status']}">{STATUS_LABELS[a['status']]}</span>
        {'<span class="badge ai">AI 결정</span>' if a.get('decided_by') == 'auto' else ''}
        {f'<span class="score">AI 승인 확률 {a["score"]:.2f}</span>' if a.get('score') is not None else ''}
        #{a['id']} · {_kst(a['published_at'])} · {escape(a['press'] or '')}
      </div>
      <a class="title" href="{escape(a['url'])}" target="_blank" rel="noopener">{escape(a['title'])}</a>
      {f'<div class="tags">근거 단어: {escape(tags)}</div>' if tags else ''}
      <form method="post" action="/articles/{a['id']}/status">
        <input type="hidden" name="back" value="{escape(back)}">{buttons}
      </form>
    </li>"""


def _require_admin(request: Request) -> None:
    if not auth.is_admin(request.cookies.get(auth.COOKIE_NAME)):
        raise HTTPException(401, "로그인이 필요해요")


LOGIN_PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>부캉이 기사 검수 로그인</title>
<style>
  :root {{ --bg:#f6f7f9; --card:#fff; --text:#1d2433; --muted:#6b7280; --line:#e5e7eb; --reject:#dc2626; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#111418; --card:#1b1f26; --text:#e5e7eb; --muted:#9ca3af; --line:#2d333b; }} }}
  body {{ margin:0; background:var(--bg); color:var(--text); font-family:system-ui,"Malgun Gothic",sans-serif; }}
  main {{ max-width:420px; margin:12vh auto; padding:16px; }}
  form {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:20px; display:grid; gap:12px; }}
  input {{ padding:10px; border:1px solid var(--line); border-radius:8px; background:var(--bg); color:var(--text); font-size:15px; }}
  button {{ padding:10px; border:0; border-radius:8px; background:var(--text); color:var(--bg); font-size:15px; cursor:pointer; }}
  .err {{ color:var(--reject); margin:0; }} small {{ color:var(--muted); }}
</style></head>
<body><main>
  <h1>🦈 관리자 로그인</h1>
  <form method="post" action="/login">
    {error}
    <input type="password" name="token" placeholder="관리자 열쇠" autocomplete="current-password" required autofocus>
    <button>들어가기</button>
    <small>관리자만 들어올 수 있어요.</small>
  </form>
</main></body></html>"""


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return LOGIN_PAGE.format(error="")


@app.post("/login")
def login(request: Request, token: str = Form(...)):
    if not auth.token_matches(token):
        return HTMLResponse(LOGIN_PAGE.format(error='<p class="err">열쇠가 맞지 않아요.</p>'), status_code=401)
    resp = RedirectResponse("/", status_code=303)
    https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    resp.set_cookie(auth.COOKIE_NAME, auth.cookie_value(), max_age=auth.COOKIE_MAX_AGE,
                    httponly=True, samesite="strict", secure=https)
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(auth.COOKIE_NAME)
    return resp


@app.get("/", response_class=HTMLResponse)
def review_page(request: Request, status: str = "pending", category: str = "", msg: str = ""):
    if not auth.is_admin(request.cookies.get(auth.COOKIE_NAME)):
        return RedirectResponse("/login", status_code=303)
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
    run = scheduler.last_run
    if scheduler.INTERVAL_MIN <= 0:
        auto = "자동 수집 꺼짐"
    elif run["at"] is None:
        auto = f"자동 수집: {scheduler.INTERVAL_MIN}분마다 · 첫 수집 중…"
    else:
        result = f"오류 ({escape(run['error'])})" if run["error"] else f"새 기사 {run['new']}건"
        if run.get("auto") and scheduler.AUTO_DECIDE != "off":
            result += f" · AI 자동 승인 {run['auto']['approved']}"
            if scheduler.AUTO_DECIDE == "both":
                result += f" / 반려 {run['auto']['rejected']}"
        auto = (f"자동 수집: {scheduler.INTERVAL_MIN}분마다 · "
                f"마지막 {run['at'].astimezone(KST):%m-%d %H:%M} {result}")

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
  .auto {{ color:var(--muted); margin-left:8px; }}
  .logout {{ float:right; font-size:13px; font-weight:400; color:var(--muted); }}
  .score {{ font-size:12px; padding:1px 8px; border-radius:999px; border:1px solid var(--line); }}
  .badge.ai {{ background:#7c3aed; }}
  .msg {{ background:var(--card); border-left:4px solid var(--safety); padding:8px 12px; }}
  ul {{ list-style:none; padding:0; margin:0; display:grid; gap:10px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-left:4px solid var(--other);
          border-radius:10px; padding:12px 14px; }}
  .card.safety {{ border-left-color:var(--safety); }}
  .card.popular {{ border-left-color:var(--popular); }}
  .meta {{ font-size:13px; color:var(--muted); display:flex; flex-wrap:wrap; gap:6px; align-items:center; }}
  .badge {{ font-size:12px; padding:1px 8px; border-radius:999px; color:#fff; background:var(--other); }}
  .badge.safety {{ background:var(--safety); }} .badge.p1 {{ background:#ea580c; }} .badge.popular {{ background:var(--popular); }}
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
  <h1>🦈 부캉이 안전 기사 검수 <a class="logout" href="/logout">로그아웃</a></h1>
  <nav>{status_tabs}</nav>
  <nav>{category_tabs}</nav>
  <div class="bar">
    <span>{len(rows)}건 <small class="auto">{auto}</small></span>
    <form method="post" action="/collect"><button>지금 새 기사 모으기</button></form>
  </div>
  {notice}
  <ul>{items}</ul>
</main></body></html>"""


@app.post("/articles/{article_id}/status")
def change_status(request: Request, article_id: int, status: str = Form(...), back: str = Form("/")):
    _require_admin(request)
    if status not in store.STATUSES:
        raise HTTPException(400, "잘못된 상태")
    conn = store.connect()
    try:
        if not store.set_status(conn, article_id, status):
            raise HTTPException(404, "기사가 없어요")
    finally:
        conn.close()
    return RedirectResponse(back if back.startswith("/") else "/", status_code=303)


API_FIELDS = ("id", "title", "url", "press", "published_at", "category", "priority", "tags",
              "reviewed_at", "decided_by", "score")


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
def collect_now(request: Request):
    _require_admin(request)
    new = scheduler.run_collection()
    msg = (f"새 기사 {new}건을 장부에 넣었어요." if new is not None
           else "이미 수집 중이거나 오류가 났어요. 잠시 뒤 다시 확인해 주세요.")
    return RedirectResponse("/?" + urlencode({"msg": msg}), status_code=303)
