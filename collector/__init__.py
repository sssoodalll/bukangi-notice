"""부캉이 안전 기사 수집 모듈.

다른 프로그램에서는 이렇게 쓴다:
    from collector import collect, store
    articles = collect()
    conn = store.connect()
    store.save(conn, articles)
"""
from collector.article import Article
from collector.classify import classify
from collector.sources import SOURCES

# 수집할 때 버리는 꼬리표: 관계없는 기사, 정치 기사
DROPPED = ("unrelated", "politics")

DEFAULT_QUERIES = [
    # 넓게 찾기
    "부캉이", "부캉이 상어", "북항 상어", "북항 친수공원 상어",
    # 1순위: 사람의 안전
    "부캉이 통제", "부캉이 안전", "부캉이 폰", "부캉이 관람객 안전",
    # 2순위: 상어의 안전
    "부캉이 투척", "부캉이 지느러미",
]


def collect(queries: list[str] = DEFAULT_QUERIES,
            keep_unrelated: bool = False) -> list[Article]:
    """모든 출처에서 기사를 모으고, 중복을 빼고, 꼬리표를 붙여 최신순으로 돌려준다.

    부캉이와 관계없는 기사와 정치 기사는 버린다. (keep_unrelated=True면 남긴다)
    """
    seen_urls, seen_titles, result = set(), set(), []
    for fetch in SOURCES.values():
        for q in queries:
            for a in fetch(q):
                key = a.title_key()
                if a.url in seen_urls or key in seen_titles:
                    continue
                seen_urls.add(a.url)
                seen_titles.add(key)
                classify(a)
                if a.category in DROPPED and not keep_unrelated:
                    continue
                result.append(a)
    result.sort(key=lambda a: a.published_at, reverse=True)
    return result
