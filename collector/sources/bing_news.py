"""Bing 뉴스 RSS에서 기사 가져오기. 키 발급이 필요 없고, robots.txt에서 허용된 경로다."""
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, quote, urlparse

import feedparser
import httpx

from collector.article import Article

RSS_URL = "https://www.bing.com/news/search?q={q}&format=rss&first={first}"
PAGE_SIZE = 10   # Bing은 한 쪽에 10~12건을 준다
PAGES = 2        # 검색어마다 몇 쪽까지 받을지
DELAY = 1.0      # 요청 사이에 쉬는 시간(초). 상대 서버에 부담을 주지 않으려고


def _real_url(link: str) -> str:
    # Bing 링크는 "bing.com/...?url=진짜주소" 형태라 진짜 기사 주소만 꺼낸다
    real = parse_qs(urlparse(link).query).get("url")
    return real[0] if real else link


def _parse(entry, query: str) -> Article:
    try:
        published = parsedate_to_datetime(entry.published)
    except (AttributeError, TypeError, ValueError):
        published = datetime.now(timezone.utc)
    return Article(
        title=entry.title.strip(),
        url=_real_url(entry.link),
        press=entry.get("news_source", ""),
        published_at=published,
        source="bing_news",
        query=query,
        summary=entry.get("summary", ""),
    )


def fetch(query: str) -> list[Article]:
    articles, seen = [], set()
    for page in range(PAGES):
        resp = httpx.get(RSS_URL.format(q=quote(query), first=page * PAGE_SIZE + 1),
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        entries = feedparser.parse(resp.content).entries
        new = [e for e in entries if e.link not in seen]
        if not new:
            break
        seen.update(e.link for e in new)
        articles += [_parse(e, query) for e in new]
        time.sleep(DELAY)
    return articles
