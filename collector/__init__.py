"""부캉이 안전 기사 수집 모듈.

다른 프로그램에서는 이렇게 쓴다:
    from collector import collect
    articles = collect()
"""
import re

from collector.article import Article
from collector.classify import classify
from collector.sources import SOURCES

DEFAULT_QUERIES = ["부캉이", "북항 상어"]


def _title_key(title: str) -> str:
    # 띄어쓰기·따옴표·기호를 지워서 "거의 같은 제목"을 같은 것으로 본다
    return re.sub(r"[\W_]+", "", title)


def collect(queries: list[str] = DEFAULT_QUERIES,
            keep_unrelated: bool = False) -> list[Article]:
    """모든 출처에서 기사를 모으고, 중복을 빼고, 꼬리표를 붙여 최신순으로 돌려준다.

    부캉이와 관계없는 기사는 버린다. (keep_unrelated=True면 남긴다)
    """
    seen_urls, seen_titles, result = set(), set(), []
    for fetch in SOURCES.values():
        for q in queries:
            for a in fetch(q):
                key = _title_key(a.title)
                if a.url in seen_urls or key in seen_titles:
                    continue
                seen_urls.add(a.url)
                seen_titles.add(key)
                classify(a)
                if a.category == "unrelated" and not keep_unrelated:
                    continue
                result.append(a)
    result.sort(key=lambda a: a.published_at, reverse=True)
    return result
