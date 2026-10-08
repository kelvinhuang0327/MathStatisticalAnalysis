"""Contract tests for the certificate-aware K20 fiber Slice-1 successor.

No real cell is solved. Successor flows use an injected fake solver and evaluator over temporary
roots, with the real frozen manifest and the pinned overlay. The overlay re-derivation and the
992-cell model comparison run only when R30 task head 6ba48113 is in the local object store.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_fiber_slice1_r30_certificate_reuse as reuse
from lottolab.research import b649_k20_fiber_slice1_r30_refutation_overlay as overlay

ROOT = Path(__file__).resolve().parents[2]
INCUMBENT = ("55555555555511111100", 270)
OPEN_CELL = ("66665555555322000000", 266)
OVERLAY_FILE = ROOT / overlay.OVERLAY_RELATIVE


def r30_available() -> bool:
    probe = ["git", "cat-file", "-e", f"{overlay.R30_TASK_HEAD}^{{commit}}"]
    return subprocess.run(probe, cwd=ROOT, capture_output=True).returncode == 0


needs_r30 = pytest.mark.skipif(
    not r30_available(), reason="R30 task head 6ba48113 is not in the local object store"
)


def no_flush(_: int) -> None:
    """Durable fsync is the engine's own contract, tested there; 992-row runs skip the flush."""


@pytest.fixture(autouse=True)
def single_thread_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in census.THREAD_ENV:
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(census, "_full_fsync", no_flush)


@pytest.fixture(scope="module")
def manifest() -> census.Manifest:
    return census.load_manifest()


@pytest.fixture(scope="module")
def certified(manifest: census.Manifest) -> reuse.Certificates:
    return reuse.certificates(manifest, overlay.load_overlay(), reuse.EQUIVALENCE_SHA256)


@pytest.fixture(scope="module")
def incumbent() -> census.Structure:
    tickets, _ = census.start_portfolio(ROOT)
    profile, structure = census.structure_from_tickets(tickets)
    assert (census.profile_id(profile), census.realization(profile, structure).triangles) == (
        INCUMBENT
    )
    return structure


class FakeSolver:
    """Realizes the incumbent once, leaves the open cell UNKNOWN and refutes everything else."""

    def __init__(self, incumbent: census.Structure) -> None:
        self.incumbent = incumbent
        self.calls: list[census.SolveRequest] = []

    def __call__(self, request: census.SolveRequest) -> census.SolveOutcome:
        self.calls.append(request)
        pid = census.profile_id(request.profile)
        if pid == INCUMBENT[0] and self.incumbent not in request.excluded:
            return census.SolveOutcome("OPTIMAL", self.incumbent, 0.0)
        if pid == OPEN_CELL[0]:
            return census.SolveOutcome("UNKNOWN", None, 0.0)
        return census.SolveOutcome("INFEASIBLE", None, 0.0)


def never_solve(request: census.SolveRequest) -> census.SolveOutcome:
    raise AssertionError(f"unexpected solve of {census.profile_id(request.profile)}")


def successor(
    manifest: census.Manifest,
    certified: reuse.Certificates,
    durable: Path,
    solve: census.Solver,
    count: int = census.START_COUNT,
) -> reuse.CertifiedCensus:
    return reuse.CertifiedCensus(manifest, certified, durable, solve, lambda _: count)


def records(directory: Path) -> list[dict[str, Any]]:
    raw = (directory / census.PROOF_LOG).read_bytes()
    return [cast(dict[str, Any], json.loads(line)) for line in raw.splitlines()]


def files(directory: Path) -> dict[str, tuple[bytes, int]]:
    return {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(directory.iterdir())}


def rechain(lines: Sequence[dict[str, Any]]) -> bytes:
    previous = census.GENESIS
    out: list[bytes] = []
    for record in lines:
        content = {"KEY": record["KEY"], "PREV_SHA256": previous, "BODY": record["BODY"]}
        previous = census.sha256_bytes(census.canonical_json(content).encode())
        out.append(census.canonical_json({**content, "LINE_SHA256": previous}).encode())
    return b"\n".join(out) + b"\n"


def tampered(edit: Callable[[Any], None]) -> overlay.Overlay:
    """Parse edited overlay data whose import digest and count were recomputed to match."""

    data = json.loads(OVERLAY_FILE.read_bytes())
    edit(data)
    data["IMPORT_COUNT"] = len(data["IMPORTS"])
    data["IMPORTS_SHA256"] = census.sha256_bytes(census.canonical_json(data["IMPORTS"]).encode())
    return overlay.parse_overlay(data, "tampered")


# The certified set ---------------------------------------------------------------------------


def test_pinned_set_is_exactly_the_990_r30_cells_and_keeps_two_cells_open(
    manifest: census.Manifest, certified: reuse.Certificates
) -> None:
    assert census.engine_sha256() == overlay.CENSUS_ENGINE_SHA256
    assert manifest.sha256 == census.MANIFEST_SHA256
    assert certified.overlay_sha256 == overlay.OVERLAY_SHA256
    cells = [overlay.cell_of(row) for row in manifest.rows]
    assert len(cells) == len(set(cells)) == 992
    assert len(certified.cells) == reuse.CERTIFIED_CELL_COUNT == 990
    assert certified.unrefuted == reuse.UNREFUTED_CELLS == (INCUMBENT, OPEN_CELL)
    assert set(certified.cells) | set(certified.unrefuted) == set(cells)
    assert not set(certified.cells) & set(certified.unrefuted)
    rows = {row.profile_id: row for row in manifest.rows}
    for (pid, t), body in certified.cells.items():
        request = census.SolveRequest(rows[pid].profile, t, (), census.SOLVE_SECONDS)
        assert t == rows[pid].cap
        assert body["NATIVE_SOLVE"] is False and body["SCOPE"] == "THIS_PROFILE_AT_THIS_T_ONLY"
        assert body["CENSUS_CHASE_REQUEST_SHA256"] == request.digest()
        assert body["CEILING"] == request.ceiling
        assert 1780 <= cast(int, body["R30_ATTEMPT_INDEX"]) <= 2772
        assert body["R30_RESULT_SHA256"] == overlay.R30_RESULT_SHA256
    assert len({body["R30_ATTEMPT_INDEX"] for body in certified.cells.values()}) == 990


def wrong_t(data: Any) -> None:
    data["IMPORTS"][0][1] -= 1


def foreign_profile(data: Any) -> None:
    data["IMPORTS"][0][0] = "66666666666600000000"


def wrong_request(data: Any) -> None:
    data["IMPORTS"][0][7] = "0" * 64


def wrong_ceiling(data: Any) -> None:
    data["IMPORTS"][0][3] += 3


def wrong_wedges(data: Any) -> None:
    data["IMPORTS"][0][2] += 1


def missing_cell(data: Any) -> None:
    data["IMPORTS"].pop()


def open_cell_imported(data: Any) -> None:
    pid, t = OPEN_CELL
    profile = census.decode_profile(pid)
    wedges = census.wedge_count(profile)
    digest = census.SolveRequest(profile, t, (), census.SOLVE_SECONDS).digest()
    data["NOT_IMPORTED"] = [e for e in data["NOT_IMPORTED"] if (e[0], e[1]) != OPEN_CELL]
    data["IMPORTS"].append([pid, t, wedges, wedges - 3 * t, 2304, "OWNER_MEMBER", "l", digest])


@pytest.mark.parametrize(
    ("edit", "match"),
    [
        (wrong_t, "not a frozen Slice-1 cell"),
        (foreign_profile, "not a frozen Slice-1 cell"),
        (wrong_request, "model or request"),
        (wrong_ceiling, "model or request"),
        (wrong_wedges, "model or request"),
        (missing_cell, "exactly the 990"),
        (open_cell_imported, "exactly the 990"),
    ],
)
def test_certified_set_rejects_any_cell_it_cannot_bind_exactly(
    manifest: census.Manifest, edit: Callable[[Any], None], match: str
) -> None:
    with pytest.raises(reuse.CertificateError, match=match):
        reuse.certificates(manifest, tampered(edit), reuse.EQUIVALENCE_SHA256)


def test_duplicate_or_corrupted_overlay_never_reaches_the_successor(tmp_path: Path) -> None:
    with pytest.raises(overlay.OverlayError, match="duplicate overlay import"):
        tampered(lambda d: d["IMPORTS"].append(list(d["IMPORTS"][0])))
    with pytest.raises(overlay.OverlayError, match="does not bind"):
        tampered(lambda d: d["R30"].__setitem__("RESULT_SHA256", "0" * 64))
    edited = tmp_path / "overlay.json"
    edited.write_bytes(OVERLAY_FILE.read_bytes().replace(b'"OWNER_MEMBER"', b'"OWNER_MEMBEX"', 1))
    with pytest.raises(overlay.OverlayError, match="SHA-256 differs"):
        overlay.load_overlay(edited)


@needs_r30
@pytest.mark.parametrize("column", [4, 6])
def test_corrupted_proof_identity_fails_rederivation_from_r30(
    manifest: census.Manifest, column: int
) -> None:
    def corrupt(data: Any) -> None:
        data["IMPORTS"][0][column] = 2304 if column == 4 else "0" * 64

    with pytest.raises(overlay.OverlayError, match="re-derivation"):
        overlay.verify_overlay(tampered(corrupt), manifest, ROOT)


# Model equivalence ---------------------------------------------------------------------------


def test_model_equivalence_needs_identical_distinct_models_for_every_cell() -> None:
    same = [["a", 270, 6, "1" * 64], ["b", 269, 9, "2" * 64]]
    digest = reuse.model_equivalence(same, [list(c) for c in same])
    assert digest == census.sha256_bytes(census.canonical_json(same).encode())
    for other in (
        [same[0], ["b", 269, 9, "3" * 64]],
        [same[0], ["b", 269, 12, "2" * 64]],
        [same[0], ["b", 268, 9, "2" * 64]],
        same[:1],
    ):
        with pytest.raises(reuse.CertificateError, match="differs from the model R30 solved"):
            reuse.model_equivalence(same, other)
    vacuous = [same[0], ["b", 269, 9, "1" * 64]]
    with pytest.raises(reuse.CertificateError, match="vacuous"):
        reuse.model_equivalence(vacuous, vacuous)


@needs_r30
def test_prepare_fails_closed_on_an_unpinned_equivalence_digest(
    manifest: census.Manifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    cells: list[list[object]] = [["a", 270, 6, "1" * 64]]

    def built(*_: object) -> list[list[object]]:
        return cells

    def other(*_: object) -> list[list[object]]:
        return [["a", 270, 6, "2" * 64]]

    monkeypatch.setattr(reuse, "census_model_digests", built)
    monkeypatch.setattr(reuse, "r30_head_model_digests", built)
    with pytest.raises(reuse.CertificateError, match="pinned digest"):
        reuse.prepare(manifest, ROOT)
    monkeypatch.setattr(reuse, "r30_head_model_digests", other)
    with pytest.raises(reuse.CertificateError, match="model R30 solved"):
        reuse.prepare(manifest, ROOT)

    def unproven() -> overlay.Overlay:
        """An overlay that parses but imports cell 0 from attempt 2304 (UNKNOWN)."""

        return tampered(lambda d: d["IMPORTS"][0].__setitem__(4, 2304))

    monkeypatch.setattr(reuse, "r30_head_model_digests", built)
    monkeypatch.setattr(overlay, "load_overlay", unproven)
    with pytest.raises(overlay.OverlayError, match="re-derivation"):
        reuse.prepare(manifest, ROOT, census.sha256_bytes(census.canonical_json(cells).encode()))


@needs_r30
def test_all_992_cell_models_match_r28_at_the_r30_head(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The real check: overlay re-derivation, then 992 model builds per side (no solve)."""

    reuse.main(["verify"])
    report = json.loads(capsys.readouterr().out)
    assert report == {
        "OVERLAY_SHA256": overlay.OVERLAY_SHA256,
        "MODEL_EQUIVALENCE_SHA256": reuse.EQUIVALENCE_SHA256,
        "CELLS": 992,
        "CERTIFIED": 990,
        "UNREFUTED": [list(INCUMBENT), list(OPEN_CELL)],
        "STRICT_GAIN_THRESHOLD": 313_263_889,
    }


# Successor execution -------------------------------------------------------------------------


def test_successor_records_990_certificates_and_solves_only_the_two_open_cells(
    tmp_path: Path,
    manifest: census.Manifest,
    certified: reuse.Certificates,
    incumbent: census.Structure,
) -> None:
    solver = FakeSolver(incumbent)
    run = successor(manifest, certified, tmp_path, solver)
    summary = run.run()
    solved = [(census.profile_id(r.profile), r.triangles, r.seconds) for r in solver.calls]
    assert solved == [
        (*INCUMBENT, census.SOLVE_SECONDS),
        (*INCUMBENT, census.SOLVE_SECONDS),
        (*OPEN_CELL, census.SOLVE_SECONDS),
        (*OPEN_CELL, census.RETRY_SECONDS),
    ]
    assert run.solver_calls == 4
    lines = records(tmp_path)
    assert lines[0]["BODY"] == {
        "TASK_ID": reuse.SUCCESSOR_ID,
        "CENSUS_TASK_ID": census.TASK_ID,
        "MANIFEST_SHA256": census.MANIFEST_SHA256,
        "ENGINE_SHA256": overlay.CENSUS_ENGINE_SHA256,
        "ADAPTER_SHA256": census.sha256_bytes(Path(reuse.__file__).read_bytes()),
        "OVERLAY_SHA256": overlay.OVERLAY_SHA256,
        "CERTIFIED_IMPORTS_SHA256": json.loads(OVERLAY_FILE.read_bytes())["IMPORTS_SHA256"],
        "CERTIFIED_CELL_COUNT": 990,
        "MODEL_EQUIVALENCE_SHA256": reuse.EQUIVALENCE_SHA256,
        "PRIOR_RUN_EVIDENCE": reuse.PRIOR_RUN_EVIDENCE,
        "LOG": "PROOF",
    }
    assert reuse.SUCCESSOR_ID != census.TASK_ID
    keys = [tuple(line["KEY"]) for line in lines]
    assert {k[1] for k in keys if k[0] == "SOLVE"} == {INCUMBENT[0], OPEN_CELL[0]}
    bodies = {tuple(line["KEY"]): line["BODY"] for line in lines}
    for cell, body in certified.cells.items():
        assert bodies[(reuse.CERTIFICATE, *cell)] == dict(body)
        assert bodies[("PROFILE_DONE", cell[0])] == {
            "STATUS": reuse.CERTIFIED_STATUS,
            "REFUTED_T": [cell[1]],
            "R30_BOUND": next(r.r30_bound for r in manifest.rows if r.profile_id == cell[0]),
        }
    assert sum(k[0] == reuse.CERTIFICATE for k in keys) == 990
    assert summary["PROFILES_DONE"] == 992 and summary["COMPLETE"] is True
    assert summary["STATUS_COUNTS"] == {
        reuse.CERTIFIED_STATUS: 990,
        "REALIZED": 1,
        "UNRESOLVED_AFTER_RETRY": 1,
    }
    assert (summary["CERTIFIED_CELLS_RECORDED"], summary["NATIVE_SOLVE_RECORDS"]) == (990, 4)
    assert summary["TASK_ID"] == reuse.SUCCESSOR_ID
    assert summary["PRIOR_RUN_EVIDENCE"] == reuse.PRIOR_RUN_EVIDENCE
    assert summary["UNREFUTED_CELLS"] == [list(INCUMBENT), list(OPEN_CELL)]
    assert (summary["WITNESSES_EVALUATED"], summary["BEST_EXACT_COUNT"]) == (1, census.START_COUNT)
    assert summary["GAINS"] == []


@pytest.mark.parametrize(("count", "gains"), [(313_263_888, 0), (313_263_889, 1)])
def test_strict_gain_threshold_is_the_census_threshold(
    tmp_path: Path,
    manifest: census.Manifest,
    certified: reuse.Certificates,
    incumbent: census.Structure,
    count: int,
    gains: int,
) -> None:
    assert manifest.threshold == census.STRICT_GAIN_THRESHOLD == 313_263_889
    run = successor(manifest, certified, tmp_path, FakeSolver(incumbent), count)
    summary = run.run(profile_limit=1)
    assert summary["STRICT_GAIN_THRESHOLD"] == 313_263_889
    assert len(cast(list[object], summary["GAINS"])) == gains
    witness = run.witnesses.get(("WITNESS", INCUMBENT[0], INCUMBENT[1], 0))
    assert witness is not None and witness["GAIN"] is bool(gains)


def test_restart_serves_every_record_and_counts_each_cell_once(
    tmp_path: Path,
    manifest: census.Manifest,
    certified: reuse.Certificates,
    incumbent: census.Structure,
) -> None:
    first = successor(manifest, certified, tmp_path, FakeSolver(incumbent)).run(profile_limit=3)
    assert first["PROFILES_DONE"] == 3 and first["CERTIFIED_CELLS_RECORDED"] == 2
    full = successor(manifest, certified, tmp_path, FakeSolver(incumbent)).run()
    complete = files(tmp_path)
    proof = complete[census.PROOF_LOG][0]
    # A crash between the last certificate and its PROFILE_DONE: the restart appends only that.
    (tmp_path / census.PROOF_LOG).write_bytes(proof[: proof.rstrip(b"\n").rfind(b"\n") + 1])
    successor(manifest, certified, tmp_path, never_solve).run()
    assert (tmp_path / census.PROOF_LOG).read_bytes() == proof
    before = files(tmp_path)
    again = successor(manifest, certified, tmp_path, never_solve)
    served = again.run()
    assert files(tmp_path) == before and again.solver_calls == 0
    assert served == {**full, "SOLVER_CALLS_THIS_PROCESS": 0}
    assert (served["PROFILES_DONE"], served["CERTIFIED_CELLS_RECORDED"]) == (992, 990)
    with pytest.raises(census.DurableLogError, match="duplicate durable key"):
        again.proof.append((reuse.CERTIFICATE, *next(iter(certified.cells))), {})


def test_tampered_or_misplaced_certificate_records_fail_closed(
    tmp_path: Path,
    manifest: census.Manifest,
    certified: reuse.Certificates,
    incumbent: census.Structure,
) -> None:
    good = tmp_path / "good"
    successor(manifest, certified, good, FakeSolver(incumbent)).run(profile_limit=2)
    lines = records(good)
    index = next(i for i, line in enumerate(lines) if line["KEY"][0] == reuse.CERTIFICATE)
    forged = [dict(line) for line in lines]
    forged[index] = {**forged[index], "BODY": {**forged[index]["BODY"], "R30_ATTEMPT_INDEX": 3155}}
    bad = tmp_path / "forged"
    bad.mkdir()
    (bad / census.PROOF_LOG).write_bytes(rechain(forged))
    (bad / census.WITNESS_LEDGER).write_bytes((good / census.WITNESS_LEDGER).read_bytes())
    with pytest.raises(census.DurableLogError, match="differs from the overlay"):
        successor(manifest, certified, bad, never_solve).run()
    misplaced = tmp_path / "misplaced"
    header = reuse.successor_header(manifest, certified)
    census.DurableLog(misplaced / census.PROOF_LOG, {**header, "LOG": "PROOF"}).append(
        (reuse.CERTIFICATE, *INCUMBENT), {"NATIVE_SOLVE": False}
    )
    with pytest.raises(census.DurableLogError, match="not certified"):
        successor(manifest, certified, misplaced, never_solve).run()


def test_run1_logs_are_never_opened_for_writing_or_consumed(
    tmp_path: Path,
    manifest: census.Manifest,
    certified: reuse.Certificates,
    incumbent: census.Structure,
) -> None:
    run1 = tmp_path / "run1"
    census.Census(manifest, run1, FakeSolver(incumbent), lambda _: census.START_COUNT).run(
        profile_limit=2
    )
    before = files(run1)
    with pytest.raises(census.DurableLogError, match="header differs"):
        successor(manifest, certified, run1, never_solve)
    named = tmp_path / Path(census.DURABLE_RELATIVE).name
    with pytest.raises(reuse.CertificateError, match="RUN1 durable root"):
        successor(manifest, certified, named, never_solve)
    assert not named.exists()
    fresh = tmp_path / "successor"
    summary = successor(manifest, certified, fresh, FakeSolver(incumbent)).run()
    assert files(run1) == before
    assert (summary["PROFILES_DONE"], summary["WITNESSES_EVALUATED"]) == (992, 1)
    with pytest.raises(census.DurableLogError, match="header differs"):
        census.Census(manifest, fresh, never_solve, lambda _: census.START_COUNT)
    assert files(run1) == before


def test_slice2_stays_disabled(
    tmp_path: Path, manifest: census.Manifest, certified: reuse.Certificates
) -> None:
    with pytest.raises(census.Slice2NotAuthorized):
        successor(manifest, certified, tmp_path, never_solve).run(2)
