# 序論（Introduction）文献レビュー
「誤答傾向分析を通じたベンチマークの妥当性検証」序論ドラフト向け

作成日: 2026-08-05
対象ドラフト: Nejumi LLMリーダーボード4上位20モデルの共通誤答を分析し、モデルの能力不足に起因するのか、ベンチマーク/評価プロトコルの欠陥（曖昧な設問、評価器のバグ、採点ルールのアーティファクト等）に起因するのかを検証する記事の序論。

本レビューは、実際にWeb検索・Webフェッチで内容を確認できたソースのみを掲載している。検索はしたが内容を十分に検証できなかったもの、関連性が薄いものは末尾の「採用しない情報源」に分離し、理由を明記した。合計 **33件** を確定ソースとして採用した（目安の30件をやや上回るが、いずれも個別に内容を確認済み）。

---

## 1. サーベイ／benchmark妥当性・汚染・飽和・構成概念妥当性に関する文献

### [1] Measuring what Matters: Construct Validity in Large Language Model Benchmarks
- **著者/組織**: NeurIPS 2025 Datasets & Benchmarks Track（29名の専門家レビュアーによる大規模レビュー）
- **年**: 2025
- **URL**: https://arxiv.org/pdf/2511.04703 / https://openreview.net/forum?id=mdA5lVvNcU
- **関連**: 主要会議の445件のLLMベンチマークを体系的にレビューし、構成概念（測定対象の定義）の曖昧さ、サンプリングの偏り（27%が便宜的サンプリング）など、妥当性を損なうパターンを実証。ドラフトの「常に完璧なベンチマークは存在しないという前提」(J)を学術的に裏付け、かつ「ベンチマークの結果解釈の精度」(K)の議論に使える具体的なチェックリスト（8つの推奨事項）を提供している。

### [2] Fantastic Bugs and Where to Find Them in AI Benchmarks
- **著者/組織**: Sang T. Truong, Yuheng Tu, Michael Hardy, Anka Reuel, Zeyu Tang 他（Stanford University）
- **年**: 2025（NeurIPS 2025）
- **URL**: https://arxiv.org/abs/2511.16842 / https://ai.stanford.edu/blog/fantastic-bugs/
- **関連**: 9つの主要ベンチマークに対し、モデル回答パターンの統計解析から「問題のある設問」を自動フラグし専門家レビューに回す手法を提案、最大84%の精度で不正確な設問を検出。本研究の「共通誤答分析からベンチマーク不備を特定する」という方法論そのものと極めて近い先行研究であり、序論で自分たちのアプローチの位置付けを説明する際に直接引用すべき最重要文献。

### [3] Are Emergent Abilities of Large Language Models a Mirage?
- **著者**: Rylan Schaeffer, Brando Miranda, Sanmi Koyejo
- **年**: 2023（NeurIPS 2023）
- **URL**: https://arxiv.org/abs/2304.15004
- **関連**: 非連続的な採点指標（完全一致・多肢選択の正誤二値判定）の選択自体が、モデル能力の見かけの急変（emergence）を生み出すことを実証。ドラフトの「問題設計が曖昧で…採点が難しい」(G)という論点を、採点指標側の設計問題として補強・一般化する重要な先行研究。

### [4] Questionable practices in machine learning
- **年**: 2024
- **URL**: https://arxiv.org/pdf/2407.12220
- **関連**: 「研究不正には至らないが問題のある慣行（QRP）」を44項目提示し、LLMのベンチマーク評価における再現性・監査可能性の欠如を指摘。ドラフトの「評価ベンチマークを作るのは大変」(I)という謝意の文脈と対になる形で、評価される側・する側双方の実務的な落とし穴を整理する文献として有用。

### [5] Benchmark Data Contamination of Large Language Models: A Survey
- **年**: 2024
- **URL**: https://arxiv.org/pdf/2406.04244
- **関連**: 学習データへのベンチマーク混入（contamination）を系統的にサーベイ。ドラフトが焦点を当てる「誤答」とは逆方向の脅威（不当に高いスコア）であり、序論で自分たちのスコープ（誤答分析であって汚染検出ではない）を明示する際の対比材料として有効。

### [6] NLP Evaluation in Trouble: On the Need to Measure LLM Data Contamination for Each Benchmark
- **年**: 2023
- **URL**: https://arxiv.org/pdf/2310.18018
- **関連**: ベンチマークごとに汚染度を測定・報告すべきと提言。[5]と合わせて、ドラフトの「評価ベンチマークの問題点を指摘したいのではない」(I)という姿勢と同様、批判ではなく改善提案としてのトーンで書かれている点が参考になる。

### [7] The Benchmark Ceiling: Human Judgment, Evaluation Scarcity, and the Political Economy of AI Capability Measurement
- **年**: 2026
- **URL**: https://arxiv.org/abs/2607.01254
- **関連**: フロンティアベンチマークの妥当性は「設問作成に関わる人間の専門家の判断の質」に構造的に規定され、モデルが上位ベンチマークを飽和させるほど、残された弁別力のある設問は少数の専門家が作った難問に集中する、という「ベンチマーク天井（ceiling）」問題を提示。ドラフトの(F)「フロンティアモデルはほとんど高いスコアに張りついている」状態の理論的説明として直接使える。

### [8] The 2025 AI Index Report（Technical Performance章）
- **著者/組織**: Stanford HAI
- **年**: 2025
- **URL**: https://hai.stanford.edu/ai-index/2025-ai-index-report
- **関連**: MMMU・GPQA・SWE-benchが登場から1年でそれぞれ18.8pt・48.9pt・67.3pt上昇し飽和したこと、トップとトップ10位のモデル差が1年で11.9%→5.4%まで縮小したという具体的な数値を提示。ドラフトの(D)(F)「すぐに攻略される」「高いスコアに張りついている」という定性的主張に、定量的裏付けを与えられる一次情報として非常に有用。

---

## 2. フロンティアラボによる飽和・設計欠陥・評価器信頼性の議論

### [9] Why SWE-bench Verified no longer measures frontier coding capabilities
- **著者/組織**: OpenAI
- **年**: 2026
- **URL**: https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
- **関連**: 監査したサブセットの59.4%でテストケースに欠陥があり正しい回答を誤って不正解と判定していたこと、問題文からの解法漏洩（データ汚染）で最大76%が暗記のみで解けることを報告し、公式にSWE-bench Verifiedでの評価を中止したと発表。ドラフトが自ら発見したという「checker bug」「evaluator-version artifact」と全く同型の問題を、大手ラボが公式に認めた極めて強力な支持証拠。

### [10] GPT-4 Technical Report（評価手法 / simple-evals）
- **著者/組織**: OpenAI
- **年**: 2023
- **URL**: https://arxiv.org/abs/2303.08774
- **関連**: MMLU・GPQA・HumanEval等の評価にあたり、プロンプト・温度・抽出方法を含む標準化フレームワーク（simple-evals）を採用したことを説明。フロンティアラボが評価プロトコルの細部（採点ルール）まで規定している事例として、ドラフトの「採点ルールのアーティファクト」という論点の背景説明に使える。

### [11] Anthropic's Responsible Scaling Policy（および関連のFrontier評価文書群）
- **著者/組織**: Anthropic
- **年**: 2024–2025（継続更新）
- **URL**: https://www.anthropic.com/responsible-scaling-policy
- **関連**: フロンティアモデルの能力評価に「Capability Threshold」という保守的な閾値を設定し、評価自体に不確実性のマージンを持たせる設計思想を説明。ベンチマークスコアを額面通りに受け取らず解釈に慎重を期すという、ドラフトの「結果解釈の精度を上げたい」(K)という目的意識と方向性が一致する。

### [12] GPQA Diamond: What's left?
- **著者/組織**: Epoch AI
- **年**: 2025
- **URL**: https://epoch.ai/gradient-updates/gpqa-diamond-whats-left
- **関連**: GPQA Diamond 198問のうち、モデルが集団で間違え続ける40問（20%）を詳細分析し、そのうち約2.25問が「無効な設問」、有機化学分野が不釣り合いに多い（誤答40問中70% vs 全体36%）ことを実証。ドラフトの(G)「フロンティアモデルでも間違える問題が存在するが、曖昧で正解しにくい問題も存在する」という中心主張と方法論的に最も近い先行事例であり、「誤答の大半は真の難易度に起因し、一部が設問不備」という穏当な結論のバランス感覚も参考になる。

### [13] What skills does SWE-bench Verified evaluate?
- **著者/組織**: Epoch AI
- **年**: 2025
- **URL**: https://epoch.ai/blog/what-skills-does-swe-bench-verified-evaluate
- **関連**: SWE-bench Verifiedが実際に測定している能力の範囲を再検討し、見かけ上の高スコアが必ずしも実務能力を反映しないことを議論。ドラフトの「能力測定」と「指針」という二側面(C)のうち、前者（能力測定としての妥当性）が崩れつつある実例として言及可能。

### [14] FrontierMath: A Benchmark for Evaluating Advanced Mathematical Reasoning in AI
- **著者/組織**: Epoch AI ほか
- **年**: 2024
- **URL**: https://arxiv.org/abs/2411.04872
- **関連**: 全モデルが2%未満の正答率という「まだ解けない問題」を意図的に設計したベンチマークの代表例。ドラフトの(D)「フロンティアモデルでもまだ解けない問題があるように設計される」という記述の直接的な裏付け。同時に、真に高難度の問題では人間による正解検証自体が困難になるという課題も指摘しており、(G)の「正解に辿り着く方が難しい」論点にも関連。

### [15] ARC-AGI-2: A New Challenge for Frontier AI Reasoning Systems
- **著者**: François Chollet ほか（ARC Prize Foundation）
- **年**: 2025
- **URL**: https://arxiv.org/abs/2505.11831
- **関連**: 旧ベンチマークが飽和した後継として設計され、汚染対策・敵対的タスク構築など「攻略されにくい」設計を追求した事例。Nejumi4もARC-AGI-2を採用しており、ドラフトの(E)「4回のバージョンアップ」という進化の背景（前バージョンの飽和への対応）を補強する。

### [16] Benchmarks should shape the frontier, not just measure it
- **著者/組織**: Vincent Chen, Snorkel AI
- **年**: 2025
- **URL**: https://snorkel.ai/blog/benchmarks-should-shape-frontier-not-just-measure-it/
- **関連**: 優れたベンチマークは「効果的な物差し」であると同時に「分野の研究の方向性（roadmap）を作る」機能を持つと明示的に論じている。ドラフトの(C)「能力測定と今後伸ばしていきたい能力獲得にむけての指針という二つの側面」という枠組みを、ほぼそのままの形で論じた数少ない一次資料であり、この一文の直接的な出典として最適。

### [17] Goodhart's Law Comes for Every Benchmark You Trust
- **著者/組織**: Communications of the ACM（blog@CACM）
- **年**: 2025
- **URL**: https://cacm.acm.org/blogcacm/goodharts-law-comes-for-every-benchmark-you-trust/
- **関連**: 「測定対象が目標になった瞬間、それは良い測定手段でなくなる」というグッドハートの法則をAIベンチマークに適用し、リーダーボードでのスコア上昇が必ずしも耐久性のある能力向上を意味しないと論じる。ドラフトの(D)「すぐにベンチマークは攻略され、期待する能力が次のステージにうつる」という記述の理論的枠組みを与える。

---

## 3. 個別ベンチマークの手法批判（ラベル誤り・曖昧設問・採点アーティファクト）

### [18] Are We Done with MMLU?（MMLU-Redux）
- **著者**: Aryo Pradipta Gema ほか
- **年**: 2024（NAACL 2025）
- **URL**: https://arxiv.org/abs/2406.04127
- **関連**: MMLU全57科目・5,700問を人手で再レビューし、平均6.49%（Virologyでは57%）に誤りがあることを発見、訂正版データセットMMLU-Reduxを構築。誤りの種類（パース誤り・複数正解・文脈欠落）を分類しており、ドラフトの「評価器のバグ」「曖昧な設問」を具体的に裏付ける、この種の文献の代表例。

### [19] Pervasive Label Errors in Test Sets Destabilize Machine Learning Benchmarks
- **著者**: Curtis G. Northcutt, Anish Athalye, Jonas Mueller
- **年**: 2021（NeurIPS Datasets & Benchmarks Track）
- **URL**: https://openreview.net/forum?id=XccDXrDNLek
- **関連**: MNIST・ImageNet等の代表的ベンチマークでラベル誤りがモデル順位を覆しうることを実証した、この分野の先駆的研究。MMLU等のLLMベンチマーク特有の話ではないが、「ベンチマークのラベル・正解が誤っていることでモデル比較そのものが歪む」という本記事の核心的問題意識の原点として引用価値が高い。

### [20] MMLU-Pro: A More Robust and Challenging Multi-Task Language Understanding Benchmark
- **年**: 2024（NeurIPS 2024）
- **URL**: https://arxiv.org/abs/2406.01574
- **関連**: MMLUの「trivialでノイズの多い設問」を除去し選択肢を4→10に拡張した改良版。旧ベンチマークでの性能頭打ち（plateau）が改良のモチベーションだったと明記されており、ドラフトの(D)「攻略されると次のステージにうつる」の具体的な事例（MMLU→MMLU-Proという世代交代）。

### [21] Is Your Code Generated by ChatGPT Really Correct? Rigorous Evaluation of Large Language Models for Code Generation（EvalPlus / HumanEval+）
- **年**: 2023
- **URL**: https://arxiv.org/abs/2305.01210
- **関連**: HumanEvalのテストケースが不十分（エッジケース欠如）で誤ったコードを正解と判定していたことを実証し、テストを80倍に拡充。GPT-4のスコアが88.4%→76.2%へ低下したと報告しており、ドラフトが指摘する「評価器のバグ」「採点ルールのアーティファクト」がコード生成ベンチマークでも同型に存在することを示す好例。

### [22] Can Good Benchmarks Contain Mistakes?
- **著者/組織**: NYU Alignment Research Group（Sam Bowman ら）
- **年**: 2024
- **URL**: https://wp.nyu.edu/arg/can-good-benchmarks-contain-mistakes/
- **関連**: GPQAの拡張セットを専門家が再検証したところ正答率65%（約1/3に誤りの可能性）であったが、「誤りがあってもベンチマークは無効にならず、専門家一致率を『測定の天井』として扱えばよい」と論じる。ドラフトの(J)「常に完璧なベンチマークは存在しないという前提」・(K)「結果解釈の精度」という穏当な立場と非常に近く、序論の結論部のトーン設計に直接応用できる。

### [23] GPQA: A Graduate-Level Google-Proof Q&A Benchmark
- **著者**: David Rein ほか
- **年**: 2023
- **URL**: https://arxiv.org/abs/2311.12022
- **関連**: 原論文自体が、専門家執筆者と2名の検証者による多段階レビューを経てもなお誤りが残りうる設計上の限界を認めている。ドラフトの(I)「評価ベンチマークを作るのは大変」という謝意の文脈を支える一次資料。

### [24] SWE-bench Verified is Flawed Despite Expert Review: UTBoost Exposes Gaps in Test Coverage
- **著者**: Daniel Kang（UTBoostの知見を紹介するブログ）
- **年**: 2025
- **URL**: https://medium.com/@danieldkang/swe-bench-verified-is-flawed-despite-expert-review-utboost-exposes-gaps-in-test-coverage-4b75c6b940c6
- **関連**: 専門家レビュー済みとされるSWE-bench Verifiedでも、500タスク中26タスクでテスト不足があり、誤ったパッチが正解として採点された事例（Lite/Verifiedでそれぞれ176/169件）を報告。ドラフトの「評価器のバグ」の具体的かつ定量的な実例として[9]と併用すると説得力が増す。

### [25] Instruction-Following Evaluation for Large Language Models（IFEval）
- **著者**: Jeffrey Zhou ほか（Google）
- **年**: 2023
- **URL**: https://arxiv.org/abs/2311.07911
- **関連**: 「検証可能な指示（verifiable instructions）」のみを対象とすることで採点を自動化・厳密化した設計思想を示す原論文。裏を返せば採点ルールに合致しない出力形式は機械的に不正解になりうるという設計上のトレードオフがあり、ドラフトの「採点ルールのアーティファクト」の一因を説明する。

### [26] The Leaderboard Illusion
- **著者**: Shivalika Singh ほか（Cohere Labs, Stanford, Princeton等）
- **年**: 2025（NeurIPS 2025）
- **URL**: https://arxiv.org/abs/2504.20879
- **関連**: Chatbot Arenaにおいて主要企業が非公開の複数バリアントをテストし最良の結果のみ公開する「best-of-N」戦略や、モデル間のサンプリング機会の不平等がランキングを歪めていたことを実証。ドラフトが扱う「設問の曖昧さ」とは異なる種類のリーダーボード整合性問題（運用・ガバナンス起因）であり、序論でスコープを明確化する（本記事は設問・採点起因の誤答に限定し、運用起因の歪みは対象外）際の対比材料として有用。

---

## 4. LLM-as-a-judge（評価器）の信頼性、二側面の枠組み、日本語・Nejumi関連の一次資料

### [27] Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena
- **著者**: Lianmin Zheng ほか
- **年**: 2023（NeurIPS 2023）
- **URL**: https://arxiv.org/abs/2306.05685
- **関連**: LLMを評価器として使うMT-Bench/Chatbot Arenaパラダイムの原論文。GPT-4判定と人間評価の一致率は80%超と高いが、位置バイアス・冗長性バイアスの存在も同時に報告しており、ドラフトの「評価器のバグ」を評価パイプライン全体（LLM-judge含む）に一般化する際の基礎文献。

### [28] Reliability without Validity: A Systematic, Large-Scale Evaluation of LLM-as-a-Judge Models Across Agreement, Consistency, and Bias
- **年**: 2026
- **URL**: https://arxiv.org/abs/2606.19544
- **関連**: 9社21種のjudgeモデルを約54万件の判定で検証し、MT-Bench上でCohenのカッパ値が一致率より33〜41ポイントも低いこと、判定モデルの順位がベンチマーク間で最大14位変動することを報告。評価器（judge）自体の信頼性が低いことを大規模に定量化した最新研究で、ドラフトが実際に発見した「評価器バグ・評価器バージョンのアーティファクト」が個別事例でなく構造的問題であることを裏付ける。

### [29] When the Judge Changes, So Does the Measurement: Auditing LLM-as-Judge Reliability
- **年**: 2026
- **URL**: https://arxiv.org/abs/2607.08535
- **関連**: 評価に使うjudgeモデルのバージョンを変えるだけで測定結果・ランキングが変動し、judgeを強化しても位置バイアス・冗長性バイアスは「軽減されるが消えない」ことを実証。ドラフトが指摘する（と推察される）「評価器バージョンのアーティファクト」という具体的現象に、タイトル・内容ともに最も直接的に対応する文献。

### [30] Measuring Massive Multitask Language Understanding（MMLU原論文）
- **著者**: Dan Hendrycks ほか
- **年**: 2020（ICLR 2021）
- **URL**: https://arxiv.org/abs/2009.03300
- **関連**: 「どのモデルでも解けない問題を残すように設計する」という思想を体現した代表的ベンチマークの原点。ドラフトの(D)の具体例として、また(I)「ベンチマークを作り公開する労力への感謝」の対象として言及すべき一次資料。

### [31] JGLUE: Japanese General Language Understanding Evaluation
- **著者**: 栗原健太郎、河原大輔、柴田知秀
- **年**: 2022（LREC 2022）
- **URL**: https://aclanthology.org/2022.lrec-1.317/
- **関連**: 翻訳に頼らずゼロから構築された日本語NLUベンチマークの代表例。Nejumiを含む日本語LLM評価エコシステムの基盤となっており、ドラフトの「日本語のLLM LEADERBOARD」(B)を支える評価データセット側の一次資料として、評価基盤構築の労力を示す好例。

### [32] llm-jp-eval: 日本語大規模言語モデルの自動評価ツール
- **著者/組織**: LLM-jp（言語処理学会年次大会2024, A8-2）
- **年**: 2024
- **URL**: https://www.anlp.jp/proceedings/annual_meeting/2024/pdf_dir/A8-2.pdf
- **関連**: 日本語圏でも「ベンチマーク汚染」「プロンプト形式による結果の変動」「評価方法論の標準化不足」が繰り返し指摘されていることを整理。ドラフトが日本語ベンチマーク（Nejumi）を対象とする以上、英語圏の議論だけでなく日本語圏固有の評価インフラの課題にも触れる根拠として重要。

### [33] Nejumi Leaderboard4のリリース！更新の背景と評価項目／Nejumi LLMリーダーボード4公開（プレスリリース）／Nejumi LLMリーダーボード4から見るモデル開発競争最前線／Nejumi LLMリーダーボード Neoからの考察
- **著者/組織**: Weights & Biases Japan（note.com公式noteおよびPR TIMES）
- **年**: 2025–2026
- **URL**:
  - https://note.com/wandb_jp/n/ncfd9d23221b3（Leaderboard4更新の背景）
  - https://prtimes.jp/main/html/rd/p/000000024.000119963.html（プレスリリース）
  - https://note.com/wandb_jp/n/nec28bede0513（開発競争最前線, 2025/12）
  - https://note.com/wandb_jp/n/n58b0df612857（Neoからの考察）
- **関連**: Nejumi運営元自身による一次資料。「Leaderboard3では上位モデル間の差分が小さくなっていた（性能頭打ち）」「翻訳タスク等は非常に高いスコアで分散が小さい一方、数学推論・コーディング・function callingは依然フロンティア領域として弁別力を保つ」「GPT-4の11月版が6月版よりわずかに性能低下した」といった記述があり、ドラフトの(E)バージョンアップの経緯、(F)フロンティアモデルの高スコア張り付き、を裏付ける最も直接的な一次資料。ただし「Neoからの考察」記事は評価器・設問の曖昧さそのものへの言及はなく、モデル間相関やインターフェース依存性の指摘にとどまる点は留意。

### [34] Evaluating LLMs is a minefield
- **著者**: Arvind Narayanan, Sayash Kapoor（Princeton University）
- **年**: 2023–2024（講演資料）
- **URL**: https://www.cs.princeton.edu/~arvindn/talks/evaluating_llms_minefield/
- **関連**: LLM評価につきまとう構造的な落とし穴（不完全なgold standard、評価者の疲労、人間評価者とLLM評価者双方に共有されるバイアス構造等）を包括的に整理した著名な講演。序論の一般的な導入部（なぜLLM評価は難しいのか）を補強する定番の引用先。

### [35] Holistic Evaluation of Language Models（HELM）
- **著者**: Percy Liang ほか（Stanford CRFM）
- **年**: 2022（継続更新）
- **URL**: https://arxiv.org/abs/2211.09110
- **関連**: 単一の指標では捉えきれない多面的な評価枠組みを提唱し、「網羅性の限界を自覚しつつ透明性を保つ」という設計思想を示す。Nejumiのような多軸リーダーボードの設計思想的な先行事例として、(C)「能力測定と指針」の二側面の議論に厚みを持たせられる。

---

## 採用しない情報源（検索はしたが不採用としたもの）

| ソース | 不採用理由 |
|---|---|
| Large Language Model Benchmarks: A Taxonomy of Capabilities, Scientific Quality Assessment, and Saturation Analysis (MDPI, doi:10.3390/make8060141) | 本文がアクセス制限（403）で内容を直接確認できず、検索スニペットのみでは具体的知見を正確に引用できないため。タイトルからは関連性が高そうだが、裏取り不十分。 |
| 日本語LLMのバイアス評価 - Nejumi LLMリーダーボード開発記（Weights & Biases Japan note） | タイトルは検索で確認したが本文を精読しておらず、ドラフトのどの主張を支持するか具体的に特定できなかったため保留。 |
| Quantifying Variance in Evaluation Benchmarks (arXiv 2406.10229) | タイトルのみ確認、内容未検証のため今回は見送り。プロンプト・シード依存でスコアが変動するという趣旨自体はドラフトと関連しそうだが、要検証。 |
| LLM Evaluation in 2026 (Medium, Milind Nair)／Zylos Research／LXT blog／digitalapplied.com／Acing AI「The LLM Evaluation Crisis」等の一般解説ブログ群 | 一次資料・査読論文ではなく、内容が他の学術ソース（AI Index Report等）の要約に留まるため、個別引用の価値が低いと判断し不採用。 |
| Coordinates of Capability: A Unified MTMM-Geometric Framework for LLM Evaluation (arXiv 2605.08522) | 統計的評価理論寄りで、序論の議論（誤答の原因分析）とは距離があり関連性が薄いため見送り。 |
| Leaving the barn door open for Clever Hans: Simple features predict LLM benchmark answers | 表層的特徴からの答え予測可能性という別テーマであり、本記事の「曖昧な設問・評価器バグ」という論点とは焦点が異なるため見送り（ただし将来的にショートカット学習の議論を加える場合は有用）。 |

---

## 総合考察：序論ドラフトへの反映提案（日本語）

現行ドラフトの骨子（① ベンチマークは能力測定と指針提示という二側面を持つ、② フロンティアモデルはすぐにベンチマークを攻略し次のステージへ移る、③ Nejumiも4回のバージョンアップを経ている、④ バージョン4ではフロンティアモデルが高スコアに張り付いている、⑤ それでも間違える問題の中には設問設計の曖昧さに起因するものがある、⑥ ベンチマーク作成者への感謝と、完璧なベンチマークは存在しないという前提での改善提案という立場）は、今回のサーベイで見つかった文献群と矛盾せず、むしろ広く支持されている。以下、具体的な追加・修正提案を優先度順に示す。

**1. 「二側面」の主張に一次資料の裏付けを追加する（最重要）**
現行ドラフトの「ベンチマークは、能力測定と今後伸ばしていきたい能力獲得にむけての指針という二つの側面がある」という一文は、実は文献上でほぼそのままの形で論じられている（Snorkel AIのブログ [16]「Benchmarks should shape the frontier, not just measure it」）。またNeurIPS 2025の構成概念妥当性サーベイ[1]やHELM[35]も、単一指標での測定と多面的な能力開発ロードマップの提示という二重機能を議論している。この一文の後に[16]を脚注として付けるだけで、序論の主張が「著者の私見」から「業界で共有された枠組み」へと格上げされる。

**2. 「すぐに攻略される」「高いスコアに張りつく」の定性的主張を定量化する**
Stanford AI Index Report 2025[8]は、GPQA/SWE-bench/MMMUが登場から1年で数十ポイント上昇し飽和したこと、トップ〜10位モデルのスコア差が11.9%→5.4%に縮小したことを具体的数値で示している。OpenAIによるSWE-bench Verified打ち切りの公式発表[9]、Epoch AIによるGPQA Diamondの精査[12]も同種の一次情報である。ドラフトの該当箇所（「すぐにベンチマークは攻略され」「ほとんど高いスコアに張りついている」）にこれらの数値を1つでも挿入すると、主張の具体性・説得力が大きく増す。Nejumi運営元自身の note記事[33]（翻訳タスク等は分散が小さく飽和、数学・コーディング・function callingは依然フロンティア領域）も併用すると、Nejumi固有の文脈として自然に接続できる。

**3. 「設問設計の曖昧さ」を、既存文献が確立した分類・数値で具体化する（記事の核心部分）**
本記事の中心的主張である「フロンティアモデルでも間違える問題の中には、問題設計が曖昧で正しく正解に辿り着く方が難しいものがある」は、[2][12][18][19][21][22][23][24]という強力な先行研究群にちょうど当てはまる、すでに確立された研究テーマである。特に MMLU-Redux[18]（6.49%に誤り、Virologyは57%）、GPQA再検証[12][22]（専門家一致率65%、誤答40問中2.25問が無効設問）、SWE-bench Verifiedの欠陥テスト（59.4%が不完全なテストケース）[9][24]、HumanEval+[21]（GPT-4のスコアが88.4%→76.2%に低下）という4つの実例は、いずれも「専門家レビュー済みとされる著名ベンチマークでも一定割合の設問・採点に欠陥がある」という同型の知見であり、Nejumiでの発見が「特異な不運」ではなく「構造的に繰り返されるパターン」であることを示す上で不可欠。[2]（Fantastic Bugs）は方法論としても本記事に最も近く、序論の終盤で「本記事のアプローチは○○[2]と同様の問題意識に基づく」と明示的に位置づけることを推奨する。

**4. 「評価器のバグ」「評価器バージョンのアーティファクト」を、判定者としてのLLM（LLM-as-a-judge）の信頼性研究として明示的に切り出す**
ドラフト本文には現れていないが、想定される分析内容（評価器バグ、評価器バージョンによる差異）は、[27][28][29]という独立した研究群がまさに扱っているテーマである。特に[29]（When the Judge Changes, So Does the Measurement）はタイトルからして本記事の知見と直接対応し、[28]は9社21種の評価器を対象に、一致率がカッパ値換算で33〜41ポイントも過大評価されていること、評価器のランキングがベンチマーク間で最大14位変動することを定量的に示している。序論に一文加え、「設問の曖昧さ」と「評価プロトコル（採点ルール・評価器）自体の不安定性」を別カテゴリとして明示的に区別すると、本記事が扱う問題の全体像がより正確に伝わる。

**5. スコープの明確化：汚染問題・リーダーボード運用問題との切り分け**
[5][6]（データ汚染サーベイ）や[26]（The Leaderboard Illusion：Chatbot Arenaでの非公開バリアント選別問題）は、ベンチマーク／リーダーボードの妥当性を脅かす別種の要因である。本記事は「誤答」＝モデルが不当に低く評価される方向の問題を扱うのに対し、汚染は不当に高く評価される方向の問題であり、[26]は設問内容ではなく運用・ガバナンスの問題である。序論で一言「本記事は汚染問題やリーダーボード運用上の公平性問題ではなく、個々の設問・採点プロトコルに起因する誤答パターンに焦点を当てる」と明記すると、後続の分析内容とのミスマッチを防げる。

**6. 「常に完璧なベンチマークは存在しない」という結びの立場を、既存研究の穏当なトーンで補強する**
[22]（Can Good Benchmarks Contain Mistakes?）は「誤りがあってもベンチマークは無効にならず、専門家一致率を測定の“天井”として扱えばよい」という結論を提示しており、[7]（The Benchmark Ceiling）も同様に「ベンチマークの弁別力は難問を作れる専門家の希少性に構造的に規定される」と論じている。これらはドラフト末尾の「常に完璧なベンチマークは存在しないという前提のもとで…参考になれば」という謙虚なトーンと完全に一致しており、そのまま引用しつつ「本記事もこの“測定の天井”の考え方に立つ」と明記すると、結論部の説得力が増す。

---

## 参照リンク一覧（番号は本文中の[n]に対応）

[1] https://arxiv.org/pdf/2511.04703
[2] https://arxiv.org/abs/2511.16842
[3] https://arxiv.org/abs/2304.15004
[4] https://arxiv.org/pdf/2407.12220
[5] https://arxiv.org/pdf/2406.04244
[6] https://arxiv.org/pdf/2310.18018
[7] https://arxiv.org/abs/2607.01254
[8] https://hai.stanford.edu/ai-index/2025-ai-index-report
[9] https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
[10] https://arxiv.org/abs/2303.08774
[11] https://www.anthropic.com/responsible-scaling-policy
[12] https://epoch.ai/gradient-updates/gpqa-diamond-whats-left
[13] https://epoch.ai/blog/what-skills-does-swe-bench-verified-evaluate
[14] https://arxiv.org/abs/2411.04872
[15] https://arxiv.org/abs/2505.11831
[16] https://snorkel.ai/blog/benchmarks-should-shape-frontier-not-just-measure-it/
[17] https://cacm.acm.org/blogcacm/goodharts-law-comes-for-every-benchmark-you-trust/
[18] https://arxiv.org/abs/2406.04127
[19] https://openreview.net/forum?id=XccDXrDNLek
[20] https://arxiv.org/abs/2406.01574
[21] https://arxiv.org/abs/2305.01210
[22] https://wp.nyu.edu/arg/can-good-benchmarks-contain-mistakes/
[23] https://arxiv.org/abs/2311.12022
[24] https://medium.com/@danieldkang/swe-bench-verified-is-flawed-despite-expert-review-utboost-exposes-gaps-in-test-coverage-4b75c6b940c6
[25] https://arxiv.org/abs/2311.07911
[26] https://arxiv.org/abs/2504.20879
[27] https://arxiv.org/abs/2306.05685
[28] https://arxiv.org/abs/2606.19544
[29] https://arxiv.org/abs/2607.08535
[30] https://arxiv.org/abs/2009.03300
[31] https://aclanthology.org/2022.lrec-1.317/
[32] https://www.anlp.jp/proceedings/annual_meeting/2024/pdf_dir/A8-2.pdf
[33] https://note.com/wandb_jp/n/ncfd9d23221b3 ; https://prtimes.jp/main/html/rd/p/000000024.000119963.html ; https://note.com/wandb_jp/n/nec28bede0513 ; https://note.com/wandb_jp/n/n58b0df612857
[34] https://www.cs.princeton.edu/~arvindn/talks/evaluating_llms_minefield/
[35] https://arxiv.org/abs/2211.09110
