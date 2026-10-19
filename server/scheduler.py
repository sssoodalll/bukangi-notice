"""정해진 간격마다 기사를 모아 장부에 넣고, 판정기로 점수를 매기는 알람.

환경 변수:
- COLLECT_INTERVAL_MIN: 수집 간격(분). 기본 60, 0이면 끔
- AUTO_DECIDE: 1이면 점수에 따라 자동 승인/반려 (기본 0 = 점수만 매기고 사람이 결정)
- AUTO_HIGH / AUTO_LOW: 자동 승인 / 자동 반려 기준 (기본 0.7 / 0.3)

서버가 켜지면 바로 한 번 돌고, 그 뒤로 간격마다 돈다.
"""
import asyncio
import logging
import os
import threading
from datetime import datetime, timezone

from collector import collect, judge, store

log = logging.getLogger("uvicorn.error")

INTERVAL_MIN = int(os.environ.get("COLLECT_INTERVAL_MIN", "60"))
AUTO_DECIDE = os.environ.get("AUTO_DECIDE", "0") == "1"
AUTO_HIGH = float(os.environ.get("AUTO_HIGH", "0.7"))
AUTO_LOW = float(os.environ.get("AUTO_LOW", "0.3"))

# 마지막 수집 결과 (검수 화면에 보여 준다)
last_run = {"at": None, "new": None, "auto": None, "error": None}
_lock = threading.Lock()  # 알람과 "지금 모으기" 버튼이 동시에 돌지 않게


def judge_pending(conn) -> dict | None:
    """사람 검수 기록으로 다시 배우고, 검수 전 기사에 점수를 매긴다.
    AUTO_DECIDE가 켜져 있으면 기준에 따라 자동 승인/반려한다.
    검수 기록이 부족하면 아무것도 하지 않고 None."""
    try:
        judge.train(store.human_reviewed(conn))
    except ValueError as e:  # 검수 기록 부족
        log.info("판정기 학습 건너뜀: %s", e)
        return None
    pending = store.list_articles(conn, status="pending")
    scores = judge.score(judge.load(), pending)
    store.set_scores(conn, {a["id"]: s for a, s in zip(pending, scores)})

    result = {"scored": len(pending), "approved": 0, "rejected": 0}
    if AUTO_DECIDE:
        for a, s in zip(pending, scores):
            if s >= AUTO_HIGH:
                store.set_status(conn, a["id"], "approved", decided_by="auto")
                result["approved"] += 1
            elif s <= AUTO_LOW:
                store.set_status(conn, a["id"], "rejected", decided_by="auto")
                result["rejected"] += 1
    return result


def run_collection() -> int | None:
    """한 번 모아서 장부에 넣고 점수를 매긴다. 이미 다른 수집이 돌고 있으면 None."""
    if not _lock.acquire(blocking=False):
        return None
    try:
        articles = collect()
        conn = store.connect()
        try:
            new = store.save(conn, articles)
            auto = judge_pending(conn)
        finally:
            conn.close()
        last_run.update(at=datetime.now(timezone.utc), new=new, auto=auto, error=None)
        log.info("자동 수집: 새 기사 %d건, 판정 %s", new, auto)
        return new
    except Exception as e:  # 인터넷이 끊겨도 서버는 계속 돈다
        last_run.update(at=datetime.now(timezone.utc), new=None, auto=None, error=str(e))
        log.exception("자동 수집 실패")
        return None
    finally:
        _lock.release()


async def loop() -> None:
    while True:
        await asyncio.to_thread(run_collection)
        await asyncio.sleep(INTERVAL_MIN * 60)
