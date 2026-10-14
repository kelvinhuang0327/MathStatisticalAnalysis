"""A universal, deliberately sufficient T<=262 certificate for three owners.

MODEL. Twenty six-label tickets use 22 triple labels and 27 pair labels;
two tickets share at most one label. A ticket with d triple labels has
6-d pair labels and support degree g=2d+(6-d)=6+d. Thus sum d=66,
sum g=186 and e(G)=93. The 22 triple supports are edge-disjoint triangles,
so 22<=T(G)<=floor(W/3). Derive every histogram, W and Goodman constant
separately; equal W does not imply equal degree-specific constraints.
For these exact profiles W=824, B=1140-sum g(19-g)/2=290, K/Z=15/5.
Each nonhomogeneous three-set contributes two to sum g(19-g), proving
T(G)+T(H)=B, where H is the complement.

SHARED SPLIT. K={d>0}, Z={d=0}; sigma_x=|N_G(x) intersect Z| and
zeta_v=|N_G(v) intersect K|. Every edge to Z uses a pair label, hence
0<=sigma_x<=u_d=min(5,6-d_x). Since each Z vertex has degree six and
only four possible neighbours in Z, 2<=zeta_v<=6. The crossing sums
both equal r. For M=H[K], N=H[Z],
  m_x=8-d_x+sigma_x, n_v=zeta_v-2,
  2e(M)=54+r, 2e(N)=r-10.
For xy in E(M), common H-neighbours in Z number exactly
5-sigma_x-sigma_y+c_Z(xy); for uv in E(N), the corresponding count is
15-zeta_u-zeta_v+c_K(uv). Here c counts common G-neighbours in the
other shore. Classifying H triangles by shore gives
  T(H)=60+10r-sum sigma*m-sum zeta*n+P,
  P=T(M)+T(N)+sum_E(M)c_Z+sum_E(N)c_K.
All four terms of P are nonnegative cardinalities. Dropping P lowers
the H lower bound and raises the G upper bound. No stronger remainder
bound is needed. Induced graphical and bipartite degree inequalities,
r>=10, r even, and equality of crossing sums are necessary; we state
them per profile, but omitting these restrictions enlarges our relaxation.

ANALYTIC ENDPOINT RELAXATION. On 2<=zeta<=6,
  zeta(zeta-2)<=6zeta-12,
because (zeta-2)(zeta-6)<=0. Summing on five Z vertices and using
sum zeta=r yields
  T(G)<=170+sum_x sigma_x(4-d_x+sigma_x).
For 0<=s<=u, the quadratic lies below its endpoint chord:
  s(4-d+s)<=s(4-d+u)<=max(0,u(4-d+u)).
The first difference is s(s-u)<=0; the second follows from s in [0,u]
even when the coefficient is negative. Endpoint contributions for
d=6,5,4,3,2,1 are respectively 0,0,4,12,24,40.
A has 1*12+2*40=92, B has 3*4+2*40=92, C has 1*4+2*24+1*40=92.
Therefore ALL legal realizations of EACH exact profile satisfy T<=262.
The enlarged endpoint relaxation permits incompatible crossing degrees;
its endpoint maxima are not asserted realizable. No support graph or
portfolio enumeration is performed. This sufficient certificate ends the
search at the cursor floor; smaller exploratory caps are not adopted.

FIXED BASE ENVELOPE. Replay the pinned input certificate and its evaluator
source closure. At every true t, o=W-3t is the open-wedge count. A nonedge
in a g-vertex neighbourhood spoils at most g-2 triples; counting unspoiled
neighbourhood triples four times per K4 gives
  q>=max(0,ceil((J-(g_max-2)o)/4)), J=sum C(g,3).
Using g_max weakens this lower bound. Pair-linearity allows at most one
triple support per K4. Counting its outside common neighbours gives
  a<=floor(sum d(g-2)/3)=A_max, and a<=q.
The pinned Base weights 448 and 679 give S4>=679q-231 min(q,A_max);
other S4 contributions are nonnegative. This expression increases in q,
so its lower bound may be substituted. Combine Base floors by MAX.
S4 authority is checked from the fixed Base, and no S5 is adopted here.
S3=2800o+20272(t-22)+154000. At most seven tickets win on seven drawn
labels: their chosen three-hit subsets use distinct pairs, so 3r<=C(7,2).
For integers r=0..7,
  1_{r>0}<=r-C(r,2)+C(r,3)-(4/7)C(r,4).
Summing gives ceil(S1-S2+S3-4*S4/7). S4 is a LOWER bound being subtracted;
K4 uses CEILING, A_max FLOOR, final Fraction CEILING. Use the exact pinned
evaluator at EVERY integer t in both old and new intervals; record every
term and every maximum. Old caps come from accepted R30, NB and class
authority, never from the desired improvement or inverted row bounds.

FAMILY AND CAVEATS. Aggregate all 4647 resolved and 197 cursor rows before
and after modifying exactly these three owners. Preserve every cursor ID
and bound and the 282 inherited exclusions with their caveats verbatim;
they are not newly proved. The family maximum is computed from the full
ledger. CONDITIONAL_PROJECTION does not assert canonical adoption, global
optimality or prediction improvement. The independent verdict remains
external to this self-hashed JSON, preserving the single reviewed tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping
from functools import cache
from importlib import import_module
from math import comb
from pathlib import Path
from typing import Any, cast

# The frozen upstream module is dynamically typed; isolate it at this boundary.
upstream: Any = import_module("lottolab.research.b649_next_two_owner_shared_bound_r1")
type Record = dict[str, Any]
type Term = list[int]

TASK_ID = "B649_NEXT_THREE_OWNER_CURSOR_FLOOR_R1"
INPUT_HEAD = "204f668efe88ab71cb55df3e71cc12948252a450"
INPUT_TREE = "9b31b53b79a5ee012055e1c77e486ec05552088a"
BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
INPUT_RESULT = "docs/research/matrix-native-results/b649-next-two-owner-shared-bound-r1-result.json"
INPUT_SHA = "a022ef35cd3e7b853e82179f7696d63cb29365d8811c40f6a2ab5d2a0f39e108"
BASE_RESULT: str = upstream.BASE_RESULT
BASE_SHA: str = upstream.BASE_SHA
PROFILE_IDS = ("65555555555531100000", "66555555554441100000", "66555555555422100000")
SOURCE = "src/lottolab/research/b649_next_three_owner_cursor_floor_r1.py"
TEST = "tests/unit/test_b649_next_three_owner_cursor_floor_r1.py"
RESULT = "docs/research/matrix-native-results/b649-next-three-owner-cursor-floor-r1-result.json"
ROOT = Path(__file__).resolve().parents[3]
UPSTREAM_CODE_PINS = {
    upstream.SOURCE: "40236da825592d922082827c5793c621e0f644c11e0bacdf40d0840372863100",
    upstream.TEST: "a42cea9382cd953980131e65705e819f8cd924f01959ec125184762ec5dca5d5",
}


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def git(*args: str, repo: Path = ROOT) -> str:
    return (
        subprocess.check_output(["git", *args], cwd=repo, stderr=subprocess.PIPE).decode().strip()
    )


def blob(ref: str, path: str, repo: Path = ROOT) -> bytes:
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=repo)


def pinned_blob(ref: str, path: str, digest: str, repo: Path = ROOT) -> bytes:
    data = blob(ref, path, repo)
    require(sha(data) == digest, "authority blob identity: " + path)
    return data


def verify_identity(candidate: str = "HEAD", repo: Path = ROOT) -> str:
    require(sys.version_info[:2] == (3, 13), "Python 3.13 required")
    for head, tree in ((INPUT_HEAD, INPUT_TREE), (BASE_HEAD, BASE_TREE)):
        require(git("rev-parse", head + "^{tree}", repo=repo) == tree, "Git TREE pin")
    head = git("rev-parse", candidate, repo=repo)
    if head == INPUT_HEAD:
        return "INPUT_HEAD_WITH_WORKING_CANDIDATE"
    parents = git("rev-list", "--parents", "-n", "1", head, repo=repo).split()
    require(parents[1:] == [INPUT_HEAD], "direct single-parent child required")
    changed = git("diff-tree", "--no-commit-id", "--name-status", "-r", head, repo=repo)
    require(
        sorted(changed.splitlines()) == sorted(f"A\t{p}" for p in (SOURCE, TEST, RESULT)),
        "exactly three authorized additions required",
    )
    for path in (SOURCE, TEST):
        require((ROOT / path).read_bytes() == blob(head, path, repo), "candidate runtime source")
    return "FIXED_DIRECT_CHILD"


@cache
def profile_facts(pid: str) -> Record:
    require(pid in PROFILE_IDS, "wrong exact profile")
    d = tuple(map(int, pid))
    require(len(d) == 20 and tuple(sorted(d, reverse=True)) == d, "histogram order/size")
    require(all(0 <= x <= 6 for x in d) and sum(d) == 66, "triple degree histogram")
    g = tuple(6 + x for x in d)
    k, z = sum(x > 0 for x in d), d.count(0)
    numerator = sum(x * (19 - x) for x in g)
    require(sum(g) == 186 and numerator % 2 == 0, "degree/Goodman integrality")
    groups = sorted(Counter(x for x in d if x).items(), reverse=True)
    return {
        "PROFILE_ID": pid,
        "D": list(d),
        "G": list(g),
        "D_HISTOGRAM": {str(x): n for x, n in sorted(Counter(d).items())},
        "DEGREE_SUM_D": sum(d),
        "DEGREE_SUM_G": sum(g),
        "EDGES": sum(g) // 2,
        "WEDGES": sum(comb(x, 2) for x in g),
        "GOODMAN": comb(20, 3) - numerator // 2,
        "K": k,
        "Z": z,
        "M_DEGREE_OFFSET": k - 7,
        "N_DEGREE_OFFSET": z - 7,
        "M_EDGE_SUM_CONSTANT": k * (k - 7) - sum(d),
        "N_EDGE_SUM_CONSTANT": z * (z - 7),
        "SPLIT_H_CONSTANT": 3 * z * (k - 11),
        "ZETA_RANGE": [max(0, 7 - z), min(k, 6)],
        "SIGMA_BY_D": {
            str(x): {"COUNT": count, "RANGE": [0, min(z, 6 - x)]} for x, count in groups
        },
        "NECESSARY_CONSTRAINTS": {
            "CROSSING": "sum sigma = sum zeta = r; 10 <= r; r even",
            "M": "m=8-d+sigma; graphical; sum m=54+r",
            "N": "n=zeta-2; 6-zeta graphical; sum n=r-10",
            "BIPARTITE": "for each h: sum h largest sigma <= sum min(h,zeta), and vice versa",
            "RELAXATION": "induced graphical and bipartite inequalities omitted",
        },
        "J": sum(comb(x, 3) for x in g),
        "G_MAX": max(g),
        "A_MAX_NUMERATOR": sum(x * (x + 4) for x in d),
        "A_MAX": sum(x * (x + 4) for x in d) // 3,
        "PAIR_DEGREES": [6 - x for x in d],
        "ASSUMPTIONS": {
            "TICKETS": 20,
            "LABELS_PER_TICKET": 6,
            "LABELS": 49,
            "TRIPLE_LABELS": 22,
            "PAIR_LABELS": 27,
            "PAIR_LINEARITY": True,
        },
    }


def validate_facts(pid: str, claimed: object) -> None:
    require(render(claimed) == render(profile_facts(pid)), "profile/split facts mismatch")


def endpoint_certificate(pid: str) -> Record:
    f = profile_facts(pid)
    require((f["K"], f["Z"], f["GOODMAN"]) == (15, 5, 290), "shared split premises")
    require(f["ZETA_RANGE"] == [2, 6], "zeta endpoint premises")
    contributions: Record = {}
    for d, info in f["SIGMA_BY_D"].items():
        degree, count, upper = int(d), info["COUNT"], info["RANGE"][1]
        value = max(0, upper * (4 - degree + upper))
        contributions[d] = {
            "COUNT": count,
            "SIGMA_RANGE": [0, upper],
            "ENDPOINTS": [0, upper * (4 - degree + upper)],
            "MAXIMUM": value,
            "ALL_ARGMAX": [s for s in range(upper + 1) if s * (4 - degree + s) == value],
            "TOTAL": count * value,
        }
    constant = f["GOODMAN"] - f["SPLIT_H_CONSTANT"] - 12 * f["Z"]
    cap = constant + sum(c["TOTAL"] for c in contributions.values())
    return {
        "CONSTANT": constant,
        "SIGMA_ENDPOINT_CONTRIBUTIONS": contributions,
        "ZETA_CHORD": {"RANGE": [2, 6], "SLOPE": 6, "INTERCEPT": -12, "ALL_ARGMAX": [2, 6]},
        "CAP": cap,
        "REMAINDER_LOWER": {"T_M": 0, "T_N": 0, "C_K": 0, "C_Z": 0},
        "REMAINDER_DIRECTION": "subtract 0 <= P, hence increase the G upper bound",
        "REALIZABILITY": "NOT_ASSERTED; INDEPENDENT_ENDPOINT_RELAXATION",
    }


@cache
def replay_input(repo: Path = ROOT) -> tuple[Record, Record]:
    for path, digest in UPSTREAM_CODE_PINS.items():
        require(
            (ROOT / path).read_bytes() == pinned_blob(INPUT_HEAD, path, digest, repo),
            "upstream code identity",
        )
    upstream.verify_result(INPUT_HEAD, repo)
    fixed = cast(Record, json.loads(pinned_blob(INPUT_HEAD, INPUT_RESULT, INPUT_SHA, repo)))
    return fixed, {
        "DIRECT_CERTIFICATE": "COMPLETE_EXACT_RECOMPUTATION_AND_BYTE_REPLAY",
        "UPSTREAM_CODE_SHA256": UPSTREAM_CODE_PINS,
        "INHERITED_REPLAY_VERBATIM": fixed["UPSTREAM_REPLAY"],
        "HISTORICAL_SOLVERS_RERUN": False,
    }


def base_authority(repo: Path = ROOT) -> tuple[Record, Record]:
    base = cast(Record, json.loads(pinned_blob(BASE_HEAD, BASE_RESULT, BASE_SHA, repo)))
    refs = upstream.upstream.decode(
        upstream.upstream.blob(
            BASE_HEAD, upstream.upstream.r2.R30_PATH, upstream.upstream.r2.R30_SHA
        )
    )
    authority: Record = {}
    for pid in PROFILE_IDS:
        d = tuple(map(int, pid))
        records = [
            a
            for a in refs["GROUP_ATTEMPTS"]
            if a.get("PROFILE_IDS") == [pid] and a.get("STATUS") == "INFEASIBLE"
        ]
        require(records, "missing exact-profile R30 authority")
        ref = min(records, key=lambda a: a["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
        accepted = ref["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"]
        require(
            upstream.upstream.route.r28.r26.accepted_cap(ref, (d,), accepted) == accepted,
            "Base rejected R30 cap",
        )
        nb = upstream.upstream.r2.nb.profile_nb_cap(d)[2]
        cls = upstream.upstream.r2.nb.r18_cap(d)
        floor = upstream.upstream.route.r28.profile_s4_floor(d)
        require(
            pid not in base["CERTIFICATES_ADOPTED"]
            and pid not in base["PROFILE_CERTIFICATES"]
            and base["INHERITED_TARGET_BONFERRONI_5"]["PROFILE_ID"] != pid
            and base["ALL_T_BONFERRONI_5_ADOPTION"] == "NOT_VERIFIED",
            "unexpected adopted target S5",
        )
        authority[pid] = {
            "ACCEPTED_R30_CAP": accepted,
            "R30_ATTEMPT": ref,
            "R30_RESULT_SHA256": upstream.upstream.r2.R30_SHA,
            "NB_CAP": nb,
            "CLASS_CAP": cls,
            "OLD_CAP": min(accepted, nb, cls),
            "S4_BASE": floor,
            "S4_BY_T": {},
            "S5_USED": False,
        }
    return base, authority


def envelope(pid: str, cap: int, auth: Mapping[str, Any]) -> list[Term]:
    f = profile_facts(pid)
    require(type(cap) is int and 22 <= cap <= f["WEDGES"] // 3, "T cap")
    require(auth["S5_USED"] is False and not auth["S4_BY_T"], "S4/S5 authority scope")
    return [
        list(upstream.upstream.route.envelope_term(tuple(f["D"]), t, auth["S4_BASE"], f["A_MAX"]))
        for t in range(22, cap + 1)
    ]


def family_summary(resolved: Mapping[str, int], cursor: Mapping[str, int]) -> Record:
    require(not (resolved.keys() & cursor.keys()), "resolved/cursor overlap")
    return cast(Record, upstream.family_summary(dict(resolved), dict(cursor)))


def compute_result(candidate: str = "HEAD", repo: Path = ROOT) -> Record:
    mode = verify_identity(candidate, repo)
    fixed, replay = replay_input(repo)
    resolved: dict[str, int] = fixed["RESOLVED_ROWS_AFTER"]
    cursor: dict[str, int] = fixed["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    before = family_summary(resolved, cursor)
    require(
        before == fixed["FAMILY_AFTER"]
        and before["MAXIMUM"] == 313391844
        and before["ALL_MAX_OWNERS"] == sorted(PROFILE_IDS)
        and before["NEXT_DISTINCT_BOUND"] == before["CURSOR_MAXIMUM"] == 313391784
        and len(resolved) == 4647
        and len(cursor) == 197,
        "complete input family frontier",
    )
    base, auth = base_authority(repo)
    after_rows, profiles = dict(resolved), cast(Record, {})
    for pid in PROFILE_IDS:
        a, theorem = auth[pid], endpoint_certificate(pid)
        old = envelope(pid, a["OLD_CAP"], a)
        require(
            max(t[1] for t in old) == resolved[pid] == base["RESOLVED_ROW_BOUNDS"][pid],
            "old full Base envelope replay",
        )
        cap = min(a["OLD_CAP"], theorem["CAP"], profile_facts(pid)["WEDGES"] // 3)
        new = envelope(pid, cap, a)
        bound = max(t[1] for t in new)
        after_rows[pid] = min(resolved[pid], bound)
        profiles[pid] = {
            "FACTS": profile_facts(pid),
            "ANALYTIC_CERTIFICATE": theorem,
            "OLD_CAP": a["OLD_CAP"],
            "NEW_CAP": cap,
            "OLD_BOUND": resolved[pid],
            "NEW_BOUND": bound,
            "ADOPTED_PROJECTED_BOUND": after_rows[pid],
            "OLD_ALL_T_TERMS": old,
            "NEW_ALL_T_TERMS": new,
            "OLD_ALL_ARGMAX": [t for t in old if t[1] == resolved[pid]],
            "NEW_ALL_ARGMAX": [t for t in new if t[1] == bound],
            "S4_BASE": a["S4_BASE"],
            "S4_BY_T": a["S4_BY_T"],
            "S5_USED": False,
            "FRACTIONAL_CREDIT_TERMS": sum((4 * t[4]) % 7 != 0 for t in new),
        }
    after = family_summary(after_rows, cursor)
    changed = sorted(p for p in resolved if resolved[p] != after_rows[p])
    require(set(changed) == set(PROFILE_IDS), "all three owners must be handled")

    def code_bytes(path: str) -> bytes:
        return (
            (ROOT / path).read_bytes()
            if mode.startswith("INPUT_HEAD")
            else blob(candidate, path, repo)
        )

    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "PROVEN_FAMILY_GAIN"
        if after["MAXIMUM"] < before["MAXIMUM"]
        else "NO_PROVEN_FAMILY_GAIN",
        "INPUT_CERTIFICATE": {
            "HEAD": INPUT_HEAD,
            "TREE": INPUT_TREE,
            "PATH": INPUT_RESULT,
            "SHA256": INPUT_SHA,
        },
        "MATHEMATICAL_BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "PATH": BASE_RESULT,
            "SHA256": BASE_SHA,
        },
        "SOURCE_SHA256": sha(code_bytes(SOURCE)),
        "TEST_SHA256": sha(code_bytes(TEST)),
        "PROOF": __doc__,
        "UPSTREAM_REPLAY": replay,
        "PROFILE_ORDER": list(PROFILE_IDS),
        "PROFILES": profiles,
        "SHARED_THEOREM": {
            "COMMON_T_CAP": max(p["ANALYTIC_CERTIFICATE"]["CAP"] for p in profiles.values()),
            "PER_PROFILE_CAPS": {
                p: profiles[p]["ANALYTIC_CERTIFICATE"]["CAP"] for p in PROFILE_IDS
            },
            "UNIVERSALITY": "ALL_LEGAL_REALIZATIONS_OF_EACH_EXACT_PROFILE",
            "FULL_SUPPORT_GRAPHS_ENUMERATED": 0,
            "PORTFOLIOS_ENUMERATED": 0,
            "RELAXED_ENDPOINTS_ASSERTED_REALIZABLE": False,
        },
        "S4_S5_AUTHORITY": {
            "PER_PROFILE": auth,
            "S4_RULE": "MAX; NEVER ADD; NO TARGET CAP_TERM_OVERRIDE",
            "S5_ADOPTED_CERTIFICATES": base["CERTIFICATES_ADOPTED"],
            "S5_ALL_T_ADOPTION": base["ALL_T_BONFERRONI_5_ADOPTION"],
            "S5_INHERITED_TARGET": base["INHERITED_TARGET_BONFERRONI_5"],
        },
        "TERM_COLUMNS": fixed["TERM_COLUMNS"],
        "FULL_ENVELOPE_TERM_COUNTS": {
            "OLD_PER_PROFILE": {p: len(profiles[p]["OLD_ALL_T_TERMS"]) for p in PROFILE_IDS},
            "NEW_PER_PROFILE": {p: len(profiles[p]["NEW_ALL_T_TERMS"]) for p in PROFILE_IDS},
            "OLD_TOTAL": sum(len(p["OLD_ALL_T_TERMS"]) for p in profiles.values()),
            "NEW_TOTAL": sum(len(p["NEW_ALL_T_TERMS"]) for p in profiles.values()),
            "OLD_T_RANGES": {p: [22, profiles[p]["OLD_CAP"]] for p in PROFILE_IDS},
            "NEW_T_RANGES": {p: [22, profiles[p]["NEW_CAP"]] for p in PROFILE_IDS},
        },
        "FAMILY_BEFORE": before,
        "FAMILY_AFTER": after,
        "FAMILY_DELTA": before["MAXIMUM"] - after["MAXIMUM"],
        "CURSOR_FLOOR_REACHED": after["MAXIMUM"] == max(cursor.values()),
        "ALL_NEW_MAX_OWNERS": after["ALL_MAX_OWNERS"],
        "NEXT_DISTINCT_BOUND": after["NEXT_DISTINCT_BOUND"],
        "RESOLVED_ROWS_BEFORE": resolved,
        "RESOLVED_ROWS_AFTER": after_rows,
        "RESOLVED_ROWS_CHANGED": changed,
        "OTHER_RESOLVED_ROWS_UNCHANGED": len(resolved) - len(changed),
        "CURSOR_197_PRESERVED": fixed["CURSOR_197_PRESERVED"],
        "INHERITED_EXCLUSION_PRESERVED": True,
        "INHERITED_EXCLUSION": fixed["INHERITED_EXCLUSION"],
        "INHERITED_CAVEATS_REFERENCE": fixed["INHERITED_CAVEATS_REFERENCE"],
        "UPSTREAM_PRIOR_REVIEW_CAVEAT_VERBATIM": fixed["UPSTREAM_PRIOR_REVIEW_CAVEAT_VERBATIM"],
        "EARLIER_WORKER_ATTEMPT_HISTORY_VERBATIM": fixed[
            "UPSTREAM_WORKER_ATTEMPT_HISTORY_VERBATIM"
        ],
        "UPSTREAM_WORKER_ATTEMPT_HISTORY_VERBATIM": fixed["WORKER_ATTEMPT_HISTORY"],
        "WORKER_ATTEMPT_HISTORY": [
            {
                "OBSERVED": "goal creation rejected because the Owner goal was already active",
                "DISPOSITION": "existing goal retained",
            },
            {
                "OBSERVED": "one bounded exploratory upstream relaxation gave caps 250/250/247",
                "DISPOSITION": "not adopted; sufficient analytic T<=262 ends further tightening",
            },
            {
                "OBSERVED": "initial focused Ruff and strict Pyright found formatting/type issues",
                "DISPOSITION": "repaired within the three-file scope before final verification",
            },
        ],
        "PRIOR_REVIEW_CAVEAT": fixed.get(
            "PRIOR_REVIEW_CAVEAT", "direct fresh verdict external to its self-hashed JSON"
        ),
        "PROJECTION_STATUS": "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION",
        "INCUMBENT": fixed["INCUMBENT"],
        "GAP_TO_INCUMBENT": after["MAXIMUM"] - fixed["INCUMBENT"],
        "GLOBAL_OPTIMUM": "UNKNOWN",
        "PREDICTION_GAIN_CLAIMED": False,
        "FRESH_JUDGE": "ONE_FRESH_FOCUSED_REVIEW_ON_FINAL_TREE; VERDICT_EXTERNAL_TO_JSON",
        "CANONICAL_AUTHORITY_CHANGED": "NO",
        "REMOTE_WRITE": "NONE",
        "PRODUCTION_MUTATION": "NONE",
    }


def validate_payload(payload: object, expected: object) -> None:
    require(render(payload) == render(expected), "result differs from complete exact recomputation")


def verify_result(candidate: str = "HEAD", repo: Path = ROOT) -> None:
    expected = compute_result(candidate, repo)
    data = (
        (ROOT / RESULT).read_bytes()
        if git("rev-parse", candidate, repo=repo) == INPUT_HEAD
        else blob(candidate, RESULT, repo)
    )
    require(data == render(expected), "stored result differs from complete exact recomputation")


def main() -> None:
    parser = argparse.ArgumentParser(description=TASK_ID)
    parser.add_argument("--write-result", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    if args.write_result:
        require(not (ROOT / RESULT).exists(), "result already exists")
        (ROOT / RESULT).write_bytes(render(result))
    if args.verify:
        verify_result()
    print(
        json.dumps(
            {k: result[k] for k in ("TASK_STATUS", "FAMILY_BEFORE", "FAMILY_AFTER", "FAMILY_DELTA")}
        )
    )


if __name__ == "__main__":
    main()
