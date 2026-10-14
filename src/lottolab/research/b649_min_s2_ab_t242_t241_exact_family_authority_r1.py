"""Exact universal caps for two profiles, composed into the SHA-pinned Family.

Frozen model: 20 tickets of six distinct labels, 22 triple and 27 pair
supports, with no repeated support pair. A ticket's triple degree d gives
g=6+d distinct neighbours. Both exact profiles have sum d=66, E=93,
W=sum C(g,2)=830, and Goodman sum 296. Every mixed vertex triple contributes
twice to sum g(19-g), proving T(G)+T(complement G)=C(20,3)-sum g(19-g)/2.

Partition proof. K={d>0} has 14 vertices and Z={d=0} has six. Set
M=complement G[K], N=complement G[Z], sigma_x=|N_G(x) intersect Z|,
zeta_u=|N_G(u) intersect K|, and r=sum sigma=sum zeta. Then
m_x=7-d_x+sigma_x, n_u=zeta_u-1, 2e(M)=32+r, 2e(N)=r-6.
For each M edge xy the number of complement common neighbours in Z is
6-sigma_x-sigma_y+c_Z(xy), where c_Z counts common G neighbours in Z.
For each N edge uv the analogous number in K is 14-zeta_u-zeta_v+c_K(uv).
Every mixed complement triangle has exactly one within-part edge. Thus
T(complement G)=6e(M)+14e(N)-sum sigma*m-sum zeta*n+P
               =54+10r-sum sigma*m-sum zeta*n+P,
P=T(M)+T(N)+sum_{xy in M}c_Z(xy)+sum_{uv in N}c_K(uv).
Each of the four terms is a count of triangles or edge/common-neighbour
incidences, hence a nonnegative integer. Subtracting from Goodman gives
T(G)=242-10r+sum sigma*(7-d+sigma)+sum zeta*(zeta-1)-P = F-P.

Coverage. Each edge from a core ticket to a zero ticket uses one of its
6-d pair supports, so 0<=sigma<=6-d. Simplicity on Z gives 1<=zeta<=6.
The degree sequence of G[Z] is 6-zeta; it is this sequence that must be
graphical. Zeta itself need not be graphical: (2,2,2,2,2,6) comes from
G[Z]=K5 plus an isolated vertex, while zeta contains a forbidden degree six.
Sort sigma only inside equal-d classes and sort zeta independently on Z.
These permutations preserve F and every retained condition. They impose no
incidence-matrix condition. Every legal realization therefore maps to one
enumerated state. Other necessary conditions are deliberately relaxed;
there is no sufficiency or legal-attainment claim. Erdős-Gallai, independent
Havel-Hakimi, and all 2^15 six-vertex graphs agree on all 462 degree multisets
and yield exactly 102 graphical multisets. The complete A/B domains have
648/540 sigma signatures and 844/683 equal-sum states. Independent labelled
sigma enumeration paired with the entire labelled zero-graph census
reproduces every state and value; A retains 1849624 labelled configurations.
The r=6,8,10,12,14,16,18 maxima are respectively
A: 242,242,238,232,228,226,220; B: 241,235,231,229,228,226,220.
Consequently T_A<=242 and T_B<=241 universally, without asserting attainment.

Route B. An outcome is a seven-label set with one distinguished special
label (seven choices). Winning means at least three of those labels on a
ticket. Choosing three hits for each winner uses three distinct label pairs;
pair-linearity prevents reuse, so at most C(7,2)/3=7 tickets win. For each
q=0..7, q-C(q,2)+C(q,3)-1[q>0]>=4*C(q,4)/7. Summing proves the upper bound
ceil(S1-S2+S3-4*S4/7). Exact local subset counts independently give
S1=372228640 and S2=63838600. A triple of tickets contributes only when its
overlap graph is an open wedge or triangle: 2800 for an open wedge, 20272
for three separate pair labels, 7000 for a shared triple label. Therefore
S3=2800*(W-3T)+20272*(T-22)+7000*22. The 22 support triangles are distinct.
Among neighbour triples at a vertex, each noncomplete triple contains an
open wedge. Every open wedge extends in at most gmax-2 ways. Complete
neighbour triples count each K4 four times. Hence
k>=max(0,ceil((J-10*(W-3T))/4)), J=sum C(g,3),
giving constants 5961 for A and 5960 for B. A K4 contains at most one triple
support since two would repeat a ticket pair. A triple's common outside
neighbours number at most one third of the sum of its three g-2 degrees;
summed over supports this gives a<=floor(sum d*(g-2)/3)=199.
Independent exact local counts give K4 weights 448 with a contained triple
and 679 otherwise. The increasing function 679k-231min(k,199) is thus an
S4 lower bound. Combine it by maximum with the immutable Base's inherited
112 floor; no S5 authority is introduced. Evaluate every old T=22..264
and new T=22..242 (A) / 22..241 (B), with separate integer and Fraction
implementations. The maxima are 313195248 and 313186092.

Family. Replay all 4647 immutable Base resolved rows and the full cursor
object, including all 197 IDs, bounds, coverage and statuses. Exactly A/B
are replaced. Independent scans derive every tied owner, each single-row
effect, the joint maximum, gap and open count. Base historical caveats and
R15 NOT_VERIFIED persist by immutable reference. Donor disposition remains
PROVEN_FAMILY_GAIN / CONDITIONAL_PROJECTION / NOT_CANONICAL_ADOPTION;
its prose's graphical-zeta error is explicitly corrected above, and its
shared 242 projection is not used for B. Fresh Judge and this task's Git
lifecycle/R15 evidence are external to this deterministic scientific result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from fractions import Fraction
from functools import cache
from itertools import combinations, combinations_with_replacement, pairwise, product
from math import ceil, comb, factorial
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_AB_T242_T241_EXACT_FAMILY_AUTHORITY_R1"
OWNER_CONVERSATION_ID = "01a13a7d-3a46-7da2-a2e5-8ef64e34ede5"
SOURCE = "src/lottolab/research/b649_min_s2_ab_t242_t241_exact_family_authority_r1.py"
TEST = "tests/unit/test_b649_min_s2_ab_t242_t241_exact_family_authority_r1.py"
RESULT = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-ab-t242-t241-exact-family-authority-r1-result.json"
)
BASE_HEAD = "69d2d3fe2696623d75e876e5cd96085297da821c"
BASE_TREE = "3fdfa51d658df73afadf6f16eaef145373a529ca"
BASE_RESULT = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-owner-655555555555410-t238-exact-authority-r1-result.json"
)
BASE_SHA = "bad130a8b2ca045ba61884c969bae7d40d9b372f9d2a460e98163998f88aead1"
BASE_SOURCE = "src/lottolab/research/b649_min_s2_owner_655555555555410_t238_exact_authority_r1.py"
BASE_SOURCE_SHA = "2df9eca4ee47c1d4e6db555f583c92126f0f550dbdb12cd47ac99ecfcdb878bd"
DONOR_HEAD = "600a9aadba5880088ffe2a69abf183b59819a860"
DONOR_TREE = "33d36fe2d183600a1557e842e2682df52a75419d"
DONOR_SOURCE = "src/lottolab/research/b649_next_resolved_frontier_shared_bound_r1.py"
DONOR_SOURCE_SHA = "c93c5a421ebf78a208d47849b1198f3756092e17fbfa9cf7a1aa6a83f4e015a7"
DONOR_RESULT = (
    "docs/research/matrix-native-results/b649-next-resolved-frontier-shared-bound-r1-result.json"
)
DONOR_SHA = "073a27d95b399e1c2e3cb0bb1a3441157ebc1d0e45a7c9348000902494f546fa"
A, B = "66655555555431000000", "66665555544441000000"
PROFILES = (A, B)
CAPS = {A: 242, B: 241}
BOUNDS = {A: 313195248, B: 313186092}
K4_CONSTANTS = {A: 5961, B: 5960}
MODEL = {"TICKETS": 20, "LABELS_PER_TICKET": 6, "TRIPLES": 22, "PAIRS": 27, "PAIR_LINEARITY": True}
INCUMBENT = 313263888
type Document = dict[str, object]
type Signature = tuple[tuple[int, ...], ...]
type Record = tuple[int, ...]
type Term = tuple[int, int, int, int, int, int]


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


def integer(value: object) -> int:
    require(type(value) is int, "expected integer")
    return cast(int, value)


def decode(raw: bytes) -> Document:
    value = obj(json.loads(raw))
    require(render(value) == raw, "noncanonical result bytes")
    return value


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", "core.fsmonitor=false", *args],
        cwd=ROOT,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def checked_blob(head: str, tree: str, path: str, digest: str) -> bytes:
    require(bool(re.fullmatch(r"[0-9a-f]{40}", head)), "source commit identity")
    require(git("cat-file", "-t", head).strip() == b"commit", "source commit type")
    require(git("rev-parse", head + "^{tree}").decode().strip() == tree, "source tree identity")
    require(not Path(path).is_absolute() and ".." not in Path(path).parts, "unsafe source path")
    meta = git("ls-tree", head, "--", path).decode().strip().split("\t")
    require(
        len(meta) == 2 and meta[0].startswith("100644 blob ") and meta[1] == path,
        "source must be a regular text blob",
    )
    raw = git("cat-file", "blob", head + ":" + path)
    require(sha(raw) == digest, "source hash/result identity mismatch")
    return raw


def load_inputs() -> tuple[Document, Document, Document]:
    head = git("rev-parse", "HEAD").decode().strip()
    require(
        head == BASE_HEAD or git("rev-parse", "HEAD^").decode().strip() == BASE_HEAD,
        "candidate is not Base or its single local child",
    )
    raw = checked_blob(BASE_HEAD, BASE_TREE, BASE_RESULT, BASE_SHA)
    require((ROOT / BASE_RESULT).read_bytes() == raw, "Base working bytes drift")
    base = decode(raw)
    checked_blob(BASE_HEAD, BASE_TREE, BASE_SOURCE, BASE_SOURCE_SHA)
    donor = decode(checked_blob(DONOR_HEAD, DONOR_TREE, DONOR_RESULT, DONOR_SHA))
    checked_blob(DONOR_HEAD, DONOR_TREE, DONOR_SOURCE, DONOR_SOURCE_SHA)
    require(
        donor["TASK_STATUS"] == "PROVEN_FAMILY_GAIN"
        and donor["PROJECTION_STATUS"] == "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION"
        and donor["CANONICAL_AUTHORITY_CHANGED"] == "NO",
        "Donor original conditional disposition",
    )
    require(
        base["MODEL"] == MODEL and base["INCUMBENT"] == INCUMBENT, "Base frozen model/incumbent"
    )
    message = git("cat-file", "commit", BASE_HEAD).split(b"\n\n", 1)[1].decode()
    report = (
        message.split("FRESH_JUDGE_REPORT_VERBATIM_BEGIN\n", 1)[1].split(
            "\nFRESH_JUDGE_REPORT_VERBATIM_END", 1
        )[0]
        + "\n"
    )
    declared = re.findall(r"(?m)^Judge-report-SHA256: ([0-9a-f]{64})$", message)
    require(
        declared == [sha(report.encode())]
        and BASE_TREE in report
        and BASE_SHA in report
        and "Fresh-context Judge: VERIFIED_WITH_CAVEATS" in message,
        "Base Judge binding",
    )
    provenance: Document = {
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_PATH": BASE_RESULT,
        "BASE_RESULT_SHA256": BASE_SHA,
        "BASE_SOURCE_SHA256": BASE_SOURCE_SHA,
        "BASE_JUDGE": "VERIFIED_WITH_CAVEATS",
        "BASE_JUDGE_REPORT_SHA256": declared[0],
        "DONOR_HEAD": DONOR_HEAD,
        "DONOR_TREE": DONOR_TREE,
        "DONOR_SOURCE_PATH": DONOR_SOURCE,
        "DONOR_SOURCE_SHA256": DONOR_SOURCE_SHA,
        "DONOR_RESULT_PATH": DONOR_RESULT,
        "DONOR_RESULT_SHA256": DONOR_SHA,
        "DONOR_ORIGINAL_STATUS": [
            donor["TASK_STATUS"],
            "CONDITIONAL_PROJECTION",
            "NOT_CANONICAL_ADOPTION",
        ],
        "DONOR_TEXT_CORRECTION": "Graphicality is of 6-zeta, not zeta itself",
        "DONOR_B_SHARED_242_PROJECTION_ADOPTED": False,
        "INHERITED_DISPOSITIONS": "PRESERVED_BY_IMMUTABLE_BASE_AND_DONOR_REFERENCES",
        "S4_FLOOR": 112,
        "S5_ADOPTED": False,
        "HISTORICAL_SOLVER_RERUN": False,
    }
    return base, donor, provenance


def degrees(pid: str) -> tuple[int, ...]:
    require(pid in PROFILES, "incorrect exact profile")
    d = tuple(map(int, pid))
    expected = (
        (6,) * 3 + (5,) * 8 + (4, 3, 1) + (0,) * 6
        if pid == A
        else ((6,) * 4 + (5,) * 5 + (4,) * 4 + (1,) + (0,) * 6)
    )
    require(d == expected, "incorrect degree identity")
    return d


def facts(pid: str, model: Mapping[str, object] = MODEL) -> Document:
    require(dict(model) == MODEL, "frozen support model")
    d = degrees(pid)
    g = tuple(6 + x for x in d)
    value: Document = {
        "D": list(d),
        "G": list(g),
        "SUM_D": sum(d),
        "E": sum(g) // 2,
        "W": sum(comb(x, 2) for x in g),
        "CORE_VERTICES": 14,
        "ZERO_VERTICES": 6,
        "GOODMAN_SUM": comb(20, 3) - sum(x * (19 - x) for x in g) // 2,
        "SUM_CHOOSE3_DEGREES": sum(comb(x, 3) for x in g),
        "A_MAX": sum(x * (x + 4) for x in d) // 3,
    }
    require(
        tuple(value[k] for k in ("SUM_D", "E", "W", "GOODMAN_SUM", "A_MAX"))
        == (66, 93, 830, 296, 199),
        "graph degree facts",
    )
    require(value["SUM_CHOOSE3_DEGREES"] == 8300 - K4_CONSTANTS[pid], "K4 constant identity")
    return value


def erdos_gallai(degrees_: Sequence[int]) -> bool:
    n = len(degrees_)
    if any(type(x) is not int or not 0 <= x < n for x in degrees_) or sum(degrees_) % 2:
        return False
    d = sorted(degrees_, reverse=True)
    return all(sum(d[:k]) <= k * (k - 1) + sum(min(k, x) for x in d[k:]) for k in range(1, n + 1))


def havel_hakimi(degrees_: Sequence[int]) -> bool:
    if any(type(x) is not int or not 0 <= x < len(degrees_) for x in degrees_):
        return False
    remaining = sorted(degrees_, reverse=True)
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


@cache
def zero_census() -> tuple[tuple[Record, ...], tuple[tuple[Record, int], ...]]:
    pairs = tuple(combinations(range(6), 2))
    frequencies: Counter[Record] = Counter()
    for mask in range(1 << 15):
        d = [0] * 6
        for i, (u, v) in enumerate(pairs):
            if mask >> i & 1:
                d[u] += 1
                d[v] += 1
        frequencies[tuple(sorted(d))] += 1
    classification: list[Record] = []
    for d in combinations_with_replacement(range(6), 6):
        eg, hh, realized = erdos_gallai(d), havel_hakimi(d), d in frequencies
        require(eg == hh == realized, "six-point graphicality disagreement")
        classification.append((*d, int(eg), int(hh), int(realized)))
    require(
        len(frequencies) == 102 and sum(frequencies.values()) == 32768,
        "incomplete zero graph census",
    )
    zeta = tuple(sorted((tuple(sorted(6 - x for x in d)), n) for d, n in frequencies.items()))
    return tuple(classification), zeta


def validate_zeta(zeta: Sequence[int], graphicality: str = "6-zeta") -> None:
    require(graphicality == "6-zeta", "graphicality must use 6-zeta")
    require(
        len(zeta) == 6 and all(type(x) is int and 1 <= x <= 6 for x in zeta),
        "zero cross-degree capacities",
    )
    require(erdos_gallai(tuple(6 - x for x in zeta)), "6-zeta is not graphical")


def groups(pid: str) -> tuple[tuple[int, int], ...]:
    return tuple(sorted(Counter(x for x in degrees(pid) if x).items(), reverse=True))


def sigma_signatures(pid: str) -> tuple[Signature, ...]:
    return tuple(
        product(*(tuple(combinations_with_replacement(range(7 - d), n)) for d, n in groups(pid)))
    )


def record(pid: str, sigma: Signature, zeta: Record) -> Record:
    require(len(sigma) == len(groups(pid)), "sigma degree classes")
    for (d, n), part in zip(groups(pid), sigma, strict=True):
        require(
            len(part) == n
            and tuple(sorted(part)) == part
            and all(type(x) is int and 0 <= x <= 6 - d for x in part),
            "core cross-degree capacities or symmetry",
        )
    validate_zeta(zeta)
    require(tuple(sorted(zeta)) == zeta, "zero symmetry")
    flattened = tuple(x for part in sigma for x in part)
    r = sum(flattened)
    require(r == sum(zeta), "cross-degree sums differ")
    score = sum(
        x * (7 - d + x) for (d, _), part in zip(groups(pid), sigma, strict=True) for x in part
    )
    f = 242 - 10 * r + score + sum(x * (x - 1) for x in zeta)
    return (*flattened, *zeta, f)


def remainder(parts: Sequence[int]) -> int:
    require(
        len(parts) == 4 and all(type(x) is int and x >= 0 for x in parts),
        "four nonnegative P counts",
    )
    return sum(parts)


def split_value(f: int, parts: Sequence[int], sign: int = -1) -> int:
    require(sign == -1, "P correction sign")
    return f - remainder(parts)


def multiplicity(values: Sequence[int]) -> int:
    divisor = 1
    for n in Counter(values).values():
        divisor *= factorial(n)
    return factorial(len(values)) // divisor


@cache
def enumeration(pid: str) -> Document:
    classification, zero = zero_census()
    signatures = sigma_signatures(pid)
    rows = sorted(
        record(pid, sigma, zeta)
        for sigma in signatures
        for zeta, _ in zero
        if sum(map(sum, sigma)) == sum(zeta)
    )
    # Independent traversal: every labelled core sigma, then zero graphs grouped
    # by their canonical degree list, with exact labelled graph multiplicity.
    d = tuple(x for x in degrees(pid) if x)
    offsets = [0]
    for _, n in groups(pid):
        offsets.append(offsets[-1] + n)
    independent: set[Record] = set()
    labelled = 0
    labelled_degree_sequences = 0
    for labelled_sigma in product(*(range(7 - x) for x in d)):
        r = sum(labelled_sigma)
        core = tuple(x for i, j in pairwise(offsets) for x in sorted(labelled_sigma[i:j]))
        core_score = sum(x * (7 - degree + x) for x, degree in zip(labelled_sigma, d, strict=True))
        for zeta, graph_count in zero:
            if sum(zeta) == r:
                f = 296 - (54 + 10 * r - core_score - sum(x * (x - 1) for x in zeta))
                independent.add((*core, *zeta, f))
                labelled += graph_count
                labelled_degree_sequences += multiplicity(zeta)
    require(
        rows == sorted(independent) and len(rows) == len(set(rows)),
        "independent complete domain/value mismatch",
    )
    r_max: dict[int, int] = {}
    for row in rows:
        r = sum(row[14:20])
        r_max[r] = max(r_max.get(r, -1), row[-1])
    expected = (
        [242, 242, 238, 232, 228, 226, 220] if pid == A else ([241, 235, 231, 229, 228, 226, 220])
    )
    require(
        list(sorted(r_max)) == [6, 8, 10, 12, 14, 16, 18]
        and [r_max[r] for r in sorted(r_max)] == expected,
        "r-class maxima",
    )
    require(
        (len(signatures), len(rows)) == ((648, 844) if pid == A else (540, 683)),
        "canonical configuration completeness",
    )
    require(pid != A or labelled == 1849624, "A labelled graph recount")
    maximum = max(row[-1] for row in rows)
    require(maximum == CAPS[pid], "universal cap")
    return {
        "CANONICAL_SIGMA": len(signatures),
        "EQUAL_SUM_STATES": len(rows),
        "ZERO_GRAPHICAL_MULTISETS": 102,
        "ZERO_LABELLED_GRAPHS": 32768,
        "ZERO_MULTISETS_CLASSIFIED": len(classification),
        "GRAPHICALITY_SEQUENCE": "6-zeta",
        "INDEPENDENT_DOMAIN_AND_VALUES_EQUAL": True,
        "INDEPENDENT_LABELLED_GRAPH_CONFIGURATIONS": labelled,
        "LABELLED_DEGREE_SEQUENCE_CONFIGURATIONS": labelled_degree_sequences,
        "LABELLED_CONFIGURATION_DEFINITION": "labelled core sigma x labelled G[Z], equal sums",
        "COLUMNS": [*[f"SIGMA_{i}" for i in range(14)], *[f"ZETA_{i}" for i in range(6)], "F"],
        "COMPLETE_DOMAIN": [list(r) for r in rows],
        "DOMAIN_SHA256": sha(render(rows)),
        "R_CLASS_MAXIMA": {str(r): m for r, m in sorted(r_max.items())},
        "UNIVERSAL_T_CAP": maximum,
        "ARGMAX_CONFIGURATIONS": [list(r) for r in rows if r[-1] == maximum],
        "DOMAIN_COVERAGE": "EVERY_LEGAL_REALIZATION_MAPS_TO_A_RETAINED_NECESSARY_STATE",
        "SYMMETRY": "only equal-d core permutations and independent zero permutations",
        "LEGAL_ATTAINMENT": "UNKNOWN",
    }


def validate_enumeration(pid: str, value: Mapping[str, object]) -> None:
    require(render(value) == render(enumeration(pid)), "incomplete canonical configurations")


def hit_weight(groups_: Sequence[tuple[int, int]], tickets: int) -> int:
    """Exact count for the few fixed local motifs, with capped hit counts."""
    state = {(0, (0,) * tickets): 1}
    for mask, count in groups_:
        updated: dict[tuple[int, Record], int] = defaultdict(int)
        for (taken, hits), ways in state.items():
            for pick in range(min(count, 7 - taken) + 1):
                new_hits = tuple(
                    min(3, h + pick) if mask >> i & 1 else h for i, h in enumerate(hits)
                )
                updated[taken + pick, new_hits] += ways * comb(count, pick)
        state = updated
    return 7 * state.get((7, (3,) * tickets), 0)


@cache
def local_weights() -> Document:
    one = hit_weight(((1, 6), (0, 43)), 1)
    disjoint = hit_weight(((1, 6), (2, 6), (0, 37)), 2)
    shared = hit_weight(((1, 5), (2, 5), (3, 1), (0, 38)), 2)
    wedge = hit_weight(((1, 5), (2, 4), (4, 5), (3, 1), (6, 1), (0, 33)), 3)
    triangle = hit_weight(((1, 4), (2, 4), (4, 4), (3, 1), (5, 1), (6, 1), (0, 34)), 3)
    triple = hit_weight(((1, 5), (2, 5), (4, 5), (7, 1), (0, 33)), 3)
    quartet = hit_weight(
        ((1, 3), (2, 3), (4, 3), (8, 3), (3, 1), (5, 1), (9, 1), (6, 1), (10, 1), (12, 1), (0, 31)),
        4,
    )
    contained = hit_weight(
        ((1, 4), (2, 4), (4, 4), (8, 3), (7, 1), (9, 1), (10, 1), (12, 1), (0, 30)), 4
    )
    s1, s2 = 20 * one, 97 * disjoint + 93 * shared
    require(
        (s1, s2, wedge, triangle, triple, quartet, contained)
        == (372228640, 63838600, 2800, 20272, 7000, 679, 448),
        "exact local weights",
    )
    for q in range(8):
        require(
            Fraction(q - comb(q, 2) + comb(q, 3) - int(q > 0)) >= Fraction(4 * comb(q, 4), 7),
            "Bonferroni polynomial",
        )
    return {
        "S1": s1,
        "S2": s2,
        "OPEN_WEDGE": wedge,
        "PAIR_TRIANGLE": triangle,
        "SHARED_TRIPLE": triple,
        "K4_PAIR": quartet,
        "K4_WITH_TRIPLE": contained,
    }


def validate_profile_binding(pid: str, cap: int, constant: int) -> None:
    degrees(pid)
    require(cap == CAPS[pid] and constant == K4_CONSTANTS[pid], "A/B cap or K4 constant binding")


def integer_terms(pid: str, cap: int) -> list[Term]:
    require(cap in (264, CAPS[pid]), "incorrect complete T domain")
    facts(pid)
    terms: list[Term] = []
    for t in range(22, cap + 1):
        k = max(0, -(-(30 * t - K4_CONSTANTS[pid]) // 4))
        a = min(k, 199)
        s4 = max(112, 679 * k - 231 * a)
        s3 = 2800 * 830 + 11872 * (t - 22) - 30800
        bound = (7 * (372228640 - 63838600 + s3) - 4 * s4 + 6) // 7
        terms.append((t, bound, k, a, s4, s3))
    return terms


def fraction_terms(pid: str, cap: int) -> list[Term]:
    d = degrees(pid)
    g = tuple(6 + x for x in d)
    w, j = sum(comb(x, 2) for x in g), sum(comb(x, 3) for x in g)
    allowance = sum(x * (degree - 2) for x, degree in zip(d, g, strict=True)) // 3
    weights = local_weights()
    terms: list[Term] = []
    for t in range(22, cap + 1):
        k = max(0, ceil(Fraction(j - (max(g) - 2) * (w - 3 * t), 4)))
        a = min(k, allowance)
        s4 = max(112, 448 * a + 679 * (k - a))
        s3 = 2800 * (w - 3 * t) + 20272 * (t - 22) + 7000 * 22
        exact = Fraction(integer(weights["S1"]) - integer(weights["S2"]) + s3)
        exact -= Fraction(4 * s4, 7)
        terms.append((t, ceil(exact), k, a, s4, s3))
    return terms


def envelope(pid: str, cap: int) -> list[Term]:
    terms = integer_terms(pid, cap)
    require(terms == fraction_terms(pid, cap), "integer/Fraction rounding or S3 drift")
    return terms


def validate_terms(pid: str, cap: int, terms: Sequence[Sequence[int]]) -> None:
    require(
        [list(t) for t in envelope(pid, cap)] == [list(t) for t in terms],
        "incomplete T terms or incorrect integer rounding",
    )


def replay_base(base: Mapping[str, object]) -> tuple[dict[str, int], Document]:
    require(sha(render(base)) == BASE_SHA, "Base result identity mismatch")
    rows = {p: integer(v) for p, v in obj(base["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = obj(base["CURSOR"])
    bounds = obj(cursor["COARSE_BOUND_PROJECTION"])
    ids = cast(list[str], cursor["PROFILE_IDS"])
    require(
        len(rows) == 4647
        and len(bounds) == len(ids) == len(set(ids)) == 197
        and set(ids) == set(bounds)
        and not set(rows) & set(bounds),
        "ledger/cursor coverage",
    )
    require(all(rows[p] == 313392412 for p in PROFILES), "Base target rows")
    return rows, cursor


def family(rows: Mapping[str, int], cursor: Mapping[str, object]) -> Document:
    bounds = {p: integer(v) for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items()}
    require(
        len(rows) == 4647 and len(bounds) == 197 and not set(rows) & set(bounds), "family coverage"
    )
    top, owners, opened = -1, [], 0
    for p, bound in (*rows.items(), *bounds.items()):
        if bound > top:
            top, owners = bound, [p]
        elif bound == top:
            owners.append(p)
        opened += int(bound > INCUMBENT)
    ordered = sorted((*rows.items(), *bounds.items()), key=lambda row: (-row[1], row[0]))
    require(
        (top, sorted(owners), opened)
        == (
            ordered[0][1],
            sorted(p for p, b in ordered if b == ordered[0][1]),
            sum(b > INCUMBENT for _, b in ordered),
        ),
        "independent family scan",
    )
    return {
        "FAMILY_BOUND": top,
        "OWNER_IDS": sorted(owners),
        "GAP_TO_INCUMBENT": top - INCUMBENT,
        "STILL_OPEN_PROFILE_COUNT": opened,
    }


def apply_updates(
    rows: Sequence[tuple[str, int]],
    cursor: Mapping[str, object],
    base: Document,
    updates: Sequence[tuple[str, int]],
) -> dict[str, int]:
    before, frozen = replay_base(base)
    require(
        len(rows) == len(dict(rows)) == len(before) and dict(rows) == before,
        "duplicate or missing family row",
    )
    require(render(cursor) == render(frozen), "cursor mutation")
    require(
        list(updates) == [(p, max(t[1] for t in envelope(p, CAPS[p]))) for p in PROFILES],
        "duplicate or missing family row update",
    )
    after = {**before, **dict(updates)}
    require(
        sorted(p for p in before if before[p] != after[p]) == list(PROFILES),
        "exactly two row updates",
    )
    return after


def compute_result() -> Document:
    base, donor, provenance = load_inputs()
    before, cursor = replay_base(base)
    profiles: dict[str, Document] = {}
    for pid in PROFILES:
        validate_profile_binding(pid, CAPS[pid], K4_CONSTANTS[pid])
        old, new = envelope(pid, 264), envelope(pid, CAPS[pid])
        bound = max(t[1] for t in new)
        require(
            max(t[1] for t in old) == before[pid] and bound == BOUNDS[pid] and bound < INCUMBENT,
            "full-profile bounds/strict gain",
        )
        profiles[pid] = {
            "FACTS": facts(pid),
            "TRIANGLE_PROOF": enumeration(pid),
            "CURRENT_T_CAP": 264,
            "NEW_T_CAP": CAPS[pid],
            "K4_CONSTANT": K4_CONSTANTS[pid],
            "OLD_T_TERMS": [list(t) for t in old],
            "NEW_T_TERMS": [list(t) for t in new],
            "OLD_TERM_COUNT": len(old),
            "NEW_TERM_COUNT": len(new),
            "OLD_FULL_BOUND": max(t[1] for t in old),
            "NEW_FULL_BOUND": bound,
            "PROFILE_DELTA": before[pid] - bound,
            "STRICT_GAIN_EXCLUDED": True,
            "MAXIMIZING_TERMS": [list(t) for t in new if t[1] == bound],
            "ALL_TERMS_INTEGER_FRACTION_EQUAL": True,
        }
    after = apply_updates(list(before.items()), cursor, base, [(p, BOUNDS[p]) for p in PROFILES])
    initial = family(before, cursor)
    a_only = family({**before, A: BOUNDS[A]}, cursor)
    b_only = family({**before, B: BOUNDS[B]}, cursor)
    both = family(after, cursor)
    require(
        initial == base["FAMILY_AFTER"] and initial["OWNER_IDS"] == list(PROFILES),
        "Base family replay",
    )
    require(
        a_only["FAMILY_BOUND"] == b_only["FAMILY_BOUND"] == 313392412
        and a_only["OWNER_IDS"] == [B]
        and b_only["OWNER_IDS"] == [A],
        "single-row replay",
    )
    require(
        both
        == {
            "FAMILY_BOUND": 313392308,
            "OWNER_IDS": ["66665555555421000000"],
            "GAP_TO_INCUMBENT": 128420,
            "STILL_OPEN_PROFILE_COUNT": 1558,
        },
        "joint Family replay",
    )
    classification, zero = zero_census()
    require(not any(k.startswith("ortools") for k in sys.modules), "heavy solver loaded")
    return {
        "TASK_ID": TASK_ID,
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "TASK_STATUS": "SCIENTIFIC_AUTHORITY_SEALED_LIFECYCLE_AND_FRESH_JUDGE_EXTERNAL",
        "SOURCE_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "PROOF": __doc__,
        "PROVENANCE": provenance,
        "MODEL": MODEL,
        "PROFILES": profiles,
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_ALLOWANCE", "S4_FLOOR", "S3"],
        "EXACT_LOCAL_EVENT_WEIGHTS": local_weights(),
        "ZERO_GRAPHICAL_CLASSIFICATION": [list(r) for r in classification],
        "ZERO_ZETA_AND_LABELLED_GRAPH_FREQUENCIES": [[list(z), n] for z, n in zero],
        "FAMILY_BEFORE": initial,
        "FAMILY_AFTER_A_ONLY": a_only,
        "FAMILY_AFTER_B_ONLY": b_only,
        "FAMILY_AFTER_BOTH": both,
        "FAMILY_AFTER": both,
        "FAMILY_DELTA": integer(initial["FAMILY_BOUND"]) - integer(both["FAMILY_BOUND"]),
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "RESOLVED_ROWS": len(after),
        "ROWS_UPDATED": 2,
        "OTHER_ROWS_UNCHANGED": sum(before[p] == after[p] for p in before),
        "OTHER_ROWS_SHA256": sha(render({p: b for p, b in before.items() if p not in PROFILES})),
        "CURSOR": cursor,
        "CURSOR_PROFILES": 197,
        "CURSOR_PRESERVED": True,
        "CURSOR_SHA256": sha(render(cursor)),
        "INCUMBENT": INCUMBENT,
        "INHERITED_BASE_CAVEATS": {
            k: base[k]
            for k in (
                "HISTORICAL_R15",
                "INHERITED_CAVEATS",
                "INHERITED_COHORT_SHA256",
                "INHERITED_T245_SHA256",
                "PROVENANCE",
            )
        },
        "DONOR_DISPOSITION_VERBATIM": {
            k: donor[k]
            for k in (
                "TASK_STATUS",
                "PROJECTION_STATUS",
                "CONDITIONAL_PROJECTION_ONLY",
                "CANONICAL_AUTHORITY_CHANGED",
            )
        },
        "HISTORICAL_R15": "NOT_VERIFIED",
        "HISTORICAL_A14": "NOT_UPGRADED",
        "G01_TO_G18_AT_SEAL": {f"G{i:02}": "PASS" for i in range(1, 19)},
        "G19_G20_SCOPE": "Fresh Judge, commands and post-seal R15 recorded in task Git metadata",
        "LEGAL_ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
    }


def verify_result(value: Mapping[str, object]) -> None:
    require(render(value) == render(compute_result()), "result identity or certificate mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(description="Certify exact A242/B241 and compose Family")
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    value = compute_result()
    payload = render(value)
    output = ROOT / RESULT
    if args.write_result and not output.exists():
        with output.open("xb") as stream:
            stream.write(payload)
    else:
        require(output.read_bytes() == payload, "stored result differs from exact recomputation")
    print(
        json.dumps(
            {
                "SHA256": sha(payload),
                "PROFILES": BOUNDS,
                "FAMILY": value["FAMILY_AFTER"],
                "FAMILY_DELTA": value["FAMILY_DELTA"],
            }
        )
    )


if __name__ == "__main__":
    main()
