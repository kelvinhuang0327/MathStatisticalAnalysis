"""Replay-only bindings for frozen BIG_LOTTO versions with proven parity.

These bindings preserve the source version as a first-class Replay identity.
They do not register or change a production strategy descriptor.
"""

from __future__ import annotations

import hashlib
import importlib
from dataclasses import dataclass, replace
from pathlib import Path

from lottolab.application.biglotto_frozen_xgboost import FrozenXGBoostWave64Replay
from lottolab.application.historical_replay_adapters import (
    ReplayStrategyBinding,
    binding_from_implementation,
)
from lottolab.application.use_cases.generate_bet import instantiate_portfolio_adapter
from lottolab.domain.biglotto_full_strategy_catalog import load_full_strategy_catalog
from lottolab.domain.historical_replay import ReplayBehavior
from lottolab.domain.strategies import ResponseShape
from lottolab.strategies.catalog import production_catalog


@dataclass(frozen=True, slots=True)
class VersionedReplaySource:
    strategy_id: str
    strategy_version: str
    source_path: str
    source_commit: str
    source_blob_id: str
    source_sha256: str
    current_version: str | None
    adapter_path: str
    implementation_sha256: str
    parity_test: str
    parity_evidence: str
    shared_modules: tuple[tuple[str, str], ...] = ()

    @property
    def locator(self) -> str:
        return (
            f"{self.source_path}@{self.source_commit}#{self.source_blob_id}"
            f";sha256={self.source_sha256}"
        )


_QUAD_MODULE_SHA256 = "36419dbff87fec29a4f31e4d24e7d508260454ad1e3fe092901d0c91ea1c3787"


def _historical_portfolio(
    source_path: str, source_blob: str, source_sha256: str, adapter: str
) -> VersionedReplaySource:
    """Bind a reviewed frozen program independently of similarly named live adapters."""
    digest = source_sha256[:12]
    return VersionedReplaySource(
        strategy_id=f"legacy_biglotto__{Path(source_path).stem}__{digest}",
        strategy_version=f"legacy-source-49a25effa62f-{digest}",
        source_path=source_path,
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id=source_blob,
        source_sha256=source_sha256,
        current_version=None,
        adapter_path=f"lottolab.strategies.adapters.biglotto_frozen_portfolios:{adapter}",
        implementation_sha256="746b58204b3f78e85948a6e937393ea18027e3869fc2c3b17f69b5b8cb70340e",
        parity_test="tests/unit/test_biglotto_frozen_portfolios.py::test_ordered_historical_parity",
        parity_evidence="EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY",
        shared_modules=(
            (
                "lottolab.strategies.adapters.biglotto_quad_strike",
                _QUAD_MODULE_SHA256,
            ),
            (
                "lottolab.strategies.adapters.biglotto_composite_quick_predict_5bet",
                "34d1fd27515b76db443c0e410ab02864fdb6e0705120bff8634368fe9741eb87",
            ),
        ),
    )


_GRID_MODULE_SHA256 = {
    "biglotto_apriori": "d9fa2b6087384719fc7fb65fc415e9c8c0475fbb6df4c81513939cb11563ab2e",
    "biglotto_batch16": "ff5e01b17e95091f8cd2aa5b88ee13776fb0e15f89757e1d4bbeb400674a8a88",
    "biglotto_composite_quick_predict_5bet": "34d1fd27515b76db443c0e410ab02864fdb6e0705120bff8634368fe9741eb87",
    "biglotto_constraint_filter": "25a2368088d32bc003b358b3977f5a2c3fd5b724a5cc9fdce4f2276b9532da35",
    "biglotto_frozen_enhancements": "6ed1127055d76e85f09c59ba5ac9ec2d1aba4842515233c78685fbf7e729011e",
    "biglotto_frozen_feature_discovery": "59c50177856c265ef1d3e3828abcf677e327067ead45af762a214bc47df7259d",
    "biglotto_frozen_recipes": "7de8a567e88f9e0e6dfec6dfde7a3297b635f396d1edb158591aafdc9575827a",
    "biglotto_frozen_signals": "cb05d2248b6ab87be038a2502ce87a567db6909a90f4380b647f88917d182d0a",
    "biglotto_frozen_sweep": "6c48c283e1c84a975f310ae41c5f2cbd1872884b9904322f8eb3e5e8de3aecaf",
    "biglotto_numpy126_twiddles": "90b4a58de8eef8fdf6ded336f2babd730aba058bffd58a4bca29279a34e85e27",
    "biglotto_quad_strike": _QUAD_MODULE_SHA256,
    "biglotto_selected": "fbe1eca1ef7d00f77cf3204e7fed9a66bd7c8bc96bd0e560a9679554a8650c34",
    "biglotto_wave12": "4182139f9e2a7bb917fe294bca017772a9cbd81b2d4c12a3cca15d92bdcb5023",
    "biglotto_wave3": "4662857f668751a187933c966860373fc6e57fa47a7f80b6a8dcfea9ad64e528",
}

_GRID_DEPENDENCIES = {
    "biglotto_frozen_signals": (
        "biglotto_quad_strike", "biglotto_constraint_filter", "biglotto_numpy126_twiddles"
    ),
    "biglotto_frozen_enhancements": (
        "biglotto_quad_strike",
        "biglotto_composite_quick_predict_5bet",
        "biglotto_constraint_filter",
    ),
    "biglotto_frozen_recipes": (
        "biglotto_batch16",
        "biglotto_constraint_filter",
        "biglotto_quad_strike",
        "biglotto_selected",
        "biglotto_wave3",
        "biglotto_wave12",
    ),
    "biglotto_frozen_sweep": ("biglotto_quad_strike", "biglotto_apriori", "biglotto_batch16"),
    "biglotto_frozen_feature_discovery": ("biglotto_constraint_filter", "biglotto_wave12"),
}


def _historical_grid(
    source_path: str, source_blob: str, source_sha256: str, module: str, adapter: str
) -> VersionedReplaySource:
    digest = source_sha256[:12]
    package = "lottolab.strategies.adapters."
    return VersionedReplaySource(
        strategy_id=f"legacy_biglotto__{Path(source_path).stem}__{digest}",
        strategy_version=f"legacy-source-49a25effa62f-{digest}",
        source_path=source_path,
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id=source_blob,
        source_sha256=source_sha256,
        current_version=None,
        adapter_path=f"{package}{module}:{adapter}",
        implementation_sha256=_GRID_MODULE_SHA256[module],
        parity_test="tests/unit/test_biglotto_frozen_grid.py::test_ordered_portfolio",
        parity_evidence="EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY",
        shared_modules=tuple(
            (package + name, _GRID_MODULE_SHA256[name]) for name in _GRID_DEPENDENCIES[module]
        ),
    )


_FROZEN_UNIFIED_MODULES = (
    (
        "lottolab.application.legacy_frozen_unified_core",
        "f401daede4d0a14bf148ceb00157c18279fde201bbc3251ef633540c61f61e8f",
    ),
    (
        "lottolab.application.legacy_history_native_portfolios",
        "e1512870990e207384a7b6faa9c683c730d7866d3c5b94307a5f30aaba0bd710",
    ),
)

_WAVE27_MODULES = (
    (
        "lottolab.application.legacy_source_native_portfolios_wave27",
        "bdc3acf0c791c9e0a530e0f0032df983348720e4e026ded379119993a89664c6",
    ),
    *_FROZEN_UNIFIED_MODULES,
)


VERSIONED_REPLAY_SOURCES = (
    VersionedReplaySource(
        strategy_id="legacy_biglotto__xgboost_model__38c72a70c627",
        strategy_version="legacy-source-49a25effa62f-38c72a70c627",
        source_path="lottery_api/models/xgboost_model.py",
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id="331b97562b593c061937ad9afac79fc5b8d88152",
        source_sha256="38c72a70c627285dab2b55163b387b3ed8ab6bd9820c10d7daed0dce777f1c01",
        current_version=None,
        adapter_path="lottolab.application.biglotto_frozen_xgboost:FrozenXGBoostWave64Replay",
        implementation_sha256="e171e91bfbf12720d8fff10038602c7c00a86a706a2483f9edbec16d56fccfae",
        parity_test="tests/unit/test_biglotto_frozen_grid.py::test_wave64_xgboost_ordered_playback",
        parity_evidence="CHECKSUMMED_FROZEN_SOURCE_RUNTIME_LEDGER_PLAYBACK",
        shared_modules=(
            (
                "lottolab.application.legacy_xgboost_native_portfolios_wave64",
                "438d85dffe738aed0bd0cf867b25bcae639e27c88c80ab32f952984f2436a78d",
            ),
            (
                "lottolab.application.legacy_history_native_portfolios",
                "e1512870990e207384a7b6faa9c683c730d7866d3c5b94307a5f30aaba0bd710",
            ),
        ),
    ),
    VersionedReplaySource(
        strategy_id="legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d",
        strategy_version="legacy-source-49a25effa62f-8caaac8fcb5d",
        source_path="tools/biglotto_diversified_ensemble_v6.py",
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id="8a2b6d9e5f8f921d5d20e719e99e94e1fb67cf3b",
        source_sha256="8caaac8fcb5d1976174e6def13bf01d47e0fb00edb6d555d838c662bb5daaf2d",
        current_version=None,
        adapter_path=(
            "lottolab.application.biglotto_frozen_diversified_ensemble_v6:"
            "FrozenDiversifiedEnsembleV6"
        ),
        implementation_sha256="aa4d91dc75da8b04e9f289bcbb630d2053d55cfc16e434e277b6f45937e4dfbd",
        parity_test="tests/unit/test_biglotto_frozen_grid.py::test_wave58_v6_ordered_portfolios",
        parity_evidence="EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY",
        shared_modules=(
            (
                "lottolab.strategies.adapters.biglotto_wave10",
                "f2b629387ce2546219dd69d12471b8b09a04bf6c40b94a32711703999a1015a8",
            ),
            (
                "lottolab.strategies.adapters.biglotto_constraint_filter",
                _GRID_MODULE_SHA256["biglotto_constraint_filter"],
            ),
        ),
    ),
    VersionedReplaySource(
        strategy_id="legacy_biglotto__advanced_methods_benchmark__87ee0d15033c",
        strategy_version="legacy-source-49a25effa62f-87ee0d15033c",
        source_path="tools/advanced_methods_benchmark.py",
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id="1d768c0ef6a66d340ef9b90d0665d420a4c3d7cd",
        source_sha256="87ee0d15033c8873c7cf4c1f7334fc154dbab434703195cc4e90810169ea620f",
        current_version=None,
        adapter_path=(
            "lottolab.application.biglotto_frozen_advanced_methods:FrozenAdvancedMethodsBenchmark"
        ),
        implementation_sha256="75e5aeda70574197ce5080274979d64a29b0256d9a1f16286264370b8c85b5d6",
        parity_test="tests/unit/test_biglotto_frozen_grid.py::test_wave63_advanced_ordered_portfolios",
        parity_evidence="EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY",
        shared_modules=(
            (
                "lottolab.application.legacy_history_native_portfolios",
                "e1512870990e207384a7b6faa9c683c730d7866d3c5b94307a5f30aaba0bd710",
            ),
        ),
    ),
    VersionedReplaySource(
        strategy_id="legacy_biglotto__hpsb_optimizer__cf5cd7d971e8",
        strategy_version="legacy-source-49a25effa62f-cf5cd7d971e8",
        source_path="lottery_api/models/hpsb_optimizer.py",
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id="a433ef189ee3a0d71a3ad67b5ba15d2ba94e5b33",
        source_sha256="cf5cd7d971e8bf2f1854d2196824278de957b3eae3697dff197ab9a3c8b78bcc",
        current_version=None,
        adapter_path="lottolab.application.biglotto_frozen_hpsb:FrozenHpsbOptimizer",
        implementation_sha256="17f350c99d661d00e588692501077abf98921dd60767412d741a0174905ac367",
        parity_test="tests/unit/test_biglotto_frozen_grid.py::test_wave57_hpsb_ordered_portfolios",
        parity_evidence="EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY",
        shared_modules=(
            *_FROZEN_UNIFIED_MODULES,
            (
                "lottolab.strategies.adapters.biglotto_wave14",
                "a590ab3cd5b616dc57307938f58737096a52c5a82018ca0882bb16edc4725d93",
            ),
            ("lottolab.strategies.adapters.biglotto_wave3", _GRID_MODULE_SHA256["biglotto_wave3"]),
            (
                "lottolab.strategies.adapters.biglotto_wave4",
                "8665920f3f81fd38ef7c08ce437ffbdcc5718f6041a82b3ce737838d8d74ac4a",
            ),
        ),
    ),
    VersionedReplaySource(
        strategy_id="legacy_biglotto__hybrid_integration_benchmark__5789ca885422",
        strategy_version="legacy-source-49a25effa62f-5789ca885422",
        source_path="tools/hybrid_integration_benchmark.py",
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id="76b4632ac1adb6efe17539cb995dbdc0397230d2",
        source_sha256="5789ca8854224383a3c84e62871bc891c0661699309ae32aeff65ca403b3a64b",
        current_version=None,
        adapter_path=(
            "lottolab.application.biglotto_frozen_hybrid_integration:FrozenHybridIntegrationBenchmark"
        ),
        implementation_sha256="45667b3deff6f1af5d10be0797c982e0bcb54fa8d7f7820ce51d5764f842dd19",
        parity_test="tests/unit/test_biglotto_frozen_grid.py::test_wave60_hybrid_ordered_portfolios",
        parity_evidence="EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY",
    ),
    VersionedReplaySource(
        strategy_id="legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876",
        strategy_version="legacy-source-49a25effa62f-898ac9e38876",
        source_path="lottery_api/models/biglotto_2bet_optimizer.py",
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id="f181c9860520e96455748be7a35b23a5481083a7",
        source_sha256="898ac9e38876841fb000796a3e9627dc339a19ad89babb23d7a2869da5db8e9c",
        current_version=None,
        adapter_path="lottolab.application.biglotto_frozen_two_bet_optimizer:FrozenTwoBetOptimizer",
        implementation_sha256="df4045c459e61d6036b51809a0f1b576e39a9d68eca844ee56a1071568ec46d4",
        parity_test="tests/unit/test_biglotto_frozen_grid.py::test_frozen_two_bet_optimizer",
        parity_evidence="EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY",
        shared_modules=_WAVE27_MODULES,
    ),
    VersionedReplaySource(
        strategy_id="legacy_biglotto__biglotto_2bet_optimizer_v2__783226366ac3",
        strategy_version="legacy-source-49a25effa62f-783226366ac3",
        source_path="lottery_api/models/biglotto_2bet_optimizer_v2.py",
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id="bcb285bc2db1a3fbebeab2b9f755b6e005716dc3",
        source_sha256="783226366ac392dd441bbdfb89b873d3c7dd9eb4a231c0f2ccb0144de56798dd",
        current_version=None,
        adapter_path=(
            "lottolab.application.biglotto_frozen_two_bet_optimizer_v2:FrozenTwoBetOptimizerV2"
        ),
        implementation_sha256="5fbf5731fdb34815c6f769b627466e471501c9e3a5c250715180ea2bcd51e411",
        parity_test="tests/unit/test_biglotto_frozen_grid.py::test_frozen_two_bet_optimizer_v2",
        parity_evidence="EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY",
        shared_modules=_WAVE27_MODULES,
    ),
    VersionedReplaySource(
        strategy_id="legacy_biglotto__orthogonal_diversification_benchmark__ce068c676ca5",
        strategy_version="legacy-source-49a25effa62f-ce068c676ca5",
        source_path="tools/orthogonal_diversification_benchmark.py",
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id="80c59b2270a0d61ae95dc1d4a8045be323b3cc7c",
        source_sha256="ce068c676ca5b16e48d95499a8b9c4cc8ba105962b02c71ad9b076f68659ca71",
        current_version=None,
        adapter_path=(
            "lottolab.application.biglotto_frozen_orthogonal_diversification:"
            "FrozenOrthogonalDiversification"
        ),
        implementation_sha256="f7da1f2e67f41a9a1fe96caa4c4643adc604a94cb581f4758ce8889c5a74017d",
        parity_test=(
            "tests/unit/test_biglotto_frozen_grid.py::test_frozen_orthogonal_diversification"
        ),
        parity_evidence="EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY",
    ),
    VersionedReplaySource(
        strategy_id="legacy_biglotto__zone_split_optimizer__0bf85e3e1517",
        strategy_version="legacy-source-49a25effa62f-0bf85e3e1517",
        source_path="tools/zone_split_optimizer.py",
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id="a5751a20008227828f80db0fbf0bc15a1dcb5067",
        source_sha256="0bf85e3e151766d3bdc174f5395200e730d0c45233afad0d1d91d43200149fe3",
        current_version=None,
        adapter_path=(
            "lottolab.application.biglotto_frozen_zone_split_optimizer:FrozenZoneSplitOptimizer"
        ),
        implementation_sha256="fd5f2a93966e6e7b038aedb9a4edb00b3318b6f8dc903f69c3463f05fb8ed648",
        parity_test="tests/unit/test_biglotto_frozen_grid.py::test_frozen_zone_split_optimizer",
        parity_evidence="EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY",
        shared_modules=(
            (
                "lottolab.strategies.adapters.biglotto_constraint_filter",
                _GRID_MODULE_SHA256["biglotto_constraint_filter"],
            ),
        ),
    ),
    VersionedReplaySource(
        strategy_id="legacy_biglotto__predict_biglotto_apriori__cda690ae84c2",
        strategy_version="legacy-source-49a25effa62f-cda690ae84c2",
        source_path="tools/predict_biglotto_apriori.py",
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id="53222aacf71474fb25487ea625e0e9519760a75a",
        source_sha256="cda690ae84c2324b5f7d160a68e0ba3cf65d6073ecfc5c28ef48402b07018e7b",
        current_version="v0.1",
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_apriori:BigLottoAprioriPredictorAdapter"
        ),
        implementation_sha256="d9fa2b6087384719fc7fb65fc415e9c8c0475fbb6df4c81513939cb11563ab2e",
        parity_test=(
            "tests/unit/test_biglotto_apriori_adapter.py::"
            "test_apriori_matches_preserved_donor_at_every_supported_cardinality"
        ),
        parity_evidence="WAVE7_RETAINED_DONOR_OUTPUT_PARITY",
    ),
    VersionedReplaySource(
        strategy_id="legacy_biglotto__backtest_radical_strategy__e54cc0812bc6",
        strategy_version="legacy-source-49a25effa62f-e54cc0812bc6",
        source_path="tools/backtest_radical_strategy.py",
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id="c460fb65561000a1e3a0d5558133784603860f2c",
        source_sha256="e54cc0812bc6fff14a259282a37821810d264c023c4fb87517305b511db08fd9",
        current_version="v0.1",
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_radical_gap:BigLottoRadicalGapBacktestAdapter"
        ),
        implementation_sha256="d612355577e934a17d6648a988cf1befbd327eef51c6ba1924e5d876abc6260d",
        parity_test=(
            "tests/unit/test_biglotto_radical_gap_adapter.py::"
            "test_complete_target_output_matches_retained_reference"
        ),
        parity_evidence="EXACT_OUTPUT_PARITY",
    ),
    VersionedReplaySource(
        strategy_id="legacy_biglotto__predict_biglotto_quad_strike__e202e664208f",
        strategy_version="legacy-source-49a25effa62f-e202e664208f",
        source_path="tools/predict_biglotto_quad_strike.py",
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id="c3416cb8ae787276a020ab4eeb2f7402612381ae",
        source_sha256="e202e664208faf3f998f93f4992a8e2595fe17f2179345bba8d4587deff48a36",
        current_version="v0.1",
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_quad_strike:BigLottoQuadStrikeAdapter"
        ),
        implementation_sha256=_QUAD_MODULE_SHA256,
        parity_test=(
            "tests/unit/test_biglotto_quad_strike_adapter.py::"
            "test_complete_portfolio_matches_frozen_donor_golden"
        ),
        parity_evidence="EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY",
    ),
    VersionedReplaySource(
        strategy_id="legacy_biglotto__backtest_biglotto_triple_strike_original__4a8297a758b9",
        strategy_version="legacy-source-49a25effa62f-4a8297a758b9",
        source_path="tools/backtest_biglotto_triple_strike_original.py",
        source_commit="49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        source_blob_id="91ee32fb9121b6771aacc5306d388e982151e998",
        source_sha256="4a8297a758b90b0a8697a889d2c9f1e9321ca2e1a5cac5322eb4e51d943e7977",
        current_version=None,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_triple_strike_original:"
            "BigLottoTripleStrikeOriginalReplayAdapter"
        ),
        implementation_sha256="6c431dfafb36f57e7f20551403a9414353bb1ef3ddfcf51df7d4c30d6a14414b",
        parity_test=(
            "tests/unit/test_biglotto_triple_strike_original.py::test_replay_matches_pinned_source"
        ),
        parity_evidence="EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY",
        shared_modules=(
            ("lottolab.strategies.adapters.biglotto_quad_strike", _QUAD_MODULE_SHA256),
        ),
    ),
    _historical_portfolio(
        "tools/backtest_direction_3.py",
        "0b9b107cafeb3fef72ae8f39dab1e58b9a60d578",
        "91f93b31efb5a4ffae1956929aea93b53f972424d80a27caf0e246b3f54c48cc",
        "DirectionThree",
    ),
    _historical_portfolio(
        "tools/backtest_biglotto_6bet_ewma.py",
        "3b77c36c031b74b7766525183cf7e0c67fc1817d",
        "e1b5e100d254e2d77a5336b2d5a77675c65034d952c99940772b33d3d2332a08",
        "EwmaSixBet",
    ),
    _historical_portfolio(
        "tools/backtest_fcf_vs_ts3.py",
        "150bdda6cab68f5729f95015337858309def7317",
        "efc61a5517309025e22b7e37186a6e23b72d3bca572f02f93af9748a238c91e8",
        "FcfVersusTripleStrike",
    ),
    _historical_portfolio(
        "tools/backtest_biglotto_6bet.py",
        "f1eae3b93dc9a18089a79b2d760360adf4296b7c",
        "f5d8c03421d2be5f093233335d5fc28d7409eed54d203c788c4b9d46e53b1410",
        "LagTwoSixBet",
    ),
    _historical_portfolio(
        "tools/backtest_biglotto_markov_4bet.py",
        "cd5b6f780cdf0d2363a631dc5faba0a013a52566",
        "aefb54eb345bf38fbeb1526959c12a3585a970325316dfbc2c6a7bb440b5ec6a",
        "MarkovFourBet",
    ),
    _historical_portfolio(
        "tools/backtest_markov_repeat_exception.py",
        "b0b304ca9944e80e208fb6e4eddaeaa00611685a",
        "9bd283fca5f3c543116b64cac512f41f889dadaf7cd646431cc83a62980ac071",
        "MarkovRepeat",
    ),
    _historical_portfolio(
        "tools/optimal_2bet_3bet_matrix.py",
        "6cc24aca66cee1a77428c3ce2b2680b6b0d6011a",
        "6e5aec296145ab1680cb90db65ba8265d7ed3b895ec26fc9506db8932d333c6e",
        "OptimalMatrix",
    ),
    _historical_portfolio(
        "ai_lab/automl_biglotto/portfolio_optimizer.py",
        "0eecf4c625005e5ee9836bfc7a1c0519c89e8f6f",
        "1a6efc7959b61fc400c037fe62fd143cfa2ad33d70c59f799326f1f196f55719",
        "PortfolioOptimizer",
    ),
    _historical_portfolio(
        "tools/backtest_big_lotto_3bet.py",
        "1f7bed9d705614f26b323bd4f0278c52e066c7ff",
        "245f477b3e77422c33472ab7d093c40526d702cdffb0385e3c2f60bc50b691ba",
        "PowerPrecisionThree",
    ),
    _historical_portfolio(
        "tools/analyze_prediction_115000019.py",
        "93332cb4728c4f6a5a0e930ec74972bc77026743",
        "021e1c5ede7bd1e89772d61744ea867616ee0af7f8fd441d92c3b4e0eb53d643",
        "PredictionAnalysis",
    ),
    _historical_portfolio(
        "tools/quick_predict.py",
        "a650fb68b3b46e10a9b1aea29d2a1d26f291ca0a",
        "86259fc99c70862b8d7730280bdccf4f37c24d9a951d67501ff188a8af3c3344",
        "QuickPredict",
    ),
    _historical_portfolio(
        "tools/backtest_biglotto_triple_strike_v2.py",
        "24b521bea2d94bed0e1bb3a3fd85fe3be93fbb0f",
        "977a7cf65c8f8c5732d08edce53eb5250c9959992bf9718adb6cd3ec32a1bda5",
        "TripleStrikeV2",
    ),
    _historical_portfolio(
        "tools/verify_markov_vs_triple_2bet.py",
        "efcbd103b3dc0e65ba6a8fdae6db245f5781c1f0",
        "2094ee4bc361d87b70e49756966284bb1e996af830ae979d1fe598c75210200a",
        "MarkovVersusTriple",
    ),
    _historical_portfolio(
        "tools/rgf_walkforward_validator.py",
        "8239d9ac39b093d04b13769da6c7fa3e514660cf",
        "cab0d1127b625660dc68f237069150d6494bc06841b692bca347518431ae1efa",
        "RegimeFormulaGrid",
    ),
    _historical_portfolio(
        "tools/backtest_structural_group.py",
        "de78e590d5baaeb1da57731a86a407208e47ca36",
        "2fc42ff67ab1e07c6a57adf9e9837ca5989163eff92c107c89f2b58d0081be0f",
        "StructuralGroup",
    ),
    _historical_grid(
        "feature_discovery_and_retrospective.py",
        "4ff25949d8472161fd26530181b7c840862cf331",
        "e2ea8b18945dd164818134738faa41bb9af1a44a24bc2925b172f202aa5e54ad",
        "biglotto_frozen_feature_discovery",
        "FeatureDiscovery",
    ),
    _historical_grid(
        "tools/backtest_biglotto_enhancements.py",
        "9f293c05a9e50a21bdbf8cafeb372931ee789f21",
        "b0bf78ef7e32ef1e07825251af45846076dbd331f6a1f2f8c89a08a1f301696e",
        "biglotto_frozen_enhancements",
        "Enhancements",
    ),
    _historical_grid(
        "tools/edge_splicer.py",
        "face53f9d700c609feb59d9d0742edc24d7fd4e8",
        "04d9e8bbfe76f16be95e0a1f4e016913fb29c69add18313eeaca9a378d51c58c",
        "biglotto_frozen_signals",
        "EdgeSplicer",
    ),
    _historical_grid(
        "tools/edge_splicer_5bet.py",
        "1e69a431c229543e8b3f5cc0730e0e1f4247023f",
        "da1d1eed4d966323a9570a75ea334983e912bf90ace978f6ad112db53951d479",
        "biglotto_frozen_signals",
        "EdgeSplicerFive",
    ),
    _historical_grid(
        "tools/edge_splicer_v2.py",
        "9d9b33a1675ef7057bca23e8d0860bf770448289",
        "6b6e9d64da1253762c5fa22eb8a4f815bf4c3e058b952c2a05a2a9654782bf00",
        "biglotto_frozen_signals",
        "EdgeSplicerV2",
    ),
    _historical_grid(
        "tools/evaluate_combinations.py",
        "c84bf2f61f45557b4e41caa5ca5fb8a5349ba95d",
        "d49d0787d0c6fb9407024111d339cf76c4b165dc90d0713a0ac589929f9371a0",
        "biglotto_frozen_signals",
        "EvaluateCombinations",
    ),
    _historical_grid(
        "tools/evaluate_concentrator.py",
        "848ae8fca098de72a71dfe44405d3d8f553d2a89",
        "d732e4dd594c9f19aff5dea2292711d33a4bb6e7c3acd0a4ecd9fc5aba302970",
        "biglotto_frozen_signals",
        "EvaluateConcentrator",
    ),
    _historical_grid(
        "tools/exhaustive_feature_sweep_v2.py",
        "f24c03c755e3e1e6910a8d5120e19bfbb59bccdc",
        "ff4096a9e7e59a4bf441d6c0ab4afa45a6471d71f532d26200fb810f5c5cb7bb",
        "biglotto_frozen_sweep",
        "ExhaustiveFeatureSweep",
    ),
    _historical_grid(
        "tools/generate_2_3_bets.py",
        "1d121da12c270495d032eff914103c3416b78633",
        "f8853b95f3c53bd25e0af0a6ddd5060046ac457faeba523d8ff68eff25af1000",
        "biglotto_frozen_signals",
        "GenerateTwoThree",
    ),
    _historical_grid(
        "tools/historical_audit_rigorous.py",
        "8dbfec14d5685a5270385a5ca7955fb0b0e37691",
        "bfb679104f6052a7bd397dba0a2bcc04f63fd74f8e2e303a9f867b7737075a97",
        "biglotto_frozen_recipes",
        "HistoricalAudit",
    ),
    _historical_grid(
        "tools/optimize_biglotto_cluster.py",
        "1a529b69dded93a978f8182c8282c16344cc8786",
        "b2a833918f9558a577c18a297e920d1eb9f50bb926795821bb65baa83d8ea675",
        "biglotto_frozen_recipes",
        "OptimizeCluster",
    ),
    _historical_grid(
        "tools/optimize_deviation_extreme_generic.py",
        "2273a2837b97c4040e50be24166e45b3e1ee79b6",
        "87e19bb3514af177077869bd8f5ca8ea0aed273584b4af8e577fa7fac11cdc31",
        "biglotto_frozen_recipes",
        "OptimizeDeviation",
    ),
    _historical_grid(
        "tools/predict_consensus_ensemble.py",
        "18457329b7993e1f9b28078b92b1296c5f06a61d",
        "3ceb975a355c1912bab79134cd6a921140aaf50d97d83cf10639bf4d48a72be2",
        "biglotto_frozen_recipes",
        "ConsensusEnsemble",
    ),
    _historical_grid(
        "tools/standard_ts3_5bet.py",
        "ac1c1283aa56ef0df4217b801d736b235d6ed39d",
        "527fed00a7c4d47bbd286dfce905ca278c471cacaadf4e8e93ab3f693425db74",
        "biglotto_frozen_signals",
        "StandardFive",
    ),
)


def _verify_source(source: VersionedReplaySource) -> None:
    record = next(
        (
            item
            for item in load_full_strategy_catalog().records
            if item.strategy_id == source.strategy_id
            and item.strategy_version == source.strategy_version
        ),
        None,
    )
    if record is None:
        raise ValueError(f"versioned Replay source is absent from catalog: {source.strategy_id}")
    actual_source = (
        record.source_path,
        record.source_commit,
        record.source_blob_id,
        record.source_sha256,
    )
    expected_source = (
        source.source_path,
        source.source_commit,
        source.source_blob_id,
        source.source_sha256,
    )
    if actual_source != expected_source:
        raise ValueError(f"versioned Replay source provenance changed: {source.strategy_id}")

    if source.current_version is None:
        return  # The historical version uses its own implementation.

    descriptor = production_catalog().get(source.strategy_id)
    provenance = set(descriptor.provenance)
    if (
        descriptor.version != source.current_version
        or descriptor.response_shape is not ResponseShape.PORTFOLIO
        or f"legacy_source:{source.source_path}" not in provenance
        or f"legacy_commit:{source.source_commit}" not in provenance
        or f"legacy_source_blob:{source.source_blob_id}" not in provenance
        or f"legacy_source_sha256:{source.source_sha256}" not in provenance
    ):
        raise ValueError(f"current descriptor does not prove source identity: {source.strategy_id}")
    required_parity = f"donor_parity:{source.parity_evidence}"
    if source.parity_evidence != "WAVE7_RETAINED_DONOR_OUTPUT_PARITY" and (
        required_parity not in provenance
    ):
        raise ValueError(f"descriptor parity evidence changed: {source.strategy_id}")


def versioned_biglotto_replay_bindings() -> tuple[ReplayStrategyBinding, ...]:
    """Build only the explicitly reviewed, source-pinned Replay bindings."""

    bindings: list[ReplayStrategyBinding] = []
    for source in VERSIONED_REPLAY_SOURCES:
        _verify_source(source)
        module_path, _, class_name = source.adapter_path.partition(":")
        module = importlib.import_module(module_path)
        adapter_class = getattr(module, class_name)
        for name, digest in ((module_path, source.implementation_sha256), *source.shared_modules):
            module_file = importlib.import_module(name).__file__
            if (
                module_file is None
                or hashlib.sha256(Path(module_file).read_bytes()).hexdigest() != digest
            ):
                raise ValueError(
                    f"versioned Replay implementation changed: {source.strategy_id}: {name}"
                )
        implementation = (
            FrozenXGBoostWave64Replay()
            if adapter_class is FrozenXGBoostWave64Replay
            else instantiate_portfolio_adapter(source.strategy_id, adapter_class)
        )
        implementation_version = source.current_version or source.strategy_version
        if (implementation.strategy_id, implementation.strategy_version) != (
            source.strategy_id,
            implementation_version,
        ):
            raise ValueError(f"Replay adapter identity changed: {source.strategy_id}")

        fingerprint_payload = "|".join(
            (
                source.strategy_id,
                source.strategy_version,
                source.locator,
                source.adapter_path,
                implementation_version,
                source.implementation_sha256,
                source.parity_test,
                source.parity_evidence,
                implementation_version,
                *(f"{name}:{digest}" for name, digest in source.shared_modules),
            )
        )
        fingerprint = hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()
        current_binding = binding_from_implementation(
            implementation,
            behavior=ReplayBehavior.DETERMINISTIC,
            fingerprint=fingerprint,
        )
        source_strategy = replace(
            current_binding.strategy,
            strategy_version=source.strategy_version,
        )
        bindings.append(
            ReplayStrategyBinding(strategy=source_strategy, implementation=implementation)
        )
    return tuple(bindings)


__all__ = [
    "VERSIONED_REPLAY_SOURCES",
    "VersionedReplaySource",
    "versioned_biglotto_replay_bindings",
]
