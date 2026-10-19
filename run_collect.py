"""수집기를 한 번 돌리고, 결과를 장부(data/articles.db)에 저장한다.

실행:  python run_collect.py
"""
import sys
from collections import Counter

from collector import collect, store

sys.stdout.reconfigure(encoding="utf-8")

articles = collect()
count = Counter(a.category for a in articles)
print(f"이번에 모은 기사: {len(articles)}건 "
      f"(안전 {count['safety']} / 기타 {count['other']} / 인기 {count['popular']})")

conn = store.connect()
new = store.save(conn, articles)
print(f"장부에 새로 들어간 기사: {new}건 (나머지는 이미 있던 기사)")

total = store.count_by_status(conn)
print(f"장부 전체: 검수 전 {total.get('pending', 0)} / "
      f"승인 {total.get('approved', 0)} / 반려 {total.get('rejected', 0)}")

print("\n===== 검수 전 안전 기사 (최신 10건) =====")
for a in store.list_articles(conn, status="pending", category="safety")[:10]:
    tags = ", ".join(t.split(":")[1] for t in a["tags"][:3])
    print(f"#{a['id']:<4} [{a['published_at'][5:16].replace('T', ' ')}] {a['title']}  ({a['press']})  ← {tags}")
