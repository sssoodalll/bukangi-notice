"""기사 한 건을 담는 상자."""
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime


@dataclass
class Article:
    title: str              # 기사 제목 (언론사 이름은 뺀 것)
    url: str                # 기사 주소
    press: str              # 언론사 이름 (예: 연합뉴스)
    published_at: datetime  # 기사가 올라온 시각
    source: str             # 어디서 찾았는지 (예: google_news, naver)
    query: str              # 어떤 검색어로 찾았는지
    summary: str = ""       # 기사 요약 (출처가 주는 경우에만)
    category: str = ""      # 꼬리표: safety / popular / other / unrelated (classify.py)
    tags: list[str] = field(default_factory=list)  # 꼬리표를 붙인 근거 단어

    def title_key(self) -> str:
        # 띄어쓰기·따옴표·기호를 지워서 "거의 같은 제목"을 같은 것으로 본다
        return re.sub(r"[\W_]+", "", self.title)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published_at"] = self.published_at.isoformat()
        return d
