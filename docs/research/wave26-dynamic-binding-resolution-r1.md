# Wave 26 dynamic binding resolution R1

## Scope and historical reference

This is a deterministic, DB-free supplemental source analysis. It preserves the original lineage result as historical evidence and follows only the four previously unresolved `wave26_authority` bindings through the canonical composition root.

- Original result: `docs/research/matrix-native-results/strategy-matrix-static-lineage-redundancy-map-r1-result.json`
- Original result SHA-256: `f2f7d1fd5e08083124aaeb43dfe889f96012f6020b9daafae49f6368f832bfad`
- Supplemental result SHA-256: `193b9301640e5561cb495903ce0d6710c47886b72b5f603542505a82f9218db3`
- Supplemental binding fingerprint SHA-256: `b97500043e23804151673bf07aa7787468a246007ae3cc420c2ea3a6f7748bde`
- Method: Python AST/static source declarations only; LottoLab modules are not imported
- Original lineage result rewritten: `NO`

## Four-row resolution

| Strategy ID | Descriptor locator | Registry adapter | Implementation callable | Injected authority | Factory/provider locator | Runtime data changes identity? | Structural source digest | Final classification |
|---|---|---|---|---|---|---|---|---|
| `legacy_biglotto__test_ces__78d17c530ab8` | `src/lottolab/strategies/catalog.py:815:StrategyDescriptor[legacy_biglotto__test_ces__78d17c530ab8]` | `lottolab.strategies.adapters.biglotto_wave8:BigLottoCesThreeAdapter` | `src/lottolab/application/legacy_source_native_portfolios_wave26.py:385:_ces_rows` | `Wave26PortfolioAuthority` | `src/lottolab/application/use_cases/generate_bet.py:563:_generate_wave26_portfolio` | `NO` | `1e28a4b57f88a0109fbca62fc40c1e9f35967ef6effae6b6de211c08178beeb6` | `RESOLVED_STATIC_IMPLEMENTATION` |
| `legacy_biglotto__test_dms__b63442289bd5` | `src/lottolab/strategies/catalog.py:836:StrategyDescriptor[legacy_biglotto__test_dms__b63442289bd5]` | `lottolab.strategies.adapters.biglotto_wave8:BigLottoDmsThreeAdapter` | `src/lottolab/application/legacy_source_native_portfolios_wave26.py:428:_dms_rows` | `Wave26PortfolioAuthority` | `src/lottolab/application/use_cases/generate_bet.py:563:_generate_wave26_portfolio` | `NO` | `e208ad41afb8cba2efd6d285928c173ab6b209a9db461e80dafa274a3e1c32f1` | `RESOLVED_STATIC_IMPLEMENTATION` |
| `legacy_biglotto__test_greedy_optimizer__82df7f878ece` | `src/lottolab/strategies/catalog.py:857:StrategyDescriptor[legacy_biglotto__test_greedy_optimizer__82df7f878ece]` | `lottolab.strategies.adapters.biglotto_wave8:BigLottoGreedyThreeAdapter` | `src/lottolab/application/legacy_source_native_portfolios_wave26.py:571:_greedy_rows` | `Wave26PortfolioAuthority` | `src/lottolab/application/use_cases/generate_bet.py:563:_generate_wave26_portfolio` | `NO` | `dd79e07ca29acb7757de688b1c43716ce3224ba2e6834e41e7eba9ea8a9365b0` | `RESOLVED_STATIC_IMPLEMENTATION` |
| `legacy_biglotto__test_mwsc__ba37643d6a3b` | `src/lottolab/strategies/catalog.py:878:StrategyDescriptor[legacy_biglotto__test_mwsc__ba37643d6a3b]` | `lottolab.strategies.adapters.biglotto_wave8:BigLottoMwscThreeAdapter` | `src/lottolab/application/legacy_source_native_portfolios_wave26.py:466:_mwsc_rows` | `Wave26PortfolioAuthority` | `src/lottolab/application/use_cases/generate_bet.py:563:_generate_wave26_portfolio` | `NO` | `51d3b444f45840125e3668b6d6a0b9eeb51db7b0391e506612b829f5d4842f3e` | `RESOLVED_STATIC_IMPLEMENTATION` |

## Source/provider lineage and exact reasons

### `legacy_biglotto__test_ces__78d17c530ab8`

`src/lottolab/strategies/catalog.py:815:StrategyDescriptor[legacy_biglotto__test_ces__78d17c530ab8]` → `src/lottolab/strategies/executable_registry.py:21:ExecutableRegistry.load_adapter` → `src/lottolab/strategies/adapters/biglotto_wave8.py:61:BigLottoCesThreeAdapter` → `src/lottolab/strategies/adapters/biglotto_wave8.py:46:_BigLottoWave8PortfolioAdapter.__init__` → `src/lottolab/strategies/adapters/biglotto_wave8.py:23:Wave26PortfolioAuthority` → `src/lottolab/application/use_cases/generate_bet.py:553:_instantiated_portfolio_adapter[wave26_authority]` → `src/lottolab/application/use_cases/generate_bet.py:563:_generate_wave26_portfolio` → `src/lottolab/application/legacy_source_native_portfolios_wave26.py:637:generate_legacy_source_native_wave26_portfolio` → `src/lottolab/application/legacy_source_native_portfolios_wave26.py:385:_ces_rows`

The descriptor names one concrete adapter class; its inherited constructor requires wave26_authority:Wave26PortfolioAuthority; the canonical instantiator injects the single named provider src/lottolab/application/use_cases/generate_bet.py:563:_generate_wave26_portfolio; the adapter's static legacy_method_id='tools/test_ces.py' selects src/lottolab/application/legacy_source_native_portfolios_wave26.py:385:_ces_rows. Runtime request/history contents affect computed tickets, not the selected class/provider/callable identity.

Supplemental binding fingerprint: `f46ad35a3e0d187dbff06c263695830f6d8218663d02637bb06204f59912af92`

### `legacy_biglotto__test_dms__b63442289bd5`

`src/lottolab/strategies/catalog.py:836:StrategyDescriptor[legacy_biglotto__test_dms__b63442289bd5]` → `src/lottolab/strategies/executable_registry.py:21:ExecutableRegistry.load_adapter` → `src/lottolab/strategies/adapters/biglotto_wave8.py:70:BigLottoDmsThreeAdapter` → `src/lottolab/strategies/adapters/biglotto_wave8.py:46:_BigLottoWave8PortfolioAdapter.__init__` → `src/lottolab/strategies/adapters/biglotto_wave8.py:23:Wave26PortfolioAuthority` → `src/lottolab/application/use_cases/generate_bet.py:553:_instantiated_portfolio_adapter[wave26_authority]` → `src/lottolab/application/use_cases/generate_bet.py:563:_generate_wave26_portfolio` → `src/lottolab/application/legacy_source_native_portfolios_wave26.py:637:generate_legacy_source_native_wave26_portfolio` → `src/lottolab/application/legacy_source_native_portfolios_wave26.py:428:_dms_rows`

The descriptor names one concrete adapter class; its inherited constructor requires wave26_authority:Wave26PortfolioAuthority; the canonical instantiator injects the single named provider src/lottolab/application/use_cases/generate_bet.py:563:_generate_wave26_portfolio; the adapter's static legacy_method_id='tools/test_dms.py' selects src/lottolab/application/legacy_source_native_portfolios_wave26.py:428:_dms_rows. Runtime request/history contents affect computed tickets, not the selected class/provider/callable identity.

Supplemental binding fingerprint: `416b774564574798d961188b0968af43b39b4721a280b9c784de65d4ff2ee25f`

### `legacy_biglotto__test_greedy_optimizer__82df7f878ece`

`src/lottolab/strategies/catalog.py:857:StrategyDescriptor[legacy_biglotto__test_greedy_optimizer__82df7f878ece]` → `src/lottolab/strategies/executable_registry.py:21:ExecutableRegistry.load_adapter` → `src/lottolab/strategies/adapters/biglotto_wave8.py:80:BigLottoGreedyThreeAdapter` → `src/lottolab/strategies/adapters/biglotto_wave8.py:46:_BigLottoWave8PortfolioAdapter.__init__` → `src/lottolab/strategies/adapters/biglotto_wave8.py:23:Wave26PortfolioAuthority` → `src/lottolab/application/use_cases/generate_bet.py:553:_instantiated_portfolio_adapter[wave26_authority]` → `src/lottolab/application/use_cases/generate_bet.py:563:_generate_wave26_portfolio` → `src/lottolab/application/legacy_source_native_portfolios_wave26.py:637:generate_legacy_source_native_wave26_portfolio` → `src/lottolab/application/legacy_source_native_portfolios_wave26.py:571:_greedy_rows`

The descriptor names one concrete adapter class; its inherited constructor requires wave26_authority:Wave26PortfolioAuthority; the canonical instantiator injects the single named provider src/lottolab/application/use_cases/generate_bet.py:563:_generate_wave26_portfolio; the adapter's static legacy_method_id='tools/test_greedy_optimizer.py' selects src/lottolab/application/legacy_source_native_portfolios_wave26.py:571:_greedy_rows. Runtime request/history contents affect computed tickets, not the selected class/provider/callable identity.

Supplemental binding fingerprint: `057b47024f8fa6e65d3f8aed1ca445aade1c5e8d920468a367ab460fbdf75600`

### `legacy_biglotto__test_mwsc__ba37643d6a3b`

`src/lottolab/strategies/catalog.py:878:StrategyDescriptor[legacy_biglotto__test_mwsc__ba37643d6a3b]` → `src/lottolab/strategies/executable_registry.py:21:ExecutableRegistry.load_adapter` → `src/lottolab/strategies/adapters/biglotto_wave8.py:89:BigLottoMwscThreeAdapter` → `src/lottolab/strategies/adapters/biglotto_wave8.py:46:_BigLottoWave8PortfolioAdapter.__init__` → `src/lottolab/strategies/adapters/biglotto_wave8.py:23:Wave26PortfolioAuthority` → `src/lottolab/application/use_cases/generate_bet.py:553:_instantiated_portfolio_adapter[wave26_authority]` → `src/lottolab/application/use_cases/generate_bet.py:563:_generate_wave26_portfolio` → `src/lottolab/application/legacy_source_native_portfolios_wave26.py:637:generate_legacy_source_native_wave26_portfolio` → `src/lottolab/application/legacy_source_native_portfolios_wave26.py:466:_mwsc_rows`

The descriptor names one concrete adapter class; its inherited constructor requires wave26_authority:Wave26PortfolioAuthority; the canonical instantiator injects the single named provider src/lottolab/application/use_cases/generate_bet.py:563:_generate_wave26_portfolio; the adapter's static legacy_method_id='tools/test_mwsc.py' selects src/lottolab/application/legacy_source_native_portfolios_wave26.py:466:_mwsc_rows. Runtime request/history contents affect computed tickets, not the selected class/provider/callable identity.

Supplemental binding fingerprint: `8d7b4cc6d782d741719373280526a2c544d299763a86a262e36582b06c18731d`

## Scientific and runtime boundary

- `DB_ACCESS = NO`
- `DB_WRITE = NO`
- `HISTORICAL_REPLAY = NOT RUN`
- `PRODUCTION_RUNTIME_START = NOT RUN`
- `SEMANTIC_EQUIVALENCE = NOT CLAIMED`

The static `legacy_method_id` values resolve which Wave 26 row callable is selected. History and target-draw contents still affect computed tickets; this supplement establishes structural implementation identity only.
