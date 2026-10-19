"""수집기를 한 번 돌려 보는 실행 파일.

실행:  python run_collect.py
"""
import sys
from collections import Counter

from collector import collect

sys.stdout.reconfigure(encoding="utf-8")

articles = collect(keep_unrelated=True)
count = Counter(a.category for a in articles)
print(f"모은 기사: {len(articles)}건 (중복 제거 후)")
for name in ("google_news", "bing_news"):
    print(f"  - {name}: {sum(a.source == name for a in articles)}건")
print(f"꼬리표: 안전 {count['safety']} / 인기 {count['popular']} / "
      f"기타 {count['other']} / 관계없음(버림) {count['unrelated']}")

LABELS = {"safety": "🟢 안전", "other": "⚪ 기타", "popular": "🔵 인기", "unrelated": "❌ 관계없음"}
for cat in ("safety", "other", "popular", "unrelated"):
    group = [a for a in articles if a.category == cat]
    print(f"\n===== {LABELS[cat]} ({len(group)}건) =====")
    for a in group[:15]:
        tags = ", ".join(t.split(":")[1] for t in a.tags[:3])
        print(f"[{a.published_at:%m-%d %H:%M}] {a.title}  ({a.press})" + (f"  ← {tags}" if tags else ""))
