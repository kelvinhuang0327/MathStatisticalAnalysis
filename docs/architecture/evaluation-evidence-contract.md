# 策略評估證據契約（Strategy Evaluation Evidence Contract）

狀態：DESIGN FOUNDATION — 契約與驗證層，非生產判斷依據 ｜ 建立：2026-07-17（P600F R2）

本文件涵蓋 `src/lottolab/evidence/`、`tools/generate_evidence_schemas.py`、
`tools/validate_evaluation_evidence.py`、`contracts/evidence/` 的設計與不變式。

## 目的

這個任務只建立「策略評估證據」的**契約基礎**：不可變模型、canonical
序列化、確定性 hash、語意驗證、EX_ANTE／HISTORICAL_REPLAY 分離、metric
定義、ranking 政策與可比較性檢查。任務**不**產生任何真實證據、**不**計算
任何真實 metric、**不**產生任何排名。目前現況維持：

- `evaluation_metrics_available = false`
- `d3_status_available = false`
- `best_strategy_ranking_available = false`
- 原因代碼：`NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE`

高優先事項：完整性（integrity）、來源可追溯（provenance）、確定性重現
（deterministic reproduction）、因果標註（causal labeling）、避免事後諸葛
（hindsight）結果被包裝成預測。**本契約不是生產就緒，也不是任何策略的
「預測力證明」。**

## 分層（Contract Part 10）

```text
1. 生成 JSON Schema      structural: 型別、regex、enum、必要欄位
2. Pydantic contract models   local field/model invariants（models.py）
3. 語意驗證              hash 重算、因果算術、hit 重算、資料集交叉檢查、
                          definition-path 解析、trust 分類、可比較性
                          （validator.py / comparability.py）
4. Governance             Owner 對受保護 registry 的核准，本地驗證無法獨立證明
```

固定的 finding 分類（僅此八種，見 `models.FindingCategory`）：
`SCHEMA_FAILURE`、`SEMANTIC_FAILURE`、`HASH_MISMATCH`、`CAUSAL_VIOLATION`、
`UNVERIFIED_PROVENANCE`、`METRIC_DEFINITION_FAILURE`、`COMPARABILITY_FAILURE`、
`AUTHORITY_FAILURE`。

## LCJ-1 canonical JSON（`canonical_json.py`）

允許的值域：object、array、string、integer、boolean。禁止：二進位浮點數
（含 NaN／Infinity）、JSON `null`。可選但缺席的欄位一律省略，不寫成
`null`。整數絕對值不得超過 `9007199254740991`。object key 必須是唯一、
ASCII、符合 `^[a-z][a-z0-9_]*$`。

Canonical bytes 由這個固定演算法產生：

```python
json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
```

不做 Unicode normalization；producer 應輸出 NFC，但不同 normalization
視為不同內容。Hash 輸入不含結尾換行；**已提交的 JSON 檔案**（fixtures、
registries、metric definitions、四份 `.schema.json`）則是 canonical
bytes 再加**恰好一個**結尾 LF，UTF-8、無 BOM、無 CR。

四份 `.schema.json` 由 `tools/generate_evidence_schemas.py` 從 Pydantic
模型匯出，可能含有 JSON `null`（例如 Optional 欄位的
`"default": null`）——LCJ-1 的值域限制只約束**契約文件實例**（dataset
snapshot、evidence artifact、metric definition、ranking policy、
registry），不約束 schema 匯出檔本身；後者只沿用相同的排序／緊縮
格式慣例以利 diff。

## Hash 規則（Contract Part 2）

**Self-key-removed tree hashing**（hash 欄位是文件自身的一部分，計算時
排除自己）：

- `artifact_content_sha256`：evidence artifact 扣除 `artifact_content_sha256`
  本身之後的 LCJ-1 bytes。
- `record_sha256`：單筆 per-draw record 扣除 `record_sha256` 之後的 bytes。
- `dataset_sha256`：dataset snapshot 扣除 `dataset_sha256` 之後的 bytes。
- `rule_parameters_sha256`：`rule_parameters`／`rule_binding` 物件扣除
  自身欄位之後的 bytes（此欄位本身就內嵌在該物件中）。

**Sibling hash**（hash 欄位在文件中，但描述的是「另一個」子物件，該子
物件不含自己的 hash 欄位）：

- `parameters_sha256`：`parameters`（策略自訂超參數 dict）的 LCJ-1
  bytes，`parameters` 本身不含 `parameters_sha256`。

**Referenced-file hash**（已提交檔案的原始 bytes，含結尾 LF）：

- `feature_definition_sha256`、`metric_definition_sha256`：對應
  `*_definition_path` 指向檔案的 SHA-256。
- `policy_definition_sha256`：ranking policy **自身檔案**的原始 bytes
  SHA-256（用於比對 `approved_ranking_policy_registry.json`；不是
  policy 文件內的欄位）。

Definition 文件本身**不**內嵌自己的 content hash。

**Git OID 契約**：`git_commit`／`*_git_oid` 欄位是 40 碼小寫 hex；
`*_sha256` 欄位是 64 碼小寫 hex。兩者長度不同，天然互斥——Git OID 絕不
會被 `*_sha256` 欄位的 regex 接受，反之亦然。

**Hash 驗證三態**（`HashVerificationState`）：`VERIFIED_MATCH`、
`VERIFIED_MISMATCH`、`NOT_VERIFIABLE_INPUT_ABSENT`。來源 bytes 拿不到
時，永遠不能算作已驗證。

## Status 與 Trust 分離（Contract Part 3）

宣告的 status（`SYNTHETIC_TEST_ONLY` / `DRAFT` / `CANONICAL`，policy 為
`DRAFT` / `APPROVED`）**不授予信任**。信任是計算出來的：

- Evidence trust：`SYNTHETIC`、`UNTRUSTED_DECLARED`、`REGISTERED_CANONICAL`。
- Policy trust：`UNTRUSTED_DECLARED`、`REGISTERED_APPROVED`。

`REGISTERED_CANONICAL` 需要同時滿足：宣告狀態為 `CANONICAL`、非
synthetic、`artifact_content_sha256` 出現在已提交的 canonical registry
中、structural／semantic 驗證通過、所有必要 hash 皆
`VERIFIED_MATCH`、無阻擋 canonical gate 的未驗證來源。

## 空的 Owner-gated Registries

`contracts/evidence/canonical_evidence_registry.json` 與
`contracts/evidence/approved_ranking_policy_registry.json` 在本任務中
永遠是空的（`"entries": []`）。任何 fixture 都不可能通過 canonical／
approved gate——測試明確驗證這點（`test_committed_empty_registries_make_canonical_gate_unsatisfied`
等）。未來要新增 entry 需要 Owner 手動核准；本地驗證邏輯無法獨立
證明一筆 entry 對應的是真實、經審查的證據。

## EX_ANTE 與 HISTORICAL_REPLAY（Contract Part 6）

兩種評估模式**永不**被靜默合併或比較（comparability 的
shared-environment 維度之一就是 `evaluation_mode`）。`HISTORICAL_REPLAY`
不構成任何事前（ex-ante）因果宣稱。

### METADATA_CHECKED_ONLY 限制

因果驗證（cutoff 嚴格早於 target、target 落在評估窗內、訓練窗與固定
參數選窗不得晚於任一 record 的 cutoff、walk-forward 的 lag 算術、
one-shot 的共用 cutoff）只證明**宣告 metadata 的順序一致性**，**不**
證明 producer process 實際上從未存取未來資料。這是刻意的、有限度的
證明——避免給出超出本契約能力範圍的保證，也是防止「事後調參」
（hindsight tuning）偽裝成預測的第一道欄杆，而非唯一欄杆。

## Dataset 與 Outcome Provenance（Contract Part 4）

Dataset provenance 三種：`SYNTHETIC`（ID 必須以 `SYNTHETIC_` 開頭）、
`LOCAL_COMMITTED_FILE`（path／git OID／file hash 三者必備）、
`EXTERNAL_DECLARED`（除非能獨立取得 bytes，否則永遠 unverified）。

本基礎任務中，target 的實際開獎結果只能來自**同一份**供給的 dataset
snapshot；evidence 明確區分「策略在 cutoff 當下能看到的資料」與「後續
用於評分的實際結果」。

## Ticket 與 Hit 重算（Contract Part 7）

驗證器對每張 ticket 重新計算 main-hit count 與 special-hit；宣告值與
重算值不一致即為 `SEMANTIC_FAILURE`。`special_hit` 的型別依賴規則
契約：`special_number_count <= 1` 時為 boolean，否則為 count（int）——
兩者在 Python 中都要同時比對型別與數值，因為 `True == 1`。

Ticket 排序：依 `(main_numbers, special_numbers, ticket_id)` 遞增，
`ticket_id` 是最終 tie-break。同一 record 內不得有重複的號碼組合；
同一 artifact 內不得有重複的 `ticket_id`。號碼的 range／count／
uniqueness／overlap 一律從 evidence 自身的 `rule_parameters` 推導，不
硬編碼特定彩種。

## Lottery-rule Binding

已知彩種（目前僅 `BIG_LOTTO`，見 `lottolab.domain.lottery_rules`）：
embedded `rule_parameters` 必須與已提交的 domain rule contract 完全
相符，否則 `SEMANTIC_FAILURE`（`RULE_BINDING_MISMATCH`）。未知彩種
（`DAILY_539`、`POWER_LOTTO`）結構上仍可宣告，但沒有權威 rule
contract 可供比對時，永遠得到 `UNVERIFIED_PROVENANCE`，並阻擋
canonical gate。

## Metric 定義／版本／Hash（Contract Part 8）

Metric definition 文件宣告 `direction`、`unit`、`aggregation`、
`sample_unit`、`decimal_scale`（0–12）、`rounding_mode`（固定
`ROUND_HALF_EVEN`）、`formula_status`（`DEFINED` /
`RESERVED_UNAVAILABLE`）。Direction 只活在 definition 裡；policy 沒有
任何欄位可以覆寫它（嘗試加入方向覆寫欄位會被 `extra="forbid"` 當作
未知欄位拒絕）。

Metric result 宣告 `metric_id`/`metric_version`/`metric_definition_path`/
`metric_definition_sha256`，驗證器會解析路徑、雜湊比對，並讀入
definition 檢查 `metric_id`/`metric_version` 是否一致、`sample_size`
是否符合 `sample_unit`（`DRAWS` = record 數；`TICKETS` = 全部 ticket
數之和）、canonical decimal 字串是否符合 definition 宣告的
`decimal_scale`。

### Missing／Zero／Not-computable 三態

`metric_results` 陣列本身可以是空的（完全沒有宣告任何 metric）；有
宣告時，`value_status` 是 `VALUE_PRESENT`（此時必有 `value`、不得有
`reason_code`）或 `NOT_COMPUTABLE`（必有 `reason_code`、不得有
`value`）。三者結構上互斥且可獨立測試：缺席、`"0.0000"`、
`NOT_COMPUTABLE` 是三個不同的狀態，驗證器不會替任何一個「補值」。

### D3 Fail-closed

已提交的 D3 定義（`contracts/evidence/metric_definitions/d3.json`）
`formula_status = RESERVED_UNAVAILABLE`、`direction = DESCRIPTIVE_ONLY`、
無公式、無門檻。**任何**引用 `RESERVED_UNAVAILABLE` 定義的 metric
result，只要宣告 `VALUE_PRESENT`，一律是
`METRIC_DEFINITION_FAILURE`——這條規則以 `formula_status` 為準，不是
硬編碼 `metric_id == "D3"`，因此天然涵蓋任何未來新增的保留中 metric。
D3 在本任務結束後仍然是 reserved／unavailable；沒有任何 D3 證據可以
是 canonical。

## Definition-path Containment（Contract Part 8）

任何 `*_definition_path`（`feature_definition_path`、
`metric_definition_path`，以及未來的同名欄位）必須是 repo-relative 的
POSIX path：非絕對路徑、無反斜線／磁碟機前綴、無 `.`／`..` 片段、
symlink 解析後仍嚴格落在 repo root 內。違規者是 `SEMANTIC_FAILURE`，
**在任何檔案系統存取之前**就被拒絕。

驗證流程（`validator.resolve_definition_path`）刻意分成三個階段，前
兩階段是純字串比對、零檔案系統存取：

1. 詞法檢查（絕對路徑、反斜線、磁碟機前綴、`.`／`..` 片段）。
2. 依名稱比對的 containment 與受保護路徑檢查。
3. 只有通過前兩者，才對磁碟做 `resolve()`，並對 **resolve 後**的相對
   路徑重跑同一組 containment／受保護路徑檢查，以攔截「路徑字面上
   看起來合法、但實際是指向受保護位置的 symlink」。

`docs/ownerinit.md` 與 `.local/` 下任何路徑，無論輸入文件怎麼宣告，
一律不被開啟、stat、雜湊或讀取——第一階段的純字串比對就會擋下直接
命名的情形。（symlink 解析本身無可避免地需要對該 symlink 檔案自身
做 stat／readlink，這是「解析 symlink 之後仍需落在 repo root 內」這
條規則本身固有的限制，不代表讀取了受保護檔案的內容。）

`CANONICAL`／`DRAFT` evidence 只能引用 `contracts/evidence/` 下的
definition 檔；`SYNTHETIC_TEST_ONLY` evidence 額外可以引用
`tests/fixtures/evidence/`。

## Ranking Policy 與 Comparability（Contract Part 9）

Comparability 維度分兩類（見 `models.SHARED_ENVIRONMENT_DIMENSIONS`、
`models.PER_STRATEGY_IDENTITY_DIMENSIONS`，policy 文件的
`comparability_dimensions` 必須逐字複述這兩份固定清單，不能被單一
policy 重新定義）：

**Shared-environment 維度**（同一比較集合內必須完全相等）：彩種、
dataset hash、evaluation mode、evaluation protocol、evaluation
window、metric ID／版本／definition hash、sample unit、candidate-count
conformance（依 policy 的 `REQUIRE_EQUAL`／`ALLOW_ANY` 而定；
`REQUIRE_EQUAL` 比對的是「每個 record 各自的 candidate 數」逐一相等，
不只是總數相等）。

**Per-strategy identity 維度**（每個 artifact 都要宣告，但跨策略時**不**
要求相等，構成比較的 key）：strategy ID／版本、method ID／版本、
feature 版本、parameters hash（本任務中固定 `PINNED_HASH` 政策：每個
artifact 宣告的 parameters hash 對其策略身份具有拘束力）。

`comparability.check_comparability()` 的判定順序：

1. 只有 `REGISTERED_CANONICAL` 信任等級的證據可能合格——這條是無條件
   的，不理會 policy 自己宣告的 `required_evidence_trust` 說了什麼
   （沒有證據能單靠自我宣告變成 canonical，也沒有 policy 能單靠自我
   宣告放寬這道門檻）。
2. Evaluation mode／彩種必須落在 policy 允許的範圍內。
3. 必須存在符合 policy 主要 metric 身份的 result，且 sample size 達到
   `minimum_sample_size`。
4. Shared-environment 維度必須在整個候選集合中**完全一致**——只要有
   任何一組不一致，整個集合視為互不可比，全數標記
   `SHARED_ENVIRONMENT_MISMATCH`（刻意不做「多數決」，因為規格沒有
   定義任何 tie-break 規則）。
5. 同一 `(strategy_id, strategy_version)` 在一個比較集合中最多一筆合
   格 artifact；重複者全數標記 `DUPLICATE_STRATEGY_IDENTITY`（無論
   parameters hash 是否相同，也沒有「取最新一筆」的靜默選擇）。

Tie-breaker 清單必須以 `strategy_id`（字典序）結尾以保證全序。Checker
**只**回傳 eligibility 與 reason code；不排序、不產生任何排名輸出。

## 目前不存在的東西

- 沒有任何真實（非 synthetic）證據。
- 沒有任何已核准的 ranking policy。
- 沒有任何排名輸出。
- D3 仍是 reserved／unavailable。

## 未來任務需要做的事

1. 真實證據的 ingestion 與持久化（本任務刻意不碰）。
2. Owner 審查並將第一筆 canonical evidence／approved policy 寫入
   registry。
3. D3 公式與門檻的正式定義與核准。
4. 真正的 replay 執行與排名計算（本任務只驗證契約，不執行任何
   replay）。

## 這份契約不是什麼

不是生產就緒的系統，不是任何策略「有效」的證明，也不對外承諾任何
預測力。它只保證：**如果**未來有人要宣稱某個策略的評估結果是可信、
可比較、非事後諸葛的，資料形狀與雜湊必須先通過這裡的檢查。
