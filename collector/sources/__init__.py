"""기사 출처 모음. 출처마다 fetch(query) -> list[Article] 를 가진다.

새 출처를 붙이기 전에 그 사이트의 robots.txt와 이용약관을 확인한다.
- 구글 뉴스 RSS는 10-19에 뺐다: robots.txt가 /rss/ 경로를 허용하지 않는다.
"""
from collector.sources import bing_news

SOURCES = {
    "bing_news": bing_news.fetch,
}
