"""검수 화면 서버를 켠다.

실행:  python run_server.py
브라우저에서 http://localhost:8000 을 연다. 끌 때는 터미널에서 Ctrl + C.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("server.app:app", host="127.0.0.1", port=8000, reload=True)
