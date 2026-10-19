"""사람 검수 기록으로 배우는 판정기 (머신러닝).

- train():    사람이 승인/반려한 기사로 "승인될 확률"을 배운다 → data/judge.joblib
- score():    기사마다 승인 확률(0~1)을 매긴다
- evaluate(): 배운 적 없는 기사로 시험을 봐서 얼마나 맞히는지 잰다 (교차 검증)

판정 방법은 바꿔 끼울 수 있다. 다른 판정기(로컬 AI, Claude 등)도
"기사 → 승인 확률"만 돌려주면 같은 자리에 쓸 수 있다.
"""
import re
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline

MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "judge.joblib"
MIN_EXAMPLES = 20   # 승인·반려가 합쳐 이만큼은 있어야 배운다
MIN_PER_CLASS = 5   # 승인도, 반려도 최소 이만큼은 있어야 한다


def _features(row: dict) -> str:
    """기사 한 건을 판정기가 읽을 글자로 바꾼다: 제목 + 요약 + 단어 규칙 결과."""
    summary = re.sub(r"<[^>]+>", " ", row.get("summary") or "")
    rule = f"규칙{row.get('category')}{row.get('priority') or ''}"
    return f"{row['title']} {summary} {rule}"


def _new_model():
    # 한국어는 띄어쓰기가 들쭉날쭉해서, 단어 대신 글자 2~4개 묶음으로 본다
    return make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True),
        LogisticRegression(class_weight="balanced", max_iter=1000),
    )


def _dataset(rows: list[dict]) -> tuple[list[str], np.ndarray]:
    X = [_features(r) for r in rows]
    y = np.array([1 if r["status"] == "approved" else 0 for r in rows])
    return X, y


def _check_enough(y: np.ndarray) -> None:
    if len(y) < MIN_EXAMPLES or min(y.sum(), len(y) - y.sum()) < MIN_PER_CLASS:
        raise ValueError(f"검수 기록이 부족해요: 전체 {len(y)}건 (승인 {y.sum()}, 반려 {len(y) - y.sum()}). "
                         f"전체 {MIN_EXAMPLES}건, 승인·반려 각 {MIN_PER_CLASS}건 이상 필요해요.")


def train(rows: list[dict], path: Path = MODEL_PATH) -> dict:
    """사람이 검수한 기사(rows)로 배우고 파일로 저장한다."""
    X, y = _dataset(rows)
    _check_enough(y)
    model = _new_model().fit(X, y)
    info = {"trained_at": datetime.now(timezone.utc).isoformat(),
            "examples": len(y), "approved": int(y.sum())}
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "info": info}, path)
    return info


def load(path: Path = MODEL_PATH):
    """저장된 판정기를 불러온다. 아직 없으면 None."""
    return joblib.load(path) if path.exists() else None


def score(saved, rows: list[dict]) -> list[float]:
    """기사마다 승인 확률(0~1)."""
    if not rows:
        return []
    return saved["model"].predict_proba([_features(r) for r in rows])[:, 1].tolist()


def evaluate(rows: list[dict], high: float = 0.7, low: float = 0.3, folds: int = 5) -> dict:
    """배운 적 없는 기사로 시험을 본다 (5등분해서 4개로 배우고 1개로 시험, 5번 반복).

    high 이상은 자동 승인, low 이하는 자동 반려, 그 사이는 사람에게 넘긴다고 가정하고 잰다.
    """
    X, y = _dataset(rows)
    _check_enough(y)
    folds = min(folds, int(min(y.sum(), len(y) - y.sum())))
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=0)
    p = cross_val_predict(_new_model(), X, y, cv=cv, method="predict_proba")[:, 1]

    auto_ok = (p >= high) | (p <= low)
    auto_pred = (p >= high).astype(int)
    rule_pred = np.array([1 if r["category"] == "safety" else 0 for r in rows])
    return {
        "examples": len(y), "approved": int(y.sum()), "rejected": int(len(y) - y.sum()),
        "accuracy": float(((p >= 0.5).astype(int) == y).mean()),        # 0.5 기준으로 다 판정할 때
        "rule_accuracy": float((rule_pred == y).mean()),                  # 단어 규칙만 쓸 때
        "auto_ratio": float(auto_ok.mean()),                              # 사람 없이 처리되는 비율
        "auto_correct": int((auto_pred[auto_ok] == y[auto_ok]).sum()),
        "auto_total": int(auto_ok.sum()),
        # 가장 위험한 실수: 사람이 승인한 기사를 AI가 자동 반려
        "missed_approvals": [rows[i]["title"] for i in np.where(auto_ok & (p <= low) & (y == 1))[0]],
        # 사람이 반려한 기사를 AI가 자동 승인
        "wrong_approvals": [rows[i]["title"] for i in np.where(auto_ok & (p >= high) & (y == 0))[0]],
        "high": high, "low": low,
    }
