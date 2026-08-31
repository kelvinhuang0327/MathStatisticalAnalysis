"""Synthetic-only conformance tests for the sealed T540 inference ledger."""

from __future__ import annotations

import copy
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest
from tools import run_t540_anytime_valid_inference_ledger as ledger

SYNTHETIC_TARGET_START = 900_000_000


def _synthetic_result(
    target: int,
    *,
    outcomes: tuple[int, int, int] = (0, 0, 0),
    status: str = ledger.VALID_PROSPECTIVE_STATUS,
    counts_as_valid: bool = True,
) -> dict[str, object]:
    """Build a full 30x3 score shape without an official-outcome fixture."""

    a_success, b_success, c_success = outcomes
    experiments: list[object] = []
    for k in ledger.K_VALUES:
        for window_label, window_size in ledger.WINDOWS:
            experiments.append(
                {
                    "arms": [
                        {
                            "arm": ledger.ARM_A,
                            "official_any_prize_success": a_success,
                        },
                        {
                            "arm": ledger.ARM_B,
                            "official_any_prize_success": b_success,
                        },
                        {
                            "arm": ledger.ARM_C,
                            "official_any_prize_success": c_success,
                        },
                    ],
                    "experiment_id": f"T539:K{k}:{window_label}",
                    "k": k,
                    "window": window_size,
                    "window_label": window_label,
                }
            )
    result: dict[str, object] = {
        "counts_as_valid_prospective_observation": counts_as_valid,
        "experiments": experiments,
        "freeze_manifest_sha256": ledger.FREEZE_SHA256,
        "input_authority": {"sha256": "1" * 64},
        "official_outcome_sha256": "2" * 64,
        "pretarget_seal_status": "PRETARGET_SEAL_CONFIRMED_BEFORE_OUTCOME",
        "pretarget_snapshot_content_hash": "3" * 64,
        "prospective_observation_status": status,
        "rule_fingerprint": ledger.RULE_FINGERPRINT,
        "schema_version": ledger.SOURCE_RESULT_SCHEMA_VERSION,
        "score_status": ledger.VALID_SCORE_STATUS,
        "surface": {
            "arm_record_count": 90,
            "arms": list(ledger.ARMS),
            "experiment_count": 30,
            "k_values": list(ledger.K_VALUES),
            "windows": [{"label": label, "size": size} for label, size in ledger.WINDOWS],
        },
        "target_identity": str(target),
    }
    result["result_content_hash"] = ledger.result_content_hash(result)
    return result


def _direct_integral(sequence: tuple[int, ...], delta: Fraction) -> Fraction:
    """Independently expand the shifted-null integrand and integrate it."""

    polynomial = [Fraction(1)]
    for difference in sequence:
        slope = Fraction(difference - delta, 1 + delta)
        updated = [Fraction(0)] * (len(polynomial) + 1)
        for degree, coefficient in enumerate(polynomial):
            updated[degree] += coefficient
            updated[degree + 1] += coefficient * slope
        polynomial = updated
    return sum(
        (coefficient / (degree + 1) for degree, coefficient in enumerate(polynomial)),
        start=Fraction(0),
    )


def test_frozen_surface_has_exactly_60_ordered_unique_streams() -> None:
    assert len(ledger.STREAM_IDENTITIES) == 60
    assert len(set(ledger.STREAM_IDENTITIES)) == 60
    assert ledger.STREAM_IDENTITIES[0] == "T539:K1:W50:B_MINUS_A"
    assert ledger.STREAM_IDENTITIES[-1] == "T539:K25:W750:B_MINUS_C"


def test_exact_paired_counts_and_delta_hat() -> None:
    counts = ledger.paired_counts([(1, 1), (1, 0), (0, 1), (0, 0)])

    assert counts == ledger.PairedCounts(n11=1, n10=1, n01=1, n00=1)
    assert counts.n == 4
    assert counts.delta_hat == 0


@pytest.mark.parametrize(
    ("sequence", "delta"),
    [
        ((1, 0, -1, 1), Fraction(-1, 2)),
        ((0, 1, 0, -1), Fraction(0)),
        ((-1, 1, 1, 0), Fraction(1, 3)),
        ((1, -1, 0), Fraction(1)),
    ],
)
def test_shifted_null_positive_term_matches_direct_exact_integral(
    sequence: tuple[int, ...], delta: Fraction
) -> None:
    assert ledger.e_value(sequence, delta) == _direct_integral(sequence, delta)


def test_delta_zero_frozen_formula_parity_with_direct_integral() -> None:
    sequence = (1, 0, -1, 1, -1, 0, 1)
    expected = _direct_integral(sequence, Fraction(0))

    assert ledger.e_value(sequence, Fraction(0)) == expected
    assert ledger.e_value_from_counts(p=3, z=2, r=2, delta=Fraction(0)) == expected


def test_boundary_semantics_are_exact() -> None:
    assert ledger.e_value((), Fraction(-1)) == 1
    assert ledger.e_value((-1, -1), Fraction(-1)) == Fraction(1, 3)
    assert ledger.e_value((-1, 0), Fraction(-1)) == ledger.POSITIVE_INFINITY
    assert ledger.running_max_e_value((-1, -1), Fraction(-1)) == 1
    assert ledger.running_max_e_value((-1, 0), Fraction(-1)) == ledger.POSITIVE_INFINITY
    assert ledger.running_max_e_value((1, -1, 0), Fraction(1)) == 1


def test_empty_and_all_minus_one_have_empty_rejection_set() -> None:
    empty = ledger.lower_confidence_sequence_bracket(())
    all_minus_one = ledger.lower_confidence_sequence_bracket((-1, -1, -1))

    assert empty.lower == empty.upper == -1
    assert all_minus_one.lower == all_minus_one.upper == -1
    assert empty.bisections == all_minus_one.bisections == 0


@pytest.mark.parametrize(
    ("sequence", "exact_lower"),
    [
        ((0,), Fraction(-2398, 2399)),
        ((1,), Fraction(-2397, 2399)),
        ((-1, 1), Fraction(-3598, 3599)),
    ],
)
def test_reference_lower_endpoints_are_enclosed_by_exact_49_bisections(
    sequence: tuple[int, ...], exact_lower: Fraction
) -> None:
    bracket = ledger.lower_confidence_sequence_bracket(sequence)

    assert bracket.bisections == 49
    assert bracket.width == Fraction(1, 2**48)
    assert bracket.lower <= exact_lower < bracket.upper


def test_running_max_inversion_retains_first_prefix_lower_bound() -> None:
    first_prefix = ledger.lower_confidence_sequence_bracket((1,))
    reversed_after_crossing = ledger.lower_confidence_sequence_bracket((1, -1))

    assert reversed_after_crossing == first_prefix
    assert reversed_after_crossing.lower <= Fraction(-2397, 2399) < reversed_after_crossing.upper


def test_13_and_14_consecutive_positive_differences_straddle_confirmation() -> None:
    thirteen = ledger.running_max_e_value((1,) * 13, Fraction(0))
    fourteen = ledger.running_max_e_value((1,) * 14, Fraction(0))

    assert thirteen == Fraction(16383, 14)
    assert fourteen == Fraction(32767, 15)
    assert isinstance(thirteen, Fraction)
    assert isinstance(fourteen, Fraction)
    assert thirteen < ledger.CONFIRMATORY_THRESHOLD
    assert fourteen > ledger.CONFIRMATORY_THRESHOLD
    assert ledger.lower_confidence_sequence_bracket((1,) * 13).lower < 0
    assert ledger.lower_confidence_sequence_bracket((1,) * 14).lower >= 0


def test_600_and_1200_thresholds_and_adjusted_anytime_p_use_equality() -> None:
    at_600 = ledger.evidence_threshold_flags(Fraction(600))
    at_1200 = ledger.evidence_threshold_flags(Fraction(1200))

    assert at_600 == {
        "confirmatory_crossing": False,
        "supports_further_study_threshold_crossing": True,
    }
    assert at_1200 == {
        "confirmatory_crossing": True,
        "supports_further_study_threshold_crossing": True,
    }
    assert ledger.adjusted_anytime_p_value(Fraction(60)) == 1
    assert ledger.adjusted_anytime_p_value(Fraction(600)) == Fraction(1, 10)
    assert ledger.adjusted_anytime_p_value(Fraction(1200)) == Fraction(1, 20)


def test_whole_target_is_validated_before_any_partial_cell_ingestion() -> None:
    state = ledger.initial_state()
    incomplete = _synthetic_result(SYNTHETIC_TARGET_START)
    cast(list[object], incomplete["experiments"]).pop()
    incomplete["result_content_hash"] = ledger.result_content_hash(incomplete)
    before = ledger.canonical_json_bytes(state)

    with pytest.raises(ledger.LedgerContractError, match="INCOMPLETE_FROZEN"):
        ledger.ingest_target_result(state, incomplete)

    assert ledger.canonical_json_bytes(state) == before
    assert all(
        cast(dict[str, int], stream["counts"])["N"] == 0
        for stream in cast(list[dict[str, object]], state["streams"])
    )


def test_missed_seal_is_recorded_separately_with_zero_confirmatory_denominator() -> None:
    missed = _synthetic_result(
        SYNTHETIC_TARGET_START,
        status="MISSED_PRETARGET_SEAL",
        counts_as_valid=False,
    )

    result = ledger.ingest_target_result(ledger.initial_state(), missed)

    assert result.disposition == "EXCLUDED_NO_CONFIRMATORY_DENOMINATOR"
    assert result.state["accepted_target_identities"] == []
    assert result.state["processed_target_identities"] == [str(SYNTHETIC_TARGET_START)]
    assert len(cast(list[object], result.state["technical_exclusions"])) == 1
    assert all(
        cast(dict[str, int], stream["counts"])["N"] == 0
        for stream in cast(list[dict[str, object]], result.state["streams"])
    )


def test_incomplete_invalid_target_records_actual_arm_count_without_ingestion() -> None:
    incomplete = _synthetic_result(
        SYNTHETIC_TARGET_START,
        status="INCOMPLETE_FROZEN_EXPERIMENT_SURFACE",
        counts_as_valid=False,
    )
    first_experiment = cast(list[dict[str, object]], incomplete["experiments"])[0]
    cast(list[object], first_experiment["arms"]).pop()
    incomplete["result_content_hash"] = ledger.result_content_hash(incomplete)

    result = ledger.ingest_target_result(ledger.initial_state(), incomplete)
    exclusion = cast(list[dict[str, object]], result.state["technical_exclusions"])[0]
    source = cast(dict[str, object], exclusion["source"])

    assert result.disposition == "EXCLUDED_NO_CONFIRMATORY_DENOMINATOR"
    assert source["raw_arm_record_count"] == 89
    assert result.state["accepted_target_identities"] == []


def test_acceptance_preserves_raw_source_hashes_and_all_60_paired_records() -> None:
    source = _synthetic_result(SYNTHETIC_TARGET_START, outcomes=(0, 1, 0))
    result = ledger.ingest_target_result(ledger.initial_state(), source)
    target = cast(list[dict[str, object]], result.state["accepted_targets"])[0]
    source_reference = cast(dict[str, object], target["source"])

    assert result.disposition == "ACCEPTED"
    assert source_reference["raw_arm_record_count"] == 90
    assert source_reference["result_content_hash"] == source["result_content_hash"]
    assert len(cast(list[object], target["paired_records"])) == 60
    assert all(
        cast(dict[str, object], record)["d"] == 1
        for record in cast(list[object], target["paired_records"])
    )


def test_exact_duplicate_is_idempotent_and_changed_duplicate_conflicts() -> None:
    source = _synthetic_result(SYNTHETIC_TARGET_START)
    accepted = ledger.ingest_target_result(ledger.initial_state(), source).state
    before = ledger.canonical_json_bytes(accepted)

    repeated = ledger.ingest_target_result(accepted, source)
    assert repeated.disposition == "EXACT_IDEMPOTENT_NO_OP"
    assert ledger.canonical_json_bytes(repeated.state) == before

    conflicting = copy.deepcopy(source)
    first_experiment = cast(list[dict[str, object]], conflicting["experiments"])[0]
    first_arm = cast(list[dict[str, object]], first_experiment["arms"])[0]
    first_arm["official_any_prize_success"] = 1
    conflicting["result_content_hash"] = ledger.result_content_hash(conflicting)
    with pytest.raises(ledger.LedgerConflictError, match="CONFLICT"):
        ledger.ingest_target_result(accepted, conflicting)


def test_restart_replay_and_deterministic_serialization_are_byte_exact(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    assert ledger.initialize_state_file(path) == "CREATED"
    before = path.read_bytes()
    result = ledger.ingest_target_result(
        ledger.load_state_file(path),
        _synthetic_result(SYNTHETIC_TARGET_START, outcomes=(1, 0, 0)),
    )
    assert ledger.persist_state_update(path, result.state, expected=before)

    persisted = path.read_bytes()
    replayed = ledger.load_state_file(path)
    assert persisted == ledger.canonical_json_bytes(replayed)
    assert persisted == ledger.canonical_json_bytes(result.state)
    assert ledger.validate_and_replay_state(replayed) == replayed


def test_replay_rejects_derived_evidence_tampering() -> None:
    accepted = ledger.ingest_target_result(
        ledger.initial_state(), _synthetic_result(SYNTHETIC_TARGET_START)
    ).state
    tampered = copy.deepcopy(accepted)
    first_stream = cast(list[dict[str, object]], tampered["streams"])[0]
    running_m = cast(dict[str, int], first_stream["running_m0"])
    running_m["numerator"] += 1

    with pytest.raises(ledger.LedgerContractError, match="STATE_REPLAY_MISMATCH"):
        ledger.validate_and_replay_state(tampered)


def test_no_reset_after_evidence_and_no_reset_command(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    assert ledger.initialize_state_file(path) == "CREATED"
    assert ledger.initialize_state_file(path) == "EXACT_IDEMPOTENT_NO_OP"
    before = path.read_bytes()
    accepted = ledger.ingest_target_result(
        ledger.load_state_file(path), _synthetic_result(SYNTHETIC_TARGET_START)
    ).state
    ledger.persist_state_update(path, accepted, expected=before)

    with pytest.raises(ledger.NoResetError, match="NO_RESET_AFTER_EVIDENCE"):
        ledger.initialize_state_file(path)
    with pytest.raises(SystemExit):
        ledger.main(["reset"])


def test_reporting_cadence_uses_one_common_denominator_and_all_60_streams() -> None:
    state = ledger.initial_state()
    for offset in range(50):
        # All -1 differences keep confidence inversion cheap and cannot trigger efficacy.
        state = ledger.ingest_target_result(
            state,
            _synthetic_result(SYNTHETIC_TARGET_START + offset, outcomes=(1, 0, 1)),
        ).state

    reporting = cast(dict[str, object], state["reporting"])
    report = ledger.report_payload(state)
    assert reporting["common_denominator"] == 50
    assert reporting["scheduled_denominators_reached"] == [50]
    assert reporting["formal_cadence_due"] is True
    assert reporting["formal_report_required"] is True
    assert reporting["stream_coverage_count"] == 60
    assert len(cast(list[object], report["streams"])) == 60
    assert all(
        cast(dict[str, int], stream["counts"])["N"] == 50
        for stream in cast(list[dict[str, object]], report["streams"])
    )


def test_full_surface_stop_requires_all_60_confirmatory_positive_streams() -> None:
    state = ledger.initial_state()
    for offset in range(13):
        state = ledger.ingest_target_result(
            state,
            _synthetic_result(SYNTHETIC_TARGET_START + offset, outcomes=(0, 1, 0)),
        ).state

    thirteen_status = cast(dict[str, object], state["evidence_status"])
    assert thirteen_status["experiment_status"] == "ACTIVE"
    assert thirteen_status["all_60_streams_confirmatory"] is False
    assert {
        cast(dict[str, object], cell)["status"]
        for cell in cast(list[object], thirteen_status["cells"])
    } == {"SUPPORTS_FURTHER_STUDY"}

    stopped = ledger.ingest_target_result(
        state,
        _synthetic_result(SYNTHETIC_TARGET_START + 13, outcomes=(0, 1, 0)),
    ).state
    stopped_status = cast(dict[str, object], stopped["evidence_status"])
    reporting = cast(dict[str, object], stopped["reporting"])
    assert stopped_status["all_60_streams_confirmatory"] is True
    assert stopped_status["all_60_current_delta_hat_positive"] is True
    assert stopped_status["full_surface_efficacy_stop"] is True
    assert stopped_status["experiment_status"] == "EFFICACY_STOPPED_ALL_60_STREAMS"
    assert reporting["terminal_report_due"] is True
    assert reporting["formal_report_required"] is True
    assert reporting["formal_cadence_due"] is False
    assert {
        cast(dict[str, object], cell)["status"]
        for cell in cast(list[object], stopped_status["cells"])
    } == {"PREDICTIVE_ADVANTAGE_ESTABLISHED_AT_K_AND_WINDOW"}

    with pytest.raises(ledger.LedgerContractError, match="TERMINAL"):
        ledger.ingest_target_result(
            stopped,
            _synthetic_result(SYNTHETIC_TARGET_START + 14, outcomes=(0, 1, 0)),
        )


def test_administrative_termination_preserves_evidence_and_forces_terminal_report() -> None:
    accepted = ledger.ingest_target_result(
        ledger.initial_state(),
        _synthetic_result(SYNTHETIC_TARGET_START, outcomes=(1, 0, 1)),
    ).state
    before_targets = accepted["accepted_targets"]

    terminated = ledger.administratively_terminate(accepted, reason="synthetic test closure")

    assert terminated["accepted_targets"] == before_targets
    assert (
        cast(dict[str, object], terminated["evidence_status"])["experiment_status"]
        == "ADMINISTRATIVELY_TERMINATED"
    )
    assert cast(dict[str, object], terminated["reporting"])["terminal_report_due"] is True


def test_contract_generation_is_twice_byte_identical_and_contains_no_real_results(
    tmp_path: Path,
) -> None:
    first = ledger.statistical_contract_bytes()
    second = ledger.statistical_contract_bytes()
    output = tmp_path / "contract.json"

    assert first == second
    assert ledger.write_contract_file(output) is True
    assert ledger.write_contract_file(output) is False
    assert output.read_bytes() == first
    assert ledger.load_contract_file(output) == ledger.statistical_contract()
    contract = ledger.statistical_contract()
    integrity = cast(dict[str, object], contract["integrity"])
    frozen_surface = cast(dict[str, object], contract["frozen_surface"])
    e_process = cast(dict[str, object], contract["e_process"])
    assert integrity["real_future_outcome_access"] == "NO"
    assert integrity["prospective_observations_at_contract_freeze"] == 0
    assert integrity["embedded_real_results"] == []
    assert frozen_surface["arms"] == {
        "A": ledger.ARM_A,
        "B": ledger.ARM_B,
        "C": ledger.ARM_C,
    }
    assert frozen_surface["stream_count"] == 60
    assert e_process["lambda_support"] == "[0,1/(1+delta)]"
    assert e_process["lambda_density"] == "1+delta"
    assert contract["statistical_contract_fingerprint"] == (
        ledger.statistical_contract_fingerprint()
    )


def test_synthetic_cli_build_init_ingest_and_report_entry_path(tmp_path: Path) -> None:
    contract_path = tmp_path / "contract.json"
    state_path = tmp_path / "state.json"
    source_path = tmp_path / "synthetic-target.json"
    report_path = tmp_path / "report.json"

    assert ledger.main(["build-contract", "--output-json", str(contract_path)]) == 0
    assert (
        ledger.main(
            [
                "init",
                "--state-json",
                str(state_path),
                "--contract-json",
                str(contract_path),
            ]
        )
        == 0
    )
    source_path.write_bytes(
        ledger.canonical_json_bytes(_synthetic_result(SYNTHETIC_TARGET_START, outcomes=(0, 1, 0)))
    )
    assert (
        ledger.main(
            [
                "ingest",
                "--state-json",
                str(state_path),
                "--target-result-json",
                str(source_path),
                "--contract-json",
                str(contract_path),
            ]
        )
        == 0
    )
    assert (
        ledger.main(
            [
                "report",
                "--state-json",
                str(state_path),
                "--output-json",
                str(report_path),
                "--contract-json",
                str(contract_path),
            ]
        )
        == 0
    )

    state = ledger.load_state_file(state_path)
    assert state["accepted_target_identities"] == [str(SYNTHETIC_TARGET_START)]
    assert report_path.read_bytes().count(b'"stream_id"') == 60


def test_all_fixtures_are_synthetic_and_contain_no_outcome_payload() -> None:
    fixture = _synthetic_result(SYNTHETIC_TARGET_START)

    assert int(cast(str, fixture["target_identity"])) >= SYNTHETIC_TARGET_START
    assert "official_outcome" not in fixture
    assert "winning_numbers" not in fixture
