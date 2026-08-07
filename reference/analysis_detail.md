# 誤答傾向分析：分析プロトコル詳細

本書は「誤答傾向分析を通じたベンチマークの妥当性検証」の分析部分（記事執筆を除く）を、再実行・再検証・拡張できる形でまとめたものである。初期実施計画（旧`Plan.md`、本書に統合済みのため削除）の内容に、実際の分析で確定した v2 時点のルール（Toxicityの部分集合組み込み、継続値ベンチマークの二値化規約、M-IFEvalのオフライン再計算、分類モデル代替時の扱いなど）を統合している。記事（`0_abstract.md`〜`5_references.md`を統合した`all.md`）そのものの執筆方法・文体規則はここには含めない。

## 1. 目的

Nejumi LLM Leaderboard の上位モデルが共通して失敗する問題を特定し、その失敗が次のどこに由来するかを、問題・モデル回答・採点処理の三者を照合して分析する。

- モデルの能力不足
- 指示追従や出力形式など評価プロトコルとの不一致
- 問題文の曖昧さ、前提情報の不足、複数解釈の余地
- 参照解答、採点規則、judge の不安定性
- 複数要因の混在、または現時点では判定不能

個別の誤答事例からベンチマーク全体を一方的に否定することが目的ではない。特定時点の上位20モデルという限定された観測範囲から、スコア解釈上の注意点と次回のベンチマーク改善候補を提示する。

## 2. 成果物

1. `experiment/report.html` — 数値、図表、代表事例、制約を含む分析の一次成果物
2. `experiment/` 以下の再現可能な実装 — W&Bからの取得、正規化、誤答抽出、LLM分類、横断分析、可視化、検証
3. 追跡可能な中間成果物 — top20 run一覧、artifact一覧、正誤定義、問題×runの正誤行列、分類結果、プロンプト、検証結果

分析の依存関係は次の順序で固定する。

`ランキングのスナップショット固定`
→ `top20 runの確定`
→ `artifact/tableの構造調査`
→ `ベンチマーク別正誤規則の確定`
→ `20 run横断の問題ID統合`
→ `80%以上誤答した問題の抽出`
→ `ベンチマーク別分類`
→ `ベンチマーク横断分析`
→ `HTMLの数値検証`

（この先に記事執筆の工程が続くが、本書の対象外とする。）

## 3. 調査開始前に固定する定義

### 3.1 ランキングの基準

- 対象は W&B project内で **`leaderboard` tagを持つrunだけ** とする。`archived`のみのrunや、公開レポートfilterが特例として追加するrunは含めない。
- 基準日時、実際の取得日時、タイムゾーン、レポートURL、table artifactのversion/digestを保存する。
- `leaderboard_table` はsummary内の単純な辞書ではなく、各runに紐づくW&B Tableへのpointerである。候補runのtable JSONを取得し、1行の `TOTAL_SCORE` を数値化して順位を再構成する。
- W&B projectの全runを単純に並べず、APIのserver-side filter `{"tags": "leaderboard"}` で母集団を固定する。各候補runの個別`leaderboard_table`を取得し、`TOTAL_SCORE`降順を適用する。
- 公開レポートspec全体、`updatedAt`、hash、統合tableも出典情報として保存する。ただし統合tableの更新遅延で新しいtag付きrunが欠落しうるため、最終順位は統合tableではなく各候補runの個別tableから決定する。
- 公開レポートのrun set、filter、除外条件、並び順を可能な限り取得し、画面上の上位20件と一致させる。filterをAPIから復元できない場合は、レポートからの手動exportまたは目視照合を必須ゲートとする。
- 同点は公開レポートの表示順を採用し、その順序をmanifestに保存する。
- 主解析では公開レポートの20行を勝手に重複排除しない。同一モデルのrerunや同系列モデルが含まれる場合は明示し、モデル名重複排除版・モデル系列ごと1件版を感度分析として併記する。

### 3.2 top20の完全性

各候補について、run ID、model name、run state、`TOTAL_SCORE`、主要カテゴリ列、tableの行数・列数を検査する。

- 20個の一意なrun IDへ解決できること
- `TOTAL_SCORE` が有限値であること
- `dummy_run`、再集計run、未完了runなどが公開レポートでどう扱われているか説明できること
- `TOTAL_SCORE` の計算対象カテゴリに欠損がないか確認すること

公開値の集計処理は、欠損カテゴリを分母から外す可能性があるため、欠損による順位上振れを監査する。公開上位20と完全評価runだけの順位が異なる場合、公開上位20を主解析として保持しつつ、完全評価コホートを感度分析に分け、差を隠さない。

### 3.3 「同一問題」の単位

主キーは次を優先する。

`benchmark + subtask + split + evaluation_condition + official_item_id`

- `evaluation_condition` には0-shot/2-shot、通常版/robust版、turn、trialなどを含める。
- 公式IDがない場合のみ、正規化した問題データのhashを使う。その際はhash衝突、同文異ラベル、表記差を別途検査する。
- 同じ基礎問題を異なる条件（0-shot/2-shotなど）で評価した結果は、正誤行列では別観測として保持する。問題数を数える際は、条件別の件数と基礎問題へまとめた件数を混同しない。
- `_dev` tableなど公式スコアに使われない表もmanifestには残すが、評価コードに基づく除外理由を記録し、主解析へ黙って混ぜない。

### 3.4 「誤答」の定義（correctness registry）

すべてのベンチマークに共通の閾値を置かず、評価コードと出力列に基づいて `correctness_registry.yaml` に事前登録する。ベンチマークごとの正誤ルールは次の5種類に分かれる。

1. **公式二値判定**: 公式のcorrect/pass列をcanonicalな `is_correct` に写像する（例: ARC-AGIの完全一致、BFCLのaccuracy、HLEのjudge判定、Jasterのexact-match系、SWE-benchのresolved/unresolved）。
2. **オフライン再計算による公式二値の復元**: 評価コードが公式の二値判定（例: `follow_all_instructions`）を内部で計算していながら、出力tableには分数・部分点しか記録していない場合、保存済みの生データ（prompt・応答・パラメータ）から同じ判定関数をオフラインで再実行し、公式の二値を復元する。これは「連続値だから二値境界がない」と即断する前に必ず確認すべき手順であり、確認方法は次のとおり。
   - 評価器のソースを読み、テーブルに書き出される直前の変数の中に、記録されていない二値フラグ（bool型の中間変数）がないか探す。
   - あれば、その計算に必要な入力（生成テキスト、パラメータ、正解条件）がoutput tableに残っているか確認する。
   - 残っていれば、評価器のロジックを最小限の依存関係で再現するスクリプト（`experiment/scripts/` 配下）を書き、全itemに対して再計算する。
   - 元の分数scoreと再計算結果の整合率を必ず記録し（完全一致が理想だが、tokenizerやjudgeの非決定性で数%のずれが出ることがある）、ずれの原因を可能な範囲で特定する。
   - 再計算時にchecker自体がエラーを返した場合は、値を推測せず欠損として扱う。
3. **分布依存の閾値慣習（half-scale / bottom-quartile convention)**: 上記1・2のいずれも成立せず、公式の二値境界が存在しない連続score（例: LLM judgeの1-10評価、char_f1、COMETのような回帰的品質指標）については、非公式の閾値慣習を明示的に定義し、コードとconfigの両方に記録する。固定的な絶対値（例: `score ≤ 0.5×満点`）よりも、**実際に観測された上位モデル群のscore分布そのものを基準にする閾値（例: 上位20モデルのpooled score分布の第1四分位、Q1を下回るスコアを誤りとみなす）**の方が望ましい。固定の絶対値は、score分布がベンチマークごとに大きく異なる散らばり方をする場合（後述）に、閾値そのものが結果を支配してしまう副作用が大きい。いずれの慣習を採用する場合も、「公式ルール」ではなく本分析が採用する閾値であることを常に明記し、他ベンチマークとの件数比較には閾値依存の限界が残ることを併記する。ベンチマークごとの「満点（スケール）」を正しく設定すること（例: MT-Benchは10点満点、char_f1/COMET/JMMLU Robustは0-1）。
   - 閾値を採用する前に、そのbenchmarkのscoreが実際に何を測っているかを必ず確認する。例えばJMMLU Robustのようにフォーマット間の自己一貫性だけを測り、正解性そのものを測っていないbenchmarkでは、「誤り」の意味が他のbenchmarkと異なることを明記する。
   - 閾値を機械的に適用した結果、極端に高い／低い誤答率が出た場合は、そのベンチマークの元のscore分布（中央値・平均・実際のitemデータ）を必ず確認し、閾値の置き方自体が結果を支配していないか検証する。特に上位モデル群のscoreが特定の値（満点など）へ極端に偏っている場合、分布依存の閾値（第1四分位など）がその偏った値と一致してしまい、「満点以外はすべて誤り」のような意図せず厳しいルールへ縮退することがある。この縮退が起きた場合は、それ自体を分析結果として明記する（閾値の欠陥ではなく、score分布の偏りそのものが示唆的な発見でありうる）。
   - 分布依存の閾値を採用する場合、どの母集団（例: 上位20モデルの全item×全run）でQ1を計算したかを固定し、再現できるようにコードに残す。ベンチマーク内でメトリクスが複数ある場合（例: JHumanEvalのcode_exec_sandbox/pylint_check、JasterのCOMET/char_f1）は、メトリクスごとに別々の閾値を計算する。
4. **部分集合での組み込み（partial-item-set inclusion）**: 出力tableの実装上の制約で、全アイテムのうち一部（例: 先頭N件）しか永続化されていないベンチマークについて、「完全なデータがないので主解析から除外する」を既定にしない。次の手順で部分集合としての組み込みを検討する。
   - 保存されている部分集合が、全run間で本当に同一のitem集合か（同じitem ID・同じ順序か）をコードとデータの両方で確認する。同一でなければ組み込みを見送る。
   - 完全なper-item sourceが他に残っていないか探す（例: 評価トレーシング基盤の呼び出しログ。ただし本分析ではこの経路の認証情報が実行環境で有効か確認できなかったため、将来の再実行時に有効な認証情報があれば最初に試すべき選択肢として記録するに留めた）。
   - 上記が得られない場合、保存されている部分集合だけを対象に、他ベンチマークと同じ閾値・集計ロジックを適用し、「N問限定の部分集合」であることを主解析・Appendix双方に明記する。全体の代表性を主張しない。
5. **欠損・未提出・運用エラー**: parse error、timeout、未実行、欠損は誤答と自動的に同一視せず、別のstatusとして保存する。

`correctness_registry.yaml` には上記のどのルールを適用したか、根拠となるソースコードの行番号、注意点を必ず記録する。ルールを変更した場合は `version` を上げ、`revision_note` に変更内容と理由を残す。

### 3.5 80%閾値

問題 \(i\) について次を計算する。

- `n_evaluable(i)`: canonicalな正誤判定が存在するrun数
- `n_wrong(i)`: `is_correct == false` のrun数
- `wrong_rate(i) = n_wrong(i) / n_evaluable(i)`

主解析の「80%以上のモデルが誤答した問題」は、**top20すべてで判定可能かつ `n_wrong >= 16`** とする。

- 15/20は対象外、16/20は対象内
- 欠損を誤答として数えない
- `n_evaluable < 20` の問題は主解析から外し、欠損一覧と `n_wrong / n_evaluable` を補足分析に出す
- 70%、80%、90%で結果がどの程度変わるかを感度分析する
- 同系列モデルの偏りを確認するため、モデル系列単位の感度分析も行う

## 4. ディレクトリ構成

```text
experiment/
├── README.md
├── pyproject.toml
├── uv.lock
├── config/
│   ├── analysis.yaml
│   ├── correctness_registry.yaml
│   └── publication_policy.yaml
├── src/leaderboard_analysis/
│   ├── freeze_snapshot.py
│   ├── freeze_ranking.py
│   ├── inventory_artifacts.py
│   ├── normalize_tables.py
│   ├── extract_common_failures.py
│   ├── prepare_llm_inputs.py
│   ├── analyze_operational_cost.py
│   ├── validate_scores.py
│   ├── build_report.py
│   └── validate.py
├── scripts/
│   ├── recompute_m_ifeval_strict.py   # 3.4節②のオフライン再計算の実例
│   └── refresh_tagged_top20_classifications.py
├── tests/
├── data/
│   ├── manifests/
│   ├── raw/                 # 原則git管理外
│   ├── interim/              # オフライン再計算などの中間成果物
│   └── processed/
│       ├── item_results.parquet
│       ├── item_summary.parquet
│       ├── common_failures.parquet
│       └── operational_metrics.csv
├── prompts/
├── outputs/
│   ├── llm/
│   │   ├── input/            # 分類器への固定入力
│   │   ├── by_benchmark/     # benchmarkごとのtaxonomy・assignments
│   │   └── cross_benchmark/  # 横断taxonomy
│   ├── tables/
│   ├── paper_facts.json
│   └── validation_report.json
└── report.html
```

`.env`、API key、private artifactのraw data、機密性のあるモデル出力を成果物へ混入させない。`.gitignore` で `.env`、raw cache、秘密情報を含みうるlogsを除外する。

## 5. 実行フェーズ

### Phase 0: 環境・出典・公開可否の固定

1. `experiment/` と再現用Python環境（`uv sync`）を作る。
2. `.env` は存在と必要な環境変数名だけを検査し、値を表示・保存しない。
3. 参照する評価コードrepositoryのcommit SHA、取得日時、URLを `snapshot.json` に保存する。main branchは変化するため、実行開始時に参照commitを再取得し、以後は固定SHAを使う。
4. benchmarkごとに、問題文・参照解答・モデル回答をHTMLへ掲載できるかを `publication_policy.yaml` で確認する。
5. privateまたは掲載条件が不明なデータはraw分析にのみ利用し、公開用HTMLでは集計値・匿名化例・item IDだけを使う。

完了条件: 秘密情報を出力しない設定が先に整っている／コード・データ・レポートのsnapshotを後から特定できる／公開可能データと非公開データが区別されている。

### Phase 1: W&B構造のprobeとtop20の固定

1. `wandb.Api(timeout=60)` を使い、大規模project向けに必要なfieldだけを取得する。
2. report IDからspecを取得し、active run set、filter、server sort、`updatedAt`を保存する。
3. server-side filter `{"tags": "leaderboard"}` で候補runを列挙する。
4. pointerから対応する`run_table` artifactと正確な `leaderboard_table.table.json` を解決する。
5. `columns`、`data`、`nrows`、`ncols`、artifact version/digestを検証する。
6. 各候補runの個別table 1行から `TOTAL_SCORE`、model name、カテゴリ別scoreを抽出し、`TOTAL_SCORE`降順を適用する。統合tableは順位決定に使わない。
7. 上位20件を `top20_runs.csv` に固定する。
8. 公開レポートの表示、再構成順位、run URLを20件すべて照合する。

検証ゲート: 20件すべてが一意なrun IDへ解決される／全20件が`leaderboard` tagを持ち個別tableのscoreと一致する／filterや重複処理を再現できない場合は推測で先へ進まず手動照合結果を保存する／欠損カテゴリ、同一モデルのrerun、非finished runを明示する。

### Phase 2: artifact棚卸しと正誤規則の確定

1. top20の各runで `logged_artifacts()` を列挙し、artifact名、type、version、digest、size、作成日時を保存する。
2. 同時にrun summaryの論理キーを調べ、`*_output_table` pointerの `artifact_path` と `sha256` を保存する。
3. `run_table` のbasenameだけに依存せず、summaryの論理キー、pointerのdigest、artifact manifest内の正確な `.table.json` entry名を突合する。
4. artifact全体を無条件にdownloadせず、manifestから対象の `.table.json` だけを取得する。
5. `columns`、型、行数、ID候補、問題列、参照解答列、モデル回答列、score列、error列を `schema_inventory.csv` に記録する。
6. 評価コードの固定commitで、各tableの生成処理、公式集計への採否、正誤・部分点・judge scoreの意味を追跡する。**このとき、テーブルには現れないが評価コード内部で計算されている二値フラグがないか（3.4節②）を必ず確認する。**
7. benchmarkごとのmappingを `correctness_registry.yaml` に定義する（3.4節の5分類のどれに該当するかを明記）。

検証ゲート: top20×全tableについて取得済みまたは理由付き除外のどちらかになっている／benchmarkごとの問題IDと正誤判定列を推測ではなくコード・データ双方で説明できる／公式datasetの期待件数とoutput tableの行数が一致する（不一致の場合は完全なper-item sourceを探し、見つからなければ3.4節④の部分集合手順を検討する）／代表tableを手作業で検算し、raw scoreからcanonical判定を再現できる／判定不能な連続scoreを無理に二値化していない（3.4節③の慣習を適用する場合はその旨を明記する）。

### Phase 3: 20 run横断の正規化

1. 固定したdataset artifactと評価コードから、benchmark別の公式item universeと期待件数を作る。
2. 各tableを共通のlong形式へ変換する。
3. 公式item IDを優先して20 run間をjoinする。
4. 公式item universe×top20 runの直積を作り、未評価・欠損も `evaluation_status` 付きの行として明示的に補う。
5. 問題文、参照解答、全モデル回答、raw score、canonical判定、provenanceを保持する。
6. 問題×runの重複、ID集合の不一致、期待件数、table version差を検査する。
7. tableから再集計したbenchmark scoreをW&Bの公開値と比較する。

検証ゲート: 主解析候補の全itemについて20 run分が必ず存在し `item_key × run_id` がちょうど1行／期待した20 runのcoverageが可視化されている／version不一致と問題集合の差が明示される／再計算scoreが公開値と事前に定めた許容誤差内で一致する／不一致が残るbenchmarkは原因が解決するまで80%抽出へ入れない。

### Phase 4: 共通誤答問題の抽出

1. `item_key` ごとに `n_evaluable`、`n_wrong`、`wrong_rate`、欠損runを集計する。
2. 主解析条件 `n_evaluable == 20 and n_wrong >= 16` を適用する。
3. benchmark、subtask、評価条件別に件数と比率を集計する。
4. 各問題について、20モデルの回答を完全一致・parse error・回答選択肢・意味的類似などで要約し、代表回答と件数を残す。
5. 70/80/90%閾値、利用可能runを分母にした場合、モデル系列ごと1件にした場合を感度分析する。

出力: `common_failures.parquet`、`coverage_matrix.parquet`、`wrong_matrix.parquet`、`threshold_sensitivity.csv`、benchmark別の対象件数表。

### Phase 5: ベンチマーク別のLLM支援分類

`wandb/fails` の考え方を参考に、次の三段階で実施する。

本番分類モデルとreasoning effortを固定し、指定された実行経路（例: 特定のsub-agent）で呼び出す。pilotも本番と同じモデル・設定を使う。API上のmodel aliasへ読み替えたり、別モデルへ黙ってfallbackしたりしない。**指定モデルが実行環境で利用不能な場合は、分類phaseを停止し、ユーザーへ次のいずれかの確認を求める。**

- 代替モデル（例えばその場のセッションで動いているモデル）による分類を許可するか
- 分類を後日・別経路で実施するまで保留するか
- 定量集計のみで一旦区切るか

代替モデルでの分類を許可された場合は、成果物（`outputs/llm/by_benchmark/*.json` の `limitations`、`outputs/llm/cross_benchmark/synthesis.json` の `scope`、および記事本文）すべてに、どの分類がどの分類器によるものかを明記する。既存の凍結済みtaxonomyに新しい対象データを追加する場合は、新しいカテゴリを作らず既存カテゴリへの当てはめを優先し、既存分類済み分と混同しないよう追記であることを記録する。

分析単位は「単一システムの失敗row」ではなく「共通誤答となった1問題」である。LLMへ渡すデータ契約は次のように固定する。

- `input`: benchmark、item ID、問題、選択肢、参照解答、評価規則
- `output`: M01〜M20へ匿名化した回答、正規化した回答パターン、各正誤
- `scores`: `wrong_count / 20`、欠損、raw score、判定根拠

モデル名とM01〜M20の対応は別ファイルへ保存し、分類時のモデル名・順位による先入観を抑える。

1. **一次オープンコーディング** — 各共通誤答問題について、問題、参照解答、採点根拠、20モデルの回答分布から1〜3個の候補コードを作る。
2. **カテゴリ統合** — benchmark内の候補コードを、重複のない少数のfailure taxonomyへ統合する。原則として最大7カテゴリ程度とし、収まらないものは `other` ではなく、まずtaxonomyの粒度を再検討する。
3. **最終再分類** — 固定したtaxonomyを使って全対象問題を1つの主カテゴリへ再分類し、該当しない場合は予約カテゴリ `other` を使う。

これはk-means、HDBSCAN、UMAPなどの数値的クラスタリングではなく、**LLM支援の定性コーディングとtaxonomy生成**である。

「参照解答・評価器は常に正しい」という仮定は採用しない。問題・参照解答・採点規則自体も検証対象とする。三段階の処理構造に加え、以下を独立した第二軸（cause axis）として付与する。

- `model_capability`
- `format_or_protocol`
- `ambiguous_or_underspecified`
- `reference_or_evaluator`
- `data_or_version`
- `mixed`
- `uncertain`

`uncertain` はcause axisとして使い、主カテゴリを決められない場合のprimary categoryは `other` とする。各分類は `category, cause_axis, confidence, evidence_item_ids, concise_rationale, improvement_candidate` をstructured outputで保存する。内部の長い思考過程ではなく、再確認できる根拠と短い判断理由を残す。

記事化の際、`reference_or_evaluator` は粒度が粗すぎて読みにくいと判断し、集計・図生成時（LLM再分類ではなく、既存のcategory_idに基づくルールベースの後処理）に2つの表示ラベルへ分割してよい：category_idが「参照解答・answer key自体の欠陥」を指すもの（例: `reference_or_evaluator_defect`, `answer_key_option_misalignment`, `reference_defect`, `tool_action_selection`, `temporal_snapshot`）は「参照解答の間違い」、それ以外（`semantic_match_failure`, `constrained_value`, `reference_conflict`, `cat_checker_mismatch`, `adequate_answer_below_score_ceiling`など、分類器・チェッカー・採点上限側の問題）は `format_or_protocol`（「出力形式・評価器」）へ統合する。この振り分けはitem単位で行い、同じcategory_idでも他のcause_axis配下の項目には適用しない（例: `temporal_snapshot`は`data_or_version`配下にも別item として存在する）。振り分け先の具体的なcategory_id集合は、記事化のたびに実際のconcise_rationaleを読んで判断し直す（固定リストを無条件に再利用しない）。

さらに記事の読みやすさのため、`data_or_version` は「参照解答の間違い」（＝古いバージョンの評価コードやデータが混ざり込んでいるのも一種の「正解データ自体の欠陥」とみなす）へ統合し、`mixed` は単独カテゴリとして残さずitem単位でどれか1つの軸へ再割り当てしてよい。再割り当ても同様にcategory_idベースのルール（`concise_rationale`を読んで、表記・プロトコル寄りなら`format_or_protocol`、解釈の境界寄りなら`ambiguous_or_underspecified`、知識・推論寄りなら`model_capability`、それ以外は`uncertain`）で行い、この判断も記事化のたびに実データを読んで見直す。この結果、記事に表示するcause axisは最終的に5種類（`format_or_protocol`, `model_capability`, `ambiguous_or_underspecified`, `reference_defect_axis`, `uncertain`）になる。

再現性対策:

- 入力schema、入力item IDの順序、プロンプトとそのSHA、モデルの完全な識別子、reasoning設定、実行日時、コードcommit、入力hashを保存する。
- temperature、top_p、max output、seed、model revision、concurrencyを明示し、指定できない項目も「未対応」として記録する。
- 問題文とモデル回答をuntrusted dataとしてdelimiter内へ入れ、そこに含まれる命令へ従わないよう明示する。特に安全性系ベンチマーク（有害性・攻撃的プロンプトなど）を扱う場合は、分類作業自体が対象コンテンツを実行・助長しないよう明記する。
- まず少数のpilotで分類品質、token量、費用を確認してから全件実行する。
- pilotや監査sampleは先頭N件ではなく、固定item IDによる層化抽出にする。本番は全共通誤答問題を対象にする。
- benchmark/taskの文脈が実際のLLM入力へ渡っていることをfixture testで確認する。
- JSON Schemaとコードで、一次候補1〜3、通常カテゴリ1〜7（`other`を除く）、カテゴリIDの重複なし、予約カテゴリ`other`がちょうど1つ、全件1 primary category、taxonomy外の出力ゼロを強制する。
- 順序を変えた層化sampleを再分類し、単なるカテゴリ名一致ではなくitem間のco-assignmentも用いて安定性を記録する。
- `ambiguous_or_underspecified`、`reference_or_evaluator`、`uncertain` は全件を人手監査し、その他も層化抽出して監査する。
- 人手監査ができない場合は「LLMによる仮説分類」と明示し、強い妥当性主張に使わない。
- structured JSONをローカル保存する。
- 固定順の入力JSON/batchを作り、各分類実行にはJSON Schemaに合う結果だけを返させる。入力、raw応答、検証後JSON、実行情報を `outputs/llm/by_benchmark/` に保存する。

長文回答、patch、画像などがcontext上限を圧迫する場合、raw dataは保持したまま、回答パターンと実行結果を構造化してLLMへ渡す。切り詰めや階層mergeが発生した項目はフラグを立てる。

**既存taxonomyへの追記時の追加ルール**: 後日新しいbenchmarkや新しい正誤ルールが二値化され、既存の共通誤答集合に項目が追加される場合、その benchmark に既に凍結済みのtaxonomyがあれば、新カテゴリを追加せず既存カテゴリへの当てはめを優先する（`correctness_registry.yaml` の `version`/`revision_note` と対応させる）。当てはめられない項目のみ、taxonomyの粒度自体を見直すか `other` を使う。

### Phase 6: ベンチマーク横断分析

入力は、ベンチマーク別taxonomy、カテゴリ件数、cause axis、代表問題、代表回答パターン、感度分析、監査結果とする。大量のraw rowを直接渡さず、元itemへ遡れるIDを必ず添える。

出力: 横断的な誤答パターンtaxonomy、benchmark別カテゴリと横断カテゴリの対応表、各横断パターンの支持benchmark・件数・代表item ID、モデル能力起因とbenchmark/evaluator起因を分けた示唆、benchmark設計・採点・結果解釈の改善候補、反証例・留保・追加確認が必要な主張。

実行条件: モデル・reasoning effortをPhase 5と同じ運用にする／同じ完全model IDを提供する正式なAPI経路が確認できない限りAPI model名へ読み替えない／利用不能時に別モデルへfallbackせず、Phase 5と同様にユーザー確認を求める／synthesis用プロンプトとevidence audit用プロンプトを分ける／item IDまたは集計表へ追跡できない主張は採用しない。

**既存synthesisへの追記時の追加ルール**: 新たに二値化された項目群を既存の横断taxonomyへ統合する場合、既存パターンで説明できるならパターンを追加せず、各benchmarkカテゴリを最も定義の近い既存パターンへマッピングし、`cross_taxonomy` の `item_count` を合計が一致するよう再計算する。既存の物語的な記述（原因分析の考察文など）は、量的整合性（`cross_taxonomy`・`benchmark_category_mapping`の合計件数）が取れていれば必ずしも全面改稿しなくてよいが、その場合は「この記述は追記前の件数を対象にしている」旨を明記する。

### Phase 7: 評価運用のコスト・時間・turn数分析（根拠データ取得時）

- wall-clock time、run time、API call数、token使用量
- judge modelのcall数とtoken使用量
- GPU/CPU resource-hours
- task数、sample数、trial数、turn数、agent step数
- 成功が確定したstepと、その後に費やした確認step
- 全体コスト・時間に占めるbenchmark別比率

`turn`、`trial`、`agent step` は意味が異なるため、benchmark横断で無理に一つの数へ合算しない。実測額と推定額を分け、価格を使う場合は出典と基準日を記録する。根拠が取れない場合は値を捏造せず「計測できなかった」という制約として扱う。少数のtaskが全体時間・コストを支配するかをPareto図で確認する。

### Phase 8: 可視化とHTMLレポート

`report.html` には以下を含める。

1. 分析対象とtop20一覧
2. データcoverageと欠損・version差
3. benchmark別の対象問題数、共通誤答数、比率
4. 問題×モデルの正誤heatmap
5. 誤答率分布と70/80/90%感度
6. benchmark別failure categoryの構成比
7. benchmark×横断categoryのheatmapまたはSankey図
8. cause axisの構成比
9. ライセンス上掲載可能な代表問題と回答分布
10. 根拠データを取得できた場合のみ、コスト・時間のPareto図
11. 方法、正誤定義、制約、再現情報

failure categoryの割合は「共通誤答問題内の構成比」と「benchmark全問題に占める率」を分けて表示する。図は集計JSON/Parquetから自動生成し、本文へ数値を手入力しない。private dataは公開版へ埋め込まない。

### Phase 9: 最終検証

自動テスト: 正誤mappingのunit test／公式IDとhash fallbackの重複・衝突test／欠損を誤答扱いしないtest／15/20が対象外・16/20が対象内になる境界test／continuous scoreを未登録閾値で二値化しないtest（分布依存閾値を適用する場合は、その閾値がどの母集団から計算されたか・満点スケールが正しく設定されているかのtestを含む）／table再集計値と公開scoreの一致test／category件数の合計が対象問題数に一致するtest／benchmark/task contextが分類プロンプトへ渡るtest／taxonomyが最大カテゴリ数・重複なし・`other`一意・全件1 primary categoryを満たすtest／`paper_facts.json`・HTMLの数値整合test。

手動・視覚検証: 公開レポート上位20との照合／benchmarkごとに複数問題の正誤判定を原表・コードと照合／欠損heatmapとartifact inventoryに黙ったskipがないことを確認／HTMLの表・filter・tooltip・図の軸・色・注記を確認／private問題文やAPI keyがHTML・logs・Markdownに含まれないことを確認。

## 6. 主なリスクと対応

| リスク | 対応 |
|---|---|
| W&BレポートのfilterをAPIから完全に復元できない | 手動exportまたは画面との20件照合を必須にし、推測順位を使わない |
| `TOTAL_SCORE`が欠損カテゴリを除いて計算される | category completenessを監査し、完全評価コホートを感度分析する |
| 同一モデルのrerunや同系列モデルが多い | 主解析は公開順位を保持し、重複排除・系列単位分析を追加する |
| table名・列・ID・score定義がbenchmarkごとに異なる | schema inventoryとcorrectness registryを80%抽出前の必須ゲートにする |
| summary pointerとartifact basename/versionが一致しない | summary key、pointer SHA、manifest entryを三者照合し、`:latest`へ依存しない |
| `_dev`や非公式tableが混ざる | 評価コードで公式集計への採否を確認し、除外理由をmanifestに残す |
| output tableが全問題を保存していない | 期待件数と照合し、完全sourceがなければ3.4節④の部分集合手順を検討する（除外を既定にしない） |
| 評価コードが二値フラグを計算しているのに出力していない | 3.4節②のオフライン再計算を先に試す |
| 欠損を誤答と数えることで誤答率が歪む | 主解析は20/20 complete-caseに限定する |
| judge型・連続scoreを恣意的に二値化する | 3.4節③の分布依存閾値慣習（固定絶対値より上位モデル群のscore分布に基づく閾値を優先）を明示し、非公式であることを常に併記する |
| LLM分類が不安定・幻覚を含む | structured output、再分類、層化監査、evidence ID、感度確認を行う |
| 指定分類モデルが実行環境で利用不能 | 黙って別モデルへfallbackせず、ユーザーに確認する。許可された場合は分類器の違いを全成果物に明記する |
| 既存の凍結済みtaxonomyに新項目を追加する必要が生じる | 新カテゴリを増やさず既存taxonomyへの当てはめを優先し、追記であることを明記する |
| 長文回答やmediaがcontextを圧迫する | rawを保持しつつ回答分布を構造化し、切り詰めを記録する |
| 問題文・回答の掲載ライセンス | benchmark別publication policyを作り、公開版では必要に応じて匿名化・集計化する |
| コスト・turn数の根拠がoutput tableにない | 別データ源を取得し、取得不能なら制約として扱う |
| top20という標本だけで妥当性全体を断定する | 結論をitem-levelの示唆と結果解釈上の注意に限定する |

## 7. 参照元

- FAILS repository（分類手法の参考）: <https://github.com/wandb/fails>

対象leaderboardの公開レポートURL・project URL・評価コードrepositoryのURLは、実行時に確認して `data/manifests/snapshot.json` に保存する。`main` branchは変化するため、実験開始時に参照commitを再取得し、以後は固定SHAを使う。
