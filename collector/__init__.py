"""부캉이 안전 기사 수집 로봇.

다른 프로그램에서는 이렇게 쓴다:
    from collector import collect
    articles = collect()
"""
import re

from collector.article import Article
from collector.sources import SOURCES

DEFAULT_QUERIES = ["부캉이", "북항 상어"]


def _title_key(title: str) -> str:
    # 띄어쓰기·따옴표·기호를 지워서 "거의 같은 제목"을 같은 것으로 본다
    return re.sub(r"[\W_]+", "", title)


def collect(queries: list[str] = DEFAULT_QUERIES) -> list[Article]:
    """모든 출처에서 검색어마다 기사를 모으고, 중복을 빼고, 최신순으로 돌려준다."""
    seen_urls, seen_titles, result = set(), set(), []
    for fetch in SOURCES.values():
        for q in queries:
            for a in fetch(q):
                key = _title_key(a.title)
                if a.url in seen_urls or key in seen_titles:
                    continue
                seen_urls.add(a.url)
                seen_titles.add(key)
                result.append(a)
    result.sort(key=lambda a: a.published_at, reverse=True)
    return result
