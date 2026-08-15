from __future__ import annotations

import pytest

from lottolab.domain.lottery_rules import DAILY_539_RULE_CONTRACT
from lottolab.research import greedy_min_overlap_constructor_t539 as t539_module
from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio


def test_pool_size_matches_daily_539_rule_contract() -> None:
    assert DAILY_539_RULE_CONTRACT.main_number_max == t539_module.POOL_SIZE


def test_draw_size_matches_daily_539_rule_contract() -> None:
    assert DAILY_539_RULE_CONTRACT.main_number_count == t539_module.DRAW_SIZE


def test_pool_and_draw_size_are_t539_native_not_a_sibling_lotterys() -> None:
    # Guards against a copy-paste from B649 (49, 6) or POWER_LOTTO (38, 6).
    assert (t539_module.POOL_SIZE, t539_module.DRAW_SIZE) == (39, 5)


def test_module_imports_the_real_shared_function_object() -> None:
    # Confirms this module calls the exact same, already-frozen B649
    # Phase-5 arm B function -- no local copy, no reimplementation,
    # nothing shadowed.
    assert t539_module.greedy_min_overlap_portfolio is greedy_min_overlap_portfolio


def test_wrapper_delegates_with_exactly_t539s_pool_and_draw_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Proves the wiring is exactly right WITHOUT ever invoking the real
    # constructor at (39, 5) -- real T539 scale -- anywhere in this
    # design task. See
    # docs/research/strategy-matrix-phase5-t539-non-sidon-low-overlap-native-design-r1.md
    # S2: constructor toolkit invocation at real T539 scale is out of
    # scope for this task, everywhere, in committed code or any script
    # run during the task.
    calls: list[tuple[int, int, int]] = []
    sentinel: tuple[tuple[int, ...], ...] = ((1, 2, 3, 4, 5), (6, 7, 8, 9, 10))

    def stub(pool_size: int, draw_size: int, ticket_count: int) -> tuple[tuple[int, ...], ...]:
        calls.append((pool_size, draw_size, ticket_count))
        return sentinel

    monkeypatch.setattr(t539_module, "greedy_min_overlap_portfolio", stub)

    result = t539_module.greedy_min_overlap_portfolio_t539(ticket_count=7)

    assert calls == [(39, 5, 7)]
    assert result == sentinel


def test_wrapper_delegates_for_a_second_ticket_count_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, int, int]] = []

    def stub(pool_size: int, draw_size: int, ticket_count: int) -> tuple[tuple[int, ...], ...]:
        calls.append((pool_size, draw_size, ticket_count))
        return ()

    monkeypatch.setattr(t539_module, "greedy_min_overlap_portfolio", stub)

    t539_module.greedy_min_overlap_portfolio_t539(ticket_count=20)

    assert calls == [(39, 5, 20)]


def test_shared_constructor_generalizes_to_a_draw_size_five_toy_shape() -> None:
    # Toy scale only (pool_size=15, far below T539's real 39) -- exercises
    # the *shared*, already-frozen constructor at draw_size=5 for the
    # first time (the committed B649 suite only covers draw_size 2 and
    # 3), strengthening -- not re-deciding -- the "no B649-specific
    # tuning" claim the design doc's mapping (S5) relies on. Calls the
    # shared function directly, not the T539 wrapper, since pool_size=15
    # is not T539's own pool size.
    portfolio = greedy_min_overlap_portfolio(pool_size=15, draw_size=5, ticket_count=6)

    assert len(portfolio) == 6
    assert len(set(portfolio)) == 6
    for ticket in portfolio:
        assert len(ticket) == 5
        assert len(set(ticket)) == 5
        assert all(1 <= n <= 15 for n in ticket)

    # 15 // 5 = 3 fully disjoint blocks fit before any candidate is
    # forced to reuse a number.
    for i in range(3):
        for j in range(i + 1, 3):
            assert len(set(portfolio[i]) & set(portfolio[j])) == 0
    assert portfolio[:3] == ((1, 2, 3, 4, 5), (6, 7, 8, 9, 10), (11, 12, 13, 14, 15))
