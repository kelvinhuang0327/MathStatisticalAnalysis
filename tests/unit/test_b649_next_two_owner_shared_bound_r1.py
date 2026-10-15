"""Independent exhaustive degree relaxation, arithmetic, and fixed-child checks."""

from __future__ import annotations

import copy
import json
import os
import subprocess
from collections import Counter
from fractions import Fraction
from itertools import combinations, product
from math import comb
from pathlib import Path
from typing import cast

import pytest

# Keep bootstrap first so certificate imports resolve from the pinned source snapshot.
# isort: off
from tests.unit.b649_certificate_replay import replay_certificate_call, replay_fixed_result
from lottolab.research import b649_next_two_owner_shared_bound_r1 as cert
# isort: on

IDS = ("66555555555521100000", "66655555554432000000", "66666555554411100000")
HISTS = (
    {0: 5, 1: 2, 2: 1, 5: 10, 6: 2},
    {0: 6, 2: 1, 3: 1, 4: 2, 5: 7, 6: 3},
    {0: 5, 1: 3, 4: 2, 5: 5, 6: 5},
)


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return replay_fixed_result(cert.__name__)


def hh(degrees):
    ds = sorted(degrees, reverse=True)
    while ds:
        top = ds.pop(0)
        if not top:
            return all(x == 0 for x in ds)
        if top < 0 or top > len(ds):
            return False
        for i in range(top):
            ds[i] -= 1
        if any(x < 0 for x in ds):
            return False
        ds.sort(reverse=True)
    return True


def graph(n, mask):
    edges = {p for i, p in enumerate(combinations(range(n), 2)) if mask & (1 << i)}
    ds = tuple(sum(v in e for e in edges) for v in range(n))
    return edges, ds


def count_triangles(n, edges):
    return sum(all(e in edges for e in combinations(t, 2)) for t in combinations(range(n), 3))


def independent_triangle_lower(degrees, prefix=True):
    ds = sorted(degrees, reverse=True)
    size, edges = len(ds), sum(ds) // 2
    lb = max(0, -(-(sum(a * a for a in ds) - size * edges) // 3))
    if prefix:
        for h in range(1, size + 1):
            crossing = sum(min(h, a) for a in ds[h:])
            minimum_edges = max(0, -(-(sum(ds[:h]) - crossing) // 2))
            costs = sorted(max(0, ds[i] + ds[j] - size) for i, j in combinations(range(h), 2))
            lb = max(lb, sum(costs[:minimum_edges]) - h * (h - 1) * (h - 2) // 3)
    return lb


def independent_induced(degrees, size):
    # Enumerate every possible outside vertex subset, independently of sort-based code.
    maximum_outside = max(sum(s) for s in combinations(degrees, len(degrees) - size))
    return max(0, sum(degrees) // 2 - maximum_outside)


def independent_states(pid):
    ds = tuple(x for x in map(int, pid) if x)
    k, z = len(ds), 20 - len(ds)
    groups = sorted(set(ds), reverse=True)
    signatures = {
        tuple(
            (d, tuple(sorted(s for x, s in zip(ds, sigma, strict=True) if x == d))) for d in groups
        )
        for sigma in product(*(range(min(z, 6 - d) + 1) for d in ds))
    }
    # Enumerate all LOCAL zero-shore graphs, not any full support graph.
    zetas = set()
    for mask in range(1 << comb(z, 2)):
        _, zero_degrees = graph(z, mask)
        if max(zero_degrees) <= 6:
            zetas.add(tuple(sorted(6 - a for a in zero_degrees)))
    B = 1140 - sum((6 + x) * (13 - x) for x in map(int, pid)) // 2
    states = []
    for signature in sorted(signatures):
        active = tuple(d for d, sigmas in signature for _ in sigmas)
        sigma = tuple(s for _, values in signature for s in values)
        m = tuple(k - 7 - d + s for d, s in zip(active, sigma, strict=True))
        if not hh(m):
            continue
        r = sum(sigma)
        for ze in sorted(zetas):
            if sum(ze) != r or not all(
                sum(sorted(a, reverse=True)[:h]) <= sum(min(h, b0) for b0 in b)
                for a, b in ((sigma, ze), (ze, sigma))
                for h in range(1, len(a) + 1)
            ):
                continue
            n = tuple(z - 7 + a for a in ze)
            ss = sum(a * b for a, b in zip(sigma, m, strict=True))
            zs = sum(a * b for a, b in zip(ze, n, strict=True))
            # Derive constant directly from shore edge sums, not a shared literal.
            constant = (z * (k * (k - 7) - 66) + k * z * (z - 7)) // 2
            raw = B - constant - 10 * r + ss + zs
            ck = sum(independent_induced(n, s) for s in sigma)
            cz = sum(independent_induced(m, a) for a in ze)
            tm, tn = independent_triangle_lower(m), independent_triangle_lower(n)
            states.append(
                {
                    "R": r,
                    "SIGMA_BY_D": [[d, list(s)] for d, s in signature],
                    "ZETA": list(ze),
                    "M_DEGREES": list(m),
                    "N_DEGREES": list(n),
                    "SIGMA_SCORE": ss,
                    "ZETA_SCORE": zs,
                    "REMAINDER_LOWER": {"T_M": tm, "T_N": tn, "C_K": ck, "C_Z": cz},
                    "WITHOUT_REMAINDER": raw,
                    "WITHOUT_PREFIX_TRIANGLE_BOUND": raw
                    - ck
                    - cz
                    - independent_triangle_lower(m, False)
                    - independent_triangle_lower(n, False),
                    "UPPER": raw - ck - cz - tm - tn,
                }
            )
    return len(signatures), zetas, states


def independent_term(pid, t, floor=112):
    d = list(map(int, pid))
    g = [6 + a for a in d]
    W = sum(a * (a - 1) // 2 for a in g)
    J = sum(a * (a - 1) * (a - 2) // 6 for a in g)
    q = max(0, -(-(J - (max(g) - 2) * (W - 3 * t)) // 4))
    a = min(q, sum(x * (x + 4) for x in d) // 3)
    s4 = max(floor, 448 * a + 679 * (q - a))
    s3 = 2800 * W + 11872 * (t - 22) - 30800
    exact = Fraction(308390040 + s3) - Fraction(4, 7) * s4
    return [t, -(-exact.numerator // exact.denominator), q, a, s4, s3]


@pytest.mark.parametrize("i", range(3))
def test_exact_facts_and_separate_split(i, result):
    f = result["PROFILES"][IDS[i]]["FACTS"]
    assert Counter(map(int, IDS[i])) == HISTS[i]
    assert f["D_HISTOGRAM"] == {str(k): v for k, v in HISTS[i].items()}
    assert (f["DEGREE_SUM_D"], f["DEGREE_SUM_G"], f["EDGES"]) == (66, 186, 93)
    assert (f["WEDGES"], f["GOODMAN"]) == ((827, 293), (827, 293), (833, 299))[i]
    assert (f["K"], f["Z"]) == ((15, 5), (14, 6), (15, 5))[i]
    assert f["SPLIT_H_CONSTANT"] == (60, 54, 60)[i]
    assert f["M_EDGE_SUM_CONSTANT"] == (54, 32, 54)[i]
    assert f["N_EDGE_SUM_CONSTANT"] == (-10, -6, -10)[i]
    assert f["ZETA_MIN"] == (2, 1, 2)[i]
    assert f["J"] == (2316, 2315, 2370)[i]
    assert f["A_MAX"] == (197, 197, 201)[i]
    assert sum(f["PAIR_DEGREES"]) == 54


@pytest.mark.parametrize("i", range(3))
def test_all_labelled_sigma_and_zero_graphs(i, result):
    pid = IDS[i]
    count, zetas, states = independent_states(pid)
    proof = result["PROFILES"][pid]["RELAXATION"]
    assert count == proof["SIGMA_SIGNATURES"] == (1155, 960, 2016)[i]
    assert tuple(sorted(zetas)) == cert.zeta_sequences((5, 6, 5)[i])
    assert len(zetas) == proof["ZETA_MULTISET_COUNT"] == (31, 102, 31)[i]
    assert len(states) == proof["RETAINED_STATE_COUNT"] == (1040, 1206, 1710)[i]
    assert sorted(cert.render(s) for s in states) == sorted(
        cert.render(s) for s in proof["ALL_RETAINED_STATES"]
    )
    maximum = max(s["UPPER"] for s in states)
    assert maximum == proof["CAP"] == (260, 227, 259)[i]
    assert len(proof["ALL_ARGMAX"]) == 1
    assert proof["ALL_ARGMAX"] == [s for s in states if s["UPPER"] == maximum]
    assert proof["STATES_SHA256"] == cert.sha(cert.render(proof["ALL_RETAINED_STATES"]))
    assert proof["ABLATION_CAPS"] == {
        "WITHOUT_REMAINDER": (265, 227, 295)[i],
        "WITHOUT_PREFIX_TRIANGLE_BOUND": (260, 227, 272)[i],
        "UPPER": maximum,
    }


def test_remainder_primitives_on_every_five_vertex_graph():
    # Exhaustive mechanics check. Universality is the general proof, not this check.
    for mask in range(1024):
        edges, degrees = graph(5, mask)
        triangles = count_triangles(5, edges)
        assert 0 <= cert.triangle_lower(degrees) <= triangles
        for size in range(6):
            lower = cert.induced_edge_lower(degrees, size)
            assert lower == independent_induced(degrees, size)
            for subset in combinations(range(5), size):
                actual = sum(set(e) <= set(subset) for e in edges)
                assert 0 <= lower <= actual


def test_exact_split_and_each_nonnegative_remainder_on_all_small_graphs():
    for mask in range(1024):
        G, degrees = graph(5, mask)
        H = set(combinations(range(5), 2)) - G
        K, Z = {0, 1, 2}, {3, 4}
        M = {e for e in H if set(e) <= K}
        N = {e for e in H if set(e) <= Z}
        sigma = {x: sum(tuple(sorted((x, z))) in G for z in Z) for x in K}
        zeta = {z: sum(tuple(sorted((x, z))) in G for x in K) for z in Z}
        m = {x: sum(x in e for e in M) for x in K}
        n = {z: sum(z in e for e in N) for z in Z}
        cz = sum(tuple(sorted((a, z))) in G and tuple(sorted((b, z))) in G for a, b in M for z in Z)
        ck = sum(tuple(sorted((x, a))) in G and tuple(sorted((x, b))) in G for a, b in N for x in K)
        tm = sum(all(e in M for e in combinations(t, 2)) for t in combinations(K, 3))
        tn = 0
        assert min(tm, tn, cz, ck) >= 0
        rhs = 2 * len(M) + 3 * len(N) - sum(sigma[x] * m[x] for x in K)
        rhs -= sum(zeta[z] * n[z] for z in Z)
        assert count_triangles(5, H) == rhs + tm + tn + cz + ck
        assert count_triangles(5, G) + count_triangles(5, H) == (
            10 - sum(d * (4 - d) for d in degrees) // 2
        )


@pytest.mark.parametrize("i", range(3))
def test_every_old_new_base_term_and_all_argmax(i, result):
    pid, p = IDS[i], result["PROFILES"][IDS[i]]
    assert p["OLD_CAP"] == (265, 265, 264)[i]
    assert p["NEW_CAP"] == (260, 227, 259)[i]
    for prefix in ("OLD", "NEW"):
        cap = p[prefix + "_CAP"]
        terms = [
            independent_term(pid, t, p["S4_BY_T"].get(str(t), 112)) for t in range(22, cap + 1)
        ]
        assert terms == p[prefix + "_ALL_T_TERMS"]
        bound = max(t[1] for t in terms)
        assert p[prefix + "_BOUND"] == bound
        assert p[prefix + "_ALL_ARGMAX"] == [t for t in terms if t[1] == bound]
    assert p["OLD_BOUND"] == (313392128, 313392128, 313391920)[i]
    assert p["OLD_ALL_ARGMAX"][0][0] == (265, 265, 263)[i]
    assert p["NEW_ALL_ARGMAX"][0][0] == (260, 227, 259)[i]


def test_exact_base_authorities_and_rounding(result):
    auth = result["S4_S5_AUTHORITY"]
    for i, pid in enumerate(IDS):
        a = auth["PER_PROFILE"][pid]
        assert a["ACCEPTED_R30_CAP"] == (265, 265, 264)[i]
        assert a["R30_ATTEMPT"]["ATTEMPT_INDEX"] == (3396, 3395, 2779)[i]
        assert a["NB_CAP"] == (271, 266, 264)[i]
        assert a["CLASS_CAP"] == (274, 274, 276)[i]
        assert a["S4_BASE"] == 112 and a["S5_USED"] is False
        assert pid not in auth["S5_ADOPTED_CERTIFICATES"]
    assert auth["PER_PROFILE"][IDS[2]]["S4_BY_T"] == {"264": 309183}
    assert auth["S5_ALL_T_ADOPTION"] == "NOT_VERIFIED"
    for r in range(8):
        assert int(r > 0) <= r - comb(r, 2) + comb(r, 3) - Fraction(4, 7) * comb(r, 4)
    # Test an actual noninteger K4 ceiling and A_max floor from the new profiles.
    f = cert.profile_facts(IDS[1])
    numerator = f["J"] - 10 * (f["WEDGES"] - 3 * 227)
    assert numerator % 4 == 3
    assert independent_term(IDS[1], 227)[2] == numerator // 4 + 1
    assert sum(d * (d + 4) for d in f["D"]) == 592
    assert f["A_MAX"] == 592 // 3
    probe = cert.envelope(IDS[0], 22, {"S4_BASE": 113, "S4_BY_T": {}})[0]
    exact = Fraction(308390040 + probe[5]) - Fraction(4 * 113, 7)
    assert exact.denominator == 7
    assert probe[1] == exact.numerator // exact.denominator + 1
    assert probe == independent_term(IDS[0], 22, 113)


def test_full_family_owner_completeness_and_preservation(result):
    direct = json.loads(cert.pinned_blob(cert.INPUT_HEAD, cert.INPUT_RESULT, cert.INPUT_SHA))
    before, after = result["RESOLVED_ROWS_BEFORE"], result["RESOLVED_ROWS_AFTER"]
    cursor = result["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    assert before == direct["RESOLVED_ROWS_AFTER"]
    assert len(before) == len(after) == 4647 and len(cursor) == 197
    assert result["FAMILY_BEFORE"] == direct["FAMILY_AFTER"]
    assert result["FAMILY_BEFORE"]["ALL_MAX_OWNERS"] == list(IDS[:2])
    assert result["FAMILY_BEFORE"]["NEXT_DISTINCT_BOUND"] == 313391920
    assert sorted(p for p in after if before[p] != after[p]) == list(IDS)
    assert result["FAMILY_AFTER"] == cert.family_summary(after, cursor)
    assert result["FAMILY_AFTER"]["MAXIMUM"] == 313391844
    assert result["FAMILY_DELTA"] == 284
    assert result["ALL_NEW_MAX_OWNERS"] == [
        "65555555555531100000",
        "66555555554441100000",
        "66555555555422100000",
    ]
    merged = after | cursor
    maximum = max(merged.values())
    assert result["ALL_NEW_MAX_OWNERS"] == sorted(p for p, b in merged.items() if b == maximum)
    for highest in IDS[:2]:
        missing = dict(after)
        missing[highest] = before[highest]
        assert cert.family_summary(missing, cursor)["MAXIMUM"] == 313392128
    assert result["CURSOR_197_PRESERVED"] == direct["CURSOR_197_PRESERVED"]
    assert result["INHERITED_EXCLUSION"] == direct["INHERITED_EXCLUSION"]
    assert result["INHERITED_EXCLUSION"]["ORIGINAL_CONDITIONS_VERBATIM"]["COUNT"] == 282
    assert len(after) + len(cursor) + 282 == 5126
    assert result["UPSTREAM_PRIOR_REVIEW_CAVEAT_VERBATIM"] == direct["PRIOR_REVIEW_CAVEAT"]
    assert result["UPSTREAM_WORKER_ATTEMPT_HISTORY_VERBATIM"] == direct["WORKER_ATTEMPT_HISTORY"]
    assert result["PROJECTION_STATUS"] == "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION"
    assert result["FULL_ENVELOPE_TERM_COUNTS"] == {
        "OLD_PER_PROFILE": dict(zip(IDS, (244, 244, 243), strict=True)),
        "NEW_PER_PROFILE": dict(zip(IDS, (239, 206, 238), strict=True)),
        "OLD_TOTAL": 731,
        "NEW_TOTAL": 683,
        "NEW_T_RANGES": dict(zip(IDS, ([22, 260], [22, 227], [22, 259]), strict=True)),
    }


NEGATIVE_CASES = (
    "profile",
    "histogram",
    "wedge",
    "Goodman",
    "split_constant",
    "K",
    "Z",
    "zeta_floor",
    "T_cap",
    "shared_cap",
    "remainder",
    "prefix_remainder",
    "rounding",
    "K4_rounding",
    "Amax_floor",
    "missing_term",
    "endpoint",
    "S4_addition",
    "S4_scope",
    "S5",
    "Git_pin",
    "SHA_pin",
    "source_pin",
    "cursor",
    "exclusion",
    "missing_owner_A",
    "missing_owner_B",
    "argmax",
    "family_delta",
)


@pytest.mark.parametrize("defect", NEGATIVE_CASES)
def test_negative_payload(defect, result):
    bad = copy.deepcopy(result)
    p = bad["PROFILES"][IDS[0]]
    fact_fields = {
        "wedge": "WEDGES",
        "Goodman": "GOODMAN",
        "split_constant": "SPLIT_H_CONSTANT",
        "K": "K",
        "Z": "Z",
        "zeta_floor": "ZETA_MIN",
        "Amax_floor": "A_MAX",
    }
    if defect in fact_fields:
        p["FACTS"][fact_fields[defect]] += 1
    elif defect == "profile":
        p["FACTS"]["PROFILE_ID"] = IDS[1]
    elif defect == "histogram":
        p["FACTS"]["D_HISTOGRAM"]["5"] += 1
    elif defect == "T_cap":
        p["NEW_CAP"] -= 1
    elif defect == "shared_cap":
        bad["SHARED_THEOREM"]["COMMON_T_CAP"] -= 1
    elif defect in ("remainder", "prefix_remainder"):
        p["RELAXATION"]["ALL_RETAINED_STATES"][0]["REMAINDER_LOWER"]["T_M"] += 1
    elif defect in ("rounding", "K4_rounding"):
        p["NEW_ALL_T_TERMS"][-1][1 if defect == "rounding" else 2] -= 1
    elif defect in ("missing_term", "endpoint"):
        p["NEW_ALL_T_TERMS"].pop(100 if defect == "missing_term" else -1)
    elif defect == "S4_addition":
        p["NEW_ALL_T_TERMS"][-1][4] += 112
    elif defect == "S4_scope":
        bad["PROFILES"][IDS[2]]["S4_BY_T"]["259"] = 309183
    elif defect == "S5":
        p["S5_USED"] = True
    elif defect in ("Git_pin", "SHA_pin"):
        bad["INPUT_CERTIFICATE"]["TREE" if defect == "Git_pin" else "SHA256"] = "0" * 64
    elif defect == "source_pin":
        bad["SOURCE_SHA256"] = "0" * 64
    elif defect == "cursor":
        bad["CURSOR_197_PRESERVED"]["ROW_BOUNDS"].pop(
            next(iter(bad["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]))
        )
    elif defect == "exclusion":
        bad["INHERITED_EXCLUSION"]["ORIGINAL_CONDITIONS_VERBATIM"]["COUNT"] = 281
    elif defect in ("missing_owner_A", "missing_owner_B"):
        pid = IDS[int(defect.endswith("B"))]
        bad["RESOLVED_ROWS_AFTER"][pid] = result["RESOLVED_ROWS_BEFORE"][pid]
    elif defect == "argmax":
        p["NEW_ALL_ARGMAX"] = []
    elif defect == "family_delta":
        bad["FAMILY_DELTA"] += 1
    with pytest.raises(ValueError, match="complete exact recomputation"):
        cert.validate_payload(bad, result)


@pytest.mark.parametrize("field", ("SPLIT_H_CONSTANT", "K", "Z", "ZETA_MIN"))
def test_reject_wrong_split_claim(field):
    bad = copy.deepcopy(cert.profile_facts(IDS[0]))
    bad[field] += 1
    with pytest.raises(ValueError, match="profile/split"):
        cert.validate_facts(IDS[0], bad)


@pytest.mark.parametrize("defect", ("input_tree", "base_tree", "parent", "merge", "paths"))
def test_negative_actual_identity_gate(monkeypatch, defect):
    def fake_git(*args, **kwargs):
        if args == ("rev-parse", cert.INPUT_HEAD + "^{tree}"):
            return "bad" if defect == "input_tree" else cert.INPUT_TREE
        if args == ("rev-parse", cert.BASE_HEAD + "^{tree}"):
            return "bad" if defect == "base_tree" else cert.BASE_TREE
        if args == ("rev-parse", "HEAD"):
            return "child"
        if args[0] == "rev-list":
            return (
                "child unrelated"
                if defect == "parent"
                else ("child " + cert.INPUT_HEAD + (" extra" if defect == "merge" else ""))
            )
        return "M\tcanonical.json"

    monkeypatch.setattr(cert, "git", fake_git)
    with pytest.raises(ValueError):
        cert.verify_identity()


def test_negative_actual_sha_gate_and_profile_cap():
    with pytest.raises(ValueError, match="authority blob identity"):
        cert.pinned_blob(cert.INPUT_HEAD, cert.INPUT_RESULT, "0" * 64)
    with pytest.raises(ValueError, match="wrong exact profile"):
        cert.profile_facts("66665555555421000000")
    for cap in (21, 276, True, 260.0):
        with pytest.raises(ValueError, match="T cap"):
            cert.envelope(IDS[0], cap, {"S4_BASE": 112, "S4_BY_T": {}})


def test_real_isolated_single_parent_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: dict[str, object]
) -> None:
    """Real Git objects under OS temp, without a second worktree or branch."""
    scratch = tmp_path / "child.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(scratch)], check=True)
    common = Path(cert.git("rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = cert.ROOT / common
    monkeypatch.setenv("GIT_ALTERNATE_OBJECT_DIRECTORIES", str(common.resolve() / "objects"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "isolated.index"))

    def run(*args, data=None):
        return (
            subprocess.check_output(["git", *args], cwd=scratch, input=data, env=os.environ.copy())
            .decode()
            .strip()
        )

    run("read-tree", cert.INPUT_HEAD)
    for path in (cert.SOURCE, cert.TEST, cert.RESULT):
        contents = cert.render(result) if path == cert.RESULT else (cert.ROOT / path).read_bytes()
        oid = run("hash-object", "-w", "--stdin", data=contents)
        run("update-index", "--add", "--cacheinfo", "100644", oid, path)
    tree = run("write-tree")
    child = run(
        "-c",
        "user.name=Verifier fixture",
        "-c",
        "user.email=fixture@invalid",
        "commit-tree",
        tree,
        "-p",
        cert.INPUT_HEAD,
        data=b"Disposable child fixture\n",
    )
    assert cert.verify_identity(child, scratch) == "FIXED_DIRECT_CHILD"
    replay_certificate_call(cert.__name__, "verify_result", child, repo=scratch)
    candidate_result = cast(
        dict[str, object],
        replay_certificate_call(cert.__name__, "compute_result", child, repo=scratch),
    )
    assert candidate_result["FAMILY_AFTER"] == result["FAMILY_AFTER"]


def test_stored_exact_result():
    assert replay_certificate_call(cert.__name__, "verify_result") is None
