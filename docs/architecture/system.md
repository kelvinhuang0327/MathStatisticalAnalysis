# 系統架構

狀態：CURRENT ｜ 建立：2026-07-15（P600B 骨架）

## 分層

```text
Frontend (Vue3 + TS)
   │  versioned API contract（contracts/openapi.json → 生成 TS types）
Interfaces (FastAPI routes / CLI)          ← 薄殼、composition root
   │
Application (use cases / ports / DTO)
   │
Domain (draws / strategies / lifecycle)    ← 純模型，零外部依賴
   ▲
Infrastructure (persistence / snapshot / scheduler)  ← 實作 ports
```

## 依賴規則（由 tests/architecture 強制）

- `domain` 不 import quantlab 其他層。
- `strategies` 只 import `domain`；**catalog 不 import adapter 實作**。
- `application` 不 import `interfaces`／`infrastructure`（透過 ports 反轉）。
- `infrastructure` 不 import `interfaces`。
- production 程式不 import research／outputs／artifacts 類目錄（未來加入 research/ 時擴充規則）。

## 策略子系統核心不變式

1. 每個策略只有一份 `StrategyDescriptor`（metadata 唯一來源）。
2. `executable=True ⟺ lifecycle_status=ONLINE`，且必有 `adapter_path`。
3. OBSERVATION／REJECTED／RETIRED 永不進 ExecutableRegistry，**不存在 stub**。
4. 新增策略＝新增一筆 descriptor；不改中央清單、不改既有測試（invariant tests 取代 exact-count）。

## 與舊系統的關係

- LotteryNew 唯讀；資料經 hash-pinned snapshot 匯入（`tools/import_snapshot.py`）。
- Parity 由 characterization tests 對 golden 檔驗證，不跨 repo import。
- 可重現性條款見 ADR-0003。
