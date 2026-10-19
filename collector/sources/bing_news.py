"""Bing 뉴스 RSS에서 기사 가져오기. 키 발급이 필요 없다."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, quote, urlparse

import feedparser
import httpx

from collector.article import Article

RSS_URL = "https://www.bing.com/news/search?q={q}&format=rss"


def _real_url(link: str) -> str:
    # Bing 링크는 "bing.com/...?url=진짜주소" 형태라 진짜 기사 주소만 꺼낸다
    real = parse_qs(urlparse(link).query).get("url")
    return real[0] if real else link


def fetch(query: str) -> list[Article]:
    resp = httpx.get(RSS_URL.format(q=quote(query)),
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    feed = feedparser.parse(resp.content)
    articles = []
    for e in feed.entries:
        try:
            published = parsedate_to_datetime(e.published)
        except (AttributeError, TypeError, ValueError):
            published = datetime.now(timezone.utc)
        articles.append(Article(
            title=e.title.strip(),
            url=_real_url(e.link),
            press=e.get("news_source", ""),
            published_at=published,
            source="bing_news",
            query=query,
            summary=e.get("summary", ""),
        ))
    return articles
