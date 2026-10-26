"""관리자 로그인 (비밀 열쇠 하나 방식).

- 환경 변수 ADMIN_TOKEN 에 긴 비밀 문자열을 넣어 둔다. 없거나 짧으면 서버를 켜지 않는다.
- 검수 화면에 들어가려면 /login 에서 이 열쇠를 넣는다. 맞으면 브라우저에 쿠키로 기억시킨다.
- 쿠키에는 열쇠 자체가 아니라 열쇠로 만든 서명(HMAC)을 넣는다.
"""
import hashlib
import hmac
import os
import time

COOKIE_NAME = "bukangi_admin"
COOKIE_MAX_AGE = 60 * 60 * 24 * 14  # 14일 동안 로그인 유지
MIN_TOKEN_LENGTH = 24


def admin_token() -> str:
    return os.environ.get("ADMIN_TOKEN", "")


def check_configured() -> None:
    """서버를 켤 때 열쇠가 제대로 있는지 확인한다."""
    if len(admin_token()) < MIN_TOKEN_LENGTH:
        raise RuntimeError(
            f"ADMIN_TOKEN이 없거나 너무 짧아요 ({MIN_TOKEN_LENGTH}자 이상 필요). "
            "열쇠 없이 검수 화면을 열지 않으려고 서버를 켜지 않았어요. .env 파일을 확인해 주세요.")


def _signature() -> str:
    return hmac.new(admin_token().encode(), b"bukangi-admin-session", hashlib.sha256).hexdigest()


def token_matches(given: str) -> bool:
    ok = hmac.compare_digest(given.encode(), admin_token().encode())
    if not ok:
        time.sleep(1)  # 틀린 열쇠를 빠르게 여러 번 시도하지 못하게
    return ok


def cookie_value() -> str:
    return _signature()


def is_admin(cookie: str | None) -> bool:
    return bool(cookie) and hmac.compare_digest(cookie, _signature())
