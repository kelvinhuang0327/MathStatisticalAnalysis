"""Split-cap chase of the current minimum-S2 family owners, succeeding e44a635f.

Authority. e44a635f proved the zero/core split identity t(G)=F-P with P>=0 for every
admissible profile with a nonempty zero part, so the maximum of F over its finite
necessary degree relaxation is a triangle cap (branch A). Its conditional P>=12+r floor
(branch B) needs d=(6^4,5^8,1^2,0^6) and sigma_A=sigma_B=5, and is not used here. Its
result is pinned by tree and SHA-256, every loaded research module is pinned byte-for-byte
to that commit, and its 4,316-configuration exploration is not rerun: the twelve top-W
bounds enter verbatim after their stored Route-B terms are re-evaluated.

Ledger. The coverage chain's zero-solve replay rebuilds the digest-pinned 4,635-row
W=786..834 ledger with each row's cap authority (source row, triangle cap, S4 base). With
the twelve top-W rows that makes 4,647 resolved rows. The 197 profiles under the W<=785
cursor keep its coarse bound and the 282 excluded histograms stay excluded. Each ledger
part is matched to the inherited partition by count and id digest, so all 4,844 admissible
profiles stay covered without re-enumerating the universe.

Refining one resolved profile. The structural screens must pass. The row's Route-B
envelope at its recorded cap and S4 base must reproduce its ledger bound exactly, which
recovers the existing authority. The split relaxation is then evaluated, and any profile
that would enter the conditional branch is refused. Both caps are valid, so the new cap is
their minimum. Route B is re-evaluated at every integer t in 22..cap, in integers and in
exact rationals, and the new bound is adopted only if it is strictly smaller. A recorded
realization of the profile must satisfy the split identity and lie under the new cap.

Chase. Recompute the complete family maximum over all 4,647 rows and the cursor. If the
cursor owns it, stop: refining the frontier would be a new class census. Otherwise refine
every tied owner and install each strict improvement. The family drops only when the
whole owner group drops. The chase stops at the first owner the split cap cannot tighten,
after 128 refinements or after 30 CPU minutes. No solver, portfolio search or outcome
enumeration is run.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from math import comb
from pathlib import Path
from time import monotonic, process_time

from . import b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 as r20
from . import b649_k20_min_s2_topw12_split_cap_certificate_r1 as split
from .b649_k20_min_s2_realizable_core_class_bound_r4 import overlap_wedge_count
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import decode_profile, profile_id

prior = split.prior
TASK_ID = "B649_K20_MIN_S2_SPLIT_CAP_CURRENT_OWNER_CHASE_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-split-cap-current-owner-chase-r1"
BASE_HEAD = "e44a635f1932166734aaa3f64f9469c0e63c7520"
BASE_TREE = "8d1b5d168157e8cea47ac44f9ca7537ace053c31"
BASE_RESULT_SHA256 = "e6bab2ae892cfccd5dcea97781e99ad1a664029e55a80c374e3441a586ba5f9d"
START_FAMILY_UB = 313_404_784
START_OWNER_IDS = ["66665555554440000000", "66655555555530000000"]
INCUMBENT = 313_263_888
ADMISSIBLE_COUNT = 4_844
RESOLVED_COUNT = 4_647
MAX_REFINED = 128
CPU_SECONDS = 1800.0
BRANCH_A = "A_NONNEGATIVE_P"
TIGHTENED = "TIGHTENED"
NOT_TIGHTENED = "NOT_TIGHTENED"
STOP_CURSOR = "CURSOR_OWNS_FAMILY_UNRESOLVED_CLASS"
STOP_ALREADY_SPLIT = "OWNER_ALREADY_SPLIT_CERTIFIED"
STOP_UNTIGHTENABLE = "OWNER_NOT_TIGHTENABLE_BY_SPLIT_CAP"
STOP_BUDGET = "REFINEMENT_BUDGET_EXHAUSTED"
STOP_CPU = "CPU_BUDGET_EXHAUSTED"
RESULT_FILENAME = "b649-k20-min-s2-split-cap-current-owner-chase-r1-result.json"
ROOT = split.ROOT
RESULT_PATH = ROOT / prior.RESULT_DIRECTORY / RESULT_FILENAME
TOP_SOURCE = split.RESULT_FILENAME
Supports = tuple[split.Support, ...]
Realization = tuple[Supports, Supports]
integer = split.integer
object_row = split.object_row
rows = split.rows
text = split.text


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


@dataclass(frozen=True)
class Row:
    """One resolved family term and the cap authority that produced it."""

    bound: int
    cap: int
    s4_base: int
    source: str
    realization: Realization | None = None


@dataclass(frozen=True)
class Authority:
    base: dict[str, object]
    ledger: dict[str, Row]
    members: dict[str, frozenset[prior.DegreeProfile]]
    coverage: dict[str, object]
    top: dict[str, object]
    provenance: dict[str, str]


def pinned_authority() -> dict[str, object]:
    """The e44a635f result at its exact tree and digest, with its family state."""

    if git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("base tree mismatch")
    blob = git("show", f"{BASE_HEAD}:{prior.RESULT_DIRECTORY}/{split.RESULT_FILENAME}")
    if hashlib.sha256(blob).hexdigest() != BASE_RESULT_SHA256:
        raise AssertionError("split-cap authority digest mismatch")
    base = object_row(json.loads(blob))
    expected: dict[str, object] = {
        "TASK_ID": split.TASK_ID,
        "FINAL_COMPLETE_FAMILY_UB": START_FAMILY_UB,
        "FINAL_BOUND_OWNER_IDS": START_OWNER_IDS,
        "PROFILE_COVERAGE_COUNT": ADMISSIBLE_COUNT,
        "UNCOVERED_PROFILE_COUNT": 0,
        "FINAL_LEDGER_COUNT": RESOLVED_COUNT,
        "INHERITED_LEDGER_SHA256": prior.LEDGER_SHA256,
        "CURRENT_INCUMBENT": INCUMBENT,
    }
    for key, value in expected.items():
        if base.get(key) != value:
            raise AssertionError(f"split-cap authority mismatch: {key}")
    return base


def module_provenance() -> dict[str, str]:
    """Every reused module equals its blob at the base, byte for byte."""

    out: dict[str, str] = {}
    for module in (split, prior, r20, *prior.PROVENANCE_MODULES):
        if module.__file__ is None:
            raise AssertionError("reused module has no source")
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(ROOT):
            raise AssertionError(f"reused module loaded outside this tree: {path}")
        relative = path.relative_to(ROOT).as_posix()
        committed = git("show", f"{BASE_HEAD}:{relative}")
        if path.read_bytes() != committed:
            raise AssertionError(f"reused source changed: {relative}")
        out[relative] = hashlib.sha256(committed).hexdigest()
    return out


def supports(raw: object) -> Supports:
    return tuple(tuple(map(int, part.split(","))) for part in text(raw).split(";"))


def recorded_realization(witness: Mapping[str, object] | None) -> Realization | None:
    if witness is None or "WITNESS_TRIPLES" not in witness:
        return None
    return supports(witness["WITNESS_TRIPLES"]), supports(witness["WITNESS_DOUBLE_SUPPORTS"])


def top_rows(base: Mapping[str, object]) -> tuple[dict[str, Row], dict[str, object]]:
    """The twelve e44a635f rows, each stored envelope re-evaluated and left unchanged."""

    out: dict[str, Row] = {}
    for index, raw in enumerate(rows(base["TOP_W_CERTIFICATES"])):
        cert = object_row(raw)
        pid = text(cert["PROFILE_ID"])
        cap, s4, bound = (integer(cert[k]) for k in ("TRIANGLE_CAP", "S4_BASE", "ALL_T_MAX_BOUND"))
        terms = split.route_b_terms(split.profile_values(pid), cap, s4)
        if (
            cert.get("STATUS") != "PASS"
            or [list(term) for term in terms] != rows(cert["ALL_T_TERMS"])
            or max(term[1] for term in terms) != bound
            or pid in out
        ):
            raise AssertionError(f"top-W certificate changed: {pid}")
        out[pid] = Row(bound, cap, s4, f"{TOP_SOURCE}:TOP_W_CERTIFICATES[{index}]")
    top_max = max(row.bound for row in out.values())
    if len(out) != 12 or top_max != base["TOPW12_MAX"]:
        raise AssertionError("top-W result changed")
    caps = {pid: row.cap for pid, row in out.items()}
    return out, {"STATUS": "UNCHANGED", "COUNT": len(out), "TOPW12_MAX": top_max, "CAPS": caps}


def resolved_ledger(
    chase: prior.Chase, base: Mapping[str, object]
) -> tuple[dict[str, Row], dict[str, frozenset[prior.DegreeProfile]], dict[str, object]]:
    """Replayed ledger rows plus the twelve, checked part by part against the partition."""

    parts: dict[str, set[prior.DegreeProfile]] = {name: set() for name in prior.LEDGER_PARTS}
    ledger: dict[str, Row] = {}
    for profile, bound in chase.bounds.items():
        c = chase.catalog[profile]
        if c.bound != bound or c.triangle_cap is None or c.s4 is None:
            raise AssertionError("ledger row has no cap authority")
        homes = [
            name
            for name, (_count, low, high, sources) in prior.LEDGER_PARTS.items()
            if low <= overlap_wedge_count(profile) <= high and c.source_result in sources
        ]
        if len(homes) != 1:
            raise AssertionError(f"ledger row {profile_id(profile)} has no unique part")
        parts[homes[0]].add(profile)
        source = f"{c.source_result}:{c.source_row}"
        realization = recorded_realization(c.witness_row)
        ledger[profile_id(profile)] = Row(bound, c.triangle_cap, c.s4, source, realization)
    top, audit = top_rows(base)
    if set(top) & set(ledger):
        raise AssertionError("top-W rows collide with the ledger")
    ledger |= top
    members = {name: frozenset(p) for name, p in parts.items()}
    members[prior.PART_TOP] = frozenset(map(decode_profile, top))
    return ledger, members, audit


def coverage(
    ledger: Mapping[str, Row],
    members: Mapping[str, frozenset[prior.DegreeProfile]],
    base: Mapping[str, object],
) -> dict[str, object]:
    """Resolved parts equal the inherited partition; the cursor covers the frontier."""

    inherited = object_row(base["INHERITED_PARTITION"])
    if set(inherited) != set(prior.PART_ORDER):
        raise AssertionError("inherited partition names changed")
    for name, part in members.items():
        row = object_row(inherited[name])
        if integer(row["COUNT"]) != len(part) or row["IDS_SHA256"] != prior.ids_digest(part):
            raise AssertionError(f"resolved part {name} differs from the inherited partition")
    frontier = object_row(inherited[prior.PART_FRONTIER])
    low, high = (integer(v) for v in rows(frontier["W_RANGE"]))
    if prior.CURSOR_ID in ledger or not low <= prior.CURSOR_W <= high:
        raise AssertionError("cursor is not the unresolved frontier representative")
    resolved = sum(map(len, members.values()))
    covered = resolved + integer(frontier["COUNT"])
    excluded = integer(object_row(inherited[prior.PART_EXCLUDED])["COUNT"])
    if (
        resolved != len(ledger)
        or resolved != RESOLVED_COUNT
        or covered != ADMISSIBLE_COUNT
        or covered + excluded != prior.RAW_COUNT
        or base["UNCOVERED_PROFILE_COUNT"] != 0
    ):
        raise AssertionError("complete admissible coverage changed")
    return {
        "STATUS": "COMPLETE",
        "ADMISSIBLE_PROFILE_COUNT": covered,
        "RESOLVED_ROW_COUNT": resolved,
        "UNDER_CURSOR_PROFILE_COUNT": covered - resolved,
        "EXCLUDED_HISTOGRAM_COUNT": excluded,
        "RAW_HISTOGRAM_COUNT": covered + excluded,
        "UNCOVERED_PROFILE_COUNT": 0,
        "PART_COUNTS": {name: len(part) for name, part in sorted(members.items())},
    }


def load_authority() -> Authority:
    """Pin e44a635f, replay the digest-pinned ledger and attach its cap authorities."""

    base = pinned_authority()
    provenance = module_provenance()
    chase, _authorities, _sealed = prior.start_chase(monotonic() + CPU_SECONDS)
    ledger, members, top = resolved_ledger(chase, base)
    return Authority(base, ledger, members, coverage(ledger, members, base), top, provenance)


def degree_data(profile: split.Profile) -> dict[str, object]:
    """Exact structural degree data of G (shadow plus pairs) and its complement H."""

    g = [6 + d for d in profile]
    h = [13 - d for d in profile]
    if sum(g) != 2 * 93 or sum(h) != 2 * 97 or sum(profile) != 66:
        raise AssertionError("shadow-plus-pair degree identity failed")
    return {
        "TRIPLE_DEGREES": list(profile),
        "DEGREE_COUNTS": {str(d): n for d, n in sorted(Counter(profile).items(), reverse=True)},
        "CORE_COUNT": 20 - profile.count(0),
        "ZERO_COUNT": profile.count(0),
        "G_DEGREES": g,
        "H_DEGREES": h,
        "PHI": sum(comb(v, 2) for v in h) - 606,
    }


def refine(pid: str, row: Row) -> dict[str, object]:
    """General-branch split certificate of one resolved row; adopt only a stronger bound."""

    p = split.profile_values(pid)
    if profile_id(p) != pid:
        raise ValueError("profile id is not canonical")
    if prior.first_failure(prior.screen_results(p)) is not None or prior.w8.admissibility_screen(p):
        raise AssertionError("profile fails a structural screen")
    previous = split.route_b_terms(p, row.cap, row.s4_base)
    if max(term[1] for term in previous) != row.bound:
        raise AssertionError("existing cap authority does not reproduce the ledger bound")
    cert = split.split_certificate(p)
    count = integer(cert["DEGREE_CONFIGURATION_COUNT"])
    if pid == split.SPECIAL or cert["BRANCH_COUNTS"] != {BRANCH_A: count}:
        raise AssertionError("conditional P12 branch is outside its premises here")
    split_cap = integer(cert["TRIANGLE_CAP"])
    cap = min(row.cap, split_cap)
    terms = split.route_b_terms(p, cap, row.s4_base)
    if terms != previous[: len(terms)]:
        raise AssertionError("tightened envelope is not the existing all-t formula")
    best = max(terms, key=lambda term: (term[1], term[0]))
    status = TIGHTENED if best[1] < row.bound else NOT_TIGHTENED
    realization: dict[str, object] | None = None
    if row.realization is not None:
        seen = split.analyze_realization(*row.realization)
        if seen["PROFILE_ID"] != pid or integer(seen["TRIANGLES"]) > cap:
            raise AssertionError("recorded realization exceeds the split cap")
        realization = {k: seen[k] for k in ("TRIANGLES", "F", "P_TERMS", "BRANCH")}
    return {
        "PROFILE_ID": pid,
        "W": overlap_wedge_count(p),
        "DEGREE_DATA": degree_data(p),
        "EXISTING_AUTHORITY": row.source,
        "EXISTING_TRIANGLE_CAP": row.cap,
        "EXISTING_BOUND": row.bound,
        "SPLIT_DEGREE_CONFIGURATION_COUNT": count,
        "SPLIT_TRIANGLE_CAP": split_cap,
        "SPLIT_BRANCH_COUNTS": cert["BRANCH_COUNTS"],
        "SPLIT_MAXIMIZER": cert["MAXIMIZER"],
        "TRIANGLE_CAP": cap,
        "S4_BASE": row.s4_base,
        "ALL_T_TERMS": [list(term) for term in terms],
        "TERM_COUNT": len(terms),
        "ARGMAX_TRIANGLES": best[0],
        "ALL_T_MAX_BOUND": best[1],
        "ALL_T_STATUS": "PASS_INTEGER_AND_RATIONAL",
        "PREMISES": {
            "STRUCTURAL_SCREENS": "PASS",
            "TWENTY_DEGREES_SUM_66_NONEMPTY_ZERO_PART": "PASS",
            "EXISTING_CAP_REPRODUCES_LEDGER_BOUND": "PASS",
            "NECESSARY_CONFIGURATIONS_NONEMPTY": "PASS",
            "GENERAL_BRANCH_P_NONNEGATIVE_ONLY": "PASS",
            "CONDITIONAL_P12_INVOKED": "NO",
            "RECORDED_REALIZATION_UNDER_CAP": "NONE_RECORDED" if realization is None else "PASS",
        },
        "RECORDED_REALIZATION": realization,
        "STATUS": status,
    }


def family_state(ledger: Mapping[str, Row]) -> tuple[int, list[str]]:
    terms = {pid: row.bound for pid, row in ledger.items()}
    return prior.family_owners(terms, prior.CURSOR_ID, prior.CURSOR_BOUND)


@dataclass(frozen=True)
class Outcome:
    ledger: dict[str, Row]
    certificates: list[dict[str, object]]
    transitions: list[dict[str, object]]
    stop: dict[str, object]


def chase(start: Mapping[str, Row], cpu_deadline: float) -> Outcome:
    """Refine load-bearing owner groups until one cannot be tightened or a budget ends."""

    ledger = dict(start)
    certificates: list[dict[str, object]] = []
    transitions: list[dict[str, object]] = []
    stop: dict[str, object] = {}
    while True:
        family, owners = family_state(ledger)
        if prior.CURSOR_ID in owners:
            reason = STOP_CURSOR
        elif any(ledger[o].source.startswith(TOP_SOURCE) for o in owners):
            reason = STOP_ALREADY_SPLIT
        elif len(certificates) + len(owners) > MAX_REFINED:
            reason = STOP_BUDGET
        elif process_time() > cpu_deadline:
            reason = STOP_CPU
        else:
            group = [refine(o, ledger[o]) for o in owners]
            for cert in group:
                if cert["STATUS"] == TIGHTENED:
                    old = ledger[text(cert["PROFILE_ID"])]
                    locator = f"{RESULT_FILENAME}:CERTIFICATES[{len(certificates)}]"
                    bound, cap = integer(cert["ALL_T_MAX_BOUND"]), integer(cert["TRIANGLE_CAP"])
                    ledger[text(cert["PROFILE_ID"])] = replace(
                        old, bound=bound, cap=cap, source=locator
                    )
                certificates.append(cert)
            after, after_owners = family_state(ledger)
            blocked = [text(c["PROFILE_ID"]) for c in group if c["STATUS"] != TIGHTENED]
            if blocked and after != family:
                raise AssertionError("partial owner-group refinement changed the family")
            if not blocked and after >= family:
                raise AssertionError("complete owner-group refinement did not lower the family")
            transitions.append(
                {
                    "FAMILY_BEFORE": family,
                    "OWNER_IDS": owners,
                    "OWNER_BOUNDS_AFTER": {
                        text(c["PROFILE_ID"]): c["ALL_T_MAX_BOUND"] for c in group
                    },
                    "OWNER_GROUP_COMPLETE": not blocked,
                    "FAMILY_AFTER": after,
                    "OWNER_IDS_AFTER": after_owners,
                }
            )
            if not blocked:
                continue
            family, owners, reason = after, after_owners, STOP_UNTIGHTENABLE
            stop["BLOCKING_OWNER_IDS"] = blocked
        stop |= {"REASON": reason, "FAMILY": family, "OWNER_IDS": owners}
        return Outcome(ledger, certificates, transitions, stop)


def final_family(ledger: Mapping[str, Row], outcome: Outcome) -> dict[str, object]:
    """Complete maximum over every resolved row and the cursor, by an independent sort."""

    ranked = sorted(((row.bound, pid) for pid, row in ledger.items()), reverse=True)
    terms = [*ranked, (prior.CURSOR_BOUND, prior.CURSOR_ID)]
    family = max(bound for bound, _pid in terms)
    owners = sorted((pid for bound, pid in terms if bound == family), reverse=True)
    reused, reused_owners = family_state(ledger)
    if (
        len(ledger) != RESOLVED_COUNT
        or (family, sorted(reused_owners, reverse=True)) != (reused, owners)
        or (family, reused_owners) != (outcome.stop["FAMILY"], outcome.stop["OWNER_IDS"])
    ):
        raise AssertionError("complete family recomputation disagrees")
    if not INCUMBENT <= family <= START_FAMILY_UB:
        raise AssertionError("family bound left the [incumbent, start] interval")
    serialized = [{"PROFILE_ID": pid, "CURRENT_BOUND": ledger[pid].bound} for pid in sorted(ledger)]
    return {
        "FINAL_COMPLETE_FAMILY_UB": family,
        "FINAL_OWNER_IDS": reused_owners,
        "NEXT_COMPETING_BOUND": max(bound for bound, pid in terms if pid not in owners),
        "FINAL_RESOLVED_ROW_COUNT": len(ledger),
        "FINAL_RESOLVED_ROWS_SHA256": hashlib.sha256(
            json.dumps(serialized, sort_keys=True).encode()
        ).hexdigest(),
        "CURRENT_INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family - INCUMBENT,
    }


def witness_soundness(ledger: Mapping[str, Row]) -> dict[str, object]:
    """P=2 counterexample stays legal; the STS(13) T=270 profile keeps a cap >= 270."""

    p2 = split.analyze_realization(*split.witness_supports("P2"))
    if (p2["TRIANGLES"], p2["P_TOTAL"], p2["BRANCH"]) != (250, 2, BRANCH_A):
        raise AssertionError("legal P=2 configuration is not accepted in the general branch")
    sts = split.analyze_realization(*split.witness_supports("STS13"))
    sts_id, sts_t = text(sts["PROFILE_ID"]), integer(sts["TRIANGLES"])
    sts_split = integer(split.split_certificate(sts_id)["TRIANGLE_CAP"])
    if sts_t != 270 or min(ledger[sts_id].cap, sts_split) < sts_t:
        raise AssertionError("STS13 witness is excluded")
    return {
        "STATUS": "PASS",
        "P2_COUNTEREXAMPLE": {k: p2[k] for k in ("PROFILE_ID", "TRIANGLES", "P_TOTAL", "BRANCH")},
        "STS13_WITNESS": {
            "PROFILE_ID": sts_id,
            "TRIANGLES": sts_t,
            "LEDGER_TRIANGLE_CAP": ledger[sts_id].cap,
            "SPLIT_TRIANGLE_CAP": sts_split,
            "LEDGER_BOUND": ledger[sts_id].bound,
        },
    }


def compute_result(authority: Authority | None = None) -> dict[str, object]:
    cpu_deadline = process_time() + CPU_SECONDS
    auth = load_authority() if authority is None else authority
    start, start_owners = family_state(auth.ledger)
    if (start, start_owners) != (START_FAMILY_UB, START_OWNER_IDS):
        raise AssertionError("starting family state differs from e44a635f")
    outcome = chase(auth.ledger, cpu_deadline)
    family = final_family(outcome.ledger, outcome)
    certs = {text(c["PROFILE_ID"]): c for c in outcome.certificates}
    tightened = [pid for pid, c in certs.items() if c["STATUS"] == TIGHTENED]
    if len(certs) != len(outcome.certificates):
        raise AssertionError("a profile was refined twice")
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "REMAINING_TASK_MODEL": "最強模型",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT": split.RESULT_FILENAME,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "PROOF": __doc__,
        "MODULE_PROVENANCE": auth.provenance,
        "START_FAMILY_BOUND": start,
        "START_OWNER_IDS": start_owners,
        "START_OWNERS_CERTIFIED": all(certs[o]["STATUS"] == TIGHTENED for o in start_owners),
        "START_OWNER_NEW_CAPS": {o: certs[o]["TRIANGLE_CAP"] for o in start_owners},
        "START_OWNER_NEW_BOUNDS": {o: certs[o]["ALL_T_MAX_BOUND"] for o in start_owners},
        "ADDITIONAL_PROFILES_CERTIFIED": len([p for p in tightened if p not in start_owners]),
        "ADDITIONAL_PROFILE_IDS": [p for p in tightened if p not in start_owners],
        "PROFILES_EVALUATED": len(certs),
        "OWNER_TRANSITIONS": outcome.transitions,
        "STOP": outcome.stop,
        "CERTIFICATES": outcome.certificates,
        "SPLIT_CAP_PREMISES_STATUS": "PASS_EVERY_EVALUATED_PROFILE_GENERAL_BRANCH_ONLY",
        "P2_COUNTEREXAMPLE_STATUS": "ACCEPTED_T250_P2_GENERAL_BRANCH",
        "CONDITIONAL_BRANCH_STATUS": "NOT_INVOKED_NO_EVALUATED_PROFILE_MEETS_B_PREMISES",
        "UNCONDITIONAL_P12_ASSERTED": False,
        "TOP_W12": auth.top,
        "COVERAGE": auth.coverage,
        "UNIVERSE_COVERAGE_STATUS": "COMPLETE_4844_INHERITED_PARTITION_DIGESTS_MATCH",
        "ALL_T_STATUS": "PASS_INTEGER_AND_RATIONAL_EVERY_T",
        "ALL_T_INTEGER_TERMS_CHECKED": sum(integer(c["TERM_COUNT"]) for c in outcome.certificates),
        "WITNESS_SOUNDNESS": witness_soundness(outcome.ledger),
        "WITNESS_SOUNDNESS_STATUS": "PASS",
        **family,
        "MAX_REFINED": MAX_REFINED,
        "CPU_SECONDS_LIMIT": CPU_SECONDS,
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def render(result: Mapping[str, object]) -> str:
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def main() -> None:
    result = compute_result()
    RESULT_PATH.write_text(render(result), encoding="utf-8")
    keys = ("START_OWNER_NEW_BOUNDS", "ADDITIONAL_PROFILES_CERTIFIED", "STOP")
    summary = {k: result[k] for k in (*keys, "FINAL_COMPLETE_FAMILY_UB", "REMAINING_GAP")}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
