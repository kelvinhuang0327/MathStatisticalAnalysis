"""Adversarial coverage for the V1B evaluation-evidence materializer.

Every artifact here is synthetic and lives only in memory or a pytest-owned
temporary directory. Nothing in this module reads a production draw database,
writes a real evidence artifact, or touches the canonical evidence registry.

Two properties get the most attention because they are the ones that would
quietly turn evidence into fiction if they broke: a BIG_LOTTO ticket must
never acquire a special number it did not predict, and an exact evaluator
``Fraction`` must survive the round trip without being rounded into a decimal.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    LOTTERY_RULE_CONTRACTS,
    resolve_lottery_rule_contract,
    score_big_lotto_ticket,
)
from lottolab.domain.replay_predictions import ReplayPredictionSnapshot, ReplaySourceMode
from lottolab.evidence import canonical_json, validator
from lottolab.evidence.method_evaluation_materialization import (
    REPLAY_TICKET_SPECIAL_NUMBER_COUNT,
    V1B_METRIC_IDS,
    EvidenceProducerIdentity,
    MethodEvaluationMaterializationError,
    load_metric_definition_bindings,
    materialize_method_evaluation_evidence,
)
from lottolab.evidence.models import (
    DatasetSnapshot,
    DrawEntry,
    EvidenceStatus,
    ExactRational,
    FindingCategory,
    RuleParameters,
    StrategyEvaluationEvidence,
)
from lottolab.research.base_method_evaluation import (
    BASE_METHOD_EVALUATOR_SEMANTIC_VERSION,
    HIT_TIER_IDS,
    WINDOW_SIZES,
    HitTierDefinition,
    LotteryMatchContract,
    MethodEvaluationRecord,
    ReplayStatus,
)
from lottolab.research.replay_method_evaluation import (
    ReplayTargetOutcome,
    evaluate_replayed_single_ticket_method,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/evidence/synthetic"

DRAW_COUNT = 60
DATASET_ID = "SYNTHETIC_V1B_MATERIALIZATION"
STRATEGY_ID = "synthetic_v1b_strategy"


# --------------------------------------------------------------------------
# Synthetic world
# --------------------------------------------------------------------------


def _draw_id(index: int) -> str:
    return str(115000000 + index)


def _draw_date(index: int) -> date:
    return date.fromordinal(date(2025, 1, 1).toordinal() + index * 3)


def _main_numbers(index: int) -> tuple[int, ...]:
    numbers = sorted({(index * 7 + offset * 5) % 49 + 1 for offset in range(6)})
    extra = 1
    while len(numbers) < 6:
        candidate = (index + extra * 13) % 49 + 1
        if candidate not in numbers:
            numbers.append(candidate)
        numbers = sorted(numbers)
        extra += 1
    return tuple(numbers[:6])


def _special_number(index: int, main_numbers: tuple[int, ...]) -> int:
    for offset in range(1, 60):
        candidate = (index * 11 + offset) % 49 + 1
        if candidate not in main_numbers:
            return candidate
    raise AssertionError("no legal special number available")


def _predicted_main_numbers(index: int) -> tuple[int, ...]:
    return tuple(sorted({(index * 3 + offset * 6) % 49 + 1 for offset in range(6)} | {1, 2, 3}))[:6]


def _rule_parameters(**overrides: Any) -> RuleParameters:
    contract = BIG_LOTTO_RULE_CONTRACT
    payload: dict[str, Any] = {
        "main_number_count": contract.main_number_count,
        "main_number_min": contract.main_number_min,
        "main_number_max": contract.main_number_max,
        "main_numbers_unique": contract.main_numbers_unique,
        "special_number_count": contract.special_number_count,
        "special_number_min": contract.special_number_min,
        "special_number_max": contract.special_number_max,
        "special_numbers_unique": contract.special_numbers_unique,
        "main_special_overlap_allowed": contract.main_special_overlap_allowed,
        "rule_contract_version": contract.contract_version,
        **overrides,
    }
    payload["rule_parameters_sha256"] = canonical_json.sha256_hex(
        canonical_json.canonical_bytes(payload)
    )
    return RuleParameters.model_validate(payload)


def _dataset() -> DatasetSnapshot:
    draws: list[DrawEntry] = []
    for index in range(DRAW_COUNT):
        main_numbers = _main_numbers(index)
        draws.append(
            DrawEntry(
                draw_id=_draw_id(index),
                draw_sequence=index,
                draw_date=_draw_date(index),
                main_numbers=main_numbers,
                special_numbers=(_special_number(index, main_numbers),),
            )
        )
    payload: dict[str, Any] = {
        "schema_id": "lottolab.evidence.dataset_snapshot",
        "schema_version": "1.0.0",
        "dataset_id": DATASET_ID,
        "dataset_version": "1.0.0",
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "rule_binding": _rule_parameters().model_dump(mode="json", exclude_none=True),
        "source_provenance": {
            "kind": "SYNTHETIC",
            "declared_description": "v1b materialization unit fixture",
        },
        "draws": [draw.model_dump(mode="json", exclude_none=True) for draw in draws],
    }
    payload["dataset_sha256"] = canonical_json.sha256_hex(canonical_json.canonical_bytes(payload))
    return DatasetSnapshot.model_validate(payload)


def _snapshot(index: int, **overrides: Any) -> ReplayPredictionSnapshot:
    fields: dict[str, Any] = {
        "snapshot_schema_version": "1.0.0",
        "dataset_id": DATASET_ID,
        "dataset_version": "1.0.0",
        "lottery_type": LotteryType.BIG_LOTTO,
        "source_mode": ReplaySourceMode.TARGET_NATIVE,
        "target_draw_number": _draw_id(index),
        "target_draw_date": _draw_date(index),
        "cutoff_draw_number": _draw_id(index - 1),
        "cutoff_draw_date": _draw_date(index - 1),
        "strategy_id": STRATEGY_ID,
        "strategy_version": "v1",
        "adapter_strategy_id": STRATEGY_ID,
        "adapter_strategy_name": "Synthetic V1B",
        "adapter_strategy_version": "v1",
        "history_status": "OK",
        "history_reason_code": None,
        "causal_history_count": index,
        "causal_history_sha256": "0" * 64,
        "prediction_status": "OK",
        "prediction_reason_code": None,
        "predicted_main_numbers": _predicted_main_numbers(index),
        "result_sha256": "1" * 64,
        **overrides,
    }
    return ReplayPredictionSnapshot(**fields)


def _snapshots() -> tuple[ReplayPredictionSnapshot, ...]:
    return tuple(_snapshot(index) for index in range(1, DRAW_COUNT))


def _producer() -> EvidenceProducerIdentity:
    definition = REPO_ROOT / "contracts/evidence/metric_definitions/avg_match.json"
    return EvidenceProducerIdentity(
        artifact_id_prefix="SYNTHETIC_V1B_MATERIALIZATION",
        evidence_status=EvidenceStatus.SYNTHETIC_TEST_ONLY,
        produced_at=datetime(2026, 8, 26, tzinfo=UTC),
        producer_name="lottolab-method-evaluation-materializer",
        method_source_git_oid="a" * 40,
        feature_version="v1",
        feature_definition_path="contracts/evidence/metric_definitions/avg_match.json",
        feature_definition_sha256=canonical_json.sha256_hex(definition.read_bytes()),
    )


def _materialize(
    *, dataset: DatasetSnapshot | None = None, snapshots: Any = None
) -> tuple[StrategyEvaluationEvidence, ...]:
    dataset = dataset if dataset is not None else _dataset()
    snapshots = snapshots if snapshots is not None else _snapshots()
    outcomes = tuple(
        ReplayTargetOutcome(
            draw_number=snapshot.target_draw_number,
            draw_date=snapshot.target_draw_date,
            main_numbers=next(
                draw.main_numbers
                for draw in dataset.draws
                if draw.draw_id == snapshot.target_draw_number
            ),
        )
        for snapshot in snapshots
    )
    record = evaluate_replayed_single_ticket_method(
        snapshots,
        outcomes,
        method_family="SYNTHETIC_V1B",
        replay_status=ReplayStatus.BASELINE_RECORDED,
    )
    return materialize_method_evaluation_evidence(
        dataset=dataset,
        snapshots=snapshots,
        evaluation=record,
        metric_definitions=load_metric_definition_bindings(REPO_ROOT),
        producer=_producer(),
    )


POWER_LOTTO_MATCH_CONTRACT = LotteryMatchContract(
    lottery_type=LotteryType.POWER_LOTTO.value,
    population_size=38,
    winning_number_count=6,
    ticket_number_count=6,
    hit_tiers=tuple(
        HitTierDefinition(tier_id, minimum)
        for minimum, tier_id in enumerate(HIT_TIER_IDS, start=1)
    ),
)


def _power_lotto_world() -> tuple[DatasetSnapshot, tuple[ReplayPredictionSnapshot, ...]]:
    """A POWER_LOTTO dataset/replay pair, used only to prove fail-closed behavior."""

    contract = resolve_lottery_rule_contract(LotteryType.POWER_LOTTO, LOTTERY_RULE_CONTRACTS)
    assert contract is not None
    rule_payload: dict[str, Any] = {
        "main_number_count": contract.main_number_count,
        "main_number_min": contract.main_number_min,
        "main_number_max": contract.main_number_max,
        "main_numbers_unique": contract.main_numbers_unique,
        "special_number_count": contract.special_number_count,
        "special_number_min": contract.special_number_min,
        "special_number_max": contract.special_number_max,
        "special_numbers_unique": contract.special_numbers_unique,
        "main_special_overlap_allowed": contract.main_special_overlap_allowed,
        "rule_contract_version": contract.contract_version,
    }
    rule_payload["rule_parameters_sha256"] = canonical_json.sha256_hex(
        canonical_json.canonical_bytes(rule_payload)
    )

    def main_numbers(index: int) -> tuple[int, ...]:
        numbers = sorted({(index * 5 + offset * 3) % 38 + 1 for offset in range(6)})
        extra = 1
        while len(numbers) < 6:
            candidate = (index + extra * 7) % 38 + 1
            if candidate not in numbers:
                numbers.append(candidate)
            numbers = sorted(numbers)
            extra += 1
        return tuple(numbers[:6])

    draws = [
        DrawEntry(
            draw_id=_draw_id(index),
            draw_sequence=index,
            draw_date=_draw_date(index),
            main_numbers=main_numbers(index),
            special_numbers=(index % 8 + 1,),
        )
        for index in range(40)
    ]
    payload: dict[str, Any] = {
        "schema_id": "lottolab.evidence.dataset_snapshot",
        "schema_version": "1.0.0",
        "dataset_id": "SYNTHETIC_V1B_POWER",
        "dataset_version": "1.0.0",
        "lottery_type": LotteryType.POWER_LOTTO.value,
        "rule_binding": rule_payload,
        "source_provenance": {"kind": "SYNTHETIC", "declared_description": "power fail-closed"},
        "draws": [draw.model_dump(mode="json", exclude_none=True) for draw in draws],
    }
    payload["dataset_sha256"] = canonical_json.sha256_hex(canonical_json.canonical_bytes(payload))
    snapshots = tuple(
        _snapshot(
            index,
            lottery_type=LotteryType.POWER_LOTTO,
            dataset_id="SYNTHETIC_V1B_POWER",
            predicted_main_numbers=main_numbers(index + 1),
        )
        for index in range(1, 40)
    )
    return DatasetSnapshot.model_validate(payload), snapshots


def _evaluation_record(
    dataset: DatasetSnapshot | None = None, snapshots: Any = None
) -> MethodEvaluationRecord:
    dataset = dataset if dataset is not None else _dataset()
    snapshots = snapshots if snapshots is not None else _snapshots()
    outcomes = tuple(
        ReplayTargetOutcome(
            draw_number=snapshot.target_draw_number,
            draw_date=snapshot.target_draw_date,
            main_numbers=next(
                draw.main_numbers
                for draw in dataset.draws
                if draw.draw_id == snapshot.target_draw_number
            ),
        )
        for snapshot in snapshots
    )
    return evaluate_replayed_single_ticket_method(
        snapshots,
        outcomes,
        method_family="SYNTHETIC_V1B",
        replay_status=ReplayStatus.BASELINE_RECORDED,
    )


def _daily_539_world() -> tuple[
    DatasetSnapshot, tuple[ReplayPredictionSnapshot, ...], LotteryMatchContract
]:
    """A DAILY_539 world: five main numbers and no special number at all."""

    contract = resolve_lottery_rule_contract(LotteryType.DAILY_539, LOTTERY_RULE_CONTRACTS)
    assert contract is not None
    rule_payload: dict[str, Any] = {
        "main_number_count": contract.main_number_count,
        "main_number_min": contract.main_number_min,
        "main_number_max": contract.main_number_max,
        "main_numbers_unique": contract.main_numbers_unique,
        "special_number_count": contract.special_number_count,
        "special_number_min": contract.special_number_min,
        "special_number_max": contract.special_number_max,
        "special_numbers_unique": contract.special_numbers_unique,
        "main_special_overlap_allowed": contract.main_special_overlap_allowed,
        "rule_contract_version": contract.contract_version,
    }
    rule_payload["rule_parameters_sha256"] = canonical_json.sha256_hex(
        canonical_json.canonical_bytes(rule_payload)
    )

    def main_numbers(index: int) -> tuple[int, ...]:
        numbers = sorted({(index * 5 + offset * 4) % 39 + 1 for offset in range(5)})
        extra = 1
        while len(numbers) < 5:
            candidate = (index + extra * 11) % 39 + 1
            if candidate not in numbers:
                numbers.append(candidate)
            numbers = sorted(numbers)
            extra += 1
        return tuple(numbers[:5])

    draws = [
        DrawEntry(
            draw_id=_draw_id(index),
            draw_sequence=index,
            draw_date=_draw_date(index),
            main_numbers=main_numbers(index),
            special_numbers=(),
        )
        for index in range(40)
    ]
    payload: dict[str, Any] = {
        "schema_id": "lottolab.evidence.dataset_snapshot",
        "schema_version": "1.0.0",
        "dataset_id": "SYNTHETIC_V1B_DAILY",
        "dataset_version": "1.0.0",
        "lottery_type": LotteryType.DAILY_539.value,
        "rule_binding": rule_payload,
        "source_provenance": {"kind": "SYNTHETIC", "declared_description": "daily539 shape"},
        "draws": [draw.model_dump(mode="json", exclude_none=True) for draw in draws],
    }
    payload["dataset_sha256"] = canonical_json.sha256_hex(canonical_json.canonical_bytes(payload))
    snapshots = tuple(
        _snapshot(
            index,
            lottery_type=LotteryType.DAILY_539,
            dataset_id="SYNTHETIC_V1B_DAILY",
            predicted_main_numbers=main_numbers(index + 2),
        )
        for index in range(1, 40)
    )
    match_contract = LotteryMatchContract(
        lottery_type=LotteryType.DAILY_539.value,
        population_size=39,
        winning_number_count=5,
        ticket_number_count=5,
        hit_tiers=tuple(
            HitTierDefinition(tier_id, minimum)
            for minimum, tier_id in enumerate(HIT_TIER_IDS, start=1)
        ),
    )
    return DatasetSnapshot.model_validate(payload), snapshots, match_contract


def _report(
    artifact: StrategyEvaluationEvidence, dataset: DatasetSnapshot
) -> validator.ValidationReport:
    return validator.validate_evidence_artifact(artifact, repo_root=REPO_ROOT, dataset=dataset)


def _codes(report: validator.ValidationReport) -> set[str]:
    return {finding.code for finding in report.findings}


# --------------------------------------------------------------------------
# Artifact shape: four windows, five metrics, evaluator order
# --------------------------------------------------------------------------


def test_one_evaluation_yields_exactly_four_artifacts_in_evaluator_order():
    artifacts = _materialize()
    assert len(artifacts) == 4
    expected = [kind.value for kind, _ in WINDOW_SIZES]
    assert expected == ["WINDOW_50", "WINDOW_300", "WINDOW_750", "FULL_HISTORY"]
    assert [artifact.artifact_id.split("MATERIALIZATION_")[1] for artifact in artifacts] == expected


def test_every_artifact_carries_exactly_the_five_observed_metrics():
    for artifact in _materialize():
        assert [result.metric_id for result in artifact.metric_results] == list(V1B_METRIC_IDS)
        assert len(artifact.metric_results) == 5


def test_window_50_selects_the_last_fifty_draws_and_full_history_selects_all():
    by_id = {artifact.artifact_id: artifact for artifact in _materialize()}
    window_50 = by_id["SYNTHETIC_V1B_MATERIALIZATION_WINDOW_50"]
    full = by_id["SYNTHETIC_V1B_MATERIALIZATION_FULL_HISTORY"]
    assert len(window_50.records) == 50
    assert len(full.records) == DRAW_COUNT - 1
    assert full.records[-1].target.draw_id == window_50.records[-1].target.draw_id


def test_metric_sample_sizes_follow_the_committed_definition_sample_unit():
    for artifact in _materialize():
        draws = len(artifact.records)
        tickets = sum(len(record.tickets) for record in artifact.records)
        for result in artifact.metric_results:
            expected = draws if result.sample_unit.value == "DRAWS" else tickets
            assert result.sample_size == expected, result.metric_id


def test_all_four_artifacts_validate_with_no_findings():
    dataset = _dataset()
    for artifact in _materialize(dataset=dataset):
        report = _report(artifact, dataset)
        assert report.findings == (), (artifact.artifact_id, report.findings)
        assert report.structurally_valid


# --------------------------------------------------------------------------
# Ticket shape: a BIG_LOTTO ticket predicts no special number
# --------------------------------------------------------------------------


def test_biglotto_evidence_declares_a_zero_ticket_special_number_count():
    for artifact in _materialize():
        assert artifact.rule_parameters.ticket_special_number_count == 0
        assert artifact.rule_parameters.special_number_count == 1
        assert artifact.rule_parameters.resolved_ticket_special_number_count == 0
    assert REPLAY_TICKET_SPECIAL_NUMBER_COUNT == 0


def test_no_biglotto_ticket_ever_declares_a_special_number():
    for artifact in _materialize():
        for record in artifact.records:
            for ticket in record.tickets:
                assert ticket.special_numbers == ()


def test_actual_special_numbers_come_from_the_dataset_snapshot():
    dataset = _dataset()
    by_draw_id = {draw.draw_id: draw for draw in dataset.draws}
    for artifact in _materialize(dataset=dataset):
        for record in artifact.records:
            source = by_draw_id[record.target.draw_id]
            assert record.actual_special_numbers == source.special_numbers
            assert record.actual_main_numbers == source.main_numbers


def test_special_hit_matches_the_committed_domain_scoring_authority_row_by_row():
    dataset = _dataset()
    by_draw_id = {draw.draw_id: draw for draw in dataset.draws}
    compared = 0
    for artifact in _materialize(dataset=dataset):
        for record in artifact.records:
            draw = by_draw_id[record.target.draw_id]
            for ticket in record.tickets:
                expected = score_big_lotto_ticket(
                    predicted_main_numbers=ticket.main_numbers,
                    winning_main_numbers=draw.main_numbers,
                    winning_special_number=draw.special_numbers[0],
                )
                assert ticket.special_hit is expected.special_hit
                assert ticket.main_hit_count == expected.main_hits
                compared += 1
    assert compared > 0


def test_at_least_one_special_hit_is_true_so_the_oracle_is_load_bearing():
    """A branch that always answered False would pass a weaker version of the
    row-by-row check above; prove the oracle actually discriminates."""

    hits = {
        ticket.special_hit
        for artifact in _materialize()
        for record in artifact.records
        for ticket in record.tickets
    }
    assert hits == {True, False}


def test_validator_special_hit_delegates_to_the_domain_authority(monkeypatch: Any):
    """No second prize/scoring table: flip the domain oracle and the verdict follows."""

    dataset = _dataset()
    artifact = _materialize(dataset=dataset)[0]
    assert _report(artifact, dataset).findings == ()

    class _Inverted:
        def __init__(self, real: Any) -> None:
            self.real = real

        def __call__(self, **kwargs: Any) -> Any:
            scored = self.real(**kwargs)
            return type(scored)(main_hits=scored.main_hits, special_hit=not scored.special_hit)

    monkeypatch.setattr(
        validator, "score_big_lotto_ticket", _Inverted(score_big_lotto_ticket)
    )
    assert "SPECIAL_HIT_MISMATCH" in _codes(_report(artifact, dataset))


def test_zero_ticket_shape_without_committed_authority_fails_closed():
    """POWER_LOTTO draws a special number but has no committed ticket-scoring
    authority, so special_hit must be reported unverifiable, never assumed."""

    artifact = _materialize()[0]
    relabelled = artifact.model_copy(
        update={
            "dataset_reference": artifact.dataset_reference.model_copy(
                update={"lottery_type": LotteryType.POWER_LOTTO}
            )
        }
    )
    report = validator.validate_evidence_artifact(relabelled, repo_root=REPO_ROOT, dataset=None)
    assert "TICKET_SPECIAL_HIT_AUTHORITY_UNAVAILABLE" in _codes(report)
    assert any(
        finding.category is FindingCategory.UNVERIFIED_PROVENANCE
        and finding.code == "TICKET_SPECIAL_HIT_AUTHORITY_UNAVAILABLE"
        for finding in report.findings
    )
    assert not report.canonical_gate_passed


def test_materializer_refuses_a_lottery_without_committed_scoring_authority():
    """POWER_LOTTO draws a special number the ticket never picks, and no
    committed authority can score it, so no evidence may be produced at all."""

    dataset, snapshots = _power_lotto_world()
    outcomes = tuple(
        ReplayTargetOutcome(
            draw_number=snapshot.target_draw_number,
            draw_date=snapshot.target_draw_date,
            main_numbers=next(
                draw.main_numbers
                for draw in dataset.draws
                if draw.draw_id == snapshot.target_draw_number
            ),
        )
        for snapshot in snapshots
    )
    record = evaluate_replayed_single_ticket_method(
        snapshots,
        outcomes,
        method_family="SYNTHETIC_V1B_POWER",
        replay_status=ReplayStatus.BASELINE_RECORDED,
        contract=POWER_LOTTO_MATCH_CONTRACT,
    )
    with pytest.raises(MethodEvaluationMaterializationError, match="scoring authority"):
        materialize_method_evaluation_evidence(
            dataset=dataset,
            snapshots=snapshots,
            evaluation=record,
            metric_definitions=load_metric_definition_bindings(REPO_ROOT),
            producer=_producer(),
            contract=POWER_LOTTO_MATCH_CONTRACT,
        )


def test_materializer_refuses_a_dataset_its_match_contract_does_not_describe():
    dataset = _dataset().model_copy(update={"lottery_type": LotteryType.POWER_LOTTO})
    snapshots = _snapshots()
    record = evaluate_replayed_single_ticket_method(
        snapshots,
        tuple(
            ReplayTargetOutcome(
                draw_number=snapshot.target_draw_number,
                draw_date=snapshot.target_draw_date,
                main_numbers=_main_numbers(int(snapshot.target_draw_number) - 115000000),
            )
            for snapshot in snapshots
        ),
        method_family="SYNTHETIC_V1B",
        replay_status=ReplayStatus.BASELINE_RECORDED,
    )
    with pytest.raises(MethodEvaluationMaterializationError, match="match contract"):
        materialize_method_evaluation_evidence(
            dataset=dataset,
            snapshots=snapshots,
            evaluation=record,
            metric_definitions=load_metric_definition_bindings(REPO_ROOT),
            producer=_producer(),
        )


# --------------------------------------------------------------------------
# Exact rational values
# --------------------------------------------------------------------------


def test_metric_values_are_exact_rationals_not_rounded_decimals():
    for artifact in _materialize():
        for result in artifact.metric_results:
            assert isinstance(result.value, ExactRational), result.metric_id


def test_evaluator_fractions_survive_model_to_lcj_to_load_unchanged():
    dataset = _dataset()
    artifacts = _materialize(dataset=dataset)
    record = _evaluation_record()
    for artifact, (window_kind, _) in zip(artifacts, WINDOW_SIZES, strict=True):
        block = record.windows[window_kind]
        reloaded = StrategyEvaluationEvidence.model_validate(
            canonical_json.loads_canonical(
                canonical_json.canonical_bytes(
                    artifact.model_dump(mode="json", exclude_none=True)
                )
            )
        )
        for result in reloaded.metric_results:
            assert isinstance(result.value, ExactRational)
            round_tripped = Fraction(result.value.numerator, result.value.denominator)
            assert round_tripped == block.metrics[result.metric_id].observed_value


def test_a_thirty_six_forty_ninths_style_value_is_exactly_representable():
    value = Fraction(36, 49)
    rational = ExactRational(numerator=value.numerator, denominator=value.denominator)
    raw = canonical_json.canonical_bytes(rational.model_dump(mode="json"))
    assert raw == b'{"denominator":49,"numerator":36}'
    reloaded = ExactRational.model_validate(canonical_json.loads_canonical(raw))
    assert Fraction(reloaded.numerator, reloaded.denominator) == value


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"numerator": 72, "denominator": 98}, "not reduced"),
        ({"numerator": 1, "denominator": 0}, "zero denominator"),
        ({"numerator": 1, "denominator": -2}, "negative denominator"),
        ({"numerator": 0, "denominator": 5}, "non-canonical zero"),
        ({"numerator": canonical_json.MAX_SAFE_INTEGER + 1, "denominator": 1}, "over LCJ bound"),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_non_canonical_rational_forms_are_rejected(payload: dict[str, int], reason: str):
    with pytest.raises(ValueError):
        ExactRational.model_validate(payload)
    del reason


def test_one_mathematical_value_has_exactly_one_serialized_form():
    canonical = ExactRational(numerator=-3, denominator=7)
    assert canonical_json.canonical_bytes(canonical.model_dump(mode="json")) == (
        b'{"denominator":7,"numerator":-3}'
    )
    with pytest.raises(ValueError):
        ExactRational.model_validate({"numerator": 3, "denominator": -7})
    with pytest.raises(ValueError):
        ExactRational.model_validate({"numerator": -6, "denominator": 14})


def test_no_float_ever_appears_in_a_canonical_artifact():
    for artifact in _materialize():
        raw = canonical_json.canonical_bytes(artifact.model_dump(mode="json", exclude_none=True))
        canonical_json.validate_value_domain(canonical_json.loads_canonical(raw))
        for result in artifact.metric_results:
            assert not isinstance(result.value, float)


def test_decimal_scale_never_quantizes_an_exact_rational():
    """The committed definitions declare a decimal scale; an exact rational is
    already lossless and must not be measured against it."""

    dataset = _dataset()
    for artifact in _materialize(dataset=dataset):
        assert "METRIC_VALUE_SCALE_MISMATCH" not in _codes(_report(artifact, dataset))


@pytest.mark.parametrize(
    ("decimal_value", "expect_mismatch"),
    [("0.5", True), ("0.500000000000", False)],
)
def test_decimal_values_still_obey_their_declared_scale(
    decimal_value: str, expect_mismatch: bool
):
    """Widening the value type must not stop decimals being scale-checked."""

    dataset = _dataset()
    artifact = _materialize(dataset=dataset)[0]
    rescaled = artifact.model_copy(
        update={
            "metric_results": (
                artifact.metric_results[0].model_copy(update={"value": decimal_value}),
                *artifact.metric_results[1:],
            )
        }
    )
    codes = _codes(_report(rescaled, dataset))
    assert ("METRIC_VALUE_SCALE_MISMATCH" in codes) is expect_mismatch


# --------------------------------------------------------------------------
# Backward compatibility
# --------------------------------------------------------------------------


COMMITTED_EVIDENCE_FIXTURES = (
    "evaluation_evidence.json",
    "historical_replay_evidence.json",
)


@pytest.mark.parametrize("name", COMMITTED_EVIDENCE_FIXTURES)
def test_committed_legacy_evidence_still_validates(name: str):
    report = validator.validate_evidence_file(
        FIXTURE_DIR / name,
        repo_root=REPO_ROOT,
        dataset_path=FIXTURE_DIR / "dataset_snapshot.json",
    )
    assert report.schema_valid
    assert report.structurally_valid, report.findings


@pytest.mark.parametrize("name", (*COMMITTED_EVIDENCE_FIXTURES, "dataset_snapshot.json"))
def test_committed_rule_bindings_keep_their_declared_hash(name: str):
    """The optional ticket-shape key is excluded from canonical bytes when
    absent, so no committed document's hash may move."""

    document: dict[str, Any] = json.loads((FIXTURE_DIR / name).read_bytes())
    key = "rule_binding" if "rule_binding" in document else "rule_parameters"
    binding = RuleParameters.model_validate(document[key])
    assert binding.ticket_special_number_count is None
    dumped = binding.model_dump(mode="json", exclude_none=True)
    assert "ticket_special_number_count" not in dumped
    assert (
        canonical_json.self_key_removed_sha256(dumped, "rule_parameters_sha256")
        == document[key]["rule_parameters_sha256"]
    )


def test_legacy_documents_resolve_the_ticket_shape_to_the_draw_shape():
    document: dict[str, Any] = json.loads((FIXTURE_DIR / "evaluation_evidence.json").read_bytes())
    binding = RuleParameters.model_validate(document["rule_parameters"])
    assert binding.ticket_special_number_count is None
    assert binding.resolved_ticket_special_number_count == binding.special_number_count == 1


def test_legacy_ticket_overlap_semantics_are_preserved_where_tickets_pick_specials():
    """The committed fixture's tickets do declare special numbers; their
    special_hit must still be recomputed by overlap, not by a scoring oracle."""

    document: dict[str, Any] = json.loads((FIXTURE_DIR / "evaluation_evidence.json").read_bytes())
    tickets = [ticket for record in document["records"] for ticket in record["tickets"]]
    assert tickets and all(ticket["special_numbers"] for ticket in tickets)
    report = validator.validate_evidence_file(
        FIXTURE_DIR / "evaluation_evidence.json",
        repo_root=REPO_ROOT,
        dataset_path=FIXTURE_DIR / "dataset_snapshot.json",
    )
    assert "SPECIAL_HIT_MISMATCH" not in _codes(report)
    assert "TICKET_SPECIAL_HIT_AUTHORITY_UNAVAILABLE" not in _codes(report)


def test_a_lottery_that_draws_no_special_number_keeps_its_original_semantics():
    """DAILY_539 resolves a ticket shape of zero by legacy fallback, but nothing
    is drawn to hit, so the overlap rule stays correct and no oracle is needed."""

    dataset, snapshots, contract = _daily_539_world()
    outcomes = tuple(
        ReplayTargetOutcome(
            draw_number=snapshot.target_draw_number,
            draw_date=snapshot.target_draw_date,
            main_numbers=next(
                draw.main_numbers
                for draw in dataset.draws
                if draw.draw_id == snapshot.target_draw_number
            ),
        )
        for snapshot in snapshots
    )
    record = evaluate_replayed_single_ticket_method(
        snapshots,
        outcomes,
        method_family="SYNTHETIC_V1B_DAILY",
        replay_status=ReplayStatus.BASELINE_RECORDED,
        contract=contract,
    )
    artifacts = materialize_method_evaluation_evidence(
        dataset=dataset,
        snapshots=snapshots,
        evaluation=record,
        metric_definitions=load_metric_definition_bindings(REPO_ROOT),
        producer=_producer(),
        contract=contract,
    )
    for artifact in artifacts:
        assert artifact.rule_parameters.special_number_count == 0
        assert artifact.rule_parameters.resolved_ticket_special_number_count == 0
        report = _report(artifact, dataset)
        assert "TICKET_SPECIAL_HIT_AUTHORITY_UNAVAILABLE" not in _codes(report)
        assert "SPECIAL_HIT_MISMATCH" not in _codes(report)
        for evaluation_record in artifact.records:
            for ticket in evaluation_record.tickets:
                assert ticket.special_hit is False


def test_evidence_schema_version_is_unchanged():
    for artifact in _materialize():
        assert artifact.schema_version == "1.0.0"
    assert _dataset().schema_version == "1.0.0"


# --------------------------------------------------------------------------
# Evaluator identity and parity
# --------------------------------------------------------------------------


def test_evaluator_semantic_version_is_bound_into_every_artifact():
    for artifact in _materialize():
        assert artifact.parameters == {
            "base_method_evaluator_semantic_version": BASE_METHOD_EVALUATOR_SEMANTIC_VERSION
        }
        assert artifact.parameters_sha256 == canonical_json.sha256_hex(
            canonical_json.canonical_bytes(artifact.parameters)
        )


def test_evaluator_semantic_version_is_not_the_strategy_method_version():
    artifact = _materialize()[0]
    assert artifact.method_version != BASE_METHOD_EVALUATOR_SEMANTIC_VERSION
    assert artifact.strategy_version != BASE_METHOD_EVALUATOR_SEMANTIC_VERSION


def test_materialization_never_perturbs_the_evaluator_record():
    """Direct evaluator output -- including random_reference and delta_vs_random,
    which V1B deliberately does not persist -- must be bit-for-bit unchanged."""

    dataset = _dataset()
    before = _evaluation_record(dataset=dataset)
    _materialize(dataset=dataset)
    after = _evaluation_record(dataset=dataset)
    assert before == after
    for window_kind, _ in WINDOW_SIZES:
        for metric_id, cell in before.windows[window_kind].metrics.items():
            other = after.windows[window_kind].metrics[metric_id]
            assert cell.random_reference == other.random_reference
            assert cell.delta_vs_random == other.delta_vs_random
            assert cell.observed_value == other.observed_value


def test_persisted_metric_values_equal_the_direct_evaluator_observed_values():
    dataset = _dataset()
    record = _evaluation_record(dataset=dataset)
    for artifact, (window_kind, _) in zip(_materialize(dataset=dataset), WINDOW_SIZES, strict=True):
        for result in artifact.metric_results:
            assert isinstance(result.value, ExactRational)
            assert Fraction(result.value.numerator, result.value.denominator) == (
                record.windows[window_kind].metrics[result.metric_id].observed_value
            )


def test_random_reference_and_delta_are_not_persisted_as_metric_identities():
    persisted = {
        result.metric_id
        for artifact in _materialize()
        for result in artifact.metric_results
    }
    assert persisted == set(V1B_METRIC_IDS)
    assert not any("RANDOM" in metric_id or "DELTA" in metric_id for metric_id in persisted)


# --------------------------------------------------------------------------
# Determinism and the read-only load boundary
# --------------------------------------------------------------------------


def test_identical_inputs_produce_byte_identical_artifacts_and_hashes():
    dataset = _dataset()
    first = _materialize(dataset=dataset)
    second = _materialize(dataset=dataset)
    assert first == second
    for left, right in zip(first, second, strict=True):
        left_bytes = canonical_json.canonical_bytes(
            left.model_dump(mode="json", exclude_none=True)
        )
        right_bytes = canonical_json.canonical_bytes(
            right.model_dump(mode="json", exclude_none=True)
        )
        assert left_bytes == right_bytes
        assert left.artifact_content_sha256 == right.artifact_content_sha256
        assert canonical_json.sha256_hex(left_bytes) == canonical_json.sha256_hex(right_bytes)


def test_declared_artifact_and_record_hashes_recompute():
    for artifact in _materialize():
        assert artifact.artifact_content_sha256 == validator.recompute_self_hash(
            artifact, excluded_key="artifact_content_sha256"
        )
        for record in artifact.records:
            assert record.record_sha256 == validator.recompute_self_hash(
                record, excluded_key="record_sha256"
            )


def test_validated_load_round_trips_to_identical_canonical_bytes(tmp_path: Path):
    dataset = _dataset()
    dataset_path = tmp_path / "dataset_snapshot.json"
    dataset_path.write_bytes(
        canonical_json.canonical_file_bytes(dataset.model_dump(mode="json", exclude_none=True))
    )
    for artifact in _materialize(dataset=dataset):
        original = canonical_json.canonical_file_bytes(
            artifact.model_dump(mode="json", exclude_none=True)
        )
        evidence_path = tmp_path / f"{artifact.artifact_id}.json"
        evidence_path.write_bytes(original)

        report = validator.validate_evidence_file(
            evidence_path, repo_root=REPO_ROOT, dataset_path=dataset_path
        )
        assert report.schema_valid
        assert report.findings == (), (artifact.artifact_id, report.findings)

        reloaded, load_findings = validator.load_evidence(evidence_path)
        assert load_findings == []
        assert reloaded is not None
        assert canonical_json.canonical_file_bytes(
            reloaded.model_dump(mode="json", exclude_none=True)
        ) == original


def test_materialization_writes_nothing_to_the_canonical_evidence_registry(tmp_path: Path):
    registry = REPO_ROOT / "contracts/evidence/canonical_evidence_registry.json"
    before = registry.read_bytes()
    _materialize()
    assert registry.read_bytes() == before
    assert validator.load_canonical_evidence_registry(registry) == frozenset()
    assert not any(path.exists() for path in (tmp_path / "evidence", tmp_path / "research.db"))


# --------------------------------------------------------------------------
# Fail-closed binding
# --------------------------------------------------------------------------


def test_a_target_absent_from_the_dataset_fails_closed():
    dataset = _dataset()
    trimmed = dataset.model_copy(update={"draws": dataset.draws[:-1]})
    with pytest.raises(MethodEvaluationMaterializationError, match="absent from the dataset"):
        materialize_method_evaluation_evidence(
            dataset=trimmed,
            snapshots=_snapshots(),
            evaluation=_evaluation_record(),
            metric_definitions=load_metric_definition_bindings(REPO_ROOT),
            producer=_producer(),
        )


def test_a_target_date_disagreement_fails_closed():
    snapshots = (*_snapshots()[:-1], _snapshot(DRAW_COUNT - 1, target_draw_date=date(2031, 1, 1)))
    with pytest.raises(MethodEvaluationMaterializationError, match="but the snapshot targets"):
        materialize_method_evaluation_evidence(
            dataset=_dataset(),
            snapshots=snapshots,
            evaluation=_evaluation_record(),
            metric_definitions=load_metric_definition_bindings(REPO_ROOT),
            producer=_producer(),
        )


def test_a_dataset_identity_disagreement_fails_closed():
    snapshots = (*_snapshots()[:-1], _snapshot(DRAW_COUNT - 1, dataset_id="SOMETHING_ELSE"))
    with pytest.raises(MethodEvaluationMaterializationError, match="was replayed against dataset"):
        materialize_method_evaluation_evidence(
            dataset=_dataset(),
            snapshots=snapshots,
            evaluation=_evaluation_record(),
            metric_definitions=load_metric_definition_bindings(REPO_ROOT),
            producer=_producer(),
        )


def test_an_evaluation_record_from_different_inputs_fails_closed():
    snapshots = _snapshots()
    foreign = _evaluation_record(snapshots=snapshots[:-1])
    with pytest.raises(MethodEvaluationMaterializationError, match="does not match an evaluation"):
        materialize_method_evaluation_evidence(
            dataset=_dataset(),
            snapshots=snapshots,
            evaluation=foreign,
            metric_definitions=load_metric_definition_bindings(REPO_ROOT),
            producer=_producer(),
        )


def test_a_non_uniform_walk_forward_lag_fails_closed():
    """The existing EvaluationWindows contract declares one lag for the whole
    artifact; a replay that does not have one must not be described by it."""

    snapshots = (
        *_snapshots()[:-1],
        _snapshot(
            DRAW_COUNT - 1,
            cutoff_draw_number=_draw_id(DRAW_COUNT - 3),
            cutoff_draw_date=_draw_date(DRAW_COUNT - 3),
        ),
    )
    with pytest.raises(
        MethodEvaluationMaterializationError, match="EVALUATION_WINDOW_MAPPING_UNRESOLVED"
    ):
        materialize_method_evaluation_evidence(
            dataset=_dataset(),
            snapshots=snapshots,
            evaluation=_evaluation_record(snapshots=snapshots),
            metric_definitions=load_metric_definition_bindings(REPO_ROOT),
            producer=_producer(),
        )


def test_a_ticket_that_is_not_in_canonical_order_is_refused_not_reordered():
    snapshots = (
        *_snapshots()[:-1],
        _snapshot(DRAW_COUNT - 1, predicted_main_numbers=(6, 5, 4, 3, 2, 1)),
    )
    with pytest.raises(MethodEvaluationMaterializationError, match="canonical ascending order"):
        materialize_method_evaluation_evidence(
            dataset=_dataset(),
            snapshots=snapshots,
            evaluation=_evaluation_record(snapshots=snapshots),
            metric_definitions=load_metric_definition_bindings(REPO_ROOT),
            producer=_producer(),
        )


def test_metric_definition_bindings_come_from_the_committed_files():
    bindings = load_metric_definition_bindings(REPO_ROOT)
    assert set(bindings) == set(V1B_METRIC_IDS)
    for metric_id, binding in bindings.items():
        path = REPO_ROOT / binding.definition_path
        assert binding.definition_sha256 == canonical_json.sha256_hex(path.read_bytes())
        document: dict[str, Any] = json.loads(path.read_bytes())
        assert document["metric_id"] == metric_id
        assert binding.sample_unit.value == document["sample_unit"]
        assert binding.aggregation == document["aggregation"]
