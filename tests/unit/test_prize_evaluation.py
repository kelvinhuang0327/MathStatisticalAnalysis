"""Golden contract tests for the official lottery prize-tier evaluators."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BigLottoPrizeTierId
from lottolab.domain.prize_evaluation import (
    DAILY_FIVE39_PRIZE_RULE_CONTRACT,
    LOTTERY_PRIZE_EVALUATOR,
    POWER_LOTTO_PRIZE_RULE_CONTRACT,
    DailyFive39PrizeTierId,
    DispatchingLotteryPrizeEvaluator,
    PowerLottoPrizeTierId,
    evaluate_daily_539_ticket,
    evaluate_lottery_prize,
    evaluate_power_lotto_ticket,
)

WINNING_MAIN = (1, 2, 3, 4, 5, 6)
WINNING_SPECIAL = 7

# Official tier -> (zone1_hits, zone2_hit) hit signature, from the live
# taiwanlottery.com super_lotto638.tableData bundle (see module docstring
# provenance on POWER_LOTTO_PRIZE_RULE_CONTRACT).
EXPECTED_WINNING_ROWS = {
    (6, True): (PowerLottoPrizeTierId.FIRST, "頭獎", 1, None),
    (6, False): (PowerLottoPrizeTierId.SECOND, "貳獎", 2, None),
    (5, True): (PowerLottoPrizeTierId.THIRD, "參獎", 3, 150_000),
    (5, False): (PowerLottoPrizeTierId.FOURTH, "肆獎", 4, 20_000),
    (4, True): (PowerLottoPrizeTierId.FIFTH, "伍獎", 5, 4_000),
    (4, False): (PowerLottoPrizeTierId.SIXTH, "陸獎", 6, 800),
    (3, True): (PowerLottoPrizeTierId.SEVENTH, "柒獎", 7, 400),
    (2, True): (PowerLottoPrizeTierId.EIGHTH, "捌獎", 8, 200),
    (3, False): (PowerLottoPrizeTierId.NINTH, "玖獎", 9, 100),
    (1, True): (PowerLottoPrizeTierId.GENERAL, "普獎", 10, 100),
}

# Adjacent signatures that are valid hit counts but do not appear in the
# official table at all -- must resolve to a clean non-winning result.
NON_WINNING_BOUNDARY_SIGNATURES = [
    (0, True),
    (0, False),
    (1, False),
    (2, False),
]


def _predicted_main(hit_count: int) -> tuple[int, ...]:
    """Build a canonical 6-number ticket with exactly ``hit_count`` winners."""

    hits = list(WINNING_MAIN[:hit_count])
    misses = [n for n in range(1, 39) if n not in WINNING_MAIN][: 6 - hit_count]
    return tuple(sorted(hits + misses))


class TestPowerLottoPrizeRuleContract:
    def test_ten_official_tiers_present_in_order(self) -> None:
        assert [t.tier_id for t in POWER_LOTTO_PRIZE_RULE_CONTRACT.tiers] == list(
            PowerLottoPrizeTierId
        )
        assert [t.tier_order for t in POWER_LOTTO_PRIZE_RULE_CONTRACT.tiers] == list(
            range(1, 11)
        )

    def test_matches_official_hit_signatures_and_labels(self) -> None:
        for tier in POWER_LOTTO_PRIZE_RULE_CONTRACT.tiers:
            signature = (tier.zone1_hits, tier.zone2_hit)
            expected_id, expected_label, expected_order, expected_amount = (
                EXPECTED_WINNING_ROWS[signature]
            )
            assert tier.tier_id is expected_id
            assert tier.official_label == expected_label
            assert tier.tier_order == expected_order
            assert tier.prize_amount == expected_amount

    def test_source_provenance_is_byte_exact_and_verifiable(self) -> None:
        contract = POWER_LOTTO_PRIZE_RULE_CONTRACT
        assert contract.source_sha256 == (
            "a7e3c41b13c6927f333a309725d870b6509bb13e9f71c5995f5ff3bd931f1836"
        )
        assert contract.source_url == "https://www.taiwanlottery.com/_nuxt/_game_.1_0_8_74.js"
        assert "super_lotto638.tableData" in contract.source_locator
        assert contract.source_accessed_at.tzinfo is not None

    def test_prize_tier_is_frozen(self) -> None:
        tier = POWER_LOTTO_PRIZE_RULE_CONTRACT.tiers[0]
        with pytest.raises(FrozenInstanceError):
            tier.tier_order = 99  # type: ignore[misc]

    def test_duplicate_hit_signature_rejected(self) -> None:
        tiers = list(POWER_LOTTO_PRIZE_RULE_CONTRACT.tiers)
        tiers[1] = replace(tiers[1], zone1_hits=tiers[0].zone1_hits, zone2_hit=tiers[0].zone2_hit)
        broken = replace(POWER_LOTTO_PRIZE_RULE_CONTRACT, tiers=tuple(tiers))
        with pytest.raises(ValueError, match="ambiguous hit signature"):
            broken.validate()

    def test_missing_tier_rejected(self) -> None:
        broken = replace(
            POWER_LOTTO_PRIZE_RULE_CONTRACT,
            tiers=POWER_LOTTO_PRIZE_RULE_CONTRACT.tiers[:-1],
        )
        with pytest.raises(ValueError, match="every tier identifier exactly once"):
            broken.validate()


class TestEvaluatePowerLottoTicket:
    @pytest.mark.parametrize(
        ("signature", "expected"), list(EXPECTED_WINNING_ROWS.items())
    )
    def test_every_official_tier_is_reachable(
        self,
        signature: tuple[int, bool],
        expected: tuple[PowerLottoPrizeTierId, str, int, int | None],
    ) -> None:
        zone1_hits, zone2_hit = signature
        expected_id, _label, expected_order, _amount = expected
        predicted_main = _predicted_main(zone1_hits)
        predicted_special = WINNING_SPECIAL if zone2_hit else _other_special(WINNING_SPECIAL)

        result = evaluate_power_lotto_ticket(
            predicted_main_numbers=predicted_main,
            predicted_special_number=predicted_special,
            winning_main_numbers=WINNING_MAIN,
            winning_special_number=WINNING_SPECIAL,
        )

        assert result.is_winner is True
        assert result.prize_tier == expected_id.value
        assert result.prize_tier_order == expected_order
        assert result.zone1_hits == zone1_hits
        assert result.zone2_hit is zone2_hit
        assert result.lottery_type is LotteryType.POWER_LOTTO
        assert result.prize_rule_version == POWER_LOTTO_PRIZE_RULE_CONTRACT.schema_version
        assert "sha256=a7e3c41b" in result.prize_rule_provenance

    @pytest.mark.parametrize("signature", NON_WINNING_BOUNDARY_SIGNATURES)
    def test_adjacent_boundary_signatures_do_not_win(
        self, signature: tuple[int, bool]
    ) -> None:
        zone1_hits, zone2_hit = signature
        predicted_main = _predicted_main(zone1_hits)
        predicted_special = WINNING_SPECIAL if zone2_hit else _other_special(WINNING_SPECIAL)

        result = evaluate_power_lotto_ticket(
            predicted_main_numbers=predicted_main,
            predicted_special_number=predicted_special,
            winning_main_numbers=WINNING_MAIN,
            winning_special_number=WINNING_SPECIAL,
        )

        assert result.is_winner is False
        assert result.prize_tier is None
        assert result.prize_tier_order is None
        assert result.zone1_hits == zone1_hits
        assert result.zone2_hit is zone2_hit

    def test_first_and_second_zone_matches_are_distinct_fields(self) -> None:
        result = evaluate_power_lotto_ticket(
            predicted_main_numbers=_predicted_main(4),
            predicted_special_number=_other_special(WINNING_SPECIAL),
            winning_main_numbers=WINNING_MAIN,
            winning_special_number=WINNING_SPECIAL,
        )
        assert result.zone1_hits == 4
        assert result.zone2_hit is False
        assert result.prize_tier == PowerLottoPrizeTierId.SIXTH.value

    def test_overlap_between_main_and_special_numbers_is_permitted(self) -> None:
        # POWER_LOTTO explicitly allows main/special overlap, unlike BIG_LOTTO.
        result = evaluate_power_lotto_ticket(
            predicted_main_numbers=(1, 2, 3, 4, 5, 7),
            predicted_special_number=7,
            winning_main_numbers=WINNING_MAIN,
            winning_special_number=WINNING_SPECIAL,
        )
        assert result.zone1_hits == 5
        assert result.zone2_hit is True

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"predicted_main_numbers": (1, 2, 3, 4, 5)}, "exactly 6 numbers"),
            ({"predicted_main_numbers": (0, 2, 3, 4, 5, 6)}, "out-of-range"),
            ({"predicted_main_numbers": (1, 1, 3, 4, 5, 6)}, "duplicates"),
            ({"predicted_main_numbers": (6, 5, 4, 3, 2, 1)}, "ascending order"),
            ({"predicted_special_number": 0}, "out of range"),
            ({"predicted_special_number": 9}, "out of range"),
        ],
    )
    def test_invalid_ticket_inputs_are_rejected(
        self, kwargs: dict[str, object], match: str
    ) -> None:
        base: dict[str, object] = {
            "predicted_main_numbers": (1, 2, 3, 4, 5, 6),
            "predicted_special_number": 7,
            "winning_main_numbers": WINNING_MAIN,
            "winning_special_number": WINNING_SPECIAL,
        }
        base.update(kwargs)
        with pytest.raises(ValueError, match=match):
            evaluate_power_lotto_ticket(**base)  # type: ignore[arg-type]


def _other_special(exclude: int) -> int:
    for candidate in range(1, 9):
        if candidate != exclude:
            return candidate
    raise AssertionError("no alternate special number available")


class TestLotteryPrizeEvaluatorDispatch:
    def test_dispatches_power_lotto_by_lottery_type(self) -> None:
        result = evaluate_lottery_prize(
            lottery_type=LotteryType.POWER_LOTTO,
            predicted_main_numbers=WINNING_MAIN,
            predicted_special_number=WINNING_SPECIAL,
            winning_main_numbers=WINNING_MAIN,
            winning_special_number=WINNING_SPECIAL,
        )
        assert result.is_winner is True
        assert result.prize_tier == PowerLottoPrizeTierId.FIRST.value

    def test_dispatches_big_lotto_by_lottery_type(self) -> None:
        result = evaluate_lottery_prize(
            lottery_type=LotteryType.BIG_LOTTO,
            predicted_main_numbers=WINNING_MAIN,
            predicted_special_number=None,
            winning_main_numbers=WINNING_MAIN,
            winning_special_number=WINNING_SPECIAL,
        )
        assert result.is_winner is True
        assert result.prize_tier == BigLottoPrizeTierId.FIRST.value

    def test_power_lotto_requires_second_zone_numbers(self) -> None:
        with pytest.raises(ValueError, match="second-zone"):
            evaluate_lottery_prize(
                lottery_type=LotteryType.POWER_LOTTO,
                predicted_main_numbers=WINNING_MAIN,
                predicted_special_number=None,
                winning_main_numbers=WINNING_MAIN,
                winning_special_number=WINNING_SPECIAL,
            )

    def test_default_port_singleton_matches_free_function(self) -> None:
        assert isinstance(LOTTERY_PRIZE_EVALUATOR, DispatchingLotteryPrizeEvaluator)
        via_port = LOTTERY_PRIZE_EVALUATOR.evaluate(
            lottery_type=LotteryType.POWER_LOTTO,
            predicted_main_numbers=WINNING_MAIN,
            predicted_special_number=WINNING_SPECIAL,
            winning_main_numbers=WINNING_MAIN,
            winning_special_number=WINNING_SPECIAL,
        )
        via_function = evaluate_lottery_prize(
            lottery_type=LotteryType.POWER_LOTTO,
            predicted_main_numbers=WINNING_MAIN,
            predicted_special_number=WINNING_SPECIAL,
            winning_main_numbers=WINNING_MAIN,
            winning_special_number=WINNING_SPECIAL,
        )
        assert via_port == via_function

    def test_dispatches_daily_539_by_lottery_type(self) -> None:
        result = evaluate_lottery_prize(
            lottery_type=LotteryType.DAILY_539,
            predicted_main_numbers=WINNING_539,
            predicted_special_number=None,
            winning_main_numbers=WINNING_539,
            winning_special_number=None,
        )
        assert result.is_winner is True
        assert result.prize_tier == DailyFive39PrizeTierId.FIRST.value


# ---------------------------------------------------------------------------
# DAILY_539 (今彩539): single 5-of-39 zone, no second zone.
# ---------------------------------------------------------------------------

WINNING_539 = (1, 2, 3, 4, 5)

# Official tier -> match_count, from the live taiwanlottery.com
# _game_.1_0_8_74.js bundle (see module docstring provenance on
# DAILY_FIVE39_PRIZE_RULE_CONTRACT).
EXPECTED_WINNING_ROWS_539 = {
    5: (DailyFive39PrizeTierId.FIRST, "頭獎", 1, 8_000_000),
    4: (DailyFive39PrizeTierId.SECOND, "貳獎", 2, 20_000),
    3: (DailyFive39PrizeTierId.THIRD, "參獎", 3, 300),
    2: (DailyFive39PrizeTierId.FOURTH, "肆獎", 4, 50),
}

# Adjacent match counts that are valid but do not appear in the official
# table at all -- must resolve to a clean non-winning result.
NON_WINNING_MATCH_COUNTS_539 = [0, 1]


def _predicted_539(hit_count: int) -> tuple[int, ...]:
    """Build a canonical 5-number DAILY_539 ticket with exactly ``hit_count`` winners."""

    hits = list(WINNING_539[:hit_count])
    misses = [n for n in range(1, 40) if n not in WINNING_539][: 5 - hit_count]
    return tuple(sorted(hits + misses))


class TestDailyFive39PrizeRuleContract:
    def test_four_official_tiers_present_in_order(self) -> None:
        assert [t.tier_id for t in DAILY_FIVE39_PRIZE_RULE_CONTRACT.tiers] == list(
            DailyFive39PrizeTierId
        )
        assert [t.tier_order for t in DAILY_FIVE39_PRIZE_RULE_CONTRACT.tiers] == list(
            range(1, 5)
        )

    def test_matches_official_hit_signatures_and_labels(self) -> None:
        for tier in DAILY_FIVE39_PRIZE_RULE_CONTRACT.tiers:
            expected_id, expected_label, expected_order, expected_amount = (
                EXPECTED_WINNING_ROWS_539[tier.match_count]
            )
            assert tier.tier_id is expected_id
            assert tier.official_label == expected_label
            assert tier.tier_order == expected_order
            assert tier.prize_amount == expected_amount

    def test_source_provenance_is_byte_exact_and_verifiable(self) -> None:
        contract = DAILY_FIVE39_PRIZE_RULE_CONTRACT
        assert contract.source_sha256 == (
            "a7e3c41b13c6927f333a309725d870b6509bb13e9f71c5995f5ff3bd931f1836"
        )
        assert contract.source_url == "https://www.taiwanlottery.com/_nuxt/_game_.1_0_8_74.js"
        assert "daily_cash" in contract.source_locator
        assert contract.source_accessed_at.tzinfo is not None

    def test_prize_tier_is_frozen(self) -> None:
        tier = DAILY_FIVE39_PRIZE_RULE_CONTRACT.tiers[0]
        with pytest.raises(FrozenInstanceError):
            tier.tier_order = 99  # type: ignore[misc]

    def test_duplicate_hit_signature_rejected(self) -> None:
        tiers = list(DAILY_FIVE39_PRIZE_RULE_CONTRACT.tiers)
        tiers[1] = replace(tiers[1], match_count=tiers[0].match_count)
        broken = replace(DAILY_FIVE39_PRIZE_RULE_CONTRACT, tiers=tuple(tiers))
        with pytest.raises(ValueError, match="ambiguous hit signature"):
            broken.validate()

    def test_missing_tier_rejected(self) -> None:
        broken = replace(
            DAILY_FIVE39_PRIZE_RULE_CONTRACT,
            tiers=DAILY_FIVE39_PRIZE_RULE_CONTRACT.tiers[:-1],
        )
        with pytest.raises(ValueError, match="every tier identifier exactly once"):
            broken.validate()


class TestEvaluateDailyFive39Ticket:
    @pytest.mark.parametrize(
        ("match_count", "expected"), list(EXPECTED_WINNING_ROWS_539.items())
    )
    def test_every_official_tier_is_reachable(
        self,
        match_count: int,
        expected: tuple[DailyFive39PrizeTierId, str, int, int],
    ) -> None:
        expected_id, _label, expected_order, _amount = expected
        predicted = _predicted_539(match_count)

        result = evaluate_daily_539_ticket(
            predicted_main_numbers=predicted,
            winning_main_numbers=WINNING_539,
        )

        assert result.is_winner is True
        assert result.prize_tier == expected_id.value
        assert result.prize_tier_order == expected_order
        assert result.zone1_hits == match_count
        assert result.zone2_hit is False
        assert result.lottery_type is LotteryType.DAILY_539
        assert result.prize_rule_version == DAILY_FIVE39_PRIZE_RULE_CONTRACT.schema_version
        assert "sha256=a7e3c41b" in result.prize_rule_provenance

    @pytest.mark.parametrize("match_count", NON_WINNING_MATCH_COUNTS_539)
    def test_adjacent_match_counts_do_not_win(self, match_count: int) -> None:
        predicted = _predicted_539(match_count)

        result = evaluate_daily_539_ticket(
            predicted_main_numbers=predicted,
            winning_main_numbers=WINNING_539,
        )

        assert result.is_winner is False
        assert result.prize_tier is None
        assert result.prize_tier_order is None
        assert result.zone1_hits == match_count

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"predicted_main_numbers": (1, 2, 3, 4)}, "exactly 5 numbers"),
            ({"predicted_main_numbers": (0, 2, 3, 4, 5)}, "out-of-range"),
            ({"predicted_main_numbers": (1, 1, 3, 4, 5)}, "duplicates"),
            ({"predicted_main_numbers": (5, 4, 3, 2, 1)}, "ascending order"),
        ],
    )
    def test_invalid_ticket_inputs_are_rejected(
        self, kwargs: dict[str, object], match: str
    ) -> None:
        base: dict[str, object] = {
            "predicted_main_numbers": (1, 2, 3, 4, 5),
            "winning_main_numbers": WINNING_539,
        }
        base.update(kwargs)
        with pytest.raises(ValueError, match=match):
            evaluate_daily_539_ticket(**base)  # type: ignore[arg-type]
