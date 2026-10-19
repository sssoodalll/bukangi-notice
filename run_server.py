"""검수 화면 서버를 켠다. 켜져 있는 동안 1시간마다 기사를 자동으로 모은다.

실행:  python run_server.py
브라우저에서 http://localhost:8000 을 연다. 끌 때는 터미널에서 Ctrl + C.
수집 간격 바꾸기: 환경 변수 COLLECT_INTERVAL_MIN (분, 기본 60, 0이면 끔)
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("server.app:app", host="127.0.0.1", port=8000)
