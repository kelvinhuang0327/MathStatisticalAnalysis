"""Contract tests for the R30 exact-refutation overlay of the K20 fiber Slice-1 census.

No solver runs. Eligibility, window and verdict logic use synthetic attempts and synthetic
census proof logs. The pinned overlay is re-derived from the R30 result when R30 task head
6ba48113 is in the local object store.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_fiber_slice1_r30_refutation_overlay as overlay

ROOT = Path(__file__).resolve().parents[2]
INCUMBENT = "55555555555511111100"
OTHER_A = "66666665332221111111"
OTHER_B = "66666665322222211110"
OPEN_CELL = ("66665555555322000000", 266)
OVERLAY_FILE = ROOT / overlay.OVERLAY_RELATIVE


def r30_available() -> bool:
    probe = ["git", "cat-file", "-e", f"{overlay.R30_TASK_HEAD}^{{commit}}"]
    return subprocess.run(probe, cwd=ROOT, capture_output=True).returncode == 0


needs_r30 = pytest.mark.skipif(
    not r30_available(), reason="R30 task head 6ba48113 is not in the local object store"
)


def row(pid: str, t: int) -> census.SliceRow:
    return census.SliceRow(pid, census.decode_profile(pid), 313_587_560, t, ((t, 313_587_560),))


ROWS = (row(INCUMBENT, 270), row(OTHER_A, 269), row(OTHER_B, 269))
MANIFEST = census.Manifest(census.MANIFEST_SHA256, {}, ROWS, census.SLICE1_FLOOR, 16, 0)


def attempt(pid: str, t: int, index: int, **changes: object) -> dict[str, object]:
    wedges = census.wedge_count(census.decode_profile(pid))
    base: dict[str, object] = {
        "ATTEMPT_INDEX": index,
        "STAGE": "OWNER_MEMBER",
        "CURRENT_TRIANGLE_CAP": t,
        "TARGET_TRIANGLE_CAP": t - 1,
        "ROUTE": overlay.ROUTE_A,
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
        "PROFILE_IDS": [pid],
        "WEDGE_COUNT": wedges,
        "REFUTED_GRAPH_TRIANGLE_COUNT": t,
        "OPEN_WEDGE_CEILING_REFUTED": wedges - 3 * t,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": t - 1,
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": wedges - 3 * t + 1,
        "OPEN_WEDGE_INDICATOR_COUNT": 3420,
        "EXTERNAL_TIMEOUT_EXIT_CODE": 0,
        "BATCH_SIZE": 1,
    }
    return {**base, **changes}


def step(pid: str, t: int, index: int, **changes: object) -> dict[str, object]:
    base: dict[str, object] = {
        "KIND": "OWNER_REFUTATION",
        "ATTEMPT_INDEX": index,
        "PROFILE_ID": pid,
        "TRIANGLE_CAP": t - 1,
    }
    return {**base, **changes}


def request_digest(pid: str, t: int, seconds: float = census.SOLVE_SECONDS) -> str:
    return census.SolveRequest(census.decode_profile(pid), t, (), seconds).digest()


# Eligibility -------------------------------------------------------------------------------


def test_single_profile_route_a_infeasible_attempt_passes_every_criterion() -> None:
    assert overlay.OPEN_WEDGE_INDICATORS == 3420
    good = attempt(OTHER_A, 269, 7)
    assert overlay.failed_criteria(ROWS[1], 7, good, step(OTHER_A, 269, 7), False) == []


ATTEMPT_MUTATIONS: list[tuple[str, dict[str, object], list[str]]] = [
    ("index", {"ATTEMPT_INDEX": 8}, ["SOURCE_IDENTITY"]),
    ("motif route", {"ROUTE": "D4_K4_MOTIF_S4_CORRECTION"}, ["ROUTE_A"]),
    ("group solve", {"PROFILE_IDS": [OTHER_A, OTHER_B]}, ["SINGLE_PROFILE"]),
    ("other profile", {"PROFILE_IDS": [OTHER_B]}, ["SAME_PROFILE"]),
    ("unknown", {"STATUS": "UNKNOWN"}, ["STATUS_INFEASIBLE"]),
    ("feasible", {"STATUS": "FEASIBLE"}, ["STATUS_INFEASIBLE"]),
    ("optimal", {"STATUS": "OPTIMAL"}, ["STATUS_INFEASIBLE"]),
    (
        "timeout",
        {"STATUS": "EXTERNAL_TIMEOUT", "ERROR": "timeout", "EXTERNAL_TIMEOUT_EXIT_CODE": -9},
        ["STATUS_INFEASIBLE", "NORMAL_TERMINATION"],
    ),
    ("motif certificate", {"CERTIFICATE_KIND": "K4_MOTIF_S4"}, ["CERTIFICATE_CP_SAT_INFEASIBLE"]),
    ("killed child", {"EXTERNAL_TIMEOUT_EXIT_CODE": 124}, ["NORMAL_TERMINATION"]),
    ("bool exit code", {"EXTERNAL_TIMEOUT_EXIT_CODE": False}, ["NORMAL_TERMINATION"]),
    ("child error", {"ERROR": "child died"}, ["NORMAL_TERMINATION"]),
    ("other refuted T", {"REFUTED_GRAPH_TRIANGLE_COUNT": 268}, ["SAME_T"]),
    ("other current cap", {"CURRENT_TRIANGLE_CAP": 270}, ["SAME_T"]),
    ("other wedge count", {"WEDGE_COUNT": 821}, ["SAME_WEDGE_COUNT"]),
    ("other ceiling", {"OPEN_WEDGE_CEILING_REFUTED": 16}, ["SAME_CEILING"]),
    ("union model", {"OPEN_WEDGE_INDICATOR_COUNT": 6840}, ["SINGLE_PROFILE_MODEL"]),
    ("target cap", {"TARGET_TRIANGLE_CAP": 267}, ["ADOPTED_CAP_T_MINUS_1"]),
    ("certified cap", {"CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": 269}, ["ADOPTED_CAP_T_MINUS_1"]),
    ("certified wedges", {"CERTIFIED_OPEN_WEDGE_LOWER_BOUND": 13}, ["ADOPTED_CAP_T_MINUS_1"]),
]


@pytest.mark.parametrize(
    ("changes", "failed"),
    [pytest.param(c, f, id=name) for name, c, f in ATTEMPT_MUTATIONS],
)
def test_each_attempt_defect_fails_exactly_its_criterion(
    changes: dict[str, object], failed: list[str]
) -> None:
    bad = attempt(OTHER_A, 269, 7, **changes)
    assert overlay.failed_criteria(ROWS[1], 7, bad, step(OTHER_A, 269, 7), False) == failed


STEP_MUTATIONS: list[tuple[str, dict[str, object] | None]] = [
    ("no adoption step", None),
    ("plateau step", {"KIND": "CURSOR_PLATEAU_CLASS_CERTIFICATE"}),
    ("motif step", {"KIND": "OWNER_K4_MOTIF_S4_CORRECTION"}),
    ("other attempt", {"ATTEMPT_INDEX": 6}),
    ("other profile", {"PROFILE_ID": OTHER_B}),
    ("adopted cap T - 2", {"TRIANGLE_CAP": 267}),
    ("adopted cap T", {"TRIANGLE_CAP": 269}),
]


@pytest.mark.parametrize("changes", [pytest.param(c, id=name) for name, c in STEP_MUTATIONS])
def test_refutation_needs_its_own_adoption_of_cap_t_minus_1(
    changes: dict[str, object] | None,
) -> None:
    adoption = None if changes is None else step(OTHER_A, 269, 7, **changes)
    failed = overlay.failed_criteria(ROWS[1], 7, attempt(OTHER_A, 269, 7), adoption, False)
    assert failed == ["ADOPTED_CAP_T_MINUS_1"]


def test_transient_window_attempt_is_not_eligible() -> None:
    failed = overlay.failed_criteria(
        ROWS[1], 7, attempt(OTHER_A, 269, 7), step(OTHER_A, 269, 7), True
    )
    assert failed == ["OUTSIDE_R28_TRANSIENT_WINDOW"]


def test_classify_imports_one_audited_row_per_eligible_cell() -> None:
    attempts = [
        attempt(INCUMBENT, 270, 0, STATUS="OPTIMAL", CERTIFICATE_KIND="CP_SAT_FEASIBLE"),
        attempt(OTHER_A, 269, 1, STATUS="UNKNOWN", CERTIFICATE_KIND="NONE"),
        attempt(OTHER_A, 269, 2, STAGE="OWNER_MEMBER_RETRY"),
        attempt(OTHER_B, 269, 3),
        attempt(OTHER_B, 268, 4),
    ]
    steps = {i: step(pid, t, i) for i, pid, t in ((2, OTHER_A, 269), (3, OTHER_B, 269))}
    imports, rejected = overlay.classify(ROWS, attempts, steps, exposed={3})
    wedges = census.wedge_count(census.decode_profile(OTHER_A))
    assert imports == [
        [
            OTHER_A,
            269,
            wedges,
            wedges - 3 * 269,
            2,
            "OWNER_MEMBER_RETRY",
            census.sha256_bytes(json.dumps(attempts[2]).encode()),
            request_digest(OTHER_A, 269),
        ]
    ]
    assert [r[:2] for r in rejected] == [[INCUMBENT, 270], [OTHER_B, 269]]
    assert rejected[1][2] == [[3, "INFEASIBLE", ["OUTSIDE_R28_TRANSIENT_WINDOW"]]]
    assert overlay.window_only(rejected) == 1


def test_two_eligible_refutations_of_one_cell_fail_closed() -> None:
    attempts = [attempt(OTHER_A, 269, 0), attempt(OTHER_A, 269, 1)]
    steps = {i: step(OTHER_A, 269, i) for i in (0, 1)}
    with pytest.raises(overlay.OverlayError, match="more than one eligible"):
        overlay.classify(ROWS[1:2], attempts, steps, exposed=set())


def test_a_cell_is_one_profile_at_one_t() -> None:
    wide = census.SliceRow(OTHER_A, ROWS[1].profile, 1, 269, ((269, 1), (268, 1)))
    with pytest.raises(overlay.OverlayError, match="one profile at one T"):
        overlay.classify((wide,), [], {}, exposed=set())


# R30 logs and the R28 transient window -----------------------------------------------------


def test_proof_log_must_be_the_result_attempts_verbatim() -> None:
    attempts = [attempt(OTHER_A, 269, i) for i in range(3)]
    raw = b"".join(json.dumps(a).encode() + b"\n" for a in attempts)
    assert overlay.check_proof_log(raw, attempts) == raw
    with pytest.raises(overlay.OverlayError, match="differs from its result"):
        overlay.check_proof_log(
            raw.replace(b'"STAGE": "OWNER_MEMBER"', b'"STAGE": "X"', 1), attempts
        )
    with pytest.raises(overlay.OverlayError, match="one line per result attempt"):
        overlay.check_proof_log(raw[:-1], attempts)


def segment(sizes: list[int]) -> list[dict[str, object]]:
    attempts: list[dict[str, object]] = [{} for _ in range(overlay.SEGMENT1_ATTEMPTS)]
    for size in sizes:
        attempts.extend(dict[str, object](BATCH_SIZE=size) for _ in range(size))
    return attempts


def test_segment2_batches_are_contiguous_runs() -> None:
    first = overlay.SEGMENT1_ATTEMPTS
    assert overlay.segment2_batches(segment([2, 1, 3])) == [
        (first, 2),
        (first + 2, 1),
        (first + 3, 3),
    ]
    broken = segment([3])[:-1]
    with pytest.raises(overlay.OverlayError, match="contiguous run"):
        overlay.segment2_batches(broken)


def launcher(lines: list[str], status: str = overlay.R30_TASK_STATUS) -> bytes:
    summary = json.dumps({"TASK_STATUS": status})
    return ("\n".join([*lines, summary]) + "\n").encode()


def spawn_line(size: int, resume: int) -> str:
    return f"{size} solve(s), family 313587560, ledger 1399, resume {resume}s, total {resume}s"


def test_launcher_log_parses_spawns_and_fails_closed() -> None:
    raw = launcher([spawn_line(64, 8), spawn_line(1, 36)])
    assert overlay.launcher_spawns(raw, overlay.R30_TASK_STATUS) == [(64, 8), (1, 36)]
    with pytest.raises(overlay.OverlayError, match="summary differs"):
        overlay.launcher_spawns(launcher([spawn_line(1, 1)], "STOPPED"), overlay.R30_TASK_STATUS)
    with pytest.raises(overlay.OverlayError, match="unreadable"):
        overlay.launcher_spawns(launcher(["64 solves"]), overlay.R30_TASK_STATUS)
    with pytest.raises(overlay.OverlayError, match="truncated"):
        overlay.launcher_spawns(raw[:-1], overlay.R30_TASK_STATUS)


def test_window_excludes_every_batch_whose_padded_spawn_meets_it() -> None:
    # The window opens 100.4 s and closes 360.247 s after this epoch.
    epoch = (overlay.TRANSIENT_START_MS - 100_400) / 1000
    assert epoch == float(int(epoch))
    first = overlay.SEGMENT1_ATTEMPTS
    batches = [(first, 2), (first + 2, 1), (first + 3, 3), (first + 6, 1)]
    spawns = [(2, 89), (1, 90), (3, 360), (1, 361)]
    assert overlay.transient_exclusions(batches, spawns, epoch) == [
        [first + 2, 1, 90],
        [first + 3, 3, 360],
    ]
    assert overlay.excluded_attempts([[first + 3, 3, 360]]) == {first + 3, first + 4, first + 5}
    with pytest.raises(overlay.OverlayError, match="do not align"):
        overlay.transient_exclusions(batches, spawns[:-1], epoch)


# Read-only census snapshot and the combined verdict ----------------------------------------

CENSUS_HEADER: dict[str, object] = {
    "TASK_ID": census.TASK_ID,
    "MANIFEST_SHA256": census.MANIFEST_SHA256,
    "ENGINE_SHA256": overlay.CENSUS_ENGINE_SHA256,
    "LOG": "PROOF",
}


def census_log(
    path: Path,
    chases: Mapping[tuple[str, int], list[str]],
    header: Mapping[str, object] = CENSUS_HEADER,
) -> bytes:
    """A proof log written by the census engine's own durable log class."""

    log = census.DurableLog(path, header)
    for (pid, t), statuses in chases.items():
        ceiling = census.wedge_count(census.decode_profile(pid)) - 3 * t
        for number, status in enumerate(statuses):
            seconds = census.RETRY_SECONDS if number else census.SOLVE_SECONDS
            body: dict[str, object] = {
                "REQUEST_SHA256": request_digest(pid, t, seconds),
                "PROFILE_ID": pid,
                "T": t,
                "CEILING": ceiling,
                "EXCLUDED_COUNT": 0,
                "SECONDS": seconds,
                "STATUS": status,
                "STRUCTURE": None,
                "WALL_SECONDS": 1.0,
            }
            log.append(("SOLVE", pid, t, "CHASE", 0, number), body)
        if statuses[-1] == census.INFEASIBLE:
            done: dict[str, object] = {"STATUS": "NO_REALIZATION_IN_SLICE", "REFUTED_T": [t]}
        elif statuses[-1] in census.REALIZED:
            done = {"STATUS": "REALIZED", "MAX_REALIZABLE_T": t, "REFUTED_T": []}
        elif len(statuses) == 2:
            done = {"STATUS": "UNRESOLVED_AFTER_RETRY", "UNRESOLVED_T": t, "REFUTED_T": []}
        else:
            continue
        log.append(("PROFILE_DONE", pid), {**done, "R30_BOUND": 0})
    return path.read_bytes()


def synthetic_overlay(
    cells: list[tuple[str, int]], realized: frozenset[tuple[str, int]] = frozenset()
) -> overlay.Overlay:
    imports: dict[tuple[str, int], tuple[object, ...]] = {
        (pid, t): (pid, t, 0, 0, i, "OWNER_MEMBER", "line", request_digest(pid, t))
        for i, (pid, t) in enumerate(cells)
    }
    return overlay.Overlay("synthetic", {}, imports, realized or frozenset({(INCUMBENT, 270)}))


def test_verdict_adds_overlay_refutations_to_census_evidence(tmp_path: Path) -> None:
    raw = census_log(
        tmp_path / "proof.jsonl",
        {(INCUMBENT, 270): ["OPTIMAL"], (OTHER_A, 269): ["UNKNOWN", "UNKNOWN"]},
    )
    snapshot = overlay.read_census_proof(raw, MANIFEST)
    assert snapshot.chase[(OTHER_A, 269)] == ("UNKNOWN", "UNKNOWN")
    assert snapshot.requests[(OTHER_A, 269)] == request_digest(OTHER_A, 269)
    verdict = overlay.combined_verdict(
        MANIFEST, synthetic_overlay([(OTHER_A, 269), (OTHER_B, 269)]), snapshot
    )
    assert (verdict["REFUTED_CELL_COUNT"], verdict["FEASIBLE_CELL_COUNT"]) == (2, 1)
    assert verdict["OPEN_CELL_COUNT"] == 0
    assert verdict["REFUTED_BY_SOURCE"] == {
        "OVERLAY_ONLY_CENSUS_NOT_REACHED": 1,
        "OVERLAY_ONLY_CENSUS_UNRESOLVED": 1,
    }
    assert verdict["HISTORICAL_CENSUS_PARITY"] == {
        "CENSUS_DECIDED": 1,
        "R30_AGREES": 1,
        "R30_SILENT": 0,
    }
    assert verdict["SLICE1_ALL_CELLS_DECIDED"] is True
    assert verdict["SLICE2"] == "NOT_EVALUATED"


def test_census_refutation_counts_once_and_cells_without_evidence_stay_open(
    tmp_path: Path,
) -> None:
    raw = census_log(tmp_path / "proof.jsonl", {(OTHER_A, 269): ["UNKNOWN", "INFEASIBLE"]})
    snapshot = overlay.read_census_proof(raw, MANIFEST)
    verdict = overlay.combined_verdict(MANIFEST, synthetic_overlay([(OTHER_A, 269)]), snapshot)
    assert verdict["REFUTED_BY_SOURCE"] == {"BOTH": 1}
    assert verdict["FEASIBLE_CELL_COUNT"] == 0
    assert verdict["OPEN_CELLS"] == [[INCUMBENT, 270, "NOT_REACHED"], [OTHER_B, 269, "NOT_REACHED"]]
    assert verdict["SLICE1_ALL_CELLS_DECIDED"] is False


def test_census_realization_of_an_imported_cell_is_a_contradiction(tmp_path: Path) -> None:
    raw = census_log(tmp_path / "proof.jsonl", {(OTHER_A, 269): ["FEASIBLE"]})
    snapshot = overlay.read_census_proof(raw, MANIFEST)
    with pytest.raises(overlay.OverlayError, match="CONTRADICTION"):
        overlay.combined_verdict(MANIFEST, synthetic_overlay([(OTHER_A, 269)]), snapshot)


def test_census_refutation_of_an_r30_realized_cell_is_a_contradiction(tmp_path: Path) -> None:
    raw = census_log(tmp_path / "proof.jsonl", {(INCUMBENT, 270): ["INFEASIBLE"]})
    snapshot = overlay.read_census_proof(raw, MANIFEST)
    with pytest.raises(overlay.OverlayError, match="CONTRADICTION"):
        overlay.combined_verdict(MANIFEST, synthetic_overlay([]), snapshot)


def test_census_request_must_match_the_imported_cell_model(tmp_path: Path) -> None:
    raw = census_log(tmp_path / "proof.jsonl", {(OTHER_A, 269): ["INFEASIBLE"]})
    snapshot = overlay.read_census_proof(raw, MANIFEST)
    imported = synthetic_overlay([(OTHER_A, 269)])
    row = imported.imports[(OTHER_A, 269)]
    wrong = overlay.Overlay("x", {}, {(OTHER_A, 269): (*row[:7], "0" * 64)}, imported.r30_realized)
    with pytest.raises(overlay.OverlayError, match="request differs"):
        overlay.combined_verdict(MANIFEST, wrong, snapshot)


def test_snapshot_sets_aside_a_partial_tail_and_never_needs_write_access(tmp_path: Path) -> None:
    path = tmp_path / "proof.jsonl"
    raw = census_log(path, {(OTHER_A, 269): ["INFEASIBLE"]})
    path.chmod(0o444)
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    snapshot = overlay.read_census_proof(path.read_bytes() + b'{"KEY"', MANIFEST)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    assert (snapshot.partial_tail_bytes, snapshot.length) == (6, len(raw))
    assert snapshot.sha256 == census.sha256_bytes(raw)
    assert snapshot.lines == 3 and set(snapshot.done) == {OTHER_A}


def test_snapshot_rejects_a_broken_chain_or_a_foreign_header(tmp_path: Path) -> None:
    raw = census_log(tmp_path / "a.jsonl", {(OTHER_A, 269): ["INFEASIBLE"]})
    with pytest.raises(overlay.OverlayError, match="hash chain"):
        overlay.read_census_proof(raw.replace(b'"INFEASIBLE"', b'"FEASIBLE"', 1), MANIFEST)
    header, _, *rest = raw.split(b"\n")
    with pytest.raises(overlay.OverlayError, match="hash chain"):
        # Every remaining line still hashes correctly; only its link to the dropped line breaks.
        overlay.read_census_proof(b"\n".join([header, *rest]), MANIFEST)
    foreign = {**CENSUS_HEADER, "ENGINE_SHA256": "0" * 64}
    raw = census_log(tmp_path / "b.jsonl", {}, foreign)
    with pytest.raises(overlay.OverlayError, match="header"):
        overlay.read_census_proof(raw, MANIFEST)


def test_snapshot_rejects_solves_outside_slice1_or_out_of_order(tmp_path: Path) -> None:
    raw = census_log(tmp_path / "a.jsonl", {(OTHER_A, 268): ["INFEASIBLE"]})
    with pytest.raises(overlay.OverlayError, match="not a Slice-1 cell solve"):
        overlay.read_census_proof(raw, MANIFEST)
    log = census.DurableLog(tmp_path / "b.jsonl", CENSUS_HEADER)
    body = {"REQUEST_SHA256": "r", "CEILING": 13, "STATUS": "INFEASIBLE"}
    log.append(("SOLVE", OTHER_A, 269, "CHASE", 0, 1), body)
    with pytest.raises(overlay.OverlayError, match="in order"):
        overlay.read_census_proof((tmp_path / "b.jsonl").read_bytes(), MANIFEST)


def test_profile_done_must_agree_with_the_chase_solves(tmp_path: Path) -> None:
    log = census.DurableLog(tmp_path / "proof.jsonl", CENSUS_HEADER)
    body = {"REQUEST_SHA256": request_digest(OTHER_A, 269), "CEILING": 13, "STATUS": "INFEASIBLE"}
    log.append(("SOLVE", OTHER_A, 269, "CHASE", 0, 0), body)
    log.append(("PROFILE_DONE", OTHER_A), {"STATUS": "REALIZED", "MAX_REALIZABLE_T": 269})
    snapshot = overlay.read_census_proof((tmp_path / "proof.jsonl").read_bytes(), MANIFEST)
    with pytest.raises(overlay.OverlayError, match="disagrees"):
        overlay.combined_verdict(MANIFEST, synthetic_overlay([]), snapshot)


# The pinned overlay ledger -----------------------------------------------------------------


def test_census_authority_is_unchanged_on_this_branch() -> None:
    manifest_raw = (ROOT / census.MANIFEST_RELATIVE).read_bytes()
    assert census.sha256_bytes(manifest_raw) == census.MANIFEST_SHA256
    assert census.engine_sha256() == overlay.CENSUS_ENGINE_SHA256
    assert len(census.load_manifest().rows) == 992


def test_pinned_overlay_accounts_for_every_cell_once() -> None:
    loaded = overlay.load_overlay()
    data = json.loads(OVERLAY_FILE.read_bytes())
    cells = {overlay.cell_of(r) for r in census.load_manifest().rows}
    rejected = {(e[0], e[1]) for e in data["NOT_IMPORTED"]}
    assert loaded.sha256 == overlay.OVERLAY_SHA256
    assert len(loaded.imports) == data["IMPORT_COUNT"] == 990
    assert rejected == {(INCUMBENT, 270), OPEN_CELL}
    assert set(loaded.imports) | rejected == cells and not set(loaded.imports) & rejected
    assert len({row[4] for row in loaded.imports.values()}) == 990
    assert loaded.r30_realized == {(INCUMBENT, 270)}
    window = data["TRANSIENT_WINDOW"]
    assert (window["EXCLUDED_ATTEMPTS"], len(window["EXCLUDED_BATCHES"])) == (565, 16)
    assert window["ELIGIBLE_CELLS_EXCLUDED_ONLY_BY_WINDOW"] == 0
    assert data["OWNER_DISPOSITION"] == overlay.OWNER_DISPOSITION
    assert (
        data["MODEL_EQUIVALENCE"]["SHARED_PROBE"]["MODEL_PROTO_TEXT_SHA256"]
        == (census.MODEL_PROBES[0][2])
    )


def tampered(data: Any) -> overlay.Overlay:
    """Parse edited ledger data whose import digest and count were recomputed to match."""

    data["IMPORT_COUNT"] = len(data["IMPORTS"])
    data["IMPORTS_SHA256"] = census.sha256_bytes(census.canonical_json(data["IMPORTS"]).encode())
    return overlay.parse_overlay(data, "tampered")


def pinned_data() -> Any:
    return json.loads(OVERLAY_FILE.read_bytes())


def test_overlay_ledger_rejects_tampering(tmp_path: Path) -> None:
    raw = OVERLAY_FILE.read_bytes()
    edited = tmp_path / "overlay.json"
    edited.write_bytes(raw.replace(b'"OWNER_MEMBER"', b'"OWNER_MEMBER_X"', 1))
    with pytest.raises(overlay.OverlayError, match="SHA-256 differs"):
        overlay.load_overlay(edited)
    data = pinned_data()
    data["IMPORTS"].append(list(data["IMPORTS"][0]))
    with pytest.raises(overlay.OverlayError, match="duplicate overlay import"):
        tampered(data)
    data = pinned_data()
    data["IMPORTS"][0][4] = 3155
    with pytest.raises(overlay.OverlayError, match="transient window"):
        tampered(data)
    data = pinned_data()
    data["IMPORTS"].append([INCUMBENT, 270, 816, 6, 1775, "OWNER_MEMBER", "l", "r"])
    with pytest.raises(overlay.OverlayError, match="both imported and not imported"):
        tampered(data)
    data = pinned_data()
    data["IMPORTS"].pop()
    with pytest.raises(overlay.OverlayError, match="digest or count"):
        overlay.parse_overlay(data, "stale digest")


def test_the_ledger_is_never_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "overlay.json"
    overlay.write_new(path, b"first\n")
    with pytest.raises(FileExistsError):
        overlay.write_new(path, b"second\n")
    assert path.read_bytes() == b"first\n"


@needs_r30
def test_pinned_overlay_rederives_from_the_r30_result() -> None:
    overlay.verify_overlay(overlay.load_overlay(), census.load_manifest(), ROOT)


# Attempt 1780 is the first import's own source. 2301 is UNKNOWN, 1775 OPTIMAL, 3741 refutes
# another profile, and 0 refutes the same profile at an earlier, higher cap.
@needs_r30
@pytest.mark.parametrize("source", [2301, 1775, 3741, 0])
def test_rederivation_rejects_an_ineligible_source(source: int) -> None:
    data = pinned_data()
    assert data["IMPORTS"][0][4] == 1780
    data["IMPORTS"][0][4] = source
    with pytest.raises(overlay.OverlayError, match="re-derivation"):
        overlay.verify_overlay(tampered(data), census.load_manifest(), ROOT)


@needs_r30
def test_rederivation_rejects_importing_the_open_cell_from_its_unknown_retry() -> None:
    data = pinned_data()
    data["NOT_IMPORTED"] = [e for e in data["NOT_IMPORTED"] if (e[0], e[1]) != OPEN_CELL]
    data["IMPORTS"].append([*OPEN_CELL, 816, 18, 2304, "OWNER_MEMBER_RETRY", "l", "r"])
    with pytest.raises(overlay.OverlayError, match="re-derivation"):
        overlay.verify_overlay(tampered(data), census.load_manifest(), ROOT)


@needs_r30
def test_cli_verdict_reads_a_census_log_without_writing_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = census.load_manifest().rows
    path = tmp_path / "proof-log.jsonl"
    census_log(
        path,
        {(rows[0].profile_id, rows[0].cap): ["OPTIMAL"], overlay.cell_of(rows[1]): ["INFEASIBLE"]},
    )
    os.chmod(path, 0o444)
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    overlay.main(["verdict", "--census-proof-log", str(path)])
    verdict = json.loads(capsys.readouterr().out)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    assert rows[0].profile_id == INCUMBENT
    assert (
        verdict["REFUTED_CELL_COUNT"],
        verdict["FEASIBLE_CELL_COUNT"],
        verdict["OPEN_CELL_COUNT"],
    ) == (990, 1, 1)
    assert verdict["REFUTED_BY_SOURCE"] == {"BOTH": 1, "OVERLAY_ONLY_CENSUS_NOT_REACHED": 989}
    assert verdict["FEASIBLE_CELLS"] == [[INCUMBENT, 270]]
    assert verdict["OPEN_CELLS"] == [[*OPEN_CELL, "NOT_REACHED"]]
    assert verdict["HISTORICAL_CENSUS_PARITY"] == {
        "CENSUS_DECIDED": 2,
        "R30_AGREES": 2,
        "R30_SILENT": 0,
    }
