"""판정기를 시험하고, 배우고, 검수 전 기사에 점수를 매긴다.

실행:  python run_judge.py
1) 시험: 사람 검수 기록 중 일부를 숨기고 맞히는지 본다 (기준선 여러 개)
2) 학습: 검수 기록 전체로 배워서 data/judge.joblib 에 저장
3) 점수: 검수 전 기사마다 승인 확률을 장부에 적는다 (상태는 바꾸지 않는다)
"""
import sys

from collector import judge, store

sys.stdout.reconfigure(encoding="utf-8")

conn = store.connect()
rows = store.human_reviewed(conn)

print("===== 1) 시험 (배운 적 없는 기사로) =====")
for high, low in ((0.9, 0.1), (0.8, 0.2), (0.7, 0.3)):
    r = judge.evaluate(rows, high=high, low=low)
    print(f"\n[자동 승인 ≥ {high} / 자동 반려 ≤ {low}]")
    print(f"  사람 없이 처리: {r['auto_total']}/{r['examples']}건 ({r['auto_ratio']:.0%}) "
          f"→ 그중 맞힘 {r['auto_correct']}/{r['auto_total']}")
    for t in r["missed_approvals"]:
        print(f"  ⚠️ 승인할 기사를 자동 반려: {t[:60]}")
    for t in r["wrong_approvals"]:
        print(f"  ⚠️ 반려할 기사를 자동 승인: {t[:60]}")
print(f"\n참고: 전부 0.5 기준으로 판정하면 정확도 {r['accuracy']:.0%} "
      f"/ 단어 규칙만 쓰면 {r['rule_accuracy']:.0%}  (검수 {r['examples']}건: "
      f"승인 {r['approved']}, 반려 {r['rejected']})")

print("\n===== 2) 학습 =====")
info = judge.train(rows)
print(f"  {info['examples']}건으로 배워서 저장했어요.")

print("\n===== 3) 검수 전 기사에 점수 매기기 =====")
pending = store.list_articles(conn, status="pending")
scores = judge.score(judge.load(), pending)
store.set_scores(conn, {a["id"]: s for a, s in zip(pending, scores)})
ranked = sorted(zip(pending, scores), key=lambda x: -x[1])
print(f"  {len(pending)}건에 점수를 적었어요. 승인 확률 높은 순 5건 / 낮은 순 5건:")
for a, s in ranked[:5] + [(None, None)] + ranked[-5:]:
    print("   ..." if a is None else f"   {s:.2f}  {a['title'][:58]}")
