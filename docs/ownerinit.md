可行，而且從這段對話呈現的狀況看，**現在已經到了值得重構的程度**。
真正拖慢新增功能的，不只是程式碼，而是三種負債疊在一起：
* **架構負債**：adapter、lifecycle metadata、generation registry、測試與evidence互相綁定。
* **測試負債**：大量blob hash、固定總數、歷史快照斷言，讓合法新增功能也會打破舊測試。
* **交付流程負債**：每個任務重複描述worktree、Git gate、cleanup、authorization、CI與DB限制，且高度依賴人工prompt。
所以我不建議只重構某個Python模組，而是做一次**「程式架構＋交付控制面」雙軌重構**。
# 建議結論
## 不建議
* 全系統推倒重寫。
* 一次搬完所有adapter與registry。
* 邊新增大量功能、邊全面更換架構。
* 再增加更多治理Markdown來解決治理複雜度。
## 建議
採用漸進式重構：
1. 先完成或明確暫停目前PR #690，取得乾淨基準。
2. 暫停新的P541衍生功能。
3. 先重構交付流程，再逐步重構registry與adapter架構。
4. 保留舊介面作為compatibility layer，逐個策略遷移。
5. 用可執行工具取代大部分長prompt與人工核對。
---
# 最值得先重構的四個區域
## 1. 把Lifecycle Catalog與Executable Registry完全分離
目前最大的概念混淆是：
* _ALL_ADAPTERS
* _REGISTRY
* _NON_EXECUTABLE_STUBS
* 實際adapter class
* lifecycle metadata
都集中在同一個registry模組中。
建議拆成：

lottery_api/models/strategy_catalog.py
lottery_api/models/executable_registry.py
lottery_api/models/adapters/
其中：
### strategy_catalog.py
只保存metadata：

StrategyDescriptor(
    strategy_id="...",
    lifecycle_status="OBSERVATION",
    adapter_path="...",
    executable=False,
)
不建立adapter instance，不import實作模組，不執行prediction。
### executable_registry.py
只包含真正可執行的ONLINE／ACTIVE strategies：

if descriptor.executable:
    load_adapter(descriptor.adapter_path)
如此一來：
* OBSERVATION可以存在catalog。
* 不需要建立假的_LifecycleStub。
* 不會誤進generation registry。
* lifecycle publication與adapter implementation不再互相衝突。
* get_adapter()與metadata lookup不再共用同一資料結構。
---
## 2. 讓每個Adapter自己提供Metadata
現在同一份策略資訊可能同時存在於：
* adapter class
* registry stub
* P541D design JSON
* tests
* PR body
* hard-coded expected sets
這會產生大量重複與hash更新。
建議每個adapter module只保留一個source of truth：

STRATEGY_DESCRIPTOR = StrategyDescriptor(
    strategy_id="biglotto_zone_split_3bet_bet1",
    strategy_name="大樂透 Zone Split 3注（Replay Bet 1）",
    version="v0.1",
    lottery_types=("BIG_LOTTO",),
    min_history=1,
    lifecycle_status="OBSERVATION",
    executable=False,
)
Catalog只讀取descriptor，或透過一份簡單manifest收集。
測試改驗證：
* ID唯一。
* OBSERVATION不在executable registry。
* ONLINE必須有adapter。
* Non-executable策略不可被generation API載入。
而不是重複寫名字、版本、status與hash。
---
## 3. 淘汰固定總數與大面積Blob Pin測試
目前歷史測試中出現：

assert len(_ALL_ADAPTERS) == 18
assert OBSERVATION_IDS == {"h6_gate_mk20_ew85"}
這些測試本質上是在阻止合理擴充。
應改成invariant-based tests：

assert strategy_ids_are_unique()
assert executable_ids <= catalog_ids
assert observation_ids.isdisjoint(executable_ids)
assert all_online_entries_have_loadable_adapters()
Blob／SHA pin只保留於真正需要不可變source binding的地方，例如：
* 研究artifact。
* 再現性基準。
* 外部source identity。
* 法規或methodology證據。
一般registry與test source不應靠SHA pin維持正確性。
---
## 4. 用工具取代長Prompt治理
目前每個任務都在重複：
* neutral cwd
* .ai context load
* branch／worktree gate
* head／base確認
* CI確認
* test commands
* merge verification
* cleanup
* quarantine
* branch deletion
這些應做成可執行的單一工具，例如：

tools/taskctl.py
建議介面：

taskctl preflight task.yaml
taskctl verify task.yaml
taskctl merge task.yaml
taskctl cleanup task.yaml
taskctl report task.yaml
每個任務只需要一份短manifest：

task_id: P541F_R2
base: 08e0d6...
head: 915cf6...
pr: 690
worktree: /Users/.../P541F-R2-...
branch: codex/p541f-...
allowed_files:
  - lottery_api/models/replay_strategy_registry.py
  - tests/test_p541d_r2_biglotto_selected_adapters.py
  - tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py
tests:
  - tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py
db_access: forbidden
merge_method: merge
cleanup_after_merge: true
工具自己完成：
* Git state。
* SHA。
* changed-file scope。
* worktree clean。
* branch ancestor。
* PR state。
* CI state。
* safe cleanup。
* JSON handoff report。
Agent只負責：
* 寫程式。
* 分析測試失敗。
* 做semantic review。
* 回報工具無法判斷的問題。
這會大量減少prompt長度與agent誤解。
---
# 建議的重構階段
## Phase A：先重構交付控制面
先不要改prediction algorithms。
建立：
* task manifest schema。
* taskctl preflight。
* taskctl verify。
* taskctl cleanup。
* 統一JSON evidence輸出。
這一階段效益最大、風險最低。
## Phase B：拆分Catalog與Executable Registry
保留現有公開函式：

list_strategies()
get_adapter()
get_strategy_lifecycle_metadata()
但內部改由新catalog／registry提供。
舊呼叫端不需立即修改。
## Phase C：選兩個策略做Pilot
剛完成的Social Wisdom與Zone Split很適合作為pilot：
* 都已有獨立adapter。
* 都有嚴格測試。
* 都是OBSERVATION。
* 不需要DB。
* 不需要ONLINE execution。
先證明新catalog可以：
* 看見metadata。
* 保持non-executable。
* 不重複registry stub。
* 保持現有API輸出。
## Phase D：遷移其他策略
逐批遷移：
1. OBSERVATION
2. REJECTED／RETIRED
3. ONLINE adapters
最後才移除：
* _LifecycleStub
* _NON_EXECUTABLE_STUBS
* 大量固定總數測試
* 重複metadata constants
---
# 重構成功的驗收標準
我建議用這些可量化指標判斷重構是否有效：
| 指標                           | 目標                           |
| ---------------------------- | ---------------------------- |
| 新增一個OBSERVATION strategy     | 不需修改中央registry Python清單      |
| Task prompt                  | 只描述業務scope，Git治理由工具執行        |
| Metadata source              | 每個strategy只有一份               |
| Historical exact-count tests | 歸零                           |
| 手動SHA pin                    | 只保留真正evidence contract       |
| Merge cleanup                | 一條標準命令可完成                    |
| Worktree遺留                   | 工具自動偵測並報告                    |
| Review                       | Semantic review與機械gate分離     |
| Authorization                | 一個明確task manifest對應一個Owner決策 |
| External memory write        | 預設禁止，除非任務明確授權                |
---
# 主要風險
重構可行，但要防止三件事：
### 1. 不要同時改演算法
重構期間只搬介面與metadata，不變更prediction semantics。否則無法判斷差異來自架構或演算法。
### 2. 不要一次移除舊Registry
先建compatibility adapter：

legacy_list_strategies() -> new_catalog.list()
等所有現有tests與consumer遷移後，再移除舊實作。
### 3. 不要把重構變成新的治理專案
重構的核心產出應是：
* 可執行程式。
* compatibility tests。
* migration tests。
* 短manifest。
不是新增十幾份roadmap、policy與handoff文件。
---
# 我對目前優先級的建議
**先完成PR #690的兩個missing review checks，讓目前工作停在乾淨且可決策的狀態。**
接著下一個主線不要直接做P541G，改成：

P600A_REFACTOR_STRATEGY_CATALOG_AND_EXECUTABLE_REGISTRY_DESIGN_NO_DB_WRITE
但P600A不應只是寫設計報告。它應在一個PR內完成最小可執行pilot：
* 新增strategy_catalog.py
* 新增executable_registry.py或compatibility facade
* 遷移Social與Zone兩個metadata records
* 保持現有public APIs相容
* 不改ONLINE registry行為
* 不寫DB
* focused tests
* draft PR
也就是**implementation-first refactor pilot**，不是大型RFC。
整體而言，這次重構不只是可行，而是很可能比繼續新增P541系列功能更能提高後續速度。真正應被重構的是「每新增一個策略就要同步修改多份metadata、hash、舊測試與長prompt」這個交付模式，而不是預測方法本身。
     # CTO 結論
**需要調整，但不是推翻你的方向。**
我會把整體決策定義為：
> **REFACTOR_APPROVED_WITH_BASELINE_AND_VERTICAL_SLICE_GATES**
> 批准漸進式重構，但必須先建立完整且可驗證的系統基線，再以「一個完整功能垂直切片」開始遷移，而不是直接從幾個 registry 檔案展開。
你提出的核心方向是正確的：
* 不全面重寫。
* 保留舊介面作為過渡層。
* 以主要功能為單位逐步遷移。
* 將 catalog、executable registry、adapter、metadata 分離。
* 用 invariant tests 取代固定總數與無意義的 hash pin。
* 用工具減少重複 Git／worktree／PR prompt。
但目前方案仍偏向「策略 registry 重構」，尚不足以支撐你後面補充的「完整前後端新架構、所有現有功能盤點、文件歷史統一管理」。
你提供的 CTO Technical Review 模板也已明確要求：修改前必須做 Phase 0 實際狀態確認，並以 live repo、code、tests、handoff、artifacts 為依據。因此，在尚未掃描 canonical repo 前，不能把目前對話中的模組名稱當成完整系統功能清單。
---
# 一、原方案應保留與應調整的部分
| 原方案                                     | CTO 判斷   | 調整方式                                                  |
| --------------------------------------- | -------- | ----------------------------------------------------- |
| 漸進式重構                                   | 保留       | 採舊系統與新模組暫時並存，逐功能切換                                    |
| Catalog／Executable Registry 分離          | 保留       | 視為策略子系統的第一個案例，不是整體架構本身                                |
| 每個 Adapter 一份 metadata source           | 保留       | Descriptor 必須成為唯一來源                                   |
| 淘汰固定總數測試                                | 保留       | 改為 invariant、contract、characterization tests          |
| 先做完整 taskctl                          | 調整       | 初期只做 preflight、verify、report，暫不自動 merge／cleanup |
| P600A 直接做 Registry implementation pilot | 調整       | 拆成 P600A 系統盤點與架構基線、P600B 完整垂直切片                       |
| 搬必要功能到新架構                               | 保留，但要改定義 | 不是搬檔案，而是以完整 capability 為單位遷移                          |
| 列出目前所有功能                                | 必須新增     | 列的是所有業務、使用者與維運能力，不是每個 Python function                 |
| 文件統一管理                                  | 必須新增     | 建立唯一文件入口、Capability Catalog、ADR 與 migration ledger    |
| 暫停新 P541 功能                             | 原則同意     | 暫停新衍生功能；既有修復、審查、landing 不應因此停止                        |
---
# 二、最大的調整：不要用「搬檔案」思考重構
目前真正需要遷移的單位不應是：
* 某個 registry.py
* 某個 route.py
* 某個 HTML
* 某個 adapter class
而應該是完整功能，例如：

策略目錄與生命週期顯示
    ├── 前端頁面／操作
    ├── API request／response
    ├── Application use case
    ├── Strategy Catalog
    ├── 權限與 executable policy
    ├── Tests
    └── 文件與 migration record
每次遷移一個完整 capability，才不會發生：
* 後端搬了，前端仍依賴舊 payload。
* registry 搬了，tests 仍 pin 舊常數。
* 文件更新了，但 scheduler 或 CLI 還在走舊路徑。
* 新舊模組各保留一份 business logic。
* 舊路徑永遠無法移除。
**重構成功的衡量標準不是檔案看起來整齊，而是依賴方向、資料流與功能責任變得可驗證。**
---
# 三、建議採用的目標架構
## 1. 先採「模組化單體」，不要立即拆微服務或建立第二個 repo
目前最安全的方式是：
* 保持同一個 canonical repo。
* 保持同一個主要部署單位。
* 在現有 repo 中建立清楚的新模組邊界。
* 舊 API／函式透過 compatibility facade 呼叫新 use case。
* 功能逐一切換完成後，才移除舊實作。
不要一開始就建立：
* 新後端 repo。
* 新前端 repo。
* 多個微服務。
* 新資料庫。
* 新 scheduler 平台。
否則會同時增加部署、資料同步、版本管理與雙系統維護問題。
## 2. 建議的邏輯架構

┌──────────────────────────────────────────────┐
│ Frontend                                     │
│ feature pages / components / API client      │
└──────────────────────┬───────────────────────┘
                       │ Versioned API Contract
┌──────────────────────▼───────────────────────┐
│ Interfaces                                   │
│ API routes / CLI / input validation / DTO    │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│ Application                                  │
│ Use cases / orchestration / ports            │
│ ListStrategies, Generate, Replay, Evaluate   │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│ Domain                                       │
│ Draws / Strategies / Generation / Replay     │
│ Evaluation / Lifecycle policies              │
└──────────────────────┬───────────────────────┘
                       │ Ports
┌──────────────────────▼───────────────────────┐
│ Infrastructure                               │
│ DB repositories / scheduler / files /        │
│ artifact storage / external integrations     │
└──────────────────────────────────────────────┘
另外保留兩條隔離通道：

Research / Analysis
    可依賴穩定的 domain/application contracts
    production runtime 不得反向 import research、outputs、artifacts
Compatibility
    舊公開函式與舊 API 暫時轉接到新 application use cases
    必須有退場條件，不可永久存在
## 3. 建議的目錄方向
實際名稱要在 live repo 盤點後確認，但邏輯結構應接近：

lottery_api/
  domain/
    draws/
    strategies/
    generation/
    replay/
    evaluation/
  application/
    use_cases/
    ports/
    dto/
  interfaces/
    api/
    cli/
  infrastructure/
    persistence/
    scheduler/
    artifact_store/
  strategies/
    descriptors.py
    catalog.py
    executable_registry.py
    adapters/
  compatibility/
frontend/
  src/
    app/
    features/
      strategy_catalog/
      generation/
      replay/
      evidence/
    shared/
      api/
      components/
      types/
contracts/
  api/
research/
  experiments/
  evaluators/
tests/
  unit/
  contract/
  integration/
  e2e/
  characterization/
docs/
tools/
這不是要求第一個 PR 就搬成上述結構，而是先確立依賴規則：
* Domain 不可 import Infrastructure。
* API route 不放核心商業邏輯。
* Frontend 不知道 adapter class、DB schema 或 registry 實作。
* Production runtime 不可 import analysis/、outputs/、artifacts/。
* Catalog 不 import adapter implementation。
* Executable Registry 可讀 Catalog，但 Catalog 不可反向依賴 Registry。
* Scheduler 只能呼叫 application use case，不可另寫一套策略邏輯。
---
# 四、Strategy Catalog 重構仍然適合當第一個 Pilot
你的 Catalog／Executable Registry 設計方向應保留，但第一個 pilot 應從「兩筆 metadata 搬遷」升級成：
> **Strategy Catalog / Lifecycle Listing 的 read-only full-stack vertical slice**
它應同時驗證：

Frontend 或現有 consumer
    ↓
現有 public API／compatibility facade
    ↓
ListStrategies application use case
    ↓
Strategy Catalog
    ↓
StrategyDescriptor
Social Wisdom 與 Zone Split 可以作為首批 descriptor，但 pilot 的驗收不只是在 Python registry 中看得到它們。
還應證明：
* OBSERVATION metadata 可被列出。
* OBSERVATION 不會進入 Executable Registry。
* Generation API 無法載入 non-executable strategy。
* 舊 list_strategies() 輸出仍相容。
* 舊 get_strategy_lifecycle_metadata() 仍相容。
* 舊 get_adapter() 對 ONLINE strategy 行為不變。
* 前端或 API payload 有 contract test。
* 不改 prediction semantics。
* 不接觸 DB write。
* 不改 scheduler。
這樣才真正驗證新架構能承接前端、後端、contract 與策略子系統，而不只是換了 registry 檔案位置。
---
# 五、「列出目前所有功能」應怎麼做
不建議列出每一個 Python function 或 class。那會變成無法維護的 symbol inventory。
應列出所有「可被使用、呼叫、排程或影響資料的 capability」。
至少涵蓋：
| 類型                | 需要盤點的內容                                     |
| ----------------- | ------------------------------------------- |
| 前端                | 頁面、入口、按鈕、篩選、報表、使用者流程                        |
| API               | Routes、request、response、錯誤格式、consumer       |
| Business use case | 查詢、生成、回放、評估、證據、生命週期                         |
| Strategy          | ID、descriptor、adapter、executable、status     |
| Data              | DB read、DB write、file read、artifact、cache   |
| Runtime           | scheduler、service、background job、PID、CLI    |
| Research          | evaluator、reproduction、evidence generation  |
| Operations        | scripts、startup、shutdown、cleanup、deployment |
| Tests             | unit、contract、integration、snapshot、hash pin |
| Documentation     | 對應功能的 canonical doc 與歷史決策                   |
建議使用 machine-readable catalog：

capability_id: strategy.catalog.list
name: Strategy Catalog Listing
domain: strategies
entrypoints:
  ui: []
  api: []
  cli: []
  jobs: []
current_implementation:
  frontend_paths: []
  backend_paths: []
  registry_paths: []
  test_paths: []
data_and_side_effects:
  db_read: false
  db_write: false
  filesystem_write: false
  scheduler_trigger: false
  external_call: false
contracts:
  public_functions: []
  api_payloads: []
status:
  lifecycle: ACTIVE
  production_readiness: UNKNOWN
  test_coverage: PARTIAL
migration:
  disposition: MIGRATE_FIRST
  target_module: lottery_api.strategies.catalog
  compatibility_required: true
  legacy_retirement_condition: null
evidence:
  verified_commit: null
  unknowns: []
每一項功能必須被分類成：

MIGRATE_FIRST
MIGRATE_LATER
KEEP_LEGACY_TEMPORARILY
REPLACE
RETIRE
FREEZE_AS_RESEARCH
UNKNOWN_NEEDS_AUDIT
## Inventory 完整性的驗收方式
不是靠人工說「應該都列完了」，而是至少交叉比對：
* 所有 API route。
* 所有前端 router／navigation entry。
* 所有 CLI command。
* 所有 scheduler／job registration。
* 所有 strategy registry／adapter。
* 所有 DB access module。
* 所有 service startup script。
* 所有主要 evidence／report generator。
每個入口都必須：
1. 對應某個 capability；或
2. 明確標示 excluded／deprecated／unknown，並附理由。
---
# 六、文件統一管理的建議
目前文件問題不能只靠「全部移到 docs」解決。真正要建立的是 canonical ownership。
建議結構：

docs/
  README.md
  architecture/
    system.md
    data-runtime.md
  capabilities/
    catalog.yaml
    catalog.md
  decisions/
    ADR-0001-modular-monolith.md
    ADR-0002-strategy-catalog-separation.md
  migration/
    migration-ledger.yaml
    migration-plan.md
  operations/
    runbook.md
  archive/
    README.md
## 文件角色必須分開
| 位置                 | 角色                                    |
| ------------------ | ------------------------------------- |
| docs/            | 系統、功能、架構與維運的 canonical documentation  |
| .ai/             | Agent 執行限制、風險、current state，不是產品文件主來源 |
| 00-Plan/roadmap/ | 優先順序與 active task，不是永久歷史庫             |
| Handoff reports    | 對話交接資料，不是架構真相                         |
| Git history        | 實際變更歷史                                |
| ADR                | 為什麼做某項架構決策                            |
| Migration ledger   | 哪個 capability 已遷移、仍相容或已退役             |
catalog.yaml 應是功能清單的 source of truth，catalog.md 由工具產生，避免 YAML 與 Markdown 各維護一份。
每份 canonical 文件至少應記錄：

status: CURRENT | DRAFT | SUPERSEDED | ARCHIVED
owner:
last_verified_commit:
supersedes:
superseded_by:
related_capabilities:
舊文件初期不要大量刪除；先標示 SUPERSEDED 並連到新位置，確認沒有 consumer 後才移入 archive。
---
# 七、調整後的重構階段
## Gate 0：建立乾淨基準
在新重構開始前，先確認：
* 目前 active PR 是 merged、closed、held 或明確暫停。
* origin/main 的 exact commit。
* 目前 open PR 與 worktree。
* canonical DB、runtime、outputs 沒有被重構任務改動。
* 新 P541 衍生功能暫停。
* P0 bugfix／review／landing 可繼續完成。
這是一個狀態 gate，不應再擴張成大型治理任務。
## P600A：Current System Capability Inventory and Target Architecture Baseline
建議任務名稱：

P600A_CURRENT_SYSTEM_CAPABILITY_INVENTORY_AND_TARGET_ARCHITECTURE_BASELINE_NO_RUNTIME_CHANGE
單一 PR 只產出：

docs/architecture/system.md
docs/capabilities/catalog.yaml
docs/migration/migration-ledger.yaml
tools/validate_capability_catalog.py
tests/test_capability_catalog_completeness.py
限制：
* 不搬 production code。
* 不改 prediction algorithm。
* 不開啟或寫入 canonical DB。
* 不改 scheduler。
* 不建立新 repo。
* 不做全 repo 文件大搬家。
* 不重寫 roadmap。
驗收：
* 所有 externally reachable／operational entrypoint 已被 catalog。
* 所有 capability 有現況路徑、資料副作用與 migration disposition。
* Target architecture 有明確 dependency rules。
* Catalog validator 可偵測重複 ID、無對應 entrypoint、缺失 migration disposition。
* Unknown 可以存在，但必須被列出，不能被隱藏。
## P600B：Strategy Catalog Read-Only Vertical Slice Pilot
建議任務名稱：

P600B_STRATEGY_CATALOG_READONLY_VERTICAL_SLICE_COMPATIBILITY_PILOT
內容：
* 新增 StrategyDescriptor。
* 新增 Catalog。
* 新增 Executable Registry 或 compatibility facade。
* 遷移 Social Wisdom、Zone Split descriptor。
* 保持舊公開 API 相容。
* 若有前端策略列表，讓該功能經新 use case 取得資料。
* 加 characterization、contract、invariant tests。
* 不改 ONLINE execution semantics。
* 不寫 DB。
## P600C：最小交付控制工具
不要一開始就讓工具自動 merge 或刪除 worktree。
第一版只做：

taskctl preflight task.yaml
taskctl verify task.yaml
taskctl report task.yaml
待多個 migration PR 證明穩定後，再增加：

taskctl merge task.yaml
taskctl cleanup task.yaml
Manifest 除了 allowed files，還應包含：

capability_ids:
side_effects:
public_contracts:
compatibility_required:
migration_phase:
db_policy:
runtime_policy:
authorization_token:
這樣 taskctl 是新架構的交付工具，而不是把舊有混亂流程自動化。
## P600D：遷移低風險 read-only capabilities
優先順序建議為：
1. Catalog／lifecycle query。
2. 一般資料查詢。
3. Evidence／report read model。
4. Replay result presentation。
5. 無副作用的 evaluation。
## P600E：遷移核心執行功能
後續再處理：
* Generation orchestration。
* Replay execution。
* Evaluation pipeline。
* ONLINE adapters。
* Artifact generation。
## P600F：最後處理高副作用區域
最後才碰：
* DB write。
* Scheduler。
* Service lifecycle。
* Runtime files。
* Deployment。
* Schema migration。
* Legacy removal。
---
# 八、需要新增的架構驗收標準
| 指標                    | 目標                                   |
| --------------------- | ------------------------------------ |
| 現有功能盤點                | 100% entrypoint 已映射或明確標示 Unknown     |
| Capability source     | 每項功能只有一個 catalog record              |
| Strategy metadata     | 每個 strategy 只有一份 descriptor          |
| Catalog 依賴            | 不 import adapter implementation      |
| Domain 邊界             | 不 import infrastructure／API／research |
| Frontend 資料來源         | 只透過 API contract                     |
| 舊 API                 | pilot 期間保持相容                         |
| 新增 OBSERVATION        | 不需修改中央 executable list               |
| Exact-count tests     | 除真正契約外歸零                             |
| Source blob hash pins | 除研究 evidence 外移除                     |
| Compatibility layer   | 每項都有退場條件                             |
| 文件                    | 每個主題只有一個 canonical path              |
| Migration PR          | 一次只遷移一個主要 capability                 |
| DB／runtime            | 早期 phases 完全不寫入                      |
| Research dependency   | production 不反向依賴 research            |
---
# 九、主要風險與修正
## 1. 新舊系統長期雙軌
最大的風險不是遷移失敗，而是新舊邏輯都留下來。
修正方式：
* 舊介面只能轉接，不能再新增 business logic。
* 每個 compatibility function 都要有 retirement condition。
* 新功能自 P600B 後不得再直接加入舊核心結構。
## 2. 架構設計過大
「精準架構」不等於預先畫完所有未來 class。
真正需要精準的是：
* 模組責任。
* 依賴方向。
* API／DTO contract。
* 資料與副作用邊界。
* 遷移與退場規則。
未來尚未存在的功能不應過度設計。
## 3. 功能盤點看似完整、實際漏掉背景入口
只看 route 與 adapter 不夠，必須同時掃：
* CLI。
* scheduler。
* startup scripts。
* background jobs。
* DB helpers。
* evidence generators。
* frontend hidden entrypoints。
## 4. 文件集中後又再次分裂
不可讓 .ai、roadmap、handoff、docs 各保存一份相同架構說明。
原則應是：

docs = canonical truth
.ai = execution constraints and references
roadmap = priority
handoff = temporary context
Git/ADR = history and rationale
---
# 最終 CTO 建議
你的「先把必要功能移植到新架構，再逐步新增功能」方向是正確的，但必須改成：

先盤點 capability
→ 確立邊界與 contract
→ 建 characterization baseline
→ 遷移一個完整 read-only 垂直功能
→ 建最小交付工具
→ 批次遷移其他功能
→ 最後處理 DB／scheduler／runtime
→ 移除 legacy
因此，不建議直接執行原本的 P600A_REFACTOR_STRATEGY_CATALOG...。
下一個主線應改為：

P600A_CURRENT_SYSTEM_CAPABILITY_INVENTORY_AND_TARGET_ARCHITECTURE_BASELINE_NO_RUNTIME_CHANGE
完成並驗收後，才進入：

P600B_STRATEGY_CATALOG_READONLY_VERTICAL_SLICE_COMPATIBILITY_PILOT
這樣才能同時解決你目前觀察到的三個根本問題：**程式檔案散落、功能責任不清、文件與歷史沒有單一依循來源**，而不會把重構變成另一場大規模搬檔案或治理文件工程。
    請針對上面兩個系統重構的分析做一個優化的總結，目標就是新建一個lottery系統，架構需要重新優化，然後從舊系統功能移植到新系統，針對程式使用的語言也請分析是否需要優化

我先快速掃一下現有 repo 的實際技術棧（語言、框架、規模），讓語言優化的分析有事實根據，再給整合總結。


Ran 6 commands

Saved 2 memories
收到，MEMORY.md 需要壓縮。我先讀取全文，確認細節都已存在對應主題檔後再壓縮索引。


Recalled 5 memories, saved 8 memories
MEMORY.md 已壓縮至 17,080 bytes（低於 17.1KB 上限），所有連結與狀態保留，細節都在對應主題檔中。以下是正題——兩份重構分析的整合總結。

新建 Lottery 系統：整合總結與語言分析
總結論
核准新建系統，但「新建」的正確做法是絞殺者式（strangler fig）遷移，不是砍掉重練。 新系統 = 同一 repo 內的全新架構套件 + 全新 TypeScript 前端 + 明確契約層；舊 lottery_api/ 立即凍結為 legacy（只修 bug 不加功能），逐個 capability 移植，每移完一個就標記退役，最終刪除舊核心。語言判定：後端留 Python（但需一次性鎖版升級與工具鏈現代化），前端是唯一真正該換語言的地方（vanilla JS → TypeScript）。

兩份分析的方向都對，且互補：第一份給了正確的「微觀設計」（catalog/registry 分離、descriptor 單一來源、invariant tests、taskctl），第二份給了正確的「宏觀順序」（先盤點、垂直切片、模組化單體、文件治理）。以下整合並針對「新建系統」目標做三處修正。

一、現況掃描事實（本次實測，語言分析的依據）
項目	現況	含義
Python 版本	.venv = 3.9.6（2025-10 已 EOL）	必須升級，但要 gated
後端框架	FastAPI 0.104.1 + pydantic 2.5.0 + uvicorn（2023 年 pin）	框架選對了，版本舊
依賴面	tensorflow、autogluon、prophet、catboost、xgboost、lightgbm 全裝	現役策略都是統計方法，重型 ML 是殭屍依賴
前端	根目錄單檔 index.html 5,976 行 vanilla JS + Chart.js，無 package.json、無 build system	不可維護，是換語言的主戰場
程式規模	repo 內 ~16,800 個 py 檔／650 萬行，但活核心只有約 1,400 檔（lottery_api 327、tools 617、tests 350、analysis+ai_lab ~130）	>90% 是歷史複本與生成樹，佐證「必須盤點而非搬檔案」
散置腳本	lottery_api/ 根目錄有 125 個 ad-hoc 分析/回測/預測腳本	職責邊界不存在
DB	canonical lottery_api/data/lottery_v2.db 之外還有 lottery_api/lottery.db、lottery_api/lottery_v2.db、data/lottery_v2.db 多份散落	P291/P351 的 DB path drift 前科在此有結構性根源
排程	launchd plist + APScheduler in-app 雙軌並存	需收斂為一
二、兩份分析的整合取捨
兩份都保留的：漸進遷移、catalog 與 executable registry 分離、每 strategy 一份 descriptor、invariant tests 取代 exact-count/blob-pin、taskctl 先做 preflight/verify/report、capability inventory 先行、垂直切片 pilot、docs canonical 治理、compatibility layer 必附退場條件。

針對「新建系統」目標的三處修正：

「新系統」落在同 repo 的新頂層套件，不是新 repo。 理由：canonical DB、evidence artifacts、350 個測試、可重現性契約都在這裡；新 repo 會讓新舊 parity 測試無法在同一環境執行，且本專案已有 canonical DB drift 且 writer 不明的前科——雙 repo 只會放大這類漂移。邊界切乾淨之後要抽 repo 只是搬家，現在抽是冒險。
舊系統的角色從「被重構對象」改為「凍結的參照實作」。 舊 lottery_api/ 不再重構、不再加功能，只當 characterization test 的 golden source；這比兩份分析中「邊改舊邊建新」更乾淨。
第一份分析的 registry 拆分降級為新系統內的第一個子設計（P600B 的內容），不是獨立任務；第二份的 P600A/P600B 順序維持為主幹。
三、新系統定義
LotteryNew/                        （同一 repo）
  lottery/                         ← 新系統後端（新套件，與舊 lottery_api 並存）
    domain/        draws / strategies / generation / replay / evaluation
    application/   use_cases / ports / dto
    interfaces/    api（FastAPI routers）/ cli
    infrastructure/persistence（唯一 DB path 強制點）/ scheduler / artifact_store
    strategies/    descriptors.py / catalog.py / executable_registry.py / adapters/
  frontend/                        ← 全新 TS + Vite 專案（取代 6k 行 index.html）
    src/features/  strategy_catalog / generation / replay / evidence
  contracts/       OpenAPI 匯出 + 生成的 TS types（機器驗證的前後端契約）
  compatibility/   舊公開函式 → 新 use case 轉接層（每條都有退場條件）
  lottery_api/     ← legacy，凍結：只修 bug、只當 golden 參照，逐步退役
依賴鐵律：domain 不 import infrastructure；catalog 不 import adapter 實作；production 不 import analysis/、outputs/、artifacts/；前端只透過 contracts；scheduler 只呼叫 application use case。

四、語言與技術棧分析（你追加的問題）
層	現況	判定	理由
後端語言	Python 3.9.6	留 Python，鎖版升級 3.12/3.13	見下方詳述
Web 框架	FastAPI 0.104	保留，升到當前版	選型正確；pydantic v2 全面 DTO 化後，OpenAPI 自動成為契約來源
前端	5,976 行單檔 vanilla JS	換成 TypeScript + Vite +（Vue 3 或 React）	唯一真正該換語言處；型別由 OpenAPI 生成（openapi-typescript），CTO 分析要的「contract test」變成編譯期保證
ML 依賴	tensorflow/autogluon/prophet/catboost…	不隨遷，移入 research optional extras	現役策略（ACB/MidFreq/Fourier/regime）只需 numpy/pandas/scipy；砍掉殭屍依賴可讓安裝與 CI 快一個量級
DB	SQLite 多份散落	留 SQLite，repository 層強制單一 canonical path + versioned migrations	單機單寫者，換 Postgres 無收益；path 收斂直接解掉 drift 的結構性根源
排程/運維	launchd + APScheduler + 50 個 bash	收斂為一（建議 launchd 觸發 typed CLI），bash → typer CLI（即 taskctl）	消滅雙軌與不可測腳本
品質工具	無統一	新套件強制 ruff + pyright/mypy strict + uv lock	語言內現代化，成本低收益大
為什麼後端不換 Go/Rust/Node：(1) 統計/科學生態（numpy/scipy/pandas/statsmodels）不可替代，全部 500+ 策略資產、評估器、350 個測試都是 Python，換語言等於把 L14–L107 所有已驗證結論重做一遍；(2) 這是單機、單用戶、SQLite 的系統，沒有吞吐瓶頸，換語言的效能收益為零；(3) 可重現性是硬約束——repo 已有教訓：Python 3.12 的 Neumaier 求和改變就會打破 digest。這也是「換語言」最被低估的代價：跨語言浮點與 RNG 行為差異會讓所有 golden digest 全滅。

因此 Python 升級本身必須是一個 gated 一次性步驟：新系統起點鎖定 3.12/3.13 + uv lockfile，在該版本下重生全部 golden digests 並固定，之後版本不再漂。效能熱點（replay/backtest 迴圈）先用 numpy/polars 向量化；只有 profiling 證明不足時才考慮 Rust/PyO3 擴充，不預先跨語言。

五、遷移路線（P600 系列，合併後）
階段	內容	過關條件
Gate 0	收掉/明確凍結在途工作（PR687 R9、PR688 repair、PR690 review）；pin main commit；凍結新 P541 衍生功能	每個 open PR 有明確 disposition
P600A 盤點	capability catalog（YAML）+ migration ledger + validator + 目標架構文件；不動 runtime	所有 API route/前端入口/CLI/scheduler/DB writer 100% 映射或標 UNKNOWN
P600B 骨架+垂直切片	建 lottery/ 新套件 + TS 前端 bootstrap + descriptor/catalog/executable_registry；Strategy Catalog read-only 全棧切片（Social Wisdom、Zone Split 為首批 descriptor）	舊 list_strategies() 等 API 輸出 byte-相容；OBSERVATION 進不了 executable registry；不碰 DB write
P600C taskctl 最小版	preflight/verify/report 三命令 + manifest schema；不做自動 merge/cleanup	一個 migration PR 全程用它跑過
P600D read-only 批次	查詢、evidence/report read model、replay 呈現	每 PR 一個 capability，characterization parity 通過
P600E 執行核心	generation、replay execution、evaluation、ONLINE adapters	預測語意零改動：固定 seed golden digest 完全一致
P600F 高副作用區	DB write/ingest hook、scheduler、部署；DB path 收斂至 repository 層	舊寫入路徑全部經由新系統
P600G 退役	依 ledger 退場條件刪 legacy、_LifecycleStub、exact-count tests；（屆時才評估抽 repo）	compatibility layer 歸零
六、驗收指標（精選）與五大風險
驗收：新增一個 OBSERVATION 策略不改任何中央清單；每策略一份 descriptor；exact-count tests 歸零（真契約除外）；前端只經 contracts 取數；golden digest 在鎖定版本下可重現；每條 compatibility 有退場條件；pip install 依賴數大幅下降（重型 ML 出核心）。

風險與對策：① 新舊雙軌永久化 → 舊層禁止新增 business logic + ledger 強制退場條件；② 遷移夾帶演算法改動 → goldens 把關，semantics 改動一律獨立任務；③ 盤點漏背景入口 → 本 repo 已知有 _refresh_after_insert 這類隱藏 hook，P600A 必須掃 CLI/launchd/hooks 而非只掃 routes；④ 可重現性斷裂 → Python/依賴升級集中在 P600B 起點一次完成並重生 goldens；⑤ 文件再分裂 → docs 為唯一 canonical，.ai/roadmap/handoff 只放執行約束與優先序。

下一步
依現行授權慣例，我不會自行啟動任何階段。建議順序：先處理在途的 PR687 R9 / PR688 repair / PR690 review 收尾 → Gate 0 → 授權 P600A_CURRENT_SYSTEM_CAPABILITY_INVENTORY_AND_TARGET_ARCHITECTURE_BASELINE_NO_RUNTIME_CHANGE。你若要，我可以把本總結落成正式的 P600 roadmap 文件（含 P600A 任務規格）供授權使用。

這部分會有規劃到我們之前紀錄需求流程的歷史軌跡嗎？wiki?ai-system?.ai?等等

我先查一下 repo 裡這些歷史軌跡實際存在哪些（.ai、ai-system、wiki、00-Plan 等），再回答它們在 P600 規劃中的位置。


Ran 7 commands
掃描完整了。先把這個補充存進 P600 記憶檔，再回答：


Saved a memory
直接回答：原總結有涵蓋這個面向，但只壓縮成兩處（P600A 盤點表的「Documentation」列、風險⑤「文件再分裂」），沒有具體點名 wiki、.ai、ai-system 的處置——這是缺口。 我剛實測了這些目錄的現況，以下補上明確規劃。

實測發現（比預期更需要處理）
來源	實際狀況
wiki/	在主 repo，README 自我宣告為「知識層唯一入口」（讀取順序：wiki → memory → docs → 根目錄 md 不讀）。但 README 宣告 13 頁 system/ 文件 + registry/hypotheses.jsonl，本 checkout 實際只存在 2 頁（randomness_final_verdict、replay_data_hygiene），registry 不存在——wiki 的索引與內容已經 drift，其餘頁面應該在 canonical-main worktree 裡（對應之前「governance 單一真相源」的政策）
.ai/	主 repo 沒有。它存在於各 worktree（如 LotteryNew.worktrees/P541B-R2-*/.ai），內含 ai-context / ai-memory / ai-report / ai-tasks / ai-wiki 五個子目錄——這是 personal-ai-flow 的 per-worktree 執行包，每個 Worker 任務一份
ai-system/	在 WorkSpace 層級、LotteryNew repo 之外（~/Kelvin-WorkSpace/ai-system/，含 prompts / rules / shared-memory，非 git repo），是跨專案共用的 agent 流程系統
需求史本體	00-Plan/roadmap/（active_task、CEO-Decision、CTO-Analysis、agent_bootstrap 模板）+ 00-Plan/old/（9 個日期快照）+ docs/ 20+ 篇歷史報告 + outputs/research/ 347 個 evidence 檔
處置原則與各來源規劃
原則只有一條，延續你 CLAUDE.md 的 Full Traceability / Fail but Record：歷史軌跡是 append-only 證據，不搬移、不改寫、不刪除；新系統只建「反向索引」，不重寫歷史。

來源	P600 處置
wiki/	保留為治理/方法論 canonical。P600A 新增一項交付：wiki 完整性稽核（宣告頁 vs 實存頁逐一比對），缺頁從 canonical worktree 促升回主 repo，促升不了的標 MISSING 並記錄最後所在
00-Plan/roadmap/ + old/	這就是你的「需求流程歷史軌跡」本體。原樣保留；roadmap 繼續當優先序層。capability catalog 每筆加 provenance 欄位：來源任務 ID（P2xx/P3xx/P5xx）、規格檔路徑、相關 wiki 頁、evidence 檔、PR 編號——讓每個被移植的功能都能反查「當初為什麼這樣做」
.ai/（worktree 內）	定位為執行約束層，不是需求真相來源。歷史 .ai 內容隨各 worktree 留存不促升；P600C 的 taskctl manifest 正是要取代 .ai 長 prompt 的角色，新任務不再手工複製這五個子目錄
ai-system/（repo 外）	在 P600 範圍外、不動它。但 P600A 的 inventory 必須登記跨 repo 依賴：哪些流程由 ai-system 的 prompts/rules 驅動、觸及本 repo 哪些入口——否則盤點會漏掉一整類背景入口（風險③的實例）
docs/ + outputs/research/ + rejected/	Evidence 層，不搬不改，舊報告補 status: SUPERSEDED/ARCHIVED 標頭即可，由 provenance 指向
對前一版總結的一個修正
CTO 分析提議「docs/ 為 canonical 文件入口」，但它不知道 repo 已存在 wiki/ 且明文宣告自己是唯一入口。兩個入口並立正是風險⑤「文件再分裂」的自我實現。 所以 P600A 要出一份 ADR 二選一定案：建議維持 wiki/README 為路由入口，新增的 architecture / capabilities / migration-ledger 文件掛進 wiki 的路由表，而不是另立門戶。

總結：需求歷史軌跡在調整後的 P600A 中不只是「被涵蓋」，而是變成三個具體交付物——capability provenance 欄位、wiki 完整性稽核、ai-system 跨 repo 依賴登記。這些已補進 P600 記憶檔，屆時寫 P600A 任務規格時會直接帶入。

所以p600會整合在一個地方嗎？而不是像現在散落各地

會——但要分清楚「整合」的是什麼。P600 做的是單一入口 + 單一索引，不是把所有東西物理搬進同一個資料夾。這兩者的差別正是成敗關鍵：把 347 個 research evidence、9 個需求快照、20 篇歷史報告搬家，只會斷掉 git 歷史和可追溯性，什麼都沒賺到。所以整合分四類處理：

1. 變成「只有一個家」的（真正合併）

知識入口：只剩一個——wiki/README 路由表。新的 architecture、capability catalog、migration ledger 全部掛在這條路由下，ADR 定案後不再有第二個入口。
功能清單：capabilities/catalog.yaml 是唯一一份「系統有哪些功能」的答案，每筆帶 provenance 反查歷史。
DB path：新系統只有 repository 層一個 canonical path，現在散落的多份 .db 收斂。
策略 metadata：每個策略只剩一份 descriptor，不再同時存在於 adapter、registry stub、design JSON、tests、PR body 五個地方。
2. 原地保留、但被索引的（歷史軌跡）
00-Plan/old/ 快照、docs/ 歷史報告、outputs/research/、rejected/、repo memory/lessons.md——全部不動，由 catalog 的 provenance 欄位反向指到。你要找「當初為什麼這樣做」，從入口一條路查到原始檔，但原始檔不搬家。

3. 被取代後消失的（散落的根源）

各 worktree 的 .ai/ 五子目錄長 prompt → taskctl 的單檔 manifest 取代，新任務不再複製整包。
根目錄 50+ 個 audit_.txt / REPORT.md、lottery_api/ 根目錄 125 個 ad-hoc 腳本 → P600A 盤點時逐一標 disposition（MIGRATE / RETIRE / FREEZE_AS_RESEARCH），之後不允許再往根目錄丟。
wiki「宣告 13 頁實存 2 頁」的 drift → 促升回主 repo，單一 checkout 就是完整知識庫，不用再去 canonical worktree 找。
4. 留在 repo 外、但被登記的
ai-system/（WorkSpace 層級）是跨專案共用的，物理上不併入 LotteryNew；但它驅動的流程、觸及的入口會登記在依賴清單裡——「在外面」和「沒人知道它在外面」是兩回事，P600 消滅的是後者。

所以完成後的動線是一條：wiki/README → capability catalog → 該功能的現況路徑 + provenance → 歷史任務卡與 evidence。現在的問題不是東西多，而是沒有任何一個地方能回答「全部有什麼、各在哪、為什麼」；P600A 建的就是那個地方。

'/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis'。 我希望把新系統放在這邊，另外主線收尾也在同步進行，這樣的話針對新系統我們有可以先行處理的步驟嗎？

我先看一下目標路徑的現況，再回答哪些步驟可以先行。

Inspected target path, workspace, and available toolchain versions

Saved 2 memories
可以，而且相當多步驟完全不用等主線收尾。 你把新系統放在獨立 repo 這個決定我已記錄（取代我原先「同 repo」的建議）；它帶來三條必要調整，先講清楚，然後是可先行的步驟。

獨立 repo 之後的三條軌道紀律
LotteryNew 對新系統軌道一律唯讀。主線收尾同時有其他 session 在寫，這個 repo 已有三次 live-writer collision 前科——新系統這條軌道永遠不寫 LotteryNew，一行都不寫。
Parity 驗證改為跨 repo harness：舊系統匯出 hash-pinned 的 golden/snapshot 檔案，新 repo 的 characterization tests 只讀匯出物，不直接 import 舊程式（舊 repo 有已知的 import 副作用）。
Inventory 要 pin commit：掃描 LotteryNew 時記下當時的 commit hash，主線收尾全部 merge 後再做一次 refresh diff。P541 系列 PR 動的是 detector/registry，幾乎不動 API 入口面，所以 diff 成本很低。
可先行的步驟（依賴由淺到深）
批次 1 — 新 repo bootstrap（只寫新目錄，零依賴，隨時可做）
git init + uv 鎖定 Python 3.13.8 + ruff/pyright strict/pytest 分層設定；domain/application/interfaces/infrastructure/strategies 套件骨架 + 依賴方向的 invariant test；contracts/、docs/（入口路由 README + ADR-0001 落點決策 + ADR-0002 文件單一入口 + 空的 capability catalog schema 與 migration ledger）；frontend/ Vite+TS 骨架；.gitignore 把 data/ 排除在 git 外 + 快照匯入工具佔位；CI workflow 檔先放好（GitHub remote 之後再建）。做完第一個 commit，新系統就有「家」了，P600 計畫文件也直接放進去——之後任何 session 打開這個 repo 都能自舉，不依賴我們這段對話。

批次 2 — P600A 盤點（唯讀掃 LotteryNew，可與主線收尾並行）
產出寫進新 repo：capability catalog（含 provenance 欄位）、wiki 完整性稽核（宣告 13 頁 vs 實存 2 頁的缺頁清單）、ai-system 跨 repo 依賴登記、launchd/CLI/hook 等背景入口掃描。

批次 3 — 資料快照（等主線一個安靜點，一次性）
canonical DB 唯讀複製 + SHA256 pin，開獎歷史匯出成 parquet/CSV 供 characterization 用；快照檔不進 git，只 commit 它的 hash manifest。

必須等主線收尾的：golden digest 重生（要舊系統停在穩定 commit 上跑）、逐 capability cutover、LotteryNew 端的 retirement 標記。

批次 1 我隨時可以開始，先確認三件事：

是否現在就執行批次 1（在 MathStatisticalAnalysis 建立新系統骨架 + 第一個 commit）？

現在就做（推薦）

MathStatisticalAnalysis 這個 repo 的定位是？（影響套件結構與命名）

你有建議的專案名字嗎？

新前端用哪個框架？（都是 TypeScript + Vite）

Vue 3（推薦）

新系統骨架 bootstrap
Initialize uv package project with Python 3.13 in new repo
骨架初始化成功。接著裝依賴、建目錄樹：


Ran 2 commands, read 3 files, created 21 files
第三批：三類測試（invariant / 依賴方向 / API 契約）＋快照工具：


Created 17 files, ran 3 commands, edited 2 files
9 個測試全過、前端 build 成功。修掉唯一的 lint 錯誤（一行超長），然後跑 pyright strict：


Edited 4 files, ran 4 commands
CLI 正常了，只剩我在 docstring 混用了全形括號。修正：


Edited a file, ran a command
pyright 出現一個新錯誤（應該是剛加的 callback 被視為未使用）。確認一下：


Ran 4 commands, edited 2 files

Saved 2 memories
Suggested task
清理 ~/.gitignore_global 危險全域規則
批次 1 完成 — 新系統已誕生
QuantLab 骨架已在 /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis 建立完成，root commit 4fb85f1（62 檔、3,523 行），所有品質關卡全綠，LotteryNew 全程零寫入。

建了什麼
部分	內容
後端骨架	src/quantlab/ 五層（domain / strategies / application / interfaces / infrastructure），依賴方向由 AST 掃描測試強制，違反即紅燈
策略子系統	StrategyDescriptor 單一 metadata 來源（executable ⟺ ONLINE 為程式碼層不變式）；catalog 與 executable registry 分離，不存在 stub
測試	9 個全過，分三類：unit invariant（取代舊系統的 exact-count 斷言）、API contract、architecture 依賴規則
契約	contracts/openapi.json 已從 FastAPI 匯出——之後前端型別由此生成，不手寫
前端	Vue 3 + TypeScript + Vite 骨架，npm run build 通過
CLI	uv run quantlab info 可用（typer，未來 taskctl 的家）
文件	docs 單一入口路由、ADR-0001（獨立 repo 落點與三條紀律）、ADR-0002（文件單一入口）、ADR-0003（語言工具鏈＋可重現性條款）、capability catalog 種子、migration ledger、P600 計畫落地版
工具鏈	Python 3.13.8 鎖版 + uv.lock、ruff 全過、pyright strict 0 錯誤、CI workflow 已就位（等建 remote 後生效）
過程中的重要發現
你的 ~/.gitignore_global 第 25 行全域忽略所有 README.md——首次 commit 時六個 README 全被默默排除，我在新 repo 的 .gitignore 用負向規則蓋回後 amend 補齊。這個全域檔還有 settings.json、.gitattributes、.editorconfig 等看似其他專案殘留卻全域生效的規則，會影響你每一個 repo；我沒動你的全域設定，已開了一個獨立任務籤（畫面上的 chip），你點一下就能在確認後清理。

命名
以建議名 QuantLab 建檔（package quantlab），定位為多 domain 數理統計平台、lottery 是第一個 bounded context。備選 MathStat、NumberLab——若你想換，骨架階段一次 grep 改名即可（程序寫在 README 裡），說一聲我就改。

下一步（皆待你授權才動）
批次 2（P600A 盤點）：唯讀掃描 LotteryNew（pin commit hash）→ 填 capability catalog + provenance、wiki 完整性稽核、ai-system 依賴登記。可與主線收尾並行。
批次 3（資料快照）：等主線一個安靜點，canonical DB 唯讀匯出 + SHA-256 manifest。
若要建 GitHub remote 也告訴我 repo 名，我把 push 前置作業備好。

AUTHORIZE_P600AB_R1_LOTTOLAB_BASELINE_PUBLISH_INVENTORY_PILOT_SNAPSHOT_GOLDEN_AND_READONLY_CAPABILITY_CUTOVER

上午11:40

適用於 1h 16m 20s

owner_decision: AUTHORIZE_P600AB_R1_LOTTOLAB_BASELINE_PUBLISH_INVENTORY_PILOT_S…
1. Authorization and scope understood
The authorization record (line 1) was followed fail-closed: LottoLab writes/publication were authorized, while every LotteryNew source, worktree, DB, WAL, and SHM write was prohibited.

A canonical DB sidecar mutation triggered the mandatory Phase S stop.

2. Phase 0 actual state
LottoLab root: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis
Package: lottolab
Initial branch: clean main
Initial/baseline OID: 0b2e3d8e3f563d19395f1080e7a11e40ba2952a7
Root commit: 4fb85f148af37e9140ab91847d1928208749fdb6
git fsck: only one benign dangling pre-rename CLI blob; inspected with no secret.
GitHub authentication, public-repository access, baseline tests, and pre-publication data/secret scan passed.
Canonical LotteryNew was proven as /Users/kelvin/Kelvin-WorkSpace/LotteryNew, not the dirty linked /LotteryNew-main candidate.
Canonical local legacy HEAD: 3d6df001da3a0633ab91f164d722b595ca76d2e1
Pinned detached inspection OID: 520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f
3. Baseline remote publication
The unchanged baseline was pushed non-force to the public MathStatisticalAnalysis repository.

Local main: 0b2e3d8e3f563d19395f1080e7a11e40ba2952a7
origin/main: 0b2e3d8e3f563d19395f1080e7a11e40ba2952a7
Default branch: main
Remote README check: HTTP 200
Feature branch created from that exact OID:
codex/p600ab-r1-lottolab-strategy-catalog-pilot
The feature branch was not pushed after the Phase S stop.

4. P600A inventory results
P600A completed and was committed locally.

Surface	Total	Mapped	Explicit UNKNOWN
FastAPI routes	98	98	0
UI navigation	24	24	0
UI handlers	174	174	0
Frontend API literals/calls	118	118	0
CLI candidates	1,122	142	980
Scheduler/hooks	5	5	0
launchd jobs	1	1	0
DB readers	729	99	630
DB writers	72	20	52
All entrypoints	2,345	683	1,662
Capability count: 17
Ledger state: all 17 INVENTORIED
API distribution: 50 GET, 46 POST, 1 PUT, 1 DELETE
Runtime strategy registry: 40 descriptors—8 ONLINE, 16 REJECTED, 13 RETIRED, 3 OBSERVATION
Inventory digest: 6b6b283b625ca93ac84643682aba6454db82b0e045b71808db6016ef049b517c
Validator: CAPABILITY_CATALOG_VALIDATION_PASS capabilities=17 entrypoints=2345
Primary outputs:

catalog.yaml
legacy-entrypoints.yaml
migration-ledger.yaml
lotterynew-baseline.md
validator
catalog tests
5. Wiki and external ai-system audit
Committed wiki result:

PRESENT: 8
SUPERSEDED: 3
MISSING: 1 (wiki/README.md)
UNKNOWN_LOCATION: 0
The unmanaged ignored README from a dirty checkout was not trusted or copied.

The external audit recorded hashes and integration metadata only:

30 orchestrator/CTO method-path declarations are absent from pinned runtime code.
No external ai-system runtime import/application dependency was found.
External systems were not modified and prompt contents were not copied.
Evidence:

lotterynew-wiki-integrity.md
external-agent-dependencies.yaml
6. Canonical DB snapshot evidence
Canonical path was proven from the resolver, database/replay code, operational evidence, and runtime configuration:

/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db

A snapshot attempt used SQLite URI mode=ro, PRAGMA query_only=ON, and sqlite3.Connection.backup. The resulting ignored local file technically reported:

Snapshot ID: p600ab-r1-20260715T122730+0800
integrity_check: ok
Snapshot SHA-256: e8a56e9f4979d3fbe91951be1f9d1ae4820ea1dcd92be47ef61cacd296c4b439
Schema SHA-256: 4e67901d7f935452df44c62b1c239e4d82798af7f30397dc7ff9fb41a07617e1
Rows: draws 33,377; replay runs 10; prediction replays 95,452; prediction runs 188; items/results 1,134 each.
However, this snapshot is not accepted as compliant:

Source DB size/mtime remained 99,368,960 bytes / 2026-07-14T17:06:21+0800.
WAL stayed zero bytes with unchanged mtime, but its ctime advanced to 2026-07-15T12:27:43+0800.
SHM remained 32,768 bytes, but its mtime advanced from 2026-07-14T17:20:33+0800 to 2026-07-15T12:27:43+0800; ctime became 12:27:44.
No pre-read content hash exists, so an SHM content change cannot be excluded.
The attempted manifest incorrectly sampled sidecars after connection closure while labelling them “before.”
Therefore:

Committed manifest: none
Attempted manifest: p600a-canonical-db-snapshot-manifest.json, untracked and invalid as compliance evidence.
Snapshot DB and its local sidecars remain under ignored .local/; none are staged or tracked.
7. Legacy golden regeneration evidence
Before the mutation was detected, two scoped fixture runs reproduced byte-for-byte:

strategy_catalog.json: f78891865cc03d800ef1da1840150427d8e61e08aa06e1b8a7b16da9600ee9af
lifecycle_metadata.json: c22178bd41d005dff8d1bcd0b8b0c7c6d71414ac2dc1d5aac17d53bcd4567e33
Aggregate: 8ba8d43fe046ff2eb1b46fbcb71bc5d14a18208aada3473379729f17c47e76ec
Pin: 520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f
Source provenance: 915cf6b0d42ee85bc00fe5d1e171879c5652af50
Runtime: Python 3.13.8
Dependency lock: absent at pin
Requirements hash: 2046dd0aa9cc084352a2fb1a664e032fba23ac81f0b1e7d3f1d70ff9d1a1e130
Two-run reproducibility command result: PASS
P600B parity-test result: NOT RUN
These fixtures and manifest.json remain untracked and are not accepted as a completed Phase S commit.

8. P600B implementation summary
P600B was not started after the hard stop.

The queued scope remains:

biglotto_social_wisdom_anti_popularity
biglotto_zone_split_3bet_bet1
Both are BIG_LOTTO, v0.1, minimum history 1, OBSERVATION, and non-executable.

No endpoint, Pydantic DTO, OpenAPI regeneration, frontend catalog, generation guard, or CUTOVER_READY ledger update was implemented.

9. Tests, lint, typecheck, build, and CI
Phase	Exact command	Result	Key output
Baseline	uv sync --frozen	PASS	Locked environment synchronized
Baseline	uv run ruff check .	PASS	No findings
Baseline	uv run pyright	PASS	No errors
Baseline	uv run pytest -q	PASS	9 passed, 1 Starlette/httpx warning
Baseline	uv run lottolab info	PASS	lottolab=0.1.0 python=3.13.8 strategies=0
Baseline	cd frontend && npm ci	PASS	Lockfile install completed
Baseline	cd frontend && npm run build	PASS	TypeScript/Vite production build completed
P600A	PYTHONDONTWRITEBYTECODE=1 uv run python tools/build_legacy_entrypoints.py --legacy-root /tmp/lottolab-p600ab-r1-lotterynew.4Izmhi/repo --output docs/capabilities/legacy-entrypoints.yaml --check	PASS	Deterministic inventory verified
P600A	uv run python tools/validate_capability_catalog.py	PASS	17 capabilities, 2,345 entrypoints
P600A	uv run ruff check .	PASS	No findings
P600A	uv run pyright	PASS	No errors
P600A	uv run pytest -q	PASS	17 passed, 1 warning
Phase S	uv run python tools/create_readonly_snapshot.py --source /Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db --destination .local/snapshots/p600ab-r1-20260715T122730+0800/lottery_v2.db --manifest docs/audits/p600a-canonical-db-snapshot-manifest.json --snapshot-id p600ab-r1-20260715T122730+0800 --source-label '<canonical LotteryNew>/lottery_api/data/lottery_v2.db' --writer-observation NO_OPEN_FILE_HOLDER_OBSERVED_BY_LSOF_IMMEDIATELY_BEFORE_BACKUP	FAIL overall	Process printed technical PASS, but subsequent SHM/WAL metadata evidence failed the zero-write gate
Phase S	Three isolated fixture exporter invocations for run1, run2, and canonical manifest verification	PASS command	Byte-exact aggregate matched twice; artifacts not accepted as completed Phase S
P600B	Required backend, OpenAPI, frontend, and regression suite	NOT RUN	P600B never began
PR/CI	GitHub checks	NOT RUN	No PR
The repository has no frontend test script; npm run build includes vue-tsc -b. Post-P600B validation, git diff --check, and CI were not run.

10. Git commits, branch, PR, and merge state
Item	State/OID
Initial baseline	0b2e3d8e3f563d19395f1080e7a11e40ba2952a7
Local main	0b2e3d8e3f563d19395f1080e7a11e40ba2952a7
origin/main	0b2e3d8e3f563d19395f1080e7a11e40ba2952a7
Feature HEAD	355858078269a1c5ef532881b6bde1846895d344
P600A commit	355858078269a1c5ef532881b6bde1846895d344
Phase S commit	None
P600B commit	None
Remote feature ref	Absent
PR number/URL/state	None
Merge commit	None
Post-cutover record	None
Current status:

 M .gitignore
?? docs/audits/p600a-canonical-db-snapshot-manifest.json
?? tests/fixtures/legacy/p600b/lifecycle_metadata.json
?? tests/fixtures/legacy/p600b/manifest.json
?? tests/fixtures/legacy/p600b/strategy_catalog.json
?? tools/create_readonly_snapshot.py
?? tools/export_legacy_p600b_fixtures.py
No staged files exist. The publication workflow remained non-force, and draft-PR creation was withheld at the hard gate.

11. Production cutover or cutover blocker
Cutover was not reached.

Evidence	Result
Scope switched	None
Deployed revision	None
Previous revision	None
Rollback method	None
Health/API/frontend smoke	NOT RUN
DB-write check	FAIL
Infrastructure created	None
A separate audit also found no documented LottoLab deployment target, traffic switch, prior deployed revision, or rollback target. If P600B later became ready, that absence would require CUTOVER_READY_NOT_DEPLOYED; the program did not reach that state here.

12. LotteryNew zero-write proof
Overall zero-write proof: FAILED.

Legacy remote main at start: 520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f
Legacy remote main at end: same OID
Remote main moved: no
Detached clone: clean at the pin
Active legacy Git branches, refs, and tracked worktree content: not mutated
Current DB holders/processes: none observed
Canonical DB auxiliary files: metadata mutation observed as detailed above
No attempt was made to restore timestamps, checkpoint WAL, or retry; each would require additional legacy writes or authority.

13. Files changed
The P600A commit contains 13 files: the capability catalog/inventory, migration ledger, baseline/wiki/external audits, deterministic builder and validator, tests, documentation indices, and pytest configuration.

Current uncommitted Phase S work consists of:

.gitignore
Attempted snapshot manifest
Three scoped fixture files
create_readonly_snapshot.py
export_legacy_p600b_fixtures.py
Ignored local artifacts include the 99,368,960-byte snapshot, local snapshot sidecars, isolated fixture runs, and UV caches. No DB file is tracked.

14. Risks and explicit UNKNOWNs
SQLite WAL-mode mode=ro access can still update the shared-memory WAL index.
The attempted snapshot tool did not capture true pre/post sidecar state.
No pre-attempt sidecar hashes exist, so content-level impact cannot be excluded.
1,662 entrypoints remain explicitly UNKNOWN_NEEDS_AUDIT.
Legacy registry/test totals conflict: current 40 versus stale tests asserting 16 or 18.
The 40-entry runtime registry and 59-entry artifact catalog are distinct contracts.
Legacy dependencies have no reproducible lock or pinned Python version.
Thirty external orchestration declarations lack pinned runtime implementations.
No production deployment/traffic target is documented.
15. Required completion check
Question	Answer
Baseline pushed to remote main?	Yes
P600A complete?	Yes, locally committed and validated
Inventory validator passed?	Yes
Canonical DB path proven?	Yes
Consistent compliant read-only snapshot created?	No
Scoped goldens reproduced twice?	Yes technically, but uncommitted/unaccepted
P600B complete?	No
Backend tests passed?	Baseline/P600A yes; P600B NOT RUN
Frontend build passed?	Baseline yes; P600B NOT RUN
PR opened?	No
PR merged?	No
Capability deployed?	No
DB bytes or secrets committed?	No
Did LotteryNew receive any write?	Yes—unintended WAL/SHM metadata mutation
Single remaining blocker?	No authorized snapshot method currently guarantees zero mutation of the live WAL/SHM family
Next migration capability unlocked?	No
16. Final classification
P600A_COMPLETE_SNAPSHOT_OR_GOLDEN_BLOCKED

Resumption requires either an externally supplied immutable, transactionally consistent snapshot or separate authorization for a controlled quiesce/checkpoint/snapshot procedure. The live canonical DB must not be retried under the current authorization.

lotterynew-baseline.md
文件 · MD
lotterynew-wiki-integrity.md
文件 · MD
README.md
文件 · MD
再顯示 1 項

已編輯 15 個檔案
+2,458
-65
.gitignore
.gitignore
+3
-0
docs/README.md
docs/
README.md
+5
-1
docs/audits/lotterynew-baseline.md
docs/audits/
lotterynew-baseline.md
+92
-0

顯示另外 12 個檔案
下午12:56
AUTHORIZE_P600B_R2_LOTTOLAB_DB_FREE_STRATEGY_CATALOG_RESUME_PUBLISH_AND_DRAFT_PR

下午1:34

適用於 1h 20m 41s

owner_decision: AUTHORIZE_P600B_R2_LOTTOLAB_DB_FREE_STRATEGY_CATALOG_RESUME_PUB…
Completed. Draft PR #1 is open, clean, and CI-green.

Branch: codex/p600ab-r1-lottolab-strategy-catalog-pilot
Remote/HEAD: 3e883210625d0b3ae65bdb1edb3215c7123a3294
PR remains a draft; no merge, deployment, readiness transition, or traffic change.
Final classification: P600B_R2_DRAFT_PR_READY_NOT_CUTOVER_READY
Key evidence:

Main baseline preserved: 0b2e3d8e3f563d19395f1080e7a11e40ba2952a7
P600A preserved unchanged: 355858078269a1c5ef532881b6bde1846895d344
Fixture commit: a2e2d6cbac6053960ed7e826f78aa4e0718bf522
Implementation commit: 3e883210625d0b3ae65bdb1edb3215c7123a3294
Inventory remains 17 capabilities, 2,345 entrypoints, 1,662 explicit unknowns.
Phase-S disposition:

General .local/ quarantine protections retained.
Invalid snapshot manifest removed and replaced with the snapshot stop record.
Snapshot tool removed.
Exporter rewritten for static ast.parse/ast.literal_eval extraction.
Three fixtures regenerated twice without DB access.
During this R2 resume, the LotteryNew DB family was never opened or touched; no LotteryNew writes or mutations occurred.
Fixture hashes:

Catalog: f78891865cc03d800ef1da1840150427d8e61e08aa06e1b8a7b16da9600ee9af
Lifecycle: c22178bd41d005dff8d1bcd0b8b0c7c6d71414ac2dc1d5aac17d53bcd4567e33
Aggregate: 8ba8d43fe046ff2eb1b46fbcb71bc5d14a18208aada3473379729f17c47e76ec
Implementation includes the DB-free API router, catalog, Vue catalog page, generated OpenAPI types, runtime response validation, mounted frontend state tests, and machine-validated migration ledger.

Validation:

Ruff and Pyright passed.
Pytest: 37 passed; one known Starlette/httpx deprecation warning.
Capability validation passed: 17 / 2,345 / 1,662.
npm ci: 169 packages audited, zero vulnerabilities.
OpenAPI check, TypeScript check, 5 mounted frontend tests, and Vite build passed.
Browser smoke passed at desktop and 390px responsive width.
GitHub CI: backend passed; frontend passed.
Branch-wide secret/data scan and three independent reviews passed.
The implementation commit changed 30 files across CI/contracts/docs, frontend, backend/API, and validation. The complete PR contains 45 files including the preserved P600A inventory and fixture foundation. OpenAPI now exposes versioned GET /api/v1/strategies; contract SHA-256 is 82e412ce63fdddd46ae0049cd3d3cc82cfc9c153805f9eae3209a87a83d268e1.

p600ab-phase-s-snapshot-stop.md
文件 · MD
README.md
文件 · MD
README.md
文件 · MD
再顯示 4 項

已編輯 33 個檔案
+1,667
-753
.github/workflows/ci.yml
.github/workflows/
ci.yml
+3
-0
/tmp/p600ab-r2-pr-body.md
/tmp/
p600ab-r2-pr-body.md
+65
-0
contracts/README.md
contracts/
README.md
+10
-1

顯示另外 30 個檔案
下午2:55




環境

變更
+28,562
-383

本機

codex/p600ab-r1-lottolab-strategy-catalog-pilot

送交或推送

P600AB: inventory LotteryNew and implement DB-free strategy catalog pilot

檢查成功

子代理

已完成 5 項

來源

owner_decision: AUTHORIZE_P600B_R2_LOTTOLAB_DB_FREE_STRATEGY_CATALOG_RESUME_PUB…

owner_decision: AUTHORIZE_P600AB_R1_LOTTOLAB_BASELINE_PUBLISH_INVENTORY_PILOT_S…
GitHub

查看全部
收到 owner 授權：`AUTHORIZE_PR1_P600AB_FIXED_HEAD_ARCHITECTURE_GOAL_CONFORMANCE_REVIEW`，read-only 固定 head 架構審查。先揭露一個 independence caveat：本 session 是 LottoLab 骨架（`4fb85f1`／`0b2e3d8`）的作者，因此對「基線架構本身」我非完全獨立；但受審的 P600A/P600B 增量（`355858`→`3e88321`）由 Worker 撰寫，對 PR 增量我是獨立的。審查全程不執行測試、不改任何檔案與 PR 狀態。

**Phase 0 — 固定 head 與實際狀態驗證**：

# PR1_P600AB_FIXED_HEAD_ARCHITECTURE_GOAL_CONFORMANCE_REVIEW — Fable5 審查報告

> Independence caveat（已於審查前揭露）：本 session 是 LottoLab 骨架（`4fb85f1`／`0b2e3d8`）的作者，對基線架構非完全獨立；受審的 PR 增量（P600A/P600B，三個 commit）由 Codex Worker 撰寫，對增量獨立。全程唯讀，未執行任何測試（CI 結論以 GitHub API 驗證）。

## 1. Fixed-Head 驗證

| 項目 | 期望 | 實際 | 判定 |
|---|---|---|---|
| Repository | kelvinhuang0327/MathStatisticalAnalysis | 同（gh API） | ✅ |
| PR #1 狀態 | OPEN, draft | OPEN, `isDraft: true` | ✅ |
| Base | main @ `0b2e3d8e…` | 同 | ✅ |
| Head | `3e883210625d0b3ae65bdb1edb3215c7123a3294` | **完全一致**；本地 worktree clean 且 HEAD 相同（本地檔案可作 head 證據） | ✅ |
| Commit 序列 | `3558580`→`a2e2d6c`→`3e88321` | 同（P600A 盤點→DB-free fixtures→P600B 實作） | ✅ |
| 變更檔數 | 45 | 45（+27,606／−383；最大 blob 為 1.02MB 生成盤點檔） | ✅ |
| Mergeability | — | `mergeStateStatus: CLEAN` | ✅ |
| CI | backend/frontend | 兩者皆 `COMPLETED/SUCCESS`（run 29395511227） | ✅ |
| 契約/fixture hash | Worker 宣稱值 | openapi `82e412ce…`、fixtures `f78891…`/`c22178…`/aggregate `8ba8d4…` 逐一重算相符 | ✅ |

Fixed-head gate **通過**，無任何 mismatch，進入實質審查。

## 2. Executive Verdict

實作**符合**原核准的 LottoLab 架構目標：分層方向、catalog/registry 分離、OBSERVATION 不可執行、OpenAPI 單一契約、DB-free 請求路徑全部成立且有機器強制。21 項目標 19 項 MET、2 項 PARTIALLY_MET、0 項 NOT_MET；**無 BLOCKING、無 CORRECT_BEFORE_MERGE 級缺陷**。架構適足性（fitness）與生產就緒（readiness）要分開：這是一個健全的遷移地基，但 ledger 誠實地標示 NOT_CUTOVER_READY——無部署目標、無 traffic 路由、Phase-S 快照因 WAL/SHM metadata 突變而 STOP 並已解耦。三筆非阻斷債（中央 descriptor tuple、前端 runtime enum 重複、ledger pr 欄位）可留待 post-merge。裁決：**可進入固定 head 的 landing review**。

## 3. Architecture Trace（實際端到端資料流）

```text
frontend/src/features/strategy-catalog/StrategyCatalogPage.vue   （泛化渲染、load/empty/error/retry、AbortController）
  → frontend/src/api/strategies.ts::listStrategies                （型別自 generated paths 派生 + runtime type-guard，fail-closed 502）
    → frontend/src/api/generated/openapi.d.ts                     （由 scripts/generate-openapi-types.mjs 從 contracts/openapi.json 生成；--check 進 CI）
      → GET /api/v1/strategies（operationId: listStrategies）
        → src/lottolab/interfaces/api/strategy_catalog.py::create_strategy_catalog_router   （薄殼，無業務邏輯）
          → src/lottolab/application/use_cases/list_strategies.py::ListStrategies.execute   （未被繞過）
            → src/lottolab/application/dto.py::StrategyView.from_descriptor                 （唯一轉換點）
              → src/lottolab/strategies/catalog.py::StrategyCatalog.list                    （宣告序、確定性、文件化）
                → src/lottolab/domain/strategies.py::StrategyDescriptor                     （雙向不變式 executable⟺ONLINE）
```

無跳層、無儀式性空殼（use case 雖薄但承擔 DTO 邊界）；composition root 在 `app.py::create_app`。逆向依賴檢查：`tests/architecture/test_dependency_rules.py` 除原有分層規則外，新增 **transitive** import 走訪（請求路徑禁 `sqlite3` 與 `lottolab.infrastructure`）、catalog 禁 adapters/importlib、production 禁 `lottery_api`/`tests`/`tools` 前綴——我逐檔直讀確認與測試結論一致。

## 4. Original-Goal Scorecard

| # | 目標 | 判定 | 證據（檔:行） |
|---|---|---|---|
| 1 | 獨立 repo 邊界 | **MET** | production 無任何 legacy import（arch test + 直讀）；exporter 以外部 clone 路徑參數運作 |
| 2 | 絞殺式遷移紀律 | **MET** | 一次一 capability；ledger 其餘 16 筆 INVENTORIED |
| 3 | 模組化單體依賴方向 | **MET** | §3 trace；test_dependency_rules.py:34 |
| 4 | Domain 純淨 | **MET** | domain 僅 import stdlib＋自層；strategies.py:1-61 |
| 5 | Application use-case 邊界 | **MET** | router 綁 ListStrategies（strategy_catalog.py:21,29） |
| 6 | StrategyDescriptor 單一來源 | **MET** | DTO/fixture/測試皆派生；catalog.py:54 為唯一宣告點 |
| 7 | Catalog／ExecutableRegistry 分離 | **MET** | test_catalog_does_not_import_adapters（arch:83） |
| 8 | OBSERVATION 不可執行 | **MET** | domain 雙向不變式（strategies.py:50）＋registry raise＋前端對抗測試 |
| 9 | 無 lifecycle stub | **MET** | LottoLab 全樹無 stub 類；fixtures 僅為測試側 JSON |
| 10 | Pilot 無 DB 存取 | **MET** | transitive arch test＋contract 測試以 monkeypatch 使 `sqlite3.connect` 直接 AssertionError（test_api_strategies.py:57-61） |
| 11 | 不改預測語意 | **MET** | 零演算法程式碼被遷移 |
| 12 | OpenAPI 為 canonical 契約 | **MET** | committed==generated 等式測試（test_api_strategies.py:85-90）＋CI `api:check` |
| 13 | 生成 TS 型別實際被用 | **MET** | strategies.ts:1-5 型別自 `paths` 派生，無手寫 DTO interface |
| 14 | 前端不可執行呈現 | **MET** | 對抗 payload（executable:true）仍 "Metadata only"、零 button/零 a（strategy-catalog.test.ts:55-67） |
| 15 | DB-free 確定性 legacy fixtures | **MET** | 2-run byte-exact、exporter 自身 hash 綁進 manifest（manifest.json:99-102） |
| 16 | Production 不依賴 fixtures/LotteryNew | **MET** | arch test（:90-96）＋直讀 |
| 17 | Capability provenance | **MET** | 每 capability 8 欄 provenance＋descriptor provenance tuple（catalog.py:63-69） |
| 18 | Ledger 誠實 | **MET**（小缺口） | MIGRATING＋NOT_CUTOVER_READY 明示；`pr: null` 應補 1 |
| 19 | Invariant 式測試 | **MET** | 全樹零 exact-count；含 5 條負向路徑＋production 不變式 |
| 20 | 下一個 capability 的可重用 pattern | **PARTIALLY_MET** | pattern 完整可複製；但新增 OBSERVATION 仍需編輯中央 `_PRODUCTION_DESCRIPTORS` tuple（見 F-1） |
| 21 | 無 cutover 誇稱 | **MET** | 無部署宣稱；Worker 自我分類即 NOT_CUTOVER_READY |

**中央清單原始成功測試（規格點名，不隱藏）**：新增第三個 OBSERVATION 需要編輯 `catalog.py` 的中央 tuple——「不改中央 Python 清單」的字面目標未全達。但相比舊系統（registry＋stub＋exact-count＋hash＋多份 metadata 同步），現在是**單檔單點宣告、零測試修改、零 stub**，已滿足「minimum justified edits」的精神。判定為可接受的 pilot 階段限制（非結構性缺陷），附明確演進步驟（F-1）。

## 5. Substantive Findings

**BLOCKING：無。**
**CORRECT_BEFORE_MERGE：無。**

**NON_BLOCKING_DEBT（3）：**

- **F-1 中央 descriptor tuple**（catalog.py:54）。影響：目標 20 字面未全達；descriptor 數量成長後將重演 `_ALL_ADAPTERS` 模式。最小修正：**不是現在抽象化**（兩筆資料就建 discovery 機制屬過度設計）；在 docs/architecture/system.md 註記「P600E 首個 ONLINE adapter 遷移前，descriptor 改為 per-strategy module／manifest 聚合」，並在該階段執行。
- **F-2 前端 runtime enum 重複**（strategies.ts:8-15）。`LIFECYCLE_STATUSES`/`LOTTERY_TYPES` 為手寫字面 Set，與生成型別平行存在。後端未來新增 enum 值→契約與型別更新、CI 全綠，但 runtime guard 會把合法回應打成 502 錯誤狀態（fail-closed 方向安全，但是 drift 陷阱）。最小修正：以 `const LIFECYCLE_STATUSES = [...] satisfies readonly StrategyView['lifecycle_status'][]` 派生，讓 enum 漂移變成編譯錯誤。
- **F-3 Ledger `pr: null`**（migration-ledger.yaml:72）。MIGRATING 條目未回填 PR 編號（提交當時 PR 尚不存在，可理解）。最小修正：landing 後補 `pr: 1`。

**OPTIONAL（2）：** `/api/health` 未版本化（慣例上可接受）；1MB `legacy-entrypoints.yaml` 進 git 屬合理的 pinned 證據，但重生時 diff 噪音大，未來可評估壓縮或摘要＋hash。另記錄：batch-1 的未版本化 `/api/strategies` 已被移除、無相容 shim——當時無任何消費者，不構成破壞。

## 6. P600A Inventory 評估

**可用作遷移基線（read-only 階段）：是。** 17 個 capability 對 2,345 個入口的映射有完整性帳目：每個 kind 有 total/mapped/unknown，1,662 個 UNKNOWN 被顯性歸入 `lottery.legacy_cli.unknown` 等專屬 capability——**是誠實的顯性債，不是靜默遺漏**。生成模式 `STATIC_AST_AND_TEXT_ONLY_NO_IMPORT_NO_DB_OPEN`、排除清單明列（archive/artifacts/outputs/tests）。驗證器超出 schema 檢查、含語意交叉規則（DB writer 不得映射到未宣告 `data_writes` 的 capability），且 `test_capability_catalog.py` 用 mutation 方式驗證驗證器本身會抓錯（重複 id、缺 provenance、錯 commit、未映射入口）。

**False-confidence 風險**：`CAPABILITY_CATALOG_VALIDATION_PASS` 證明的是帳目一致性，**不是**分類語意正確性；71% unknown 率意味著「已盤點」≠「已理解」。噪音來源合理（CLI 1,122 候選中 980 unknown——與本 session 實測的 125 個 lottery_api 散置腳本＋617 個 tools 檔一致）。

**後續階段前的必要改善**：(a) **52 個 UNKNOWN DB writers 在 P600F 前必須全數 triage**——這是最高風險項；(b) CLI unknowns 批次 disposition（多數可 FREEZE_AS_RESEARCH/RETIRE）；(c) legacy 三套數字對帳（runtime registry 40 vs 舊測試 16/18 vs artifact catalog 59）需在 ONLINE adapter 遷移（P600E）前定案。這些均不阻斷本 PR。

## 7. Tests 與 Contract 評估

**已證明**：分層與 transitive DB-free（靜態）、`sqlite3.connect` 運行時攔截（動態）、OBSERVATION 不可執行（後端 raise＋前端對抗 payload＋零操作元素）、fixture 完整性（exporter hash 自綁、2-run byte-exact、aggregate 重算）、契約時效性（committed==generated 等式＋CI `api:check`＋`vue-tsc`）。36 個測試函式（parametrize 展開後 37 執行實例，與 CI 宣稱一致）；前端 5 個 mounted 測試涵蓋 loading/adversarial/empty/malformed/retry。

**未證明**：真實 uvicorn 行為與前後端整合（無 e2e；瀏覽器 smoke 是 Worker 手動證詞）、兩筆以外的 legacy parity、任何部署面。OpenAPI 治理健全：單一來源、生成器確定性（自製 mjs、無外部依賴、`--check` 不寫檔）、契約變更必然出現在 diff。

## 8. Scope 與複雜度評估

45 檔＝13（盤點）＋4（fixtures）＋30（實作），與「bootstrap 盤點＋一個垂直切片」相稱；體積大宗是 1MB pinned 盤點證據而非程式碼。**無過度工程**：沒有 premature discovery 機制、沒有大型 design system、application 層薄而正當。**無結構不足**：該有的機器強制都在。此 pattern 會**降低**下一個 capability 的成本：複製「descriptor→use case→router→契約重生→型別生成→feature page→invariant/contract/characterization 測試→ledger 條目」即可，且已有可執行的驗證器把關。

## 9. Merge Path Recommendation

**`PROCEED_TO_FIXED_HEAD_LANDING_REVIEW`**

理由：0 blocking、0 correct-before-merge；三筆 NON_BLOCKING_DEBT 皆有一行級修正且不影響地基安全；在固定 head 紀律下，為它們追加 commit 反而會使 head 位移、重啟審查循環，成本大於收益。debt 以 post-merge 微任務處理。

## 10. Required Corrections

**Mandatory（merge 前）：無。**
**Optional（post-merge 微任務，≤3）：**
1. ledger 補 `pr: 1`（F-3）。
2. `strategies.ts` enum Set 改為自生成型別派生（F-2）。
3. system.md 註記 descriptor per-strategy module 演進步驟，掛在 P600E 進入條件（F-1）。

## 11. Next Copyable Prompt（landing／readiness review）

```text
owner_decision: AUTHORIZE_PR1_P600AB_FIXED_HEAD_LANDING_REVIEW
task: PR1_P600AB_FIXED_HEAD_LANDING_REVIEW
mode: READ_ONLY_VERIFICATION_THEN_GATED_LANDING
repository: kelvinhuang0327/MathStatisticalAnalysis
local_candidate: /Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis
pr: 1
expected_base_oid: 0b2e3d8e3f563d19395f1080e7a11e40ba2952a7
expected_head_oid: 3e883210625d0b3ae65bdb1edb3215c7123a3294

phase_0_fixed_head_gate (read-only):
  - Re-verify PR #1 OPEN, draft, base/head OIDs exactly as pinned; STOP on any drift.
  - Re-verify CI conclusions at head (backend, frontend) are SUCCESS via API.
  - Verify mergeStateStatus is CLEAN and no new commits/reviews altered the head.
  - Verify architecture review verdict on record:
    PR1_P600AB_ARCHITECTURE_CONFORMS_WITH_NONBLOCKING_DEBT (0 blocking).

phase_1_landing (each step gated; do NOT proceed without the explicit token):
  - Await standalone owner token: MERGE_CONFIRMED_PR1.
  - Then: mark ready, merge with a merge commit (preserve the 3-commit sequence), no squash.
  - Post-merge verification: origin/main == merge commit; local main fast-forwarded;
    feature branch deleted local+remote; worktree clean.

phase_2_post_merge_followups (single micro-commit on main, separately authorized):
  - migration-ledger: set pr: 1 on lottery.strategy_catalog.list.
  - strategies.ts: derive enum sets from generated types (satisfies pattern).
  - docs/architecture/system.md: note per-strategy descriptor module step as a P600E entry condition.

not_authorized: deployment, traffic change, cutover-state transition, DB access,
LotteryNew writes, force-push, PR body rewrite beyond landing mechanics.
```

## 12. Required Completion Check

| 問題 | 答案 |
|---|---|
| 審查的是否為期望的確切 head？ | 是——`3e88321…`，gh API＋本地 clean worktree 雙重確認 |
| 是否檢視完整 patch？ | 是——45 檔全列；production/測試/契約/文件逐檔直讀，1MB 生成盤點抽樣＋帳目驗證 |
| 實作是否符合原架構？ | 是——19 MET／2 PARTIALLY_MET／0 NOT_MET |
| 有無 blocking 架構缺陷？ | 無 |
| 是否需要 corrective commit？ | 否 |
| PR #1 可否進 landing review？ | 可 |
| 最重要的殘餘風險？ | P600A 的 1,662 unknowns——尤其 **52 個 UNKNOWN DB writers** 必須在 P600F 前 triage 完畢（本 PR 範圍內無阻斷） |
| 是否變更任何檔案/ref/PR/DB/runtime/deployment？ | 否——全程唯讀（git/gh 讀取、檔案讀取、hash 重算）；另：審查記憶已寫入本人 memory 目錄（repo 外，非審查對象） |

## 13. Final Classification

**`PR1_P600AB_ARCHITECTURE_CONFORMS_WITH_NONBLOCKING_DEBT`**

附帶一個跨系統的交叉印證值得 owner 知道：Worker 的 wiki 稽核發現 `wiki/README.md` 在 pin 上**沒有任何 git 歷史**——這正是本 session 稍早發現的 `~/.gitignore_global` 全域忽略 `README.md` 規則造成的（LotteryNew 的 wiki 索引從未進過版控，只存在於 dirty checkout）。之前開的全域 gitignore 清理任務籤又多了一個真實受害案例。