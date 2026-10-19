"""단어 규칙으로 기사에 꼬리표와 우선순위를 붙인다.

꼬리표(category):
- unrelated: 부캉이·상어 이야기가 아님 → collect()에서 버린다
- excluded:  제외 단어가 제목에 있는 기사 → collect()에서 버린다
             (단어 목록은 exclude_words.txt. 운영자가 정하며 Git에 올리지 않는다)
- safety:    안전 기사
- popular:   인기·방문객 기사
- other:     부캉이 기사지만 어느 쪽도 아님 (구조·이동 작전 기사도 여기) → 사람이 판단

우선순위(priority, safety일 때만):
- 1: 사람의 안전 (가장 중요)
- 2: 상어의 안전

규칙:
- 사람 안전 단어가 하나라도 있으면 1순위 safety (인기 단어가 같이 있어도)
- 상어 안전의 "강한 단어"가 있으면 2순위 safety
- "약한 단어"(건강, 수온 등)만 있으면, 인기 단어가 없을 때만 2순위 safety
- 구조·이동 작전은 안전 기사로 보지 않는다 (관광객 안내에 가깝다, 10-19 결정)
  구조 기사에는 "해경·통제·물속" 같은 단어가 작전 설명으로 자주 나온다.
  그래서 구조 단어가 있으면, 사람 안전은 "강한 단어"(사고·풍덩 등)가 있을 때만 인정한다.
"""
import os
import re
from pathlib import Path

from collector.article import Article

TOPIC_WORDS = ["부캉이", "상어"]
# "부캉이"가 들어간 검색어로 찾은 기사는 제목에 단어가 없어도 버리지 않는다.
# (흔한 단어가 아니라서, 검색 엔진이 본문에서 찾아낸 것으로 본다)
TRUSTED_WORD = "부캉이"

HUMAN_SAFETY_WORDS = [
    # 물에 들어가거나 빠뜨림
    "풍덩", "퐁당", "빠뜨", "빠져", "물속", "입수", "뛰어들", "추락",
    # 사고·위험
    "사고", "부상자", "다쳐", "위험", "압사", "구급",
    # 통제·규칙·단속
    "통제", "출입", "접근", "금지", "주의", "유의", "당부", "자제", "경고", "과태료",
    "처벌", "단속", "불법 주차", "계도", "안내방송", "수칙", "안전요원",
    # 대응 기관
    "출동", "비상", "해경", "상황실", "관람객 안전", "시민 안전", "안전사고",
    "안전 문제", "안전 우려",
]
# 구조 기사 안에서도 사람 안전으로 볼 강한 단어
HUMAN_SAFETY_STRONG = ["풍덩", "퐁당", "빠뜨", "입수", "뛰어들", "추락", "사고", "부상자",
                       "다쳐", "압사", "구급", "과태료", "처벌", "단속", "불법 주차",
                       "안전사고", "안전 문제", "안전 우려", "관람객 안전", "시민 안전"]

# 구조·이동 작전 기사를 알아보는 단어 (안전 기사가 아님)
RESCUE_WORDS = ["구조", "외해", "유도", "그물", "방류", "물대포", "물줄기", "워터펌프",
                "귀환", "돌려보내", "내보내"]

SHARK_SAFETY_STRONG = [
    "상처", "손상", "지느러미", "출혈", "부상", "스트레스", "이상 행동", "탈진", "폐사",
    # 상어를 해치는 사람의 행동
    "불빛", "랜턴", "손전등", "플래시", "투척", "던지", "던져", "만지", "괴롭", "자극",
]
SHARK_SAFETY_STRONG += [
    # 멸종위기종이라는 정보 → 사람들이 더 조심하게 된다 (10-19 결정)
    "멸종", "보호종", "보호 대상", "보호대상", "정체는", "흑상어였", "흑상어로",
]
SHARK_SAFETY_WEAK = ["건강", "수온", "먹이", "굶"]

# 제외 단어 목록: 한 줄에 단어 하나, '#'으로 시작하는 줄은 설명. 파일이 없으면 제외하지 않는다.
EXCLUDE_FILE = Path(os.environ.get(
    "EXCLUDE_WORDS_FILE", Path(__file__).resolve().parent.parent / "exclude_words.txt"))


def _load_exclude_words(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [w.strip() for w in lines if w.strip() and not w.strip().startswith("#")]


EXCLUDE_WORDS = _load_exclude_words(EXCLUDE_FILE)

POPULAR_WORDS = ["방문객", "관람객", "돌파", "인기", "상표", "굿즈", "관광", "핫플",
                 "명소", "뉴욕타임스", "스타", "체험", "축제", "구경", "관중", "인파"]


def _text(article: Article) -> str:
    # 요약에 섞인 HTML 태그(<a> 등)를 지우고 제목과 합친다
    return article.title + " " + re.sub(r"<[^>]+>", " ", article.summary)


def _found(words: list[str], text: str) -> list[str]:
    return [w for w in words if w in text]


def classify(article: Article) -> Article:
    """기사에 category(꼬리표), priority(우선순위), tags(근거 단어)를 채워서 돌려준다."""
    text = _text(article)
    article.priority = None
    if not any(w in text for w in TOPIC_WORDS) and TRUSTED_WORD not in article.query:
        article.category, article.tags = "unrelated", []
        return article

    if _found(EXCLUDE_WORDS, article.title):  # 제목 기준 (요약에 스치듯 나오는 건 봐준다)
        article.category, article.tags = "excluded", []
        return article

    human = _found(HUMAN_SAFETY_WORDS, text)
    rescue = _found(RESCUE_WORDS, text)
    if rescue:  # 구조 기사면 작전 설명 단어는 빼고 강한 단어만 남긴다
        human = [w for w in human if w in HUMAN_SAFETY_STRONG]
    strong = _found(SHARK_SAFETY_STRONG, text)
    weak = _found(SHARK_SAFETY_WEAK, text)
    popular = _found(POPULAR_WORDS, text)

    if human:
        article.category, article.priority = "safety", 1
    elif strong or (weak and not popular):
        article.category, article.priority = "safety", 2
    elif popular:
        article.category = "popular"
    else:
        article.category = "other"

    article.tags = ([f"사람 안전:{w}" for w in human]
                    + [f"상어 안전:{w}" for w in strong + weak]
                    + ([f"인기:{w}" for w in popular] if article.category == "popular" else []))
    return article
