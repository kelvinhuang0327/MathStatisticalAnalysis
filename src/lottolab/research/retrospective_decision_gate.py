"""Retrospective bundle-level statistical decision gate.

Descriptive rate/Pareto comparison output is not confirmatory evidence.
This module screens frozen hit-count observations with exact one-sided
upper-tail binomial tests and Holm step-down families, while preserving
the descriptive frontier, horizon-power annotations, independent QC/harm
flags, and unresolved futility fields.

It is a ``RETROSPECTIVE_BUNDLE_LEVEL_DECISION_GATE`` helper. It is not a
pre-registered analysis, not program-level confirmatory FWER control, not
proof that every strategy has zero advantage, and not proof of lottery
fairness. Future prospective use must load a separately frozen config.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from lottolab.research.exact_statistics import (
    binomial_exact_minimum_detectable_lift,
    binomial_exact_upper_critical_value,
    binomial_lower_tail,
    binomial_two_sided_exact_p_value,
    binomial_upper_tail,
    holm_bonferroni_adjusted,
    holm_step_down_rejections,
)

_UNSET = "UNSET"
_UNKNOWN = "UNKNOWN"
_NONE = "NONE"
_YES = "YES"
_NO = "NO"
_DEFAULT_CONFIG_NAME = "biglotto_l2_pairwise_retrospective_decision_gate_r1.json"
_HORIZON_50 = "50"
_FULL_REFERENCE = "FULL_REFERENCE"
_FORBIDDEN_TOKENS = ("SCIENTIFICALLY_MEANINGFUL", "MAX_ANSWERABLE_LIFT")
# IEEE-754 binary64 log-sum-exp tails and 80-step bisection. Oracle lifts are
# 12-significant-digit displays of the same critical-value/power definition.
MDE_NUMERIC_REPRESENTATION = (
    "float64_log_sum_exp_binomial_tail; 80-step bisection on lift in [1, 1/p0]"
)
MDE_COMPARISON_TOLERANCE_ABS = 1e-11
# float64 log-sum-exp vs the independent mpmath oracle; relative error ~1e-12.
P_VALUE_COMPARISON_TOLERANCE_ABS = 1e-14


@dataclass(frozen=True, slots=True)
class NullSuccessProbability:
    numerator: int
    denominator: int

    @property
    def as_fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    @property
    def as_float(self) -> float:
        return float(self.as_fraction)


@dataclass(frozen=True, slots=True)
class RetrospectiveDecisionGateConfig:
    config_id: str
    scientific_classification: str
    program_level_confirmatory: bool
    primary_candidates: tuple[str, ...]
    primary_endpoints: tuple[str, ...]
    primary_family_size: int
    sensitivity_endpoints: tuple[str, ...]
    sensitivity_family_size: int
    alpha: float
    power_target: float
    null_success_probability: NullSuccessProbability
    owner_minimum_worthwhile_lift: str
    futility_rule: str
    current_available_common_target_count: int
    current_frozen_common_target_historical_budget: str
    additional_retrospective_common_targets: str
    low_expected_count_threshold: float
    moderate_lift: float
    qc_candidate: str
    qc_endpoint: str
    c6_minimal_qc_audit: str
    c6_further_engineering_audit: str
    candidate_expansion_when_futility_unresolved: str
    unresolved_candidate_status_when_futility_unresolved: str
    unresolved_candidate_status_fields: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class EndpointObservation:
    candidate: str
    endpoint: str
    n: int
    hits: int

    @property
    def rate(self) -> Fraction:
        return Fraction(self.hits, self.n)

    @property
    def test_id(self) -> str:
        return f"{self.candidate}:{self.endpoint}"


@dataclass(frozen=True, slots=True)
class FamilyTestRecord:
    candidate: str
    endpoint: str
    n: int
    hits: int
    upper_tail_p: float
    holm_adjusted_p: float
    holm_rank: int
    holm_first_step_threshold: float
    rejected: bool

    @property
    def test_id(self) -> str:
        return f"{self.candidate}:{self.endpoint}"


@dataclass(frozen=True, slots=True)
class ExactMdeEntry:
    n: int
    alpha: float
    k_star: int
    mde_lift: float
    label: str


@dataclass(frozen=True, slots=True)
class HorizonFiftyAnnotation:
    low_expected_count: str
    low_power_for_moderate_lift: str
    primary_decision_grade: str
    descriptive_use_only: str
    expected_count: float


@dataclass(frozen=True, slots=True)
class C6QcAnnotation:
    harm_or_antisignal_qc_flag: str
    minimal_qc_audit: str
    further_engineering_audit: str
    hits: int
    n: int
    lower_tail_p: float
    two_sided_p: float
    upper_tail_p: float


@dataclass(frozen=True, slots=True)
class RetrospectiveDecisionGateResult:
    config: RetrospectiveDecisionGateConfig
    descriptive_rate_frontier: tuple[str, ...]
    descriptive_frontier_without_horizon_50: tuple[str, ...]
    primary_family: tuple[FamilyTestRecord, ...]
    sensitivity_family: tuple[FamilyTestRecord, ...]
    primary_holm_discoveries: tuple[str, ...]
    sensitivity_holm_discoveries: tuple[str, ...]
    program_level_confirmatory_superiority_established: str
    decision_grade_frontier_available: str
    horizon_50: HorizonFiftyAnnotation
    single_test_mde: tuple[ExactMdeEntry, ...]
    primary_holm_first_step_mde: tuple[ExactMdeEntry, ...]
    sensitivity_holm_first_step_mde: tuple[ExactMdeEntry, ...]
    c6_qc: C6QcAnnotation
    owner_minimum_worthwhile_lift: str
    futility_rule: str
    futility_established: str
    candidate_expansion: str
    unresolved_candidate_statuses: Mapping[str, str]


def default_config_path() -> Path:
    return Path(__file__).resolve().parent / "configs" / _DEFAULT_CONFIG_NAME


def load_retrospective_decision_gate_config(
    path: Path | None = None,
) -> RetrospectiveDecisionGateConfig:
    config_path = default_config_path() if path is None else path
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    null_payload = payload["null_success_probability"]
    primary_candidates = tuple(payload["primary_candidates"])
    primary_endpoints = tuple(payload["primary_endpoints"])
    sensitivity_endpoints = tuple(payload["sensitivity_endpoints"])
    primary_family_size = int(payload["primary_family_size"])
    sensitivity_family_size = int(payload["sensitivity_family_size"])
    if primary_family_size != len(primary_candidates) * len(primary_endpoints):
        raise ValueError("PRIMARY_FAMILY_SIZE does not match candidates x endpoints")
    if sensitivity_family_size != len(primary_candidates) * len(sensitivity_endpoints):
        raise ValueError("SENSITIVITY_FAMILY_SIZE does not match candidates x endpoints")
    if _FULL_REFERENCE in primary_endpoints:
        raise ValueError("FULL_REFERENCE must not enter the primary family")
    if _FULL_REFERENCE not in sensitivity_endpoints:
        raise ValueError("FULL_REFERENCE must remain in the sensitivity family")

    return RetrospectiveDecisionGateConfig(
        config_id=str(payload["config_id"]),
        scientific_classification=str(payload["scientific_classification"]),
        program_level_confirmatory=bool(payload["program_level_confirmatory"]),
        primary_candidates=primary_candidates,
        primary_endpoints=primary_endpoints,
        primary_family_size=primary_family_size,
        sensitivity_endpoints=sensitivity_endpoints,
        sensitivity_family_size=sensitivity_family_size,
        alpha=float(payload["alpha"]),
        power_target=float(payload["power_target"]),
        null_success_probability=NullSuccessProbability(
            numerator=int(null_payload["numerator"]),
            denominator=int(null_payload["denominator"]),
        ),
        owner_minimum_worthwhile_lift=str(payload["owner_minimum_worthwhile_lift"]),
        futility_rule=str(payload["futility_rule"]),
        current_available_common_target_count=int(payload["current_available_common_target_count"]),
        current_frozen_common_target_historical_budget=str(
            payload["current_frozen_common_target_historical_budget"]
        ),
        additional_retrospective_common_targets=str(
            payload["additional_retrospective_common_targets"]
        ),
        low_expected_count_threshold=float(payload["low_expected_count_threshold"]),
        moderate_lift=float(payload["moderate_lift"]),
        qc_candidate=str(payload["qc_candidate"]),
        qc_endpoint=str(payload["qc_endpoint"]),
        c6_minimal_qc_audit=str(payload["c6_minimal_qc_audit"]),
        c6_further_engineering_audit=str(payload["c6_further_engineering_audit"]),
        candidate_expansion_when_futility_unresolved=str(
            payload["candidate_expansion_when_futility_unresolved"]
        ),
        unresolved_candidate_status_when_futility_unresolved=str(
            payload["unresolved_candidate_status_when_futility_unresolved"]
        ),
        unresolved_candidate_status_fields={
            str(key): str(value)
            for key, value in payload["unresolved_candidate_status_fields"].items()
        },
    )


def load_endpoint_observations_from_seven_candidate_metric_matrix(
    path: Path,
) -> tuple[EndpointObservation, ...]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    observations = tuple(
        EndpointObservation(
            candidate=str(row["candidate"]),
            endpoint=str(row["horizon"]),
            n=int(row["N"]),
            hits=int(row["any_prize_count"]),
        )
        for row in rows
    )
    if not observations:
        raise ValueError("metric matrix contains no observations")
    return observations


def descriptive_rate_frontier(
    observations: Sequence[EndpointObservation],
    *,
    candidates: Sequence[str],
    endpoints: Sequence[str],
) -> tuple[str, ...]:
    rates = _rate_vectors(observations, candidates, endpoints)
    undominated: list[str] = []
    for candidate in candidates:
        if any(
            _dominates(rates[other], rates[candidate]) for other in candidates if other != candidate
        ):
            continue
        undominated.append(candidate)
    return tuple(undominated)


def evaluate_retrospective_decision_gate(
    observations: Sequence[EndpointObservation],
    config: RetrospectiveDecisionGateConfig,
) -> RetrospectiveDecisionGateResult:
    index = {(item.candidate, item.endpoint): item for item in observations}
    p0 = config.null_success_probability.as_float
    primary_family = _screen_family(
        index,
        candidates=config.primary_candidates,
        endpoints=config.primary_endpoints,
        expected_family_size=config.primary_family_size,
        p0=p0,
        alpha=config.alpha,
    )
    sensitivity_family = _screen_family(
        index,
        candidates=config.primary_candidates,
        endpoints=config.sensitivity_endpoints,
        expected_family_size=config.sensitivity_family_size,
        p0=p0,
        alpha=config.alpha,
    )
    if any(record.endpoint == _FULL_REFERENCE for record in primary_family):
        raise ValueError("FULL_REFERENCE leaked into the primary family")

    primary_discoveries = tuple(record.test_id for record in primary_family if record.rejected)
    sensitivity_discoveries = tuple(
        record.test_id for record in sensitivity_family if record.rejected
    )
    futility_unresolved = (
        config.owner_minimum_worthwhile_lift == _UNSET or config.futility_rule == _UNSET
    )
    futility_established = _UNKNOWN if futility_unresolved else _NO
    candidate_expansion = (
        config.candidate_expansion_when_futility_unresolved if futility_unresolved else _UNSET
    )
    unresolved_statuses = (
        dict(config.unresolved_candidate_status_fields)
        if futility_unresolved
        else {
            key: config.unresolved_candidate_status_when_futility_unresolved
            for key in config.unresolved_candidate_status_fields
        }
    )
    program_level = _YES if config.program_level_confirmatory and primary_discoveries else _NO
    decision_grade_frontier = (
        _YES if config.program_level_confirmatory and primary_discoveries else _NO
    )

    return RetrospectiveDecisionGateResult(
        config=config,
        descriptive_rate_frontier=descriptive_rate_frontier(
            observations,
            candidates=config.primary_candidates,
            endpoints=config.primary_endpoints,
        ),
        descriptive_frontier_without_horizon_50=descriptive_rate_frontier(
            observations,
            candidates=config.primary_candidates,
            endpoints=tuple(
                endpoint for endpoint in config.primary_endpoints if endpoint != _HORIZON_50
            ),
        ),
        primary_family=primary_family,
        sensitivity_family=sensitivity_family,
        primary_holm_discoveries=primary_discoveries,
        sensitivity_holm_discoveries=sensitivity_discoveries,
        program_level_confirmatory_superiority_established=program_level,
        decision_grade_frontier_available=decision_grade_frontier,
        horizon_50=_annotate_horizon_50(config, p0),
        single_test_mde=_mde_table(
            sample_sizes=_mde_sample_sizes(config),
            p0=p0,
            alpha=config.alpha,
            power_target=config.power_target,
            label="SINGLE_TEST_80PCT_MDE",
        ),
        primary_holm_first_step_mde=_mde_table(
            sample_sizes=tuple(int(endpoint) for endpoint in config.primary_endpoints),
            p0=p0,
            alpha=config.alpha / config.primary_family_size,
            power_target=config.power_target,
            label="HOLM_FIRST_STEP_MDE",
        ),
        sensitivity_holm_first_step_mde=_mde_table(
            sample_sizes=_mde_sample_sizes(config),
            p0=p0,
            alpha=config.alpha / config.sensitivity_family_size,
            power_target=config.power_target,
            label="HOLM_FIRST_STEP_MDE",
        ),
        c6_qc=_annotate_c6_qc(index, config, p0),
        owner_minimum_worthwhile_lift=config.owner_minimum_worthwhile_lift,
        futility_rule=config.futility_rule,
        futility_established=futility_established,
        candidate_expansion=candidate_expansion,
        unresolved_candidate_statuses=unresolved_statuses,
    )


def compact_result_document(
    result: RetrospectiveDecisionGateResult,
) -> dict[str, object]:
    config = result.config
    p0 = config.null_success_probability
    document: dict[str, object] = {
        "CONFIG_ID": config.config_id,
        "SCIENTIFIC_CLASSIFICATION": config.scientific_classification,
        "NULL_P0": f"{p0.numerator}/{p0.denominator}",
        "DESCRIPTIVE_RATE_FRONTIER": _join_or_none(result.descriptive_rate_frontier),
        "DESCRIPTIVE_FRONTIER_WITHOUT_HORIZON_50": _join_or_none(
            result.descriptive_frontier_without_horizon_50
        ),
        "RETROSPECTIVE_PRIMARY_FAMILY_SIZE": config.primary_family_size,
        "RETROSPECTIVE_SENSITIVITY_FAMILY_SIZE": config.sensitivity_family_size,
        "RETROSPECTIVE_PRIMARY_HOLM_SUPERIORITY_DISCOVERIES": _join_or_none(
            result.primary_holm_discoveries
        ),
        "RETROSPECTIVE_SENSITIVITY_HOLM_SUPERIORITY_DISCOVERIES": _join_or_none(
            result.sensitivity_holm_discoveries
        ),
        "PROGRAM_LEVEL_CONFIRMATORY_SUPERIORITY_ESTABLISHED": (
            result.program_level_confirmatory_superiority_established
        ),
        "HORIZON_50_LOW_EXPECTED_COUNT": result.horizon_50.low_expected_count,
        "HORIZON_50_LOW_POWER_FOR_MODERATE_LIFT": result.horizon_50.low_power_for_moderate_lift,
        "HORIZON_50_PRIMARY_DECISION_GRADE": result.horizon_50.primary_decision_grade,
        "HORIZON_50_DESCRIPTIVE_USE_ONLY": result.horizon_50.descriptive_use_only,
        "SINGLE_TEST_80PCT_MDE": _mde_entries(result.single_test_mde),
        "PRIMARY_HOLM_FIRST_STEP_MDE": _mde_entries(result.primary_holm_first_step_mde),
        "SENSITIVITY_HOLM_FIRST_STEP_MDE": _mde_entries(result.sensitivity_holm_first_step_mde),
        "MDE_NUMERIC_REPRESENTATION": MDE_NUMERIC_REPRESENTATION,
        "MDE_COMPARISON_TOLERANCE_ABS": MDE_COMPARISON_TOLERANCE_ABS,
        "P_VALUE_COMPARISON_TOLERANCE_ABS": P_VALUE_COMPARISON_TOLERANCE_ABS,
        "CURRENT_AVAILABLE_COMMON_TARGET_COUNT": config.current_available_common_target_count,
        "CURRENT_FROZEN_COMMON_TARGET_HISTORICAL_BUDGET": (
            config.current_frozen_common_target_historical_budget
        ),
        "ADDITIONAL_RETROSPECTIVE_COMMON_TARGETS": config.additional_retrospective_common_targets,
        "OWNER_MINIMUM_WORTHWHILE_LIFT": result.owner_minimum_worthwhile_lift,
        "FUTILITY_RULE": result.futility_rule,
        "FUTILITY_ESTABLISHED": result.futility_established,
        "C6_HARM_OR_ANTISIGNAL_QC_FLAG": result.c6_qc.harm_or_antisignal_qc_flag,
        "C6_MINIMAL_QC_AUDIT": result.c6_qc.minimal_qc_audit,
        "C6_FURTHER_ENGINEERING_AUDIT": result.c6_qc.further_engineering_audit,
        "DECISION_GRADE_FRONTIER_AVAILABLE": result.decision_grade_frontier_available,
        "CANDIDATE_EXPANSION": result.candidate_expansion,
        "C7_V3_STATUS": result.unresolved_candidate_statuses["C7_V3_STATUS"],
        "C9_STATUS": result.unresolved_candidate_statuses["C9_STATUS"],
        "C10_STATUS": result.unresolved_candidate_statuses["C10_STATUS"],
        "C11_STATUS": result.unresolved_candidate_statuses["C11_STATUS"],
        "C6_FULL_REFERENCE_HITS": f"{result.c6_qc.hits}/{result.c6_qc.n}",
        "C6_LOWER_TAIL_EXACT_P": result.c6_qc.lower_tail_p,
        "C6_TWO_SIDED_EXACT_P": result.c6_qc.two_sided_p,
        "HORIZON_50_EXPECTED_COUNT": result.horizon_50.expected_count,
        "HOLM_FIRST_STEP_MDE_NOTE": (
            "HOLM_FIRST_STEP_MDE uses alpha/m only; it is not the effective "
            "alpha of every Holm test"
        ),
    }
    serialized = json.dumps(document)
    for token in _FORBIDDEN_TOKENS:
        if token in serialized:
            raise ValueError(f"forbidden token {token} emitted by decision gate")
    return document


def evaluate_metric_matrix(
    matrix_path: Path,
    config_path: Path | None = None,
) -> RetrospectiveDecisionGateResult:
    return evaluate_retrospective_decision_gate(
        load_endpoint_observations_from_seven_candidate_metric_matrix(matrix_path),
        load_retrospective_decision_gate_config(config_path),
    )


def write_compact_decision_artifact(
    result: RetrospectiveDecisionGateResult,
    output_dir: Path,
    *,
    filename: str = "decision_gate_result.json",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    document = compact_result_document(result)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (output_dir / "SHA256SUMS").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return path


def _screen_family(
    index: Mapping[tuple[str, str], EndpointObservation],
    *,
    candidates: Sequence[str],
    endpoints: Sequence[str],
    expected_family_size: int,
    p0: float,
    alpha: float,
) -> tuple[FamilyTestRecord, ...]:
    ordered: list[EndpointObservation] = []
    for candidate in candidates:
        for endpoint in endpoints:
            try:
                ordered.append(index[(candidate, endpoint)])
            except KeyError as exc:
                raise ValueError(f"missing observation for {candidate}:{endpoint}") from exc
    if len(ordered) != expected_family_size:
        raise ValueError(f"family size {len(ordered)} != expected {expected_family_size}")

    p_values = tuple(binomial_upper_tail(item.n, item.hits, p0) for item in ordered)
    adjusted = holm_bonferroni_adjusted(p_values)
    rejected = holm_step_down_rejections(p_values, alpha=alpha)
    order = sorted(range(len(ordered)), key=lambda i: (p_values[i], i))
    ranks = [0] * len(ordered)
    for rank, index_i in enumerate(order, start=1):
        ranks[index_i] = rank
    first_step_threshold = alpha / len(ordered)
    return tuple(
        FamilyTestRecord(
            candidate=item.candidate,
            endpoint=item.endpoint,
            n=item.n,
            hits=item.hits,
            upper_tail_p=p_values[i],
            holm_adjusted_p=adjusted[i],
            holm_rank=ranks[i],
            holm_first_step_threshold=first_step_threshold,
            rejected=rejected[i],
        )
        for i, item in enumerate(ordered)
    )


def _rate_vectors(
    observations: Sequence[EndpointObservation],
    candidates: Sequence[str],
    endpoints: Sequence[str],
) -> dict[str, tuple[Fraction, ...]]:
    index = {(item.candidate, item.endpoint): item for item in observations}
    vectors: dict[str, tuple[Fraction, ...]] = {}
    for candidate in candidates:
        rates: list[Fraction] = []
        for endpoint in endpoints:
            try:
                rates.append(index[(candidate, endpoint)].rate)
            except KeyError as exc:
                raise ValueError(f"missing observation for {candidate}:{endpoint}") from exc
        vectors[candidate] = tuple(rates)
    return vectors


def _dominates(left: Sequence[Fraction], right: Sequence[Fraction]) -> bool:
    if len(left) != len(right):
        raise ValueError("rate vectors must share a horizon set")
    at_least_as_good = all(a >= b for a, b in zip(left, right, strict=True))
    strictly_better = any(a > b for a, b in zip(left, right, strict=True))
    return at_least_as_good and strictly_better


def _annotate_horizon_50(
    config: RetrospectiveDecisionGateConfig, p0: float
) -> HorizonFiftyAnnotation:
    n = 50
    expected = n * p0
    low_expected = expected < config.low_expected_count_threshold
    mde = binomial_exact_minimum_detectable_lift(
        n, p0, alpha=config.alpha, power_target=config.power_target
    )
    low_power = mde > config.moderate_lift
    decision_grade = not low_expected and not low_power
    return HorizonFiftyAnnotation(
        low_expected_count=_YES if low_expected else _NO,
        low_power_for_moderate_lift=_YES if low_power else _NO,
        primary_decision_grade=_YES if decision_grade else _NO,
        descriptive_use_only=_NO if decision_grade else _YES,
        expected_count=expected,
    )


def _annotate_c6_qc(
    index: Mapping[tuple[str, str], EndpointObservation],
    config: RetrospectiveDecisionGateConfig,
    p0: float,
) -> C6QcAnnotation:
    try:
        observation = index[(config.qc_candidate, config.qc_endpoint)]
    except KeyError as exc:
        raise ValueError("missing C6 FULL_REFERENCE observation") from exc
    lower = binomial_lower_tail(observation.n, observation.hits, p0)
    two_sided = binomial_two_sided_exact_p_value(observation.n, observation.hits, p0)
    upper = binomial_upper_tail(observation.n, observation.hits, p0)
    harm = lower <= config.alpha
    return C6QcAnnotation(
        harm_or_antisignal_qc_flag=_YES if harm else _NO,
        minimal_qc_audit=config.c6_minimal_qc_audit,
        further_engineering_audit=config.c6_further_engineering_audit,
        hits=observation.hits,
        n=observation.n,
        lower_tail_p=lower,
        two_sided_p=two_sided,
        upper_tail_p=upper,
    )


def _mde_sample_sizes(config: RetrospectiveDecisionGateConfig) -> tuple[int, ...]:
    sizes = [int(endpoint) for endpoint in config.primary_endpoints]
    sizes.append(config.current_available_common_target_count)
    return tuple(sizes)


def _mde_table(
    *,
    sample_sizes: Sequence[int],
    p0: float,
    alpha: float,
    power_target: float,
    label: str,
) -> tuple[ExactMdeEntry, ...]:
    return tuple(
        ExactMdeEntry(
            n=n,
            alpha=alpha,
            k_star=binomial_exact_upper_critical_value(n, p0, alpha),
            mde_lift=binomial_exact_minimum_detectable_lift(
                n, p0, alpha=alpha, power_target=power_target
            ),
            label=label,
        )
        for n in sample_sizes
    )


def _mde_entries(entries: Sequence[ExactMdeEntry]) -> dict[str, dict[str, int | float | str]]:
    return {
        str(entry.n): {
            "k_star": entry.k_star,
            "mde_lift": entry.mde_lift,
            "alpha": entry.alpha,
            "label": entry.label,
        }
        for entry in entries
    }


def _join_or_none(values: Sequence[str]) -> str:
    return ",".join(values) if values else _NONE
