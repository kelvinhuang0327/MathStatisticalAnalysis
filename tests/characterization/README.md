# Characterization tests（批次 3 後啟用）

驗證「新系統輸出 == 舊系統輸出」的 parity 測試放這裡。

規則：

- 大型資料／DB golden 放入 `data/`（不進 git），manifest 進 `data/manifests/`。
- 小型、純文字、DB-free metadata fixture 可放入 `tests/fixtures/legacy/`，但必須固定 legacy commit、匯出器 hash、兩次重現 hash 與 no-DB extraction method。
- 測試只讀匯出物，**絕不 import 舊系統程式碼**（舊 repo 有已知的 import 副作用）。
- Golden 不一致＝遷移錯誤或有意變更；有意變更必須在 PR 中明示並重生 golden。
