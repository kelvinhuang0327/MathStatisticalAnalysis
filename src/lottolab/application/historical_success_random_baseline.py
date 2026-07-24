"""Exact official-six-number IID random baseline for Historical Prefix windows.

This application-owned projection is deliberately separate from the legacy
success-window result.  It recomputes ticket outcomes from raw six-number
operands and uses only standard-library integer and rational arithmetic.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from math import comb, gcd

from lottolab.application.historical_prefix_success_windows import (
    SUPPORTED_PREFIX_COUNTS,
    HistoricalPrefixSuccessCriterion,
)
from lottolab.domain.strategy_success_evaluation import WindowKind
from lottolab.domain.strategy_success_measurement import DEFAULT_WINDOW_POLICY_VERSION

RANDOM_BASELINE_POLICY_VERSION = (
    "HISTORICAL_SUCCESS_RANDOM_NULL_BASELINE_R1_OFFICIAL_SIX_NUMBER_IID"
)
LEGAL_TICKET_COUNT = comb(49, 6)
NOMINAL_TICKET_COUNT_EQUIVALENT = "nominal-ticket-count equivalent"
INTERPRETATION_CAVEAT = (
    "Descriptive official-six-number IID random benchmark only. This result does not "
    "establish statistical significance, ranking, promotion, rejection, prediction "
    "quality, production eligibility, or monetary cost equivalence."
)

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_CRITERION_PARAMETERS = {
    HistoricalPrefixSuccessCriterion.M3_PLUS: (3, False),
    HistoricalPrefixSuccessCriterion.M4_PLUS: (4, False),
    HistoricalPrefixSuccessCriterion.M5_PLUS: (5, False),
    HistoricalPrefixSuccessCriterion.M6: (6, False),
    HistoricalPrefixSuccessCriterion.M2_PLUS_SPECIAL: (2, True),
    HistoricalPrefixSuccessCriterion.M3_PLUS_SPECIAL: (3, True),
    HistoricalPrefixSuccessCriterion.M4_PLUS_SPECIAL: (4, True),
    HistoricalPrefixSuccessCriterion.M5_PLUS_SPECIAL: (5, True),
}
_FROZEN_CRITERION_COUNTS = {
    HistoricalPrefixSuccessCriterion.M3_PLUS: 260_624,
    HistoricalPrefixSuccessCriterion.M4_PLUS: 13_804,
    HistoricalPrefixSuccessCriterion.M5_PLUS: 259,
    HistoricalPrefixSuccessCriterion.M6: 1,
    HistoricalPrefixSuccessCriterion.M2_PLUS_SPECIAL: 190_056,
    HistoricalPrefixSuccessCriterion.M3_PLUS_SPECIAL: 17_856,
    HistoricalPrefixSuccessCriterion.M4_PLUS_SPECIAL: 636,
    HistoricalPrefixSuccessCriterion.M5_PLUS_SPECIAL: 6,
}


class HistoricalSuccessRandomBaselineContractError(ValueError):
    """The caller supplied a contradictory or non-canonical baseline contract."""


class HistoricalSuccessRandomBaselineSamplingPolicy(StrEnum):
    UNIFORM_IID_LEGAL_TICKETS_WITH_REPLACEMENT = (
        "UNIFORM_IID_LEGAL_TICKETS_WITH_REPLACEMENT"
    )


class HistoricalSuccessRandomBaselineReadiness(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class HistoricalSuccessRandomBaselineNotReadyReason(StrEnum):
    NO_OBSERVATIONS = "NO_OBSERVATIONS"
    WINDOW_INCOMPLETE = "WINDOW_INCOMPLETE"
    EXCLUDED_OBSERVATIONS = "EXCLUDED_OBSERVATIONS"
    SOURCE_TICKET_SEMANTICS_CONFLICT = "SOURCE_TICKET_SEMANTICS_CONFLICT"
    EXACT_COMPUTATION_UNAVAILABLE = "EXACT_COMPUTATION_UNAVAILABLE"


_REASON_ORDER = tuple(HistoricalSuccessRandomBaselineNotReadyReason)


def _contract_error(message: str) -> HistoricalSuccessRandomBaselineContractError:
    return HistoricalSuccessRandomBaselineContractError(message)


def _require_text(value: str, name: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise _contract_error(f"{name} must be a non-empty canonical string")


def _require_sha256(value: str, name: str) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise _contract_error(f"{name} must be an exact lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class HistoricalSuccessExactRational:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise _contract_error("exact rational fields must be integers")
        if self.denominator <= 0:
            raise _contract_error("exact rational denominator must be positive")
        if self.numerator < 0:
            raise _contract_error("exact rational numerator must be non-negative")
        if gcd(self.numerator, self.denominator) != 1:
            raise _contract_error("exact rational must be reduced")

    @classmethod
    def from_fraction(cls, value: Fraction) -> HistoricalSuccessExactRational:
        if type(value) is not Fraction or value < 0:
            raise _contract_error("value must be a non-negative Fraction")
        return cls(value.numerator, value.denominator)

    def as_fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    def canonical_dict(self) -> dict[str, int]:
        return {"denominator": self.denominator, "numerator": self.numerator}


def _derived_criterion_count(criterion: HistoricalPrefixSuccessCriterion) -> int:
    minimum_main_hits, require_special_hit = _CRITERION_PARAMETERS[criterion]
    if require_special_hit:
        return sum(
            comb(6, main_hits) * comb(42, 5 - main_hits)
            for main_hits in range(minimum_main_hits, 6)
        )
    return sum(
        comb(6, main_hits) * comb(43, 6 - main_hits)
        for main_hits in range(minimum_main_hits, 7)
    )


def criterion_success_ticket_count(criterion: HistoricalPrefixSuccessCriterion) -> int:
    if type(criterion) is not HistoricalPrefixSuccessCriterion:
        raise _contract_error("criterion is outside the closed supported set")
    derived = _derived_criterion_count(criterion)
    frozen = _FROZEN_CRITERION_COUNTS[criterion]
    if derived != frozen:
        raise ArithmeticError("frozen criterion count does not match exact combinatorics")
    return frozen


def portfolio_success_probability(
    criterion: HistoricalPrefixSuccessCriterion,
    prefix_count: int,
) -> HistoricalSuccessExactRational:
    if type(prefix_count) is not int or prefix_count <= 0:
        raise _contract_error("prefix_count must be a positive integer")
    success_count = criterion_success_ticket_count(criterion)
    failure_count = LEGAL_TICKET_COUNT - success_count
    probability = Fraction(
        LEGAL_TICKET_COUNT**prefix_count - failure_count**prefix_count,
        LEGAL_TICKET_COUNT**prefix_count,
    )
    return HistoricalSuccessExactRational.from_fraction(probability)


def binomial_upper_tail(
    observation_count: int,
    observed_success_count: int,
    probability: HistoricalSuccessExactRational,
) -> HistoricalSuccessExactRational:
    if type(observation_count) is not int or observation_count < 0:
        raise _contract_error("observation_count must be a non-negative integer")
    if (
        type(observed_success_count) is not int
        or not 0 <= observed_success_count <= observation_count
    ):
        raise _contract_error(
            "observed_success_count must be between zero and observation_count"
        )
    if type(probability) is not HistoricalSuccessExactRational:
        raise _contract_error("probability must be an exact rational")
    if probability.numerator > probability.denominator:
        raise _contract_error("probability must be between zero and one")
    if observed_success_count == 0:
        return HistoricalSuccessExactRational(1, 1)

    success = probability.numerator
    total = probability.denominator
    failure = total - success
    denominator = total**observation_count
    if success == 0:
        return HistoricalSuccessExactRational(0, 1)
    if failure == 0:
        return HistoricalSuccessExactRational(1, 1)

    lower_term_count = observed_success_count
    upper_term_count = observation_count - observed_success_count + 1
    if upper_term_count <= lower_term_count:
        numerator = sum(
            comb(observation_count, successes)
            * success**successes
            * failure ** (observation_count - successes)
            for successes in range(observed_success_count, observation_count + 1)
        )
    else:
        lower = sum(
            comb(observation_count, successes)
            * success**successes
            * failure ** (observation_count - successes)
            for successes in range(observed_success_count)
        )
        numerator = denominator - lower
    return HistoricalSuccessExactRational.from_fraction(Fraction(numerator, denominator))


def render_exact_decimal_18(value: HistoricalSuccessExactRational) -> str:
    if type(value) is not HistoricalSuccessExactRational:
        raise _contract_error("value must be an exact rational")
    scale = 10**18
    rounded, remainder = divmod(value.numerator * scale, value.denominator)
    doubled_remainder = remainder * 2
    if doubled_remainder > value.denominator or (
        doubled_remainder == value.denominator and rounded % 2 == 1
    ):
        rounded += 1
    integer_part, fractional_part = divmod(rounded, scale)
    return f"{integer_part}.{fractional_part:018d}"


@dataclass(frozen=True, slots=True)
class HistoricalSuccessRandomBaselineCellIdentity:
    policy_version: str
    import_identity_sha256: str
    dataset_sha256: str
    source_artifact_sha256: str
    strategy_id: str
    strategy_version: str
    replicate: int
    window_kind: WindowKind
    window_policy_version: str
    prefix_count: int
    criterion: HistoricalPrefixSuccessCriterion

    def __post_init__(self) -> None:
        for name in ("policy_version", "strategy_id", "strategy_version", "window_policy_version"):
            _require_text(getattr(self, name), name)
        for name in (
            "import_identity_sha256",
            "dataset_sha256",
            "source_artifact_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        if self.policy_version != RANDOM_BASELINE_POLICY_VERSION:
            raise _contract_error("policy_version is outside the R1 contract")
        if type(self.replicate) is not int or self.replicate < 1:
            raise _contract_error("replicate must be an integer >= 1")
        if type(self.window_kind) is not WindowKind:
            raise _contract_error("window_kind must be a WindowKind")
        if self.window_policy_version != DEFAULT_WINDOW_POLICY_VERSION:
            raise _contract_error("window_policy_version must be the existing default policy")
        if type(self.prefix_count) is not int or self.prefix_count not in SUPPORTED_PREFIX_COUNTS:
            raise _contract_error("prefix_count is outside the closed supported set")
        if type(self.criterion) is not HistoricalPrefixSuccessCriterion:
            raise _contract_error("criterion is outside the closed supported set")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "criterion": self.criterion.value,
            "dataset_sha256": self.dataset_sha256,
            "import_identity_sha256": self.import_identity_sha256,
            "policy_version": self.policy_version,
            "prefix_count": self.prefix_count,
            "replicate": self.replicate,
            "source_artifact_sha256": self.source_artifact_sha256,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "window_kind": self.window_kind.value,
            "window_policy_version": self.window_policy_version,
        }


@dataclass(frozen=True, slots=True)
class HistoricalSuccessRandomBaselineTicketOperand:
    main_numbers: tuple[int, ...]
    persisted_main_hit_count: int
    persisted_legacy_special_hit: bool


@dataclass(frozen=True, slots=True)
class HistoricalSuccessRandomBaselineObservationOperand:
    target_main_numbers: tuple[int, ...]
    target_special_number: int
    tickets: tuple[HistoricalSuccessRandomBaselineTicketOperand, ...]


@dataclass(frozen=True, slots=True)
class HistoricalSuccessRandomBaselineResult:
    cell: HistoricalSuccessRandomBaselineCellIdentity
    readiness: HistoricalSuccessRandomBaselineReadiness
    reason_codes: tuple[HistoricalSuccessRandomBaselineNotReadyReason, ...]
    sampling_policy: HistoricalSuccessRandomBaselineSamplingPolicy
    ticket_count_interpretation: str
    legal_ticket_count: int
    success_ticket_count: int
    portfolio_success_probability: HistoricalSuccessExactRational
    eligible_observation_count: int
    excluded_observation_count: int
    observed_success_count: int | None
    expected_successes: HistoricalSuccessExactRational | None
    upper_tail_probability: HistoricalSuccessExactRational | None
    observed_ticket_position_count: int
    observed_distinct_ticket_count: int
    observed_duplicate_ticket_count: int
    observation_count_with_duplicates: int
    interpretation_caveat: str

    def __post_init__(self) -> None:
        if type(self.cell) is not HistoricalSuccessRandomBaselineCellIdentity:
            raise _contract_error("cell identity is malformed")
        if type(self.readiness) is not HistoricalSuccessRandomBaselineReadiness:
            raise _contract_error("readiness is outside the closed set")
        if type(self.reason_codes) is not tuple or any(
            type(reason) is not HistoricalSuccessRandomBaselineNotReadyReason
            for reason in self.reason_codes
        ):
            raise _contract_error("reason_codes must be a closed immutable tuple")
        if self.reason_codes != tuple(
            reason for reason in _REASON_ORDER if reason in self.reason_codes
        ):
            raise _contract_error("reason_codes must be unique and canonical")
        if (
            self.sampling_policy
            is not (
                HistoricalSuccessRandomBaselineSamplingPolicy
                .UNIFORM_IID_LEGAL_TICKETS_WITH_REPLACEMENT
            )
        ):
            raise _contract_error("sampling_policy is outside the R1 contract")
        if self.ticket_count_interpretation != NOMINAL_TICKET_COUNT_EQUIVALENT:
            raise _contract_error("ticket_count_interpretation is not the fixed R1 wording")
        if self.legal_ticket_count != LEGAL_TICKET_COUNT:
            raise _contract_error("legal_ticket_count does not match C(49,6)")
        if self.success_ticket_count != criterion_success_ticket_count(self.cell.criterion):
            raise _contract_error("success_ticket_count contradicts the criterion")
        if self.portfolio_success_probability != portfolio_success_probability(
            self.cell.criterion, self.cell.prefix_count
        ):
            raise _contract_error("portfolio probability contradicts the exact IID policy")
        for name in (
            "eligible_observation_count",
            "excluded_observation_count",
            "observed_ticket_position_count",
            "observed_distinct_ticket_count",
            "observed_duplicate_ticket_count",
            "observation_count_with_duplicates",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise _contract_error(f"{name} must be a non-negative integer")
        if (
            self.observed_ticket_position_count
            != self.observed_distinct_ticket_count + self.observed_duplicate_ticket_count
        ):
            raise _contract_error("duplicate disclosure counts are contradictory")
        if self.observation_count_with_duplicates > self.eligible_observation_count:
            raise _contract_error("duplicate-observation count exceeds eligible observations")
        if self.interpretation_caveat != INTERPRETATION_CAVEAT:
            raise _contract_error("interpretation caveat is not the fixed R1 text")

        if self.readiness is HistoricalSuccessRandomBaselineReadiness.READY:
            if self.reason_codes:
                raise _contract_error("READY must not carry reason codes")
            if self.eligible_observation_count == 0 or self.excluded_observation_count != 0:
                raise _contract_error("READY requires eligible observations and zero exclusions")
            if (
                type(self.observed_success_count) is not int
                or not 0 <= self.observed_success_count <= self.eligible_observation_count
                or type(self.expected_successes) is not HistoricalSuccessExactRational
                or type(self.upper_tail_probability) is not HistoricalSuccessExactRational
            ):
                raise _contract_error("READY requires complete exact result fields")
            if (
                self.observed_ticket_position_count
                != self.eligible_observation_count * self.cell.prefix_count
            ):
                raise _contract_error("READY ticket-position count must equal n * K")
            expected = HistoricalSuccessExactRational.from_fraction(
                self.eligible_observation_count
                * self.portfolio_success_probability.as_fraction()
            )
            if self.expected_successes != expected:
                raise _contract_error("expected_successes contradicts n times exact probability")
            if self.upper_tail_probability != binomial_upper_tail(
                self.eligible_observation_count,
                self.observed_success_count,
                self.portfolio_success_probability,
            ):
                raise _contract_error("upper_tail_probability contradicts the exact upper tail")
        else:
            if not self.reason_codes:
                raise _contract_error("NOT_READY requires at least one canonical reason")
            if any(
                value is not None
                for value in (
                    self.observed_success_count,
                    self.expected_successes,
                    self.upper_tail_probability,
                )
            ):
                raise _contract_error("NOT_READY must not expose inferential result fields")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "cell": self.cell.canonical_dict(),
            "eligible_observation_count": self.eligible_observation_count,
            "excluded_observation_count": self.excluded_observation_count,
            "expected_successes": (
                None
                if self.expected_successes is None
                else self.expected_successes.canonical_dict()
            ),
            "interpretation_caveat": self.interpretation_caveat,
            "legal_ticket_count": self.legal_ticket_count,
            "observation_count_with_duplicates": self.observation_count_with_duplicates,
            "observed_distinct_ticket_count": self.observed_distinct_ticket_count,
            "observed_duplicate_ticket_count": self.observed_duplicate_ticket_count,
            "observed_success_count": self.observed_success_count,
            "observed_ticket_position_count": self.observed_ticket_position_count,
            "portfolio_success_probability": self.portfolio_success_probability.canonical_dict(),
            "readiness": self.readiness.value,
            "reason_codes": [reason.value for reason in self.reason_codes],
            "sampling_policy": self.sampling_policy.value,
            "success_ticket_count": self.success_ticket_count,
            "ticket_count_interpretation": self.ticket_count_interpretation,
            "upper_tail_probability": (
                None
                if self.upper_tail_probability is None
                else self.upper_tail_probability.canonical_dict()
            ),
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


def _not_ready(
    *,
    cell: HistoricalSuccessRandomBaselineCellIdentity,
    reasons: tuple[HistoricalSuccessRandomBaselineNotReadyReason, ...],
    probability: HistoricalSuccessExactRational,
    eligible_observation_count: int,
    excluded_observation_count: int,
) -> HistoricalSuccessRandomBaselineResult:
    canonical_reasons = tuple(reason for reason in _REASON_ORDER if reason in reasons)
    return HistoricalSuccessRandomBaselineResult(
        cell=cell,
        readiness=HistoricalSuccessRandomBaselineReadiness.NOT_READY,
        reason_codes=canonical_reasons,
        sampling_policy=(
            HistoricalSuccessRandomBaselineSamplingPolicy.UNIFORM_IID_LEGAL_TICKETS_WITH_REPLACEMENT
        ),
        ticket_count_interpretation=NOMINAL_TICKET_COUNT_EQUIVALENT,
        legal_ticket_count=LEGAL_TICKET_COUNT,
        success_ticket_count=criterion_success_ticket_count(cell.criterion),
        portfolio_success_probability=probability,
        eligible_observation_count=eligible_observation_count,
        excluded_observation_count=excluded_observation_count,
        observed_success_count=None,
        expected_successes=None,
        upper_tail_probability=None,
        observed_ticket_position_count=0,
        observed_distinct_ticket_count=0,
        observed_duplicate_ticket_count=0,
        observation_count_with_duplicates=0,
        interpretation_caveat=INTERPRETATION_CAVEAT,
    )


def _valid_six_numbers(numbers: tuple[int, ...]) -> bool:
    return (
        type(numbers) is tuple
        and len(numbers) == 6
        and all(type(value) is int and 1 <= value <= 49 for value in numbers)
        and len(set(numbers)) == 6
        and numbers == tuple(sorted(numbers))
    )


def _ticket_succeeds(
    *,
    main_hit_count: int,
    official_special_hit: bool,
    criterion: HistoricalPrefixSuccessCriterion,
) -> bool:
    minimum_main_hits, require_special_hit = _CRITERION_PARAMETERS[criterion]
    return main_hit_count >= minimum_main_hits and (
        not require_special_hit or official_special_hit
    )


def evaluate_historical_success_random_baseline(
    *,
    cell: HistoricalSuccessRandomBaselineCellIdentity,
    observations: tuple[HistoricalSuccessRandomBaselineObservationOperand, ...],
    window_complete: bool,
    eligible_observation_count: int,
    excluded_observation_count: int,
    legacy_window_success_count: int,
) -> HistoricalSuccessRandomBaselineResult:
    if type(cell) is not HistoricalSuccessRandomBaselineCellIdentity:
        raise _contract_error("cell identity is malformed")
    if type(observations) is not tuple or any(
        type(item) is not HistoricalSuccessRandomBaselineObservationOperand
        for item in observations
    ):
        raise _contract_error("observations must be an immutable typed tuple")
    if type(window_complete) is not bool:
        raise _contract_error("window_complete must be a boolean")
    for name, value in (
        ("eligible_observation_count", eligible_observation_count),
        ("excluded_observation_count", excluded_observation_count),
        ("legacy_window_success_count", legacy_window_success_count),
    ):
        if type(value) is not int or value < 0:
            raise _contract_error(f"{name} must be a non-negative integer")
    if eligible_observation_count + excluded_observation_count != len(observations):
        raise _contract_error("window counts contradict the selected observation tuple")
    if legacy_window_success_count > eligible_observation_count:
        raise _contract_error("legacy success count exceeds eligible observations")

    try:
        probability = portfolio_success_probability(cell.criterion, cell.prefix_count)
    except ArithmeticError:
        probability = HistoricalSuccessExactRational(0, 1)
        return _not_ready(
            cell=cell,
            reasons=(HistoricalSuccessRandomBaselineNotReadyReason.EXACT_COMPUTATION_UNAVAILABLE,),
            probability=probability,
            eligible_observation_count=eligible_observation_count,
            excluded_observation_count=excluded_observation_count,
        )

    readiness_reasons: list[HistoricalSuccessRandomBaselineNotReadyReason] = []
    if not observations:
        readiness_reasons.append(HistoricalSuccessRandomBaselineNotReadyReason.NO_OBSERVATIONS)
    elif not window_complete:
        readiness_reasons.append(HistoricalSuccessRandomBaselineNotReadyReason.WINDOW_INCOMPLETE)
    if excluded_observation_count:
        readiness_reasons.append(
            HistoricalSuccessRandomBaselineNotReadyReason.EXCLUDED_OBSERVATIONS
        )
    if readiness_reasons:
        return _not_ready(
            cell=cell,
            reasons=tuple(readiness_reasons),
            probability=probability,
            eligible_observation_count=eligible_observation_count,
            excluded_observation_count=excluded_observation_count,
        )

    observation_successes: list[bool] = []
    distinct_ticket_count = 0
    duplicate_observation_count = 0
    for observation in observations:
        if (
            not _valid_six_numbers(observation.target_main_numbers)
            or type(observation.target_special_number) is not int
            or not 1 <= observation.target_special_number <= 49
            or observation.target_special_number in observation.target_main_numbers
            or type(observation.tickets) is not tuple
            or len(observation.tickets) < cell.prefix_count
        ):
            return _not_ready(
                cell=cell,
                reasons=(
                    HistoricalSuccessRandomBaselineNotReadyReason.SOURCE_TICKET_SEMANTICS_CONFLICT,
                ),
                probability=probability,
                eligible_observation_count=eligible_observation_count,
                excluded_observation_count=excluded_observation_count,
            )

        selected = observation.tickets[: cell.prefix_count]
        distinct = set[tuple[int, ...]]()
        ticket_successes: list[bool] = []
        for ticket in selected:
            if (
                type(ticket) is not HistoricalSuccessRandomBaselineTicketOperand
                or not _valid_six_numbers(ticket.main_numbers)
                or type(ticket.persisted_main_hit_count) is not int
                or not 0 <= ticket.persisted_main_hit_count <= 6
                or type(ticket.persisted_legacy_special_hit) is not bool
            ):
                return _not_ready(
                    cell=cell,
                    reasons=(
                        HistoricalSuccessRandomBaselineNotReadyReason.SOURCE_TICKET_SEMANTICS_CONFLICT,
                    ),
                    probability=probability,
                    eligible_observation_count=eligible_observation_count,
                    excluded_observation_count=excluded_observation_count,
                )
            recomputed_main_hits = len(
                set(ticket.main_numbers) & set(observation.target_main_numbers)
            )
            official_special_hit = observation.target_special_number in ticket.main_numbers
            if (
                recomputed_main_hits != ticket.persisted_main_hit_count
                or (recomputed_main_hits == 6 and official_special_hit)
            ):
                return _not_ready(
                    cell=cell,
                    reasons=(
                        HistoricalSuccessRandomBaselineNotReadyReason.SOURCE_TICKET_SEMANTICS_CONFLICT,
                    ),
                    probability=probability,
                    eligible_observation_count=eligible_observation_count,
                    excluded_observation_count=excluded_observation_count,
                )
            distinct.add(ticket.main_numbers)
            ticket_successes.append(
                _ticket_succeeds(
                    main_hit_count=recomputed_main_hits,
                    official_special_hit=official_special_hit,
                    criterion=cell.criterion,
                )
            )
        distinct_ticket_count += len(distinct)
        if len(distinct) != cell.prefix_count:
            duplicate_observation_count += 1
        observation_successes.append(any(ticket_successes))

    observed_success_count = sum(observation_successes)
    _, require_special_hit = _CRITERION_PARAMETERS[cell.criterion]
    if not require_special_hit and observed_success_count != legacy_window_success_count:
        return _not_ready(
            cell=cell,
            reasons=(
                HistoricalSuccessRandomBaselineNotReadyReason.SOURCE_TICKET_SEMANTICS_CONFLICT,
            ),
            probability=probability,
            eligible_observation_count=eligible_observation_count,
            excluded_observation_count=excluded_observation_count,
        )

    ticket_position_count = len(observations) * cell.prefix_count
    expected = HistoricalSuccessExactRational.from_fraction(
        eligible_observation_count * probability.as_fraction()
    )
    try:
        upper_tail = binomial_upper_tail(
            eligible_observation_count,
            observed_success_count,
            probability,
        )
    except ArithmeticError:
        return _not_ready(
            cell=cell,
            reasons=(HistoricalSuccessRandomBaselineNotReadyReason.EXACT_COMPUTATION_UNAVAILABLE,),
            probability=probability,
            eligible_observation_count=eligible_observation_count,
            excluded_observation_count=excluded_observation_count,
        )
    return HistoricalSuccessRandomBaselineResult(
        cell=cell,
        readiness=HistoricalSuccessRandomBaselineReadiness.READY,
        reason_codes=(),
        sampling_policy=(
            HistoricalSuccessRandomBaselineSamplingPolicy.UNIFORM_IID_LEGAL_TICKETS_WITH_REPLACEMENT
        ),
        ticket_count_interpretation=NOMINAL_TICKET_COUNT_EQUIVALENT,
        legal_ticket_count=LEGAL_TICKET_COUNT,
        success_ticket_count=criterion_success_ticket_count(cell.criterion),
        portfolio_success_probability=probability,
        eligible_observation_count=eligible_observation_count,
        excluded_observation_count=excluded_observation_count,
        observed_success_count=observed_success_count,
        expected_successes=expected,
        upper_tail_probability=upper_tail,
        observed_ticket_position_count=ticket_position_count,
        observed_distinct_ticket_count=distinct_ticket_count,
        observed_duplicate_ticket_count=ticket_position_count - distinct_ticket_count,
        observation_count_with_duplicates=duplicate_observation_count,
        interpretation_caveat=INTERPRETATION_CAVEAT,
    )


__all__ = [
    "INTERPRETATION_CAVEAT",
    "LEGAL_TICKET_COUNT",
    "NOMINAL_TICKET_COUNT_EQUIVALENT",
    "RANDOM_BASELINE_POLICY_VERSION",
    "HistoricalSuccessExactRational",
    "HistoricalSuccessRandomBaselineCellIdentity",
    "HistoricalSuccessRandomBaselineContractError",
    "HistoricalSuccessRandomBaselineNotReadyReason",
    "HistoricalSuccessRandomBaselineObservationOperand",
    "HistoricalSuccessRandomBaselineReadiness",
    "HistoricalSuccessRandomBaselineResult",
    "HistoricalSuccessRandomBaselineSamplingPolicy",
    "HistoricalSuccessRandomBaselineTicketOperand",
    "binomial_upper_tail",
    "criterion_success_ticket_count",
    "evaluate_historical_success_random_baseline",
    "portfolio_success_probability",
    "render_exact_decimal_18",
]
