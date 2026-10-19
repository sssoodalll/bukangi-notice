"""기사 출처 모음. 출처마다 fetch(query) -> list[Article] 를 가진다."""
from collector.sources import bing_news, google_news

SOURCES = {
    "google_news": google_news.fetch,
    "bing_news": bing_news.fetch,
}
