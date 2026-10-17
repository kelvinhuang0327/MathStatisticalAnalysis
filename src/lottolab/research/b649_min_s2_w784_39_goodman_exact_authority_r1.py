"""Universal Goodman certificate and exact adoption for the 39 W784 cursors.

Frozen support model: 20 tickets of size six, 22 labels supported on three
tickets and 27 on two, with pair-linearity. Each triple label creates three
distinct graph edges; each pair label one. The overlap graph is therefore
simple, E=93, g_i=6+d_i, sum(d)=66 and sum(g)=186. All legal realizations of
each profile, including any not constructed here, are covered.

Count ordered choices of a neighbour and a non-neighbour at each vertex.
Each non-homogeneous vertex triple contributes two, and a homogeneous triple
contributes zero. Thus T(G)+T(complement G)=C(20,3)-sum(g_i(19-g_i))/2.
For W784, sum(g_i^2)=2W+sum(g)=1754, so the right side is 250. Since the
complement has nonnegative triangle count, T(G)<=250. This is a universal
upper bound; existence and attainment of its endpoint are not asserted.

The immutable R8/r4 coarse evaluator uses S3=2800(W-3T)+20272(T-22)+7000*22
=2800W+11872(T-22)-30800. Its T coefficient is positive. The inherited r2
S4>=112 proof covers the entire frozen model, not just a constructed graph:
sum d^2>=222 gives at least 486 cross incidences on 374 core/outside pairs.
If no contributing quartet existed, at most two incidences per pair and at
most one outside common neighbour per core edge would force >=112 such
pairs to inject into only 66 core edges, a contradiction. Each contributing
quartet has at least 112 outcomes, by the inherited exact local table.

For a seven-label outcome, choose three hit labels from each winning ticket.
Pair-linearity makes their label pairs distinct, hence 3r<=C(7,2) and r<=7.
For every integer r=0..7, 1[r>0]<=r-C(r,2)+C(r,3)-(4/7)C(r,4).
Consequently B=ceil(S1-S2+S3-4*112/7). The negative S4 coefficient licenses
a LOWER S4 floor; it is equivalent to subtracting floor(4*112/7)=64.
No S5 term or stronger Route-B/K4 certificate enters this task.

Only 39 cursor projection values change. Cursor IDs, membership, partition,
coverage, all 4647 resolved rows, and all other cursor fields are inherited
unchanged. The legacy cursor BOUND is frozen metadata; the recomputed
CURSOR_MAXIMUM and FAMILY_AFTER fields are the aggregate authority.
Advanced 11-row certificates are accepted through the SHA-pinned Base result
and its fresh Judge, never rerun here. Historical limitations are not upgraded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from fractions import Fraction
from math import ceil, comb
from pathlib import Path
from typing import cast

from . import b649_k20_min_s2_higher_order_closure_r2 as r2
from . import b649_k20_min_s2_next_active_profile_exact_bound_r8 as r8
from . import b649_k20_min_s2_realizable_core_class_bound_r4 as r4

type Document = dict[str, object]
ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_W784_39_GOODMAN_EXACT_AUTHORITY_R1"
OWNER_CONVERSATION_ID = "01a13d3b-9564-7e42-a794-84adced05457"
STEM = "b649_min_s2_w784_39_goodman_exact_authority_r1"
SOURCE = f"src/lottolab/research/{STEM}.py"
TEST = f"tests/unit/test_{STEM}.py"
DIRECTORY = "docs/research/matrix-native-results/"
RESULT = DIRECTORY + STEM.replace("_", "-") + "-result.json"
BASE_HEAD = "b280d90be0c35b8c5b1ca7798a394332194f8887"
BASE_TREE = "7d94024cebbce0c05d80902256ccae137fcbc279"
BASE_RESULT = DIRECTORY + "b649-min-s2-advanced-11row-exact-adoption-r1-result.json"
BASE_SHA = "48dfb1fdcbcc232ef43cb540b80e4dc04dffc33b00dc0c55f6d2be491aecf24f"
R8_HEAD = "5ac18ded3f2bc61449baa4d5e00ac0c1c8b247d1"
PRIOR_HEAD = "93c263d187e4b0445ae465a5235c3a630f91396a"
PRIOR_TREE = "94a5c7c9987d517a095c16a3730a3d911fda8463"
PRIOR_RESULT = DIRECTORY + "b649-w784-39-cursor-shared-bound-r1-result.json"
PRIOR_SHA = "5d0692d6153a38c4a4f1ff021041102d83cbd00ad4f4701ccdb672e1eb7f4b15"
IDS_SHA = "f8b9eeec6bd56a9603ac96611e2be5b2190e023227c5c1276c628b7f4a651af0"
INCUMBENT = 313263888
OLD_BOUND = 313391784
NEW_BOUND = 313261192
PINS = {
    "b649_k20_min_s2_next_active_profile_exact_bound_r8.py": (
        "8b70fbfa9f3cc3cabe0c48956d92b7f81600c474b4331717695de303855d382a"
    ),
    "b649_k20_min_s2_realizable_core_class_bound_r4.py": (
        "cbc57debfcc037b8be605f9c3e157dba9029fbbcca50fa05dcff99390066edec"
    ),
    "b649_k20_min_s2_higher_order_closure_r2.py": (
        "6897c974fe9679f2ec567602522bb4c38c996275368b714c6a7fadedd66d6e45"
    ),
}


BASE_JUDGE: Document = {
    "VERDICT": "VERIFIED_WITH_CAVEATS",
    "JUDGED_HEAD": "b280d90be0c35b8c5b1ca7798a394332194f8887",
    "JUDGED_TREE": "7d94024cebbce0c05d80902256ccae137fcbc279",
    "REPORT_SHA256": "c703dd43fbb3653bbac5fc3db84de44a4a2def55c0cc4f8d49b97cd70cc59527",
    "CAVEATS_VERBATIM": (
        "## Findings\n"
        "\n"
        "finding_id: F1\n"
        "severity: NON_BLOCKING\n"
        "FINDING_CONFIDENCE: CONFIRMED\n"
        "claim: Judge-side write: one Judge command (`git write-tree`, run as an "
        "identity check) rewrote the per-worktree index file.\n"
        "criterion_or_rule: Judge write accounting / read-only boundary; Packet "
        "R15.\n"
        "evidence: index mtime 2026-10-15T04:32:20 after the command; SHA256 "
        "before (worker r15-pre-judge FINAL_INDEX_SHA256) and after = "
        "2978e6e7149797ffd99283e0eba5655a7e9c8ead913c047853139a59a378c707; "
        "printed tree 7d94024c already existed as the commit tree.\n"
        "expected: no file outside the report/scratch touched.\n"
        "observed: byte-identical index rewrite (mtime only); no new object, no "
        "ref change, HEAD/tree unchanged, status clean. Not a candidate defect; "
        "any final R15 observation of index mtime should attribute it to the "
        "Judge.\n"
        "\n"
        "finding_id: F2\n"
        "severity: NON_BLOCKING\n"
        "FINDING_CONFIDENCE: CONFIRMED\n"
        "claim: The cap-swap, S4-scope-leakage and rounding negative tests call "
        "test-facing validators that the production path never calls.\n"
        "criterion_or_rule: G17 test integrity.\n"
        "evidence: validate_old_cap / validate_terms / validate_s4_scope (src "
        "lines 1040\u20131054) have no call site in compute_result (grep: only tests "
        "call them). The production path relies on other guards: old envelope "
        "must reproduce the Base row and the sealed T264 terms, `require(not "
        "special)` for new envelopes, frozen-r32 vs Fraction agreement, and byte "
        "equality with the sealed result.\n"
        "expected: negative tests reject the mutation class on the real path.\n"
        "observed: Judge mutants on the production path (old cap -> 263; T264 "
        "floor leaked to all t) were killed (9 errors each), so the classes are "
        "rejected; the helper-level tests are weaker evidence than they appear "
        "but not vacuous.\n"
        "\n"
        "finding_id: F3\n"
        "severity: NON_BLOCKING\n"
        "FINDING_CONFIDENCE: CONFIRMED\n"
        "claim: DONOR_DISPOSITIONS.VERBATIM carries a curated subset of 13 keys; "
        "donor keys holding nested SELF_CHECK_ONLY / PENDING / exclusion text "
        "(INHERITED_CAVEATS_REFERENCE, INHERITED_CAVEATS_AUTHORITY, "
        "INHERITED_EXCLUSION, WORKER_ATTEMPT_HISTORY, UPSTREAM_*) are not copied."
        "\n"
        'criterion_or_rule: Packet §四 "all donor '
        'pending/conditional/SELF_CHECK_ONLY/resource caveats preserved" (G05).\n'
        "evidence: key comparison against donor blobs; those objects remain bound"
        " by the SHA-pinned immutable donor results in IDENTITIES, nothing is "
        "upgraded, and the 282-histogram exclusion (IDS_SHA256 2c4d5b04...) is "
        "also in the byte-identical Base cursor PARTITION.\n"
        "observed: preserved by immutable reference rather than verbatim copy; "
        "non-material.\n"
        "\n"
        "finding_id: F4\n"
        "severity: NON_BLOCKING\n"
        "FINDING_CONFIDENCE: CONFIRMED\n"
        "claim: The Packet's item-by-item cross-reference to the prior read-only "
        "18526-term study was not performed.\n"
        "criterion_or_rule: Packet §七.4 / G13.\n"
        'evidence: result PRIOR_18526_TERM_STUDY = "LOCATOR_NOT_SUPPLIED; '
        'COMPARED_AGAINST_IMMUTABLE_SEALED_TERMS"; Judge search of all '
        '.git/worktrees/*/task-evidence found "18526" only in this Packet.\n'
        "observed: all 2534 load-bearing new terms and 2685 old terms are instead"
        " matched to immutable sealed donor/protected/Base terms and "
        "independently recounted by the Judge; the specific prior study remains "
        "unreferenced."
    ),
    "BINDING": (
        "observed SHA-pinned Base report; caveats preserved verbatim in this source; "
        "no mutable report read"
    ),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def obj(value: object) -> Document:
    require(isinstance(value, dict), "expected object")
    return cast(Document, value)


def ledger(value: object) -> dict[str, int]:
    result = obj(value)
    require(all(type(b) is int for b in result.values()), "integer bounds required")
    return cast(dict[str, int], result)


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", "core.fsmonitor=false", "-C", str(ROOT), *args], text=True
    ).strip()


def blob(head: str, path: str, expected_sha: str) -> bytes:
    metadata = git("ls-tree", head, "--", path).split()
    require(len(metadata) == 4 and metadata[:2] == ["100644", "blob"], "unsafe blob mode")
    require(metadata[3] == path, "blob path mismatch")
    payload = subprocess.check_output(["git", "-C", str(ROOT), "cat-file", "blob", metadata[2]])
    require(sha(payload) == expected_sha, "source mismatch: immutable blob SHA256")
    return payload


def working_bytes(path: str) -> bytes:
    target = ROOT / path
    require(target.is_file() and not target.is_symlink(), "unsafe working source")
    return target.read_bytes()


def load_base() -> Document:
    require(git("rev-parse", BASE_HEAD + "^{tree}") == BASE_TREE, "Base tree mismatch")
    payload = blob(BASE_HEAD, BASE_RESULT, BASE_SHA)
    require(working_bytes(BASE_RESULT) == payload, "source mismatch: Base result bytes")
    return obj(json.loads(payload))


def verify_sources() -> None:
    require(git("rev-parse", R8_HEAD + "^{commit}") == R8_HEAD, "R8 commit mismatch")
    for module in (r8, r4, r2):
        filename = module.__file__
        if filename is None:
            raise ValueError("source mismatch: imported evaluator filename")
        require(
            Path(filename).resolve().parent == ROOT / "src/lottolab/research",
            "source mismatch: imported evaluator root",
        )
    for name, digest in PINS.items():
        path = "src/lottolab/research/" + name
        payload = blob(R8_HEAD, path, digest)
        require(working_bytes(path) == payload, "source mismatch: working evaluator bytes")
        require(blob(BASE_HEAD, path, digest) == payload, "source mismatch: Base evaluator")
    require(r8.INHERITED_S4_LOWER_BOUND == 112, "inherited S4 scope")
    require(r8.INHERITED_FOURTH_ORDER_CREDIT == 64, "inherited S4 correction")


def profile_facts(pid: str) -> dict[str, int]:
    require(len(pid) == 20 and all(c in "0123456" for c in pid), "profile format")
    require(pid == "".join(sorted(pid, reverse=True)), "profile order")
    d = tuple(map(int, pid))
    require(sum(d) == 66, "profile degree sum")
    g = tuple(6 + x for x in d)
    return {
        "N": len(g),
        "E": sum(g) // 2,
        "SUM_D": sum(d),
        "SUM_G": sum(g),
        "SUM_G_SQUARED": sum(x * x for x in g),
        "W": sum(comb(x, 2) for x in g),
        "MIXED_ORDERED": sum(x * (19 - x) for x in g),
    }


def derive_cohort(ids: Sequence[str]) -> list[str]:
    return sorted((p for p in ids if profile_facts(p)["W"] == 784), reverse=True)


def ids_digest(ids: Sequence[str]) -> str:
    """Packet serialization: default json.dumps(list), UTF-8, no final newline."""
    return sha(json.dumps(list(ids)).encode("utf-8"))


def goodman_cap(facts: Mapping[str, int]) -> int:
    return comb(facts["N"], 3) - facts["MIXED_ORDERED"] // 2


def s3_at(w: int, t: int) -> int:
    return 2800 * w + 11872 * (t - 22) - 30800


def ceil_fraction(value: Fraction) -> int:
    return ceil(value)


def exact_bound(w: int, t: int, s4: int = 112) -> int:
    return ceil_fraction(Fraction(372228640 - 63838600 + s3_at(w, t)) - Fraction(4 * s4, 7))


def arithmetic_audit() -> Document:
    require(s3_at(784, 23) - s3_at(784, 22) == 11872, "wrong S3 sign")
    require(s3_at(784, 22) == 2164400, "S3 constant")
    polynomial: list[str] = []
    for r in range(8):
        upper = Fraction(r - comb(r, 2) + comb(r, 3)) - Fraction(4 * comb(r, 4), 7)
        require(upper >= int(r > 0), "4/7 multiplicity inequality")
        polynomial.append(str(upper))
    # Same production rounding path, with nonintegral credit to distinguish floor/ceil.
    for s4 in (112, 113, 114):
        integral = 372228640 - 63838600 + 2164400
        require(exact_bound(784, 22, s4) == integral - (4 * s4) // 7, "wrong rounding")
    certificate = r2.k20_min_s2_s4_lower_bound_certificate()
    require(
        (
            certificate.minimum_triple_incidence_square_sum,
            certificate.cross_incidence_lower_bound,
            certificate.core_outside_pair_count,
            certificate.double_incidence_lower_bound_if_no_contribution,
            certificate.core_edge_count,
            certificate.s4_lower_bound,
        )
        == (222, 486, 374, 112, 66, 112),
        "inherited S4 certificate",
    )
    return {
        "S3_T_COEFFICIENT": 11872,
        "S4_LOWER_BOUND": 112,
        "S4_CREDIT": 64,
        "S4_PROOF_SCOPE": "entire frozen pair-linear 22-triple/27-pair support model",
        "MAX_WINNERS": 7,
        "BONFERRONI_POLYNOMIAL_R0_TO_R7": polynomial,
        "ROUNDING": "ceil(integer-4*S4/7)=integer-floor(4*S4/7)",
        "NONINTEGRAL_ROUNDING_PROBES": [113, 114],
        "S5_USED": False,
    }


def make_updates(ids: Sequence[str], bound: int) -> list[tuple[str, int]]:
    return [(p, bound) for p in ids]


def family(rows: Mapping[str, int], bounds: Mapping[str, int]) -> Document:
    require(
        len(rows) == 4647 and len(bounds) == 197 and not set(rows) & set(bounds), "family coverage"
    )
    all_rows = {**rows, **bounds}
    best = max(all_rows.values())
    owners = sorted(p for p, b in all_rows.items() if b == best)
    ordered = sorted(all_rows.items(), key=lambda item: (-item[1], item[0]))
    require(owners == [p for p, b in ordered if b == ordered[0][1]], "family tied owners")
    opened = sum(b > INCUMBENT for b in all_rows.values())
    require(opened == sum(b > INCUMBENT for _, b in ordered), "family open replay")
    return {
        "FAMILY_BOUND": best,
        "OWNER_IDS": owners,
        "GAP_TO_INCUMBENT": best - INCUMBENT,
        "STILL_OPEN_PROFILE_COUNT": opened,
        "RESOLVED_MAXIMUM": max(rows.values()),
        "CURSOR_MAXIMUM": max(bounds.values()),
        "NEXT_DISTINCT_BOUND": max(b for b in all_rows.values() if b < best),
    }


def prior_disposition() -> Document:
    require(git("rev-parse", PRIOR_HEAD + "^{tree}") == PRIOR_TREE, "prior art tree")
    donor = obj(json.loads(blob(PRIOR_HEAD, PRIOR_RESULT, PRIOR_SHA)))
    theorem = obj(donor["SHARED_THEOREM"])
    require(
        donor["CANONICAL_AUTHORITY_CHANGED"] == "NO"
        and donor["PROJECTION_STATUS"] == "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION",
        "prior art disposition",
    )
    return {
        "HEAD": PRIOR_HEAD,
        "TREE": PRIOR_TREE,
        "RESULT_SHA256": PRIOR_SHA,
        "ORIGINAL_DISPOSITION_VERBATIM": {
            k: donor[k]
            for k in (
                "TASK_STATUS",
                "PROJECTION_STATUS",
                "CANONICAL_AUTHORITY_CHANGED",
                "FRESH_JUDGE",
                "PRIOR_REVIEW_CAVEAT_VERBATIM",
                "UPSTREAM_PRIOR_REVIEW_CAVEAT_VERBATIM",
                "UPSTREAM_WORKER_ATTEMPT_HISTORY_VERBATIM",
                "WORKER_ATTEMPT_HISTORY",
                "INHERITED_CAVEATS_REFERENCE",
                "INHERITED_EXCLUSION",
                "GLOBAL_OPTIMUM",
            )
        },
        "SHARED_THEOREM_REFERENCE_ONLY": theorem,
        "ADOPTED": False,
        "FORMAL_ROUTE_B_RECERTIFIED": False,
    }


def compute_result() -> Document:
    verify_sources()
    base = load_base()
    require(
        base["MODEL"]
        == {
            "TICKETS": 20,
            "LABELS_PER_TICKET": 6,
            "TRIPLES": 22,
            "PAIRS": 27,
            "PAIR_LINEARITY": True,
        },
        "frozen support model scope",
    )
    rows = ledger(base["RESOLVED_ROW_BOUNDS"])
    cursor = obj(base["CURSOR"])
    bounds = ledger(cursor["COARSE_BOUND_PROJECTION"])
    ids = cast(list[str], cursor["PROFILE_IDS"])
    require(
        len(rows) == 4647
        and len(ids) == len(set(ids)) == len(bounds) == 197
        and set(ids) == set(bounds)
        and not set(rows) & set(bounds),
        "missing cursor/coverage",
    )
    require(cursor["PROFILE_COUNT"] == base["CURSOR_PROFILES"] == 197, "cursor count")
    cohort = derive_cohort(ids)
    require(len(cohort) == len(set(cohort)) == 39 and set(cohort) <= set(ids), "wrong cohort")
    require(ids_digest(cohort) == IDS_SHA, "wrong cohort canonical SHA256")
    proofs: Document = {}
    audit = arithmetic_audit()
    for pid in cohort:
        facts = profile_facts(pid)
        require(
            (facts["N"], facts["E"], facts["SUM_G"], facts["SUM_G_SQUARED"], facts["W"])
            == (20, 93, 186, 1754, 784),
            "wrong W/degree identities",
        )
        require(facts["MIXED_ORDERED"] == 1780, "Goodman mixed count")
        cap = goodman_cap(facts)
        independent = Fraction(comb(20, 3)) - Fraction(19 * 186 - 1754, 2)
        require(cap == independent == 250, "incorrect Goodman cap")
        frozen = r8.coarse_profile_envelope(tuple(map(int, pid)))
        require(
            frozen.wedge_count == 784
            and frozen.graph_triangle_upper_bound == 261
            and frozen.fourth_order_credit == 64,
            "R8 coarse premise",
        )
        require(frozen.s3_upper_bound == s3_at(784, 261), "R8 S3 identity")
        require(
            bounds[pid] == frozen.family_upper_bound == exact_bound(784, 261) == OLD_BOUND,
            "old bound reproduction",
        )
        new = exact_bound(784, cap)
        integer_bound = 372228640 - 63838600 + 2800 * 784 + 11872 * (cap - 22) - 30800 - 64
        require(new == integer_bound == NEW_BOUND, "new bound exact recount")
        # Independently expand local-event terms for every integer in the relaxation.
        terms: list[int] = []
        for t in range(22, cap + 1):
            expanded = 2800 * (784 - 3 * t) + 20272 * (t - 22) + 7000 * 22
            rational = Fraction(372228640 - 63838600 + expanded) - Fraction(4 * 112, 7)
            independent_ceiling = -(-rational.numerator // rational.denominator)
            require(exact_bound(784, t) == independent_ceiling, "wrong sign/rounding term")
            terms.append(independent_ceiling)
        require(max(terms) == new and terms[-1] == new, "all-T envelope")
        proofs[pid] = {
            "FACTS": facts,
            "UNIVERSAL_T_CAP": cap,
            "OLD_T_CAP": 261,
            "OLD_BOUND": OLD_BOUND,
            "NEW_BOUND": new,
            "ALL_T_INTEGER_BOUNDS": terms,
            "LEGAL_ATTAINMENT": "UNKNOWN",
        }
    updates = make_updates(cohort, NEW_BOUND)
    require(len(updates) == len(dict(updates)), "duplicate update")
    require(set(dict(updates)) == set(cohort), "wrong cohort/missing update")
    require(all(b == NEW_BOUND for _, b in updates), "incorrect update bound")
    after_bounds = {**bounds, **dict(updates)}
    changed = sorted(p for p in bounds if bounds[p] != after_bounds[p])
    require(changed == sorted(cohort), "exactly 39 cursor changes")
    others = {p: b for p, b in bounds.items() if p not in cohort}
    require(
        len(others) == 158 and all(after_bounds[p] == b for p, b in others.items()),
        "other cursor mutation",
    )
    after_cursor = {**cursor, "COARSE_BOUND_PROJECTION": dict(sorted(after_bounds.items()))}
    require(
        {k: v for k, v in after_cursor.items() if k != "COARSE_BOUND_PROJECTION"}
        == {k: v for k, v in cursor.items() if k != "COARSE_BOUND_PROJECTION"},
        "cursor identity/membership mutation",
    )
    before, after = family(rows, bounds), family(rows, after_bounds)
    sealed_before = obj(base["S2_69D2_PLUS_STRONGER_ROWS"])
    require(all(before[k] == sealed_before[k] for k in before), "Base family replay")
    require(
        after["FAMILY_BOUND"] == 313391740
        and after["OWNER_IDS"] == ["66655555555331100000", "66655555555411110000"]
        and after["GAP_TO_INCUMBENT"] == 127852
        and after["STILL_OPEN_PROFILE_COUNT"] == 1516,
        "Family after replay",
    )
    return {
        "TASK_ID": TASK_ID,
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "TASK_STATUS": "SCIENTIFIC_AUTHORITY_SEALED; FRESH_JUDGE_AND_LIFECYCLE_EXTERNAL",
        "PROOF": __doc__,
        "MODEL": base["MODEL"],
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_SHA,
        "BASE_FRESH_JUDGE": BASE_JUDGE,
        "SOURCE_SHA256": sha(working_bytes(SOURCE)),
        "TEST_SHA256": sha(working_bytes(TEST)),
        "R8_HEAD": R8_HEAD,
        "EVALUATOR_SOURCE_PINS": PINS,
        "PRIOR_ART": prior_disposition(),
        "COHORT_IDS": cohort,
        "COHORT_COUNT": len(cohort),
        "COHORT_IDS_SHA256": ids_digest(cohort),
        "UNIVERSAL_T_CAP": 250,
        "COHORT_BOUND_BEFORE": OLD_BOUND,
        "COHORT_BOUND_AFTER": NEW_BOUND,
        "COHORT_DELTA": OLD_BOUND - NEW_BOUND,
        "PROFILE_CERTIFICATES": proofs,
        "EXACT_ARITHMETIC": audit,
        "RESOLVED_ROWS": len(rows),
        "RESOLVED_ROW_BOUNDS": dict(sorted(rows.items())),
        "RESOLVED_ROW_BOUNDS_CHANGED": 0,
        "RESOLVED_ROWS_SHA256": sha(render(rows)),
        "CURSOR_PROFILES": len(ids),
        "CURSOR": after_cursor,
        "CURSOR_BOUNDS_UPDATED": len(changed),
        "OTHER_CURSOR_BOUNDS_UNCHANGED": len(others),
        "OTHER_CURSOR_BOUNDS_SHA256": sha(render(others)),
        "FAMILY_BEFORE": before,
        "FAMILY_AFTER": after,
        "FAMILY_DELTA": cast(int, before["FAMILY_BOUND"]) - cast(int, after["FAMILY_BOUND"]),
        "INCUMBENT": INCUMBENT,
        "INHERITED_AUTHORITY_VERBATIM": {
            k: base[k]
            for k in (
                "IDENTITIES",
                "DONOR_DISPOSITIONS",
                "BASE_JUDGE",
                "PROTECTED_JUDGE",
                "INHERITED_BASE_CAVEATS",
                "INHERITED_PROTECTED_STATUS",
                "HISTORICAL_A14",
                "HISTORICAL_R15",
                "PRIOR_18526_TERM_STUDY",
            )
        },
        "HISTORICAL_R15": "NOT_VERIFIED",
        "EXTERNAL_18526_TERM_REFERENCE": "NOT_VERIFIED",
        "ADVANCED_11ROW_RECERTIFIED": False,
        "LEGAL_ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "GATE_SCOPE": "G01-G16 deterministic proof/tests; G17-G18 per-worktree task evidence",
    }


def verify_result(value: object) -> None:
    require(render(value) == render(compute_result()), "deterministic result mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    payload = render(compute_result())
    path = ROOT / RESULT
    if args.write_result and not path.exists():
        with path.open("xb") as stream:
            stream.write(payload)
    else:
        require(path.is_file() and path.read_bytes() == payload, "sealed result mismatch")
    value = obj(json.loads(payload))
    print(json.dumps({"RESULT_SHA256": sha(payload), "FAMILY_AFTER": value["FAMILY_AFTER"]}))


if __name__ == "__main__":
    main()
