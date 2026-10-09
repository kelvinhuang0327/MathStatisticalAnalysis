"""Contract tests for the certificate-aware K20 fiber Slice-1 successor.

No real cell is solved. Successor flows use an injected fake solver and evaluator over temporary
roots, with the real frozen manifest and the pinned overlay. The overlay re-derivation and the
992-cell model comparison is a separate heavy test, excluded from focused verification.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.research import b649_fiber_execution_safety as safety
from lottolab.research import b649_fiber_t266_closed_form_certificate as theorem
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
def single_thread_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in census.THREAD_ENV:
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(census, "_full_fsync", no_flush)
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setenv(safety.AUTHORITY_HEAD_ENV, head)
    monkeypatch.setenv(safety.AUTHORITY_TREE_ENV, tree)
    monkeypatch.setattr(safety, "_process_table", lambda: ())
    monkeypatch.setattr(
        safety, "DEFAULT_HEAVY_LOCK_PATH", tmp_path / "machine-lock" / "b649-heavy.lock"
    )
    # Exercise the real authority/lock chain with fake solves on this uncommitted test tree.
    # Production still requires clean tracked source; only this test seam reports it clean.
    git_output = safety._git_output  # pyright: ignore[reportPrivateUsage]

    def clean_test_status(root: Path, *args: str) -> str:
        if args and args[0] == "status":
            return ""
        return git_output(root, *args)

    monkeypatch.setattr(safety, "_git_output", clean_test_status)
    # Validate source authority once per test, then reuse it for the fake-solver
    # flow. Repeated Git subprocesses are not part of certificate acceptance.
    identity = reuse.source_identity_preflight(ROOT, process_lines=())

    def verified_test_identity(*_: object, **__: object) -> safety.SourceIdentity:
        return identity

    monkeypatch.setattr(safety, "preflight_source_identity", verified_test_identity)


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
    return {
        p.name: (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(directory.iterdir())
        if p.is_file()
    }


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


def test_successor_records_990_r30_and_one_theorem_and_solves_only_incumbent(
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
    ]
    assert run.solver_calls == 2
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
        "THEOREM_MODULE_SHA256": census.sha256_bytes(Path(str(theorem.__file__)).read_bytes()),
        "THEOREM_CERTIFIED_CELL_COUNT": 1,
        "THEOREM_CERTIFICATES_SHA256": census.sha256_bytes(
            census.canonical_json([[*cell, body] for cell, body in run.theorems.items()]).encode()
        ),
        "PRIOR_RUN_EVIDENCE": reuse.PRIOR_RUN_EVIDENCE,
        "LOG": "PROOF",
    }
    assert reuse.SUCCESSOR_ID != census.TASK_ID
    keys = [tuple(line["KEY"]) for line in lines]
    assert {k[1] for k in keys if k[0] == "SOLVE"} == {INCUMBENT[0]}
    bodies = {tuple(line["KEY"]): line["BODY"] for line in lines}
    for cell, body in certified.cells.items():
        assert bodies[(reuse.CERTIFICATE, *cell)] == dict(body)
        assert bodies[("PROFILE_DONE", cell[0])] == {
            "STATUS": reuse.CERTIFIED_STATUS,
            "REFUTED_T": [cell[1]],
            "R30_BOUND": next(r.r30_bound for r in manifest.rows if r.profile_id == cell[0]),
        }
    assert sum(k[0] == reuse.CERTIFICATE for k in keys) == 990
    assert sum(k[0] == theorem.CERTIFICATE for k in keys) == 1
    assert bodies[(theorem.CERTIFICATE, *OPEN_CELL)] == run.theorems[OPEN_CELL]
    assert (reuse.CERTIFICATE, *OPEN_CELL) not in bodies
    assert summary["PROFILES_DONE"] == 992 and summary["COMPLETE"] is True
    assert summary["STATUS_COUNTS"] == {
        reuse.CERTIFIED_STATUS: 990,
        "REALIZED": 1,
        theorem.CERTIFIED_STATUS: 1,
    }
    assert (summary["CERTIFIED_CELLS_RECORDED"], summary["NATIVE_SOLVE_RECORDS"]) == (990, 2)
    assert summary["THEOREM_CERTIFIED_CELLS_RECORDED"] == 1
    assert summary["TASK_ID"] == reuse.SUCCESSOR_ID
    assert summary["PRIOR_RUN_EVIDENCE"] == reuse.PRIOR_RUN_EVIDENCE
    assert summary["UNREFUTED_CELLS"] == [list(INCUMBENT)]
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
        successor(manifest, certified, run1, never_solve).run()
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


def test_guarded_legacy_cli_uses_global_claim_without_successor_imports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    durable = tmp_path / "authorized-legacy-run"

    def unexpected_prepare(*_: object, **__: object) -> reuse.Certificates:
        raise AssertionError("legacy-run must not prepare successor certificates")

    monkeypatch.setattr(reuse, "prepare", unexpected_prepare)
    monkeypatch.setattr(census, "official_evaluator", lambda: lambda _: census.START_COUNT)
    monkeypatch.setattr(census, "preflight", lambda *_: {"STATUS": "PASS"})
    monkeypatch.setattr(census, "cp_sat_solve", never_solve)
    append = reuse._ClaimCheckedDurableLog.append
    write_atomic = census.write_atomic

    def append_while_task_locked(
        log: reuse._ClaimCheckedDurableLog, key: census.Key, body: dict[str, object]
    ) -> dict[str, object]:
        with (
            pytest.raises(census.CensusError, match="another census writer"),
            census.durable_lock(log.path.parent),
        ):
            pytest.fail("durable log append must hold the task-local lock")
        return append(log, key, body)

    def write_summary_while_task_locked(path: Path, data: bytes) -> None:
        with (
            pytest.raises(census.CensusError, match="another census writer"),
            census.durable_lock(path.parent),
        ):
            pytest.fail("summary write must hold the task-local lock")
        write_atomic(path, data)

    monkeypatch.setattr(reuse._ClaimCheckedDurableLog, "append", append_while_task_locked)
    monkeypatch.setattr(census, "write_atomic", write_summary_while_task_locked)

    reuse.main(["legacy-run", "--durable", str(durable), "--profile-limit", "0"])

    summary = json.loads(capsys.readouterr().out)
    assert summary["TASK_ID"] == census.TASK_ID
    assert summary["PROFILES_DONE"] == 0
    assert (durable / census.PROOF_LOG).is_file()
    assert (durable / census.WITNESS_LEDGER).is_file()
    assert (durable / census.SUMMARY).is_file()


def test_legacy_run_help_marks_fable_route_and_raw_cli_boundary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as result:
        reuse.main(["--help"])

    assert result.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "legacy-run" in help_text
    assert "authorized Fable --run/--recover-run argv" in help_text
    assert "raw legacy CLI remains unenforced" in help_text


def test_guarded_legacy_cli_rejects_slice2_before_durable_writes(tmp_path: Path) -> None:
    durable = tmp_path / "unauthorized-slice"

    with pytest.raises(census.Slice2NotAuthorized, match="only Slice 1 is authorized"):
        reuse.main(["legacy-run", "--durable", str(durable), "--slice", "2"])

    assert not durable.exists()


def test_guarded_legacy_log_requires_machine_claim_before_any_write(
    tmp_path: Path, manifest: census.Manifest
) -> None:
    durable = tmp_path / "must-stay-absent"

    with pytest.raises(safety.SafetyGateError, match="active machine-level claim"):
        reuse.GuardedLegacyCensus(
            ROOT, manifest, durable, never_solve, lambda _: census.START_COUNT
        )

    assert not durable.exists()


def test_guarded_legacy_log_refuses_detached_machine_lock_before_append(
    tmp_path: Path, manifest: census.Manifest
) -> None:
    durable = tmp_path / "guarded-run"
    lock_path = safety.DEFAULT_HEAVY_LOCK_PATH
    lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path.parent.chmod(0o700)
    with (
        pytest.raises(safety.LockIntegrityError, match="no longer names the inode"),
        reuse._protected_execution(ROOT, durable_root=durable),
    ):
        legacy = reuse.GuardedLegacyCensus(
            ROOT, manifest, durable, never_solve, lambda _: census.START_COUNT
        )
        proof_before = (durable / census.PROOF_LOG).read_bytes()
        lock_path.unlink()
        lock_path.write_text("replacement", encoding="utf-8")
        legacy.proof.append(("FAULT_INJECTION",), {})
        pytest.fail("append must reject a detached machine lock inode")

    assert (durable / census.PROOF_LOG).read_bytes() == proof_before


def test_slice2_stays_disabled(
    tmp_path: Path, manifest: census.Manifest, certified: reuse.Certificates
) -> None:
    with pytest.raises(census.Slice2NotAuthorized):
        successor(manifest, certified, tmp_path, never_solve).run(2)


# Exact-profile closed-form theorem -----------------------------------------------------------


def test_theorem_arithmetic_and_all_local_parameter_bounds() -> None:
    arithmetic = theorem.verify_arithmetic()
    assert arithmetic == {
        "ACTIVE_VERTICES": 14,
        "INACTIVE_VERTICES": 6,
        "DEGREE_6_VERTICES": 4,
        "MIN_ACTIVE_TRIPLE_DEGREE": 2,
        "ACTIVE_DOUBLE_INCIDENCE": 18,
        "M_MIN": 6,
        "M_MAX": 18,
        "M_PARITY": "EVEN",
        "CATEGORY_A": "9+d+m/2-x",
        "CATEGORY_B": "m-x",
        "X_BOUND": "0<=x<=6-d; d>=2",
        "PER_VERTEX_BOUND": "3+3m/2",
        "PER_VERTEX_MIN": 12,
        "OPEN_WEDGES_MIN": 48,
        "W": 831,
        "T_MAX": 261,
    }
    profile = census.decode_profile(OPEN_CELL[0])
    assert profile.count(6) == 4 and sum(profile) == 22 * 3
    assert 6 * 6 - 2 * 15 == 6
    assert census.wedge_count(profile) == 831
    # Exhaust all arithmetic parameters admitted by the proof, including a superset
    # of realizable combinations. These are inequalities, not sampled support graphs.
    for m in range(6, 19, 2):
        for d in {degree for degree in profile if degree}:
            for x in range(6 - d + 1):
                active_non_edges = 91 - (22 * 3 + (18 - m) // 2)
                missing_u = 13 - (6 + d - x)
                category_a = active_non_edges - (1 + missing_u - 1)
                category_b = m - x
                assert category_a == 9 + d + m // 2 - x
                assert category_a + category_b >= 3 + 3 * m // 2
                assert 4 * (category_a + category_b) >= 48
    assert (831 - 48) // 3 == 261 and 831 - 3 * 266 == 33 < 48
    assert "cannot have degree 6" in theorem.PROOF
    assert "pairwise disjoint, even when u itself has degree 6" in theorem.PROOF
    assert "they may overcount but cannot undercount" in theorem.PROOF


def test_exact_theorem_certificate_is_self_contained_and_pinned(
    manifest: census.Manifest, certified: reuse.Certificates
) -> None:
    row = next(r for r in manifest.rows if overlay.cell_of(r) == OPEN_CELL)
    body = theorem.certificate(manifest, row, certified.equivalence_sha256, ROOT)
    assert body is not None
    assert (body["PROFILE_ID"], body["T"], body["CEILING"]) == (*OPEN_CELL, 33)
    assert body["PROOF_IDENTITY"] == theorem.PROOF_IDENTITY
    assert body["PROOF_VERSION"] == 1
    assert body["PROOF"] == theorem.PROOF
    assert body["PROOF_SHA256"] == census.sha256_bytes(theorem.PROOF.encode())
    assert body["ARITHMETIC"] == theorem.verify_arithmetic()
    assert body["NATIVE_SOLVE"] is False
    assert body["SCOPE"] == "THIS_PROFILE_AT_THIS_T_ONLY"
    assert body["R28_HEAD"] == census.R28_COMMIT
    assert body["R28_TREE"] == census.R28_TREE
    assert body["R28_MODULE_SHA256"] == census.R28_MODULE_SHA256
    assert body["ENGINE_SHA256"] == overlay.CENSUS_ENGINE_SHA256
    assert body["MANIFEST_SHA256"] == manifest.sha256
    assert body["MODEL_EQUIVALENCE_SHA256"] == reuse.EQUIVALENCE_SHA256
    assert theorem.CERTIFICATE not in (reuse.CERTIFICATE, census.INFEASIBLE)
    assert not any(k.startswith("R30_") for k in body)
    assert reuse.execution_source_spec(ROOT).module_files["theorem"][0] == Path(
        str(theorem.__file__)
    )


@pytest.mark.parametrize("t", [260, 261, 262, 265, 267, 270])
def test_unsupported_t_has_no_theorem_and_uses_original_solver_path(
    manifest: census.Manifest, certified: reuse.Certificates, tmp_path: Path, t: int
) -> None:
    target = next(r for r in manifest.rows if overlay.cell_of(r) == OPEN_CELL)
    row = replace(target, cap=t, band=((t, target.r30_bound),))
    assert theorem.certificate(manifest, row, certified.equivalence_sha256, ROOT) is None
    requests: list[census.SolveRequest] = []

    def unknown(request: census.SolveRequest) -> census.SolveOutcome:
        requests.append(request)
        return census.SolveOutcome("UNKNOWN", None, 0.0)

    run = successor(manifest, certified, tmp_path, unknown)
    result = run.run_profile(row)
    assert [r.triangles for r in requests] == [t, t]
    assert result["STATUS"] == "UNRESOLVED_AFTER_RETRY"
    assert run.proof.get((theorem.CERTIFICATE, OPEN_CELL[0], t)) is None


@pytest.mark.parametrize("t", [261, 265, 267])
@pytest.mark.parametrize("restart", [False, True])
def test_unsupported_t_cannot_reuse_theorem_completion_in_same_journal(
    manifest: census.Manifest,
    certified: reuse.Certificates,
    tmp_path: Path,
    t: int,
    restart: bool,
) -> None:
    target = next(r for r in manifest.rows if overlay.cell_of(r) == OPEN_CELL)
    run = successor(manifest, certified, tmp_path, never_solve)
    run.run_profile(target)
    before = files(tmp_path)
    if restart:
        run = successor(manifest, certified, tmp_path, never_solve)
    unsupported = replace(target, cap=t, band=((t, target.r30_bound),))
    with pytest.raises(census.DurableLogError, match="unsupported cell cannot reuse"):
        run.run_profile(unsupported)
    assert run.solver_calls == 0 and files(tmp_path) == before
    assert run.proof.get((theorem.CERTIFICATE, target.profile_id, t)) is None


def test_wrong_profile_is_not_certified_and_inconsistent_target_row_fails_closed(
    manifest: census.Manifest, certified: reuse.Certificates, tmp_path: Path
) -> None:
    target = next(r for r in manifest.rows if overlay.cell_of(r) == OPEN_CELL)
    incumbent = manifest.rows[0]
    assert theorem.certificate(manifest, incumbent, certified.equivalence_sha256, ROOT) is None
    other = replace(incumbent, cap=266)
    assert theorem.certificate(manifest, other, certified.equivalence_sha256, ROOT) is None
    with pytest.raises(theorem.TheoremError, match="cell or manifest"):
        successor(manifest, certified, tmp_path, never_solve).run_profile(
            replace(target, profile=incumbent.profile)
        )
    with pytest.raises(overlay.OverlayError, match="one profile at one T"):
        successor(manifest, certified, tmp_path, never_solve).run_profile(
            replace(target, band=((266, target.r30_bound), (265, target.r30_bound - 1)))
        )


@pytest.mark.parametrize("constant", ["R28_COMMIT", "R28_TREE", "R28_MODULE_SHA256"])
def test_altered_model_identity_fails_closed_before_any_durable_write(
    manifest: census.Manifest,
    certified: reuse.Certificates,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    constant: str,
) -> None:
    monkeypatch.setattr(census, constant, "altered")
    with pytest.raises(theorem.TheoremError, match="authority differs"):
        successor(manifest, certified, tmp_path / "uncreated", never_solve)
    assert not (tmp_path / "uncreated").exists()


def test_altered_source_manifest_or_equivalence_cannot_authorize_theorem(
    manifest: census.Manifest, certified: reuse.Certificates, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = next(r for r in manifest.rows if overlay.cell_of(r) == OPEN_CELL)
    with pytest.raises(theorem.TheoremError, match="authority differs"):
        theorem.certificate(manifest, row, "0" * 64, ROOT)
    with pytest.raises(theorem.TheoremError, match="authority differs"):
        theorem.certificate(
            replace(manifest, sha256="0" * 64), row, certified.equivalence_sha256, ROOT
        )
    data = json.loads(census.canonical_json(manifest.data))
    data["AUTHORITIES"]["MODEL_IDENTITY"]["ORTOOLS_VERSION"] = "altered"
    with pytest.raises(theorem.TheoremError, match="cell or manifest"):
        theorem.certificate(replace(manifest, data=data), row, certified.equivalence_sha256, ROOT)
    with monkeypatch.context() as changed:
        changed.setattr(census, "engine_sha256", lambda: "0" * 64)
        with pytest.raises(theorem.TheoremError, match="authority differs"):
            theorem.certificate(manifest, row, certified.equivalence_sha256, ROOT)
    with monkeypatch.context() as changed:

        def changed_r28(*_: object) -> bytes:
            return b"changed R28"

        changed.setattr(census, "git_show", changed_r28)
        with pytest.raises(theorem.TheoremError, match="R28 source bytes"):
            theorem.certificate(manifest, row, certified.equivalence_sha256, ROOT)


def test_theorem_record_and_interrupted_completion_replay_deterministically(
    manifest: census.Manifest, certified: reuse.Certificates, tmp_path: Path
) -> None:
    row = next(r for r in manifest.rows if overlay.cell_of(r) == OPEN_CELL)
    first = successor(manifest, certified, tmp_path, never_solve)
    done = first.run_profile(row)
    assert done["STATUS"] == theorem.CERTIFIED_STATUS
    assert first.solver_calls == 0
    before = files(tmp_path)
    replay = successor(manifest, certified, tmp_path, never_solve)
    assert replay.run_profile(row) == done and files(tmp_path) == before
    proof = before[census.PROOF_LOG][0]
    (tmp_path / census.PROOF_LOG).write_bytes(proof[: proof.rstrip(b"\n").rfind(b"\n") + 1])
    resumed = successor(manifest, certified, tmp_path, never_solve)
    assert resumed.run_profile(row) == done
    assert (tmp_path / census.PROOF_LOG).read_bytes() == proof
    assert len([k for k in resumed.proof.records if k[0] == theorem.CERTIFICATE]) == 1
    assert all(k[0] not in ("SOLVE", reuse.CERTIFICATE) for k in resumed.proof.records)


@pytest.mark.parametrize(
    ("location", "field", "value", "match"),
    [
        ("certificate", "PROOF_VERSION", 2, "differs from its proof"),
        ("certificate", "PROOF_VERSION", True, "differs from its proof"),
        ("certificate", "PROOF", "forged", "differs from its proof"),
        ("certificate", "T", 265, "differs from its proof"),
        ("certificate", "R28_MODULE_SHA256", "0" * 64, "differs from its proof"),
        ("certificate", "MANIFEST_SHA256", "0" * 64, "differs from its proof"),
        ("certificate", "NATIVE_SOLVE", True, "differs from its proof"),
        ("key", "PROFILE_ID", INCUMBENT[0], "differs from its proof"),
        ("key", "T", 265, "differs from its proof"),
        ("done", "REFUTED_T", [265, 266], "completion conflicts"),
        ("done", "STATUS", reuse.CERTIFIED_STATUS, "completion conflicts"),
    ],
)
def test_conflicting_theorem_records_fail_even_with_recomputed_hash_chain(
    manifest: census.Manifest,
    certified: reuse.Certificates,
    tmp_path: Path,
    location: str,
    field: str,
    value: object,
    match: str,
) -> None:
    row = next(r for r in manifest.rows if overlay.cell_of(r) == OPEN_CELL)
    successor(manifest, certified, tmp_path, never_solve).run_profile(row)
    lines = records(tmp_path)
    if location == "key":
        lines[1]["KEY"][1 if field == "PROFILE_ID" else 2] = value
    else:
        lines[1 if location == "certificate" else 2]["BODY"][field] = value
    (tmp_path / census.PROOF_LOG).write_bytes(rechain(lines))
    with pytest.raises(census.DurableLogError, match=match):
        successor(manifest, certified, tmp_path, never_solve).run(profile_limit=0)


@pytest.mark.parametrize(
    "conflict", ["SOLVE", reuse.CERTIFICATE, "WITNESS", "MISSING", "DUPLICATE"]
)
def test_theorem_rejects_native_r30_witness_missing_and_duplicate_records(
    manifest: census.Manifest, certified: reuse.Certificates, tmp_path: Path, conflict: str
) -> None:
    row = next(r for r in manifest.rows if overlay.cell_of(r) == OPEN_CELL)
    run = successor(manifest, certified, tmp_path, never_solve)
    run.run_profile(row)
    lines = records(tmp_path)
    if conflict == "MISSING":
        lines.pop(1)
    elif conflict == "DUPLICATE":
        lines.append(dict(lines[1]))
    elif conflict == "WITNESS":
        run.witnesses.append((conflict, *OPEN_CELL, 0), {})
    else:
        lines.append({"KEY": [conflict, *OPEN_CELL], "BODY": {"STATUS": "INFEASIBLE"}})
    (tmp_path / census.PROOF_LOG).write_bytes(rechain(lines))
    with pytest.raises(census.DurableLogError, match=r"conflict|duplicate"):
        successor(manifest, certified, tmp_path, never_solve).run(profile_limit=0)
