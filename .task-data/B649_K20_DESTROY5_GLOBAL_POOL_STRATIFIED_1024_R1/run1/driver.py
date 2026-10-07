from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import itertools
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TASK_ID = "B649_K20_DESTROY5_GLOBAL_POOL_STRATIFIED_1024_R1"
EXECUTION_ID = "run1"
REUSE_COMMIT = "b470fbfd2eae74bc3c567408746951a8f27c306a"
START_COMMIT = "3655b0f4bc43450748b4fc87c641d0acd11a8509"
START_ARTIFACT = (
    "docs/research/matrix-native-results/"
    "b649-k20-three-ticket-cycle-full-family-r1-result.json"
)
PROMOTION_ARTIFACT = (
    "docs/research/matrix-native-results/"
    "b649-k20-r2-start-incumbent-promotion-r1.json"
)
RESULT_RELATIVE_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-destroy5-global-pool-stratified-1024-r1-result.json"
)
CHECKPOINT_INTERVAL = 25
EXPECTED_START_COUNT = 313239661
EXPECTED_START_SHA256 = (
    "7ce41ff21d5c0821f1d5dda683e23114086f5024fc6d98d4e574df5306659b1e"
)
EXPECTED_TOTAL_TICKETS = 13_983_816
DESTROY_SIZE = 5
FROZEN_TICKET_COUNT = 20 - DESTROY_SIZE
TOTAL_POSSIBLE_SETS = math.comb(20, DESTROY_SIZE)
EXPECTED_DESTROY_SETS = 1024
SAMPLE_SEED = 20261002
# the manifest was frozen (read-only) before any scoring; these pin its exact bytes
FROZEN_MANIFEST_FILE_SHA256 = (
    "6aeefa64d3d5f64e31fb91cbed5c3deff0a4fd322e5e8326bd5ed37bd787e3b8"
)
FROZEN_MANIFEST_DIGEST = (
    "693c1eeb3eed3e81de3e87c6e82c4af7711a29365d67ef843d939ee0bf646a7f"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write(path: Path, payload: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.tmp.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        finally:
            raise


def atomic_create_or_match(path: Path, payload: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode
        )
    except FileExistsError:
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"result path is not a regular file: {path}")
        if path.read_bytes() != payload:
            raise RuntimeError(f"refusing to replace a different result: {path}")
        return
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        fsync_directory(path.parent)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def append_fsync(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("append made no forward progress")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[bytes]]:
    if not path.exists():
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.fsync(descriptor)
        os.close(descriptor)
        fsync_directory(path.parent)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"journal is not a regular file: {path}")
    raw = path.read_bytes()
    final_newline = raw.rfind(b"\n") + 1
    if final_newline != len(raw):
        # An interrupted append without its newline is not a completed set.
        with path.open("r+b") as stream:
            stream.truncate(final_newline)
            stream.flush()
            os.fsync(stream.fileno())
        raw = raw[:final_newline]
    lines = raw.splitlines(keepends=True)
    records: list[dict[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        if not line.endswith(b"\n"):
            raise RuntimeError(f"unterminated journal line {number}: {path}")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError(f"journal line {number} is not an object: {path}")
        records.append(value)
    return records, lines


def git_output(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def require_regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"expected regular file: {path}")


def load_result_semantics(repo_root: Path) -> Any:
    source_root = repo_root / "src"
    helper_path = source_root / (
        "lottolab/research/b649_k20_destroy5_result_semantics.py"
    )
    require_regular(helper_path)
    module_name = "_b649_k20_destroy5_result_semantics"
    semantics = sys.modules.get(module_name)
    if semantics is None:
        spec = importlib.util.spec_from_file_location(module_name, helper_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Destroy5 result semantics module cannot be loaded")
        semantics = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = semantics
        spec.loader.exec_module(semantics)
    if Path(semantics.__file__).resolve() != helper_path.resolve():
        raise RuntimeError("Destroy5 result semantics import escaped the repository source")
    if semantics.FROZEN_START_COUNT != EXPECTED_START_COUNT:
        raise RuntimeError("Destroy5 result helper disagrees with the frozen START count")
    return semantics


def incumbent_authority_state_fields(authority: Any, semantics: Any) -> dict[str, Any]:
    fields = semantics.execution_authority_fields(authority)
    return {
        "CURRENT_VERIFIED_INCUMBENT_COUNT": fields[
            "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_COUNT"
        ],
        "CURRENT_VERIFIED_INCUMBENT_SHA256": fields[
            "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_SHA256"
        ],
        "CURRENT_INCUMBENT_AUTHORITY_LOCATOR": fields[
            "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_ARTIFACT_LOCATOR"
        ],
        "CURRENT_VERIFIED_INCUMBENT_SOURCE_COMMIT": fields[
            "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_SOURCE_COMMIT"
        ],
    }


def incumbent_authority_from_state(state: dict[str, Any], semantics: Any) -> Any:
    required = (
        "CURRENT_VERIFIED_INCUMBENT_COUNT",
        "CURRENT_VERIFIED_INCUMBENT_SHA256",
        "CURRENT_INCUMBENT_AUTHORITY_LOCATOR",
        "CURRENT_VERIFIED_INCUMBENT_SOURCE_COMMIT",
    )
    if any(key not in state for key in required):
        raise RuntimeError("resume state lacks persisted launch-time incumbent authority")
    authority = semantics.IncumbentAuthority(
        count=state["CURRENT_VERIFIED_INCUMBENT_COUNT"],
        sha256=state["CURRENT_VERIFIED_INCUMBENT_SHA256"],
        artifact_locator=state["CURRENT_INCUMBENT_AUTHORITY_LOCATOR"],
        source_commit=state["CURRENT_VERIFIED_INCUMBENT_SOURCE_COMMIT"],
    )
    expected = incumbent_authority_state_fields(authority, semantics)
    if any(state.get(key) != value for key, value in expected.items()):
        raise RuntimeError("resume incumbent authority is invalid")
    return authority


def classify_candidate_fields(
    count: int, authority: Any, semantics: Any
) -> dict[str, Any]:
    return semantics.classify_candidate(count, authority)


def classify_set_result(
    row: dict[str, Any], authority: Any, semantics: Any
) -> dict[str, Any]:
    fields = classify_candidate_fields(int(row["BEST_COUNT"]), authority, semantics)
    if row.get("BEST_DELTA") != fields["DELTA_FROM_FROZEN_START"]:
        raise RuntimeError("set BEST_DELTA differs from the frozen START classification")
    if (
        "CURRENT_VERIFIED_INCUMBENT_COUNT" in row
        and row["CURRENT_VERIFIED_INCUMBENT_COUNT"] != authority.count
    ):
        raise RuntimeError("set result uses a different launch-time incumbent")
    for key, value in fields.items():
        if key in row and row[key] != value:
            raise RuntimeError(f"set result classification mismatch at {key}")
    row.update(fields)
    row["CURRENT_VERIFIED_INCUMBENT_COUNT"] = authority.count
    return row


def record_set_result(
    row: dict[str, Any],
    journal_path: Path,
    authority: Any,
    semantics: Any,
) -> bytes:
    classify_set_result(row, authority, semantics)
    encoded = canonical_json(row)
    append_fsync(journal_path, encoded)
    return encoded


def terminal_result_fields(
    best_count: int, authority: Any, semantics: Any
) -> dict[str, Any]:
    fields = classify_candidate_fields(best_count, authority, semantics)
    global_gain = fields["GLOBAL_STRICT_GAIN"] == "YES"
    return {
        **fields,
        "STRICT_GAIN": global_gain,
        "SCIENTIFIC_RESULT": (
            "IMPROVED_VS_CURRENT_VERIFIED_INCUMBENT"
            if global_gain
            else "NO_GLOBAL_IMPROVEMENT_IN_STRATIFIED_DESTROY5_GLOBAL_POOL_CAMPAIGN"
        ),
    }


def load_manifest(run_root: Path, portfolio: tuple[tuple[int, ...], ...]) -> dict[str, Any]:
    """The frozen destroy-set manifest, verified byte-for-byte and re-derived from the START."""

    manifest_path = run_root / "destroy-sets-frozen.json"
    require_regular(manifest_path)
    raw = manifest_path.read_bytes()
    if sha256_bytes(raw) != FROZEN_MANIFEST_FILE_SHA256:
        raise RuntimeError("frozen destroy-set manifest bytes differ from the pinned digest")
    manifest = json.loads(raw)
    sys.path.insert(0, str(run_root))
    import stratify

    stratify.verify_manifest_digest(manifest)
    if manifest.get("MANIFEST_SHA256") != FROZEN_MANIFEST_DIGEST:
        raise RuntimeError("frozen destroy-set manifest digest is not the pinned one")
    # the sample must be reproducible from the START alone (no outcome information)
    rederived = stratify.derive_manifest(portfolio)
    if canonical_json(rederived) != raw:
        raise RuntimeError("manifest is not the deterministic function of the START portfolio")
    sets = manifest["SETS"]
    positions = [tuple(int(i) for i in row["DESTROY_INDICES"]) for row in sets]
    if (
        manifest.get("TASK_ID") != TASK_ID
        or manifest.get("SEED") != SAMPLE_SEED
        or manifest.get("SAMPLE_COUNT") != EXPECTED_DESTROY_SETS
        or manifest.get("TOTAL_POSSIBLE") != TOTAL_POSSIBLE_SETS
        or manifest.get("DESTROY_SIZE") != DESTROY_SIZE
        or len(sets) != EXPECTED_DESTROY_SETS
        or len(set(positions)) != EXPECTED_DESTROY_SETS
        or [row["ORDER"] for row in sets] != list(range(1, EXPECTED_DESTROY_SETS + 1))
        or any(
            len(p) != DESTROY_SIZE
            or tuple(sorted(set(p))) != p
            or p[0] < 0
            or p[-1] > 19
            for p in positions
        )
        or sum(row["ALLOCATED"] for row in manifest["STRATA"]) != EXPECTED_DESTROY_SETS
    ):
        raise RuntimeError("frozen destroy-set manifest is not the authorized 1024-set sample")
    return manifest


def load_frozen_inputs(
    run_root: Path, repo_root: Path
) -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
    start_path = run_root / "start.json"
    reuse_path = run_root / "engine/reuse-manifest.json"
    require_regular(start_path)
    require_regular(reuse_path)
    start_doc = json.loads(start_path.read_text(encoding="utf-8"))
    reuse_doc = json.loads(reuse_path.read_text(encoding="utf-8"))
    if (
        start_doc.get("TASK_ID") != TASK_ID
        or start_doc.get("START_SOURCE_COMMIT") != START_COMMIT
        or start_doc.get("START_SOURCE_ARTIFACT") != START_ARTIFACT
        or start_doc.get("REUSE_COMMIT") != REUSE_COMMIT
        or start_doc.get("START_COUNT") != EXPECTED_START_COUNT
        or start_doc.get("START_SHA256") != EXPECTED_START_SHA256
        or start_doc.get("START_TICKET_COUNT") != 20
        or reuse_doc.get("REUSE_COMMIT") != REUSE_COMMIT
    ):
        raise RuntimeError("frozen START or reuse identity differs from the bound packet input")
    portfolio = tuple(tuple(int(n) for n in ticket) for ticket in start_doc["START_PORTFOLIO"])
    if len(portfolio) != 20 or len(set(portfolio)) != 20:
        raise RuntimeError("frozen START does not contain 20 unique tickets")
    if any(
        len(ticket) != 6
        or len(set(ticket)) != 6
        or tuple(sorted(ticket)) != ticket
        or any(number < 1 or number > 49 for number in ticket)
        for ticket in portfolio
    ):
        raise RuntimeError("frozen START contains an illegal B649 ticket")
    promotion_path = repo_root / PROMOTION_ARTIFACT
    require_regular(promotion_path)
    promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
    if (
        tuple(tuple(int(n) for n in ticket) for ticket in promotion["TICKETS"]) != portfolio
        or promotion.get("PORTFOLIO_SHA256") != EXPECTED_START_SHA256
        or promotion.get("WINNING_OUTCOMES") != EXPECTED_START_COUNT
    ):
        raise RuntimeError("frozen START is not the durable promoted K20 incumbent")
    manifest = load_manifest(run_root, portfolio)
    overlay = run_root / "engine/src"
    expected_module = (
        "lottolab/research/b649_k20_global_residual_pool_repair_r1.py"
    )
    module_path = overlay / expected_module
    if not module_path.is_file() or module_path.is_symlink():
        raise RuntimeError(f"reused scorer source is missing or unsafe: {module_path}")
    source_hashes = reuse_doc.get("FILES")
    for relative, expected in source_hashes.items():
        copied = overlay / relative.removeprefix("src/")
        if copied.is_symlink() or not copied.is_file():
            raise RuntimeError(f"reused source is missing or unsafe: {copied}")
        if sha256_file(copied) != expected:
            raise RuntimeError(f"reused source hash mismatch: {relative}")
    sys.path.insert(0, str(overlay))
    from lottolab.research import b649_k20_five_ticket_exact_repair_r1 as base
    from lottolab.research import b649_k20_global_residual_pool_repair_r1 as engine

    if Path(base.__file__).resolve() != (
        overlay / "lottolab/research/b649_k20_five_ticket_exact_repair_r1.py"
    ).resolve():
        raise RuntimeError("base repair import escaped the frozen source overlay")
    if Path(engine.__file__).resolve() != module_path.resolve():
        raise RuntimeError("global scorer import escaped the frozen source overlay")
    if (
        base.START_COUNT != EXPECTED_START_COUNT
        or base.START_SHA256 != EXPECTED_START_SHA256
        or tuple(base.START_PORTFOLIO) != portfolio
        or engine.GLOBAL_TOP_MARGINAL != 48
        or engine.REPAIR_POOL_MAX != 64
        or engine.TOTAL_TICKETS != EXPECTED_TOTAL_TICKETS
    ):
        raise RuntimeError("reused implementation constants differ from the authorized scope")
    return base, engine, start_doc, manifest


def initialize_state(
    state_path: Path,
    repo_root: Path,
    start_doc: dict[str, Any],
    reuse_doc: dict[str, Any],
    *,
    incumbent_resolver: Any = None,
    result_semantics: Any = None,
) -> dict[str, Any]:
    semantics = result_semantics or load_result_semantics(repo_root)
    state = {
        "SCHEMA_VERSION": 2,
        "TASK_ID": TASK_ID,
        "EXECUTION_ID": EXECUTION_ID,
        "REPOSITORY": str(repo_root),
        "WORKTREE": str(repo_root),
        "START_COUNT": EXPECTED_START_COUNT,
        "START_SHA256": EXPECTED_START_SHA256,
        "START_TICKET_COUNT": 20,
        "START_SOURCE_COMMIT": START_COMMIT,
        "START_SOURCE_ARTIFACT": START_ARTIFACT,
        "REUSE_COMMIT": REUSE_COMMIT,
        "REUSE_FILES": reuse_doc["FILES"],
        "CHECKPOINT_INTERVAL": CHECKPOINT_INTERVAL,
        "DESTROY_SIZE": DESTROY_SIZE,
        "SAMPLE_SEED": SAMPLE_SEED,
        "DESTROY_SET_COUNT": EXPECTED_DESTROY_SETS,
        "MANIFEST_FILE_SHA256": FROZEN_MANIFEST_FILE_SHA256,
        "MANIFEST_DIGEST": FROZEN_MANIFEST_DIGEST,
        "PHASE": "START_BINDING",
        "SETS_COMPLETED": 0,
        "GLOBAL_TICKETS_SCORED": 0,
        "PROVEN_OPTIMAL_SETS": 0,
        "NODES_EXPLORED": 0,
        "NODES_PRUNED": 0,
        "BEST_COUNT": None,
        "BEST_SHA256": None,
        "GLOBAL_BEST_TIE_COUNT": 0,
        "JOURNAL_PREFIX_SHA256": hashlib.sha256(b"").hexdigest(),
        "CANONICAL_RECOUNTED_TIES": 0,
        "CAMPAIGN_STARTED_AT": utc_now(),
        "UPDATED_AT": utc_now(),
    }
    if state_path.exists():
        require_regular(state_path)
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
        incumbent_authority_from_state(loaded, semantics)
        immutable = (
            "SCHEMA_VERSION",
            "TASK_ID",
            "EXECUTION_ID",
            "REPOSITORY",
            "WORKTREE",
            "START_COUNT",
            "START_SHA256",
            "START_TICKET_COUNT",
            "START_SOURCE_COMMIT",
            "START_SOURCE_ARTIFACT",
            "REUSE_COMMIT",
            "REUSE_FILES",
            "CHECKPOINT_INTERVAL",
            "DESTROY_SIZE",
            "SAMPLE_SEED",
            "DESTROY_SET_COUNT",
            "MANIFEST_FILE_SHA256",
            "MANIFEST_DIGEST",
        )
        for key in immutable:
            if loaded.get(key) != state[key]:
                raise RuntimeError(f"resume state identity mismatch at {key}")
        return loaded
    prior_artifacts = (
        "set-results.jsonl",
        "canonical-recounts.jsonl",
        "result.json",
    )
    if any((state_path.parent / name).exists() for name in prior_artifacts):
        raise RuntimeError("run artifacts exist without persisted incumbent authority")
    resolver = incumbent_resolver or semantics.resolve_launch_time_incumbent
    state.update(incumbent_authority_state_fields(resolver(), semantics))
    atomic_write(state_path, canonical_json(state))
    return state


def prepare_run_authority(
    state_path: Path,
    repo_root: Path,
    start_doc: dict[str, Any],
    reuse_doc: dict[str, Any],
    *,
    incumbent_resolver: Any = None,
) -> tuple[Any, dict[str, Any], Any]:
    semantics = load_result_semantics(repo_root)
    state = initialize_state(
        state_path,
        repo_root,
        start_doc,
        reuse_doc,
        incumbent_resolver=incumbent_resolver,
        result_semantics=semantics,
    )
    authority = incumbent_authority_from_state(state, semantics)
    return semantics, state, authority


def merge_tie(
    tie_map: dict[str, dict[str, Any]], candidate: dict[str, Any], engine: Any
) -> None:
    portfolio = tuple(tuple(int(n) for n in row) for row in candidate["PORTFOLIO"])
    digest = engine.portfolio_sha256(portfolio)
    if digest != candidate.get("SHA256"):
        raise RuntimeError("optimal tie candidate has a bad portfolio SHA256")
    indices = tuple(int(i) for i in candidate["DESTROY_INDICES"])
    prior = tie_map.get(digest)
    normalized = {
        "SHA256": digest,
        "PORTFOLIO": [list(ticket) for ticket in portfolio],
        "DESTROY_INDICES": list(indices),
        "NEW_TICKETS": [list(ticket) for ticket in candidate["NEW_TICKETS"]],
    }
    if prior is None:
        tie_map[digest] = normalized
        return
    if prior["PORTFOLIO"] != normalized["PORTFOLIO"]:
        raise RuntimeError("portfolio SHA256 collision among global-best ties")
    if tuple(indices) < tuple(prior["DESTROY_INDICES"]):
        tie_map[digest] = normalized


def summarize_set_row(row: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "SET_INDEX",
        "DESTROY_INDICES",
        "STRATUM",
        "TICKETS_SCORED",
        "GLOBAL_SCORE_IDENTITIES_PASS",
        "TOP48_COUNT",
        "TOP48_SHA256",
        "POOL_SIZE",
        "POOL_UNION_SIZE",
        "POOL_DROPPED_COUNT",
        "REPAIR_POOL_SHA256",
        "POOL_OPTIMALITY_STATUS",
        "OPTIMAL_SET_COUNT",
        "NODES_EXPLORED",
        "NODES_PRUNED",
        "LEAVES_SCORED",
        "SETS_PRUNED",
        "BEST_COUNT",
        "BEST_DELTA",
        "CURRENT_VERIFIED_INCUMBENT_COUNT",
        "DELTA_FROM_FROZEN_START",
        "DELTA_FROM_CURRENT_VERIFIED_INCUMBENT",
        "LOCAL_GAIN_VS_FROZEN_START",
        "GLOBAL_STRICT_GAIN",
        "BEST_SHA256",
        "BEST_NEW_TICKETS",
        "SCORE_SECONDS",
        "ELAPSED_SECONDS",
    )
    return {field: row[field] for field in fields}


def empty_aggregate() -> dict[str, Any]:
    return {
        "SETS_COMPLETED": 0,
        "GLOBAL_TICKETS_SCORED": 0,
        "PROVEN_OPTIMAL_SETS": 0,
        "NODES_EXPLORED": 0,
        "NODES_PRUNED": 0,
        "LEAVES_SCORED": 0,
        "SETS_PRUNED": 0,
        "BEST_COUNT": None,
        "TIE_MAP": {},
        "POOL_SIZE_MIN": None,
        "POOL_SIZE_MAX": 0,
        "POOL_SIZE_SUM": 0,
        "POOL_UNION_SIZE_MAX": 0,
        "ELAPSED_SECONDS_SUM": 0.0,
        "SCORE_SECONDS_SUM": 0.0,
        "PER_DESTROY_SET": [],
    }


def apply_set_row(
    aggregate: dict[str, Any],
    row: dict[str, Any],
    expected_positions: tuple[int, ...],
    expected_stratum: str,
    start: Any,
    base: Any,
    engine: Any,
    launch_time_incumbent: Any,
    result_semantics: Any,
) -> None:
    index = aggregate["SETS_COMPLETED"] + 1
    positions = tuple(int(i) for i in row.get("DESTROY_INDICES", ()))
    if positions != expected_positions or row.get("SET_INDEX") != index:
        raise RuntimeError(f"journal sequence/indices mismatch at set {index}")
    if len(positions) != DESTROY_SIZE or row.get("STRATUM") != expected_stratum:
        raise RuntimeError(f"set {index} is not the frozen destroy-{DESTROY_SIZE} stratum row")
    if row.get("FROZEN_TICKET_COUNT") != FROZEN_TICKET_COUNT:
        raise RuntimeError(f"set {index} did not freeze {FROZEN_TICKET_COUNT} tickets")
    if row.get("TICKETS_SCORED") != EXPECTED_TOTAL_TICKETS:
        raise RuntimeError(f"set {index} did not score the complete ticket universe")
    if row.get("SCORER_ORDER") != "FULL_UNIVERSE_BEFORE_GLOBAL_TOP48_AND_POOL":
        raise RuntimeError(f"set {index} did not preserve scorer-before-pool ordering")
    if row.get("GLOBAL_SCORE_IDENTITIES_PASS") is not True:
        raise RuntimeError(f"global score identities failed in set {index}")
    if row.get("TOP48_COUNT") != 48 or len(row.get("GLOBAL_TOP48", ())) != 48:
        raise RuntimeError(f"set {index} does not retain exactly GLOBAL_TOP_MARGINAL=48")
    top_rows = row["GLOBAL_TOP48"]
    if [int(entry["RANK"]) for entry in top_rows] != list(range(1, 49)):
        raise RuntimeError(f"set {index} global top-48 ranks are incomplete or reordered")
    for entry in top_rows:
        ticket = tuple(int(n) for n in entry["TICKET"])
        if (
            len(ticket) != 6
            or tuple(sorted(ticket)) != ticket
            or len(set(ticket)) != 6
            or any(number < 1 or number > 49 for number in ticket)
        ):
            raise RuntimeError(f"set {index} global top-48 contains an illegal ticket")
    top_digest = sha256_bytes(
        canonical_json(
            [
                [entry["TICKET"], entry["MARGINAL_SUBSETS"], entry["RANK"]]
                for entry in top_rows
            ]
        )
    )
    if top_digest != row.get("TOP48_SHA256"):
        raise RuntimeError(f"set {index} top-48 digest mismatch")
    pool = row.get("REPAIR_POOL", [])
    if (
        not 1 <= len(pool) <= 64
        or row.get("POOL_SIZE") != len(pool)
        or len({tuple(item["TICKET"]) for item in pool}) != len(pool)
    ):
        raise RuntimeError(f"set {index} pool is not deduplicated/capped at 64")
    if int(row["POOL_UNION_SIZE"]) < len(pool):
        raise RuntimeError(f"set {index} pool union is smaller than its capped pool")
    if int(row["POOL_DROPPED_COUNT"]) != int(row["POOL_UNION_SIZE"]) - len(pool):
        raise RuntimeError(f"set {index} pool cap accounting does not reconcile")
    removed = [list(start[i]) for i in positions]
    pool_tickets = {tuple(item["TICKET"]) for item in pool}
    if any(tuple(ticket) not in pool_tickets for ticket in removed):
        raise RuntimeError(f"set {index} omits a removed ticket from the pool")
    if any(item["SOURCE"] not in {"A_REMOVED", "B_ELITE", "C_GLOBAL"} for item in pool):
        raise RuntimeError(f"set {index} has an unknown pool source")
    pool_digest = sha256_bytes(
        canonical_json(
            [
                [
                    item["TICKET"],
                    item["SOURCE"],
                    item["MARGINAL_SUBSETS"],
                    item["GLOBAL_RANK"],
                    item["IN_GLOBAL_TOP48"],
                ]
                for item in pool
            ]
        )
    )
    if pool_digest != row.get("REPAIR_POOL_SHA256"):
        raise RuntimeError(f"set {index} repair-pool digest mismatch")
    if row.get("POOL_OPTIMALITY_STATUS") != base.OPTIMALITY_PROVEN:
        raise RuntimeError(f"set {index} lacks a PROVEN_OPTIMAL pool proof")
    if int(row.get("UNRESOLVED_POOL_SETS", -1)) != 0:
        raise RuntimeError(f"set {index} leaves unresolved pool sets")
    if int(row["TOTAL_POOL_SETS"]) != math.comb(len(pool), DESTROY_SIZE):
        raise RuntimeError(f"set {index} pool search cardinality mismatch")

    optimal_count = int(row["OPTIMAL_SET_COUNT"])
    candidate_count = int(row["BEST_COUNT"])
    classify_set_result(row, launch_time_incumbent, result_semantics)
    candidates = row.get("GLOBAL_BEST_CANDIDATES")
    prior_best = aggregate["BEST_COUNT"]
    needs_candidates = prior_best is None or candidate_count >= prior_best
    if needs_candidates:
        if not isinstance(candidates, list) or len(candidates) != optimal_count:
            raise RuntimeError(f"set {index} omitted one or more global-best ties")
    elif candidates is not None:
        raise RuntimeError(f"set {index} carries unexpected non-best tie payload")
    if candidate_count < EXPECTED_START_COUNT:
        raise RuntimeError(f"set {index} optimum is below the feasible START")
    if candidates is not None:
        candidate_hashes = [candidate.get("SHA256") for candidate in candidates]
        if candidate_hashes != sorted(candidate_hashes):
            raise RuntimeError(f"set {index} optimal tie candidates are not SHA ordered")
        if candidate_hashes[0] != row.get("BEST_SHA256"):
            raise RuntimeError(f"set {index} did not choose its lowest-SHA optimum")

    if prior_best is None or candidate_count > prior_best:
        aggregate["BEST_COUNT"] = candidate_count
        aggregate["TIE_MAP"] = {}
    if candidate_count == aggregate["BEST_COUNT"]:
        for candidate in candidates:
            if tuple(candidate["DESTROY_INDICES"]) != positions:
                raise RuntimeError(f"set {index} tie is bound to different indices")
            portfolio = tuple(tuple(ticket) for ticket in candidate["PORTFOLIO"])
            if len(portfolio) != 20 or len(set(portfolio)) != 20:
                raise RuntimeError(f"set {index} tie is not a 20-ticket portfolio")
            if candidate["NEW_TICKETS"] != [
                list(ticket) for ticket in sorted(set(portfolio) - set(start))
            ]:
                raise RuntimeError(f"set {index} tie has an invalid new-ticket list")
            merge_tie(aggregate["TIE_MAP"], candidate, engine)

    aggregate["SETS_COMPLETED"] += 1
    aggregate["GLOBAL_TICKETS_SCORED"] += int(row["TICKETS_SCORED"])
    aggregate["PROVEN_OPTIMAL_SETS"] += 1
    aggregate["NODES_EXPLORED"] += int(row["NODES_EXPLORED"])
    aggregate["NODES_PRUNED"] += int(row["NODES_PRUNED"])
    aggregate["LEAVES_SCORED"] += int(row["LEAVES_SCORED"])
    aggregate["SETS_PRUNED"] += int(row["SETS_PRUNED"])
    size = int(row["POOL_SIZE"])
    aggregate["POOL_SIZE_MIN"] = (
        size
        if aggregate["POOL_SIZE_MIN"] is None
        else min(aggregate["POOL_SIZE_MIN"], size)
    )
    aggregate["POOL_SIZE_MAX"] = max(aggregate["POOL_SIZE_MAX"], size)
    aggregate["POOL_SIZE_SUM"] += size
    aggregate["POOL_UNION_SIZE_MAX"] = max(
        aggregate["POOL_UNION_SIZE_MAX"], int(row["POOL_UNION_SIZE"])
    )
    aggregate["ELAPSED_SECONDS_SUM"] += float(row["ELAPSED_SECONDS"])
    aggregate["SCORE_SECONDS_SUM"] += float(row["SCORE_SECONDS"])
    aggregate["PER_DESTROY_SET"].append(summarize_set_row(row))


def replay_set_journal(
    records: list[dict[str, Any]],
    raw_lines: list[bytes],
    state: dict[str, Any],
    base: Any,
    engine: Any,
    start: Any,
    manifest: dict[str, Any],
    launch_time_incumbent: Any,
    result_semantics: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]], str, dict[int, dict[str, Any]]]:
    expected_rows = manifest["SETS"]
    if len(records) > EXPECTED_DESTROY_SETS:
        raise RuntimeError("set journal exceeds the frozen sample")
    aggregate = empty_aggregate()
    journal_hasher = hashlib.sha256()
    checkpoint_sets = int(state["SETS_COMPLETED"])
    snapshots: dict[int, dict[str, Any]] = {}
    for index, (row, raw_line) in enumerate(zip(records, raw_lines, strict=True)):
        apply_set_row(
            aggregate,
            row,
            tuple(expected_rows[index]["DESTROY_INDICES"]),
            expected_rows[index]["STRATUM"],
            start,
            base,
            engine,
            launch_time_incumbent,
            result_semantics,
        )
        journal_hasher.update(raw_line)
        completed = index + 1
        if completed % CHECKPOINT_INTERVAL == 0 or completed == EXPECTED_DESTROY_SETS:
            best_sha = min(aggregate["TIE_MAP"]) if aggregate["TIE_MAP"] else None
            snapshots[completed] = {
                "SETS_COMPLETED": completed,
                "GLOBAL_TICKETS_SCORED": completed * EXPECTED_TOTAL_TICKETS,
                "PROVEN_OPTIMAL_SETS": completed,
                "NODES_EXPLORED": aggregate["NODES_EXPLORED"],
                "NODES_PRUNED": aggregate["NODES_PRUNED"],
                "BEST_COUNT": aggregate["BEST_COUNT"],
                "BEST_SHA256": best_sha,
                "GLOBAL_BEST_TIE_COUNT": len(aggregate["TIE_MAP"]),
                "JOURNAL_PREFIX_SHA256": journal_hasher.hexdigest(),
            }
    empty_digest = hashlib.sha256(b"").hexdigest()
    snapshots[0] = {
        "SETS_COMPLETED": 0,
        "GLOBAL_TICKETS_SCORED": 0,
        "PROVEN_OPTIMAL_SETS": 0,
        "NODES_EXPLORED": 0,
        "NODES_PRUNED": 0,
        "BEST_COUNT": None,
        "BEST_SHA256": None,
        "GLOBAL_BEST_TIE_COUNT": 0,
        "JOURNAL_PREFIX_SHA256": empty_digest,
    }
    if checkpoint_sets not in snapshots:
        raise RuntimeError("checkpoint does not identify a durable journal boundary")
    snapshot = snapshots[checkpoint_sets]
    for key, value in snapshot.items():
        if state.get(key) != value:
            raise RuntimeError(f"state checkpoint {key} does not match its journal prefix")
    latest = (len(records) // CHECKPOINT_INTERVAL) * CHECKPOINT_INTERVAL
    allowed = {latest}
    if len(records) % CHECKPOINT_INTERVAL == 0 and latest >= CHECKPOINT_INTERVAL:
        allowed.add(latest - CHECKPOINT_INTERVAL)
    if len(records) == EXPECTED_DESTROY_SETS:
        allowed.add(EXPECTED_DESTROY_SETS)
        allowed.add((EXPECTED_DESTROY_SETS // CHECKPOINT_INTERVAL) * CHECKPOINT_INTERVAL)
    if checkpoint_sets not in allowed:
        raise RuntimeError(
            f"state checkpoint {checkpoint_sets} is inconsistent with "
            f"{len(records)} durable set records"
        )
    return (
        aggregate,
        aggregate["PER_DESTROY_SET"],
        journal_hasher.hexdigest(),
        snapshots,
    )


def checkpoint_state(
    state_path: Path,
    state: dict[str, Any],
    aggregate: dict[str, Any],
    phase: str,
    journal_sha256: str,
    *,
    checkpoint_sets: int | None = None,
    snapshot: dict[str, Any] | None = None,
    recount_count: int | None = None,
) -> None:
    completed = aggregate["SETS_COMPLETED"]
    if snapshot is None:
        snapshot = {
            "SETS_COMPLETED": completed if checkpoint_sets is None else checkpoint_sets,
            "GLOBAL_TICKETS_SCORED": (
                (completed if checkpoint_sets is None else checkpoint_sets)
                * EXPECTED_TOTAL_TICKETS
            ),
            "PROVEN_OPTIMAL_SETS": (
                completed if checkpoint_sets is None else checkpoint_sets
            ),
            "NODES_EXPLORED": aggregate["NODES_EXPLORED"],
            "NODES_PRUNED": aggregate["NODES_PRUNED"],
            "BEST_COUNT": aggregate["BEST_COUNT"],
            "BEST_SHA256": min(aggregate["TIE_MAP"]) if aggregate["TIE_MAP"] else None,
            "GLOBAL_BEST_TIE_COUNT": len(aggregate["TIE_MAP"]),
            "JOURNAL_PREFIX_SHA256": journal_sha256,
        }
    state.update(
        {
            "PHASE": phase,
            "CANONICAL_RECOUNTED_TIES": (
                int(state.get("CANONICAL_RECOUNTED_TIES", 0))
                if recount_count is None
                else recount_count
            ),
            "UPDATED_AT": utc_now(),
            **snapshot,
        }
    )
    atomic_write(state_path, canonical_json(state))


def per_stratum_best(per_set_summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in per_set_summary:
        grouped.setdefault(item["STRATUM"], []).append(item)
    rows = []
    for key in sorted(grouped):
        best = max(int(item["BEST_COUNT"]) for item in grouped[key])
        rows.append(
            {
                "STRATUM": key,
                "SETS": len(grouped[key]),
                "BEST_COUNT": best,
                "BEST_DELTA": best - EXPECTED_START_COUNT,
                "SETS_AT_BEST": sum(1 for item in grouped[key] if int(item["BEST_COUNT"]) == best),
            }
        )
    return rows


def progress_line(aggregate: dict[str, Any], phase: str) -> None:
    best_sha = min(aggregate["TIE_MAP"]) if aggregate["TIE_MAP"] else None
    print(
        json.dumps(
            {
                "TASK_ID": TASK_ID,
                "PHASE": phase,
                "SETS_COMPLETED": aggregate["SETS_COMPLETED"],
                "SETS_TOTAL": EXPECTED_DESTROY_SETS,
                "GLOBAL_TICKETS_SCORED": aggregate["GLOBAL_TICKETS_SCORED"],
                "PROVEN_OPTIMAL_SETS": aggregate["PROVEN_OPTIMAL_SETS"],
                "NODES_EXPLORED": aggregate["NODES_EXPLORED"],
                "NODES_PRUNED": aggregate["NODES_PRUNED"],
                "BEST_COUNT": aggregate["BEST_COUNT"],
                "BEST_SHA256": best_sha,
                "GLOBAL_BEST_TIE_COUNT": len(aggregate["TIE_MAP"]),
            },
            sort_keys=True,
        ),
        flush=True,
    )


def run_one_set(
    *,
    set_index: int,
    positions: tuple[int, ...],
    stratum: str,
    start: Any,
    base: Any,
    engine: Any,
    universe: Any,
    recounter: Any,
    elites: list[Any],
    prior_best: int | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    if len(positions) != DESTROY_SIZE:
        raise AssertionError(f"destroy set {positions} is not of size {DESTROY_SIZE}")
    destroyed = engine.destroy_positions(start, positions)
    remaining_count = recounter.count(destroyed.remaining)
    if remaining_count % engine.SUBSET_SIZE:
        raise AssertionError("canonical frozen-ticket count is not divisible by 7")
    residual = engine.BIG_LOTTO_GEOMETRY.subset_count - (
        remaining_count // engine.SUBSET_SIZE
    )

    # This is the complete legal-ticket pass. No candidate or mutation filter precedes it.
    scores = engine.score_all_tickets(universe, destroyed.remaining)
    if scores.tickets_scored != EXPECTED_TOTAL_TICKETS:
        raise AssertionError(
            f"scored {scores.tickets_scored}, expected {EXPECTED_TOTAL_TICKETS}"
        )
    identities = engine.check_score_identities(scores, universe, residual)
    if identities.get("PASS") is not True:
        raise AssertionError("global scorer identities failed")

    plan = engine.assemble_global_pool(
        universe,
        scores,
        destroyed,
        elites=elites,
        top_count=48,
        pool_max=64,
    )
    if len(plan.top) != 48 or len(plan.members) > 64:
        raise AssertionError("global top-48 or repair-pool cap was violated")
    histogram = engine.build_repair_histogram(destroyed.remaining, plan.tickets)
    if histogram.residual_subsets != residual:
        raise AssertionError(
            f"repair histogram residual {histogram.residual_subsets} != {residual}"
        )
    for pool_index, member in enumerate(plan.members):
        if histogram.subset_value([pool_index]) != member.marginal:
            raise AssertionError(
                f"global scorer/histogram marginal mismatch for {member.ticket}"
            )

    start_indices = tuple(plan.tickets.index(ticket) for ticket in destroyed.removed)
    start_outcomes = histogram.outcome_count(start_indices)
    if start_outcomes != EXPECTED_START_COUNT:
        raise AssertionError(
            f"START is not preserved by the repair kernel: {start_outcomes}"
        )

    def portfolio_of(chosen: tuple[int, ...]) -> Any:
        return engine.normalize_portfolio(
            (*destroyed.remaining, *(plan.tickets[index] for index in chosen))
        )

    def tie_key(chosen: tuple[int, ...]) -> str:
        return engine.portfolio_sha256(portfolio_of(chosen))

    pool_count = len(plan.members)
    tie_limit = math.comb(pool_count, len(positions))
    solve = engine.solve_pool_exact(
        histogram.masks,
        histogram.weights,
        pool_count,
        len(positions),
        start_indices,
        tie_key,
        deadline=None,
        use_bound=True,
        tie_limit=tie_limit,
    )
    if solve.status != base.OPTIMALITY_PROVEN:
        raise AssertionError(f"pool solver returned {solve.status}")
    if not solve.optimal_sets or len(solve.optimal_sets) > tie_limit:
        raise AssertionError("pool solver omitted an optimal set or exceeded full tie capacity")
    optimal_portfolios = [portfolio_of(chosen) for chosen in solve.optimal_sets]
    optimal_counts = [histogram.outcome_count(chosen) for chosen in solve.optimal_sets]
    if any(count != optimal_counts[0] for count in optimal_counts):
        raise AssertionError("exact solver returned unequal objective values as ties")
    if optimal_counts[0] != EXPECTED_START_COUNT + 7 * (
        solve.best_value - solve.start_value
    ):
        raise AssertionError("pool optimum count does not match the exact residual objective")
    ranked_ties = [
        {
            "SHA256": engine.portfolio_sha256(portfolio),
            "PORTFOLIO": [list(ticket) for ticket in portfolio],
            "DESTROY_INDICES": list(positions),
            "NEW_TICKETS": [
                list(ticket) for ticket in sorted(set(portfolio) - set(start))
            ],
        }
        for portfolio in optimal_portfolios
    ]
    ranked_ties.sort(key=lambda item: item["SHA256"])
    if ranked_ties[0]["SHA256"] != tie_key(solve.best_set):
        raise AssertionError("pool solver did not select the lowest-SHA exact optimum")
    best_count = optimal_counts[0]
    candidate_payload = ranked_ties if prior_best is None or best_count >= prior_best else None
    top_rows = [
        {
            "RANK": entry.rank,
            "TICKET": list(entry.ticket),
            "MARGINAL_SUBSETS": entry.marginal,
        }
        for entry in plan.top
    ]
    pool_rows = [
        {
            "TICKET": list(member.ticket),
            "SOURCE": member.source,
            "MARGINAL_SUBSETS": member.marginal,
            "GLOBAL_RANK": member.global_rank,
            "IN_GLOBAL_TOP48": member.in_global_top,
        }
        for member in plan.members
    ]
    top_digest = sha256_bytes(
        canonical_json(
            [
                [entry["TICKET"], entry["MARGINAL_SUBSETS"], entry["RANK"]]
                for entry in top_rows
            ]
        )
    )
    pool_digest = sha256_bytes(
        canonical_json(
            [
                [
                    item["TICKET"],
                    item["SOURCE"],
                    item["MARGINAL_SUBSETS"],
                    item["GLOBAL_RANK"],
                    item["IN_GLOBAL_TOP48"],
                ]
                for item in pool_rows
            ]
        )
    )
    best_portfolio = optimal_portfolios[0]
    best_sha = ranked_ties[0]["SHA256"]
    elapsed = time.perf_counter() - started
    return {
        "SET_INDEX": set_index,
        "DESTROY_INDICES": list(positions),
        "STRATUM": stratum,
        "REMOVED_TICKETS": [list(ticket) for ticket in destroyed.removed],
        "FROZEN_TICKET_COUNT": len(destroyed.remaining),
        "FROZEN_OUTCOMES": remaining_count,
        "RESIDUAL_SUBSETS": residual,
        "TICKETS_SCORED": scores.tickets_scored,
        "GLOBAL_SCORE_IDENTITIES_PASS": identities["PASS"],
        "GLOBAL_SCORE_IDENTITIES": identities,
        "SCORER_ORDER": "FULL_UNIVERSE_BEFORE_GLOBAL_TOP48_AND_POOL",
        "TOP48_COUNT": len(plan.top),
        "TOP48_SHA256": top_digest,
        "GLOBAL_TOP48": top_rows,
        "POOL_SIZE": len(plan.members),
        "POOL_UNION_SIZE": plan.union_size,
        "POOL_DROPPED_COUNT": len(plan.dropped),
        "POOL_DROPPED_TICKETS": [list(ticket) for ticket in plan.dropped],
        "REPAIR_POOL_SHA256": pool_digest,
        "REPAIR_POOL": pool_rows,
        "HISTOGRAM_ROWS": int(histogram.masks.size),
        "DEAD_SUBSETS": histogram.dead_subsets,
        "START_OUTCOMES_VIA_KERNEL": start_outcomes,
        "POOL_OPTIMALITY_STATUS": solve.status,
        "OPTIMAL_SET_COUNT": len(solve.optimal_sets),
        "NODES_EXPLORED": solve.nodes_explored,
        "NODES_PRUNED": solve.nodes_pruned,
        "LEAVES_SCORED": solve.leaf_sets_evaluated,
        "SETS_PRUNED": solve.sets_pruned,
        "TOTAL_POOL_SETS": solve.total_sets,
        "UNRESOLVED_POOL_SETS": solve.unresolved_sets,
        "BEST_COUNT": best_count,
        "BEST_DELTA": best_count - EXPECTED_START_COUNT,
        "BEST_SHA256": best_sha,
        "BEST_NEW_TICKETS": [
            list(ticket) for ticket in sorted(set(best_portfolio) - set(start))
        ],
        "SCORE_SECONDS": scores.seconds,
        "ELAPSED_SECONDS": elapsed,
        "GLOBAL_BEST_CANDIDATES": candidate_payload,
    }


def validate_checkpoint_prefix(
    state: dict[str, Any], records: list[dict[str, Any]], raw_lines: list[bytes]
) -> None:
    checkpoint_sets = int(state.get("SETS_COMPLETED", -1))
    if checkpoint_sets < 0 or checkpoint_sets > len(records):
        raise RuntimeError("checkpoint set count is outside the durable journal")
    digest = hashlib.sha256()
    prefix_hash = hashlib.sha256(b"").hexdigest() if checkpoint_sets == 0 else None
    for index, line in enumerate(raw_lines[:checkpoint_sets], start=1):
        digest.update(line)
        if index == checkpoint_sets:
            prefix_hash = digest.hexdigest()
    if prefix_hash != state.get("JOURNAL_PREFIX_SHA256"):
        raise RuntimeError("checkpoint prefix hash differs from the durable set journal")
    completed = len(records)
    latest_boundary = (completed // CHECKPOINT_INTERVAL) * CHECKPOINT_INTERVAL
    allowed = {latest_boundary}
    if completed % CHECKPOINT_INTERVAL == 0 and latest_boundary >= CHECKPOINT_INTERVAL:
        allowed.add(latest_boundary - CHECKPOINT_INTERVAL)
    if completed == EXPECTED_DESTROY_SETS:
        allowed.add(EXPECTED_DESTROY_SETS)
        allowed.add(latest_boundary)
    if checkpoint_sets not in allowed:
        raise RuntimeError(
            f"checkpoint is {checkpoint_sets}; incompatible with {completed} durable sets"
        )


def read_recount_journal(
    path: Path, global_ties: dict[str, dict[str, Any]]
) -> tuple[dict[str, int], list[bytes]]:
    records, lines = read_jsonl(path)
    counts: dict[str, int] = {}
    for index, row in enumerate(records, start=1):
        digest = row.get("SHA256")
        if digest not in global_ties:
            raise RuntimeError(f"canonical recount row {index} is not a global-best tie")
        if row.get("PORTFOLIO") != global_ties[digest]["PORTFOLIO"]:
            raise RuntimeError(f"canonical recount row {index} portfolio identity mismatch")
        value = int(row["CANONICAL_RECOUNT"])
        if digest in counts and counts[digest] != value:
            raise RuntimeError(f"conflicting canonical recounts for {digest}")
        counts[digest] = value
    return counts, lines


def run_campaign(repo_root: Path, run_root: Path) -> dict[str, Any]:
    lock_path = run_root / "single-writer.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("single-writer lock is already owned") from error

        base, engine, start_doc, manifest = load_frozen_inputs(run_root, repo_root)
        reuse_doc = json.loads(
            (run_root / "engine/reuse-manifest.json").read_text(encoding="utf-8")
        )
        state_path = run_root / "state.json"
        set_journal_path = run_root / "set-results.jsonl"
        recount_journal_path = run_root / "canonical-recounts.jsonl"
        result_semantics, state, launch_time_incumbent = prepare_run_authority(
            state_path, repo_root, start_doc, reuse_doc
        )
        start = tuple(tuple(ticket) for ticket in start_doc["START_PORTFOLIO"])
        if state.get("RUN_HEAD_AT_START") is None:
            state["RUN_HEAD_AT_START"] = git_output(repo_root, "rev-parse", "HEAD")
            state["RUN_TREE_AT_START"] = git_output(repo_root, "rev-parse", "HEAD^{tree}")
        run_start_head = state["RUN_HEAD_AT_START"]
        run_start_tree = state["RUN_TREE_AT_START"]

        recounter = base.CanonicalRecounter()
        start_reproduction = engine.reproduce_start(recounter, repo_root)
        if (
            start_reproduction.get("MATCH") is not True
            or start_reproduction.get("CANONICAL_RECOUNT") != EXPECTED_START_COUNT
            or start_reproduction.get("EMBEDDED_SHA256") != EXPECTED_START_SHA256
            or start_reproduction.get("SOURCE_PORTFOLIO_SHA256") != EXPECTED_START_SHA256
        ):
            raise RuntimeError("fresh START source/count/SHA/ticket identity check failed")
        verified_pins = engine.verify_pins(recounter)
        elites = [pin.tickets for pin in base.PINNED_ELITES]
        if len(elites) != len(verified_pins):
            raise RuntimeError("not all pinned stable elites were verified")
        state["START_CANONICAL_RECOUNT"] = start_reproduction
        state["PINNED_ELITES_VERIFIED"] = verified_pins
        state["RUN_HEAD_AT_START"] = run_start_head
        state["RUN_TREE_AT_START"] = run_start_tree
        state["PHASE"] = "SWEEP"
        state["UPDATED_AT"] = utc_now()
        atomic_write(state_path, canonical_json(state))

        records, raw_lines = read_jsonl(set_journal_path)
        validate_checkpoint_prefix(state, records, raw_lines)
        aggregate, per_set_summary, journal_digest, checkpoint_snapshots = replay_set_journal(
            records,
            raw_lines,
            state,
            base,
            engine,
            start,
            manifest,
            launch_time_incumbent,
            result_semantics,
        )
        latest_boundary = (len(records) // CHECKPOINT_INTERVAL) * CHECKPOINT_INTERVAL
        if len(records) == EXPECTED_DESTROY_SETS:
            latest_boundary = EXPECTED_DESTROY_SETS
        if int(state["SETS_COMPLETED"]) < latest_boundary:
            phase = (
                "CANONICAL_RECOUNT"
                if len(records) == EXPECTED_DESTROY_SETS
                else "SWEEP"
            )
            checkpoint_state(
                state_path,
                state,
                aggregate,
                phase,
                checkpoint_snapshots[latest_boundary]["JOURNAL_PREFIX_SHA256"],
                snapshot=checkpoint_snapshots[latest_boundary],
            )
        journal_hasher = hashlib.sha256()
        with set_journal_path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                journal_hasher.update(chunk)
        del records, raw_lines, checkpoint_snapshots

        campaign_started = datetime.fromisoformat(state["CAMPAIGN_STARTED_AT"])
        if campaign_started.tzinfo is None:
            raise RuntimeError("campaign start time has no UTC offset")
        frozen_at = datetime.fromisoformat(start_doc["MANIFEST_FROZEN_AT_UTC"])
        if frozen_at.tzinfo is None or campaign_started < frozen_at:
            raise RuntimeError("campaign started before the destroy-set sample was frozen")
        if aggregate["SETS_COMPLETED"] < EXPECTED_DESTROY_SETS:
            universe = engine.build_universe()
            if int(universe.tickets.shape[0]) != EXPECTED_TOTAL_TICKETS:
                raise RuntimeError("legal ticket universe cardinality mismatch")
            for set_index, frozen_row in enumerate(manifest["SETS"], start=1):
                if set_index <= aggregate["SETS_COMPLETED"]:
                    continue
                positions = tuple(int(i) for i in frozen_row["DESTROY_INDICES"])
                stratum = frozen_row["STRATUM"]
                prior_best = aggregate["BEST_COUNT"]
                row = run_one_set(
                    set_index=set_index,
                    positions=positions,
                    stratum=stratum,
                    start=start,
                    base=base,
                    engine=engine,
                    universe=universe,
                    recounter=recounter,
                    elites=elites,
                    prior_best=prior_best,
                )
                if row["POOL_OPTIMALITY_STATUS"] != base.OPTIMALITY_PROVEN:
                    raise RuntimeError(f"set {set_index} did not prove pool optimality")
                apply_set_row(
                    aggregate,
                    row,
                    positions,
                    stratum,
                    start,
                    base,
                    engine,
                    launch_time_incumbent,
                    result_semantics,
                )
                encoded = record_set_result(
                    row, set_journal_path, launch_time_incumbent, result_semantics
                )
                journal_hasher.update(encoded)
                journal_digest = journal_hasher.hexdigest()
                if set_index % CHECKPOINT_INTERVAL == 0:
                    checkpoint_state(
                        state_path,
                        state,
                        aggregate,
                        "SWEEP",
                        journal_digest,
                        checkpoint_sets=set_index,
                    )
                    progress_line(aggregate, "SWEEP")
            if aggregate["SETS_COMPLETED"] != EXPECTED_DESTROY_SETS:
                raise RuntimeError(
                    f"enumerated {aggregate['SETS_COMPLETED']} destroy sets, "
                    f"expected {EXPECTED_DESTROY_SETS}"
                )
            checkpoint_state(
                state_path,
                state,
                aggregate,
                "CANONICAL_RECOUNT",
                journal_digest,
                checkpoint_sets=EXPECTED_DESTROY_SETS,
            )

        if (
            aggregate["SETS_COMPLETED"] != EXPECTED_DESTROY_SETS
            or aggregate["PROVEN_OPTIMAL_SETS"] != EXPECTED_DESTROY_SETS
            or aggregate["GLOBAL_TICKETS_SCORED"]
            != EXPECTED_DESTROY_SETS * EXPECTED_TOTAL_TICKETS
        ):
            raise RuntimeError("sweep totals do not cover all required destroy sets")
        if not aggregate["TIE_MAP"] or aggregate["BEST_COUNT"] is None:
            raise RuntimeError("complete sweep produced no exact global-best portfolio")
        global_ties = aggregate["TIE_MAP"]
        recounts, recount_lines = read_recount_journal(
            recount_journal_path, global_ties
        )
        missing_ties = [digest for digest in sorted(global_ties) if digest not in recounts]
        if missing_ties:
            state["PHASE"] = "CANONICAL_RECOUNT"
            state["UPDATED_AT"] = utc_now()
            atomic_write(state_path, canonical_json(state))
            for index, digest in enumerate(missing_ties, start=1):
                portfolio = tuple(
                    tuple(ticket) for ticket in global_ties[digest]["PORTFOLIO"]
                )
                started = time.perf_counter()
                value = recounter.count(portfolio)
                elapsed = time.perf_counter() - started
                recount_row = {
                    "SHA256": digest,
                    "PORTFOLIO": [list(ticket) for ticket in portfolio],
                    "CANONICAL_RECOUNT": value,
                    "EXPECTED_GLOBAL_BEST_COUNT": aggregate["BEST_COUNT"],
                    "MATCH": value == aggregate["BEST_COUNT"],
                    "ELAPSED_SECONDS": elapsed,
                }
                encoded = canonical_json(recount_row)
                append_fsync(recount_journal_path, encoded)
                recount_lines.append(encoded)
                recounts[digest] = value
                if index % CHECKPOINT_INTERVAL == 0:
                    state["CANONICAL_RECOUNTED_TIES"] = len(recounts)
                    state["UPDATED_AT"] = utc_now()
                    atomic_write(state_path, canonical_json(state))
                    progress_line(aggregate, "CANONICAL_RECOUNT")

        recounts, recount_lines = read_recount_journal(
            recount_journal_path, global_ties
        )
        if set(recounts) != set(global_ties):
            raise RuntimeError("canonical recount ledger does not cover every global-best tie")
        canonical_pass = all(
            recounts[digest] == aggregate["BEST_COUNT"] for digest in global_ties
        )
        if not canonical_pass:
            raise RuntimeError("canonical recount disagrees with the exact residual optimum")

        best_sha = min(global_ties)
        best = global_ties[best_sha]
        finished_at = datetime.now(timezone.utc)
        wall_seconds = (
            finished_at - campaign_started.astimezone(timezone.utc)
        ).total_seconds()
        if wall_seconds < 0:
            raise RuntimeError("campaign wall time is negative")
        recount_elapsed = sum(
            float(json.loads(line)["ELAPSED_SECONDS"]) for line in recount_lines
        )
        set_journal_sha = sha256_file(set_journal_path)
        recount_journal_sha = sha256_file(recount_journal_path)
        terminal_classification = terminal_result_fields(
            aggregate["BEST_COUNT"], launch_time_incumbent, result_semantics
        )
        result = {
            **incumbent_authority_state_fields(
                launch_time_incumbent, result_semantics
            ),
            **terminal_classification,
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "COMPLETE",
            "START_COUNT": EXPECTED_START_COUNT,
            "START_SHA256": EXPECTED_START_SHA256,
            "START_TICKET_COUNT": 20,
            "START_PORTFOLIO": [list(ticket) for ticket in start],
            "START_SOURCE_COMMIT": START_COMMIT,
            "START_SOURCE_ARTIFACT": START_ARTIFACT,
            "START_SOURCE_ARTIFACT_SHA256": start_doc[
                "START_SOURCE_ARTIFACT_SHA256"
            ],
            "START_CANONICAL_RECOUNT_STATUS": "PASS",
            "START_CANONICAL_RECOUNT": EXPECTED_START_COUNT,
            "PINNED_ELITES_VERIFIED": verified_pins,
            "REUSE_COMMIT": REUSE_COMMIT,
            "REUSE_FILES_SHA256": reuse_doc["FILES"],
            "RUN_HEAD_AT_START": run_start_head,
            "RUN_TREE_AT_START": run_start_tree,
            "CHECKPOINT_INTERVAL": CHECKPOINT_INTERVAL,
            "SINGLE_WRITER": True,
            "WORKERS": 1,
            "NO_PREFILTER_BEFORE_GLOBAL_ENUMERATION": True,
            "GLOBAL_TICKET_UNIVERSE_SIZE": EXPECTED_TOTAL_TICKETS,
            "GLOBAL_TOP_MARGINAL": 48,
            "REPAIR_POOL_MAX": 64,
            "DESTROY_SET_SIZE": DESTROY_SIZE,
            "DESTROY_SET_COUNT_EXPECTED": EXPECTED_DESTROY_SETS,
            "DESTROY_SET_TOTAL_POSSIBLE": TOTAL_POSSIBLE_SETS,
            "SAMPLE_SEED": SAMPLE_SEED,
            "SAMPLE_FROZEN_BEFORE_SCORING": True,
            "SAMPLE_FROZEN_AT": start_doc["MANIFEST_FROZEN_AT_UTC"],
            "SAMPLE_MANIFEST_FILE_SHA256": FROZEN_MANIFEST_FILE_SHA256,
            "SAMPLE_MANIFEST_DIGEST": FROZEN_MANIFEST_DIGEST,
            "SAMPLE_OUTCOME_INFORMATION_USED": "NONE",
            "SAMPLE_STRATIFICATION": manifest["STRATIFICATION"],
            "SAMPLE_THRESHOLDS": manifest["THRESHOLDS"],
            "SAMPLE_STRATA": manifest["STRATA"],
            "SAMPLER_SOURCE_SHA256": sha256_file(run_root / "stratify.py"),
            "DRIVER_SOURCE_SHA256": sha256_file(Path(__file__).resolve()),
            "UNSAMPLED_DESTROY_SETS_NOT_EVALUATED": TOTAL_POSSIBLE_SETS - EXPECTED_DESTROY_SETS,
            "SETS_WITH_STRICT_GAIN": sum(
                1 for item in per_set_summary if item["GLOBAL_STRICT_GAIN"] == "YES"
            ),
            "SETS_WITH_LOCAL_GAIN_VS_FROZEN_START": sum(
                1
                for item in per_set_summary
                if item["LOCAL_GAIN_VS_FROZEN_START"] == "YES"
            ),
            "SETS_WITH_MULTIPLE_OPTIMA": sum(
                1 for item in per_set_summary if item["OPTIMAL_SET_COUNT"] > 1
            ),
            "PER_STRATUM_BEST": per_stratum_best(per_set_summary),
            "SETS_COMPLETED": aggregate["SETS_COMPLETED"],
            "GLOBAL_TICKETS_SCORED": aggregate["GLOBAL_TICKETS_SCORED"],
            "PROVEN_OPTIMAL_SETS": aggregate["PROVEN_OPTIMAL_SETS"],
            "NODES_EXPLORED": aggregate["NODES_EXPLORED"],
            "NODES_PRUNED": aggregate["NODES_PRUNED"],
            "LEAVES_SCORED": aggregate["LEAVES_SCORED"],
            "SETS_PRUNED": aggregate["SETS_PRUNED"],
            "WALL_SECONDS": round(wall_seconds, 3),
            "WALL_SECONDS_DEFINITION": (
                "campaign start timestamp to completion of the canonical recount "
                "(includes any interruption between resumes)"
            ),
            "SWEEP_SET_SECONDS_SUM": round(
                aggregate["ELAPSED_SECONDS_SUM"], 3
            ),
            "SCORER_SECONDS_SUM": round(aggregate["SCORE_SECONDS_SUM"], 3),
            "CANONICAL_RECOUNT_SECONDS_SUM": round(recount_elapsed, 3),
            "POOL_SIZE_MIN": aggregate["POOL_SIZE_MIN"],
            "POOL_SIZE_MAX": aggregate["POOL_SIZE_MAX"],
            "POOL_SIZE_MEAN": round(
                aggregate["POOL_SIZE_SUM"] / EXPECTED_DESTROY_SETS, 6
            ),
            "POOL_UNION_SIZE_MAX": aggregate["POOL_UNION_SIZE_MAX"],
            "BEST_COUNT": aggregate["BEST_COUNT"],
            "BEST_DELTA": aggregate["BEST_COUNT"] - EXPECTED_START_COUNT,
            "BEST_SHA256": best_sha,
            "BEST_PORTFOLIO": best["PORTFOLIO"],
            "BEST_DESTROY_INDICES": best["DESTROY_INDICES"],
            "BEST_NEW_TICKETS": best["NEW_TICKETS"],
            "BEST_IS_START_PORTFOLIO": best_sha == EXPECTED_START_SHA256,
            "START_PORTFOLIO_IS_A_GLOBAL_BEST_TIE": EXPECTED_START_SHA256 in global_ties,
            "BEST_TIE_BREAK": "lowest portfolio SHA-256 among all exact optima of the best count",
            "BEST_CANONICAL_RECOUNT_STATUS": "PASS",
            "BEST_CANONICAL_RECOUNT": recounts[best_sha],
            "GLOBAL_BEST_TIE_COUNT_UNIQUE_PORTFOLIOS": len(global_ties),
            "GLOBAL_BEST_TIES_ALL_CANONICALLY_RECOUNTED": True,
            "GLOBAL_BEST_TIES": [
                {
                    **global_ties[digest],
                    "CANONICAL_RECOUNT": recounts[digest],
                }
                for digest in sorted(global_ties)
            ],
            "SCIENTIFIC_SCOPE": (
                "STRATIFIED_1024_OF_15504_DESTROY5_GLOBAL_TOP48_POOL_FAMILY_ON_FIXED_START"
            ),
            "COMPLETE_N5_OPTIMUM": "NOT_CLAIMED",
            "INCUMBENT_SWITCHED_MID_CAMPAIGN": False,
            "PROJECT_MEMORY_WRITTEN": "NO",
            "PROTECTED_LANE_3_TOUCHED": "NO",
            "PUSH": "NO",
            "PR": "NO",
            "MERGE": "NO",
            "PRODUCTION": "NONE",
            "SET_JOURNAL_PATH": str(set_journal_path),
            "SET_JOURNAL_SHA256": set_journal_sha,
            "SET_JOURNAL_RECORDS": aggregate["SETS_COMPLETED"],
            "CANONICAL_RECOUNT_JOURNAL_PATH": str(recount_journal_path),
            "CANONICAL_RECOUNT_JOURNAL_SHA256": recount_journal_sha,
            "PER_DESTROY_SET": per_set_summary,
            "CAMPAIGN_STARTED_AT": state["CAMPAIGN_STARTED_AT"],
            "CAMPAIGN_FINISHED_AT": finished_at.isoformat(timespec="seconds"),
        }
        result_bytes = canonical_json(result)
        run_result_path = run_root / "result.json"
        if run_result_path.exists():
            if run_result_path.is_symlink() or run_result_path.read_bytes() != result_bytes:
                raise RuntimeError("existing run result differs from computed result")
        else:
            atomic_write(run_result_path, result_bytes, mode=0o644)
        public_result = repo_root / RESULT_RELATIVE_PATH
        atomic_create_or_match(public_result, result_bytes)
        state["PHASE"] = "COMPLETE"
        state["TASK_STATUS"] = "COMPLETE"
        state["SETS_COMPLETED"] = EXPECTED_DESTROY_SETS
        state["GLOBAL_TICKETS_SCORED"] = (
            EXPECTED_DESTROY_SETS * EXPECTED_TOTAL_TICKETS
        )
        state["PROVEN_OPTIMAL_SETS"] = EXPECTED_DESTROY_SETS
        state["NODES_EXPLORED"] = aggregate["NODES_EXPLORED"]
        state["NODES_PRUNED"] = aggregate["NODES_PRUNED"]
        state["BEST_COUNT"] = aggregate["BEST_COUNT"]
        state["BEST_SHA256"] = best_sha
        state["GLOBAL_BEST_TIE_COUNT"] = len(global_ties)
        state["CANONICAL_RECOUNTED_TIES"] = len(recounts)
        state["RESULT_PATH"] = str(public_result)
        state["RESULT_SHA256"] = sha256_bytes(result_bytes)
        state["CAMPAIGN_FINISHED_AT"] = finished_at.isoformat(timespec="seconds")
        state["UPDATED_AT"] = utc_now()
        atomic_write(state_path, canonical_json(state))
        progress_line(aggregate, "COMPLETE")
        print(
            json.dumps(
                {
                    "RESULT_PATH": str(public_result),
                    "RESULT_SHA256": sha256_bytes(result_bytes),
                    "WALL_SECONDS": round(wall_seconds, 3),
                    "BEST_COUNT": aggregate["BEST_COUNT"],
                    "BEST_SHA256": best_sha,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return result
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    run_root = args.run_root.resolve()
    if git_output(repo_root, "rev-parse", "--show-toplevel") != str(repo_root):
        raise RuntimeError("repository root differs from the authorized workspace")
    try:
        run_campaign(repo_root, run_root)
        return 0
    except BaseException:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
