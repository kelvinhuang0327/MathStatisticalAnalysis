"""Bounded OOS feature/outcome validation for the B649 forecast lanes.

This module is a pure composition seam.  Callers supply already-parsed,
already-authoritative forecast artifacts and official outcomes; the module
does not read files, databases, clocks, networks, or schedulers.  It keeps
feature association separate from method lift and reuses the existing
``base_method_evaluation`` contract for the primary M2+ endpoint and its
same-shape random references.

The implementation is deliberately fail-closed around the replay boundary:
every forecast carries a strict prior cutoff, every target is paired by the
same draw number, and portfolio rows are evaluated at the exact published K.
Unavailable feature families remain unavailable rather than being recreated
from a differently named signal.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum
from fractions import Fraction
from math import sqrt

from lottolab.research.base_method_evaluation import (
    AVG_MATCH_ID,
    BIG_LOTTO_MATCH_CONTRACT,
    MINIMUM_EXPECTED_NULL_SUCCESSES,
    MINIMUM_SUPPORTED_DRAWS,
    ExposureKind,
    LotteryMatchContract,
    MethodDrawObservation,
    MethodEvaluationRecord,
    MethodExposure,
    MethodIdentity,
    MethodTargetCoverage,
    OutputShape,
    ReplayStatus,
    average_match_reference,
    evaluate_method,
)

STUDY_ID = "b649-cross-lane-oos-feature-outcome-validation-r1"
RESULT_SCHEMA_ID = "lottolab.research.b649_cross_lane_oos_feature_outcome_validation"
RESULT_SCHEMA_VERSION = "1.0.0"

CANONICAL_CONSENSUS_METHOD_ID = "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS"
OPERATIONAL_PORTFOLIO_METHOD_ID = "B649_OPERATIONAL_PORTFOLIO_SELECTOR"
CONSENSUS_METHOD_FAMILY = "B649_CROSS_LANE_CONSENSUS"
PORTFOLIO_METHOD_FAMILY = "B649_CROSS_LANE_PORTFOLIO"
PORTFOLIO_BUDGETS: tuple[int, ...] = (5, 10, 20)
RANK_MARGIN_PAIR: tuple[int, int] = (6, 7)
PRIMARY_METRIC_ID = "M2_PLUS"
AUXILIARY_METRIC_IDS: tuple[str, ...] = (
    "MAX_HIT_COUNT",
    "P_MAX_GE_3",
    "P_MAX_GE_4",
    "EXPECTED_MAX_MAIN_MATCHES",
)
WILSON_95_Z = 1.959963984540054

# The minimum is owned by base_method_evaluation. This alias makes the
# feature/lift gate visible in this module without introducing a second floor.
MINIMUM_ASSOCIATION_DRAW_COUNT = MINIMUM_SUPPORTED_DRAWS


class CrossLaneValidationError(ValueError):
    """A supplied artifact fails the closed pre-draw or pairing contract."""


class FeatureAvailability(str, Enum):  # noqa: UP042
    AVAILABLE = "AVAILABLE"
    AVAILABLE_PARTIAL = "AVAILABLE_PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class Classification(str, Enum):  # noqa: UP042
    SUPPORTED = "SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    REFUTED = "REFUTED"
    INSUFFICIENT_POWER = "INSUFFICIENT_POWER"
    UNAVAILABLE = "UNAVAILABLE"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CrossLaneValidationError(message)


def _iso_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CrossLaneValidationError(f"{label} must be an ISO date: {value!r}") from exc


def _validate_pre_draw_identity(
    *,
    draw_number: str,
    target_draw_date: str,
    scheduled_at_date: str,
    cutoff_draw_number: str,
    cutoff_draw_date: str,
) -> None:
    _require(draw_number.isdigit(), "draw_number must be numeric")
    _require(cutoff_draw_number.isdigit(), "cutoff_draw_number must be numeric")
    target_date = _iso_date(target_draw_date, "target_draw_date")
    scheduled_date = _iso_date(scheduled_at_date, "scheduled_at_date")
    cutoff_date = _iso_date(cutoff_draw_date, "cutoff_draw_date")
    _require(cutoff_date < target_date, "cutoff_draw_date must be before target_draw_date")
    _require(
        int(cutoff_draw_number) < int(draw_number),
        "cutoff_draw_number must be strictly before draw_number",
    )
    _require(
        scheduled_date <= target_date,
        "scheduled_at_date must not be after target_draw_date",
    )


@dataclass(frozen=True, slots=True)
class FeatureFamilyRecord:
    """One requested feature family's availability determination and evidence."""

    family_id: str
    requested_aliases: tuple[str, ...]
    availability: FeatureAvailability
    evidence: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "availability": self.availability.value,
            "evidence": self.evidence,
            "family_id": self.family_id,
            "requested_aliases": list(self.requested_aliases),
        }


FEATURE_FAMILY_REGISTRY: tuple[FeatureFamilyRecord, ...] = (
    FeatureFamilyRecord(
        "raw_vote_support",
        ("raw vote count / raw support",),
        FeatureAvailability.AVAILABLE,
        "Directly published per-number support_units in the canonical consensus "
        "ranking; no new producer.",
    ),
    FeatureFamilyRecord(
        "t1_t2_weighted_support",
        ("T1/T2 weighted support",),
        FeatureAvailability.UNAVAILABLE,
        "No T1/T2 weighting tier exists. The frozen canonical policy is "
        "EQUAL_STREAM_WEIGHT with FULL_VOTE_PER_FROZEN_STREAM_NO_FAMILY_NORMALIZATION; "
        "no producer is synthesized.",
    ),
    FeatureFamilyRecord(
        "cross_budget_persistence",
        ("cross-budget stability / K-budget persistence",),
        FeatureAvailability.AVAILABLE,
        "Published K=1 consensus and K=5/10/20 portfolio ticket lists permit an "
        "exact first-ticket equality check; no new producer.",
    ),
    FeatureFamilyRecord(
        "loo_robustness",
        ("LOO robustness", "leave-one-out robustness"),
        FeatureAvailability.UNAVAILABLE,
        "No leave-one-stream-out consensus ranking is published; synthesizing one "
        "would create a new producer.",
    ),
    FeatureFamilyRecord(
        "rank_entropy_cross_stream_disagreement",
        ("rank entropy / cross-stream disagreement",),
        FeatureAvailability.UNAVAILABLE,
        "The canonical artifact publishes number-level support only; no frozen "
        "stream-rank entropy or disagreement producer exists.",
    ),
    FeatureFamilyRecord(
        "pair_consensus",
        ("pair consensus",),
        FeatureAvailability.UNAVAILABLE,
        "The canonical aggregation unit is NUMBER_LEVEL. Existing pair-frequency "
        "signals are a different quantity and are not aliased to pair consensus.",
    ),
    FeatureFamilyRecord(
        "portfolio_diversity",
        ("portfolio diversity",),
        FeatureAvailability.AVAILABLE,
        "The existing portfolio_internal_jaccard_mean definition is applied to "
        "the already-published K-ticket sets.",
    ),
    FeatureFamilyRecord(
        "rank6_rank7_margin",
        ("rank6/rank7 margin",),
        FeatureAvailability.AVAILABLE,
        "Published support_units at deterministic ranking positions 6 and 7 permit "
        "a direct margin calculation.",
    ),
    FeatureFamilyRecord(
        "recent_window_vs_full_history_stability",
        ("recent-window vs full-history stability",),
        FeatureAvailability.AVAILABLE,
        "The existing WINDOW_50/WINDOW_300/WINDOW_750/FULL_HISTORY evaluator output "
        "is reused without reselecting a winner.",
    ),
    FeatureFamilyRecord(
        "forecast_freshness_time_to_draw",
        ("forecast freshness / time-to-draw",),
        FeatureAvailability.AVAILABLE,
        "Whole-day target-date minus scheduled-date lead time is published in each "
        "forecast. It is not conflated with history-input freshness.",
    ),
    FeatureFamilyRecord(
        "method_family_diversity",
        ("method-family diversity",),
        FeatureAvailability.AVAILABLE_PARTIAL,
        "method_family exists in the research FullStrategyCatalog for a subset of "
        "the canonical streams; unresolved streams remain missing and coverage is "
        "reported rather than imputed.",
    ),
)

_FAMILY_BY_ID = {record.family_id: record for record in FEATURE_FAMILY_REGISTRY}
_require(
    len(_FAMILY_BY_ID) == len(FEATURE_FAMILY_REGISTRY),
    "duplicate feature family id in the registry",
)


def feature_family(family_id: str) -> FeatureFamilyRecord:
    try:
        return _FAMILY_BY_ID[family_id]
    except KeyError as exc:
        raise CrossLaneValidationError(f"unknown feature family: {family_id}") from exc


@dataclass(frozen=True, slots=True)
class RankedNumber:
    number: int
    rank: int
    support_units: int

    def __post_init__(self) -> None:
        _require(1 <= self.number <= 49, "number out of range")
        _require(self.rank >= 1, "rank must be positive")
        _require(self.support_units >= 0, "support_units must be non-negative")


@dataclass(frozen=True, slots=True)
class ConsensusForecastRecord:
    """The load-bearing fields published for one canonical consensus forecast."""

    draw_number: str
    target_draw_date: str
    scheduled_at_date: str
    cutoff_draw_number: str
    cutoff_draw_date: str
    exact_stream_ids: tuple[str, ...]
    final_decision_ranking: tuple[RankedNumber, ...]
    final_ticket: tuple[int, ...]
    pre_outcome_temporal_integrity: str
    target_result_used: bool

    def __post_init__(self) -> None:
        _require(bool(self.draw_number), "draw_number must be non-empty")
        _validate_pre_draw_identity(
            draw_number=self.draw_number,
            target_draw_date=self.target_draw_date,
            scheduled_at_date=self.scheduled_at_date,
            cutoff_draw_number=self.cutoff_draw_number,
            cutoff_draw_date=self.cutoff_draw_date,
        )
        _require(len(self.exact_stream_ids) == 11, "exact_stream_ids must have 11 entries")
        _require(
            len(set(self.exact_stream_ids)) == len(self.exact_stream_ids),
            "exact_stream_ids must be unique",
        )
        _require(len(self.final_decision_ranking) == 49, "ranking must cover all 49 numbers")
        _require(
            tuple(item.rank for item in self.final_decision_ranking) == tuple(range(1, 50)),
            "ranking must be in contiguous rank order 1..49",
        )
        _require(
            {item.number for item in self.final_decision_ranking} == set(range(1, 50)),
            "ranking must contain every legal number exactly once",
        )
        _require(len(self.final_ticket) == 6, "final_ticket must have six numbers")
        _require(
            len(set(self.final_ticket)) == 6
            and all(1 <= number <= 49 for number in self.final_ticket),
            "final_ticket must contain six unique legal numbers",
        )
        _require(
            set(self.final_ticket)
            == {item.number for item in self.final_decision_ranking[:6]},
            "final_ticket must equal the published top-six ranking numbers",
        )
        _require(
            self.pre_outcome_temporal_integrity == "PASS",
            "consensus record must self-attest pre_outcome_temporal_integrity=PASS",
        )
        _require(
            self.target_result_used is False,
            "consensus record must self-attest target_result_used=False",
        )

    def support_units(self, number: int) -> int:
        for item in self.final_decision_ranking:
            if item.number == number:
                return item.support_units
        raise CrossLaneValidationError(f"number {number} missing from ranking")

    def at_rank(self, rank: int) -> RankedNumber:
        if not 1 <= rank <= 49:
            raise CrossLaneValidationError(f"rank out of range: {rank}")
        return self.final_decision_ranking[rank - 1]


@dataclass(frozen=True, slots=True)
class PortfolioForecastRecord:
    """The load-bearing fields published for one K-ticket portfolio run."""

    draw_number: str
    target_draw_date: str
    scheduled_at_date: str
    cutoff_draw_number: str
    cutoff_draw_date: str
    tickets_by_budget: Mapping[int, tuple[tuple[int, ...], ...]]
    target_result_used: bool
    outcome_used: str | None = None
    pre_outcome_temporal_integrity: str | None = None

    def __post_init__(self) -> None:
        _require(bool(self.draw_number), "draw_number must be non-empty")
        _validate_pre_draw_identity(
            draw_number=self.draw_number,
            target_draw_date=self.target_draw_date,
            scheduled_at_date=self.scheduled_at_date,
            cutoff_draw_number=self.cutoff_draw_number,
            cutoff_draw_date=self.cutoff_draw_date,
        )
        _require(
            set(self.tickets_by_budget) == set(PORTFOLIO_BUDGETS),
            f"portfolio must publish exactly K={PORTFOLIO_BUDGETS}",
        )
        _require(
            self.target_result_used is False,
            "portfolio record must self-attest target_result_used=False",
        )
        _require(
            self.outcome_used in (None, "NO"),
            "portfolio record must self-attest outcome_used=NO when present",
        )
        _require(
            self.pre_outcome_temporal_integrity in (None, "PASS"),
            "portfolio pre_outcome_temporal_integrity must be PASS when present",
        )
        for budget, tickets in self.tickets_by_budget.items():
            _require(budget in PORTFOLIO_BUDGETS, f"unsupported portfolio budget: {budget}")
            _require(len(tickets) == budget, f"K={budget} must publish exactly {budget} tickets")
            for ticket in tickets:
                _require(
                    len(ticket) == 6
                    and len(set(ticket)) == 6
                    and all(1 <= number <= 49 for number in ticket),
                    "every ticket must contain six unique legal numbers",
                )

    def first_ticket(self, budget: int) -> tuple[int, ...]:
        try:
            return self.tickets_by_budget[budget][0]
        except KeyError as exc:
            raise CrossLaneValidationError(f"budget K={budget} not published") from exc


@dataclass(frozen=True, slots=True)
class DrawOutcome:
    draw_number: str
    main_numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        _require(bool(self.draw_number), "draw_number must be non-empty")
        _require(
            len(self.main_numbers) == 6
            and len(set(self.main_numbers)) == 6
            and all(1 <= number <= 49 for number in self.main_numbers),
            "main_numbers must be six unique legal numbers",
        )

    def hit_count(self, ticket: tuple[int, ...]) -> int:
        return len(set(ticket) & set(self.main_numbers))


def _validate_outcome_map(outcomes: Mapping[str, DrawOutcome]) -> None:
    for key, outcome in outcomes.items():
        _require(key == outcome.draw_number, "outcome map key must equal outcome.draw_number")


def _paired_consensus(
    records: Sequence[ConsensusForecastRecord], outcomes: Mapping[str, DrawOutcome]
) -> tuple[tuple[ConsensusForecastRecord, DrawOutcome], ...]:
    _validate_outcome_map(outcomes)
    seen: set[str] = set()
    paired: list[tuple[ConsensusForecastRecord, DrawOutcome]] = []
    for record in records:
        _require(record.draw_number not in seen, "duplicate consensus forecast draw")
        seen.add(record.draw_number)
        outcome = outcomes.get(record.draw_number)
        if outcome is not None:
            _require(
                outcome.draw_number == record.draw_number,
                "outcome draw_number must equal forecast draw_number",
            )
            paired.append((record, outcome))
    _require_chronological_pairs(paired, "consensus")
    return tuple(paired)


def _paired_portfolio(
    records: Sequence[PortfolioForecastRecord], outcomes: Mapping[str, DrawOutcome]
) -> tuple[tuple[PortfolioForecastRecord, DrawOutcome], ...]:
    _validate_outcome_map(outcomes)
    seen: set[str] = set()
    paired: list[tuple[PortfolioForecastRecord, DrawOutcome]] = []
    for record in records:
        _require(record.draw_number not in seen, "duplicate portfolio forecast draw")
        seen.add(record.draw_number)
        outcome = outcomes.get(record.draw_number)
        if outcome is not None:
            _require(
                outcome.draw_number == record.draw_number,
                "outcome draw_number must equal forecast draw_number",
            )
            paired.append((record, outcome))
    _require_chronological_pairs(paired, "portfolio")
    return tuple(paired)


def _require_chronological_pairs(
    pairs: Sequence[tuple[ConsensusForecastRecord | PortfolioForecastRecord, DrawOutcome]],
    label: str,
) -> None:
    previous: tuple[date, int] | None = None
    for record, _outcome in pairs:
        current = (_iso_date(record.target_draw_date, "target_draw_date"), int(record.draw_number))
        _require(
            previous is None or current > previous,
            f"{label} paired forecasts must be in strict chronological order",
        )
        previous = current


def wilson_score_interval(
    successes: int,
    trials: int,
    *,
    z: float = WILSON_95_Z,
) -> tuple[float, float]:
    """Return a bounded Wilson score interval for one observed event rate.

    The baseline in this study is an exact contract value, so method-lift rows
    shift this observed-rate interval by the fixed baseline. The interval is
    descriptive; the existing minimum-draw and expected-null-success gates
    still control classification.
    """

    _require(trials > 0, "trials must be positive")
    _require(0 <= successes <= trials, "successes must lie in [0, trials]")
    _require(z > 0, "z must be positive")
    observed = successes / trials
    z_squared = z * z
    denominator = 1.0 + z_squared / trials
    center = (observed + z_squared / (2.0 * trials)) / denominator
    radius = (
        z
        * sqrt(
            observed * (1.0 - observed) / trials
            + z_squared / (4.0 * trials * trials)
        )
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def _not_estimable_interval(reason: str) -> dict[str, object]:
    return {"status": "NOT_ESTIMABLE", "reason": reason}


@dataclass(frozen=True, slots=True)
class DecisionRow:
    """One row of the reproducible decision table."""

    row_id: str
    row_kind: str
    feature_family_id: str | None
    classification: Classification
    sample_count: int
    baseline_definition: str
    candidate_result: dict[str, object]
    absolute_delta: float | None
    relative_lift: float | None
    uncertainty_interval: dict[str, object] | None
    auxiliary_outcomes: dict[str, object] | None
    stability_note: str
    notes: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "absolute_delta": self.absolute_delta,
            "auxiliary_outcomes": self.auxiliary_outcomes,
            "baseline_definition": self.baseline_definition,
            "candidate_result": self.candidate_result,
            "classification": self.classification.value,
            "feature_family_id": self.feature_family_id,
            "notes": self.notes,
            "relative_lift": self.relative_lift,
            "row_id": self.row_id,
            "row_kind": self.row_kind,
            "sample_count": self.sample_count,
            "stability_note": self.stability_note,
            "uncertainty_interval": self.uncertainty_interval,
        }


def _classification_for_sample(sample_count: int) -> Classification:
    if sample_count < MINIMUM_ASSOCIATION_DRAW_COUNT:
        return Classification.INSUFFICIENT_POWER
    return Classification.INCONCLUSIVE


def _below_minimum_note(sample_count: int) -> str:
    return f"n={sample_count} < MINIMUM_ASSOCIATION_DRAW_COUNT={MINIMUM_ASSOCIATION_DRAW_COUNT}"


def _unavailable_row(record: FeatureFamilyRecord) -> DecisionRow:
    return DecisionRow(
        row_id=record.family_id,
        row_kind="FEATURE_ASSOCIATION",
        feature_family_id=record.family_id,
        classification=Classification.UNAVAILABLE,
        sample_count=0,
        baseline_definition="NOT_APPLICABLE",
        candidate_result={"status": "NOT_APPLICABLE"},
        absolute_delta=None,
        relative_lift=None,
        uncertainty_interval=None,
        auxiliary_outcomes=None,
        stability_note="NOT_APPLICABLE",
        notes=record.evidence,
    )


def _no_data_row(record: FeatureFamilyRecord) -> DecisionRow:
    return DecisionRow(
        row_id=record.family_id,
        row_kind="FEATURE_ASSOCIATION",
        feature_family_id=record.family_id,
        classification=Classification.INSUFFICIENT_POWER,
        sample_count=0,
        baseline_definition=record.evidence,
        candidate_result={"status": "NO_PAIRED_FORECAST_OUTCOME"},
        absolute_delta=None,
        relative_lift=None,
        uncertainty_interval=_not_estimable_interval("zero paired observations"),
        auxiliary_outcomes=None,
        stability_note=(
            f"n=0 < MINIMUM_ASSOCIATION_DRAW_COUNT={MINIMUM_ASSOCIATION_DRAW_COUNT}"
        ),
        notes="The producer exists, but this run has no usable same-draw forecast/outcome pair.",
    )


def raw_vote_support_row(
    consensus_pairs: Sequence[tuple[ConsensusForecastRecord, DrawOutcome]],
) -> DecisionRow:
    """Compare drawn-number support with the same forecast's field mean."""

    if not consensus_pairs:
        return _no_data_row(feature_family("raw_vote_support"))
    per_draw: dict[str, dict[str, float]] = {}
    drawn_means: list[Fraction] = []
    field_means: list[Fraction] = []
    for record, outcome in consensus_pairs:
        drawn_mean = Fraction(
            sum(record.support_units(number) for number in outcome.main_numbers), 6
        )
        field_mean = Fraction(
            sum(item.support_units for item in record.final_decision_ranking), 49
        )
        drawn_means.append(drawn_mean)
        field_means.append(field_mean)
        per_draw[record.draw_number] = {
            "drawn_mean_support_units": float(drawn_mean),
            "field_mean_support_units": float(field_mean),
        }
    sample_count = len(per_draw)
    mean_drawn = sum(drawn_means, Fraction()) / sample_count
    mean_field = sum(field_means, Fraction()) / sample_count
    delta = mean_drawn - mean_field
    return DecisionRow(
        row_id="raw_vote_support__drawn_vs_field_mean",
        row_kind="FEATURE_ASSOCIATION",
        feature_family_id="raw_vote_support",
        classification=_classification_for_sample(sample_count),
        sample_count=sample_count,
        baseline_definition="mean support_units across all 49 numbers in the same forecast",
        candidate_result={
            "mean_drawn_support_units": float(mean_drawn),
            "mean_field_support_units": float(mean_field),
            "per_draw": per_draw,
        },
        absolute_delta=float(delta),
        relative_lift=float(delta / mean_field) if mean_field else None,
        uncertainty_interval=_not_estimable_interval(
            "continuous feature association is not interval-estimated at this sample size"
        ),
        auxiliary_outcomes=None,
        stability_note=_below_minimum_note(sample_count),
        notes=(
            "Exploratory association only; no outcome-conditioned support "
            "reweighting is performed."
        ),
    )


def rank_margin_row(
    consensus_pairs: Sequence[tuple[ConsensusForecastRecord, DrawOutcome]],
) -> DecisionRow:
    rank_a, rank_b = RANK_MARGIN_PAIR
    if not consensus_pairs:
        return _no_data_row(feature_family("rank6_rank7_margin"))
    margins: dict[str, int] = {}
    rank_a_hit: dict[str, bool] = {}
    for record, outcome in consensus_pairs:
        margins[record.draw_number] = (
            record.at_rank(rank_a).support_units - record.at_rank(rank_b).support_units
        )
        rank_a_hit[record.draw_number] = record.at_rank(rank_a).number in outcome.main_numbers
    sample_count = len(margins)
    hit_count = sum(rank_a_hit.values())
    return DecisionRow(
        row_id="rank6_rank7_margin__vs_rank6_hit",
        row_kind="FEATURE_ASSOCIATION",
        feature_family_id="rank6_rank7_margin",
        classification=_classification_for_sample(sample_count),
        sample_count=sample_count,
        baseline_definition=(
            "descriptive rank-6/rank-7 support margin; no margin-conditioned baseline"
        ),
        candidate_result={
            "margin_by_draw": margins,
            "rank6_hit_by_draw": rank_a_hit,
            "rank6_hit_count": hit_count,
            "rank6_hit_rate": hit_count / sample_count,
        },
        absolute_delta=None,
        relative_lift=None,
        uncertainty_interval=_not_estimable_interval(
            "no predeclared margin-conditioned inferential test is run"
        ),
        auxiliary_outcomes=None,
        stability_note=_below_minimum_note(sample_count),
        notes=(
            "Exploratory descriptive pairing only; no boundary-number winner "
            "search is performed."
        ),
    )


def cross_budget_persistence_row(
    consensus_by_draw: Mapping[str, ConsensusForecastRecord],
    portfolio_by_draw: Mapping[str, PortfolioForecastRecord],
) -> DecisionRow:
    shared_draws = sorted(set(consensus_by_draw) & set(portfolio_by_draw))
    if not shared_draws:
        return _no_data_row(feature_family("cross_budget_persistence"))
    persistence: dict[str, dict[str, bool]] = {}
    for draw_number in shared_draws:
        consensus = consensus_by_draw[draw_number]
        portfolio = portfolio_by_draw[draw_number]
        _require(
            (
                consensus.target_draw_date,
                consensus.cutoff_draw_number,
                consensus.cutoff_draw_date,
            )
            == (
                portfolio.target_draw_date,
                portfolio.cutoff_draw_number,
                portfolio.cutoff_draw_date,
            ),
            "cross-budget comparison requires identical target draw and cutoff",
        )
        consensus_ticket = frozenset(consensus.final_ticket)
        persistence[draw_number] = {
            str(budget): frozenset(portfolio.first_ticket(budget)) == consensus_ticket
            for budget in PORTFOLIO_BUDGETS
        }
    return DecisionRow(
        row_id="cross_budget_persistence__k1_vs_k5_k10_k20_first_ticket",
        row_kind="FEATURE_ASSOCIATION",
        feature_family_id="cross_budget_persistence",
        classification=Classification.INCONCLUSIVE,
        sample_count=len(shared_draws),
        baseline_definition=(
            "structural equality: canonical K=1 final_ticket versus published "
            "ticket_position=1 at K=5/10/20 on the same draw and cutoff"
        ),
        candidate_result={
            "persistence_by_draw": persistence,
            "all_budgets_persist": all(all(values.values()) for values in persistence.values()),
        },
        absolute_delta=None,
        relative_lift=None,
        uncertainty_interval=None,
        auxiliary_outcomes=None,
        stability_note=(
            f"structural_n={len(shared_draws)}; not an inferential outcome association"
        ),
        notes="Descriptive cross-lane consistency check over outcome-matched artifacts only.",
    )


def _mean_pairwise_jaccard(tickets: tuple[tuple[int, ...], ...]) -> Fraction:
    sets = tuple(frozenset(ticket) for ticket in tickets)
    pair_count = len(sets) * (len(sets) - 1) // 2
    if pair_count == 0:
        return Fraction(0)
    total = Fraction(0)
    for index, left in enumerate(sets):
        for right in sets[index + 1 :]:
            union = left | right
            total += Fraction(len(left & right), len(union))
    return total / pair_count


def portfolio_diversity_row(
    portfolio_pairs: Sequence[tuple[PortfolioForecastRecord, DrawOutcome]],
) -> DecisionRow:
    if not portfolio_pairs:
        return _no_data_row(feature_family("portfolio_diversity"))
    per_draw: dict[str, dict[str, float]] = {}
    for record, _outcome in portfolio_pairs:
        per_draw[record.draw_number] = {
            str(budget): float(_mean_pairwise_jaccard(record.tickets_by_budget[budget]))
            for budget in PORTFOLIO_BUDGETS
        }
    sample_count = len(per_draw)
    return DecisionRow(
        row_id="portfolio_diversity__mean_pairwise_jaccard_by_budget",
        row_kind="FEATURE_ASSOCIATION",
        feature_family_id="portfolio_diversity",
        classification=_classification_for_sample(sample_count),
        sample_count=sample_count,
        baseline_definition=(
            "portfolio_internal_jaccard_mean; 0 = no pairwise overlap, computed "
            "within each already-published K portfolio"
        ),
        candidate_result={"mean_pairwise_jaccard_by_draw_and_budget": per_draw},
        absolute_delta=None,
        relative_lift=None,
        uncertainty_interval=_not_estimable_interval(
            "continuous diversity/outcome association is not interval-estimated at this sample size"
        ),
        auxiliary_outcomes=None,
        stability_note=_below_minimum_note(sample_count),
        notes=(
            "No portfolio geometry is reoptimized and no diversity-conditioned "
            "selection is performed."
        ),
    )


def forecast_freshness_row(
    consensus_pairs: Sequence[tuple[ConsensusForecastRecord, DrawOutcome]],
) -> DecisionRow:
    if not consensus_pairs:
        return _no_data_row(feature_family("forecast_freshness_time_to_draw"))
    lead_days: dict[str, int] = {}
    for record, _outcome in consensus_pairs:
        lead_days[record.draw_number] = (
            _iso_date(record.target_draw_date, "target_draw_date")
            - _iso_date(record.scheduled_at_date, "scheduled_at_date")
        ).days
    sample_count = len(lead_days)
    return DecisionRow(
        row_id="forecast_freshness__lead_days_vs_outcome",
        row_kind="FEATURE_ASSOCIATION",
        feature_family_id="forecast_freshness_time_to_draw",
        classification=_classification_for_sample(sample_count),
        sample_count=sample_count,
        baseline_definition="whole-day target_draw_date minus scheduled_at_date",
        candidate_result={"lead_days_by_draw": lead_days},
        absolute_delta=None,
        relative_lift=None,
        uncertainty_interval=_not_estimable_interval(
            "continuous freshness/outcome association is not interval-estimated at this sample size"
        ),
        auxiliary_outcomes=None,
        stability_note=_below_minimum_note(sample_count),
        notes=(
            "Measured at day granularity; no authoritative intraday draw-closing time "
            "is introduced."
        ),
    )


def method_family_diversity_row(
    consensus_pairs: Sequence[tuple[ConsensusForecastRecord, DrawOutcome]],
    method_family_lookup: Mapping[str, str | None],
) -> DecisionRow:
    if not consensus_pairs:
        return _no_data_row(feature_family("method_family_diversity"))
    per_draw: dict[str, dict[str, object]] = {}
    for record, _outcome in consensus_pairs:
        resolved = [
            family
            for stream_id in record.exact_stream_ids
            if (family := method_family_lookup.get(stream_id)) is not None
        ]
        per_draw[record.draw_number] = {
            "distinct_family_count": len(set(resolved)),
            "resolved_stream_count": len(resolved),
            "total_stream_count": len(record.exact_stream_ids),
            "resolved_families": sorted(set(resolved)),
        }
    sample_count = len(per_draw)
    return DecisionRow(
        row_id="method_family_diversity__distinct_families_among_11_streams",
        row_kind="FEATURE_ASSOCIATION",
        feature_family_id="method_family_diversity",
        classification=_classification_for_sample(sample_count),
        sample_count=sample_count,
        baseline_definition=(
            "distinct method_family count among stream_ids resolved in the frozen "
            "FullStrategyCatalog; unresolved streams are not imputed"
        ),
        candidate_result={"coverage_by_draw": per_draw},
        absolute_delta=None,
        relative_lift=None,
        uncertainty_interval=_not_estimable_interval(
            "partial categorical feature/outcome association is not "
            "interval-estimated at this sample size"
        ),
        auxiliary_outcomes=None,
        stability_note=_below_minimum_note(sample_count),
        notes=(
            "AVAILABLE_PARTIAL: coverage is explicit and unresolved stream "
            "families remain missing."
        ),
    )


def _window_metric_summary(record: MethodEvaluationRecord) -> dict[str, object]:
    result: dict[str, object] = {}
    for window_name in ("WINDOW_50", "WINDOW_300", "WINDOW_750", "FULL_HISTORY"):
        window = _window_by_name(record, window_name)
        window_dict = window.canonical_dict()
        m2 = window.metrics[PRIMARY_METRIC_ID]
        avg = window.metrics[AVG_MATCH_ID]
        result[window_name] = {
            "window_status": window_dict["WINDOW_STATUS"],
            "window_role": window_dict["WINDOW_ROLE"],
            "eligible_draw_count": window.eligible_draw_count,
            "m2_plus_observed_rate": (
                None if m2.observed_value is None else float(m2.observed_value)
            ),
            "m2_plus_random_reference": (
                None if m2.random_reference is None else float(m2.random_reference)
            ),
            "avg_match_observed": (
                None if avg.observed_value is None else float(avg.observed_value)
            ),
        }
    return result


def _window_by_name(record: MethodEvaluationRecord, window_name: str):
    for key, window in record.windows.items():
        if str(key) == window_name:
            return window
    raise CrossLaneValidationError(f"missing evaluator window: {window_name}")


def recent_window_vs_full_history_row(
    consensus_evaluation: MethodEvaluationRecord | None,
    portfolio_evaluations: Mapping[int, MethodEvaluationRecord],
    sample_count: int,
) -> DecisionRow:
    methods: dict[str, object] = {}
    if consensus_evaluation is not None:
        methods["consensus_k1"] = _window_metric_summary(consensus_evaluation)
    methods["portfolio_by_budget"] = {
        str(budget): _window_metric_summary(record)
        for budget, record in sorted(portfolio_evaluations.items())
    }
    return DecisionRow(
        row_id="recent_window_vs_full_history__m2_plus_and_avg_match",
        row_kind="FEATURE_ASSOCIATION",
        feature_family_id="recent_window_vs_full_history_stability",
        classification=_classification_for_sample(sample_count),
        sample_count=sample_count,
        baseline_definition=(
            "the existing evaluator's WINDOW_50/WINDOW_300/WINDOW_750 versus "
            "FULL_HISTORY outputs; FULL_HISTORY remains descriptive"
        ),
        candidate_result={"method_windows": methods},
        absolute_delta=None,
        relative_lift=None,
        uncertainty_interval=_not_estimable_interval(
            "window stability is descriptive at the available paired sample count"
        ),
        auxiliary_outcomes=None,
        stability_note=_below_minimum_note(sample_count),
        notes="No window winner is selected and no post-outcome window is constructed.",
    )


def consensus_draw_observation(
    record: ConsensusForecastRecord, outcome: DrawOutcome
) -> MethodDrawObservation:
    _require(record.draw_number == outcome.draw_number, "consensus/outcome draw mismatch")
    return MethodDrawObservation(
        draw_id=record.draw_number,
        draw_date=record.target_draw_date,
        native_ticket_count=1,
        distinct_ticket_count=1,
        main_hit_counts=(outcome.hit_count(record.final_ticket),),
    )


def portfolio_draw_observation(
    record: PortfolioForecastRecord, outcome: DrawOutcome, budget: int
) -> MethodDrawObservation:
    _require(record.draw_number == outcome.draw_number, "portfolio/outcome draw mismatch")
    try:
        tickets = record.tickets_by_budget[budget]
    except KeyError as exc:
        raise CrossLaneValidationError(f"budget K={budget} not published") from exc
    return MethodDrawObservation(
        draw_id=record.draw_number,
        draw_date=record.target_draw_date,
        native_ticket_count=len(tickets),
        distinct_ticket_count=len(set(tickets)),
        main_hit_counts=tuple(outcome.hit_count(ticket) for ticket in tickets),
    )


def _method_identity(
    *,
    method_id: str,
    method_family: str,
    native_ticket_count: int,
    observations: tuple[MethodDrawObservation, ...],
) -> MethodIdentity:
    _require(bool(observations), "observations must not be empty")
    return MethodIdentity(
        method_id=method_id,
        method_version=RESULT_SCHEMA_VERSION,
        method_family=method_family,
        output_shape=(
            OutputShape.SINGLE_OUTPUT if native_ticket_count == 1 else OutputShape.PORTFOLIO
        ),
        exposure=MethodExposure(
            kind=ExposureKind.FIXED,
            minimum_native_ticket_count=native_ticket_count,
            maximum_native_ticket_count=native_ticket_count,
        ),
        target_coverage=MethodTargetCoverage(
            eligible_draw_count=len(observations),
            first_draw_id=observations[0].draw_id,
            last_draw_id=observations[-1].draw_id,
        ),
        replay_status=ReplayStatus.RESEARCH_AVAILABLE,
    )


def evaluate_consensus_method(
    observations: tuple[MethodDrawObservation, ...],
    *,
    contract: LotteryMatchContract = BIG_LOTTO_MATCH_CONTRACT,
) -> MethodEvaluationRecord:
    return evaluate_method(
        contract,
        _method_identity(
            method_id=CANONICAL_CONSENSUS_METHOD_ID,
            method_family=CONSENSUS_METHOD_FAMILY,
            native_ticket_count=1,
            observations=observations,
        ),
        observations,
    )


def evaluate_portfolio_method(
    observations: tuple[MethodDrawObservation, ...],
    budget: int,
    *,
    contract: LotteryMatchContract = BIG_LOTTO_MATCH_CONTRACT,
) -> MethodEvaluationRecord:
    _require(budget in PORTFOLIO_BUDGETS, f"unsupported portfolio budget: {budget}")
    return evaluate_method(
        contract,
        _method_identity(
            method_id=f"{OPERATIONAL_PORTFOLIO_METHOD_ID}_K{budget}",
            method_family=PORTFOLIO_METHOD_FAMILY,
            native_ticket_count=budget,
            observations=observations,
        ),
        observations,
    )


def _method_lift_row(
    row_id: str,
    record: MethodEvaluationRecord,
    observations: tuple[MethodDrawObservation, ...],
    *,
    expected_max_by_draw: Mapping[str, Fraction] | None,
    expected_max_baseline_note: str,
) -> DecisionRow:
    full = _window_by_name(record, "FULL_HISTORY")
    primary = full.metrics[PRIMARY_METRIC_ID]
    m3 = full.metrics["M3_PLUS"]
    m4 = full.metrics["M4_PLUS"]
    avg = full.metrics[AVG_MATCH_ID]
    if primary.observed_value is None:
        raise CrossLaneValidationError("primary metric observed value is missing")
    if primary.random_reference is None:
        raise CrossLaneValidationError("primary metric baseline is missing")
    if m3.random_reference is None or m4.random_reference is None:
        raise CrossLaneValidationError("auxiliary tier baseline is missing")
    sample_count = full.eligible_draw_count
    observed_rate = float(primary.observed_value)
    baseline_rate = float(primary.random_reference)
    delta = observed_rate - baseline_rate
    if sample_count:
        lower, upper = wilson_score_interval(primary.success_draw_count or 0, sample_count)
        interval: dict[str, object] = {
            "method": "WILSON_SCORE_95_OBSERVED_RATE_SHIFTED_BY_FIXED_BASELINE",
            "observed_rate": {"lower": lower, "upper": upper},
            "delta_vs_baseline": {
                "lower": lower - baseline_rate,
                "upper": upper - baseline_rate,
            },
            "baseline_treated_as_fixed": True,
        }
    else:
        interval = _not_estimable_interval("zero eligible draws")

    max_hits_by_draw = {
        observation.draw_id: max(observation.main_hit_counts) for observation in observations
    }
    max_ge_3_count = sum(max_hits >= 3 for max_hits in max_hits_by_draw.values())
    max_ge_4_count = sum(max_hits >= 4 for max_hits in max_hits_by_draw.values())
    expected_max_observed = (
        Fraction(sum(max_hits_by_draw.values()), sample_count) if sample_count else None
    )
    expected_max_reference = (
        sum(expected_max_by_draw.values(), Fraction()) / sample_count
        if expected_max_by_draw and sample_count
        else None
    )
    expected_null_successes = float(primary.random_reference * sample_count)
    if sample_count < MINIMUM_SUPPORTED_DRAWS:
        insufficient_reason = (
            f"n={sample_count} < MINIMUM_SUPPORTED_DRAWS={MINIMUM_SUPPORTED_DRAWS}"
        )
    elif expected_null_successes < MINIMUM_EXPECTED_NULL_SUCCESSES:
        insufficient_reason = (
            f"expected_null_successes={expected_null_successes} < "
            f"MINIMUM_EXPECTED_NULL_SUCCESSES={MINIMUM_EXPECTED_NULL_SUCCESSES}"
        )
    else:
        insufficient_reason = ""
    classification = (
        Classification.INSUFFICIENT_POWER if insufficient_reason else Classification.INCONCLUSIVE
    )
    return DecisionRow(
        row_id=row_id,
        row_kind="METHOD_LIFT",
        feature_family_id=None,
        classification=classification,
        sample_count=sample_count,
        baseline_definition=(
            "PRIMARY M2_PLUS: exact same-draw/same-cutoff/same-K random reference from "
            "base_method_evaluation; "
            + expected_max_baseline_note
        ),
        candidate_result={
            "primary_metric_id": PRIMARY_METRIC_ID,
            "primary_success_count": primary.success_draw_count,
            "primary_observed_rate": observed_rate,
            "primary_random_reference_rate": baseline_rate,
            "avg_match_observed": None if avg.observed_value is None else float(avg.observed_value),
            "avg_match_random_reference": (
                None if avg.random_reference is None else float(avg.random_reference)
            ),
            "window_metrics": _window_metric_summary(record),
        },
        absolute_delta=delta,
        relative_lift=(delta / baseline_rate) if baseline_rate else None,
        uncertainty_interval=interval,
        auxiliary_outcomes={
            "max_hit_count_by_draw": max_hits_by_draw,
            "max_ge_3_success_count": max_ge_3_count,
            "p_max_ge_3": max_ge_3_count / sample_count if sample_count else None,
            "p_max_ge_3_random_reference": float(m3.random_reference),
            "delta_p_max_ge_3": (
                max_ge_3_count / sample_count - float(m3.random_reference)
                if sample_count
                else None
            ),
            "max_ge_4_success_count": max_ge_4_count,
            "p_max_ge_4": max_ge_4_count / sample_count if sample_count else None,
            "p_max_ge_4_random_reference": float(m4.random_reference),
            "delta_p_max_ge_4": (
                max_ge_4_count / sample_count - float(m4.random_reference)
                if sample_count
                else None
            ),
            "expected_max_main_matches_observed": (
                None if expected_max_observed is None else float(expected_max_observed)
            ),
            "expected_max_main_matches_random_reference": (
                None if expected_max_reference is None else float(expected_max_reference)
            ),
            "expected_max_reference_by_draw": (
                {
                    draw_number: float(value)
                    for draw_number, value in expected_max_by_draw.items()
                }
                if expected_max_by_draw
                else None
            ),
            "expected_max_reference_contract": expected_max_baseline_note,
        },
        stability_note=(
            f"FULL_HISTORY n={sample_count}; {insufficient_reason or 'minimum gates clear'}; "
            "recent windows are descriptive and are not searched for a winner"
        ),
        notes=(
            "Paired/matched evaluation only; target outcomes are never used in forecast "
            "construction. SUPPORTED/REFUTED is withheld without a locked confirmatory period."
        ),
    )


ANALYSIS_CONTRACT: dict[str, object] = {
    "primary_metric": {
        "id": PRIMARY_METRIC_ID,
        "definition": "at least one published ticket has at least two main-number hits",
        "source": "lottolab.research.base_method_evaluation",
    },
    "auxiliary_outcomes": list(AUXILIARY_METRIC_IDS),
    "minimum_gates": {
        "minimum_supported_draws": MINIMUM_SUPPORTED_DRAWS,
        "minimum_expected_null_successes": MINIMUM_EXPECTED_NULL_SUCCESSES,
    },
    "baseline_policy": {
        "k1": "exact single-ticket hypergeometric M2+/AVG_MATCH reference",
        "k5_k10_k20": (
            "existing portfolio_tier_probability same-K IID reference for tier rates; "
            "expected max is reported as an observed auxiliary; the exact fixed-geometry "
            "reference is not run in this bounded sample"
        ),
        "comparison_rule": "same draw, same cutoff, same published K; no cross-K lift claim",
    },
    "replay_invariants": [
        "PRE_DRAW temporal integrity",
        "strict cutoff date and cutoff draw-number ordering",
        "target_result_used=False and portfolio outcome_used=NO",
        "same draw-number outcome pairing",
        "caller chronological order preserved",
    ],
    "uncertainty_interval": {
        "method": "Wilson score 95% interval for observed primary event rate",
        "delta": "interval shifted by exact fixed baseline",
        "continuous_features": "not estimated at this sample size",
    },
    "multiple_testing": {
        "method": "NOT_APPLIED",
        "reason": (
            "No feature or lift hypothesis is selected for inferential promotion; all "
            "outcome rows in this run are gated INSUFFICIENT_POWER."
        ),
    },
    "selection_bias": {
        "winner_search": "NONE",
        "adaptive_feature_expansion": "NONE",
        "confirmatory_period": "NONE_AVAILABLE; current forward sample is exploratory",
    },
}


@dataclass(frozen=True, slots=True)
class CrossLaneValidationResult:
    feature_registry: tuple[FeatureFamilyRecord, ...]
    decision_rows: tuple[DecisionRow, ...]
    consensus_evaluation: MethodEvaluationRecord | None
    portfolio_evaluations: Mapping[int, MethodEvaluationRecord]
    consensus_forecast_count: int
    portfolio_forecast_count: int
    outcome_count: int
    consensus_pair_draw_numbers: tuple[str, ...]
    portfolio_pair_draw_numbers: tuple[str, ...]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "analysis_contract": ANALYSIS_CONTRACT,
            "decision_rows": [row.canonical_dict() for row in self.decision_rows],
            "feature_family_registry": [
                record.canonical_dict() for record in self.feature_registry
            ],
            "input_pairing": {
                "consensus_forecast_count": self.consensus_forecast_count,
                "portfolio_forecast_count": self.portfolio_forecast_count,
                "outcome_count": self.outcome_count,
                "consensus_pair_draw_numbers": list(self.consensus_pair_draw_numbers),
                "portfolio_pair_draw_numbers": list(self.portfolio_pair_draw_numbers),
            },
            "method_evaluations": {
                "consensus_k1": (
                    self.consensus_evaluation.canonical_dict()
                    if self.consensus_evaluation is not None
                    else None
                ),
                "portfolio_by_budget": {
                    str(budget): record.canonical_dict()
                    for budget, record in sorted(self.portfolio_evaluations.items())
                },
            },
            "result_schema_id": RESULT_SCHEMA_ID,
            "result_schema_version": RESULT_SCHEMA_VERSION,
            "study_id": STUDY_ID,
        }


def build_decision_table(
    *,
    consensus_records: Sequence[ConsensusForecastRecord],
    portfolio_records: Sequence[PortfolioForecastRecord],
    outcomes: Mapping[str, DrawOutcome],
    method_family_lookup: Mapping[str, str | None],
) -> CrossLaneValidationResult:
    """Assemble the complete decision table from already-parsed artifacts."""

    consensus_pairs = _paired_consensus(consensus_records, outcomes)
    portfolio_pairs = _paired_portfolio(portfolio_records, outcomes)
    consensus_by_draw = {record.draw_number: record for record, _outcome in consensus_pairs}
    portfolio_by_draw = {record.draw_number: record for record, _outcome in portfolio_pairs}

    rows: list[DecisionRow] = [
        _unavailable_row(family)
        for family in FEATURE_FAMILY_REGISTRY
        if family.availability is FeatureAvailability.UNAVAILABLE
    ]
    rows.extend(
        (
            raw_vote_support_row(consensus_pairs),
            rank_margin_row(consensus_pairs),
            cross_budget_persistence_row(consensus_by_draw, portfolio_by_draw),
            portfolio_diversity_row(portfolio_pairs),
            forecast_freshness_row(consensus_pairs),
            method_family_diversity_row(consensus_pairs, method_family_lookup),
        )
    )

    consensus_observations = tuple(
        consensus_draw_observation(record, outcome) for record, outcome in consensus_pairs
    )
    consensus_evaluation = (
        evaluate_consensus_method(consensus_observations) if consensus_observations else None
    )
    portfolio_evaluations: dict[int, MethodEvaluationRecord] = {}
    portfolio_observations_by_budget: dict[int, tuple[MethodDrawObservation, ...]] = {}
    for budget in PORTFOLIO_BUDGETS:
        observations_for_budget = tuple(
            portfolio_draw_observation(record, outcome, budget)
            for record, outcome in portfolio_pairs
        )
        portfolio_observations_by_budget[budget] = observations_for_budget
        if observations_for_budget:
            portfolio_evaluations[budget] = evaluate_portfolio_method(
                observations_for_budget, budget
            )

    rows.append(
        recent_window_vs_full_history_row(
            consensus_evaluation,
            portfolio_evaluations,
            len(consensus_pairs),
        )
    )

    if consensus_evaluation is not None:
        expected_max_by_draw = {
            record.draw_number: average_match_reference(BIG_LOTTO_MATCH_CONTRACT)
            for record, _outcome in consensus_pairs
        }
        rows.append(
            _method_lift_row(
                "method_lift__consensus_k1_vs_random_baseline",
                consensus_evaluation,
                consensus_observations,
                expected_max_by_draw=expected_max_by_draw,
                expected_max_baseline_note=(
                    "one-ticket exact uniform-draw expectation (equal to AVG_MATCH for K=1)"
                ),
            )
        )

    for budget in PORTFOLIO_BUDGETS:
        evaluation = portfolio_evaluations.get(budget)
        observations_for_budget = portfolio_observations_by_budget[budget]
        if evaluation is None:
            continue
        rows.append(
            _method_lift_row(
                f"method_lift__portfolio_k{budget}_vs_random_baseline",
                evaluation,
                observations_for_budget,
                expected_max_by_draw=None,
                expected_max_baseline_note=(
                    "same-K existing portfolio_tier_probability is the tier baseline; "
                    "expected max is observed only because the exact fixed-portfolio "
                    "geometry reference is outside this bounded run"
                ),
            )
        )

    return CrossLaneValidationResult(
        feature_registry=FEATURE_FAMILY_REGISTRY,
        decision_rows=tuple(rows),
        consensus_evaluation=consensus_evaluation,
        portfolio_evaluations=portfolio_evaluations,
        consensus_forecast_count=len(consensus_records),
        portfolio_forecast_count=len(portfolio_records),
        outcome_count=len(outcomes),
        consensus_pair_draw_numbers=tuple(record.draw_number for record, _ in consensus_pairs),
        portfolio_pair_draw_numbers=tuple(record.draw_number for record, _ in portfolio_pairs),
    )


__all__ = [
    "ANALYSIS_CONTRACT",
    "AUXILIARY_METRIC_IDS",
    "CANONICAL_CONSENSUS_METHOD_ID",
    "CONSENSUS_METHOD_FAMILY",
    "FEATURE_FAMILY_REGISTRY",
    "MINIMUM_ASSOCIATION_DRAW_COUNT",
    "OPERATIONAL_PORTFOLIO_METHOD_ID",
    "PORTFOLIO_BUDGETS",
    "PORTFOLIO_METHOD_FAMILY",
    "PRIMARY_METRIC_ID",
    "RANK_MARGIN_PAIR",
    "RESULT_SCHEMA_ID",
    "RESULT_SCHEMA_VERSION",
    "STUDY_ID",
    "Classification",
    "ConsensusForecastRecord",
    "CrossLaneValidationError",
    "CrossLaneValidationResult",
    "DecisionRow",
    "DrawOutcome",
    "FeatureAvailability",
    "FeatureFamilyRecord",
    "PortfolioForecastRecord",
    "RankedNumber",
    "build_decision_table",
    "consensus_draw_observation",
    "cross_budget_persistence_row",
    "evaluate_consensus_method",
    "evaluate_portfolio_method",
    "feature_family",
    "forecast_freshness_row",
    "method_family_diversity_row",
    "portfolio_diversity_row",
    "portfolio_draw_observation",
    "rank_margin_row",
    "raw_vote_support_row",
    "recent_window_vs_full_history_row",
    "wilson_score_interval",
]
