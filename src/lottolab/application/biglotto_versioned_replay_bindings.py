"""Replay-only bindings for frozen BIG_LOTTO versions with proven parity.

These bindings preserve the source version as a first-class Replay identity.
They do not register or change a production strategy descriptor.
"""

from __future__ import annotations

import hashlib
import importlib
from dataclasses import dataclass, replace
from pathlib import Path

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


_QUAD_MODULE_SHA256 = "702a325778a1f5abadd1f4fa9d2e114d4751ab5ff7a6298a43a1b734095dc7d6"


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


VERSIONED_REPLAY_SOURCES = (
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
        return  # Dedicated historical adapter with no production descriptor.

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
        implementation = instantiate_portfolio_adapter(source.strategy_id, adapter_class)
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
