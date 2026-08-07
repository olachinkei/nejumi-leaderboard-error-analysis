from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from jinja2 import Template

from leaderboard_analysis.common import MANIFEST_DIR, PROJECT_ROOT, read_json, write_json

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
LLM_DIR = PROJECT_ROOT / "outputs" / "llm" / "by_benchmark"

TEMPLATE = Template(
    """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>誤答傾向分析を通じたベンチマークの妥当性検証</title>
  <style>
    :root { color-scheme: light; --ink:#17212b; --muted:#5b6773; --line:#d8dee6; --accent:#4263eb; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans JP",sans-serif; color:var(--ink); background:#f5f7fa; }
    main { max-width:1180px; margin:auto; padding:40px 24px 80px; }
    h1 { font-size:clamp(28px,4vw,48px); line-height:1.18; margin:0 0 12px; }
    h2 { margin-top:48px; padding-top:12px; border-top:1px solid var(--line); }
    .lede,.note { color:var(--muted); max-width:900px; line-height:1.75; }
    .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; margin:28px 0; }
    .card,.panel { background:white; border:1px solid var(--line); border-radius:14px; padding:18px; box-shadow:0 5px 18px rgba(23,33,43,.04); }
    .value { font-size:32px; font-weight:750; color:var(--accent); }
    .label { color:var(--muted); margin-top:4px; }
    table { border-collapse:collapse; width:100%; font-size:14px; background:white; }
    th,td { border-bottom:1px solid var(--line); padding:9px 10px; text-align:left; }
    th { position:sticky; top:0; background:#eef2ff; }
    .scroll { overflow:auto; max-height:520px; border:1px solid var(--line); border-radius:12px; }
    code { background:#edf0f4; padding:2px 5px; border-radius:4px; }
  </style>
</head>
<body><main>
  <h1>誤答傾向分析を通じた<br>ベンチマークの妥当性検証</h1>
  <p class="lede">Nejumi LLM Leaderboard 4で<code>leaderboard</code> tagを持つrunだけを対象に、
  TOTAL_SCORE上位20 runを2026年7月31日JST時点で固定し、
  20/20 runで判定可能かつ16 run以上が誤答した問題を抽出した。問題文・参照解答・モデル回答は
  公開版へ埋め込まず、集計値とitem IDだけを掲載する。</p>
  <div class="cards">
    {% for card in cards %}<div class="card"><div class="value">{{ card.value }}</div><div class="label">{{ card.label }}</div></div>{% endfor %}
  </div>

  <h2>分析対象</h2>
  <div class="scroll">{{ top20_table }}</div>

  <h2>ベンチマーク別coverageと共通誤答</h2>
  <p class="note">連続scoreに公式の失敗境界がないbenchmarkは二値item数を0とし、共通誤答へ含めていない。</p>
  <div class="scroll">{{ benchmark_table }}</div>
  <div class="panel">{{ benchmark_figure }}</div>

  <h2>70%・80%・90%の閾値感度</h2>
  <div class="panel">{{ sensitivity_figure }}</div>

  <h2>共通誤答の問題×run行列</h2>
  <p class="note">赤が誤答、青が正答、灰色が欠損・運用エラーである。行はbenchmarkと誤答率で並べた。</p>
  <div class="panel">{{ heatmap }}</div>

  {% if category_table %}
  <h2>LLM支援によるfailure taxonomy</h2>
  <p class="note">gpt-5.6-sol（reasoning high）による仮説分類であり、人手による全件監査済みではない。</p>
  <div class="scroll">{{ category_table }}</div>
  <div class="panel">{{ category_figure }}</div>
  <div class="panel">{{ cause_figure }}</div>
  {% endif %}

  {% if cross_table %}
  <h2>ベンチマーク横断taxonomy</h2>
  <p class="note">benchmark別カテゴリを8つの横断パターンへ対応付けた。件数は元の{{ classification_count }} assignmentと一致する。</p>
  <div class="scroll">{{ cross_table }}</div>
  <div class="panel">{{ cross_figure }}</div>
  {% endif %}

  <h2>方法と制約</h2>
  <ul>
    <li>project内の<code>leaderboard</code> tag付き102 runをserver-side filterで取得し、各runの個別tableからTOTAL_SCORE順を再構成した。</li>
    <li>公開レポートspecと統合tableは出典として保存したが、統合tableに未反映のtag付きrunがあったため順位決定には使っていない。</li>
    <li>440 output tableをsummary pointer SHA、artifact ID/version/digest、manifest entryで照合した。</li>
    <li>Dev表140件と先頭12行のみのToxicity表20件は主解析から除外した。</li>
    <li>HLEは194 item中183 itemのみ20 runすべてで判定可能、SWE-benchは80中18 itemのみであった。</li>
    <li>同一モデル名のrerunを別runとして保持しており、観測は独立標本ではない。</li>
    <li>token量は一部tableだけで取得でき、金額・benchmark別時間・resource-hoursは定量化していない。</li>
  </ul>
  <p class="note">Snapshot: <code>{{ snapshot_id }}</code> / report spec:
  <code>{{ report_hash }}</code> / evaluator commit: <code>{{ evaluator_commit }}</code></p>
</main></body></html>"""
)


def html_table(frame: pd.DataFrame) -> str:
    return frame.to_html(index=False, escape=True, border=0)


def load_assignments() -> pd.DataFrame:
    rows = []
    if not LLM_DIR.exists():
        return pd.DataFrame()
    for path in sorted(LLM_DIR.glob("*.json")):
        payload = read_json(path)
        benchmark = payload.get("benchmark", path.stem)
        for assignment in payload.get("assignments", []):
            rows.append(
                {
                    "benchmark": benchmark,
                    "item_key": assignment.get("item_key", ""),
                    "item_id": assignment.get("item_id", ""),
                    "category": assignment.get("category_id", assignment.get("category", "other")),
                    "cause": assignment.get("cause_axis", assignment.get("cause", "uncertain")),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    top20 = pd.read_csv(MANIFEST_DIR / "top20_runs.csv")
    counts = pd.read_csv(TABLE_DIR / "benchmark_counts.csv")
    sensitivity = pd.read_csv(PROCESSED_DIR / "threshold_sensitivity.csv")
    results = pd.read_parquet(PROCESSED_DIR / "item_results.parquet")
    common = pd.read_parquet(PROCESSED_DIR / "common_failures.parquet")
    snapshot = read_json(MANIFEST_DIR / "snapshot.json")

    cards = [
        {"value": "20", "label": "leaderboard tag内の上位run数"},
        {"value": f"{results.item_key.nunique():,}", "label": "正規化item数"},
        {
            "value": f"{int(counts.fully_evaluable_items.sum()):,}",
            "label": "20/20判定可能な二値item",
        },
        {"value": f"{len(common):,}", "label": "16/20以上の共通誤答"},
    ]
    top_display = top20[["rank", "model_name", "run_id", "total_score", "state"]].copy()
    top_display["total_score"] = top_display["total_score"].map(lambda value: f"{value:.4f}")

    counts_plot = counts[counts["fully_evaluable_items"] > 0].copy()
    figure = px.bar(
        counts_plot,
        x="benchmark",
        y=["fully_evaluable_items", "common_failures"],
        barmode="group",
        labels={"value": "items", "variable": "区分"},
    )
    figure.update_layout(margin=dict(l=20, r=20, t=30, b=20))

    sensitivity_total = sensitivity.groupby(["threshold", "required_wrong_of_20"], as_index=False)[
        "common_failure_count"
    ].sum()
    sensitivity_figure = px.line(
        sensitivity_total,
        x="threshold",
        y="common_failure_count",
        markers=True,
        text="common_failure_count",
    )
    sensitivity_figure.update_layout(margin=dict(l=20, r=20, t=30, b=20))

    common_keys = set(common["item_key"])
    matrix_source = results[results["item_key"].isin(common_keys)].copy()
    order = common.sort_values(
        ["benchmark", "wrong_rate", "item_key"], ascending=[True, False, True]
    )
    matrix_source["value"] = matrix_source["is_correct"].map({True: 1, False: 0})
    matrix = matrix_source.pivot(index="item_key", columns="rank", values="value").reindex(
        order["item_key"]
    )
    heatmap = go.Figure(
        go.Heatmap(
            z=matrix.to_numpy(dtype=float, na_value=float("nan")),
            x=[f"M{int(value):02d}" for value in matrix.columns],
            y=[f"{row.benchmark}:{row.item_id}" for row in order.itertuples()],
            colorscale=[[0, "#d9485f"], [0.49, "#d9485f"], [0.5, "#4c78a8"], [1, "#4c78a8"]],
            zmin=0,
            zmax=1,
            colorbar=dict(tickvals=[0, 1], ticktext=["wrong", "correct"]),
        )
    )
    heatmap.update_layout(height=900, margin=dict(l=160, r=20, t=30, b=50))

    assignments = load_assignments()
    category_table = category_figure = cause_figure = ""
    cross_table = cross_figure = ""
    category_counts: list[dict[str, object]] = []
    if not assignments.empty:
        category_counts_frame = (
            assignments.groupby(["benchmark", "category"]).size().reset_index(name="items")
        )
        category_counts = category_counts_frame.to_dict(orient="records")
        category_table = html_table(category_counts_frame)
        category_figure = px.bar(
            category_counts_frame,
            x="benchmark",
            y="items",
            color="category",
            barmode="stack",
        ).to_html(full_html=False, include_plotlyjs=False)
        causes = assignments.groupby(["benchmark", "cause"]).size().reset_index(name="items")
        cause_figure = px.bar(
            causes, x="benchmark", y="items", color="cause", barmode="stack"
        ).to_html(full_html=False, include_plotlyjs=False)

    cross_path = PROJECT_ROOT / "outputs" / "llm" / "cross_benchmark" / "synthesis.json"
    cross_patterns: list[dict[str, object]] = []
    if cross_path.exists():
        cross = read_json(cross_path)
        cross_patterns = cross.get("cross_taxonomy", [])
        cross_display = pd.DataFrame(
            [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "items": item["item_count"],
                    "supporting_benchmarks": ", ".join(item["supporting_benchmarks"]),
                }
                for item in cross_patterns
            ]
        )
        cross_table = html_table(cross_display)
        mapping_rows = [
            {
                "benchmark": benchmark,
                "cross_taxonomy": mapping["cross_taxonomy_id"],
                "items": mapping["item_count"],
            }
            for benchmark, mappings in cross["benchmark_category_mapping"].items()
            for mapping in mappings
        ]
        mapping_frame = pd.DataFrame(mapping_rows)
        cross_figure = px.bar(
            mapping_frame,
            x="benchmark",
            y="items",
            color="cross_taxonomy",
            barmode="stack",
        ).to_html(full_html=False, include_plotlyjs=False)

    facts = {
        "snapshot_id": top20["snapshot_id"].iloc[0],
        "report_spec_hash": top20["report_spec_hash"].iloc[0],
        "top20_run_count": len(top20),
        "normalized_item_count": int(results.item_key.nunique()),
        "fully_evaluable_binary_items": int(counts.fully_evaluable_items.sum()),
        "common_failure_count": len(common),
        "benchmark_counts": counts.to_dict(orient="records"),
        "threshold_totals": sensitivity_total.to_dict(orient="records"),
        "classification_assignment_count": len(assignments),
        "classification_category_counts": category_counts,
        "cross_taxonomy": cross_patterns,
    }
    write_json(PROJECT_ROOT / "outputs" / "paper_facts.json", facts)
    html = TEMPLATE.render(
        cards=cards,
        top20_table=html_table(top_display),
        benchmark_table=html_table(counts),
        benchmark_figure=figure.to_html(full_html=False, include_plotlyjs="inline"),
        sensitivity_figure=sensitivity_figure.to_html(full_html=False, include_plotlyjs=False),
        heatmap=heatmap.to_html(full_html=False, include_plotlyjs=False),
        category_table=category_table,
        category_figure=category_figure,
        cause_figure=cause_figure,
        classification_count=len(assignments),
        cross_table=cross_table,
        cross_figure=cross_figure,
        snapshot_id=facts["snapshot_id"],
        report_hash=facts["report_spec_hash"][:16],
        evaluator_commit=snapshot["sources"]["wandb_llm_leaderboard"]["commit"][:16],
    )
    output = PROJECT_ROOT / "report.html"
    output.write_text(html, encoding="utf-8")
    print(f"Wrote {output} ({len(html):,} characters).")


if __name__ == "__main__":
    main()
