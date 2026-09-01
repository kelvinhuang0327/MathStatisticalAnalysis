"""Golden vectors, non-regression, RNG sharing, fail-closed, and provenance
coverage for :mod:`lottolab.application.fixed13_prospective_producer`.
"""

from __future__ import annotations

import random as random_module
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import pytest

from lottolab.application.fixed13_prospective_producer import (
    FIXED_13_COHORT_STRATEGY_IDS,
    RNG_REQUIRED_STRATEGY_IDS,
    AdapterConstruction,
    AdapterMetadataUnavailableError,
    EmptyCausalHistoryError,
    FreezeIdentityMismatchError,
    InvalidOfficialDrawIdentityError,
    UnknownFixed13StrategyError,
    produce_fixed13_member,
)
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_frontend_auto_optimize import (
    BigLottoFrontendAutoOptimizeAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_ml import (
    BigLottoFrontendMLFeatureWeightedAdapter,
    BigLottoFrontendMLGeneticAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_monte_carlo import (
    BigLottoFrontendMonteCarloAdapter,
)
from lottolab.strategies.catalog import StrategyCatalog

_FREEZE_SHA256 = "61beff4d35f7b0d10502fe0d1f36cc39e5a240128499061eac2599132019154b"
_TEST_DRAW_IDENTITY = "999999999"

_RNG_REQUIRED_ADAPTER_CLASSES = {
    "legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6": (
        BigLottoFrontendAutoOptimizeAdapter
    ),
    "legacy_biglotto__frontend_ml_features__3a4324bc2aa9": (
        BigLottoFrontendMLFeatureWeightedAdapter
    ),
    "legacy_biglotto__frontend_ml_genetic__3a4324bc2aa9": BigLottoFrontendMLGeneticAdapter,
}


def _synthetic_causal_240_stride8_v1() -> tuple[CausalDrawRow, ...]:
    """SYNTHETIC_CAUSAL_240_STRIDE8_V1 from the pinned reachability authority."""

    return tuple(
        CausalDrawRow(
            draw=f"SYNTHETIC-{index + 1:06d}",
            date="2020-01-01",
            numbers=tuple(sorted(((index + offset * 8) % 49) + 1 for offset in range(6))),
        )
        for index in range(240)
    )


def test_cohort_matches_the_frozen_hypothesis_membership_exactly() -> None:
    expected_order = (
        "biglotto_p0_2bet_bet1",
        "biglotto_wave2_neighbor_ad_graph_bridge_bet",
        "biglotto_wave2_neighbor_ad_graph_centrality_bet",
        "biglotto_wave2_neighbor_ad_graph_pagerank_bet",
        "biglotto_zone_split_3bet_bet1",
        "biglotto_zone_split_3bet_bet3",
        "legacy_biglotto__attention_replay_predictor__a811e2eb8215",
        "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae",
        "legacy_biglotto__cold_hunter_predict__9e89f2b41add",
        "legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6",
        "legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
        "legacy_biglotto__frontend_ml_genetic__3a4324bc2aa9",
        "legacy_biglotto__frontend_odd_even_balance_strategy__5b7f125437d0",
    )
    assert expected_order == FIXED_13_COHORT_STRATEGY_IDS
    assert set(FIXED_13_COHORT_STRATEGY_IDS) >= RNG_REQUIRED_STRATEGY_IDS


# --- Test B: golden vectors for the three RNG-required members --------------
#
# Established once from this exact implementation (CPython 3.13.8) against
# SYNTHETIC_CAUSAL_240_STRIDE8_V1 and official_draw_identity="999999999".


@dataclass(frozen=True, slots=True)
class _GoldenVector:
    strategy_id: str
    ticket: tuple[int, int, int, int, int, int]
    seed_sha256_hex: str
    selfcheck: tuple[float, float, float]


_GOLDEN_VECTORS: tuple[_GoldenVector, ...] = (
    _GoldenVector(
        strategy_id="legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6",
        ticket=(4, 12, 20, 28, 36, 45),
        seed_sha256_hex="7b03dadaca124f67cec4d5a821f0d5203843f43fc46a0ed3bf36e911d6a1357d",
        selfcheck=(0.3763792075495572, 0.2368646342899241, 0.9040070381509003),
    ),
    _GoldenVector(
        strategy_id="legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
        ticket=(6, 11, 18, 19, 26, 27),
        seed_sha256_hex="ce929103cd34ad394b67d0cbdf4ae93a1390a164d34d4955303f32fc7ffa64fb",
        selfcheck=(0.5050089198508392, 0.07459003538197595, 0.3460918828059265),
    ),
    _GoldenVector(
        strategy_id="legacy_biglotto__frontend_ml_genetic__3a4324bc2aa9",
        ticket=(6, 14, 20, 29, 37, 47),
        seed_sha256_hex="392b9973c3a663256e8cf68776e7b84b264e3fd136655862a340ce0dea9ee186",
        selfcheck=(0.6466217330060612, 0.09123788750029282, 0.28456158293939726),
    ),
)


@pytest.mark.parametrize("golden", _GOLDEN_VECTORS, ids=lambda g: g.strategy_id)
def test_golden_vector_for_rng_required_member(golden: _GoldenVector) -> None:
    record = produce_fixed13_member(
        strategy_id=golden.strategy_id,
        official_draw_identity=_TEST_DRAW_IDENTITY,
        freeze_sha256_hex=_FREEZE_SHA256,
        causal_history=_synthetic_causal_240_stride8_v1(),
    )
    assert record.execution.legal_main_numbers == golden.ticket
    assert record.per_member_rng_seed_sha256_hex == golden.seed_sha256_hex
    assert len(golden.seed_sha256_hex) == 64
    assert record.rng_selfcheck_vector == golden.selfcheck
    assert record.per_member_adapter_construction is AdapterConstruction.RNG_INJECTED
    assert "CPython" in record.python_implementation_identity


# --- Test D: the other ten zero-arg members are unchanged --------------------

_TEN_MEMBER_ANCHOR_TICKETS: tuple[tuple[str, tuple[int, int, int, int, int, int]], ...] = (
    ("biglotto_p0_2bet_bet1", (2, 10, 18, 26, 34, 43)),
    ("biglotto_wave2_neighbor_ad_graph_bridge_bet", (1, 2, 3, 4, 5, 6)),
    ("biglotto_wave2_neighbor_ad_graph_centrality_bet", (2, 10, 18, 26, 34, 43)),
    ("biglotto_wave2_neighbor_ad_graph_pagerank_bet", (3, 11, 18, 26, 34, 44)),
    ("biglotto_zone_split_3bet_bet1", (3, 4, 5, 8, 9, 17)),
    ("biglotto_zone_split_3bet_bet3", (34, 35, 37, 43, 45, 48)),
    ("legacy_biglotto__attention_replay_predictor__a811e2eb8215", (3, 11, 19, 27, 35, 44)),
    (
        "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae",
        (2, 3, 10, 11, 18, 19),
    ),
    ("legacy_biglotto__cold_hunter_predict__9e89f2b41add", (3, 4, 11, 12, 19, 36)),
    (
        "legacy_biglotto__frontend_odd_even_balance_strategy__5b7f125437d0",
        (1, 3, 9, 11, 17, 19),
    ),
)


def test_ten_member_anchor_set_matches_the_pinned_reachability_authority() -> None:
    assert len(_TEN_MEMBER_ANCHOR_TICKETS) == 10
    anchored_ids = {strategy_id for strategy_id, _ in _TEN_MEMBER_ANCHOR_TICKETS}
    expected_ids = set(FIXED_13_COHORT_STRATEGY_IDS) - RNG_REQUIRED_STRATEGY_IDS
    assert anchored_ids == expected_ids


@pytest.mark.parametrize(("strategy_id", "expected_ticket"), _TEN_MEMBER_ANCHOR_TICKETS)
def test_ten_zero_arg_members_remain_byte_identical_to_the_reachability_probe(
    strategy_id: str, expected_ticket: tuple[int, int, int, int, int, int]
) -> None:
    record = produce_fixed13_member(
        strategy_id=strategy_id,
        official_draw_identity=_TEST_DRAW_IDENTITY,
        freeze_sha256_hex=_FREEZE_SHA256,
        causal_history=_synthetic_causal_240_stride8_v1(),
    )
    assert record.execution.legal_main_numbers == expected_ticket
    assert record.per_member_adapter_construction is AdapterConstruction.ZERO_ARG_DEFAULT
    assert record.per_member_rng_required is False
    assert record.per_member_rng_seed_sha256_hex is None
    assert record.rng_selfcheck_vector is None


# --- Test E: auto-optimize shares one RNG object across its composite path --


def _extract_rng_argument(call_args: Any) -> object:
    assert call_args is not None
    args: tuple[object, ...] = call_args.args
    kwargs: dict[str, object] = call_args.kwargs
    if "rng" in kwargs:
        return kwargs["rng"]
    return args[1]


def test_auto_optimize_injects_the_same_rng_object_through_the_composite_path() -> None:
    history = _synthetic_causal_240_stride8_v1()
    with (
        patch.object(
            BigLottoFrontendAutoOptimizeAdapter,
            "__init__",
            autospec=True,
            side_effect=BigLottoFrontendAutoOptimizeAdapter.__init__,
        ) as top_level_init,
        patch.object(
            BigLottoFrontendMonteCarloAdapter,
            "__init__",
            autospec=True,
            side_effect=BigLottoFrontendMonteCarloAdapter.__init__,
        ) as montecarlo_init,
    ):
        record = produce_fixed13_member(
            strategy_id="legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6",
            official_draw_identity=_TEST_DRAW_IDENTITY,
            freeze_sha256_hex=_FREEZE_SHA256,
            causal_history=history,
        )

    top_level_rng = _extract_rng_argument(top_level_init.call_args)
    montecarlo_rng = _extract_rng_argument(montecarlo_init.call_args)

    assert top_level_rng is not None
    assert top_level_rng is montecarlo_rng
    # Not merely equal outputs — the exact ticket must still match the golden
    # vector even though construction was intercepted and re-run for real.
    assert record.execution.legal_main_numbers == (4, 12, 20, 28, 36, 45)


# --- Test F: fail-closed gates ------------------------------------------------


def test_unknown_strategy_id_is_fail_closed() -> None:
    with pytest.raises(UnknownFixed13StrategyError) as exc_info:
        produce_fixed13_member(
            strategy_id="not_a_real_fixed13_strategy_id",
            official_draw_identity=_TEST_DRAW_IDENTITY,
            freeze_sha256_hex=_FREEZE_SHA256,
            causal_history=_synthetic_causal_240_stride8_v1(),
        )
    assert exc_info.value.disposition == "PRE_OUTCOME_INELIGIBLE"


def test_empty_official_draw_identity_is_fail_closed() -> None:
    with pytest.raises(InvalidOfficialDrawIdentityError) as exc_info:
        produce_fixed13_member(
            strategy_id="biglotto_p0_2bet_bet1",
            official_draw_identity="",
            freeze_sha256_hex=_FREEZE_SHA256,
            causal_history=_synthetic_causal_240_stride8_v1(),
        )
    assert exc_info.value.disposition == "PRE_OUTCOME_INELIGIBLE"


@pytest.mark.parametrize(
    "malformed_hex",
    [
        "not-hex-at-all",
        "0" * 63,
        "0" * 65,
        "F" * 64,
    ],
)
def test_malformed_freeze_hex_shape_is_fail_closed(malformed_hex: str) -> None:
    with pytest.raises(FreezeIdentityMismatchError) as exc_info:
        produce_fixed13_member(
            strategy_id="biglotto_p0_2bet_bet1",
            official_draw_identity=_TEST_DRAW_IDENTITY,
            freeze_sha256_hex=malformed_hex,
            causal_history=_synthetic_causal_240_stride8_v1(),
        )
    assert exc_info.value.disposition == "PRE_OUTCOME_INELIGIBLE"


def test_wrong_but_well_formed_freeze_hex_is_fail_closed() -> None:
    with pytest.raises(FreezeIdentityMismatchError):
        produce_fixed13_member(
            strategy_id="biglotto_p0_2bet_bet1",
            official_draw_identity=_TEST_DRAW_IDENTITY,
            freeze_sha256_hex="0" * 64,
            causal_history=_synthetic_causal_240_stride8_v1(),
        )


def test_missing_adapter_metadata_is_fail_closed() -> None:
    with (
        patch(
            "lottolab.application.fixed13_prospective_producer.production_catalog",
            return_value=StrategyCatalog([]),
        ),
        pytest.raises(AdapterMetadataUnavailableError) as exc_info,
    ):
        produce_fixed13_member(
            strategy_id="biglotto_p0_2bet_bet1",
            official_draw_identity=_TEST_DRAW_IDENTITY,
            freeze_sha256_hex=_FREEZE_SHA256,
            causal_history=_synthetic_causal_240_stride8_v1(),
        )
    assert exc_info.value.disposition == "PRE_OUTCOME_INELIGIBLE"


def test_empty_causal_history_is_fail_closed() -> None:
    with pytest.raises(EmptyCausalHistoryError) as exc_info:
        produce_fixed13_member(
            strategy_id="biglotto_p0_2bet_bet1",
            official_draw_identity=_TEST_DRAW_IDENTITY,
            freeze_sha256_hex=_FREEZE_SHA256,
            causal_history=(),
        )
    assert exc_info.value.disposition == "PRE_OUTCOME_INELIGIBLE"


@pytest.mark.parametrize("strategy_id", sorted(RNG_REQUIRED_STRATEGY_IDS))
def test_malformed_freeze_identity_never_constructs_the_rng_required_adapter(
    strategy_id: str,
) -> None:
    """A fail-closed gate must fire before any of the three ever binds an RNG.

    If the adapter's ``__init__`` were reached with ``rng=None`` it would
    silently fall back to the process-global ``random`` module — so proving
    it is never called at all is the strongest available evidence that no
    such fallback path exists.
    """

    adapter_class = _RNG_REQUIRED_ADAPTER_CLASSES[strategy_id]
    history = _synthetic_causal_240_stride8_v1()
    with (
        patch.object(adapter_class, "__init__", autospec=True) as spy_init,
        pytest.raises(FreezeIdentityMismatchError) as exc_info,
    ):
        produce_fixed13_member(
            strategy_id=strategy_id,
            official_draw_identity=_TEST_DRAW_IDENTITY,
            freeze_sha256_hex="0" * 64,
            causal_history=history,
        )
    spy_init.assert_not_called()
    assert exc_info.value.disposition == "PRE_OUTCOME_INELIGIBLE"


# --- Test G: provenance ------------------------------------------------------


def test_provenance_fields_present_for_rng_required_member() -> None:
    record = produce_fixed13_member(
        strategy_id="legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6",
        official_draw_identity=_TEST_DRAW_IDENTITY,
        freeze_sha256_hex=_FREEZE_SHA256,
        causal_history=_synthetic_causal_240_stride8_v1(),
    )
    assert record.rng_policy_id == "TARGET_BOUND_DETERMINISTIC_V1"
    assert record.rng_domain_tag == "LOTTOLAB_FIXED13_PROSPECTIVE_RNG_V1"
    assert record.rng_seed_derivation_formula
    assert record.per_member_rng_required is True
    seed_hex = record.per_member_rng_seed_sha256_hex
    assert seed_hex is not None
    assert len(seed_hex) == 64
    assert record.per_member_adapter_path == (
        "lottolab.strategies.adapters.biglotto_frontend_auto_optimize:"
        "BigLottoFrontendAutoOptimizeAdapter"
    )
    assert record.per_member_adapter_construction is AdapterConstruction.RNG_INJECTED
    assert len(record.per_member_causal_history_digest) == 64
    assert record.causal_history_row_count == 240
    assert record.causal_history_last_draw_identity == "SYNTHETIC-000240"
    assert record.producer_implementation_identity.repository_head
    assert record.producer_implementation_identity.repository_tree
    assert record.producer_implementation_identity.module_path == (
        "lottolab.application.fixed13_prospective_producer"
    )
    assert "CPython" in record.python_implementation_identity
    assert record.rng_selfcheck_vector is not None
    assert len(record.rng_selfcheck_vector) == 3
    assert record.historical_r2_ticket_parity_note == "NOT_ASSERTED_FOR_THE_THREE_MEMBERS"


def test_provenance_fields_null_for_zero_arg_member() -> None:
    record = produce_fixed13_member(
        strategy_id="biglotto_p0_2bet_bet1",
        official_draw_identity=_TEST_DRAW_IDENTITY,
        freeze_sha256_hex=_FREEZE_SHA256,
        causal_history=_synthetic_causal_240_stride8_v1(),
    )
    assert record.per_member_rng_required is False
    assert record.per_member_rng_seed_sha256_hex is None
    assert record.rng_selfcheck_vector is None
    assert record.per_member_adapter_construction is AdapterConstruction.ZERO_ARG_DEFAULT
    assert record.historical_r2_ticket_parity_note == "NOT_APPLICABLE_ZERO_ARG_MEMBER"
    assert record.producer_implementation_identity.repository_head


def test_producer_implementation_identity_matches_live_repository_head() -> None:
    import subprocess
    from pathlib import Path

    record = produce_fixed13_member(
        strategy_id="biglotto_p0_2bet_bet1",
        official_draw_identity=_TEST_DRAW_IDENTITY,
        freeze_sha256_hex=_FREEZE_SHA256,
        causal_history=_synthetic_causal_240_stride8_v1(),
    )
    repo_root = Path(__file__).resolve().parents[2]
    live_head = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    # Deliberately compared live rather than pinned to a literal: HEAD moves
    # with every commit, unlike the other golden fields in this file.
    assert record.producer_implementation_identity.repository_head == live_head


def test_selfcheck_vector_does_not_advance_the_producer_rng() -> None:
    strategy_id = "legacy_biglotto__frontend_ml_features__3a4324bc2aa9"
    history = _synthetic_causal_240_stride8_v1()

    record = produce_fixed13_member(
        strategy_id=strategy_id,
        official_draw_identity=_TEST_DRAW_IDENTITY,
        freeze_sha256_hex=_FREEZE_SHA256,
        causal_history=history,
    )
    seed_hex = record.per_member_rng_seed_sha256_hex
    assert seed_hex is not None
    seed_int = int(seed_hex, 16)

    # Independently confirm the reported selfcheck vector against a fresh
    # Random(seed_int) with zero prior draws.
    reference_rng = random_module.Random(seed_int)
    expected_selfcheck = (
        reference_rng.random(),
        reference_rng.random(),
        reference_rng.random(),
    )
    assert record.rng_selfcheck_vector == expected_selfcheck

    # If computing the selfcheck vector had advanced the SAME Random instance
    # later handed to the strategy, the producer's ticket would only be
    # reproducible from a Random(seed_int) that already had 3 draws consumed.
    # A truly pristine Random(seed_int) must instead match the producer ticket
    # exactly.
    pristine_rng = random_module.Random(seed_int)
    pristine_adapter = BigLottoFrontendMLFeatureWeightedAdapter(rng=pristine_rng)
    pristine_execution = pristine_adapter.get_one_bet_with_emission(history, LotteryType.BIG_LOTTO)
    assert pristine_execution.legal_main_numbers == record.execution.legal_main_numbers
