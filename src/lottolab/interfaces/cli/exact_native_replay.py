"""Operator CLI for the canonical exact-native BIG_LOTTO replay universe.

Two commands: ``replay-biglotto-exact-native`` (one coherent run, optionally
``--shard-count``-parallelized) and ``replay-biglotto-exact-native-shard``
(one explicit target-index range -- the standalone operational seam a
parallel orchestrator invokes, and that an operator may also invoke
directly). Every donor task-specific constant is an explicit option here;
current defaults reproduce current post-PR231 behavior exactly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab.application.use_cases.replay_exact_native_targets import (
    DEFAULT_EXPECTED_MAIN_NUMBERS,
    DEFAULT_EXPECTED_SPECIAL_NUMBER,
    DEFAULT_MAX_VISIBLE_DRAW,
    ExactNativeReplayRuntimeError,
    ReplayTargetRangeRequest,
    load_authoritative_draws,
    replay_exact_native_target_range,
)
from lottolab.application.use_cases.shard_exact_native_replay import (
    ShardExactNativeReplayRequest,
    run_sharded_exact_native_replay,
)
from lottolab.domain.exact_native_replay import (
    DEFAULT_NATIVE_TICKET_COUNTS,
    ExactNativeReplayError,
    freeze_visible_draws,
)
from lottolab.evidence.exact_native_replay_manifest import (
    EVIDENCE_FILENAME,
    METADATA_FILENAME,
    write_json_file,
)

_DEFAULT_WINDOW_SPECS = ("FULL:FULL", "RECENT_750:750", "RECENT_300:300", "RECENT_50:50")


def _parse_windows(specs: list[str]) -> tuple[tuple[str, ...], dict[str, int | None]]:
    order: list[str] = []
    sizes: dict[str, int | None] = {}
    for spec in specs:
        name, _, raw_size = spec.partition(":")
        if not name or not raw_size:
            raise ExactNativeReplayError(f"invalid --window spec (want NAME:SIZE): {spec!r}")
        order.append(name)
        sizes[name] = None if raw_size.upper() == "FULL" else int(raw_size)
    return tuple(order), sizes


def _parse_expected_main_numbers(value: str | None) -> tuple[int, ...] | None:
    if value is None or not value.strip():
        return None
    return tuple(int(item) for item in value.split(","))


def _resolve_native_ticket_counts(value: list[int] | None) -> tuple[int, ...]:
    return DEFAULT_NATIVE_TICKET_COUNTS if not value else tuple(value)


def _resolve_window_specs(value: list[str] | None) -> list[str]:
    return value if value else list(_DEFAULT_WINDOW_SPECS)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def replay_biglotto_exact_native_command(
    run_id: Annotated[
        str, typer.Option("--run-id", help="Explicit run identity for evidence rows.")
    ],
    draw_authority_db: Annotated[
        Path,
        typer.Option(
            "--draw-authority-db",
            exists=True,
            dir_okay=False,
            help="Explicit, caller-verified read-only DRAW_DATA sqlite path.",
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir", help="Directory for target_evidence.jsonl and sealed_manifest.json."
        ),
    ],
    native_ticket_count: Annotated[
        list[int] | None,
        typer.Option(
            "--native-ticket-count", help="Repeatable; current canonical universe is 5, 10, 20."
        ),
    ] = None,
    max_visible_draw: Annotated[
        str,
        typer.Option("--max-visible-draw", help="Causal cutoff: draws after this are invisible."),
    ] = DEFAULT_MAX_VISIBLE_DRAW,
    expected_main_numbers: Annotated[
        str,
        typer.Option(
            "--expected-main-numbers",
            help="Comma-separated known-answer guard on the max-visible draw; empty to skip.",
        ),
    ] = ",".join(str(n) for n in DEFAULT_EXPECTED_MAIN_NUMBERS),
    expected_special_number: Annotated[
        int, typer.Option("--expected-special-number", help="Known-answer guard; -1 to skip.")
    ] = DEFAULT_EXPECTED_SPECIAL_NUMBER,
    window: Annotated[
        list[str] | None,
        typer.Option(
            "--window",
            help="Repeatable NAME:SIZE (SIZE=FULL or a positive int); order sets WINDOW_ORDER.",
        ),
    ] = None,
    shard_count: Annotated[
        int,
        typer.Option(
            "--shard-count", min=1, help="1 = single process; >1 = parallel subprocess shards."
        ),
    ] = 1,
) -> None:
    """Replay every current exact-native binding over the full visible target range."""

    try:
        native_ticket_counts = _resolve_native_ticket_counts(native_ticket_count)
        window_order, window_sizes = _parse_windows(_resolve_window_specs(window))
        expected_mains = _parse_expected_main_numbers(expected_main_numbers)
        expected_special = None if expected_special_number < 0 else expected_special_number

        if shard_count == 1:
            output_dir.mkdir(parents=True, exist_ok=True)
            request = ReplayTargetRangeRequest(
                run_id=run_id,
                draw_authority_db=draw_authority_db,
                repository_root=_repository_root(),
                output_path=output_dir / EVIDENCE_FILENAME,
                start_index=0,
                end_index=_total_visible_targets(
                    draw_authority_db, max_visible_draw, expected_mains, expected_special
                ),
                native_ticket_counts=native_ticket_counts,
                max_visible_draw=max_visible_draw,
                expected_main_numbers=expected_mains,
                expected_special_number=expected_special,
                window_order=window_order,
                window_sizes=window_sizes,
            )
            result = replay_exact_native_target_range(request)
            typer.echo(
                f"status=SEALED rows={result.actual_rows} bindings={result.binding_count} "
                f"evidence_sha256={result.evidence_sha256} output_dir={output_dir}"
            )
            return

        shard_request = ShardExactNativeReplayRequest(
            run_id=run_id,
            draw_authority_db=draw_authority_db,
            repository_root=_repository_root(),
            output_root=output_dir,
            shard_count=shard_count,
            native_ticket_counts=native_ticket_counts,
            max_visible_draw=max_visible_draw,
            expected_main_numbers=expected_mains,
            expected_special_number=expected_special,
            window_order=window_order,
            window_sizes=window_sizes,
        )
        shard_result = run_sharded_exact_native_replay(shard_request)
        typer.echo(
            f"status=SEALED rows={shard_result.total_rows} bindings={shard_result.binding_count} "
            f"evidence_sha256={shard_result.evidence_sha256} output_dir={output_dir}"
        )
    except (ExactNativeReplayError, ExactNativeReplayRuntimeError) as exc:
        _fail(str(exc))
    except OSError as exc:
        _fail(f"I/O error: {exc}")


def replay_biglotto_exact_native_shard_command(
    run_id: Annotated[
        str, typer.Option("--run-id", help="Explicit run identity for evidence rows.")
    ],
    draw_authority_db: Annotated[
        Path,
        typer.Option(
            "--draw-authority-db",
            exists=True,
            dir_okay=False,
            help="Explicit, caller-verified read-only DRAW_DATA sqlite path.",
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="This shard's own directory (target_evidence.jsonl, metadata.json).",
        ),
    ],
    start_index: Annotated[int, typer.Option("--start-index", min=0)],
    end_index: Annotated[int, typer.Option("--end-index", min=0)],
    native_ticket_count: Annotated[list[int] | None, typer.Option("--native-ticket-count")] = None,
    max_visible_draw: Annotated[str, typer.Option("--max-visible-draw")] = DEFAULT_MAX_VISIBLE_DRAW,
    expected_main_numbers: Annotated[str, typer.Option("--expected-main-numbers")] = ",".join(
        str(n) for n in DEFAULT_EXPECTED_MAIN_NUMBERS
    ),
    expected_special_number: Annotated[int, typer.Option("--expected-special-number")] = (
        DEFAULT_EXPECTED_SPECIAL_NUMBER
    ),
    window: Annotated[list[str] | None, typer.Option("--window")] = None,
) -> None:
    """Replay every current exact-native binding over one explicit ``[start, end)`` range.

    The standalone operational seam: callable directly by an operator, or
    invoked as a subprocess by the parallel shard orchestrator.
    """

    try:
        window_order, window_sizes = _parse_windows(_resolve_window_specs(window))
        expected_mains = _parse_expected_main_numbers(expected_main_numbers)
        expected_special = None if expected_special_number < 0 else expected_special_number

        output_dir.mkdir(parents=True, exist_ok=True)
        request = ReplayTargetRangeRequest(
            run_id=run_id,
            draw_authority_db=draw_authority_db,
            repository_root=_repository_root(),
            output_path=output_dir / EVIDENCE_FILENAME,
            start_index=start_index,
            end_index=end_index,
            native_ticket_counts=_resolve_native_ticket_counts(native_ticket_count),
            max_visible_draw=max_visible_draw,
            expected_main_numbers=expected_mains,
            expected_special_number=expected_special,
            window_order=window_order,
            window_sizes=window_sizes,
        )
        result = replay_exact_native_target_range(request)
        write_json_file(
            output_dir / METADATA_FILENAME,
            {
                "start_target_index": start_index,
                "end_target_index": end_index,
                "target_count": end_index - start_index,
                "binding_count": result.binding_count,
                "actual_rows": result.actual_rows,
                "expected_rows": result.expected_rows,
                "evidence_sha256": result.evidence_sha256,
                "evidence_byte_size": result.evidence_byte_size,
                "status_counts": dict(result.status_counts),
                "harness_head": result.source.get("head"),
                "harness_tree": result.source.get("tree"),
            },
        )
        typer.echo(
            f"status=SHARD_SEALED rows={result.actual_rows} "
            f"evidence_sha256={result.evidence_sha256}"
        )
    except (ExactNativeReplayError, ExactNativeReplayRuntimeError) as exc:
        _fail(str(exc))
    except OSError as exc:
        _fail(f"I/O error: {exc}")


def _total_visible_targets(
    draw_authority_db: Path,
    max_visible_draw: str,
    expected_main_numbers: tuple[int, ...] | None,
    expected_special_number: int | None,
) -> int:
    loaded_draws, _authority = load_authoritative_draws(draw_authority_db)
    visible = freeze_visible_draws(
        loaded_draws,
        max_visible_draw=max_visible_draw,
        expected_main_numbers=expected_main_numbers,
        expected_special_number=expected_special_number,
    )
    return len(visible)


def _fail(message: str) -> NoReturn:
    typer.echo(f"replay-biglotto-exact-native error: {message}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "replay_biglotto_exact_native_command",
    "replay_biglotto_exact_native_shard_command",
]
