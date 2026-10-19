"""단어 규칙으로 기사에 꼬리표를 붙인다.

- unrelated: 부캉이·상어 이야기가 아님 → collect()에서 버린다
- safety:    안전 기사 (아래 4가지 중 하나라도 해당)
- popular:   인기·방문객 기사
- other:     부캉이 기사지만 어느 쪽 단어도 없음 → 사람이 판단

안전 단어가 하나라도 있으면 인기 단어가 같이 있어도 safety로 본다.
(안전 기사를 놓치는 것이 더 위험하기 때문)
"""
import re

from collector.article import Article

TOPIC_WORDS = ["부캉이", "상어"]
# 이 검색어로 찾은 기사는 제목에 단어가 없어도 버리지 않는다.
# (흔한 단어가 아니라서, 검색 엔진이 본문에서 찾아낸 것으로 본다)
TRUSTED_QUERIES = ["부캉이"]

SAFETY_WORDS = {
    "통제·수칙": ["통제", "금지", "자제", "당부", "주의", "접근", "출입", "안내방송",
               "계도", "불빛", "랜턴", "손전등", "수칙"],
    "구조·이동": ["구조", "외해", "유도", "그물", "포획", "방류", "퇴로", "돌려보내"],
    "상어 건강": ["상처", "건강", "부상", "손상", "지느러미", "출혈", "굶", "먹이",
               "수온", "폐사", "스트레스", "탈진"],
    "사고·위험": ["사고", "위험", "추락", "물림", "물려", "다쳐", "혼잡", "안전"],
}

POPULAR_WORDS = ["방문객", "관람객", "돌파", "인기", "상표", "굿즈", "관광", "핫플",
                 "명소", "뉴욕타임스", "스타", "체험", "축제", "구경"]


def _text(article: Article) -> str:
    # 요약에 섞인 HTML 태그(<a> 등)를 지우고 제목과 합친다
    return article.title + " " + re.sub(r"<[^>]+>", " ", article.summary)


def classify(article: Article) -> Article:
    """기사에 category(꼬리표)와 tags(걸린 단어)를 채워서 돌려준다."""
    text = _text(article)
    if not any(w in text for w in TOPIC_WORDS) and article.query not in TRUSTED_QUERIES:
        article.category, article.tags = "unrelated", []
        return article

    tags = [f"{group}:{w}" for group, words in SAFETY_WORDS.items()
            for w in words if w in text]
    if tags:
        article.category = "safety"
    else:
        tags = [f"인기:{w}" for w in POPULAR_WORDS if w in text]
        article.category = "popular" if tags else "other"
    article.tags = tags
    return article
