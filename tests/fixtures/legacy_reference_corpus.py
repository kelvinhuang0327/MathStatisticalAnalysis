"""Synthetic sealed-corpus builder for Phase 2a importer tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lottolab.application.legacy_reference_import import CORPUS_ROOT_NAME


def build_legacy_reference_corpus(
    parent: Path,
    *,
    causal_violation: bool = False,
) -> Path:
    root = parent / CORPUS_ROOT_NAME
    tables = root / "tables"
    tables.mkdir(parents=True)
    draws = (
        _draw_row("100", "2020/01/01", [7, 8, 9, 10, 11, 12], 13),
        _draw_row("101", "2020/01/02", [1, 2, 10, 11, 12, 13], 6),
        _draw_row("102", "2020-01-03", [1, 3, 14, 15, 16, 17], 2),
    )
    replay_rows: list[dict[str, object]] = []
    source_id = 0
    for target_draw, target_date, cutoff, actual, special, hits in (
        (
            "101",
            "2020/01/02",
            "101" if causal_violation else "100",
            [1, 2, 10, 11, 12, 13],
            6,
            [1, 2],
        ),
        (
            "102",
            "2020-01-03",
            "101",
            [1, 3, 14, 15, 16, 17],
            2,
            [1, 3],
        ),
    ):
        for bet_index in range(1, 251):
            source_id += 1
            replay_rows.append(
                {
                    "actual_numbers": _json(actual),
                    "actual_special": special,
                    "bet_index": bet_index,
                    "dry_run": 0,
                    "generated_at": "2026-01-01T00:00:00+00:00",
                    "history_cutoff_draw": cutoff,
                    "hit_count": 2,
                    "hit_numbers": _json(hits),
                    "id": source_id,
                    "lottery_type": "BIG_LOTTO",
                    "predicted_numbers": _json([1, 2, 3, 4, 5, 6]),
                    "predicted_special": None,
                    "provenance_hash": f"{source_id:016x}",
                    "provenance_source": "synthetic-legacy-source",
                    "reject_reason": None,
                    "replay_run_id": "synthetic",
                    "replay_status": "PREDICTED",
                    "special_hit": 1,
                    "strategy_id": "synthetic_duplicate_strategy",
                    "strategy_name": "Synthetic Duplicate Strategy",
                    "strategy_version": "v0.1",
                    "target_date": target_date,
                    "target_draw": target_draw,
                }
            )
    replay_rows.extend(
        (
            {"lottery_type": "POWER_LOTTO"},
            {"lottery_type": "DAILY_539"},
        )
    )
    replay_path = tables / "strategy_prediction_replays.jsonl"
    draws_path = tables / "draws.jsonl"
    replay_path.write_text(
        "".join(f"{_json(row)}\n" for row in replay_rows),
        encoding="utf-8",
    )
    draws_path.write_text(
        "".join(f"{_json(row)}\n" for row in draws),
        encoding="utf-8",
    )
    checksums = (
        f"{_sha256(draws_path)}  tables/draws.jsonl\n"
        f"{_sha256(replay_path)}  tables/strategy_prediction_replays.jsonl\n"
    )
    (root / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    return root


def reseal_corpus(root: Path) -> None:
    draws_path = root / "tables" / "draws.jsonl"
    replay_path = root / "tables" / "strategy_prediction_replays.jsonl"
    (root / "SHA256SUMS").write_text(
        (
            f"{_sha256(draws_path)}  tables/draws.jsonl\n"
            f"{_sha256(replay_path)}  tables/strategy_prediction_replays.jsonl\n"
        ),
        encoding="utf-8",
    )


def _draw_row(
    draw: str,
    draw_date: str,
    numbers: list[int],
    special: int,
) -> dict[str, object]:
    return {
        "created_at": "2026-01-01 00:00:00",
        "date": draw_date,
        "draw": draw,
        "id": int(draw),
        "lottery_type": "BIG_LOTTO",
        "numbers": _json(numbers),
        "special": special,
    }


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = ["build_legacy_reference_corpus", "reseal_corpus"]
