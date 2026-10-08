"""Hash-pinned overlay of R30 exact cell refutations for the K20 fiber Slice-1 census.

A Slice-1 census cell is one (degree profile, T) pair: the frozen manifest gives every profile
a single-T band, and the census refutes the cell only when R28's exact single-profile support
model, with at most W - 3T open wedges and no exclusions, is CP-SAT INFEASIBLE. R30 Segment 2
(result 9ed94532 at task head 6ba48113) solved that same model as its Route A owner refutation
of cap T for 990 of the 992 cells.

This module imports exactly those refutations into a separate immutable ledger. A cell is
imported from one R30 attempt only. That attempt must be single-profile Route A and
CP_SAT_INFEASIBLE with a normal termination, at the same profile, T, wedge count and ceiling.
Its certified cap must be T - 1, adopted through its own OWNER_REFUTATION step. Its proof-log
line must be the result's attempt verbatim, and its solver child must not have been spawned
while R28 was being edited in place (Owner disposition, 2026-10-08). UNKNOWN, FEASIBLE,
OPTIMAL, timeouts, motif corrections and class or family bounds are never imported.

Nothing here writes to the census. The frozen manifest, the census proof log and its witness
ledger are only read. The combined verdict is computed on demand from a byte snapshot of the
census proof log plus the pinned overlay. A census realization that the overlay would refute,
or a census refutation of a cell R30 realized, is a contradiction and fails closed. No solver
is ever started.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import ceil, comb, floor
from pathlib import Path
from typing import cast

from lottolab.research import b649_k20_fiber_near_top_s3_census as census

TASK_ID = "B649_K20_FIBER_SLICE1_R30_EXACT_REFUTATION_OVERLAY_R1"
OVERLAY_RELATIVE = (
    "docs/research/matrix-native-results/b649-k20-fiber-slice1-r30-exact-refutation-overlay-r1.json"
)
OVERLAY_SHA256 = "6c44200780ea742efadb1e5d161744a7665f99b13822b1613a07fc804d016b19"

CENSUS_SOURCE_COMMIT = "4ff5fac583d86a61469b812397b064ba15532d95"
CENSUS_ENGINE_SHA256 = "479f3163659a91234d23637b697527224e947ae3268e49515cd609ca82ca6276"

R30_TASK_HEAD = "6ba4811304ec6528738a0c0b38969901b264d241"
R30_RESULT_SHA256 = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
R30_TASK_STATUS = "SUCCESS_C_BUDGET_END_EXACT_OWNER_AND_DURABLE_LEDGER"
R30_PROOF_LOG_RELATIVE = ".task-data/r30/proof-log.jsonl"
R30_PROOF_LOG_SHA256 = "4258c2c6a85bc4bdcbdee401ce83767fc03471d8853169f4fbf7f1603ccf3d26"
R30_LAUNCHER_LOG_RELATIVE = ".task-data/r30/segment-2-launcher.out"
R30_LAUNCHER_LOG_SHA256 = "f1419f2d4560914b917d5bc981b79fed86352195342ede364bfacffc926e5d81"
SEGMENT1_ATTEMPTS = 1780
SEGMENT1_PROOF_LOG_SHA256 = "ef319997d4c9cd412061a3eb4500468557ece74f824f4fd3508bd4a28254d596"

ROUTE_A = "A_EXACT_SUPPORT_UNION_OPEN_WEDGE_REFUTATION"
CERTIFICATE = "CP_SAT_INFEASIBLE"
OWNER_REFUTATION = "OWNER_REFUTATION"
OPEN_WEDGE_INDICATORS = census.TICKET_COUNT * comb(census.TICKET_COUNT - 1, 2)

# R28 was edited in place in the R30 worktree from the first edit call at 06:00:20.400Z until
# the byte-exact restore returned at 06:04:40.247Z (session c6bbb209 tool timestamps). Every
# R30 solver batch re-imports R28 in a fresh child, so a batch whose spawn could fall inside
# that window is excluded. The launcher prints "resume Ns" (rounded) just before each spawn.
TRANSIENT_START_MS = 1_791_439_220_400
TRANSIENT_END_MS = 1_791_439_480_247
SPAWN_ROUNDING_MS = 500
CHILD_IMPORT_SLACK_MS = 10_000
LAUNCHER_LINE = re.compile(
    r"(?P<size>[1-9]\d*) solve\(s\), family \d+, ledger \d+, resume (?P<resume>\d+)s, total \d+s"
)

CRITERIA = (
    "SOURCE_IDENTITY",
    "ROUTE_A",
    "SINGLE_PROFILE",
    "SAME_PROFILE",
    "STATUS_INFEASIBLE",
    "CERTIFICATE_CP_SAT_INFEASIBLE",
    "NORMAL_TERMINATION",
    "SAME_T",
    "SAME_WEDGE_COUNT",
    "SAME_CEILING",
    "SINGLE_PROFILE_MODEL",
    "ADOPTED_CAP_T_MINUS_1",
    "OUTSIDE_R28_TRANSIENT_WINDOW",
)
IMPORT_COLUMNS = (
    "PROFILE_ID",
    "T",
    "WEDGE_COUNT",
    "CEILING",
    "R30_ATTEMPT_INDEX",
    "R30_STAGE",
    "R30_PROOF_LOG_LINE_SHA256",
    "CENSUS_CHASE_REQUEST_SHA256",
)
OWNER_DISPOSITION = {
    "R30_ADOPTION": "ADOPTED_EXCLUDING_R28_TRANSIENT_WINDOW_ATTEMPTS",
    "FIBER_SLICE1_REUSE": "AUTHORIZED_SEPARATE_IMMUTABLE_OVERLAY_ONLY",
    "RECORDED": "2026-10-08",
    "CHANNEL": f"Owner chat answers to {TASK_ID}",
}
MODEL_EQUIVALENCE = {
    "CELL_MODEL": "R28 support_union_model((profile,), W - 3T) with no exclusions",
    "CENSUS_BUILDER": "census.support_model, R28 155f6f1c verbatim",
    "R28_MODULE_SHA256": census.R28_MODULE_SHA256,
    "PER_CELL_EXACT_EQUIVALENCE": "992/992 PASS per the Owner Packet; not re-run here",
    "SOLVER_SETTINGS": (
        "R30 used 8 CP-SAT workers with 30 s and 120 s limits; the census uses 1 worker with "
        "120 s and 600 s. An INFEASIBLE status is a property of the model, not of these."
    ),
}
NEVER_IMPORTED = (
    "UNKNOWN",
    "FEASIBLE",
    "OPTIMAL",
    "EXTERNAL_TIMEOUT",
    "OWNER_K4_MOTIF_S4_CORRECTION",
    "CURSOR_PLATEAU_CLASS_CERTIFICATE",
    "FAMILY_UPPER_BOUND",
)

Cell = tuple[str, int]
Attempt = Mapping[str, object]


class OverlayError(RuntimeError):
    """Fail-closed overlay error: nothing may be imported or concluded."""


def _obj(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise OverlayError(f"{name} must be an object")
    return cast(dict[str, object], value)


def _list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise OverlayError(f"{name} must be a list")
    return cast(list[object], value)


def _int(value: object, name: str) -> int:
    if type(value) is not int:
        raise OverlayError(f"{name} must be an integer")
    return value


def _str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise OverlayError(f"{name} must be a string")
    return value


def _is(value: object, expected: int) -> bool:
    """Exact integer equality; a bool never stands in for 0 or 1."""

    return type(value) is int and value == expected


def _pin(data: bytes, expected: str, name: str) -> None:
    if census.sha256_bytes(data) != expected:
        raise OverlayError(f"{name} SHA-256 differs from its pin")


# R30 evidence ------------------------------------------------------------------------------


def r30_result(root: Path) -> tuple[dict[str, object], bytes]:
    raw = census.git_show(root, R30_TASK_HEAD, census.R30_RESULT_RELATIVE)
    _pin(raw, R30_RESULT_SHA256, "R30 result")
    result = _obj(json.loads(raw), "R30 result")
    checkpoint = _obj(result["RESUME_CHECKPOINT"], "RESUME_CHECKPOINT")
    if (
        result.get("TASK_STATUS") != R30_TASK_STATUS
        or not _is(checkpoint.get("CHECKPOINT_ATTEMPT_COUNT"), SEGMENT1_ATTEMPTS)
        or checkpoint.get("SEGMENT1_PROOF_LOG_SHA256") != SEGMENT1_PROOF_LOG_SHA256
    ):
        raise OverlayError("R30 result is not the pinned Segment-2 terminal")
    return result, raw


def attempts_of(result: Mapping[str, object]) -> list[dict[str, object]]:
    attempts = [_obj(a, "attempt") for a in _list(result["GROUP_ATTEMPTS"], "GROUP_ATTEMPTS")]
    for index, attempt in enumerate(attempts):
        if not _is(attempt.get("ATTEMPT_INDEX"), index):
            raise OverlayError(f"R30 attempt {index} is out of order")
    return attempts


def line_sha256(attempt: Attempt) -> str:
    """SHA-256 of the attempt's proof-log line; derive checks the log is exactly these lines."""

    return census.sha256_bytes(json.dumps(attempt).encode())


def check_proof_log(raw: bytes, attempts: Sequence[Attempt]) -> bytes:
    """The proof log must be the result's attempts, line for line and byte for byte.

    Returns the Segment-1 prefix, which the caller pins.
    """

    *lines, tail = raw.split(b"\n")
    if tail != b"" or len(lines) != len(attempts):
        raise OverlayError("R30 proof log does not hold one line per result attempt")
    if any(json.dumps(a).encode() != line for a, line in zip(attempts, lines, strict=True)):
        raise OverlayError("an R30 proof-log line differs from its result attempt")
    return b"".join(line + b"\n" for line in lines[:SEGMENT1_ATTEMPTS])


def owner_steps(result: Mapping[str, object]) -> dict[int, dict[str, object]]:
    steps: dict[int, dict[str, object]] = {}
    for raw in _list(result["REFINEMENT_STEPS"], "REFINEMENT_STEPS"):
        step = _obj(raw, "step")
        if step.get("KIND") != OWNER_REFUTATION:
            continue
        index = _int(step.get("ATTEMPT_INDEX"), "step attempt")
        if index in steps:
            raise OverlayError(f"two OWNER_REFUTATION steps cite attempt {index}")
        steps[index] = step
    return steps


def segment2_batches(attempts: Sequence[Attempt]) -> list[tuple[int, int]]:
    """Consecutive Segment-2 attempt runs that share one solver child, as (first, size)."""

    batches: list[tuple[int, int]] = []
    index = SEGMENT1_ATTEMPTS
    while index < len(attempts):
        size = _int(attempts[index].get("BATCH_SIZE"), "BATCH_SIZE")
        run = attempts[index : index + size]
        if size < 1 or len(run) != size or any(not _is(a.get("BATCH_SIZE"), size) for a in run):
            raise OverlayError(f"R30 batch at attempt {index} is not one contiguous run")
        batches.append((index, size))
        index += size
    return batches


def launcher_spawns(raw: bytes, status: str) -> list[tuple[int, int]]:
    """(batch size, resume seconds) per spawn; the last line must be the terminal summary."""

    lines = raw.decode().split("\n")
    if lines[-1] != "" or len(lines) < 2:
        raise OverlayError("R30 launcher log is truncated")
    if _obj(json.loads(lines[-2]), "launcher summary").get("TASK_STATUS") != status:
        raise OverlayError("R30 launcher summary differs from the result")
    spawns: list[tuple[int, int]] = []
    for line in lines[:-2]:
        match = LAUNCHER_LINE.fullmatch(line)
        if match is None:
            raise OverlayError(f"unreadable R30 launcher line: {line!r}")
        spawns.append((int(match["size"]), int(match["resume"])))
    return spawns


def transient_exclusions(
    batches: Sequence[tuple[int, int]], spawns: Sequence[tuple[int, int]], epoch: float
) -> list[list[int]]:
    """Batches whose padded spawn interval meets the R28 window, as [first, size, resume]."""

    if [size for _, size in batches] != [size for size, _ in spawns]:
        raise OverlayError("R30 launcher spawns do not align with the Segment-2 batches")
    excluded: list[list[int]] = []
    for (first, size), (_, resume) in zip(batches, spawns, strict=True):
        low = floor(epoch * 1000) + resume * 1000 - SPAWN_ROUNDING_MS
        high = ceil(epoch * 1000) + resume * 1000 + SPAWN_ROUNDING_MS + CHILD_IMPORT_SLACK_MS
        if high >= TRANSIENT_START_MS and low <= TRANSIENT_END_MS:
            excluded.append([first, size, resume])
    return excluded


def excluded_attempts(excluded: Sequence[Sequence[int]]) -> set[int]:
    return {i for first, size, *_ in excluded for i in range(first, first + size)}


# Eligibility -------------------------------------------------------------------------------


def failed_criteria(
    row: census.SliceRow,
    index: int,
    attempt: Attempt,
    step: Attempt | None,
    exposed: bool,
) -> list[str]:
    """Every eligibility criterion this attempt fails for this cell; empty means eligible."""

    t = row.cap
    wedges = census.wedge_count(row.profile)
    ceiling = wedges - 3 * t
    ids = attempt.get("PROFILE_IDS")
    checks = {
        "SOURCE_IDENTITY": _is(attempt.get("ATTEMPT_INDEX"), index),
        "ROUTE_A": attempt.get("ROUTE") == ROUTE_A,
        "SINGLE_PROFILE": isinstance(ids, list) and len(cast(list[object], ids)) == 1,
        "SAME_PROFILE": isinstance(ids, list) and row.profile_id in cast(list[object], ids),
        "STATUS_INFEASIBLE": attempt.get("STATUS") == census.INFEASIBLE,
        "CERTIFICATE_CP_SAT_INFEASIBLE": attempt.get("CERTIFICATE_KIND") == CERTIFICATE,
        "NORMAL_TERMINATION": "ERROR" not in attempt
        and _is(attempt.get("EXTERNAL_TIMEOUT_EXIT_CODE"), 0),
        "SAME_T": _is(attempt.get("REFUTED_GRAPH_TRIANGLE_COUNT"), t)
        and _is(attempt.get("CURRENT_TRIANGLE_CAP"), t),
        "SAME_WEDGE_COUNT": _is(attempt.get("WEDGE_COUNT"), wedges),
        "SAME_CEILING": _is(attempt.get("OPEN_WEDGE_CEILING_REFUTED"), ceiling),
        "SINGLE_PROFILE_MODEL": _is(
            attempt.get("OPEN_WEDGE_INDICATOR_COUNT"), OPEN_WEDGE_INDICATORS
        ),
        "ADOPTED_CAP_T_MINUS_1": _is(attempt.get("TARGET_TRIANGLE_CAP"), t - 1)
        and _is(attempt.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"), t - 1)
        and _is(attempt.get("CERTIFIED_OPEN_WEDGE_LOWER_BOUND"), ceiling + 1)
        and step is not None
        and step.get("KIND") == OWNER_REFUTATION
        and _is(step.get("ATTEMPT_INDEX"), index)
        and step.get("PROFILE_ID") == row.profile_id
        and _is(step.get("TRIANGLE_CAP"), t - 1),
        "OUTSIDE_R28_TRANSIENT_WINDOW": not exposed,
    }
    return [name for name in CRITERIA if not checks[name]]


def cell_of(row: census.SliceRow) -> Cell:
    if len(row.band) != 1 or row.band[0][0] != row.cap:
        raise OverlayError(f"{row.profile_id}: a Slice-1 cell is one profile at one T")
    return row.profile_id, row.cap


def candidates(attempts: Sequence[Attempt], cell: Cell) -> list[int]:
    profile, t = cell
    return [
        i
        for i, a in enumerate(attempts)
        if isinstance(a.get("PROFILE_IDS"), list)
        and profile in cast(list[object], a["PROFILE_IDS"])
        and (_is(a.get("CURRENT_TRIANGLE_CAP"), t) or _is(a.get("REFUTED_GRAPH_TRIANGLE_COUNT"), t))
    ]


def classify(
    rows: Sequence[census.SliceRow],
    attempts: Sequence[Attempt],
    steps: Mapping[int, Attempt],
    exposed: set[int],
) -> tuple[list[list[object]], list[list[object]]]:
    """Import rows and the audited non-imported cells, both in manifest order."""

    imports: list[list[object]] = []
    rejected: list[list[object]] = []
    for row in rows:
        cell = cell_of(row)
        audit: list[list[object]] = []
        passing: list[int] = []
        for i in candidates(attempts, cell):
            failed = failed_criteria(row, i, attempts[i], steps.get(i), i in exposed)
            audit.append([i, attempts[i].get("STATUS"), failed])
            if not failed:
                passing.append(i)
        if len(passing) > 1:
            raise OverlayError(f"{cell}: more than one eligible R30 refutation {passing}")
        if not passing:
            rejected.append([*cell, audit])
            continue
        i = passing[0]
        wedges = census.wedge_count(row.profile)
        request = census.SolveRequest(row.profile, row.cap, (), census.SOLVE_SECONDS)
        imports.append(
            [
                *cell,
                wedges,
                wedges - 3 * row.cap,
                i,
                attempts[i].get("STAGE"),
                line_sha256(attempts[i]),
                request.digest(),
            ]
        )
    return imports, rejected


def window_only(rejected: Sequence[Sequence[object]]) -> int:
    """Cells whose only failing candidate criterion was the R28 transient window."""

    return sum(
        any(f == ["OUTSIDE_R28_TRANSIENT_WINDOW"] for *_, f in cast(list[list[object]], r[2]))
        for r in rejected
    )


# Overlay ledger ----------------------------------------------------------------------------


def shared_probe(result: Mapping[str, object]) -> dict[str, object]:
    """R30 recorded the same model proto hash as the census pins for the same probe."""

    identity = _obj(result["MODEL_IDENTITY"], "MODEL_IDENTITY")
    probe = (identity.get("PROBE_PROFILE"), identity.get("CEILING"))
    proto = identity.get("MODEL_PROTO_TEXT_SHA256")
    if identity.get("STATUS") != "PASS" or (*probe, proto) not in census.MODEL_PROBES:
        raise OverlayError("R30 model identity is not a census-pinned model probe")
    return {"PROFILE_ID": probe[0], "CEILING": probe[1], "MODEL_PROTO_TEXT_SHA256": proto}


def derive_overlay(
    manifest: census.Manifest, root: Path, proof_raw: bytes, launcher_raw: bytes
) -> dict[str, object]:
    result, _ = r30_result(root)
    attempts = attempts_of(result)
    _pin(proof_raw, R30_PROOF_LOG_SHA256, "R30 proof log")
    prefix = check_proof_log(proof_raw, attempts)
    _pin(prefix, SEGMENT1_PROOF_LOG_SHA256, "R30 Segment-1 proof-log prefix")
    r28 = census.git_show(root, R30_TASK_HEAD, census.R28_MODULE_RELATIVE)
    _pin(r28, census.R28_MODULE_SHA256, "R28 module at the R30 task head")
    epoch = result["RESUME_STARTED_UNIX_TIME"]
    if not isinstance(epoch, float):
        raise OverlayError("R30 resume start time must be a float")
    _pin(launcher_raw, R30_LAUNCHER_LOG_SHA256, "R30 launcher log")
    spawns = launcher_spawns(launcher_raw, R30_TASK_STATUS)
    excluded = transient_exclusions(segment2_batches(attempts), spawns, epoch)
    imports, rejected = classify(
        manifest.rows, attempts, owner_steps(result), excluded_attempts(excluded)
    )
    slice1 = _obj(manifest.data["SLICE1"], "SLICE1")
    return {
        "SCHEMA_VERSION": 1,
        "TASK_ID": TASK_ID,
        "KIND": "EXACT_CELL_REFUTATION_IMPORT_OVERLAY",
        "CENSUS": {
            "TASK_ID": census.TASK_ID,
            "SOURCE_COMMIT": CENSUS_SOURCE_COMMIT,
            "MANIFEST_RELATIVE": census.MANIFEST_RELATIVE,
            "MANIFEST_SHA256": manifest.sha256,
            "ENGINE_SHA256": CENSUS_ENGINE_SHA256,
            "PROFILES_SHA256": slice1["PROFILES_SHA256"],
            "CELL_COUNT": len(manifest.rows),
            "CELL": "ONE_PROFILE_AT_ONE_T_CHASE_WITHOUT_EXCLUSIONS",
        },
        "R30": {
            "TASK_HEAD": R30_TASK_HEAD,
            "RESULT_RELATIVE": census.R30_RESULT_RELATIVE,
            "RESULT_SHA256": R30_RESULT_SHA256,
            "TASK_STATUS": R30_TASK_STATUS,
            "PROOF_LOG_RELATIVE": R30_PROOF_LOG_RELATIVE,
            "PROOF_LOG_SHA256": R30_PROOF_LOG_SHA256,
            "PROOF_LOG_LINES": len(attempts),
            "SEGMENT1_ATTEMPTS": SEGMENT1_ATTEMPTS,
            "SEGMENT1_PROOF_LOG_SHA256": SEGMENT1_PROOF_LOG_SHA256,
            "LAUNCHER_LOG_RELATIVE": R30_LAUNCHER_LOG_RELATIVE,
            "LAUNCHER_LOG_SHA256": R30_LAUNCHER_LOG_SHA256,
            "RESUME_STARTED_UNIX_TIME": epoch,
        },
        "OWNER_DISPOSITION": OWNER_DISPOSITION,
        "TRANSIENT_WINDOW": {
            "START_MS": TRANSIENT_START_MS,
            "END_MS": TRANSIENT_END_MS,
            "START_UTC": "2026-10-08T06:00:20.400Z",
            "END_UTC": "2026-10-08T06:04:40.247Z",
            "SPAWN_ROUNDING_MS": SPAWN_ROUNDING_MS,
            "CHILD_IMPORT_SLACK_MS": CHILD_IMPORT_SLACK_MS,
            "RULE": "EXCLUDE_EVERY_SEGMENT2_BATCH_WHOSE_PADDED_SPAWN_INTERVAL_MEETS_THE_WINDOW",
            "EXCLUDED_BATCHES": excluded,
            "EXCLUDED_ATTEMPTS": sum(size for _, size, _ in excluded),
            "ELIGIBLE_CELLS_EXCLUDED_ONLY_BY_WINDOW": window_only(rejected),
        },
        "MODEL_EQUIVALENCE": {**MODEL_EQUIVALENCE, "SHARED_PROBE": shared_probe(result)},
        "ELIGIBILITY_CRITERIA": list(CRITERIA),
        "NEVER_IMPORTED": list(NEVER_IMPORTED),
        "IMPORT_COLUMNS": list(IMPORT_COLUMNS),
        "IMPORT_COUNT": len(imports),
        "IMPORTS_SHA256": census.sha256_bytes(census.canonical_json(imports).encode()),
        "IMPORTS": imports,
        "NOT_IMPORTED": rejected,
    }


def render_overlay(overlay: Mapping[str, object]) -> bytes:
    """Canonical bytes: sorted keys, one compact import row per line."""

    rows = _list(overlay["IMPORTS"], "IMPORTS")
    marker = json.dumps("__OVERLAY_IMPORTS__")
    text = json.dumps({**overlay, "IMPORTS": "__OVERLAY_IMPORTS__"}, indent=1, sort_keys=True)
    if text.count(marker) != 1:
        raise OverlayError("overlay marker collision")
    body = ",\n".join("  " + json.dumps(row, separators=(",", ":")) for row in rows)
    return (text.replace(marker, "[\n" + body + "\n ]") + "\n").encode()


@dataclass(frozen=True, slots=True)
class Overlay:
    sha256: str
    data: Mapping[str, object]
    imports: Mapping[Cell, tuple[object, ...]]
    r30_realized: frozenset[Cell]


def parse_overlay(data: Mapping[str, object], sha: str) -> Overlay:
    """Structural checks that need no R30 or census bytes."""

    window = _obj(data["TRANSIENT_WINDOW"], "TRANSIENT_WINDOW")
    pinned = _obj(data["CENSUS"], "CENSUS")
    if (
        data.get("TASK_ID") != TASK_ID
        or data.get("IMPORT_COLUMNS") != list(IMPORT_COLUMNS)
        or data.get("ELIGIBILITY_CRITERIA") != list(CRITERIA)
        or pinned.get("MANIFEST_SHA256") != census.MANIFEST_SHA256
        or pinned.get("ENGINE_SHA256") != CENSUS_ENGINE_SHA256
        or _obj(data["R30"], "R30").get("RESULT_SHA256") != R30_RESULT_SHA256
    ):
        raise OverlayError("overlay does not bind the pinned census and R30 authorities")
    rows = _list(data["IMPORTS"], "IMPORTS")
    if data.get("IMPORT_COUNT") != len(rows) or data.get("IMPORTS_SHA256") != census.sha256_bytes(
        census.canonical_json(rows).encode()
    ):
        raise OverlayError("overlay import digest or count differs")
    excluded = excluded_attempts(
        [
            [_int(v, "batch") for v in _list(b, "batch")]
            for b in _list(window["EXCLUDED_BATCHES"], "")
        ]
    )
    imports: dict[Cell, tuple[object, ...]] = {}
    sources: set[int] = set()
    for raw in rows:
        row = tuple(_list(raw, "import row"))
        if len(row) != len(IMPORT_COLUMNS):
            raise OverlayError("overlay import rows have the pinned columns")
        cell = (_str(row[0], "profile"), _int(row[1], "T"))
        source = _int(row[4], "attempt")
        if cell in imports or source in sources:
            raise OverlayError(f"duplicate overlay import {cell} from attempt {source}")
        if source in excluded:
            raise OverlayError(f"{cell} imports attempt {source} from the R28 transient window")
        imports[cell] = row
        sources.add(source)
    realized: set[Cell] = set()
    for raw in _list(data["NOT_IMPORTED"], "NOT_IMPORTED"):
        entry = _list(raw, "non-imported cell")
        cell = (_str(entry[0], "profile"), _int(entry[1], "T"))
        if cell in imports:
            raise OverlayError(f"{cell} is both imported and not imported")
        statuses = {_list(a, "audit")[1] for a in _list(entry[2], "audit")}
        if statuses & set(census.REALIZED):
            realized.add(cell)
    return Overlay(sha, data, imports, frozenset(realized))


def load_overlay(path: Path | None = None, expected_sha256: str = OVERLAY_SHA256) -> Overlay:
    raw = (path or census.repo_root() / OVERLAY_RELATIVE).read_bytes()
    _pin(raw, expected_sha256, "overlay")
    data = _obj(json.loads(raw), "overlay")
    if render_overlay(data) != raw:
        raise OverlayError("overlay bytes are not canonical")
    return parse_overlay(data, census.sha256_bytes(raw))


def verify_overlay(overlay: Overlay, manifest: census.Manifest, root: Path) -> None:
    """Re-derive every import and rejection from the pinned R30 result alone."""

    result, _ = r30_result(root)
    attempts = attempts_of(result)
    window = _obj(overlay.data["TRANSIENT_WINDOW"], "TRANSIENT_WINDOW")
    excluded = cast(list[list[int]], window["EXCLUDED_BATCHES"])
    batches = segment2_batches(attempts)
    if any((first, size) not in batches for first, size, _ in excluded):
        raise OverlayError("an excluded batch is not a Segment-2 batch")
    imports, rejected = classify(
        manifest.rows, attempts, owner_steps(result), excluded_attempts(excluded)
    )
    if imports != overlay.data["IMPORTS"] or rejected != overlay.data["NOT_IMPORTED"]:
        raise OverlayError("overlay differs from its re-derivation from the R30 result")
    if _obj(overlay.data["MODEL_EQUIVALENCE"], "MODEL_EQUIVALENCE").get(
        "SHARED_PROBE"
    ) != shared_probe(result):
        raise OverlayError("overlay model probe differs from R30's")


def write_new(path: Path, data: bytes) -> None:
    """The ledger is immutable: an existing file is never replaced."""

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


# Read-only census snapshot and combined verdict --------------------------------------------


@dataclass(frozen=True, slots=True)
class CensusSnapshot:
    sha256: str
    length: int
    lines: int
    partial_tail_bytes: int
    chase: Mapping[Cell, tuple[str, ...]]
    requests: Mapping[Cell, str]
    done: Mapping[str, Mapping[str, object]]


def read_census_proof(raw: bytes, manifest: census.Manifest) -> CensusSnapshot:
    """Verify the census proof log's complete lines exactly as the engine would on restart.

    A live writer may be mid-append, so an unterminated last line is set aside, not read.
    """

    end = raw.rfind(b"\n") + 1
    complete = raw[:end]
    header = {
        "TASK_ID": census.TASK_ID,
        "MANIFEST_SHA256": census.MANIFEST_SHA256,
        "ENGINE_SHA256": CENSUS_ENGINE_SHA256,
        "LOG": "PROOF",
    }
    caps = {row.profile_id: row for row in manifest.rows}
    seen: set[tuple[object, ...]] = set()
    chase: dict[Cell, list[str]] = {}
    requests: dict[Cell, str] = {}
    done: dict[str, Mapping[str, object]] = {}
    last = census.GENESIS
    lines = complete.split(b"\n")[:-1]
    for number, line in enumerate(lines):
        record = _obj(json.loads(line), "census line")
        if set(record) != {"KEY", "PREV_SHA256", "BODY", "LINE_SHA256"}:
            raise OverlayError(f"census line {number} has the wrong fields")
        content = {k: record[k] for k in ("KEY", "PREV_SHA256", "BODY")}
        if (
            census.canonical_json(record).encode() != line
            or record["PREV_SHA256"] != last
            or record["LINE_SHA256"] != census.sha256_bytes(census.canonical_json(content).encode())
        ):
            raise OverlayError(f"census proof-log hash chain broken at line {number}")
        key = tuple(_list(record["KEY"], "KEY"))
        body = _obj(record["BODY"], "BODY")
        if key in seen or (number == 0) != (key == ("HEADER",)):
            raise OverlayError(f"census line {number} repeats a key or misplaces the header")
        seen.add(key)
        last = _str(record["LINE_SHA256"], "LINE_SHA256")
        if number == 0 and body != header:
            raise OverlayError("census proof-log header is not the pinned census")
        if key[0] == "PROFILE_DONE":
            done[_str(key[1], "profile")] = body
        if key[0] != "SOLVE" or key[3] != "CHASE":
            continue
        # ("SOLVE", profile, T, "CHASE", 0, try): try 0 is the 120 s solve, try 1 its retry.
        cell = (_str(key[1], "profile"), _int(key[2], "T"))
        row = caps.get(cell[0])
        statuses = chase.setdefault(cell, [])
        if (
            row is None
            or row.cap != cell[1]
            or body.get("CEILING") != (census.wedge_count(row.profile) - 3 * row.cap)
            or len(key) != 6
            or key[4] != 0
            or key[5] != len(statuses)
            or len(statuses) > 1
        ):
            raise OverlayError(f"census chase {key} is not a Slice-1 cell solve in order")
        if key[5] == 0:
            requests[cell] = _str(body.get("REQUEST_SHA256"), "REQUEST_SHA256")
        statuses.append(_str(body.get("STATUS"), "STATUS"))
    return CensusSnapshot(
        census.sha256_bytes(complete),
        len(complete),
        len(lines),
        len(raw) - end,
        {cell: tuple(statuses) for cell, statuses in chase.items()},
        requests,
        done,
    )


def census_status(snapshot: CensusSnapshot, cell: Cell) -> str:
    statuses = snapshot.chase.get(cell, ())
    if census.INFEASIBLE in statuses:
        state = "REFUTED"
    elif any(s in census.REALIZED for s in statuses):
        state = "REALIZED"
    elif len(statuses) == 2:
        state = "UNRESOLVED"
    else:
        state = "IN_PROGRESS" if statuses else "NOT_REACHED"
    done = snapshot.done.get(cell[0])
    if done is not None:
        expected = {
            "REALIZED": ("REALIZED", "MAX_REALIZABLE_T"),
            "REFUTED": ("NO_REALIZATION_IN_SLICE", None),
            "UNRESOLVED": ("UNRESOLVED_AFTER_RETRY", "UNRESOLVED_T"),
        }.get(state)
        refuted = done.get("REFUTED_T") == ([cell[1]] if state == "REFUTED" else [])
        if (
            expected is None
            or done.get("STATUS") != expected[0]
            or (expected[1] is not None and done.get(expected[1]) != cell[1])
            or not refuted
        ):
            raise OverlayError(f"census PROFILE_DONE for {cell} disagrees with its chase solves")
    return state


def combined_verdict(
    manifest: census.Manifest, overlay: Overlay, snapshot: CensusSnapshot
) -> dict[str, object]:
    """Census evidence plus the approved overlay, cell by cell; contradictions fail closed."""

    sources: dict[str, int] = {}
    census_states: dict[str, int] = {}
    feasible: list[list[object]] = []
    open_cells: list[list[object]] = []
    parity = {"CENSUS_DECIDED": 0, "R30_AGREES": 0, "R30_SILENT": 0}
    for row in manifest.rows:
        cell = cell_of(row)
        state = census_status(snapshot, cell)
        census_states[state] = census_states.get(state, 0) + 1
        imported = overlay.imports.get(cell)
        if (
            imported is not None
            and cell in snapshot.requests
            and imported[7] != (snapshot.requests[cell])
        ):
            raise OverlayError(f"{cell}: census chase request differs from the overlay's")
        if state == "REALIZED" and imported is not None:
            raise OverlayError(f"CONTRADICTION {cell}: census realized what R30 refuted")
        if state == "REFUTED" and cell in overlay.r30_realized:
            raise OverlayError(f"CONTRADICTION {cell}: census refuted what R30 realized")
        if state in ("REALIZED", "REFUTED"):
            parity["CENSUS_DECIDED"] += 1
            agrees = imported is not None if state == "REFUTED" else cell in overlay.r30_realized
            parity["R30_AGREES" if agrees else "R30_SILENT"] += 1
        if state == "REALIZED":
            feasible.append([*cell])
            continue
        if state == "REFUTED" or imported is not None:
            source = (
                "BOTH"
                if state == "REFUTED" and imported
                else "CENSUS"
                if state == "REFUTED"
                else "OVERLAY_ONLY_CENSUS_" + state
            )
            sources[source] = sources.get(source, 0) + 1
            continue
        open_cells.append([*cell, state])
    refuted = sum(sources.values())
    return {
        "TASK_ID": TASK_ID,
        "VERDICT_KIND": "READ_ONLY_COMBINED_CENSUS_PLUS_OVERLAY",
        "CENSUS_MANIFEST_SHA256": manifest.sha256,
        "CENSUS_PROOF_SNAPSHOT": {
            "SHA256": snapshot.sha256,
            "BYTES": snapshot.length,
            "LINES": snapshot.lines,
            "PARTIAL_TAIL_BYTES_IGNORED": snapshot.partial_tail_bytes,
            "PROFILES_DONE": len(snapshot.done),
        },
        "OVERLAY_SHA256": overlay.sha256,
        "TOTAL_CELLS": len(manifest.rows),
        "REFUTED_CELL_COUNT": refuted,
        "FEASIBLE_CELL_COUNT": len(feasible),
        "OPEN_CELL_COUNT": len(open_cells),
        "REFUTED_BY_SOURCE": dict(sorted(sources.items())),
        "CENSUS_CELL_STATES": dict(sorted(census_states.items())),
        "HISTORICAL_CENSUS_PARITY": parity,
        "CONTRADICTIONS": 0,
        "FEASIBLE_CELLS": feasible,
        "OPEN_CELLS": open_cells,
        "SLICE1_ALL_CELLS_DECIDED": not open_cells,
        "SLICE2": "NOT_EVALUATED",
    }


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)
    derive = commands.add_parser("derive")
    derive.add_argument("--r30-proof-log", type=Path, required=True)
    derive.add_argument("--r30-launcher-log", type=Path, required=True)
    derive.add_argument("--output", type=Path, required=True)
    commands.add_parser("verify")
    verdict = commands.add_parser("verdict")
    verdict.add_argument("--census-proof-log", type=Path, required=True)
    args = parser.parse_args(argv)
    root = census.repo_root()
    manifest = census.load_manifest()
    if args.command == "derive":
        overlay = derive_overlay(
            manifest, root, args.r30_proof_log.read_bytes(), args.r30_launcher_log.read_bytes()
        )
        data = render_overlay(overlay)
        write_new(args.output, data)
        print(json.dumps({"OVERLAY": str(args.output), "SHA256": census.sha256_bytes(data)}))
        return
    overlay = load_overlay()
    verify_overlay(overlay, manifest, root)
    if args.command == "verify":
        print(json.dumps({"OVERLAY_SHA256": overlay.sha256, "IMPORTS": len(overlay.imports)}))
        return
    snapshot = read_census_proof(args.census_proof_log.read_bytes(), manifest)
    print(json.dumps(combined_verdict(manifest, overlay, snapshot), indent=1))


if __name__ == "__main__":
    main()
