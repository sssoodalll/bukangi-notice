"""서버를 켠다: 검수 화면 + 전달 API + 자동 수집(기본 1시간마다).

실행:  python run_server.py
브라우저에서 http://localhost:8000 을 연다. 끌 때는 터미널에서 Ctrl + C.
설정(환경 변수): HOST(기본 127.0.0.1), PORT(기본 8000), 나머지는 server/scheduler.py 참고
"""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("server.app:app",
                host=os.environ.get("HOST", "127.0.0.1"),
                port=int(os.environ.get("PORT", "8000")))
