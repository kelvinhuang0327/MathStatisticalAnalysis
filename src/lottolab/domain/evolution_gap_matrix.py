"""Pure temporal gap-matrix transform from the legacy evolution engine.

The donor is ``tools/evolving_strategy_engine/data_loader.py`` in the
preserved ``LotteryNewMeraged`` source snapshot (sha256
``0f3f8c75acf87b510be1787cc9cb2b99c029ffa51af38f2b47fed4a5275074ac``).
The accessible snapshot has no Git metadata, so this module does not claim a
donor commit identity.

For valid inputs, :func:`compute_evolution_gap_matrix` preserves the donor's
``compute_gaps`` recurrence.  Every row-number cell is ``-1`` until that
number has appeared in an earlier row.  Thereafter it is the current row
index minus the most recent earlier occurrence index.  An occurrence in the
current row updates state only after that row's gap cell is written.

The target adaptation validates valid Big Lotto draws and returns an
immutable tuple matrix.  It has no dependency on NumPy, strategy catalogs,
evaluation, persistence, schedulers, networks, or process runtime.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

DONOR_SOURCE = "tools/evolving_strategy_engine/data_loader.py"
DONOR_SOURCE_SHA256 = "0f3f8c75acf87b510be1787cc9cb2b99c029ffa51af38f2b47fed4a5275074ac"
DONOR_METHOD = "compute_gaps"

BIG_LOTTO_NUMBER_COUNT = 49
BIG_LOTTO_PICK_COUNT = 6
UNSEEN_GAP = -1

EvolutionGapDraw = tuple[int, ...]
EvolutionGapRow = tuple[int, ...]
EvolutionGapMatrix = tuple[EvolutionGapRow, ...]


class EvolutionGapMatrixError(ValueError):
    """Raised when a gap-matrix input violates its closed contract."""


def _validated_draws(values: object) -> tuple[EvolutionGapDraw, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise EvolutionGapMatrixError("draws must be a sequence")

    normalized: list[EvolutionGapDraw] = []
    for draw_index, value in enumerate(cast(Sequence[object], values)):
        if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
            raise EvolutionGapMatrixError(f"draws[{draw_index}] must be a sequence")
        raw_draw = tuple(cast(Sequence[object], value))
        if len(raw_draw) != BIG_LOTTO_PICK_COUNT:
            raise EvolutionGapMatrixError(
                f"draws[{draw_index}] must contain exactly {BIG_LOTTO_PICK_COUNT} numbers"
            )
        if any(type(number) is not int for number in raw_draw):
            raise EvolutionGapMatrixError(
                f"draws[{draw_index}] must contain exact built-in integers"
            )

        draw = cast(EvolutionGapDraw, raw_draw)
        if len(set(draw)) != BIG_LOTTO_PICK_COUNT:
            raise EvolutionGapMatrixError(f"draws[{draw_index}] must contain unique numbers")
        if any(number < 1 or number > BIG_LOTTO_NUMBER_COUNT for number in draw):
            raise EvolutionGapMatrixError(
                f"draws[{draw_index}] contains a number outside [1, {BIG_LOTTO_NUMBER_COUNT}]"
            )
        normalized.append(draw)

    return tuple(normalized)


def compute_evolution_gap_matrix(
    draws: Sequence[Sequence[int]],
) -> EvolutionGapMatrix:
    """Return the donor-equivalent full temporal gap matrix.

    The output has one row per input draw and exactly 49 columns in number
    order 1 through 49.  Inputs are fully validated before the transition, so
    a failure cannot expose a partial result or mutate caller-owned state.
    """

    history = _validated_draws(draws)
    last_seen = [UNSEEN_GAP] * BIG_LOTTO_NUMBER_COUNT
    rows: list[EvolutionGapRow] = []

    for draw_index, draw in enumerate(history):
        current_numbers = set(draw)
        gap_row: list[int] = []
        for number_index in range(BIG_LOTTO_NUMBER_COUNT):
            previous_index = last_seen[number_index]
            gap_row.append(draw_index - previous_index if previous_index >= 0 else UNSEEN_GAP)
            if number_index + 1 in current_numbers:
                last_seen[number_index] = draw_index
        rows.append(tuple(gap_row))

    return tuple(rows)


__all__ = [
    "BIG_LOTTO_NUMBER_COUNT",
    "BIG_LOTTO_PICK_COUNT",
    "DONOR_METHOD",
    "DONOR_SOURCE",
    "DONOR_SOURCE_SHA256",
    "UNSEEN_GAP",
    "EvolutionGapDraw",
    "EvolutionGapMatrix",
    "EvolutionGapMatrixError",
    "EvolutionGapRow",
    "compute_evolution_gap_matrix",
]
