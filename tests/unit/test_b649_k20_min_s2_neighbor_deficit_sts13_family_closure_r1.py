"""Independent design/term/family oracles and semantic mutations for the joint closure."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from math import ceil, comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_neighbor_deficit_sts13_family_closure_r1 as x

STS13 = "55555555555511111100"
RUNNER_UP = "55555555555542000000"
type Block = tuple[int, ...]


@pytest.fixture(scope="module")
def authority() -> x.Authority:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("new solver, R25/R30 execution or outcome enumeration")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(x.primary.nb.r28, "bounded_batch", forbidden)
        patch.setattr(x.primary.nb.r28, "solve_group", forbidden)
        patch.setattr(x.primary.nb.r30, "evaluate_portfolio", forbidden)
        from lottolab.research import b649_k20_min_s2_class_dominance_or_descent_r13 as r13
        from lottolab.research import b649_k20_min_s2_cursor_dynamic_owner_chase_r25 as r25

        patch.setattr(r13, "degree_class_open_wedge_relaxation", forbidden)
        patch.setattr(r25, "degree_class_open_wedge_relaxation", forbidden)
        return x.load_authority()


@pytest.fixture(scope="module")
def result(authority: x.Authority) -> dict[str, object]:
    return x.compute_result(authority)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=x.ROOT, text=True).strip()


def independent_designs() -> dict[str, list[Block]]:
    cyclic = sorted(
        {tuple(sorted((v + s) % 13 for v in b)) for b in ((0, 1, 4), (0, 2, 8)) for s in range(13)}
    )
    old = {(2, 3, 6), (2, 4, 10), (3, 4, 7), (6, 7, 10)}
    new = {(2, 3, 4), (2, 6, 10), (3, 6, 7), (4, 7, 10)}
    return {"CYCLIC": cyclic, "NON_CYCLIC": sorted((set(cyclic) - old) | new)}


def independent_pasches(design: Sequence[Block]) -> set[Block]:
    """Six-sets carrying four triples meeting every point exactly twice."""
    found: set[Block] = set()
    for four in combinations(design, 4):
        counts = Counter(v for b in four for v in b)
        if len(counts) == 6 and set(counts.values()) == {2}:
            key = tuple(sorted(counts))
            assert key not in found
            found.add(key)
    return found


def pair_cover(design: Sequence[Block]) -> Counter[tuple[int, ...]]:
    return Counter(e for b in design for e in combinations(b, 2))


def independent_q(g: Sequence[int]) -> tuple[int, ...]:
    answer: list[int] = []
    for v, own in enumerate(g):
        h = sorted((value for i, value in enumerate(g) if i != v), reverse=True)[:own]
        deficits = [max(own - degree, 0) for degree in h]
        answer.append(max(ceil(Fraction(sum(deficits), 2)), max(deficits, default=0)))
    return tuple(answer)


def joint_rows(result: dict[str, object]) -> list[list[object]]:
    cert = x.object_row(x.plain(result["JOINT_STS13_CERTIFICATE"]))  # sealed JSON rows
    return [x.rows(r) for r in x.rows(cert["ALL_T_TERMS"])]


def test_sibling_authorities_byte_identity_and_common_parent(
    authority: x.Authority, result: dict[str, object]
) -> None:
    assert git("merge-base", x.PRIMARY_HEAD, x.DONOR_HEAD) == x.COMMON_PARENT
    for head, tree in ((x.PRIMARY_HEAD, x.PRIMARY_TREE), (x.DONOR_HEAD, x.DONOR_TREE)):
        assert git("rev-parse", f"{head}^{{tree}}") == tree
        assert git("rev-parse", f"{head}^") == x.COMMON_PARENT
        assert git("rev-list", "--count", f"{x.COMMON_PARENT}..{head}") == "1"
    files = x.SIBLINGS[x.DONOR_HEAD][1] + x.SIBLINGS[x.PRIMARY_HEAD][1]
    head_of = {path: head for head, (_tree, paths) in x.SIBLINGS.items() for path in paths}
    assert len(files) == 6
    for path in files:
        # Identical blob object ids prove original bytes, not merely equal JSON.
        assert git("hash-object", path) == git("rev-parse", f"{head_of[path]}:{path}")
        digest = hashlib.sha256((x.ROOT / path).read_bytes()).hexdigest()
        assert x.object_row(result["SIBLING_FILE_SHA256"])[path] == digest
    assert x.object_row(result["SIBLING_FILE_SHA256"])[x.PRIMARY_RESULT] == (
        "4e7b8163846f6b87c561fc7a96f12a18c46636ee66c9d0dfdd0b24eb1ec08dfa"
    )
    assert x.object_row(result["SIBLING_FILE_SHA256"])[x.DONOR_RESULT] == (
        "b1a113c9cc179a9ec50761f162af3c367ec433465f3398cd5b358c9ea087c67d"
    )
    assert x.primary.BASE_HEAD == x.donor.BASE_HEAD == x.COMMON_PARENT
    assert authority.provenance == result["SIBLING_FILE_SHA256"]
    assert result["SOURCE_SHA256"] == hashlib.sha256(Path(x.__file__).read_bytes()).hexdigest()
    assert result["SOLVER_CALLS"] == result["OUTCOME_ENUMERATIONS"] == 0


def test_primary_neighbor_deficit_certificates_preserved(
    authority: x.Authority, result: dict[str, object]
) -> None:
    primary = authority.neighbor_result
    certs = x.object_row(primary["ACTIVE_CERTIFICATES"])
    assert len(certs) == 78
    for pid, raw in certs.items():
        proof = x.object_row(x.object_row(raw)["NEIGHBOR_DEFICIT_PROOF"])
        assert tuple(x.rows(proof["Q_V"])) == independent_q([6 + int(v) for v in pid])
    preserved = x.object_row(result["PRIMARY_CERTIFICATE_PRESERVATION"])
    assert preserved["CAP_REDUCTION_PROFILE_IDS"] == primary["CAP_REDUCTION_PROFILE_IDS"]
    assert len(x.rows(preserved["CAP_REDUCTION_PROFILE_IDS"])) == 11
    assert preserved["EXCLUDED_T_TERM_COUNT"] == 24
    assert preserved["RETAINED_T_TERM_COUNT"] == 18944
    assert preserved["SPECIAL_S4_SCOPE_STATUS"] == "PASS_ORIGINAL_CERTIFIED_T_ONLY"
    assert preserved["S5_IDENTITY"] == authority.neighbor.sealed["S5_IDENTITY"]
    assert preserved["FRONTIER_CERTIFICATES_SHA256"] == x.digest(
        authority.neighbor.sealed["FRONTIER_CERTIFICATES"]
    )
    assert preserved["UNCHANGED_RESOLVED_ROW_COUNT"] == 4569
    before = {
        x.integration.text(p): b for p, b in map(x.rows, x.rows(primary["COMPLETE_PROFILE_BOUNDS"]))
    }
    after = {
        x.integration.text(p): b for p, b in map(x.rows, x.rows(result["COMPLETE_PROFILE_BOUNDS"]))
    }
    assert before.keys() == after.keys() and len(after) == 4844
    assert [p for p in after if after[p] != before[p]] == [STS13] == result["CHANGED_PROFILE_IDS"]
    assert before[STS13] == primary["FINAL_COMPLETE_FAMILY_UB"] == 313263916
    for pid, raw in certs.items():
        if pid != STS13:
            assert after[pid] == x.object_row(raw)["CERTIFIED_PROFILE_BOUND"]


def test_two_sts13_classes_all_26_deletions_unique_completion_and_pasch_floor(
    authority: x.Authority, result: dict[str, object]
) -> None:
    designs = independent_designs()
    complete_counts: dict[str, int] = {}
    for name, design in designs.items():
        assert len(design) == 26 and set(pair_cover(design).values()) == {1}
        assert set(pair_cover(design)) == set(combinations(range(13), 2))
        complete_counts[name] = len(independent_pasches(design))
    assert complete_counts == {"CYCLIC": 13, "NON_CYCLIC": 8}  # distinct: non-isomorphic
    sts = x.object_row(result["STS13_POINTED_PASCH_CERTIFICATE"])
    assert sts["COMPLETE_DESIGN_PASCH_COUNTS"] == complete_counts
    summary = {(r[0], r[1]): r for r in map(x.rows, x.rows(sts["POINTED_SUMMARY"]))}
    observed: dict[str, Counter[int]] = {name: Counter() for name in designs}
    for name, design in designs.items():
        for point in range(13):
            relabel = {v: i for i, v in enumerate(u for u in range(13) if u != point)}
            core = sorted(tuple(relabel[v] for v in b) for b in design if point not in b)
            uncovered = set(combinations(range(12), 2)) - set(pair_cover(core))
            assert len(core) == 20 and len(uncovered) == 6
            assert Counter(v for e in uncovered for v in e) == Counter(range(12))
            # Unique completion through one new point recovers the deleted design.
            restored = {(*e, 12) for e in uncovered} | set(core)
            back = {v: (12 if v == point else relabel[v]) for v in range(13)}
            assert restored == {tuple(sorted(back[v] for v in b)) for b in design}
            p = len(independent_pasches(core))
            observed[name][p] += 1
            assert summary[name, point] == [name, point, p, 7 * p, 313263916 - 7 * p]
    assert observed == {"CYCLIC": Counter({7: 13}), "NON_CYCLIC": Counter({4: 9, 5: 4})}
    assert len(summary) == sts["POINTED_DELETION_COUNT"] == 26
    assert sts["PASCH_DISTRIBUTION"] == {"CYCLIC": {"7": 13}, "NON_CYCLIC": {"4": 9, "5": 4}}
    assert sts["P_UNIVERSAL_FLOOR"] == min(min(c) for c in observed.values()) == 4
    assert authority.pasch_result["P_UNIVERSAL_LOWER_BOUND"] == 4


def test_exact_moment_identities_and_single_s6_credit_at_t270(result: dict[str, object]) -> None:
    sts = x.object_row(result["STS13_POINTED_PASCH_CERTIFICATE"])
    moments = x.object_row(sts["MOMENT_IDENTITIES"])
    # K12+(K8-e): K4 counts, triple-containing K4s and diamonds are exact.
    k4 = comb(12, 4) + comb(8, 4) - comb(6, 2)
    contained = 20 * (12 - 3) + 2 * (8 - 3)
    assert (k4, contained, comb(6, 2)) == (550, 190, 15)
    assert moments["S4"] == 679 * (k4 - contained) + 448 * contained + 112 * 15 == 331240
    # Five-sets: K12 with one triple (blocks x C(9,2) minus double counts), K8-e
    # with one triple (18 complete + 2 missing-edge), and two meeting triples.
    pairs_of_meeting_triples = 12 * comb(5, 2)
    assert moments["S5"] == 7 * (20 * comb(9, 2) - 2 * pairs_of_meeting_triples + 20) + 28 * (
        pairs_of_meeting_triples
    )
    assert (moments["S6"], moments["S7"]) == ("7*P", 0)
    s1, s2, s3 = (x.integer(moments[k]) for k in ("S1", "S2", "S3"))
    fifth = s1 - s2 + s3 - 331240 + 6860
    assert fifth == 313263916
    for p in (4, 5, 7):
        assert sum((-1) ** i * v for i, v in enumerate((s1, s2, s3, 331240, 6860, 7 * p, 0))) == (
            fifth - 7 * p
        )
    terms = joint_rows(result)
    cert = x.object_row(result["JOINT_STS13_CERTIFICATE"])
    assert [t[0] for t in terms] == list(range(22, 271)) and len(terms) == 249
    assert [t[0] for t in terms if t[13] is not None] == [270]
    top = terms[-1]
    assert top[11] == top[12] == fifth  # primary = exact fifth partial sum, S4/S5 exact
    assert top[9] == 331240 and x.integer(top[8]) <= 331240
    assert top[14] == min(fifth, fifth - 7 * 4) == 313263888  # MIN, applied exactly once
    assert all(t[14] == t[12] for t in terms[:-1])
    lower = [x.integer(t[14]) for t in terms[:-1]]
    assert max(lower) == cert["LOWER_T_MAX"] == 313257672 <= 313261872
    assert cert["CERTIFIED_PROFILE_BOUND"] == 313263888 and cert["ARGMAX_T"] == [270]


def test_lower_t_terms_retained_and_no_weakening(authority: x.Authority) -> None:
    cert = x.object_row(x.object_row(authority.neighbor_result["ACTIVE_CERTIFICATES"])[STS13])
    donor = x.object_row(authority.pasch_result["PROFILE_CERTIFICATE"])
    primary_terms = [x.rows(r) for r in x.rows(cert["ALL_T_TERMS"])]
    donor_terms = [x.rows(r) for r in x.rows(donor["ALL_T_TERMS"])]
    joint = x.joint_terms(authority, 313263888)
    assert len(donor_terms) == len(primary_terms) == len(joint) == 249
    for p, d, j in zip(primary_terms, donor_terms, joint, strict=True):
        assert list(j[:13]) == p and p[:6] == (d if p[0] != 270 else [270, 313263916, *d[2:]])
        assert x.integer(j[14]) <= x.integer(d[1])  # never weaker than either sibling
        assert x.integer(j[14]) <= x.integer(p[12])
    assert (
        sum(x.integer(j[14]) < x.integer(d[1]) for j, d in zip(joint, donor_terms, strict=True))
        == 134
    )
    bad = list(joint)
    bad[0] = (*bad[0][:13], 313263888, bad[0][14])
    with pytest.raises(AssertionError, match="outside the exact t=270"):
        x.validate_scope(
            [cast(x.primary.Term, tuple(j[:13])) for j in joint],
            bad,
            [tuple(map(x.integer, d)) for d in donor_terms],
            313263888,
        )
    with pytest.raises(AssertionError, match="incomplete or duplicated"):
        x.validate_scope(
            [cast(x.primary.Term, tuple(j[:13])) for j in joint],
            [joint[0], *joint[:-1]],
            [tuple(map(x.integer, d)) for d in donor_terms],
            313263888,
        )


def test_complete_family_closure_owner_gap_and_all_witnesses(
    authority: x.Authority, result: dict[str, object]
) -> None:
    pairs = [x.rows(r) for r in x.rows(result["COMPLETE_PROFILE_BOUNDS"])]
    ids = [x.integration.text(r[0]) for r in pairs]
    resolved = set(authority.neighbor.ledger)
    frontier = set(x.object_row(authority.neighbor_result["FRONTIER_CERTIFICATES"]))
    assert ids == sorted(set(ids)) and len(ids) == 4844
    assert len(resolved) == 4647 and len(frontier) == 197 and not resolved & frontier
    assert resolved | frontier == set(ids)
    bounds = {x.integration.text(r[0]): x.integer(r[1]) for r in pairs}
    top = max(bounds.values())
    assert top == result["FINAL_COMPLETE_FAMILY_UB"] == result["CANONICAL_INCUMBENT"] == 313263888
    assert [p for p, b in bounds.items() if b == top] == [STS13] == result["FINAL_OWNER_IDS"]
    second = max(b for p, b in bounds.items() if p != STS13)
    assert second == result["NEXT_RESOLVED_COMPETING_BOUND"] == 313263811
    assert [p for p, b in bounds.items() if b == second] == [RUNNER_UP] and RUNNER_UP in resolved
    assert max(bounds[p] for p in frontier) == result["FRONTIER_MAX_BOUND"] == 313226448
    assert result["REMAINING_GAP"] == 0 and result["START_COMPLETE_FAMILY_UB"] == 313263916
    family = x.object_row(result["FINAL_FAMILY"])
    assert family["FAMILY_UB"] == 313263888 and family["OWNER_IDS"] == [STS13]
    assert x.object_row(family["COVERAGE"])["DISJOINT_EXHAUSTIVE"] is True
    sound = x.object_row(result["WITNESS_SOUNDNESS"])
    checks = {k: x.object_row(v) for k, v in x.object_row(sound["CHECKS"]).items()}
    assert len(checks) == 77
    for check in checks.values():
        value = x.integer(check["VALUE"])
        assert (
            value <= x.integer(check["T_BOUND"])
            and value <= bounds[x.integration.text(check["PROFILE_ID"])]
        )
    assert {
        k: (c["VALUE"], c["VALUE_KIND"]) for k, c in checks.items() if c["PROFILE_ID"] == STS13
    } == {
        "STS13": (313263867, "EXACT_UNION"),
        "TRADED_STS13": (313263888, "EXACT_UNION"),
    }
    # The legal incumbent: twenty six-label tickets on 49 labels, pair-linear, P=4.
    witness = x.object_row(authority.pasch_result["INCUMBENT_WITNESS"])
    tickets = [tuple(x.integer(v) for v in x.rows(t)) for t in x.rows(witness["TICKETS"])]
    triples = [tuple(x.integer(v) for v in x.rows(t)) for t in x.rows(witness["TRIPLE_SUPPORTS"])]
    assert len(set(tickets)) == 20 and all(len(t) == 6 for t in tickets)
    assert set[int]().union(*map(set, tickets)) == set(range(1, 50))
    assert all(len(set(a) & set(b)) <= 1 for a, b in combinations(tickets, 2))
    assert len(independent_pasches([t for t in triples if max(t) < 12])) == 4
    assert x.object_row(result["INCUMBENT_WITNESS"])["EXACT_UNION"] == 313263916 - 28
    assert "NOT_A_GLOBAL_K20_OPTIMALITY_CLAIM" in x.integration.text(result["CLAIM_SCOPE"])


def evidence_mutation(authority: x.Authority, kind: str) -> x.Authority:
    pasch = copy.deepcopy(authority.pasch_result)
    neighbor = copy.deepcopy(authority.neighbor_result)
    records = x.rows(pasch["POINTED_DELETIONS"])
    noncyclic_p4 = next(
        x.object_row(r)
        for r in records
        if x.object_row(r)["CLASS"] == "NON_CYCLIC" and x.object_row(r)["P"] == 4
    )
    if kind == "wrong_pasch_count":
        # Internally consistent false claim: only an independent recount refutes it.
        noncyclic_p4.update(P=5, S6=35, EXACT_UNION=313263916 - 35)
    elif kind == "missing_deletion":
        records.pop()
    elif kind == "duplicated_deletion":
        records[1] = copy.deepcopy(records[0])
    elif kind == "wrong_s6_weight":
        noncyclic_p4.update(S6=24, EXACT_UNION=313263916 - 24)
    elif kind == "wrong_s7_weight":
        noncyclic_p4.update(S7=1, EXACT_UNION=313263888 + 1)
    elif kind == "missing_class":
        del x.object_row(pasch["REPRESENTATIVES"])["NON_CYCLIC"]
    elif kind == "wrong_pasch_floor":
        pasch["P_UNIVERSAL_LOWER_BOUND"] = 5
    elif kind == "improper_t_scope":
        cert = x.object_row(x.object_row(neighbor["ACTIVE_CERTIFICATES"])[STS13])
        x.rows(x.rows(cert["ALL_T_TERMS"])[-2])[12] = 313263888
    elif kind == "duplicated_row":
        bounds = x.rows(neighbor["COMPLETE_PROFILE_BOUNDS"])
        bounds.insert(1, copy.deepcopy(bounds[0]))
    elif kind == "missing_frontier_profile":
        frontier = x.object_row(neighbor["FRONTIER_CERTIFICATES"])
        del frontier[next(iter(frontier))]
    elif kind == "missing_profile":
        ledger = dict(authority.neighbor.ledger)
        del ledger[next(p for p in ledger if p not in authority.neighbor.active)]
        return replace(authority, neighbor=replace(authority.neighbor, ledger=ledger))
    else:
        pytest.fail("unknown evidence mutation")
    return replace(authority, pasch_result=pasch, neighbor_result=neighbor)


@pytest.mark.parametrize(
    "kind",
    [
        "wrong_pasch_count",
        "missing_deletion",
        "duplicated_deletion",
        "wrong_s6_weight",
        "wrong_s7_weight",
        "missing_class",
        "wrong_pasch_floor",
        "improper_t_scope",
        "duplicated_row",
        "missing_frontier_profile",
        "missing_profile",
    ],
)
def test_semantic_evidence_mutations_rejected(
    kind: str, authority: x.Authority, result: dict[str, object]
) -> None:
    assert x.render(x.compute_result(authority)) == x.render(result)
    with pytest.raises((AssertionError, ValueError)):
        x.compute_result(evidence_mutation(authority, kind))


MUTATIONS = {
    "complete_design_pasch_count": (
        "pointed_classification",
        "donor.pasches(core, tuple(range(12)))",
        "donor.pasches(complete, tuple(range(13)))",
    ),
    "wrong_s6_weight": (
        "pointed_classification",
        "EXACT_S5, 7 * p, EXACT_S7]",
        "EXACT_S5, 6 * p, EXACT_S7]",
    ),
    "wrong_s7_weight": (
        "pointed_classification",
        "EXACT_S5, 7 * p, EXACT_S7]",
        "EXACT_S5, 7 * p, 1]",
    ),
    "pasch_floor_max": ("pointed_classification", "p_min = min(", "p_min = max("),
    "omit_noncyclic_deletions": (
        "pointed_classification",
        "for record in records:",
        "for record in records[:13]:",
    ),
    "credit_at_t269": (
        "joint_terms",
        "bound if term[0] == CAP else None",
        "bound if term[0] >= CAP - 1 else None",
    ),
    "double_count_s6": ("joint_terms", "min(term[12], credit)", "min(term[12], credit) - 7 * 4"),
    "max_instead_of_min": ("joint_terms", "min(term[12], credit)", "max(term[12], credit)"),
    "drop_lower_t": ("joint_terms", "for term in old:", "for term in old[-1:]:"),
    "credit_all_profiles": (
        "complete_family",
        "**ledger,",
        "**{p: replace(r, bound=r.bound - 7 * 4) for p, r in ledger.items()},",
    ),
    "drop_profile": ("complete_family", "**ledger,", "**dict(list(ledger.items())[1:]),"),
    "witness_moment_not_union": (
        "witness_soundness",
        'value = integer(exact["EXACT_UNION"])',
        "value = moment",
    ),
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_non_equivalent_source_mutations_killed(
    name: str,
    authority: x.Authority,
    result: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    function, old, new = MUTATIONS[name]
    original = cast(Callable[..., object], getattr(x, function))
    source = inspect.getsource(original)
    assert source.count(old) == 1
    namespace: dict[str, object] = dict(original.__globals__)
    exec(compile(source.replace(old, new), f"<semantic-mutation:{name}>", "exec"), namespace)
    assert x.render(x.compute_result(authority)) == x.render(result)
    with monkeypatch.context() as patch:
        patch.setattr(x, function, namespace[function])
        with pytest.raises((AssertionError, ValueError)):
            x.compute_result(authority)
    assert x.render(x.compute_result(authority)) == x.render(result)


def test_exact_result_bytes_and_tampering(
    authority: x.Authority, result: dict[str, object]
) -> None:
    raw = x.RESULT_PATH.read_bytes()
    assert raw == x.render(result)
    assert json.loads(raw) == json.loads(x.render(result))
    x.verify_result(result, authority)
    for key, value in (
        ("FINAL_COMPLETE_FAMILY_UB", 313263916),
        ("REMAINING_GAP", 28),
        ("FINAL_OWNER_IDS", [STS13, RUNNER_UP]),
    ):
        with pytest.raises(AssertionError, match="tampered joint"):
            x.verify_result({**result, key: value}, authority)


def run_fresh(arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=x.ROOT,
        env={**os.environ, "PYTHONPATH": str(x.ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )


def test_module_verify_byte_replay() -> None:
    run = run_fresh(["-m", x.__name__, "--verify"])
    assert run.returncode == 0, run.stdout + run.stderr
    output = x.object_row(json.loads(run.stdout))
    assert output["RESULT_REPLAY_STATUS"] == "PASS"
    assert output["FINAL_COMPLETE_FAMILY_UB"] == 313263888 and output["REMAINING_GAP"] == 0


@pytest.mark.parametrize("first", ["donor", "primary", "joint"])
def test_fresh_process_import_order(first: str) -> None:
    names = {"donor": x.donor.__name__, "primary": x.primary.__name__, "joint": x.__name__}
    script = (
        "import importlib; "
        f"importlib.import_module({names[first]!r}); "
        f"x=importlib.import_module({x.__name__!r}); "
        "r=x.compute_result(); assert r['FINAL_COMPLETE_FAMILY_UB']==313263888; "
        f"assert r['FINAL_OWNER_IDS']==[{STS13!r}] and r['REMAINING_GAP']==0; "
        "assert x.RESULT_PATH.read_bytes()==x.render(r)"
    )
    run = run_fresh(["-c", script])
    assert run.returncode == 0, run.stdout + run.stderr
