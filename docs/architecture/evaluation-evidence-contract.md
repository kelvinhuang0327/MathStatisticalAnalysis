# 策略評估證據契約（Strategy Evaluation Evidence Contract）

狀態：DESIGN FOUNDATION — 契約與驗證層，非生產判斷依據 ｜ 建立：2026-07-17（P600F R2）｜ 更新：P600F R3

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

讀取 LCJ-1 時，語法不完整的 JSON 或非 UTF-8 bytes 一律轉成固定、有限的
`CanonicalizationError`（`$: input is not valid UTF-8 JSON`）。一般 validator／
CLI 路徑會把它回報為 sanitized validation failure，不輸出原始 bytes、完整
輸入、受保護的絕對路徑或 traceback。

## Hash 規則（Contract Part 2）

**Self-key-removed tree hashing**（hash 欄位是文件自身的一部分，計算時
排除自己）：

- `artifact_content_sha256`：evidence artifact 扣除 `artifact_content_sha256`
  本身之後的 LCJ-1 bytes。
- `record_sha256`：單筆 per-draw record 扣除 `record_sha256` 之後的 bytes。
- `dataset_sha256`：dataset snapshot 扣除 `dataset_sha256` 之後的 bytes。
- `rule_parameters_sha256`：`rule_parameters`／`rule_binding` 物件扣除
  自身欄位之後的 bytes（此欄位本身就內嵌在該物件中）。

Evidence validation 只要收到 dataset snapshot，就會在同一份 report 內重新執行
dataset 的 intrinsic validation：重算 `dataset_sha256` 與 dataset
`rule_binding.rule_parameters_sha256`，並保留 draw sequence、日期、ID 與號碼規則的
語意檢查。Dataset 內部 finding／hash-check pointer 一律加上
`/dataset_snapshot` 前綴；因此 evidence reference 與 dataset 宣告即使填入同一個
假 hash，也無法繞過 snapshot bytes 的獨立重算。Dataset 自身 hash 不符會讓
`structurally_valid = false` 並阻擋 canonical gate。

**Sibling hash**（hash 欄位在文件中，但描述的是「另一個」子物件，該子
物件不含自己的 hash 欄位）：

- `parameters_sha256`：`parameters`（策略自訂超參數 dict）的 LCJ-1
  bytes，`parameters` 本身不含 `parameters_sha256`。

**Referenced-file hash**（已提交檔案的原始 bytes，含結尾 LF）：

- `feature_definition_sha256`、`metric_definition_sha256`：對應
  `*_definition_path` 指向檔案的 SHA-256。
- `source_file_sha256`（`LOCAL_COMMITTED_FILE`）：對指定、可達的 Git commit
  中指定 path 的 blob 原始 bytes 計算 SHA-256；不讀取目前 working tree 的檔案
  內容。
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
synthetic、供給的 dataset snapshot 自身有效、dataset provenance 與 canonical
用途相容、`artifact_content_sha256` 出現在已提交的 canonical registry 中、
structural／semantic 驗證通過、artifact／dataset／rule／definition／local-source
所有必要 hash 皆 `VERIFIED_MATCH`、無 `AUTHORITY_FAILURE`，且沒有阻擋
canonical gate 的未驗證來源。Registry membership 只是必要條件，不能覆寫
synthetic／external provenance、Git 證明缺席、source hash mismatch 或 dataset
self-hash mismatch。

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
one-shot 的共用 cutoff）仍**不**證明 producer process 實際上從未存取
未來資料；`METADATA_CHECKED_ONLY` 專指這種本地無法觀察的 producer 行為。
但只要有供給 dataset snapshot，validator 能直接觀察到的 DrawRef
矛盾就不是此限制：ID／sequence／date 對不上 snapshot 是 fail-closed 的
`CAUSAL_VIOLATION`，不得繼續視為乾淨的 EX_ANTE。這是刻意的、有限度的
證明——避免給出超出本契約能力範圍的保證，也是防止「事後調參」
（hindsight tuning）偽裝成預測的第一道欄杆，而非唯一欄杆。

## Dataset 與 Outcome Provenance（Contract Part 4）

Dataset provenance 有三種，採 fail-closed trust matrix：

| Dataset provenance | 本地證明與 evidence 相容性 | Canonical 結果 |
| --- | --- | --- |
| `SYNTHETIC` | Dataset ID 必須以 `SYNTHETIC_` 開頭；只可搭配 `SYNTHETIC_TEST_ONLY` evidence。 | 合法 synthetic evidence 維持 `SYNTHETIC` trust，永不通過 canonical gate。搭配 `DRAFT`／`CANONICAL` 會得到 `AUTHORITY_FAILURE`（`SYNTHETIC_DATASET_REQUIRES_SYNTHETIC_EVIDENCE`）。 |
| `EXTERNAL_DECLARED` | 本 foundation 不做網路或外部來源查詢；固定回報 `UNVERIFIED_PROVENANCE`（`DATASET_EXTERNAL_DECLARED_UNVERIFIED`）。 | 若無其他結構缺陷，`structurally_valid` 可以是 true，但 canonical gate 永遠為 false。 |
| `LOCAL_COMMITTED_FILE` | path／Git OID／raw-file SHA-256 三者必備；依下列 Git proof 驗證。 | 只有完整 proof 為 match 時，provenance component 才能支援 canonical gate；缺席或 mismatch 一律 fail closed。 |

### `LOCAL_COMMITTED_FILE` 的精確 Git proof

在讀取任何 blob bytes 之前，`source_definition_path` 必須通過既有的 lexical、
protected-path、status-based allowed-root 與 symlink containment 規則。接著 validator
只對呼叫者供給的 repository 執行以下本地、唯讀證明：

1. repository top level 必須可解析，且就是供給的 `repo_root`；
2. `source_git_oid` 的 exact object type 必須是 commit；
3. 該 commit 必須是目前 `HEAD` 的 ancestor；
4. `source_git_oid:source_definition_path` 必須存在且 object type 是 blob；
5. 以 `git cat-file blob` 從 object database 讀取該 historical blob 的 exact bytes；
6. blob bytes 的 SHA-256 必須等於 `source_file_sha256`，並在
   `/dataset_snapshot/source_provenance/source_file_sha256` 產生 hash check。

Match 為 `VERIFIED_MATCH`。Repository、commit、ancestry、historical path 或 blob
bytes 無法取得時，source hash 為 `NOT_VERIFIABLE_INPUT_ABSENT` 並回報
`UNVERIFIED_PROVENANCE`；raw-byte hash 不同時為 `VERIFIED_MISMATCH` 加
`HASH_MISMATCH`（`DATASET_SOURCE_FILE_HASH_MISMATCH`）。目前 working tree 即使在
該 commit 之後被修改，也不會取代 historical blob。相同 path 在 commit A 是 bytes A、
後代 `HEAD` B 已改成 bytes B 時，proof 仍固定讀取內部形成的 `A:path`，不會改讀 working
tree、`HEAD:path` 或最新版本。

Git boundary 使用 exact argv allowlist，而非只看 subcommand 名稱：只接受
`rev-parse --show-toplevel`、`rev-parse --git-common-dir`、對 40 碼小寫 OID 或內部驗證
`OID:path` 執行的 `cat-file -t`、對同一內部 blob spec 執行的 `cat-file blob`，以及
`merge-base --is-ancestor <40-hex-oid> HEAD`。額外／重排參數、任意 ref、任意
`rev-parse` option、`--filters`、`--textconv`、`--batch` 與 `--batch-command` 都在啟動
subprocess 前被拒絕；raw input 不會成為 Git option。所有命令使用 argument array、
`shell=False`、`stdin=DEVNULL`、bounded timeout，停用 lazy fetch、replace objects、terminal
prompt 與 optional locks。

每次 Git subprocess 都會移除所有名稱以 `GIT_TRACE` 開頭的 inherited variable，避免 trace
destination 建立或 append 檔案；`GIT_GRAFT_FILE` 固定設為 `os.devnull`，因此 repository-local
`info/grafts` 不參與 ancestry proof。Inherited `GIT_ALTERNATE_OBJECT_DIRECTORIES` 會被明確移除；
可能把 Git 指向其他 repository／object database 的其餘 environment variables 也會先移除。

在任何 repository top-level、commit、ancestry 或 blob query 前，validator 以唯一允許的
`rev-parse --git-common-dir` 找到 shared Git metadata。輸出必須是 bounded、單行且 UTF-8 strict；
relative path 一律相對於供 `git -C` 使用的 `repo_root` 解析。空白、control character、decode／
resolution failure 都 fail closed，且不把 absolute common-directory path 暴露於 finding。解析後的
common Git directory 是後續 object metadata inspection 的唯一 anchor；合法 linked worktree 的
common directory 可以位於 linked working tree 外，不會因此被拒絕。

Validator 先以 `O_DIRECTORY`、`O_NOFOLLOW`、`O_CLOEXEC` 及 nonblocking protection 開啟 common
directory，再只用 parent directory descriptor 依序開啟固定名稱 `objects` 與 `info`。它不對
`objects`、`objects/info` 或 final metadata name 呼叫 `resolve()`，也不透過一般 `Path.open()`
走訪中間元件。任一中間元件不存在、是 symlink、不是 directory、不可讀或在 stat／open 間被
替換，都視為 unsafe；目標平台缺少 no-follow 或 directory-fd primitive 時同樣 fail closed。

`alternates` 與 `http-alternates` 只相對於已錨定的 `info` descriptor 檢查。唯一安全狀態是 final
file 不存在，或它在 no-follow stat、no-follow/nonblocking open、`fstat()` 與 final no-follow stat
四個 stage 都是同一個 exact zero-byte regular file。比較欄位包含 type／mode、device、inode、
size、nanosecond mtime 與 ctime。任何 nonzero file 都 unsafe；單一 space、tab、LF、CRLF 或 mixed
whitespace 也不例外，validator 不做 whitespace normalization，也不需要 decode nonzero content。
Symlink、directory、FIFO、socket／其他 special type、unreadable file、open／stat failure 或任何
被觀察到的 metadata instability 都回報
`DATASET_SOURCE_ALTERNATE_OBJECT_DATABASE_UNSAFE`；source hash 是
`NOT_VERIFIABLE_INPUT_ABSENT`，canonical gate 為 false，且不可由 registry 注入覆寫。Finding 不
包含 raw metadata path、content、OS exception 或 traceback。

Common、`objects` 與 `info` descriptors 在完整 Git object proof 期間保持開啟。Validator 在 proof
正前與正後，分別以 parent-relative no-follow stat 及 descriptor `fstat()` 重查 directory type、
device 與 inode；任何可觀察到的 replacement 都 fail closed。這是 before／after observation 的
有限保證，不宣稱能偵測完全發生在兩次 observation 之間、且不留下可見 metadata 差異的 concurrent
change。

驗證不執行 checkout、switch、reset、index／ref／config mutation、fetch 或任何網路操作，也不
修改 HEAD、index、working tree、refs、config、graft 或 alternate configuration。

這個 proof 的能力邊界必須明確：它只證明「指定的 exact reachable commit 中，
指定 path 的 raw bytes 具有宣告的 SHA-256」；**尚未**證明任意 source-file
內容如何被 normalization／ingestion 成 dataset snapshot。Source-to-snapshot
derivation 與 authoritative ingestion 是未來的獨立任務，不可把 Git blob proof
誤稱為 ingestion proof。

本基礎任務中，target 的實際開獎結果只能來自**同一份**供給的 dataset
snapshot；evidence 明確區分「策略在 cutoff 當下能看到的資料」與「後續
用於評分的實際結果」。

供給 snapshot 時，每筆 record 的 `target` 與 `cutoff` 都必須以 `draw_id`
解析到 snapshot，且宣告的 `draw_sequence`、`draw_date` 必須逐項相等；
不存在的 cutoff ID 或任一可觀察矛盾都會阻擋 structural／canonical gate。
artifact 層級的 `maximum_data_cutoff` 與（若存在）`one_shot_cutoff` 也做
相同 reconciliation。`dataset_reference.first_draw`／`last_draw` 除了 ID 與
sequence，日期也必須吻合 snapshot 的首末 draw。

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
`metric_definition_sha256`，驗證器會解析路徑、雜湊比對，並讀入 definition
檢查 `metric_id`/`metric_version`、`sample_unit` 與 `aggregation` 是否逐字一致。
`sample_unit` 不同回報 `METRIC_SAMPLE_UNIT_MISMATCH`；`aggregation` 不同回報
`METRIC_AGGREGATION_MISMATCH`。

`sample_size` 的唯一 source of truth 是 **metric definition 的** `sample_unit`，
不是 result 自行宣告的 unit：`DRAWS` = record 數；`TICKETS` = 全部 ticket 數之
和。即使 result 與 definition 的 unit 已不一致，sample-size 重算仍會執行，
所以錯誤 unit 不能略過或規避 `SAMPLE_SIZE_MISMATCH`。Metric value 仍維持
`DECLARED_NOT_RECOMPUTED`；validator 不計算、不推導、不補上任何 metric value。

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
不含 NUL、U+0001–U+001F 或 DEL（U+007F），且 symlink 解析後仍嚴格落在 repo root
內。違規者是 `SEMANTIC_FAILURE`，
**在任何檔案系統存取之前**就被拒絕。

驗證流程（`validator.resolve_definition_path`）刻意分成三個階段，前
兩階段是純字串比對、零檔案系統存取：

1. 詞法檢查（絕對路徑、反斜線、磁碟機前綴、`.`／`..` 片段）。
2. 依名稱比對的 containment 與受保護路徑檢查。
3. 只有通過前兩者，才對磁碟做 `resolve()`，並對 **resolve 後**的相對
   路徑重跑同一組 containment／受保護路徑檢查，以攔截「路徑字面上
   看起來合法、但實際是指向受保護位置的 symlink」。

Repository 或 candidate path 的 `resolve()` 若遇到 `ValueError`、`RuntimeError` 或相關
`OSError`（包含 symlink loop），會轉成單一 `DEFINITION_PATH_RESOLUTION_FAILED` finding，訊息
固定為 `definition path could not be resolved safely`。Finding 不包含 raw input、絕對路徑、
protected pathname、OS detail 或 traceback；LOCAL_COMMITTED_FILE 在此狀態不執行任何 Git
query，source hash 固定為 `NOT_VERIFIABLE_INPUT_ABSENT`，canonical gate 固定失敗。

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
- 沒有 source-to-snapshot ingestion／normalization proof，也沒有 evidence
  ingestion 或 persistence。

## 未來任務需要做的事

1. Source-to-snapshot normalization contract、真實證據的 ingestion 與持久化
   （本任務刻意不碰）。
2. Owner 審查並將第一筆 canonical evidence／approved policy 寫入
   registry。
3. D3 公式與門檻的正式定義與核准。
4. 真正的 replay 執行與排名計算（本任務只驗證契約，不執行任何
   replay）。

## 這份契約不是什麼

不是生產就緒的系統，不是任何策略「有效」的證明，也不對外承諾任何
預測力。它只保證：**如果**未來有人要宣稱某個策略的評估結果是可信、
可比較、非事後諸葛的，資料形狀與雜湊必須先通過這裡的檢查。
