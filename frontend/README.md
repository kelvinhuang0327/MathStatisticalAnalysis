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

## ThreeUI Vue page pilot (dev-only)

`src/features/ui-page-pilot/` is a development-only preview generated from the
`threeui-vue-page` Skill (`kelvinhuang0327/skill`, path `/threeui-vue-page/SKILL.md`).
It activates only when both `import.meta.env.DEV` is true and the page is loaded
with `?uiPilot=threeui`; a production build cannot activate it. Run `npm run dev`
and open the dev server URL with that query string to preview it. See the Skill
repository for the adaptation recipe and ThreeUI source provenance — it is not
duplicated here.
