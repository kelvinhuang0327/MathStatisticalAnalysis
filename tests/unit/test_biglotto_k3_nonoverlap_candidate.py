from __future__ import annotations

import ast
from datetime import date, timedelta
from fractions import Fraction
from itertools import product
from math import comb, prod
from pathlib import Path
from types import ModuleType

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, InvalidOutput
from lottolab.strategies.adapters.biglotto_k3_nonoverlap_candidate import (
    BigLottoK3NonoverlapEcpCandidateAdapter,
    BigLottoK3NonoverlapOptimizerCandidateAdapter,
    make_k3_nonoverlap,
)
from lottolab.strategies.adapters.biglotto_wave4 import BigLottoThreeBetOptimizerAdapter
from lottolab.strategies.adapters.biglotto_wave14 import BigLottoTestEcpAdapter

_RULE_O_K3 = Fraction(32528, 582659)
_RULE_N_K3 = Fraction(330422, 3579191)


def _legal_k3(tickets: tuple[tuple[int, ...], ...]) -> bool:
    return (
        len(tickets) == 3
        and all(
            len(ticket) == 6
            and all(type(number) is int and 1 <= number <= 49 for number in ticket)
            and len(set(ticket)) == 6
            for ticket in tickets
        )
        and all(
            set(tickets[left]).isdisjoint(tickets[right])
            for left in range(3)
            for right in range(left + 1, 3)
        )
        and len({number for ticket in tickets for number in ticket}) == 18
    )


def _history(count: int = 64) -> tuple[CausalDrawRow, ...]:
    start = date(2025, 1, 1)
    rows: list[CausalDrawRow] = []
    for index in range(count):
        numbers = tuple(sorted(((index * 11 + offset * 7) % 49) + 1 for offset in range(6)))
        rows.append(
            CausalDrawRow(
                draw=str(index + 1),
                date=(start + timedelta(days=index)).isoformat(),
                numbers=numbers,
            )
        )
    return tuple(rows)


def _fair_probability(tickets: tuple[set[int], ...], *, include_two_plus_special: bool) -> Fraction:
    """Count fair Big Lotto outcomes exactly from ticket-membership regions.

    Rule O awards on at least three main hits. Rule N also awards on exactly
    two main hits plus a special-number hit. The special ball has 43 possible
    values after six main numbers are drawn.
    """

    membership_sizes: dict[int, int] = {}
    union = {number for ticket in tickets for number in ticket}
    for number in union:
        membership = sum(1 << index for index, ticket in enumerate(tickets) if number in ticket)
        membership_sizes[membership] = membership_sizes.get(membership, 0) + 1

    regions = tuple(membership_sizes.items())
    outside_size = 49 - len(union)
    winning_outcomes = 0
    for selected_counts in product(*(range(size + 1) for _mask, size in regions)):
        selected_total = sum(selected_counts)
        outside_selected = 6 - selected_total
        if outside_selected < 0 or outside_selected > outside_size:
            continue
        main_ways = prod(
            comb(size, selected)
            for (_mask, size), selected in zip(regions, selected_counts, strict=True)
        ) * comb(outside_size, outside_selected)
        hits = tuple(
            sum(
                selected
                for (membership, _size), selected in zip(regions, selected_counts, strict=True)
                if membership & (1 << ticket_index)
            )
            for ticket_index in range(len(tickets))
        )
        if any(hit >= 3 for hit in hits):
            winning_outcomes += main_ways * 43
        elif include_two_plus_special:
            qualifying_tickets = sum(1 << index for index, hit in enumerate(hits) if hit == 2)
            eligible_specials = sum(
                size - selected
                for (membership, size), selected in zip(regions, selected_counts, strict=True)
                if membership & qualifying_tickets
            )
            winning_outcomes += main_ways * eligible_specials

    return Fraction(winning_outcomes, comb(49, 6) * 43)


def _venn_geometry_tickets(
    regions: tuple[int, int, int, int, int, int, int],
) -> tuple[set[int], set[int], set[int]]:
    region_sets: list[set[int]] = []
    next_number = 1
    for size in regions:
        region_sets.append(set(range(next_number, next_number + size)))
        next_number += size
    a, b, c, ab, ac, bc, abc = region_sets
    tickets = (a | ab | ac | abc, b | ab | bc | abc, c | ac | bc | abc)
    assert tuple(map(len, tickets)) == (6, 6, 6)
    return tickets


def _all_three_ticket_geometries() -> tuple[tuple[set[int], set[int], set[int]], ...]:
    geometries: list[tuple[set[int], set[int], set[int]]] = []
    for all_3 in range(7):
        for only_12 in range(7 - all_3):
            for only_13 in range(7 - all_3):
                for only_23 in range(7 - all_3):
                    only_1 = 6 - only_12 - only_13 - all_3
                    only_2 = 6 - only_12 - only_23 - all_3
                    only_3 = 6 - only_13 - only_23 - all_3
                    if min(only_1, only_2, only_3) < 0:
                        continue
                    geometries.append(
                        _venn_geometry_tickets(
                            (
                                only_1,
                                only_2,
                                only_3,
                                only_12,
                                only_13,
                                only_23,
                                all_3,
                            )
                        )
                    )
    return tuple(geometries)


def test_transform_preserves_or_removes_numbers_by_the_fixed_order() -> None:
    disjoint = ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), (13, 14, 15, 16, 17, 18))
    assert make_k3_nonoverlap(disjoint) == disjoint

    first_second_overlap = ((1, 2, 3, 4, 5, 6), (5, 6, 7, 8, 9, 10), (11, 12, 13, 14, 15, 16))
    converted = make_k3_nonoverlap(first_second_overlap)
    assert converted == (
        first_second_overlap[0],
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
    )
    assert converted[0] == first_second_overlap[0]
    assert _legal_k3(converted)

    second_third_overlap = ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), (11, 12, 13, 14, 15, 16))
    converted = make_k3_nonoverlap(second_third_overlap)
    assert converted[2] == (13, 14, 15, 16, 17, 18)
    assert _legal_k3(converted)

    identical_tickets = ((1, 2, 3, 4, 5, 6),) * 3
    converted = make_k3_nonoverlap(identical_tickets)
    assert converted == (
        identical_tickets[0],
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
    )
    assert converted == make_k3_nonoverlap(identical_tickets)


def test_legal_sources_with_fourteen_to_seventeen_unique_numbers_are_filled() -> None:
    sources = (
        (
            (1, 2, 3, 4, 5, 6),
            (5, 6, 7, 8, 9, 10),
            (1, 2, 11, 12, 13, 14),
        ),
        (
            (1, 2, 3, 4, 5, 6),
            (6, 7, 8, 9, 10, 11),
            (1, 2, 12, 13, 14, 15),
        ),
        (
            (1, 2, 3, 4, 5, 6),
            (6, 7, 8, 9, 10, 11),
            (1, 12, 13, 14, 15, 16),
        ),
        (
            (1, 2, 3, 4, 5, 6),
            (6, 7, 8, 9, 10, 11),
            (12, 13, 14, 15, 16, 17),
        ),
    )
    expected_unique_counts = (14, 15, 16, 17)
    actual_unique_counts = tuple(
        len({number for ticket in source for number in ticket}) for source in sources
    )
    assert actual_unique_counts == expected_unique_counts
    for source in sources:
        converted = make_k3_nonoverlap(source)
        assert converted[0] == source[0]
        assert _legal_k3(converted)


def test_invalid_source_portfolios_fail_closed() -> None:
    legal = ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), (13, 14, 15, 16, 17, 18))
    with pytest.raises(ValueError, match="EXACTLY_THREE"):
        make_k3_nonoverlap(legal[:2])
    with pytest.raises(ValueError, match="SIX_NUMBERS"):
        make_k3_nonoverlap((legal[0][:-1], legal[1], legal[2]))
    with pytest.raises(ValueError, match="DUPLICATES"):
        make_k3_nonoverlap(((1, 1, 2, 3, 4, 5), legal[1], legal[2]))
    with pytest.raises(ValueError, match="OUT_OF_RANGE"):
        make_k3_nonoverlap(((0, 1, 2, 3, 4, 5), legal[1], legal[2]))


def test_rule_o_and_n_exact_q_match_the_packet_baselines() -> None:
    one_ticket = (set(range(1, 7)),)
    disjoint_k3 = (set(range(1, 7)), set(range(7, 13)), set(range(13, 19)))
    assert _fair_probability(one_ticket, include_two_plus_special=False) == Fraction(4654, 249711)
    assert _fair_probability(one_ticket, include_two_plus_special=True) == Fraction(7729, 249711)
    assert _fair_probability(disjoint_k3, include_two_plus_special=False) == _RULE_O_K3
    assert _fair_probability(disjoint_k3, include_two_plus_special=True) == _RULE_N_K3


def test_all_256_three_ticket_overlap_geometries_do_not_beat_disjoint_k3() -> None:
    geometries = _all_three_ticket_geometries()
    assert len(geometries) == 256
    strict_overlap_count = 0
    for tickets in geometries:
        q_old_o = _fair_probability(tickets, include_two_plus_special=False)
        q_old_n = _fair_probability(tickets, include_two_plus_special=True)
        assert q_old_o <= _RULE_O_K3
        assert q_old_n <= _RULE_N_K3
        has_overlap = any(
            not tickets[left].isdisjoint(tickets[right])
            for left in range(3)
            for right in range(left + 1, 3)
        )
        if has_overlap:
            strict_overlap_count += 1
            assert q_old_o < _RULE_O_K3
            assert q_old_n < _RULE_N_K3
        else:
            assert q_old_o == _RULE_O_K3
            assert q_old_n == _RULE_N_K3
    assert strict_overlap_count == 255


@pytest.mark.parametrize(
    ("donor_type", "candidate_type", "strategy_id"),
    (
        (
            BigLottoThreeBetOptimizerAdapter,
            BigLottoK3NonoverlapOptimizerCandidateAdapter,
            "research_biglotto__k3_nonoverlap_optimizer_candidate_20261116",
        ),
        (
            BigLottoTestEcpAdapter,
            BigLottoK3NonoverlapEcpCandidateAdapter,
            "research_biglotto__k3_nonoverlap_ecp_candidate_20261116",
        ),
    ),
)
def test_native_and_candidate_adapters_run_deterministically(
    donor_type: type,
    candidate_type: type,
    strategy_id: str,
) -> None:
    history = _history()
    donor = donor_type()
    native = donor.get_bets(history, LotteryType.BIG_LOTTO)
    assert len(native) == 3
    assert all(len(ticket) == 6 and len(set(ticket)) == 6 for ticket in native)

    candidate = candidate_type()
    first = candidate.get_bets(history, LotteryType.BIG_LOTTO)
    second = candidate.get_bets(history, LotteryType.BIG_LOTTO)
    assert candidate.strategy_id == strategy_id
    assert candidate.strategy_id != donor.strategy_id
    assert candidate.strategy_version != donor.strategy_version
    assert first == second
    assert first[0] == native[0]
    assert _legal_k3(first)


@pytest.mark.parametrize(
    ("donor_type", "candidate_type"),
    (
        (BigLottoThreeBetOptimizerAdapter, BigLottoK3NonoverlapOptimizerCandidateAdapter),
        (BigLottoTestEcpAdapter, BigLottoK3NonoverlapEcpCandidateAdapter),
    ),
)
def test_native_adapter_failures_are_propagated(
    monkeypatch: pytest.MonkeyPatch,
    donor_type: type,
    candidate_type: type,
) -> None:
    def native_failure(self: object, history: object, lottery_type: object) -> object:
        raise ValueError("SENTINEL_NATIVE_FAILURE")

    monkeypatch.setattr(donor_type, "_predict_all", native_failure)
    with pytest.raises(ValueError, match="SENTINEL_NATIVE_FAILURE"):
        candidate_type().get_bets(_history(), LotteryType.BIG_LOTTO)


@pytest.mark.parametrize(
    ("donor_type", "candidate_type", "native_output"),
    (
        (
            BigLottoThreeBetOptimizerAdapter,
            BigLottoK3NonoverlapOptimizerCandidateAdapter,
            ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12)),
        ),
        (
            BigLottoTestEcpAdapter,
            BigLottoK3NonoverlapEcpCandidateAdapter,
            ((1, 1, 2, 3, 4, 5), (7, 8, 9, 10, 11, 12), (13, 14, 15, 16, 17, 18)),
        ),
    ),
)
def test_native_ticket_count_or_legality_failures_are_not_repaired(
    monkeypatch: pytest.MonkeyPatch,
    donor_type: type,
    candidate_type: type,
    native_output: tuple[tuple[int, ...], ...],
) -> None:
    def invalid_native_output(self: object, history: object, lottery_type: object) -> object:
        return native_output

    monkeypatch.setattr(donor_type, "_predict_all", invalid_native_output)
    with pytest.raises(InvalidOutput):
        candidate_type().get_bets(_history(), LotteryType.BIG_LOTTO)


def test_candidate_and_native_imports_are_isolated_to_task_root() -> None:
    import lottolab
    import lottolab.strategies.adapters.base as base_module
    import lottolab.strategies.adapters.biglotto_k3_nonoverlap_candidate as candidate_module
    import lottolab.strategies.adapters.biglotto_wave3 as wave3_module
    import lottolab.strategies.adapters.biglotto_wave4 as wave4_module
    import lottolab.strategies.adapters.biglotto_wave6 as wave6_module
    import lottolab.strategies.adapters.biglotto_wave14 as wave14_module

    source_root = Path(__file__).resolve().parents[2] / "src"
    modules: tuple[ModuleType, ...] = (
        lottolab,
        base_module,
        wave3_module,
        wave4_module,
        wave6_module,
        wave14_module,
        candidate_module,
    )
    for module in modules:
        assert Path(module.__file__).resolve().is_relative_to(source_root)

    candidate_tree = ast.parse(Path(candidate_module.__file__).read_text(encoding="utf-8"))
    imported_modules = {
        alias.name.split(".", maxsplit=1)[0]
        for node in ast.walk(candidate_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".", maxsplit=1)[0]
        for node in ast.walk(candidate_tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert imported_modules <= {"__future__", "typing", "lottolab"}
    assert "random" not in imported_modules
    assert "sqlite3" not in imported_modules


def test_candidate_strategy_identities_are_independent() -> None:
    optimizer_id = BigLottoK3NonoverlapOptimizerCandidateAdapter.strategy_id
    ecp_id = BigLottoK3NonoverlapEcpCandidateAdapter.strategy_id
    assert optimizer_id != ecp_id
    assert optimizer_id != BigLottoThreeBetOptimizerAdapter.strategy_id
    assert ecp_id != BigLottoTestEcpAdapter.strategy_id
    assert BigLottoK3NonoverlapOptimizerCandidateAdapter.strategy_version == "v1.0.0"
    assert BigLottoK3NonoverlapEcpCandidateAdapter.strategy_version == "v1.0.0"
