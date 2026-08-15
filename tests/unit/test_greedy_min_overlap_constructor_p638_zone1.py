from __future__ import annotations

import statistics
from itertools import combinations

import pytest

from lottolab.domain.lottery_rules import POWER_LOTTO_RULE_CONTRACT
from lottolab.research import greedy_min_overlap_constructor_p638_zone1 as p638_zone1_module
from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio


def test_pool_size_matches_power_lotto_zone1_rule_contract() -> None:
    assert POWER_LOTTO_RULE_CONTRACT.main_number_max == p638_zone1_module.POOL_SIZE


def test_draw_size_matches_power_lotto_zone1_rule_contract() -> None:
    assert POWER_LOTTO_RULE_CONTRACT.main_number_count == p638_zone1_module.DRAW_SIZE


def test_pool_and_draw_size_are_p638_zone1_native_not_a_sibling_lotterys() -> None:
    # Guards against a copy-paste from B649 (49, 6) or DAILY_539 (39, 5).
    assert (p638_zone1_module.POOL_SIZE, p638_zone1_module.DRAW_SIZE) == (38, 6)


def test_module_imports_the_real_shared_function_object() -> None:
    # Confirms this module calls the exact same, already-frozen B649
    # Phase-5 / T539 arm B function -- no local copy, no reimplementation,
    # nothing shadowed.
    assert p638_zone1_module.greedy_min_overlap_portfolio is greedy_min_overlap_portfolio


def test_wrapper_delegates_with_exactly_p638_zone1s_pool_and_draw_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Proves the wiring is exactly right WITHOUT ever invoking the real
    # constructor at (38, 6) -- real P638 Zone-1 scale -- anywhere in this
    # design task. See
    # docs/research/strategy-matrix-phase5-p638-non-sidon-low-overlap-native-design-r1.md
    # S2: constructor toolkit invocation at real P638 Zone-1 scale is out
    # of scope for this task, everywhere, in committed code or any script
    # run during the task.
    calls: list[tuple[int, int, int]] = []
    sentinel: tuple[tuple[int, ...], ...] = ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12))

    def stub(pool_size: int, draw_size: int, ticket_count: int) -> tuple[tuple[int, ...], ...]:
        calls.append((pool_size, draw_size, ticket_count))
        return sentinel

    monkeypatch.setattr(p638_zone1_module, "greedy_min_overlap_portfolio", stub)

    result = p638_zone1_module.greedy_min_overlap_portfolio_p638_zone1(ticket_count=7)

    assert calls == [(38, 6, 7)]
    assert result == sentinel


def test_wrapper_delegates_for_a_second_ticket_count_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, int, int]] = []

    def stub(pool_size: int, draw_size: int, ticket_count: int) -> tuple[tuple[int, ...], ...]:
        calls.append((pool_size, draw_size, ticket_count))
        return ()

    monkeypatch.setattr(p638_zone1_module, "greedy_min_overlap_portfolio", stub)

    p638_zone1_module.greedy_min_overlap_portfolio_p638_zone1(ticket_count=20)

    assert calls == [(38, 6, 20)]


def test_shared_constructor_generalizes_to_a_draw_size_six_toy_shape_matching_p638s_remainder() -> (
    None
):
    # Toy scale only (pool_size=20, far below P638 Zone-1's real 38) --
    # exercises the *shared*, already-frozen constructor at draw_size=6
    # for the first time (the committed suite only covers draw_size 2, 3,
    # and T539's own draw_size 5), strengthening -- not re-deciding -- the
    # "no B649/T539-specific tuning" claim the design doc's mapping (S5)
    # relies on. pool_size=20 is chosen so that pool_size % draw_size ==
    # 2, matching 38 % 6 == 2 exactly (P638 Zone-1's own remainder shape)
    # -- deliberately, not arbitrarily: the Sidon reference's own
    # even-modulus obstruction (`cyclic_sidon_shift_p638.py`) makes "does
    # P638 Zone-1's specific pool/draw shape misbehave" a live question
    # worth checking on this shared constructor too, not assumed clean by
    # analogy alone. Calls the shared function directly, not the P638
    # Zone-1 wrapper, since pool_size=20 is not P638 Zone-1's own pool
    # size.
    pool_size, draw_size = 20, 6
    disjoint_capacity = pool_size // draw_size  # 3, remainder 2 -- same remainder as 38 % 6
    ticket_count = disjoint_capacity + 1  # exactly one ticket beyond disjoint capacity

    portfolio = greedy_min_overlap_portfolio(
        pool_size=pool_size, draw_size=draw_size, ticket_count=ticket_count
    )

    assert len(portfolio) == ticket_count
    assert len(set(portfolio)) == ticket_count  # no duplicates
    for ticket in portfolio:
        assert len(ticket) == draw_size
        assert len(set(ticket)) == draw_size
        assert all(1 <= n <= pool_size for n in ticket)

    # The first `disjoint_capacity` tickets should be fully disjoint --
    # the general min-max-overlap rule finds them, not a special case.
    for i in range(disjoint_capacity):
        for j in range(i + 1, disjoint_capacity):
            assert len(set(portfolio[i]) & set(portfolio[j])) == 0

    # The one ticket beyond disjoint capacity is forced to reuse numbers:
    # only `pool_size - disjoint_capacity * draw_size` = 2 fresh numbers
    # remain, so it must reuse `draw_size - 2` = 4 numbers spread across
    # the `disjoint_capacity` = 3 prior tickets. Unlike T539/B649's own
    # toy check (pool=10, draw=3, remainder 1 -- only 1 number needs
    # reuse there, spreadable at <=1 per prior ticket), P638 Zone-1's own
    # remainder of 2 forces 4 reused numbers across only 3 prior tickets,
    # so by pigeonhole the best *achievable* max-overlap-against-any-
    # single-prior-ticket is ceil(4/3) = 2, not 1 -- a real, disclosed
    # difference in degree from the existing toy tests' own numbers, not
    # a defect in this shared constructor or a special case for P638.
    reused_needed = draw_size - (pool_size - disjoint_capacity * draw_size)
    expected_min_max_overlap = -(-reused_needed // disjoint_capacity)  # ceil division
    max_overlap = max(
        len(set(portfolio[disjoint_capacity]) & set(portfolio[j])) for j in range(disjoint_capacity)
    )
    assert max_overlap == expected_min_max_overlap


def test_geometry_metrics_are_computable_on_a_toy_p638_zone1_shaped_portfolio() -> None:
    # Confirms the six frozen geometry-metric definitions (design doc S7,
    # reused verbatim from the Owner packet's own GEOMETRY METRICS list)
    # are well-defined and computable against a toy portfolio of this
    # constructor's own output shape -- not a claim about real P638
    # Zone-1 geometry, which this task never builds at (38, 6).
    pool_size, draw_size, ticket_count = 20, 6, 5
    portfolio = greedy_min_overlap_portfolio(
        pool_size=pool_size, draw_size=draw_size, ticket_count=ticket_count
    )

    pairs = list(combinations(portfolio, 2))
    overlaps = [len(set(a) & set(b)) for a, b in pairs]
    max_pairwise_overlap = max(overlaps)
    mean_pairwise_overlap = sum(overlaps) / len(overlaps)
    overlap_profile: dict[int, int] = {}
    for overlap in overlaps:
        overlap_profile[overlap] = overlap_profile.get(overlap, 0) + 1

    number_use_counts = dict.fromkeys(range(1, pool_size + 1), 0)
    for ticket in portfolio:
        for number in ticket:
            number_use_counts[number] += 1
    unique_number_coverage = sum(1 for count in number_use_counts.values() if count >= 1)
    reuse_dispersion = statistics.pstdev(number_use_counts.values())
    duplicate_tickets = ticket_count - len(set(portfolio))

    assert max_pairwise_overlap <= draw_size
    assert sum(overlap_profile.values()) == len(pairs)
    assert unique_number_coverage <= pool_size
    assert reuse_dispersion >= 0
    assert duplicate_tickets == 0  # frozen invariant
    assert 0 <= mean_pairwise_overlap <= max_pairwise_overlap
