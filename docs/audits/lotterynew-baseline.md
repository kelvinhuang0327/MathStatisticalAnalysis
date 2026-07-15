# LotteryNew pinned baseline audit

Status: P600A VERIFIED ｜ 2026-07-15 ｜ static inspection only

## Pin and repository identity

- Inventory and golden code pin: `520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f` (`origin/main` at task start; merge of PR #690).
- The project profile, roadmap bootstrap, wiki index, remote identity, and runtime paths designate the primary `LotteryNew` checkout as canonical.
- The reported `LotteryNew-main` candidate is only a linked worktree sharing the canonical repository object store. It was on an older dirty task branch, so it was not used as source evidence.
- The canonical active checkout was also dirty and on an older task branch. It received no writes and was not used for source inspection.
- All P600A source reads used a clean isolated detached clone at the exact pin. Legacy Python was not imported or executed and no database was opened.

## Static inventory method

`tools/build_legacy_entrypoints.py` parses Python AST and frontend text without importing legacy modules. Its committed manifest records every detected surface plus explicit scan exclusions. Deterministic regeneration uses:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python tools/build_legacy_entrypoints.py \
  --legacy-root <detached-pinned-clone> \
  --output docs/capabilities/legacy-entrypoints.yaml
```

The current manifest digest is `6b6b283b625ca93ac84643682aba6454db82b0e045b71808db6016ef049b517c`. Catalog validation is performed by `tools/validate_capability_catalog.py`.

## Measured surfaces

| Surface | Total | Mapped | Explicit UNKNOWN |
|---|---:|---:|---:|
| FastAPI routes | 98 | 98 | 0 |
| UI navigation sections | 24 | 24 | 0 |
| Frontend API literals | 53 | 53 | 0 |
| Frontend HTTP call sites | 65 | 65 | 0 |
| UI event handlers | 174 | 174 | 0 |
| Python/shell CLI candidates | 1,122 | 142 | 980 |
| APScheduler registrations | 3 | 3 | 0 |
| Runtime/ingest hooks | 2 | 2 | 0 |
| launchd jobs | 1 | 1 | 0 |
| Static DB-reader candidates | 729 | 99 | 630 |
| Static DB-writer candidates | 72 | 20 | 52 |

The API surface is 50 GET, 46 POST, one PUT, and one DELETE across nine mounted routers. Unknown CLI/DB candidates are retained in two `UNKNOWN_NEEDS_AUDIT` capabilities; the catalog does not infer that a command is safe from a filename such as `readonly` or `dryrun`.

## Strategy registries and conflicting universes

The runtime registry at the pin contains 40 descriptors: 8 ONLINE, 16 REJECTED, 13 RETIRED, and 3 OBSERVATION. A separate artifact-backed P24 catalog contains 59 records and is not the same contract. Older legacy tests still assert obsolete totals of 16 or 18; these are recorded as stale contradictions, not used as the P600B truth source.

The P600B pilot is derived from pinned registry source and the focused P541F_R2 test:

1. `biglotto_social_wisdom_anti_popularity`
2. `biglotto_zone_split_3bet_bet1`

Both are BIG_LOTTO, version `v0.1`, minimum history 1, OBSERVATION, and non-executable. Their source commit is `915cf6b0d42ee85bc00fe5d1e171879c5652af50`, merged by PR #690.

## Canonical database path proof

The code pin resolves the canonical database only as `<canonical LotteryNew>/lottery_api/data/lottery_v2.db`:

- `lottery_api/canonical_db_path.py` anchors it to the repository root and rejects relative or missing custom paths.
- `lottery_api/database.py` defaults to that resolver, but its constructor/first access can initialize and alter schema; it is forbidden for snapshot reads.
- `lottery_api/routes/replay.py` independently resolves the same path and demonstrates SQLite URI `mode=ro` plus `PRAGMA query_only=ON`.
- current P540B/P540C/P541A evidence records the same operational path.
- the runtime plist and startup script point to the primary canonical checkout, not the stale linked worktree.

Eight tracked database/backup decoys exist at other paths in the pinned Git tree. Filename matching is therefore not accepted as canonical-path proof. The live canonical database was not opened in Phase A.

## Runtime, hooks, and deployment

- `com.kelvin.lottery.dev.plist` declares a local legacy service only; its hard-coded path and KeepAlive/nohup behavior are stale risks.
- Three `add_job` registrations exist in `lottery_api/utils/scheduler.py` and `smart_scheduler.py`.
- FastAPI startup loads scheduler data. There is no corresponding shutdown hook.
- The ingest `_refresh_after_insert` hook currently calls `scheduler.load_data()`; older reports describing removed cascading hooks are stale.
- LottoLab has no documented deployment/traffic target, deploy command, reverse proxy, feature flag, prior deployed revision, or rollback revision. Source-level readiness cannot be called production cutover.

## Source identity evidence

| Pinned path | Git blob | SHA-256 |
|---|---|---|
| `lottery_api/app.py` | `76839dfca63a84cbfd8c0920d135b0c6c6aa4a7b` | `9e52105858e2dcbd2faaea6390469cbdba88450c1890e932d1197961b9656877` |
| `lottery_api/routes/replay.py` | `96d655fbc85a5ece647853665d5fd8c6f536470d` | `51855456a782a1d034b52e5ffef73baab52809027f33f444ca5b6d7bd684a0bc` |
| `lottery_api/models/replay_strategy_registry.py` | `380ac2942a7374bd7ccad940ec50b273757ae100` | `c6c0352868f93c27e68c230e14b1b1c8f8c6a4f2feb021574d2f7cc49170976e` |
| `lottery_api/models/replay_strategy_state_labels.py` | `58b900ff09ccd64a4d1ca100019664a858ef15b2` | `c5e428983e9574e9d6047ed9bd498d4187b7af09a4a3d1f2bb241bf549afc182` |
| `outputs/replay/p24_full_strategy_universe_inventory_20260521.json` | `4c7538b6b3322de67557c9181e62dd3093131a70` | `48204f9745137aeb0cd47520de94fb740b160e3e806268d23c952a5d7f3061da` |

## Explicit unknowns and boundaries

- The repository has no declared console-script manifest; main-guard publicness is not inferable, so 980 CLI candidates remain explicit UNKNOWN.
- Many nominal read-only/dry-run scripts use default SQLite connections; 682 DB candidates remain explicit UNKNOWN across reader/writer classifications.
- Strategy universes of 40, 59, and larger historical research inventories serve different contracts and must not be merged silently.
- The pinned dependency set is not reproducible: there is only a broadly/unpinned `lottery_api/requirements.txt`, with no lock file or pinned Python version.
- Generation, replay execution, evaluation, DB writers, ingestion, schedulers, launchd, and ONLINE adapters are outside the P600B cutover scope.

LotteryNew received zero writes during this audit. No active legacy branch, ref, worktree, output, runtime file, or database was modified.
