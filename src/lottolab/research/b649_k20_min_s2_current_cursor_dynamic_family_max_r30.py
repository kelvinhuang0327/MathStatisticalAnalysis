"""Resolve R29's load-bearing cursor plateau, then chase the family maximum (R30).

Authority is the sealed R29 result at cbea8328, pinned by SHA-256. R28's
chain is replayed through R29's own replay, and R29's INFEASIBLE proofs are
then re-applied without solving. Together they reproduce R29's complete
934-row ledger digest and its unique unresolved cursor owner.

Phase 1 freezes every unresolved profile tied with the cursor at its coarse
bound. Phase 2 applies the R18 induced-P3 class certificate to the whole
plateau with zero solves. A drop of only 673 is enough to expose the resolved
maximum. Phase 3 recomputes the complete family maximum after every certified
change and works only on its current owners:

* an unresolved cursor: freeze its plateau and apply the class certificate;
* resolved owners: R26's closed-form lemma, else the exact-support
  open-wedge refutation of one profile at its exit cap. The exit cap is the
  shallowest cap strictly below the certificate.

* a resolved owner whose exact-support refutation returns a witness (or
  stays UNKNOWN after one retry): the closed-form K4-motif S4 correction.

Route 4 (motif/S4 correction). A realization with t graph triangles has
exactly W - 3t open wedges, where W is the profile's wedge count. A vertex of
graph degree g whose neighbourhood misses o pairs spans at least
C(g,3) - (g-2)*o triangles. Each such triangle is a K4 through that vertex,
and every K4 is counted at its four vertices, so the number of K4 quartets is
at least ceil((sum_v C(g_v,3) - (g_max-2)*(W-3t))/4). Pair overlaps are at
most one and multiplicities at most three. A K4 quartet therefore has one of
two exact local profiles, and the compressed four-ticket DP of R2 weighs them
at 448 (contained triple) and 679 outcomes. All S4 terms are non-negative, so
S4 >= 448*K4. The profile bound becomes the maximum over t <= cap of the
R13/R20 envelope with that S4 floor. Route 3, the complement triangle bound,
cannot cut a cap that the exact-support model realizes, so it is never tried
after a witness.

The cyclic STS(13)-minus-a-point (12,8) portfolio lies in this family, with
degree profile 55555555555511111100. Its exact any-prize union is
313,263,867, 21 below the canonical incumbent 313,263,888. It realizes 270
graph triangles with 6 open wedges, so no exact-support refutation can lower
that profile's 270 cap. Route 4 is checked on the witness's exact K4 count
and exact S4. Every family recomputation asserts the realized union as a
soundness tripwire.

Resume. The first segment stopped after 2,113 s at the Route-4 blocker
55555555555511111100 (family 313,588,232). Its result stays in place. A
resumed segment replays that segment's sealed steps with no solves, keeping
every attempt index, and asserts the checkpoint ledger. It certifies the
blocker by Route 4 from the logged exact-support witness. It then chases the
family maximum, with both segments together held to the 3,600 s budget.

Method limit. The canonical incumbent 313,263,888 also has profile
55555555555511111100, with 270 triangles, 550 K4, S3 = 5,198,256 and
S4 = 331,240. Every routes 1-4 bound on that profile is therefore at least
313,399,016, which is 135,128 above the incumbent. So routes 1-4 cannot close
the family.

Large unions repeatedly returned UNKNOWN in R28 and R29, so every solver
model here holds exactly one profile. Only INFEASIBLE certifies a cap.
FEASIBLE, UNKNOWN and timeouts never change a bound. No R28 or R29 target is
ever re-solved. Every dispatched attempt is appended to a durable proof log,
and the complete ledger is checkpointed after every batch. A resumed segment
serves this task's own definitive logged results and spends only the rest of
the 3600-second budget.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from functools import cache
from itertools import combinations, permutations
from math import comb
from pathlib import Path
from time import monotonic, time

from . import b649_k20_min_s2_current_cursor_class_owner_chase_r28 as r28
from . import b649_k20_min_s2_higher_order_closure_r2 as r2
from . import b649_k20_min_s2_ss332_owner_class_to_cursor_r29 as r29
from .b649_k20_min_s2_class_dominance_or_descent_r13 import (
    graph_triangle_upper_bound_from_open_wedges,
    profile_family_envelope_from_triangle_bound,
)
from .b649_k20_min_s2_cursor_plateau_closure_r18 import generic_open_wedge_floor
from .b649_k20_min_s2_load_bearing_plateau_descent_r16 import PlateauFrontier
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import coarse_profile_envelope
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
)
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    bound_from_cap,
    decode_profile,
    profile_id,
)
from .b649_k20_min_s2_successive_class_dominance_r14 import lookup_ranked_frontier
from .b649_official_any_prize_exact import evaluate_portfolio

DegreeProfile = r28.DegreeProfile
Solve = r28.Solve
Prover = r28.Prover
Chase = r28.Chase
OldWork = frozenset[tuple[tuple[str, ...], int]]

TASK_ID = "B649_K20_MIN_S2_CURRENT_CURSOR_DYNAMIC_FAMILY_MAX_R30"
TASK_BRANCH = "codex/b649-k20-min-s2-current-cursor-dynamic-family-max-r30"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "cbea83281a9ea7959de584a6b66d500f7bd0e6e1"
BASE_TREE = "bf7fd8af9b8b7c5df1d89eafb0a4c713b970fb66"
R29_RESULT = r29.RESULT_FILENAME
R29_SHA256 = "f7a081c0455c367984c156ec38e6bc80f2fae96038c4267a5b5c845d6b81951e"
R29_LEDGER_SHA256 = "c430909cc7dad7f63ef912139f33191b9f17e15335d9c9c16f4cd7a822e1203b"
START_BOUND = 313_611_976
START_CURSOR = decode_profile("66666664322222211111")
START_MAX_RESOLVED = 313_611_304
OWNER_MARGIN = 672
INCUMBENT = 313_263_888
INCUMBENT_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
R29_INCUMBENT = 313_239_661
START_GAP = 372_315
LEDGER_COUNT = 934
EXPECTED_PLATEAU_COUNT = 112
EXPECTED_PLATEAU_SQUARE_SUM = 306
EXPECTED_CLASS_BOUND = 313_588_232
EXPECTED_NEXT_CURSOR = decode_profile("66666664222222221111")
EXPECTED_NEXT_BOUND = 313_597_304
EXPECTED_FIRST_RESOLVED_OWNERS = 88
EDGE_COUNT = r28.EDGE_COUNT
RESULT_DIRECTORY = r28.RESULT_DIRECTORY
RESULT_FILENAME = "b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
DURABLE_DIRECTORY = ".task-data/r30"
PROOF_LOG = "proof-log.jsonl"
CHECKPOINT = "ledger-checkpoint.json"
PROOF_WALL_SECONDS = 3_600.0
MEMBER_SECONDS = 30.0
RETRY_SECONDS = 120.0
BATCH_LIMIT = 64
MAX_PLATEAU_PROFILES = 4_096
RETRYABLE = ("UNKNOWN", "EXTERNAL_TIMEOUT")
ROUTE4_TRIGGERS = ("OPTIMAL", "FEASIBLE", *RETRYABLE)
STAGE_MEMBER = "OWNER_MEMBER"
STAGE_RETRY = "OWNER_MEMBER_RETRY"
KIND_PLATEAU = "CURSOR_PLATEAU_CLASS_CERTIFICATE"
KIND_REFUTATION = "OWNER_REFUTATION"
KIND_MOTIF = "OWNER_K4_MOTIF_S4_CORRECTION"
ROUTE_MOTIF = "D4_K4_MOTIF_S4_CORRECTION"
DEFINITIVE = ("INFEASIBLE", "OPTIMAL", "FEASIBLE")
WITNESS_PROFILE = decode_profile("55555555555511111100")
WITNESS_UNION = 313_263_867
WITNESS_TRIANGLES = 270
SUCCESS_A = "SUCCESS_A_FAMILY_UPPER_BOUND_AT_OR_BELOW_INCUMBENT"
SUCCESS_B = "SUCCESS_B_ROUTE4_BLOCKER_CERTIFIED_NEXT_LOAD_BEARING_OWNER_REACHED"
SUCCESS_C = "SUCCESS_C_BUDGET_END_EXACT_OWNER_AND_DURABLE_LEDGER"
STOPPED = "STOPPED_CURRENT_OWNER_NOT_CERTIFIED"
SEGMENT1_RESULT = "segment-1-result.json"
SEGMENT1_CHECKPOINT = "segment-1-ledger-checkpoint.json"
SEGMENT1_SHA256 = "5b7e5d10583d275409441c422e107994fb6058fae5060933c6c35c436481e777"
SEGMENT1_CHECKPOINT_SHA256 = "ac9384758d0dd893615716ac22fb9359791df43dcd3df1898a9bd52d01c2d520"
SEGMENT1_LOG_SHA256 = "ef319997d4c9cd412061a3eb4500468557ece74f824f4fd3508bd4a28254d596"
SEGMENT1_ATTEMPTS_SHA256 = "271088148ccbd1a6ddc16cf451a22237b7048d09dc5ee05a7ce2d74b56eb11d5"
SEGMENT1_STEPS_SHA256 = "b0502b9a769c9ef30160e8fcde8e65119d142d15f400af7e2e003435badae177"
CHECKPOINT_BOUND = 313_588_232
CHECKPOINT_OWNER = WITNESS_PROFILE
CHECKPOINT_NEXT_COMPETITOR = 313_587_560
CHECKPOINT_LEDGER_SHA256 = "375ccbe04ac1e5216ef66d69e9d5576ce7e5bd0fb6813925f53af64301f359b0"
CHECKPOINT_LEDGER_COUNT = 1_399
CHECKPOINT_ATTEMPTS = 1_780
CHECKPOINT_STEPS = 1_782
CHECKPOINT_PLATEAUS = 4
CHECKPOINT_SEQUENCE_LENGTH = 48
CHECKPOINT_TRIGGER = 1_775
SEGMENT1_WALL_SECONDS = 2_113.4437457919994
SEGMENT1_ACCOUNTED_MS = 2_113_444
SEGMENT2_CAP_MS = 3_600_000 - SEGMENT1_ACCOUNTED_MS
FINALIZE_RESERVE_SECONDS = 30.0
REPLAYED_PLATEAU_FIELDS = (
    "PLATEAU_MEMBERSHIP_SHA256",
    "COMPLETE_LEDGER_SHA256",
    "NEXT_CURSOR_BOUND",
)

object_row = r28.object_row
rows = r28.rows
integer = r28.integer


class PlateauLookupLimit(RuntimeError):
    """The ranked lookup could not close the current coarse-bound plateau."""


def git_blob(relative: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{BASE_HEAD}:{relative}"], cwd=r28.repo_root())


def r29_authority() -> tuple[dict[str, object], str]:
    """Read only the pinned R29 blob and assert every load-bearing fact."""

    blob = git_blob(f"{RESULT_DIRECTORY}/{R29_RESULT}")
    digest = hashlib.sha256(blob).hexdigest()
    if digest != R29_SHA256:
        raise AssertionError("sealed R29 fingerprint changed")
    result = object_row(json.loads(blob))
    expected: dict[str, object] = {
        "TASK_ID": r29.TASK_ID,
        "TASK_STATUS": r29.SUCCESS_B,
        "FAMILY_UPPER_BOUND": START_BOUND,
        "MAX_RESOLVED_BOUND": START_MAX_RESOLVED,
        "NEXT_COMPETING_BOUND": START_MAX_RESOLVED,
        "NEXT_CURSOR_BOUND": START_BOUND,
        "NEXT_CURSOR_PROFILE": profile_id(START_CURSOR),
        "FINAL_BOUND_OWNER_IDS": [profile_id(START_CURSOR)],
        "FINAL_BOUND_OWNER_TYPE": r28.CURSOR_OWNER,
        "CURSOR_GENUINELY_LOAD_BEARING": True,
        "RESOLVED_LEDGER_COUNT": LEDGER_COUNT,
        "FINAL_COMPLETE_LEDGER_SHA256": R29_LEDGER_SHA256,
        "INCUMBENT": R29_INCUMBENT,
        "REMAINING_GAP": START_GAP,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise AssertionError(f"R29 authority mismatch: {key}")
    if START_BOUND - START_MAX_RESOLVED != OWNER_MARGIN or START_BOUND - R29_INCUMBENT != START_GAP:
        raise AssertionError("owner-margin arithmetic changed")
    return result, digest


def attempt_keys(result: Mapping[str, object]) -> set[tuple[tuple[str, ...], int]]:
    keys: set[tuple[tuple[str, ...], int]] = set()
    for raw in rows(result["GROUP_ATTEMPTS"]):
        attempt = object_row(raw)
        ids = tuple(str(p) for p in rows(attempt["PROFILE_IDS"]))
        keys.add((ids, integer(attempt["TARGET_TRIANGLE_CAP"])))
    return keys


def start_chase(deadline: float) -> tuple[Chase, str, OldWork]:
    """Replay R28 via R29, re-apply R29's proofs, assert the sealed state."""

    sealed29, digest = r29_authority()
    sealed28, _ = r29.authority()
    chase = r29.replay(sealed28, deadline)
    steps = {
        integer(step["ATTEMPT_INDEX"]): step
        for step in map(object_row, rows(sealed29["REFINEMENT_STEPS"]))
    }
    for index, raw in enumerate(rows(sealed29["GROUP_ATTEMPTS"])):
        attempt = object_row(raw)
        chase.attempts.append(attempt)
        step = steps.pop(index, None)
        if step is None:
            if attempt.get("STATUS") == "INFEASIBLE":
                raise AssertionError("an R29 INFEASIBLE attempt has no refinement step")
            continue
        profiles = tuple(decode_profile(p) for p in rows(step["PROFILE_IDS"]))
        if not r29.adopt(chase, (profiles, integer(step["TRIANGLE_CAP"])), attempt):
            raise AssertionError("sealed R29 step is not certified")
        if r28.family_state(chase)[0] != step["FAMILY_BOUND_AFTER"]:
            raise AssertionError("R29 owner transition replay diverged")
    sealed = {
        decode_profile(row["PROFILE_ID"]): integer(row["CURRENT_BOUND"])
        for row in map(object_row, rows(sealed29["FINAL_RESOLVED_LEDGER"]))
    }
    family, owners = r28.family_state(chase)
    if (
        steps
        or chase.bounds != sealed
        or r29.ledger_digest(chase) != R29_LEDGER_SHA256
        or family != START_BOUND
        or owners != (START_CURSOR,)
        or chase.cursor_bound != START_BOUND
        or max(chase.bounds.values()) != START_MAX_RESOLVED
        or any(b > START_BOUND for b in chase.bounds.values())
    ):
        raise AssertionError("R29 complete-ledger/unique-cursor reconstruction failed")
    old = frozenset(attempt_keys(sealed28) | attempt_keys(sealed29))
    chase.attempts.clear()
    chase.steps.clear()
    chase.sequence.clear()
    chase.plateaus.clear()
    chase.failed.clear()
    chase.dispatched.clear()
    chase.nonvacuity.clear()
    chase.checked.clear()
    record_owner(chase)
    return chase, digest, old


def record_owner(chase: Chase) -> None:
    """Append one entry each time the family maximum takes a new value."""

    family, owners = r28.family_state(chase)
    if family < WITNESS_UNION:
        raise AssertionError("family bound fell below a realized min-S2 portfolio")
    if chase.sequence and chase.sequence[-1]["FAMILY_BOUND"] == family:
        return
    chase.sequence.append(
        {
            "FAMILY_BOUND": family,
            "OWNER_TYPES": sorted({r28.owner_type(chase, p) for p in owners}),
            "OWNER_COUNT": len(owners),
            "OWNER_IDS": list(map(profile_id, owners)),
            "COMPLETE_LEDGER_COUNT": len(chase.bounds),
        }
    )


def freeze_plateau(
    cursor: DegreeProfile, active: int, prior: Collection[DegreeProfile], deadline: float
) -> PlateauFrontier:
    """R16's exact ranked plateau freeze, with a larger bounded prefix."""

    if coarse_profile_envelope(cursor).family_upper_bound != active:
        raise AssertionError("plateau cursor does not own the active coarse bound")
    square_sum = sum(d * d for d in cursor)
    limit = 8
    while True:
        frontier = lookup_ranked_frontier(
            start_profile=cursor,
            start_square_sum=square_sum,
            profile_limit=limit,
            deadline=deadline,
            prior_profiles=prior,
        )
        if not frontier.profiles or frontier.profiles[0] != cursor:
            raise AssertionError("ranked frontier does not begin at the active cursor")
        bounds = [e.family_upper_bound for e in frontier.envelopes]
        if any(b > active for b in bounds):
            raise AssertionError("an unresolved ranked profile exceeds the active bound")
        lower = next((i for i, b in enumerate(bounds) if b < active), None)
        if lower is not None or frontier.lookup_complete:
            end = len(bounds) if lower is None else lower
            return PlateauFrontier(
                bound=active,
                profiles=frontier.profiles[:end],
                next_profile=None if lower is None else frontier.profiles[lower],
                next_bound=None if lower is None else bounds[lower],
                lookup_profile_count=len(frontier.profiles),
                complete_profiles_examined=frontier.complete_profiles_examined,
                square_sum_classes_examined=frontier.square_sum_classes_examined,
                lookup_complete=frontier.lookup_complete,
                frontier=frontier,
            )
        if limit >= MAX_PLATEAU_PROFILES:
            raise PlateauLookupLimit("the coarse-bound plateau did not end in the bounded prefix")
        limit = min(MAX_PLATEAU_PROFILES, 2 * limit)


def membership_digest(profiles: Sequence[DegreeProfile]) -> str:
    return hashlib.sha256(json.dumps(list(map(profile_id, profiles))).encode()).hexdigest()


def phase1_freeze(chase: Chase) -> dict[str, object]:
    """Freeze the exact plateau tied with the start cursor; assert ownership."""

    family, owners = r28.family_state(chase)
    above = [p for p, b in chase.bounds.items() if b > START_BOUND]
    plateau = freeze_plateau(
        START_CURSOR, START_BOUND, chase.bounds, min(chase.deadline, monotonic() + 120.0)
    )
    members = plateau.profiles
    resolved = max(chase.bounds.values())
    if (
        family != START_BOUND
        or owners != (START_CURSOR,)
        or members[0] != START_CURSOR
        or START_CURSOR not in members
        or above
        or resolved != START_MAX_RESOLVED
        or START_BOUND - resolved != OWNER_MARGIN
        or any(p in chase.bounds for p in members)
        or any(coarse_profile_envelope(p).family_upper_bound != START_BOUND for p in members)
        or plateau.next_bound is None
        or plateau.next_bound >= START_BOUND
    ):
        raise AssertionError("start plateau membership or cursor ownership changed")
    return {
        "CURSOR_PROFILE": profile_id(START_CURSOR),
        "ACTIVE_COARSE_BOUND": START_BOUND,
        "PLATEAU_PROFILE_COUNT": len(members),
        "PLATEAU_PROFILE_IDS": list(map(profile_id, members)),
        "PLATEAU_MEMBERSHIP_SHA256": membership_digest(members),
        "SQUARE_SUMS": sorted({sum(d * d for d in p) for p in members}),
        "CURSOR_IS_MEMBER": True,
        "RESOLVED_ABOVE_CURSOR_COUNT": len(above),
        "MAX_RESOLVED_BOUND": resolved,
        "OWNER_MARGIN_OVER_RESOLVED": START_BOUND - resolved,
        "CLASS_DROP_THAT_EXPOSES_RESOLVED_MAX": START_BOUND - resolved + 1,
        "NEXT_LOWER_PROFILE": None
        if plateau.next_profile is None
        else profile_id(plateau.next_profile),
        "NEXT_LOWER_BOUND": plateau.next_bound,
        "LOOKUP_PROFILE_COUNT": plateau.lookup_profile_count,
    }


def certify_plateau(chase: Chase) -> dict[str, object]:
    """R28's zero-solve R18 class certificate on the cursor plateau, R30 provenance."""

    family, owners = r28.family_state(chase)
    cursor, active = chase.cursor, chase.cursor_bound
    if cursor is None or active is None or active != family or owners[0] != cursor:
        raise AssertionError("only an unresolved cursor that owns the family max is certified")
    plateau = freeze_plateau(
        cursor, active, chase.bounds, min(chase.deadline, monotonic() + r28.PLATEAU_LOOKUP_SECONDS)
    )
    members = plateau.profiles
    if (
        members[0] != cursor
        or len(set(members)) != len(members)
        or any(p in chase.bounds for p in members)
        or any(coarse_profile_envelope(p).family_upper_bound != active for p in members)
        or (plateau.next_bound is not None and plateau.next_bound >= active)
    ):
        raise AssertionError("plateau membership is incomplete or exceeds the active bound")
    floor = generic_open_wedge_floor(
        K20_TICKET_COUNT, EDGE_COUNT, K20_TICKET_CAPACITY, 2 * K20_TICKET_CAPACITY
    )
    envelope = graph_triangle_upper_bound_from_open_wedges(
        tuple(K20_TICKET_CAPACITY + d for d in cursor), floor
    )
    cap = envelope["GRAPH_TRIANGLE_UPPER_BOUND"]
    index = len(chase.plateaus)
    residual: list[DegreeProfile] = []
    class_bounds: list[int] = []
    for p in members:
        if (
            graph_triangle_upper_bound_from_open_wedges(
                tuple(K20_TICKET_CAPACITY + d for d in p), floor
            )
            != envelope
        ):
            raise AssertionError("plateau members do not share the class wedge envelope")
        s4 = r28.profile_s4_floor(p)
        s3, bound = bound_from_cap(p, cap, s4)
        if bound < active:
            if profile_family_envelope_from_triangle_bound(p, cap)["FAMILY_UPPER_BOUND"] != bound:
                raise AssertionError("class bound does not reproduce the R13 motif envelope")
        else:
            residual.append(p)
        class_bounds.append(min(bound, active))
        chase.bounds[p] = min(bound, active)
        chase.catalog[p] = Certificate(
            p,
            min(bound, active),
            RESULT_FILENAME,
            f"PLATEAU_CERTIFICATES[{index}]",
            "CLASS_ENVELOPE_ONLY",
            s3,
            s4,
            cap,
            r28.ROUTE_CLASS if bound < active else r28.ROUTE_RESIDUAL,
        )
    chase.cursor, chase.cursor_bound = plateau.next_profile, plateau.next_bound
    after, new_owners = r28.family_state(chase)
    row: dict[str, object] = {
        "PLATEAU_INDEX": index,
        "CURSOR_PROFILE": profile_id(cursor),
        "ACTIVE_COARSE_BOUND": active,
        "SQUARE_SUMS": sorted({sum(d * d for d in p) for p in members}),
        "PLATEAU_PROFILE_COUNT": len(members),
        "PLATEAU_PROFILE_IDS": list(map(profile_id, members)),
        "PLATEAU_MEMBERSHIP_SHA256": membership_digest(members),
        "CLASS_CERTIFICATE_KIND": r28.ROUTE_CLASS,
        "INDUCED_P3_OPEN_WEDGE_LOWER_BOUND": floor,
        **envelope,
        "CLASS_FAMILY_UPPER_BOUND": max(class_bounds),
        "CERTIFIED_MEMBER_COUNT": len(members) - len(residual),
        "RESIDUAL_MEMBER_COUNT": len(residual),
        "RESIDUAL_MEMBER_IDS": list(map(profile_id, residual)),
        "CLASS_DOMINANCE": "COMPLETE" if not residual else "PARTIAL_RESIDUALS_TO_MEMBERS",
        "INDIVIDUAL_SOLVES": 0,
        "NEXT_CURSOR_PROFILE": None
        if plateau.next_profile is None
        else profile_id(plateau.next_profile),
        "NEXT_CURSOR_BOUND": plateau.next_bound,
        "LOOKUP_PROFILE_COUNT": plateau.lookup_profile_count,
        "FAMILY_BOUND_BEFORE": family,
        "FAMILY_BOUND_AFTER": after,
        "OWNER_COUNT_AFTER": len(new_owners),
        "COMPLETE_LEDGER_COUNT": len(chase.bounds),
        "COMPLETE_LEDGER_SHA256": r29.ledger_digest(chase),
    }
    chase.plateaus.append(row)
    chase.steps.append(
        {
            "KIND": KIND_PLATEAU,
            "PLATEAU_INDEX": index,
            "FAMILY_BOUND_BEFORE": family,
            "FAMILY_BOUND_AFTER": after,
        }
    )
    record_owner(chase)
    return row


def exit_cap(cert: Certificate) -> int:
    """The shallowest cap strictly below the certificate that lowers its bound."""

    cap = integer(cert.triangle_cap) - 1
    while cap >= K20_TRIPLE_SUPPORT_COUNT:
        if bound_from_cap(cert.profile, cap, integer(cert.s4))[1] < cert.bound:
            return cap
        cap -= 1
    raise AssertionError("no stricter triangle cap remains")


class DurableLog:
    """Append-only proof log plus an atomically replaced ledger checkpoint."""

    def __init__(
        self, directory: Path | None, replayed: dict[tuple[str, int], list[dict[str, object]]]
    ):
        self.directory = directory
        self.replayed = replayed
        self.served = 0

    def append(self, attempt: Mapping[str, object]) -> None:
        if self.directory is None:
            return
        with (self.directory / PROOF_LOG).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(attempt) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def checkpoint(self, chase: Chase) -> None:
        if self.directory is None:
            return
        family, owners = r28.family_state(chase)
        state = {
            "TASK_ID": TASK_ID,
            "UNIX_TIME": time(),
            "FAMILY_UPPER_BOUND": family,
            "FINAL_BOUND_OWNER_IDS": list(map(profile_id, owners)),
            "NEXT_ACTIVE_PROFILE": None if chase.cursor is None else profile_id(chase.cursor),
            "NEXT_ACTIVE_BOUND": chase.cursor_bound,
            "ATTEMPT_COUNT": len(chase.attempts),
            "STEP_COUNT": len(chase.steps),
            "PLATEAUS_PROCESSED": len(chase.plateaus),
            "RESOLVED_LEDGER_COUNT": len(chase.bounds),
            "COMPLETE_LEDGER_SHA256": r29.ledger_digest(chase),
            "FINAL_RESOLVED_LEDGER": r29.ledger(chase),
        }
        temporary = self.directory / (CHECKPOINT + ".tmp")
        temporary.write_text(json.dumps(state) + "\n", encoding="utf-8")
        os.replace(temporary, self.directory / CHECKPOINT)

    def serve(self, solve: Solve, index: int) -> dict[str, object] | None:
        """The next logged attempt for this target, only at its original attempt index."""

        queue = self.replayed.get((profile_id(solve[0][0]), solve[1]))
        if not queue:
            return None
        logged = queue.pop(0)
        if logged["ATTEMPT_INDEX"] != index:
            raise AssertionError("a logged attempt identity shifted on resume")
        self.served += 1
        proof = {k: v for k, v in logged.items() if k not in ATTEMPT_CONTEXT}
        return {**proof, "REPLAYED_FROM_DURABLE_LOG": True}


def load_replayed(path: Path) -> dict[tuple[str, int], list[dict[str, object]]]:
    """This task's own logged single-profile attempts, queued per target in log order.

    A timeout and its retry share one target; serving both in order, each at its
    original attempt index, replays the retry path instead of shifting indices.
    """

    replayed: dict[tuple[str, int], list[dict[str, object]]] = {}
    if not path.exists():
        return replayed
    for line in path.read_text(encoding="utf-8").splitlines():
        attempt = object_row(json.loads(line))
        ids = rows(attempt["PROFILE_IDS"])
        if attempt.get("STATUS") in (*DEFINITIVE, *RETRYABLE) and len(ids) == 1:
            key = (str(ids[0]), integer(attempt["TARGET_TRIANGLE_CAP"]))
            replayed.setdefault(key, []).append(attempt)
    return replayed


ATTEMPT_CONTEXT = (
    "ATTEMPT_INDEX",
    "STAGE",
    "FAMILY_BOUND_AT_DISPATCH",
    "OWNER_COUNT_AT_DISPATCH",
    "CURRENT_BOUND",
    "CURRENT_TRIANGLE_CAP",
    "TARGET_TRIANGLE_CAP",
    "TARGET_BOUND",
    "REPLAYED_FROM_DURABLE_LOG",
)


def guard(chase: Chase, solve: Solve, old: OldWork) -> None:
    """Single current owner, exact exit cap, never an old or failed target."""

    profiles, cap = solve
    if len(profiles) != 1:
        raise AssertionError("union models are excluded; one profile per solver model")
    r28.assert_owner_scope(chase, profiles)
    if chase.catalog[profiles[0]].relaxation == ROUTE_MOTIF:
        raise AssertionError("route A is not motif-aware; a motif owner cannot be re-refuted")
    if cap != exit_cap(chase.catalog[profiles[0]]):
        raise AssertionError("old, weaker, or unnecessarily deep profile work rejected")
    if (tuple(map(profile_id, profiles)), cap) in old or solve in chase.failed:
        raise AssertionError("an R28/R29 or failed profile/cap target must not be rerun")


def dispatch(
    chase: Chase,
    solves: Sequence[Solve],
    seconds: float,
    prove: Prover,
    stage: str,
    old: OldWork,
    log: DurableLog,
) -> list[tuple[int, dict[str, object]]]:
    """Lemma, then the durable log, then one bounded solver child for the rest."""

    family, owners = r28.family_state(chase)
    out: dict[int, dict[str, object]] = {}
    pending: list[int] = []
    for index, solve in enumerate(solves):
        guard(chase, solve, old)
        proof = r28.r26.lemma_proof(*solve) or log.serve(solve, len(chase.attempts) + index)
        if proof is None:
            pending.append(index)
        else:
            out[index] = proof
    if pending:
        proofs = prove([solves[i] for i in pending], seconds, owners)
        if len(proofs) != len(pending):
            raise AssertionError("prover returned the wrong number of proofs")
        for index, proof in zip(pending, proofs, strict=True):
            out[index] = proof
            p = solves[index][0][0]
            if p not in chase.dispatched:
                chase.dispatched.append(p)
    results: list[tuple[int, dict[str, object]]] = []
    for index, (profiles, cap) in enumerate(solves):
        cert = chase.catalog[profiles[0]]
        attempt: dict[str, object] = {
            "ATTEMPT_INDEX": len(chase.attempts),
            "STAGE": stage,
            "FAMILY_BOUND_AT_DISPATCH": family,
            "OWNER_COUNT_AT_DISPATCH": len(owners),
            "CURRENT_BOUND": cert.bound,
            "CURRENT_TRIANGLE_CAP": cert.triangle_cap,
            "TARGET_TRIANGLE_CAP": cap,
            "TARGET_BOUND": bound_from_cap(profiles[0], cap, integer(cert.s4))[1],
            **out[index],
        }
        chase.attempts.append(attempt)
        log.append(attempt)
        results.append((integer(attempt["ATTEMPT_INDEX"]), out[index]))
    return results


def adopt(chase: Chase, solve: Solve, index: int, proof: Mapping[str, object]) -> bool:
    """Adopt one exact INFEASIBLE refutation and recompute the complete family."""

    profiles, cap = solve
    if r28.r26.accepted_cap(proof, profiles, cap) is None:
        chase.failed[solve] = str(proof.get("STATUS"))
        return False
    r28.assert_owner_scope(chase, profiles)
    before, _ = r28.family_state(chase)
    (p,) = profiles
    cert = chase.catalog[p]
    s3, bound = bound_from_cap(p, cap, integer(cert.s4))
    if cap != exit_cap(cert) or bound >= chase.bounds[p]:
        raise AssertionError("refutation does not strictly tighten its current owner")
    chase.bounds[p] = bound
    chase.catalog[p] = replace(
        cert,
        bound=bound,
        s3=s3,
        triangle_cap=cap,
        source_result=RESULT_FILENAME,
        source_row=f"GROUP_ATTEMPTS[{index}]",
        relaxation=str(proof["ROUTE"]),
    )
    after, owners = r28.family_state(chase)
    chase.steps.append(
        {
            "KIND": KIND_REFUTATION,
            "ATTEMPT_INDEX": index,
            "PROFILE_ID": profile_id(p),
            "TRIANGLE_CAP": cap,
            "NEW_BOUND": bound,
            "FAMILY_BOUND_BEFORE": before,
            "FAMILY_BOUND_AFTER": after,
            "OWNER_COUNT_AFTER": len(owners),
        }
    )
    record_owner(chase)
    return True


@cache
def k4_quartet_weights() -> dict[str, int]:
    """Exact four-ticket outcome counts of both K4 quartet profiles (R2 DP)."""

    def weight(masks: Mapping[int, int]) -> int:
        counts = [0] * 16
        for mask, count in masks.items():
            counts[mask] = count
        counts[0] = r2.BIG_LOTTO_POOL_SIZE - sum(counts)
        return r2.compressed_four_ticket_intersection_count(
            counts,
            pool_size=r2.BIG_LOTTO_POOL_SIZE,
            draw_size=r2.BIG_LOTTO_DRAW_SIZE,
            outright_matches=r2.BIG_LOTTO_OUTRIGHT_MATCHES,
        )

    pairs = {3: 1, 5: 1, 6: 1, 9: 1, 10: 1, 12: 1}
    return {
        "SIX_EDGES_WITH_CONTAINED_TRIPLE": weight(
            {7: 1, 9: 1, 10: 1, 12: 1, 1: 4, 2: 4, 4: 4, 8: 3}
        ),
        "SIX_EDGES_WITHOUT_CONTAINED_TRIPLE": weight({**pairs, 1: 3, 2: 3, 4: 3, 8: 3}),
    }


def k4_lower_bound(degrees: Sequence[int], open_wedges: int) -> int:
    """K4 floor of every simple graph with these degrees and open-wedge count."""

    if open_wedges < 0 or min(degrees) < 0:
        raise AssertionError("open wedges and degrees must be non-negative")
    excess = sum(comb(g, 3) for g in degrees) - max(0, max(degrees) - 2) * open_wedges
    return max(0, -(-excess // 4))


def motif_s4_floor(profile: DegreeProfile, triangles: int) -> tuple[int, int]:
    """K4 and S4 floors for every realization with exactly ``triangles`` triangles."""

    degrees = [K20_TICKET_CAPACITY + d for d in profile]
    open_wedges = overlap_wedge_count(profile) - 3 * triangles
    if open_wedges < 0:
        raise AssertionError("triangle count exceeds the wedge identity")
    k4 = k4_lower_bound(degrees, open_wedges)
    return k4, min(k4_quartet_weights().values()) * k4


def sts13_witness() -> tuple[tuple[int, ...], ...]:
    """Cyclic STS(13) ({0,1,4},{0,2,7} mod 13) minus point 0, plus the rigid 8-block.

    Tickets 0..11 are the points 1..12. A block avoiding 0 is a triple label, and
    a block through 0 leaves a pair label. Tickets 12..19 form K8 minus the edge
    {18,19}: trios {12,13,14} and {15,16,17} and a pair label on every other edge.
    """

    blocks = sorted(
        sorted({i % 13, (i + a) % 13, (i + b) % 13}) for i in range(13) for a, b in ((1, 4), (2, 7))
    )
    labels = [tuple(v - 1 for v in block if v) for block in blocks]
    trios = ((12, 13, 14), (15, 16, 17))
    labels += trios
    labels += [
        e
        for e in combinations(range(12, 20), 2)
        if e != (18, 19) and not any(set(e) <= set(t) for t in trios)
    ]
    if len(labels) != 49 or len({frozenset(b) for b in blocks}) != 26:
        raise AssertionError("witness construction does not use 49 labels")
    return tuple(
        tuple(n + 1 for n, label in enumerate(labels) if v in label)
        for v in range(K20_TICKET_COUNT)
    )


def quartet_outcomes(tickets: Sequence[Collection[int]]) -> int:
    """Outcomes common to four tickets, by the R2 DP on their incidence profile."""

    counts = [0] * 16
    for label in range(1, r2.BIG_LOTTO_POOL_SIZE + 1):
        counts[sum(1 << i for i, t in enumerate(tickets) if label in t)] += 1
    return canonical_quartet_outcomes(
        min(
            tuple(counts[sum(1 << p[i] for i in range(4) if m >> i & 1)] for m in range(16))
            for p in permutations(range(4))
        )
    )


@cache
def canonical_quartet_outcomes(counts: tuple[int, ...]) -> int:
    return r2.compressed_four_ticket_intersection_count(
        counts,
        pool_size=r2.BIG_LOTTO_POOL_SIZE,
        draw_size=r2.BIG_LOTTO_DRAW_SIZE,
        outright_matches=r2.BIG_LOTTO_OUTRIGHT_MATCHES,
    )


def witness_soundness() -> dict[str, object]:
    """Recount the realizable witness and check every Route-4 premise against it."""

    tickets = sts13_witness()
    sets = [set(t) for t in tickets]
    triple = [sum(1 for n in t if sum(n in s for s in sets) == 3) for t in tickets]
    profile = tuple(sorted(triple, reverse=True))
    adjacent = {(a, b): len(sets[a] & sets[b]) for a, b in combinations(range(K20_TICKET_COUNT), 2)}
    if any(v > 1 for v in adjacent.values()):
        raise AssertionError("witness pair overlap exceeds one")

    def clique(q: Sequence[int]) -> bool:
        return all(adjacent[e] for e in combinations(q, 2))

    degrees = [
        sum(adjacent[min(a, b), max(a, b)] for b in range(K20_TICKET_COUNT) if b != a)
        for a in range(K20_TICKET_COUNT)
    ]
    triangles = sum(clique(q) for q in combinations(range(K20_TICKET_COUNT), 3))
    k4 = sum(clique(q) for q in combinations(range(K20_TICKET_COUNT), 4))
    s4 = sum(
        quartet_outcomes([tickets[i] for i in q]) for q in combinations(range(K20_TICKET_COUNT), 4)
    )
    union = evaluate_portfolio(tickets).official_any_prize_outcome_count
    open_wedges = overlap_wedge_count(profile) - 3 * triangles
    k4_floor, s4_floor = motif_s4_floor(profile, triangles)
    exact_s4_bound = bound_from_cap(profile, triangles, s4)[1]
    floor_bound = bound_from_cap(profile, triangles, s4_floor)[1]
    if (
        profile != WITNESS_PROFILE
        or degrees != [K20_TICKET_CAPACITY + d for d in triple]
        or union != WITNESS_UNION
        or triangles != WITNESS_TRIANGLES
        or k4 < k4_floor
        or s4 < s4_floor
        or s4 < min(k4_quartet_weights().values()) * k4
        or not union <= exact_s4_bound <= floor_bound
        or not WITNESS_UNION < INCUMBENT
    ):
        raise AssertionError("Route 4 over-tightens the realizable STS(13) witness")
    return {
        "STATUS": "PASS",
        "CONSTRUCTION": "CYCLIC_STS13_0_1_4_0_2_7_MINUS_POINT_0_PLUS_K8_MINUS_EDGE_8_BLOCK",
        "PROFILE_ID": profile_id(profile),
        "EXACT_ANY_PRIZE_UNION": union,
        "CANONICAL_INCUMBENT": INCUMBENT,
        "BELOW_INCUMBENT_BY": INCUMBENT - union,
        "GRAPH_TRIANGLES": triangles,
        "OPEN_WEDGES": open_wedges,
        "EXACT_K4": k4,
        "K4_FLOOR_AT_WITNESS_TRIANGLES": k4_floor,
        "EXACT_S4": s4,
        "S4_FLOOR_AT_WITNESS_TRIANGLES": s4_floor,
        "BOUND_WITH_EXACT_S4": exact_s4_bound,
        "ROUTE4_BOUND_AT_WITNESS_TRIANGLES": floor_bound,
        "SLACK_UNDER_ROUTE4_BOUND": floor_bound - union,
    }


def method_capability(witness: Mapping[str, object]) -> dict[str, object]:
    """Routes 1-4 bound a profile by S1 - S2 + S3 - floor(4*S4_floor/7).

    A valid S4 floor at 270 triangles cannot exceed the exact S4 of a realization
    with 270 triangles. The witness and the canonical incumbent share the profile,
    270 triangles, 550 K4, S3 and S4, so no routes 1-4 bound on that profile can
    fall below the exact-S4 value, which lies above the incumbent.
    """

    floor = integer(witness["BOUND_WITH_EXACT_S4"])
    return {
        "INCUMBENT": INCUMBENT,
        "INCUMBENT_SHA256": INCUMBENT_SHA256,
        "INCUMBENT_PROFILE_ID": profile_id(WITNESS_PROFILE),
        "ROUTES_1_TO_4_FLOOR_FOR_INCUMBENT_PROFILE": floor,
        "ROUTES_1_TO_4_SHORTFALL_TO_INCUMBENT": floor - INCUMBENT,
        "SUCCESS_A_REACHABLE_BY_ROUTES_1_TO_4": floor <= INCUMBENT,
    }


def motif_certify(chase: Chase, profile: DegreeProfile, trigger: int) -> dict[str, object] | None:
    """Route 4 on one current owner whose exact-support refutation failed."""

    r28.assert_owner_scope(chase, (profile,))
    cert = chase.catalog[profile]
    if cert.relaxation == ROUTE_MOTIF:
        return None
    cap, base = integer(cert.triangle_cap), integer(cert.s4)
    envelope = [
        (bound_from_cap(profile, t, max(base, s4))[1], t, k4, s4)
        for t in range(K20_TRIPLE_SUPPORT_COUNT, cap + 1)
        for k4, s4 in (motif_s4_floor(profile, t),)
    ]
    bound, top, k4, floor = max(envelope)
    s4 = max(base, floor)
    s3, at_cap = bound_from_cap(profile, cap, s4)
    if top != cap or at_cap != bound or bound >= cert.bound:
        return None
    if profile == WITNESS_PROFILE and bound < WITNESS_UNION:
        raise AssertionError("motif bound fell below the realized witness portfolio")
    before, _ = r28.family_state(chase)
    chase.bounds[profile] = bound
    chase.catalog[profile] = replace(
        cert,
        bound=bound,
        s3=s3,
        source_result=RESULT_FILENAME,
        source_row=f"REFINEMENT_STEPS[{len(chase.steps)}]",
        relaxation=ROUTE_MOTIF,
    )
    after, owners = r28.family_state(chase)
    degrees = [K20_TICKET_CAPACITY + d for d in profile]
    row: dict[str, object] = {
        "KIND": KIND_MOTIF,
        "PROFILE_ID": profile_id(profile),
        "TRIGGER_ATTEMPT_INDEX": trigger,
        "ROUTE": ROUTE_MOTIF,
        "TRIANGLE_CAP": cap,
        "WEDGE_COUNT": overlap_wedge_count(profile),
        "OPEN_WEDGES_AT_CAP": overlap_wedge_count(profile) - 3 * cap,
        "SUM_GRAPH_DEGREE_CHOOSE_3": sum(comb(g, 3) for g in degrees),
        "MAX_GRAPH_DEGREE": max(degrees),
        "K4_LOWER_BOUND_AT_CAP": k4,
        "K4_QUARTET_WEIGHTS": k4_quartet_weights(),
        "GLOBAL_S4_FLOOR": base,
        "S4_LOWER_BOUND_AT_CAP": s4,
        "CAP_SCOPED_FLOOR_VALIDITY": "ONLY_REALIZATIONS_WITH_EXACTLY_TRIANGLE_CAP_TRIANGLES",
        "BOUND_RULE": "MAX_OVER_T_IN_22..CAP_OF_S1-S2+S3(T)-FLOOR(4*MAX(GLOBAL,448*K4(T))/7)",
        "ENVELOPE_MAXIMIZED_AT_TRIANGLES": top,
        "PREVIOUS_BOUND": cert.bound,
        "NEW_BOUND": bound,
        "FAMILY_BOUND_BEFORE": before,
        "FAMILY_BOUND_AFTER": after,
        "OWNER_COUNT_AFTER": len(owners),
    }
    chase.steps.append(row)
    record_owner(chase)
    return row


def stop_status(chase: Chase) -> str | None:
    """SUCCESS_A closes the family; SUCCESS_C is the end of the proof budget.

    A stall at an owner no route can lower returns STOPPED to the caller. A resumed
    segment reports SUCCESS_B only for a stall at an owner other than its Route-4
    blocker, after the blocker left the family maximum.
    """

    family, _ = r28.family_state(chase)
    if family <= INCUMBENT:
        return SUCCESS_A
    if monotonic() >= chase.deadline - r28.EXTERNAL_GRACE_SECONDS - 1:
        return SUCCESS_C
    return None


def run(
    chase: Chase, prove: Prover, old: OldWork, log: DurableLog
) -> tuple[str, tuple[DegreeProfile, ...]]:
    """Phase 3: certify only the current family maximum until A/B, C or a stop."""

    while (status := stop_status(chase)) is None:
        _, owners = r28.family_state(chase)
        if chase.cursor is not None and owners[0] == chase.cursor:
            certify_plateau(chase)
            log.checkpoint(chase)
            continue
        motif_owners = tuple(p for p in owners if chase.catalog[p].relaxation == ROUTE_MOTIF)
        if motif_owners:
            log.checkpoint(chase)
            return STOPPED, motif_owners
        solves: list[Solve] = [((p,), exit_cap(chase.catalog[p])) for p in owners[:BATCH_LIMIT]]
        before = {solve: chase.bounds[solve[0][0]] for solve in solves}
        proofs = dispatch(chase, solves, MEMBER_SECONDS, prove, STAGE_MEMBER, old, log)
        stuck: list[Solve] = []
        trigger: dict[Solve, int] = {}
        for solve, (index, proof) in zip(solves, proofs, strict=True):
            if not adopt(chase, solve, index, proof):
                stuck.append(solve)
                trigger[solve] = index
        for solve in stuck:
            reason = chase.failed[solve]
            late = monotonic() >= chase.deadline - r28.EXTERNAL_GRACE_SECONDS - RETRY_SECONDS
            if reason == "PROOF_BUDGET_EXHAUSTED" or (reason in RETRYABLE and late):
                log.checkpoint(chase)
                return SUCCESS_C, tuple(s[0][0] for s in stuck if s in chase.failed)
            if reason in RETRYABLE:
                del chase.failed[solve]
                retried = dispatch(chase, [solve], RETRY_SECONDS, prove, STAGE_RETRY, old, log)
                ((trigger[solve], proof),) = retried
                if adopt(chase, solve, trigger[solve], proof):
                    continue
                reason = chase.failed[solve]
            if reason in ROUTE4_TRIGGERS:
                motif_certify(chase, solve[0][0], trigger[solve])
        log.checkpoint(chase)
        unresolved = tuple(s[0][0] for s in stuck if chase.bounds[s[0][0]] == before[s])
        if unresolved:
            return stop_status(chase) or STOPPED, unresolved
    return status, ()


def replay_result(result: Mapping[str, object], deadline: float) -> Chase:
    """Recompute the complete ledger from the sealed R30 steps without solving."""

    chase, _ = replay_steps(result, None, deadline)
    if (
        r29.ledger(chase) != result["FINAL_RESOLVED_LEDGER"]
        or r29.ledger_digest(chase) != result["FINAL_COMPLETE_LEDGER_SHA256"]
        or r28.family_state(chase)[0] != result["FAMILY_UPPER_BOUND"]
        or chase.sequence != result["OWNER_CLASS_SEQUENCE"]
    ):
        raise AssertionError("complete R30 ledger replay diverged")
    return chase


def json_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def replay_steps(
    result: Mapping[str, object], limit: int | None, deadline: float
) -> tuple[Chase, OldWork]:
    """Replay the first ``limit`` sealed steps (all when None) without solving."""

    chase, _, old = start_chase(deadline)
    phase1_freeze(chase)
    attempts = [object_row(a) for a in rows(result["GROUP_ATTEMPTS"])]
    plateaus = [object_row(p) for p in rows(result["PLATEAU_CERTIFICATES"])]
    for step in map(object_row, rows(result["REFINEMENT_STEPS"])[:limit]):
        if step["KIND"] == KIND_PLATEAU:
            row = certify_plateau(chase)
            sealed = plateaus[integer(step["PLATEAU_INDEX"])]
            if any(row[k] != sealed[k] for k in REPLAYED_PLATEAU_FIELDS):
                raise AssertionError("plateau class certificate replay diverged")
        elif step["KIND"] == KIND_REFUTATION:
            index = integer(step["ATTEMPT_INDEX"])
            attempt = attempts[index]
            cap = integer(step["TRIANGLE_CAP"])
            if (
                attempt["ATTEMPT_INDEX"] != index
                or attempt["PROFILE_IDS"] != [step["PROFILE_ID"]]
                or attempt["TARGET_TRIANGLE_CAP"] != cap
            ):
                raise AssertionError("refutation step does not name its sealed attempt")
            proof = {k: v for k, v in attempt.items() if k not in ATTEMPT_CONTEXT}
            if not adopt(chase, ((decode_profile(str(step["PROFILE_ID"])),), cap), index, proof):
                raise AssertionError("sealed R30 refutation is not certified")
        elif step["KIND"] == KIND_MOTIF:
            index = integer(step["TRIGGER_ATTEMPT_INDEX"])
            if (
                attempts[index]["PROFILE_IDS"] != [step["PROFILE_ID"]]
                or attempts[index]["STATUS"] == "INFEASIBLE"
            ):
                raise AssertionError("motif step does not name a failed exact-support attempt")
            row = motif_certify(chase, decode_profile(str(step["PROFILE_ID"])), index)
            if row is None or row["NEW_BOUND"] != step["NEW_BOUND"]:
                raise AssertionError("motif certificate replay diverged")
        else:
            raise AssertionError("unknown sealed R30 step")
        if r28.family_state(chase)[0] != step["FAMILY_BOUND_AFTER"]:
            raise AssertionError("R30 owner transition replay diverged")
    return chase, old


def checkpoint_chase(result: Mapping[str, object], deadline: float) -> tuple[Chase, OldWork]:
    """Replay exactly the first segment, assert its checkpoint, restore its attempts.

    ``result`` is the sealed first segment or any later result that extends it.
    Every first-segment profile/cap target joins the never-rerun set.
    """

    attempts = [object_row(a) for a in rows(result["GROUP_ATTEMPTS"])][:CHECKPOINT_ATTEMPTS]
    steps = rows(result["REFINEMENT_STEPS"])[:CHECKPOINT_STEPS]
    if (
        len(attempts) != CHECKPOINT_ATTEMPTS
        or json_digest(attempts) != SEGMENT1_ATTEMPTS_SHA256
        or json_digest(steps) != SEGMENT1_STEPS_SHA256
    ):
        raise AssertionError("first-segment attempts or steps differ from the sealed checkpoint")
    chase, old = replay_steps(result, CHECKPOINT_STEPS, deadline)
    family, owners = r28.family_state(chase)
    trigger = attempts[CHECKPOINT_TRIGGER]
    cap = exit_cap(chase.catalog[CHECKPOINT_OWNER])
    if (
        family != CHECKPOINT_BOUND
        or owners != (CHECKPOINT_OWNER,)
        or r29.ledger_digest(chase) != CHECKPOINT_LEDGER_SHA256
        or len(chase.bounds) != CHECKPOINT_LEDGER_COUNT
        or len(chase.plateaus) != CHECKPOINT_PLATEAUS
        or len(chase.sequence) != CHECKPOINT_SEQUENCE_LENGTH
        or r28.competing_bound(chase, owners) != CHECKPOINT_NEXT_COMPETITOR
        or chase.catalog[CHECKPOINT_OWNER].relaxation == ROUTE_MOTIF
        or trigger["PROFILE_IDS"] != [profile_id(CHECKPOINT_OWNER)]
        or trigger["TARGET_TRIANGLE_CAP"] != cap
        or trigger["STATUS"] not in ("OPTIMAL", "FEASIBLE")
        or r28.r26.accepted_cap(trigger, (CHECKPOINT_OWNER,), cap) is not None
    ):
        raise AssertionError("first-segment checkpoint replay diverged")
    chase.attempts.extend(attempts)
    chase.failed[((CHECKPOINT_OWNER,), cap)] = str(trigger["STATUS"])
    for attempt in attempts:
        p = decode_profile(str(rows(attempt["PROFILE_IDS"])[0]))
        if attempt.get("ROUTE") != r28.ROUTE_D and p not in chase.dispatched:
            chase.dispatched.append(p)
    return chase, old | frozenset(attempt_keys({"GROUP_ATTEMPTS": attempts}))


def compute_result(
    prove: Prover | None = None,
    proof_wall_seconds: float = PROOF_WALL_SECONDS,
    durable: Path | None = None,
    resume: bool = False,
) -> dict[str, object]:
    if not 0 < proof_wall_seconds <= PROOF_WALL_SECONDS:
        raise ValueError("proof wall budget must be in (0, 3600]")
    started, epoch = monotonic(), time()
    deadline = started + proof_wall_seconds
    checks = preflights()
    chase, _, old = start_chase(deadline)
    start_ledger = r29.ledger_digest(chase)
    phase1 = phase1_freeze(chase)
    if phase1["PLATEAU_PROFILE_COUNT"] != EXPECTED_PLATEAU_COUNT or phase1["SQUARE_SUMS"] != [
        EXPECTED_PLATEAU_SQUARE_SUM
    ]:
        raise AssertionError("start plateau membership changed")
    replayed = load_replayed(durable / PROOF_LOG) if durable is not None and resume else {}
    log = DurableLog(durable, replayed)
    phase2 = certify_plateau(chase)
    family, owners = r28.family_state(chase)
    if (
        phase2["PLATEAU_MEMBERSHIP_SHA256"] != phase1["PLATEAU_MEMBERSHIP_SHA256"]
        or phase2["CLASS_FAMILY_UPPER_BOUND"] != EXPECTED_CLASS_BOUND
        or phase2["RESIDUAL_MEMBER_COUNT"] != 0
        or phase2["NEXT_CURSOR_PROFILE"] != profile_id(EXPECTED_NEXT_CURSOR)
        or phase2["NEXT_CURSOR_BOUND"] != EXPECTED_NEXT_BOUND
        or family != START_MAX_RESOLVED
        or len(owners) != EXPECTED_FIRST_RESOLVED_OWNERS
    ):
        raise AssertionError("class certificate no longer exposes the resolved maximum")
    log.checkpoint(chase)

    def solver(
        solves: Sequence[Solve], seconds: float, live: Collection[DegreeProfile]
    ) -> list[dict[str, object]]:
        print(
            f"{len(solves)} solve(s), family {r28.family_state(chase)[0]}, "
            f"ledger {len(chase.bounds)}, elapsed {monotonic() - started:.0f}s",
            file=sys.stderr,
            flush=True,
        )
        return r28.bounded_batch(solves, seconds, live, deadline)

    status, stuck = run(chase, prove or solver, old, log)
    return {
        **result_header(status),
        "START_COMPLETE_LEDGER_SHA256": start_ledger,
        "PHASE1_PLATEAU_FREEZE": phase1,
        "PLATEAU_PROFILE_COUNT": phase1["PLATEAU_PROFILE_COUNT"],
        "PHASE2_CLASS_CERTIFICATE": {
            k: phase2[k]
            for k in (
                "PLATEAU_INDEX",
                "CLASS_DOMINANCE",
                "GRAPH_TRIANGLE_UPPER_BOUND",
                "CLASS_FAMILY_UPPER_BOUND",
                "FAMILY_BOUND_AFTER",
                "OWNER_COUNT_AFTER",
                "INDIVIDUAL_SOLVES",
            )
        },
        **chase_fields(chase, stuck, old, checks, proof_wall_seconds),
        "DURABLE_STATE": {
            "PROOF_LOG": f"{DURABLE_DIRECTORY}/{PROOF_LOG}",
            "LEDGER_CHECKPOINT": f"{DURABLE_DIRECTORY}/{CHECKPOINT}",
            "RESUMED": resume,
            "REPLAYED_PROOFS_SERVED": log.served,
        },
        "PROOF_STARTED_UNIX_TIME": epoch,
        "PROOF_ACTUAL_WALL_SECONDS": monotonic() - started,
        **RESULT_TRAILER,
    }


RESULT_TRAILER: dict[str, object] = {
    "WORKTREE_DISPOSITION": "RETAIN",
    "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
    "PRODUCTION_MUTATION": "NONE",
    "JUDGE_MODE": "NOT_APPLICABLE",
    "JUDGE_DISPATCH": "SUPPRESSED",
}


def preflights() -> dict[str, object]:
    primitives = r28.canonical_primitive_preflight()
    return {
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "CANONICAL_PRIMITIVES": primitives,
        "SOLVER_RUNTIME_PREFLIGHT": r28.solver_runtime_preflight(),
        "MODEL_IDENTITY": r28.model_identity(),
    }


def result_header(status: str) -> dict[str, object]:
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "TASK_STATUS": status,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "INPUT_AUTHORITY": "CBEA8328_R29_SEALED_RESULT_REPLAYED_ON_R28_CHAIN",
        "AUTHORITY_FINGERPRINT": {
            "R29_RESULT_SHA256": R29_SHA256,
            "R29_FINAL_LEDGER_SHA256": R29_LEDGER_SHA256,
            "R28_RESULT_SHA256": r29.R28_SHA256,
            "SEALED_REPLAY": "PASS",
        },
        "START_BOUND": START_BOUND,
        "START_CURSOR_PROFILE": profile_id(START_CURSOR),
    }


def chase_fields(
    chase: Chase,
    stuck: Sequence[DegreeProfile],
    old: OldWork,
    checks: Mapping[str, object],
    proof_wall_seconds: float,
) -> dict[str, object]:
    """Result fields shared by a fresh and a resumed R30 segment."""

    family, owners = r28.family_state(chase)
    types = sorted({r28.owner_type(chase, p) for p in owners})
    solved = [a for a in chase.attempts if not a.get("REPLAYED_FROM_DURABLE_LOG")]
    return {
        "PLATEAUS_PROCESSED": len(chase.plateaus),
        "PLATEAU_CERTIFICATES": chase.plateaus,
        "CLASSES_CERTIFIED": sum(p["CLASS_DOMINANCE"] == "COMPLETE" for p in chase.plateaus),
        "PROFILES_PROCESSED": sum(
            c.source_result == RESULT_FILENAME for c in chase.catalog.values()
        ),
        "PROFILES_PROCESSED_SCOPE": "DISTINCT_PROFILES_WHOSE_CERTIFICATE_R30_STRENGTHENED",
        "PROFILES_SENT_TO_SOLVER": len(chase.dispatched),
        "OWNER_TRANSITION_COUNT": len(chase.sequence) - 1,
        "OWNER_TRANSITION_SCOPE": "CHANGES_OF_THE_FAMILY_MAXIMUM_VALUE",
        "OWNER_CLASS_SEQUENCE": chase.sequence,
        "FINAL_BOUND_OWNER_TYPE": types[0] if len(types) == 1 else types,
        "FINAL_BOUND_OWNER_IDS": list(map(profile_id, owners)),
        "FINAL_BOUND_OWNERS": r28.owner_rows(chase, owners),
        "UNTIGHTENED_OWNER_IDS": list(map(profile_id, stuck)),
        "MAX_RESOLVED_BOUND": max(chase.bounds.values()),
        "NEXT_ACTIVE_BOUND": chase.cursor_bound,
        "NEXT_ACTIVE_PROFILE": None if chase.cursor is None else profile_id(chase.cursor),
        "NEXT_COMPETING_BOUND": r28.competing_bound(chase, owners),
        "FAMILY_UPPER_BOUND": family,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family - INCUMBENT,
        "CERTIFIED_FAMILY_DROP": START_BOUND - family,
        "FAMILY_STATUS": "CLOSED"
        if family <= INCUMBENT
        else "OPEN_STRICTLY_TIGHTENED"
        if family < START_BOUND
        else "OPEN_UNCHANGED",
        **checks,
        "SOLVER_STATUS": dict(sorted(Counter(str(a["STATUS"]) for a in chase.attempts).items())),
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "MEMBER_NATIVE_SECONDS": MEMBER_SECONDS,
            "RETRY_NATIVE_SECONDS": RETRY_SECONDS,
            "CP_SAT_SEARCH_WORKERS": r28.CP_SAT_WORKERS,
            "BATCH_LIMIT": BATCH_LIMIT,
            "PROOF_WALL_SECONDS": proof_wall_seconds,
            "EXTERNAL_GRACE_SECONDS": r28.EXTERNAL_GRACE_SECONDS,
            "EXTERNAL_KILL_AFTER_SECONDS": r28.EXTERNAL_KILL_SECONDS,
        },
        "SOLVER_ACTUAL_WALL_TIME": sum(
            float(str(a.get("SOLVER_WALL_TIME_SECONDS", 0))) for a in solved
        ),
        "SOLVER_CERTIFIED_BOUND": family,
        "SOLVER_CERTIFIED_BOUND_SCOPE": "COMPLETE_FAMILY_LEDGER_PLUS_UNRESOLVED_CURSOR",
        "GROUP_ATTEMPTS": chase.attempts,
        "REFINEMENT_STEPS": chase.steps,
        "FINAL_RESOLVED_LEDGER": r29.ledger(chase),
        "FINAL_COMPLETE_LEDGER_SHA256": r29.ledger_digest(chase),
        "RESOLVED_LEDGER_COUNT": len(chase.bounds),
        "R28_R29_PROOF_RERUN_COUNT": 0,
        "NO_OLD_WORK_GUARD": "PASS",
        "OLD_TARGET_COUNT_GUARDED": len(old),
        "UNION_ATTEMPTS": sum(len(rows(a["PROFILE_IDS"])) != 1 for a in chase.attempts),
        "NO_LARGE_UNION_WASTE_GUARD": "PASS",
        "WORK_BELOW_CURRENT_FAMILY_MAX_STARTED": False,
        "FULL_4850_PROFILE_CENSUS_REBUILT": False,
    }


def pinned(path: Path, pin: str) -> bytes:
    data = path.read_bytes() if path.exists() else b""
    if hashlib.sha256(data).hexdigest() != pin:
        raise AssertionError(f"first-segment durable state changed: {path.name}")
    return data


def preserve_segment1(target: Path, durable: Path) -> None:
    """Copy the in-place first-segment result and checkpoint before the resume rewrites them."""

    for source, copy, pin in (
        (target, durable / SEGMENT1_RESULT, SEGMENT1_SHA256),
        (durable / CHECKPOINT, durable / SEGMENT1_CHECKPOINT, SEGMENT1_CHECKPOINT_SHA256),
    ):
        if copy.exists():
            pinned(copy, pin)
        else:
            copy.write_bytes(pinned(source, pin))


def segment1_authority(durable: Path) -> dict[str, object]:
    """The sealed first segment, its checkpoint and an untouched first-segment proof log."""

    for path, pin in (
        (durable / SEGMENT1_RESULT, SEGMENT1_SHA256),
        (durable / SEGMENT1_CHECKPOINT, SEGMENT1_CHECKPOINT_SHA256),
        (durable / CHECKPOINT, SEGMENT1_CHECKPOINT_SHA256),
        (durable / PROOF_LOG, SEGMENT1_LOG_SHA256),
    ):
        pinned(path, pin)
    segment1 = object_row(json.loads((durable / SEGMENT1_RESULT).read_text(encoding="utf-8")))
    logged = [json.loads(line) for line in (durable / PROOF_LOG).read_text().splitlines()]
    if logged != segment1["GROUP_ATTEMPTS"]:
        raise AssertionError("first-segment proof log does not equal its sealed attempts")
    return segment1


def new_profiles(chase: Chase) -> list[str]:
    """Distinct profiles whose certificate the resumed segment strengthened."""

    seen: dict[str, None] = {}
    for step in chase.steps[CHECKPOINT_STEPS:]:
        if step["KIND"] == KIND_PLATEAU:
            plateau = chase.plateaus[integer(step["PLATEAU_INDEX"])]
            seen.update(dict.fromkeys(map(str, rows(plateau["PLATEAU_PROFILE_IDS"]))))
        else:
            seen[str(step["PROFILE_ID"])] = None
    return list(seen)


def resume_result(
    segment1: Mapping[str, object], prove: Prover | None = None, durable: Path | None = None
) -> dict[str, object]:
    """Replay the stopped first segment, certify its blocker by Route 4, chase the rest."""

    sealed = float(str(segment1["PROOF_ACTUAL_WALL_SECONDS"]))
    prior = SEGMENT1_ACCOUNTED_MS / 1000
    cap = SEGMENT2_CAP_MS / 1000
    budget = cap - FINALIZE_RESERVE_SECONDS
    if (
        segment1.get("TASK_STATUS") != STOPPED
        or sealed != SEGMENT1_WALL_SECONDS
        or not sealed <= prior < PROOF_WALL_SECONDS
        or not 0 < budget < cap
    ):
        raise AssertionError("only the stopped first segment with proof budget left resumes")
    started, epoch = monotonic(), time()
    deadline = started + budget
    checks = preflights()
    chase, old = checkpoint_chase(segment1, deadline)
    chase.deadline = deadline
    replay_seconds = monotonic() - started
    witness = witness_soundness()
    route4 = motif_certify(chase, CHECKPOINT_OWNER, CHECKPOINT_TRIGGER)
    route4_status = (
        "NOT_CERTIFIED"
        if route4 is None
        else "TIGHTENED_OWNER_UNCHANGED"
        if CHECKPOINT_OWNER in r28.family_state(chase)[1]
        else "OWNER_SWITCH"
    )
    log = DurableLog(durable, {})
    log.checkpoint(chase)

    def solver(
        solves: Sequence[Solve], seconds: float, live: Collection[DegreeProfile]
    ) -> list[dict[str, object]]:
        elapsed = monotonic() - started
        print(
            f"{len(solves)} solve(s), family {r28.family_state(chase)[0]}, "
            f"ledger {len(chase.bounds)}, resume {elapsed:.0f}s, total {prior + elapsed:.0f}s",
            file=sys.stderr,
            flush=True,
        )
        return r28.bounded_batch(solves, seconds, live, deadline)

    if route4 is None:
        status, stuck = STOPPED, (CHECKPOINT_OWNER,)
    else:
        status, stuck = run(chase, prove or solver, old, log)
    family, owners = r28.family_state(chase)
    switched = family < CHECKPOINT_BOUND and CHECKPOINT_OWNER not in owners
    if status == STOPPED and switched and stuck:
        status = SUCCESS_B
    sequence = chase.sequence[CHECKPOINT_SEQUENCE_LENGTH - 1 :]
    resumed = monotonic() - started
    within = resumed <= cap and prior + resumed <= PROOF_WALL_SECONDS
    if not within:
        status = STOPPED
    return {
        **result_header(status),
        "START_COMPLETE_LEDGER_SHA256": segment1["START_COMPLETE_LEDGER_SHA256"],
        "PHASE1_PLATEAU_FREEZE": segment1["PHASE1_PLATEAU_FREEZE"],
        "PLATEAU_PROFILE_COUNT": segment1["PLATEAU_PROFILE_COUNT"],
        "PHASE2_CLASS_CERTIFICATE": segment1["PHASE2_CLASS_CERTIFICATE"],
        "RESUME_CHECKPOINT": {
            "CHECKPOINT_REPLAY_STATUS": "PASS",
            "SEGMENT1_RESULT_SHA256": SEGMENT1_SHA256,
            "SEGMENT1_TASK_STATUS": segment1["TASK_STATUS"],
            "SEGMENT1_ATTEMPTS_SHA256": SEGMENT1_ATTEMPTS_SHA256,
            "SEGMENT1_STEPS_SHA256": SEGMENT1_STEPS_SHA256,
            "SEGMENT1_PROOF_LOG_SHA256": SEGMENT1_LOG_SHA256,
            "SEGMENT1_CHECKPOINT_SHA256": SEGMENT1_CHECKPOINT_SHA256,
            "RESUME_CHECKPOINT_BOUND": CHECKPOINT_BOUND,
            "CHECKPOINT_OWNER": profile_id(CHECKPOINT_OWNER),
            "CHECKPOINT_NEXT_COMPETING_BOUND": CHECKPOINT_NEXT_COMPETITOR,
            "CHECKPOINT_COMPLETE_LEDGER_SHA256": CHECKPOINT_LEDGER_SHA256,
            "CHECKPOINT_LEDGER_COUNT": CHECKPOINT_LEDGER_COUNT,
            "CHECKPOINT_ATTEMPT_COUNT": CHECKPOINT_ATTEMPTS,
            "CHECKPOINT_STEP_COUNT": CHECKPOINT_STEPS,
            "CHECKPOINT_TRIGGER_ATTEMPT_INDEX": CHECKPOINT_TRIGGER,
            "SOLVES_DURING_REPLAY": 0,
            "REPLAY_WALL_SECONDS": replay_seconds,
        },
        "ROUTE4_STATUS": route4_status,
        "FINAL_OWNER_SWITCHED_FROM_CHECKPOINT": switched,
        "ROUTE4_CERTIFICATE": route4,
        "ROUTE4_SCOPE": "EXACT_DEGREE_PROFILE_ALL_REALIZATIONS_AT_OR_BELOW_CERTIFIED_CAP",
        "MOTIF_CERTIFICATE_STATUS": "NOT_CERTIFIED" if route4 is None else "PASS",
        "S4_CERTIFICATE_STATUS": "NOT_CERTIFIED" if route4 is None else "PASS",
        "SOUNDNESS_WITNESS_STATUS": witness["STATUS"],
        "SOUNDNESS_WITNESS": witness,
        "METHOD_CAPABILITY": method_capability(witness),
        **chase_fields(chase, stuck, old, checks, PROOF_WALL_SECONDS),
        "NEW_PROFILES_PROCESSED": len(new_profiles(chase)),
        "NEW_PROFILES_PROCESSED_SCOPE": "DISTINCT_PROFILES_THE_RESUMED_SEGMENT_STRENGTHENED",
        "RESUME_OWNER_TRANSITION_COUNT": len(sequence) - 1,
        "RESUME_OWNER_CLASS_SEQUENCE": sequence,
        "RESUME_FAMILY_DROP": CHECKPOINT_BOUND - family,
        "NEXT_BLOCKER_OWNER_IDS": list(map(profile_id, stuck)) if status == SUCCESS_B else [],
        "DURABLE_STATE": {
            "PROOF_LOG": f"{DURABLE_DIRECTORY}/{PROOF_LOG}",
            "LEDGER_CHECKPOINT": f"{DURABLE_DIRECTORY}/{CHECKPOINT}",
            "SEGMENT1_RESULT": f"{DURABLE_DIRECTORY}/{SEGMENT1_RESULT}",
            "SEGMENT1_CHECKPOINT": f"{DURABLE_DIRECTORY}/{SEGMENT1_CHECKPOINT}",
            "RESUMED": True,
            "RESUME_MODE": "SEALED_FIRST_SEGMENT_STEP_REPLAY",
            "REPLAYED_PROOFS_SERVED": 0,
        },
        "PROOF_STARTED_UNIX_TIME": segment1["PROOF_STARTED_UNIX_TIME"],
        "RESUME_STARTED_UNIX_TIME": epoch,
        "ORIGINAL_PROOF_BUDGET": PROOF_WALL_SECONDS,
        "SEGMENT1_SEALED_WALL_SECONDS": sealed,
        "PRIOR_SEGMENT_WALL_TIME": prior,
        "PRIOR_SEGMENT_ACCOUNTING": "SEALED_ELAPSED_ROUNDED_UP_TO_THE_MILLISECOND",
        "SEGMENT2_CAP_SECONDS": cap,
        "RESUME_SEGMENT_BUDGET": budget,
        "FINALIZE_RESERVE_SECONDS": FINALIZE_RESERVE_SECONDS,
        "RESUME_SEGMENT_WALL_TIME": resumed,
        "TOTAL_PROOF_WALL_TIME": prior + resumed,
        "TOTAL_BUDGET_CHECK": "PASS" if within else "FAIL",
        "PROOF_ACTUAL_WALL_SECONDS": prior + resumed,
        **RESULT_TRAILER,
    }


SUMMARY_KEYS = (
    "TASK_STATUS",
    "FAMILY_UPPER_BOUND",
    "FINAL_BOUND_OWNER_TYPE",
    "NEXT_ACTIVE_PROFILE",
    "PROOF_ACTUAL_WALL_SECONDS",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-wall-seconds", type=float, default=PROOF_WALL_SECONDS)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--resume-checkpoint", action="store_true")
    args = parser.parse_args()
    target = r28.repo_root() / RESULT_DIRECTORY / RESULT_FILENAME
    durable = r28.repo_root() / DURABLE_DIRECTORY
    if args.resume_checkpoint:
        preserve_segment1(target, durable)
        result = resume_result(segment1_authority(durable), None, durable)
    else:
        if target.exists():
            raise AssertionError("only a new exact R30 result output is authorized")
        durable.mkdir(parents=True, exist_ok=True)
        if (durable / PROOF_LOG).exists() and not args.resume:
            raise AssertionError("a durable R30 proof log exists; pass --resume explicitly")
        result = compute_result(None, args.proof_wall_seconds, durable, args.resume)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    print(json.dumps({k: result[k] for k in SUMMARY_KEYS}), flush=True)


if __name__ == "__main__":
    main()
