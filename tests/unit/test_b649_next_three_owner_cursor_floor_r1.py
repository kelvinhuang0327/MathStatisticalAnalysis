"""Independent algebra, complete exact envelopes, ledger and adverse identity tests."""

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
from typing import Any, cast

import pytest

# The certificate is introduced by the current math input commit, newer than
# its INPUT_HEAD. Keep the shared replay bootstrap first, then bind that source.
# isort: off
from tests.unit.b649_certificate_replay import replay_certificate_call, replay_fixed_result
from lottolab.research import b649_next_three_owner_cursor_floor_r1 as cert
# isort: on

type Record = dict[str, Any]
_CERTIFICATE_SOURCE_HEAD = "2159f5257e8c0742662bc087f4cf9bb275a515a5"
_CERTIFICATE_SOURCE_TREE = "2018f025de0a5d47c0542bfa00cc5d8bba6ac8de"
IDS = ("65555555555531100000", "66555555554441100000", "66555555555422100000")
HISTS = (
    {0: 5, 1: 2, 3: 1, 5: 11, 6: 1},
    {0: 5, 1: 2, 4: 3, 5: 8, 6: 2},
    {0: 5, 1: 1, 2: 2, 4: 1, 5: 9, 6: 2},
)


@pytest.fixture(scope="module")
def result() -> Record:
    return cast(
        Record,
        replay_fixed_result(
            cert.__name__,
            source_head=_CERTIFICATE_SOURCE_HEAD,
            source_tree=_CERTIFICATE_SOURCE_TREE,
            operation_head=_CERTIFICATE_SOURCE_HEAD,
            operation_tree=_CERTIFICATE_SOURCE_TREE,
        ),
    )


def independent_term(pid: str, t: int, floor: int = 112) -> list[int]:
    d = list(map(int, pid))
    g = [6 + a for a in d]
    w = sum(a * (a - 1) // 2 for a in g)
    j = sum(a * (a - 1) * (a - 2) // 6 for a in g)
    q_fraction = Fraction(j - (max(g) - 2) * (w - 3 * t), 4)
    q = max(0, -(-q_fraction.numerator // q_fraction.denominator))
    a = min(q, sum(x * (x + 4) for x in d) // 3)
    s4 = max(floor, 448 * a + 679 * (q - a))
    s3 = 2800 * (w - 3 * t) + 20272 * (t - 22) + 154000
    exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
    return [t, -(-exact.numerator // exact.denominator), q, a, s4, s3]


@pytest.mark.parametrize("i", range(3))
def test_independent_exact_histogram_and_constraints(i: int, result: Record) -> None:
    pid = IDS[i]
    f = result["PROFILES"][pid]["FACTS"]
    d = list(map(int, pid))
    assert Counter(d) == HISTS[i]
    assert f["D_HISTOGRAM"] == {str(k): v for k, v in HISTS[i].items()}
    assert (sum(d), sum(x * x for x in d)) == (66, 322)
    assert (f["DEGREE_SUM_D"], f["DEGREE_SUM_G"], f["EDGES"]) == (66, 186, 93)
    assert (f["WEDGES"], f["GOODMAN"], f["K"], f["Z"]) == (824, 290, 15, 5)
    assert f["ASSUMPTIONS"] == {
        "TICKETS": 20,
        "LABELS_PER_TICKET": 6,
        "LABELS": 49,
        "TRIPLE_LABELS": 22,
        "PAIR_LABELS": 27,
        "PAIR_LINEARITY": True,
    }
    assert f["J"] == (2289, 2290, 2292)[i]
    assert f["A_MAX_NUMERATOR"] == 586 and f["A_MAX"] == 195
    assert sum(f["PAIR_DEGREES"]) == 54
    assert (f["M_DEGREE_OFFSET"], f["N_DEGREE_OFFSET"]) == (8, -2)
    assert (f["M_EDGE_SUM_CONSTANT"], f["N_EDGE_SUM_CONSTANT"]) == (54, -10)
    assert f["SPLIT_H_CONSTANT"] == 60 and f["ZETA_RANGE"] == [2, 6]
    assert f["SIGMA_BY_D"] == {
        str(x): {"COUNT": count, "RANGE": [0, 6 - x]} for x, count in HISTS[i].items() if x
    }
    cert.validate_facts(pid, f)


@pytest.mark.parametrize("i", range(3))
def test_all_independent_degree_endpoint_bounds(i: int, result: Record) -> None:
    p = result["PROFILES"][IDS[i]]["ANALYTIC_CERTIFICATE"]
    # Every labelled sigma coordinate is allowed by this enlarged relaxation.
    # Max of a separable expression is the sum of coordinate maxima.
    active = [x for x in map(int, IDS[i]) if x]
    total = 0
    for d in sorted(set(active)):
        values = [s * (4 - d + s) for s in range(7 - d)]
        maximum = max(values)
        record = p["SIGMA_ENDPOINT_CONTRIBUTIONS"][str(d)]
        assert record["MAXIMUM"] == maximum
        assert record["ALL_ARGMAX"] == [s for s, v in enumerate(values) if v == maximum]
        assert record["TOTAL"] == active.count(d) * maximum
        total += record["TOTAL"]
        for s in range(7 - d):
            assert s * (4 - d + s) <= s * (10 - 2 * d) <= maximum
    assert total == 92
    # Independent closed moment calculation, without endpoint implementation.
    assert total == 2 * sum(d * d for d in active) - 22 * sum(active) + 60 * len(active)
    assert p["CONSTANT"] == 290 - 60 - 12 * 5 == 170
    assert p["CAP"] == 262
    for zeta in product(range(2, 7), repeat=5):
        lhs = sum(v * (v - 2) for v in zeta)
        rhs = 6 * sum(zeta) - 60
        assert lhs <= rhs
        if lhs == rhs:
            assert all(v in (2, 6) for v in zeta)
    assert p["ZETA_CHORD"]["ALL_ARGMAX"] == [2, 6]
    assert p["REMAINDER_LOWER"] == dict.fromkeys(("T_M", "T_N", "C_K", "C_Z"), 0)
    assert result["SHARED_THEOREM"]["RELAXED_ENDPOINTS_ASSERTED_REALIZABLE"] is False


def test_complement_split_goodman_and_four_remainders_on_toy_graphs() -> None:
    # Exhaustive five-vertex mechanics check; these are not 20-ticket support graphs.
    vertices = set(range(5))
    k, z = {0, 1, 2}, {3, 4}
    pairs = list(combinations(range(5), 2))

    def triangles(vs: set[int], edges: set[tuple[int, int]]) -> int:
        return sum(all(e in edges for e in combinations(t, 2)) for t in combinations(sorted(vs), 3))

    for mask in range(1024):
        g = {e for i, e in enumerate(pairs) if mask & (1 << i)}
        h = set(pairs) - g
        m = {e for e in h if set(e) <= k}
        n = {e for e in h if set(e) <= z}
        sigma = {x: sum(tuple(sorted((x, v))) in g for v in z) for x in k}
        zeta = {v: sum(tuple(sorted((x, v))) in g for x in k) for v in z}
        md = {x: sum(x in e for e in m) for x in k}
        nd = {v: sum(v in e for e in n) for v in z}
        cz = sum(tuple(sorted((a, v))) in g and tuple(sorted((b, v))) in g for a, b in m for v in z)
        ck = sum(tuple(sorted((x, a))) in g and tuple(sorted((x, b))) in g for a, b in n for x in k)
        tm, tn = triangles(k, m), triangles(z, n)
        assert min(tm, tn, ck, cz) >= 0
        mixed = len(z) * len(m) + len(k) * len(n)
        mixed -= sum(sigma[x] * md[x] for x in k) + sum(zeta[v] * nd[v] for v in z)
        assert triangles(vertices, h) == mixed + tm + tn + ck + cz
        degrees = [sum(v in e for e in g) for v in vertices]
        goodman = comb(5, 3) - sum(d * (4 - d) for d in degrees) // 2
        assert triangles(vertices, g) + triangles(vertices, h) == goodman
        assert triangles(vertices, g) <= goodman - mixed


@pytest.mark.parametrize("i", range(3))
def test_every_old_new_term_and_all_argmax(i: int, result: Record) -> None:
    pid, p = IDS[i], result["PROFILES"][IDS[i]]
    assert (p["OLD_CAP"], p["NEW_CAP"]) == (266, 262)
    for prefix in ("OLD", "NEW"):
        terms = [independent_term(pid, t) for t in range(22, p[prefix + "_CAP"] + 1)]
        assert terms == p[prefix + "_ALL_T_TERMS"]
        maximum = max(t[1] for t in terms)
        assert p[prefix + "_BOUND"] == maximum
        assert p[prefix + "_ALL_ARGMAX"] == [t for t in terms if t[1] == maximum]
    assert p["OLD_ALL_ARGMAX"] == [[266, 313391844, 508, 195, 299887, 5173168]]
    assert p["NEW_ALL_ARGMAX"] == [[262, 313355996, 478, 195, 279517, 5125680]]


def test_real_authorities_and_exact_rounding(result: Record) -> None:
    auth = result["S4_S5_AUTHORITY"]
    for i, pid in enumerate(IDS):
        a = auth["PER_PROFILE"][pid]
        assert a["R30_ATTEMPT"]["ATTEMPT_INDEX"] == (3037, 3035, 3034)[i]
        assert a["R30_ATTEMPT"]["STATUS"] == "INFEASIBLE"
        assert a["R30_ATTEMPT"]["PROFILE_IDS"] == [pid]
        assert a["ACCEPTED_R30_CAP"] == a["OLD_CAP"] == 266
        assert a["NB_CAP"] == (272, 267, 266)[i] and a["CLASS_CAP"] == 273
        assert a["S4_BASE"] == 112 and a["S4_BY_T"] == {} and a["S5_USED"] is False
        assert pid not in auth["S5_ADOPTED_CERTIFICATES"]
    assert auth["S5_ALL_T_ADOPTION"] == "NOT_VERIFIED"
    for r in range(8):
        assert int(r > 0) <= r - comb(r, 2) + comb(r, 3) - Fraction(4, 7) * comb(r, 4)
    for i, pid in enumerate(IDS):
        f = result["PROFILES"][pid]["FACTS"]
        numerator = f["J"] - 10 * (824 - 3 * 262)
        assert numerator % 4 == (1, 2, 0)[i]
        assert independent_term(pid, 262)[2] == -(-numerator // 4)
        assert 3 * f["A_MAX"] <= 586 < 3 * (f["A_MAX"] + 1)
    probe = cert.envelope(IDS[0], 22, {"S4_BASE": 113, "S4_BY_T": {}, "S5_USED": False})[0]
    exact = Fraction(308390040 + probe[5]) - Fraction(4 * 113, 7)
    assert exact.denominator == 7
    assert probe[1] == exact.numerator // exact.denominator + 1
    assert probe == independent_term(IDS[0], 22, 113)


def test_complete_family_and_all_preserved_rows(result: Record) -> None:
    fixed = cast(
        Record, json.loads(cert.pinned_blob(cert.INPUT_HEAD, cert.INPUT_RESULT, cert.INPUT_SHA))
    )
    before, after = result["RESOLVED_ROWS_BEFORE"], result["RESOLVED_ROWS_AFTER"]
    cursor = result["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    assert before == fixed["RESOLVED_ROWS_AFTER"]
    assert len(before) == len(after) == 4647 and len(cursor) == 197
    assert result["FAMILY_BEFORE"] == fixed["FAMILY_AFTER"]
    assert result["FAMILY_BEFORE"]["ALL_MAX_OWNERS"] == list(IDS)
    assert sorted(p for p in after if before[p] != after[p]) == list(IDS)
    assert all(after[p] == before[p] for p in before.keys() - set(IDS))
    merged = after | cursor
    maximum = max(merged.values())
    assert maximum == result["FAMILY_AFTER"]["MAXIMUM"] == 313391784
    owners = sorted(p for p, bound in merged.items() if bound == maximum)
    assert (
        owners == result["ALL_NEW_MAX_OWNERS"] == fixed["FAMILY_AFTER"]["ALL_NEXT_DISTINCT_OWNERS"]
    )
    assert len(owners) == 39 and all(p in cursor for p in owners)
    for pid in IDS:
        missing = dict(after)
        missing[pid] = before[pid]
        assert max((missing | cursor).values()) == 313391844
    assert result["FAMILY_DELTA"] == 60 and result["CURSOR_FLOOR_REACHED"] is True
    assert result["GAP_TO_INCUMBENT"] == maximum - 313263888 == 127896
    assert result["CURSOR_197_PRESERVED"] == fixed["CURSOR_197_PRESERVED"]
    assert result["INHERITED_EXCLUSION"] == fixed["INHERITED_EXCLUSION"]
    assert result["INHERITED_CAVEATS_REFERENCE"] == fixed["INHERITED_CAVEATS_REFERENCE"]
    assert result["INHERITED_EXCLUSION"]["ORIGINAL_CONDITIONS_VERBATIM"]["COUNT"] == 282
    assert len(merged) + 282 == 5126
    assert result["PROJECTION_STATUS"] == "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION"
    assert result["FULL_ENVELOPE_TERM_COUNTS"] == {
        "OLD_PER_PROFILE": dict.fromkeys(IDS, 245),
        "NEW_PER_PROFILE": dict.fromkeys(IDS, 241),
        "OLD_TOTAL": 735,
        "NEW_TOTAL": 723,
        "OLD_T_RANGES": {p: [22, 266] for p in IDS},
        "NEW_T_RANGES": {p: [22, 262] for p in IDS},
    }


NEGATIVE_CASES = (
    "profile",
    "histogram",
    "wedge",
    "Goodman",
    "K",
    "Z",
    "split",
    "sigma",
    "zeta",
    "cap",
    "shared_cap",
    "remainder",
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
    "missing_owner_C",
    "argmax",
    "family_delta",
)


@pytest.mark.parametrize("defect", NEGATIVE_CASES)
def test_negative_payload(defect: str, result: Record) -> None:
    bad = copy.deepcopy(result)
    p = bad["PROFILES"][IDS[0]]
    fields = {
        "wedge": "WEDGES",
        "Goodman": "GOODMAN",
        "K": "K",
        "Z": "Z",
        "split": "SPLIT_H_CONSTANT",
        "Amax_floor": "A_MAX",
    }
    if defect in fields:
        p["FACTS"][fields[defect]] += 1
    elif defect == "profile":
        p["FACTS"]["PROFILE_ID"] = IDS[1]
    elif defect == "histogram":
        p["FACTS"]["D_HISTOGRAM"]["5"] += 1
    elif defect == "sigma":
        p["FACTS"]["SIGMA_BY_D"]["5"]["RANGE"][1] += 1
    elif defect == "zeta":
        p["FACTS"]["ZETA_RANGE"][0] -= 1
    elif defect == "cap":
        p["NEW_CAP"] -= 1
    elif defect == "shared_cap":
        bad["SHARED_THEOREM"]["COMMON_T_CAP"] -= 1
    elif defect == "remainder":
        p["ANALYTIC_CERTIFICATE"]["REMAINDER_LOWER"]["T_M"] = 1
    elif defect in ("rounding", "K4_rounding"):
        p["NEW_ALL_T_TERMS"][-1][1 if defect == "rounding" else 2] -= 1
    elif defect in ("missing_term", "endpoint"):
        p["NEW_ALL_T_TERMS"].pop(100 if defect == "missing_term" else -1)
    elif defect == "S4_addition":
        p["NEW_ALL_T_TERMS"][-1][4] += 112
    elif defect == "S4_scope":
        p["S4_BY_T"]["262"] = 309183
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
    elif defect.startswith("missing_owner_"):
        pid = IDS[ord(defect[-1]) - ord("A")]
        bad["RESOLVED_ROWS_AFTER"][pid] = result["RESOLVED_ROWS_BEFORE"][pid]
    elif defect == "argmax":
        p["NEW_ALL_ARGMAX"] = []
    elif defect == "family_delta":
        bad["FAMILY_DELTA"] += 1
    else:
        raise AssertionError("unexercised mutation")
    with pytest.raises(ValueError, match="complete exact recomputation"):
        cert.validate_payload(bad, result)


@pytest.mark.parametrize("field", ("WEDGES", "GOODMAN", "SPLIT_H_CONSTANT", "K", "Z", "A_MAX"))
def test_actual_fact_gate(field: str) -> None:
    bad = copy.deepcopy(cert.profile_facts(IDS[0]))
    bad[field] += 1
    with pytest.raises(ValueError, match="profile/split"):
        cert.validate_facts(IDS[0], bad)


@pytest.mark.parametrize("defect", ("input_tree", "base_tree", "parent", "merge", "paths"))
def test_actual_git_identity_gate(monkeypatch: pytest.MonkeyPatch, defect: str) -> None:
    def fake_git(*args: str, **_kwargs: Any) -> str:
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


def test_actual_sha_profile_cap_and_authority_gates() -> None:
    with pytest.raises(ValueError, match="authority blob identity"):
        cert.pinned_blob(cert.INPUT_HEAD, cert.INPUT_RESULT, "0" * 64)
    with pytest.raises(ValueError, match="wrong exact profile"):
        cert.profile_facts("66555555555521100000")
    auth: Record = {"S4_BASE": 112, "S4_BY_T": {}, "S5_USED": False}
    for cap in (21, 275, True, 262.0):
        with pytest.raises(ValueError, match="T cap"):
            cert.envelope(IDS[0], cast(int, cap), auth)
    for bad in ({**auth, "S5_USED": True}, {**auth, "S4_BY_T": {"262": 309183}}):
        with pytest.raises(ValueError, match="S4/S5 authority scope"):
            cert.envelope(IDS[0], 262, bad)


def test_real_single_parent_child(
    tmp_path: Path, result: Record
) -> None:
    """Disposable bare Git objects in OS temp; no extra retained branch/worktree."""
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("GIT_"):
            environment.pop(name)

    scratch = tmp_path / "child.git"
    subprocess.run(
        ["git", "init", "--bare", "--quiet", str(scratch)], check=True, env=environment
    )
    common = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"], cwd=cert.ROOT, env=environment, text=True
        ).strip()
    )
    if not common.is_absolute():
        common = cert.ROOT / common
    environment["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = str(common.resolve() / "objects")
    environment["GIT_INDEX_FILE"] = str(tmp_path / "isolated.index")

    def run(*args: str, data: bytes | None = None) -> str:
        return (
            subprocess.check_output(["git", *args], cwd=scratch, input=data, env=environment)
            .decode()
            .strip()
        )

    def commit_result(contents: bytes, message: bytes) -> str:
        run("read-tree", cert.INPUT_HEAD)
        for path in (cert.SOURCE, cert.TEST, cert.RESULT):
            blob_contents = (
                contents
                if path == cert.RESULT
                else subprocess.check_output(
                    ["git", "show", f"{_CERTIFICATE_SOURCE_HEAD}:{path}"],
                    cwd=cert.ROOT,
                    env={
                        name: value
                        for name, value in environment.items()
                        if not name.startswith("GIT_")
                    },
                )
            )
            oid = run("hash-object", "-w", "--stdin", data=blob_contents)
            run("update-index", "--add", "--cacheinfo", "100644", oid, path)
        tree = run("write-tree")
        return run(
            "-c",
            "user.name=Verifier fixture",
            "-c",
            "user.email=fixture@invalid",
            "commit-tree",
            tree,
            "-p",
            cert.INPUT_HEAD,
            data=message,
        )

    child = commit_result(cert.render(result), b"Disposable child fixture\n")
    assert (
        replay_certificate_call(
            cert.__name__,
            "verify_result",
            child,
            repo=scratch,
            source_head=_CERTIFICATE_SOURCE_HEAD,
            source_tree=_CERTIFICATE_SOURCE_TREE,
            operation_head=_CERTIFICATE_SOURCE_HEAD,
            operation_tree=_CERTIFICATE_SOURCE_TREE,
        )
        is None
    )

    invalid_result = cert.render({**result, "NEGATIVE_FIXTURE": True})
    invalid_child = commit_result(invalid_result, b"Disposable invalid result fixture\n")
    with pytest.raises(ValueError, match="stored result differs from complete exact recomputation"):
        replay_certificate_call(
            cert.__name__,
            "verify_result",
            invalid_child,
            repo=scratch,
            source_head=_CERTIFICATE_SOURCE_HEAD,
            source_tree=_CERTIFICATE_SOURCE_TREE,
            operation_head=_CERTIFICATE_SOURCE_HEAD,
            operation_tree=_CERTIFICATE_SOURCE_TREE,
        )


def test_stored_exact_result() -> None:
    assert replay_certificate_call(
        cert.__name__,
        "verify_result",
        source_head=_CERTIFICATE_SOURCE_HEAD,
        source_tree=_CERTIFICATE_SOURCE_TREE,
        operation_head=_CERTIFICATE_SOURCE_HEAD,
        operation_tree=_CERTIFICATE_SOURCE_TREE,
    ) is None
