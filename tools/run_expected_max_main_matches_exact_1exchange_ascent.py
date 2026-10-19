"""Canonical guarded exact ascent: run --input JSON or inspect --input JSON.

BIG_LOTTO is fixed at 49/6. SYNTHETIC is explicitly test-only and limited to
pools of at most ten numbers. seed_portfolio is a starting portfolio, not RNG.
The foreground child owns computation and all raw persistence, even if its
wrapper disappears. Internal child arguments are not an alternative public API.
Resume uses run --input JSON --takeover-stale --resume-from DESCRIPTOR_JSON.
The descriptor freezes predecessor_attempt_id, sequence and checkpoint_id.
Only completed iterations are checkpointed. Saved rows are physically rescanned
for validation; terminal recovery performs no new scientific continuation scan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import subprocess
import sys
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import cast

CHECKOUT = Path(__file__).resolve().parents[1]
# Pin imports to this launcher checkout, including when invoked as a script.
sys.path[:0] = [str(CHECKOUT), str(CHECKOUT / "src")]

from lottolab.research.expected_max_main_matches_exact_1exchange_ascent import (  # noqa: E402
    METHOD_ID,
    ExpectedMaxAscentIteration,
    ExpectedMaxResumeState,
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
    Metadata,
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
COMPATIBILITY_PATHS = (
    *SOURCE_PATHS,
    "src/lottolab/__init__.py",
    "tools/__init__.py",
    "src/lottolab/research/__init__.py",
)
CHECKPOINT_FIELDS = {
    "schema_version",
    "task_key",
    "identity",
    "seed_portfolio",
    "attempt_id",
    "source_manifest",
    "sequence",
    "iterations",
    "created_at_utc",
    "checkpoint_id",
}
LINEAGE_FIELDS = {
    "schema_version",
    "task_key",
    "attempt_id",
    "resumed_from_attempt_id",
    "resumed_from_checkpoint_id",
    "resume_iteration",
}


def _json(value: object) -> str:
    return json.dumps(
        value,
        default=_fraction_json,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


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


@dataclass(frozen=True, slots=True)
class ResumeDescriptor:
    predecessor_attempt_id: str
    sequence: int
    checkpoint_id: str


def _object(raw: object, required: set[str]) -> dict[str, object]:
    if not isinstance(raw, dict) or set(cast(dict[str, object], raw)) != required:
        raise ValueError("Unexpected or missing JSON fields")
    return cast(dict[str, object], raw)


def _uuid(value: object) -> str:
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError("Invalid attempt UUID")
    return value


def _digest(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("Invalid SHA-256")
    return value


def _descriptor(raw: object) -> ResumeDescriptor:
    data = _object(raw, {"predecessor_attempt_id", "sequence", "checkpoint_id"})
    return ResumeDescriptor(
        _uuid(data["predecessor_attempt_id"]),
        _integer(data["sequence"], "sequence", 1, 2**31 - 1),
        _digest(data["checkpoint_id"]),
    )


def _command(
    snapshot: Snapshot,
    nonce: str,
    owner_pid: int,
    owner_cwd: str,
    resume: ResumeDescriptor | None = None,
) -> list[str]:
    command = [
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
    if resume is not None:
        command.append(_json(asdict(resume)))
    return command


def _attempts_root(root: Path, snapshot: Snapshot) -> Path:
    return root.parent / "expected-max-exact-1exchange" / snapshot.h / "attempts"


def _verify_child(
    snapshot: Snapshot,
    nonce: str,
    owner_pid: int,
    owner_cwd: str,
    resume: ResumeDescriptor | None = None,
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
        or state.get("command") != _command(snapshot, nonce, owner_pid, owner_cwd, resume)
        # macOS framework Python may re-exec with a different orig_argv[0].
        # sys.executable still identifies the requested venv interpreter above.
        or sys.orig_argv[1:] != _command(snapshot, nonce, owner_pid, owner_cwd, resume)[1:]
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
    _safe_path(destination)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            target.write(_json(value) + "\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, destination)
        _sync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_path(path: Path) -> None:
    if not path.is_absolute() or path != path.resolve():
        raise ClaimError("Unsafe path: raw state must not traverse symlinks")


def _sync_directory(path: Path) -> None:
    _safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _read_bytes(path: Path) -> bytes:
    _safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink not in (0, 1):
            raise ClaimError("Unsafe raw state file")
        data = source.read(16 * 1024 * 1024 + 1)
    if len(data) > 16 * 1024 * 1024:
        raise ClaimError("Oversized raw state file")
    return data


def _read_json(path: Path) -> object:
    def reject_number(value: str) -> object:
        raise ValueError(f"Non-integer JSON number: {value}")

    return json.loads(
        _read_bytes(path),
        object_pairs_hook=_unique_object,
        parse_float=reject_number,
        parse_constant=reject_number,
    )


def _source_manifest() -> dict[str, str]:
    modules = {
        __name__: SOURCE_PATHS[0],
        "tools.task_execution_claim": SOURCE_PATHS[1],
        "lottolab.research.expected_max_main_matches_exact_1exchange_ascent": SOURCE_PATHS[2],
        "lottolab.research.reference_e_exact_one_exchange_refinement": SOURCE_PATHS[3],
        "lottolab.research.exact_coverage_fast_evaluator": SOURCE_PATHS[4],
        "lottolab": "src/lottolab/__init__.py",
        "tools": "tools/__init__.py",
    }
    for name, rel in modules.items():
        module = sys.modules.get(name)
        if module is None or getattr(module, "__file__", None) != str(CHECKOUT / rel):
            raise ClaimError(f"Imported source authority mismatch: {name}")
    for name, directory in (
        ("lottolab", "src/lottolab"),
        ("tools", "tools"),
        ("lottolab.research", "src/lottolab/research"),
    ):
        if list(getattr(sys.modules[name], "__path__", [])) != [str(CHECKOUT / directory)]:
            raise ClaimError(f"Imported package authority mismatch: {name}")
    manifest: dict[str, str] = {}
    for rel in COMPATIBILITY_PATHS:
        try:
            manifest[rel] = hashlib.sha256(_read_bytes(CHECKOUT / rel)).hexdigest()
        except FileNotFoundError:
            if rel != "src/lottolab/research/__init__.py":
                raise
            manifest[rel] = "ABSENT"
    research_origin = getattr(sys.modules["lottolab.research"], "__file__", None)
    expected_origin = (
        None
        if manifest[COMPATIBILITY_PATHS[-1]] == "ABSENT"
        else str(CHECKOUT / COMPATIBILITY_PATHS[-1])
    )
    if research_origin != expected_origin:
        raise ClaimError("Imported research package authority mismatch")
    return manifest


def _common(snapshot: Snapshot) -> dict[str, object]:
    return {
        "schema_version": 1,
        "task_key": snapshot.task_key,
        "H": snapshot.h,
        "identity": snapshot.identity,
        "canonical_input": snapshot.canonical_input,
    }


def _lineage(
    snapshot: Snapshot, attempt_id: str, resume: ResumeDescriptor | None
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "task_key": snapshot.task_key,
        "attempt_id": attempt_id,
        "resumed_from_attempt_id": None if resume is None else resume.predecessor_attempt_id,
        "resumed_from_checkpoint_id": None if resume is None else resume.checkpoint_id,
        "resume_iteration": 0 if resume is None else resume.sequence,
    }


def _create_attempt(attempt: Path, snapshot: Snapshot, resume: ResumeDescriptor | None) -> None:
    _safe_path(attempt)
    missing: list[Path] = []
    parent = attempt.parent
    while not parent.exists():
        _safe_path(parent)
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir()
        _sync_directory(directory.parent)
    attempt.mkdir()  # Never adopt or overwrite an existing attempt.
    _sync_directory(attempt.parent)
    _atomic_json(attempt / "input.json", _common(snapshot))
    _atomic_json(attempt / "lineage.json", _lineage(snapshot, attempt.name, resume))


def _checkpoint(
    snapshot: Snapshot,
    attempt_id: str,
    manifest: dict[str, str],
    iterations: tuple[ExpectedMaxAscentIteration, ...],
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": 1,
        "task_key": snapshot.task_key,
        "identity": snapshot.identity,
        "seed_portfolio": snapshot.seed_portfolio,
        "attempt_id": attempt_id,
        "source_manifest": manifest,
        "sequence": len(iterations),
        "iterations": [asdict(row) for row in iterations],
        "created_at_utc": _now(),
    }
    return {**body, "checkpoint_id": hashlib.sha256(_json(body).encode()).hexdigest()}


def _fraction(raw: object) -> Fraction:
    data = _object(raw, {"numerator", "denominator"})
    numerator, denominator = data["numerator"], data["denominator"]
    if type(numerator) is not int or type(denominator) is not int or denominator <= 0:
        raise ValueError("Invalid exact Fraction")
    if math.gcd(numerator, denominator) != 1:
        raise ValueError("Fraction must be reduced")
    return Fraction(numerator, denominator)


def _portfolio(raw: object, snapshot: Snapshot) -> Portfolio:
    parsed = validate_input({**snapshot.canonical_input, "seed_portfolio": raw})
    if _json(raw) != _json(parsed.seed_portfolio):
        raise ValueError("Noncanonical checkpoint portfolio")
    return parsed.seed_portfolio


def _rows(raw: object, snapshot: Snapshot) -> tuple[ExpectedMaxAscentIteration, ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("Checkpoint needs complete iteration rows")
    rows: list[ExpectedMaxAscentIteration] = []
    for raw_row in cast(list[object], raw):
        row = _object(raw_row, {field.name for field in fields(ExpectedMaxAscentIteration)})
        if type(row["accepted_move"]) is not bool:
            raise ValueError("Invalid accepted_move")
        rows.append(
            ExpectedMaxAscentIteration(
                iteration_index=_integer(row["iteration_index"], "iteration_index", 0, 2**31 - 1),
                input_portfolio=_portfolio(row["input_portfolio"], snapshot),
                input_expected_max=_fraction(row["input_expected_max"]),
                unique_legal_neighbor_count=_integer(
                    row["unique_legal_neighbor_count"], "neighbor count", 1, 2**31 - 1
                ),
                best_neighbor_portfolio=_portfolio(row["best_neighbor_portfolio"], snapshot),
                best_neighbor_expected_max=_fraction(row["best_neighbor_expected_max"]),
                delta=_fraction(row["delta"]),
                accepted_move=row["accepted_move"],
            )
        )
    return tuple(rows)


def _checkpoint_structure(
    attempt: Path,
    snapshot: Snapshot,
    manifest: dict[str, str],
) -> tuple[dict[str, object], tuple[ExpectedMaxAscentIteration, ...]]:
    raw = _object(_read_json(attempt / "checkpoint.json"), CHECKPOINT_FIELDS)
    digest = _digest(raw["checkpoint_id"])
    body = {key: value for key, value in raw.items() if key != "checkpoint_id"}
    if hashlib.sha256(_json(body).encode()).hexdigest() != digest:
        raise ValueError("Checkpoint checksum mismatch")
    _integer(raw["schema_version"], "schema_version", 1, 1)
    if (
        raw["task_key"] != snapshot.task_key
        or _json(raw["identity"]) != _json(snapshot.identity)
        or _portfolio(raw["seed_portfolio"], snapshot) != snapshot.seed_portfolio
        or _uuid(raw["attempt_id"]) != attempt.name
        or raw["source_manifest"] != manifest
    ):
        raise ValueError("Checkpoint identity, seed or source manifest mismatch")
    stamp = raw["created_at_utc"]
    if not isinstance(stamp, str) or datetime.fromisoformat(stamp).utcoffset() != UTC.utcoffset(
        None
    ):
        raise ValueError("Checkpoint timestamp must be UTC")
    rows = _rows(raw["iterations"], snapshot)
    if _integer(raw["sequence"], "sequence", 1, 2**31 - 1) != len(rows):
        raise ValueError("Checkpoint sequence/trace mismatch")
    return raw, rows


def _validate_lineage(attempt: Path, snapshot: Snapshot, sequence: int) -> dict[str, object]:
    first: dict[str, object] | None = None
    visited: set[str] = set()
    while True:
        if attempt.name in visited:
            raise ValueError("Cyclic attempt lineage")
        visited.add(attempt.name)
        if _json(_read_json(attempt / "input.json")) != _json(_common(snapshot)):
            raise ValueError("Attempt input mismatch")
        lineage = _object(_read_json(attempt / "lineage.json"), LINEAGE_FIELDS)
        _integer(lineage["schema_version"], "schema_version", 1, 1)
        if lineage["task_key"] != snapshot.task_key or _uuid(lineage["attempt_id"]) != attempt.name:
            raise ValueError("Lineage identity mismatch")
        if first is None:
            first = lineage
        start = _integer(lineage["resume_iteration"], "resume_iteration", 0, sequence)
        predecessor = lineage["resumed_from_attempt_id"]
        if predecessor is None:
            if start != 0 or lineage["resumed_from_checkpoint_id"] is not None:
                raise ValueError("Malformed fresh lineage")
            return first
        predecessor = _uuid(predecessor)
        if start == 0 or predecessor == attempt.name:
            raise ValueError("Malformed resume lineage")
        expected_digest = _digest(lineage["resumed_from_checkpoint_id"])
        attempt = attempt.parent / predecessor
        # R1 retains ancestor checkpoints; no background pruning or latest pointer.
        raw = _object(_read_json(attempt / "checkpoint.json"), CHECKPOINT_FIELDS)
        body = {key: value for key, value in raw.items() if key != "checkpoint_id"}
        if (
            raw["checkpoint_id"] != expected_digest
            or hashlib.sha256(_json(body).encode()).hexdigest() != expected_digest
            or raw["sequence"] != start
            or raw["task_key"] != snapshot.task_key
            or raw["attempt_id"] != predecessor
        ):
            raise ValueError("Predecessor lineage/checkpoint mismatch")
        sequence = start


def _validation_record(descriptor: ResumeDescriptor, attempt_id: str) -> dict[str, object]:
    return {
        "work_class": "VALIDATION_RESCAN",
        "checkpoint_id": descriptor.checkpoint_id,
        "attempt_id": attempt_id,
        "iteration_indices": [],
        "completed_scan_count": 0,
        "physical_neighbor_evaluations": 0,
        "outcome": "IN_PROGRESS",
    }


def _load_resume(
    attempt: Path,
    snapshot: Snapshot,
    manifest: dict[str, str],
    report: dict[str, object],
    selection: ResumeDescriptor | None = None,
) -> ExpectedMaxResumeState:
    try:
        raw, rows = _checkpoint_structure(attempt, snapshot, manifest)
        if selection is not None and (
            attempt.name != selection.predecessor_attempt_id
            or raw["sequence"] != selection.sequence
            or raw["checkpoint_id"] != selection.checkpoint_id
        ):
            raise ValueError("Checkpoint selection changed; select again explicitly")
        _validate_lineage(attempt, snapshot, len(rows))
        report["checkpoint_id"] = raw["checkpoint_id"]
        report["source_manifest_id"] = hashlib.sha256(_json(manifest).encode()).hexdigest()

        def observed(index: int, count: int) -> None:
            cast(list[int], report["iteration_indices"]).append(index)
            report["completed_scan_count"] = cast(int, report["completed_scan_count"]) + 1
            report["physical_neighbor_evaluations"] = (
                cast(int, report["physical_neighbor_evaluations"]) + count
            )

        state = ExpectedMaxResumeState(
            snapshot.pool_size, snapshot.draw_size, snapshot.seed_portfolio, rows, observed
        )
        report["outcome"] = "PASSED"
        return state
    except Exception:
        report["outcome"] = "FAILED"
        raise


def _completion_guard(attempt: Path, snapshot: Snapshot, state: ExpectedMaxResumeState) -> None:
    try:
        raw = _read_json(attempt / "receipt.json")
    except FileNotFoundError:
        return
    if not isinstance(raw, dict):
        raise ValueError("Malformed completion receipt")
    receipt = cast(dict[str, object], raw)
    if (
        receipt.get("task_key") != snapshot.task_key
        or receipt.get("attempt_id") != attempt.name
        or receipt.get("claim_owner_id") != attempt.name
        or type(receipt.get("successful_completion")) is not bool
    ):
        raise ValueError("Contradictory completion receipt")
    if receipt["successful_completion"] is False:
        if receipt.get("outcome") not in ("FAILED", "PREPARED"):
            raise ValueError("Contradictory completion receipt")
        return
    if state.iterations[-1].accepted_move or receipt.get("outcome") != "COMPLETED":
        raise ValueError("Contradictory successful completion")
    result = iterative_exact_1exchange_expected_max_ascent(
        snapshot.pool_size, snapshot.draw_size, snapshot.seed_portfolio, resume_state=state
    )
    if _json(_read_json(attempt / "result.json")) != _json(asdict(result)):
        raise ValueError("Contradictory successful completion result")
    raise ClaimError("ALREADY_COMPLETE")


def _prepare_resume(
    root: Path,
    snapshot: Snapshot,
    selection: ResumeDescriptor,
) -> Callable[[Metadata, Metadata], None]:
    def prepare(predecessor: Metadata, successor: Metadata) -> None:
        report = _validation_record(selection, successor["owner_id"])
        try:
            if predecessor["owner_id"] != selection.predecessor_attempt_id:
                raise ClaimError("Expected predecessor mismatch")
            manifest = _source_manifest()
            previous = _attempts_root(root, snapshot) / predecessor["owner_id"]
            state = _load_resume(previous, snapshot, manifest, report, selection)
            _completion_guard(previous, snapshot, state)
            attempt = previous.parent / successor["owner_id"]
            _create_attempt(attempt, snapshot, selection)
            _atomic_json(
                attempt / "checkpoint.json",
                _checkpoint(snapshot, attempt.name, manifest, state.iterations),
            )
            _atomic_json(
                attempt / "receipt.json",
                {
                    "schema_version": 1,
                    "task_key": snapshot.task_key,
                    "attempt_id": attempt.name,
                    "claim_owner_id": attempt.name,
                    "successful_completion": False,
                    "outcome": "PREPARED",
                    "validation": [report],
                },
            )
            _sync_directory(attempt)
            _sync_directory(attempt.parent)
        except Exception as exc:
            raise ClaimError(_json({"reason": str(exc), "validation": report})) from exc

    return prepare


def _child(
    snapshot: Snapshot,
    nonce: str,
    owner_pid: int,
    owner_cwd: str,
    resume: ResumeDescriptor | None = None,
) -> int:
    state = _verify_child(snapshot, nonce, owner_pid, owner_cwd, resume)
    root = resolve_claim_root(CHECKOUT)
    attempt = _attempts_root(root, snapshot) / str(state["owner_id"])
    _safe_path(attempt)
    if resume is None:
        _create_attempt(attempt, snapshot, None)
    common = _common(snapshot)
    validation: list[dict[str, object]] = []
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
        "validation": validation,
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
            "resume": "COMPLETED_ITERATIONS_V1; explicit stale predecessor required",
        },
    }
    try:
        receipt["provenance"] = _provenance()
        manifest = _source_manifest()
        receipt["source_manifest"] = manifest
        resume_state: ExpectedMaxResumeState | None = None
        if resume is not None:
            if _json(_read_json(attempt / "lineage.json")) != _json(
                _lineage(snapshot, attempt.name, resume)
            ):
                raise ClaimError("Successor lineage does not match guarded resume descriptor")
            prepared = cast(dict[str, object], _read_json(attempt / "receipt.json"))
            if prepared.get("outcome") != "PREPARED" or prepared.get("attempt_id") != attempt.name:
                raise ClaimError("Successor lacks prepared provenance")
            validation.extend(cast(list[dict[str, object]], prepared["validation"]))
            report = _validation_record(resume, attempt.name)
            validation.append(report)
            resume_state = _load_resume(attempt, snapshot, manifest, report)
            if len(resume_state.iterations) != resume.sequence:
                raise ClaimError("Successor inherited sequence mismatch")

        def checkpoint(rows: tuple[ExpectedMaxAscentIteration, ...]) -> None:
            _atomic_json(
                attempt / "checkpoint.json", _checkpoint(snapshot, attempt.name, manifest, rows)
            )

        result = iterative_exact_1exchange_expected_max_ascent(
            snapshot.pool_size,
            snapshot.draw_size,
            snapshot.seed_portfolio,
            resume_state=resume_state,
            on_completed_iteration=checkpoint,
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
            if len(arguments) not in (5, 6):
                raise ClaimError("Invalid internal child invocation")
            snapshot = validate_input(json.loads(arguments[1], object_pairs_hook=_unique_object))
            if arguments[1] != snapshot.payload:
                raise ClaimError("Internal snapshot is not canonical")
            resume = (
                None
                if len(arguments) == 5
                else _descriptor(json.loads(arguments[5], object_pairs_hook=_unique_object))
            )
            if resume is not None and arguments[5] != _json(asdict(resume)):
                raise ClaimError("Internal resume descriptor is not canonical")
            return _child(snapshot, arguments[2], int(arguments[3]), arguments[4], resume)
        parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
        operations = parser.add_subparsers(dest="operation", required=True)
        for operation in ("run", "inspect"):
            sub = operations.add_parser(operation, allow_abbrev=False)
            sub.add_argument("--input", type=Path, required=True)
            if operation == "run":
                sub.add_argument("--takeover-stale", action="store_true")
                sub.add_argument("--resume-from", type=Path)
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
        resume = (
            None
            if args.resume_from is None
            else _descriptor(_read_json(args.resume_from.absolute()))
        )
        command = _command(snapshot, str(uuid.uuid4()), os.getpid(), str(Path.cwd()), resume)
        if resume is not None:
            return store.run(
                snapshot.task_key,
                command,
                takeover_stale=args.takeover_stale,
                expected_predecessor_owner_id=resume.predecessor_attempt_id,
                prepare_takeover=_prepare_resume(root, snapshot, resume),
            )
        return store.run(
            snapshot.task_key,
            command,
            takeover_stale=args.takeover_stale,
        )
    except (ClaimError, OSError, ValueError, OverflowError, subprocess.SubprocessError) as exc:
        print(_json({"status": "UNVERIFIABLE", "reason": str(exc)}), file=sys.stderr)
        return UNVERIFIABLE


if __name__ == "__main__":
    sys.exit(main())
