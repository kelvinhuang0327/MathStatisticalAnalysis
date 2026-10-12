"""Combine two existing profile certificates in the frozen 2f709256 min-S2 ledger.

This is an authority integration, not a new proof or search. Git objects bind each
certificate's source, proof text, result and archived inputs. The zero-solve replay
recovers all 4,647 resolved rows; only recorded baseline refinements are replayed.
Two profile-specific bounds are then installed in a copy. Certificate B retains
its cap 270 and VERIFIED_WITH_CAVEATS status: its all-T closure is a union-count
bound, not a triangle cap of 255. All other full rows and the unresolved cursor's
197-profile partition remain unchanged. The family maximum includes the cursor.

The five STS(13) representatives and the upstream certificate searches are not
rebuilt. A and B remain the scientific proof authorities. Global K20 optimality
is unknown. Reproduction requires the pinned local Git objects and frozen data.
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32
from . import b649_k20_min_s2_split_cap_current_owner_chase_r1 as chase

TASK_ID = "B649_MIN_S2_TWO_CERTIFIED_ROW_COMBINED_AUTHORITY_R1"
BASE_HEAD = "2f70925698cb28758fdf29a62bc5e91028c03a81"
BASE_TREE = "216bd91dee0afa58f8186a38aec52b1d47781ef8"
BASE_RESULT_SHA256 = "2269cc5e5e3bf08650fa711a240e7d088814e1bcd35d0cb9efcb01a91a2d67f3"
LEDGER_DIGEST = "2cf91665b86167e917f47779fdee3cb23b07b1d1b3d2491eae8b3ab42d9307a8"
LEDGER_ROWS = 4_647
FAMILY_BEFORE = 313_404_008
INCUMBENT = 313_263_888
A_PROFILE = "66666555555311100000"
B_PROFILE = "55555555555511111100"
B_WORKER_CAVEATS = (
    "If an original source file's bytes later change, the two local-origin tests are skipped "
    "instead of failing. The certificate itself still fails closed.",
    "My note that the A Agent's Y/L cap-246 worktree had no changes is now stale: it has since "
    "staged three files. My result still records that work as not applied.",
    "One of the three caps I combine is the ledger row's own cap, so that input is circular. "
    "It's harmless, because the R18 cap alone gives 270.",
)
RESULT_DIRECTORY = chase.prior.RESULT_DIRECTORY
RESULT_STEM = "b649-min-s2-two-certified-row-combined-authority-r1"
ROOT = chase.ROOT
integer, object_row, rows, text = chase.integer, chase.object_row, chase.rows, chase.text


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Pin:
    head: str
    tree: str
    module: str
    source_sha256: str
    result_sha256: str
    profile: str
    judge_status: str

    @property
    def result_path(self) -> str:
        return f"{RESULT_DIRECTORY}/{self.module.replace('_', '-')}-result.json"


A = Pin(
    "7683a4853929b32506a1343f8659427abb4f1ecc",
    "39b1de3977495fdfee7cd64eb8cdeb0f1a2123e0",
    "b649_min_s2_top_owner_yl_cap246_formal_cert_r1",
    "08eed128c2fea7e7e2aac6a2fcbf05d16d991c407300d2857b4459e8c09e4634",
    "8be4bb4711f016a2fc0af24fd879f1a67cc7080d178692adbed28b1cd2cf991c",
    A_PROFILE,
    "VERIFIED",
)
B = Pin(
    "22747b6ebab1c1ded8773d39edf9e5a44eb70769",
    "af0c469501fce7b6002b92065ad2c236845edab1",
    "b649_min_s2_incumbent_profile_all_triangle_closure_r1",
    "3ea80f145689e5b6239593e1c44eb75b40ef83f4f6d00550f1f4c24760f16b67",
    "912642e2acf202b1d6490856ee5df117240b4321dc4b545174bc00eef2723a51",
    B_PROFILE,
    "VERIFIED_WITH_CAVEATS",
)


def blob(head: str, path: str, digest: str) -> bytes:
    raw = chase.git("show", f"{head}:{path}")
    require(sha256(raw) == digest, f"blob digest mismatch: {head}:{path}")
    return raw


def certificate(pin: Pin) -> tuple[dict[str, object], dict[str, object]]:
    require(
        chase.git("rev-parse", f"{pin.head}^{{tree}}").decode().strip() == pin.tree,
        "certificate tree mismatch",
    )
    source_path = f"src/lottolab/research/{pin.module}.py"
    source = blob(pin.head, source_path, pin.source_sha256)
    result = object_row(json.loads(blob(pin.head, pin.result_path, pin.result_sha256)))
    require(
        (result["BASE_HEAD"], result["BASE_TREE"], result["TARGET_PROFILE"])
        == (BASE_HEAD, BASE_TREE, pin.profile),
        "certificate base or target mismatch",
    )
    require(
        ast.get_docstring(ast.parse(source), clean=False) == result["PROOF"], "proof text mismatch"
    )
    manifest = {source_path: pin.source_sha256, pin.result_path: pin.result_sha256}
    if pin == B:
        for raw in rows(result["SOURCES"]):
            archived = object_row(raw)
            for kind in ("RESULT", "SCRIPT"):
                path = archived[f"ARCHIVED_{kind}"]
                if path is not None:
                    name, digest = text(path), text(archived[f"{kind}_SHA256"])
                    blob(pin.head, name, digest)
                    manifest[name] = digest
    return result, {
        "IDENTITY": "PASS",
        "LOCAL_HEAD": pin.head,
        "LOCAL_TREE": pin.tree,
        "TARGET_PROFILE": pin.profile,
        "BLOB_SHA256": manifest,
        "JUDGE_STATUS": pin.judge_status,
        "JUDGE_STATUS_SOURCE": "OWNER_PACKET",
    }


def bounds_digest(ledger: Mapping[str, chase.Row]) -> str:
    serialized = [{"PROFILE_ID": p, "CURRENT_BOUND": ledger[p].bound} for p in sorted(ledger)]
    return sha256(json.dumps(serialized, sort_keys=True).encode())


def full_digest(ledger: Mapping[str, chase.Row]) -> str:
    serialized = {p: asdict(ledger[p]) for p in sorted(ledger)}
    return sha256(json.dumps(serialized, sort_keys=True).encode())


def baseline() -> tuple[dict[str, chase.Row], dict[str, object], dict[str, str]]:
    require(
        chase.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() == BASE_TREE,
        "baseline tree mismatch",
    )
    path = f"{RESULT_DIRECTORY}/{chase.RESULT_FILENAME}"
    result = object_row(json.loads(blob(BASE_HEAD, path, BASE_RESULT_SHA256)))
    auth = chase.load_authority()
    provenance = dict(auth.provenance)
    for module in (chase, r32):
        require(module.__file__ is not None, "reused module has no source")
        source = Path(text(module.__file__)).resolve()
        require(source.is_relative_to(ROOT), "reused module outside this worktree")
        relative = source.relative_to(ROOT).as_posix()
        committed = chase.git("show", f"{BASE_HEAD}:{relative}")
        require(source.read_bytes() == committed, f"reused source changed: {relative}")
        provenance[relative] = sha256(committed)
    ledger = dict(auth.ledger)
    for index, raw in enumerate(rows(result["CERTIFICATES"])):
        cert = object_row(raw)
        if cert["STATUS"] != chase.TIGHTENED:
            continue
        pid = text(cert["PROFILE_ID"])
        old = ledger[pid]
        cap, bound = integer(cert["TRIANGLE_CAP"]), integer(cert["ALL_T_MAX_BOUND"])
        terms = chase.split.route_b_terms(chase.split.profile_values(pid), cap, old.s4_base)
        require(
            cert["EXISTING_BOUND"] == old.bound
            and cert["EXISTING_TRIANGLE_CAP"] == old.cap
            and cert["S4_BASE"] == old.s4_base
            and [list(t) for t in terms] == rows(cert["ALL_T_TERMS"])
            and max(t[1] for t in terms) == bound,
            "recorded baseline refinement mismatch",
        )
        ledger[pid] = replace(
            old, bound=bound, cap=cap, source=f"{chase.RESULT_FILENAME}:CERTIFICATES[{index}]"
        )
    require(
        len(ledger) == result["FINAL_RESOLVED_ROW_COUNT"] == LEDGER_ROWS
        and bounds_digest(ledger) == result["FINAL_RESOLVED_ROWS_SHA256"] == LEDGER_DIGEST
        and chase.family_state(ledger) == (FAMILY_BEFORE, [A_PROFILE])
        and result["FINAL_COMPLETE_FAMILY_UB"] == FAMILY_BEFORE
        and result["CURRENT_INCUMBENT"] == INCUMBENT,
        "frozen ledger mismatch",
    )
    return ledger, result, dict(sorted(provenance.items()))


@dataclass(frozen=True)
class Update:
    profile: str
    bound: int
    cap: int
    source: str


def certified_updates(
    ledger: Mapping[str, chase.Row], a: Mapping[str, object], b: Mapping[str, object]
) -> tuple[Update, Update]:
    require(
        (a["TARGET_PROFILE"], b["TARGET_PROFILE"]) == (A_PROFILE, B_PROFILE),
        "certificate scope mismatch",
    )
    old_a, old_b = ledger[A_PROFILE], ledger[B_PROFILE]
    cap = integer(a["CERTIFIED_T_CAP"])
    route = object_row(a["ROUTE_B"])
    terms = r32.route_b_envelope(chase.split.profile_values(A_PROFILE), cap, old_a.s4_base)
    a_bound = max(t[1] for t in terms)
    require(
        a["THEOREM_STATUS"] == "PROVEN"
        and a["COMPLETE_ENUMERATION"] == "PASS"
        and a["LEDGER_SHA256"] == LEDGER_DIGEST
        and a["PROFILE_BOUND_BEFORE"] == old_a.bound
        and a["PREVIOUS_TRIANGLE_CAP"] == old_a.cap
        and a["PREVIOUS_CAP_AUTHORITY"] == old_a.source
        and route["S4_BASE"] == old_a.s4_base
        and route["TRIANGLE_CAP"] == cap == 246
        and [list(t) for t in terms] == rows(route["ALL_T_TERMS"])
        and a_bound == route["ALL_T_MAX_BOUND"] == a["PROFILE_BOUND_AFTER"]
        and a_bound < old_a.bound,
        "certificate A row binding mismatch",
    )
    partition = object_row(b["PARTITION"])
    next_t = 22
    nonempty_bounds: list[int] = []
    for raw in rows(partition["RANGES"]):
        cell = object_row(raw)
        low, high = integer(cell["T_LOW"]), integer(cell["T_HIGH"])
        require(low == next_t and high >= low, "certificate B partition gap or overlap")
        next_t = high + 1
        if cell["STATUS"] == "EMPTY":
            require(cell["BOUND"] is None, "empty cell carries a bound")
        else:
            require(cell["STATUS"] in ("UPPER_BOUND", "EXACT_MAX"), "unproved partition cell")
            nonempty_bounds.append(integer(cell["BOUND"]))
    b_bound = max(nonempty_bounds)
    binding = object_row(b["LEDGER_SINGLE_PROFILE_UPDATE"])
    require(
        partition["T_DOMAIN"] == [22, 272]
        and next_t == 273
        and partition["DISJOINT_AND_COVERING"] is True
        and b["FULL_PROFILE_NO_STRICT_GAIN"] == "PASS"
        and b_bound == partition["PROFILE_OFFICIAL_MAX_UB"]
        == b["INCUMBENT_PROFILE_OFFICIAL_MAX_UB"] == b["T270_EXACT_MAX"] == INCUMBENT
        and b["CURRENT_ACCEPTED_BEST"] == INCUMBENT
        and binding["ROWS_SHA256_BEFORE"] == LEDGER_DIGEST
        and binding["CHANGED_ROW_IDS"] == [B_PROFILE]
        and binding["PROFILE_ROW_BEFORE"] == old_b.bound
        and old_b.cap == object_row(b["EXISTING_TRIANGLE_CAP"])["LEDGER_ROW_CAP"] == 270
        and old_b.s4_base == object_row(b["R32_ROUTE_B_CAP_255"])["S4_BASE"]
        and b_bound < old_b.bound,
        "certificate B row binding mismatch",
    )
    return (
        Update(A_PROFILE, a_bound, cap, f"{A.head}:{A.result_path}:CERTIFIED_T_CAP"),
        Update(B_PROFILE, b_bound, old_b.cap, f"{B.head}:{B.result_path}:PROFILE_CLOSURE"),
    )


def apply_updates(
    ledger: Mapping[str, chase.Row], updates: Sequence[Update]
) -> dict[str, chase.Row]:
    require(
        len(updates) == 2 and {u.profile for u in updates} == {A_PROFILE, B_PROFILE},
        "exactly two distinct certified profiles required",
    )
    before_digest = full_digest(ledger)
    after = dict(ledger)
    for u in updates:
        require(type(u.bound) is int and type(u.cap) is int, "update must use exact integers")
        old = ledger[u.profile]
        require(u.bound < old.bound and 22 <= u.cap <= old.cap, "update does not tighten")
        after[u.profile] = replace(old, bound=u.bound, cap=u.cap, source=u.source)
    require(
        set(after) == set(ledger)
        and sorted(p for p in ledger if ledger[p] != after[p]) == sorted((A_PROFILE, B_PROFILE))
        and full_digest(ledger) == before_digest,
        "update changed the frozen ledger or another row",
    )
    return after


def family(ledger: Mapping[str, chase.Row]) -> tuple[int, list[str]]:
    terms = [(row.bound, pid) for pid, row in ledger.items()]
    terms.append((chase.prior.CURSOR_BOUND, chase.prior.CURSOR_ID))
    require(all(type(bound) is int for bound, _pid in terms), "non-integer family term")
    best = max(bound for bound, _pid in terms)
    owners = sorted(pid for bound, pid in terms if bound == best)
    reused, reused_owners = chase.family_state(ledger)
    require((best, owners) == (reused, sorted(reused_owners)), "family recomputation differs")
    return best, owners


def compute_result() -> dict[str, object]:
    a, a_identity = certificate(A)
    b, b_identity = certificate(B)
    ledger, base, provenance = baseline()
    updates = certified_updates(ledger, a, b)
    after = apply_updates(ledger, updates)
    before, before_owners = family(ledger)
    best, owners = family(after)
    unchanged_before = {p: r for p, r in ledger.items() if p not in (A_PROFILE, B_PROFILE)}
    unchanged_after = {p: r for p, r in after.items() if p not in (A_PROFILE, B_PROFILE)}
    require(unchanged_before == unchanged_after, "another profile was affected")
    partition = object_row(base["COVERAGE"])
    require(partition["UNDER_CURSOR_PROFILE_COUNT"] == 197, "cursor coverage changed")
    cursor = {
        "PROFILE_ID": chase.prior.CURSOR_ID,
        "BOUND": chase.prior.CURSOR_BOUND,
        "W": chase.prior.CURSOR_W,
        "PARTITION": object_row(base["COVERAGE"]),
        "INHERITED_PARTITION": chase.pinned_authority()["INHERITED_PARTITION"],
    }
    require(
        object_row(b["LEDGER_SINGLE_PROFILE_UPDATE"])["CURSOR"]
        == {"PROFILE_ID": cursor["PROFILE_ID"], "BOUND": cursor["BOUND"]},
        "certificate B cursor differs",
    )
    b_identity["RECORDED_LIMITATIONS"] = {
        "SCOPE": b["SCOPE"],
        "COMMITTED_T270_VERIFIER": b["COMMITTED_T270_VERIFIER"],
        "STS_REPRESENTATIVES_REBUILT": b["STS_REPRESENTATIVES_REBUILT"],
    }
    b_identity["JUDGE_CAVEATS_TEXT"] = list(B_WORKER_CAVEATS)
    b_identity["JUDGE_CAVEATS_SOURCE"] = "OWNER_SUPPLIED_ORIGINAL_WORKER_REPORT"
    actual: dict[str, object] = {
        "FAMILY_BOUND_AFTER": best,
        "EXACT_DELTA": before - best,
        "NEW_FAMILY_OWNER": owners,
        "NEW_GAP_TO_INCUMBENT": best - INCUMBENT,
    }
    expected: dict[str, object] = {
        "FAMILY_BOUND_AFTER": 313_401_852,
        "EXACT_DELTA": 2_156,
        "NEW_FAMILY_OWNER": ["66655555555440000000"],
        "NEW_GAP_TO_INCUMBENT": 137_964,
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMBINED_AUTHORITY_WITH_OWNER_CAVEAT_ADDENDUM",
        "PRIOR_COMBINED_FRESH_JUDGE": {
            "LOCAL_HEAD": "4e2fa8a560d6538c2b05b499f99d639e356c6cfa",
            "LOCAL_TREE": "a452a2a868abce481d3ea02fcfa47ba865981a65",
            "VERDICT": "VERIFIED_WITH_CAVEATS",
            "SCOPE": "COMBINED_AUTHORITY_BEFORE_OWNER_CAVEAT_METADATA_ADDENDUM",
            "ADDENDUM_JUDGE": "NOT_RERUN_PER_OWNER_INSTRUCTION",
        },
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "CERTIFICATE_A_IDENTITY": a_identity,
        "CERTIFICATE_B_IDENTITY": b_identity,
        "BASELINE_LEDGER_DIGEST": "PASS",
        "LEDGER_ROWS": len(ledger),
        "ROWS_CHANGED": len(updates),
        "ROW_UPDATES": [
            {"PROFILE_ID": u.profile, "BEFORE": asdict(ledger[u.profile]),
             "AFTER": asdict(after[u.profile])} for u in updates
        ],
        "FAMILY_BOUND_BEFORE": before,
        "FAMILY_OWNERS_BEFORE": before_owners,
        **actual,
        "EXPECTED_VALUES_MATCH": actual == expected,
        "EXPECTED_VALUE_DIFFERENCES": {
            key: {"EXPECTED": expected[key], "ACTUAL": actual[key]}
            for key in expected if actual[key] != expected[key]
        },
        "CURRENT_ACCEPTED_BEST": INCUMBENT,
        "RESOLVED_ROWS_ABOVE_INCUMBENT": sum(r.bound > INCUMBENT for r in after.values()),
        "RESOLVED_ROWS_ABOVE_INCUMBENT_BEFORE": sum(r.bound > INCUMBENT for r in ledger.values()),
        "BOUNDS_SHA256_BEFORE": bounds_digest(ledger),
        "BOUNDS_SHA256_AFTER": bounds_digest(after),
        "FULL_ROWS_SHA256_BEFORE": full_digest(ledger),
        "FULL_ROWS_SHA256_AFTER": full_digest(after),
        "UNCHANGED_ROWS_COUNT": len(unchanged_before),
        "UNCHANGED_FULL_ROWS_SHA256": full_digest(unchanged_before),
        "OTHER_PROFILES_AFFECTED": [],
        "CURSOR_AUTHORITY": cursor,
        "CURSOR_AUTHORITY_MUTATED": "NO",
        "NEW_OWNER_ROWS": {p: asdict(after[p]) for p in owners if p in after},
        "MODULE_PROVENANCE": provenance,
        "T264_DISPOSITION": "SUPERSEDED_INCOMPLETE",
        "T264_REASON": {"OBSERVED_TARGET_PROFILE": A_PROFILE, "OBSOLETE_TERM_T": 264,
                        "ADOPTED_CERTIFIED_CAP": 246, "MUTATION_SWEEP_RESUMED": False},
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "FROZEN_LEDGER_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SEARCH_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "SOLVER_CALLS": 0,
        "NEXT_ACTION": "END_WITH_COMBINED_AUTHORITY",
    }


def render(result: Mapping[str, object]) -> bytes:
    return (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()


def main() -> None:
    result = compute_result()
    payload = render(result)
    digest = sha256(payload)
    target = ROOT / RESULT_DIRECTORY / f"{RESULT_STEM}-{digest}.json"
    if target.exists():
        require(target.read_bytes() == payload, "content-addressed output collision")
    else:
        with target.open("xb") as output:
            output.write(payload)
    keys = ("FAMILY_BOUND_AFTER", "EXACT_DELTA", "NEW_FAMILY_OWNER",
            "NEW_GAP_TO_INCUMBENT", "RESOLVED_ROWS_ABOVE_INCUMBENT")
    print(json.dumps({**{k: result[k] for k in keys}, "RESULT": str(target), "SHA256": digest}))


if __name__ == "__main__":
    main()
