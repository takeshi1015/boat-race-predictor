"""
Failure Analyzer
Analyzes why predictions were wrong to guide model improvement.
"""

from collections import Counter, defaultdict
from typing import Any, Dict, List

from utils.logger import setup_logger

logger = setup_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Failure category constants
# ──────────────────────────────────────────────────────────────────────────────

CATEGORY_PLAYER_DATA_INSUFFICIENT = "player_data_insufficient"
CATEGORY_WEATHER_IMPACT = "weather_impact"
CATEGORY_MOTOR_CHANGE = "motor_change"
CATEGORY_COURSE_PREFERENCE = "course_preference_overlooked"
CATEGORY_START_EXPERT_DELAYED = "start_expert_delayed"
CATEGORY_ACCIDENT = "accident_or_incident"
CATEGORY_BET_MISS = "bet_miss_prediction_was_correct"
CATEGORY_CONFIDENCE_ERROR = "confidence_setting_error"
CATEGORY_UPSET = "general_upset"

_ALL_CATEGORIES = [
    CATEGORY_PLAYER_DATA_INSUFFICIENT,
    CATEGORY_WEATHER_IMPACT,
    CATEGORY_MOTOR_CHANGE,
    CATEGORY_COURSE_PREFERENCE,
    CATEGORY_START_EXPERT_DELAYED,
    CATEGORY_ACCIDENT,
    CATEGORY_BET_MISS,
    CATEGORY_CONFIDENCE_ERROR,
    CATEGORY_UPSET,
]

_CATEGORY_LABELS_JA = {
    CATEGORY_PLAYER_DATA_INSUFFICIENT: "選手データ不足（新加入・久しぶりなど）",
    CATEGORY_WEATHER_IMPACT: "天候の予測外の影響",
    CATEGORY_MOTOR_CHANGE: "モーターの調子が変わった",
    CATEGORY_COURSE_PREFERENCE: "コース得意度を見落とし",
    CATEGORY_START_EXPERT_DELAYED: "スタート巧者なのに出遅れた",
    CATEGORY_ACCIDENT: "着水・転覆などのアクシデント",
    CATEGORY_BET_MISS: "買い目の漏れ（予想は当たってるが買ってない）",
    CATEGORY_CONFIDENCE_ERROR: "信頼度の設定ミス",
    CATEGORY_UPSET: "波乱・一般的な不適中",
}


def classify_failure(prediction: Dict[str, Any], actual_result: List[Any]) -> str:
    """Classify why a prediction failed into a named category.

    Uses heuristic rules based on available prediction metadata.

    Args:
        prediction: The prediction dict (output of a model's ``predict()``).
            May contain optional keys: ``confidence``, ``details``.
        actual_result: The true top-3 finishing order.

    Returns:
        One of the CATEGORY_* string constants.
    """
    confidence: float = float(prediction.get("confidence", 0.5))
    details: Dict[str, Any] = prediction.get("details", {})
    predicted: List[Any] = prediction.get("prediction", [])

    # Very high confidence but wrong → model overconfident / confidence error
    if confidence >= 0.80:
        return CATEGORY_CONFIDENCE_ERROR

    # Check if actual winner was predicted but in wrong position
    if predicted and actual_result:
        winner = actual_result[0]
        if winner in predicted:
            return CATEGORY_BET_MISS

    # Weather encoded in prediction metadata
    method = details.get("method", "")
    if "weather" in method or "rainy" in str(details):
        return CATEGORY_WEATHER_IMPACT

    # Course/lane mismatch heuristic (inner lane won but wasn't predicted)
    if actual_result and actual_result[0] in (1, "1", "P001"):
        # Frame 1 (inner lane) won but wasn't predicted first
        if predicted and predicted[0] != actual_result[0]:
            return CATEGORY_COURSE_PREFERENCE

    # Low-data heuristic: very low confidence may indicate data scarcity
    if confidence < 0.40:
        return CATEGORY_PLAYER_DATA_INSUFFICIENT

    # Medium confidence failure → motor/start issue
    if confidence < 0.60:
        return CATEGORY_MOTOR_CHANGE

    return CATEGORY_UPSET


def analyze_failure(prediction: Dict[str, Any], actual_result: List[Any]) -> Dict[str, Any]:
    """Perform detailed analysis of a single prediction failure.

    Args:
        prediction: The prediction dict.
        actual_result: The true top-3 finishing order.

    Returns:
        Analysis dict with category, label, description, and recommendations.
    """
    category = classify_failure(prediction, actual_result)
    label_ja = _CATEGORY_LABELS_JA.get(category, category)

    predicted = prediction.get("prediction", [])
    confidence = float(prediction.get("confidence", 0.0))

    recommendations = _get_recommendations(category, confidence)

    return {
        "category": category,
        "label": label_ja,
        "predicted": predicted,
        "actual": actual_result,
        "confidence": round(confidence, 4),
        "recommendations": recommendations,
    }


def _get_recommendations(category: str, confidence: float) -> List[str]:
    """Return a list of improvement recommendations for the given category."""
    recs: Dict[str, List[str]] = {
        CATEGORY_PLAYER_DATA_INSUFFICIENT: [
            "新加入・復帰選手のデータ補完ロジックを追加する",
            "最低出走数 (例: 20走以上) のフィルタを設ける",
            "類似成績の選手データで補間する",
        ],
        CATEGORY_WEATHER_IMPACT: [
            "天候フィーチャーの重みを増やす",
            "雨天・強風時は1号艇有利度を下げる補正を入れる",
            "天気予報APIを組み込んで事前に補正する",
        ],
        CATEGORY_MOTOR_CHANGE: [
            "直近のモーター成績（直近5走）を取得して加味する",
            "展示タイムとモーター成績を組み合わせたフィーチャーを作成する",
            "本番前の展示タイムを重視する重みを増やす",
        ],
        CATEGORY_COURSE_PREFERENCE: [
            "選手のコース別成績をフィーチャーに追加する",
            "会場別コース有利度（各会場の1コース勝率）を加味する",
            "ランレーン補正係数を導入する",
        ],
        CATEGORY_START_EXPERT_DELAYED: [
            "スタートタイミング（avg_start_timing）の重みを調整する",
            "フライング/出遅れカウントの影響を大きくする",
            "直近スタート失敗が多い選手のスコアを下げる",
        ],
        CATEGORY_ACCIDENT: [
            "アクシデントは予測困難のため、信頼度スコアに不確実性バッファを追加する",
            "荒れた水面（rough）条件でのベット額を小さくする",
        ],
        CATEGORY_BET_MISS: [
            "買い目フォーメーションを広げる (2・3着を複数選択)",
            "信頼度が高い場合は複数の3連単を購入する",
        ],
        CATEGORY_CONFIDENCE_ERROR: [
            "信頼度の校正（calibration）を実施する",
            "信頼度0.80以上の予測の実際の的中率を測定する",
            "予測確率を現実的な範囲（0.30〜0.70）に正規化する",
        ],
        CATEGORY_UPSET: [
            "信頼度しきい値を上げる（例: 0.65 → 0.70）",
            "アンサンブルモデルの重みを再調整する",
            "過去の外れパターンをモデルの追加フィーチャーとして導入する",
        ],
    }
    return recs.get(category, ["モデルのハイパーパラメータを調整する"])


def analyze_failures(
    failures: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Analyze a batch of failure records to identify dominant patterns.

    Each entry in ``failures`` must have:
        - ``prediction``: model prediction dict
        - ``actual``: actual top-3 result list

    Args:
        failures: List of failure records from a backtest run.

    Returns:
        Summary dict with category counts, rates, and improvement plan.
    """
    if not failures:
        return {
            "total_failures": 0,
            "categories": {},
            "top_category": None,
            "improvement_plan": [],
        }

    category_counts: Counter = Counter()
    category_examples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for record in failures:
        prediction = {
            "prediction": record.get("predicted", []),
            "confidence": record.get("confidence", 0.5),
            "details": record.get("details", {}),
        }
        actual = record.get("actual", [])
        analysis = analyze_failure(prediction, actual)
        cat = analysis["category"]
        category_counts[cat] += 1
        if len(category_examples[cat]) < 3:
            category_examples[cat].append(record)

    total = len(failures)
    categories_summary: Dict[str, Any] = {}
    for cat, count in category_counts.most_common():
        categories_summary[cat] = {
            "count": count,
            "rate": round(count / total, 4),
            "label": _CATEGORY_LABELS_JA.get(cat, cat),
            "recommendations": _get_recommendations(cat, 0.5),
            "examples": category_examples[cat],
        }

    top_cat = category_counts.most_common(1)[0][0] if category_counts else None
    improvement_plan = _build_improvement_plan(category_counts, total)

    logger.info(
        "Failure analysis: %d failures, top category=%s (%d occurrences)",
        total,
        top_cat,
        category_counts[top_cat] if top_cat else 0,
    )

    return {
        "total_failures": total,
        "categories": categories_summary,
        "top_category": top_cat,
        "top_category_label": _CATEGORY_LABELS_JA.get(top_cat, top_cat) if top_cat else None,
        "improvement_plan": improvement_plan,
    }


def _build_improvement_plan(
    category_counts: Counter, total: int
) -> List[Dict[str, Any]]:
    """Build a prioritized improvement plan from category counts.

    Args:
        category_counts: Counter of failure categories.
        total: Total number of failures.

    Returns:
        List of improvement action dicts ordered by priority.
    """
    plan: List[Dict[str, Any]] = []
    for cat, count in category_counts.most_common():
        rate = count / total if total > 0 else 0.0
        if rate < 0.05:
            continue  # Skip very rare categories
        plan.append(
            {
                "priority": len(plan) + 1,
                "category": cat,
                "label": _CATEGORY_LABELS_JA.get(cat, cat),
                "occurrence_rate": round(rate, 4),
                "actions": _get_recommendations(cat, 0.5),
            }
        )
    return plan


def improvement_summary(analysis_result: Dict[str, Any]) -> str:
    """Format a human-readable improvement summary from an analysis result.

    Args:
        analysis_result: Output of :func:`analyze_failures`.

    Returns:
        Multi-line string summary.
    """
    lines = []
    total = analysis_result.get("total_failures", 0)
    lines.append(f"外れ分析サマリー: {total}件の不適中")
    lines.append("")

    categories = analysis_result.get("categories", {})
    for cat_data in sorted(
        categories.values(), key=lambda x: x["count"], reverse=True
    ):
        rate_pct = f"{cat_data['rate'] * 100:.1f}%"
        lines.append(f"  【{cat_data['label']}】: {cat_data['count']}件 ({rate_pct})")

    lines.append("")
    lines.append("改善アクション（優先順）:")
    for action in analysis_result.get("improvement_plan", []):
        lines.append(f"  {action['priority']}. {action['label']}")
        for a in action["actions"][:2]:
            lines.append(f"     → {a}")

    return "\n".join(lines)
