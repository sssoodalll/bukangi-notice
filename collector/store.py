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
    tags         TEXT,
    status       TEXT NOT NULL DEFAULT 'pending',
    collected_at TEXT NOT NULL,
    reviewed_at  TEXT
);
"""

# 검수할 때 보여 줄 순서: 안전 → 기타 → 인기
CATEGORY_ORDER = "CASE category WHEN 'safety' THEN 0 WHEN 'other' THEN 1 ELSE 2 END"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def save(conn: sqlite3.Connection, articles: list[Article]) -> int:
    """기사를 장부에 넣는다. 이미 있는 기사(같은 주소나 같은 제목)는 건너뛴다.
    새로 들어간 기사 수를 돌려준다."""
    before = conn.total_changes
    conn.executemany(
        """INSERT OR IGNORE INTO articles
           (url, title, title_key, press, published_at, source, query,
            summary, category, tags, collected_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(a.url, a.title, a.title_key(), a.press, a.published_at.isoformat(),
          a.source, a.query, a.summary, a.category,
          json.dumps(a.tags, ensure_ascii=False), _now()) for a in articles],
    )
    conn.commit()
    return conn.total_changes - before


def list_articles(conn: sqlite3.Connection, status: str | None = None,
                  category: str | None = None) -> list[dict]:
    """장부에서 기사를 꺼낸다. 안전 기사가 먼저, 같은 꼬리표 안에서는 최신순."""
    where, args = [], []
    if status:
        where.append("status = ?"); args.append(status)
    if category:
        where.append("category = ?"); args.append(category)
    sql = "SELECT * FROM articles"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {CATEGORY_ORDER}, published_at DESC"
    rows = conn.execute(sql, args).fetchall()
    return [dict(r, tags=json.loads(r["tags"] or "[]")) for r in rows]


def list_approved(conn: sqlite3.Connection, since: str | None = None,
                  limit: int = 50) -> list[dict]:
    """승인된 기사를 최근 승인 순으로 꺼낸다. since(UTC ISO 시각) 이후 승인분만 고를 수 있다."""
    sql, args = "SELECT * FROM articles WHERE status = 'approved'", []
    if since:
        sql += " AND reviewed_at > ?"; args.append(since)
    sql += " ORDER BY reviewed_at DESC LIMIT ?"; args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    return [dict(r, tags=json.loads(r["tags"] or "[]")) for r in rows]


def set_status(conn: sqlite3.Connection, article_id: int, status: str) -> bool:
    """검수 결과를 기록한다. 해당 기사가 없으면 False."""
    if status not in STATUSES:
        raise ValueError(f"status는 {STATUSES} 중 하나여야 합니다: {status}")
    cur = conn.execute(
        "UPDATE articles SET status = ?, reviewed_at = ? WHERE id = ?",
        (status, _now() if status != "pending" else None, article_id),
    )
    conn.commit()
    return cur.rowcount > 0


def count_by_status(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT status, COUNT(*) FROM articles GROUP BY status")
    return {s: n for s, n in rows}
