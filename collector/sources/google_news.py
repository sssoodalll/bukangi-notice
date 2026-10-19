"""구글 뉴스 RSS에서 기사 가져오기. 키 발급이 필요 없다."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import feedparser

from collector.article import Article

RSS_URL = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"


def fetch(query: str) -> list[Article]:
    feed = feedparser.parse(RSS_URL.format(q=quote(query)))
    articles = []
    for e in feed.entries:
        press = e.get("source", {}).get("title", "")
        title = e.title
        # 구글 뉴스 제목은 "제목 - 언론사" 형태라 뒤의 언론사 이름을 잘라 낸다
        if press and title.endswith(" - " + press):
            title = title[: -len(" - " + press)]
        try:
            published = parsedate_to_datetime(e.published)
        except (AttributeError, TypeError, ValueError):
            published = datetime.now(timezone.utc)
        articles.append(Article(
            title=title.strip(),
            url=e.link,
            press=press,
            published_at=published,
            source="google_news",
            query=query,
        ))
    return articles
