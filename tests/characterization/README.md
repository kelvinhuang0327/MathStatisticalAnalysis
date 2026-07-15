# Characterization tests（批次 3 後啟用）

驗證「新系統輸出 == 舊系統輸出」的 parity 測試放這裡。

規則：

- Golden 檔由舊系統（LotteryNew）在**固定 commit** 上匯出，經 SHA-256 pin 後放入 `data/`（不進 git），manifest 進 `data/manifests/`。
- 測試只讀匯出物，**絕不 import 舊系統程式碼**（舊 repo 有已知的 import 副作用）。
- Golden 不一致＝遷移錯誤或有意變更；有意變更必須在 PR 中明示並重生 golden。
