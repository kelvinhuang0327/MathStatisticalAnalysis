"""Lottery-agnostic base-method universe evaluation contract.

Implements the METHOD_UNIVERSE_FIRST admission-recording contract: for one
prediction method, compute descriptive four-window (50 / 300 / 750 / full
history) hit-tier and average-match performance against an exact same-shape
random reference. This module only records; it never ranks, promotes,
rejects, or removes a method, and significance is never an admission gate.

The lottery match parameters (population size, winning-number count,
ticket-number count) are supplied by the caller through ``LotteryMatchContract``
so the same contract can later back DAILY_539 and POWER_LOTTO pilots without
any change to this module. Only ``BIG_LOTTO_MATCH_CONTRACT`` below is
B649-specific, and it is a plain data value, not a code path.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from math import comb

#: Semantic version of this module's *evaluator semantics* -- window selection,
#: hit-tier and average-match formulas, the exact random references, the
#: evaluable/insufficient thresholds, and the exact ``Fraction`` arithmetic that
#: produces every value below.
#:
#: This is deliberately not a strategy's ``METHOD_VERSION``: two records for the
#: same strategy and the same dataset are only meaningfully equal if the
#: evaluator that produced them meant the same thing by "M3_PLUS". Evidence
#: binds this identity so that a future change to any load-bearing semantic
#: above is distinguishable in the artifact rather than silently reinterpreted.
#: Bump it in the task that changes those semantics -- never for a refactor,
#: comment, or type-only edit that leaves every computed value identical.
BASE_METHOD_EVALUATOR_SEMANTIC_VERSION = "base_method_evaluation/1.0.0"

MINIMUM_SUPPORTED_DRAWS = 30
MINIMUM_EXPECTED_NULL_SUCCESSES = 5
HIT_TIER_IDS: tuple[str, ...] = ("M1_PLUS", "M2_PLUS", "M3_PLUS", "M4_PLUS")
AVG_MATCH_ID = "AVG_MATCH"


class BaseMethodEvaluationError(ValueError):
    """Base class for closed-contract validation failures in this module."""


class OutputShape(StrEnum):
    SINGLE_OUTPUT = "SINGLE_OUTPUT"
    PORTFOLIO = "PORTFOLIO"


class ExposureKind(StrEnum):
    FIXED = "FIXED"
    VARIABLE = "VARIABLE"


class WindowKind(StrEnum):
    WINDOW_50 = "WINDOW_50"
    WINDOW_300 = "WINDOW_300"
    WINDOW_750 = "WINDOW_750"
    FULL_HISTORY = "FULL_HISTORY"


class WindowRole(StrEnum):
    OPERATIONAL_WINDOW = "OPERATIONAL_WINDOW"
    DESCRIPTIVE_REFERENCE_ONLY = "DESCRIPTIVE_REFERENCE_ONLY"


class WindowStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INSUFFICIENT_WINDOW_HISTORY = "INSUFFICIENT_WINDOW_HISTORY"
    NO_ELIGIBLE_DRAWS = "NO_ELIGIBLE_DRAWS"


class EvaluableStatus(StrEnum):
    EVALUABLE = "EVALUABLE"
    INSUFFICIENT = "INSUFFICIENT"
    NO_ELIGIBLE_DRAWS = "NO_ELIGIBLE_DRAWS"


class RandomStatus(StrEnum):
    ABOVE_RANDOM = "ABOVE_RANDOM"
    AROUND_RANDOM = "AROUND_RANDOM"
    BELOW_RANDOM = "BELOW_RANDOM"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class BaselineMethod(StrEnum):
    BINOMIAL_EXACT = "BINOMIAL_EXACT"
    POISSON_BINOMIAL_EXACT = "POISSON_BINOMIAL_EXACT"
    HYPERGEOMETRIC_MEAN_EXACT = "HYPERGEOMETRIC_MEAN_EXACT"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class ReplayStatus(StrEnum):
    """Closed vocabulary owned by the METHOD_UNIVERSE_FIRST BASE_METHOD_INTAKE queue."""

    DISCOVERED = "DISCOVERED"
    ADAPTER_READY = "ADAPTER_READY"
    REPLAY_READY = "REPLAY_READY"
    BASELINE_RECORDED = "BASELINE_RECORDED"
    RESEARCH_AVAILABLE = "RESEARCH_AVAILABLE"
    REPLAY_ERROR = "REPLAY_ERROR"
    INSUFFICIENT_COVERAGE = "INSUFFICIENT_COVERAGE"


WINDOW_SIZES: tuple[tuple[WindowKind, int | None], ...] = (
    (WindowKind.WINDOW_50, 50),
    (WindowKind.WINDOW_300, 300),
    (WindowKind.WINDOW_750, 750),
    (WindowKind.FULL_HISTORY, None),
)
_WINDOW_ROLE: dict[WindowKind, WindowRole] = {
    WindowKind.WINDOW_50: WindowRole.OPERATIONAL_WINDOW,
    WindowKind.WINDOW_300: WindowRole.OPERATIONAL_WINDOW,
    WindowKind.WINDOW_750: WindowRole.OPERATIONAL_WINDOW,
    WindowKind.FULL_HISTORY: WindowRole.DESCRIPTIVE_REFERENCE_ONLY,
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BaseMethodEvaluationError(message)


def _classify_delta(delta: Fraction) -> RandomStatus:
    if delta > 0:
        return RandomStatus.ABOVE_RANDOM
    if delta < 0:
        return RandomStatus.BELOW_RANDOM
    return RandomStatus.AROUND_RANDOM


@dataclass(frozen=True, slots=True)
class HitTierDefinition:
    tier_id: str
    minimum_hits: int

    def __post_init__(self) -> None:
        _require(bool(self.tier_id), "tier_id must be non-empty")
        _require(self.minimum_hits >= 1, "minimum_hits must be >= 1")


@dataclass(frozen=True, slots=True)
class LotteryMatchContract:
    """Population parameters for one lottery's ticket-vs-draw matching rule.

    Deliberately generic: BIG_LOTTO, DAILY_539, and POWER_LOTTO's main-number
    matching all reduce to "pick ticket_number_count numbers, count overlap
    with winning_number_count drawn numbers out of population_size."
    """

    lottery_type: str
    population_size: int
    winning_number_count: int
    ticket_number_count: int
    hit_tiers: tuple[HitTierDefinition, ...]

    def __post_init__(self) -> None:
        _require(bool(self.lottery_type), "lottery_type must be non-empty")
        _require(self.population_size > 0, "population_size must be positive")
        _require(
            0 < self.winning_number_count <= self.population_size,
            "winning_number_count out of range",
        )
        _require(
            0 < self.ticket_number_count <= self.population_size,
            "ticket_number_count out of range",
        )
        _require(len(self.hit_tiers) > 0, "hit_tiers must be non-empty")
        tier_ids = [tier.tier_id for tier in self.hit_tiers]
        _require(len(tier_ids) == len(set(tier_ids)), "hit_tiers must have unique tier_id")
        for tier in self.hit_tiers:
            _require(
                tier.minimum_hits <= self.ticket_number_count,
                "minimum_hits exceeds ticket_number_count",
            )

    @property
    def legal_ticket_count(self) -> int:
        return comb(self.population_size, self.ticket_number_count)


BIG_LOTTO_MATCH_CONTRACT = LotteryMatchContract(
    lottery_type="BIG_LOTTO",
    population_size=49,
    winning_number_count=6,
    ticket_number_count=6,
    hit_tiers=tuple(
        HitTierDefinition(tier_id, index) for index, tier_id in enumerate(HIT_TIER_IDS, start=1)
    ),
)


def single_ticket_tier_probability(
    contract: LotteryMatchContract, tier: HitTierDefinition
) -> Fraction:
    """Exact P(a uniformly random legal ticket matches >= tier.minimum_hits numbers)."""

    _require(tier in contract.hit_tiers, "tier does not belong to this contract")
    other_pool = contract.population_size - contract.winning_number_count
    ticket_count = contract.ticket_number_count
    success_count = sum(
        comb(contract.winning_number_count, hits) * comb(other_pool, ticket_count - hits)
        for hits in range(tier.minimum_hits, ticket_count + 1)
        if 0 <= ticket_count - hits <= other_pool
    )
    return Fraction(success_count, contract.legal_ticket_count)


def average_match_reference(contract: LotteryMatchContract) -> Fraction:
    """Exact E[main hit count] for one uniformly random legal ticket (hypergeometric mean)."""

    return Fraction(
        contract.ticket_number_count * contract.winning_number_count, contract.population_size
    )


def portfolio_tier_probability(
    single_ticket_probability: Fraction, distinct_ticket_count: int
) -> Fraction:
    """Exact P(>=1 of distinct_ticket_count legal tickets meets the tier) for one draw.

    Distinct tickets within one draw are treated as independent single-ticket
    Bernoulli trials against that one random draw, matching the sealed
    B649_HIT_DEPTH_PROJECTION_R1 q_i = 1-(1-p)^D_i portfolio contract.
    """

    _require(distinct_ticket_count >= 0, "distinct_ticket_count must be non-negative")
    if distinct_ticket_count == 0:
        return Fraction(0)
    return 1 - (1 - single_ticket_probability) ** distinct_ticket_count


@dataclass(frozen=True, slots=True)
class MethodDrawObservation:
    """One eligible draw's outcome for one method. Callers supply ascending
    chronological order; this module never reorders observations."""

    draw_id: str
    draw_date: str
    native_ticket_count: int
    distinct_ticket_count: int
    main_hit_counts: tuple[int, ...]

    def __post_init__(self) -> None:
        _require(bool(self.draw_id), "draw_id must be non-empty")
        _require(bool(self.draw_date), "draw_date must be non-empty")
        _require(self.native_ticket_count >= 1, "native_ticket_count must be >= 1")
        _require(
            1 <= self.distinct_ticket_count <= self.native_ticket_count,
            "distinct_ticket_count must be between 1 and native_ticket_count",
        )
        _require(
            len(self.main_hit_counts) == self.native_ticket_count,
            "main_hit_counts length must equal native_ticket_count",
        )
        _require(
            all(hits >= 0 for hits in self.main_hit_counts),
            "main_hit_counts must be non-negative",
        )


@dataclass(frozen=True, slots=True)
class MethodExposure:
    kind: ExposureKind
    minimum_native_ticket_count: int
    maximum_native_ticket_count: int

    def __post_init__(self) -> None:
        _require(self.minimum_native_ticket_count >= 1, "minimum_native_ticket_count must be >= 1")
        _require(
            self.maximum_native_ticket_count >= self.minimum_native_ticket_count,
            "maximum_native_ticket_count must be >= minimum_native_ticket_count",
        )
        expected_kind = (
            ExposureKind.FIXED
            if self.minimum_native_ticket_count == self.maximum_native_ticket_count
            else ExposureKind.VARIABLE
        )
        _require(self.kind is expected_kind, "kind contradicts min/max native ticket counts")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "KIND": self.kind.value,
            "MIN_NATIVE_TICKET_COUNT": self.minimum_native_ticket_count,
            "MAX_NATIVE_TICKET_COUNT": self.maximum_native_ticket_count,
        }


@dataclass(frozen=True, slots=True)
class MethodTargetCoverage:
    eligible_draw_count: int
    first_draw_id: str | None
    last_draw_id: str | None

    def __post_init__(self) -> None:
        _require(self.eligible_draw_count >= 0, "eligible_draw_count must be non-negative")
        if self.eligible_draw_count == 0:
            _require(
                self.first_draw_id is None and self.last_draw_id is None,
                "empty coverage must have no draw ids",
            )
        else:
            _require(
                self.first_draw_id is not None and self.last_draw_id is not None,
                "non-empty coverage requires draw ids",
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "ELIGIBLE_DRAW_COUNT": self.eligible_draw_count,
            "FIRST_DRAW_ID": self.first_draw_id,
            "LAST_DRAW_ID": self.last_draw_id,
        }


@dataclass(frozen=True, slots=True)
class MethodIdentity:
    method_id: str
    method_version: str
    method_family: str
    output_shape: OutputShape
    exposure: MethodExposure
    target_coverage: MethodTargetCoverage
    replay_status: ReplayStatus

    def __post_init__(self) -> None:
        for name in ("method_id", "method_version", "method_family"):
            _require(bool(getattr(self, name)), f"{name} must be non-empty")
        expected_shape = (
            OutputShape.SINGLE_OUTPUT
            if self.exposure.maximum_native_ticket_count == 1
            else OutputShape.PORTFOLIO
        )
        _require(self.output_shape is expected_shape, "output_shape contradicts exposure")


@dataclass(frozen=True, slots=True)
class MetricCell:
    evaluable_status: EvaluableStatus
    eligible_draw_count: int
    success_draw_count: int | None
    observed_value: Fraction | None
    random_reference: Fraction | None
    delta_vs_random: Fraction | None
    random_status: RandomStatus
    baseline_method: BaselineMethod

    def __post_init__(self) -> None:
        _require(self.eligible_draw_count >= 0, "eligible_draw_count must be non-negative")
        if self.evaluable_status is EvaluableStatus.NO_ELIGIBLE_DRAWS:
            _require(
                self.observed_value is None
                and self.random_reference is None
                and self.delta_vs_random is None
                and self.success_draw_count is None,
                "NO_ELIGIBLE_DRAWS cell must not expose inferential values",
            )
            _require(
                self.random_status is RandomStatus.NOT_EVALUABLE,
                "NO_ELIGIBLE_DRAWS cell must have NOT_EVALUABLE random_status",
            )
            _require(
                self.baseline_method is BaselineMethod.NOT_EVALUABLE,
                "NO_ELIGIBLE_DRAWS cell must have NOT_EVALUABLE baseline_method",
            )
            return
        if (
            self.observed_value is None
            or self.random_reference is None
            or self.delta_vs_random is None
        ):
            raise BaseMethodEvaluationError(
                "a cell with eligible draws requires complete exact values"
            )
        _require(
            self.delta_vs_random == self.observed_value - self.random_reference,
            "delta_vs_random must equal observed_value - random_reference",
        )
        _require(
            self.random_status is _classify_delta(self.delta_vs_random),
            "random_status contradicts delta sign",
        )
        _require(
            self.baseline_method is not BaselineMethod.NOT_EVALUABLE,
            "a cell with eligible draws requires a real baseline_method",
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "EVALUABLE_STATUS": self.evaluable_status.value,
            "ELIGIBLE_DRAW_COUNT": self.eligible_draw_count,
            "SUCCESS_DRAW_COUNT": self.success_draw_count,
            "OBSERVED_VALUE": None if self.observed_value is None else float(self.observed_value),
            "RANDOM_REFERENCE": (
                None if self.random_reference is None else float(self.random_reference)
            ),
            "DELTA_VS_RANDOM": (
                None if self.delta_vs_random is None else float(self.delta_vs_random)
            ),
            "RANDOM_STATUS": self.random_status.value,
            "BASELINE_METHOD": self.baseline_method.value,
        }


@dataclass(frozen=True, slots=True)
class WindowBlock:
    window_kind: WindowKind
    window_role: WindowRole
    window_status: WindowStatus
    requested_size: int | None
    eligible_draw_count: int
    tier_ids: frozenset[str]
    metrics: dict[str, MetricCell]

    def __post_init__(self) -> None:
        _require(
            self.window_role is _WINDOW_ROLE[self.window_kind],
            "window_role contradicts window_kind",
        )
        _require(
            AVG_MATCH_ID not in self.tier_ids,
            "tier_ids must not include the reserved AVG_MATCH id",
        )
        expected_keys: set[str] = set(self.tier_ids) | {AVG_MATCH_ID}
        _require(
            set(self.metrics) == expected_keys,
            "metrics must cover exactly the caller's declared hit tiers plus AVG_MATCH",
        )

    def canonical_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "WINDOW_KIND": self.window_kind.value,
            "WINDOW_STATUS": self.window_status.value,
            "WINDOW_ROLE": self.window_role.value,
            "REQUESTED_SIZE": self.requested_size,
            "ELIGIBLE_DRAW_COUNT": self.eligible_draw_count,
        }
        for metric_id, cell in self.metrics.items():
            result[metric_id] = cell.canonical_dict()
        return result


@dataclass(frozen=True, slots=True)
class MethodEvaluationRecord:
    identity: MethodIdentity
    windows: dict[WindowKind, WindowBlock]

    def __post_init__(self) -> None:
        _require(
            set(self.windows) == {kind for kind, _ in WINDOW_SIZES},
            "windows must cover the full four-window set",
        )

    def canonical_dict(self) -> dict[str, object]:
        identity = self.identity
        return {
            "METHOD_ID": identity.method_id,
            "METHOD_VERSION": identity.method_version,
            "METHOD_FAMILY": identity.method_family,
            "OUTPUT_SHAPE": identity.output_shape.value,
            "EXPOSURE": identity.exposure.canonical_dict(),
            "TARGET_COVERAGE": identity.target_coverage.canonical_dict(),
            "REPLAY_STATUS": identity.replay_status.value,
            "WINDOW_50": self.windows[WindowKind.WINDOW_50].canonical_dict(),
            "WINDOW_300": self.windows[WindowKind.WINDOW_300].canonical_dict(),
            "WINDOW_750": self.windows[WindowKind.WINDOW_750].canonical_dict(),
            "FULL_HISTORY": self.windows[WindowKind.FULL_HISTORY].canonical_dict(),
        }


def _select_window(
    history: tuple[MethodDrawObservation, ...], requested_size: int | None
) -> tuple[MethodDrawObservation, ...]:
    return history if requested_size is None else history[-requested_size:]


def _window_status(
    selected: tuple[MethodDrawObservation, ...], requested_size: int | None
) -> WindowStatus:
    if not selected:
        return WindowStatus.NO_ELIGIBLE_DRAWS
    if requested_size is not None and len(selected) < requested_size:
        return WindowStatus.INSUFFICIENT_WINDOW_HISTORY
    return WindowStatus.COMPLETE


def _no_eligible_draws_cell(eligible_draw_count: int) -> MetricCell:
    return MetricCell(
        evaluable_status=EvaluableStatus.NO_ELIGIBLE_DRAWS,
        eligible_draw_count=eligible_draw_count,
        success_draw_count=None,
        observed_value=None,
        random_reference=None,
        delta_vs_random=None,
        random_status=RandomStatus.NOT_EVALUABLE,
        baseline_method=BaselineMethod.NOT_EVALUABLE,
    )


def _evaluate_tier_cell(
    contract: LotteryMatchContract,
    tier: HitTierDefinition,
    selected: tuple[MethodDrawObservation, ...],
    window_status: WindowStatus,
) -> MetricCell:
    eligible_draw_count = len(selected)
    if window_status is WindowStatus.NO_ELIGIBLE_DRAWS:
        return _no_eligible_draws_cell(eligible_draw_count)

    single_probability = single_ticket_tier_probability(contract, tier)
    distinct_counts = {draw.distinct_ticket_count for draw in selected}
    success_count = sum(
        1 for draw in selected if any(hits >= tier.minimum_hits for hits in draw.main_hit_counts)
    )
    per_draw_probabilities = (
        portfolio_tier_probability(single_probability, draw.distinct_ticket_count)
        for draw in selected
    )
    expected = sum(per_draw_probabilities, Fraction(0))
    observed_rate = Fraction(success_count, eligible_draw_count)
    baseline_rate = expected / eligible_draw_count
    delta = observed_rate - baseline_rate
    baseline_method = (
        BaselineMethod.BINOMIAL_EXACT
        if len(distinct_counts) == 1
        else BaselineMethod.POISSON_BINOMIAL_EXACT
    )
    is_insufficient = (
        window_status is WindowStatus.INSUFFICIENT_WINDOW_HISTORY
        or eligible_draw_count < MINIMUM_SUPPORTED_DRAWS
        or expected < MINIMUM_EXPECTED_NULL_SUCCESSES
    )
    evaluable_status = (
        EvaluableStatus.INSUFFICIENT if is_insufficient else EvaluableStatus.EVALUABLE
    )
    return MetricCell(
        evaluable_status=evaluable_status,
        eligible_draw_count=eligible_draw_count,
        success_draw_count=success_count,
        observed_value=observed_rate,
        random_reference=baseline_rate,
        delta_vs_random=delta,
        random_status=_classify_delta(delta),
        baseline_method=baseline_method,
    )


def _evaluate_avg_match_cell(
    contract: LotteryMatchContract,
    selected: tuple[MethodDrawObservation, ...],
    window_status: WindowStatus,
) -> MetricCell:
    eligible_draw_count = len(selected)
    if window_status is WindowStatus.NO_ELIGIBLE_DRAWS:
        return _no_eligible_draws_cell(eligible_draw_count)

    total_hits = sum(sum(draw.main_hit_counts) for draw in selected)
    total_tickets = sum(draw.native_ticket_count for draw in selected)
    observed_average = Fraction(total_hits, total_tickets)
    reference_average = average_match_reference(contract)
    delta = observed_average - reference_average
    is_insufficient = (
        window_status is WindowStatus.INSUFFICIENT_WINDOW_HISTORY
        or eligible_draw_count < MINIMUM_SUPPORTED_DRAWS
    )
    evaluable_status = (
        EvaluableStatus.INSUFFICIENT if is_insufficient else EvaluableStatus.EVALUABLE
    )
    return MetricCell(
        evaluable_status=evaluable_status,
        eligible_draw_count=eligible_draw_count,
        success_draw_count=None,
        observed_value=observed_average,
        random_reference=reference_average,
        delta_vs_random=delta,
        random_status=_classify_delta(delta),
        baseline_method=BaselineMethod.HYPERGEOMETRIC_MEAN_EXACT,
    )


def evaluate_method(
    contract: LotteryMatchContract,
    identity: MethodIdentity,
    history: tuple[MethodDrawObservation, ...],
) -> MethodEvaluationRecord:
    """Compute the full four-window evaluation record for one base method.

    ``history`` must already be in ascending chronological order; this
    function does not sort it, matching the append-only replay ordering the
    raw Foundation source guarantees.
    """

    _require(len(history) > 0, "history must be non-empty")
    tier_ids = frozenset(tier.tier_id for tier in contract.hit_tiers)
    windows: dict[WindowKind, WindowBlock] = {}
    for window_kind, requested_size in WINDOW_SIZES:
        selected = _select_window(history, requested_size)
        status = _window_status(selected, requested_size)
        metrics: dict[str, MetricCell] = {
            tier.tier_id: _evaluate_tier_cell(contract, tier, selected, status)
            for tier in contract.hit_tiers
        }
        metrics[AVG_MATCH_ID] = _evaluate_avg_match_cell(contract, selected, status)
        windows[window_kind] = WindowBlock(
            window_kind=window_kind,
            window_role=_WINDOW_ROLE[window_kind],
            window_status=status,
            requested_size=requested_size,
            eligible_draw_count=len(selected),
            tier_ids=tier_ids,
            metrics=metrics,
        )
    return MethodEvaluationRecord(identity=identity, windows=windows)


__all__ = [
    "AVG_MATCH_ID",
    "BASE_METHOD_EVALUATOR_SEMANTIC_VERSION",
    "BIG_LOTTO_MATCH_CONTRACT",
    "HIT_TIER_IDS",
    "MINIMUM_EXPECTED_NULL_SUCCESSES",
    "MINIMUM_SUPPORTED_DRAWS",
    "WINDOW_SIZES",
    "BaseMethodEvaluationError",
    "BaselineMethod",
    "EvaluableStatus",
    "ExposureKind",
    "HitTierDefinition",
    "LotteryMatchContract",
    "MethodDrawObservation",
    "MethodEvaluationRecord",
    "MethodExposure",
    "MethodIdentity",
    "MethodTargetCoverage",
    "MetricCell",
    "OutputShape",
    "RandomStatus",
    "ReplayStatus",
    "WindowBlock",
    "WindowKind",
    "WindowRole",
    "WindowStatus",
    "average_match_reference",
    "evaluate_method",
    "portfolio_tier_probability",
    "single_ticket_tier_probability",
]
