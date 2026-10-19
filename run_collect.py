"""수집 로봇을 한 번 돌려 보는 실행 파일.

실행:  python run_collect.py
"""
import sys

from collector import collect

sys.stdout.reconfigure(encoding="utf-8")

articles = collect()
print(f"모은 기사: {len(articles)}건 (중복 제거 후)")
for name in ("google_news", "bing_news"):
    print(f"  - {name}: {sum(a.source == name for a in articles)}건")
print()
for a in articles[:20]:
    print(f"[{a.published_at:%m-%d %H:%M}] {a.title}  ({a.press})")
