"""Strict R2 coordinator for a fresh, serial, strategy-isolated 54 x 800 replay.

The public commands build a closed plan, execute one strategy per spawned
interpreter, and compare exactly two completed runs. Importing this module is
side-effect free: it never imports LottoLab, opens a database, creates an
output path, or launches a campaign.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from tools import next_draw_54_replay_r2_lib as c
from tools import next_draw_54_replay_r2_runtime as runtime

MODULE = "tools.next_draw_54_replay_r2"


@dataclass(frozen=True, slots=True)
class SpawnOutcome:
    """One whole-strategy child process and its complete combined output."""

    pid: int
    exit_status: int
    started_at_utc: str
    ended_at_utc: str
    elapsed_ns: int
    raw: bytes


LaunchOne = Callable[[str], SpawnOutcome]


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def child_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(c.ENVIRONMENT)
    environment["PYTHONPATH"] = str(runtime.RUNNER_ROOT)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def environment_ready() -> bool:
    return (
        sys.version_info[:2] == (3, 13)
        and all(os.environ.get(key) == value for key, value in c.ENVIRONMENT.items())
        and sys.flags.utf8_mode == 1
        and sys.flags.hash_randomization == 0
        and sys.flags.dont_write_bytecode == 1
        and sys.flags.no_user_site == 1
        and sys.flags.safe_path
        and os.environ.get("PYTHONPATH") == str(runtime.RUNNER_ROOT)
    )


def reexec_with_frozen_environment() -> None:
    """Exec this module once so every load-bearing setting predates imports."""
    c.require(sys.version_info[:2] == (3, 13), "the R2 runner requires CPython 3.13")
    if environment_ready():
        return
    argv = [sys.executable, "-B", "-s", "-P", "-m", MODULE, *sys.argv[1:]]
    os.execve(sys.executable, argv, child_environment())


def validate_concurrency(value: int) -> None:
    c.integer(value, "concurrency", minimum=1)
    c.equal(value, 1, "R2 is serial-only; concurrency must equal 1")


def validate_max_attempts(value: int) -> None:
    c.integer(value, "max attempts", minimum=1)


def load_plan(path: Path) -> tuple[dict[str, Any], bytes]:
    c.require(path.is_file() and not path.is_symlink(), "plan must be a regular non-symlink file")
    raw = path.read_bytes()
    return c.validate_plan(c.parse_file(raw)), raw


def write_new_manifest(path: Path, value: dict[str, Any]) -> Path:
    parent = path.parent.resolve(strict=True)
    c.require(parent.is_dir() and not path.parent.is_symlink(), "manifest parent directory")
    target = parent / path.name
    c.require(not target.exists() and not target.is_symlink(), "manifest output already exists")
    raw = c.file_bytes(value)
    with target.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    c.require(target.read_bytes() == raw, "written manifest bytes: mismatch")
    return target


def create_output_root(path: Path) -> Path:
    parent = path.parent.resolve(strict=True)
    c.require(parent.is_dir() and not path.parent.is_symlink(), "output-root parent directory")
    target = parent / path.name
    c.require(not target.exists() and not target.is_symlink(), "output root must be fresh")
    target.mkdir(mode=0o700)
    return target


def build_plan(source_root: Path, source_db: Path, output: Path) -> tuple[Path, dict[str, Any]]:
    source_root = source_root.resolve(strict=True)
    source_db = source_db.resolve(strict=True)
    authority = runtime.verify_source(source_root)
    snapshot, database_sha256, database_size = runtime.read_snapshot(source_db)
    catalog = source_root / "src/lottolab/strategies/catalog.py"
    strategies = c.strategy_manifest(catalog.read_bytes())
    fingerprint = runtime.capture_runtime(authority)
    plan = c.make_plan(
        authority=authority,
        dataset=c.dataset_manifest(snapshot, database_sha256, database_size),
        strategies=strategies,
        runtime=fingerprint,
    )
    c.validate_plan(plan)
    return write_new_manifest(output, plan), plan


def spawn_child(
    plan_path: Path,
    source_root: Path,
    source_db: Path,
    strategy_id: str,
) -> SpawnOutcome:
    """Launch one child with posix_spawn/exec and capture no reusable partial file."""
    c.require(hasattr(os, "posix_spawn"), "POSIX_SPAWN is required")
    c.string(strategy_id, "strategy id")
    read_fd, write_fd = os.pipe()
    argv = [
        sys.executable,
        "-B",
        "-s",
        "-P",
        "-m",
        MODULE,
        "_child",
        "--plan",
        str(plan_path),
        "--source-root",
        str(source_root),
        "--source-db",
        str(source_db),
        "--strategy-id",
        strategy_id,
    ]
    started_at = utc_now()
    started_ns = time.monotonic_ns()
    try:
        pid = os.posix_spawn(
            sys.executable,
            argv,
            child_environment(),
            file_actions=[
                (os.POSIX_SPAWN_DUP2, write_fd, 1),
                (os.POSIX_SPAWN_DUP2, write_fd, 2),
                (os.POSIX_SPAWN_CLOSE, read_fd),
                (os.POSIX_SPAWN_CLOSE, write_fd),
            ],
        )
    except BaseException:
        os.close(read_fd)
        os.close(write_fd)
        raise
    os.close(write_fd)
    status = 0
    try:
        with os.fdopen(read_fd, "rb") as stream:
            raw = stream.read()
    finally:
        _, status = os.waitpid(pid, 0)
    ended_ns = time.monotonic_ns()
    return SpawnOutcome(
        pid=pid,
        exit_status=os.waitstatus_to_exitcode(status),
        started_at_utc=started_at,
        ended_at_utc=utc_now(),
        elapsed_ns=ended_ns - started_ns,
        raw=raw,
    )


def _attempt_base(
    outcome: SpawnOutcome,
    *,
    attempt_id: str,
    strategy_id: str,
    ordinal: int,
    previous_attempt_id: str,
) -> dict[str, Any]:
    return {
        "attempt_id": attempt_id,
        "strategy_id": strategy_id,
        "ordinal": ordinal,
        "pid": outcome.pid,
        "started_at_utc": outcome.started_at_utc,
        "ended_at_utc": outcome.ended_at_utc,
        "elapsed_ns": outcome.elapsed_ns,
        "exit_status": outcome.exit_status,
        "previous_attempt_id": previous_attempt_id,
    }


def execute_strategy_with_restarts(
    plan: dict[str, Any],
    identity: dict[str, Any],
    *,
    run_id: str,
    strategy_index: int,
    max_attempts: int,
    launch: LaunchOne,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Accept only a complete child; every retry calls a new whole-child launcher."""
    validate_max_attempts(max_attempts)
    c.integer(strategy_index, "strategy index", minimum=1)
    c.equal(c.child_identity(plan, [identity["strategy_id"]]), identity, "strategy retry identity")
    attempts: list[dict[str, Any]] = []
    previous_attempt_id = ""
    for ordinal in range(1, max_attempts + 1):
        outcome = launch(identity["strategy_id"])
        attempt_id = f"{run_id}-{strategy_index:02d}-{ordinal:02d}"
        base = _attempt_base(
            outcome,
            attempt_id=attempt_id,
            strategy_id=identity["strategy_id"],
            ordinal=ordinal,
            previous_attempt_id=previous_attempt_id,
        )
        if outcome.exit_status == 0:
            try:
                child = c.validate_child_result(plan, identity, c.parse_file(outcome.raw))
            except (c.ProtocolError, ValueError):
                failure_kind = "CHILD_OUTPUT_PROTOCOL_ERROR"
            else:
                result = cast(dict[str, Any], child["result"])
                attempts.append(
                    {
                        **base,
                        "status": "SUCCEEDED",
                        "failure_kind": "",
                        "result_sha256": result["strategy_output_sha256"],
                        "partial_output_sha256": "",
                        "bootstrap_before_sha256": child["bootstrap_before_sha256"],
                        "bootstrap_after_sha256": child["bootstrap_after_sha256"],
                    }
                )
                return result, attempts
        else:
            failure_kind = "CHILD_EXIT_NONZERO"
        attempts.append(
            {
                **base,
                "status": "FAILED",
                "failure_kind": failure_kind,
                "result_sha256": "",
                "partial_output_sha256": c.sha256(outcome.raw) if outcome.raw else "",
                "bootstrap_before_sha256": "",
                "bootstrap_after_sha256": "",
            }
        )
        previous_attempt_id = attempt_id
    raise c.ProtocolError(
        f"{identity['strategy_id']}: whole-strategy attempts exhausted without complete output"
    )


def run_campaign(
    plan_path: Path,
    source_root: Path,
    source_db: Path,
    output_root: Path,
    campaign_label: str,
    *,
    max_attempts: int = 1,
    concurrency: int = 1,
) -> tuple[Path, dict[str, Any]]:
    validate_concurrency(concurrency)
    validate_max_attempts(max_attempts)
    c.string(campaign_label, "campaign label")
    plan_path = plan_path.resolve(strict=True)
    source_root = source_root.resolve(strict=True)
    source_db = source_db.resolve(strict=True)
    plan, _ = load_plan(plan_path)
    c.equal(plan["dataset"]["snapshot"]["kind"], c.REAL_DATA, "campaign requires sealed real data")
    authority = runtime.verify_source(source_root)
    c.equal(authority, plan["authority"], "coordinator source authority")
    runtime.verify_database(source_db, plan)
    c.equal(runtime.capture_runtime(authority), plan["runtime_fingerprint"], "coordinator runtime")

    with runtime.serial_lock():
        root = create_output_root(output_root)
        run_id = uuid.uuid4().hex
        started_at = utc_now()
        started_ns = time.monotonic_ns()
        results: list[dict[str, Any]] = []
        attempts: list[dict[str, Any]] = []
        for index, identity in enumerate(plan["strategies"]["records"], start=1):
            result, lineage = execute_strategy_with_restarts(
                plan,
                identity,
                run_id=run_id,
                strategy_index=index,
                max_attempts=max_attempts,
                launch=lambda strategy_id: spawn_child(
                    plan_path, source_root, source_db, strategy_id
                ),
            )
            results.append(result)
            attempts.extend(lineage)

        c.equal(runtime.verify_source(source_root), authority, "campaign source final integrity")
        runtime.verify_database(source_db, plan)
        c.equal(
            runtime.capture_runtime(authority),
            plan["runtime_fingerprint"],
            "campaign runtime final integrity",
        )
        ended_ns = time.monotonic_ns()
        operational = {
            "run_id": run_id,
            "output_root": str(root),
            "source_root": str(source_root),
            "source_db_path": str(source_db),
            "host_label": platform.node() or "UNKNOWN_HOST",
            "started_at_utc": started_at,
            "ended_at_utc": utc_now(),
            "elapsed_ns": ended_ns - started_ns,
            "attempts": attempts,
        }
        manifest = c.make_run(plan, results, operational, campaign_label)
        c.validate_run(plan, manifest)
        path = write_new_manifest(root / "run_manifest.json", manifest)
        return path, manifest


def build_acceptance(
    plan_path: Path,
    run_a_path: Path,
    run_b_path: Path,
    output: Path,
) -> tuple[Path, dict[str, Any]]:
    plan, _ = load_plan(plan_path.resolve(strict=True))
    run_a_bytes = run_a_path.resolve(strict=True).read_bytes()
    run_b_bytes = run_b_path.resolve(strict=True).read_bytes()
    acceptance = c.make_acceptance(plan, run_a_bytes, run_b_bytes)
    c.validate_acceptance(plan, acceptance, run_a_bytes, run_b_bytes)
    return write_new_manifest(output, acceptance), acceptance


def child_command(
    plan_path: Path,
    source_root: Path,
    source_db: Path,
    strategy_ids: list[str],
) -> int:
    plan, _ = load_plan(plan_path.resolve(strict=True))
    identity = c.child_identity(plan, strategy_ids)
    child = runtime.execute_native_child(
        plan,
        source_root.resolve(strict=True),
        source_db.resolve(strict=True),
        strategy_ids,
    )
    c.validate_child_result(plan, identity, child)
    sys.stdout.buffer.write(c.file_bytes(child))
    sys.stdout.buffer.flush()
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan", help="build a closed R2 Plan Manifest V2")
    plan.add_argument("--source-root", type=Path, required=True)
    plan.add_argument("--source-db", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)

    run = commands.add_parser("run", help="execute one serial, strategy-isolated campaign")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--source-root", type=Path, required=True)
    run.add_argument("--source-db", type=Path, required=True)
    run.add_argument("--output-root", type=Path, required=True)
    run.add_argument("--campaign-label", required=True)
    run.add_argument("--max-attempts", type=int, default=1)
    run.add_argument("--concurrency", type=int, default=1)

    acceptance = commands.add_parser(
        "acceptance", help="compare exactly two completed R2 campaigns"
    )
    acceptance.add_argument("--plan", type=Path, required=True)
    acceptance.add_argument("--run-a", type=Path, required=True)
    acceptance.add_argument("--run-b", type=Path, required=True)
    acceptance.add_argument("--output", type=Path, required=True)

    child = commands.add_parser("_child", help=argparse.SUPPRESS)
    child.add_argument("--plan", type=Path, required=True)
    child.add_argument("--source-root", type=Path, required=True)
    child.add_argument("--source-db", type=Path, required=True)
    child.add_argument("--strategy-id", action="append", required=True)
    return result


def _path_arg(args: argparse.Namespace, name: str) -> Path:
    return cast(Path, getattr(args, name))


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        reexec_with_frozen_environment()
        runtime.validate_environment()
    args = parser().parse_args(argv)
    command = cast(str, args.command)
    if command == "plan":
        path, manifest = build_plan(
            _path_arg(args, "source_root"),
            _path_arg(args, "source_db"),
            _path_arg(args, "output"),
        )
    elif command == "run":
        path, manifest = run_campaign(
            _path_arg(args, "plan"),
            _path_arg(args, "source_root"),
            _path_arg(args, "source_db"),
            _path_arg(args, "output_root"),
            cast(str, args.campaign_label),
            max_attempts=cast(int, args.max_attempts),
            concurrency=cast(int, args.concurrency),
        )
    elif command == "acceptance":
        path, manifest = build_acceptance(
            _path_arg(args, "plan"),
            _path_arg(args, "run_a"),
            _path_arg(args, "run_b"),
            _path_arg(args, "output"),
        )
    else:
        return child_command(
            _path_arg(args, "plan"),
            _path_arg(args, "source_root"),
            _path_arg(args, "source_db"),
            cast(list[str], args.strategy_id),
        )
    print(f"{path} {c.digest(manifest)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (c.ProtocolError, OSError, ValueError) as exc:
        print(f"R2 runner error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
