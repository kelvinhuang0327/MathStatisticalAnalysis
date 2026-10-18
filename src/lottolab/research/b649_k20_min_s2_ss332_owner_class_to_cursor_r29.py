"""Strengthen R28's complete SS332 owner class and chase only live owners.

The exact sealed R28 ledger is replayed without a solver. One additional
triangle cap is attempted for the complete 30-member union before member
work. Every accepted refutation rebuilds the complete ledger maximum. The
unresolved cursor is a stop, not an invitation to open a lower plateau.
Only INFEASIBLE with the exact model/cap identity certifies a bound.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from time import monotonic, time

from . import b649_k20_min_s2_current_cursor_class_owner_chase_r28 as r28
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    bound_from_cap,
    decode_profile,
    profile_id,
)

DegreeProfile = r28.DegreeProfile
Solve = r28.Solve
Prover = r28.Prover
TASK_ID = "B649_K20_MIN_S2_SS332_OWNER_CLASS_TO_CURSOR_R29"
TASK_BRANCH = "codex/b649-k20-min-s2-ss332-owner-class-to-cursor-r29"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "155f6f1cc083f4dcd17918484e26be0810c08854"
BASE_TREE = "548fdbe01805b52b447318f18fca4e83100dd0e2"
R28_SHA256 = "edf54e9f34d41f27440b603695076d378fa42ce47922d69e36f16cb2f5cd6dce"
START_BOUND = 313_612_760
NEXT_COMPETING_BOUND = 313_612_088
NEXT_CURSOR_BOUND = 313_611_976
NEXT_CURSOR_PROFILE = decode_profile("66666664322222211111")
INCUMBENT = 313_239_661
OWNER_COUNT = 30
LEDGER_COUNT = 934
TRIANGLE_UNIT = 11_872
RESULT_FILENAME = "b649-k20-min-s2-ss332-owner-class-to-cursor-r29-result.json"
PROOF_WALL_SECONDS = 3_600.0
UNION_SECONDS = 10.0
MEMBER_SECONDS = 30.0
SUCCESS_A = "SUCCESS_A_FAMILY_CLOSED"
SUCCESS_B = "SUCCESS_B_UNRESOLVED_CURSOR_GENUINELY_LOAD_BEARING"
SUCCESS_C = "SUCCESS_C_CERTIFIED_FAMILY_DROP_AT_LEAST_25000"
SUCCESS_D = "SUCCESS_D_BUDGET_END_EXACT_OWNER_AND_LEDGER"
STOPPED = "STOPPED_CURRENT_OWNER_NOT_CERTIFIED"


def authority() -> tuple[dict[str, object], str]:
    """Read only the pinned base blob and assert all load-bearing R28 facts."""

    import subprocess

    relative = f"{r28.RESULT_DIRECTORY}/{r28.RESULT_FILENAME}"
    blob = subprocess.check_output(["git", "show", f"{BASE_HEAD}:{relative}"], cwd=r28.repo_root())
    digest = hashlib.sha256(blob).hexdigest()
    if digest != R28_SHA256:
        raise AssertionError("sealed R28 fingerprint changed")
    result = r28.object_row(json.loads(blob))
    expected = {
        "TASK_ID": r28.TASK_ID,
        "FAMILY_UPPER_BOUND": START_BOUND,
        "MAX_RESOLVED_BOUND": START_BOUND,
        "NEXT_COMPETING_BOUND": NEXT_COMPETING_BOUND,
        "NEXT_ACTIVE_BOUND": NEXT_CURSOR_BOUND,
        "NEXT_ACTIVE_PROFILE": profile_id(NEXT_CURSOR_PROFILE),
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": 373_099,
        "RESOLVED_LEDGER_COUNT": LEDGER_COUNT,
        "NO_OLD_WORK_GUARD": "PASS",
        "WORK_BELOW_CURRENT_FAMILY_MAX_STARTED": False,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise AssertionError(f"R28 authority mismatch: {key}")
    if START_BOUND - NEXT_COMPETING_BOUND != 672 or START_BOUND - NEXT_CURSOR_BOUND != 784:
        raise AssertionError("owner-exit threshold arithmetic changed")
    return result, digest


def ledger(chase: r28.Chase) -> list[dict[str, object]]:
    """Serialize every resolved term, without truncating to current owners."""

    r28.family_state(chase)
    return [
        {"PROFILE_ID": profile_id(p), "CURRENT_BOUND": chase.bounds[p]}
        for p in sorted(chase.bounds, reverse=True)
    ]


def ledger_digest(chase: r28.Chase) -> str:
    return hashlib.sha256(json.dumps(ledger(chase), sort_keys=True).encode()).hexdigest()


def replay(result: Mapping[str, object], deadline: float) -> r28.Chase:
    """Replay the sealed proof chain; no previous model or proof is rerun."""

    chase = r28.start_chase(deadline)[0]
    attempts = list(map(r28.object_row, r28.rows(result["GROUP_ATTEMPTS"])))
    for step in map(r28.object_row, r28.rows(result["REFINEMENT_STEPS"])):
        if step["KIND"] == "CURSOR_PLATEAU_CLASS_CERTIFICATE":
            r28.certify_cursor_plateau(chase)
        elif step["KIND"] == "OWNER_REFUTATION":
            proof = attempts[r28.integer(step["ATTEMPT_INDEX"])]
            profiles = tuple(decode_profile(p) for p in r28.rows(proof["PROFILE_IDS"]))
            cap = r28.integer(step["TRIANGLE_CAP"])
            chase.attempts.append(proof)
            if not r28.apply_proof(chase, (profiles, cap), proof):
                raise AssertionError("sealed R28 step is not certified")
        else:
            raise AssertionError("unknown sealed R28 step")
        if r28.family_state(chase)[0] != step["FAMILY_BOUND_AFTER"]:
            raise AssertionError("R28 owner transition replay diverged")
    sealed = {
        decode_profile(row["PROFILE_ID"]): r28.integer(row["CURRENT_BOUND"])
        for row in map(r28.object_row, r28.rows(result["FINAL_RESOLVED_LEDGER"]))
    }
    family, owners = r28.family_state(chase)
    if (
        chase.bounds != sealed
        or len(sealed) != LEDGER_COUNT
        or family != START_BOUND
        or list(map(profile_id, owners)) != result["FINAL_BOUND_OWNER_IDS"]
        or chase.cursor != NEXT_CURSOR_PROFILE
        or chase.cursor_bound != NEXT_CURSOR_BOUND
        or len(owners) != OWNER_COUNT
        or any(sum(d * d for d in p) != 332 for p in owners)
        or any(chase.catalog[p].triangle_cap != 269 for p in owners)
        or r28.competing_bound(chase, owners) != NEXT_COMPETING_BOUND
    ):
        raise AssertionError("complete R28 934-row ledger/30-owner reconstruction failed")
    chase.attempts.clear()
    chase.steps.clear()
    chase.sequence.clear()
    chase.plateaus.clear()
    chase.failed.clear()
    chase.dispatched.clear()
    chase.nonvacuity.clear()
    chase.checked.clear()
    r28.record_owner(chase)
    return chase


def exit_cap(cert: Certificate) -> int:
    """One triangle is already sufficient; never search a deeper target."""

    cap = r28.integer(cert.triangle_cap) - 1
    if cap < r28.K20_TRIPLE_SUPPORT_COUNT:
        raise AssertionError("no stricter triangle cap remains")
    if bound_from_cap(cert.profile, cap, r28.integer(cert.s4))[1] >= cert.bound:
        raise AssertionError("target cap does not strictly strengthen the certificate")
    return cap


def guard(chase: r28.Chase, profiles: Sequence[DegreeProfile], cap: int) -> None:
    r28.assert_owner_scope(chase, profiles)
    if any(cap != exit_cap(chase.catalog[p]) for p in profiles):
        raise AssertionError("old, weaker, or unnecessarily deep profile work rejected")
    if any(
        a.get("PROFILE_IDS") == list(map(profile_id, profiles))
        and a.get("TARGET_TRIANGLE_CAP") == cap
        for a in chase.attempts
    ):
        raise AssertionError("an old profile/cap model must not be rerun")


def adopt(chase: r28.Chase, solve: Solve, proof: Mapping[str, object]) -> bool:
    """Check refutation identity, strengthen members, rebuild all 934 rows."""

    profiles, cap = solve
    if r28.r26.accepted_cap(proof, profiles, cap) is None:
        chase.failed[solve] = str(proof.get("STATUS"))
        return False
    r28.assert_owner_scope(chase, profiles)
    before, _ = r28.family_state(chase)
    for p in profiles:
        cert = chase.catalog[p]
        if cap != exit_cap(cert):
            raise AssertionError("refutation reuses a sealed or deeper cap")
        s3, bound = bound_from_cap(p, cap, r28.integer(cert.s4))
        chase.bounds[p] = bound
        chase.catalog[p] = replace(
            cert,
            bound=bound,
            s3=s3,
            triangle_cap=cap,
            source_result=RESULT_FILENAME,
            source_row=f"GROUP_ATTEMPTS[{len(chase.attempts) - 1}]",
            relaxation=str(proof["ROUTE"]),
        )
    after, owners = r28.family_state(chase)
    chase.steps.append(
        {
            "ATTEMPT_INDEX": len(chase.attempts) - 1,
            "PROFILE_IDS": list(map(profile_id, profiles)),
            "TRIANGLE_CAP": cap,
            "FAMILY_BOUND_BEFORE": before,
            "FAMILY_BOUND_AFTER": after,
            "OWNER_IDS_AFTER": list(map(profile_id, owners)),
            "COMPLETE_LEDGER_COUNT": len(chase.bounds),
            "COMPLETE_LEDGER_SHA256": ledger_digest(chase),
        }
    )
    r28.record_owner(chase)
    return True


def attempt(
    chase: r28.Chase,
    profiles: tuple[DegreeProfile, ...],
    seconds: float,
    prove: Prover,
    stage: str,
) -> bool:
    cap = exit_cap(chase.catalog[profiles[0]])
    guard(chase, profiles, cap)
    family, owners = r28.family_state(chase)
    solve = (profiles, cap)
    proof = r28.r26.lemma_proof(profiles, cap)
    if proof is None:
        results = prove([solve], seconds, owners)
        if len(results) != 1:
            raise AssertionError("prover returned the wrong number of results")
        proof = results[0]
        chase.dispatched.extend(p for p in profiles if p not in chase.dispatched)
    chase.attempts.append(
        {
            "STAGE": stage,
            "FAMILY_BOUND_AT_DISPATCH": family,
            "OWNER_IDS_AT_DISPATCH": list(map(profile_id, owners)),
            "TARGET_TRIANGLE_CAP": cap,
            "CURRENT_TRIANGLE_CAP": chase.catalog[profiles[0]].triangle_cap,
            "TARGET_BOUND": bound_from_cap(
                profiles[0], cap, r28.integer(chase.catalog[profiles[0]].s4)
            )[1],
            **proof,
        }
    )
    return adopt(chase, solve, proof)


def stop_status(chase: r28.Chase) -> str | None:
    family, owners = r28.family_state(chase)
    if family <= INCUMBENT:
        return SUCCESS_A
    if chase.cursor in owners:
        if max(chase.bounds.values()) > r28.integer(chase.cursor_bound):
            raise AssertionError("cursor claimed ownership above a resolved term")
        return SUCCESS_B
    if START_BOUND - family >= 25_000:
        return SUCCESS_C
    if monotonic() >= chase.deadline - r28.EXTERNAL_GRACE_SECONDS - 1:
        return SUCCESS_D
    return None


def groups(chase: r28.Chase) -> list[tuple[DegreeProfile, ...]]:
    """Group the actual owners by the arithmetic needed for one union cap."""

    _, owners = r28.family_state(chase)
    grouped: dict[tuple[int, int, int], list[DegreeProfile]] = defaultdict(list)
    for p in owners:
        cert = chase.catalog[p]
        key = (r28.overlap_wedge_count(p), r28.integer(cert.triangle_cap), r28.integer(cert.s4))
        grouped[key].append(p)
    return [tuple(members) for members in grouped.values()]


def run(chase: r28.Chase, prove: Prover) -> str:
    """Class first, residual members only; stop as soon as the cursor owns."""

    first = True
    while (status := stop_status(chase)) is None:
        progressed = False
        for members in groups(chase):
            if stop_status(chase) is not None:
                break
            stage = "GENERIC_SS332_CLASS" if first else "DYNAMIC_OWNER_CLASS"
            first = False
            if len(members) > 1 and attempt(chase, members, UNION_SECONDS, prove, stage):
                progressed = True
                continue
            for p in members:
                if stop_status(chase) is not None:
                    break
                _, owners = r28.family_state(chase)
                if p not in owners:
                    continue
                if attempt(chase, (p,), MEMBER_SECONDS, prove, "RESIDUAL_OWNER_MEMBER"):
                    progressed = True
        if not progressed and stop_status(chase) is None:
            return STOPPED
    return status


def compute_result(proof_wall_seconds: float = PROOF_WALL_SECONDS) -> dict[str, object]:
    if not 0 < proof_wall_seconds <= PROOF_WALL_SECONDS:
        raise ValueError("proof wall budget must be in (0, 3600]")
    started, epoch = monotonic(), time()
    deadline = started + proof_wall_seconds
    primitives = r28.canonical_primitive_preflight()
    runtime = r28.solver_runtime_preflight()
    identity = r28.model_identity()
    sealed, digest = authority()
    chase = replay(sealed, deadline)
    initial = r28.family_state(chase)[1]
    initial_digest = ledger_digest(chase)

    def prove(
        solves: Sequence[Solve], seconds: float, owners: Collection[DegreeProfile]
    ) -> list[dict[str, object]]:
        print(
            f"{len(solves[0][0])} owner(s), cap {solves[0][1]}, "
            f"family {r28.family_state(chase)[0]}",
            file=sys.stderr,
            flush=True,
        )
        return r28.bounded_batch(solves, seconds, owners, deadline)

    status = run(chase, prove)
    family, owners = r28.family_state(chase)
    types = sorted({r28.owner_type(chase, p) for p in owners})
    class_attempt = chase.attempts[0] if chase.attempts else {}
    individual = [
        str(p)
        for a in chase.attempts
        if a["STAGE"] == "RESIDUAL_OWNER_MEMBER" and a["STATUS"] == "INFEASIBLE"
        for p in r28.rows(a["PROFILE_IDS"])
    ]
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "TASK_STATUS": status,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "START_BOUND": START_BOUND,
        "OWNER_PROFILE_COUNT": len(initial),
        "OWNER_PROFILES": list(map(profile_id, initial)),
        "AUTHORITY_FINGERPRINT": {"R28_RESULT_SHA256": digest, "SEALED_LEDGER_REPLAY": "PASS"},
        "INITIAL_COMPLETE_LEDGER_SHA256": initial_digest,
        "THRESHOLD_ARITHMETIC": {
            "TO_NEXT_COMPETITOR": 672,
            "TO_CURSOR": 784,
            "ONE_TRIANGLE_DROP": TRIANGLE_UNIT,
        },
        "CLASS_WIDE_CERTIFICATE_STATUS": class_attempt.get("STATUS", "NOT_RUN"),
        "CLASS_WIDE_CERTIFICATE": class_attempt,
        "PROFILES_INDIVIDUALLY_REFINED": sorted(set(individual), reverse=True),
        "OWNER_TRANSITION_COUNT": len(chase.sequence) - 1,
        "OWNER_CLASS_SEQUENCE": chase.sequence,
        "INITIAL_NEXT_COMPETING_BOUND": NEXT_COMPETING_BOUND,
        "NEXT_COMPETING_BOUND": r28.competing_bound(chase, owners),
        "NEXT_COMPETING_BOUND_SCOPE": "FINAL_FAMILY_OUTSIDE_CURRENT_OWNER_SET",
        "NEXT_CURSOR_BOUND": chase.cursor_bound,
        "NEXT_CURSOR_PROFILE": profile_id(NEXT_CURSOR_PROFILE),
        "FINAL_BOUND_OWNER_TYPE": types[0] if len(types) == 1 else types,
        "FINAL_BOUND_OWNER_IDS": list(map(profile_id, owners)),
        "FINAL_BOUND_OWNERS": r28.owner_rows(chase, owners),
        "MAX_RESOLVED_BOUND": max(chase.bounds.values()),
        "FAMILY_UPPER_BOUND": family,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family - INCUMBENT,
        "CERTIFIED_FAMILY_DROP": START_BOUND - family,
        "FAMILY_STATUS": "CLOSED"
        if family <= INCUMBENT
        else "OPEN_STRICTLY_TIGHTENED"
        if family < START_BOUND
        else "OPEN_UNCHANGED",
        "CURSOR_GENUINELY_LOAD_BEARING": chase.cursor in owners,
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "CANONICAL_PRIMITIVES": primitives,
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "MODEL_IDENTITY": identity,
        "SOLVER_STATUS": dict(Counter(str(a["STATUS"]) for a in chase.attempts)),
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "UNION_NATIVE_SECONDS": UNION_SECONDS,
            "MEMBER_NATIVE_SECONDS": MEMBER_SECONDS,
            "CP_SAT_SEARCH_WORKERS": r28.CP_SAT_WORKERS,
            "PROOF_WALL_SECONDS": proof_wall_seconds,
            "EXTERNAL_GRACE_SECONDS": r28.EXTERNAL_GRACE_SECONDS,
            "EXTERNAL_KILL_AFTER_SECONDS": r28.EXTERNAL_KILL_SECONDS,
        },
        "SOLVER_ACTUAL_WALL_TIME": sum(
            float(str(a.get("SOLVER_WALL_TIME_SECONDS", 0))) for a in chase.attempts
        ),
        "SOLVER_CERTIFIED_BOUND": family,
        "SOLVER_CERTIFIED_BOUND_SCOPE": "COMPLETE_R28_LEDGER_PLUS_UNRESOLVED_CURSOR",
        "GROUP_ATTEMPTS": chase.attempts,
        "REFINEMENT_STEPS": chase.steps,
        "FINAL_RESOLVED_LEDGER": ledger(chase),
        "FINAL_COMPLETE_LEDGER_SHA256": ledger_digest(chase),
        "RESOLVED_LEDGER_COUNT": len(chase.bounds),
        "R28_PROOF_RERUN_COUNT": 0,
        "NO_OLD_PROFILE_RERUN_GUARD": "PASS",
        "NO_WORK_BELOW_FAMILY_MAX_GUARD": "PASS",
        "CURSOR_PROFILE_SOLVES": 0,
        "PROOF_STARTED_UNIX_TIME": epoch,
        "PROOF_ACTUAL_WALL_SECONDS": monotonic() - started,
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "JUDGE_MODE": "NOT_APPLICABLE",
        "JUDGE_DISPATCH": "SUPPRESSED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-wall-seconds", type=float, default=PROOF_WALL_SECONDS)
    args = parser.parse_args()
    result = compute_result(args.proof_wall_seconds)
    path: Path = r28.repo_root() / r28.RESULT_DIRECTORY / RESULT_FILENAME
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {k: result[k] for k in ("TASK_STATUS", "FAMILY_UPPER_BOUND", "FINAL_BOUND_OWNER_IDS")}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
