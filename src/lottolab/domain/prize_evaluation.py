"""Lottery-specific official prize-tier evaluation, dispatched by lottery type.

Each lottery type owns its own versioned, source-bound prize-tier table.
There is no universal cross-lottery hit threshold: a hit signature that wins
one lottery's prize tier has no bearing on any other lottery's rules.  Only
BIG_LOTTO, POWER_LOTTO (Super Lotto 638, 威力彩), and DAILY_539 (今彩539)
are implemented here; other lottery types must supply their own evaluator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    BigLottoPrizeTier,
    resolve_big_lotto_prize_tier,
    score_big_lotto_ticket,
)

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class PowerLottoPrizeTierId(StrEnum):
    """Stable identifiers for the official POWER_LOTTO prize tiers, highest to lowest."""

    FIRST = "FIRST"
    SECOND = "SECOND"
    THIRD = "THIRD"
    FOURTH = "FOURTH"
    FIFTH = "FIFTH"
    SIXTH = "SIXTH"
    SEVENTH = "SEVENTH"
    EIGHTH = "EIGHTH"
    NINTH = "NINTH"
    GENERAL = "GENERAL"


@dataclass(frozen=True, slots=True)
class PowerLottoPrizeTier:
    """One official POWER_LOTTO prize tier and its unique hit signature."""

    tier_id: PowerLottoPrizeTierId
    tier_order: int
    official_label: str
    zone1_hits: int
    zone2_hit: bool
    prize_amount: int | None

    def validate(self) -> None:
        if type(self.tier_id) is not PowerLottoPrizeTierId:
            raise ValueError("tier_id must be a PowerLottoPrizeTierId")
        if type(self.tier_order) is not int or not 1 <= self.tier_order <= 10:
            raise ValueError("tier_order must be an integer between 1 and 10")
        if type(self.official_label) is not str or not self.official_label.strip():
            raise ValueError("official_label must be a non-empty string")
        if type(self.zone1_hits) is not int or not 0 <= self.zone1_hits <= 6:
            raise ValueError("zone1_hits must be an integer between 0 and 6")
        if type(self.zone2_hit) is not bool:
            raise ValueError("zone2_hit must be a boolean")
        if self.prize_amount is not None and (
            type(self.prize_amount) is not int or self.prize_amount <= 0
        ):
            raise ValueError("prize_amount must be a positive integer or None")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "official_label": self.official_label,
            "prize_amount": self.prize_amount,
            "tier_id": self.tier_id.value,
            "tier_order": self.tier_order,
            "zone1_hits": self.zone1_hits,
            "zone2_hit": self.zone2_hit,
        }


@dataclass(frozen=True, slots=True)
class PowerLottoPrizeRuleContract:
    """Versioned, source-bound collection of official POWER_LOTTO prize tiers."""

    schema_version: str
    source_sha256: str
    source_url: str
    source_locator: str
    source_accessed_at: datetime
    tiers: tuple[PowerLottoPrizeTier, ...]

    def validate(self) -> None:
        for name, value in (
            ("schema_version", self.schema_version),
            ("source_sha256", self.source_sha256),
            ("source_url", self.source_url),
            ("source_locator", self.source_locator),
        ):
            if type(value) is not str or not value.strip():
                raise ValueError(f"prize_rule.{name} must be a non-empty string")
        if _SHA256.fullmatch(self.source_sha256) is None:
            raise ValueError("prize_rule.source_sha256 must be a lowercase SHA-256 digest")
        if type(self.source_accessed_at) is not datetime:
            raise ValueError("prize_rule.source_accessed_at must be a datetime")
        if self.source_accessed_at.tzinfo is None:
            raise ValueError("prize_rule.source_accessed_at must be timezone-aware")
        if self.source_accessed_at.utcoffset() != UTC.utcoffset(self.source_accessed_at):
            raise ValueError("prize_rule.source_accessed_at must use UTC")
        if type(self.tiers) is not tuple or not self.tiers:
            raise ValueError("prize_rule.tiers must be a non-empty tuple")

        expected_ids = tuple(PowerLottoPrizeTierId)
        actual_ids: list[PowerLottoPrizeTierId] = []
        signatures: set[tuple[int, bool]] = set()
        orders: set[int] = set()
        for index, tier in enumerate(self.tiers, start=1):
            if type(tier) is not PowerLottoPrizeTier:
                raise ValueError("prize_rule.tiers must contain PowerLottoPrizeTier values")
            tier.validate()
            if tier.tier_order != index:
                raise ValueError("prize_rule.tiers must be listed in official tier_order")
            actual_ids.append(tier.tier_id)
            signature = (tier.zone1_hits, tier.zone2_hit)
            if signature in signatures:
                raise ValueError("prize_rule.tiers contains an ambiguous hit signature")
            signatures.add(signature)
            orders.add(tier.tier_order)
        if tuple(actual_ids) != expected_ids:
            raise ValueError(
                "prize_rule.tiers must contain every tier identifier exactly once "
                "in canonical order"
            )
        if orders != set(range(1, 11)):
            raise ValueError("prize_rule.tiers must cover tier_order 1 through 10 exactly once")

    def resolve(self, *, zone1_hits: int, zone2_hit: bool) -> PowerLottoPrizeTier | None:
        """Return the matching official tier, or ``None`` when the signature does not win."""

        for tier in self.tiers:
            if tier.zone1_hits == zone1_hits and tier.zone2_hit is zone2_hit:
                return tier
        return None

    def canonical_dict(self) -> dict[str, object]:
        accessed_at = self.source_accessed_at.isoformat().replace("+00:00", "Z")
        return {
            "schema_version": self.schema_version,
            "source_accessed_at": accessed_at,
            "source_locator": self.source_locator,
            "source_sha256": self.source_sha256,
            "source_url": self.source_url,
            "tiers": [tier.canonical_dict() for tier in self.tiers],
        }


POWER_LOTTO_PRIZE_RULE_CONTRACT = PowerLottoPrizeRuleContract(
    schema_version="power-lotto-prize-rule-2026-08-04.1",
    source_sha256="a7e3c41b13c6927f333a309725d870b6509bb13e9f71c5995f5ff3bd931f1836",
    source_url="https://www.taiwanlottery.com/_nuxt/_game_.1_0_8_74.js",
    source_locator="super_lotto638.tableData, UTF-8 bytes 5277-6339",
    source_accessed_at=datetime(2026, 8, 4, 13, 57, 20, tzinfo=UTC),
    tiers=(
        PowerLottoPrizeTier(PowerLottoPrizeTierId.FIRST, 1, "頭獎", 6, True, None),
        PowerLottoPrizeTier(PowerLottoPrizeTierId.SECOND, 2, "貳獎", 6, False, None),
        PowerLottoPrizeTier(PowerLottoPrizeTierId.THIRD, 3, "參獎", 5, True, 150_000),
        PowerLottoPrizeTier(PowerLottoPrizeTierId.FOURTH, 4, "肆獎", 5, False, 20_000),
        PowerLottoPrizeTier(PowerLottoPrizeTierId.FIFTH, 5, "伍獎", 4, True, 4_000),
        PowerLottoPrizeTier(PowerLottoPrizeTierId.SIXTH, 6, "陸獎", 4, False, 800),
        PowerLottoPrizeTier(PowerLottoPrizeTierId.SEVENTH, 7, "柒獎", 3, True, 400),
        PowerLottoPrizeTier(PowerLottoPrizeTierId.EIGHTH, 8, "捌獎", 2, True, 200),
        PowerLottoPrizeTier(PowerLottoPrizeTierId.NINTH, 9, "玖獎", 3, False, 100),
        PowerLottoPrizeTier(PowerLottoPrizeTierId.GENERAL, 10, "普獎", 1, True, 100),
    ),
)
POWER_LOTTO_PRIZE_RULE_CONTRACT.validate()


class DailyFive39PrizeTierId(StrEnum):
    """Stable identifiers for the official DAILY_539 prize tiers, highest to lowest."""

    FIRST = "FIRST"
    SECOND = "SECOND"
    THIRD = "THIRD"
    FOURTH = "FOURTH"


@dataclass(frozen=True, slots=True)
class DailyFive39PrizeTier:
    """One official DAILY_539 prize tier and its unique hit signature.

    DAILY_539 has a single 39-number zone and no second zone, unlike
    POWER_LOTTO; ``match_count`` is the only hit signature component.
    """

    tier_id: DailyFive39PrizeTierId
    tier_order: int
    official_label: str
    match_count: int
    prize_amount: int

    def validate(self) -> None:
        if type(self.tier_id) is not DailyFive39PrizeTierId:
            raise ValueError("tier_id must be a DailyFive39PrizeTierId")
        if type(self.tier_order) is not int or not 1 <= self.tier_order <= 4:
            raise ValueError("tier_order must be an integer between 1 and 4")
        if type(self.official_label) is not str or not self.official_label.strip():
            raise ValueError("official_label must be a non-empty string")
        if type(self.match_count) is not int or not 2 <= self.match_count <= 5:
            raise ValueError("match_count must be an integer between 2 and 5")
        if type(self.prize_amount) is not int or self.prize_amount <= 0:
            raise ValueError("prize_amount must be a positive integer")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "match_count": self.match_count,
            "official_label": self.official_label,
            "prize_amount": self.prize_amount,
            "tier_id": self.tier_id.value,
            "tier_order": self.tier_order,
        }


@dataclass(frozen=True, slots=True)
class DailyFive39PrizeRuleContract:
    """Versioned, source-bound collection of official DAILY_539 prize tiers."""

    schema_version: str
    source_sha256: str
    source_url: str
    source_locator: str
    source_accessed_at: datetime
    tiers: tuple[DailyFive39PrizeTier, ...]

    def validate(self) -> None:
        for name, value in (
            ("schema_version", self.schema_version),
            ("source_sha256", self.source_sha256),
            ("source_url", self.source_url),
            ("source_locator", self.source_locator),
        ):
            if type(value) is not str or not value.strip():
                raise ValueError(f"prize_rule.{name} must be a non-empty string")
        if _SHA256.fullmatch(self.source_sha256) is None:
            raise ValueError("prize_rule.source_sha256 must be a lowercase SHA-256 digest")
        if type(self.source_accessed_at) is not datetime:
            raise ValueError("prize_rule.source_accessed_at must be a datetime")
        if self.source_accessed_at.tzinfo is None:
            raise ValueError("prize_rule.source_accessed_at must be timezone-aware")
        if self.source_accessed_at.utcoffset() != UTC.utcoffset(self.source_accessed_at):
            raise ValueError("prize_rule.source_accessed_at must use UTC")
        if type(self.tiers) is not tuple or not self.tiers:
            raise ValueError("prize_rule.tiers must be a non-empty tuple")

        expected_ids = tuple(DailyFive39PrizeTierId)
        actual_ids: list[DailyFive39PrizeTierId] = []
        signatures: set[int] = set()
        orders: set[int] = set()
        for index, tier in enumerate(self.tiers, start=1):
            if type(tier) is not DailyFive39PrizeTier:
                raise ValueError("prize_rule.tiers must contain DailyFive39PrizeTier values")
            tier.validate()
            if tier.tier_order != index:
                raise ValueError("prize_rule.tiers must be listed in official tier_order")
            actual_ids.append(tier.tier_id)
            if tier.match_count in signatures:
                raise ValueError("prize_rule.tiers contains an ambiguous hit signature")
            signatures.add(tier.match_count)
            orders.add(tier.tier_order)
        if tuple(actual_ids) != expected_ids:
            raise ValueError(
                "prize_rule.tiers must contain every tier identifier exactly once "
                "in canonical order"
            )
        if orders != set(range(1, 5)):
            raise ValueError("prize_rule.tiers must cover tier_order 1 through 4 exactly once")

    def resolve(self, *, match_count: int) -> DailyFive39PrizeTier | None:
        """Return the matching official tier, or ``None`` when the signature does not win."""

        for tier in self.tiers:
            if tier.match_count == match_count:
                return tier
        return None

    def canonical_dict(self) -> dict[str, object]:
        accessed_at = self.source_accessed_at.isoformat().replace("+00:00", "Z")
        return {
            "schema_version": self.schema_version,
            "source_accessed_at": accessed_at,
            "source_locator": self.source_locator,
            "source_sha256": self.source_sha256,
            "source_url": self.source_url,
            "tiers": [tier.canonical_dict() for tier in self.tiers],
        }


DAILY_FIVE39_PRIZE_RULE_CONTRACT = DailyFive39PrizeRuleContract(
    schema_version="daily-539-prize-rule-2026-08-05.1",
    source_sha256="a7e3c41b13c6927f333a309725d870b6509bb13e9f71c5995f5ff3bd931f1836",
    source_url="https://www.taiwanlottery.com/_nuxt/_game_.1_0_8_74.js",
    source_locator=(
        "daily_cash.tableData (BaseRule award/type), UTF-8 bytes 8406-9404, combined with "
        "daily_cash bonus table (BonusDistribution unit prize amounts), UTF-8 bytes 23483-24422"
    ),
    source_accessed_at=datetime(2026, 8, 5, 6, 17, 34, tzinfo=UTC),
    tiers=(
        DailyFive39PrizeTier(DailyFive39PrizeTierId.FIRST, 1, "頭獎", 5, 8_000_000),
        DailyFive39PrizeTier(DailyFive39PrizeTierId.SECOND, 2, "貳獎", 4, 20_000),
        DailyFive39PrizeTier(DailyFive39PrizeTierId.THIRD, 3, "參獎", 3, 300),
        DailyFive39PrizeTier(DailyFive39PrizeTierId.FOURTH, 4, "肆獎", 2, 50),
    ),
)
DAILY_FIVE39_PRIZE_RULE_CONTRACT.validate()


@dataclass(frozen=True, slots=True)
class PrizeEvaluationResult:
    """One deterministic prize-evaluation outcome for a single ticket vs. one draw."""

    lottery_type: LotteryType
    is_winner: bool
    prize_tier: str | None
    prize_tier_order: int | None
    zone1_hits: int
    zone2_hit: bool
    prize_rule_version: str
    prize_rule_provenance: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "is_winner": self.is_winner,
            "lottery_type": self.lottery_type.value,
            "prize_rule_provenance": self.prize_rule_provenance,
            "prize_rule_version": self.prize_rule_version,
            "prize_tier": self.prize_tier,
            "prize_tier_order": self.prize_tier_order,
            "zone1_hits": self.zone1_hits,
            "zone2_hit": self.zone2_hit,
        }


def _validate_zone1_numbers(label: str, numbers: tuple[int, ...]) -> None:
    if type(numbers) is not tuple:
        raise ValueError(f"{label} must be a tuple")
    if len(numbers) != 6:
        raise ValueError(f"{label} must contain exactly 6 numbers")
    if any(type(number) is not int for number in numbers):
        raise ValueError(f"{label} must contain exact built-in integers")
    if any(not 1 <= number <= 38 for number in numbers):
        raise ValueError(f"{label} contains an out-of-range number")
    if len(set(numbers)) != len(numbers):
        raise ValueError(f"{label} must not contain duplicates")
    if numbers != tuple(sorted(numbers)):
        raise ValueError(f"{label} must use canonical ascending order")


def _validate_zone2_number(label: str, number: int) -> None:
    if type(number) is not int:
        raise ValueError(f"{label} must be an exact built-in integer")
    if not 1 <= number <= 8:
        raise ValueError(f"{label} is out of range")


def _validate_daily539_numbers(label: str, numbers: tuple[int, ...]) -> None:
    if type(numbers) is not tuple:
        raise ValueError(f"{label} must be a tuple")
    if len(numbers) != 5:
        raise ValueError(f"{label} must contain exactly 5 numbers")
    if any(type(number) is not int for number in numbers):
        raise ValueError(f"{label} must contain exact built-in integers")
    if any(not 1 <= number <= 39 for number in numbers):
        raise ValueError(f"{label} contains an out-of-range number")
    if len(set(numbers)) != len(numbers):
        raise ValueError(f"{label} must not contain duplicates")
    if numbers != tuple(sorted(numbers)):
        raise ValueError(f"{label} must use canonical ascending order")


def evaluate_big_lotto_ticket(
    *,
    predicted_main_numbers: tuple[int, ...],
    predicted_special_number: int | None,
    winning_main_numbers: tuple[int, ...],
    winning_special_number: int | None,
) -> PrizeEvaluationResult:
    """Score one canonical BIG_LOTTO ticket using the committed rule contract.

    BIG_LOTTO tickets contain six main numbers; the draw's special number is
    compared with the ticket's main-number set and is not a second ticket zone.
    """

    if predicted_special_number is not None:
        raise ValueError("BIG_LOTTO tickets must not carry a predicted special number")
    if winning_special_number is None:
        raise ValueError("BIG_LOTTO evaluation requires a winning special number")

    score = score_big_lotto_ticket(
        predicted_main_numbers=predicted_main_numbers,
        winning_main_numbers=winning_main_numbers,
        winning_special_number=winning_special_number,
    )
    tier = resolve_big_lotto_prize_tier(score.main_hits, score.special_hit)
    prize_rule = BIG_LOTTO_RULE_CONTRACT.prize_rule
    assert prize_rule is not None
    return PrizeEvaluationResult(
        lottery_type=LotteryType.BIG_LOTTO,
        is_winner=isinstance(tier, BigLottoPrizeTier),
        prize_tier=tier.tier_id.value if isinstance(tier, BigLottoPrizeTier) else None,
        prize_tier_order=None,
        zone1_hits=score.main_hits,
        zone2_hit=score.special_hit,
        prize_rule_version=prize_rule.schema_version,
        prize_rule_provenance=f"{prize_rule.source_locator} (sha256={prize_rule.source_sha256})",
    )


def evaluate_power_lotto_ticket(
    *,
    predicted_main_numbers: tuple[int, ...],
    predicted_special_number: int,
    winning_main_numbers: tuple[int, ...],
    winning_special_number: int,
    prize_rule: PowerLottoPrizeRuleContract = POWER_LOTTO_PRIZE_RULE_CONTRACT,
) -> PrizeEvaluationResult:
    """Score one canonical POWER_LOTTO ticket against the official prize table.

    POWER_LOTTO permits overlap between a ticket's first-zone (1-38) and
    second-zone (1-8) numbers, unlike BIG_LOTTO, so no overlap check applies.
    """

    _validate_zone1_numbers("predicted_main_numbers", predicted_main_numbers)
    _validate_zone1_numbers("winning_main_numbers", winning_main_numbers)
    _validate_zone2_number("predicted_special_number", predicted_special_number)
    _validate_zone2_number("winning_special_number", winning_special_number)
    if type(prize_rule) is not PowerLottoPrizeRuleContract:
        raise ValueError("prize_rule must be a PowerLottoPrizeRuleContract")

    zone1_hits = len(set(predicted_main_numbers) & set(winning_main_numbers))
    zone2_hit = predicted_special_number == winning_special_number
    tier = prize_rule.resolve(zone1_hits=zone1_hits, zone2_hit=zone2_hit)
    return PrizeEvaluationResult(
        lottery_type=LotteryType.POWER_LOTTO,
        is_winner=tier is not None,
        prize_tier=tier.tier_id.value if tier is not None else None,
        prize_tier_order=tier.tier_order if tier is not None else None,
        zone1_hits=zone1_hits,
        zone2_hit=zone2_hit,
        prize_rule_version=prize_rule.schema_version,
        prize_rule_provenance=f"{prize_rule.source_locator} (sha256={prize_rule.source_sha256})",
    )


def evaluate_daily_539_ticket(
    *,
    predicted_main_numbers: tuple[int, ...],
    winning_main_numbers: tuple[int, ...],
    prize_rule: DailyFive39PrizeRuleContract = DAILY_FIVE39_PRIZE_RULE_CONTRACT,
) -> PrizeEvaluationResult:
    """Score one canonical DAILY_539 ticket against the official prize table.

    DAILY_539 draws a single 5-of-39 set with no second zone, so the shared
    ``PrizeEvaluationResult.zone2_hit`` field is always ``False`` here: it is
    not a "no match" signal, it simply does not apply to this lottery type.
    """

    _validate_daily539_numbers("predicted_main_numbers", predicted_main_numbers)
    _validate_daily539_numbers("winning_main_numbers", winning_main_numbers)
    if type(prize_rule) is not DailyFive39PrizeRuleContract:
        raise ValueError("prize_rule must be a DailyFive39PrizeRuleContract")

    match_count = len(set(predicted_main_numbers) & set(winning_main_numbers))
    tier = prize_rule.resolve(match_count=match_count)
    return PrizeEvaluationResult(
        lottery_type=LotteryType.DAILY_539,
        is_winner=tier is not None,
        prize_tier=tier.tier_id.value if tier is not None else None,
        prize_tier_order=tier.tier_order if tier is not None else None,
        zone1_hits=match_count,
        zone2_hit=False,
        prize_rule_version=prize_rule.schema_version,
        prize_rule_provenance=f"{prize_rule.source_locator} (sha256={prize_rule.source_sha256})",
    )


def evaluate_lottery_prize(
    *,
    lottery_type: LotteryType,
    predicted_main_numbers: tuple[int, ...],
    predicted_special_number: int | None,
    winning_main_numbers: tuple[int, ...],
    winning_special_number: int | None,
) -> PrizeEvaluationResult:
    """Dispatch to the lottery-specific evaluator; there is no universal hit threshold."""

    if lottery_type is LotteryType.BIG_LOTTO:
        return evaluate_big_lotto_ticket(
            predicted_main_numbers=predicted_main_numbers,
            predicted_special_number=predicted_special_number,
            winning_main_numbers=winning_main_numbers,
            winning_special_number=winning_special_number,
        )
    if lottery_type is LotteryType.POWER_LOTTO:
        if predicted_special_number is None or winning_special_number is None:
            raise ValueError("POWER_LOTTO evaluation requires a second-zone number")
        return evaluate_power_lotto_ticket(
            predicted_main_numbers=predicted_main_numbers,
            predicted_special_number=predicted_special_number,
            winning_main_numbers=winning_main_numbers,
            winning_special_number=winning_special_number,
        )
    if lottery_type is LotteryType.DAILY_539:
        return evaluate_daily_539_ticket(
            predicted_main_numbers=predicted_main_numbers,
            winning_main_numbers=winning_main_numbers,
        )
    raise NotImplementedError(f"no prize evaluator is implemented for {lottery_type.value}")


@dataclass(frozen=True, slots=True)
class DispatchingLotteryPrizeEvaluator:
    """Default ``LotteryPrizeEvaluator`` port implementation: routes by lottery type."""

    def evaluate(
        self,
        *,
        lottery_type: LotteryType,
        predicted_main_numbers: tuple[int, ...],
        predicted_special_number: int | None,
        winning_main_numbers: tuple[int, ...],
        winning_special_number: int | None,
    ) -> PrizeEvaluationResult:
        return evaluate_lottery_prize(
            lottery_type=lottery_type,
            predicted_main_numbers=predicted_main_numbers,
            predicted_special_number=predicted_special_number,
            winning_main_numbers=winning_main_numbers,
            winning_special_number=winning_special_number,
        )


LOTTERY_PRIZE_EVALUATOR = DispatchingLotteryPrizeEvaluator()
