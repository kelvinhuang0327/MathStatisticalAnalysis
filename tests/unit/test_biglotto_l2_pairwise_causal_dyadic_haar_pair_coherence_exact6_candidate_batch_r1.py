# pyright: reportPrivateUsage=false

from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Context, Decimal, DivisionByZero, InvalidOperation, Overflow
from itertools import combinations
from pathlib import Path
from typing import overload

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_causal_dyadic_haar_pair_coherence_exact6_candidate_batch_r1 as candidate,
)

Draw = tuple[int, ...]


def _embed_streams(streams: Mapping[int, Sequence[int]]) -> tuple[Draw, ...]:
    assert streams
    assert all(len(stream) == 256 for stream in streams.values())
    named_numbers = frozenset(streams)
    assert len(named_numbers) <= 6
    assert all(1 <= number <= 49 for number in named_numbers)

    draws: list[Draw] = []
    for position in range(256):
        selected: list[int] = []
        for number in sorted(named_numbers):
            value = streams[number][position]
            assert value in (0, 1)
            if value == 1:
                selected.append(number)
        fillers = [
            number
            for number in range(1, 50)
            if number not in named_numbers and number not in selected
        ]
        selected.extend(fillers[: 6 - len(selected)])
        draws.append(tuple(sorted(selected)))
    return tuple(draws)


def _literal_haar_contrasts(stream: Sequence[int], scale: int) -> tuple[int, ...]:
    block_length = 2**scale
    half = block_length // 2
    contrasts: list[int] = []
    for start in range(0, 256, block_length):
        first_half = sum(stream[start : start + half])
        second_half = sum(stream[start + half : start + block_length])
        contrasts.append(first_half - second_half)
    return tuple(contrasts)


def _literal_orthonormal_pair_quanta(
    left_stream: Sequence[int],
    right_stream: Sequence[int],
) -> int:
    context = Context(
        prec=80,
        rounding=ROUND_HALF_EVEN,
        Emin=-999999,
        Emax=999999,
        capitals=1,
        clamp=0,
        traps=[InvalidOperation, DivisionByZero, Overflow],
    )
    coherences: list[Decimal] = []
    for scale in range(1, 7):
        left_h = _literal_haar_contrasts(left_stream, scale)
        right_h = _literal_haar_contrasts(right_stream, scale)
        normalization = context.sqrt(Decimal(2**scale))
        left_d = tuple(context.divide(Decimal(value), normalization) for value in left_h)
        right_d = tuple(context.divide(Decimal(value), normalization) for value in right_h)

        cross = Decimal(0)
        left_energy = Decimal(0)
        right_energy = Decimal(0)
        for left_value, right_value in zip(left_d, right_d, strict=True):
            cross = context.add(cross, context.multiply(left_value, right_value))
            left_energy = context.add(
                left_energy,
                context.multiply(left_value, left_value),
            )
            right_energy = context.add(
                right_energy,
                context.multiply(right_value, right_value),
            )
        if left_energy == 0 or right_energy == 0 or cross == 0:
            coherences.append(Decimal(0))
            continue
        denominator = context.sqrt(context.multiply(left_energy, right_energy))
        coherences.append(context.divide(context.abs(cross), denominator))

    total = Decimal(0)
    for coherence in coherences:
        total = context.add(total, coherence)
    mean = context.divide(total, Decimal(6))
    quantized = context.quantize(mean, Decimal("1e-30"))
    return int(context.multiply(quantized, Decimal(10**30)))


def _zero_pair_quanta() -> dict[tuple[int, int], int]:
    return {pair: 0 for pair in combinations(range(1, 50), 2)}


class _TrapHistory(Sequence[Draw]):
    def __init__(self, length: int) -> None:
        self._length = length
        self.accesses: list[int | slice] = []

    def __len__(self) -> int:
        return self._length

    @overload
    def __getitem__(self, index: int) -> Draw: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[Draw, ...]: ...

    def __getitem__(self, index: int | slice) -> Draw | tuple[Draw, ...]:
        self.accesses.append(index)
        raise AssertionError(f"history element unexpectedly read: {index}")


class _CausalHistory(Sequence[Draw]):
    def __init__(self, completed: tuple[Draw, ...], sentinel: str) -> None:
        self._completed = completed
        self._sentinel = sentinel
        self.accesses: list[int] = []

    def __len__(self) -> int:
        return len(self._completed) + 2

    @overload
    def __getitem__(self, index: int) -> Draw: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[Draw, ...]: ...

    def __getitem__(self, index: int | slice) -> Draw | tuple[Draw, ...]:
        if isinstance(index, slice):
            raise AssertionError(f"slice unexpectedly read: {index}")
        self.accesses.append(index)
        if index >= len(self._completed):
            raise AssertionError(f"{self._sentinel} sentinel unexpectedly read: {index}")
        return self._completed[index]


def test_t01_min_history_below_boundary_fallback_never_reads_history() -> None:
    history = _TrapHistory(255)

    result = candidate.run_design(history, 255)

    assert history.accesses == []
    assert result.status == "FALLBACK_INSUFFICIENT_HISTORY"
    assert len(result.pair_quanta) == 1176
    assert all(value == 0 for value in result.pair_quanta.values())
    assert len(result.number_ranks) == 49
    assert tuple(row.number for row in result.number_ranks) == tuple(range(1, 50))
    assert all(row.score == 0 for row in result.number_ranks)
    assert result.ticket_objective == 0
    assert result.ticket == (1, 2, 3, 4, 5, 6)


def test_t02_min_history_exact_constant_draws_have_all_zero_haar_energy() -> None:
    history = ((1, 2, 3, 4, 5, 6),) * 256

    result = candidate.run_design(history, 256)

    contrasts = candidate.compute_haar_contrasts(history)
    assert result.status == "SUCCESS"
    assert all(
        value == 0
        for number_scales in contrasts.values()
        for scale_values in number_scales.values()
        for value in scale_values
    )
    assert all(value == 0 for value in result.pair_quanta.values())
    assert result.ticket == (1, 2, 3, 4, 5, 6)


def test_t03_target_and_future_are_excluded_and_outputs_are_byte_identical() -> None:
    completed = tuple(
        tuple(sorted(((index + offset) % 49) + 1 for offset in range(6))) for index in range(256)
    )
    first_history = _CausalHistory(completed, "first")
    second_history = _CausalHistory(completed, "second")

    first = candidate.run_design(first_history, 256)
    second = candidate.run_design(second_history, 256)

    expected_accesses = list(range(256))
    assert first_history.accesses == expected_accesses
    assert second_history.accesses == expected_accesses
    assert first.to_canonical_json() == second.to_canonical_json()


def test_t04_hand_calculable_scale_one_cross_energy_and_zero_coherence() -> None:
    x_prefix = (1, 0, 0, 1, 1, 0, 0, 1)
    z_prefix = (1, 0, 1, 0, 0, 1, 0, 1)
    x = (*x_prefix, *((0,) * 248))
    z = (*z_prefix, *((0,) * 248))
    contrasts = candidate.compute_haar_contrasts(_embed_streams({1: x, 2: x, 49: z}))

    assert contrasts[1][1][:4] == (1, -1, 1, -1)
    assert contrasts[2][1][:4] == (1, -1, 1, -1)
    assert contrasts[49][1][:4] == (1, 1, -1, -1)
    assert candidate.scale_statistics(contrasts, 1, 2, 1) == (4, 4, 4)
    assert candidate.scale_statistics(contrasts, 1, 49, 1) == (0, 4, 4)
    assert candidate.normalized_cross_energy(4, 4, 4) == Decimal(1)
    assert candidate.normalized_cross_energy(0, 4, 4) == Decimal(0)


def test_t05_orthogonal_patterns_have_zero_pair_weight_at_all_six_scales() -> None:
    x = tuple(1 if position % 2 == 0 else 0 for position in range(256))
    y = tuple(1 if position % 4 < 2 else 0 for position in range(256))
    contrasts = candidate.compute_haar_contrasts(_embed_streams({1: x, 49: y}))

    for scale in range(1, 7):
        cross, left_energy, right_energy = candidate.scale_statistics(
            contrasts,
            1,
            49,
            scale,
        )
        assert candidate.normalized_cross_energy(cross, left_energy, right_energy) == 0
    assert candidate.compute_pair_weight_quantum(contrasts, 1, 49) == 0


def test_t06_identical_impulses_have_perfect_coherence_at_every_scale() -> None:
    impulse = (1, *((0,) * 255))
    contrasts = candidate.compute_haar_contrasts(_embed_streams({1: impulse, 49: impulse}))

    for scale in range(1, 7):
        assert candidate.scale_statistics(contrasts, 1, 49, scale) == (1, 1, 1)
    quanta = candidate.compute_pair_weight_quantum(contrasts, 1, 49)
    assert quanta == 10**30
    assert candidate.weight_string_from_quanta(quanta) == "1.000000000000000000000000000000"


def test_t07_negative_phase_is_discarded_by_absolute_coherence() -> None:
    left = (1, -1)
    right = (-1, 1)
    cross = sum(a * b for a, b in zip(left, right, strict=True))
    left_energy = sum(value * value for value in left)
    right_energy = sum(value * value for value in right)

    assert (cross, left_energy, right_energy) == (-2, 2, 2)
    assert candidate.normalized_cross_energy(cross, left_energy, right_energy) == Decimal(1)


def test_t08_pair_coherence_is_symmetric_and_emits_one_unordered_entry() -> None:
    left = tuple(1 if position % 4 == 0 else 0 for position in range(256))
    right = tuple(1 if position % 8 < 3 else 0 for position in range(256))
    contrasts = candidate.compute_haar_contrasts(_embed_streams({1: left, 49: right}))

    forward = candidate.compute_pair_weight_quantum(contrasts, 1, 49)
    reverse = candidate.compute_pair_weight_quantum(contrasts, 49, 1)
    assert forward == reverse
    assert sum(pair == (1, 49) for pair in candidate.PAIR_ORDER) == 1
    assert (49, 1) not in candidate.PAIR_ORDER


def test_t09_decimal_80_digit_sqrt_vector_and_nearest_cell_proof() -> None:
    expected_quanta = 707106781186547524400844362105
    denominator = 10**30
    coherence = candidate.normalized_cross_energy(1, 1, 2)

    assert candidate.DECIMAL_CONTEXT.prec == 80
    assert candidate.DECIMAL_CONTEXT.rounding == ROUND_HALF_EVEN
    assert (2 * expected_quanta - 1) ** 2 < 2 * denominator**2
    assert 2 * denominator**2 < (2 * expected_quanta + 1) ** 2
    quanta = candidate.mean_coherence_quanta((coherence,) * 6)
    assert quanta == expected_quanta
    assert candidate.weight_string_from_quanta(quanta) == ("0.707106781186547524400844362105")


def test_t10_zero_energy_short_circuits_without_sqrt_or_division() -> None:
    assert candidate.normalized_cross_energy(9, 0, 9) == Decimal(0)
    assert candidate.normalized_cross_energy(-9, 9, 0) == Decimal(0)
    assert candidate.normalized_cross_energy(0, 9, 9) == Decimal(0)


def test_t11_all_zero_pair_matrix_ranks_all_49_numbers_by_number() -> None:
    ranks = candidate.rank_numbers(_zero_pair_quanta())

    assert tuple(row.number for row in ranks) == tuple(range(1, 50))
    assert tuple(row.rank for row in ranks) == tuple(range(1, 50))
    assert all(row.score == 0 for row in ranks)


def test_t12_exact_six_subset_optimizer_finds_unique_edge_clique() -> None:
    clique = (1, 10, 20, 30, 40, 49)
    clique_pairs = frozenset(combinations(clique, 2))
    pair_quanta = {
        pair: (10**30 if pair in clique_pairs else 0) for pair in combinations(range(1, 50), 2)
    }

    objective, ticket = candidate.construct_exact_ticket(pair_quanta)

    assert ticket == clique
    assert len(ticket) == len(set(ticket)) == 6
    assert tuple(sorted(ticket)) == ticket
    assert ticket[0] == 1 and ticket[-1] == 49
    assert objective == 15 * 10**30


def test_t13_all_zero_exact_optimizer_uses_lexicographically_smallest_tie() -> None:
    objective, ticket = candidate.construct_exact_ticket(_zero_pair_quanta())

    assert candidate.EXACT_SIX_SUBSET_COUNT == 13_983_816
    assert objective == 0
    assert ticket == (1, 2, 3, 4, 5, 6)


@pytest.mark.parametrize("cutoff", [-1, True, 257, 1.5, "256", None])
def test_t14_invalid_cutoff_fails_closed(cutoff: object) -> None:
    history = ((1, 2, 3, 4, 5, 6),) * 256
    with pytest.raises(candidate.InvalidCutoffError):
        candidate.run_design(history, cutoff)


@pytest.mark.parametrize(
    "invalid_draw",
    [
        (1, 2, 3, 4, 5),
        (1, 2, 3, 4, 5, 6, 7),
        (1, 2, 3, 4, 5, 5),
        (0, 1, 2, 3, 4, 5),
        (1, 2, 3, 4, 5, 50),
        (1, 2, 3, 4, 5, True),
        (1, 2, 3, 4, 5, 6.0),
        (1, 2, 3, 4, 5, "6"),
    ],
)
def test_t14_invalid_accessed_draw_fails_closed(invalid_draw: object) -> None:
    history: tuple[object, ...] = (*(((1, 2, 3, 4, 5, 6),) * 255), invalid_draw)
    with pytest.raises(candidate.InvalidHistoryError):
        candidate.run_design(history, 256)


def test_t14_boundary_numbers_one_and_49_are_valid() -> None:
    history = ((49, 5, 4, 3, 2, 1),) * 256
    contrasts = candidate.compute_haar_contrasts(history)

    assert set(contrasts) == set(range(1, 50))
    assert all(value == 0 for value in contrasts[1][6])
    assert all(value == 0 for value in contrasts[49][6])


def test_t15_boundary_impulses_use_aligned_blocks_without_wrap() -> None:
    first_impulse = (1, *((0,) * 255))
    last_impulse = (*((0,) * 255), 1)
    contrasts = candidate.compute_haar_contrasts(
        _embed_streams({1: first_impulse, 49: last_impulse})
    )

    for scale in range(1, 7):
        expected_first = _literal_haar_contrasts(first_impulse, scale)
        expected_last = _literal_haar_contrasts(last_impulse, scale)
        assert contrasts[1][scale] == expected_first
        assert contrasts[49][scale] == expected_last
        assert expected_first[0] == 1
        assert expected_last[-1] == -1
        assert sum(value != 0 for value in expected_first) == 1
        assert sum(value != 0 for value in expected_last) == 1


def test_t16_literal_orthonormal_details_match_integer_contrast_core() -> None:
    streams = {
        1: (1,) * 256,
        2: (1, *((0,) * 255)),
        48: tuple(1 if position % 2 == 0 else 0 for position in range(256)),
        49: tuple(1 if position % 4 < 2 else 0 for position in range(256)),
    }
    contrasts = candidate.compute_haar_contrasts(_embed_streams(streams))

    for left, right in combinations(sorted(streams), 2):
        literal_quanta = _literal_orthonormal_pair_quanta(streams[left], streams[right])
        optimized_quanta = candidate.compute_pair_weight_quantum(contrasts, left, right)
        assert optimized_quanta == literal_quanta


def test_t17_twenty_fresh_processes_are_byte_deterministic() -> None:
    project_root = Path(candidate.__file__).resolve().parents[3]
    code = """
import hashlib
from importlib import import_module

c = import_module(
    "lottolab.research."
    "biglotto_l2_pairwise_causal_dyadic_haar_pair_coherence_exact6_"
    "candidate_batch_r1"
)

draws = []
for position in range(256):
    selected = [1]
    if position == 0:
        selected.append(2)
    if position % 2 == 0:
        selected.append(48)
    if position % 4 < 2:
        selected.append(49)
    selected.extend(number for number in range(3, 48) if number not in selected)
    draws.append(tuple(sorted(selected[:6])))
serialized = c.run_design(tuple(draws), 256).to_canonical_json().encode("utf-8")
print(hashlib.sha256(serialized).hexdigest())
"""
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(project_root / "src")

    digests: list[str] = []
    for _ in range(20):
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=project_root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        digests.append(completed.stdout.strip())

    assert len(digests) == 20
    assert all(len(digest) == 64 for digest in digests)
    assert len(set(digests)) == 1


def test_frozen_identity_serialization_and_dependency_boundary() -> None:
    assert candidate.METHOD_ID == "BMSGV1_L2_PAIRWISE_96368234e833a391"
    assert candidate.DESIGN_NAME == "CAUSAL_DYADIC_HAAR_PAIR_COHERENCE_EXACT6_V1"
    assert candidate.SEMANTIC_SIGNATURE == (
        "96368234e833a391f98ebe9d4deaf5adea2b12335a341e80be87cf9a7c4a3ba2"
    )
    assert candidate.METHOD_ID.endswith(candidate.SEMANTIC_SIGNATURE[:16])

    module_path = Path(candidate.__file__)
    syntax = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(syntax):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    assert imported_modules <= {
        "__future__",
        "collections.abc",
        "dataclasses",
        "decimal",
        "itertools",
        "json",
        "typing",
    }
    assert not imported_modules & {
        "datetime",
        "httpx",
        "numpy",
        "pandas",
        "random",
        "requests",
        "scipy",
        "secrets",
        "sklearn",
        "socket",
        "sqlite3",
        "time",
    }

    fallback = candidate.run_design((), 0)
    serialized = fallback.to_canonical_json()
    assert (
        hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        == hashlib.sha256(fallback.to_canonical_json().encode("utf-8")).hexdigest()
    )
    assert '"ticket":[1,2,3,4,5,6]' in serialized
    assert '"ticket_objective":"0"' in serialized
