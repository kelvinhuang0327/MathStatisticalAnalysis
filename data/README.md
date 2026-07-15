# data/

快照 payload 放這裡，**不進 git**（.gitignore 排除）。

- `data/manifests/`（進 git）：每份快照的 hash manifest（來源 repo、commit、每檔 SHA-256）。
- 使用前一律先驗證：`uv run python tools/import_snapshot.py verify data/manifests/<name>.yaml`
- 來源唯一：LotteryNew canonical DB／匯出檔；本 repo 永不寫回來源。
