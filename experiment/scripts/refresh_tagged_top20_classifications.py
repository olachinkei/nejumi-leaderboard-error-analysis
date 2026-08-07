from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION_DIR = ROOT / "outputs" / "llm" / "by_benchmark"
COMMON_PATH = ROOT / "data" / "processed" / "common_failures.parquet"
CROSS_PATH = ROOT / "outputs" / "llm" / "cross_benchmark" / "synthesis.json"

ADDITIONS: dict[str, list[dict[str, Any]]] = {
    "bfcl": [
        {
            "item_id": "multi_turn_miss_func_85",
            "category_id": "multiturn_execution",
            "cause_axis": "model_capability",
            "confidence": 0.94,
            "concise_rationale": (
                "複数ターンにまたがる距離・走行可否確認と、給油・施錠・制動・始動の"
                "依存順序を完全には保持できていない。"
            ),
            "evidence_item_ids": ["multi_turn_miss_func_85"],
            "improvement_candidate": (
                "ターン別の状態台帳を保持し、未実行の必須callと依存順序を実行前に照合する。"
            ),
        },
        {
            "item_id": "multi_turn_miss_param_104",
            "category_id": "multiturn_execution",
            "cause_axis": "model_capability",
            "confidence": 0.92,
            "concise_rationale": (
                "会社名から得た銘柄コードを後続ターンへ引き継ぎ、追加後にwatchlist全体を"
                "取得する一連の操作を正しいターンで完了できていない。"
            ),
            "evidence_item_ids": ["multi_turn_miss_param_104"],
            "improvement_candidate": (
                "エンティティ解決結果と操作済み状態をターン間で保持し、要求された後処理まで"
                "call checklistで検証する。"
            ),
        },
    ],
    "hle": [
        {
            "item_id": "67253a6aab5670ae51f28912",
            "category_id": "reference_conflict",
            "cause": "reference_or_evaluator",
            "confidence": 0.97,
            "concise_rationale": (
                "最多回答のSMILESは参照と同じC8H18N6骨格を別の等価表記で示しており、"
                "judgeまたは文字列表現の同値性判定に起因する偽陰性が疑われる。"
            ),
            "evidence_item_ids": ["67253a6aab5670ae51f28912"],
            "improvement_candidate": (
                "SMILESを分子グラフへ正規化し、組成・結合・官能基制約を化学情報学ツールで"
                "検証してから採点する。"
            ),
        }
    ],
    "jaster": [
        {
            "item_id": "jamp|21|exact_match",
            "item_key": "c41bd6b838a4a310640b1685ddb581c96735f5a7692421a6bbf5f7a7cdc92d78",
            "evaluation_condition": "0shot:exact_match",
            "category": "linguistic_inference_boundary",
            "cause_axis": "model_capability",
            "confidence": 0.91,
            "evidence_item_ids": ["jamp|21|exact_match"],
            "concise_rationale": (
                "14時以来継続している状態から15時時点の同状態を含意する時間推論で、"
                "16ランがcontradictionを選んだ。"
            ),
            "improvement_candidate": (
                "継続相と時点包含関係を明示した最小対を追加し、時間区間の推論を評価する。"
            ),
        },
        {
            "item_id": "jcola-out-of-domain|57|exact_match",
            "item_key": "51543d5197ae10a2d5b163f8ba28c8aadbf741abd524a671f107a18a69e4c4df",
            "evaluation_condition": "0shot:exact_match",
            "category": "linguistic_inference_boundary",
            "cause_axis": "mixed",
            "confidence": 0.88,
            "evidence_item_ids": ["jcola-out-of-domain|57|exact_match"],
            "concise_rationale": (
                "相互表現と与格句の係り方が不自然に見える文で、文法性注釈1に対し16ランが"
                "0を選んでおり、細粒度の容認度境界で分岐している。"
            ),
            "improvement_candidate": (
                "複数話者の容認度評定を保存し、二値ラベルに加えて評定分布も公開する。"
            ),
        },
        {
            "item_id": "kuci|40|exact_match",
            "item_key": "94a434a18110df41739e395648d130f7237c083e55a3abab5817e4919e66e5b0",
            "evaluation_condition": "0shot:exact_match",
            "category": "underspecified_or_versioned",
            "cause_axis": "ambiguous_or_underspecified",
            "confidence": 0.9,
            "evidence_item_ids": ["kuci|40|exact_match"],
            "concise_rationale": (
                "「ちょっと気を抜くと」には参照の「ペース落ちる」だけでなく"
                "「体調を崩します」も自然に続き、文脈なしでは一意に選びにくい。"
            ),
            "improvement_candidate": (
                "前後文脈を追加するか、複数の自然な後続候補を正解として許容する。"
            ),
        },
    ],
    "jtruthfulqa": [
        {
            "item_id": "356",
            "category_id": "reference_defect",
            "cause": "data_or_version",
            "confidence": 0.93,
            "concise_rationale": (
                "正解候補には「完全だ」がある一方、同じ参照欄に「こたふ／いらふ」の"
                "無関係な説明が混入しており、参照データの汚染が疑われる。"
            ),
            "evidence_item_ids": ["356"],
            "improvement_candidate": (
                "参照候補を設問単位で再監査し、無関係な回答候補を除去する。"
            ),
        },
        {
            "item_id": "414",
            "category_id": "semantic_match_failure",
            "cause": "reference_or_evaluator",
            "confidence": 0.99,
            "concise_rationale": (
                "回答の26.9°Cは参照の約27°Cと同値であるのに、多数が不正解判定されている。"
            ),
            "evidence_item_ids": ["414"],
            "improvement_candidate": (
                "数値回答を単位付きで正規化し、妥当な丸め誤差を許容して採点する。"
            ),
        },
        {
            "item_id": "508",
            "category_id": "semantic_match_failure",
            "cause": "reference_or_evaluator",
            "confidence": 0.99,
            "concise_rationale": (
                "最多回答「箱根山」は参照候補と文字どおり一致しており、classifierの"
                "偽陰性が強く疑われる。"
            ),
            "evidence_item_ids": ["508"],
            "improvement_candidate": (
                "参照候補との正規化完全一致をclassifierより先に判定し、明白な一致を保護する。"
            ),
        },
    ],
}


def category_of(assignment: dict[str, Any]) -> str:
    return str(assignment.get("category_id", assignment.get("category", "other")))


def identity(benchmark: str, assignment: dict[str, Any]) -> str:
    key = "item_key" if benchmark == "jaster" else "item_id"
    return str(assignment.get(key, ""))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def refresh_classifications(common: pd.DataFrame) -> dict[str, int]:
    counts: dict[str, int] = {}
    for benchmark, expected in common.groupby("benchmark", sort=True):
        path = CLASSIFICATION_DIR / f"{benchmark}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        key_column = "item_key" if benchmark == "jaster" else "item_id"
        expected_ids = expected[key_column].astype(str).tolist()
        expected_set = set(expected_ids)
        assignments = {
            identity(benchmark, assignment): assignment
            for assignment in payload["assignments"]
            if identity(benchmark, assignment) in expected_set
        }
        for assignment in ADDITIONS.get(benchmark, []):
            assignments[identity(benchmark, assignment)] = assignment
        missing = expected_set - assignments.keys()
        if missing:
            raise RuntimeError(f"{benchmark}: unclassified items remain: {sorted(missing)}")
        payload["assignments"] = [assignments[item_id] for item_id in expected_ids]

        current_item_ids = set(expected["item_id"].astype(str))
        by_category: dict[str, list[dict[str, Any]]] = {}
        for assignment in payload["assignments"]:
            by_category.setdefault(category_of(assignment), []).append(assignment)
        for taxonomy in payload["taxonomy"]:
            category_id = taxonomy["category_id"]
            representatives = [
                item_id
                for item_id in taxonomy.get("representative_item_ids", [])
                if str(item_id) in current_item_ids
            ]
            target_count = max(1, len(representatives))
            candidates = sorted(
                by_category.get(category_id, []),
                key=lambda assignment: float(assignment.get("confidence", 0)),
                reverse=True,
            )
            for assignment in candidates:
                item_id = str(assignment["item_id"])
                if item_id not in representatives:
                    representatives.append(item_id)
                if len(representatives) >= target_count:
                    break
            taxonomy["representative_item_ids"] = representatives

        write_json(path, payload)
        counts[benchmark] = len(payload["assignments"])
    return counts


def refresh_cross_synthesis(classification_counts: dict[str, int]) -> None:
    payload = json.loads(CROSS_PATH.read_text(encoding="utf-8"))
    cross_totals: dict[str, int] = {}
    for benchmark, mappings in payload["benchmark_category_mapping"].items():
        classification = json.loads(
            (CLASSIFICATION_DIR / f"{benchmark}.json").read_text(encoding="utf-8")
        )
        category_counts: dict[str, int] = {}
        for assignment in classification["assignments"]:
            category = category_of(assignment)
            category_counts[category] = category_counts.get(category, 0) + 1
        for mapping in mappings:
            count = category_counts.get(mapping["category_id"], 0)
            mapping["item_count"] = count
            cross_id = mapping["cross_taxonomy_id"]
            cross_totals[cross_id] = cross_totals.get(cross_id, 0) + count
    for taxonomy in payload["cross_taxonomy"]:
        taxonomy["item_count"] = cross_totals.get(taxonomy["id"], 0)
    payload["scope"]["assignment_count"] = sum(classification_counts.values())
    write_json(CROSS_PATH, payload)


def main() -> None:
    common = pd.read_parquet(COMMON_PATH)
    classification_counts = refresh_classifications(common)
    refresh_cross_synthesis(classification_counts)
    print(
        f"Refreshed {sum(classification_counts.values())} assignments "
        f"across {len(classification_counts)} benchmarks."
    )


if __name__ == "__main__":
    main()
