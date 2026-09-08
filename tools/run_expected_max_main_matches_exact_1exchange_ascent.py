"""Canonical guarded exact ascent: run --input JSON or inspect --input JSON.

BIG_LOTTO is fixed at 49/6. SYNTHETIC is explicitly test-only and limited to
pools of at most ten numbers. seed_portfolio is a starting portfolio, not RNG.
The foreground child owns computation and all raw persistence, even if its
wrapper disappears. Internal child arguments are not an alternative public API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import cast

CHECKOUT = Path(__file__).resolve().parents[1]
# Pin imports to this launcher checkout, including when invoked as a script.
sys.path[:0] = [str(CHECKOUT), str(CHECKOUT / "src")]

from lottolab.research.expected_max_main_matches_exact_1exchange_ascent import (  # noqa: E402
    METHOD_ID,
    iterative_exact_1exchange_expected_max_ascent,
    portfolio_sha256,
)
from lottolab.research.reference_e_exact_one_exchange_refinement import (  # noqa: E402
    Portfolio,
    canonicalize_portfolio,
)
from tools.task_execution_claim import (  # noqa: E402
    UNVERIFIABLE,
    ClaimError,
    ClaimStore,
    resolve_claim_root,
)

DRAW_MODEL = "UNIFORM_MAIN_WITHOUT_REPLACEMENT_V1"
SEMANTICS_ID = "EXACT_FULL_1EXCHANGE_STRICT_BEST_LEX_UNTIL_LOCAL_OPTIMUM_V1"
SUPPORTED_K = (2, 3, 5, 10, 20)
SOURCE_PATHS = (
    "tools/run_expected_max_main_matches_exact_1exchange_ascent.py",
    "tools/task_execution_claim.py",
    "src/lottolab/research/expected_max_main_matches_exact_1exchange_ascent.py",
    "src/lottolab/research/reference_e_exact_one_exchange_refinement.py",
    "src/lottolab/research/exact_coverage_fast_evaluator.py",
)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _integer(value: object, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return value


@dataclass(frozen=True, slots=True)
class Snapshot:
    lottery_id: str
    pool_size: int
    draw_size: int
    k: int
    seed_portfolio: Portfolio

    @property
    def canonical_input(self) -> dict[str, object]:
        return {"schema_version": 1, "method_id": METHOD_ID, **asdict(self)}

    @property
    def identity(self) -> dict[str, object]:
        return {
            "method_id": METHOD_ID,
            "lottery_id": self.lottery_id,
            "pool_size": self.pool_size,
            "draw_size": self.draw_size,
            "draw_model": DRAW_MODEL,
            "k": self.k,
            "seed_sha256": portfolio_sha256(self.seed_portfolio),
            "semantics_id": SEMANTICS_ID,
        }

    @property
    def h(self) -> str:
        return hashlib.sha256(_json(self.identity).encode("utf-8")).hexdigest()

    @property
    def task_key(self) -> str:
        return METHOD_ID + ":" + self.h

    @property
    def payload(self) -> str:
        return _json(self.canonical_input)


def validate_input(raw: object) -> Snapshot:
    if not isinstance(raw, dict):
        raise ValueError("Input must be a JSON object")
    data = cast(dict[str, object], raw)
    fields = {
        "schema_version",
        "method_id",
        "lottery_id",
        "pool_size",
        "draw_size",
        "k",
        "seed_portfolio",
    }
    if set(data) != fields:
        raise ValueError("Require exactly the JSON v1 fields")
    _integer(data["schema_version"], "schema_version", 1, 1)
    if data["method_id"] != METHOD_ID:
        raise ValueError("Unsupported method_id")
    pool = _integer(data["pool_size"], "pool_size", 2, 64)
    draw = _integer(data["draw_size"], "draw_size", 1, pool - 1)
    k = _integer(data["k"], "k", 2, 20)
    if k not in SUPPORTED_K or k >= math.comb(pool, draw):
        raise ValueError("Unsupported k or universe has no legal exchange")
    lottery = data["lottery_id"]
    if not isinstance(lottery, str):
        raise ValueError("lottery_id must be a string")
    if lottery == "BIG_LOTTO":
        if (pool, draw) != (49, 6):
            raise ValueError("BIG_LOTTO requires pool_size=49 and draw_size=6")
    elif lottery == "SYNTHETIC":
        if pool > 10:
            raise ValueError("SYNTHETIC is only for bounded tests (pool_size <= 10)")
    else:
        raise ValueError("Unsupported lottery_id")
    tickets = data["seed_portfolio"]
    if not isinstance(tickets, list) or len(cast(list[object], tickets)) != k:
        raise ValueError("k must equal the number of tickets")
    checked: list[tuple[int, ...]] = []
    for ticket in cast(list[object], tickets):
        if not isinstance(ticket, list) or len(cast(list[object], ticket)) != draw:
            raise ValueError("Each ticket must contain exactly draw_size numbers")
        numbers = tuple(_integer(n, "ticket number", 1, pool) for n in cast(list[object], ticket))
        if len(set(numbers)) != draw:
            raise ValueError("Duplicate numbers in ticket")
        checked.append(tuple(sorted(numbers)))
    if len(set(checked)) != k:
        raise ValueError("Duplicate tickets")
    return Snapshot(lottery, pool, draw, k, canonicalize_portfolio(checked))


def read_input(path: Path) -> Snapshot:
    # The only external input read. Children receive immutable argv bytes.
    return validate_input(json.loads(path.read_bytes(), object_pairs_hook=_unique_object))


def _command(snapshot: Snapshot, nonce: str, owner_pid: int, owner_cwd: str) -> list[str]:
    return [
        sys.executable,
        "-I",
        "-B",
        str(CHECKOUT / SOURCE_PATHS[0]),
        "_child",
        snapshot.payload,
        nonce,
        str(owner_pid),
        owner_cwd,
    ]


def _attempts_root(root: Path, snapshot: Snapshot) -> Path:
    return root.parent / "expected-max-exact-1exchange" / snapshot.h / "attempts"


def _verify_child(
    snapshot: Snapshot,
    nonce: str,
    owner_pid: int,
    owner_cwd: str,
) -> dict[str, object]:
    if str(uuid.UUID(nonce)) != nonce or not 0 < owner_pid <= 2**31 - 1:
        raise ClaimError("Invalid invocation identity")
    root = resolve_claim_root(CHECKOUT)
    state = ClaimStore(root).inspect(snapshot.task_key)
    if (
        state["status"] not in ("ACTIVE", "ACTIVE_ORPHAN_CHILD")
        or state.get("child_pid") != os.getpid()
        or state.get("owner_pid") != owner_pid
        or state.get("cwd") != owner_cwd
        or state.get("command") != _command(snapshot, nonce, owner_pid, owner_cwd)
        # macOS framework Python may re-exec with a different orig_argv[0].
        # sys.executable still identifies the requested venv interpreter above.
        or sys.orig_argv[1:] != _command(snapshot, nonce, owner_pid, owner_cwd)[1:]
        or state.get("claim_root") != str(root)
        or state.get("task_key") != snapshot.task_key
    ):
        raise ClaimError("Internal child has no matching active execution claim")
    return state


def _git(*args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(CHECKOUT), *args],
        env=env,
        text=True,
        stderr=subprocess.PIPE,
        timeout=10,
    ).strip()


def _provenance() -> dict[str, object]:
    status = _git("status", "--porcelain=v1", "--untracked-files=normal")
    return {
        "checkout": str(CHECKOUT),
        "source_commit": _git("rev-parse", "HEAD"),
        "source_tree": _git("rev-parse", "HEAD^{tree}"),
        "dirty": bool(status),
        "dirty_status": status,
        "source_sha256": {
            path: hashlib.sha256((CHECKOUT / path).read_bytes()).hexdigest()
            for path in SOURCE_PATHS
        },
        "python_executable": sys.executable,
        "python_version": sys.version,
    }


def _fraction_json(value: object) -> object:
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    raise TypeError(f"Unsupported result value: {type(value).__name__}")


def _atomic_json(destination: Path, value: object) -> None:
    temporary = destination.with_name("." + destination.name + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as target:
            json.dump(value, target, default=_fraction_json, sort_keys=True, ensure_ascii=True)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, destination)
        fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _child(snapshot: Snapshot, nonce: str, owner_pid: int, owner_cwd: str) -> int:
    state = _verify_child(snapshot, nonce, owner_pid, owner_cwd)
    root = resolve_claim_root(CHECKOUT)
    attempt = _attempts_root(root, snapshot) / str(state["owner_id"])
    if attempt != attempt.resolve():
        raise ClaimError("Raw output must not traverse symlinks")
    attempt.parent.mkdir(parents=True, exist_ok=True)
    attempt.mkdir()  # Never reuse or overwrite a previous attempt.
    common: dict[str, object] = {
        "schema_version": 1,
        "task_key": snapshot.task_key,
        "H": snapshot.h,
        "identity": snapshot.identity,
        "canonical_input": snapshot.canonical_input,
    }
    receipt: dict[str, object] = {
        **common,
        "claim_owner_id": state["owner_id"],
        "attempt_id": state["owner_id"],
        "invocation_id": nonce,
        "claim_root": str(root),
        "owner_pid": owner_pid,
        "child_pid": os.getpid(),
        "actual_executable_argv": list(sys.orig_argv),
        "guarded_executable_argv": state["command"],
        "started_at_utc": _now(),
        "successful_completion": False,
        "replay": {
            "input": snapshot.canonical_input,
            "argv": [
                sys.executable,
                str(CHECKOUT / SOURCE_PATHS[0]),
                "run",
                "--input",
                "<JSON containing replay.input>",
            ],
            "draw_model": DRAW_MODEL,
            "semantics_id": SEMANTICS_ID,
            "rng": "NONE",
            "resume": "NOT_IMPLEMENTED; restart from original seed",
        },
    }
    try:
        receipt["provenance"] = _provenance()
        _atomic_json(attempt / "input.json", common)
        result = iterative_exact_1exchange_expected_max_ascent(
            snapshot.pool_size,
            snapshot.draw_size,
            snapshot.seed_portfolio,
        )
        _atomic_json(attempt / "result.json", asdict(result))
        receipt.update(outcome="COMPLETED", successful_completion=True, ended_at_utc=_now())
        # This is the publication barrier: result file AND directory fsync precede success.
        _atomic_json(attempt / "receipt.json", receipt)
        return 0
    except Exception as exc:
        receipt.update(
            outcome="FAILED",
            successful_completion=False,
            ended_at_utc=_now(),
            error=f"{type(exc).__name__}: {exc}",
        )
        _atomic_json(attempt / "receipt.json", receipt)
        return 1


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if arguments[:1] == ["_child"]:
            if len(arguments) != 5:
                raise ClaimError("Invalid internal child invocation")
            snapshot = validate_input(json.loads(arguments[1], object_pairs_hook=_unique_object))
            if arguments[1] != snapshot.payload:
                raise ClaimError("Internal snapshot is not canonical")
            return _child(snapshot, arguments[2], int(arguments[3]), arguments[4])
        parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
        operations = parser.add_subparsers(dest="operation", required=True)
        for operation in ("run", "inspect"):
            sub = operations.add_parser(operation, allow_abbrev=False)
            sub.add_argument("--input", type=Path, required=True)
            if operation == "run":
                sub.add_argument("--takeover-stale", action="store_true")
        args = parser.parse_args(arguments)
        snapshot = read_input(args.input)
        root = resolve_claim_root(CHECKOUT)
        store = ClaimStore(root)
        if args.operation == "inspect":
            state = store.inspect(snapshot.task_key)
            print(
                _json(
                    {
                        **state,
                        "H": snapshot.h,
                        "identity": snapshot.identity,
                        "attempts_root": str(_attempts_root(root, snapshot)),
                    }
                )
            )
            return UNVERIFIABLE if state["status"] == "UNVERIFIABLE" else 0
        return store.run(
            snapshot.task_key,
            _command(snapshot, str(uuid.uuid4()), os.getpid(), str(Path.cwd())),
            takeover_stale=args.takeover_stale,
        )
    except (ClaimError, OSError, ValueError, OverflowError, subprocess.SubprocessError) as exc:
        print(_json({"status": "UNVERIFIABLE", "reason": str(exc)}), file=sys.stderr)
        return UNVERIFIABLE


if __name__ == "__main__":
    sys.exit(main())
