"""Exact adoption of the strictly stronger Advanced rows into the 69d2 Family.

Frozen model. Twenty six-label tickets use 22 triple labels and 27 pair labels
(49 labels, each on exactly three or two tickets); two tickets share at most
one label. A ticket of triple degree d has g=6+d overlap neighbours, so
sum d=66, sum g=186 and the overlap graph G has E=93 edges. The 22 triple
supports are distinct triangles: 22<=T(G)<=floor(W/3), W=sum C(g,2). Every
non-homogeneous vertex triple contributes exactly two to sum g(19-g), hence
T(G)+T(complement G)=B=C(20,3)-sum g(19-g)/2.

Selection. The immutable 69d2 ledger (4647 resolved rows, 197-profile cursor)
is compared row by row with the final Advanced ledger, after replaying the
chain 06664eeb->600a9aad->0f0c9a32->204f668e->2159f525 link by link. Rows
that differ are classified by direction only: a row is adoptable exactly when
its Advanced value is strictly below 69d2 and a checkable proof is verified
below. Weaker Advanced values never replace accepted 69d2 rows. Each adopted
row takes the minimum of its re-verified donor bound and the accepted 641173
bound, so the certified T241 row is never relaxed to a shared T242.

K/Z split. K={d>0}, Z={d=0}, k+z=20, sigma_x=|N(x) in Z|, zeta_u=|N(u) in K|,
r=sum sigma=sum zeta. A K-Z edge uses a pair label: 0<=sigma_x<=min(z,6-d_x).
A zero ticket has six neighbours and at most z-1 in Z: max(0,7-z)<=zeta_u<=6.
In H=complement(G), M=H[K] and N=H[Z] have degrees m=k-7-d+sigma and
n=z-7+zeta. A mixed H-triangle has exactly one within-shore edge: an M edge xy
has z-sigma_x-sigma_y+c_Z(xy) apexes and an N edge uv k-zeta_u-zeta_v+c_K(uv),
c counting common G-neighbours on the other shore. Summing,
  T(H)=3z(k-11)+10r-sum sigma*m-sum zeta*n+P,
  P=T(M)+T(N)+sum_{E(M)} c_Z+sum_{E(N)} c_K,
so T(G)<=B-3z(k-11)-10r+sum sigma*m+sum zeta*n-P_lower for any P_lower<=P.

Necessary-condition relaxations (steps 3 and 4). Every sorted sigma inside
equal-d classes and every sorted zeta in range with graphical 6-zeta (the
degrees of G[Z]) is enumerated; m must be graphical (M is simple on K) and
sigma/zeta must satisfy Gale-Ryser with equal sums (the K-Z bipartite graph).
These conditions are necessary, and permuting equal-d core vertices or zero
vertices preserves every condition and score, so every legal realization maps
to a retained state. Step 3 uses P_lower=0. Step 4 adds four separately valid
lower bounds: an s-subset of a graph with degrees a spans at least
max(0, sum of the s smallest a - e) edges, and by double counting
sum_{E(N)} c_K=sum_x e(N[N(x) in Z]), sum_{E(M)} c_Z=sum_u e(M[N(u) in K]);
3T(F)>=sum a^2-|F|e; and for the h largest-degree vertices L,
e(F[L])>=ceil((sum_L a-sum_out min(h,a))/2), each such edge ij has at least
max(0,a_i+a_j-|F|) common neighbours, and the edge/apex count over L equals
3T(F[L]) plus the triangles with exactly two vertices in L, so
T(F)>=(sum of the ell smallest pair weights)-2C(h,3). Both domains are
regenerated here independently (zeta first, histogram sigma recursion,
Havel-Hakimi, Z-side Gale-Ryser, smallest-degree induced-edge form) and
compared with the immutable donor evidence: the canonical step-3 state SHA256
and the complete step-4 state lists, together with every maximum and argmax.
Together they hold 6044 retained states. Relaxation optima are not asserted
realizable.

Analytic step 5 (k=15, z=5, B=290). On 2<=zeta<=6, zeta(zeta-2)<=6zeta-12; with
sum zeta=r this gives T<=170+sum sigma(4-d+sigma). A convex quadratic on
[0,u] is at most max(0,u(4-d+u)), giving 0,0,4,12,24,40 for d=6,...,1. Each
of the three exact profiles totals 92, so T<=262 for every legal realization.

Route B. An outcome is a seven-label set with a distinguished label; a ticket
wins when it holds at least three of the seven. Winners' chosen three-subsets
use distinct label pairs (pair-linearity), so at most C(7,2)/3=7 tickets win,
and for r=0..7, 1[r>0]<=r-C(r,2)+C(r,3)-(4/7)C(r,4). Exact local outcome
counts, recomputed here from explicit tickets, give S1=372228640,
S2=63838600, open-wedge/pair-triangle/shared-triple weights 2800/20272/7000
(triples with at most one overlap contribute zero), and K4 weights 679 and
448 (with a contained triple). So S3=2800(W-3t)+20272(t-22)+7000*22. Each
neighbourhood non-edge spoils at most g_max-2 triples, giving
q>=ceil((J-(g_max-2)(W-3t))/4) K4s, J=sum C(g,3); a K4 contains at most one
triple support and contained K4s number at most floor(sum d(g-2)/3), so
S4>=max(floor_t, 679q-231min(q,A_max)), increasing in q. The bound at t is
ceil(S1-S2+S3-4*S4/7), with S4 a lower bound being subtracted. Every t from
22 to the cap is evaluated twice, by the frozen r32 evaluator and by an
independent Fraction recount, and compared term by term with sealed donor
or protected terms. floor_t is the frozen r28 floor 112, except two sealed
T264-only certificates (308560 for 66665555555421000000, 309183 for
66666555554411100000) that apply to t=264 alone. They enter only the old
envelopes; no new cap reaches 264. The old universal cap 264 of
66665555555421000000 is kept separate from its comparison-only argmax 263.
No S5 term is used anywhere.

Family. Exactly the adopted rows change among the 4647; every other row and
the entire cursor object stay byte-identical to 69d2. Independent scans of
S0 (69d2), S1 (641173) and S2 (this adoption) derive every maximum, tied
owner, gap and open count, and S2 is pointwise at most S1. Legal attainment
and the global optimum remain UNKNOWN; donor conditional dispositions and all
historical caveats are carried verbatim and never upgraded.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import heapq
import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from fractions import Fraction
from functools import cache
from itertools import combinations, combinations_with_replacement, pairwise
from math import ceil, comb, prod
from pathlib import Path
from typing import NamedTuple, cast

from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as route

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_ADVANCED_11ROW_EXACT_ADOPTION_R1"
OWNER_CONVERSATION_ID = "694777f6-5198-4c59-9ef7-633b736154de"
STEM = "b649_min_s2_advanced_11row_exact_adoption_r1"
SOURCE = f"src/lottolab/research/{STEM}.py"
TEST = f"tests/unit/test_{STEM}.py"
DIRECTORY = "docs/research/matrix-native-results/"
RESULT = DIRECTORY + STEM.replace("_", "-") + "-result.json"
R30_RESULT = DIRECTORY + "b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
R30_SHA = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
SIX_ROW_RESULT = DIRECTORY + "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
SIX_ROW_SHA = "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f"
INCUMBENT = 313263888
FIRST_T = 22
T264 = 264
MODEL = {"TICKETS": 20, "LABELS_PER_TICKET": 6, "TRIPLES": 22, "PAIRS": 27, "PAIR_LINEARITY": True}
# Frozen evaluator blobs exactly as pinned by the step-3 donor (identical in all lineages).
FROZEN_EVALUATOR_PINS = {
    "b649_k20_min_s2_route_b_current_owner_refinement_r32.py": (
        "d2bd52eaa53825fc138b95f42d06ec6152757ae25a70212b0674bf8ea311dc1d"
    ),
    "b649_k20_min_s2_current_cursor_class_owner_chase_r28.py": (
        "72d7462a4cf32ed6932e81c6e62819e351e4b289246fd0644e5696b70b832fb0"
    ),
    "b649_k20_min_s2_higher_order_closure_r2.py": (
        "6897c974fe9679f2ec567602522bb4c38c996275368b714c6a7fadedd66d6e45"
    ),
    "b649_k20_min_s2_dangerous_core_realizability_r5.py": (
        "ad2c524bcdb716af1f1f744435576376499e3f39c3a744aec613542c41964487"
    ),
    "b649_k20_min_s2_next_distinct_plateau_r10.py": (
        "7a5dab79591f1fa59c2012a55ab89d3711ec4fc93ddfeb05245260c0bbd92ffb"
    ),
    "b649_k20_min_s2_current_cursor_dynamic_family_max_r30.py": (
        "230cb455bb162f6c8ab428afbbc8e7d9cbc7ee3c88575ef247e8d57ae925acb5"
    ),
}
# Observed once at seal; the verifier never reads this mutable per-worktree file.
PROTECTED_JUDGE_REPORT = {
    "LOCATOR": (
        ".git/worktrees/B649_MIN_S2_AB_T242_T241_EXACT_FAMILY_AUTHORITY_R1/"
        "task-evidence/fresh-judge-report.md"
    ),
    "SHA256_OBSERVED_AT_SEAL": "216340c3d1cd2b7724571d95e4c7951d731fd48d04996dd10d53e83b98e12a3b",
    "FIRST_LINE_OBSERVED": "VERIFIED_WITH_CAVEATS",
    "JUDGED_TREE_OBSERVED": "8c2719af507006a74fd0f5f205d9fbb24c528994",
    "READ_BY_DETERMINISTIC_VERIFIER": False,
}
DISPOSITION_KEYS = (
    "TASK_STATUS",
    "PROJECTION_STATUS",
    "CANONICAL_AUTHORITY_CHANGED",
    "CONDITIONAL_PROJECTION_ONLY",
    "FRESH_FOCUSED_REVIEW",
    "FRESH_JUDGE",
    "PRIOR_REVIEW_CAVEAT",
    "UPSTREAM_PRIOR_REVIEW_CAVEAT_VERBATIM",
    "INHERITED_EXCLUSION_PRESERVED",
    "GLOBAL_OPTIMUM",
    "PREDICTION_GAIN_CLAIMED",
    "REMOTE_WRITE",
    "PRODUCTION_MUTATION",
)
# The proof method each Advanced step used for the rows it changed.
STEP_METHODS = {
    "STEP_2": "ACCEPTED_641173_CERTIFICATE",
    "STEP_3": "RELAXATION_WITHOUT_REMAINDER",
    "STEP_4": "RELAXATION_WITH_REMAINDER_LOWER_BOUNDS",
    "STEP_5": "ANALYTIC_ENDPOINT_CERTIFICATE",
}
REALIZABILITY = "NOT_ASSERTED; NECESSARY_CONDITION_RELAXATION"
type Document = dict[str, object]
type Degrees = tuple[int, ...]
type Term = tuple[int, int, int, int, int, int]
type Parts = tuple[tuple[int, ...], ...]


class Commit(NamedTuple):
    role: str
    head: str
    tree: str
    parent: str
    source: str
    source_sha: str
    test: str
    test_sha: str
    result: str
    result_sha: str


BASE = Commit(
    "BASE_69D2",
    "69d2d3fe2696623d75e876e5cd96085297da821c",
    "3fdfa51d658df73afadf6f16eaef145373a529ca",
    "2bdf3a6843800b1a1c818bd4e168585a7971611a",
    "src/lottolab/research/b649_min_s2_owner_655555555555410_t238_exact_authority_r1.py",
    "2df9eca4ee47c1d4e6db555f583c92126f0f550dbdb12cd47ac99ecfcdb878bd",
    "tests/unit/test_b649_min_s2_owner_655555555555410_t238_exact_authority_r1.py",
    "1941d06180e0d46164df1306dad00d3894f3443d7c46ed206e6842e1729f0fc3",
    DIRECTORY + "b649-min-s2-owner-655555555555410-t238-exact-authority-r1-result.json",
    "bad130a8b2ca045ba61884c969bae7d40d9b372f9d2a460e98163998f88aead1",
)
PROTECTED = Commit(
    "PROTECTED_641173",
    "641173e6307a03e24f7a4c026acb03eb4915229e",
    "8c2719af507006a74fd0f5f205d9fbb24c528994",
    BASE.head,
    "src/lottolab/research/b649_min_s2_ab_t242_t241_exact_family_authority_r1.py",
    "794b73876f2fd23fb70426ebae670713ba2bf7c0e2aceedfd6c3ca469afe356f",
    "tests/unit/test_b649_min_s2_ab_t242_t241_exact_family_authority_r1.py",
    "869cac90fd2f4ef434aedd5119eee44d1612ef065ad8012ccb0a9a6b9df337f1",
    DIRECTORY + "b649-min-s2-ab-t242-t241-exact-family-authority-r1-result.json",
    "f196fb11922feb30cf1bbe8b3ff7403a64d19a166a4d6a946be5a67eb6b5e4c6",
)
DONORS = (
    Commit(
        "STEP_1",
        "06664eeb1a7ecb8138e15f70bac32681f84bbf55",
        "11cf44e93cf921446118edf3b26127ff24e0fd49",
        "317210d56cac9efcb779e0967049302c74d7be77",
        "src/lottolab/research/b649_cursor_41_owner_shared_bound_r1.py",
        "c1e65bd5300fbd83be743e0a963622bd2686d23a855039cadadc6deb8f514e65",
        "tests/unit/test_b649_cursor_41_owner_shared_bound_r1.py",
        "61d3ed10d7c0b8b94c3a8da540a1a3a1e229978f8204ada63ccd3b32a8e79fa7",
        DIRECTORY + "b649-cursor-41-owner-shared-bound-r1-result.json",
        "f298983c96e321d5c4d1e5e3a53f127b2b730bf84d115ead4005dc63f2d8e148",
    ),
    Commit(
        "STEP_2",
        "600a9aadba5880088ffe2a69abf183b59819a860",
        "33d36fe2d183600a1557e842e2682df52a75419d",
        "06664eeb1a7ecb8138e15f70bac32681f84bbf55",
        "src/lottolab/research/b649_next_resolved_frontier_shared_bound_r1.py",
        "c93c5a421ebf78a208d47849b1198f3756092e17fbfa9cf7a1aa6a83f4e015a7",
        "tests/unit/test_b649_next_resolved_frontier_shared_bound_r1.py",
        "00b1167cc2accb7c5b4c878a871ca2d5193230786db7f786bbdd2dc5345c1e8a",
        DIRECTORY + "b649-next-resolved-frontier-shared-bound-r1-result.json",
        "073a27d95b399e1c2e3cb0bb1a3441157ebc1d0e45a7c9348000902494f546fa",
    ),
    Commit(
        "STEP_3",
        "0f0c9a32dbed811eddbefc55fd5093a8ee0e914d",
        "2092a1dc434e210f28455f9de3c59947217db889",
        "600a9aadba5880088ffe2a69abf183b59819a860",
        "src/lottolab/research/b649_next_frontier_three_profile_bound_r1.py",
        "7fe17d688b9d23fe971178f751c22558c8f4da156b82a4c50607db216bf63814",
        "tests/unit/test_b649_next_frontier_three_profile_bound_r1.py",
        "abb9ed01ec7ad6266a6b8c783d9c6f5f4d1174c4b970975e445938794e1f7180",
        DIRECTORY + "b649-next-frontier-three-profile-bound-r1-result.json",
        "9769ee3e125ce8b3e66b810f9683d28b9e93c06e601b36959f86c0d3a2812c76",
    ),
    Commit(
        "STEP_4",
        "204f668efe88ab71cb55df3e71cc12948252a450",
        "9b31b53b79a5ee012055e1c77e486ec05552088a",
        "0f0c9a32dbed811eddbefc55fd5093a8ee0e914d",
        "src/lottolab/research/b649_next_two_owner_shared_bound_r1.py",
        "40236da825592d922082827c5793c621e0f644c11e0bacdf40d0840372863100",
        "tests/unit/test_b649_next_two_owner_shared_bound_r1.py",
        "a42cea9382cd953980131e65705e819f8cd924f01959ec125184762ec5dca5d5",
        DIRECTORY + "b649-next-two-owner-shared-bound-r1-result.json",
        "a022ef35cd3e7b853e82179f7696d63cb29365d8811c40f6a2ab5d2a0f39e108",
    ),
    Commit(
        "STEP_5",
        "2159f5257e8c0742662bc087f4cf9bb275a515a5",
        "2018f025de0a5d47c0542bfa00cc5d8bba6ac8de",
        "204f668efe88ab71cb55df3e71cc12948252a450",
        "src/lottolab/research/b649_next_three_owner_cursor_floor_r1.py",
        "36832313285c6ee53f07e8a9ebda9fef0d630acfe0bc53c6262051c43ac1a979",
        "tests/unit/test_b649_next_three_owner_cursor_floor_r1.py",
        "fc74e32fe231405cebf46528db9d6ea54ab45f7a8d1e1249ab0aa961d1840f66",
        DIRECTORY + "b649-next-three-owner-cursor-floor-r1-result.json",
        "72fa2649bfb76174b52bef6161218b48e54a4413463bdb38d53280a6cf924a28",
    ),
)
COMMITS = (BASE, PROTECTED, *DONORS)


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def obj(value: object) -> Document:
    require(isinstance(value, dict), "expected object")
    return cast(Document, value)


def items(value: object) -> list[object]:
    require(isinstance(value, list), "expected list")
    return cast(list[object], value)


def integer(value: object) -> int:
    require(type(value) is int, "expected exact integer")
    return cast(int, value)


def ledger(value: object) -> dict[str, int]:
    return {p: integer(b) for p, b in obj(value).items()}


def parse(raw: bytes) -> Document:
    def unique(pairs: list[tuple[str, object]]) -> Document:
        require(len(pairs) == len(dict(pairs)), "duplicate JSON key")
        return dict(pairs)

    return obj(json.loads(raw, object_pairs_hook=unique))


def decode(raw: bytes) -> Document:
    value = parse(raw)
    require(render(value) == raw, "noncanonical result bytes")
    return value


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", "core.fsmonitor=false", *args],
        cwd=ROOT,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        stderr=subprocess.DEVNULL,
    )


def checked_blob(head: str, tree: str, path: str, digest: str) -> bytes:
    """Immutable Git bytes of one regular file, bound to commit, tree and SHA256."""

    require(re.fullmatch(r"[0-9a-f]{40}", head) is not None, "commit identity")
    require(git("cat-file", "-t", head).strip() == b"commit", "commit type")
    require(git("rev-parse", head + "^{tree}").decode().strip() == tree, "tree identity")
    require(not Path(path).is_absolute() and ".." not in Path(path).parts, "unsafe path")
    meta = git("ls-tree", head, "--", path).decode().strip().split("\t")
    require(
        len(meta) == 2 and meta[0].startswith("100644 blob ") and meta[1] == path,
        "missing or non-regular blob",
    )
    raw = git("cat-file", "blob", f"{head}:{path}")
    require(sha(raw) == digest, "source SHA256 mismatch")
    return raw


def commit_message(head: str) -> str:
    return git("cat-file", "commit", head).split(b"\n\n", 1)[1].decode()


def verify_candidate() -> None:
    head = git("rev-parse", "HEAD").decode().strip()
    if head == BASE.head:
        return
    parents = git("rev-list", "--parents", "-n", "1", head).decode().split()
    require(parents[1:] == [BASE.head], "candidate is not Base or its single local child")
    changed = git("diff-tree", "--no-commit-id", "--name-status", "-r", head).decode()
    require(
        sorted(changed.splitlines()) == sorted(f"A\t{p}" for p in (SOURCE, TEST, RESULT)),
        "candidate must add exactly the three task files",
    )


def commit_document(commit: Commit) -> Document:
    parents = git("rev-list", "--parents", "-n", "1", commit.head).decode().split()
    require(parents == [commit.head, commit.parent], "commit parent identity")
    checked_blob(commit.head, commit.tree, commit.source, commit.source_sha)
    checked_blob(commit.head, commit.tree, commit.test, commit.test_sha)
    doc = decode(checked_blob(commit.head, commit.tree, commit.result, commit.result_sha))
    require(
        doc["SOURCE_SHA256"] == commit.source_sha and doc["TEST_SHA256"] == commit.test_sha,
        "result source/test pins differ from immutable Git bytes",
    )
    return doc


@cache
def inputs() -> Mapping[str, Document]:
    verify_candidate()
    docs = {c.role: commit_document(c) for c in COMMITS}
    require((ROOT / BASE.result).read_bytes() == render(docs[BASE.role]), "Base working drift")
    base, protected = docs[BASE.role], docs[PROTECTED.role]
    require(base["MODEL"] == protected["MODEL"] == MODEL, "frozen support model")
    require(base["INCUMBENT"] == protected["INCUMBENT"] == INCUMBENT, "incumbent identity")
    return docs


def identities() -> Document:
    return {
        c.role: {
            "HEAD": c.head,
            "TREE": c.tree,
            "PARENT": c.parent,
            "SOURCE_PATH": c.source,
            "SOURCE_SHA256": c.source_sha,
            "TEST_PATH": c.test,
            "TEST_SHA256": c.test_sha,
            "RESULT_PATH": c.result,
            "RESULT_SHA256": c.result_sha,
        }
        for c in COMMITS
    }


def base_judge() -> Document:
    message = commit_message(BASE.head)
    report = (
        message.split("FRESH_JUDGE_REPORT_VERBATIM_BEGIN\n", 1)[1].split(
            "\nFRESH_JUDGE_REPORT_VERBATIM_END", 1
        )[0]
        + "\n"
    )
    declared = re.findall(r"(?m)^Judge-report-SHA256: ([0-9a-f]{64})$", message)
    require(
        declared == [sha(report.encode())]
        and BASE.tree in report
        and BASE.result_sha in report
        and "Fresh-context Judge: VERIFIED_WITH_CAVEATS" in message,
        "Base Judge binding",
    )
    return {
        "VERDICT": "VERIFIED_WITH_CAVEATS",
        "BINDING": "VERBATIM_REPORT_IN_IMMUTABLE_COMMIT_MESSAGE",
        "REPORT_SHA256": declared[0],
        "COMMIT_MESSAGE_SHA256": sha(message.encode()),
    }


def protected_judge() -> Document:
    message = commit_message(PROTECTED.head)
    lines = set(message.splitlines())
    require(
        {
            f"Scientific-Base: {BASE.head}",
            f"Candidate-tree: {PROTECTED.tree}",
            f"Result-SHA256: {PROTECTED.result_sha}",
            "Fresh-context Judge and task-scoped R15: per-worktree Git task-evidence.",
        }
        <= lines,
        "protected authority commit binding",
    )
    return {
        "VERDICT": "VERIFIED_WITH_CAVEATS",
        "BINDING": "COMMIT_MESSAGE_LOCATOR_AND_OBSERVED_PER_WORKTREE_REPORT",
        "COMMIT_MESSAGE_SHA256": sha(message.encode()),
        "REPORT": PROTECTED_JUDGE_REPORT,
    }


def donor_dispositions(docs: Mapping[str, Document]) -> Document:
    """Original donor statuses and review lines, verbatim; nothing is upgraded."""

    out: Document = {}
    for commit in DONORS:
        doc = docs[commit.role]
        require(
            doc["CANONICAL_AUTHORITY_CHANGED"] == "NO"
            and doc["PROJECTION_STATUS"] == "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION",
            "donor original conditional disposition",
        )
        lines = commit_message(commit.head).splitlines()
        out[commit.role] = {
            "HEAD": commit.head,
            "VERBATIM": {k: doc[k] for k in DISPOSITION_KEYS if k in doc},
            "COMMIT_MESSAGE_REVIEW_LINES": [
                line for line in lines if re.search("judge|review|caveat", line, re.IGNORECASE)
            ],
            "FRESH_JUDGE_ACCEPTANCE_CLAIMED_BY_THIS_TASK": "NO",
            "DISPOSITION_UPGRADED": False,
        }
    return out


def evaluator_closure() -> dict[str, str]:
    """SHA256 of every lottolab module the frozen r32 evaluator imports, from Base."""

    pending, pins = [route.__name__], dict[str, str]()
    while pending:
        module = pending.pop()
        relative = "src/" + module.replace(".", "/") + ".py"
        if relative in pins:
            continue
        raw = git("cat-file", "blob", f"{BASE.head}:{relative}")
        require((ROOT / relative).read_bytes() == raw, "frozen evaluator working drift")
        pins[relative] = sha(raw)
        package = module.rsplit(".", 1)[0]
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node, ast.ImportFrom):
                prefix = node.module or ""
                if node.level:
                    parts = package.split(".")
                    head = ".".join(parts[: len(parts) + 1 - node.level])
                    prefix = head + ("." + prefix if prefix else "")
                if prefix.startswith("lottolab"):
                    if node.module:
                        pending.append(prefix)
                    else:
                        pending.extend(prefix + "." + a.name for a in node.names)
            elif isinstance(node, ast.Import):
                pending.extend(a.name for a in node.names if a.name.startswith("lottolab"))
    for name, digest in FROZEN_EVALUATOR_PINS.items():
        require(pins.get("src/lottolab/research/" + name) == digest, "frozen evaluator pin")
    require(not any(m.startswith("ortools") for m in sys.modules), "heavy solver loaded")
    return dict(sorted(pins.items()))


# ----------------------------------------------------------------- exact profile facts


def degrees(pid: str) -> Degrees:
    require(len(pid) == 20 and set(pid) <= set("0123456"), "wrong profile encoding")
    d = tuple(map(int, pid))
    require(d == tuple(sorted(d, reverse=True)) and sum(d) == 66, "wrong exact degree profile")
    return d


def classes(pid: str) -> tuple[tuple[int, int, int], ...]:
    """(triple degree, multiplicity, sigma upper bound) for each core class, descending."""

    d = degrees(pid)
    z = d.count(0)
    counts = Counter(x for x in d if x)
    return tuple((x, counts[x], min(z, 6 - x)) for x in sorted(counts, reverse=True))


@cache
def facts(pid: str) -> Document:
    d = degrees(pid)
    g = [6 + x for x in d]
    k = sum(x > 0 for x in d)
    z = len(d) - k
    goodman = Fraction(2 * comb(20, 3) - sum(x * (19 - x) for x in g), 2)
    allowance = Fraction(sum(x * (x + 4) for x in d), 3)
    require(goodman.denominator == 1 and sum(g) == 186, "degree or Goodman identity")
    w = sum(comb(x, 2) for x in g)
    return {
        "PROFILE_ID": pid,
        "D": list(d),
        "G": list(g),
        "K": k,
        "Z": z,
        "E": sum(g) // 2,
        "W": w,
        "W_DIV_3": w // 3,
        "J": sum(comb(x, 3) for x in g),
        "G_MAX": max(g),
        "GOODMAN": goodman.numerator,
        "SPLIT_H_CONSTANT": 3 * z * (k - 11),
        "A_MAX": allowance.numerator // allowance.denominator,
        "SIGMA_UPPER_BY_D": {str(x): u for x, _, u in classes(pid)},
        "ZETA_RANGE": [max(0, 7 - z), 6],
    }


def validate_facts(pid: str, claimed: Mapping[str, object]) -> None:
    """Reject a certificate whose degree facts belong to another (e.g. adjacent) profile."""

    mine = facts(pid)
    aliases = {"W": ("W", "WEDGES"), "G_MAX": ("G_MAX",), "J": ("J",), "A_MAX": ("A_MAX",)}
    require(claimed.get("D") == mine["D"], "certificate degree profile mismatch")
    for key, names in (("GOODMAN", ("GOODMAN",)), *aliases.items()):
        for name in names:
            if name in claimed:
                require(claimed[name] == mine[key], "certificate degree facts mismatch")


# ------------------------------------------------------------- graph-degree conditions


def havel_hakimi(sequence: Sequence[int]) -> bool:
    remaining = sorted(sequence, reverse=True)
    if any(x < 0 or x >= len(remaining) for x in remaining):
        return False
    while remaining and remaining[0]:
        take = remaining.pop(0)
        if take > len(remaining):
            return False
        for i in range(take):
            remaining[i] -= 1
            if remaining[i] < 0:
                return False
        remaining.sort(reverse=True)
    return True


def gale_ryser_zero_side(zeta: Sequence[int], sigma: Sequence[int]) -> bool:
    """Bipartite K-Z realizability, checked from the zero shore."""

    if sum(zeta) != sum(sigma):
        return False
    ordered = sorted(zeta, reverse=True)
    return all(
        sum(ordered[:j]) <= sum(min(j, s) for s in sigma) for j in range(1, len(ordered) + 1)
    )


def induced_edge_floor(degree_list: Sequence[int], size: int) -> int:
    """Any `size` vertices span at least (sum of the `size` smallest degrees) - e edges."""

    require(0 <= size <= len(degree_list), "subset size")
    return max(0, sum(sorted(degree_list)[:size]) - sum(degree_list) // 2)


@cache
def triangle_floors(degree_list: Degrees) -> tuple[int, int]:
    """(square-sum floor, best floor including the h-largest prefix bound)."""

    a = sorted(degree_list, reverse=True)
    n, e = len(a), sum(a) // 2
    square = max(0, ceil(Fraction(sum(x * x for x in a) - n * e, 3)))
    best = square
    for h in range(1, n + 1):
        top = a[:h]
        ell = max(0, ceil(Fraction(sum(top) - sum(min(h, x) for x in a[h:]), 2)))
        weights = [max(0, x + y - n) for x, y in combinations(top, 2)]
        require(ell <= len(weights), "impossible necessary degree sequence")
        best = max(best, sum(heapq.nsmallest(ell, weights)) - 2 * comb(h, 3))
    return square, best


# --------------------------------------------------------------- relaxation regeneration


@cache
def zero_lists(z: int) -> tuple[Degrees, ...]:
    """Sorted zeta whose zero-shore degrees 6-zeta are graphical (Havel-Hakimi)."""

    low = max(0, 7 - z)
    return tuple(
        zeta
        for zeta in combinations_with_replacement(range(low, 7), z)
        if havel_hakimi([6 - x for x in zeta])
    )


@cache
def class_options(count: int, upper: int) -> Mapping[int, tuple[Degrees, ...]]:
    """Sorted sigma tuples of one equal-d class by histogram recursion, grouped by sum."""

    grouped: dict[int, list[Degrees]] = {}

    def visit(value: int, left: int, prefix: Degrees) -> None:
        if value > upper:
            if left == 0:
                grouped.setdefault(sum(prefix), []).append(prefix)
            return
        for times in range(left + 1):
            visit(value + 1, left - times, prefix + (value,) * times)

    visit(0, count, ())
    return {s: tuple(sorted(v)) for s, v in sorted(grouped.items())}


def sigma_parts(pid: str, total: int) -> Iterator[Parts]:
    options = [class_options(n, u) for _, n, u in classes(pid)]

    def visit(index: int, left: int, chosen: Parts) -> Iterator[Parts]:
        if index == len(options):
            if left == 0:
                yield chosen
            return
        for subtotal, tuples in options[index].items():
            if subtotal <= left:
                for option in tuples:
                    yield from visit(index + 1, left - subtotal, (*chosen, option))

    yield from visit(0, total, ())


def state_record(pid: str, parts: Parts, zeta: Degrees, remainder: bool) -> Document | None:
    f = facts(pid)
    k, z = integer(f["K"]), integer(f["Z"])
    ds = [x for x, n, _ in classes(pid) for _ in range(n)]
    sigma = [s for part in parts for s in part]
    m = tuple(k - 7 - x + s for x, s in zip(ds, sigma, strict=True))
    if not havel_hakimi(m) or not gale_ryser_zero_side(zeta, sigma):
        return None
    n = tuple(z - 7 + x for x in zeta)
    r = sum(sigma)
    sigma_score = sum(a * b for a, b in zip(sigma, m, strict=True))
    zeta_score = sum(a * b for a, b in zip(zeta, n, strict=True))
    raw = integer(f["GOODMAN"]) - integer(f["SPLIT_H_CONSTANT"]) - 10 * r + sigma_score + zeta_score
    record: Document = {
        "R": r,
        "SIGMA_BY_D": [[x, list(p)] for (x, _, _), p in zip(classes(pid), parts, strict=True)],
        "ZETA": list(zeta),
        "SIGMA_SCORE": sigma_score,
        "ZETA_SCORE": zeta_score,
    }
    if not remainder:
        record["UPPER"] = raw
        return record
    c_k = sum(induced_edge_floor(n, s) for s in sigma)
    c_z = sum(induced_edge_floor(m, q) for q in zeta)
    (m_square, m_best), (n_square, n_best) = triangle_floors(m), triangle_floors(n)
    record.update(
        {
            "M_DEGREES": list(m),
            "N_DEGREES": list(n),
            "REMAINDER_LOWER": {"T_M": m_best, "T_N": n_best, "C_K": c_k, "C_Z": c_z},
            "WITHOUT_REMAINDER": raw,
            "WITHOUT_PREFIX_TRIANGLE_BOUND": raw - c_k - c_z - m_square - n_square,
            "UPPER": raw - c_k - c_z - m_best - n_best,
        }
    )
    return record


@cache
def relaxation(pid: str, remainder: bool) -> Document:
    """Independent regeneration of a donor necessary-condition domain, in donor order."""

    z = integer(facts(pid)["Z"])
    keyed: list[tuple[tuple[Parts, Degrees], Document]] = []
    for zeta in zero_lists(z):
        for parts in sigma_parts(pid, sum(zeta)):
            record = state_record(pid, parts, zeta, remainder)
            if record is not None:
                keyed.append(((parts, zeta), record))
    keyed.sort(key=lambda item: item[0])
    states = [record for _, record in keyed]
    require(states, "empty necessary-condition relaxation")
    upper = [integer(s["UPPER"]) for s in states]
    cap = max(upper)
    per_r: dict[int, int] = {}
    for s, u in zip(states, upper, strict=True):
        per_r[integer(s["R"])] = max(per_r.get(integer(s["R"]), u), u)
    signatures = prod(comb(u + n, n) for _, n, u in classes(pid))
    require(
        signatures == prod(sum(map(len, class_options(n, u).values())) for _, n, u in classes(pid)),
        "sigma signature coverage",
    )
    value: Document = {
        "CAP": cap,
        "SIGMA_SIGNATURES": signatures,
        "ZETA_MULTISET_COUNT": len(zero_lists(z)),
        "RETAINED_STATE_COUNT": len(states),
        "STATES_SHA256": sha(render(states)),
        "ALL_ARGMAX": [s for s, u in zip(states, upper, strict=True) if u == cap],
        "PER_R_MAXIMUM": {str(r): per_r[r] for r in sorted(per_r)},
        "REALIZABILITY": REALIZABILITY,
    }
    if remainder:
        value["ALL_RETAINED_STATES"] = states
        value["ABLATION_CAPS"] = {
            key: max(integer(s[key]) for s in states)
            for key in ("WITHOUT_REMAINDER", "WITHOUT_PREFIX_TRIANGLE_BOUND", "UPPER")
        }
    return value


def relaxation_summary(pid: str, remainder: bool) -> Document:
    return {k: v for k, v in relaxation(pid, remainder).items() if k != "ALL_RETAINED_STATES"}


@cache
def analytic_certificate(pid: str) -> Document:
    f = facts(pid)
    require(
        (f["K"], f["Z"], f["GOODMAN"], f["ZETA_RANGE"]) == (15, 5, 290, [2, 6]),
        "analytic split premises",
    )
    require(all(q * (q - 2) <= 6 * q - 12 for q in range(2, 7)), "zeta chord")
    contributions: Document = {}
    for x, count, upper in classes(pid):
        values = [s * (4 - x + s) for s in range(upper + 1)]
        best = max(values)
        require(best == max(0, upper * (4 - x + upper)), "convex endpoint maximum")
        contributions[str(x)] = {
            "COUNT": count,
            "SIGMA_RANGE": [0, upper],
            "ENDPOINTS": [0, upper * (4 - x + upper)],
            "MAXIMUM": best,
            "ALL_ARGMAX": [s for s, v in enumerate(values) if v == best],
            "TOTAL": count * best,
        }
    constant = integer(f["GOODMAN"]) - integer(f["SPLIT_H_CONSTANT"]) - 12 * integer(f["Z"])
    total = sum(integer(obj(c)["TOTAL"]) for c in contributions.values())
    return {
        "CONSTANT": constant,
        "SIGMA_ENDPOINT_CONTRIBUTIONS": contributions,
        "ZETA_CHORD": {
            "RANGE": [2, 6],
            "SLOPE": 6,
            "INTERCEPT": -12,
            "ALL_ARGMAX": [q for q in range(2, 7) if q * (q - 2) == 6 * q - 12],
        },
        "CAP": constant + total,
        "REMAINDER_LOWER": {"T_M": 0, "T_N": 0, "C_K": 0, "C_Z": 0},
        "REMAINDER_DIRECTION": "subtract 0 <= P, hence increase the G upper bound",
        "REALIZABILITY": "NOT_ASSERTED; INDEPENDENT_ENDPOINT_RELAXATION",
    }


@cache
def analytic_box_maximum(pid: str) -> int:
    """Finite check of the analytic chain over its whole sorted capacity box."""

    f = facts(pid)
    constant = integer(f["GOODMAN"]) - integer(f["SPLIT_H_CONSTANT"])
    ds = [x for x, n, _ in classes(pid) for _ in range(n)]
    best = -(10**9)
    for zeta in combinations_with_replacement(range(2, 7), integer(f["Z"])):
        zeta_score = sum(q * (q - 2) for q in zeta)
        for parts in sigma_parts(pid, sum(zeta)):
            sigma = [s for part in parts for s in part]
            score = sum(s * (8 - x + s) for x, s in zip(ds, sigma, strict=True))
            best = max(best, constant - 10 * sum(zeta) + score + zeta_score)
    return best


# ------------------------------------------------------------------- Route-B envelope


def outcome_weight(tickets: Sequence[frozenset[int]]) -> int:
    """Outcomes (seven of 49 labels, one distinguished) on which every ticket wins."""

    require(all(len(t) == 6 for t in tickets), "six-label tickets")
    masks = Counter(sum(1 << i for i, t in enumerate(tickets) if x in t) for x in range(49))
    groups = sorted(masks.items())

    def visit(index: int, left: int, hits: Degrees) -> int:
        if index == len(groups):
            return int(left == 0 and all(h >= 3 for h in hits))
        mask, size = groups[index]
        total = 0
        for take in range(min(size, left) + 1):
            new = tuple(h + take * (mask >> i & 1) for i, h in enumerate(hits))
            total += comb(size, take) * visit(index + 1, left - take, new)
        return total

    return 7 * visit(0, 7, (0,) * len(tickets))


@cache
def local_weights() -> Document:
    def tickets(*labels: Sequence[int]) -> list[frozenset[int]]:
        return [frozenset(x) for x in labels]

    def check_linear(ts: Sequence[frozenset[int]]) -> None:
        require(all(len(a & b) <= 1 for a, b in combinations(ts, 2)), "pair-linear motif")

    motifs = {
        "ONE": tickets(range(6)),
        "DISJOINT": tickets(range(6), range(6, 12)),
        "SHARED": tickets(range(6), (0, 6, 7, 8, 9, 10)),
        "OPEN_WEDGE": tickets(range(6), (0, 6, 7, 8, 9, 10), (1, 11, 12, 13, 14, 15)),
        "PAIR_TRIANGLE": tickets((0, 1, 3, 4, 5, 6), (0, 2, 7, 8, 9, 10), (1, 2, 11, 12, 13, 14)),
        "SHARED_TRIPLE": tickets(range(6), (0, 6, 7, 8, 9, 10), (0, 11, 12, 13, 14, 15)),
        "K4_PAIR": tickets(
            (0, 1, 2, 6, 7, 8), (0, 3, 4, 9, 10, 11), (1, 3, 5, 12, 13, 14), (2, 4, 5, 15, 16, 17)
        ),
        "K4_WITH_TRIPLE": tickets(
            (0, 1, 4, 5, 6, 7), (0, 2, 8, 9, 10, 11), (0, 3, 12, 13, 14, 15), (1, 2, 3, 16, 17, 18)
        ),
        "ONE_EDGE_TRIPLE": tickets(range(6), (0, 6, 7, 8, 9, 10), range(11, 17)),
        "EMPTY_TRIPLE": tickets(range(6), range(6, 12), range(12, 18)),
    }
    for ts in motifs.values():
        check_linear(ts)
    w = {name: outcome_weight(ts) for name, ts in motifs.items()}
    edges, pairs = 93, comb(20, 2)
    s1, s2 = 20 * w["ONE"], (pairs - edges) * w["DISJOINT"] + edges * w["SHARED"]
    require(w["ONE_EDGE_TRIPLE"] == w["EMPTY_TRIPLE"] == 0, "sparse triples contribute zero")
    require(3 * 7 <= comb(7, 2) < 3 * 8, "at most seven winners per outcome")
    for q in range(8):
        require(
            Fraction(int(q > 0)) <= q - comb(q, 2) + comb(q, 3) - Fraction(4 * comb(q, 4), 7),
            "Bonferroni-4 polynomial",
        )
    value: Document = {
        "S1": s1,
        "S2": s2,
        "OPEN_WEDGE": w["OPEN_WEDGE"],
        "PAIR_TRIANGLE": w["PAIR_TRIANGLE"],
        "SHARED_TRIPLE": w["SHARED_TRIPLE"],
        "K4_PAIR": w["K4_PAIR"],
        "K4_WITH_TRIPLE": w["K4_WITH_TRIPLE"],
        "SPARSE_TRIPLES": [w["ONE_EDGE_TRIPLE"], w["EMPTY_TRIPLE"]],
        "MAX_WINNERS_PER_OUTCOME": 7,
        "BONFERRONI_POLYNOMIAL_CHECKED_R": list(range(8)),
    }
    require(
        [value[k] for k in ("S1", "S2", "OPEN_WEDGE", "PAIR_TRIANGLE", "SHARED_TRIPLE")]
        == [372228640, 63838600, 2800, 20272, 7000]
        and (value["K4_PAIR"], value["K4_WITH_TRIPLE"]) == (679, 448),
        "exact local weights",
    )
    return value


def base_s4_floor(pid: str) -> int:
    floor = route.r28.profile_s4_floor(degrees(pid))
    require(floor == 112, "frozen r28 S4 floor drift")
    return floor


def frozen_terms(pid: str, cap: int, special: Mapping[int, int]) -> list[Term]:
    d = degrees(pid)
    a_max = route.contained_triple_k4_cap(d)
    base = base_s4_floor(pid)
    return [
        cast(Term, tuple(route.envelope_term(d, t, max(base, special.get(t, 0)), a_max)))
        for t in range(FIRST_T, cap + 1)
    ]


def fraction_terms(pid: str, cap: int, special: Mapping[int, int]) -> list[Term]:
    f, w = facts(pid), local_weights()
    wedges, j, top = integer(f["W"]), integer(f["J"]), integer(f["G_MAX"])
    a_max, base = integer(f["A_MAX"]), base_s4_floor(pid)
    terms: list[Term] = []
    for t in range(FIRST_T, cap + 1):
        opened = wedges - 3 * t
        require(opened >= 0, "triangle count beyond the wedge identity")
        q = max(0, ceil(Fraction(j - (top - 2) * opened, 4)))
        contained = min(q, a_max)
        credit = integer(w["K4_WITH_TRIPLE"]) * contained + integer(w["K4_PAIR"]) * (q - contained)
        s4 = max(base, special.get(t, 0), credit)
        s3 = (
            integer(w["OPEN_WEDGE"]) * opened
            + integer(w["PAIR_TRIANGLE"]) * (t - FIRST_T)
            + integer(w["SHARED_TRIPLE"]) * FIRST_T
        )
        exact = Fraction(integer(w["S1"]) - integer(w["S2"]) + s3) - Fraction(4 * s4, 7)
        terms.append((t, ceil(exact), q, contained, s4, s3))
    return terms


def envelope(pid: str, cap: int, special: Mapping[int, int]) -> list[Term]:
    require(type(cap) is int and FIRST_T <= cap <= integer(facts(pid)["W_DIV_3"]), "T-cap domain")
    terms = frozen_terms(pid, cap, special)
    require(terms == fraction_terms(pid, cap, special), "integer/Fraction evaluator disagreement")
    return terms


def as_lists(terms: Sequence[Term]) -> list[list[int]]:
    return [list(t) for t in terms]


def same_terms(terms: Sequence[Term], sealed: object) -> bool:
    return as_lists(terms) == items(sealed)


def top(terms: Sequence[Term]) -> int:
    return max(t[1] for t in terms)


# --------------------------------------------------------- old caps and T264 S4 scope


@cache
def r30_attempts() -> tuple[Document, ...]:
    raw = checked_blob(BASE.head, BASE.tree, R30_RESULT, R30_SHA)
    require((ROOT / R30_RESULT).read_bytes() == raw, "R30 working drift")
    return tuple(obj(a) for a in items(parse(raw)["GROUP_ATTEMPTS"]))


def old_cap(pid: str) -> Document:
    """Universal old cap: the tightest accepted exact-profile R30 refutation."""

    found = [
        a
        for a in r30_attempts()
        if a.get("PROFILE_IDS") == [pid] and a.get("STATUS") == "INFEASIBLE"
    ]
    require(found, "missing exact-profile R30 refutation")
    cap = min(integer(a["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"]) for a in found)
    proof = next(a for a in found if a["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == cap)
    require(route.r28.r26.accepted_cap(proof, (degrees(pid),), cap) == cap, "R30 not accepted")
    return {
        "OLD_UNIVERSAL_T_CAP": cap,
        "SOURCE": f"{R30_RESULT}:GROUP_ATTEMPTS[{integer(proof['ATTEMPT_INDEX'])}]",
        "REFUTED_T": integer(proof["REFUTED_GRAPH_TRIANGLE_COUNT"]),
        "CERTIFICATE_KIND": proof["CERTIFICATE_KIND"],
    }


@cache
def t264_certificates() -> Mapping[str, Document]:
    """The two sealed T264-only S4 certificates of the Base tree, verbatim."""

    raw = checked_blob(BASE.head, BASE.tree, SIX_ROW_RESULT, SIX_ROW_SHA)
    require((ROOT / SIX_ROW_RESULT).read_bytes() == raw, "six-row working drift")
    doc = parse(raw)
    f = obj(doc["CERTIFICATE_F"])
    four = obj(obj(doc["PRESERVED_FIVE_ROW_AUTHORITY"])["PRESERVED_FOUR_ROW_AUTHORITY"])
    envelope_four = obj(four["PROFILE_ENVELOPE"])
    require(
        f["STATUS"] == "PASS" and f["LOAD_BEARING_T"] == T264 and f["TRIANGLE_CAP"] == T264,
        "Certificate F scope",
    )
    require(
        four["T264_S4_AUTHORITY"] == "PASS" and len(items(four["CHANGED_ROW_IDS"])) == 1,
        "four-row T264 certificate scope",
    )
    return {
        cast(str, f["PROFILE_ID"]): {
            "T": T264,
            "S4_FLOOR": integer(f["NEW_S4_FLOOR"]),
            "SOURCE": SIX_ROW_RESULT + ":/CERTIFICATE_F",
            "SEALED_TERMS": f["ALL_T_TERMS"],
            "SEALED_PROFILE_BOUND": integer(f["CERTIFIED_PROFILE_BOUND"]),
        },
        cast(str, items(four["CHANGED_ROW_IDS"])[0]): {
            "T": T264,
            "S4_FLOOR": integer(four["T264_S4_FLOOR"]),
            "SOURCE": SIX_ROW_RESULT
            + ":/PRESERVED_FIVE_ROW_AUTHORITY/PRESERVED_FOUR_ROW_AUTHORITY",
            "SEALED_TERMS": envelope_four["ALL_T_TERMS"],
            "SEALED_PROFILE_BOUND": integer(four["PROFILE_BOUND_AFTER"]),
            "SEALED_ARGMAX_T": integer(envelope_four["ARGMAX_T"]),
        },
    }


def scoped_floors(pid: str, cap: int) -> dict[int, int]:
    """T-specific S4 floors valid for this exact profile inside [22, cap], and nowhere else."""

    cert = t264_certificates().get(pid)
    if cert is None or integer(cert["T"]) > cap:
        return {}
    return {integer(cert["T"]): integer(cert["S4_FLOOR"])}


def validate_s4_scope(pid: str, cap: int, special: Mapping[int, int]) -> None:
    require(dict(special) == scoped_floors(pid, cap), "S4 floor scope leakage")


def validate_terms(pid: str, cap: int, special: Mapping[int, int], terms: object) -> None:
    validate_s4_scope(pid, cap, special)
    require(same_terms(envelope(pid, cap, special), terms), "incomplete T terms or rounding")


def validate_old_cap(pid: str, claimed_universal: int) -> None:
    """An argmax location never substitutes for the universal old cap."""

    require(
        claimed_universal == old_cap(pid)["OLD_UNIVERSAL_T_CAP"], "universal/effective cap swap"
    )


def old_record(pid: str, base_bound: int) -> Document:
    cap_record = old_cap(pid)
    cap = integer(cap_record["OLD_UNIVERSAL_T_CAP"])
    special = scoped_floors(pid, cap)
    terms = envelope(pid, cap, special)
    bound = top(terms)
    require(bound == base_bound, "old envelope does not reproduce the Base row")
    cert = t264_certificates().get(pid)
    if cert is not None:
        require(
            same_terms(terms, cert["SEALED_TERMS"]) and cert["SEALED_PROFILE_BOUND"] == bound,
            "sealed T264 envelope replay",
        )
    argmax = [t[0] for t in terms if t[1] == bound]
    return {
        **cap_record,
        "OLD_T264_ONLY_S4_FLOORS": {str(t): v for t, v in special.items()},
        "OLD_T264_ONLY_SOURCE": None if cert is None else cert["SOURCE"],
        "OLD_EFFECTIVE_ARGMAX_T_COMPARISON_ONLY": argmax,
        "EFFECTIVE_ARGMAX_IS_A_UNIVERSAL_CAP": False,
        "OLD_TERMS": as_lists(terms),
        "OLD_TERM_COUNT": len(terms),
        "OLD_FULL_PROFILE_BOUND": bound,
    }


# ----------------------------------------------------------------- donor certificates


def step_documents(docs: Mapping[str, Document]) -> list[tuple[str, Document]]:
    return [(c.role, docs[c.role]) for c in DONORS]


def advanced_chain(docs: Mapping[str, Document]) -> list[tuple[str, dict[str, int]]]:
    """Replay each donor ledger link: before(k) must equal after(k-1)."""

    steps = step_documents(docs)
    first = steps[0][1]
    require(first["RESOLVED_ROWS_CHANGED"] == 0, "step 1 changes no resolved row")
    chain = [(steps[0][0], ledger(first["RESOLVED_ROW_BOUNDS"]))]
    for role, doc in steps[1:]:
        before, after = ledger(doc["RESOLVED_ROWS_BEFORE"]), ledger(doc["RESOLVED_ROWS_AFTER"])
        require(before == chain[-1][1], "Advanced ledger chain break")
        changed = sorted(p for p in before if before[p] != after[p])
        declared = doc["RESOLVED_ROWS_CHANGED"]
        require(
            declared == changed if isinstance(declared, list) else declared == len(changed),
            "declared donor row changes",
        )
        chain.append((role, after))
    return chain


def select_candidates(
    base_rows: Mapping[str, int], advanced: Mapping[str, int]
) -> tuple[list[str], list[str]]:
    """(strict improvements, weaker values) of the Advanced ledger against Base."""

    require(set(base_rows) == set(advanced), "ledger coverage")
    differing = [p for p in sorted(base_rows) if base_rows[p] != advanced[p]]
    strict = [p for p in differing if advanced[p] < base_rows[p]]
    weaker = [p for p in differing if advanced[p] > base_rows[p]]
    return strict, weaker


def donor_step(pid: str, chain: Sequence[tuple[str, Mapping[str, int]]]) -> str:
    changed = [role for (_, before), (role, after) in pairwise(chain) if before[pid] != after[pid]]
    return changed[-1] if changed else "ADVANCED_INPUT_LEDGER_06664EEB"


def step_three_record(pid: str, doc: Document) -> Document:
    profiles = obj(doc["PROFILES"])
    donor = obj(profiles[pid])
    validate_facts(pid, obj(donor["FACTS"]))
    mine = relaxation_summary(pid, False)
    require(render(mine) == render(donor["RELAXATION"]), "step-3 domain recount mismatch")
    shared = max(
        integer(relaxation_summary(p, False)["CAP"]) for p in cast(list[str], doc["PROFILE_ORDER"])
    )
    require(shared == integer(donor["NEW_SHARED_CAP"]), "derived shared cap")
    return {
        "PROOF_STATUS": "UNIVERSAL_NECESSARY_CONDITION_RELAXATION_INDEPENDENTLY_RECOUNTED",
        "PROFILE_RELAXATION_CAP": mine["CAP"],
        "APPLIED_T_CAP": shared,
        "APPLIED_CAP_VALIDITY": "shared cap >= this profile's own universal relaxation cap",
        "RELAXATION": mine,
        "DONOR_OLD_EFFECTIVE_CAP_COMPARISON_ONLY": donor["OLD_EFFECTIVE_CAP_COMPARISON_ONLY"],
    }


def step_four_record(pid: str, doc: Document, old: int) -> Document:
    donor = obj(obj(doc["PROFILES"])[pid])
    validate_facts(pid, obj(donor["FACTS"]))
    mine = relaxation(pid, True)
    require(render(mine) == render(donor["RELAXATION"]), "step-4 domain recount mismatch")
    cap = min(old, integer(mine["CAP"]), integer(facts(pid)["W_DIV_3"]))
    require(cap == donor["NEW_CAP"] and old == donor["OLD_CAP"], "step-4 cap identity")
    return {
        "PROOF_STATUS": "UNIVERSAL_NECESSARY_CONDITION_RELAXATION_INDEPENDENTLY_RECOUNTED",
        "PROFILE_RELAXATION_CAP": mine["CAP"],
        "APPLIED_T_CAP": cap,
        "APPLIED_CAP_VALIDITY": "min(old universal cap, relaxation cap, floor(W/3))",
        "RELAXATION": relaxation_summary(pid, True),
    }


def step_five_record(pid: str, doc: Document, old: int) -> Document:
    donor = obj(obj(doc["PROFILES"])[pid])
    validate_facts(pid, obj(donor["FACTS"]))
    mine = analytic_certificate(pid)
    require(render(mine) == render(donor["ANALYTIC_CERTIFICATE"]), "analytic certificate")
    box = analytic_box_maximum(pid)
    require(box <= integer(mine["CAP"]), "analytic inequality chain violated on its box")
    cap = min(old, integer(mine["CAP"]), integer(facts(pid)["W_DIV_3"]))
    require(cap == donor["NEW_CAP"] and old == donor["OLD_CAP"], "step-5 cap identity")
    return {
        "PROOF_STATUS": "UNIVERSAL_ANALYTIC_ENDPOINT_CERTIFICATE_REVERIFIED",
        "PROFILE_RELAXATION_CAP": mine["CAP"],
        "APPLIED_T_CAP": cap,
        "APPLIED_CAP_VALIDITY": "min(old universal cap, analytic cap, floor(W/3))",
        "ANALYTIC_CERTIFICATE": mine,
        "BOX_MAXIMUM_BEFORE_ENDPOINT_RELAXATION": box,
    }


def protected_record(pid: str, docs: Mapping[str, Document]) -> Document:
    """641173's accepted cap (not re-proved) and the donor's shared-cap corroboration."""

    certified = obj(obj(docs[PROTECTED.role]["PROFILES"])[pid])
    validate_facts(pid, obj(certified["FACTS"]))
    cap = integer(certified["NEW_T_CAP"])
    require(
        obj(certified["TRIANGLE_PROOF"])["UNIVERSAL_T_CAP"] == cap
        and certified["CURRENT_T_CAP"] == T264,
        "protected certificate identity",
    )
    donor_doc = docs["STEP_2"]
    donor = obj(obj(donor_doc["PROFILES"])[pid])
    shared = integer(donor["NEW_SHARED_T_CAP"])
    donor_caps = obj(obj(donor_doc["PER_PROFILE_OLD_NEW_CAP"])[pid])
    require(donor_caps["PROFILE_RELAXATION_CAP"] == cap and shared >= cap, "donor corroboration")
    shared_terms = envelope(pid, shared, {})
    require(same_terms(shared_terms, donor["NEW_ALL_T_TERMS"]), "donor shared-cap terms")
    require(top(shared_terms) == donor["NEW_ROW_BOUND"], "donor shared-cap bound")
    return {
        "PROOF_STATUS": (
            "ACCEPTED_641173_VERIFIED_WITH_CAVEATS; CAP_NOT_REPROVED; ROUTE_B_RECOUNTED"
        ),
        "PROFILE_RELAXATION_CAP": cap,
        "APPLIED_T_CAP": cap,
        "APPLIED_CAP_VALIDITY": "641173 universal cap, Fresh Judge VERIFIED_WITH_CAVEATS",
        "PROTECTED_DOMAIN_SHA256": obj(certified["TRIANGLE_PROOF"])["DOMAIN_SHA256"],
        "DONOR_SHARED_T_CAP": shared,
        "DONOR_SHARED_CAP_BOUND": top(shared_terms),
        "PROTECTED_TERMS_REPLAYED": same_terms(envelope(pid, cap, {}), certified["NEW_T_TERMS"]),
    }


def row_certificate(
    pid: str,
    step: str,
    docs: Mapping[str, Document],
    base_rows: Mapping[str, int],
    protected_rows: Mapping[str, int],
    advanced: Mapping[str, int],
) -> Document:
    require(step in STEP_METHODS, "row without a verifiable proof source")
    old = old_record(pid, base_rows[pid])
    old_cap_value = integer(old["OLD_UNIVERSAL_T_CAP"])
    doc = docs[step]
    scope = doc["FRONTIER_OWNER_IDS"] if step == "STEP_2" else doc["PROFILE_ORDER"]
    require(pid in cast(list[str], scope), "row not in its donor's scope")
    if step == "STEP_2":
        proof = protected_record(pid, docs)
    elif step == "STEP_3":
        proof = step_three_record(pid, doc)
    elif step == "STEP_4":
        proof = step_four_record(pid, doc, old_cap_value)
    else:
        proof = step_five_record(pid, doc, old_cap_value)
    cap = integer(proof["APPLIED_T_CAP"])
    require(cap < old_cap_value, "new cap must tighten the old universal cap")
    special = scoped_floors(pid, cap)
    require(not special, "a T264-only floor cannot enter a new envelope below 264")
    terms = envelope(pid, cap, special)
    bound = top(terms)
    if step == "STEP_2":
        certified = obj(obj(docs[PROTECTED.role]["PROFILES"])[pid])
        require(proof["PROTECTED_TERMS_REPLAYED"] is True, "protected terms replay")
        require(bound == certified["NEW_FULL_BOUND"] == protected_rows[pid], "protected bound")
        donor_bound = integer(proof["DONOR_SHARED_CAP_BOUND"])
    else:
        donor = obj(obj(doc["PROFILES"])[pid])
        require(same_terms(terms, donor["NEW_ALL_T_TERMS"]), "donor new terms")
        sealed_old = items(donor["OLD_ALL_T_TERMS"])
        require(
            len(sealed_old) <= len(items(old["OLD_TERMS"]))
            and items(old["OLD_TERMS"])[: len(sealed_old)] == sealed_old,
            "donor old terms",
        )
        donor_bound = integer(donor["NEW_BOUND"])
        require(bound == donor_bound, "donor bound")
    require(donor_bound == advanced[pid] < base_rows[pid], "strict donor improvement")
    adopted = min(bound, donor_bound, protected_rows[pid])
    require(adopted < base_rows[pid] and adopted <= protected_rows[pid], "non-regression")
    if adopted < donor_bound:
        source = f"{PROTECTED.role} (donor {step} value {donor_bound} rejected as weaker)"
    elif adopted < protected_rows[pid]:
        source = f"{step} {doc['TASK_ID']}"
    else:
        source = f"{PROTECTED.role}; {step} identical"
    return {
        "PROFILE_ID": pid,
        "FACTS": facts(pid),
        "BASE_BOUND": base_rows[pid],
        "PROTECTED_BOUND": protected_rows[pid],
        "DONOR_STEP": step,
        "DONOR_HEAD": next(c.head for c in DONORS if c.role == step),
        "DONOR_BOUND": donor_bound,
        "METHOD": STEP_METHODS[step],
        **proof,
        "OLD": old,
        "VALID_S4_SCOPE": {
            "BASE_FLOOR_ALL_NEW_T": base_s4_floor(pid),
            "BASE_FLOOR_SOURCE": "frozen r28.profile_s4_floor",
            "NEW_T_SPECIFIC_FLOORS": {},
            "OLD_T264_ONLY_FLOORS": old["OLD_T264_ONLY_S4_FLOORS"],
            "S5_ADOPTED": False,
        },
        "NEW_TERMS": as_lists(terms),
        "NEW_TERM_COUNT": len(terms),
        "NEW_ARGMAX": as_lists([t for t in terms if t[1] == bound]),
        "FULL_PROFILE_BOUND": bound,
        "ADOPTED_BOUND": adopted,
        "ACTUAL_SOURCE": source,
        "ROW_DELTA_VS_BASE": base_rows[pid] - adopted,
        "FRACTIONAL_S4_CREDIT_TERMS": sum((4 * t[4]) % 7 != 0 for t in terms),
        "LEGAL_ATTAINMENT": "UNKNOWN",
    }


# ---------------------------------------------------------------------- Family replay


def base_ledger(docs: Mapping[str, Document]) -> tuple[dict[str, int], Document]:
    base = docs[BASE.role]
    rows = ledger(base["RESOLVED_ROW_BOUNDS"])
    cursor = obj(base["CURSOR"])
    bounds = ledger(cursor["COARSE_BOUND_PROJECTION"])
    ids = cast(list[str], cursor["PROFILE_IDS"])
    require(
        len(rows) == 4647
        and len(bounds) == len(ids) == len(set(ids)) == 197
        and set(ids) == set(bounds)
        and not set(rows) & set(bounds),
        "ledger/cursor coverage",
    )
    return rows, cursor


def family(rows: Mapping[str, int], cursor: Mapping[str, object]) -> Document:
    bounds = ledger(cursor["COARSE_BOUND_PROJECTION"])
    require(len(rows) == 4647 and len(bounds) == 197 and not set(rows) & set(bounds), "coverage")
    best, owners, opened = -1, list[str](), 0
    for p, b in (*rows.items(), *bounds.items()):
        if b > best:
            best, owners = b, [p]
        elif b == best:
            owners.append(p)
        opened += int(b > INCUMBENT)
    ordered = sorted((*rows.items(), *bounds.items()), key=lambda row: (-row[1], row[0]))
    require(
        (best, sorted(owners), opened)
        == (
            ordered[0][1],
            [p for p, b in ordered if b == ordered[0][1]],
            sum(b > INCUMBENT for _, b in ordered),
        ),
        "independent family scan",
    )
    levels = sorted({b for _, b in ordered}, reverse=True)
    resolved_top = max(rows.values())
    return {
        "FAMILY_BOUND": best,
        "OWNER_IDS": sorted(owners),
        "OWNER_COUNT": len(owners),
        "OWNER_CURSOR_COUNT": sum(p in bounds for p in owners),
        "OWNER_W": sorted({wedge_count(p) for p in owners}),
        "GAP_TO_INCUMBENT": best - INCUMBENT,
        "STILL_OPEN_PROFILE_COUNT": opened,
        "NEXT_DISTINCT_BOUND": levels[1],
        "RESOLVED_MAXIMUM": resolved_top,
        "RESOLVED_MAXIMUM_OWNERS": sorted(p for p, b in rows.items() if b == resolved_top),
        "CURSOR_MAXIMUM": max(bounds.values()),
    }


def wedge_count(pid: str) -> int:
    return sum(comb(6 + int(c), 2) for c in pid)


def apply_adoption(
    rows: Sequence[tuple[str, int]],
    cursor: Mapping[str, object],
    updates: Sequence[tuple[str, int]],
    certified: Mapping[str, int],
) -> dict[str, int]:
    """Replace exactly the certified rows; reject duplicates, gaps, weaker or foreign rows."""

    base_rows, frozen = base_ledger(inputs())
    require(
        len(rows) == len(dict(rows)) == len(base_rows) and dict(rows) == base_rows,
        "duplicate or missing ledger row",
    )
    require(render(cursor) == render(frozen), "cursor mutation")
    require(len(updates) == len(dict(updates)), "duplicate row update")
    require(set(dict(updates)) == set(certified), "wrong or missing adopted profile")
    for pid, bound in updates:
        require(bound == certified[pid], "update differs from the certified bound")
        require(bound < base_rows[pid], "weaker donor value cannot replace an accepted row")
    after = {**base_rows, **dict(updates)}
    require(
        sorted(p for p in base_rows if after[p] != base_rows[p]) == sorted(certified),
        "exact row replacement",
    )
    return after


def compute_result() -> Document:
    docs = inputs()
    base_rows, cursor = base_ledger(docs)
    protected_rows = ledger(docs[PROTECTED.role]["RESOLVED_ROW_BOUNDS"])
    require(set(protected_rows) == set(base_rows), "protected ledger coverage")
    require(render(docs[PROTECTED.role]["CURSOR"]) == render(cursor), "protected cursor")
    pins = evaluator_closure()
    chain = advanced_chain(docs)
    advanced = chain[-1][1]
    strict, weaker = select_candidates(base_rows, advanced)
    certificates = {
        p: row_certificate(p, donor_step(p, chain), docs, base_rows, protected_rows, advanced)
        for p in strict
    }
    certified = {p: integer(c["ADOPTED_BOUND"]) for p, c in certificates.items()}
    rejected = [
        {
            "PROFILE_ID": p,
            "BASE_BOUND": base_rows[p],
            "DONOR_BOUND": advanced[p],
            "DONOR_SOURCE": donor_step(p, chain),
            "PROTECTED_BOUND": protected_rows[p],
            "DISPOSITION": "REJECTED_WEAKER_THAN_ACCEPTED_BASE",
        }
        for p in weaker
    ]
    after = apply_adoption(sorted(base_rows.items()), cursor, sorted(certified.items()), certified)
    s0, s1, s2 = family(base_rows, cursor), family(protected_rows, cursor), family(after, cursor)
    sealed_keys = ("FAMILY_BOUND", "OWNER_IDS", "GAP_TO_INCUMBENT", "STILL_OPEN_PROFILE_COUNT")
    for scenario, commit in ((s0, BASE), (s1, PROTECTED)):
        sealed = docs[commit.role]["FAMILY_AFTER"]
        require(sealed == {k: scenario[k] for k in sealed_keys}, "sealed family replay")
    counts = [0] + [
        sum(before[p] != now[p] for p in before) for (_, before), (_, now) in pairwise(chain)
    ]
    regressions = sorted(p for p in after if after[p] > protected_rows[p])
    strengthened = sorted(p for p in after if after[p] < protected_rows[p])
    require(not regressions and all(after[p] <= base_rows[p] for p in after), "non-regression")
    relaxed_states = {
        p: integer(obj(c["RELAXATION"])["RETAINED_STATE_COUNT"])
        for p, c in certificates.items()
        if "RELAXATION" in c
    }
    return {
        "TASK_ID": TASK_ID,
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "TASK_STATUS": "SCIENTIFIC_AUTHORITY_SEALED_FRESH_JUDGE_AND_LIFECYCLE_EXTERNAL",
        "SOURCE_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "PROOF": __doc__,
        "MODEL": MODEL,
        "IDENTITIES": identities(),
        "BASE_JUDGE": base_judge(),
        "PROTECTED_JUDGE": protected_judge(),
        "DONOR_DISPOSITIONS": donor_dispositions(docs),
        "FROZEN_EVALUATOR_SOURCE_PINS": pins,
        "AUTHORITY_FILES": {R30_RESULT: R30_SHA, SIX_ROW_RESULT: SIX_ROW_SHA},
        "T264_ONLY_S4_CERTIFICATES": {
            p: {k: v for k, v in c.items() if k != "SEALED_TERMS"}
            for p, c in sorted(t264_certificates().items())
        },
        "EXACT_LOCAL_EVENT_WEIGHTS": local_weights(),
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4_FLOOR", "S3"],
        "ADVANCED_CHAIN": [
            {"STEP": role, "ROWS_CHANGED_FROM_PREVIOUS": n}
            for (role, _), n in zip(chain, counts, strict=True)
        ],
        "DIFFERING_ROWS_VS_BASE": len(strict) + len(weaker),
        "STRICT_IMPROVEMENT_PROFILE_IDS": strict,
        "STRICT_IMPROVEMENT_COUNT": len(strict),
        "WEAKER_CANDIDATES_REJECTED": rejected,
        "ROW_CERTIFICATES": certificates,
        "RELAXATION_RETAINED_STATES": {
            "BY_PROFILE": relaxed_states,
            "TOTAL": sum(relaxed_states.values()),
        },
        "LOAD_BEARING_NEW_TERM_COUNT": sum(
            integer(c["NEW_TERM_COUNT"]) for c in certificates.values()
        ),
        "OLD_TERM_COUNT": sum(
            integer(obj(c["OLD"])["OLD_TERM_COUNT"]) for c in certificates.values()
        ),
        "S0_69D2": s0,
        "S1_641173": s1,
        "S2_69D2_PLUS_STRONGER_ROWS": s2,
        "S3_NONREGRESSION_COMPARISON": {
            "REGRESSED_ROWS_VS_S1": regressions,
            "STRENGTHENED_ROWS_VS_S1": strengthened,
            "EQUAL_ROWS_VS_S1": sum(after[p] == protected_rows[p] for p in after),
            "PROTECTED_CERTIFIED_ROWS": {
                p: {"S1": protected_rows[p], "S2": after[p]}
                for p in sorted(obj(docs[PROTECTED.role]["PROFILES"]))
            },
            "PASS": not regressions,
        },
        "FAMILY_DELTA_VS_69D2": integer(s0["FAMILY_BOUND"]) - integer(s2["FAMILY_BOUND"]),
        "FAMILY_DELTA_VS_641173": integer(s1["FAMILY_BOUND"]) - integer(s2["FAMILY_BOUND"]),
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "RESOLVED_ROWS": len(after),
        "ROWS_UPDATED": sum(after[p] != base_rows[p] for p in after),
        "OTHER_ROWS_UNCHANGED": sum(after[p] == base_rows[p] for p in after),
        "OTHER_ROWS_SHA256": sha(
            render({p: b for p, b in base_rows.items() if p not in certified})
        ),
        "CURSOR": cursor,
        "CURSOR_PROFILES": len(cast(list[str], cursor["PROFILE_IDS"])),
        "CURSOR_BOUNDS_CHANGED": 0,
        "CURSOR_SHA256": sha(render(cursor)),
        "ADVANCED_CURSOR_ROWS_DIFFERING_NOT_ADOPTED": sum(
            v != ledger(cursor["COARSE_BOUND_PROJECTION"])[p]
            for p, v in ledger(obj(docs["STEP_5"]["CURSOR_197_PRESERVED"])["ROW_BOUNDS"]).items()
        ),
        "INCUMBENT": INCUMBENT,
        "INHERITED_BASE_CAVEATS": {
            k: docs[BASE.role][k]
            for k in (
                "HISTORICAL_R15",
                "INHERITED_CAVEATS",
                "INHERITED_COHORT_SHA256",
                "INHERITED_T245_SHA256",
            )
        },
        "INHERITED_PROTECTED_STATUS": {
            k: docs[PROTECTED.role][k]
            for k in (
                "TASK_STATUS",
                "HISTORICAL_R15",
                "HISTORICAL_A14",
                "DONOR_DISPOSITION_VERBATIM",
            )
        },
        "HISTORICAL_R15": "NOT_VERIFIED",
        "HISTORICAL_A14": "NOT_UPGRADED",
        "PRIOR_18526_TERM_STUDY": "LOCATOR_NOT_SUPPLIED; COMPARED_AGAINST_IMMUTABLE_SEALED_TERMS",
        "LEGAL_ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "GATE_SCOPE": "G01-G17 by deterministic replay; G18-G20 in per-worktree task evidence",
    }


def verify_result(value: Mapping[str, object]) -> None:
    require(render(value) == render(compute_result()), "deterministic result mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(description="Exact Advanced row adoption into 69d2")
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    payload = render(compute_result())
    path = ROOT / RESULT
    if args.write_result and not path.exists():
        with path.open("xb") as stream:
            stream.write(payload)
    else:
        require(path.is_file() and path.read_bytes() == payload, "sealed result differs")
    value = decode(payload)
    print(
        json.dumps(
            {
                "SHA256": sha(payload),
                "S2": value["S2_69D2_PLUS_STRONGER_ROWS"],
                "STRICT": value["STRICT_IMPROVEMENT_COUNT"],
            }
        )
    )


if __name__ == "__main__":
    main()
