# API 契約

`openapi.json` 是前後端之間的機器可驗契約，由 FastAPI 匯出：

```bash
uv run python -c "import json; from lottolab.interfaces.api.app import create_app; \
print(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2))" > contracts/openapi.json
```

規則：

1. 任何修改 API 的 PR **必須重生** `openapi.json`——契約變更在 diff 中可見。
2. 前端型別由此生成；`frontend` 不得手寫 API payload 型別：

   ```bash
   cd frontend
   npm run api:generate
   npm run api:check
   ```

   生成器只依賴 Node.js，從 OpenAPI paths/components 產生
   `frontend/src/api/generated/openapi.d.ts`，`--check` 模式不寫檔。
3. 破壞性變更需在 PR 說明中明示並同步前端。
