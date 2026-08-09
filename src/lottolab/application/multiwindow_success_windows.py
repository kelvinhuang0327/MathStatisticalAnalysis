"""Count-independent four-window official-any-prize research evidence.

The module is deliberately persistence- and HTTP-free.  A reader supplies one
validated, read-only replay source and this module computes the exact
ticket-matched null, one-sided binomial tails, Benjamini--Yekutieli values, and
signed nested-window deltas.  The result is descriptive research evidence;
it is not a prediction, ranking, promotion, or production-adoption signal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from fractions import Fraction
from math import comb, gcd

from lottolab.domain.prize_evaluation import (
    DAILY_FIVE39_PRIZE_RULE_CONTRACT,
    POWER_LOTTO_PRIZE_RULE_CONTRACT,
)


class MultiWindowSuccessQueryError(RuntimeError):
    """Base class for sanitized multi-window query failures."""


class MultiWindowSuccessResultsUnavailableError(MultiWindowSuccessQueryError):
    """The configured replay source is unavailable or fails its contract."""


class WindowKind(StrEnum):
    FULL_HISTORY = "FULL_HISTORY"
    LONG_750 = "LONG_750"
    MEDIUM_300 = "MEDIUM_300"
    SHORT_50 = "SHORT_50"


class WindowStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INSUFFICIENT_WINDOW_HISTORY = "INSUFFICIENT_WINDOW_HISTORY"
    NO_ELIGIBLE_TARGETS = "NO_ELIGIBLE_TARGETS"


class StabilityRelation(StrEnum):
    HIGHER = "HIGHER"
    EQUAL = "EQUAL"
    LOWER = "LOWER"
    UNAVAILABLE = "UNAVAILABLE"


WINDOW_DEFINITIONS: tuple[tuple[WindowKind, int | None], ...] = (
    (WindowKind.FULL_HISTORY, None),
    (WindowKind.LONG_750, 750),
    (WindowKind.MEDIUM_300, 300),
    (WindowKind.SHORT_50, 50),
)

_STABILITY_PAIRS: tuple[tuple[WindowKind, WindowKind], ...] = (
    (WindowKind.FULL_HISTORY, WindowKind.LONG_750),
    (WindowKind.LONG_750, WindowKind.MEDIUM_300),
    (WindowKind.MEDIUM_300, WindowKind.SHORT_50),
    (WindowKind.LONG_750, WindowKind.SHORT_50),
)

_EVENT_ID = "OFFICIAL_ANY_PRIZE_TARGET_SUCCESS"
_EVIDENCE_STATUS = "DESCRIPTIVE_ONLY"
_SAMPLING_POLICY = "UNIFORM_IID_LEGAL_TICKETS_WITH_REPLACEMENT"


def _decimal_18(numerator: int, denominator: int) -> str:
    sign = "-" if numerator < 0 else ""
    numerator = abs(numerator)
    scale = 10**18
    rounded, remainder = divmod(numerator * scale, denominator)
    if remainder * 2 > denominator or (
        remainder * 2 == denominator and rounded % 2 == 1
    ):
        rounded += 1
    integer_part, fractional_part = divmod(rounded, scale)
    return f"{sign}{integer_part}.{fractional_part:018d}"


@dataclass(frozen=True, slots=True)
class ExactRational:
    """A reduced exact rational, including signed stability deltas."""

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise ValueError("exact rational fields must be integers")
        if self.denominator <= 0:
            raise ValueError("exact rational denominator must be positive")
        if gcd(abs(self.numerator), self.denominator) != 1:
            raise ValueError("exact rational must be reduced")

    @classmethod
    def from_fraction(cls, value: Fraction) -> ExactRational:
        if type(value) is not Fraction:
            raise ValueError("value must be a Fraction")
        return cls(value.numerator, value.denominator)

    def as_fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    def canonical_dict(self) -> dict[str, int | str]:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "decimal_18": _decimal_18(self.numerator, self.denominator),
        }


@dataclass(frozen=True, slots=True)
class WindowDefinition:
    window_kind: WindowKind
    requested_target_count: int | None
    selection: str
    window_role: str = "DESCRIPTIVE_RESEARCH"

    def canonical_dict(self) -> dict[str, object]:
        return {
            "window_kind": self.window_kind.value,
            "requested_target_count": self.requested_target_count,
            "selection": self.selection,
            "window_role": self.window_role,
        }


@dataclass(frozen=True, slots=True)
class TierCount:
    tier_id: str
    tier_order: int
    count: int

    def canonical_dict(self) -> dict[str, object]:
        return {
            "tier_id": self.tier_id,
            "tier_order": self.tier_order,
            "count": self.count,
        }


@dataclass(frozen=True, slots=True)
class TargetOutcome:
    """One complete target portfolio after official ticket evaluation."""

    target_id: str
    target_date: str
    cutoff_draw_id: str | None
    cutoff_draw_date: str | None
    target_order: int
    cutoff_order: int | None
    native_ticket_count: int
    ticket_count: int
    winning_ticket_count: int
    tier_counts: tuple[tuple[str, int, int], ...]


@dataclass(frozen=True, slots=True)
class StrategySource:
    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    min_history: int
    observations: tuple[TargetOutcome, ...]


@dataclass(frozen=True, slots=True)
class NullContract:
    lottery_type: str
    game_spec: str
    sampling_policy: str
    official_evaluator: str
    prize_rule_version: str
    prize_rule_source_sha256: str
    legal_ticket_count: int
    any_prize_ticket_count: int
    single_ticket_any_prize_probability: ExactRational
    hit_state_weights: tuple[dict[str, object], ...]
    portfolio_formula: str = "1-(1-P_RANDOM_SINGLE_TICKET_ANY_PRIZE)^N"

    def canonical_dict(self) -> dict[str, object]:
        return {
            "lottery_type": self.lottery_type,
            "game_spec": self.game_spec,
            "sampling_policy": self.sampling_policy,
            "official_evaluator": self.official_evaluator,
            "prize_rule_version": self.prize_rule_version,
            "prize_rule_source_sha256": self.prize_rule_source_sha256,
            "legal_ticket_count": self.legal_ticket_count,
            "any_prize_ticket_count": self.any_prize_ticket_count,
            "single_ticket_any_prize_probability": (
                self.single_ticket_any_prize_probability.canonical_dict()
            ),
            "portfolio_formula": self.portfolio_formula,
            "hit_state_weights": list(self.hit_state_weights),
        }


@dataclass(frozen=True, slots=True)
class MultiWindowSource:
    lottery_type: str
    run_id: str
    schema_version: str
    source_sha256: str
    source_commit: str
    strategy_set_fingerprint: str
    status: str
    draw_count: int
    strategies: tuple[StrategySource, ...]
    null_contract: NullContract
    source_authority: str


@dataclass(frozen=True, slots=True)
class WindowResult:
    lottery_type: str
    run_id: str
    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    window_kind: WindowKind
    window_role: str
    status: WindowStatus
    source_target_count: int
    requested_target_count: int | None
    actual_target_count: int
    first_target_id: str | None
    first_target_date: str | None
    last_target_id: str | None
    last_target_date: str | None
    observed_winning_target_count: int
    observed_winning_target_rate: ExactRational | None
    observed_ticket_count: int
    observed_winning_ticket_count: int
    observed_ticket_winning_rate: ExactRational | None
    prize_tier_vector: tuple[TierCount, ...]
    highest_prize_tier: str | None
    null_single_ticket_probability: ExactRational
    null_portfolio_probability: ExactRational
    expected_null_target_successes: ExactRational | None
    observed_minus_null_rate: ExactRational | None
    lift_vs_null: ExactRational | None
    raw_p_value: ExactRational | None
    by_adjusted_p_value: ExactRational | None
    evidence_status: str = _EVIDENCE_STATUS

    def canonical_dict(self) -> dict[str, object]:
        return {
            "lottery_type": self.lottery_type,
            "run_id": self.run_id,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "native_ticket_count": self.native_ticket_count,
            "window_kind": self.window_kind.value,
            "window_role": self.window_role,
            "status": self.status.value,
            "source_target_count": self.source_target_count,
            "requested_target_count": self.requested_target_count,
            "actual_target_count": self.actual_target_count,
            "first_target_id": self.first_target_id,
            "first_target_date": self.first_target_date,
            "last_target_id": self.last_target_id,
            "last_target_date": self.last_target_date,
            "observed_winning_target_count": self.observed_winning_target_count,
            "observed_winning_target_rate": _optional_dict(self.observed_winning_target_rate),
            "observed_ticket_count": self.observed_ticket_count,
            "observed_winning_ticket_count": self.observed_winning_ticket_count,
            "observed_ticket_winning_rate": _optional_dict(self.observed_ticket_winning_rate),
            "prize_tier_vector": [item.canonical_dict() for item in self.prize_tier_vector],
            "highest_prize_tier": self.highest_prize_tier,
            "null_single_ticket_probability": self.null_single_ticket_probability.canonical_dict(),
            "null_portfolio_probability": self.null_portfolio_probability.canonical_dict(),
            "expected_null_target_successes": _optional_dict(self.expected_null_target_successes),
            "observed_minus_null_rate": _optional_dict(self.observed_minus_null_rate),
            "lift_vs_null": _optional_dict(self.lift_vs_null),
            "raw_p_value": _optional_dict(self.raw_p_value),
            "by_adjusted_p_value": _optional_dict(self.by_adjusted_p_value),
            "evidence_status": self.evidence_status,
        }


@dataclass(frozen=True, slots=True)
class StabilityDelta:
    strategy_id: str
    strategy_version: str
    from_window: WindowKind
    to_window: WindowKind
    delta_observed_winning_target_rate: ExactRational | None
    relation: StabilityRelation

    def canonical_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "from_window": self.from_window.value,
            "to_window": self.to_window.value,
            "delta_observed_winning_target_rate": _optional_dict(
                self.delta_observed_winning_target_rate
            ),
            "relation": self.relation.value,
        }


@dataclass(frozen=True, slots=True)
class MultiWindowAnalysis:
    lottery_type: str
    run_id: str
    schema_version: str
    source_sha256: str
    source_commit: str
    strategy_set_fingerprint: str
    status: str
    draw_count: int
    event: str
    evidence_status: str
    research_only: bool
    promotion_allowed: bool
    window_definitions: tuple[WindowDefinition, ...]
    null_contract: NullContract
    strategy_count: int
    family_size: int
    rows: tuple[WindowResult, ...]
    stability: tuple[StabilityDelta, ...]
    source_authority: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "lottery_type": self.lottery_type,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "source_sha256": self.source_sha256,
            "source_commit": self.source_commit,
            "strategy_set_fingerprint": self.strategy_set_fingerprint,
            "status": self.status,
            "draw_count": self.draw_count,
            "event": self.event,
            "evidence_status": self.evidence_status,
            "research_only": self.research_only,
            "promotion_allowed": self.promotion_allowed,
            "window_definitions": [item.canonical_dict() for item in self.window_definitions],
            "null_contract": self.null_contract.canonical_dict(),
            "strategy_count": self.strategy_count,
            "family_size": self.family_size,
            "rows": [item.canonical_dict() for item in self.rows],
            "stability": [item.canonical_dict() for item in self.stability],
            "source_authority": self.source_authority,
        }


def _optional_dict(value: ExactRational | None) -> dict[str, int | str] | None:
    return None if value is None else value.canonical_dict()


def _ratio(numerator: int, denominator: int) -> ExactRational:
    return ExactRational.from_fraction(Fraction(numerator, denominator))


def _fraction_ratio(numerator: Fraction) -> ExactRational:
    return ExactRational.from_fraction(numerator)


def _raw_p_fraction(row: WindowResult) -> Fraction:
    value = row.raw_p_value
    return Fraction(1) if value is None else value.as_fraction()


def exact_binomial_upper_tail(
    observation_count: int, observed_success_count: int, probability: ExactRational
) -> ExactRational:
    """Return an exact upper tail using a recurrence between adjacent terms."""

    if observed_success_count == 0:
        return ExactRational(1, 1)
    success = probability.numerator
    total = probability.denominator
    failure = total - success
    if success == 0:
        return ExactRational(0, 1)
    if failure == 0:
        return ExactRational(1, 1)

    denominator = total**observation_count
    lower_term_count = observed_success_count
    upper_term_count = observation_count - observed_success_count + 1
    if upper_term_count <= lower_term_count:
        term = (
            comb(observation_count, observed_success_count)
            * success**observed_success_count
            * failure ** (observation_count - observed_success_count)
        )
        numerator = term
        for successes in range(observed_success_count, observation_count):
            term = term * (observation_count - successes) * success
            term //= (successes + 1) * failure
            numerator += term
        return ExactRational.from_fraction(Fraction(numerator, denominator))

    term = failure**observation_count
    lower = term
    for successes in range(0, observed_success_count - 1):
        term = term * (observation_count - successes) * success
        term //= (successes + 1) * failure
        lower += term
    return ExactRational.from_fraction(Fraction(denominator - lower, denominator))


def _null_contract_for(lottery_type: str) -> NullContract:
    if lottery_type == "DAILY_539":
        legal_ticket_count = comb(39, 5)
        states: list[dict[str, object]] = []
        any_prize_ticket_count = 0
        for hit_count in range(6):
            count = comb(5, hit_count) * comb(34, 5 - hit_count)
            tier = DAILY_FIVE39_PRIZE_RULE_CONTRACT.resolve(match_count=hit_count)
            if tier is not None:
                any_prize_ticket_count += count
            states.append(
                {
                    "main_hits": hit_count,
                    "zone2_hit": False,
                    "legal_ticket_count": count,
                    "is_any_prize": tier is not None,
                    "prize_tier": None if tier is None else tier.tier_id.value,
                }
            )
        rule = DAILY_FIVE39_PRIZE_RULE_CONTRACT
        return NullContract(
            lottery_type=lottery_type,
            game_spec="DAILY_539_5_OF_39",
            sampling_policy=_SAMPLING_POLICY,
            official_evaluator="evaluate_daily_539_ticket",
            prize_rule_version=rule.schema_version,
            prize_rule_source_sha256=rule.source_sha256,
            legal_ticket_count=legal_ticket_count,
            any_prize_ticket_count=any_prize_ticket_count,
            single_ticket_any_prize_probability=_fraction_ratio(
                Fraction(any_prize_ticket_count, legal_ticket_count)
            ),
            hit_state_weights=tuple(states),
        )
    if lottery_type == "POWER_LOTTO":
        legal_ticket_count = comb(38, 6) * 8
        states = []
        any_prize_ticket_count = 0
        for zone1_hits in range(7):
            for zone2_hit in (False, True):
                count = comb(6, zone1_hits) * comb(32, 6 - zone1_hits)
                count *= 1 if zone2_hit else 7
                tier = POWER_LOTTO_PRIZE_RULE_CONTRACT.resolve(
                    zone1_hits=zone1_hits, zone2_hit=zone2_hit
                )
                if tier is not None:
                    any_prize_ticket_count += count
                states.append(
                    {
                        "zone1_hits": zone1_hits,
                        "zone2_hit": zone2_hit,
                        "legal_ticket_count": count,
                        "is_any_prize": tier is not None,
                        "prize_tier": None if tier is None else tier.tier_id.value,
                    }
                )
        rule = POWER_LOTTO_PRIZE_RULE_CONTRACT
        return NullContract(
            lottery_type=lottery_type,
            game_spec="POWER_LOTTO_6_OF_38_PLUS_1_OF_8",
            sampling_policy=_SAMPLING_POLICY,
            official_evaluator="evaluate_power_lotto_ticket",
            prize_rule_version=rule.schema_version,
            prize_rule_source_sha256=rule.source_sha256,
            legal_ticket_count=legal_ticket_count,
            any_prize_ticket_count=any_prize_ticket_count,
            single_ticket_any_prize_probability=_fraction_ratio(
                Fraction(any_prize_ticket_count, legal_ticket_count)
            ),
            hit_state_weights=tuple(states),
        )
    raise ValueError(f"unsupported multi-window lottery type: {lottery_type}")


def _tier_vector(
    lottery_type: str, counts: dict[str, int]
) -> tuple[TierCount, ...]:
    if lottery_type == "DAILY_539":
        tiers = DAILY_FIVE39_PRIZE_RULE_CONTRACT.tiers
    elif lottery_type == "POWER_LOTTO":
        tiers = POWER_LOTTO_PRIZE_RULE_CONTRACT.tiers
    else:
        raise ValueError(f"unsupported multi-window lottery type: {lottery_type}")
    return tuple(
        TierCount(tier.tier_id.value, tier.tier_order, counts.get(tier.tier_id.value, 0))
        for tier in tiers
    )


def _highest_prize_tier(vector: Sequence[TierCount]) -> str | None:
    for item in vector:
        if item.count > 0:
            return item.tier_id
    return None


def _window_result(
    source: MultiWindowSource,
    strategy: StrategySource,
    window_kind: WindowKind,
    requested_target_count: int | None,
) -> WindowResult:
    observations = strategy.observations
    selected = (
        observations
        if requested_target_count is None
        else observations[-requested_target_count:]
    )
    if not selected:
        status = WindowStatus.NO_ELIGIBLE_TARGETS
    elif requested_target_count is not None and len(observations) < requested_target_count:
        status = WindowStatus.INSUFFICIENT_WINDOW_HISTORY
    else:
        status = WindowStatus.COMPLETE

    tier_counts: dict[str, int] = {}
    target_success_count = 0
    ticket_count = 0
    winning_ticket_count = 0
    for observation in selected:
        target_success_count += int(observation.winning_ticket_count > 0)
        ticket_count += observation.ticket_count
        winning_ticket_count += observation.winning_ticket_count
        for tier_id, _tier_order, count in observation.tier_counts:
            tier_counts[tier_id] = tier_counts.get(tier_id, 0) + count

    vector = _tier_vector(source.lottery_type, tier_counts)
    portfolio_probability = _fraction_ratio(
        1
        - (1 - source.null_contract.single_ticket_any_prize_probability.as_fraction())
        ** strategy.native_ticket_count
    )
    target_rate: ExactRational | None = None
    ticket_rate: ExactRational | None = None
    expected: ExactRational | None = None
    excess: ExactRational | None = None
    lift: ExactRational | None = None
    raw_p: ExactRational | None = None
    if status is WindowStatus.COMPLETE:
        target_rate = _ratio(target_success_count, len(selected))
        ticket_rate = _ratio(winning_ticket_count, ticket_count)
        expected = _fraction_ratio(portfolio_probability.as_fraction() * len(selected))
        excess = _fraction_ratio(target_rate.as_fraction() - portfolio_probability.as_fraction())
        lift = _fraction_ratio(target_rate.as_fraction() / portfolio_probability.as_fraction())
        raw_p = exact_binomial_upper_tail(
            len(selected), target_success_count, portfolio_probability
        )

    first = selected[0] if selected else None
    last = selected[-1] if selected else None
    return WindowResult(
        lottery_type=source.lottery_type,
        run_id=source.run_id,
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.strategy_version,
        native_ticket_count=strategy.native_ticket_count,
        window_kind=window_kind,
        window_role="DESCRIPTIVE_RESEARCH",
        status=status,
        source_target_count=len(observations),
        requested_target_count=requested_target_count,
        actual_target_count=len(selected),
        first_target_id=None if first is None else first.target_id,
        first_target_date=None if first is None else first.target_date,
        last_target_id=None if last is None else last.target_id,
        last_target_date=None if last is None else last.target_date,
        observed_winning_target_count=target_success_count,
        observed_winning_target_rate=target_rate,
        observed_ticket_count=ticket_count,
        observed_winning_ticket_count=winning_ticket_count,
        observed_ticket_winning_rate=ticket_rate,
        prize_tier_vector=vector,
        highest_prize_tier=_highest_prize_tier(vector),
        null_single_ticket_probability=source.null_contract.single_ticket_any_prize_probability,
        null_portfolio_probability=portfolio_probability,
        expected_null_target_successes=expected,
        observed_minus_null_rate=excess,
        lift_vs_null=lift,
        raw_p_value=raw_p,
        by_adjusted_p_value=None,
    )


def _benjamini_yekutieli(rows: Sequence[WindowResult]) -> tuple[ExactRational, ...]:
    family_size = len(rows)
    if family_size <= 0:
        return ()
    harmonic = sum((Fraction(1, rank) for rank in range(1, family_size + 1)), Fraction(0))
    ordered = sorted(
        range(family_size),
        key=lambda index: (_raw_p_fraction(rows[index]), index),
    )
    candidates = [Fraction(1) for _ in rows]
    for rank, index in enumerate(ordered, start=1):
        raw = _raw_p_fraction(rows[index])
        candidates[index] = min(Fraction(1), raw * family_size * harmonic / rank)
    adjusted = [Fraction(1) for _ in rows]
    running = Fraction(1)
    for index in reversed(ordered):
        running = min(running, candidates[index])
        adjusted[index] = running
    return tuple(ExactRational.from_fraction(value) for value in adjusted)


def _stability(
    rows_by_strategy: dict[tuple[str, str], dict[WindowKind, WindowResult]],
) -> tuple[StabilityDelta, ...]:
    values: list[StabilityDelta] = []
    for (strategy_id, strategy_version), windows in sorted(rows_by_strategy.items()):
        for from_window, to_window in _STABILITY_PAIRS:
            left = windows[from_window]
            right = windows[to_window]
            if (
                left.status is not WindowStatus.COMPLETE
                or right.status is not WindowStatus.COMPLETE
                or left.observed_winning_target_rate is None
                or right.observed_winning_target_rate is None
            ):
                values.append(
                    StabilityDelta(
                        strategy_id,
                        strategy_version,
                        from_window,
                        to_window,
                        None,
                        StabilityRelation.UNAVAILABLE,
                    )
                )
                continue
            delta = _fraction_ratio(
                right.observed_winning_target_rate.as_fraction()
                - left.observed_winning_target_rate.as_fraction()
            )
            relation = (
                StabilityRelation.HIGHER
                if delta.numerator > 0
                else StabilityRelation.LOWER
                if delta.numerator < 0
                else StabilityRelation.EQUAL
            )
            values.append(
                StabilityDelta(
                    strategy_id,
                    strategy_version,
                    from_window,
                    to_window,
                    delta,
                    relation,
                )
            )
    return tuple(values)


def analyze_multiwindow_success_windows(source: MultiWindowSource) -> MultiWindowAnalysis:
    """Compute the complete four-window evidence projection for one source."""

    if not source.strategies:
        raise MultiWindowSuccessResultsUnavailableError("replay source has no strategies")
    if any(strategy.native_ticket_count <= 0 for strategy in source.strategies):
        raise MultiWindowSuccessResultsUnavailableError(
            "replay source contains a non-positive native ticket count"
        )
    ordered_strategies = tuple(
        sorted(source.strategies, key=lambda item: (item.strategy_id, item.strategy_version))
    )
    rows: list[WindowResult] = []
    rows_by_strategy: dict[tuple[str, str], dict[WindowKind, WindowResult]] = {}
    for strategy in ordered_strategies:
        key = (strategy.strategy_id, strategy.strategy_version)
        if key in rows_by_strategy:
            raise MultiWindowSuccessResultsUnavailableError(
                "replay source contains duplicate strategy identities"
            )
        windows: dict[WindowKind, WindowResult] = {}
        for window_kind, requested_target_count in WINDOW_DEFINITIONS:
            result = _window_result(source, strategy, window_kind, requested_target_count)
            windows[window_kind] = result
            rows.append(result)
        rows_by_strategy[key] = windows
    adjusted = _benjamini_yekutieli(rows)
    rows = [replace(row, by_adjusted_p_value=adjusted[index]) for index, row in enumerate(rows)]
    return MultiWindowAnalysis(
        lottery_type=source.lottery_type,
        run_id=source.run_id,
        schema_version=source.schema_version,
        source_sha256=source.source_sha256,
        source_commit=source.source_commit,
        strategy_set_fingerprint=source.strategy_set_fingerprint,
        status=source.status,
        draw_count=source.draw_count,
        event=_EVENT_ID,
        evidence_status=_EVIDENCE_STATUS,
        research_only=True,
        promotion_allowed=False,
        window_definitions=tuple(
            WindowDefinition(
                window_kind=window_kind,
                requested_target_count=requested_target_count,
                selection=(
                    "ALL_ELIGIBLE_COMPLETE_TARGETS"
                    if requested_target_count is None
                    else "LATEST_MIN_REQUESTED_OR_AVAILABLE_ELIGIBLE_COMPLETE_TARGETS"
                ),
            )
            for window_kind, requested_target_count in WINDOW_DEFINITIONS
        ),
        null_contract=source.null_contract,
        strategy_count=len(ordered_strategies),
        family_size=len(rows),
        rows=tuple(rows),
        stability=_stability(rows_by_strategy),
        source_authority=source.source_authority,
    )


def source_with_default_null_contract(
    *,
    lottery_type: str,
    run_id: str,
    schema_version: str,
    source_sha256: str,
    source_commit: str,
    strategy_set_fingerprint: str,
    status: str,
    draw_count: int,
    strategies: tuple[StrategySource, ...],
    source_authority: str,
) -> MultiWindowSource:
    """Small construction boundary used by SQLite readers and focused tests."""

    return MultiWindowSource(
        lottery_type=lottery_type,
        run_id=run_id,
        schema_version=schema_version,
        source_sha256=source_sha256,
        source_commit=source_commit,
        strategy_set_fingerprint=strategy_set_fingerprint,
        status=status,
        draw_count=draw_count,
        strategies=strategies,
        null_contract=_null_contract_for(lottery_type),
        source_authority=source_authority,
    )


__all__ = [
    "ExactRational",
    "MultiWindowAnalysis",
    "MultiWindowSource",
    "MultiWindowSuccessQueryError",
    "MultiWindowSuccessResultsUnavailableError",
    "NullContract",
    "StabilityDelta",
    "StabilityRelation",
    "StrategySource",
    "TargetOutcome",
    "TierCount",
    "WindowDefinition",
    "WindowKind",
    "WindowResult",
    "WindowStatus",
    "analyze_multiwindow_success_windows",
    "exact_binomial_upper_tail",
    "source_with_default_null_contract",
]
