# 大樂透全策略復現與多注回測

本功能的研究母體固定來自 P541B 判定為
`is_actual_prediction_method=true` 的 221 筆方法；production
`StrategyCatalog`、legacy lifecycle、ONLINE、REJECTED、RETIRED、DRY_RUN
或 replay row 是否存在，都不能縮小這個母體。

目前 packaged catalog 的狀態是：

- 總策略數 221。
- 134 筆已有 frozen source 對映、原生注數復現與因果回測證據，為
  `BACKTESTED`。
- 74 筆經 frozen source review 正式判定為 `CLOSED_UNEXECUTABLE`。
- 12 筆為 `DUPLICATE_ALIAS`。
- 1 筆為 `OWNER_DECISION_REQUIRED`。
- 11 個 replay-backed strategy ID 明確標記為第一批，`is_full_universe=false`。
  其中只有 2 個能精確對映至 221 母體，另 9 個仍需 owner 決策。

這些數字是 migration progress，不是完成宣告。只有
`OWNER_DECISION_REQUIRED` 歸零，且每筆都成為 `BACKTESTED`、
`CLOSED_UNEXECUTABLE` 或 `DUPLICATE_ALIAS` 後，才可把
`full_universe_complete` 設為 `true`。

## 清冊輸出

```bash
uv run --no-sync lottolab export-biglotto-strategy-universe \
  --output-directory /absolute/new-or-empty/output-directory
```

命令輸出 canonical JSON、CSV、progress JSON 與 `SHA256SUMS`，且拒絕覆寫同名檔案。
清冊中每筆都保存 stable strategy ID、source path、frozen commit、Git blob ID、source
SHA-256、source-derived version、P541B/R2 classification 與明示未排名原因。

若需由 frozen audit 重新產生 packaged catalog：

```bash
uv run --no-sync python tools/build_biglotto_full_strategy_catalog.py \
  --p541b /absolute/p541b_biglotto_legacy_method_classification_audit_20260709.json \
  --p541b-r2 /absolute/p541b_r2_biglotto_legacy_method_classification_audit_20260711.json \
  --replay-batch-evidence \
    src/lottolab/strategies/data/biglotto_replay_batch_exact2_evidence_v1.json \
  --random-native-evidence \
    src/lottolab/strategies/data/biglotto_legacy_random_native_evidence_v1.json \
  --history-native-evidence \
    src/lottolab/strategies/data/biglotto_legacy_history_native_evidence_v1.json \
  --static-disposition-evidence \
    src/lottolab/strategies/data/biglotto_static_disposition_evidence_v1.json \
  --output /absolute/base-catalog-v1.json

uv run --no-sync python \
  tools/apply_biglotto_history_native_wave2_evidence.py \
  --base-catalog /absolute/base-catalog-v1.json \
  --evidence \
    src/lottolab/strategies/data/biglotto_legacy_history_native_wave2_evidence_v1.json \
  --output /absolute/wave2-catalog-v1.json

uv run --no-sync python \
  tools/apply_biglotto_history_native_wave3_evidence.py \
  --base-catalog /absolute/wave2-catalog-v1.json \
  --evidence \
    src/lottolab/strategies/data/biglotto_legacy_history_native_wave3_evidence_v1.json \
  --output /absolute/wave3-catalog-v1.json

uv run --no-sync python \
  tools/apply_biglotto_static_disposition_wave4_evidence.py \
  --base-catalog /absolute/wave3-catalog-v1.json \
  --evidence \
    src/lottolab/strategies/data/biglotto_static_disposition_wave4_evidence_v1.json \
  --output /absolute/wave4-catalog-v1.json

uv run --no-sync python \
  tools/apply_biglotto_history_native_wave5_evidence.py \
  --base-catalog /absolute/wave4-catalog-v1.json \
  --evidence \
    src/lottolab/strategies/data/biglotto_legacy_history_native_wave5_evidence_v1.json \
  --output /absolute/wave5-catalog-v1.json

uv run --no-sync python \
  tools/apply_biglotto_source_native_wave6_evidence.py \
  --base-catalog /absolute/wave5-catalog-v1.json \
  --evidence \
    src/lottolab/strategies/data/biglotto_legacy_source_native_wave6_evidence_v1.json \
  --output /absolute/wave6-catalog-v1.json

uv run --no-sync python \
  tools/apply_biglotto_source_native_wave7_evidence.py \
  --base-catalog /absolute/wave6-catalog-v1.json \
  --evidence \
    src/lottolab/strategies/data/biglotto_legacy_source_native_wave7_evidence_v1.json \
  --output /absolute/wave7-catalog-v1.json

uv run --no-sync python \
  tools/apply_biglotto_source_native_wave8_evidence.py \
  --base-catalog /absolute/wave7-catalog-v1.json \
  --evidence \
    src/lottolab/strategies/data/biglotto_legacy_source_native_wave8_evidence_v1.json \
  --output /absolute/wave8-catalog-v1.json

uv run --no-sync python \
  tools/apply_biglotto_source_native_wave9_evidence.py \
  --base-catalog /absolute/wave8-catalog-v1.json \
  --evidence \
    src/lottolab/strategies/data/biglotto_legacy_source_native_wave9_evidence_v1.json \
  --output /absolute/wave9-catalog-v1.json

uv run --no-sync python \
  tools/apply_biglotto_static_disposition_wave10_evidence.py \
  --base-catalog /absolute/wave9-catalog-v1.json \
  --evidence \
    src/lottolab/strategies/data/biglotto_static_disposition_wave10_evidence_v1.json \
  --output src/lottolab/strategies/data/biglotto_full_strategy_catalog_v1.json
```

建置器不是新的 discovery scan；它 join 兩份 frozen inventory evidence 與 compact
backtest evidence，並在數量不是 221、source commit 漂移、source SHA 缺失、ID
重複、來源 DB 前後 checksum 不同，或兩個回測策略離開 exact mapping 時 fail closed。
Wave-2 overlay 只接受已知 SHA-256 的 8-backtested base catalog 與四筆完整證據，
Wave-3 overlay 再接受已知 SHA-256 的 12-backtested catalog 與三筆完整證據；
Wave-4 disposition overlay 只接受已知 SHA-256 的 15-backtested catalog，並以
frozen Git blob ID、byte size、source SHA-256 與 decisive source facts 裁決十五筆
closed 與一筆 exact duplicate alias；Wave-5 overlay 再接受其
15-backtested／21-closed／4-alias 結果及三筆完整因果證據；Wave-6 overlay
只接受已知 SHA-256 的 18-backtested catalog、十二個 frozen-source parity case
與四筆 source-native 完整因果證據；Wave-7 overlay 只接受已知 SHA-256 的
22-backtested catalog、十五個 frozen-source parity case 與五筆完整因果證據。
Wave-8 overlay 再接受已知 SHA-256 的 27-backtested catalog、十二個直接由
frozen commit blob 編譯的 parity case 與四筆完整因果證據；Wave-9 overlay
再接受已知 SHA-256 的 31-backtested catalog、九個 frozen-blob parity case
與三筆完整因果證據；Wave-10 disposition overlay 再以 exact blob identity、
source SHA-256、byte size 與 decisive source facts 正式處置四筆只委派給
unversioned localhost HTTP response 的方法。
每層套用後都重新計算 catalog checksum，且不能掃描、增刪或重新分類 221 母體。

## Exact replay 第一批

目前可證明的一對一 source/symbol 對映只有：

- `biglotto_triple_strike` →
  `tools/predict_biglotto_triple_strike.py`：replay 保存 Fourier 第 1 注，
  其後依 frozen source 因果重建 cold 與 tail，共 3 注。
- `biglotto_ts3_markov_4bet_w30` →
  `tools/backtest_biglotto_5bet_ts3markov.py`：依 `bet_index=1..4`
  保存原生 4 注順序。

可由明確指定、checksum-pinned 的 legacy SQLite 建立 evaluator input：

```bash
uv run --no-sync lottolab materialize-biglotto-replay-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

命令以 SQLite `mode=ro`、`immutable=1`、`query_only=ON` 開啟來源，讀取前後
驗證同一 SHA-256，並拒絕覆寫輸出。每個 strategy/draw 先復現原生有序票券，
再以 outcome-blind `strategy_preserving_20_ticket/v1` 建構同一 ordered-20。
建構 seed 沿用 frozen P20C namespace，且不接收 target 開獎號碼。

Legacy canonical view 以「最大主號必須大於 25」過濾資料，因此會錯漏合法的低號碼
開獎期。materializer 只在 canonical view 缺期、raw `BIG_LOTTO` 列與所有 replay
truth 的期號、日期、六主號及特別號完全一致且唯一時補回；目前 pinned DB 的 compact
evidence 記錄 21 期。這些 closed results 只會進入後續 target 的 causal history，
不會回灌至自身 prediction。

Pinned 實跑為 3,050 個成功 execution（1,550 + 1,500）與 1,552 個 target
聯集期別。compact evidence 保存 input、report、DB 的 checksum、原生注數、版本、
期別範圍與 execution 數；它是 2 策略的狀態證據，不是 11 或 221 策略完成宣告。

## Frozen factory random-native 批次

另兩個 frozen factory 方法已逐行對照來源並移植原生選號流程：

- `lottery_api/models/core_satellite.py`：先 shuffle 1..49，取前 2 號為 core，
  再依序切出 3 組各 4 號 satellite，產生 3 注。
- `lottery_api/models/zone_split.py`：依序從三個固定區間各 sample 6 號，
  產生 3 注。

舊來源使用未注入 seed 的 module-global `random`，無法逐次重播。新移植版本以
`legacy_random_native/cpython_mt19937_v1` 將 method ID、frozen source SHA-256、
target 期號、replicate 與固定 user-seed domain 組成 outcome-blind seed；仍保留
CPython MT19937 的 `shuffle`／`sample` 呼叫順序、原生 3 注順序與重複票券語意。
這是可重現的版本化復現契約，不聲稱猜回舊執行當時未保存的 RNG state。

可從同一份 checksum-pinned legacy SQLite 產生完整輸入：

```bash
uv run --no-sync lottolab materialize-biglotto-random-native-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 實跑涵蓋 2,149 期：每個方法的第一期因沒有嚴格較早的歷史 cutoff 而明示為
`CLOSED_INSUFFICIENT_HISTORY`，其餘各 2,148 期成功，共 4,296 個成功 execution
與 2 個 closed execution。每個成功 execution 先保存原生有序 3 注，再用同一
outcome-blind ordered-20 constructor 擴成 20 注；5／10／15／20 注皆取此 portfolio
的前綴。compact evidence 保存 seed protocol、source identity、input/report/DB
checksum、期別範圍、執行數與狀態分布。

這兩個方法不屬於「11 個 replay-backed ID 已全部完成」的宣告；目前 exact replay
第一批仍只有 2 個精確對映。所有結果只作描述性歷史研究。

## Frozen history-native 第一批

第二個 source-native 批次逐行移植四個 frozen entrypoint：

- `optimized_ensemble.py`：依原始 `predict(..., n_bets=1)` 產生 1 注，
  歷史不足 20 期時保留來源的 `[1,2,3,4,5,6]` fallback。
- `social_wisdom_predictor.py`：依 `generate_8_bets` 的 4 注激進、2 注平衡、
  2 注保守順序產生 8 注；用版本化 NumPy `RandomState(MT19937)` seed 取代
  原本未保存的全域 RNG state。
- `quick_ml_predict.py`：主程式依序執行 advanced ensemble 與 smart hybrid，
  因而原生為 2 注。Frozen pattern loop 在 causal history 達 5 期後必然對
  2-row tail slice 取第 3 列而拋出 `IndexError`；回測明示保存為
  `CLOSED_EXECUTION_ERROR/FROZEN_SOURCE_PATTERN_SLICE_INDEX_ERROR`，不偷改來源。
- `big_lotto_exhaustive_audit.py`：保留 50 期窗口、hot／cold／orthogonal 的
  原生 3 注順序，以版本化 CPython MT19937 seed 重現。

```bash
uv run --no-sync lottolab materialize-biglotto-history-native-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史輸入含 2,149 個 target、8,596 個 execution：6,399 個成功、
2,144 個 frozen-source execution error、53 個歷史不足。成功數依序為
2,148／2,148／4／2,099；每個成功 execution 都先保留原生注數與順序，再建立
同一 ordered-20 portfolio。Frozen-source synthetic fixture 已在相同 NumPy
與 CPython RNG seed 下逐票比對舊來源。

## Frozen history-native 第二批

再有四個 frozen source entrypoint 已完成原生語意移植：

- `anti_consensus_strategy.py`：保留來源預設 `num_sets=6` 與 1,000 次
  pattern-search 呼叫順序；原本未保存的 NumPy RNG state 改為版本化
  `RandomState(MT19937)` seed，原生為有序 6 注。
- `constraint_filter_predictor.py`：保留加權無放回選號、sum／odd-even／區間／
  consecutive 約束、最多 100 次 fallback 與 complementary 第二注，原生為有序
  2 注。
- `cooccurrence_graph.py`：依 frozen benchmark 的至少 100 期 gate，使用
  chronological history 建構共現 graph、PageRank、degree、community 與 mixed
  strategy；Candidate-K 固定為 20，但 source-native output 是最多 4 注且去重，
  兩者不混為票券數。
- `concentrated_pool_predictor.py`：由 28 號 candidate pool 產生 balanced 與
  gap-based 兩注；Candidate-K=28、原生票券數=2，兩者分欄保存。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-history-native-wave2-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史輸入同樣含 2,149 個 target 與 8,596 個 execution：8,493 個成功，
103 個 `CLOSED_INSUFFICIENT_HISTORY`。成功數依上述順序為
2,148／2,148／2,049／2,148；closed 數為 1／1／100／1。每個成功 execution
都保存 frozen source native tickets、原始順序、重複語意、版本化 seed 與嚴格較早
的 cutoff，再只建構一次 ordered-20；5／10／15／20 注均取同一 portfolio 的前綴。
Candidate-K 僅位於 execution 層，`native_generation.candidate_k` 保持空值；
所有方法的 strategy combination count 皆不適用。

## Frozen history-native 第三批

第三批保留多 entrypoint／mode 的組合語意，而不是把組合數冒充票券數：

- `engine/core_satellite.py`：依 source 文件與 CLI choice order，完整執行
  `mid_frequency`、`hot`、`cold`、`balanced` 四種
  `generate_from_history` mode；每個 mode 3 注，合計原生有序 12 注，
  `combination_count=4`。
- `negative_selection_biglotto.py`：依 frozen `__main__` 順序執行 base
  `negative_selection_predict(num_bets=4)` 與
  `enhanced_negative_predict(num_bets=4)`，`combination_count=2`。Enhanced
  source 會去除與 base 分支重複的 cluster ticket，因此全歷史原生票券數為 7 或
  8，不能硬補成 8；內部候選票券數 400／200 只保存在分支 provenance，不等同
  Candidate-K 或原生票券數。
- `quantum_random_predictor.py`：保留 `generate_8_bets` 與每注最多 50 次
  diversity search 的 call order。舊 QRNG／`secrets` entropy 未保存，因此使用
  版本化 target-stable seed 取代，並明示為 source-call-order reproduction，
  不宣稱還原舊量子 entropy。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-history-native-wave3-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史輸入含 2,149 個 target 與 6,447 個 execution：每法首期各 1 個
`CLOSED_INSUFFICIENT_HISTORY`，其餘每法 2,148 個成功，共 6,444 個成功、
3 個 closed。Candidate-K 全部不適用；Core／Negative 的 combination count
分別為 4／2，Quantum 為單一 source entrypoint。三法都只建立一個 ordered-20，
5／10／15／20 注只取同一 portfolio 的前綴。

## Frozen history-native 第五批

第五批移植三個不依賴舊大型 engine、但具有不同多注與組合語意的 deterministic
source：

- `backtest_moderate_selection.py`：依 frozen script 的比較順序，先執行單注
  `moderate_selection_strategy(last_draw_penalty=0.15)`，再執行
  `moderate_selection_2bet` 的兩注，合計原生有序 3 注；
  `combination_count=2`，不是票券數。
- `backtest_diversified_2bet.py`：保留 source `strategies` dict 的五個設定順序：
  三個 single、diversified-2bet、diversified-3bet。Flatten 後原生為 8 個位置，
  其中 hot／comeback／zone 票券依設定重複出現；重複位置不得去重，
  `combination_count=5`。
- `predict_biglotto_echo_2bet.py`：保留 `window=50`、
  `echo_weight=0.25`、Hot+Echo 先於排除已用號碼的 Cold+Echo，原生為兩個互斥
  ticket；此方法是單一 source entrypoint，沒有 combination count。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-history-native-wave5-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史輸入含 2,149 個 target 與 6,447 個 execution。Moderate 以 10 期、
Diversified 以 30 期、Echo 以 1 期作 frozen selector minimum，故成功數依序為
2,139／2,119／2,148，另有 10／30／1 個
`CLOSED_INSUFFICIENT_HISTORY`；總計 6,406 成功、41 closed。三法 Candidate-K
皆不適用，每個成功 execution 保存原生票券、順序與重複位置後，只建構一次
ordered-20。

獨立 parity CLI 直接 `git show` frozen commit 的 exact bytes，以 Python
compile/exec 載入原始 selector function；在 14 個跨方法、跨歷史長度 case 上逐票
與逐順序比對新移植版本。Materializer 與完整 backtest 都雙跑且 byte-identical；
compact evidence 保存 parity、input、report、CSV、DB 及 `SHA256SUMS` checksum。
所有 5／10／15／20 注仍只取同一 ordered-20 的前綴。

## Frozen source-native 第六批

第六批保留四個 script 的真正 entrypoint、參數 grid 與 evaluation loop 語意：

- `predict_biglotto_echo_phase2.py`：依 frozen `main` 順序先執行 2-bet，
  再執行 3-bet，flatten 後為 5 個位置；前兩注會依來源語意重複，
  `combination_count=2`。
- `backtest_biglotto_hot_stop_rebound.py`：保留 source declaration order 的八組
  `(freq_threshold, gap_threshold)` 設定，原生為有序 8 注，
  `combination_count=8`。最後十期出現過的號碼依 frozen source 一律
  `gap=0`。
- `compare_random_vs_smart.py`：來源的十次 loop 是評估 replicate，不是
  50 張原生票券；每次 strategy execution 的 native output 為
  `generate_random_5_bets` 的有序 5 注。
- `sbp_baseline_check.py`：不同 horizon 是評估執行，不是 strategy
  combination；每次 execution 的 native output 為 inline random baseline
  的有序 3 注。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave6-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

兩個隨機 script 的 module-global RNG state 或 horizon-dependent stream 未保存；
新契約保留 exact frozen `random.sample` call order，並以 method、source、target
與固定 user-seed 組成版本化 target-stable CPython MT19937 seed。這不聲稱猜回
舊執行當時的 RNG state。

Pinned 全歷史輸入含 2,149 個 target 與 8,596 個 execution：Echo Phase 2、
Hot-Stop、Random-vs-Smart、SBP 的成功數依序為
2,148／1,949／2,148／2,148，歷史不足 closed 數為 1／200／1／1；
合計 8,393 成功、203 closed。Frozen-source parity CLI 直接 compile/exec
exact Git bytes，在 12 個 deterministic 與 injected-seed random case 逐票比較；
materializer 與完整 report 均雙跑且 byte-identical。四法 Candidate-K 都不適用，
source entrypoint／parameter-grid count、native ticket count 與 ordered-20
portfolio 分欄保存，5／10／15／20 注只取同一 portfolio 前綴。

## Frozen source-native 第七批

第七批復現 Cluster Pivot／Apriori 家族的五個獨立 frozen 方法：

- `predict_biglotto_6bets_cluster.py` 與
  `predict_biglotto_7bets_cluster.py`：以 recent-first 的最近 150 期建
  co-occurrence matrix，依 source insertion/tie order 取 8／9 個 cluster
  center candidates，再依 bet loop 產生 6／7 注。Candidate-K=8／9，
  不等同原生票券數。
- `predict_biglotto_apriori.py`：以 recent-first 最近 150 期挖掘
  support ≥ 3、confidence ≥ 0.4 的規則，依不同 antecedent 的 source order
  產生最多 7 注；歷史早期可合法只產生 2–6 注。
- `backtest_apriori.py`：保留 oldest-first rolling history，依 source
  configuration order 執行 1／2／3／7 注四組設定，flatten 後為 13 個位置；
  `combination_count=4`，不是 13。規則不足時的 global-random fallback
  改用版本化 target-stable MT19937 seed。
- `predict_biglotto_best.py`：保留 CLI 預設 7 注的實際分支，先產生 6 注
  Cluster Pivot，再附加 1 注 random skew defense。Candidate-K=8、
  native ticket count=7。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave7-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史輸入含 2,149 個 target 與 10,745 個 execution：
10,726 成功、5 個首期 `CLOSED_INSUFFICIENT_HISTORY`，另有 14 個
`CLOSED_EXECUTION_ERROR`。後者逐字保存 frozen early-history 行為：
Cluster 6／7 與 Best Hybrid 各 2 個不足六碼 ticket output，Apriori predictor
有 8 個尚無規則而輸出空 portfolio；不會把它們補票或靜默略過。成功數依上述
五法為 2,146／2,146／2,140／2,148／2,146。

Parity CLI 直接 compile/exec 五份 exact Git bytes，在 15 個跨方法與歷史長度
case 上逐票、逐位置比對。兩個含 random 的方法以 injected versioned seed
比對 exact frozen call order，不聲稱恢復舊全域 RNG stream。Materializer
與完整 report 均雙跑 byte-identical；每個成功 execution 只建構一次
ordered-20，5／10／15／20 注只取同一 portfolio 前綴。

## Frozen source-native 第八批

第八批復現四個 deterministic frozen entrypoint：

- `verify_gemini_phase2_claim.py`：依 source `generate_7_bets` 順序保存
  Markov、Statistical、Deviation、Frequency、Trend、Bayesian、
  Hot-Cold Mix 共 7 個方法票券。`combination_count=7` 是方法配置數，
  不是 Candidate-K。
- `dynamic_frequency_predictor.py`：以嚴格先前歷史，在 30／50／100／200／300
  五個 window 上重播 source 的最近 50 期選窗程序，再輸出最佳 window 的 1 注。
  `combination_count=5`，原生票券數仍為 1。
- `research_cluster_enhancements.py`：依 frozen `strategies` 宣告順序保存六個
  single configuration、Orthogonal-4 與 Hybrid-5，flatten 後合法 execution
  原生為 14 或 15 個位置；`combination_count=8`。
- `optimize_3rd_bet.py`：保留 source 內兩張固定已購票券作為外部輸入，依
  尾數、弱區、頻率、遺漏與結構分搜尋第 3 注。每期只輸出 1 注，
  但 execution-level Candidate-K 為 20 或 21，候選組合搜尋數分別為
  38,760 或 54,264；source entrypoint count 仍為 1。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave8-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史輸入含 2,149 個 target 與 8,596 個 execution。Gemini、
Dynamic Frequency、Cluster Enhancements、Optimize 3rd Bet 的成功數依序為
2,049／1,949／169／2,148；歷史不足 closed 數為 100／200／100／1。
Cluster Enhancements 另有 1,880 個 `CLOSED_EXECUTION_ERROR`：frozen source
會把非空但不足六碼的 Gap／組合輸出拿去集合命中計分，新系統不把這種 partial
number list 冒充合法大樂透票券，因此逐 target 保存
`FROZEN_SOURCE_INVALID_TICKET`，並在 coverage 中完整反映。

Parity CLI 以 `git show 49a25e…:<path>` 直接讀 frozen commit blob，不使用舊
repo 目前工作樹；12 個跨方法與歷史長度 case 逐票、逐位置完全相同。
Materializer 與 overlay 前後完整 report 都雙跑 byte-identical。更新後清冊為
31 `BACKTESTED`、21 `CLOSED_UNEXECUTABLE`、4 `DUPLICATE_ALIAS`、
165 `OWNER_DECISION_REQUIRED`，仍明確 `full_universe_complete=false`。

## Frozen source-native 第九批

第九批復現三個 frozen entrypoint，保留 source 配置、原生位置順序與重複位置：

- `backtest_cluster_pivot_biglotto.py`：依 source `strategies` 宣告順序保存
  single、2／3／4-bet、Win50 2-bet、Hybrid 3／4-bet 共 7 個配置。
  歷史達 50 期時原生為 17 個位置，達 100 期後為 19 個位置；
  `combination_count=7` 是配置數，不是 Candidate-K 或票券數。
- `research_true_orthogonal.py`：保存 Cluster Pivot、Pure Frequency、
  Pure Gap、Zone Balance 四個 single，以及 2／3／4-bet Orthogonal、
  MultiWindow 與 Diversity 共 9 個配置。原生為 17–21 個位置；
  21 個位置時由既有 outcome-blind constructor 依同一規則選成 ordered-20，
  不會因 5／10／15／20 注前綴重新產號。
- `backtest_p0p1_upgrade.py`：依 source 比較順序保存 Original 2-bet、
  P0 2-bet、Original 3-bet、P0+P1 3-bet，共固定 10 個原生位置。
  第三注嚴格使用 frozen `random.Random(42 + len(history))` 呼叫順序。
  source configuration 內候選池 K 的觀測值為 12–18 或 24，保存在
  per-configuration metadata；頂層 Candidate-K 仍為不適用，
  `combination_count=4` 仍只是比較配置數。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave9-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史輸入含 2,149 個 target 與 6,447 個 execution。Cluster Pivot
benchmark、True Orthogonal、P0/P1 Upgrade 的成功數依序為
2,099／2,049／2,148，歷史不足 closed 數為 50／100／1；總計 6,296 個
成功 execution 與 151 個明示 closed。

Parity CLI 直接編譯 frozen commit blob 的 exact function definitions，在 9 個
跨方法與歷史長度 case 上逐票、逐位置完全相同。Materializer 雙跑輸入
SHA-256 均為
`2b8e84428f9aa9d4d49c0337f35129ba272b880c7773478292699577ada90f54`；
overlay 前 report file SHA-256 均為
`ae1865a09b7f02b58f292142116678a4f05cda15ee9dda5d69be291e7ac70c72`，
CSV／JSON／`SHA256SUMS` 目錄亦 byte-identical。更新後清冊為
34 `BACKTESTED`、21 `CLOSED_UNEXECUTABLE`、4 `DUPLICATE_ALIAS`、
162 `OWNER_DECISION_REQUIRED`，仍明確 `full_universe_complete=false`。

## Frozen static disposition 第十批

第十批對四個只委派給 localhost HTTP service 的 frozen backtest driver
作正式 source review。這四個檔案雖然被保留在 221 個 actual-method 母體中，
但本身只保存 model 名稱、window／`recent_count` 與 request payload；所有
六碼票券都直接複製自 `localhost:8002` response JSON。Frozen evidence 沒有
保存 response ledger、server build、model checkpoint／training artifact 或
可重播 random state，因此不能從 pinned causal history 獨立重建原生票券。

Disposition builder 直接以 frozen commit blob 驗證每個檔案的 source SHA-256、
Git blob ID、byte size 與 decisive HTTP call facts；evidence SHA-256 為
`8bc75c4a11dc14fe1b43b41fb6d5ad9be912b0b8cea0a251af50052c4faeedb3`。
四筆均以
`CLOSED_UNEXECUTABLE:EXTERNAL_HTTP_PREDICTION_RESPONSES_NOT_PRESERVED`
留在完整 universe 與 ranking，不能用目前任意啟動的 server response 冒充
歷史 frozen output。更新後清冊為 34 `BACKTESTED`、
25 `CLOSED_UNEXECUTABLE`、4 `DUPLICATE_ALIAS`、
158 `OWNER_DECISION_REQUIRED`，仍明確 `full_universe_complete=false`。

## Frozen source-native 第十一批

第十一批再復現兩個 frozen entrypoint，並明確拆開策略配置數、Candidate-K、
原生合法票券與原生位置數：

- `exhaustive_nbet_benchmark.py`：只納入 12 個實際 selector 與
  `DIVERSE_ENSEMBLE` 的 2-bet／3-bet 配置；source 明示的兩個
  `RANDOM_BASELINE` 僅是比較基準，不冒充 actual strategy output。共保留
  26 個配置、65 個有序原生位置及所有重複位置，最低因果歷史為 500 期。
- `backtest_must_hit.py`：完整保存 `top_n=6／10／15` 三個 source 配置；
  只有 Top 6 是一張合法六碼票券，Top 10 與 Top 15 則保存在
  `source_candidate_number_pools`。因此 `combination_count=3`、
  Candidate-K `(6,10,15)` 與 `native_ticket_count=1` 是三種不同語意。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave11-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史輸入含 2,149 個 target 與 4,298 個 execution。Exhaustive
N-bet 與 Must-Hit 的成功數依序為 1,649／2,099，歷史不足 closed 數為
500／50；總計 3,748 個成功 execution 與 550 個明示 closed。

Parity CLI 直接從 frozen commit AST 編譯 source function／class，在 6 個
跨方法與歷史長度 case 上驗證 canonical ticket、位置順序、重複位置與
Must-Hit Candidate-K pools。Parity artifact SHA-256 為
`c6d31d2a91a53ba7324a45eee2de51ed9af9d6c282d40a40aa6408298d2a7781`；
雙跑 materialization SHA-256 均為
`1c0ac208fdf55272f7aa3d513598b1cf3296a06eccc2539560b2c19166d4ff7c`，
evidence SHA-256 為
`f7c16a9f7b04710b1dfdd9bfdaa85d05dcde9b2a0eb2bc41278e53281a2daee3`。
Overlay 後雙跑完整 report file SHA-256 均為
`c961a1e34366a673e101de77cad0b26f00f109883eda8e028a79af57f5f25e8e`，
內部 report SHA-256 均為
`4feaa0c0e31d12697fb97d0664a9ba2b54e9cabed8e6a5d4e749f123ff4c6635`。
更新後清冊為 36 `BACKTESTED`、25 `CLOSED_UNEXECUTABLE`、
4 `DUPLICATE_ALIAS`、156 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。

## Frozen source-native 第十二批

第十二批復現 `tools/optimize_moderate_selection.py`。舊 audit 的阻擋原因只是
直接開啟 SQLite 且沒有唯讀 guard；實際 selector、參數 grid 與歷史需求都在
同一 frozen source 內。新 adapter 不執行舊 DB access，而只讀 pinned
causal history。

Source grid 依 `last_draw_penalty` 9 值、`hot_rank_min` 4 值與
`cold_gap_range` 5 值的巢狀迴圈，形成 180 個固定配置；每個配置依 source
`bet_idx=0／1` 調整 penalty 與 hot-rank，產生 2 個位置，共 360 個有序
原生位置。所有重複位置都保留。`combination_count=180` 是 grid 配置數，
不是 360 個位置，也不是 Candidate-K。

Source 原本會用同一批 300 期結果排序 grid winner；將該 winner 直接套到同一
目標期會造成 outcome leakage。因此因果 adapter 不做 target-outcome winner
selection，而是把全部 180 個固定配置依 source order 保存，再由既有
outcome-blind constructor 派生同一組 ordered-20。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave12-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史輸入含 2,149 個 target；2,099 個成功 execution，前 50 期因
source backtest minimum 明示 closed。Frozen AST parity 在 50／300／2,148
期三個案例驗證全部 180 個配置、360 個位置與重複位置，artifact SHA-256
為 `c44305dc7dd261ebad854e7ed67d0314f4892f00077d243b4bb67ca50f40c69d`。
雙跑 materialization SHA-256 均為
`5050de6ed276dce805e4d5f0bfb5334a8be1ef8adf0d2151cb8f3d081f111d42`，
evidence SHA-256 為
`f30372475a33d2d76195f5749bec86f4a47c0d9593e0d8d8da19fe09cb17dfc5`。
Overlay 後雙跑完整 report file SHA-256 均為
`4e25ac2953e606732b9c6461b7c882b462f798966cc3fe85ce44f6dd949646a1`，
內部 report SHA-256 均為
`a73a6a5dfc63a581b9dcceddeca52ce54d225d2a398c06772c554edce6389922`。
更新後清冊為 37 `BACKTESTED`、25 `CLOSED_UNEXECUTABLE`、
4 `DUPLICATE_ALIAS`、155 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。

## Frozen static disposition 第十三批

第十三批正式 review 兩個只輸出殺號／排除池的方法：

- `backtest_must_not_hit.py` 產生 Bottom 5／10／15 號碼池，評估這些號碼
  漏進開獎結果的次數與 clean rate；沒有產生任何六碼票券，也沒有定義如何
  從其補集挑出六碼。
- `backtest_p1_dynamic.py` 比較 Smart-10 與 P1 Dynamic 兩個十碼 kill set，
  只計算 leaks 與 clean-kill rate；沒有上游票券 selector，也沒有把排除池
  套用成票券的規則。

兩者均以
`CLOSED_UNEXECUTABLE:EXCLUSION_NUMBER_POOLS_WITHOUT_TICKET_CONSTRUCTION`
留在完整 universe 與每個 ranking cell；不能把 Candidate-K／排除池大小
誤當票券數，也不能憑空補一個 complement ranking。Evidence SHA-256 為
`85443d2ffead3ea2cd60b804fb5b1aae45ee354372157f94825c3c192b5ef8f1`。
Overlay 後雙跑完整 report file SHA-256 均為
`683ac2363a3b2b9ac6057cda81525145e3163aa79dc184e23b75d8114fe8c392`，
內部 report SHA-256 均為
`71f50ec921ad549caa72435e75973a5888be97d91cfb61ee3ce973a2fce74e37`。
更新後清冊為 37 `BACKTESTED`、27 `CLOSED_UNEXECUTABLE`、
4 `DUPLICATE_ALIAS`、153 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。

## Frozen source-native／static disposition 第十四批

第十四批同時完成兩個可執行 source port 與一個特別號-only 靜態處置：

- `ai_lab/scripts/graph_predictor.py` 保留指數衰減共現 graph、固定 20 次
  PageRank、Top-15 candidate pool 與 greedy clique 的原生 1 注。
  `Candidate-K=15` 只表示中間候選池，不等同票券數。
- `ai_lab/scripts/high_prize_trend_optimizer.py` 依 frozen `__main__` 的 BIG_LOTTO
  分支，保留 λ=0.01／0.02／0.03／0.05／0.07／0.10／0.15 七個設定與宣告
  順序，原生為有序 7 注；跨 λ 重複票券不得去重。
- `tools/biglotto_special_v4.py` 只對第七顆特別號產生 Top-4 單號排名，並只檢查
  實際特別號是否落入該排名；沒有任何六個主號的票券建構規則，因此以
  `CLOSED_UNEXECUTABLE:SPECIAL_NUMBER_RANKING_WITHOUT_MAIN_NUMBER_TICKET_CONSTRUCTION`
  留在完整排名。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave14-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史雙跑各含 2,149 個 target、4,298 個 execution：
4,197 個成功、101 個歷史不足；input SHA-256 均為
`ae51abaac3277dc952f52b55bd5312322ce37950f950d07b18a89645c137e176`。
三個歷史切點共六個 frozen-class parity 案例逐票一致，parity artifact SHA-256
為 `834ecc1341387943eb6ce126488eca359ca3b9f1ad0e4a4e4db205c17889eaa8`；
compact evidence SHA-256 為
`07caf36d15c42a8b34445e854bb6bb77a37035a18165861cc23513b2b192ff8a`。
Overlay 後雙跑完整 report file SHA-256 均為
`62e7c40da12c05f60e5ad8279efe7991a024afe5a9a8c30c0e8d35ac1dba424e`，
內部 report SHA-256 均為
`420dc34e28d70aa4ef439917ffd343d5d05b7a94e251ecf01e51d07f7caefaf0`。
更新後清冊為 39 `BACKTESTED`、28 `CLOSED_UNEXECUTABLE`、
4 `DUPLICATE_ALIAS`、150 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。

第十五批完成 `ai_lab/scripts/attention_replay_predictor.py` 的 frozen-source
原生復現。來源固定讀取最近 15 期，使用由舊到新遞增的 1.0–2.4 權重計算
加權頻率，再依穩定排序取六碼，原生為 1 注。Frozen class 雖會載入
`v3_deep_resonance.pth` 並執行 forward pass，但其 logits 隨後未被使用；
選號只取決於固定 recency weights 與因果歷史。為保存完整版本語意，
checkpoint、`real_biglotto.json` 及 `train_v3.py` 的 frozen blob 與 SHA-256
仍全部鎖定在 parity evidence。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave15-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史雙跑各含 2,149 個 target 與 2,149 個 execution：
2,148 個成功，第一期因不足 15 期嚴格較早歷史而明示為
`CLOSED_INSUFFICIENT_HISTORY`；input SHA-256 均為
`d8fe5c0ec3753a8b7a64bb5bbae0eedf6ec299c0bd2ac8a5e3f22db81c951b3e`。
四個歷史切點的 frozen-class parity 逐票一致，parity artifact SHA-256 為
`27af91133a4bcceb84c2f71c40003418569ab8c7f53eb387de5566bae165612e`；
compact evidence SHA-256 為
`5ab41c5df8bce3bed81e817f24837b4914308a905eb9a60c2f02ed4f5094c551`。
Overlay 後 catalog file SHA-256 為
`120efb6ff855717320568473d32ff3b46649c4ea75a728c710fcbeeb0f8168a1`，
內部 catalog SHA-256 為
`2924248b76d3ecbf43e237b6a29a002a7e2320baeeeed09f8f8e7ccbac1d8eff`。
雙跑完整 report file SHA-256 均為
`4fade373e027e9cf9ff2e6118cff97005ee1d5ca883b2fa034f0b2fd3b141352`，
內部 report SHA-256 均為
`9164abe7da6bd059dd7b24d95e7af8e93859a1d065d1dda3bb4cba45a8d9a56c`。
更新後清冊為 40 `BACKTESTED`、28 `CLOSED_UNEXECUTABLE`、
4 `DUPLICATE_ALIAS`、149 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。

第十六批完成 `tools/hot_cooccurrence_analyzer.py` 的 frozen-source
原生復現，並對兩個只分析既有 replay portfolio 的舊程式作正式 closed
處置。可執行方法先以最近 50 期頻率取最多 20 個 hot numbers，再以最近
100 期 normalized co-occurrence 和固定權重 0.3 重排，原生輸出 1 注。
實際 Candidate-K 隨可用歷史為 6／11／16／19／20，與原生票券數 1 及
唯一 source configuration 明確分離。

`analysis/p270b_outcome_blind_portfolio_geometry_power_audit.py` 的 binding
contract 明示不產生策略、只讀既有 `strategy_prediction_replays` 的 ticket-pool
geometry；`tools/p282b_big649_deduplicated_portfolio_replay.py` 只比較既有
replay tickets，Group D 僅移除 exact duplicates、從不補票，也明示不輸出
current/future live ticket。因此兩者都沒有可獨立復現的 target-draw portfolio，
分別以
`CLOSED_UNEXECUTABLE:OUTCOME_BLIND_EXISTING_PORTFOLIO_GEOMETRY_AUDIT_WITHOUT_TICKET_GENERATION`
及
`CLOSED_UNEXECUTABLE:RETROSPECTIVE_EXISTING_PORTFOLIO_DEDUP_FALSIFICATION_WITHOUT_LIVE_TICKET_OUTPUT`
留在完整排名。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave16-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史雙跑各含 2,149 個 target 與 2,149 個 execution：
2,148 個成功，第一期因沒有嚴格較早歷史而明示為
`CLOSED_INSUFFICIENT_HISTORY`；input SHA-256 均為
`4bb228b98745ccf947ecc52bdbc8c27e6bb9c9ac5881bfc3dc6637daa856be0c`。
四個歷史切點的 frozen-class parity 逐票一致，parity artifact SHA-256 為
`e4f6194577f61fbefc4074b1f7b51e267fa1a1d13f24e7c6dcf576eca6cc6a79`；
compact evidence SHA-256 為
`c2e4bfe2b2aa36ec9624d7077a466c5990f00172bde3fee4dc11f3ebd512fb00`。
Overlay 後 catalog file SHA-256 為
`8471835db7ced2da766cb6dfc4422927206fd0b9f87c2224218de1628e631d3d`，
內部 catalog SHA-256 為
`4a03137a6d7c2be3b8daa238a1292cbe35f563c800b6654c6c585888a25917dd`。
雙跑完整 report file SHA-256 均為
`d25983a615f1e11f4e7f6388479356292f2c4b4e82dffc3bbc450df3e52bf35e`，
內部 report SHA-256 均為
`1f9a4edf1321168b3672636df5f3cbf24d742d918521ec0d64628379cf6741ef`。
更新後清冊為 41 `BACKTESTED`、30 `CLOSED_UNEXECUTABLE`、
4 `DUPLICATE_ALIAS`、146 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。

第十七批完成兩個舊系統中以 module-global `random` 產生原生 portfolio
的方法。`tools/scientific_baseline_report.py` 透過 frozen
`MainZoneSmartOptimizer.generate_smart_bets(count=7)` 產生七個常態／多樣性
篩選後的 smart-random tickets，再以 EV score 穩定降冪排序；其 source
configuration count 為 1，與原生 7 注不同。`lottery_api/models/smart_multi_bet.py`
固定使用最近 300 期 recent-first 歷史，依 hot-dominant、balanced、
cold-comeback、consecutive、zone-coverage、constrained 的宣告順序產生
6 注；六個 strategy branches 是 combination count，與恰好也是 6 的
原生票券數維持不同語意，各分類池大小另行保存而非冒充 Candidate-K。

兩個 frozen source 都沒有保存可跨 target 重播的 module-global PRNG state；
因果 adapter 因此以 method/source/target/replicate/user-seed 建立
target-stable CPython MT19937 seed，並逐 execution 保存 seed material 與
digest。Frozen-class parity 使用同一 seed 直接執行舊 commit，四個歷史
切點、兩個方法共八個案例全部逐票一致；原生票券順序與任何位置重複都在
ordered-20 建構前原樣保留。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave17-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史雙跑各含 2,149 個 target、4,298 個 execution：
4,296 個成功，兩個方法的第一期各因沒有嚴格較早歷史而明示為
`CLOSED_INSUFFICIENT_HISTORY`；input SHA-256 均為
`9f2a80e5ab5d88c5938ed867a1bdafc94da68f0b63b8c8b8d527dd8a947bd06a`。
八個 frozen-class parity 案例的 artifact SHA-256 為
`f4ced21625d1c5f3021ace69920af8ba4df88626925963e4c63a14c958e921de`；
compact evidence SHA-256 為
`2362665d0e019c118c71ee468281b90046e9e61b5f5d24b60f106def9340bb91`。
Overlay 後 catalog file SHA-256 為
`b366db29a7572adf54fd09c8596c8c4ae81dd9a37bb854fe70081c9e9aa01793`，
內部 catalog SHA-256 為
`6c86158c8ba85234896e2a7ae05f05b083a5cd9716b53d9c130fb95d07c7e336`。
雙跑完整 report file SHA-256 均為
`b3347e13664dcce69c352df4386b20043444a8a3102b27668db6f44c6b64b536`，
內部 report SHA-256 均為
`1bfc0d1530de864ed64557429722f8710ad7031aa258311a16101f57b9ad353f`。
更新後清冊為 43 `BACKTESTED`、30 `CLOSED_UNEXECUTABLE`、
4 `DUPLICATE_ALIAS`、144 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。

第十八批以 frozen-source review 正式處置兩個純比較 harness，並辨識一個
selection-function duplicate alias：

- `tools/audit_raw_experts.py` 只呼叫 imported HPSB DMS 與 AI V3 predictors，
  本地隨機票券明確標為比較 baseline；檔案只累計已知 target 的 match
  distribution，沒有獨立 target portfolio。
- `tools/experimental/compare_models.py` 的 wrappers 只轉呼叫 imported LSTM、
  optimized ensemble、frequency 與 zone-balance predictors；唯一的本地選擇
  是事後依平均命中排名 model metrics，不是選號規則。
- `tools/verify_randomness_impact.py` 與
  `tools/verify_gemini_3bet_claim.py` 的 `generate_3bet_diversified` 在只移除
  說明 docstring 後，完整參數與 executable AST 均相同，function-body
  SHA-256 同為
  `97ba09dbea86ef96dbc69164ac1cec90170effb71e5bfb549bdd7d3b64a60611`。
  前者只改變重複／seed 評估流程，因此明示為後者的 `DUPLICATE_ALIAS`，
  不取得獨立排名。

Compact disposition evidence SHA-256 為
`818a6874a0c846e2268443283b633a41dafd544c1a1a917d140c2cbfbcb22f4d`。
Overlay 後 catalog file SHA-256 為
`04f1477852e201c83d10edbb0aef3794995bb896a06e740ca518c4f954396546`，
內部 catalog SHA-256 為
`048eab0b352a030a3f38634b9c5122142e5a0749e4ae569104dfeb0b85065736`。
沿用 Wave 17 位元一致的 full input 執行完整排名雙跑，report file SHA-256
均為
`857df14f36743be07b158e33b6762ae346c8ddc02d52308574f0e535e4f0be2b`，
內部 report SHA-256 均為
`8cadfc544071107ecb7eff18c92e2fb7444adc6d7d060de6d7aa81754ae3b9cc`。
更新後清冊為 43 `BACKTESTED`、32 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、141 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。

第十九批以 frozen-source review 處置五個沒有獨立大樂透 target portfolio
語意的來源：

- `tools/backtest_39lotto_comprehensive.py` 的 DB query 固定只讀
  `DAILY_539`，且 `POOL=39`、`PICK=5` 與輸出 metadata 都明示
  39 樂合彩；若改成 6/49 就已不是 frozen 方法。
- `tools/testing/test-optimization-simple.py`、
  `tools/testing/test-optimization-b.py` 與
  `tools/testing/test-all-optimizations.py` 都先建立隨機 synthetic history，
  再直接呼叫 imported `UnifiedPredictionEngine` predictors；本地只檢查呼叫
  成功與 confidence range，沒有真實 target 或獨立選號組合規則。
- `tools/backtest_ml_comprehensive_2025_biglotto.py` 的八個方法全是 imported
  predictor pass-through；本地 `backtest_method` 只計分，最後依已知結果的
  win rate 排名，沒有 source-defined target portfolio 選擇。

Compact disposition evidence SHA-256 為
`4ef9ff56ae02fce17b19134fe872c316fab4d5536b1bc42dd668fef199f51982`。
Overlay 後 catalog file SHA-256 為
`63a868f17bd6b8c3938034d18cd2c8a8d2e7be1d0a880c8d097ad9e809dd8fd1`，
內部 catalog SHA-256 為
`9d5bbcc15bc584b3bbda51bf38ad49a5e0e93b7f30ff38bfc88d82a67d9c8261`。
沿用 Wave 17 位元一致的 full input 執行完整排名雙跑，report file SHA-256
均為
`64a835173cab85e1885ba22cb06aafdbd6f1e7709856146beb7f68a3fedd18cd`，
內部 report SHA-256 均為
`d964ffd7c67b57e0029bd30bd3258998a56121054fac31713d85b7810a4d1bcb`。
更新後清冊為 43 `BACKTESTED`、37 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、136 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。

第二十批復現 root-level
`predict_biglotto_115000002_zone_balance.py` 的 frozen Zone Balance
輸出語意。來源先輸出一個 500 期窗口主推薦，再依序列印
100／200／300／500 期四個比較結果；因此原生 portfolio 保留五個位置，
包含主推薦 500 與比較 500 的位置重複，而 source configuration count
仍為四，兩者不混用。來源 `UnifiedPredictionEngine` 以字串比較期號決定
歷史方向的行為也原樣保留，沒有在移植時修正早期跨位數期號的反轉。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave20-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史雙跑各含 2,149 個 target／execution：2,148 個成功，
第一期因沒有嚴格較早歷史而明示為 `CLOSED_INSUFFICIENT_HISTORY`；
input SHA-256 均為
`b0eb82554a5f42283544935cdfe2f5857f6012385e790e052f01eb50862eb695`。
四個 frozen-method parity 案例的 artifact SHA-256 為
`7d8bf265c3bdc7229966f637a60b10c363afda57c4f2d2cab70b0641430f2365`；
compact evidence SHA-256 為
`7d9c179f7bc1b8fd51379ebc90b219442bef41014b5cb896ad9487dbaefa5abc`。
Overlay 後 catalog file SHA-256 為
`80f71bd488af67541eb4699ad5bcd2127e987ed4b3a13fdb435ad1c0a1e7ff99`，
內部 catalog SHA-256 為
`41dbed7938e716dad58bfea74fe6d2b3cf471dba030aba111314438bfb7d2d0e`。
雙跑完整 report file SHA-256 均為
`d0a092486cdaead8339176e3613309a2ffd9c8bdc88f3ee93e70b63e1ff7dea3`，
內部 report SHA-256 均為
`3478990ec2ce3f9f7aa9215f53f60d1958b2afe784cabd09f48e046ac846187a`。
更新後清冊為 44 `BACKTESTED`、37 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、135 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。

第二十一批復現 `tools/backtest_strategy_1.py` 的兩個 frozen 原生票券位置：
第一注依最近 50 期 frequency insertion-order 排名，排除連續三期都出現的
danger numbers 後取前六碼；第二注先執行 Zone Balance 500，若碰到 danger
number 則依來源規則以 510 期窗口重試，來源 broad fallback
`[1,2,3,4,5,6]` 也保留。兩個 branch 是 source combination count 2，
不等同 candidate-K；兩注順序與可能的跨 branch 重複票券均不去重。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave21-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史雙跑各含 2,149 個 target／execution：2,148 個成功，
第一期因沒有嚴格較早歷史而明示為 `CLOSED_INSUFFICIENT_HISTORY`；
input SHA-256 均為
`fa3a2909fa5eba3712d625de318805dd5295228d186b9cd9920d5b906d7bf62a`。
五個 pinned history cutoff 加一個 danger-triggered 500→510 案例的
frozen-statement parity artifact SHA-256 為
`a8b41f349dadc54dd38f9e61a96bc46c97ade90fad14013ba9aa787aba80e00c`。
完整執行中 59 期觸發 510 retry，frozen fallback 為 0 期；compact evidence
SHA-256 為
`050454d55849f06d105cb58aaa4af3f38917ffc521b5c02f867d342293e4c54a`。
Overlay 後 catalog file SHA-256 為
`b90d7121a5b47f9a93099927b890472110f90504bf124211d060d1ef2c2bf5c7`，
內部 catalog SHA-256 為
`87b00e843eca65f043e2313199ce5d984e4b433f974848da97b47cfcc64be1f2`。
雙跑最終完整 report file SHA-256 均為
`14aa25a4cec1473658f62662dc1ba6351d0f46c655bcdfb03d2f7ac897623e01`，
內部 report SHA-256 均為
`680da6f6faf2c2200a7f404d6bc6badc4099000820615b0fe61062a461221fc0`。
更新後清冊為 45 `BACKTESTED`、37 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、134 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。

第二十二批復現 `tools/predict_big_lotto_smart_2bet.py` 的兩個固定原生位置：
第一注為 recent-first 最近 50 期的 True Frequency conservative ticket，
依 `(-count, number)` 穩定排序；第二注為 recent-first 全歷史的五維
Deviation aggressive ticket，保留 frequency／zone／odd-even／high-low／gap
權重 `0.30／0.25／0.20／0.15／0.10`。兩個 predictor configuration 與兩個
原生票券位置均保持獨立語意；不重新產號、不依 target outcome 選配置。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave22-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史雙跑各含 2,149 個 target／execution：2,148 個成功，
第一期明示為 `CLOSED_INSUFFICIENT_HISTORY`；input SHA-256 均為
`35bac6eaaccac9d21c8aac87bad5cce93973129b5e6cf85773db07216b2b4bc0`。
六個 frozen-method selection parity 案例的 artifact SHA-256 為
`3eb74b3101a239e2f01f2b79e55bd0fb9b3f5d3c6a66db567bae1cd6d2ca8f87`；
compact evidence SHA-256 為
`76aa41b01d62df0aa78bf354eb1a40ffdf0fae9ffd576e527576d9ca9294ab04`。
Overlay 後 catalog file SHA-256 為
`7234a3d7006ca37d7d0985b10eb09f468242512f2cc09a33e38f0de9dec0c253`，
內部 catalog SHA-256 為
`a9049b4dfe6167731f256fae70e6d3fa4af09ecd48147b3a2a859d1501236838`。
雙跑最終完整 report file SHA-256 均為
`9973b42f18207f2e79c31cb44d7610ad7c7909bd66aa6d6566911a3a7aaa633d`，
內部 report SHA-256 均為
`fb8bc2353cfaf8e993a8fbb5d289344b8e61d9bb53e6d4bdaebd43e717516b04`。
更新後清冊為 46 `BACKTESTED`、37 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、133 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。

第二十三批復現兩個以 frozen `UnifiedPredictionEngine` 組成的 positional
portfolio。`tools/predict_5me_115000004.py` 依序保存 Statistical、
Deviation、Markov、Hot-Cold、Trend 五注；`tools/test_tme.py` 依序保存
Statistical、Deviation、Markov 三注。兩個來源中只供顯示或未使用的 kill-number
計算不會改變票券。BIG_LOTTO 的 pinned config、Statistical
`random.seed(len(history))`、Markov 1／2／3 階切換，以及舊程式以 draw 字串
判斷歷史方向的行為均原樣保存。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave23-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史包含 2,149 個 target、4,298 個 execution：兩法各有 2,148
個成功 execution，第一期各明示為 `CLOSED_INSUFFICIENT_HISTORY`。Input
SHA-256 為
`fcfc8cf2a826d56867b032023d92cc9e8973365d71e2b3e2017efd4dc2e79753`；
十二個 frozen AST selection parity 案例的 artifact SHA-256 為
`8064df37f44f695699e87071a4ffe2cb7a816405862f73d37fa14e038f73edd5`；
compact evidence SHA-256 為
`397ff15d0691c85ed4c21a331e5148fba60126501bd632246219a331781469d5`。
Overlay 後 catalog file SHA-256 為
`4ffe29730ec5d609416b33e7bc5c82dd23fca07b4900fce4d53e3b0e43f4e2d0`，
內部 catalog SHA-256 為
`4bf91cc16f300afa0eb40236fff1f7f791eacbc1d5ca462772dc795411a3dff4`。
最終 catalog 上雙跑的完整 report byte-identical；report file SHA-256 為
`5c4512c0d668a36f2a0cfb0ca8e3e47aa39f0262207646e683ec59b24fcb054a`，
內部 report SHA-256 為
`5eee79ad4ba9168e4eba422d4b4fc34c8ddb8f6cfa164a5141cd0e1aaac27e3c`。
更新後清冊為 48 `BACKTESTED`、37 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、131 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。

第二十四批復現六個共享 frozen `UnifiedPredictionEngine` 的加權候選池方法：
`biglotto_2bet_final.py`、`biglotto_3bet_optimizer.py`、ASM、DCB、
4-Bet DCB 與 ECP。每個 execution 分別保存實際 candidate-K、加權 predictor
組合數及原生 2／3／4 注；三種數量不互相代用。`tools/negative_selector.py`
的區域熵動態殺號、`Counter.most_common` 穩定順序、DCB 最近 200 期共現加權、
ASM index mapping、ECP 50 次重新 seed 的 Statistical 呼叫，以及來源短候選池
產生的非法短票 closed 語意均原樣保存。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave24-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史包含 2,149 個 target、12,894 個 execution：12,872 個成功、
6 個首期 `CLOSED_INSUFFICIENT_HISTORY`，另有 16 個 frozen source
`CLOSED_EXECUTION_ERROR`；後者是來源候選池不足以組成每注六個號碼，並已由
首 30 個 cutoff 的 frozen-class parity 逐一證實。Input SHA-256 為
`b8268ec1a7e43a771ed7b83b4c498f4683f417b8561a15994e1360d22251a1ce`；
198 個 frozen AST class parity 案例的 artifact SHA-256 為
`fdd97d8cc1d909582ec9e399ee13a692ef9af8079e10db46175bd9f0778aa3b8`；
compact evidence SHA-256 為
`e83363e8b67e6ecc0139d8ff3de7709e0ba4261d131c8b24eea3ba75500d647e`。
Overlay 後 catalog file SHA-256 為
`14e605b34aaafee07127cb75c493157c3a3460f9b30ca191967654d0cd584a44`，
內部 catalog SHA-256 為
`d2f4d085daa3da16b05b0fc1e6e02b1e8b3ffafcbc91480e7d970c6b6f3c6524`。
最終 catalog 上雙跑的完整 report byte-identical；report file SHA-256 為
`81bccb1eddea256e8bf915397af3b438b09fd55e559a666da92153dcadb6f544`，
內部 report SHA-256 為
`a2b28478dcd24c4dff68cc765dcf9c010fdf2ebb500c7f5c8b195a2853fe5821`。
更新後清冊為 54 `BACKTESTED`、37 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、125 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第二十五批復現四個 frozen source-native 方法：
`biglotto_tme_optimizer.py` 的 Statistical／Deviation／Markov／Hot-Cold
四注、CAG 共現圖、Cluster Cover 三群覆蓋，以及 ZDP 區域分散組合。CAG 與
Cluster Cover 保存 CPython integer-set iteration 的 tie order；CAG 與 ZDP
保存來源重複票券。Cluster Cover 只有 candidate-K=18 時才能由三個互斥六碼
cluster 形成合法票券，較短候選池按 frozen source 語意明示
`CLOSED_EXECUTION_ERROR`。ZDP 保存未參與出票的 base 3-bet 呼叫、固定
seed-42 區域 fallback，以及依序執行的 Deviation／Markov／Statistical 三注。
Candidate-K、source method combination count、native ticket count 與 ordered-20
portfolio count 仍是不同欄位。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave25-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史包含 2,149 個 target、8,596 個 execution：8,465 個成功、
4 個首期 `CLOSED_INSUFFICIENT_HISTORY`，以及 127 個 Cluster Cover
`CLOSED_EXECUTION_ERROR`。Input 與獨立重跑均為 byte-identical，SHA-256
為 `238f3d97c6ec218871f103d1385784f3802f74e98466b3e5d50564275e7b6900`。
Frozen parity 覆蓋 532 個方法／cutoff 案例，包括全歷史每個 Cluster closure；
artifact SHA-256 為
`90615f61aec224f72d5214b34c8bb1eec130cce83f3750472527db60729d2282`。
Compact evidence SHA-256 為
`d85cfcfd24e4b301ad2a4ce0f66aefc3c8b035e62e681826a97c3df29aeabe06`。
Overlay 後 catalog file SHA-256 為
`2606e0f710d4af2de4f65a22e4e1305308ccd3db33b823960c3ca25d86b667ad`，
內部 catalog SHA-256 為
`ae4b21d03d6c4c56b29d6ae53292d2f85671fa8ab07fdf36e867f2fb62162957`。
最終 catalog 上以原始與重跑 input 產生的完整 report byte-identical；
report file SHA-256 為
`f318eded7b3fae3e253d199708ea8ee78f39f241ff92834dc833ef58b9c9a6e4`，
內部 report SHA-256 為
`309bb317d00d2759f10ec7b75da9edd09295a588cff9daa4047450feaea7d01a`，
`SHA256SUMS` file SHA-256 為
`6d86e7b5f9d31244df3b8453cbf9a890eb99b0db0a864df67e157c7790e9a4a9`。
更新後清冊為 58 `BACKTESTED`、37 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、121 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第二十六批復現 CES constrained top-20、DMS 最近 20 個 audit target 的動態
method selection、Greedy top-18 constraint scoring、MWSC 10／20／50／100
期 multi-window consensus，以及 PCE pairwise consensus 五個 frozen
source-native 三注方法。所有 `Counter.most_common` 與 stable sort tie order、
CES／Greedy exhaustive combination order、DMS 八個 method 的宣告與評分順序、
MWSC 三個固定 slice、PCE pair insertion order、P1 kill list、原生票序與重複
票券均保存。Candidate-K、source predictor component count、native ticket count
與 ordered-20 count 仍分欄處理。

`tools/test_smh.py` 另取得正式 `CLOSED_UNEXECUTABLE` 處置：其 frozen
entrypoint 直接呼叫 module-global `random.sample` 兩次，沒有 `seed`／`setstate`
／`Random` state binding，也不接受 RNG state 參數；歷史執行前狀態未被保存。
任意補上一個 adapter seed 會改變方法，不能冒充 source-native 復現。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave26-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史包含 2,149 個 target、10,745 個 execution：10,721 個成功，
24 個 `CLOSED_INSUFFICIENT_HISTORY`；其中 DMS 需要 20 期歷史，其餘四法需要
1 期。沒有隱藏 execution error。獨立全量重跑與首跑 byte-identical，input
SHA-256 為
`664c1bf977c187cf6c0985a1cea5fdba38ffaf2f5db46ece8c57d21859855e33`。
Frozen parity 包含 165 個方法／cutoff 案例，19 個 DMS minimum-history
closure 亦逐案匹配，並同時保存 SMH 的 AST random-state disposition；
artifact SHA-256 為
`4f5e8a7007f9e1e09332d9c95dfdc0e9a4df1e14948fb842b6397b8978083329`。
Compact evidence SHA-256 為
`2fdfc4daf2bed05615ba8f664959960a6c9e64379501bd739557dfda2beae980`。
Overlay 後 catalog file SHA-256 為
`0a93137d3e1b1a779dc709f843b5fefe6debc4c66e8868a7d0a63fa731d172cd`，
內部 catalog SHA-256 為
`97b459b3835353c9a3f9cea24183c488a7c50f3a4168c62f8574f8a0484650bd`。
最終 catalog 上以兩份 byte-identical input 產生的完整 report 亦
byte-identical；report file SHA-256 為
`8768bb65064464535fffae9a6576b538900ef1bde15bc0d8f43967490000406c`，
內部 report SHA-256 為
`0a2e29b29a4e41e7b12ee333a67e62a2f7d42b21906553c73b7ccc7440c9af84`，
`SHA256SUMS` file SHA-256 為
`f704ac83378a4a042e05030b854ac786d80c61a4e5b8f8cda40ea5919f669e9a`。
更新後清冊為 63 `BACKTESTED`、38 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、115 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第二十七批復現兩個 model optimizer 與兩個 Gemini verifier：
`biglotto_2bet_optimizer.py`、`biglotto_2bet_optimizer_v2.py`、
`verify_gemini_2bet_claim.py` 與 `verify_gemini_3bet_claim.py`。四者均保存
Deviation／Markov／Statistical（V2 另含 Bayesian／Frequency）的 frozen
浮點權重、`Counter.most_common` 首次插入同分順序、Top-12／Top-18 候選池，
以及 0:6、3:9、4:10、8:14 的 positional slice。兩個 verifier 另保存來源
strict rolling harness 的 50 期最低歷史門檻；3-bet 候選池不足 14 個時，
來源回傳 `None`，因此按 frozen 語意明示 closure。Model V1 與 Gemini V1
即使在可執行期產生相同票券，也因最低歷史與 closed-result 契約不同而保留為
兩個獨立方法，不錯誤合併為 alias。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave27-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史包含 2,149 個 target、8,596 個 execution：8,483 個成功、
102 個 `CLOSED_INSUFFICIENT_HISTORY`，以及 11 個 3-bet
`FROZEN_SOURCE_CANDIDATE_POOL_BELOW_REQUIRED_SLICE` closure。兩次完整
materialization byte-identical，input SHA-256 為
`3a0b8fb891f3cc23ef977886a4405a04b8fb0a7f217189a54d9747bdd60085e0`。
Frozen high-level AST parity 包含 292 個方法／cutoff 案例，109 個
minimum-history 或 candidate-pool closure 亦逐案匹配；artifact SHA-256 為
`47103efd10d1aeed29e026a105ebcedf555222e395d1a8407114c53e8ea387cb`。
Compact evidence SHA-256 為
`848f5dcba142c1e98163e2194191e4bcaf872f51577eec266240843323c17675`。
Overlay 後 catalog file SHA-256 為
`d8b28cc828c3656b9640db2fd134e3ede82f5f30b5c49e9be454ca09f0ce9ed9`，
內部 catalog SHA-256 為
`39c5335761c4dbf9e655d2c5aa003617d076386ded36b4172b307889e50aaf5e`。
最終 catalog 上以兩份 byte-identical input 產生的完整 report 亦
byte-identical；report file SHA-256 為
`c72c1f059c0c8f2559c203513bb9f42c97451b9b4d04cc5c0fe8f650130cfb3b`，
內部 report SHA-256 為
`55ab205a18ff9c6f3138c5e67cce299d908ddd76d16ee5af35590af627a61040`，
`SHA256SUMS` file SHA-256 為
`0a419d8e6b8dab2c6bbc97f57188278df17cb64dd87def41343a55743260aef1`。
更新後清冊為 67 `BACKTESTED`、38 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、111 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第二十八批復現三個 frozen source-native portfolio：
`predict_biglotto_115000007_2bets.py`、
`predict_biglotto_7bets.py` 與 `predict_biglotto_elite7.py`。來源
`DatabaseManager.get_all_draws` 以期號整數降冪回傳，因此三者均保存
newest-first source order，而 causal evaluator 的輸入仍維持 oldest-first 並只在
entrypoint 邊界反轉。前兩者保存五個 Unified predictor 的浮點權重、
`NegativeSelector` 動態 kill-number 邏輯、被殺號設為 `-9999` 後仍留在
`Counter` 的首次插入順序，以及 Top-20／Top-30 positional slices。七注來源
在候選池不足時原生只產生 4–7 注，不補造成七注；Elite-7 保存
50／100／100／200／100／110 的 source-tail windows、六張基礎票加一張
consensus 票，且保留共識票造成的所有重複票券。Elite-7 沒有 Candidate-K；
三者的 source predictor configuration count 分別為 5、5、6，均不與原生注數
或 ordered-20 注數混用。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave28-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史包含 2,149 個 target、6,447 個 execution：6,444 個成功，以及
三個首期 `CLOSED_INSUFFICIENT_HISTORY`。兩次完整 materialization
byte-identical，input raw SHA-256 為
`34b103708c95c848364849950ba8710280a82fa7046c737615da9b05ef76caf8`，
canonical SHA-256 為
`4f67768f44cd1f0df013deb610f26800edc5e0415232e56e4c3bee2b73edbd18`。
Frozen high-level AST parity 包含 210 個方法／cutoff 案例，涵蓋七注的
15–30 Candidate-K、4–7 原生注數與 Elite-7 的 0／2／3／4 duplicate
分支；artifact SHA-256 為
`0444356d9c419d62ffbce789a0f3d4079fbab5a3ffd9103b0769cfd9ff4b9003`。
Compact evidence SHA-256 為
`3181285d28709e348d1865f4bb213b32047385ba87b837bb0191870ff89bd706`。
Overlay 後 catalog file SHA-256 為
`aa9f313aac761aef4d9dcd542b0e6ee31629107174717d16b95aac9904ffd852`，
內部 catalog SHA-256 為
`d35ea79ecccbc89dbe8584b85f7d9f621d075cabda769df94880fd31ad97e079`。
最終 catalog 上以兩份 byte-identical input 產生的完整 report 亦
byte-identical；report file SHA-256 為
`fb70fd9786be6b8477dbc674f7664639c624051f53c458eef0a93a5732085d7f`，
內部 report SHA-256 為
`83a8c5af11ef3c0fb5bc6de37af64465f1931837994b6be5879450fbd0601b88`，
`SHA256SUMS` file SHA-256 為
`d6a611ec5ae72f08ad0aae7184ace5d4e69d661b8d8c845ae4a252e52256a49c`。
更新後清冊為 70 `BACKTESTED`、38 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、108 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第二十九批復現兩個 chronological rolling Elite-7 驗證方法：
`backtest_biglotto_7bet_optimized.py` 與 `verify_elite7_claim.py`。
兩者都先把 legacy DB 的 newest-first rows 反轉為 oldest-first，再對每個 target
依序產生 Markov W50、Markov W100、Deviation W100、Deviation W200、
Statistical W100、Statistical W110 六張票，最後以未加權
`Counter.most_common(6)` 產生第七張 consensus 票。這與第二十八批 live
Elite-7 對 newest-first rows 直接取 tail 的 frozen 行為不同，不能合併。
兩個 rolling 方法也不標為 alias：前者在所有六方法失敗時有未 seed random
fallback，後者則不產生 consensus；雖然 pinned valid histories 從未走到該分支，
AST evidence 仍保存此 closed-result 差異。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave29-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史包含 2,149 個 target、4,298 個 execution：4,296 個成功，以及
兩個首期 `CLOSED_INSUFFICIENT_HISTORY`。兩次完整 materialization
byte-identical，input raw SHA-256 為
`76e8b96d8c821c5fd54dcb4158afd983b5349ae88b0f7b27a87590965653401a`，
canonical SHA-256 為
`a46fa574e4ae9f59c41f95f01a7b0c269ce70824aaee2ff282ed67cd45e67afd`。
Frozen high-level AST parity 在 source portfolio construction 後、outcome
scoring 前插入只讀 capture，涵蓋 130 個方法／cutoff 案例；artifact
SHA-256 為
`90b87ad2abaafae49e4766f6025febf07bea2c22178947dd0500bb4d9cd3a35d`。
Compact evidence SHA-256 為
`f243b727b44214ea0c15b1382c41a3d22892b6e28611f005048a808659931cf4`。
Overlay 後 catalog file SHA-256 為
`72275a74a5459e7f5fd27c8d1185e54d988abaf257e872bb0e47c256eb24ec70`，
內部 catalog SHA-256 為
`dca1c838cc8d9003e51ff84d66d68248e44fe48f9b7fbde1ee77ba9d093f0c3f`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`4fee02ba37189b4f742f64767f38779693941aa8656184ee5c66567ea2533983`，
內部 report SHA-256 為
`6cd2f5b0a71ce9c33420a85404cfa4352a9f26be332452a2ab4a9dbdba166de3`，
`SHA256SUMS` file SHA-256 為
`c7b6834a148c1437ad3652cbe8033b03cd5434886a84f600d489713576f5b72e`。
更新後清冊為 72 `BACKTESTED`、38 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、106 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第三十批復現 `backtest_10bet_biglotto.py` 的 chronological rolling 十注方法。
來源先把 legacy DB 的 newest-first rows 反轉為 oldest-first；每個 target 的
原生 portfolio 依序包含 Markov、Deviation、Statistical、Trend、Frequency、
Bayesian、Hot/Cold Mix 七張 Unified engine 票，再接 scalar EWMA
λ=0.03、0.10、0.15 三張票。Candidate-K 維持 null，source combination
count 與 native ticket count 均為 10，但仍各自保有不同語意。原生票券順序
及重複位置完整保留，再以同一 ordered-20 portfolio 提取 5／10／15／20
prefix。來源在每期 statistical call 以完整 prefix history length 重新 seed；
其 `lottery_api/requirements.txt` 固定 `numpy==1.26.2`，scalar
`numpy.exp` 由 IEEE-754 `math.exp` 等值復現並受 AST parity 證據約束。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave30-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史雙跑各含 2,149 個 target、2,149 個 execution：2,148 個成功，
以及首期 `CLOSED_INSUFFICIENT_HISTORY`。兩次完整 materialization
byte-identical，input raw SHA-256 為
`01cc1c8e17c8ea4af8d2592df93b826968ea1de470092131c462deefae187f5c`，
canonical SHA-256 為
`e2f4e84e27c1effd6ee19d9a6c810a08d1921ab056959c725a0deb55ce14795c`。
2,148 個成功 execution 的原生 duplicate count 分布為
0:1219、1:769、2:134、3:11、4:11、5:2、6:2。
Frozen high-level AST parity 在十張 source ticket 建構後、outcome scoring
前插入只讀 capture，涵蓋 65 個 cutoff，並驗證唯一 scalar `numpy.exp`
call site 與 NumPy version pin；artifact SHA-256 為
`77d5a4e74c9eb381cc049994111199ee2cb6ffebc7c3ee3af6a0e720ca01e2e4`。
Compact evidence SHA-256 為
`4041ca30bc3998612b24bc38039c4c2572c87b7c372cdb665c9364d55d22a8df`。
Overlay 後 catalog file SHA-256 為
`f9a0b7f07b949d1156deaa9b5a52ed44124df8e4f583901241bd7f6d097d3014`，
內部 catalog SHA-256 為
`1b1b66eb3821d48ab0df9e94460fae3dfd69da104fd3532b3ff2bbebd1c56b7e`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`4a41d4ac4cdc1045fbe2e51c3db5f599aea2b08b1cab44f7b4f9a5a0cef80fe5`，
內部 report SHA-256 為
`0eaca7a617e9a02edf7b167c964936010c46e7787d17a2c1aa0b45e5a34021dc`，
`SHA256SUMS` file SHA-256 為
`1e0eabe74759433b26393b3a28923ed818a5b53d05add8a897b2f55cef7ebc2c`。
更新後清冊為 73 `BACKTESTED`、38 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、105 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第三十一批復現 `predict_biglotto_radical.py` 與
`backtest_radical_strategy.py` 兩個 radical gap 方法。兩者都保留 frozen
Unified Deviation／Markov／Frequency 的 recent-first 呼叫順序與加權
`Counter` 首次插入 tie；live 方法固定排除 01–19、從 Top-12 候選產生一注，
總和低於 150 時保留 source 的一位 shift，並永久從 history 排除硬編碼期號
`115000007`。Rolling backtest 方法只使用最近 300 期 source window、保留
50 期 warm-up，依序產生排除 01–19 與排除 20–29 的兩張票。Candidate-K
維持 null；Top-12 source pools、component／gap configuration count、原生
注數與 ordered-20 注數分開保存。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave31-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史雙跑各含 2,149 個 target、4,298 個 execution，且
byte-identical。Live 方法有 2,116 個成功、1 個歷史不足 closed、32 個
source-native 不足六碼的 `CLOSED_INVALID_OUTPUT`；rolling 方法有 1,970
個成功、50 個歷史不足 closed、129 個 `CLOSED_INVALID_OUTPUT`。後者成功
execution 中有 9 期兩張原生票完全重複，均保留原位。Input raw SHA-256 為
`eb9636d04e229aea0063886d76160710f73a17c64a86027f318e07e4f777290c`，
canonical SHA-256 為
`3956dd4cb618ac415d0ffe40b1b1512146249b735ceba15bb6ec81d93c354b35`。
Frozen class-method AST parity 涵蓋 130 個方法／cutoff 案例，其中 61 個
明示 closed，artifact SHA-256 為
`c93e878890ff14b95a03e01625d782531fd97f9962481b80f0f9f3953ac75917`。
Compact evidence SHA-256 為
`4faa3f7f4b6b2fcd647b268557259748a67f1a61d3f2340282203d31413fb97a`。
Overlay 後 catalog file SHA-256 為
`c63b3d4db5a7d8b2d07801bf093505654a855b2f35f19191ab4e40e8f3377b31`，
內部 catalog SHA-256 為
`e078f1b01daf9d3a24ed1770f0f7b27d41c4e4bcb713cd375c781f02876f09b9`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`fbae34f98978502569a516b1ee5b60013235d5c42687067190dd0000c1cfe9ed`，
內部 report SHA-256 為
`3aea88cf48c6d76caf83cfc93d8f6a5296e37954775fdf3b031d6e5059701901`，
`SHA256SUMS` file SHA-256 為
`5e998daf4315196e698a8793e35aa56714fff5ba1a884e50ce443ef84f076a29`。
更新後清冊為 75 `BACKTESTED`、38 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、103 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第三十二批復現 `research_variant_history.py` 的十一個 frozen
predictor/window 位置：Deviation、Statistical 與 Markov 各使用
50／100／200 期，Frequency 使用 50 期，Zone Balance 使用 100 期。
每個 target 都只取嚴格早於目標期的 oldest-first trailing window；
Candidate-K 維持 null，而來源 variant configuration count、11 張原生票與
ordered-20 注數各自保存。Statistical 三個位置保留來源
`random.seed(len(history))`，所有位置與原生重複票券均不去重。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave32-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史共有 2,149 個 target，其中 2,129 個成功、20 個明確
`CLOSED_INSUFFICIENT_HISTORY`。成功 execution 的原生重複票券數分布為
0:1799、1:224、2:24、3:34、4:15、5:2、6:31。Input raw SHA-256 為
`59ccb1b1b7ea4296598e9bfdac676bcf5d0d3497f94e7c69a3433d7290eb212c`，
canonical SHA-256 為
`91a7fbd0c379e3e25f7e741c44d722404cd364652012a69055a59b9662c52598`。
Frozen high-level wrapper parity 涵蓋 480 個 target，每個案例均核對
11 個方法位置與因果 window，artifact SHA-256 為
`5a777d036d292676a273ae5acfbc999124859ca689ee051a4c0e8391ef793c81`。
Compact evidence SHA-256 為
`6aec14a06944aa0ec97de92eb2c0ba2b02557ab9c671988d245f9c63de1314c1`。
Overlay 後 catalog file SHA-256 為
`4cb3f616e07db272162b880b6eb4472bd2050378847bff4070f88449afacd49f`，
內部 catalog SHA-256 為
`0316f019dea91815a451d1a71481d79e910b5760c842d2223e808acf8cc2337d`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`c8de5fc183e74fff6db360727ffa81f9f217413da75053867de02699c533fc5f`，
內部 report SHA-256 為
`7c9672dcc7375f0cdf1a913a00ff76e40fd98f649758419957ae84fc227142c5`，
`SHA256SUMS` file SHA-256 為
`b7e3adbe2b9203775b6b4c8d45b1ea49f2906b5aaa6ffdf1febd99c1b6e8a743`。
更新後清冊為 76 `BACKTESTED`、38 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、102 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第三十三批復現 `feasibility_benchmark_biglotto.py` 的六個 frozen benchmark
configuration，依序為 Markov、Deviation、Statistical、Bayesian 四個單注，
Markov + Deviation 雙注，以及 Markov／Deviation／Statistical
unweighted Counter Top-12 的兩個不重疊切片，共八個原生票券位置。
Candidate-K 維持 null；Top-12 candidate pool、六個 source configuration、
八張原生票與 ordered-20 注數分開保存。來源 wrapper 的 seed 42 以及
Statistical 的 `random.seed(len(history))` 均保留。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave33-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史共有 2,149 個 target，其中 2,148 個成功、首期 1 個明確
`CLOSED_INSUFFICIENT_HISTORY`。成功 execution 的原生重複票券數分布為
2:1028、3:266、4:854，均保留原位；Top-12 pool 每次均完整。
Input raw SHA-256 為
`ea97a6d3086fad923ae9da5f2cf1c93313b27037fc9cd44575a3a1bea21a2a8b`，
canonical SHA-256 為
`6f8606c98077ed86d8fe0bd0fc10267cc9e087c60e581f2b938230a42b7f7094`。
Frozen wrapper AST parity 涵蓋 65 個 history cutoff，artifact SHA-256 為
`c6dbbf82db8a8e39de2b544f53b8ef5d4bd169a52c39efb4cb099c7ce429a339`。
Compact evidence SHA-256 為
`034a6d6b34556f6122b03f1fe1df8c31733875d3342861811a3dad42fef4ad4e`。
Overlay 後 catalog file SHA-256 為
`a025d60b023b0bc641ee3410653d49296c1984b65eba90713ae0c928ec1810e7`，
內部 catalog SHA-256 為
`8d6a97dd1f2565da903d8ae86ff75503f0d97a748f6d96e9f9a36391801fd719`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`85f3149751ae6479d9646f96e8bfc03b3c1148f804875be63dbeb0bea47799af`，
內部 report SHA-256 為
`76a198c10719eb21a7ab171b2348600b3e8f16dedfee5c8c095fb4d79b653594`，
`SHA256SUMS` file SHA-256 為
`0fcd0b46873b33a2fcf095fe0ed03c5aee9990f12548d6ac0e29c5b400b77faa`。
更新後清冊為 77 `BACKTESTED`、38 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、101 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第三十四批復現 `auto_optimizer_alpha.py` 的 frozen AutoOptimizer
五種 predictor 與五種 window 組合。原生 portfolio 依 method-major
順序保留 Zone Balance、Bayesian、Trend、Frequency、Deviation，各自再依
50／100／200／300／500 期排列，共 25 個位置。每個 target 都只取嚴格早於
目標期的 oldest-first trailing window；Candidate-K 維持 null，而 25 個
source configuration、25 張原生票與 ordered-20 注數分開保存。來源的
retrospective champion 報表不會被用作未來 target 的選號證據，跨 window
重複票券亦不去重。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave34-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史共有 2,149 個 target，其中 2,148 個成功、首期 1 個明確
`CLOSED_INSUFFICIENT_HISTORY`。成功 execution 的原生重複票券數為
3 至 23，所有重複位置均原樣保留。兩份 input byte-identical；raw SHA-256
為
`7f0ac4e7289af91e70a420b386206f711dfc3e66e6e26a079263efeabb1427e9`，
canonical SHA-256 為
`c893cfea5294e3b778acd1bb3d70ea195af2d6730a3a87ea0d9b65442e1770bd`。
Frozen class-method parity 涵蓋 65 個 history cutoff，artifact SHA-256 為
`36ec1118ac9783579d27de74f30fccec8d2ba2965c73b32bd8372ca69b61ee73`。
Compact evidence SHA-256 為
`98246f7a250329bd83e1b8589c510fb2c540d92ce56e51f45ffccbbdeb07e94d`。
Overlay 後 catalog file SHA-256 為
`a634edc4008e3935475449e791e286672f4e645c56918279a739a65370a0074a`，
內部 catalog SHA-256 為
`3d17d7c7d030dc1309045beeef6172bdbe1a839a1f28eaf6a5763422dc279d0a`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`64c1d2faade13ed2e34b9d90ffc7cb318d140c11582d27c841944bfefe4ec77d`，
內部 report SHA-256 為
`8d611ae6a2dad1747885c94645e9ea88cb929e4ebae64f4c6ad0fdc30e923677`，
`SHA256SUMS` file SHA-256 為
`42e71810149b55fc7ee52af0ad9282c9e5134a7ff9df6078adde45f7f9e7de9d`。
更新後清冊為 78 `BACKTESTED`、38 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、100 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第三十五批對 frozen AI-Lab 模型 artifact 做結構相容性裁決。
`benchmark_hybrid.py` 與 `benchmark_rl.py` 都以無參數
`HybridLotteryTransformer()` 建立 frozen 預設 9-feature
`stat_projector`，但其 `HybridPredictor` 只產生 7 維統計特徵。
`hybrid_best.pth` 與 `rl_gen3_best.pth` 的 frozen
`stat_projector.weight` 也都是 32×7，SHA-256 分別為
`d363b1203c44791d4cd516d40dee738353486d77b344d4bd72d2a9049e29a082`
及
`c3a4057535722bb9e7bd45d422d7cb0257f918d22582aab249016e8e8c60fdf5`。
兩個程式都在任何 `predict` 呼叫前執行 strict `load_state_dict`，因此會因
32×7 checkpoint 與 32×9 model shape 不相容而停止，無法產生原生票券。
這不是忽略方法，而是以
`FROZEN_MODEL_CHECKPOINT_ARCHITECTURE_INCOMPATIBLE` 正式標記為
`CLOSED_UNEXECUTABLE`。

證據 builder 不匯入或執行 PyTorch；它從 frozen Git blob 讀取來源與
checkpoint，並以受限 unpickler 只解析 tensor shape metadata。兩次 evidence
輸出 byte-identical，SHA-256 為
`71eae1c4b8193485734087b765a153f738be90e1d2b3267cf3572e94f5d8be2a`。
Overlay 後 catalog file SHA-256 為
`d2d15de8a6ee168def33636c9d6a724bc780b4218f24866be7e6ab8f4473a846`，
內部 catalog SHA-256 為
`fca99742869404dd397cdb6cdc2b0755db2d7ff591002e2b30004c7a9e57fab9`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`75cd6db8b4fcc65b36cec0482fc394e7db9de1748cc38496d036295f300766be`，
內部 report SHA-256 為
`dffd0c38361098279ec9a6d1134b484e7ad76fc9aa9a050d1fa21ba0bfd498a6`，
`SHA256SUMS` file SHA-256 為
`7d13e4cdb25b78b5e6185edca9aea003e0d157ff16efac024380a3d0df99eee6`。
更新後清冊為 78 `BACKTESTED`、40 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、98 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第三十六批對 frozen 神經模型的訓練隨機狀態做可重現性裁決。
`lstm_attention_predictor.py` 在首次呼叫時建立隨機初始權重、以
`shuffle=True` 的 DataLoader 訓練，然後把模型保存在 module-global
singleton；selection entrypoint 沒有綁定 Python／NumPy／PyTorch seed、
RNG pre-state、deterministic 設定或 checkpoint identity。
`perball_lstm.py` 的主 entrypoint 同樣在每次呼叫建立並訓練新的
TensorFlow/Keras 模型，`model.fit` 與初始權重都沒有綁定 seed 或 pre-state。
兩者的訓練隨機性會直接改變原生票券；事後補一個新 seed 或 reset policy 會
創造不同方法，因此正式以
`UNBOUND_NEURAL_TRAINING_RANDOMNESS_WITHOUT_FROZEN_PRESTATE` 標記為
`CLOSED_UNEXECUTABLE`。

兩次 evidence 輸出 byte-identical，SHA-256 為
`7e88c5242c7f738afaed6c48b7bc74d08b4c7472ac87e8334e7eac66aa14ce7e`。
Overlay 後 catalog file SHA-256 為
`30927825f4e8dd7ecfb088e6492b62ec36f5936f32880cb242c51d5ba80ea798`，
內部 catalog SHA-256 為
`77987cc9a0bc6c2f048a946a2c09143730ebe0bb4b2dac12ce989614bbb92513`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`8d1a342960dabc4d1f70da593862883bbc424e6a9a57bd710b01f11a0fc80fde`，
內部 report SHA-256 為
`1e5c1f4501d922aa14702242ac7e5690e072ebf3042950f35fa3522691bc9281`，
`SHA256SUMS` file SHA-256 為
`f8c61a2f4799d7ce0b6161f2a6f3267a00db7a7fbec4035c32828fbfe25e8d0e`。
更新後清冊為 78 `BACKTESTED`、42 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、96 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第三十七批對會直接改變原生注單的未綁定隨機狀態做 frozen-source 裁決。
`multi_bet_optimizer.py` 每次呼叫都先建立並訓練新的 Per-Ball LSTM；來源沒有
綁定 neural RNG pre-state 或 checkpoint，且第二注在沒有 anomaly 時還會走
temperature sampling。`coverage_strategy_research.py` 的所有 portfolio 都經過
未 seed 的 `random.shuffle`／`sample`，信號池與 fallback 也會消耗 module-global
RNG；`covering_research.py` 同樣先隨機建池，再 shuffle 後切成有序票券。三者都
沒有保存歷史 RNG pre-state，事後指定任意 seed 會創造不同方法，因此正式以
`UNBOUND_TICKET_GENERATION_RANDOMNESS_WITHOUT_FROZEN_PRESTATE` 標記為
`CLOSED_UNEXECUTABLE`。

兩次 evidence 輸出 byte-identical，SHA-256 為
`01b17fb3af8d5bdb8cd2b9302ed1b7f71e6ee214b0fd66a7e8fea2f8dac976d0`。
Overlay 後 catalog file SHA-256 為
`4e47c7c8bb4c6160140f8d2578e594a14c7a86afc508ef3482bff872c1c33223`，
內部 catalog SHA-256 為
`01c54ea1d5ce2f578663d4639de5d2f12f6dc39b6a2158f4118a03cdc253753a`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`10e21063034bed0e0292a727bed61891314aaffdb09c2aec0fc148d1a4b256d5`，
內部 report SHA-256 為
`397e5e50aa7ba4ad69430bd2c4f43ea8e9cfa3562f2a1bcef08fca3342170b1d`，
`SHA256SUMS` file SHA-256 為
`3e40b0bbd9494cde81e5828ffb4b4cf19570695b0a5b647f63acae0564b9601e`。
更新後清冊為 78 `BACKTESTED`、45 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、93 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第三十八批把 frozen source 中位於實際 native portfolio 路徑、而非只用於
統計檢定的未綁定 stochastic selection 分開裁決。九個來源涵蓋：每次都以
unseeded weighted sampling 執行 constrained／enhanced ensemble 的
`enhanced_predictor.py` 與其 consumers `dynamic_ensemble_predictor.py`、
`multi_bet_optimizer.py`；用 `random.sample` 初始化並 mutation 兩注的
`mcts_portfolio_optimizer.py`；首次預測即初始化並 shuffle-train 的
`transformer_model.py`；以及把 unseeded Monte Carlo、Random 3-Bet、
Random Chaos 或 Random/LSTM-AR ticket 當成正式 source configuration 的
`benchmark_dual_bet.py`、`benchmark_new_strategies.py`、
`predict_biglotto_6bets_optimized.py`、`strategy_leaderboard.py`。
這些來源沒有綁定 seed、RNG pre-state 或對應 ticket ledger，正式以
`UNBOUND_STOCHASTIC_NATIVE_SELECTION_WITHOUT_FROZEN_PRESTATE` 標記為
`CLOSED_UNEXECUTABLE`。

兩次 evidence 輸出 byte-identical，SHA-256 為
`c1a4e85a706d3a5390da41e21153e1c34e0f5361c144eb49ef29e5bcf2bb982f`。
Overlay 後 catalog file SHA-256 為
`0cde129c724bdf0048ad295a198c902d2e1f6e668321becbc998ab18b86c7cfa`，
內部 catalog SHA-256 為
`660d35418eedb2c7daab0911fd4ade3aa33cd0ccbf479c78ac2a0366afa212a9`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`a8e8c26c3a596da8b47d7bc764ae260ad89ef15149f0c97ab0a2d05c64b512fd`，
內部 report SHA-256 為
`bbaf0784c5b8f68920b7221b0cf15e39074391c1b9cc6e1e51c55d54b420bc1d`，
`SHA256SUMS` file SHA-256 為
`acd35866fd5f32586410ed10b0f97eb6933040080317ad5981028fe123074d92`。
更新後清冊為 78 `BACKTESTED`、54 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、84 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第三十九批延伸 frozen-source dependency review，但只處理 caller 沒有重新
綁定 stochastic state 的實際出票路徑。`auto_optimizer.py` 把 unseeded
constrained selector 納入每一組 method/window 搜尋，隨機回測分數可改變最後
保存的配置；`meta_learning.py` 在 torch 可用時直接用未訓練、隨機初始化的
Linear layers 排名出票；`ultra_optimized_predictor.py` 的正常、短歷史與多注
路徑都會 unseeded sample。`optimized_predictor.py` 及六個工具
`backtest_phase1_comparison.py`、`find_best_test_periods.py`、
`generate_final_predictions.py`、`generate_v7_predictions.py`、
`predict_big_lotto_115000003.py`、`predict_biglotto_7bets_optimized.py`
則把 Wave 38 已證明沒有 frozen pre-state 的 diversified optimizer 輸出直接
當成自己的 ordered native portfolio，且沒有 caller seed 或輸出 ledger。
這十個來源正式以
`UNBOUND_OR_TRANSITIVE_STOCHASTIC_NATIVE_SELECTION_WITHOUT_FROZEN_PRESTATE`
標記為 `CLOSED_UNEXECUTABLE`；有明確 `seed=42` 的其他 caller 不在本批處置。

兩次 evidence 輸出 byte-identical，SHA-256 為
`b508a1e9a6f3096be48fe181d5e3cb4253cfb07d1d4889de3db1ca8c9adab974`。
Overlay 後 catalog file SHA-256 為
`f013536b311d93ee2af19f9d6041701aebc3f4fd930e073b79e301147968ad0e`，
內部 catalog SHA-256 為
`9970c56da9efc613fb9d2b033bb613dc6d6124a9227458183b303b2a369c6141`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`28db1778cde4fd2f7ea53e6f51b5d472c9b39b3dbcc1aa39681f28b978032967`，
內部 report SHA-256 為
`c7be53d4b401aa7625ac48ad2086c40bba831a1371ca6c2f8e329d4976c7c3ed`，
`SHA256SUMS` file SHA-256 為
`82cec6ae51660d57e9829bced5077c2e7d1890329d8971529e4b86099bff19e0`。
更新後清冊為 78 `BACKTESTED`、64 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、74 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第四十批復現 `backtest_biglotto_portfolio.py` 的 deterministic
Cluster Pivot「3+1」portfolio。來源先保留 `cluster_pivot_3bet` 的三張核心票，
再嘗試加入 `cluster_pivot_hybrid(..., num_bets=1)` 的第一張票；若與核心票
完全重複則抑制，接著最多加入一張
`cluster_pivot_windowed(..., window=50, num_bets=1)` 補票，最後截為四張。
來源內的 seeded random baseline 只用於比較，不參與 native strategy selection。
Candidate-K 維持 null，三個 source portfolio component、四張原生票與
ordered-20 注數分開保存。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave40-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史共有 2,149 個 target，其中 2,049 個成功、前 100 個以
`CLOSED_INSUFFICIENT_HISTORY` 明確結案。所有成功 execution 都保留四張
原生票，且 frozen 行為均為 hybrid 第一張與核心票重複後抑制，再加入
window-50 補票。Input raw SHA-256 為
`5ae1dfd4ce5e2f96c2f0a9be48f75d5fa8195a3d066f5fee7031580a787dbc82`，
canonical SHA-256 為
`da07e6a3d12d4e9b097fdc718fb9400f5461a51e1c1ada405a08d60b1b8b6957`。
Frozen source 與 support-function parity 涵蓋 65 個 history cutoff，
parity file SHA-256 為
`30b4e3852fa1a64d2f2e433f9b1234754e80b11eb03edcbbe7efdec4d086e0ce`，
內部 parity SHA-256 為
`70d1e24808e9dba9df77d22a6f74aac2770c110228dba73c0c06832d5da63852`。
Compact evidence SHA-256 為
`26db8ff17a7040b9f424026b131d06837f36d80d270e40c6f6cd594959677ca1`。
Overlay 後 catalog file SHA-256 為
`a1041e8fac30b9680a3b36adbf4a0b65063e2e3c7ea8482eb1bb7f08283dc332`，
內部 catalog SHA-256 為
`ed095e2bd580075b42f6be5239bbb2bbf7cf7552e551aee96b9ab8a7c7dba88f`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`2dcba21e57dc5de260e40792de801cc21696c394875e817a6123b9356401cffd`，
內部 report SHA-256 為
`f55bf17e3ae7279c0198d66153ccb79b51b3e00c5e5d9bb96c8b041b82d794fc`，
`SHA256SUMS` file SHA-256 為
`2d4e3ab1e8e67c691d71e33390d2fdc4477e4a589ad5b90d216f3d7c6c107153`。
更新後清冊為 79 `BACKTESTED`、64 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、73 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第四十一批復現 `backtest_graph_method.py` 的兩個 source configuration：
先以最近最多 500 期建立 1..49 共現圖，依 frozen NetworkX 3.2.1
`degree_centrality` 與 `betweenness_centrality(weight="weight")` 語意產生
graph-centrality 票，再保留 unified predictor 的 deviation baseline 票。
Candidate-K 維持 null，兩個 source configuration、兩張原生票與
ordered-20 注數分開保存；原生票序固定為 graph 後 deviation。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-source-native-wave41-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Pinned 全歷史共有 2,149 個 target，其中 2,099 個成功、前 50 個以
`CLOSED_INSUFFICIENT_HISTORY` 明確結案。Input raw SHA-256 為
`fbc8710f9771b755781f30fca3907cfe19995dc89b80d3874d689cac8064b1b3`，
canonical SHA-256 為
`f7c870cd7ac52980f728afa6a38d554db5eca2fc5f68685f3effd860f7eb412e`。
Frozen source graph parity 在裝有 NetworkX 3.2.1 的隔離 reference
interpreter 上涵蓋 65 個 history cutoff，parity file SHA-256 為
`d5585ed5acaa4807528c10a34668bcc423c34b7b20334d3a631626b8062127d7`，
內部 parity SHA-256 為
`bbe310f97a66eb4f2b7163e14f2ef373721a4cd807f277f628b0744a79e11863`。
Compact evidence SHA-256 為
`03afecea6e2288ca34258d8299a557bcff20dc1aa3a268962b4aa652c58f859f`。
Overlay 後 catalog file SHA-256 為
`bc95d77aa4c6b4e68e511f80224111ba7cb685017932256b2367e124ca1699cd`，
內部 catalog SHA-256 為
`2296f709d572f62dd4a77033cd8a5d7e5ac62cc57c7c718d4e20392636998b3a`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`ea5281fc81defc6ee96a7afd843595cdcfccbb5e673e2c58e928b86673224f35`，
內部 report SHA-256 為
`64913bc743f5c4a7a87613f956a8b9f042d0dec0c26a1669a180c2a361fbc1c4`，
`SHA256SUMS` file SHA-256 為
`ef3df0d722bf63d62ce052e5aef9bfc3939a857d0bde9c9af8d2a0b6e8c2c9ba`。
更新後清冊為 80 `BACKTESTED`、64 `CLOSED_UNEXECUTABLE`、
5 `DUPLICATE_ALIAS`、72 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第四十二批對兩個 `AdvancedStrategies` pass-through wrapper 做 frozen AST
alias 裁決。`predict_v9_anomaly_cluster.py` 的大樂透路徑只呼叫
`anomaly_cluster_predict`，`final_draw_v11.py` 的大樂透路徑只呼叫
`anomaly_cluster_v11_predict`；兩者都直接取上游 `details["bets"]` 後格式化
輸出，沒有新增選號、排序或 portfolio 選擇。因此兩列保留在 221 母體中並
標成指向 `advanced_strategies.py` 清冊列的 `DUPLICATE_ALIAS`，不重複排行。
上游 canonical row 仍為 `OWNER_DECISION_REQUIRED`，本批沒有把它提前算成
已復現或已回測。

兩次 evidence 輸出 byte-identical，SHA-256 為
`1ed8c1145ccf6ae10e82085e8a19fb069888f8cd3a1e66054a0a9844b180d9f1`。
Overlay 後 catalog file SHA-256 為
`41c9f7b2d711b1c9f7105d204575d053a40799dee0d31a2e7bfc94809ce8898f`，
內部 catalog SHA-256 為
`792ed501402cf371412515e7364a566bb1e8635fbc8eee74a1c2baf4aca8c468`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`d87a03e2bc5f62e000a7b0cf8a73826201d5e135ce13e962a8187ae9ddce0d31`，
內部 report SHA-256 為
`e27f6fa13673254ca952f3f1a49b4d999eb7046caf51005a72073ce99faf0f26`，
`SHA256SUMS` file SHA-256 為
`64555320c2d6f2999af97784efe4fc23e88547609925a867ab22160ee5d53d3b`。
更新後清冊為 80 `BACKTESTED`、64 `CLOSED_UNEXECUTABLE`、
7 `DUPLICATE_ALIAS`、70 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第四十三批對 `advanced_bayesian_analyzer.py` 的 frozen output contract
正式裁決。`recommend_strategy` 最多回傳十個 hot candidates 或十個 cold
candidates，奇偶偏差分支只回傳比例文字；來源沒有六碼票券、候選轉票規則、
原生票序或 portfolio 注數。Candidate-K 與票券數不可混用，因此不能把
候選列表任意截成前六名。本列以
`VARIABLE_LENGTH_CANDIDATE_RECOMMENDATIONS_WITHOUT_SOURCE_DEFINED_LEGAL_TICKET`
標成 `CLOSED_UNEXECUTABLE`，同時保存
`UP_TO_TEN_HOT_OR_COLD_RECOMMENDATION_CANDIDATES` 的候選語意。

兩次 evidence 輸出 byte-identical，SHA-256 為
`7982e99da15ef4518d029b01a4ad3675dca6255d8a659186e564bcc630dce465`。
Overlay 後 catalog file SHA-256 為
`e5c40c227be80624a9134e44e4c6df2dd27157904faca612e3f103d8a663a351`，
內部 catalog SHA-256 為
`c73ae9a4cb6aa872e839031b17975011b8ea0bb1b241336ab172a775afd3511a`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`c10deba0dd368d27ec7ba7261de1da4a165da363a3154b905327d035a37de01c`，
內部 report SHA-256 為
`33465e2d4508a1369744dbf2fccf7bb3f9dae3de3ea361d47c0e9123fd32a410`，
`SHA256SUMS` file SHA-256 為
`745e994f2fd29d1d7af322623740ed7a6f9dc5d1ea52f26f6368b204c4fc61f3`。
更新後清冊為 80 `BACKTESTED`、65 `CLOSED_UNEXECUTABLE`、
7 `DUPLICATE_ALIAS`、69 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第四十四批復現三個具有本地 predictor class 與 frozen checkpoint 的實際方法：
`benchmark_ai.py` 的 Transformer、`benchmark_ai_zdp.py` 的
Transformer + ZDP，以及 `benchmark_v3.py` 的 U-HPE V3。各檔案中的 DMS
比較列，以及 ZDP benchmark 匯入的 raw Transformer 比較列，只是 imported
benchmark rows，不重複計為本地 source configuration。每個方法因此保留一張
原生票；Candidate-K 為完整 49 個合法號碼排名，`combination_count` 為 null，
三者與 ordered-20 注數保持不同語意。

兩個 checkpoint 首次出現在 Git commit
`e56ce9f196342e9d50edc9fd19c42f72c1fa2047`，時間為
`2026-02-24T11:02:20+08:00`。由於 checkpoint 本身沒有可證明更早 cutoff 的
逐期訓練 lineage，本批採保守因果界線：target draw date 必須嚴格晚於該
Git introduction local date。三個方法各在 48 期成功執行，較早的 2,101 期均以
`TARGET_NOT_STRICTLY_AFTER_CHECKPOINT_GIT_INTRODUCTION_LOCAL_DATE`
明確 `CLOSED_REJECTED`，不讓較晚 checkpoint 回灌較早 outcome。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-checkpoint-native-wave44-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Exact source runtime 使用 CPython 3.9.6、PyTorch 2.8.0、NumPy 1.26.2、
CPU MKLDNN 與 `model.eval()`，對 48 個 target × 3 個方法重建全部 144 張
票券。Packaged ticket ledger file SHA-256 為
`4bced583132b8409310454775d3405fdc534f3ecb0f92ccb39723c4fe4b92173`，
內部 content SHA-256 為
`b159977ad040a110a27d3cf6793100d95b808f19660aff54efcab823e6598072`；
每個 lookup 另核對 pinned dataset 與 exact 15-draw model context SHA。
Parity file SHA-256 為
`19680af17c03f5cb98e72093066fdf99b20d9651d9a8c2561094a7e9e4d272f8`，
內部 parity SHA-256 為
`7e5456e3ebdd852cd21a636532ae3b8cc2989877e9042c46b76d72618a1a042c`。

Full input 含 2,149 個 target 與 6,447 個 strategy-target execution，
raw SHA-256 為
`e84c070c33cc6d70a186cab34b881d516a45e3826fac365620cfba050b4c5ef5`，
canonical SHA-256 為
`b482ecc6e9db23428d45160ea437ebb749007a140baaa5853426b2f089d6f759`。
Compact evidence 兩次 byte-identical，SHA-256 為
`9377511351325c55cd25563bc99b8290c945475add25991619b6f8d109d50224`。
Overlay 後 catalog file SHA-256 為
`ed43a5e50f66d2d00d8d8dbaf1a69447c6cf70dee8b2c9b38e643bd3f0c28c38`，
內部 catalog SHA-256 為
`b18e432eac7be977fe81e9d4fd1bc71830fcffde20a48579572ddde55de77f4e`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`c96c22007bfd13b6de0bddee61a743802ace155e4ad0465124dac7189b8e7b27`，
內部 report SHA-256 為
`1e58c353f34429e5c5c245e4353a8d405f0e846f1cec8fe26a007e4932efdf24`，
`SHA256SUMS` file SHA-256 為
`981c893f5c39a8c8ef6d0b21af5280ead15f4a1864c4ea6d196335056e2b730d`。
更新後清冊為 83 `BACKTESTED`、65 `CLOSED_UNEXECUTABLE`、
7 `DUPLICATE_ALIAS`、66 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

第四十五批以 frozen CPython 3.9.6、NumPy 1.26.2 與 SciPy 1.12.0
執行五個 FFT／Markov 來源列。四個獨立可執行方法保留原生 portfolio：

- `backtest_big_lotto_3bet.py`：3 注 PP3（兩個 Fourier rank block，
  再接 Lag-2 echo／cold）。
- `backtest_biglotto_triple_strike_original.py`：3 注 Fourier／cold／tail。
- `backtest_fcf_vs_ts3.py`：依 source 先 TS3、再 FCF，共兩個本地配置與
  6 個位置；跨配置重複票券原位保留。
- `verify_markov_vs_triple_2bet.py`：依 source 先 Markov 2 注、再
  Triple Strike 2 注，共兩個本地配置與 4 個位置。Markov 的票內號碼原本
  是 score rank order，3,181 張票只為合法 canonical ticket 表示做升冪排序；
  號碼集合、注序與配置順序均未改。

`verify_biglotto_3bet_comparison.py` 的 source-local Triple Strike 在全部
1,648 個共同有效 causal cutoffs 與 original 方法逐注相同、零 mismatch，
因此標為 `DUPLICATE_ALIAS`；該檔匯入的 Apriori comparator 已由自己的清冊列
保存，不在此 wrapper 重複排名。

各方法嚴格使用 target 之前的歷史。FCF／TS3 comparison 的 source minimum
為 150 期，PP3 與 original Triple Strike 為 500 期，Markov comparison
為 501 期。四個可排名方法合計 6,945 個 causal OK 與 1,651 個
`AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM` closure。Candidate-K 固定為
49，和 source configuration count、3／6／4／3 張原生票及 ordered-20
注數分開保存。

```bash
uv run --no-sync lottolab \
  materialize-biglotto-fft-native-wave45-batch \
  --database /absolute/legacy-read-only.db \
  --expected-database-sha256 <64-lowercase-hex> \
  --output-file /absolute/new-output.json
```

Exact ticket ledger file SHA-256 為
`eba3d384f550808a6934d0b54d37814847accc87e59630dafc0ed155e5dfb5fe`，
內部 content SHA-256 為
`c01fa6591c40faf799981b1682fb106a99e045577218d0478ab653e2043c4899`。
三次 frozen-runtime 重建 byte-identical；parity file SHA-256 為
`2a1b0c033e2e94f03b52cc988a89f7005d06a3f83522f9c3147aa0531991e6bf`，
內部 parity SHA-256 為
`ff1f8fdbc1b5adee1b396d5ae4fd25ce15ef4a286e6f7fbd372a0ab44f549d1b`。

兩份 full input 均有 2,149 個 target、8,596 個 execution，raw SHA-256 為
`e1279cd05dfbdb7e7d8a9e1b6667f2099a54543dd71b7881435550bf25ef51c4`，
canonical SHA-256 為
`72c10326fd66073ed40cf5d77a115a7c2aafe2a73cac3e70442a3b7edae92907`。
Compact evidence 兩次 byte-identical，內部 SHA-256 為
`611c1a940505ecb9e5e1f079e31b0ca2e42948c8dad40a68610ead8060abb06c`。
Overlay 後 catalog file SHA-256 為
`d6c7a0dbbd6430f5d8c74c1d9b93de0ae2cc1bc81806936c0b5156ea52b84bf2`，
內部 catalog SHA-256 為
`a13329f3bbe134d6825f7c14d9476b98e9ae4864588cc5f83ac94be17264a2c3`。
最終 catalog 上兩份完整 report byte-identical；report file SHA-256 為
`9327b91caf94acb5e0b5d274f99c7440ea2aa4a7b6e534c5835f71b5644f69d5`，
內部 report SHA-256 為
`02b7c18e7d82138308de386c7a79cf6d40f691c31648a28e9680687e9a93daa0`，
`SHA256SUMS` file SHA-256 為
`cf06f8c4c1fc978e3d92e2c15cd597e2105b6f5fa62884dd289ee3f0d40dbb63`。
更新後清冊為 87 `BACKTESTED`、65 `CLOSED_UNEXECUTABLE`、
8 `DUPLICATE_ALIAS`、61 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

### Wave 46：source configuration grid 與 full-prefix ledger

Wave 46 從 frozen commit 直接執行 13 個來源方法；其中 12 個保留為可獨立
回測的方法，`predictability_engine.py` 內嵌的五注 label portfolio 則在
1,949 個共同因果 cutoff 上逐票、逐位置等同
`optimal_2bet_3bet_matrix.py`，零 mismatch，因此以 `DUPLICATE_ALIAS`
指向後者。可執行方法涵蓋 P3 portfolio optimizer、orthogonal 5-bet、
6-bet／EWMA 6-bet 比較、cold-pool 12／15、Markov 4-bet window grid、
Triple Strike v2、Markov repeat boost grid、structural group、
sum-constraint grid、optimal 2/3-bet matrix 及 Quad Strike。

比較與網格來源保留主程式宣告的完整 configuration 與原生位置，而不是只留
事後最佳結果：6-bet 為 11 張、EWMA 為 17 張、cold-pool 為 10 張、
Markov window grid 為 27 張、repeat boost grid 為 24 張、structural
group 為 10 張，sum-constraint baseline 加 12 組 grid 為 39 張。原生
重複票券與配置順序完整留在 `native_tickets`；ordered-20 另以單一
checksummed constructor 衍生，5／10／15／20 注只取同一組 portfolio 前綴。
Candidate-K、source internal pool K、configuration count、native ticket
count 與 ordered-20 count 均為不同欄位。

因部分來源會掃描超過固定 500 期的歷史，ledger 對每個 target 鎖定完整
strict prefix 的號碼 SHA-256。CPython 3.9.6、NumPy 1.26.2、SciPy 1.12.0
凍結執行共驗證 323,981 個原生票券位置；所有票券合法且注數固定。
`backtest_sum_constraint.py` 有 5,920 張來源合法票券不是升冪排列，封裝只將
票內同一號碼集合正規化為升冪，不改變配置、票券位置或重複。三次獨立生成
byte-identical。Packaged ledger 的實體 SHA-256 為
`fa7e629fe14c167cf1f7a188db91072bc31017204b18be767fa6d0e95f28cb02`，
內容 SHA-256 為
`a25bef088b8d31815a50565be6fe7e8a94ff3218327bfbfd2090fe959fdb9227`；
parity 檔案實體 SHA-256 為
`436afe0a07f8cbfeef54dc61ace3a8a47b5766f9ab44c8dc77bd01f700532928`，
內部 parity SHA-256 為
`a2aead3767df485be996ad99616024776fba760643f722630a17d94479f0e33e`。

完整 Wave 46 input 包含 2,149 個 target、25,788 個 execution：
23,087 個成功、2,701 個明確 `CLOSED_INSUFFICIENT_HISTORY`。Input 實體
SHA-256 為
`cc9232c049d57689b4d63cbb8f57db13e5a2b72b77833f9e7a007b363956ad26`，
canonical SHA-256 為
`00f3f0b628971b2a0b9ce24816dcb686619aa868354183bcd868f523eed5954e`。
Pre-overlay report 產生 1,536 筆八項成功標準、192 筆官方獎項分布及
28,288 筆涵蓋完整 221 母體的 ranking；report 實體 SHA-256 為
`3809474d978486d832e4f02b4e4f5ea1d0c371e07ec43f3038782e82b1bcac43`，
內部 SHA-256 為
`80351893fb4f3cfc1a83d48bbf91edf341fe409ed32d1e09dad007dbc0b4e383`。
Compact evidence SHA-256 為
`a81d0c1b2a4f9ed343d547dbaeff5b83ca77bb453bcf7ecb843779ff7414f9ac`。

更新後 catalog 內容 SHA-256 為
`6d744b689e99702c0b2bc5693dbdd091b6aeea881a45c13eb8a90c44aa85089a`，
實體 SHA-256 為
`2e175399ff7df9eb80102791522d47d616104992710288d51548d4548633d8a0`。
更新後 catalog 上兩份 final report byte-identical；report 實體 SHA-256 為
`5e1c8c0dd68f6affe004b9f8fc07752c28158d93b92326799d1e4e10ff5b09fe`，
內部 SHA-256 為
`548508a26b048fd793b9f72a89b9aab7debb3b033361cef0ae443b136fc6150f`，
`SHA256SUMS` 實體 SHA-256 為
`a395c933b554cff22fa4d44bafff712a9de69b77318032692c483c766ccf8d81`。
清冊為 99 `BACKTESTED`、65 `CLOSED_UNEXECUTABLE`、
9 `DUPLICATE_ALIAS`、48 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

### Wave 47：FeatureLibrary orthogonal methods 與 logical-history anchor

Wave 47 從 frozen commit 直接執行八個來源方法。七個方法保留為獨立可回測
策略：Edge Splicer 的 2 注加 3 注 positional portfolio、五軸 Edge
Splicer、三軸 Edge Splicer v2、Co-occurrence Concentrator 2 注、
2／3 注 snake-draft orthogonal portfolio、standard TS3 5 注，以及
`quick_predict.py` 的預設大樂透五注。`stability_coverage_study.py` 的五注
portfolio 在 1,649 個共同因果 cutoff 上逐票、逐位置等同 Wave 46 的
`backtest_big_lotto_orthogonal_5bet.py`，零 mismatch，因此以
`DUPLICATE_ALIAS` 指向後者，不重複排名。

來源 main 所宣告的 last-1500 walk-forward 範圍保留為 Edge Splicer、
Concentrator 與 standard TS3 的 649 期最低歷史邊界；
`stability_coverage_study.py` 保留明示 `MIN_BUFFER=500`，
`quick_predict.py` 保留 CLI 的 50 期檢查，而 `generate_2_3_bets.py`
自第一個具有一筆 prior history 的 target 起執行。這些 boundary 不是拿
未來結果挑選窗口；每個 eligible target 都只收到 target 之前的完整 strict
prefix。Candidate-K 固定為 ordered-20 input 的合法 49 號領域，仍與來源
configuration count、原生 2／3／5 注及 ordered-20 count 分欄保存。

CPython 3.9.6、NumPy 1.26.2、SciPy 1.12.0 凍結執行驗證 59,480 個原生
票券位置，所有票券合法且保留來源順序。三次獨立生成 byte-identical；
packaged ledger 的實體 SHA-256 為
`0cc9d97e5a647c6f60da5612636b39f05b06a9f98c2b53286ef3eb595b0e07df`，
內容 SHA-256 為
`e16399eb618b29eb0cbde3d4ee9e51e493f661cbb472e7470c112a1b3348072e`；
parity 檔案實體 SHA-256 為
`d51236920b51a298db3c55181d48b99959cd98c680b5e12838c3f33de44fc497`，
內部 parity SHA-256 為
`cfc7de53d6bffcbb4070a255c4c5b777590f87e1feff4d1e1ae149c3e52d5983`。

跨日重建時原先的暫存 DB 已由作業系統回收；重新使用的 legacy DB 實體
SHA-256 為
`cb3354e22b2cd85a54f4ae1d78e95705a7dfce6960a7011f46f41b3e21c3ac8b`。
驗證器沒有把它默認當成原 pinned DB，而是逐一證實 2,149 個 target order
及所有 full-prefix 號碼 SHA-256 都等於已 checksummed 的 Wave 46 pinned
logical-history anchor，才保留原 dataset identity
`2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b`。
Wave 47 input provenance 同時明示 physical regeneration DB 與 logical
dataset anchor，沒有把兩種 SHA 語意混用。

完整 Wave 47 input 含 2,149 個 target、15,043 個 execution：
11,747 個成功、3,296 個明確 `CLOSED_INSUFFICIENT_HISTORY`。Input 實體
SHA-256 為
`ebfce877aeba18a19a249baf59c08aa74c81b4088585e8d21ae1980cffe21dd9`，
canonical SHA-256 為
`cc238cd9c932da052bba5e9dd88afdee4d904097580f215dee729f31a1a3f955`。
Pre-overlay report 產生 896 筆八項成功標準、112 筆官方獎項分布及
28,288 筆涵蓋完整 221 母體的 ranking；report 實體 SHA-256 為
`45632e7d0d1208032b2c5ee95d21936259e6ce2b0591c358a0643566cb451175`，
內部 SHA-256 為
`1a46057c48f86f9f1e5186583fcdcee547551af76ce809eccfeca84a06320971`。
Compact evidence 內容 SHA-256 為
`aeaae35577c58b7e9e9b981f65480da471472670db1f0f170237b328ac543348`，
實體 SHA-256 為
`226ef87bd7e97e9a74dc9bac5194ccc2be5b869528fb191c7c0ea16f0d0fa7fb`。

更新後 catalog 內容 SHA-256 為
`ec260faa8b40d9cf8435ee2b6c460be1ec5ba500ac27968923fce26b869c1bfe`，
實體 SHA-256 為
`d09eb4876f0dbaa47c8d8fc83e9e5fcd9926ab3a4d14f3cd632a402410d43f4d`。
更新後 catalog 上兩份 final report byte-identical；report 實體 SHA-256 為
`44623d60656eea44a073f27a53a1dcc54506a80b1c8700ce6165ddf049865dc7`，
內部 SHA-256 為
`f040b1366b6a5c2b845697d15bdc3d9c2b8018722f6fba0f4f7936e94be6f0e4`，
`SHA256SUMS` 實體 SHA-256 為
`44c293aed331e53b35fb0dc1291fbc334f65195414397fa433c0854d22e969ea`。
清冊為 106 `BACKTESTED`、65 `CLOSED_UNEXECUTABLE`、
10 `DUPLICATE_ALIAS`、40 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

### Wave 48：enhancement grid、Direction 3 與 TS3 alias

Wave 48 從同一 frozen commit 直接執行三個來源方法。
`backtest_biglotto_enhancements.py` 依來源主程式的宣告順序保留 Base、
P1-A、P1-B、P2-A、P2-B、P3-A、P3-B、C-P1、C-ALL4 與 C-5BET
十個配置，展平為 42 個原生 positional tickets；
`backtest_direction_3.py` 保留 Triple Strike 與 Stabilized P0+P1
兩個三注配置，展平為六注。來源的 last-1500 與 min-buffer 語意分別形成
649 與 500 筆最低歷史邊界，所有 eligible target 都只收到 target 之前的
完整 strict prefix。

`optimize_5bet_weights.py` 的票券生成器與 Wave 47
`standard_ts3_5bet.py` 在 1,500 個共同因果 cutoff 上逐票、逐位置完全
相同，零 mismatch，因此標為 `DUPLICATE_ALIAS`，不把事後門檻與權重
搜尋結果誤當成另一個獨立選號策略。Candidate-K、十／二個來源配置、
42／6 個原生票券、重複票券與 ordered-20 count 均分欄保存。

CPython 3.9.6、NumPy 1.26.2、SciPy 1.12.0 凍結執行驗證 80,394 個原生
票券位置。Packaged ledger 的實體 SHA-256 為
`b4c9982695af44909ebadc7f1a8cad2a4969f36b460bed3ed423fdabfda1e0b3`，
內容 SHA-256 為
`6c2b44676a69f880c7da6368f6fcf0dc44df67f15787651d62e868c5d3a766d0`；
parity 檔案實體 SHA-256 為
`14363930c208c58bca911e44f55ad023db663cd845bc35c536d399377c217259`，
內部 parity SHA-256 為
`b38d648411c2e354d5bbbecd8b8e79f0235b15ccc9b97df1c1d364bcc8efad87`。
本批同樣逐一驗證 2,149 個 target order 與所有 full-prefix SHA，
才將實體 regeneration DB
`cb3354e22b2cd85a54f4ae1d78e95705a7dfce6960a7011f46f41b3e21c3ac8b`
繫結至 pinned logical dataset
`2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b`。

完整 Wave 48 input 含 2,149 個 target、4,298 個 execution：
3,149 個成功、1,149 個明確 `CLOSED_INSUFFICIENT_HISTORY`。Input 實體
SHA-256 為
`d991dcea0d23e772a8771244223a5fdc207e3a4f97bf5d75d71b0bbb314cc799`，
canonical SHA-256 為
`0de7e1613b0c58f3bcec4299c50494a770a631bf6e29270449fe7d2d14c80af3`。
Pre-overlay report 產生 256 筆八項成功標準、32 筆官方獎項分布及
28,288 筆涵蓋完整 221 母體的 ranking；report 實體 SHA-256 為
`c30e5e9ca5f913f96e4074097aecf21ea51db0ff65d1aa65c2b4856b002a1914`，
內部 SHA-256 為
`d8538162672b1048719fdef97c6700f8dd380f58695e534a4424985ad961495a`。
Compact evidence 內容 SHA-256 為
`a07f4af5037d7b172425855f96411999307161b2f8bf5d59f2971b59149f4cae`，
實體 SHA-256 為
`c24bd6976d5311066fc0c5a8ccf3f58b41b6897c6cdb9ff8adc3c868dcfd2d02`。

更新後 catalog 內容 SHA-256 為
`b4fdd1ce3e5edf21592b83cc0473f140a1360dbd6dea9aef2a3b90c91dd3ba4f`，
實體 SHA-256 為
`7a6038a751cd8ac3d0e39c40acfe2b3042ef3d1e4aa0525f0f5cc9cacfaec730`。
更新後兩份 final report byte-identical；report 實體 SHA-256 為
`e04b4098e60573cdd55380b7fa7ecc9c5bbbfc7fd6d2dc091a56c03f0573829d`，
內部 SHA-256 為
`878d3d84f8cc02d943fe8d38320d78f4d8b40caa4ca3710d6ce91a107ce64497`，
`SHA256SUMS` 實體 SHA-256 為
`68bc4ff358a1757971258bc6663553d00d864a03ddaaf390dd66668fb03ff870`。
清冊為 108 `BACKTESTED`、65 `CLOSED_UNEXECUTABLE`、
11 `DUPLICATE_ALIAS`、37 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

### Wave 49：Auto-Discovery、signal prefix 與 Fourier grid

Wave 49 直接執行三個 deterministic frozen sources。
`auto_discovery_biglotto.py` 保留主程式按名稱排序的 54 個 A 至 F 維度
配置，每個配置一注；`evaluate_combinations.py` 保留 2、3、4、5 注四個
source prefix 配置並依宣告次序展平為 14 注；`power_fourier_rhythm.py`
保留大樂透模式、500 期 Fourier window 的預設兩注。Auto-Discovery 與
signal prefix 的 last-1500 source evaluation boundary 為 649 筆 prior
history，Fourier 保留其 500 期窗口。三者均未使用回測結果挑選當期票券。

CPython 3.9.6、NumPy 1.26.2、SciPy 1.12.0 凍結執行驗證 105,298 個原生
票券位置，批內及與 Wave 48 的整體 portfolio 比對均沒有 alias。
Packaged ledger 的實體 SHA-256 為
`401a6abb2fef088c70c982c1ea4f466e98dfe6c030c9ee093d40ee4c8c018e05`，
內容 SHA-256 為
`fcc1883924238ecf5afc5ebb1216ce084371b4c01dbebc283e1c9961d975c0b8`；
parity 檔案實體 SHA-256 為
`8ce9f0ea7c7f4dd1b5eb2d1683ee348c2c2b4fa122ebc5421d3c15070320a8c3`，
內部 parity SHA-256 為
`f9575eb59ced463f17102ce2914edbd9857c76f0d5aa234f7743a3de28b506bb`。
Target order 與所有 full-prefix SHA 仍逐一繫結至 pinned logical dataset，
沒有把 regeneration DB 實體 identity 當成原始 pinned 檔案。

完整 Wave 49 input 含 2,149 個 target、6,447 個 execution：
4,649 個成功、1,798 個明確 `CLOSED_INSUFFICIENT_HISTORY`。Input 實體
SHA-256 為
`94e1ff9e043d6ac39a581df843dda0dbdb5ea433e03ecc62d354b1a24cb036c7`，
canonical SHA-256 為
`3cf636a9b60c28ce9efb5a5a8c795850e52533d276b8a3a2bbdbf130f7269b18`。
Pre-overlay report 產生 384 筆八項成功標準、48 筆官方獎項分布及
28,288 筆完整母體 ranking；report 實體 SHA-256 為
`7fcccf90df28ab34c3e0f88133fd3c71946e79a8138ee02649e6112da991c530`，
內部 SHA-256 為
`f7db309e7fc254bb1ab1e156f727843685fee499e69744e821841620bc44a8d7`。
Compact evidence 內容 SHA-256 為
`5c6f759bdb23b7ad19814611bfc495eda8a1e992446d4a88209351daf79ae0cc`，
實體 SHA-256 為
`0bed024360fdc04f0a36ba8ddef7dadc46b9640230d495314009631385f36a0e`。

更新後 catalog 內容 SHA-256 為
`a6250c550977f10c305c7d1a707825b3a96945496ca3620fcc0b976dfe0d4d6d`，
實體 SHA-256 為
`c4c017ca7acbb60a76ae402840ead7f016dde6903823dbdd7dbb48a533cc2f77`。
更新後兩份 final report byte-identical；report 實體 SHA-256 為
`ef25de31df15b20dd8fa91b3861859a9a92fcabd2e72f7ba8b6ff3a53e40b4f4`，
內部 SHA-256 為
`0655b6120fce03d4a19a43497302c5084ff88582fce0512b9e1a0b6b508986a9`，
`SHA256SUMS` 實體 SHA-256 為
`3da5c3ea3db1a852336748fd3ebb2ca3b39fc1931a3053f6a8baf1627a1ed20b`。
清冊為 111 `BACKTESTED`、65 `CLOSED_UNEXECUTABLE`、
11 `DUPLICATE_ALIAS`、34 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有歷史成功率與隨機基準差異只供描述性
研究，不保證未來中獎。

### Wave 50：covering 與 exhaustive feature sweep 的 frozen source-grid

Wave 50 將兩個仍可執行的 actual-method row 從
`OWNER_DECISION_REQUIRED` 移為 `BACKTESTED`：

- `tools/covering_strategy_research.py` 保留來源 main 的 8 個配置順序：
  5 個固定 5 注 covering portfolio，接著是 signal-guided、
  co-occurrence-guided 與以 `len(history) % 10000` 為 seed 的動態
  zero-overlap；每個 target 的原生 portfolio 是同序 40 注。
- `tools/exhaustive_feature_sweep_v2.py` 保留來源 insertion order 的 6 個
  feature configuration，並保留 `UnifiedAuditor.audit` 預設
  `num_bets=2`，所以每個 target 是同序 12 注。來源 CLI 的預設 `--n=150`
  被保留為 150 個 eligible target；其餘 target 明確
  `CLOSED_INSUFFICIENT_HISTORY`。

兩者都在 frozen commit
`49a25effa62fc24f40789c16be6f11bdfb41a4a9` 與
CPython 3.9.6／NumPy 1.26.2／SciPy 1.12.0 執行。Wave 50 parity 覆蓋
61,800 個原生票券位置，批內與對 Wave 49 的 exact full-sequence alias
candidate 都是 0。Ledger physical SHA-256 是
`bed023802501fa525375c50b64d9f5f76f5b450da7ba668a60e9162e31aa8316`，
content SHA-256 是
`e0efca7d50a81fcd8afc1cd72cf2c2114f1eb00b291c6dc5f76e14bca6074c26`；
parity physical／internal SHA-256 分別是
`4c7bbe17f143d40d265c89a133292e8701c35a6e1c180ba609db3b7cda0358b4` 與
`c006673f6f9b4df9f538c170b0205a09d002c7043f4cbaebea6f47b854247513`。

完整 input 有 4,298 個 execution：1,650 `OK`、2,648
`CLOSED_INSUFFICIENT_HISTORY`；physical／canonical SHA-256 分別是
`b55f0816b8b43b9f5f6ecf893f9af32cf9b3d0192c575de955bbde0a6c2da46b` 與
`975431d032eb3ae0c8fbdd045caf97b0854a1316e27ba1458c5ab02f3cbda3c7`。
Compact evidence physical／content SHA-256 分別是
`2d0a142046b9fff65446daa8d2d2144fd959d7c3c00120eac18f2a03dbabf425` 與
`8677e817497c0daba496f1169ea708575f738fe7931d4ddfdd2a9c4123b92059`。
Overlay 後 catalog physical／content SHA-256 分別是
`46985123b9144b03337ed494283d58d72e51862f169e014485f8863260e6e906` 與
`b3dcb5405ee9178f548f7022518384af5c81abb53670c6a3611d7538ecd83a30`。
最終報表雙跑 byte-identical；report physical／internal SHA-256 分別是
`d5ad09fd92c9ef2e98f76213fdf0fff4ce1b16cb4a28087b6aa4922a3e9f7977` 與
`f1f5d0d6b2784367eb921536403a0c8384e0507038672a7c1f466fbd2d811554`。

更新後清冊為 113 `BACKTESTED`、65 `CLOSED_UNEXECUTABLE`、
11 `DUPLICATE_ALIAS`、32 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有成功率與隨機基準差異只供描述性
歷史研究，不保證未來中獎。

### Wave 51：cluster 與 deviation-extreme 的全域 seed 序列重播

Wave 51 將 `tools/optimize_biglotto_cluster.py` 與
`tools/optimize_deviation_extreme_generic.py` 從
`OWNER_DECISION_REQUIRED` 移為 `BACKTESTED`。前者保留 cold-5 negative
pool 與 dynamic cluster 的來源 4 注順序；後者保留每期 500 次候選抽樣後
選出的單一 extreme ticket。兩個來源都只回測最近 150 期，因此其餘 target
保持明確 `CLOSED_INSUFFICIENT_HISTORY`。

兩個方法分別保留來源的 oldest-first prefix 與 recent-first causal suffix
語意，並各自在獨立來源 process 中從 NumPy MT19937 seed 42 開始，依來源
target 順序連續消耗 RNG；不得對每個 target 重新 seed。Wave 51 parity 覆蓋
750 個原生票券位置，批內與對 Wave 50 的 exact full-sequence alias candidate
都是 0。Ledger physical／content SHA-256 分別是
`626a4f8d1e779e48fe3411023da68ef2b25b4cfbe538d0e93b470273c554c4a0` 與
`5faa258c2f0d24213be5c2f98f3ef505c389844624a5322ff3deb16a04d2156c`；
parity physical／internal SHA-256 分別是
`0901f6943023b5f4026051aabe7327a2acb5c62cb59180d32a31f9c99dddfd37` 與
`02f28318579c71c3dbecf63f884cd7a0c51f29225df01002d4e46f0fcf767a99`。

完整 input 有 4,298 個 execution：300 `OK`、3,998
`CLOSED_INSUFFICIENT_HISTORY`；physical／canonical SHA-256 分別是
`3d34c93faee094fceb82712922f22b74245340289ecba1e42e79a400f2a73c5c` 與
`2f7cbdd5ff8690129edbd9d5588039801464f4f2c03f24a44a78d617fd0b7ccc`。
Compact evidence physical／content SHA-256 分別是
`292dee4f94a057b7ba44a92bcdce67ee11662f2f2f2e6fdc436bad7e965bb802` 與
`fe728b48e139137d778fd26f163322d56e817f7e981fabd14afa9e3cec00b963`。
Overlay 後 catalog physical／content SHA-256 分別是
`e1af7ebf25acd41061bd786cf398b99d3a8d1892807b11e903ef97659eeb1d02` 與
`49ec499f5471538c4255867af513a53e2a67c0c8013938f541cc971a1a7765cd`。
最終報表雙跑 byte-identical；report physical／internal SHA-256 分別是
`10c3ded3e1fe11797dacbbae615aec1468979c176d3d0184139422320b21c35e` 與
`d3f6bef0dd21477a50660c96579e3809c0b9290d6a99a3d81615c4cf92cf2fe9`。

更新後清冊為 115 `BACKTESTED`、65 `CLOSED_UNEXECUTABLE`、
11 `DUPLICATE_ALIAS`、30 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有成功率與隨機基準差異只供描述性
歷史研究，不保證未來中獎。

## Wave 52：Feature Discovery 與 Historical Audit frozen recipe

Wave 52 將 `feature_discovery_and_retrospective.py` 與
`tools/historical_audit_rigorous.py` 從 `OWNER_DECISION_REQUIRED` 移為
`BACKTESTED`。前者保存 Information Theory、Structural Constraint 與
Cold Reversion + Lag-2 Echo 的三個來源位置；後者保存 frozen
`best_config_BIG_LOTTO.json` weighted recipe 的兩個 positional bets。
兩者原生注數分別為 3 與 2，source configuration count 分別為 3 與 1。
Feature method 同時明示 49-number ranking domain 與 100,000 個 structural
candidate combinations，沒有把 Candidate-K、configuration count、native
ticket count 或 ordered-20 count 混為同一語意。

Feature source 自行對每個 target 重設 NumPy MT19937 seed 42。Historical
Audit 的 frozen recipe 會呼叫舊 `interval_predict`，但該來源使用
module-global Python RNG 且未保存 seed；Wave 52 因此把執行前
`random.seed(42)` 明示為缺失的外部重現輸入，並在載入與執行 frozen
source 之前固定。兩次獨立 frozen-source 重建得到 byte-identical ledger 與
parity artifact；不把第一次未固定 seed 的偶然輸出當作可重現證據。

嚴格 causal minimum 分別是 2,131 與 200 個 target 前歷史期數。完整 input
包含 4,298 個 execution，其中 1,967 `OK`、2,331
`CLOSED_INSUFFICIENT_HISTORY`；每個成功 execution 只建立一組 ordered-20，
5／10／15／20 注均取同一序列前綴。Frozen parity 比對 3,952 個原生票券位置，
批內與跨既有 wave 的 exact alias candidate 均為 0。

本批次 checksum：

- ledger physical SHA-256：
  `54b1fe150c6ebe1336dd936c095173030b632be7d19a9b167c9f87948237d852`；
  ledger content SHA-256：
  `e2f6070c27fdd33d6257dbcbc1849945e1c1bb1199ed0f0c69fee6a9da8b0deb`。
- parity physical SHA-256：
  `a59c8bbc8baa0f73a5a94d709cdf3dcc0b8e2e3bd42588f425f8a6b7014e3f3b`；
  parity content SHA-256：
  `892179f9803344e671b4be4b3b2ea9f1dd5cb3bb27dd9061390b95a2fe176d43`。
- input physical SHA-256：
  `b066de5361d538288de3d37a2c4410c26c329c2c5132ccf1e3d7a798e5168d40`；
  canonical SHA-256：
  `b3edb1fa8cc6c1a7adc1de106567813caa2c4d48528c4d36cee322abdb24f509`。
- compact evidence physical SHA-256：
  `0f1520033e06172acb152c6e1c6f382ae07c620bc437bbc4017f1be216f2e452`；
  evidence content SHA-256：
  `ada478ff7f67880ef1d6907142d3a47afd51c10aeb029a7f3f79eb779c2fb111`。
- pre-overlay transition report physical SHA-256：
  `e93a2f1e440d0336494cfea23a1a9aa2593384d16122cac333373fb3b398d61b`；
  report content SHA-256：
  `0f1ea5c43ab75ddf4c6604c3e0a21e13db885d0ef38e16c3afb8445f9b9facaa`。
- 更新後 catalog physical SHA-256：
  `2b6e20ee56cb4707aa8a0cbb7a7c296394e4cfd50bd4026910c4eebd3c6e6daf`；
  catalog content SHA-256：
  `92c8c4cf9967950b07f8188f0d7fa2cbc87d595bbc643e66ff2fbfe1edf5a1f8`。

Post-overlay final-tree 重跑仍產生 byte-identical input 與七個計算 CSV。Report
JSON 只把 `catalog_sha256` 從 pre-overlay `49ec499f…` 更新為 post-overlay
`92c8c4cf…`，其 physical SHA-256 因而為
`b526d0851c12a31ece414b121100cc92dcf60a7b3128871f13813b31ddd47f9c`，
content SHA-256 為
`0b7081bb35de9a964a6f5770ddb043d42836e085635da543bbe3d4eff13ccddd`。
另一次 evidence build 與 catalog overlay 分別逐位元重現
`0f152003…` 與 `2b6e20ee…`，證明轉移 artifact 可由保存的 Wave 51 base
catalog 重新建立。

更新後清冊為 117 `BACKTESTED`、65 `CLOSED_UNEXECUTABLE`、
11 `DUPLICATE_ALIAS`、28 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有成功率與精確隨機基準差異只供描述性
歷史研究，不保證未來中獎。

## Wave 53：巢狀 verified strategies 與 RGF 六公式

Wave 53 將 `tools/analyze_prediction_115000019.py` 與
`tools/rgf_walkforward_validator.py` 從 `OWNER_DECISION_REQUIRED` 移為
`BACKTESTED`。前者依來源順序完整保存 P0 2-bet、Triple Strike 3-bet、
TS3+Markov 4-bet 與 TS3+Markov+FreqOrtho 5-bet，共 14 個 positional
tickets；四個巢狀配置間重複出現的票券不去重、不壓縮。後者依 frozen
`FORMULAS` insertion order 保存 `freq×gap`、`freq×markov`、
`gap×markov`、`freq+gap`、`freq+markov` 與 `freq-only` 六個 top-6
set；只在票內 canonicalize 為升冪，不更動公式或票券位置。

兩個方法都是 deterministic selection，不需要 RNG。嚴格 causal minimum
分別採來源 Fourier window 500 與 RGF walk-forward `GMM_BURN_IN=200`。
完整 input 有 4,298 個 execution：3,598 `OK`、700
`CLOSED_INSUFFICIENT_HISTORY`。Frozen AST parity 比對 34,780 個原生
票券位置，兩次重建逐位元相同；批內與跨 Wave1–52 exact alias candidate
皆為 0。

本批次 checksum：

- ledger physical／content SHA-256：
  `519b25c61e374cacce762d0ce4aaceb2813500260867c8443fec03418182cefd`／
  `201233318fe457d53f8f614f1fc4e3cc165b004493c8f0c75f58eac2ceddc675`。
- parity physical／content SHA-256：
  `7415ebf9a5b6663bd5b0ce0b0e6a90b8eafdc82f52263781a344809dc8d015b5`／
  `6373c2d0979b3b50affec5db407fe57efbe0515ac5cdecf28bfa3a6dbe39620f`。
- input physical／canonical SHA-256：
  `308b239f549394fa4d17585dafe8cc2f991e2ac3ef0d90fc059b511533d36601`／
  `36fe88bc9a89056620dac3dcf205a328969335f3252c952df3e7809f027ae4f5`。
- compact evidence physical／content SHA-256：
  `b1d56a07a67afe563bd412465fc624ba875e77f6821a5898a5a04b41039304c7`／
  `08e62eb8a3a791bb1dd0d7ff123f77f47f7bbfe0749ba53850c7a05e79c17f60`。
- pre-overlay transition report physical／content SHA-256：
  `81420b851f33bb1555dd6044aa670cca297a6dd08ba1355d3b00368758dd5a16`／
  `735b4b7c05b7166237283ed5c60cc60c4038e50b16ac005585e95dcd7da0b01e`。
- 更新後 catalog physical／content SHA-256：
  `6c2f6f1addcf3545aad655957331c79edceba0695009c8db861bdb0479862224`／
  `f7203b3a3951f56f09d8f635998697d8903aa3d345854626e9ac44be7916a1aa`。

Post-overlay final-tree 重跑的 input 與七個計算 CSV 仍逐位元一致；
report 只更新 catalog identity，其 physical／content SHA-256 為
`85484efda34a93652dd952703942430a1b5438cdd1d5f4cf1765f5d6daa54ab8`／
`35d7e85b66d8effe0617c6ea5a1f5253ba913b4cba2dfdf648877f835d494586`。
第二次 evidence build 與 catalog overlay 也分別逐位元重現
`b1d56a07…` 與 `6c2f6f1a…`。

更新後清冊為 119 `BACKTESTED`、65 `CLOSED_UNEXECUTABLE`、
11 `DUPLICATE_ALIAS`、26 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有成功率與精確隨機基準差異只供描述性
歷史研究，不保證未來中獎。

## Wave 54：Consensus 與 Evolutionary GUM one-shot portfolio

Wave 54 將 `tools/predict_consensus_ensemble.py` 與
`tools/predict_evolutionary_gum.py` 從 `OWNER_DECISION_REQUIRED` 移為
`BACKTESTED`。兩個 frozen source entrypoint 都原生產生 2 個 positional
tickets；前者保存 `best_config_BIG_LOTTO.json` 的 window-50 配置，後者保存
regime 選出的 frontier recipe（找不到適用 frontier 時依來源使用 stable
recipe）。每個方法的 source configuration count 均為 1，與 Candidate-K 49、
原生票券 2 及 ordered-20 portfolio count 分別保存，不混用語意。

兩個 entrypoint 都會間接進入 `UnifiedPredictionEngine.interval_predict`，
該來源使用 Python module-global `random.choice` 卻沒有保存 seed。Frozen
reference 因此在每個 target entry 重設 `random.seed(42)`，並將
`PYTHON_RANDOM_RESET_SEED42_PER_TARGET`、source／dependency identity 與完整
strict-prefix context 封裝進 checksummed ledger。這不是把來源誤寫成
deterministic no-RNG，而是明確補足原本缺失的執行輸入。嚴格 causal minimum
分別為 50 與 150 期。

完整 input 有 4,298 個 execution：4,098 `OK`、200
`CLOSED_INSUFFICIENT_HISTORY`。Frozen module parity 比對 8,196 個原生票券
位置，兩次獨立重建逐位元相同；批內與跨 Wave1–53 exact alias candidate
皆為 0。

本批次 checksum：

- ledger physical／content SHA-256：
  `ae8846b500c6d0ec6754ee992018793605a5716a050d2600c486a3da4d0346b9`／
  `f40fd33499cc9f43ff53f352505a175ecd35c4cbee7b4a866017eea25c41103a`。
- parity physical／content SHA-256：
  `7e6aadbd00a2116a801b999d49aa0c3d06c538a19cb5ba0901c659b296be64fc`／
  `50ef49fb13189c7c776a22e08057d8439ab362540549d146720b18afab310fa6`。
- input physical／canonical SHA-256：
  `41024ab48c9cd71f969b3ef5d4359cd9b249fd91d3e842ea346146a997fa30d3`／
  `d62c108821e05b69446b960b478c53e98b1871353680a151cfd4523883a8c7a3`。
- compact evidence physical／content SHA-256：
  `b8f41fec1687b7798d3b9d01ca73c586df8fc17a1f39021dd948368382a6721a`／
  `e37f7074d5f7385077c16d7dc7ef28680f087341d0b55f6eb398d29e0701fee3`。
- pre-overlay transition report physical／content SHA-256：
  `e1f0a19fccb48aaa439419862f210d853e0c10a21b5d2d70c1dcf890745631eb`／
  `a8508a240024bc0faff6f343233449577a8abe606acca5d3199c71e00366bf15`。
- 更新後 catalog physical／content SHA-256：
  `023434b64df1af74cde40191474133709eff35401273fe0f29d17b70009642f5`／
  `6599e096044c967623bdf7d58f4fbe0e11515459bd77613cb389754ae72a58a1`。

Post-overlay final-tree 重跑的 input 與七個計算 CSV 仍逐位元一致；
report 只更新 catalog identity，其 physical／content SHA-256 為
`03d6bc48e1631cd99832e160ab376f220502384345b940f50ea10a7496927c8d`／
`6e89f2be255b26a7591272bf4c2eb5e5d4a2b05cb519e1cee103146445ef4804`。
第二次 evidence build 與 catalog overlay 也分別逐位元重現
`b8f41fec…` 與 `023434b6…`。

更新後清冊為 121 `BACKTESTED`、65 `CLOSED_UNEXECUTABLE`、
11 `DUPLICATE_ALIAS`、24 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有成功率與精確隨機基準差異只供描述性
歷史研究，不保證未來中獎。

## Wave 55：checkpoint-native orthogonal 與 six-expert portfolio

Wave 55 將 `tools/predict_next_draw.py` 與 `tools/predict_6expert.py`
從 `OWNER_DECISION_REQUIRED` 移為 `BACKTESTED`。前者保存原生 3 張 positional
票券（Structural AI、HPSB DMS、Hybrid Balance），後者保存原生 6 張
positional 票券（Structural AI、HPSB DMS、Co-occurrence Graph、Hybrid
Balance、Gap Recovery、Tail）。兩者各只有一個 source-defined local
configuration；Candidate-K 的來源觀測值、原生票券數、configuration count
與 ordered-20 portfolio count 仍分欄保存。

兩個 entrypoint 都載入 frozen
`ai_lab/ai_models/v3_deep_resonance.pth`，checkpoint SHA-256 為
`ef21497fe396cff4d96dc7a123987f9cb188725900162b435be91cfd7d23712d`。
該 checkpoint 首次出現在 commit
`e56ce9f196342e9d50edc9fd19c42f72c1fa2047`，時間為
`2026-02-24T11:02:20+08:00`；因此只有 target local date 嚴格晚於該日的
48 期可執行，其餘每個方法各 2,101 期明確標為 `CLOSED_REJECTED`，避免把
較晚 checkpoint 回灌較早結果。Six-expert 的 Tail 依 frozen source 以
history length 重設 Python RNG；其餘 expert selection 與 model-eval 路徑
不消耗選號 RNG。

完整 input 有 4,298 個 execution：96 `OK`、4,202
`CLOSED_REJECTED`。Frozen runtime parity 比對 432 個原生票券位置；orthogonal
三張票在每個可執行 target 都等於 six-expert 的位置 0、1、3，但兩者原生
注數及完整 portfolio 不同，因此不是 exact alias。批內與跨 Wave1–54 exact
alias candidate 均為 0，兩次獨立 parity 重建逐位元相同。

本批次 checksum：

- ledger physical／content SHA-256：
  `9281469b90edf4b46b6fb7ae9f4de7c14a26aae077ac95f344207c9b34fc8966`／
  `d0a49cc9d8ed82f7555a56bb08d6fc0470f6cc1a7d65a39734d8a246d092e76b`。
- parity physical／content SHA-256：
  `4b78a788b720f2f166d7cfbe3c95eae1f6193b0fcaf46158cb210f021e644371`／
  `a76ed536c74aef55b096b60a2d8dd9b476b242ae39cf440a0f478aa9b116bc11`。
- input physical／canonical SHA-256：
  `e2b059af420c9988ff0eec057a77fdc372bb0277c48cb1d889e41a9ee7d4f53a`／
  `15257ad42fdb6fb8a7aa4e095e62f01c9575c1a448909827918858060c79f1d8`。
- compact evidence physical SHA-256：
  `080e64dc16e80941b1700c1425e6a7527537eca51235e2957aacc01e32e4f4ca`。
- pre-overlay transition report physical／content SHA-256：
  `de04454b16afacb11d3ebbc79094c7e364b8cc3c7538f1aa77ff2aceb2c852a9`／
  `63fe6c56873b2d14a92c8a92c13e5d5e6e69fcdb3061e6f7a3286a2942ba1993`。
- 更新後 catalog physical／content SHA-256：
  `f89e763a8d25a094ac2f0876b38cd37bd6e50a384306d985afd709ff43c95f71`／
  `1103e1ec10b1af374ef48c649dd32a3e9b72fb46f38d39c2921aaedd179bbf81`。

Post-overlay final-tree 重跑的 input 與六個計算 CSV 仍逐位元一致；
report 只更新 catalog identity，其 physical／content SHA-256 為
`04874040f0fbe89398f8c3dbfac7a4f2031ae2351a06398583374d0f9a3e73da`／
`47d229047043c54ed05ae40b7ef36c113247a257fc9ea7fa8c3ae6187a523673`。
第二次 evidence build 與 catalog overlay 也分別逐位元重現
`080e64dc…` 與 `f89e763a…`。

更新後清冊為 123 `BACKTESTED`、65 `CLOSED_UNEXECUTABLE`、
11 `DUPLICATE_ALIAS`、22 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有成功率與精確隨機基準差異只供描述性
歷史研究，不保證未來中獎。

## Wave 56：未保存 stochastic pre-state 的正式處置

Wave 56 對八個 frozen actual-method source 完成逐檔 source/blob review：
`advanced_strategies.py`、`big_lotto_dual_bet_optimizer.py`、
`selective_ensemble.py`、`unified_predictor.py`、`auto_optimizer_v2.py`、
`big_lotto_2025_tournament.py`、`predict_114000118.py` 與
`verify_cluster_size.py`。它們仍完整保留在 221 母體，但正式移為
`CLOSED_UNEXECUTABLE`。

這些方法的正式票券路徑直接或間接消耗未綁定的 Python／NumPy RNG：
Unified ensemble 的正常策略集合包含 20,000 次 NumPy choice 的 Monte Carlo；
dual-bet、Selective Ensemble、tournament、draw-specific meta-selector 與
cluster-size verifier 都會再消耗該 upstream output；AdvancedStrategies 的
entropy-outlier 直接抽樣 50 個 candidate tickets，V3／V11 也有 stochastic
portfolio completion；Auto Optimizer V2 則公開 unseeded genetic sampling 與
ticket fill 路徑。Frozen source 沒有保存對應 pre-state 或 emitted-ticket
ledger，因此事後補 seed 會創造新方法，不能宣稱是原生票券復現。

Evidence 以 commit、blob、byte size、source SHA-256、decisive fragments、
三項 source facts 及穩定 reason code 鎖定；兩次獨立 evidence build 與
catalog overlay 均逐位元一致：

- disposition evidence SHA-256：
  `c9a9d9420e29e718ceec5bfe309869ed9a6b3f3e76c78c1b04d381e85089edbf`。
- 更新後 catalog physical／content SHA-256：
  `524cbf255ee3d791691ce6f946b554ff2e2b941c5815967e6f874a7c7f3ea465`／
  `46f4a8aab26f63db2db1c1299e90bd9e516d10f53fdfcb35251d18259a47278b`。
- Final-tree report physical／content SHA-256：
  `0335dc38ee85c2eb07a8951ef48b4f830f2faa4753cb967c350dd2136ca5c051`／
  `df0373e09df71c44439491864a30f08cf8fad8fb598376963db8170a7c279869`。

更新後清冊為 123 `BACKTESTED`、73 `CLOSED_UNEXECUTABLE`、
11 `DUPLICATE_ALIAS`、14 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。Closed rows 仍出現在完整 universe、ranking
與 CSV／JSON，並帶不能排名的原因；所有成功率與精確隨機基準差異只供描述性
歷史研究，不保證未來中獎。

## Wave 57：HPSB-V2 全前綴回測與 Ensemble 精確同義別名

Wave 57 將 `lottery_api/models/hpsb_optimizer.py` 的公開
`predict_hpsb_v2` entrypoint 從 `OWNER_DECISION_REQUIRED` 移為
`BACKTESTED`。Frozen CPython 3.9.6／NumPy 1.26.2／SciPy 1.12.0
逐期執行全部 2,149 個 target：每一期只讀嚴格較早的完整 history prefix，
第一期使用空歷史；統計子方法保留來源內 `random.seed(len(history))` 語意。
每期原生輸出固定為一張有序單注，Candidate-K 49、原生注數 1、來源配置數 1、
combination count null 與 ordered-20 注數保持不同語意。

封存 ledger 涵蓋 2,149 張原生票券；evaluator input 保留 2,148 個 `OK`
execution，第一期因 evaluator 必須記錄前一期 cutoff identity 而明示為一個
`CLOSED_INSUFFICIENT_HISTORY:NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF`。所有 `OK`
execution 都先由相同原生單注導出一組有序 20 注，再以其前 5／10／15／20 注
計算 FULL／750／300／50、八項成功標準、官方獎項、coverage、精確隨機基準
差異、完整排名與 Top 10。

同一 frozen runtime 也逐期執行
`lottery_api/models/ensemble_predictor.py` 的 default
`predict_ensemble` entrypoint。來源檔雖定義 `patch_ai_adapter`，但公開
entrypoint 與 module main 都不呼叫它；既有 `AIAdapter` 不支援
`transformer_v3_raw`，因此 default path 將 AI weight 設為 0，保留同一張
HPSB-DMS 票券。2,149／2,149 個 target 逐票完全相同，故該方法正式保留為
指向 HPSB-V2 canonical strategy 的 `DUPLICATE_ALIAS`，不建立重複排名列。

可重現 artifact identity：

- ledger physical／content SHA-256：
  `5120f4cf4928eb843c4b1a29ccfe913692bcf34398308d0c89bcde66527f1e45`／
  `f014535c4befa3598a408bf0a05b1b81e11736c6bb57357f71161c8ab70de8c5`。
- parity physical／content SHA-256：
  `01b263e415318cb13ba78eb866b009be1544bffa63fe52e43d0367db45fa0c9a`／
  `aba837bdf2680da52ab28ab095532ace02c14f29b63eba6c2fa094f912cb72ec`。
- materialized input physical／canonical SHA-256：
  `caa29d5e1e9c68df790197321c1b98a3421b9ddebb056323d0d221ab38ea6384`／
  `10a44c3ac64306432d02604b74bbfd1ef9c7d07cf58f937cec148cb782eae8b8`。
- compact evidence SHA-256：
  `235947a7035aa43396125ba3340d48872dd81a60a3f367a1908da98dbf4b0512`。
- 更新後 catalog physical／content SHA-256：
  `b2ae5e48fa59f6619b853d6bdf3d4a2e5a05f5aa840e139950b2539cdc9686f7`／
  `6316066d537d3966d25549f7a8d220db13a5b5b506345f779dcfdb7e75c7f476`。
- Final-tree report physical／content SHA-256：
  `06b140f9bdc5ccd3b02a262aa6012da3544f9f5c56ff147534aa405d183f6023`／
  `f577a911c8e7de61cc37c8a31ef827f053aa12d3bf4b350521d524474920d5e7`。

更新後清冊為 124 `BACKTESTED`、73 `CLOSED_UNEXECUTABLE`、
12 `DUPLICATE_ALIAS`、12 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。因此本批完成兩個正式處置，但全策略工作仍
未完成；11 個 replay-backed 策略也仍只是一個先行批次。所有成功率與精確
隨機基準差異只供描述性歷史研究，不保證未來中獎。

## Wave 58：Enhanced Dual 與 seeded Diversified V6

Wave 58 將 `lottery_api/models/enhanced_dual_bet_predictor.py` 與
`tools/biglotto_diversified_ensemble_v6.py` 從
`OWNER_DECISION_REQUIRED` 移為 `BACKTESTED`。前者保存公開
`EnhancedDualBetPredictor.predict("BIG_LOTTO")` 的兩張 positional
原生票券：window-500 zone balance 後接 window-300 Bayesian，並套用來源的
negative exclusion。後者保存 `DiversifiedEnsemble.predict_3bets` 的三張
positional 票券：consensus／graph synergy 兩張後接 tail disruptor。

兩法都以 target 嚴格較早的完整 history prefix 執行，並在呼叫 frozen
recent-first entrypoint 前反轉資料順序。Enhanced Dual 是 deterministic
selection path，最低需要 100 期歷史；V6 每個 target 呼叫都依原始碼重設
Python 與 NumPy seed 為 42，最低需要 1 期歷史。其 RNG protocol 與 frozen
CPython 3.9.6／NumPy 1.26.2／SciPy 1.12.0／NetworkX 3.2.1 runtime identity
一併保存在 ledger，不把 seeded 方法誤記為 deterministic。

完整 input 有 4,298 個 execution：4,197 `OK`、101
`CLOSED_INSUFFICIENT_HISTORY`。Enhanced Dual 為 2,049 `OK`／100 closed，
其中一個兩注原生 portfolio 保留一張 positional duplicate；V6 為
2,148 `OK`／1 closed，所有三注 portfolio 均無原生 duplicate。Candidate-K
49、來源內候選池 K（Enhanced Dual 為 49；V6 為 12／20／49）、原生注數
2／3、來源配置數 1、combination count null 與 ordered-20 注數均分欄保存。
每個成功 execution 只建立一次 ordered 20，5／10／15／20 回測只取同一
portfolio 的 prefix。

可重現 artifact identity：

- ledger physical／content SHA-256：
  `3070f69175c806674547111c54b8109d94ec57c8b34a78b1082f4e34adbabe01`／
  `c104cd26281dd1786a0dc037eab2ceff2f4a1ac5f4c237b6be723c724637fa44`。
- parity physical／content SHA-256：
  `653afe296021e296f495e2b131bc3a55bf5b76010f76b7b8c3a82f3e1f4c39af`／
  `5243a1537b7f109a9cc784c12cf1621f2f2f109055c837ca8e9f41611890440e`。
- materialized input physical／canonical SHA-256：
  `68d841d826fe7904bcd9cd0498234ed4f42e8883390d4b1bd06241c37b03f9a7`／
  `93bf5662d66ed7bd7a9add2e87d59e7b3cc4df05349905c8db419aa1cba26b29`。
- compact evidence SHA-256：
  `7db702bf9754c1a2d037130b9a11ce7b52e14121097e048d6c09cf505832ad35`。
- pre-overlay transition report physical／content SHA-256：
  `8c4a71e41a6de16d3fbea7f79a2ecfafdbaeadf7344f4af277e1f1ca0e1d0a99`／
  `9d797d7300cebba69af48389ac792bf23520b043dad39b63c5469f3c05509f04`。
- 更新後 catalog physical／content SHA-256：
  `33c4a9f1be363fab2e566b3931c58a2990ee52abf4199f0b8d4fe5076d020199`／
  `4d4211355dc84791616a6f68f29dce3bbd293fa829426d8ed519618eb0fbf369`。
- Final-tree report physical／content SHA-256：
  `4f1d38c90eb155044d357ac84169c17000b7b0ad403d2012481d7d265d80bdb6`／
  `8fa5012c2bf81d571dd44ad4da8121d0b418c3e47d05cbbded922db2bc65c7ad`。

第二次 frozen-runtime parity、ledger、input、evidence 與 catalog 重建均逐位元
相同。Final-tree report 中除 catalog identity 與 checksum manifest 外，七個
計算 CSV 也與 pre-overlay transition run 逐位元一致。

更新後清冊為 126 `BACKTESTED`、73 `CLOSED_UNEXECUTABLE`、
12 `DUPLICATE_ALIAS`、10 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。本批僅完成兩個正式處置；221 筆工作尚未
全量完成，11 個 replay-backed 策略也仍只是一個先行批次。所有成功率與精確
隨機基準差異只供描述性歷史研究，不保證未來中獎。

## Wave 59：AutoML retrospective search 正式處置

Wave 59 對 `ai_lab/scripts/automl_strategy_optimizer.py` 完成 frozen
source／blob review，並從 `OWNER_DECISION_REQUIRED` 移為
`CLOSED_UNEXECUTABLE`。該來源逐一用已知 target outcomes 評分
method／window combinations，`search` 的唯一輸出是 methods、window、
win rate、M4 count 等 aggregate leaderboard records；`main` 也只保存
Power Lotto／Big Lotto 的 search return value，沒有把勝出配置套用到下一個
target 或回傳 evaluation loop 內曾產生的票券。

因此任意選一個 leaderboard row、再補一套「如何對後續 target 出票」的規則，
都會創造新方法而不是復現 frozen source。這不是因舊治理狀態排除，而是以
source output boundary 明確證明沒有可供 ordered-20 回測的 source-defined
target portfolio。

Artifact identity：

- disposition evidence SHA-256：
  `c57853e4d6a0daad65ed9852072ac3037210715f5ce2fc5786baa57b821e084e`。
- 更新後 catalog physical／content SHA-256：
  `5034dea7d5f1e9b42b62a0291237ea103fe93d79617db4564bb735bbf4936138`／
  `57897e5073fbeb796ad90df9ad67010d8001c14c775c554b2304c3d6c6e6fd88`。
- Final-tree report physical／content SHA-256：
  `9b8a7a84542abab6ce29002d0a19ea187d385a56b4f516d66f971175bfdec8a8`／
  `fafa3b318c0e284344ec5dfa689ff69ca7f8ab46d4578f81c370d182a64da6b5`。

Evidence build 與 catalog overlay 在第二個獨立目錄逐位元相同。更新後清冊為
126 `BACKTESTED`、74 `CLOSED_UNEXECUTABLE`、12 `DUPLICATE_ALIAS`、
9 `OWNER_DECISION_REQUIRED`，仍明確 `full_universe_complete=false`；
其 closed row 仍保留在完整 universe、ranking 與 CSV／JSON。

## Wave 60：Hybrid、Orthogonal 與 Zone seeded benchmark selectors

Wave 60 將 `tools/hybrid_integration_benchmark.py`、
`tools/orthogonal_diversification_benchmark.py` 與
`tools/zone_split_optimizer.py` 從 `OWNER_DECISION_REQUIRED` 移為
`BACKTESTED`。三法都保留 frozen source 的 BIG_LOTTO local
configuration declaration order，並將 module-level Python／NumPy seed 42
轉為明示的 target-stable causal protocol：每個 target 先重設兩個 RNG，再依
來源順序執行所有本地配置。這個 protocol、runtime 與 full-prefix context
均封存在 checksummed ledger。

原生 portfolio 語意如下：

- Hybrid 保留 Zone + Frequency、Zone + Gap、Zone + Entropy、Mixed
  四個本地配置，每個配置三注，共 12 個 positional tickets；imported
  `MultiBetOptimizer` comparator 依來源邊界明示排除，不冒充本檔選號邏輯。
- Orthogonal 依 source main 的 2-bet block 再 3-bet block，於每個 block
  依七個策略宣告順序展開，共 35 個 positional tickets。
- Zone 依六個 variant 宣告順序、每個三注展開，共 18 個 positional tickets。

三法各有 2,148 個 `OK` execution，首期因沒有前一期 cutoff 明示
`CLOSED_INSUFFICIENT_HISTORY`；總 input 為 6,447 個 execution。
Candidate-K 49、local configuration count 4／14／6、native ticket count
12／35／18 與 ordered-20 分欄保存。原生重複位置不刪除：Hybrid duplicate
count 分布為 3:2128、4:6、5:8、6:6；Orthogonal 固定為 4:2148；Zone
為 0:2145、1:3。

可重現 artifact identity：

- ledger physical／content SHA-256：
  `0834d1b9e1acb622a142fbf29b35ef2a4aa5d269583b67a0fecd6862ca9ccc4b`／
  `5541db19ad9ffe08d43ea375415662b19063db40df28d58ae8a1dfe1ecc52ab6`。
- parity physical／content SHA-256：
  `0321d87cec9552b0c0bd6d3dfba7596de320ecb2511de7a94a39dbc063bf4705`／
  `025ca7355f1567eb387576e08c42bf125cea1acf80e44c31008a2139a3ea9777`。
- materialized input physical／canonical SHA-256：
  `e3b66f2626919549c794e5b6ecaee0de48f1426e130a7679018a8ad06d31283a`／
  `9946c3113bf8031cb28765dee428b153ef5616ef57a96ad17be37e722e7d599c`。
- compact evidence SHA-256：
  `e93a8759d40dbacc674546e2fca284ac14c728e31e74a91d6a9a1e974329033e`。
- pre-overlay transition report physical／content SHA-256：
  `0d14296afd286c8cbe91a3211addbc98deca763600446aa8542aa63f3f7f2693`／
  `0769459ec4aa11c3da4cc1b353eddf65bcc26daf75fc045218775d7fb4b4224b`。
- 更新後 catalog physical／content SHA-256：
  `21e229c8994b292dc7be08922c15113094d3f19e8d675282ca388a6d23ceeb44`／
  `d3d3aaa7b8b0b8b6dff39ea900440944812cdb5118f90c20a9dd02c733be77f9`。
- Final-tree report physical／content SHA-256：
  `e97bf0ba6d3b5f27a021afb391d739ef6515972f085400f66b2b53bfb16be42d`／
  `042b8251563245cab086615286999540f0d140ed0d4703bd8e9472566c0f832d`。

第二次 frozen-runtime ledger、parity、input、evidence 與 catalog 重建均逐位元
相同。更新後清冊為 129 `BACKTESTED`、74 `CLOSED_UNEXECUTABLE`、
12 `DUPLICATE_ALIAS`、6 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有成功率與精確隨機基準差異只供描述性
歷史研究，不保證未來中獎。

## Wave 61：Five-bet closed-result horizon replay

Wave 61 將 `tools/test_5bet_optimization.py` 從
`OWNER_DECISION_REQUIRED` 移為 `BACKTESTED`。復現保留 source main 的五個
呼叫區塊與原始順序：5ME horizon 150、4P1 horizon 150、5ME horizon 200、
4P1 horizon 200、Dense horizon 200；每個 horizon run 均依 frozen source
重設 Python／NumPy seed 42。每個 target 只提供嚴格較早的完整歷史 prefix，
不讀 target 結果。

來源本身只定義最後 200 期的 closed-result benchmark，因此 2,149 個 target
中有 1,949 個明確 `CLOSED_REJECTED`。其餘 target 有 186 個合法
portfolio：前 50 個 horizon-only target 含三個完成配置、保留 15 個原生
票券位置；最後 150 個 target 原則上含五個配置、保留 25 個位置，其中 frozen
來源有 14 個 target 產出非法票券，依原始執行邊界明確記為
`CLOSED_EXECUTION_ERROR`，不修號、不補票、不冒充成功執行。合法輸出共
4,160 個原生票券位置；重複票券分布 2:20、3:19、4:5、5:5、11:39、
12:66、13:19、14:12、15:1，均依原位保留。

Candidate-K 固定保存為合法號碼域 49；來源實際完成的 configuration count
為 3 或 5；native ticket count 為 15 或 25。三者與 ordered-20 portfolio
分欄保存。每個合法 target 只建構一次有序 20 注，5／10／15／20 注回測
皆取相同 portfolio 的 prefix。合法 ticket sequence SHA-256 為
`226f676ff85288bf8adf0198a92640144a46da04e88315252bd56733a3983af1`。

可重現 artifact identity：

- ledger physical／content SHA-256：
  `b20c1aadef9c63c3918d461f69790bdee77e6b8d1b883ea9a57a4d6719340810`／
  `6f30be57e92a71d6aa3570d84b71af9ef844949dad72ca9e36b39390d6944a7d`。
- parity physical／content SHA-256：
  `47d27bbd00eefe9525d2c028154727b919850a0658ae0b1fb78246a07f100949`／
  `0de9a589013df3748f0b9b8d596a470d00b78d5ccf11f6f54e04563d2762c88e`。
- materialized input physical／canonical SHA-256：
  `ddbb9ff87252e0844cb0deb40d7a1fa02d825ed11e07e6b931bf1877182717d3`／
  `2accbe2596a33d767833f375b37c4715a8f9272c5159df4c295eb1a886729c32`。
- compact evidence SHA-256：
  `75df66d094c926c4e58f2872599fcaca780508ed0061452d957d20e6c2b53560`。
- pre-overlay transition report physical／content SHA-256：
  `8eb95f4a9e4d34d7f0612c5df37d0a15239012d01a9aad1ceaec4de3ea237a10`／
  `ea0950f3f9f46ecbf29f12c54e95540a4641f76565d82ae1d940b081ad830181`。
- 更新後 catalog physical／content SHA-256：
  `b216eebf3cad8fc47bc75c908f7035a9697cc9165d872f9fae1d9f9ca42b83bd`／
  `9d80f7e5e6e996b825f19cf8c209f7148576429785a72daa9462134549a8661c`。
- Final-tree report physical／content SHA-256：
  `700d77025c74ff2d5276fad26236896d957d78d1dd441d6874bfc51adb9f68bf`／
  `2395178b9afbced9b703bcf4a3178a372049ae91e15375023c952134c674b5db`。

第二次 frozen-runtime ledger、parity、input、evidence 與 catalog 重建均逐位元
相同。更新後清冊為 130 `BACKTESTED`、74 `CLOSED_UNEXECUTABLE`、
12 `DUPLICATE_ALIAS`、5 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有成功率與精確隨機基準差異只供描述性
歷史研究，不保證未來中獎。

## Wave 62：Diversified ensemble 與 horizon wrapper

Wave 62 將 `tools/biglotto_diversified_ensemble.py` 與
`tools/backtest_diversified_3bet.py` 從 `OWNER_DECISION_REQUIRED` 移為
`BACKTESTED`。兩筆 universe record 維持獨立策略 identity：

- 原始 ensemble 保存公開 `DiversifiedEnsemble.predict_3bets` 的
  Consensus Prime、GNN-Structural Flux、Entropy Outlier 三個 positional
  tickets。每個 target 重新建立 frozen predictor，依來源將 Python／NumPy
  seed 重設為 42；2,149 個 target 中 2,099 個成功，前 50 個依 frozen
  clustering 的明示最低歷史需求記為 `CLOSED_INSUFFICIENT_HISTORY`。
- wrapper 保存 `run_comprehensive_audit` 的 DIVERSIFIED 路徑，依 source main
  先執行 horizon 150、再執行 horizon 500，且每個 horizon 開頭重設
  Python／NumPy seed 123。最後 500 期中，前 350 期保留一個三注區塊，
  重疊的最後 150 期依 source horizon order 保留兩個區塊、共六個位置；
  其餘 1,649 期明確 `CLOSED_REJECTED`。`predict_random_3bets` 在來源中是
  明示的 Random comparator，不混入 DIVERSIFIED 策略的原生 portfolio。

兩法合計 4,298 個 execution：2,599 `OK`、50
`CLOSED_INSUFFICIENT_HISTORY`、1,649 `CLOSED_REJECTED`，保存 8,247 個
原生票券位置。原始 ensemble 的 2,099 個三注 portfolio 都沒有重複位置；
wrapper 的 duplicate count 分布為 0:350、1:139、2:10、3:1。Candidate-K
49、來源 candidate pools 8／12／49、configuration block count 1／2、
native ticket count 3／6 與 ordered-20 注數分欄保存。每個成功 execution
只建立一個有序 20 注 portfolio，5／10／15／20 注皆取同一序列 prefix。

可重現 artifact identity：

- ledger physical／content SHA-256：
  `223b593f391d3f9f9aafc1c494b7693e4e25a194c68c620a83c8ee822b1182e9`／
  `e9425e15961b4d5733b6a1eaa5aac976229a6e55e3d7f1ecfcf27378f1e57f1c`。
- parity physical／content SHA-256：
  `6eca2bba9558892160858d0bfdc96051f1529f1607da5fb5b16390b1b5007938`／
  `633e517f7fa33e14206d526b31a16a4a2a496a94a42166b9ec5baf8c80543709`。
- materialized input physical／canonical SHA-256：
  `6a200ea7a0b8fe9c6b558a4489ba376238fb8ffd29639a2060653700bf09ff63`／
  `4ccbccd2bd8f33bfcdeda4fa0833afe3904980df60ddefd4b6e062c37b5dcd19`。
- compact evidence SHA-256：
  `7441a0e0007e8d4e53f9e2e05ccc350d20518411b847b6c36ffd07ec4cbbfd3d`。
- pre-overlay transition report physical／content SHA-256：
  `89f4af7d63901748e8e0c7994a2914e812bad7c3b58792efc5834f2a83d2da98`／
  `5e48902cd79eae2498989aae7729b7d6cfafeee949393f1a57c3b7761050612b`。
- 更新後 catalog physical／content SHA-256：
  `0e8a8ab19084a112a354b754d98fe91386d2fafa4617db352fa8305af8f84ae4`／
  `093eca2714e5f3c35e0b03eaf359cca4c8570c7d4b2f0a092b06eacfc3629063`。
- Final-tree report physical／content SHA-256：
  `72246b7ed0ea3bd7aa365a5b5dbbc5c12fc72439c5d96360d46b2f37118d73ba`／
  `5e1858f2a713c320af0564e538bee5f4720dcfbd914bed8906ee3664320dcf67`。

第二次 frozen-runtime ledger、parity、input、evidence 與 catalog 重建均逐位元
相同。更新後清冊為 132 `BACKTESTED`、74 `CLOSED_UNEXECUTABLE`、
12 `DUPLICATE_ALIAS`、3 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。所有成功率與精確隨機基準差異只供描述性
歷史研究，不保證未來中獎。

## Wave 63：Advanced local-method benchmark

Wave 63 將 `tools/advanced_methods_benchmark.py` 從
`OWNER_DECISION_REQUIRED` 移為 `BACKTESTED`。本批次直接重用已完成、通過
SHA-256 與 authority 驗證的 frozen parity ledger，沒有重新執行 2,148 個
frozen selector targets 或 53,700 個原生票券位置。

因果 adapter 對每個 target 只使用嚴格較早的完整歷史 prefix，依來源限制取最近
1,000 期，再重新建立 Contextual Bandit、Copula Analysis、Anomaly Detection、
Graph PageRank 與 Attention Scorer 五個 local selectors。每期先將 Python 與
NumPy RNG 重設為 42，再依來源順序展開 `num_bets=2` 的五個方法區塊，接著展開
`num_bets=3` 的五個方法區塊，共保存 25 個 positional native tickets。來源中
明示的 random comparator 不混入策略 portfolio；source main 以反時間順序重用
mutable selector state 的非因果執行方式也不納入 adapter。

2,149 個 target 中有 2,148 個 `OK` execution；第一期因沒有嚴格較早 cutoff
明示為 `CLOSED_INSUFFICIENT_HISTORY`。Candidate-K 49、local configuration
count 10、native ticket count 25 與 ordered-20 portfolio count 分欄保存。
原生重複位置不刪除，duplicate count 分布為 20:2133、21:8、22:6、23:1；
完整含 closed 位置的 ticket sequence SHA-256 為
`7a1927a300c96155ce9914344fa0247911ea2c3f0dda55ec84192766a2b6ed5f`。
每個成功 execution 只建構一次有序 20 注，5／10／15／20 注皆取同一序列
prefix。

可重現 artifact identity：

- ledger physical／content SHA-256：
  `f98ad62752c35bcf47fe00338f8e8b4ddd1f39caa73a80405409c963a8651d04`／
  `e168ef2d3176bbc62056fd54351a9eba4506ad7b841838d969107eace8b6cf34`。
- parity physical／content SHA-256：
  `52dc9ee26bde75e8fab2045ae1aa4aaa05f80dbd2dd967fb5cbf2c7958af9d6d`／
  `644f9b6cd3ddb19b647056da2d2cccc7c9e0119f8567df7c22a3ce67f8d46169`。
- materialized input physical／canonical SHA-256：
  `e501c2e1b0a5c610bae3822a2784a72860e2c549daadb37c344de61d16129493`／
  `155766ddc1f7581392d91fc8f5e79a433f6e245a9feefb5cb059b8d2594af7c9`。
- compact evidence SHA-256：
  `c9d0a3ae6e5678f1aca771dc88b1cc03b11756ce66c129a5198713bf594e0057`。
- pre-overlay transition report physical／content SHA-256：
  `7bb01b29c4e30b12c7feadbb6253c1b99986c0ec6fc66430399276088f0c702b`／
  `8fb4ab606e88cf9c1dc74f8ceaf6a476e76aa978925ed85ceb8e8b16a9df45c7`。
- 更新後 catalog physical／content SHA-256：
  `c9f632d1306af42748a5f11493fb19c8bafcddecd3810676ad4178d9133c68ab`／
  `518c00da6a791551a74766b1356686e16cef88a087e00e1fdc839dce8e18e8a4`。
- Final-tree report physical／content SHA-256：
  `b28c630de68352a1b1567a3d58473d68f1877ac6f6cfaab012b71c65ed8141b6`／
  `167b58d36242ca8b08f1231fccec9ee19ad71e59b8e888c23db5972b8adb153b`。

第二次 materialization 與 final-tree report 重建均逐位元相同；既有 parity
只作 checksum-pinned reuse，沒有重跑。更新後清冊為 133 `BACKTESTED`、
74 `CLOSED_UNEXECUTABLE`、12 `DUPLICATE_ALIAS`、2
`OWNER_DECISION_REQUIRED`，仍明確 `full_universe_complete=false`。剩餘兩筆
為 `lottery_api/models/xgboost_model.py` 與
`tools/evolving_strategy_engine/evolution_engine.py`，本 Wave 未開始其實作。
所有成功率與精確隨機基準差異只供描述性歷史研究，不保證未來中獎。

## Wave 64：Frozen XGBoost full-prefix replay

Wave 64 將 `lottery_api/models/xgboost_model.py` 從
`OWNER_DECISION_REQUIRED` 移為 `BACKTESTED`。Frozen authority 固定為 commit
`49a25effa62fc24f40789c16be6f11bdfb41a4a9`、blob
`331b97562b593c061937ad9afac79fc5b8d88152` 及 source SHA-256
`38c72a70c627285dab2b55163b387b3ed8ab6bd9820c10d7daed0dce777f1c01`。
原生 parity 使用 CPython 3.9.6、NumPy 1.26.2、pandas 2.1.3、
scikit-learn 1.3.2 與 XGBoost 2.0.2，沒有改用目前專案 runtime 的近似模型。

每個 target 只收到嚴格較早的完整歷史 prefix；來源再自行限制為最近 1,000
期，以過去五期起建構訓練樣本，為 1..49 各訓練一個 50-tree、
max-depth-3 binary classifier。少於 15 期歷史時，來源的 `len(X) < 10`
分支明確產生 `CLOSED_INSUFFICIENT_HISTORY`；因此 2,149 個 target 中保存
15 個 closed 與 2,134 個 `OK` execution。每個成功 execution 原生只有一張
由 49 個 label probability 排序後取 Top-6、再升冪排序的票券。

來源沒有明示 `random_state`，但 `subsample` 與 column sampling 均維持完整
取樣。Parity 對 cutoffs 15、50、100、999、2148 分別執行單執行緒重跑，
並與 OpenMP 8-thread 輸出的票券及 selected probabilities 精確比對，全部
一致。完整 native ticket sequence SHA-256 為
`1d9752141cdc71301c7410b015bbbf6ca6dd522a687d6171da3def2b139a36df`；
selected-probability sequence SHA-256 為
`c35cda28dda4b45e0455842d07fa0d6db5224bc0a3281125ad919ecab600dc95`。

每個成功 target 只從該一張原生票建構一次有序 20 注；5／10／15／20 注都
取同一序列 prefix。Candidate-K 49、source configuration count 1、native
ticket count 1 與 ordered-20 count 保持不同欄位。Pre-overlay report 含
128 筆成功標準列（4 注數 × 4 視窗 × 8 標準）、16 筆官方獎項分布、
28,288 筆完整排名（221 策略 × 128 ranking slices）及 128 筆 Top-10 輸出；
未執行的其餘策略仍保留明確 unranked reason。

可重現 artifact identity：

- ledger physical／content SHA-256：
  `0e2946ccf9a803488afd5475e833bd557a40bf93e5d1cb26e912a29926b1a9ba`／
  `e227e6c3aafb859fb56afaee99e0f1ab31cb792d8747ea972e2d959149810908`。
- parity physical／content SHA-256：
  `5778462fd4b4d1034e66c3e9e4b10ef8e2bcadf053ad2c096a0bdfc322114927`／
  `ed47a272603b1f4701f1615bf2c613161230dcb0aef8ea0720c11666db3de857`。
- materialized input physical／canonical SHA-256：
  `25ba060686325f72ba6a89d9528243f499e378f494cf055a52c2992943628480`／
  `477d8597fe76104bcd7abcece88a258a51d04b4de801d7afaba133d6e1da038a`。
- compact evidence SHA-256：
  `2173aa5a4c354c8d8d11c0459e3017dcc4baaca770dc6fc623df683c0b191741`。
- pre-overlay report physical／content SHA-256：
  `6167700a8a44e0d7f9e2596e093c53ac97c278bd1ab20e7d0682b49dd91e3279`／
  `505c0dc63d081dcd10a9aa530b20af4319000a4d16d22613e73ef6c7e448542f`。
- catalog overlay 後的 final-tree report physical／content SHA-256：
  `ca6ea3cc5472d23cd9734de8323e18a885bb368326f2466b87e9e05fbac0292a`／
  `bf803972e4b8e4ea114d323203a6b3dbcb2ed2f49fa1e573841f5b07ee187f05`；
  兩次獨立 ledger-backed materialization 與 report build 的 input 及八個 report
  檔案均逐位元相同，且沒有重跑 XGBoost target。
- 更新後 catalog physical／content SHA-256：
  `36f2a7cf61f5e0c9d436154f8477ebd320d287e8601debbc47409ab45b1e2eb1`／
  `f66487d501864ee00f62a7cb237175600308120f7ad60df79681e812ae7e34e9`。

更新後清冊為 134 `BACKTESTED`、74 `CLOSED_UNEXECUTABLE`、
12 `DUPLICATE_ALIAS`、1 `OWNER_DECISION_REQUIRED`，仍明確
`full_universe_complete=false`。唯一尚未正式處置的方法為
`tools/evolving_strategy_engine/evolution_engine.py`；Wave 64 沒有開始其
實作。所有成功率與精確隨機基準差異只供描述性歷史研究，不保證未來中獎。

## Wave 65：Frozen evolution-engine full-prefix replay

Wave 65 完成最後一個
`tools/evolving_strategy_engine/evolution_engine.py`。唯一 authority 是
frozen commit `49a25effa62fc24f40789c16be6f11bdfb41a4a9` 的 source blob；
`tools/run_evolution.py` 所指定的 seed 42、8 generations、population 50 與
`n_test=1500` 均保留。Import-time 全腳本副作用由隔離 wrapper 阻止，來源的
population、fitness、selection、crossover、mutation、generation 與最終
`report["1_leaderboard"]` 票券位置順序則保持不變。

每個 target 只接收嚴格較早的完整歷史 prefix。來源 OOS evaluator 要求超過
500 期歷史，因此前 501 個 target 明確保存
`CLOSED_INSUFFICIENT_HISTORY/OOS_EVALUATOR_REQUIRES_MORE_THAN_500_HISTORY_DRAWS`，
其後 1,648 個 target 成功。原生 leaderboard 長度介於 1 至 10，共 12,959 個
票券位置；重複位置不去除，其 duplicate-count 分布為
0:413、1:479、2:352、3:225、4:111、5:46、6:13、7:7、8:2。
完整 native ticket sequence SHA-256 為
`f730565f18f4fe44071f71c0e5f1bfe0159943eab7ae64bee144412caea4bfbe`。

Candidate-K 與 combination count 在此來源都沒有定義，故保持 `None`；
population size、每代 population、strategies tested、native ticket count 與
ordered-20 count 分欄保存，沒有互相冒充。每個成功 target 只從來源
leaderboard 建構一次有序 20 注，5／10／15／20 注全部取同一 portfolio prefix。
Pre-overlay report 包含 128 筆成功標準列、16 筆官方獎項分布、28,288 筆完整
221 策略排名與 128 筆 Top-10；所有未排名列均保留原因。

可重現 artifact identity：

- ledger physical／content SHA-256：
  `3bc4067a0b27cfdf79e9514b4dc578a89b8e454565737dba6c854b23f0a62d1b`／
  `27e73c12ffae5388f112d252e94dedc130322b7124d39129c970575b84455bd3`。
- parity physical／content SHA-256：
  `97b68328d7a6435f18cadc3785b5f1d96abdf37044c2b24581fdf01b784a3195`／
  `bd573643a061f27a9620fb296bca2679dabcd610a9c162bed8c38ca2c7afe0da`；
  83 個 shard 的兩次 combine 逐位元相同，且 cutoff 501 原生與純 memoization
  projection checksum 相同。
- materialized input physical／canonical SHA-256：
  `172fbf2ac4c3bbe7c7e6da11089067f68f10d6c5d6f5008983609c49f4fcbe71`／
  `8d147879497fcf78134e42801203a9499dfc11fc23c1f4de658a0c74c7128d1b`。
- compact evidence SHA-256：
  `d99600e08f1160f3e750e1ea3656030a3cd77dfbef821de102ec666c5d2c3541`。
- pre-overlay report physical／content SHA-256：
  `98bbf9a02c2b0621576c3824d52c116c0071b81fce7f4db9987dcd38e234dab4`／
  `26f5a59b060aec251a3882ce31f8ee9c77ecb324e868013e425cb0f94dfe7a08`。
- final catalog physical／content SHA-256：
  `e604a038622fa9476aa86b33cd8068287664ec49cd5a27c81996ecb59a88dfbf`／
  `9e2d9f6c3cffbfe9867d4aaafbf8c9315922503fc0b806dfc84627699e0d82e3`。
- final-tree report physical／content SHA-256：
  `640bc79681a8879849f7c9b2efc9f353569f5fb0efeb1de0d53cb6918e35080c`／
  `23289a455d57803acaa4457a12c97d2976e7e8af08e4e27ddcf504adea1b7d46`；
  兩次獨立 ledger-backed materialization 及八個 report 檔案逐位元相同，
  沒有重跑 legacy evolution targets。

最終清冊為 135 `BACKTESTED`、74 `CLOSED_UNEXECUTABLE`、
12 `DUPLICATE_ALIAS`、0 `OWNER_DECISION_REQUIRED`，
`uncompleted_count=0` 且 `full_universe_complete=true`。這表示 221 個
authoritative actual methods 均已取得正式處置；11 個 replay-backed 策略仍只是
早期批次，不能當成母體定義。所有歷史成功率、官方獎項統計與精確隨機基準差異
只供描述性研究，不保證未來中獎。

另有七十四個方法已取得正式 `CLOSED_UNEXECUTABLE` 處置，而非靜默排除：

- `backtest_39lotto_comprehensive.py` 固定只讀 `DAILY_539` 並以 1..39 選 5
  產票與計算基準，沒有大樂透 6/49 語意。
- `test-optimization-simple.py`、`test-optimization-b.py` 與
  `test-all-optimizations.py` 只以 synthetic random history smoke-test imported
  predictors 與 confidence，沒有自己的 target portfolio。
- `automl_strategy_optimizer.py` 只輸出 outcome-ranked method／window
  leaderboard，沒有把勝出配置套用到後續 target 或輸出一組原生票券。
- `backtest_ml_comprehensive_2025_biglotto.py` 只計分並排名八個 imported
  predictors，沒有獨立選號或 source-defined portfolio choice。
- `audit_raw_experts.py` 只比較 imported HPSB／AI predictors 與明示 random
  baseline 的已知結果命中分布，沒有自己的 target portfolio。
- `experimental/compare_models.py` 只包裝 imported models 並事後排名 metrics，
  wrappers 沒有新增選號邏輯。
- `analyze_theoretical_vs_actual.py` 只有純量機率與硬編碼報表，沒有選號 entrypoint。
- `p47_wave4_powerlotto_adapters.py` 明示只支援 `POWER_LOTTO`，且拒絕
  `BIG_LOTTO`；1..38 加獨立特別號不能冒充大樂透票券。
- `big_lotto_optimizer.py` 必須先接收未保存、也未指定來源策略的
  `predicted_numbers`，不能憑空製造歷史上游輸入。
- `advanced_prediction_engine.py` 依執行環境決定 ML backend，並從三個相對
  CSV path 選第一個存在者；歷史分支與資料 identity 均未保存。
- `bayesian_ensemble.py` 要求外部 `UnifiedPredictionEngine` 提供六個未在本來源
  版本化的策略方法。
- `autogluon_model.py` 會條件讀取未保存的 `models/best_config.json` 並替換所有
  預設權重。
- `automl_biglotto/report.py` 只把外部傳入的已完成 AutoML 結果轉成 JSON／console
  report，沒有選號 entrypoint。
- `p540a_full_replay_regeneration_readiness.py` 明示是只讀 readiness inventory；
  `choose_recommended_next_task` 選的是後續工作描述，不是樂透號碼。
- `p540b_daily539_incremental_replay_generation.py` 把 `LOTTERY_TYPE` 固定為
  `DAILY_539`，且所有 adapter 都以該常數執行；不能改成大樂透後聲稱為原方法。
- `predraw_ledger.py` 的 writer 要求 caller 先傳入 `predicted_numbers`；
  `select_eligible_records` 選的是既有 ledger record，不是選號方法。
- `analyze_proximity_115000019.py` 只比較既有 hard-coded 策略票券與已知結果；
  隨機票券只作 Monte Carlo baseline。
- `null_hypothesis_115000019.py` 對已知 target draw 執行統計假設檢定；模擬組合
  只累計 null distribution，不輸出票券。
- `analyze_draw_115000019.py` 是已知開獎結果的描述性分析；隨機樣本只用於
  percentile／simulation。
- `eval_traits_115000021.py` 只列印 caller 提供或 hard-coded winning numbers
  的 frequency／gap traits。
- `predict_superlotto_best.py` 明示只讀 `POWER_LOTTO`，產生 1..38 主區加 1..8
  第二區，不能轉稱為大樂透方法。
- `train_critic.py` 的隨機組合只是 NeuralCritic 的 synthetic negative training
  examples；程式只訓練並保存權重，不產生 target-draw ticket。
- `analyze_biglotto_special.py` 只稽核歷史特別號的 repeater／Markov 稀疏性，
  沒有輸出主號票券或任何預測。
- `arbitrage_analysis.py` 的契約明示不輸出號碼；組合運算只計算機率、覆蓋成本
  與 jackpot threshold。
- `generate_realistic_data.py` 產生 synthetic historical CSV 與輸入模板，不是
  以因果歷史預測某個 target draw。
- `negative_selector.py` 與 `negative_selector_optimized.py` 只產生
  variable-length kill list；來源未指定哪個 positive selector 應消費它，不能把
  排除號碼冒充六碼票券。
- `backtest_must_not_hit.py` 只產生 Bottom 5／10／15 號碼池並統計 clean rate，
  沒有六碼票券建構規則，也沒有定義如何從補集選票。
- `backtest_p1_dynamic.py` 只比較 Smart-10 與 P1 Dynamic 十碼 kill set 的
  leaks／clean-kill rate，沒有 positive selector 或票券輸出。
- `test_smh.py` 使用未 seed、未保存 pre-state 的 module-global RNG 取樣；
  補一個新 seed 會改變 frozen 方法，無法產生可重現的歷史原生票券。
- `biglotto_special_v4.py` 只排名 Top-4 特別號候選並評估第七顆特別號命中，
  沒有六個主號的票券建構規則。
- `p270b_outcome_blind_portfolio_geometry_power_audit.py` 只稽核既有 replay
  portfolio 的 geometry 與 statistical power，明示不回測、也不生成策略。
- `p282b_big649_deduplicated_portfolio_replay.py` 只對既有 replay tickets
  作 retrospective dedup falsification，不補票且不輸出 current/future live ticket。
- `backtest_6_bets.py` 的六注全部來自 localhost `/api/predict` response；
  source 沒有保存 response 或 server／model artifact identity。
- `backtest_8_bets_2025.py` 的八模型票券來自
  `/api/predict-from-backend-eval`，且 prediction request 只傳 `recent_count`，
  沒有傳入宣稱的 rolling history。
- `backtest_8_bets_2025_v2.py` 雖保存八個 history window，但每張票仍由
  localhost `/api/predict` 回傳；補票只會複製最後一個 opaque response。
- `rolling_backtest_2025.py` 同樣只把 caller history 壓成 `recent_count` 後
  讀取 server 自有 DB 與 model state，沒有 source-native ticket generator。
- `benchmark_hybrid.py` 與 `benchmark_rl.py` 的 frozen 9-feature model
  architecture 無法 strict-load 各自的 7-feature checkpoint，且 predictor
  也只產生 7 維特徵；兩者都在任何 ticket selection 前停止。
- `lstm_attention_predictor.py` 與 `perball_lstm.py` 會在 selection
  entrypoint 內訓練未綁定 seed／pre-state 的新神經模型；任意補 seed 會改變
  frozen 原生票券，不能冒充來源結果。
- `multi_bet_optimizer.py` 會先訓練同一個未保存 pre-state 的 Per-Ball LSTM，
  並可能用 temperature sampling 產生第二注，無法恢復唯一三注序列。
- `coverage_strategy_research.py` 與 `covering_research.py` 都用未 seed 的
  module-global RNG 建池、shuffle 或 sample 原生注單；歷史 RNG pre-state
  沒有保存。
- `enhanced_predictor.py` 的 constrained 與 enhanced-ensemble selector、
  `dynamic_ensemble_predictor.py` 的正常 strategy loop，以及
  `multi_bet_optimizer.py` 的 diversified portfolio 都會消耗未綁定的
  stochastic selection state。
- `mcts_portfolio_optimizer.py` 以 unseeded sample 初始化兩注，並以
  randint／choice mutation；`transformer_model.py` 則在首次選票前訓練未
  seed 的新模型。
- `benchmark_dual_bet.py`、`benchmark_new_strategies.py`、
  `predict_biglotto_6bets_optimized.py` 與 `strategy_leaderboard.py` 都把
  unseeded Monte Carlo／random ticket 路徑納入正式 native configuration。
- `auto_optimizer.py` 的 method/window 選擇、`meta_learning.py` 的 torch
  backend 與 `ultra_optimized_predictor.py` 的正常出票都依賴未保存的
  stochastic pre-state；`optimized_predictor.py` 的多注輸出則直接委派給
  unseeded diversified optimizer。
- `backtest_phase1_comparison.py`、`find_best_test_periods.py`、
  `generate_final_predictions.py`、`generate_v7_predictions.py`、
  `predict_big_lotto_115000003.py` 與 `predict_biglotto_7bets_optimized.py`
  都把同一個未綁定 pre-state 的 upstream portfolio 當成實際票券。
- `unified_predictor.py` 的 Monte Carlo／ensemble、`advanced_strategies.py`
  的 entropy-outlier／portfolio completion、`selective_ensemble.py` 與
  `auto_optimizer_v2.py` 都有未保存 pre-state 的正式 stochastic
  selection path。
- `big_lotto_dual_bet_optimizer.py`、`big_lotto_2025_tournament.py`、
  `predict_114000118.py` 與 `verify_cluster_size.py` 都會把上述 unseeded
  unified ensemble output 納入其原生票券或 meta-method selection。

每筆 closed record 仍留在 221 策略 universe、完整排名及 CSV／JSON，並帶穩定
reason code；其 frozen source facts 與 checksum 保存在 static disposition evidence。

另有 `biglotto_diversified_ensemble_v6_backup.py` 與
`biglotto_diversified_ensemble_v6.py` 在 frozen commit 中指向同一 Git blob、byte
size 與 SHA-256，且逐位元比較相同。因此 backup 以 `DUPLICATE_ALIAS` 留在 221
母體，明確指向 canonical strategy ID，不另造排名列或假裝是不同方法。

## 多注回測輸入

```bash
uv run --no-sync lottolab backtest-biglotto-portfolios \
  --input-file /absolute/operator-owned/backtest-input.json \
  --output-directory /absolute/new-or-empty/output-directory
```

輸入的 `schema_version` 必須是
`BIG_LOTTO_MULTI_TICKET_BACKTEST_INPUT_V1`。頂層必要欄位為：

- `lottery_type="BIG_LOTTO"`、`dataset_id`、`dataset_version`、`dataset_sha256`。
- 依日期與期號遞增的 `targets`；每期包含 6 個官方主號與 1 個特別號。
- `executions`；identity 是 `strategy_id + target_draw_number`，不可重複。

成功 execution 必須提供：

- 與 packaged 221 清冊相符的 `strategy_id`、`strategy_version`。
- 嚴格早於 target 的 `history_cutoff_draw_number` 與
  `history_cutoff_draw_date`。
- `native_ticket_count` 與同序的 `native_tickets`；重複票券不會被靜默刪除。
- `portfolio_ticket_count=20` 與同序的 `ordered_portfolio`。
- `portfolio_derivation`。
- 若為可重現隨機原生移植，另帶 `native_generation`，鎖定 protocol、method、
  source、target、replicate、seed digest 與原生注數。
- 可省略、但語意獨立的 `candidate_k`、`candidate_combination_count`
  與 `combination_count`。

closed execution 使用
`CLOSED_INSUFFICIENT_HISTORY`、`CLOSED_REJECTED`、
`CLOSED_INVALID_OUTPUT` 或 `CLOSED_EXECUTION_ERROR`，必須帶
`reason_code`，且不得帶任何票券欄位。若 causal cutoff 已知，兩個 cutoff
欄位必須同時提供且仍須早於 target。

評估器不產生或重新產生號碼。每次成功 execution 只接受一組 ordered 20
portfolio，5、10、15、20 注一律取 `portfolio[:K]`。Candidate-K、candidate
combination count、native ticket count、portfolio ticket count 與 source
combination count 維持不同欄位。

## 輸出與排名

輸出包含 report JSON、universe、execution audit、success metrics、官方獎項分布、
完整排名、Top 10 的 CSV，以及所有資料檔案的 `SHA256SUMS`。

每個可執行策略會產生：

- prefix 5、10、15、20；
- FULL、最近 750、300、50 期；
- `M3_PLUS`、`M4_PLUS`、`M5_PLUS`、`M6`、
  `M2_PLUS_SPECIAL`、`M3_PLUS_SPECIAL`、
  `M4_PLUS_SPECIAL`、`M5_PLUS_SPECIAL`；
- 官方 FIRST、SECOND、THIRD、FOURTH、FIFTH、SIXTH、SEVENTH、
  GENERAL 與 no-prize 統計；
- execution coverage、票券位置數、distinct／duplicate 數；
- `C(49,6)` 下 uniform IID legal-ticket-with-replacement 的精確分數基準與
  observed-minus-baseline 精確差異。

每個 prefix／window／criterion 的完整 ranking 都有 221 列。未執行、closed、
alias 或該視窗沒有成功 execution 的策略仍保留，並帶 `unranked_reason`；Top 10
只是同一完整 ranking 的前十列，不是另一套產號或評分。

所有成功率與隨機基準只供描述性歷史研究，不保證未來中獎、獎金或投資報酬。
