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

DEFAULT_QUERIES = [
    # 넓게 찾기
    "부캉이", "부캉이 상어", "북항 상어", "북항 친수공원 상어",
    # 안전 기사를 겨냥 (안전 기준 ①~④)
    "부캉이 통제", "부캉이 안전",       # ① 출입 통제·행동 수칙, ④ 사고·위험
    "부캉이 구조", "부캉이 외해",       # ② 구조·이동 작전
    "부캉이 건강", "부캉이 지느러미",   # ③ 상어 건강
]


def collect(queries: list[str] = DEFAULT_QUERIES,
            keep_unrelated: bool = False) -> list[Article]:
    """모든 출처에서 기사를 모으고, 중복을 빼고, 꼬리표를 붙여 최신순으로 돌려준다.

    부캉이와 관계없는 기사는 버린다. (keep_unrelated=True면 남긴다)
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
                if a.category == "unrelated" and not keep_unrelated:
                    continue
                result.append(a)
    result.sort(key=lambda a: a.published_at, reverse=True)
    return result
