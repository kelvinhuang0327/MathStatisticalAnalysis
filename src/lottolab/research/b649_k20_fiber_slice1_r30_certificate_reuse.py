"""Certificate-aware successor execution of the K20 fiber Slice-1 census.

The frozen Slice-1 census (manifest 4b1df050, engine 479f3163) has 992 cells, one degree profile
at one T each. Refutations require infeasibility of R28's exact single-profile support model
with at most W - 3T open wedges. R30 Segment 2 proved that for 990 cells, and the
committed overlay (6c442007) imports those proofs and nothing else.

This adapter runs the unchanged census engine over its own durable root. For each of the 990
imported cells it records the R30 certificate, with the overlay's provenance, instead of solving.
It never solves those cells. An independent closed-form theorem certifies only
66665555555322000000 at T=266, with a distinct certificate type and pinned proof authority.
The incumbent cell, witness rule, official evaluator and strict-gain threshold follow the census.

Before a run, the overlay is re-derived from the pinned R30 result. Every cell's census model is
then compared with the model R30's solver built, using R28 code unpacked from the R30 task head.
The two proto texts must be identical for all 992 cells, and the per-cell list must hash to the
pinned EQUIVALENCE_SHA256.

The successor's logs carry their own header, binding the successor id, the adapter, the overlay,
the certified set and the model-equivalence digest. Neither the census engine nor this adapter
can load the other's logs. The census RUN1 root is refused by name. Nothing is migrated from
RUN1: its logs stay as they are, and the successor counts only its own records. Lower T and
Slice 2 are never claimed. Slice 2 stays disabled.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_fiber_execution_safety as safety
from lottolab.research import b649_fiber_t266_closed_form_certificate as theorem
from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_fiber_slice1_r30_refutation_overlay as overlay

TASK_ID = "B649_FIBER_R30_CERTIFICATE_REUSE_PREP_R1"
SUCCESSOR_ID = f"{census.TASK_ID}_R30_CERTIFIED_SUCCESSOR"
DURABLE_RELATIVE = ".task-data/b649-k20-fiber-slice1-r30-certified-successor-r1"
CERTIFIED_CELL_COUNT = 990
UNREFUTED_CELLS: tuple[overlay.Cell, ...] = (
    ("55555555555511111100", 270),
    ("66665555555322000000", 266),
)
CERTIFICATE = "R30_CERTIFICATE"
CERTIFIED_STATUS = "NO_REALIZATION_IN_SLICE_BY_R30_CERTIFICATE"
PRIOR_RUN_EVIDENCE = "CENSUS_RUN1_NOT_CONSUMED"
# sha256 of the canonical [[profile, T, ceiling, proto-text sha256], ...] list over all 992 cells
# in manifest order; the census builder and R28 at the R30 task head must both give it.
EQUIVALENCE_SHA256 = "7bf4bed1d679f302cbaff33c86e4e71d066ac3571d64f2d773a18d764ba4988c"
R30_SOURCE_TAG = "b649-r30-source-6ba4811304ec6528738a0c0b38969901b264d241"


def execution_source_spec(root: Path | None = None) -> safety.SourceSpec:
    """The published source pins and exact import paths that an Owner must authorize."""

    repository_root = (root or census.repo_root()).resolve()
    return safety.SourceSpec(
        repository_root=repository_root,
        module_files={
            "successor": (
                Path(__file__),
                "src/lottolab/research/b649_k20_fiber_slice1_r30_certificate_reuse.py",
            ),
            "engine": (
                Path(str(census.__file__)),
                "src/lottolab/research/b649_k20_fiber_near_top_s3_census.py",
            ),
            "overlay": (
                Path(str(overlay.__file__)),
                "src/lottolab/research/b649_k20_fiber_slice1_r30_refutation_overlay.py",
            ),
            "theorem": (
                Path(str(theorem.__file__)),
                "src/lottolab/research/b649_fiber_t266_closed_form_certificate.py",
            ),
        },
        engine_path=Path(str(census.__file__)),
        manifest_path=repository_root / census.MANIFEST_RELATIVE,
        overlay_path=repository_root / overlay.OVERLAY_RELATIVE,
        engine_sha256=overlay.CENSUS_ENGINE_SHA256,
        manifest_sha256=census.MANIFEST_SHA256,
        overlay_sha256=overlay.OVERLAY_SHA256,
        r30_source_tag=R30_SOURCE_TAG,
        r30_task_head=overlay.R30_TASK_HEAD,
        r30_result_relative=census.R30_RESULT_RELATIVE,
        r30_result_sha256=overlay.R30_RESULT_SHA256,
        census_durable_relative=census.DURABLE_RELATIVE,
    )


def source_identity_preflight(
    root: Path | None = None,
    *,
    durable_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
    process_lines: Sequence[str] | None = None,
) -> safety.SourceIdentity:
    """Pure preflight: verify identity and predecessor state without taking a lock or solving."""

    return safety.preflight_source_identity(
        execution_source_spec(root),
        durable_root=durable_root,
        environ=environ,
        process_lines=process_lines,
    )


def _protected_execution(
    root: Path,
    *,
    durable_root: Path | None = None,
):
    return safety.protected_heavy_execution(
        execution_source_spec(root),
        durable_root=durable_root,
    )


class CertificateError(census.CensusError):
    """Fail-closed certificate import error: nothing may be skipped."""


@dataclass(frozen=True, slots=True)
class Certificates:
    """The exact certified cells, each with the body its durable record must carry."""

    overlay_sha256: str
    imports_sha256: str
    equivalence_sha256: str
    cells: Mapping[overlay.Cell, Mapping[str, object]]
    unrefuted: tuple[overlay.Cell, ...]


def certificates(
    manifest: census.Manifest, loaded: overlay.Overlay, equivalence_sha256: str
) -> Certificates:
    """Bind every overlay import to its frozen census cell and chase request, or fail closed."""

    rows = {row.profile_id: row for row in manifest.rows}
    cells: dict[overlay.Cell, Mapping[str, object]] = {}
    for cell, imported in loaded.imports.items():
        row = rows.get(cell[0])
        if row is None or overlay.cell_of(row) != cell:
            raise CertificateError(f"{cell} is not a frozen Slice-1 cell")
        request = census.SolveRequest(row.profile, row.cap, (), census.SOLVE_SECONDS)
        if (
            imported[2] != census.wedge_count(row.profile)
            or imported[3] != request.ceiling
            or imported[7] != request.digest()
        ):
            raise CertificateError(f"{cell}: imported model or request differs from the chase")
        cells[cell] = {
            "SOURCE": "R30_SEGMENT2_ROUTE_A_CP_SAT_INFEASIBLE",
            "NATIVE_SOLVE": False,
            "SCOPE": "THIS_PROFILE_AT_THIS_T_ONLY",
            "PROFILE_ID": cell[0],
            "T": cell[1],
            "CEILING": request.ceiling,
            "CENSUS_CHASE_REQUEST_SHA256": request.digest(),
            "R30_TASK_HEAD": overlay.R30_TASK_HEAD,
            "R30_RESULT_SHA256": overlay.R30_RESULT_SHA256,
            "R30_PROOF_LOG_SHA256": overlay.R30_PROOF_LOG_SHA256,
            "R30_ATTEMPT_INDEX": imported[4],
            "R30_STAGE": imported[5],
            "R30_PROOF_LOG_LINE_SHA256": imported[6],
            "OVERLAY_SHA256": loaded.sha256,
        }
    unrefuted = tuple(
        overlay.cell_of(row) for row in manifest.rows if overlay.cell_of(row) not in cells
    )
    rejected = {(e[0], e[1]) for e in cast(list[list[object]], loaded.data["NOT_IMPORTED"])}
    if (
        len(cells) != CERTIFIED_CELL_COUNT
        or unrefuted != UNREFUTED_CELLS
        or set(unrefuted) != rejected
    ):
        raise CertificateError("certified cells are not exactly the 990 R30 refutations")
    return Certificates(
        loaded.sha256,
        str(loaded.data["IMPORTS_SHA256"]),
        equivalence_sha256,
        cells,
        unrefuted,
    )


# Per-cell model equivalence ------------------------------------------------------------------

R30_HEAD_MODEL_SCRIPT = r"""
import hashlib, json, sys
from pathlib import Path
tree = Path(sys.argv[1]).resolve()
import lottolab.research.b649_k20_min_s2_current_cursor_class_owner_chase_r28 as r28
for name, module in sorted(sys.modules.items()):
    if name.split(".")[0] != "lottolab":
        continue
    for path in (getattr(module, "__file__", None), *getattr(module, "__path__", ())):
        if path is not None and not Path(path).resolve().is_relative_to(tree):
            raise SystemExit(f"{name} resolved outside the R30 task-head tree")
if any(name.endswith(("_r29", "_r30")) for name in sys.modules):
    raise SystemExit("an R30 module was loaded")
cells = []
for pid, t in json.loads(sys.stdin.read()):
    profile = r28.decode_profile(pid)
    # R30's solve_group refutes cap + 1 = T with ceiling W - 3 * (cap + 1).
    ceiling = r28.overlap_wedge_count(profile) - 3 * ((t - 1) + 1)
    model = r28.support_union_model((profile,), ceiling)[0]
    cells.append([pid, t, ceiling, hashlib.sha256(str(model.Proto()).encode()).hexdigest()])
print(json.dumps({
    "R28_MODULE_SHA256": hashlib.sha256(Path(r28.__file__).read_bytes()).hexdigest(),
    "CELLS": cells,
}))
"""


def manifest_cells(manifest: census.Manifest) -> list[overlay.Cell]:
    return [overlay.cell_of(row) for row in manifest.rows]


def census_model_digests(manifest: census.Manifest) -> list[list[object]]:
    """Each cell's chase model as the census builds it, by proto-text SHA-256."""

    with _protected_execution(census.repo_root()):
        digests: list[list[object]] = []
        for row in manifest.rows:
            ceiling = census.wedge_count(row.profile) - 3 * row.cap
            model: Any = census.support_model((row.profile,), ceiling)[0]
            proto = hashlib.sha256(str(model.Proto()).encode()).hexdigest()
            digests.append([row.profile_id, row.cap, ceiling, proto])
        return digests


def r30_head_model_digests(root: Path, cells: Sequence[overlay.Cell]) -> list[list[object]]:
    """Each cell's model as R30's solver built it: R28 unpacked from the R30 task head, in a child.

    The child's only ``lottolab`` is that Git tree, and no R30 module may load in it.
    """

    with _protected_execution(root):
        return _r30_head_model_digests_under_gate(root, cells)


def _r30_head_model_digests_under_gate(
    root: Path, cells: Sequence[overlay.Cell]
) -> list[list[object]]:
    archive = subprocess.run(
        ["git", "archive", "--format=tar", overlay.R30_TASK_HEAD, *census.R28_SOURCE_PATHS],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout
    with tempfile.TemporaryDirectory(prefix="b649-r30-head-") as directory:
        tree = Path(directory).resolve()
        with tarfile.open(fileobj=io.BytesIO(archive)) as unpacked:
            unpacked.extractall(tree, filter="data")
        env = {
            **os.environ,
            **dict.fromkeys(census.THREAD_ENV, "1"),
            "PYTHONPATH": str(tree / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        done = subprocess.run(
            [sys.executable, "-c", R30_HEAD_MODEL_SCRIPT, str(tree)],
            input=json.dumps([list(cell) for cell in cells]),
            cwd=tree,
            env=env,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    if done.returncode != 0:
        raise CertificateError(f"R30-head model build failed: {done.stderr.strip()[-400:]}")
    data = cast(dict[str, Any], json.loads(done.stdout))
    if data.get("R28_MODULE_SHA256") != census.R28_MODULE_SHA256:
        raise CertificateError("R28 at the R30 task head is not the census-pinned R28")
    return cast(list[list[object]], data["CELLS"])


def model_equivalence(
    census_side: Sequence[Sequence[object]], r30_side: Sequence[Sequence[object]]
) -> str:
    """The digest of the per-cell list when both builders give identical models, else fail."""

    if [list(c) for c in census_side] != [list(c) for c in r30_side]:
        raise CertificateError("a cell's census model differs from the model R30 solved")
    if len({c[3] for c in census_side}) != len(census_side):
        raise CertificateError("two cells share one model; the comparison would be vacuous")
    return census.sha256_bytes(census.canonical_json([list(c) for c in census_side]).encode())


def prepare(
    manifest: census.Manifest, root: Path, expected_equivalence: str = EQUIVALENCE_SHA256
) -> Certificates:
    """Re-derive the pinned overlay and re-check all 992 models, then bind the certified set."""

    with _protected_execution(root):
        loaded = overlay.load_overlay()
        overlay.verify_overlay(loaded, manifest, root)
        r30_side = r30_head_model_digests(root, manifest_cells(manifest))
        digest = model_equivalence(census_model_digests(manifest), r30_side)
        if digest != expected_equivalence:
            raise CertificateError("per-cell model equivalence differs from its pinned digest")
        return certificates(manifest, loaded, digest)


# Successor census ----------------------------------------------------------------------------


def refuse_run1_root(durable: Path) -> None:
    if durable.resolve().name == Path(census.DURABLE_RELATIVE).name:
        raise CertificateError("the successor never opens the census RUN1 durable root")
    # Reject an existing census journal before even creating a successor lock.
    # The caller may have renamed or symlinked its directory.
    proof = durable / census.PROOF_LOG
    if proof.exists():
        with proof.open("rb") as handle:
            first = handle.readline()
        try:
            record: object = json.loads(first)
        except ValueError as error:
            raise census.DurableLogError("existing proof header is unreadable") from error
        if isinstance(record, dict):
            body = cast(dict[str, object], record).get("BODY")
            if (
                isinstance(body, dict)
                and cast(dict[str, object], body).get("TASK_ID") == census.TASK_ID
            ):
                raise census.DurableLogError(
                    "header differs: census RUN1 root must remain untouched"
                )


def theorem_certificates(
    manifest: census.Manifest, certified: Certificates
) -> dict[overlay.Cell, Mapping[str, object]]:
    cells: dict[overlay.Cell, Mapping[str, object]] = {}
    for row in manifest.rows:
        body = theorem.certificate(manifest, row, certified.equivalence_sha256, census.repo_root())
        if body is not None:
            cell = overlay.cell_of(row)
            if cell in certified.cells or cell in cells:
                raise CertificateError("theorem cell overlaps another certificate")
            cells[cell] = body
    return cells


def successor_header(
    manifest: census.Manifest,
    certified: Certificates,
    theorems: Mapping[overlay.Cell, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    bound = theorem_certificates(manifest, certified) if theorems is None else theorems
    return {
        "TASK_ID": SUCCESSOR_ID,
        "CENSUS_TASK_ID": census.TASK_ID,
        "MANIFEST_SHA256": manifest.sha256,
        "ENGINE_SHA256": census.engine_sha256(),
        "ADAPTER_SHA256": census.sha256_bytes(Path(__file__).read_bytes()),
        "OVERLAY_SHA256": certified.overlay_sha256,
        "CERTIFIED_IMPORTS_SHA256": certified.imports_sha256,
        "CERTIFIED_CELL_COUNT": len(certified.cells),
        "MODEL_EQUIVALENCE_SHA256": certified.equivalence_sha256,
        "THEOREM_MODULE_SHA256": census.sha256_bytes(Path(str(theorem.__file__)).read_bytes()),
        "THEOREM_CERTIFIED_CELL_COUNT": len(bound),
        "THEOREM_CERTIFICATES_SHA256": census.sha256_bytes(
            census.canonical_json([[*cell, body] for cell, body in sorted(bound.items())]).encode()
        ),
        "PRIOR_RUN_EVIDENCE": PRIOR_RUN_EVIDENCE,
    }


class CertifiedCensus(census.Census):
    """The census engine over a successor root; certified cells are recorded, never solved."""

    def __init__(
        self,
        manifest: census.Manifest,
        certified: Certificates,
        durable: Path,
        solve: census.Solver = census.cp_sat_solve,
        evaluate: census.Evaluator | None = None,
    ) -> None:
        # Census.__init__ would open logs under the census header, so it is not called.
        refuse_run1_root(durable)
        census.require_single_thread_env(os.environ)
        self.manifest = manifest
        self.certified = certified
        self.theorems = theorem_certificates(manifest, certified)
        self.solve = solve
        self.evaluate = evaluate or census.official_evaluator()
        self.durable = durable
        self.root = census.repo_root()
        self._proof: census.DurableLog | None = None
        self._witnesses: census.DurableLog | None = None
        self.solver_calls = 0

    @property
    def proof(self) -> census.DurableLog:
        if self._proof is None:
            raise CertificateError("successor proof log is not initialized")
        return self._proof

    @property
    def witnesses(self) -> census.DurableLog:
        if self._witnesses is None:
            raise CertificateError("successor witness ledger is not initialized")
        return self._witnesses

    def _open_logs(self) -> None:
        if self._proof is not None and self._witnesses is not None:
            self._validate_theorem_records()
            return
        header = successor_header(self.manifest, self.certified, self.theorems)
        self._proof = census.DurableLog(self.durable / census.PROOF_LOG, {**header, "LOG": "PROOF"})
        self._witnesses = census.DurableLog(
            self.durable / census.WITNESS_LEDGER, {**header, "LOG": "WITNESS"}
        )
        self._validate_theorem_records()

    def _theorem_done(self, cell: overlay.Cell) -> dict[str, object]:
        row = next(r for r in self.manifest.rows if overlay.cell_of(r) == cell)
        return {
            "STATUS": theorem.CERTIFIED_STATUS,
            "REFUTED_T": [cell[1]],
            "R30_BOUND": row.r30_bound,
            "PROOF_IDENTITY": theorem.PROOF_IDENTITY,
        }

    def _validate_theorem_records(self) -> None:
        for key, recorded in self.proof.records.items():
            if key[0] == theorem.CERTIFICATE:
                body = self.theorems.get(cast(overlay.Cell, key[1:]))
                if body is None or census.canonical_json(recorded) != census.canonical_json(body):
                    raise census.DurableLogError(
                        "logged theorem certificate differs from its proof"
                    )
            if key[0] in ("SOLVE", CERTIFICATE) and key[1:3] in self.theorems:
                raise census.DurableLogError("theorem cell has a conflicting solver/R30 record")
        for key in self.witnesses.records:
            if key[0] == "WITNESS" and key[1:3] in self.theorems:
                raise census.DurableLogError("theorem cell has a conflicting witness")
        for cell in self.theorems:
            done = self.proof.get(("PROFILE_DONE", cell[0]))
            if done is not None and (
                self.proof.get((theorem.CERTIFICATE, *cell)) is None
                or census.canonical_json(done) != census.canonical_json(self._theorem_done(cell))
            ):
                raise census.DurableLogError("theorem completion conflicts with its certificate")

    def run(self, slice_number: int = 1, profile_limit: int | None = None) -> dict[str, object]:
        with (
            _protected_execution(self.root, durable_root=self.durable),
            census.durable_lock(self.durable),
        ):
            self._open_logs()
            return super().run(slice_number, profile_limit)

    def logged_solve(self, key: census.Key, request: census.SolveRequest) -> census.SolveOutcome:
        with _protected_execution(self.root, durable_root=self.durable):
            claim = safety.active_claim()
            if claim is None:
                raise safety.SafetyGateError("census solver requires the active machine claim")
            claim.assert_path_matches_fd()
            return super().logged_solve(key, request)

    def run_profile(self, row: census.SliceRow) -> dict[str, object]:
        with _protected_execution(self.root, durable_root=self.durable):
            if self._proof is None:
                with census.durable_lock(self.durable):
                    self._open_logs()
                    return self._run_profile_under_gate(row)
            return self._run_profile_under_gate(row)

    def _run_profile_under_gate(self, row: census.SliceRow) -> dict[str, object]:
        cell = overlay.cell_of(row)
        theorem_body = self.theorems.get(cell)
        if theorem_body is not None:
            if (
                theorem.certificate(
                    self.manifest, row, self.certified.equivalence_sha256, self.root
                )
                != theorem_body
            ):
                raise CertificateError("theorem request differs from its certified cell")
            self._validate_theorem_records()
            if self.proof.get((theorem.CERTIFICATE, *cell)) is None:
                self.proof.append((theorem.CERTIFICATE, *cell), theorem_body)
            done = self.proof.get(("PROFILE_DONE", row.profile_id))
            if done is not None:
                return done
            return self.proof.append(("PROFILE_DONE", row.profile_id), self._theorem_done(cell))
        # The census completion key contains only the profile, so it cannot serve
        # a different T from a theorem-certified cell in this same journal.
        if any(
            prior[0] == row.profile_id and self.proof.get((theorem.CERTIFICATE, *prior)) is not None
            for prior in self.theorems
        ):
            raise census.DurableLogError("unsupported cell cannot reuse theorem profile completion")
        body = self.certified.cells.get(cell)
        recorded = self.proof.get((CERTIFICATE, *cell))
        if body is None:
            if recorded is not None:
                raise census.DurableLogError(f"{cell} has a certificate but is not certified")
            return super().run_profile(row)
        if recorded is None:
            if self.proof.get(("PROFILE_DONE", row.profile_id)) is not None:
                raise census.DurableLogError(f"{cell} is done without its certificate")
            self.proof.append((CERTIFICATE, *cell), body)
        elif recorded != dict(body):
            raise census.DurableLogError(f"logged certificate for {cell} differs from the overlay")
        done = self.proof.get(("PROFILE_DONE", row.profile_id))
        if done is not None:
            return done
        return self.proof.append(
            ("PROFILE_DONE", row.profile_id),
            {"STATUS": CERTIFIED_STATUS, "REFUTED_T": [cell[1]], "R30_BOUND": row.r30_bound},
        )

    def summary(self, summaries: Sequence[Mapping[str, object]]) -> dict[str, object]:
        keys = list(self.proof.records)
        return {
            **super().summary(summaries),
            "TASK_ID": SUCCESSOR_ID,
            "CENSUS_TASK_ID": census.TASK_ID,
            "OVERLAY_SHA256": self.certified.overlay_sha256,
            "CERTIFIED_CELLS_RECORDED": sum(k[0] == CERTIFICATE for k in keys),
            "THEOREM_CERTIFIED_CELLS_RECORDED": sum(k[0] == theorem.CERTIFICATE for k in keys),
            "NATIVE_SOLVE_RECORDS": sum(k[0] == "SOLVE" for k in keys),
            "UNREFUTED_CELLS": [
                list(c) for c in self.certified.unrefuted if c not in self.theorems
            ],
            "PRIOR_RUN_EVIDENCE": PRIOR_RUN_EVIDENCE,
        }


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify")
    run = commands.add_parser("run")
    run.add_argument("--profile-limit", type=int, default=None)
    run.add_argument("--durable", type=Path, default=None)
    args = parser.parse_args(argv)
    root = census.repo_root()
    durable = (args.durable or root / DURABLE_RELATIVE) if args.command == "run" else None
    with _protected_execution(root, durable_root=durable):
        census.require_single_thread_env(os.environ)
        manifest = census.load_manifest()
        certified = prepare(manifest, root)
        if args.command == "verify":
            print(
                json.dumps(
                    {
                        "OVERLAY_SHA256": certified.overlay_sha256,
                        "MODEL_EQUIVALENCE_SHA256": certified.equivalence_sha256,
                        "CELLS": len(manifest.rows),
                        "CERTIFIED": len(certified.cells),
                        "UNREFUTED": [list(c) for c in certified.unrefuted],
                        "STRICT_GAIN_THRESHOLD": manifest.threshold,
                    }
                )
            )
            return
        if durable is None:
            raise CertificateError("successor durable root was not selected")
        evaluate = census.official_evaluator()
        census.preflight(manifest, root, evaluate)
        successor = CertifiedCensus(manifest, certified, durable, census.cp_sat_solve, evaluate)
        summary = successor.run(1, args.profile_limit)
        census.write_atomic(
            durable / census.SUMMARY, (json.dumps(summary, indent=1) + "\n").encode()
        )
        print(json.dumps({k: v for k, v in summary.items() if k != "GAINS"}, indent=1))


if __name__ == "__main__":
    main()
