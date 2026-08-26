# pyright: reportPrivateUsage=false

"""Independent synthetic acceptance suite for the frozen R2 Hawkes candidate."""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import cast

import pytest

import lottolab.research.biglotto_l2_pairwise_hawkes as hawkes


def _synthetic_history(count: int = 256) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(sorted(1 + ((time + 8 * offset) % 49) for offset in range(6)))
        for time in range(count)
    )


class _ReadSpy:
    def __init__(self, values: Sequence[object], *, poison: set[int] | None = None) -> None:
        self._values = tuple(values)
        self._poison: set[int] = set() if poison is None else set(poison)
        self.read_indices: list[int] = []

    def __len__(self) -> int:
        return len(self._values)

    def __getitem__(self, index: int) -> object:
        if index in self._poison:
            raise AssertionError(f"forbidden history index read: {index}")
        self.read_indices.append(index)
        return self._values[index]


def _as_sequence(spy: _ReadSpy) -> Sequence[object]:
    return cast(Sequence[object], spy)


def _audit36(value: Decimal) -> str:
    with localcontext(hawkes.DECIMAL_CONTEXT):
        return format(value.quantize(Decimal("1e-36"), rounding=ROUND_HALF_EVEN), "f")


def _zero_pair_quanta(value: int = 0) -> dict[tuple[int, int], int]:
    return {pair: value for pair in itertools.combinations(range(1, 50), 2)}


@pytest.fixture(scope="module")
def normal_fixture() -> tuple[_ReadSpy, hawkes.PairwiseHawkesResult]:
    spy = _ReadSpy(_synthetic_history(), poison=set(range(256, 512)))
    return spy, hawkes.compute_pairwise_hawkes(_as_sequence(spy), 256)


def test_identity_and_decimal_contract_are_frozen() -> None:
    assert hawkes.METHOD_ID == "BMSGV1_L2_PAIRWISE_7080016a070700c3"
    assert hawkes.DESIGN_NAME == "CAUSAL_BIVARIATE_EXPONENTIAL_HAWKES_EXACT6_V2"
    assert (
        hawkes.SEMANTIC_SIGNATURE
        == "7080016a070700c34990c834df208135be0eb0338d744cdb9974bc11852176a6"
    )
    assert hawkes.DECIMAL_CONTEXT.prec == 80
    assert hawkes.DECIMAL_CONTEXT.rounding is ROUND_HALF_EVEN
    assert hawkes.MAX_ACCEPTED_ITERATIONS_PER_ROW == 256
    assert hawkes.MAX_ARMIJO_TRIALS_PER_DIRECTION == 256


def test_st01_minimum_history_below_fallback_reads_no_element() -> None:
    spy = _ReadSpy([None] * 255, poison=set(range(255)))
    result = hawkes.compute_pairwise_hawkes(_as_sequence(spy), 255)

    assert spy.read_indices == []
    assert result.status == "FALLBACK_INSUFFICIENT_HISTORY"
    assert len(result.pair_quanta) == hawkes.PAIR_COUNT
    assert set(result.pair_quanta.values()) == {0}
    assert result.pair_matrix == tuple(tuple(0 for _ in range(49)) for _ in range(49))
    assert result.number_scores == tuple((number, 0) for number in range(1, 50))
    assert tuple(row.number for row in result.rank_table) == tuple(range(1, 50))
    assert result.ticket == (1, 2, 3, 4, 5, 6)
    assert result.ticket_objective == 0


def test_st02_minimum_history_exact_certifies_all_rows(normal_fixture: object) -> None:
    spy, result = cast(tuple[_ReadSpy, hawkes.PairwiseHawkesResult], normal_fixture)
    rows = [row for pair in result.pair_rows for row in (pair.row_i, pair.row_j)]

    assert spy.read_indices == list(range(256))
    assert result.status == "NORMAL"
    assert len(rows) == hawkes.ROW_FIT_COUNT
    assert len(result.pair_rows) == hawkes.PAIR_COUNT
    assert len(result.pair_quanta) == hawkes.PAIR_COUNT
    assert len(result.pair_matrix) == 49
    assert all(len(row) == 49 for row in result.pair_matrix)
    assert max(row.accepted_updates for row in rows) <= 13
    assert sum(row.fallback_updates > 0 for row in rows) == 240
    assert sum(row.fallback_updates for row in rows) == 398
    assert all(row.residual_raw <= Decimal("1e-32") for row in rows)
    assert all(
        row.self_alpha_quantum + row.cross_alpha_quantum
        <= 950_000_000_000_000_000_000_000
        for row in rows
    )
    assert len(result.rank_table) == 49
    assert len(result.ticket) == 6
    assert result.ticket == tuple(sorted(set(result.ticket)))
    assert all(1 <= number <= 49 for number in result.ticket)


def test_st03_causal_exclusion_ignores_earlier_and_future_poison() -> None:
    history = _synthetic_history(270)
    clean = _ReadSpy(history)
    poisoned_values: list[object] = list(history)
    poisoned_values[:4] = [object(), object(), object(), object()]
    poisoned_values[260:] = [object() for _ in range(10)]
    poisoned = _ReadSpy(poisoned_values, poison=set(range(4)) | set(range(260, 270)))

    clean_result = hawkes.compute_pairwise_hawkes(_as_sequence(clean), 260)
    poisoned_result = hawkes.compute_pairwise_hawkes(_as_sequence(poisoned), 260)

    assert clean.read_indices == list(range(4, 260))
    assert poisoned.read_indices == list(range(4, 260))
    assert clean_result.serialize() == poisoned_result.serialize()


def test_st04_core_hand_calculation_matches_frozen_fingerprint() -> None:
    objective = hawkes.target_row_objective([256], [256], [255], "1", "0", "0.5")
    gradient = hawkes.target_row_gradient([256], [256], [255], "1", "0", "0.5")

    assert _audit36(objective) == "1.003016455687171769792908188164406297"
    assert tuple(_audit36(value) for value in gradient) == (
        "1.000606884388660014089036791359467314",
        "0.000000000000000000000000000000000000",
        "0.003208577155604025253193902553872166",
    )
    assert _audit36(hawkes.build_exponential_table()[1]) == (
        "0.367879441171442321595523770161460867"
    )


def test_st05_zero_cross_dependence_and_st10_empty_target_boundary() -> None:
    row_i = hawkes.fit_target_row([64, 128, 192, 255], [64, 128, 192, 255], [])
    row_j = hawkes.fit_target_row([], [], [64, 128, 192, 255])

    assert row_i.cross_alpha_quantum == 0
    assert row_j.cross_alpha_quantum == 0
    assert row_i.cross_alpha_serialized == "0.000000000000000000000000"
    assert row_j.cross_alpha_serialized == "0.000000000000000000000000"
    assert row_j.accepted_updates == 0
    assert row_j.baseline_serialized == "0.000000000001000000000000"
    assert row_j.projected_gradient_residual == Decimal("0")


def test_st06_strong_directionality_matches_revised_coefficients() -> None:
    reverse = hawkes.fit_target_row([255], [255], [256])
    forward = hawkes.fit_target_row([256], [256], [255])
    pair_quantum = hawkes.half_even_pair_quantum(
        reverse.cross_alpha_quantum,
        forward.cross_alpha_quantum,
    )

    assert reverse.accepted_updates == 3
    assert reverse.cross_alpha_serialized == "0.000000000000000000000000"
    assert forward.accepted_updates == 10
    assert forward.cross_alpha_serialized == "0.732698081801364604625939"
    assert forward.cross_alpha_quantum == 732698081801364604625939
    assert pair_quantum == 366349040900682302312970


def test_st07_pair_label_swap_preserves_symmetrization() -> None:
    original_left = hawkes.fit_target_row([255], [255], [256])
    original_right = hawkes.fit_target_row([256], [256], [255])
    swapped_left = hawkes.fit_target_row([256], [256], [255])
    swapped_right = hawkes.fit_target_row([255], [255], [256])

    assert (swapped_left.cross_alpha_quantum, swapped_right.cross_alpha_quantum) == (
        original_right.cross_alpha_quantum,
        original_left.cross_alpha_quantum,
    )
    assert hawkes.half_even_pair_quantum(
        original_left.cross_alpha_quantum, original_right.cross_alpha_quantum
    ) == hawkes.half_even_pair_quantum(
        swapped_left.cross_alpha_quantum, swapped_right.cross_alpha_quantum
    )


def test_st08_same_draw_events_do_not_excitate_each_other() -> None:
    left = hawkes.fit_target_row([256], [256], [256])
    right = hawkes.fit_target_row([256], [256], [256])

    assert left.cross_alpha_quantum == 0
    assert right.cross_alpha_quantum == 0
    assert hawkes.half_even_pair_quantum(left.cross_alpha_quantum, right.cross_alpha_quantum) == 0


def test_st09_stability_projection_boundary_is_orthogonal() -> None:
    projected = hawkes.project_feasible("0", "0.8", "0.8")

    assert tuple(format(value.quantize(Decimal("1e-24")), "f") for value in projected) == (
        "0.000000000001000000000000",
        "0.475000000000000000000000",
        "0.475000000000000000000000",
    )
    assert projected[1] + projected[2] == Decimal("0.95")


def test_st11_half_even_directional_mean_uses_even_neighbor() -> None:
    assert hawkes.half_even_pair_quantum(1, 2) == 2


def test_st12_invalid_inputs_and_solver_failure_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid_history = _synthetic_history()
    with pytest.raises(hawkes.InvalidCutoffError):
        hawkes.compute_pairwise_hawkes(valid_history, True)
    with pytest.raises(hawkes.InvalidCutoffError):
        hawkes.compute_pairwise_hawkes(valid_history, 257)

    duplicate = list(valid_history)
    duplicate[0] = (1, 1, 2, 3, 4, 5)
    with pytest.raises(hawkes.InvalidHistoryError):
        hawkes.compute_pairwise_hawkes(tuple(duplicate), 256)

    boolean_number = list(valid_history)
    boolean_number[0] = (True, 2, 3, 4, 5, 6)
    with pytest.raises(hawkes.InvalidHistoryError):
        hawkes.compute_pairwise_hawkes(tuple(boolean_number), 256)

    monkeypatch.setattr(hawkes, "MAX_ACCEPTED_ITERATIONS_PER_ROW", 0)
    with pytest.raises(hawkes.SolverConvergenceError):
        hawkes.fit_target_row([256], [256], [255])


def test_st13_exact_six_endpoint_fixture() -> None:
    pair_quanta = _zero_pair_quanta()
    target = (1, 2, 3, 4, 5, 49)
    for left_index, left in enumerate(target[:-1]):
        for right in target[left_index + 1 :]:
            pair_quanta[(left, right)] = 1

    selection = hawkes.construct_exact_six_ticket(pair_quanta)
    assert selection.objective == 15
    assert selection.ticket == target
    assert selection.combinations_examined == hawkes.TICKET_COMBINATION_COUNT


def test_st14_exact_six_lexicographic_tie_fixture() -> None:
    selection = hawkes.construct_exact_six_ticket(_zero_pair_quanta(7))
    assert selection.objective == 105
    assert selection.ticket == (1, 2, 3, 4, 5, 6)


def test_st15_repeated_normal_invocations_are_byte_deterministic() -> None:
    history = _synthetic_history()
    first = hawkes.compute_pairwise_hawkes(history, 256)
    second = hawkes.compute_pairwise_hawkes(history, 256)

    assert first.serialize() == second.serialize()
    assert len(first.pair_rows) == 1176
    assert len(first.pair_quanta) == 1176
    assert len(first.rank_table) == 49
    assert len(first.ticket) == 6
    assert first.ticket == tuple(sorted(set(first.ticket)))


def test_st16_mandatory_pair_1_8_revised_solver(normal_fixture: object) -> None:
    _, result = cast(tuple[_ReadSpy, hawkes.PairwiseHawkesResult], normal_fixture)
    mandatory = next(pair for pair in result.pair_rows if (pair.i, pair.j) == (1, 8))

    assert mandatory.pair_quantum == 473214435347853167423307
    assert mandatory.row_i.accepted_updates == 11
    assert mandatory.row_i.baseline_serialized == "0.007078371206932434434989"
    assert mandatory.row_i.cross_alpha_serialized == "0.946428870695706334846614"
    assert mandatory.row_i.self_alpha_quantum == 0
    assert mandatory.row_i.residual_raw <= Decimal("1e-32")
    assert mandatory.row_j.accepted_updates == 4
    assert mandatory.row_j.cross_alpha_quantum == 0
    assert mandatory.row_j.residual_raw <= Decimal("1e-32")


def test_st17_active_set_order_and_fallback_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    point = (Decimal("0.000000000001"), Decimal("0"), Decimal("0"))
    gradient = (Decimal("1"), Decimal("1"), Decimal("-1"))
    rows, flags = hawkes._active_constraints(point, gradient)
    assert flags == {
        "mu_floor": True,
        "self_zero": True,
        "cross_zero": False,
        "alpha_sum": False,
    }
    assert rows == (
        (Decimal("1"), Decimal("0"), Decimal("0")),
        (Decimal("0"), Decimal("1"), Decimal("0")),
    )

    original_solver = hawkes._solve_kkt
    calls = 0

    def fail_once(
        hessian: tuple[tuple[Decimal, ...], ...],
        row_gradient: tuple[Decimal, Decimal, Decimal],
        active_rows: tuple[tuple[Decimal, Decimal, Decimal], ...],
    ) -> tuple[Decimal, Decimal, Decimal]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise hawkes.NumericContractError("injected singular KKT")
        return original_solver(hessian, row_gradient, active_rows)

    monkeypatch.setattr(hawkes, "_solve_kkt", fail_once)
    row = hawkes.fit_target_row([256], [256], [255])
    assert calls >= 1
    assert row.fallback_updates >= 1
    assert row.residual_raw <= Decimal("1e-32")


def test_semantic_signature_helper_is_deterministic() -> None:
    core = {"b": [2, 1], "a": {"x": True}}
    assert hawkes.semantic_signature_for_core(core) == hawkes.semantic_signature_for_core(core)
