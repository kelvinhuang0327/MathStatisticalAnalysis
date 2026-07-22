"""Frozen-donor zone geometry and fail-closed tests for the live Zone Split core port.

P605C ports only ``lottery_api/models/zone_split.py`` (donor commit
520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f) as an internal, unregistered,
non-executable compatibility component. It must never be confused with the
deterministic, catalog-registered ``biglotto_zone_split_3bet_bet1`` strategy.
"""

from __future__ import annotations

import inspect
import random
from collections.abc import Sequence

import pytest

from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.strategies.live.biglotto_zone_split import (
    LiveZoneSplitResult,
    MalformedSamplerOutput,
    Sampler,
    generate_live_zone_split_bets,
)

_MIN = BIG_LOTTO_RULE_CONTRACT.main_number_min
_MAX = BIG_LOTTO_RULE_CONTRACT.main_number_max
_PICK = BIG_LOTTO_RULE_CONTRACT.main_number_count


def _recording_sampler(calls: list[tuple[int, ...]]) -> Sampler:
    def sampler(population: Sequence[int], k: int) -> list[int]:
        calls.append(tuple(population))
        return sorted(population)[:k]

    return sampler


def _first_k(population: Sequence[int], k: int) -> list[int]:
    return sorted(population)[:k]


def _last_k(population: Sequence[int], k: int) -> list[int]:
    return sorted(population)[-k:]


class TestFrozenDonorZoneGeometry:
    """Proof point 1: frozen donor zone boundaries and ±2 overlap for BIG_LOTTO."""

    def test_three_bet_zone_pools_match_donor_arithmetic(self) -> None:
        calls: list[tuple[int, ...]] = []
        generate_live_zone_split_bets(3, sampler=_recording_sampler(calls))
        # full_range=49, zone_size=49//3=16; overlap=2 on each side, clamped to [1,49].
        assert calls[0] == tuple(range(1, 19))  # zone [1,16] -> pool [1,18]
        assert calls[1] == tuple(range(15, 35))  # zone [17,32] -> pool [15,34]
        assert calls[2] == tuple(range(31, 50))  # last zone [33,49] -> pool [31,49]

    def test_ten_bet_zone_pools_match_donor_arithmetic(self) -> None:
        calls: list[tuple[int, ...]] = []
        generate_live_zone_split_bets(10, sampler=_recording_sampler(calls))
        # full_range=49, zone_size=49//10=4.
        assert calls[0] == tuple(range(1, 7))  # zone [1,4] -> pool [1,6]
        assert calls[1] == tuple(range(3, 11))  # zone [5,8] -> pool [3,10]
        assert calls[8] == tuple(range(31, 39))  # zone [33,36] -> pool [31,38]


class TestLastZoneRemainder:
    """Proof point 2: last-zone remainder handling."""

    def test_last_zone_absorbs_remainder_for_ten_bets(self) -> None:
        calls: list[tuple[int, ...]] = []
        generate_live_zone_split_bets(10, sampler=_recording_sampler(calls))
        # Pre-remainder arithmetic would end zone 9 at 1+10*4-1=40; the donor
        # overrides this to max_num=49 for the final zone.
        assert calls[9] == tuple(range(35, 50))
        assert max(calls[9]) == _MAX

    def test_last_zone_absorbs_remainder_for_three_bets(self) -> None:
        calls: list[tuple[int, ...]] = []
        generate_live_zone_split_bets(3, sampler=_recording_sampler(calls))
        assert max(calls[2]) == _MAX


class TestBetCounts:
    """Proof point 3: exactly num_bets outputs for 1, 3, and 10."""

    @pytest.mark.parametrize("num_bets", [1, 3, 10])
    def test_exactly_num_bets_outputs(self, num_bets: int) -> None:
        result = generate_live_zone_split_bets(num_bets, sampler=random.Random(1).sample)
        assert len(result.bets) == num_bets


class TestSixUniqueInRangeNumbers:
    """Proof point 4: six unique in-range integers per bet."""

    @pytest.mark.parametrize("num_bets", [1, 3, 10])
    def test_each_bet_has_six_unique_in_range_numbers(self, num_bets: int) -> None:
        result = generate_live_zone_split_bets(num_bets, sampler=random.Random(7).sample)
        for bet in result.bets:
            assert len(bet) == _PICK
            assert len(set(bet)) == _PICK
            assert all(_MIN <= number <= _MAX for number in bet)


class TestDeterministicInjection:
    """Proof point 5: injected deterministic sampler produces exact expected bets."""

    def test_injected_sampler_produces_exact_expected_bets(self) -> None:
        result = generate_live_zone_split_bets(3, sampler=_first_k)
        assert result.bets == (
            (1, 2, 3, 4, 5, 6),
            (15, 16, 17, 18, 19, 20),
            (31, 32, 33, 34, 35, 36),
        )

    def test_injected_rng_produces_exact_expected_bets(self) -> None:
        result_a = generate_live_zone_split_bets(3, sampler=random.Random(42))
        result_b = generate_live_zone_split_bets(3, sampler=random.Random(42))
        assert result_a.bets == result_b.bets


class TestDifferentSamplersDifferentBets:
    """Proof point 6: different injected deterministic samplers can diverge."""

    def test_different_samplers_produce_different_valid_bets(self) -> None:
        result_first = generate_live_zone_split_bets(3, sampler=_first_k)
        result_last = generate_live_zone_split_bets(3, sampler=_last_k)
        assert result_first.bets != result_last.bets


class TestProductionRandomnessIsolation:
    """Proof point 7: production default does not mutate process-global random state."""

    def test_production_default_does_not_mutate_global_random_state(self) -> None:
        before = random.getstate()
        generate_live_zone_split_bets(3)
        after = random.getstate()
        assert before == after

    def test_production_default_is_nondeterministic_across_calls(self) -> None:
        distinct_results = {generate_live_zone_split_bets(3).bets for _ in range(8)}
        assert len(distinct_results) > 1


class TestNoHistoryParameter:
    """Proof point 8: no history parameter exists or influences output."""

    def test_signature_has_no_history_parameter(self) -> None:
        signature = inspect.signature(generate_live_zone_split_bets)
        assert "history" not in signature.parameters
        assert set(signature.parameters) == {"num_bets", "sampler"}


class TestInvalidNumBetsFailClosed:
    """Proof point 9: invalid num_bets values fail closed."""

    @pytest.mark.parametrize(
        ("invalid_value", "expected_exception"),
        [
            (0, ValueError),
            (11, ValueError),
            (-1, ValueError),
            (True, TypeError),
            (False, TypeError),
            (3.0, TypeError),
            ("3", TypeError),
        ],
    )
    def test_invalid_num_bets_raises(
        self, invalid_value: object, expected_exception: type[Exception]
    ) -> None:
        with pytest.raises(expected_exception):
            generate_live_zone_split_bets(invalid_value)  # type: ignore[arg-type]


def _malformed_too_few(population: Sequence[int], k: int) -> list[int]:
    return list(population)[: k - 1]


def _malformed_duplicates(population: Sequence[int], k: int) -> list[int]:
    return [population[0]] * k


def _malformed_below_range(population: Sequence[int], k: int) -> list[int]:
    return [0, 1, 2, 3, 4, 5]


def _malformed_above_range(population: Sequence[int], k: int) -> list[int]:
    return [50, 1, 2, 3, 4, 5]


def _malformed_wrong_element_type(population: Sequence[int], k: int) -> list[str]:
    return ["a", "b", "c", "d", "e", "f"]


def _malformed_wrong_container_type(population: Sequence[int], k: int) -> str:
    return "123456"


def _malformed_wrong_zone(population: Sequence[int], k: int) -> list[int]:
    # Globally valid BIG_LOTTO numbers (unique, six of them, within [1, 49]),
    # but always drawn from the last zone's pool regardless of which zone's
    # population was actually supplied to this call.
    return [44, 45, 46, 47, 48, 49]


class TestMalformedSamplerOutputFailsClosed:
    """Proof point 10: malformed sampler output fails closed."""

    @pytest.mark.parametrize(
        "sampler",
        [
            _malformed_too_few,
            _malformed_duplicates,
            _malformed_below_range,
            _malformed_above_range,
            _malformed_wrong_element_type,
            _malformed_wrong_container_type,
            _malformed_wrong_zone,
        ],
    )
    def test_malformed_output_raises(self, sampler: object) -> None:
        with pytest.raises(MalformedSamplerOutput):
            generate_live_zone_split_bets(3, sampler=sampler)  # type: ignore[arg-type]


class TestZonePopulationMembershipFailsClosed:
    """Proof point 11: globally valid numbers from the wrong zone fail closed.

    ``[44, 45, 46, 47, 48, 49]`` are six unique, in-range (1-49) BIG_LOTTO
    numbers, so they pass every prior check (container, length, type,
    uniqueness, global range). They are members of the *last* zone's pool
    (``[31, 49]`` per ``TestLastZoneRemainder``), not the *first* zone's pool
    (``[1, 18]`` per ``TestFrozenDonorZoneGeometry``). A sampler that ignores
    the population it is given and always returns these values must still be
    rejected when called for the first zone.
    """

    def test_globally_valid_wrong_zone_numbers_raise(self) -> None:
        with pytest.raises(MalformedSamplerOutput, match="zone population"):
            generate_live_zone_split_bets(3, sampler=_malformed_wrong_zone)

    def test_same_numbers_are_individually_valid_big_lotto_numbers(self) -> None:
        # Isolates the cause: this is not a range/type/count/duplicate failure.
        values = (44, 45, 46, 47, 48, 49)
        assert len(values) == _PICK
        assert len(set(values)) == _PICK
        assert all(_MIN <= number <= _MAX for number in values)

    def test_same_numbers_are_accepted_when_they_are_the_correct_zone(self) -> None:
        # Confirms the rejection above is about zone membership, not the
        # specific numeric values: the identical sampler output is accepted
        # when it is actually drawn from the zone it corresponds to.
        result = generate_live_zone_split_bets(3, sampler=_last_k)
        assert result.bets[2] == (44, 45, 46, 47, 48, 49)


class TestDistinctFromDeterministicStrategy:
    """The port must not be represented as biglotto_zone_split_3bet_bet1."""

    def test_method_identifier_differs_from_deterministic_strategy_id(self) -> None:
        result = generate_live_zone_split_bets(3, sampler=random.Random(1).sample)
        assert result.method != "biglotto_zone_split_3bet_bet1"
        assert result.method == "biglotto_live_zone_split_core_port"


class TestResultShapeAndCoverageMetadata:
    def test_result_is_frozen(self) -> None:
        result = generate_live_zone_split_bets(3, sampler=random.Random(1).sample)
        assert isinstance(result, LiveZoneSplitResult)
        with pytest.raises(AttributeError):
            result.bets = ()  # type: ignore[misc]

    def test_coverage_metadata_matches_bets(self) -> None:
        result = generate_live_zone_split_bets(3, sampler=random.Random(1).sample)
        all_numbers = {number for bet in result.bets for number in bet}
        assert result.total_unique_numbers == len(all_numbers)
        assert result.coverage_rate == round(len(all_numbers) / (_MAX - _MIN + 1), 4)
