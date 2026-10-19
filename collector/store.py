"""모은 기사를 SQLite 장부(data/articles.db)에 저장하고 꺼낸다.

검수 상태(status):
- pending:  검수 전 (처음 저장될 때)
- approved: 승인 → 부캉이 사이트로 전달할 기사
- rejected: 반려
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from collector.article import Article

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "articles.db"
STATUSES = ("pending", "approved", "rejected")
DECIDERS = ("human", "auto")  # 누가 결정했나: 사람 / AI 판정기

# 처음 만든 뒤에 추가한 칸들 (예전 장부를 열 때 자동으로 붙인다)
NEW_COLUMNS = {"priority": "INTEGER", "decided_by": "TEXT", "score": "REAL"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL UNIQUE,
    title        TEXT NOT NULL,
    title_key    TEXT NOT NULL UNIQUE,
    press        TEXT,
    published_at TEXT NOT NULL,
    source       TEXT,
    query        TEXT,
    summary      TEXT,
    category     TEXT,
    priority     INTEGER,
    tags         TEXT,
    status       TEXT NOT NULL DEFAULT 'pending',
    decided_by   TEXT,
    score        REAL,
    collected_at TEXT NOT NULL,
    reviewed_at  TEXT
);
"""

# 검수할 때 보여 줄 순서: 사람 안전 → 상어 안전 → 기타 → 인기
CATEGORY_ORDER = ("CASE WHEN category = 'safety' THEN priority "
                  "WHEN category = 'other' THEN 3 ELSE 4 END")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    # 예전 장부에 없는 칸은 추가한다 (이미 있으면 그대로)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    for name, kind in NEW_COLUMNS.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE articles ADD COLUMN {name} {kind}")
    return conn


def save(conn: sqlite3.Connection, articles: list[Article]) -> int:
    """기사를 장부에 넣는다. 이미 있는 기사(같은 주소나 같은 제목)는 건너뛴다.
    새로 들어간 기사 수를 돌려준다."""
    before = conn.total_changes
    conn.executemany(
        """INSERT OR IGNORE INTO articles
           (url, title, title_key, press, published_at, source, query,
            summary, category, priority, tags, collected_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(a.url, a.title, a.title_key(), a.press, a.published_at.isoformat(),
          a.source, a.query, a.summary, a.category, a.priority,
          json.dumps(a.tags, ensure_ascii=False), _now()) for a in articles],
    )
    conn.commit()
    return conn.total_changes - before


def list_articles(conn: sqlite3.Connection, status: str | None = None,
                  category: str | None = None) -> list[dict]:
    """장부에서 기사를 꺼낸다. 안전 기사가 먼저, 같은 꼬리표 안에서는 최신순.
    관계없는 기사·정치 기사는 빼고 꺼낸다."""
    where, args = ["category NOT IN ('unrelated', 'politics')"], []
    if status:
        where.append("status = ?"); args.append(status)
    if category:
        where.append("category = ?"); args.append(category)
    sql = "SELECT * FROM articles WHERE " + " AND ".join(where)
    sql += f" ORDER BY {CATEGORY_ORDER}, published_at DESC"
    rows = conn.execute(sql, args).fetchall()
    return [dict(r, tags=json.loads(r["tags"] or "[]")) for r in rows]


def list_approved(conn: sqlite3.Connection, since: str | None = None,
                  limit: int = 50) -> list[dict]:
    """승인된 기사를 최근 승인 순으로 꺼낸다. since(UTC ISO 시각) 이후 승인분만 고를 수 있다."""
    sql = ("SELECT * FROM articles WHERE status = 'approved' "
           "AND category NOT IN ('unrelated', 'politics')")
    args = []
    if since:
        sql += " AND reviewed_at > ?"; args.append(since)
    sql += " ORDER BY reviewed_at DESC LIMIT ?"; args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    return [dict(r, tags=json.loads(r["tags"] or "[]")) for r in rows]


def set_status(conn: sqlite3.Connection, article_id: int, status: str,
               decided_by: str = "human") -> bool:
    """검수 결과를 기록한다. 해당 기사가 없으면 False."""
    if status not in STATUSES:
        raise ValueError(f"status는 {STATUSES} 중 하나여야 합니다: {status}")
    if decided_by not in DECIDERS:
        raise ValueError(f"decided_by는 {DECIDERS} 중 하나여야 합니다: {decided_by}")
    pending = status == "pending"
    cur = conn.execute(
        "UPDATE articles SET status = ?, reviewed_at = ?, decided_by = ? WHERE id = ?",
        (status, None if pending else _now(), None if pending else decided_by, article_id),
    )
    conn.commit()
    return cur.rowcount > 0


def human_reviewed(conn: sqlite3.Connection) -> list[dict]:
    """사람이 승인/반려한 기사 (판정기의 정답지). AI가 결정한 것, 수집 때 버리는 꼬리표는 넣지 않는다."""
    rows = conn.execute("SELECT * FROM articles WHERE status != 'pending' "
                        "AND (decided_by IS NULL OR decided_by = 'human') "
                        "AND category NOT IN ('unrelated', 'politics') ORDER BY id").fetchall()
    return [dict(r, tags=json.loads(r["tags"] or "[]")) for r in rows]


def set_scores(conn: sqlite3.Connection, scores: dict[int, float]) -> None:
    """기사마다 판정기가 매긴 승인 확률을 적는다."""
    conn.executemany("UPDATE articles SET score = ? WHERE id = ?",
                     [(s, i) for i, s in scores.items()])
    conn.commit()


def reclassify(conn: sqlite3.Connection) -> int:
    """장부의 모든 기사에 지금 규칙으로 꼬리표를 다시 붙인다. 검수 상태는 건드리지 않는다."""
    from collector.classify import classify
    rows = conn.execute("SELECT id, title, url, press, published_at, source, query, summary "
                        "FROM articles").fetchall()
    updates = []
    for r in rows:
        a = classify(Article(r["title"], r["url"], r["press"] or "",
                             datetime.fromisoformat(r["published_at"]), r["source"] or "",
                             r["query"] or "", r["summary"] or ""))
        updates.append((a.category, a.priority, json.dumps(a.tags, ensure_ascii=False), r["id"]))
    conn.executemany("UPDATE articles SET category = ?, priority = ?, tags = ? WHERE id = ?", updates)
    conn.commit()
    return len(updates)


def count_by_status(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT status, COUNT(*) FROM articles GROUP BY status")
    return {s: n for s, n in rows}
