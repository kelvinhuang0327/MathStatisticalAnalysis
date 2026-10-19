"""Core-zero cap T<=257 for 66655555555440000000, then the three-row min-S2 family.

Support model (r5.validate_k20_support_realization at cc493492). Twenty tickets carry
six labels each: 22 labels have triple supports and 27 have pair supports. Every
2-subset of every support is distinct, so two tickets share at most one label and the
overlap graph G (shadow plus pairs) has deg(v)=6+d_v, where d_v counts the triples
through v. T is the triangle count of G.

Premises. d=(6^3,5^8,4^2,0^7): core K={d>0} with k=13, zeros Z with z=7. A zero lies
in no triple, so every G-edge from a core x into Z is one of x's 6-d_x pair labels:
0<=sigma_x<=6-d_x<=2. A zero has six G-neighbours, so 0<=zeta_u<=6. Both sums count
the K-Z edges: sum sigma = sum zeta = r.

Identity (e44a635f, re-derived). Let H be the complement of G. Inclusion-exclusion
over the H-edges of each vertex triple gives t(G)=C(20,3)-18|E(H)|+sum C(13-d,2)-t(H)
=Phi-t(H), with |E(H)|=190-93=97 and Phi=sum C(13-d,2)-606=299. Put M=H[K], MZ=H[Z],
so deg_M(x)=h_x=6-d_x+sigma_x and deg_MZ(u)=a_u=zeta_u. A mixed H triangle has
exactly one same-part edge. Over an M edge xy its zero apices number
z-sigma_x-sigma_y+c_Z(xy), with c_Z the common G-neighbours in Z, and likewise over
MZ edges. Summing, t(H)=z|M|+k|MZ|-sum sigma*h-sum zeta*a+P, where
P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K>=0. Hence T=F-P with
 F=299-7(12+r)/2-13r/2+sum sigma(6-d+sigma)+sum zeta^2
  =257-10r+sum sigma(6-d+sigma)+sum zeta^2.

Cap. Write -10r=-4 sum sigma-6 sum zeta, so
 F-257=sum_x sigma_x(sigma_x+2-d_x)+sum_u zeta_u(zeta_u-6).
Since d_x>=4 and sigma_x<=6-d_x, sigma_x+2-d_x<=8-2d_x<=0, so each core term is <=0.
Since 0<=zeta_u<=6, each zero term is <=0. So F<=257, and T=F-P<=257 for every legal
structure. No graphicality, sampling or structure enumeration is used. The code checks
the separable maximum coordinate by coordinate over each whole legal range, and checks
the identity as a polynomial: a separable quadratic is fixed by its values at 0, e_i
and 2e_i. Equality needs P=0, sigma_x in {0,d_x-2} (so 0 for d>=5 and {0,2} for d=4),
and zeta_u in {0,6}.

Attainment. Delete blocks 014, 027, 3510 and 3911 from the cyclic STS(13). The 22 blocks
left are linear, with degrees 6^3 5^8 4^2. Six of the 12 uncovered core pairs become
pair labels (14, 02, 07, 5-10, 39, 3-11). That leaves M as two 2-paths and two edges,
which is triangle-free. The zeros form K7 with 21 pair labels. Then T=222+35=257, F=257
and P=0, so the cap is the exact profile maximum.

Ledger. The cc493492 two-row authority is pinned by tree and result digest. Its own
baseline replay and certified updates rebuild the ledger, which must match its stored
digests. Route B (R32 envelope, integer and exact rational) at cap 257 and the row's S4
base 1680 gives 313339312. That envelope is a prefix of the cap-264 one, which
reproduces the row bound 313401852. Exactly one more row changes, in a copy. The family
maximum over all 4,647 rows and the W<=785 cursor is recomputed with every tied owner.
Certificate B keeps VERIFIED_WITH_CAVEATS and its Worker-sourced caveat text. The
cc493492 addendum is audited against the Judge-reviewed 4e2fa8a5 tree: only caveat
metadata changed, and that Judge did not review cc493492. Global K20 optimality is
unknown. No solver or search is run.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, replace
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path

from . import b649_min_s2_two_certified_row_combined_authority_r1 as two

TASK_ID = "B649_MIN_S2_CORE_ZERO_T257_THREE_ROW_CERT_R1"
BASE_HEAD = "cc493492701d19ad433bba967f14c2f27f844c3e"
BASE_TREE = "82e3f6ca1660282906a55a9f32302c826bb97fe1"
TWO_MODULE = "src/lottolab/research/b649_min_s2_two_certified_row_combined_authority_r1.py"
TWO_RESULT_SHA256 = "2b24ca7b202f01d9980c3ec0ffa34336685836145cc61ac5b062ec0ca1bc78bc"
JUDGED_HEAD = "4e2fa8a560d6538c2b05b499f99d639e356c6cfa"
JUDGED_TREE = "a452a2a868abce481d3ea02fcfa47ba865981a65"
JUDGED_RESULT_SHA256 = "c72d582f2c667d24332c96c5fd24ff8252b9e616fc2cc2da855411a7db59af8b"
C_PROFILE = "66655555555440000000"
CURRENT_CAP = 264
PROPOSED_CAP = 257
S4_BASE = 1_680
TWO_ROW_BOUND = 313_401_852
ORIGINAL_BOUND = two.FAMILY_BEFORE
INCUMBENT = two.INCUMBENT
CORE_TERM_CONSTANT = 2
ZERO_TERM_CONSTANT = 6
STS13_BASE_BLOCKS = ((0, 1, 4), (0, 2, 7))
REMOVED_BLOCKS = ((0, 1, 4), (0, 2, 7), (3, 5, 10), (3, 9, 11))
CORE_PAIRS = ((1, 4), (0, 2), (0, 7), (5, 10), (3, 9), (3, 11))
ZERO_TICKETS = tuple(range(13, 20))
RESULT_STEM = "b649-min-s2-core-zero-t257-three-row-cert-r1"
ROOT = two.ROOT
require, sha256 = two.require, two.sha256
integer, object_row, rows, text = two.integer, two.object_row, two.rows, two.text
chase, split, r32 = two.chase, two.chase.split, two.r32
r5 = split.prior.r5
Row = two.chase.Row
Support = tuple[int, ...]
Term = tuple[int, int, int, int, int, int]


def git_tree(head: str) -> str:
    return chase.git("rev-parse", f"{head}^{{tree}}").decode().strip()


def module_provenance() -> dict[str, str]:
    """Every module this certificate calls equals its cc493492 blob, byte for byte."""

    out: dict[str, str] = {}
    for module in (two, chase, split, r32, r5):
        require(module.__file__ is not None, "reused module has no source")
        source = Path(text(module.__file__)).resolve()
        require(source.is_relative_to(ROOT), "reused module outside this worktree")
        relative = source.relative_to(ROOT).as_posix()
        committed = chase.git("show", f"{BASE_HEAD}:{relative}")
        require(source.read_bytes() == committed, f"reused source changed: {relative}")
        out[relative] = sha256(committed)
    return out


def support_model() -> dict[str, int]:
    """The pinned validator's counts that the degree identity deg(v)=6+d_v rests on."""

    model = {
        "TICKETS": r5.K20_TICKET_COUNT,
        "TICKET_CAPACITY": r5.K20_TICKET_CAPACITY,
        "TRIPLE_SUPPORTS": r5.K20_TRIPLE_SUPPORT_COUNT,
        "PAIR_SUPPORTS": r5.K20_DOUBLE_SUPPORT_COUNT,
        "LABELS": r5.K20_LABEL_COUNT,
        "TRIPLE_INCIDENCES": r5.K20_TRIPLE_INCIDENCE_COUNT,
    }
    require(
        model
        == {
            "TICKETS": 20,
            "TICKET_CAPACITY": 6,
            "TRIPLE_SUPPORTS": 22,
            "PAIR_SUPPORTS": 27,
            "LABELS": 49,
            "TRIPLE_INCIDENCES": 66,
        },
        "pinned support model changed",
    )
    return model


def pinned_two_row() -> tuple[dict[str, object], dict[str, object]]:
    """The cc493492 result and module, plus an audit of its post-Judge addendum."""

    require(git_tree(BASE_HEAD) == BASE_TREE, "two-row base tree mismatch")
    require(git_tree(JUDGED_HEAD) == JUDGED_TREE, "judged tree mismatch")
    source = Path(two.__file__).resolve()
    require(source.relative_to(ROOT).as_posix() == TWO_MODULE, "two-row module path differs")
    committed = chase.git("show", f"{BASE_HEAD}:{TWO_MODULE}")
    require(source.read_bytes() == committed, "two-row module differs from cc493492")
    directory = two.RESULT_DIRECTORY
    final_path = f"{directory}/{two.RESULT_STEM}-{TWO_RESULT_SHA256}.json"
    judged_path = f"{directory}/{two.RESULT_STEM}-{JUDGED_RESULT_SHA256}.json"
    final = object_row(json.loads(two.blob(BASE_HEAD, final_path, TWO_RESULT_SHA256)))
    judged = object_row(json.loads(two.blob(JUDGED_HEAD, judged_path, JUDGED_RESULT_SHA256)))
    changed = chase.git("diff", "--name-status", JUDGED_HEAD, BASE_HEAD).decode().splitlines()
    require(
        sorted(changed) == sorted([f"A\t{final_path}", f"M\t{TWO_MODULE}"]),
        "addendum touched files beyond the module and its new result",
    )
    final_b, judged_b = (object_row(r["CERTIFICATE_B_IDENTITY"]) for r in (final, judged))
    added = sorted(set(final) - set(judged))
    altered = sorted(k for k in judged if final.get(k) != judged[k])
    b_added = sorted(set(final_b) - set(judged_b))
    b_altered = sorted(k for k in judged_b if final_b.get(k) != judged_b[k])
    prior_judge = object_row(final["PRIOR_COMBINED_FRESH_JUDGE"])
    require(
        added == ["PRIOR_COMBINED_FRESH_JUDGE"]
        and altered == ["CERTIFICATE_B_IDENTITY", "TASK_STATUS"]
        and b_added == ["JUDGE_CAVEATS_SOURCE"]
        and b_altered == ["JUDGE_CAVEATS_TEXT"]
        and final_b["JUDGE_CAVEATS_TEXT"] == list(two.B_WORKER_CAVEATS)
        and final_b["JUDGE_CAVEATS_SOURCE"] == "OWNER_SUPPLIED_ORIGINAL_WORKER_REPORT"
        and final_b["JUDGE_STATUS"] == two.B.judge_status == "VERIFIED_WITH_CAVEATS"
        and (prior_judge["LOCAL_HEAD"], prior_judge["LOCAL_TREE"]) == (JUDGED_HEAD, JUDGED_TREE)
        and final["FAMILY_BOUND_AFTER"] == TWO_ROW_BOUND
        and final["NEW_FAMILY_OWNER"] == [C_PROFILE],
        "addendum is not caveat metadata only",
    )
    audit: dict[str, object] = {
        "JUDGED_HEAD": JUDGED_HEAD,
        "JUDGED_TREE": JUDGED_TREE,
        "JUDGED_RESULT_SHA256": JUDGED_RESULT_SHA256,
        "FINAL_HEAD": BASE_HEAD,
        "FINAL_TREE": BASE_TREE,
        "FINAL_RESULT_SHA256": TWO_RESULT_SHA256,
        "CHANGED_FILES": sorted(changed),
        "RESULT_KEYS_ADDED": added,
        "RESULT_KEYS_CHANGED": altered,
        "B_IDENTITY_KEYS_ADDED": b_added,
        "B_IDENTITY_KEYS_CHANGED": b_altered,
        "SCIENTIFIC_FIELDS_UNCHANGED": "PASS",
        "PRIOR_JUDGE_REVIEWED_FINAL_TREE": False,
    }
    return final, audit


def split_objective(profile: Sequence[int], sigma: Sequence[int], zeta: Sequence[int]) -> Fraction:
    """e44a635f's F for any cross degrees, exact and without graphicality filters."""

    core = [d for d in profile if d]
    k, z = len(core), len(profile) - len(core)
    h = [13 - z - d + s for d, s in zip(core, sigma, strict=True)]
    a = [z - 7 + v for v in zeta]
    phi = sum(comb(13 - d, 2) for d in profile) - 606
    return (
        phi
        - Fraction(z * sum(h), 2)
        - Fraction(k * sum(a), 2)
        + sum(s * v for s, v in zip(sigma, h, strict=True))
        + sum(v * w for v, w in zip(zeta, a, strict=True))
    )


def decomposition(profile: Sequence[int], sigma: Sequence[int], zeta: Sequence[int]) -> int:
    """257 + sum sigma(sigma+2-d) + sum zeta(zeta-6), the certified separable form."""

    core = [d for d in profile if d]
    return (
        PROPOSED_CAP
        + sum(s * (s + CORE_TERM_CONSTANT - d) for d, s in zip(core, sigma, strict=True))
        + sum(v * (v - ZERO_TERM_CONSTANT) for v in zeta)
    )


def packet_objective(profile: Sequence[int], sigma: Sequence[int], zeta: Sequence[int]) -> int:
    """The proposed 257 - 10r + sum sigma(6-d+sigma) + sum zeta^2 with r = sum zeta."""

    core = [d for d in profile if d]
    r = sum(zeta)
    return (
        PROPOSED_CAP
        - 10 * r
        + sum(s * (6 - d + s) for d, s in zip(core, sigma, strict=True))
        + (sum(v * v for v in zeta))
    )


def identity_points(k: int, z: int) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    """0, e_i and 2e_i: these values fix every separable quadratic in k+z variables."""

    points = [((0,) * k, (0,) * z)]
    for i in range(k + z):
        for step in (1, 2):
            v = [0] * (k + z)
            v[i] = step
            points.append((tuple(v[:k]), tuple(v[k:])))
    return points


def core_zero_theorem(pid: str) -> dict[str, object]:
    """T <= 257 for every legal structure of the target profile, by the proof above."""

    p = split.profile_values(pid)
    require(chase.profile_id(p) == pid == C_PROFILE, "theorem is stated for one profile only")
    core = [d for d in p if d]
    k, z = len(core), p.count(0)
    phi = sum(comb(13 - d, 2) for d in p) - 606
    require(
        (k, z, min(core), sum(p)) == (13, 7, 4, 66)
        and phi == 299
        and comb(20, 3) - 18 * (comb(20, 2) - 93) == -606
        and sum(6 + d for d in p) == 2 * 93
        and 13 - z == 6
        and z - 7 == 0,
        "core-zero premises fail",
    )
    sigma_ranges = {d: range(7 - d) for d in sorted(set(core), reverse=True)}
    zeta_range = range(7)
    require(all(max(r) <= 2 for r in sigma_ranges.values()), "core cross capacity exceeds two")
    # Polynomial identities: F(e44) = D + (sum sigma - sum zeta)/2 and packet F = D +
    # 4(sum sigma - sum zeta) hold at the 1+2(k+z) points fixing a separable quadratic.
    for sigma, zeta in identity_points(k, z):
        gap = sum(sigma) - sum(zeta)
        f = split_objective(p, sigma, zeta)
        require(f == decomposition(p, sigma, zeta) + Fraction(gap, 2), "split identity fails")
        require(
            packet_objective(p, sigma, zeta) == decomposition(p, sigma, zeta) + 4 * gap,
            "proposed closed form fails",
        )
    core_terms = {
        d: {s: s * (s + CORE_TERM_CONSTANT - d) for s in values}
        for d, values in sigma_ranges.items()
    }
    zero_terms = {v: v * (v - ZERO_TERM_CONSTANT) for v in zeta_range}
    maxima = [max(core_terms[d].values()) for d in core] + [max(zero_terms.values())] * z
    cap = PROPOSED_CAP + sum(maxima)
    require(all(m == 0 for m in maxima) and cap == PROPOSED_CAP, "separable maximum exceeds 257")
    equality = {
        "CORE_SIGMA": {str(d): [s for s, v in t.items() if v == 0] for d, t in core_terms.items()},
        "ZERO_ZETA": [v for v, w in zero_terms.items() if w == 0],
        "P": 0,
    }
    require(
        equality["CORE_SIGMA"] == {"6": [0], "5": [0], "4": [0, 2]}
        and equality["ZERO_ZETA"] == [0, 6],
        "equality conditions changed",
    )
    return {
        "PROFILE_ID": pid,
        "CORE_VERTICES": k,
        "ZERO_VERTICES": z,
        "PHI": phi,
        "F_CLOSED_FORM": "257-10r+sum sigma(6-d+sigma)+sum zeta^2",
        "F_MINUS_257": "sum sigma(sigma+2-d)+sum zeta(zeta-6)",
        "SIGMA_RANGES": {str(d): list(r) for d, r in sigma_ranges.items()},
        "ZETA_RANGE": list(zeta_range),
        "CORE_TERMS": {str(d): {str(s): v for s, v in t.items()} for d, t in core_terms.items()},
        "ZERO_TERMS": {str(v): w for v, w in zero_terms.items()},
        "IDENTITY_POINTS_CHECKED": len(identity_points(k, z)),
        "EQUALITY_CONDITIONS": equality,
        "TRIANGLE_CAP": cap,
        "STATUS": "PROVEN",
    }


def sts13_blocks() -> tuple[Support, ...]:
    blocks = {
        tuple(sorted((v + s) % 13 for v in base)) for base in STS13_BASE_BLOCKS for s in range(13)
    }
    pairs = [e for b in blocks for e in combinations(b, 2)]
    require(len(blocks) == 26 and sorted(pairs) == list(combinations(range(13), 2)), "not STS13")
    return tuple(sorted(blocks))


def witness() -> tuple[tuple[Support, ...], tuple[Support, ...]]:
    triples = tuple(b for b in sts13_blocks() if b not in REMOVED_BLOCKS)
    return triples, (*CORE_PAIRS, *combinations(ZERO_TICKETS, 2))


def legal_degrees(triples: Sequence[Support], pairs: Sequence[Support]) -> tuple[int, ...]:
    """Independent 22-triple/27-pair incidence and pair-disjointness check."""

    supports = [*triples, *pairs]
    require(
        len(triples) == 22
        and len(pairs) == 27
        and all(len(s) == 3 for s in triples)
        and all(len(s) == 2 for s in pairs),
        "support counts or sizes differ",
    )
    require(
        all(type(v) is int and 0 <= v < 20 for s in supports for v in s)
        and all(len(set(s)) == len(s) for s in supports),
        "support tickets are invalid",
    )
    shadow = [tuple(sorted(e)) for s in supports for e in combinations(s, 2)]
    require(len(shadow) == len(set(shadow)) == 66 + 27, "two tickets share more than one label")
    labels = [sum(v in s for s in supports) for v in range(20)]
    require(labels == [6] * 20, "a ticket does not carry exactly six labels")
    return tuple(sum(v in s for s in triples) for v in range(20))


def triangles(vertices: Sequence[int], edges: set[tuple[int, int]]) -> int:
    return sum(
        (a, b) in edges and (a, c) in edges and (b, c) in edges
        for a, b, c in combinations(sorted(vertices), 3)
    )


def realization_split(triples: Sequence[Support], pairs: Sequence[Support]) -> dict[str, object]:
    """Count T directly and confirm T = Phi - t(H) = F - P with every P part >= 0."""

    d = legal_degrees(triples, pairs)
    r5.validate_k20_support_realization(triples, pairs, d)
    g = {(min(x, y), max(x, y)) for s in (*triples, *pairs) for x, y in combinations(s, 2)}
    h = set(combinations(range(20), 2)) - g
    nb = [{w for w in range(20) if (min(v, w), max(v, w)) in g} for v in range(20)]
    core = [v for v in range(20) if d[v]]
    zero = [v for v in range(20) if not d[v]]
    m = {e for e in h if d[e[0]] and d[e[1]]}
    mz = {e for e in h if not d[e[0]] and not d[e[1]]}
    sigma = [len(nb[v] & set(zero)) for v in core]
    zeta = [len(nb[u] & set(core)) for u in zero]
    parts = [
        triangles(core, m),
        triangles(zero, mz),
        sum(len(nb[x] & nb[y] & set(zero)) for x, y in m),
        sum(len(nb[u] & nb[w] & set(core)) for u, w in mz),
    ]
    t = triangles(range(20), g)
    profile = [d[v] for v in core] + [0] * len(zero)
    phi = sum(comb(13 - v, 2) for v in d) - 606
    f = split_objective(profile, sigma, zeta)
    require(sum(sigma) == sum(zeta), "cross-edge counts differ")
    require(
        t == phi - triangles(range(20), h) and t == f - sum(parts) and min(parts) >= 0,
        "split identity fails on the realization",
    )
    require(
        f == decomposition(profile, sigma, zeta) == packet_objective(profile, sigma, zeta),
        "realization objective forms differ",
    )
    return {
        "PROFILE_ID": chase.profile_id(split.profile_values(d)),
        "TRIANGLES": t,
        "F": int(f),
        "P_TERMS": parts,
        "SIGMA": sigma,
        "ZETA": zeta,
        "R": sum(sigma),
    }


def route_b(cap: int) -> tuple[list[Term], int]:
    """R32 envelope at cap, equal to the split integer form, rechecked in rationals."""

    p = split.profile_values(C_PROFILE)
    terms = r32.route_b_envelope(p, cap, S4_BASE)
    require(terms == split.route_b_terms(p, cap, S4_BASE), "Route-B implementations differ")
    g = [6 + d for d in p]
    w, u = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    a_max = Fraction(sum(d * (v - 2) for d, v in zip(p, g, strict=True)), 3)
    for t, bound, k4, contained, s4, s3 in terms:
        excess = Fraction(u - (max(g) - 2) * (w - 3 * t), 4)
        require(k4 == max(0, -((-excess.numerator) // excess.denominator)), "K4 floor")
        require(
            contained == min(k4, int(a_max)) and s4 == max(S4_BASE, 679 * k4 - 231 * contained),
            "S4 floor",
        )
        exact = 372_228_640 - 63_838_600 + s3 - Fraction(4 * s4, 7)
        require(s3 == 2800 * w + 11872 * (t - 22) - 30800 and 0 <= bound - exact < 1, "S3 bound")
    return terms, max(term[1] for term in terms)


def two_row_ledger(
    final: Mapping[str, object],
) -> tuple[dict[str, Row], dict[str, Row], dict[str, str]]:
    """The 4,647-row replay and cc493492's two certified updates, matched to its result."""

    ledger, _base, provenance = two.baseline()
    a, b = two.certificate(two.A)[0], two.certificate(two.B)[0]
    updates = two.certified_updates(ledger, a, b)
    after = two.apply_updates(ledger, updates)
    stored = {text(object_row(u)["PROFILE_ID"]): object_row(u) for u in rows(final["ROW_UPDATES"])}
    require(
        len(ledger) == two.LEDGER_ROWS
        and two.bounds_digest(ledger) == two.LEDGER_DIGEST
        and two.full_digest(after) == final["FULL_ROWS_SHA256_AFTER"]
        and two.bounds_digest(after) == final["BOUNDS_SHA256_AFTER"]
        and two.family(after) == (TWO_ROW_BOUND, [C_PROFILE])
        and sorted(stored) == sorted((two.A_PROFILE, two.B_PROFILE))
        and all(
            json.loads(json.dumps(asdict(after[pid]))) == stored[pid]["AFTER"] for pid in stored
        ),
        "two-row ledger does not reproduce cc493492",
    )
    return ledger, after, provenance


def apply_third(ledger: Mapping[str, Row], bound: int, cap: int, source: str) -> dict[str, Row]:
    """Install exactly one tighter row for the target profile; nothing else may move."""

    old = ledger[C_PROFILE]
    require(type(bound) is int and type(cap) is int, "update must use exact integers")
    require(
        (old.bound, old.cap, old.s4_base) == (TWO_ROW_BOUND, CURRENT_CAP, S4_BASE)
        and bound < old.bound
        and 22 <= cap < old.cap,
        "third update does not tighten the recorded row",
    )
    after = dict(ledger)
    after[C_PROFILE] = replace(old, bound=bound, cap=cap, source=source)
    require(
        set(after) == set(ledger) and [p for p in ledger if ledger[p] != after[p]] == [C_PROFILE],
        "third update changed another row",
    )
    return after


def family(ledger: Mapping[str, Row]) -> tuple[int, list[str], int]:
    """Maximum over every row and the cursor, all tied owners, and the next level."""

    terms = sorted(
        [(row.bound, pid) for pid, row in ledger.items()]
        + [(chase.prior.CURSOR_BOUND, chase.prior.CURSOR_ID)],
        reverse=True,
    )
    best = terms[0][0]
    owners = sorted(pid for bound, pid in terms if bound == best)
    require((best, owners) == two.family(ledger), "family recomputation differs")
    return best, owners, max(bound for bound, _pid in terms if bound < best)


def compute_result() -> dict[str, object]:
    final, addendum = pinned_two_row()
    theorem = core_zero_theorem(C_PROFILE)
    seen = realization_split(*witness())
    require(
        (seen["PROFILE_ID"], seen["TRIANGLES"], seen["F"], seen["P_TERMS"])
        == (C_PROFILE, PROPOSED_CAP, PROPOSED_CAP, [0, 0, 0, 0]),
        "witness does not attain 257",
    )
    cross = split.analyze_realization(*witness())
    require((cross["TRIANGLES"], cross["P_TOTAL"]) == (257, 0), "e44 realization check differs")
    relaxation = split.split_certificate(C_PROFILE)
    configs = list(split.degree_configurations(C_PROFILE))
    require(
        len(configs) == relaxation["DEGREE_CONFIGURATION_COUNT"] == 145
        and all(
            split_objective(c.profile, c.sigma, c.zeta)
            == c.f
            == decomposition(c.profile, c.sigma, c.zeta)
            for c in configs
        )
        and max(c.f for c in configs) == relaxation["TRIANGLE_CAP"] == PROPOSED_CAP,
        "supplemental reduced configurations disagree",
    )
    old_terms, old_bound = route_b(CURRENT_CAP)
    new_terms, new_bound = route_b(PROPOSED_CAP)
    require(
        old_bound == TWO_ROW_BOUND and new_terms == old_terms[: len(new_terms)],
        "Route B does not extend the existing row authority",
    )
    ledger, two_row, provenance = two_row_ledger(final)
    provenance = dict(sorted({**provenance, **module_provenance()}.items()))
    recorded = two_row[C_PROFILE].realization
    if recorded is None:
        raise AssertionError("target row has no recorded realization")
    recorded_seen = realization_split(*recorded)
    require(
        recorded_seen["PROFILE_ID"] == C_PROFILE
        and integer(recorded_seen["TRIANGLES"]) <= PROPOSED_CAP,
        "recorded realization exceeds the cap",
    )
    source = f"{TASK_ID}:CORE_ZERO_T257_THEOREM"
    three_row = apply_third(two_row, new_bound, PROPOSED_CAP, source)
    before, before_owners, _ = family(two_row)
    best, owners, next_level = family(three_row)
    original, _original_owners, _ = family(ledger)
    require(
        all(three_row[p] == two_row[p] for p in (two.A_PROFILE, two.B_PROFILE))
        and original == ORIGINAL_BOUND
        and (before, before_owners) == (TWO_ROW_BOUND, [C_PROFILE]),
        "certified two-row updates or baselines were not preserved",
    )
    changed = sorted(p for p in ledger if ledger[p] != three_row[p])
    actual: dict[str, object] = {
        "PROFILE_BOUND_AFTER": new_bound,
        "FAMILY_BOUND_AFTER": best,
        "DELTA_VS_TWO_ROW": before - best,
        "DELTA_VS_ORIGINAL": original - best,
        "NEW_FAMILY_OWNER": owners,
        "GAP_TO_INCUMBENT": best - INCUMBENT,
    }
    expected: dict[str, object] = {
        "PROFILE_BOUND_AFTER": 313_339_312,
        "FAMILY_BOUND_AFTER": 313_401_464,
        "DELTA_VS_TWO_ROW": 388,
        "DELTA_VS_ORIGINAL": 2_544,
        "NEW_FAMILY_OWNER": ["66665555555421000000"],
        "GAP_TO_INCUMBENT": 137_576,
    }
    b_identity = object_row(final["CERTIFICATE_B_IDENTITY"])
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "THREE_ROW_COMBINED_RESULT_PENDING_FRESH_JUDGE",
        "PROOF": __doc__,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": TWO_RESULT_SHA256,
        "ORIGINAL_SPLIT_CAP_HEAD": two.BASE_HEAD,
        "ORIGINAL_RESULT_SHA256": two.BASE_RESULT_SHA256,
        "LEDGER_DIGEST": two.LEDGER_DIGEST,
        "LEDGER_ROWS": len(ledger),
        "ADDENDUM_AUDIT": addendum,
        "PRIOR_COMBINED_FRESH_JUDGE": final["PRIOR_COMBINED_FRESH_JUDGE"],
        "CERTIFICATE_A_IDENTITY": final["CERTIFICATE_A_IDENTITY"],
        "CERTIFICATE_B_IDENTITY": b_identity,
        "CERTIFICATE_B_JUDGE_STATUS": b_identity["JUDGE_STATUS"],
        "CERTIFICATE_B_CAVEATS": b_identity["JUDGE_CAVEATS_TEXT"],
        "CERTIFICATE_B_CAVEATS_SOURCE": b_identity["JUDGE_CAVEATS_SOURCE"],
        "SUPPORT_MODEL": support_model(),
        "THEOREM_T257": theorem,
        "T257_REALIZATION": {
            "SOURCE": "INDEPENDENT_CONSTRUCTION_STS13_MINUS_FOUR_BLOCKS_PLUS_K7",
            "REPORTED_REALIZATION_SUPPLIED": False,
            "REMOVED_STS13_BLOCKS": [list(b) for b in REMOVED_BLOCKS],
            "TRIPLES": [list(s) for s in witness()[0]],
            "PAIRS": [list(s) for s in witness()[1]],
            **seen,
            "STATUS": "PASS",
        },
        "RECORDED_ROW_REALIZATION": recorded_seen,
        "SUPPLEMENTAL_REDUCED_CONFIGURATIONS": {
            "COUNT": len(configs),
            "MAX_F": max(c.f for c in configs),
            "BRANCH_COUNTS": relaxation["BRANCH_COUNTS"],
            "ROLE": "SUPPLEMENTAL_NOT_PROOF",
        },
        "ROUTE_B": {
            "S4_BASE": S4_BASE,
            "CAP_BEFORE": CURRENT_CAP,
            "BOUND_BEFORE": old_bound,
            "CAP_AFTER": PROPOSED_CAP,
            "ALL_T_TERMS": [list(t) for t in new_terms],
            "ALL_T_MAX_BOUND": new_bound,
            "STATUS": "PASS_INTEGER_AND_RATIONAL",
        },
        "PROFILE_BOUND_BEFORE": TWO_ROW_BOUND,
        "CERTIFICATES_COMPOSED": 3,
        "ROWS_CHANGED_VS_ORIGINAL": changed,
        "ROW_UPDATE": {
            "PROFILE_ID": C_PROFILE,
            "BEFORE": asdict(two_row[C_PROFILE]),
            "AFTER": asdict(three_row[C_PROFILE]),
        },
        "FAMILY_BOUND_BEFORE": before,
        "ORIGINAL_FAMILY_BOUND": original,
        **actual,
        "NEXT_COMPETING_BOUND": next_level,
        "EXPECTED_VALUES_MATCH": actual == expected,
        "EXPECTED_VALUE_DIFFERENCES": {
            k: {"EXPECTED": expected[k], "ACTUAL": actual[k]}
            for k in expected
            if actual[k] != expected[k]
        },
        "NEW_OWNER_ROWS": {p: asdict(three_row[p]) for p in owners if p in three_row},
        "CURRENT_ACCEPTED_BEST": INCUMBENT,
        "RESOLVED_ROWS_ABOVE_INCUMBENT": sum(r.bound > INCUMBENT for r in three_row.values()),
        "BOUNDS_SHA256_AFTER": two.bounds_digest(three_row),
        "FULL_ROWS_SHA256_AFTER": two.full_digest(three_row),
        "MODULE_PROVENANCE": provenance,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "FROZEN_LEDGER_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SEARCH_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "SOLVER_CALLS": 0,
    }


def main() -> None:
    result = compute_result()
    payload = two.render(result)
    digest = sha256(payload)
    target = ROOT / two.RESULT_DIRECTORY / f"{RESULT_STEM}-{digest}.json"
    if target.exists():
        require(target.read_bytes() == payload, "content-addressed output collision")
    else:
        with target.open("xb") as output:
            output.write(payload)
    keys = (
        "PROFILE_BOUND_AFTER",
        "FAMILY_BOUND_AFTER",
        "DELTA_VS_TWO_ROW",
        "DELTA_VS_ORIGINAL",
        "NEW_FAMILY_OWNER",
        "GAP_TO_INCUMBENT",
        "EXPECTED_VALUES_MATCH",
    )
    print(json.dumps({**{k: result[k] for k in keys}, "RESULT": str(target), "SHA256": digest}))


if __name__ == "__main__":
    main()
