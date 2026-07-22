from __future__ import annotations

import dataclasses

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategy_success_measurement import (
    DEFAULT_WINDOW_POLICY,
    DEFAULT_WINDOW_POLICY_VERSION,
    BigLottoOutcomeSignature,
    BigLottoPortfolioOutcomeSignature,
    Daily539OutcomeSignature,
    EvidenceStatus,
    MeasurementMode,
    MeasurementProvenance,
    MeasurementWindowPolicy,
    OutcomeEligibility,
    PowerLottoOutcomeSignature,
    SelectionIdentity,
    StrategySuccessMeasurement,
    WindowRole,
)


def _provenance(*, complete: bool = False) -> MeasurementProvenance:
    if not complete:
        return MeasurementProvenance(strategy_version="v1")
    return MeasurementProvenance(
        strategy_version="v1",
        parameter_or_config_identity="config:sha256:abc",
        history_cutoff="2026-001",
        target_draw="2026-002",
        window_policy_version=DEFAULT_WINDOW_POLICY_VERSION,
        game_rule_version="rules-v1",
        selection_family_identity="family-a",
        source_artifact_identity="artifact:sha256:def",
    )


def _big_selection(**overrides: object) -> SelectionIdentity:
    values: dict[str, object] = {
        "lottery": LotteryType.BIG_LOTTO,
        "strategy_id": "strategy_2bet",
        "strategy_version": "v1",
    }
    values.update(overrides)
    return SelectionIdentity(**values)  # type: ignore[arg-type]


def _measurement(
    *,
    mode: MeasurementMode = MeasurementMode.CANDIDATE_COVERAGE,
    selection: SelectionIdentity | None = None,
    outcome: BigLottoOutcomeSignature
    | BigLottoPortfolioOutcomeSignature
    | PowerLottoOutcomeSignature
    | Daily539OutcomeSignature
    | None = None,
    status: EvidenceStatus = EvidenceStatus.DESCRIPTIVE_ONLY,
    provenance: MeasurementProvenance | None = None,
    official_prize_tier_id: str | None = None,
) -> StrategySuccessMeasurement:
    if outcome is None:
        outcome = (
            BigLottoPortfolioOutcomeSignature((BigLottoOutcomeSignature(2, True),))
            if mode is MeasurementMode.LEGAL_TICKET_PRIZE
            else BigLottoOutcomeSignature(2, True)
        )
    return StrategySuccessMeasurement(
        mode=mode,
        selection=selection or _big_selection(candidate_k=6),
        outcome_signature=outcome,
        evidence_status=status,
        provenance=provenance or _provenance(),
        official_prize_tier_id=official_prize_tier_id,
    )


def test_selection_axes_remain_independent_and_display_name_is_not_parsed() -> None:
    selection = _big_selection(
        candidate_k=6,
        max_bet_index=2,
        ticket_count=10,
        cost_units=500.0,
    )

    assert selection.candidate_k == 6
    assert selection.max_bet_index == 2
    assert selection.ticket_count == 10
    assert selection.cost_units == 500.0
    assert _big_selection().candidate_k is None
    assert _big_selection().ticket_count is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candidate_k", 0),
        ("max_bet_index", 0),
        ("ticket_count", 0),
        ("cost_units", -0.01),
        ("cost_units", float("inf")),
    ],
)
def test_selection_rejects_invalid_numeric_axes(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _big_selection(**{field: value})


def test_candidate_coverage_requires_candidate_k_not_other_k_axes() -> None:
    with pytest.raises(ValueError, match="requires candidate_k"):
        _measurement(selection=_big_selection(max_bet_index=6, ticket_count=6))


def test_legal_ticket_prize_requires_ticket_data_not_candidate_quota() -> None:
    with pytest.raises(ValueError, match="requires ticket_count"):
        _measurement(
            mode=MeasurementMode.LEGAL_TICKET_PRIZE,
            selection=_big_selection(candidate_k=6),
        )


def test_measurement_modes_cannot_masquerade_as_official_tiers() -> None:
    selection = _big_selection(ticket_count=1)
    with pytest.raises(ValueError, match="distinct from official-tier"):
        _measurement(
            mode=MeasurementMode.LEGAL_TICKET_PRIZE,
            selection=selection,
            official_prize_tier_id="GENERAL",
        )
    official = _measurement(
        mode=MeasurementMode.OFFICIAL_PRIZE_TIER,
        selection=selection,
        official_prize_tier_id="GENERAL",
    )
    assert official.mode is MeasurementMode.OFFICIAL_PRIZE_TIER


def test_default_window_policy_pins_roles_and_non_independence() -> None:
    assert DEFAULT_WINDOW_POLICY.policy_version == DEFAULT_WINDOW_POLICY_VERSION
    assert DEFAULT_WINDOW_POLICY.full_history_role is WindowRole.REFERENCE_ONLY
    assert (DEFAULT_WINDOW_POLICY.long_draws, DEFAULT_WINDOW_POLICY.long_role) == (
        750,
        WindowRole.PRIMARY_EVIDENCE,
    )
    assert (DEFAULT_WINDOW_POLICY.medium_draws, DEFAULT_WINDOW_POLICY.medium_role) == (
        300,
        WindowRole.STABILITY_CONFIRMATION,
    )
    assert (DEFAULT_WINDOW_POLICY.short_draws, DEFAULT_WINDOW_POLICY.short_role) == (
        50,
        WindowRole.DEGRADATION_VETO,
    )
    assert DEFAULT_WINDOW_POLICY.nested_windows_independent is False


def test_window_policy_rejects_invalid_order_and_independence_claim() -> None:
    with pytest.raises(ValueError, match="long > medium > short"):
        MeasurementWindowPolicy(policy_version="v2", long_draws=300, medium_draws=300)
    with pytest.raises(ValueError, match="not independent"):
        MeasurementWindowPolicy(policy_version="v2", nested_windows_independent=True)


def test_full_history_and_short_window_cannot_promote() -> None:
    with pytest.raises(ValueError, match="REFERENCE_ONLY"):
        MeasurementWindowPolicy(
            policy_version="v2",
            full_history_role=WindowRole.PROMOTION_FILTER,
        )
    with pytest.raises(ValueError, match="cannot independently promote"):
        MeasurementWindowPolicy(
            policy_version="v2",
            short_role=WindowRole.PRIMARY_EVIDENCE,
        )


def test_custom_windows_require_new_policy_version() -> None:
    with pytest.raises(ValueError, match="new policy_version"):
        MeasurementWindowPolicy(long_draws=800)
    assert MeasurementWindowPolicy(policy_version="v2", long_draws=800).long_draws == 800


def test_big_lotto_outcome_represents_m2_special_without_claiming_a_tier() -> None:
    signature = BigLottoOutcomeSignature(main_hits=2, special_hit=True)
    measurement = _measurement(outcome=signature)

    assert signature.diagnostic_signature == "M2+SPECIAL"
    assert measurement.official_prize_tier_id is None


def test_big_lotto_portfolio_preserves_source_order_duplicates_and_derived_identity() -> None:
    first = BigLottoOutcomeSignature(main_hits=1, special_hit=True)
    second = BigLottoOutcomeSignature(main_hits=4, special_hit=False)
    portfolio = BigLottoPortfolioOutcomeSignature((first, second, first))

    assert portfolio.tickets == (first, second, first)
    assert portfolio.ticket_count == 3
    assert portfolio.maximum_main_hits == 4
    assert not hasattr(portfolio, "special_hit")
    assert not hasattr(portfolio, "diagnostic_signature")
    assert portfolio.canonical_json() == (
        '{"maximum_main_hits":4,"ticket_count":3,"tickets":['
        '{"diagnostic_signature":"M1+SPECIAL","main_hits":1,"special_hit":true},'
        '{"diagnostic_signature":"M4","main_hits":4,"special_hit":false},'
        '{"diagnostic_signature":"M1+SPECIAL","main_hits":1,"special_hit":true}]}'
    )
    assert portfolio.canonical_json() == portfolio.canonical_json()
    with pytest.raises(dataclasses.FrozenInstanceError):
        portfolio.tickets = (second,)  # type: ignore[misc]


def test_big_lotto_portfolio_requires_a_nonempty_exact_tuple_of_atomic_outcomes() -> None:
    ticket = BigLottoOutcomeSignature(2, False)

    assert BigLottoPortfolioOutcomeSignature((ticket,)).ticket_count == 1
    with pytest.raises(ValueError, match="immutable tuple"):
        BigLottoPortfolioOutcomeSignature([ticket])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must not be empty"):
        BigLottoPortfolioOutcomeSignature(())
    with pytest.raises(ValueError, match="only BigLottoOutcomeSignature"):
        BigLottoPortfolioOutcomeSignature((object(),))  # type: ignore[arg-type]


def test_big_lotto_measurement_modes_require_their_exact_outcome_contracts() -> None:
    atomic = BigLottoOutcomeSignature(2, True)
    portfolio = BigLottoPortfolioOutcomeSignature((atomic,))

    with pytest.raises(ValueError, match="does not match"):
        _measurement(outcome=portfolio)
    with pytest.raises(ValueError, match="does not match"):
        _measurement(
            mode=MeasurementMode.LEGAL_TICKET_PRIZE,
            selection=_big_selection(ticket_count=1),
            outcome=atomic,
        )
    with pytest.raises(ValueError, match="ticket_count must match"):
        _measurement(
            mode=MeasurementMode.LEGAL_TICKET_PRIZE,
            selection=_big_selection(ticket_count=2),
            outcome=portfolio,
        )
    with pytest.raises(ValueError, match="does not match"):
        _measurement(
            mode=MeasurementMode.OFFICIAL_PRIZE_TIER,
            selection=_big_selection(ticket_count=1),
            outcome=portfolio,
            official_prize_tier_id="GENERAL",
        )


@pytest.mark.parametrize("main_hits", [-1, 7])
def test_big_lotto_outcome_rejects_invalid_hits(main_hits: int) -> None:
    with pytest.raises(ValueError):
        BigLottoOutcomeSignature(main_hits=main_hits, special_hit=False)


def test_power_lotto_represents_m1_zone2_and_missing_prediction_separately() -> None:
    hit = PowerLottoOutcomeSignature(zone1_hits=1, zone2_hit=True)
    miss = PowerLottoOutcomeSignature(zone1_hits=1, zone2_hit=False)
    missing = PowerLottoOutcomeSignature(
        zone1_hits=1,
        zone2_hit=None,
        eligibility=OutcomeEligibility.MISSING_PREDICTED_SECOND_ZONE,
    )

    assert hit.diagnostic_signature == "ZONE1_M1+ZONE2"
    assert miss.diagnostic_signature == "ZONE1_M1"
    assert missing.zone2_hit is None
    assert missing.eligibility is OutcomeEligibility.MISSING_PREDICTED_SECOND_ZONE
    assert missing != miss


def test_power_lotto_missing_state_cannot_be_encoded_as_a_miss() -> None:
    with pytest.raises(ValueError, match="requires zone2_hit=None"):
        PowerLottoOutcomeSignature(
            zone1_hits=1,
            zone2_hit=False,
            eligibility=OutcomeEligibility.MISSING_PREDICTED_SECOND_ZONE,
        )
    with pytest.raises(ValueError, match="requires a boolean"):
        PowerLottoOutcomeSignature(zone1_hits=1, zone2_hit=None)


@pytest.mark.parametrize("zone1_hits", [-1, 7])
def test_power_lotto_rejects_invalid_zone1_hits(zone1_hits: int) -> None:
    with pytest.raises(ValueError):
        PowerLottoOutcomeSignature(zone1_hits=zone1_hits, zone2_hit=False)


def test_daily_539_has_only_main_hits() -> None:
    assert Daily539OutcomeSignature(main_hits=5).diagnostic_signature == "M5"
    with pytest.raises(ValueError):
        Daily539OutcomeSignature(main_hits=6)
    with pytest.raises(TypeError):
        Daily539OutcomeSignature(main_hits=2, special_hit=True)  # type: ignore[call-arg]


def test_outcome_type_must_match_lottery() -> None:
    with pytest.raises(ValueError, match="does not match"):
        _measurement(
            selection=SelectionIdentity(
                lottery=LotteryType.DAILY_539,
                strategy_id="daily",
                candidate_k=5,
            ),
            outcome=BigLottoOutcomeSignature(2, False),
        )


def test_descriptive_status_does_not_imply_production_eligibility() -> None:
    measurement = _measurement(status=EvidenceStatus.DESCRIPTIVE_ONLY)
    assert measurement.production_eligible is False


def test_incomplete_provenance_cannot_be_production_eligible() -> None:
    with pytest.raises(ValueError, match="complete provenance"):
        _measurement(status=EvidenceStatus.PRODUCTION_ELIGIBLE)
    assert _measurement(
        status=EvidenceStatus.PRODUCTION_ELIGIBLE,
        provenance=_provenance(complete=True),
    ).production_eligible


def test_strategy_and_window_policy_versions_remain_explicit_and_consistent() -> None:
    with pytest.raises(ValueError, match="strategy versions must match"):
        _measurement(provenance=MeasurementProvenance(strategy_version="v2"))
    with pytest.raises(ValueError, match="window policy version"):
        _measurement(
            provenance=MeasurementProvenance(
                strategy_version="v1",
                window_policy_version="other-policy",
            )
        )


def test_immutable_equality_and_canonical_serialization_are_deterministic() -> None:
    first = _measurement()
    second = _measurement()

    assert first == second
    assert first.canonical_json() == second.canonical_json()
    assert '"candidate_k":6' in first.canonical_json()
    assert '"max_bet_index":null' in first.canonical_json()
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.selection.candidate_k = 9  # type: ignore[misc]
