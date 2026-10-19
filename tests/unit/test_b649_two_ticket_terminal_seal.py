"""Focused seal regressions and an import from an independent task-local driver."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from lottolab.research.b649_two_ticket_terminal_seal import (
    canonicalize_winning_slot_pairs,
    validate_winning_slot_pairs,
)

WINNING_TUPLES = [(3, 7), (0, 1), (18, 19)]
WINNING_LISTS = [[3, 7], [0, 1], [18, 19]]


@pytest.mark.parametrize("recorded", [WINNING_TUPLES, WINNING_LISTS])
@pytest.mark.parametrize("expected", [WINNING_TUPLES, WINNING_LISTS])
def test_tuple_and_json_list_winning_pairs_pass(recorded: object, expected: object) -> None:
    assert validate_winning_slot_pairs(recorded, expected, ticket_count=20) == WINNING_LISTS


def test_canonical_outputs_have_identical_bytes_and_preserve_order() -> None:
    representations = [WINNING_TUPLES, WINNING_LISTS, ((3, 7), [0, 1], (18, 19))]
    outputs = [canonicalize_winning_slot_pairs(pairs, ticket_count=20) for pairs in representations]
    assert outputs == [WINNING_LISTS] * 3
    assert [json.dumps(pairs, separators=(",", ":")).encode("utf-8") for pairs in outputs] == [
        b"[[3,7],[0,1],[18,19]]"
    ] * 3
    outputs[1][0][0] = 2
    assert WINNING_LISTS == [[3, 7], [0, 1], [18, 19]]
    assert outputs[0] == outputs[2] == WINNING_LISTS


@pytest.mark.parametrize(
    "recorded",
    [
        [[3, 8], [0, 1], [18, 19]],  # Different membership, same length.
        [[0, 1], [3, 7], [18, 19]],  # Same members, changed sequence order.
        [[3, 7], [0, 1]],  # Missing winner.
        [[3, 7], [0, 1], [18, 19], [2, 4]],  # Extra winner.
    ],
)
def test_semantic_mismatch_fails_closed(recorded: object) -> None:
    with pytest.raises(ValueError, match="winning slot pairs mismatch"):
        validate_winning_slot_pairs(recorded, WINNING_LISTS, ticket_count=20)


@pytest.mark.parametrize("side", ["recorded", "expected"])
def test_duplicate_pair_in_either_input_fails_closed(side: str) -> None:
    duplicate = [(3, 7), [3, 7], (0, 1), (18, 19)]
    recorded, expected = (
        (duplicate, WINNING_LISTS)
        if side == "recorded"
        else (WINNING_TUPLES, duplicate)
    )
    with pytest.raises(ValueError, match="duplicate winning slot pair"):
        validate_winning_slot_pairs(recorded, expected, ticket_count=20)


@pytest.mark.parametrize(
    "pairs",
    [
        None,
        [],
        {(0, 1)},
        {"0_1": [0, 1]},
        [[0]],
        [[0, 1, 2]],
        [["0", 1]],
        [[False, 1]],
        [[0, 1.0]],
        [[-1, 1]],
        [[0, 20]],
        [[1, 1]],
        [[7, 3]],  # Pair orientation must not be normalized away.
    ],
)
def test_invalid_pair_shape_or_membership_fails_closed(pairs: object) -> None:
    with pytest.raises(ValueError):
        canonicalize_winning_slot_pairs(pairs, ticket_count=20)


@pytest.mark.parametrize("ticket_count", [True, 1, 20.0])
def test_invalid_ticket_count_fails_closed(ticket_count: int) -> None:
    with pytest.raises(ValueError, match="ticket_count"):
        canonicalize_winning_slot_pairs(WINNING_TUPLES, ticket_count=ticket_count)


def test_future_task_local_driver_can_import_and_use_tracked_seal(tmp_path: Path) -> None:
    driver = tmp_path / "driver.py"
    driver.write_text(
        dedent('''\
            import json
            from lottolab.research.b649_two_ticket_terminal_seal import validate_winning_slot_pairs

            def seal_winning_pairs(iteration):
                # Existing identity, accounting and invariant gates run before this boundary.
                results = iteration["slot_pairs"]
                best_delta = max(item["best_delta_outcome"] for item in results.values())
                winning_pairs = [
                    [item["pos_i"], item["pos_j"]]
                    for item in results.values()
                    if item["best_delta_outcome"] == best_delta
                ]
                try:
                    return validate_winning_slot_pairs(
                        iteration.get("global_best_winning_slot_pairs"),
                        winning_pairs,
                        ticket_count=20,
                    )
                except ValueError as error:
                    raise SystemExit(
                        f"CHECKPOINT_RESULT_MISMATCH: winning pairs: {error}"
                    ) from error

            iteration = {"slot_pairs": {
                "3_7": {"pos_i": 3, "pos_j": 7, "best_delta_outcome": 0},
                "0_1": {"pos_i": 0, "pos_j": 1, "best_delta_outcome": 0},
                "2_4": {"pos_i": 2, "pos_j": 4, "best_delta_outcome": -1},
            }, "global_best_winning_slot_pairs": [(3, 7), (0, 1)]}
            print(json.dumps(seal_winning_pairs(iteration), separators=(",", ":")))
            restored = json.loads(json.dumps(iteration))
            print(json.dumps(seal_winning_pairs(restored), separators=(",", ":")))
            restored["global_best_winning_slot_pairs"] = [[3, 7], [2, 4]]
            seal_winning_pairs(restored)
            ''')
    )
    source_root = Path(__file__).resolve().parents[2] / "src"
    result = subprocess.run(
        [sys.executable, str(driver)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(source_root), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.stdout.splitlines() == ["[[3,7],[0,1]]", "[[3,7],[0,1]]"]
    assert result.returncode == 1
    assert "CHECKPOINT_RESULT_MISMATCH: winning pairs: winning slot pairs mismatch" in result.stderr
