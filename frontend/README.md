# LottoLab Strategy Catalog frontend

Vue 3 + TypeScript + Vite client for the read-only P600B Strategy Catalog.

```bash
npm ci
npm run api:check
npm run typecheck
npm test
npm run build
```

`src/api/generated/openapi.d.ts` is generated from `../contracts/openapi.json` by
`npm run api:generate`; frontend code must derive response types from that file.
During local development Vite proxies `/api` to the documented LottoLab API at
`http://127.0.0.1:8000`.
