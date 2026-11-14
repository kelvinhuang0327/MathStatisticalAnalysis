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
    current_version: str
    adapter_path: str
    implementation_sha256: str
    parity_test: str
    parity_evidence: str

    @property
    def locator(self) -> str:
        return (
            f"{self.source_path}@{self.source_commit}#{self.source_blob_id}"
            f";sha256={self.source_sha256}"
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
            "lottolab.strategies.adapters.biglotto_apriori:"
            "BigLottoAprioriPredictorAdapter"
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
            "lottolab.strategies.adapters.biglotto_radical_gap:"
            "BigLottoRadicalGapBacktestAdapter"
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
            "lottolab.strategies.adapters.biglotto_quad_strike:"
            "BigLottoQuadStrikeAdapter"
        ),
        implementation_sha256="702a325778a1f5abadd1f4fa9d2e114d4751ab5ff7a6298a43a1b734095dc7d6",
        parity_test=(
            "tests/unit/test_biglotto_quad_strike_adapter.py::"
            "test_complete_portfolio_matches_frozen_donor_golden"
        ),
        parity_evidence="EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY",
    ),
)


def _source_descriptor(source: VersionedReplaySource) -> tuple[object, object]:
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
    return record, descriptor


def versioned_biglotto_replay_bindings() -> tuple[ReplayStrategyBinding, ...]:
    """Build only the explicitly reviewed, source-pinned Replay bindings."""

    bindings: list[ReplayStrategyBinding] = []
    for source in VERSIONED_REPLAY_SOURCES:
        _record, descriptor = _source_descriptor(source)
        module_path, _, class_name = source.adapter_path.partition(":")
        module = importlib.import_module(module_path)
        adapter_class = getattr(module, class_name)
        implementation_file = Path(module.__file__).resolve()
        implementation_sha256 = hashlib.sha256(implementation_file.read_bytes()).hexdigest()
        if implementation_sha256 != source.implementation_sha256:
            raise ValueError(f"versioned Replay implementation changed: {source.strategy_id}")
        implementation = instantiate_portfolio_adapter(source.strategy_id, adapter_class)
        if implementation.strategy_version != source.current_version:
            raise ValueError(f"current adapter version changed: {source.strategy_id}")

        fingerprint_payload = "|".join(
            (
                source.strategy_id,
                source.strategy_version,
                source.locator,
                source.adapter_path,
                source.current_version,
                source.implementation_sha256,
                source.parity_test,
                source.parity_evidence,
                descriptor.version,
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
