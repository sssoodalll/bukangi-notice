"""서버를 켠다: 검수 화면 + 전달 API + 자동 수집(기본 1시간마다).

실행:  python run_server.py
브라우저에서 http://localhost:8000 을 연다. 끌 때는 터미널에서 Ctrl + C.
설정(환경 변수 또는 .env 파일):
- ADMIN_TOKEN (필수): 검수 화면 관리자 열쇠. 없으면 서버가 켜지지 않는다
- HOST(기본 127.0.0.1), PORT(기본 8000), 나머지는 server/scheduler.py 참고
"""
import os
from pathlib import Path

import uvicorn


def load_env_file(path: Path) -> None:
    """KEY=VALUE 줄을 읽어 환경 변수로 넣는다. 이미 정해진 환경 변수가 있으면 그쪽이 우선이다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


if __name__ == "__main__":
    load_env_file(Path(__file__).resolve().parent / ".env")
    uvicorn.run("server.app:app",
                host=os.environ.get("HOST", "127.0.0.1"),
                port=int(os.environ.get("PORT", "8000")))
