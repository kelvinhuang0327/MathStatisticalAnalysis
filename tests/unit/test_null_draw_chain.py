from __future__ import annotations

import dataclasses
from datetime import date, timedelta

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT, LOTTERY_RULE_CONTRACTS
from lottolab.evidence import canonical_json
from lottolab.evidence.validator import recompute_self_hash
from lottolab.research.null_draw_chain import chain_canonical_bytes, generate_null_draw_chain

ALL_LOTTERY_TYPES = (LotteryType.BIG_LOTTO, LotteryType.DAILY_539, LotteryType.POWER_LOTTO)


def test_draw_count_must_be_positive() -> None:
    rule = LOTTERY_RULE_CONTRACTS[LotteryType.BIG_LOTTO]
    with pytest.raises(ValueError, match="draw_count must be positive"):
        generate_null_draw_chain(rule, draw_count=0, start_date=date(2026, 1, 1), seed=1)


@pytest.mark.parametrize("lottery_type", ALL_LOTTERY_TYPES)
def test_same_seed_produces_identical_chain(lottery_type: LotteryType) -> None:
    rule = LOTTERY_RULE_CONTRACTS[lottery_type]
    first = generate_null_draw_chain(rule, draw_count=50, start_date=date(2026, 1, 1), seed=7)
    second = generate_null_draw_chain(rule, draw_count=50, start_date=date(2026, 1, 1), seed=7)
    assert first.draws == second.draws
    assert first.chain_sha256 == second.chain_sha256
    assert chain_canonical_bytes(first) == chain_canonical_bytes(second)


@pytest.mark.parametrize("lottery_type", ALL_LOTTERY_TYPES)
def test_different_seed_produces_different_chain(lottery_type: LotteryType) -> None:
    rule = LOTTERY_RULE_CONTRACTS[lottery_type]
    first = generate_null_draw_chain(rule, draw_count=50, start_date=date(2026, 1, 1), seed=7)
    second = generate_null_draw_chain(rule, draw_count=50, start_date=date(2026, 1, 1), seed=8)
    assert first.draws != second.draws
    assert first.chain_sha256 != second.chain_sha256


def test_chain_sha256_matches_recomputed_canonical_bytes() -> None:
    rule = LOTTERY_RULE_CONTRACTS[LotteryType.POWER_LOTTO]
    chain = generate_null_draw_chain(rule, draw_count=5, start_date=date(2026, 1, 1), seed=3)
    recomputed = canonical_json.sha256_hex(chain_canonical_bytes(chain))
    assert recomputed == chain.chain_sha256


def test_chain_hash_changes_when_a_draw_is_mutated() -> None:
    rule = LOTTERY_RULE_CONTRACTS[LotteryType.BIG_LOTTO]
    chain = generate_null_draw_chain(rule, draw_count=10, start_date=date(2026, 1, 1), seed=42)

    original = chain.draws[0].main_numbers
    alternate = tuple(range(1, 7)) if original != tuple(range(1, 7)) else tuple(range(44, 50))
    tampered_first_draw = dataclasses.replace(chain.draws[0], main_numbers=alternate)
    tampered_chain = dataclasses.replace(chain, draws=(tampered_first_draw, *chain.draws[1:]))

    tampered_hash = canonical_json.sha256_hex(chain_canonical_bytes(tampered_chain))
    assert tampered_hash != chain.chain_sha256


def test_embedded_rule_parameters_hash_independently_verifies_via_evidence_validator() -> None:
    rule = LOTTERY_RULE_CONTRACTS[LotteryType.DAILY_539]
    chain = generate_null_draw_chain(rule, draw_count=5, start_date=date(2026, 1, 1), seed=1)
    recomputed = recompute_self_hash(chain.rule_parameters, excluded_key="rule_parameters_sha256")
    assert recomputed == chain.rule_parameters.rule_parameters_sha256


@pytest.mark.parametrize("lottery_type", ALL_LOTTERY_TYPES)
def test_every_draw_conforms_to_the_authoritative_rule_contract(lottery_type: LotteryType) -> None:
    rule = LOTTERY_RULE_CONTRACTS[lottery_type]
    chain = generate_null_draw_chain(rule, draw_count=200, start_date=date(2026, 1, 1), seed=11)

    for index, draw in enumerate(chain.draws):
        assert draw.draw_sequence == index
        assert draw.draw_date == date(2026, 1, 1) + timedelta(days=index)

        assert len(draw.main_numbers) == rule.main_number_count
        assert list(draw.main_numbers) == sorted(draw.main_numbers)
        assert all(rule.main_number_min <= n <= rule.main_number_max for n in draw.main_numbers)
        if rule.main_numbers_unique:
            assert len(set(draw.main_numbers)) == len(draw.main_numbers)

        assert len(draw.special_numbers) == rule.special_number_count
        assert list(draw.special_numbers) == sorted(draw.special_numbers)
        assert all(
            rule.special_number_min <= n <= rule.special_number_max for n in draw.special_numbers
        )
        if rule.special_numbers_unique:
            assert len(set(draw.special_numbers)) == len(draw.special_numbers)

        if not rule.main_special_overlap_allowed:
            assert not set(draw.main_numbers) & set(draw.special_numbers)


def test_daily_539_has_no_special_numbers() -> None:
    rule = LOTTERY_RULE_CONTRACTS[LotteryType.DAILY_539]
    chain = generate_null_draw_chain(rule, draw_count=20, start_date=date(2026, 1, 1), seed=5)
    assert all(draw.special_numbers == () for draw in chain.draws)


def test_wide_sampling_covers_most_of_the_big_lotto_number_space() -> None:
    """Coarse sanity check only, not a calibration test.

    Catches a broken generator that only draws from a narrow sub-range
    (e.g. a fixed slice, or an off-by-one in the pool bounds) without
    asserting anything about the shape of the distribution.
    """

    rule = LOTTERY_RULE_CONTRACTS[LotteryType.BIG_LOTTO]
    chain = generate_null_draw_chain(rule, draw_count=500, start_date=date(2026, 1, 1), seed=99)
    seen = {number for draw in chain.draws for number in draw.main_numbers}
    assert len(seen) >= 45  # of 49 possible values


def test_exhausted_pool_after_overlap_exclusion_fails_closed() -> None:
    """A rule shrunk so the disallowed-overlap special pool is provably empty.

    main_number_max=6 forces every draw to use all of {1..6} (capacity ==
    count, so there is no randomness in *which* numbers are used, only
    their draw order). With special_number_max also shrunk to 6 and
    overlap disallowed, the special pool is deterministically empty on
    every draw regardless of seed.
    """

    broken_rule = dataclasses.replace(
        BIG_LOTTO_RULE_CONTRACT, main_number_max=6, special_number_max=6
    )
    with pytest.raises(ValueError, match="not enough eligible numbers"):
        generate_null_draw_chain(broken_rule, draw_count=1, start_date=date(2026, 1, 1), seed=1)
