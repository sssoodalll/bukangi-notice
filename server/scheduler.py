"""정해진 간격마다 기사를 모아 장부에 넣는 알람.

간격은 환경 변수 COLLECT_INTERVAL_MIN 으로 바꾼다 (기본 60분, 0이면 끔).
서버가 켜지면 바로 한 번 모으고, 그 뒤로 간격마다 모은다.
"""
import asyncio
import logging
import os
import threading
from datetime import datetime, timezone

from collector import collect, store

log = logging.getLogger("uvicorn.error")

INTERVAL_MIN = int(os.environ.get("COLLECT_INTERVAL_MIN", "60"))

# 마지막 수집 결과 (검수 화면에 보여 준다)
last_run = {"at": None, "new": None, "error": None}
_lock = threading.Lock()  # 알람과 "지금 모으기" 버튼이 동시에 돌지 않게


def run_collection() -> int | None:
    """한 번 모아서 장부에 넣는다. 이미 다른 수집이 돌고 있으면 None."""
    if not _lock.acquire(blocking=False):
        return None
    try:
        articles = collect()
        conn = store.connect()
        try:
            new = store.save(conn, articles)
        finally:
            conn.close()
        last_run.update(at=datetime.now(timezone.utc), new=new, error=None)
        log.info("자동 수집: 새 기사 %d건", new)
        return new
    except Exception as e:  # 인터넷이 끊겨도 서버는 계속 돈다
        last_run.update(at=datetime.now(timezone.utc), new=None, error=str(e))
        log.exception("자동 수집 실패")
        return None
    finally:
        _lock.release()


async def loop() -> None:
    while True:
        await asyncio.to_thread(run_collection)
        await asyncio.sleep(INTERVAL_MIN * 60)
