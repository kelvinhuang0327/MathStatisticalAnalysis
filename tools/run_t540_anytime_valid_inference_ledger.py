"""Exact anytime-valid inference ledger for the frozen T539 experiment.

The implementation is deliberately self-contained and uses only integer and
``fractions.Fraction`` arithmetic for evidence and confidence-sequence work.
It consumes a structurally complete T539 post-target score artifact; it never
opens an outcome authority, database, network resource, or prospective store.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from math import comb
from pathlib import Path
from typing import Final, Literal, cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = Path(
    "docs/research/matrix-native-results/t540-anytime-valid-inference-protocol-r1.json"
)
DEFAULT_CONTRACT_PATH = REPOSITORY_ROOT / CONTRACT_RELATIVE_PATH

STATE_SCHEMA_VERSION: Final = "T540_ANYTIME_VALID_INFERENCE_LEDGER_STATE_V1"
REPORT_SCHEMA_VERSION: Final = "T540_ANYTIME_VALID_INFERENCE_REPORT_V1"
CONTRACT_SCHEMA_VERSION: Final = "T540_ANYTIME_VALID_INFERENCE_CONTRACT_V1"
CONTRACT_ID: Final = "T540_ANYTIME_VALID_INFERENCE_LEDGER_R1"

FREEZE_BOUNDARY: Final = "115000186"
FREEZE_SHA256: Final = "f1b299ace019393440bce8bd2768f6618b2362d220d81b4cc14151a5080908a8"
RULE_FINGERPRINT: Final = "eb4eb89082cd782041c240e80858efd8453c3bbf08edec3b76e98e2e8051f446"
PRIMARY_METRIC: Final = "OFFICIAL_ANY_PRIZE_TARGET_RATE"
SOURCE_RESULT_SCHEMA_VERSION: Final = "T539_PROSPECTIVE_TARGET_SCORE_V1"
VALID_PROSPECTIVE_STATUS: Final = "VALID_PROSPECTIVE_OBSERVATION"
VALID_SCORE_STATUS: Final = "STRUCTURALLY_VALID_TARGET_SCORE"
VALID_PRETARGET_SEAL_STATUS: Final = "PRETARGET_SEAL_CONFIRMED_BEFORE_OUTCOME"

K_VALUES: Final = (1, 2, 3, 4, 5, 7, 10, 11, 12, 25)
WINDOWS: Final = (("W50", 50), ("W300", 300), ("W750", 750))
ARM_A: Final = "ORIGINAL_ROLLING"
ARM_B: Final = "CALLABLE_FAMILY_DEDUP_ROLLING"
ARM_C: Final = "CALLABLE_FAMILY_DEDUP_FROZEN_BASELINE"
ARMS: Final = (ARM_A, ARM_B, ARM_C)
COMPARISONS: Final = (("B_MINUS_A", ARM_A), ("B_MINUS_C", ARM_C))

STREAM_COUNT: Final = 60
FAMILY_ALPHA: Final = Fraction(1, 20)
PER_STREAM_ALPHA: Final = Fraction(1, 1200)
FURTHER_STUDY_THRESHOLD: Final = 600
CONFIRMATORY_THRESHOLD: Final = 1200
CS_BISECTIONS: Final = 49
CS_CERTIFIED_WIDTH: Final = Fraction(1, 2**48)
FORMAL_REPORT_STEP: Final = 50

POSITIVE_INFINITY: Final = "POSITIVE_INFINITY"
TECHNICAL_EXCLUSION_STATUSES: Final = frozenset(
    {
        "MISSED_PRETARGET_SEAL",
        "PRETARGET_SNAPSHOT_INVALID",
        "RULE_FINGERPRINT_MISMATCH",
        "TARGET_IDENTITY_MISMATCH",
        "OUTCOME_AUTHORITY_UNAVAILABLE",
        "INCOMPLETE_FROZEN_EXPERIMENT_SURFACE",
    }
)

_TARGET_IDENTITY = re.compile(r"[0-9]{1,32}", flags=re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)

type JsonObject = dict[str, object]
type ExactEValue = Fraction | Literal["POSITIVE_INFINITY"]
type IngestDisposition = Literal[
    "ACCEPTED", "EXCLUDED_NO_CONFIRMATORY_DENOMINATOR", "EXACT_IDEMPOTENT_NO_OP"
]


class LedgerContractError(ValueError):
    """An input or persisted state violates the sealed T540 contract."""


class LedgerConflictError(LedgerContractError):
    """The same target identity was presented with different canonical bytes."""


class NoResetError(LedgerContractError):
    """An initialization attempt would discard already processed evidence."""


@dataclass(frozen=True, slots=True)
class StreamDefinition:
    stream_id: str
    experiment_id: str
    k: int
    window_label: str
    window_size: int
    comparison_id: str
    comparator_arm: str


@dataclass(frozen=True, slots=True)
class PairedCounts:
    n11: int = 0
    n10: int = 0
    n01: int = 0
    n00: int = 0

    @property
    def n(self) -> int:
        return self.n11 + self.n10 + self.n01 + self.n00

    @property
    def delta_hat(self) -> Fraction | None:
        if self.n == 0:
            return None
        return Fraction(self.n10 - self.n01, self.n)


@dataclass(frozen=True, slots=True)
class ConfidenceSequenceBracket:
    lower: Fraction
    upper: Fraction
    bisections: int

    @property
    def width(self) -> Fraction:
        return self.upper - self.lower


@dataclass(frozen=True, slots=True)
class IngestionResult:
    disposition: IngestDisposition
    state: JsonObject
    target_identity: str


def _stream_definitions() -> tuple[StreamDefinition, ...]:
    definitions: list[StreamDefinition] = []
    for k in K_VALUES:
        for window_label, window_size in WINDOWS:
            experiment_id = f"T539:K{k}:{window_label}"
            for comparison_id, comparator_arm in COMPARISONS:
                definitions.append(
                    StreamDefinition(
                        stream_id=f"{experiment_id}:{comparison_id}",
                        experiment_id=experiment_id,
                        k=k,
                        window_label=window_label,
                        window_size=window_size,
                        comparison_id=comparison_id,
                        comparator_arm=comparator_arm,
                    )
                )
    return tuple(definitions)


STREAM_DEFINITIONS: Final = _stream_definitions()
STREAM_IDENTITIES: Final = tuple(stream.stream_id for stream in STREAM_DEFINITIONS)

if len(STREAM_IDENTITIES) != STREAM_COUNT or len(set(STREAM_IDENTITIES)) != STREAM_COUNT:
    raise RuntimeError("the frozen T540 surface must contain exactly 60 unique streams")


def canonical_json_bytes(value: object) -> bytes:
    """Return deterministic, human-readable JSON bytes with one trailing newline."""

    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()


def compact_json_bytes(value: object) -> bytes:
    """Return compact bytes for content fingerprints."""

    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode()


def _content_sha256(value: object) -> str:
    return hashlib.sha256(compact_json_bytes(value)).hexdigest()


def result_content_hash(result: Mapping[str, object]) -> str:
    """Reproduce the T539 score harness's logical result-content hash."""

    material = dict(result)
    material.pop("result_content_hash", None)
    return _content_sha256(material)


def _mapping(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise LedgerContractError(f"{context} must be a JSON object")
    return cast(Mapping[str, object], value)


def _list(value: object, *, context: str) -> list[object]:
    if not isinstance(value, list):
        raise LedgerContractError(f"{context} must be a JSON array")
    return cast(list[object], value)


def _text(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise LedgerContractError(f"{context} must be a non-empty string")
    return value


def _integer(value: object, *, context: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise LedgerContractError(f"{context} must be an integer >= {minimum}")
    return value


def _boolean(value: object, *, context: str) -> bool:
    if not isinstance(value, bool):
        raise LedgerContractError(f"{context} must be boolean")
    return value


def _binary(value: object, *, context: str) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and not isinstance(value, bool) and value in (0, 1):
        return value
    raise LedgerContractError(f"{context} must be exactly 0, 1, false, or true")


def _sha256_text(value: object, *, context: str) -> str:
    text = _text(value, context=context)
    if _SHA256.fullmatch(text) is None:
        raise LedgerContractError(f"{context} must be a lowercase SHA-256 hex digest")
    return text


def _target_text(value: object, *, context: str) -> str:
    text = _text(value, context=context)
    if _TARGET_IDENTITY.fullmatch(text) is None:
        raise LedgerContractError(f"{context} must contain 1 to 32 ASCII decimal digits")
    return text


def _exact_keys(value: Mapping[str, object], expected: set[str], *, context: str) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise LedgerContractError(f"{context} keys mismatch: missing={missing}, extra={extra}")


def _fraction_payload(value: Fraction) -> JsonObject:
    return {"denominator": value.denominator, "numerator": value.numerator}


def _contract_core() -> JsonObject:
    stream_rows: list[object] = [
        {
            "comparison_id": stream.comparison_id,
            "comparator_arm": stream.comparator_arm,
            "experiment_id": stream.experiment_id,
            "k": stream.k,
            "stream_id": stream.stream_id,
            "window_label": stream.window_label,
            "window_size": stream.window_size,
        }
        for stream in STREAM_DEFINITIONS
    ]
    return {
        "authority": {
            "freeze_boundary": FREEZE_BOUNDARY,
            "freeze_sha256": FREEZE_SHA256,
            "metric": PRIMARY_METRIC,
            "rule_fingerprint": RULE_FINGERPRINT,
            "source_result_schema_version": SOURCE_RESULT_SCHEMA_VERSION,
        },
        "confidence_sequence": {
            "bisection_count": CS_BISECTIONS,
            "bisection_interval": ["-1", "1"],
            "certified_width": "2^-48",
            "confidence_set": "(L_t,1]",
            "conservative_scalar": "LOWER_BRACKET_ENDPOINT",
            "equality_is_rejected": True,
            "empty_rejection_set_lower_endpoint": "-1",
            "lower_endpoint_definition": "sup{delta:M_t(delta)>=1200}",
            "rejection_set": "{delta:M_t(delta)>=1200}",
            "running_max_not_current_e": True,
            "threshold": CONFIRMATORY_THRESHOLD,
        },
        "e_process": {
            "boundary_delta_minus_one": {
                "empty": "1",
                "nonempty_all_D_minus_one": "1/(t+1)",
                "otherwise": POSITIVE_INFINITY,
            },
            "boundary_delta_plus_one": {"running_max": "1_FOR_EVERY_PATH"},
            "current_null_integral": "integral_0^1 product_i(1+gamma*D_i) dgamma",
            "current_null_reduced_integral": "integral_0^1 (1+gamma)^n10 (1-gamma)^n01 dgamma",
            "gamma_distribution": "UNIFORM_0_1",
            "initial_e": "1",
            "lambda_density": "1+delta",
            "lambda_support": "[0,1/(1+delta)]",
            "no_adaptive_stake": True,
            "numeric_semantics": {
                "arithmetic": "ARBITRARY_INTEGER_EXACT_RATIONAL",
                "clipping": "FORBIDDEN",
                "float_overflow_saturation": "FORBIDDEN",
                "float_residual_tolerance": "FORBIDDEN",
                "underflow_to_zero": "FORBIDDEN",
            },
            "positive_term_conformance": {
                "A_u_k": "sum_{j=max(0,k-z)}^{min(k,p)} C(p,j)C(z,k-j)2^j",
                "E_u_delta": "1/(u+1) sum_{k=0}^{p+z} A_u_k/C(u,k)*(1+delta)^(-k)",
                "authoritative_evaluation": "EXACT_POSITIVE_TERM_RATIONAL",
                "generic_numerical_quadrature": "FORBIDDEN",
                "p": "n10_at_prefix_u",
                "r": "n01_at_prefix_u",
                "z": "n11_at_prefix_u+n00_at_prefix_u",
            },
            "running_max": "M_t(delta)=max_{0<=u<=t}E_u(delta)",
            "running_max_reset": "FORBIDDEN",
            "shifted_null_integral": (
                "integral_0^1 product_i[1+gamma*(D_i-delta)/(1+delta)] dgamma"
            ),
            "shifted_null_range": "-1<delta<=1",
            "ties_at_delta_zero_factor": "1",
        },
        "evidence_tiers": {
            "confirmatory_crossing": "M_t(0)>=1200",
            "further_study_cell_rule": (
                "B_MINUS_A_M>=600 AND B_MINUS_C_M>=600 AND both_current_delta_hat>0"
            ),
            "further_study_label": "SUPPORTS_FURTHER_STUDY",
            "further_study_not_confirmatory_advantage": True,
            "further_study_threshold": FURTHER_STUDY_THRESHOLD,
            "no_95_percent_claim_at_600": True,
            "no_best_cell_designation": True,
            "predictive_advantage_cell_label": ("PREDICTIVE_ADVANTAGE_ESTABLISHED_AT_K_AND_WINDOW"),
            "predictive_advantage_cell_rule": (
                "B_MINUS_A_M>=1200 AND B_MINUS_C_M>=1200 AND both_current_delta_hat>0"
            ),
            "whole_surface_rule": "ALL_60_STREAMS_CONFIRMATORY_AND_POSITIVE",
        },
        "frozen_surface": {
            "arms": {"A": ARM_A, "B": ARM_B, "C": ARM_C},
            "comparisons": [
                {
                    "comparison_id": comparison_id,
                    "minuend_arm": ARM_B,
                    "subtrahend_arm": comparator_arm,
                }
                for comparison_id, comparator_arm in COMPARISONS
            ],
            "experiment_count": 30,
            "k_values": list(K_VALUES),
            "stream_count": STREAM_COUNT,
            "windows": [
                {"label": window_label, "size": window_size}
                for window_label, window_size in WINDOWS
            ],
        },
        "integrity": {
            "database_access": "NO",
            "embedded_real_results": [],
            "network_draw_refresh": "NOT_RUN",
            "prospective_observations_at_contract_freeze": 0,
            "real_future_outcome_access": "NO",
            "synthetic_fixture_policy": "TESTS_ONLY",
        },
        "multiplicity": {
            "adjusted_anytime_p": "min(1,60/M_t(0))",
            "confirmatory_threshold": CONFIRMATORY_THRESHOLD,
            "equality_is_crossing": True,
            "family_alpha": "1/20",
            "per_stream_alpha": "1/1200",
            "stream_count": STREAM_COUNT,
        },
        "observation_eligibility": {
            "accepted_target_cannot_be_dropped_by_result": True,
            "all_30_experiments_and_3_arms_required": True,
            "invalid_status_denominator_contribution": 0,
            "invalid_statuses": sorted(TECHNICAL_EXCLUSION_STATUSES),
            "missed_pretarget_seal_denominator_contribution": 0,
            "no_partial_cell_ingestion": True,
            "observation_unit": "ONE_OFFICIAL_TARGET",
            "valid_pretarget_seal_status": VALID_PRETARGET_SEAL_STATUS,
            "valid_status": VALID_PROSPECTIVE_STATUS,
        },
        "paired_statistic": {
            "D_domain": [-1, 0, 1],
            "D_formula": "Y_B-Y_X",
            "Y_domain": [0, 1],
            "counts": ["n11", "n10", "n01", "n00", "N"],
            "delta_hat": "(n10-n01)/N",
            "floating_counts": "FORBIDDEN",
        },
        "persistence": {
            "accepted_target_order": "ASCENDING_NUMERIC_TARGET_IDENTITY",
            "conflicting_duplicate": "CONFLICT",
            "exact_duplicate": "EXACT_IDEMPOTENT_NO_OP",
            "no_reset_after_evidence": True,
            "preserved_state_fields": [
                "statistical_schema_version",
                "freeze_sha256",
                "rule_fingerprint",
                "statistical_contract_fingerprint",
                "accepted_target_identities",
                "raw_90_arm_source_identity_and_hash",
                "all_60_replay_complete_paired_records",
                "paired_counts",
                "current_E_0",
                "running_M_0",
                "lower_confidence_sequence_bracket",
                "evidence_tier_flags",
            ],
            "replay_complete_paired_records": True,
            "running_max_reset": "FORBIDDEN",
            "serialization": "UTF8_INDENT2_SORTED_KEYS_TRAILING_NEWLINE",
            "state_contract_bindings": [
                "schema_version",
                "freeze_sha256",
                "rule_fingerprint",
                "statistical_contract_fingerprint",
            ],
        },
        "reporting": {
            "formal_common_denominators": "N=50,100,150,...",
            "ledger_update": "EVERY_ELIGIBLE_TARGET",
            "no_best_cell_output": True,
            "terminal_report": True,
            "whole_surface_stream_count": STREAM_COUNT,
        },
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "stopping": {
            "administrative_termination_may_reset": False,
            "cell_specific_winner_stop": "FORBIDDEN",
            "efficacy_stop": "ALL_60_M>=1200_AND_ALL_CURRENT_DELTA_HAT>0",
            "futility_stop": "FORBIDDEN",
            "semantic_change_disposition": "TERMINAL_NEW_EXPERIMENT_REQUIRED",
            "successor_evidence_sharing_after_semantic_change": "FORBIDDEN",
        },
        "streams": stream_rows,
        "synthetic_reference_cases": {
            "(-1,+1)_L": "-3598/3599",
            "(+1,-1)_L": "-2397/2399",
            "13_consecutive_+1_M0": "16383/14",
            "14_consecutive_+1_M0": "32767/15",
            "EMPTY_L": "-1",
            "all_-1_L": "-1",
            "single_+1_L": "-2397/2399",
            "single_tie_L": "-2398/2399",
        },
    }


def statistical_contract_fingerprint() -> str:
    """Hash the compact canonical contract core (excluding its seal field)."""

    return _content_sha256(_contract_core())


def statistical_contract() -> JsonObject:
    """Build the complete machine-readable contract and its deterministic seal."""

    core = _contract_core()
    return {
        **core,
        "statistical_contract_fingerprint": statistical_contract_fingerprint(),
    }


def statistical_contract_bytes() -> bytes:
    return canonical_json_bytes(statistical_contract())


def statistical_contract_artifact_sha256() -> str:
    return hashlib.sha256(statistical_contract_bytes()).hexdigest()


@cache
def _positive_coefficients(p: int, z: int) -> tuple[int, ...]:
    coefficients = [1]
    for _ in range(p):
        updated = [0] * (len(coefficients) + 1)
        for index, coefficient in enumerate(coefficients):
            updated[index] += coefficient
            updated[index + 1] += 2 * coefficient
        coefficients = updated
    for _ in range(z):
        updated = [0] * (len(coefficients) + 1)
        for index, coefficient in enumerate(coefficients):
            updated[index] += coefficient
            updated[index + 1] += coefficient
        coefficients = updated
    return tuple(coefficients)


def e_value_from_counts(*, p: int, z: int, r: int, delta: Fraction) -> ExactEValue:
    """Evaluate the preregistered positive-term formula for one prefix exactly."""

    if min(p, z, r) < 0:
        raise LedgerContractError("p, z, and r must be non-negative exact integers")
    if delta < -1 or delta > 1:
        raise LedgerContractError("delta must lie in [-1,1]")
    u = p + z + r
    if delta == -1:
        if u == 0:
            return Fraction(1)
        if p == 0 and z == 0:
            return Fraction(1, u + 1)
        return POSITIVE_INFINITY

    inverse_one_plus_delta = Fraction(1, 1) / (1 + delta)
    coefficients = _positive_coefficients(p, z)
    value = Fraction(0)
    for k in range(len(coefficients) - 1, -1, -1):
        weight = Fraction(coefficients[k], (u + 1) * comb(u, k))
        value = value * inverse_one_plus_delta + weight
    return value


def _validated_d_sequence(values: Sequence[int]) -> tuple[int, ...]:
    sequence = tuple(values)
    if any(isinstance(value, bool) or value not in (-1, 0, 1) for value in sequence):
        raise LedgerContractError("every paired difference must be exactly -1, 0, or 1")
    return sequence


def e_value(sequence: Sequence[int], delta: Fraction) -> ExactEValue:
    """Evaluate E_t(delta) for the current prefix."""

    values = _validated_d_sequence(sequence)
    return e_value_from_counts(
        p=values.count(1), z=values.count(0), r=values.count(-1), delta=delta
    )


@cache
def _prefix_weight_rows(sequence: tuple[int, ...]) -> tuple[tuple[Fraction, ...], ...]:
    coefficients = [1]
    rows: list[tuple[Fraction, ...]] = [(Fraction(1),)]
    for u, difference in enumerate(sequence, start=1):
        if difference in (0, 1):
            multiplier = 2 if difference == 1 else 1
            updated = [0] * (len(coefficients) + 1)
            for index, coefficient in enumerate(coefficients):
                updated[index] += coefficient
                updated[index + 1] += multiplier * coefficient
            coefficients = updated
        rows.append(
            tuple(
                Fraction(coefficient, (u + 1) * comb(u, k))
                for k, coefficient in enumerate(coefficients)
            )
        )
    return tuple(rows)


def _evaluate_weight_row(row: tuple[Fraction, ...], inverse_one_plus_delta: Fraction) -> Fraction:
    value = Fraction(0)
    for weight in reversed(row):
        value = value * inverse_one_plus_delta + weight
    return value


@cache
def _running_max_cached(sequence: tuple[int, ...], delta: Fraction) -> ExactEValue:
    if delta < -1 or delta > 1:
        raise LedgerContractError("delta must lie in [-1,1]")
    if delta == -1:
        return Fraction(1) if not any(value != -1 for value in sequence) else POSITIVE_INFINITY
    if delta == 1:
        return Fraction(1)

    inverse_one_plus_delta = Fraction(1, 1) / (1 + delta)
    maximum = Fraction(1)
    for row in _prefix_weight_rows(sequence)[1:]:
        maximum = max(maximum, _evaluate_weight_row(row, inverse_one_plus_delta))
    return maximum


def running_max_e_value(sequence: Sequence[int], delta: Fraction) -> ExactEValue:
    """Evaluate M_t(delta), retaining every chronological prefix including u=0."""

    return _running_max_cached(_validated_d_sequence(sequence), delta)


@cache
def _lower_confidence_bracket_cached(
    sequence: tuple[int, ...],
) -> ConfidenceSequenceBracket:
    if not any(value != -1 for value in sequence):
        return ConfidenceSequenceBracket(lower=Fraction(-1), upper=Fraction(-1), bisections=0)

    lower = Fraction(-1)
    upper = Fraction(1)
    for _ in range(CS_BISECTIONS):
        midpoint = (lower + upper) / 2
        evidence = _running_max_cached(sequence, midpoint)
        rejected = evidence == POSITIVE_INFINITY or evidence >= CONFIRMATORY_THRESHOLD
        if rejected:
            lower = midpoint
        else:
            upper = midpoint
    if upper - lower != CS_CERTIFIED_WIDTH:
        raise RuntimeError("the exact 49-bisection confidence bracket has the wrong width")
    return ConfidenceSequenceBracket(lower=lower, upper=upper, bisections=CS_BISECTIONS)


def lower_confidence_sequence_bracket(
    sequence: Sequence[int],
) -> ConfidenceSequenceBracket:
    """Invert max-prefix evidence with exactly 49 deterministic bisections."""

    return _lower_confidence_bracket_cached(_validated_d_sequence(sequence))


def paired_counts(pairs: Sequence[tuple[int, int]]) -> PairedCounts:
    """Count exact (Y_B,Y_X) pairs without floating-point conversion."""

    n11 = n10 = n01 = n00 = 0
    for index, (raw_b, raw_x) in enumerate(pairs):
        y_b = _binary(raw_b, context=f"pairs[{index}].Y_B")
        y_x = _binary(raw_x, context=f"pairs[{index}].Y_X")
        if (y_b, y_x) == (1, 1):
            n11 += 1
        elif (y_b, y_x) == (1, 0):
            n10 += 1
        elif (y_b, y_x) == (0, 1):
            n01 += 1
        else:
            n00 += 1
    return PairedCounts(n11=n11, n10=n10, n01=n01, n00=n00)


def evidence_threshold_flags(m_value: Fraction) -> JsonObject:
    if m_value <= 0:
        raise LedgerContractError("M_t(0) must be an exact positive rational")
    return {
        "confirmatory_crossing": m_value >= CONFIRMATORY_THRESHOLD,
        "supports_further_study_threshold_crossing": m_value >= FURTHER_STUDY_THRESHOLD,
    }


def adjusted_anytime_p_value(m_value: Fraction) -> Fraction:
    if m_value <= 0:
        raise LedgerContractError("M_t(0) must be an exact positive rational")
    return min(Fraction(1), Fraction(STREAM_COUNT, 1) / m_value)


def _expected_surface_payload() -> JsonObject:
    return {
        "arm_record_count": 90,
        "arms": list(ARMS),
        "experiment_count": 30,
        "k_values": list(K_VALUES),
        "windows": [{"label": label, "size": size} for label, size in WINDOWS],
    }


def _normalize_source_reference(source: Mapping[str, object]) -> tuple[str, JsonObject]:
    schema_version = _text(source.get("schema_version"), context="source.schema_version")
    if schema_version != SOURCE_RESULT_SCHEMA_VERSION:
        raise LedgerContractError("SOURCE_RESULT_SCHEMA_VERSION_MISMATCH")
    target = _target_text(source.get("target_identity"), context="source.target_identity")
    supplied_result_hash = _sha256_text(
        source.get("result_content_hash"), context="source.result_content_hash"
    )
    observed_result_hash = result_content_hash(source)
    if supplied_result_hash != observed_result_hash:
        raise LedgerContractError(
            f"SOURCE_RESULT_CONTENT_HASH_MISMATCH: {supplied_result_hash} != {observed_result_hash}"
        )
    pretarget_hash = _sha256_text(
        source.get("pretarget_snapshot_content_hash"),
        context="source.pretarget_snapshot_content_hash",
    )
    outcome_hash = _sha256_text(
        source.get("official_outcome_sha256"), context="source.official_outcome_sha256"
    )
    input_authority = _mapping(source.get("input_authority"), context="source.input_authority")
    input_authority_hash = _sha256_text(
        input_authority.get("sha256"), context="source.input_authority.sha256"
    )
    experiments = _list(source.get("experiments"), context="source.experiments")
    raw_arm_record_count = 0
    for index, raw_experiment in enumerate(experiments):
        experiment = _mapping(raw_experiment, context=f"source.experiments[{index}]")
        raw_arm_record_count += len(
            _list(experiment.get("arms"), context=f"source.experiments[{index}].arms")
        )
    canonical_source_hash = hashlib.sha256(canonical_json_bytes(source)).hexdigest()
    return target, {
        "canonical_source_sha256": canonical_source_hash,
        "input_authority_sha256": input_authority_hash,
        "official_outcome_sha256": outcome_hash,
        "pretarget_snapshot_content_hash": pretarget_hash,
        "raw_arm_record_count": raw_arm_record_count,
        "result_content_hash": supplied_result_hash,
        "schema_version": schema_version,
        "source_identity": f"T539_TARGET_SCORE:{target}:{supplied_result_hash}",
    }


def _validate_source_surface(source: Mapping[str, object]) -> None:
    surface = _mapping(source.get("surface"), context="source.surface")
    if canonical_json_bytes(surface) != canonical_json_bytes(_expected_surface_payload()):
        raise LedgerContractError("INCOMPLETE_FROZEN_EXPERIMENT_SURFACE")


def _paired_records_from_source(source: Mapping[str, object]) -> list[object]:
    _validate_source_surface(source)
    experiments = _list(source.get("experiments"), context="source.experiments")
    if len(experiments) != 30:
        raise LedgerContractError("INCOMPLETE_FROZEN_EXPERIMENT_SURFACE")

    by_experiment: dict[str, Mapping[str, object]] = {}
    for index, raw_experiment in enumerate(experiments):
        experiment = _mapping(raw_experiment, context=f"source.experiments[{index}]")
        experiment_id = _text(
            experiment.get("experiment_id"),
            context=f"source.experiments[{index}].experiment_id",
        )
        if experiment_id in by_experiment:
            raise LedgerContractError(f"DUPLICATE_EXPERIMENT_ID: {experiment_id}")
        by_experiment[experiment_id] = experiment

    expected_experiments = {stream.experiment_id for stream in STREAM_DEFINITIONS}
    if set(by_experiment) != expected_experiments:
        raise LedgerContractError("INCOMPLETE_FROZEN_EXPERIMENT_SURFACE")

    outcomes_by_experiment: dict[str, dict[str, int]] = {}
    for k in K_VALUES:
        for window_label, window_size in WINDOWS:
            experiment_id = f"T539:K{k}:{window_label}"
            experiment = by_experiment[experiment_id]
            if _integer(experiment.get("k"), context=f"{experiment_id}.k") != k:
                raise LedgerContractError(f"EXPERIMENT_K_MISMATCH: {experiment_id}")
            if (
                _text(experiment.get("window_label"), context=f"{experiment_id}.window_label")
                != window_label
            ):
                raise LedgerContractError(f"EXPERIMENT_WINDOW_LABEL_MISMATCH: {experiment_id}")
            if _integer(experiment.get("window"), context=f"{experiment_id}.window") != window_size:
                raise LedgerContractError(f"EXPERIMENT_WINDOW_SIZE_MISMATCH: {experiment_id}")
            arms = _list(experiment.get("arms"), context=f"{experiment_id}.arms")
            if len(arms) != 3:
                raise LedgerContractError("INCOMPLETE_FROZEN_EXPERIMENT_SURFACE")
            arm_outcomes: dict[str, int] = {}
            for arm_index, raw_arm in enumerate(arms):
                arm = _mapping(raw_arm, context=f"{experiment_id}.arms[{arm_index}]")
                arm_name = _text(arm.get("arm"), context=f"{experiment_id}.arms[{arm_index}].arm")
                if arm_name in arm_outcomes:
                    raise LedgerContractError(f"DUPLICATE_ARM: {experiment_id}:{arm_name}")
                arm_outcomes[arm_name] = _binary(
                    arm.get("official_any_prize_success"),
                    context=f"{experiment_id}.arms[{arm_index}].official_any_prize_success",
                )
            if set(arm_outcomes) != set(ARMS):
                raise LedgerContractError("INCOMPLETE_FROZEN_EXPERIMENT_SURFACE")
            outcomes_by_experiment[experiment_id] = arm_outcomes

    paired_records: list[object] = []
    for stream in STREAM_DEFINITIONS:
        outcomes = outcomes_by_experiment[stream.experiment_id]
        y_b = outcomes[ARM_B]
        y_x = outcomes[stream.comparator_arm]
        paired_records.append(
            {
                "d": y_b - y_x,
                "stream_id": stream.stream_id,
                "y_b": y_b,
                "y_x": y_x,
            }
        )
    return paired_records


def _normalize_source_for_ingestion(
    source: Mapping[str, object],
) -> tuple[str, str, bool, JsonObject]:
    target, source_reference = _normalize_source_reference(source)
    if int(target) <= int(FREEZE_BOUNDARY):
        raise LedgerContractError(
            f"TARGET_AT_OR_BELOW_FREEZE_BOUNDARY: {target} <= {FREEZE_BOUNDARY}"
        )
    status = _text(
        source.get("prospective_observation_status"),
        context="source.prospective_observation_status",
    )
    counts_as_valid = _boolean(
        source.get("counts_as_valid_prospective_observation"),
        context="source.counts_as_valid_prospective_observation",
    )
    if status == VALID_PROSPECTIVE_STATUS:
        if not counts_as_valid:
            raise LedgerContractError("VALID_STATUS_DENOMINATOR_FLAG_MISMATCH")
        if source.get("pretarget_seal_status") != VALID_PRETARGET_SEAL_STATUS:
            raise LedgerContractError("VALID_PRETARGET_SEAL_STATUS_MISMATCH")
    elif status in TECHNICAL_EXCLUSION_STATUSES:
        if counts_as_valid:
            raise LedgerContractError("INVALID_STATUS_DENOMINATOR_FLAG_MISMATCH")
    else:
        raise LedgerContractError(f"UNRECOGNIZED_PROSPECTIVE_STATUS: {status}")
    return target, status, counts_as_valid, source_reference


def _normalize_source_reference_record(value: object, *, context: str) -> JsonObject:
    source = _mapping(value, context=context)
    expected = {
        "canonical_source_sha256",
        "input_authority_sha256",
        "official_outcome_sha256",
        "pretarget_snapshot_content_hash",
        "raw_arm_record_count",
        "result_content_hash",
        "schema_version",
        "source_identity",
    }
    _exact_keys(source, expected, context=context)
    normalized: JsonObject = {
        "canonical_source_sha256": _sha256_text(
            source.get("canonical_source_sha256"), context=f"{context}.canonical_source_sha256"
        ),
        "input_authority_sha256": _sha256_text(
            source.get("input_authority_sha256"), context=f"{context}.input_authority_sha256"
        ),
        "official_outcome_sha256": _sha256_text(
            source.get("official_outcome_sha256"), context=f"{context}.official_outcome_sha256"
        ),
        "pretarget_snapshot_content_hash": _sha256_text(
            source.get("pretarget_snapshot_content_hash"),
            context=f"{context}.pretarget_snapshot_content_hash",
        ),
        "raw_arm_record_count": _integer(
            source.get("raw_arm_record_count"), context=f"{context}.raw_arm_record_count"
        ),
        "result_content_hash": _sha256_text(
            source.get("result_content_hash"), context=f"{context}.result_content_hash"
        ),
        "schema_version": _text(source.get("schema_version"), context=f"{context}.schema_version"),
        "source_identity": _text(
            source.get("source_identity"), context=f"{context}.source_identity"
        ),
    }
    if normalized["schema_version"] != SOURCE_RESULT_SCHEMA_VERSION:
        raise LedgerContractError(f"{context}.schema_version mismatch")
    return normalized


def _normalize_paired_record(value: object, *, index: int) -> JsonObject:
    record = _mapping(value, context=f"paired_records[{index}]")
    _exact_keys(record, {"d", "stream_id", "y_b", "y_x"}, context=f"paired_records[{index}]")
    stream_id = _text(record.get("stream_id"), context=f"paired_records[{index}].stream_id")
    if stream_id != STREAM_IDENTITIES[index]:
        raise LedgerContractError(f"PAIRED_RECORD_STREAM_ORDER_MISMATCH: {stream_id}")
    y_b = _binary(record.get("y_b"), context=f"paired_records[{index}].y_b")
    y_x = _binary(record.get("y_x"), context=f"paired_records[{index}].y_x")
    difference = record.get("d")
    if isinstance(difference, bool) or not isinstance(difference, int):
        raise LedgerContractError(f"paired_records[{index}].d must be an exact integer")
    if difference != y_b - y_x:
        raise LedgerContractError(f"PAIRED_RECORD_DIFFERENCE_MISMATCH: {stream_id}")
    return {"d": difference, "stream_id": stream_id, "y_b": y_b, "y_x": y_x}


def _normalize_accepted_target(value: object, *, index: int) -> JsonObject:
    target = _mapping(value, context=f"accepted_targets[{index}]")
    _exact_keys(
        target,
        {"paired_records", "source", "target_identity"},
        context=f"accepted_targets[{index}]",
    )
    target_identity = _target_text(
        target.get("target_identity"), context=f"accepted_targets[{index}].target_identity"
    )
    source = _normalize_source_reference_record(
        target.get("source"), context=f"accepted_targets[{index}].source"
    )
    if source["raw_arm_record_count"] != 90:
        raise LedgerContractError(
            f"accepted_targets[{index}].source.raw_arm_record_count must equal 90"
        )
    records = _list(
        target.get("paired_records"), context=f"accepted_targets[{index}].paired_records"
    )
    if len(records) != STREAM_COUNT:
        raise LedgerContractError("accepted target must contain exactly 60 paired records")
    normalized_records = [
        _normalize_paired_record(record, index=record_index)
        for record_index, record in enumerate(records)
    ]
    return {
        "paired_records": normalized_records,
        "source": source,
        "target_identity": target_identity,
    }


def _normalize_technical_exclusion(value: object, *, index: int) -> JsonObject:
    exclusion = _mapping(value, context=f"technical_exclusions[{index}]")
    _exact_keys(
        exclusion,
        {"source", "status", "target_identity"},
        context=f"technical_exclusions[{index}]",
    )
    target_identity = _target_text(
        exclusion.get("target_identity"),
        context=f"technical_exclusions[{index}].target_identity",
    )
    status = _text(exclusion.get("status"), context=f"technical_exclusions[{index}].status")
    if status not in TECHNICAL_EXCLUSION_STATUSES:
        raise LedgerContractError(f"invalid persisted technical exclusion status: {status}")
    return {
        "source": _normalize_source_reference_record(
            exclusion.get("source"), context=f"technical_exclusions[{index}].source"
        ),
        "status": status,
        "target_identity": target_identity,
    }


def _stream_state(stream: StreamDefinition, accepted_targets: Sequence[JsonObject]) -> JsonObject:
    pairs: list[tuple[int, int]] = []
    differences: list[int] = []
    stream_index = STREAM_IDENTITIES.index(stream.stream_id)
    for target in accepted_targets:
        records = cast(list[object], target["paired_records"])
        record = _mapping(records[stream_index], context=f"{stream.stream_id}.paired_record")
        y_b = cast(int, record["y_b"])
        y_x = cast(int, record["y_x"])
        pairs.append((y_b, y_x))
        differences.append(cast(int, record["d"]))

    counts = paired_counts(pairs)
    current_e = e_value(differences, Fraction(0))
    running_m = running_max_e_value(differences, Fraction(0))
    if current_e == POSITIVE_INFINITY or running_m == POSITIVE_INFINITY:
        raise RuntimeError("delta=0 evidence must always be a finite exact rational")
    bracket = lower_confidence_sequence_bracket(differences)
    flags = evidence_threshold_flags(running_m)
    return {
        "adjusted_anytime_p": _fraction_payload(adjusted_anytime_p_value(running_m)),
        "comparison_id": stream.comparison_id,
        "comparator_arm": stream.comparator_arm,
        "confidence_sequence": {
            "bisections": bracket.bisections,
            "certified_width": _fraction_payload(bracket.width),
            "confidence_set": "(L_t,1]",
            "equality_is_rejected": True,
            "lower_bracket": _fraction_payload(bracket.lower),
            "upper_bracket": _fraction_payload(bracket.upper),
        },
        "counts": {
            "N": counts.n,
            "n00": counts.n00,
            "n01": counts.n01,
            "n10": counts.n10,
            "n11": counts.n11,
        },
        "current_e0": _fraction_payload(current_e),
        "d_sequence": differences,
        "delta_hat": None if counts.delta_hat is None else _fraction_payload(counts.delta_hat),
        "evidence_flags": flags,
        "experiment_id": stream.experiment_id,
        "k": stream.k,
        "running_m0": _fraction_payload(running_m),
        "stream_id": stream.stream_id,
        "window_label": stream.window_label,
        "window_size": stream.window_size,
    }


def _positive_delta_from_stream(stream: Mapping[str, object]) -> bool:
    raw_delta = stream.get("delta_hat")
    if raw_delta is None:
        return False
    delta = _mapping(raw_delta, context="stream.delta_hat")
    numerator = delta.get("numerator")
    if isinstance(numerator, bool) or not isinstance(numerator, int):
        raise LedgerContractError("stream.delta_hat.numerator must be an exact integer")
    return numerator > 0


def _cell_statuses(streams: Sequence[JsonObject]) -> list[object]:
    by_id = {cast(str, stream["stream_id"]): stream for stream in streams}
    cells: list[object] = []
    for k in K_VALUES:
        for window_label, window_size in WINDOWS:
            prefix = f"T539:K{k}:{window_label}"
            comparison_streams = [
                by_id[f"{prefix}:B_MINUS_A"],
                by_id[f"{prefix}:B_MINUS_C"],
            ]
            further = all(
                cast(
                    bool,
                    _mapping(stream["evidence_flags"], context="flags")[
                        "supports_further_study_threshold_crossing"
                    ],
                )
                and _positive_delta_from_stream(stream)
                for stream in comparison_streams
            )
            confirmatory = all(
                cast(
                    bool,
                    _mapping(stream["evidence_flags"], context="flags")["confirmatory_crossing"],
                )
                and _positive_delta_from_stream(stream)
                for stream in comparison_streams
            )
            if confirmatory:
                status = "PREDICTIVE_ADVANTAGE_ESTABLISHED_AT_K_AND_WINDOW"
            elif further:
                status = "SUPPORTS_FURTHER_STUDY"
            else:
                status = "INSUFFICIENT_PREREGISTERED_ANYTIME_EVIDENCE"
            cells.append(
                {
                    "experiment_id": prefix,
                    "k": k,
                    "status": status,
                    "stream_ids": [stream["stream_id"] for stream in comparison_streams],
                    "window_label": window_label,
                    "window_size": window_size,
                }
            )
    return cells


def _normalize_administrative_termination(value: object) -> JsonObject | None:
    if value is None:
        return None
    termination = _mapping(value, context="administrative_termination")
    _exact_keys(termination, {"reason", "status"}, context="administrative_termination")
    if termination.get("status") != "ADMINISTRATIVELY_TERMINATED":
        raise LedgerContractError("administrative termination status mismatch")
    reason = _text(termination.get("reason"), context="administrative_termination.reason")
    return {"reason": reason, "status": "ADMINISTRATIVELY_TERMINATED"}


def _build_state(
    *,
    accepted_targets: Sequence[JsonObject],
    technical_exclusions: Sequence[JsonObject],
    administrative_termination: JsonObject | None,
) -> JsonObject:
    normalized_accepted = [
        _normalize_accepted_target(target, index=index)
        for index, target in enumerate(accepted_targets)
    ]
    normalized_exclusions = [
        _normalize_technical_exclusion(exclusion, index=index)
        for index, exclusion in enumerate(technical_exclusions)
    ]
    accepted_numbers = [int(cast(str, record["target_identity"])) for record in normalized_accepted]
    exclusion_numbers = [
        int(cast(str, record["target_identity"])) for record in normalized_exclusions
    ]
    if accepted_numbers != sorted(accepted_numbers):
        raise LedgerContractError("ACCEPTED_TARGET_LEDGER_NOT_CHRONOLOGICAL")
    if exclusion_numbers != sorted(exclusion_numbers):
        raise LedgerContractError("TECHNICAL_EXCLUSION_LEDGER_NOT_CHRONOLOGICAL")
    events = [
        (int(cast(str, record["target_identity"])), cast(str, record["target_identity"]))
        for record in [*normalized_accepted, *normalized_exclusions]
    ]
    identities = [identity for _, identity in sorted(events)]
    if len(identities) != len(set(identities)):
        raise LedgerContractError("DUPLICATE_PERSISTED_TARGET_IDENTITY")
    numeric_identities = [number for number, _ in sorted(events)]
    if len(numeric_identities) != len(set(numeric_identities)):
        raise LedgerContractError("DUPLICATE_NUMERIC_TARGET_IDENTITY")
    if any(number <= int(FREEZE_BOUNDARY) for number in numeric_identities):
        raise LedgerContractError("persisted target is at or below the freeze boundary")

    streams = [_stream_state(stream, normalized_accepted) for stream in STREAM_DEFINITIONS]
    all_confirmatory = all(
        cast(bool, _mapping(stream["evidence_flags"], context="flags")["confirmatory_crossing"])
        for stream in streams
    )
    all_positive = all(_positive_delta_from_stream(stream) for stream in streams)
    efficacy_stop = all_confirmatory and all_positive
    if efficacy_stop and administrative_termination is not None:
        raise LedgerContractError("efficacy and administrative terminal states cannot coexist")
    if efficacy_stop:
        experiment_status = "EFFICACY_STOPPED_ALL_60_STREAMS"
    elif administrative_termination is not None:
        experiment_status = "ADMINISTRATIVELY_TERMINATED"
    else:
        experiment_status = "ACTIVE"

    common_denominator = len(normalized_accepted)
    scheduled_denominators = list(
        range(FORMAL_REPORT_STEP, common_denominator + 1, FORMAL_REPORT_STEP)
    )
    terminal = experiment_status != "ACTIVE"
    formal_cadence_due = common_denominator > 0 and common_denominator % FORMAL_REPORT_STEP == 0
    return {
        "accepted_target_identities": [
            cast(str, target["target_identity"]) for target in normalized_accepted
        ],
        "accepted_targets": normalized_accepted,
        "administrative_termination": administrative_termination,
        "contract_binding": {
            "contract_artifact_sha256": statistical_contract_artifact_sha256(),
            "freeze_sha256": FREEZE_SHA256,
            "rule_fingerprint": RULE_FINGERPRINT,
            "statistical_contract_fingerprint": statistical_contract_fingerprint(),
        },
        "evidence_status": {
            "all_60_current_delta_hat_positive": all_positive,
            "all_60_streams_confirmatory": all_confirmatory,
            "cells": _cell_statuses(streams),
            "experiment_status": experiment_status,
            "full_surface_efficacy_stop": efficacy_stop,
            "no_best_cell_selection": True,
            "no_futility_stop": True,
        },
        "processed_target_identities": identities,
        "reporting": {
            "common_denominator": common_denominator,
            "formal_cadence_due": formal_cadence_due,
            "formal_report_required": formal_cadence_due or terminal,
            "no_best_cell_output": True,
            "scheduled_denominators_reached": scheduled_denominators,
            "stream_coverage_count": STREAM_COUNT,
            "terminal_report_due": terminal,
        },
        "schema_version": STATE_SCHEMA_VERSION,
        "streams": streams,
        "technical_exclusions": normalized_exclusions,
    }


def initial_state() -> JsonObject:
    """Create the only valid empty state for this sealed experiment."""

    return _build_state(
        accepted_targets=[], technical_exclusions=[], administrative_termination=None
    )


def validate_and_replay_state(value: Mapping[str, object]) -> JsonObject:
    """Rebuild all derived fields from replay-complete records and compare bytes."""

    if value.get("schema_version") != STATE_SCHEMA_VERSION:
        raise LedgerContractError("STATE_SCHEMA_VERSION_MISMATCH")
    binding = _mapping(value.get("contract_binding"), context="state.contract_binding")
    expected_binding = _mapping(initial_state()["contract_binding"], context="expected.binding")
    if canonical_json_bytes(binding) != canonical_json_bytes(expected_binding):
        raise LedgerContractError("EXPERIMENT_CONTRACT_MISMATCH_TERMINAL")
    accepted = _list(value.get("accepted_targets"), context="state.accepted_targets")
    exclusions = _list(value.get("technical_exclusions"), context="state.technical_exclusions")
    normalized_accepted = [
        _normalize_accepted_target(target, index=index) for index, target in enumerate(accepted)
    ]
    normalized_exclusions = [
        _normalize_technical_exclusion(exclusion, index=index)
        for index, exclusion in enumerate(exclusions)
    ]
    termination = _normalize_administrative_termination(value.get("administrative_termination"))
    rebuilt = _build_state(
        accepted_targets=normalized_accepted,
        technical_exclusions=normalized_exclusions,
        administrative_termination=termination,
    )
    if canonical_json_bytes(value) != canonical_json_bytes(rebuilt):
        raise LedgerContractError("STATE_REPLAY_MISMATCH")
    return rebuilt


def _existing_source_for_target(
    state: Mapping[str, object], target_identity: str
) -> Mapping[str, object] | None:
    for collection_name in ("accepted_targets", "technical_exclusions"):
        collection = _list(state.get(collection_name), context=f"state.{collection_name}")
        for raw_record in collection:
            record = _mapping(raw_record, context=f"state.{collection_name}[]")
            if record.get("target_identity") == target_identity:
                return _mapping(record.get("source"), context="persisted source")
    return None


def ingest_target_result(
    state: Mapping[str, object], source: Mapping[str, object]
) -> IngestionResult:
    """Atomically derive and append one whole target, or reject before mutation."""

    validated = validate_and_replay_state(state)
    target, status, counts_as_valid, source_reference = _normalize_source_for_ingestion(source)
    existing_source = _existing_source_for_target(validated, target)
    if existing_source is not None:
        existing_hash = existing_source.get("canonical_source_sha256")
        if existing_hash == source_reference["canonical_source_sha256"]:
            return IngestionResult(
                disposition="EXACT_IDEMPOTENT_NO_OP",
                state=validated,
                target_identity=target,
            )
        raise LedgerConflictError(f"CONFLICT: target {target} already has different source bytes")

    evidence_status = _mapping(validated["evidence_status"], context="state.evidence_status")
    if evidence_status.get("experiment_status") != "ACTIVE":
        raise LedgerContractError("EXPERIMENT_TERMINAL_NO_FURTHER_INGESTION")
    processed = cast(list[object], validated["processed_target_identities"])
    if processed and int(target) <= int(cast(str, processed[-1])):
        raise LedgerContractError("NON_CHRONOLOGICAL_TARGET_INGESTION")

    accepted = cast(list[JsonObject], validated["accepted_targets"])
    exclusions = cast(list[JsonObject], validated["technical_exclusions"])
    if counts_as_valid:
        if source.get("freeze_manifest_sha256") != FREEZE_SHA256:
            raise LedgerContractError("FREEZE_IDENTITY_DRIFT")
        if source.get("rule_fingerprint") != RULE_FINGERPRINT:
            raise LedgerContractError("RULE_FINGERPRINT_MISMATCH")
        if source.get("score_status") != VALID_SCORE_STATUS:
            raise LedgerContractError("SOURCE_SCORE_STATUS_MISMATCH")
        paired_records = _paired_records_from_source(source)
        accepted_record: JsonObject = {
            "paired_records": paired_records,
            "source": source_reference,
            "target_identity": target,
        }
        next_accepted = [
            *accepted,
            accepted_record,
        ]
        next_state = _build_state(
            accepted_targets=next_accepted,
            technical_exclusions=exclusions,
            administrative_termination=None,
        )
        return IngestionResult(disposition="ACCEPTED", state=next_state, target_identity=target)

    exclusion_record: JsonObject = {
        "source": source_reference,
        "status": status,
        "target_identity": target,
    }
    next_exclusions = [*exclusions, exclusion_record]
    next_state = _build_state(
        accepted_targets=accepted,
        technical_exclusions=next_exclusions,
        administrative_termination=None,
    )
    return IngestionResult(
        disposition="EXCLUDED_NO_CONFIRMATORY_DENOMINATOR",
        state=next_state,
        target_identity=target,
    )


def administratively_terminate(state: Mapping[str, object], *, reason: str) -> JsonObject:
    """Represent a terminal administrative decision without resetting evidence."""

    validated = validate_and_replay_state(state)
    if not reason.strip():
        raise LedgerContractError("administrative termination reason must be non-empty")
    evidence_status = _mapping(validated["evidence_status"], context="state.evidence_status")
    if evidence_status.get("experiment_status") != "ACTIVE":
        raise LedgerContractError("EXPERIMENT_ALREADY_TERMINAL")
    return _build_state(
        accepted_targets=cast(list[JsonObject], validated["accepted_targets"]),
        technical_exclusions=cast(list[JsonObject], validated["technical_exclusions"]),
        administrative_termination={
            "reason": reason.strip(),
            "status": "ADMINISTRATIVELY_TERMINATED",
        },
    )


def report_payload(state: Mapping[str, object]) -> JsonObject:
    """Return an all-60-stream report; no best-cell projection exists."""

    validated = validate_and_replay_state(state)
    return {
        "accepted_target_identities": validated["accepted_target_identities"],
        "contract_binding": validated["contract_binding"],
        "evidence_status": validated["evidence_status"],
        "reporting": validated["reporting"],
        "schema_version": REPORT_SCHEMA_VERSION,
        "streams": validated["streams"],
        "technical_exclusions": validated["technical_exclusions"],
    }


def _parse_json_object(raw: bytes, *, context: str) -> Mapping[str, object]:
    try:
        parsed = cast(object, json.loads(raw))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LedgerContractError(f"{context} is not valid UTF-8 JSON") from exc
    return _mapping(parsed, context=context)


def load_contract_file(path: Path = DEFAULT_CONTRACT_PATH) -> JsonObject:
    raw = path.read_bytes()
    expected = statistical_contract_bytes()
    if raw != expected:
        raise LedgerContractError("STATISTICAL_CONTRACT_ARTIFACT_DRIFT")
    return statistical_contract()


def load_state_file(path: Path) -> JsonObject:
    raw = path.read_bytes()
    parsed = _parse_json_object(raw, context="ledger state")
    if canonical_json_bytes(parsed) != raw:
        raise LedgerContractError("STATE_SERIALIZATION_IS_NOT_CANONICAL")
    return validate_and_replay_state(parsed)


def _atomic_replace_bytes(path: Path, desired: bytes, *, expected: bytes | None) -> bool:
    if not path.parent.is_dir():
        raise LedgerContractError(f"output parent does not exist: {path.parent}")
    observed = path.read_bytes() if path.exists() else None
    if observed == desired:
        return False
    if observed != expected:
        raise LedgerConflictError(f"destination changed before write: {path}")

    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.t540-")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(desired)
            handle.flush()
            os.fsync(handle.fileno())
        current = path.read_bytes() if path.exists() else None
        if current != expected:
            raise LedgerConflictError(f"destination changed during write: {path}")
        os.replace(temporary, path)
        if path.read_bytes() != desired:
            raise LedgerContractError(f"readback differs after atomic write: {path}")
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def write_contract_file(path: Path = DEFAULT_CONTRACT_PATH) -> bool:
    """Build twice, then atomically materialize the exact generated contract."""

    first = statistical_contract_bytes()
    second = statistical_contract_bytes()
    if first != second:
        raise RuntimeError("statistical contract generation is not byte deterministic")
    existing = path.read_bytes() if path.exists() else None
    return _atomic_replace_bytes(path, first, expected=existing)


def initialize_state_file(path: Path) -> Literal["CREATED", "EXACT_IDEMPOTENT_NO_OP"]:
    """Create an empty ledger once; never truncate a processed ledger."""

    desired = canonical_json_bytes(initial_state())
    if not path.exists():
        _atomic_replace_bytes(path, desired, expected=None)
        return "CREATED"
    current = load_state_file(path)
    if cast(list[object], current["processed_target_identities"]):
        raise NoResetError("NO_RESET_AFTER_EVIDENCE")
    if path.read_bytes() != desired:
        raise NoResetError("NO_STATE_REINITIALIZATION")
    return "EXACT_IDEMPOTENT_NO_OP"


def persist_state_update(path: Path, state: Mapping[str, object], *, expected: bytes) -> bool:
    validated = validate_and_replay_state(state)
    return _atomic_replace_bytes(path, canonical_json_bytes(validated), expected=expected)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    contract = subparsers.add_parser("build-contract")
    contract.add_argument("--output-json", type=Path, default=DEFAULT_CONTRACT_PATH)

    initialize = subparsers.add_parser("init")
    initialize.add_argument("--state-json", type=Path, required=True)
    initialize.add_argument("--contract-json", type=Path, default=DEFAULT_CONTRACT_PATH)

    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("--state-json", type=Path, required=True)
    ingest.add_argument("--target-result-json", type=Path, required=True)
    ingest.add_argument("--contract-json", type=Path, default=DEFAULT_CONTRACT_PATH)

    report = subparsers.add_parser("report")
    report.add_argument("--state-json", type=Path, required=True)
    report.add_argument("--output-json", type=Path)
    report.add_argument("--contract-json", type=Path, default=DEFAULT_CONTRACT_PATH)

    terminate = subparsers.add_parser("terminate-administratively")
    terminate.add_argument("--state-json", type=Path, required=True)
    terminate.add_argument("--reason", required=True)
    terminate.add_argument("--contract-json", type=Path, default=DEFAULT_CONTRACT_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build-contract":
        write_contract_file(args.output_json)
        print(statistical_contract_artifact_sha256())
        return 0

    load_contract_file(args.contract_json)
    if args.command == "init":
        print(initialize_state_file(args.state_json))
        return 0
    if args.command == "ingest":
        before = args.state_json.read_bytes()
        state = load_state_file(args.state_json)
        source = _parse_json_object(args.target_result_json.read_bytes(), context="target result")
        result = ingest_target_result(state, source)
        if result.disposition != "EXACT_IDEMPOTENT_NO_OP":
            persist_state_update(args.state_json, result.state, expected=before)
        print(result.disposition)
        return 0
    if args.command == "report":
        report = report_payload(load_state_file(args.state_json))
        encoded = canonical_json_bytes(report)
        if args.output_json is None:
            print(encoded.decode(), end="")
        else:
            existing = args.output_json.read_bytes() if args.output_json.exists() else None
            _atomic_replace_bytes(args.output_json, encoded, expected=existing)
        return 0
    if args.command == "terminate-administratively":
        before = args.state_json.read_bytes()
        state = administratively_terminate(load_state_file(args.state_json), reason=args.reason)
        persist_state_update(args.state_json, state, expected=before)
        print("ADMINISTRATIVELY_TERMINATED")
        return 0
    raise LedgerContractError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
