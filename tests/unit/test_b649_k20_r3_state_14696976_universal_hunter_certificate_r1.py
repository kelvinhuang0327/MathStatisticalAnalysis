"""Independent universal-domain arithmetic and targeted non-equivalent defects."""

from __future__ import annotations

import copy
import inspect
import json
from collections.abc import Callable
from dataclasses import replace
from hashlib import sha256
from itertools import product
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import (
    b649_k20_r3_state_14696976_universal_hunter_certificate_r1 as cert,
)


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden region ledger, R7 census, solver, or portfolio search")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    with pytest.MonkeyPatch.context() as patch:
        for module, names in (
            (cert.hunter.r7, ("joint_residual_census", "_joint_residual_states")),
            (cert.hunter.r14, ("owner_region", "s4_child", "run_chase")),
            (cert.hunter.r6, ("iter_type_count_vectors", "candidate_type_count_vectors")),
            (cert.hunter.r8, ("support_model_status", "solver_runtime_preflight")),
            (cert.hunter.catalog, ("rebuild_member", "load_region_ledger")),
        ):
            for name in names:
                if hasattr(module, name):
                    patch.setattr(module, name, forbidden)
        return cert.build_result()


def test_pinned_sources_and_all_five_research_fingerprints(result: dict[str, Any]) -> None:
    authority = cert.verify_source_authority()
    assert authority == result["SOURCE_AUTHORITY"]
    for label, head, tree, digest in (
        ("BASE", cert.BASE_HEAD, cert.BASE_TREE, cert.BASE_RESULT_SHA256),
        ("R10", cert.R10_HEAD, cert.R10_TREE, cert.R10_RESULT_SHA256),
    ):
        assert authority[label] == {"HEAD": head, "TREE": tree, "RESULT_SHA256": digest}
    assert (
        result["TYPE_COEFFICIENT_PROOF"]["coefficient_sha256"]
        == cert.FINGERPRINTS["type_coefficients"]
    )
    assert result["ROOT_PAIR_PROOF"]["rows_sha256"] == cert.FINGERPRINTS["root_rows"]
    assert result["HUNTER_NINE_ROW_PROOF"]["rows_sha256"] == cert.FINGERPRINTS["scalar_rows"]
    assert result["EXISTING_FAMILY_TERMS_SHA256"] == cert.FINGERPRINTS["existing_family"]
    assert result["NEW_FAMILY_TERMS_SHA256"] == cert.FINGERPRINTS["new_family"]


def test_first_dominator_equivalence_on_every_coordinate_cell(result: dict[str, Any]) -> None:
    p = result["STATE_MEMBERSHIP_PROOF"]
    frontier = tuple(tuple(r) for r in p["frontier"])
    # First-dominator predicates are constant in these integer coordinate cells.
    # Test all sides of every frontier boundary, including unbounded final cells.
    xs = sorted({0, *(x + d for x, _ in frontier for d in (-1, 0, 1))})
    ys = sorted({0, *(y + d for _, y in frontier for d in (-1, 0, 1))})
    for s2, s3 in product(xs, ys):
        owner = next((i for i, (x, y) in enumerate(frontier) if x <= s2 and y >= s3), -1)
        rectangle = s2 >= 14696976 and 1005536 < s3 <= 1059324
        assert (owner == 12) == rectangle
        assert cert.first_dominator(frontier, s2, s3) == owner
    assert p["rank"] == 13 and p["local_loss_max_inclusive"] == 6695798
    assert len(p["unchanged_domain_constraints"]) == 3
    assert p["complete_region_ledger_used"] is False


def test_30_coefficients_dual_and_exhaustive_k_partition(result: dict[str, Any]) -> None:
    proof = result["TYPE_COEFFICIENT_PROOF"]
    coefficients = tuple(tuple(r) for r in proof["coefficients"])
    profiles = cert.hunter.r5.anchor_incidence_profiles()
    assert len(coefficients) == len(profiles) == 30
    assert coefficients == tuple(
        (p.triple_recovery - 9485, p.pair_recovery_cost - p.triple_recovery - 206115)
        for p in profiles
    )
    assert coefficients[29][0] == 1576204
    assert 18 * 9485 + coefficients[29][0] > 1059324
    assert all(x >= 0 for x, _ in coefficients)
    slacks = [39137 * ell - 13733226360 - 154447 * x for x, ell in coefficients[1:29]]
    assert len(slacks) == 28 and min(slacks) == 0
    assert slacks == proof["dual_slacks_types_1_through_28"]
    for k in range(19):
        numerator = (18 - k) * 13733226360 + 154447 * (1005537 - 18 * 9485)
        floor, remainder = divmod(numerator, 39137)
        floor += bool(remainder)
        assert cert.loss_floor(k) == floor
        assert 39137 * (floor - 1) < numerator <= 39137 * floor
        if k <= 8:
            assert floor > 6695798
        elif k == 18:
            assert 18 * 9485 < 1005537
        else:
            assert k in proof["universal_k_range"]
    # These identities reconstruct S3 and L for arbitrary count vectors, not a ledger.
    for counts in (
        (18, *([0] * 29)),
        tuple(17 if i == 0 else 1 if i == 29 else 0 for i in range(30)),
        tuple(9 if i == 0 else 3 if i in (5, 6, 16) else 0 for i in range(30)),
    ):
        assert sum(counts) == 18
        assert sum(n * p.triple_recovery for n, p in zip(counts, profiles, strict=True)) == (
            18 * 9485 + sum(n * x for n, (x, _) in zip(counts, coefficients, strict=True))
        )
        assert sum(n * ell for n, (_, ell) in zip(counts, coefficients, strict=True)) == sum(
            n * (p.pair_recovery_cost - p.triple_recovery - 206115)
            for n, p in zip(counts, profiles, strict=True)
        )


def test_exact_ceil_never_uses_float() -> None:
    for n in (0, 1, 39136, 39137, 39138, 2**80 + 1):
        q = cert.ceil_div(n, 39137)
        assert (q - 1) * 39137 < n <= q * 39137
    with pytest.raises(ValueError):
        cert.ceil_div(3, 0)


def test_complete_105_rows_residual_dp_and_raw_E_negative_control(result: dict[str, Any]) -> None:
    proof = result["ROOT_PAIR_PROOF"]
    keys: list[tuple[int, int]] = []
    for t in range(30):
        outside = cert.hunter.type_cells(t)[3]
        keys.extend((t, z) for z in range(min(3, outside) + 1))
    assert [(r[0], r[1]) for r in proof["rows"]] == keys
    assert len(keys) == 105 and {t for t, _ in keys} == set(range(30))
    assert min(r[2] for r in proof["rows"]) == 88830
    assert tuple(r[2] for r in proof["rows"] if r[0] == 0) == (107800, 574000, 1691620, 3451651)
    for row in proof["row_counts"]:
        value = row["raw_E"] - row["triple_A"] - row["triple_B"] + row["quadruple"]
        assert value == row["residual_R"] >= 88830
    changed = [r for r in proof["row_counts"] if r["raw_E"] != r["residual_R"]]
    assert changed and min(r["raw_E"] for r in proof["row_counts"]) == 107800
    rows = tuple(tuple(r) for r in proof["full_rows"])
    for unsafe in (88831, 107800):
        with pytest.raises(AssertionError, match="residual root floor"):
            cert.require_root_floor(unsafe, rows)
    with pytest.raises(AssertionError, match="105-row"):
        cert.require_root_floor(88830, rows[:-1])


@pytest.mark.parametrize("k", range(9, 18))
def test_nine_independent_threshold_minima_and_scalar_rows(result: dict[str, Any], k: int) -> None:
    row = result["HUNTER_NINE_ROW_PROOF"]["rows"][k - 9]
    proof = result["HUNTER_NINE_ROW_PROOF"]["cores"][k - 9]
    q, r = divmod(6 * k, 40)
    mass = (40 - r) * comb(q, 2) + r * comb(q + 1, 2)
    capacity = comb(k, 2)
    rho = [next(rank for rank in range(k) if comb(rank + 1, 2) >= e) for e in range(capacity + 1)]
    best: tuple[int, tuple[int, int, int]] | None = None
    cases = 0
    all_nested = 0
    for e1 in range(capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                all_nested += 1
                if e1 + e2 + e3 < mass:
                    continue
                value = (k - 1) * 107800 + 466200 * rho[e1] + 1117620 * rho[e2] + 1760031 * rho[e3]
                candidate = (value, (e1, e2, e3))
                best = candidate if best is None else min(best, candidate)
                cases += 1
    assert best is not None
    assert row[1] == mass == proof["Q"]
    assert row[3] == best[0] == 3193400 + (k - 9) * 574000
    assert proof["threshold_case_count"] == cases
    assert proof["all_nested_case_count"] == all_nested == comb(capacity + 3, 3)
    assert proof["rejected_collision_case_count"] == all_nested - cases
    assert proof["minimizer_edges"] == list(best[1])
    assert proof["rank_floor_table"] == rho
    assert row[4] == row[3] + (18 - k) * 88830
    assert row[5] == 365048628 - row[2] - row[4]
    for high in range(2, k + 1):
        for low in range(high - 1):
            assert comb(high, 2) + comb(low, 2) > comb(high - 1, 2) + comb(low + 1, 2)
    for a, b in product(range(k), repeat=2):
        assert comb(a + 1, 2) + comb(b + 1, 2) + a * b == comb(a + b + 1, 2)


def test_case_count_metadata_distinguishes_pre_filter_and_admissible_domains(
    result: dict[str, Any],
) -> None:
    proof = result["HUNTER_NINE_ROW_PROOF"]
    audit = proof["case_count_audit"]
    assert sum(p["all_nested_case_count"] for p in proof["cores"]) == 1273815
    assert sum(p["threshold_case_count"] for p in proof["cores"]) == 1229966
    assert audit["all_nested_count"] == audit["reported_research_count"] == 1273815
    assert audit["admissible_count"] == 1229966
    assert audit["rejected_by_collision_sum"] == 43849
    assert audit["historical_script_status"].startswith("UNAVAILABLE")


def test_hunter_rank_nested_kruskal_and_pointwise_union_lemmas() -> None:
    assert cert.hunter.verify_rank_floor_algebra(17) == comb(17, 2) + 1
    assert cert.hunter.verify_threshold_tree_lemma() > 0
    assert cert.hunter.verify_hunter_exhaustively(4, 3) > 0


@pytest.mark.parametrize("k", range(9, 18))
def test_extension_on_arbitrary_core_labels_and_duplicate_edge_rejection(k: int) -> None:
    indices = tuple(reversed(range(18 - k, 18)))
    core = tuple((indices[j - 1], indices[j]) for j in range(1, k))
    attachments = tuple((indices[0], j) for j in range(18) if j not in indices)
    full = cert.validate_tree_extension(indices, core, attachments)
    assert len(full) == cert.hunter.graph_rank(18, full) == 17
    assert len({frozenset(e) for e in full}) == 17
    for bad in (
        (core[0], *attachments[1:]),
        attachments[:-1],
        ((indices[0], 18), *attachments[1:]),
    ):
        with pytest.raises(AssertionError, match="18-vertex 17-edge"):
            cert.validate_tree_extension(indices, core, bad)


def test_complete_family_only_one_state_changes_and_max_only(result: dict[str, Any]) -> None:
    old = cert.family_terms()
    updated = cert.replace_state(old, 354603232)
    assert len(updated) == len(dict(updated)) == 56574
    assert [(a, b) for a, b in zip(old, updated, strict=True) if a != b] == [
        ((cert.STATE_ID, 355121046), (cert.STATE_ID, 354603232))
    ]
    assert sum(a == b for a, b in zip(old, updated, strict=True)) == 56573
    assert max(b for _, b in updated[23:-1]) == 354800665
    assert updated[-1] == ("unclassified-tail", 354039277)
    assert dict(updated)["state:s2-12695020-s3-735532"] == 355111939
    ordered = sorted(updated, key=lambda r: (-r[1], r[0]))
    assert ordered[:2] == [
        ("state:s2-13548976-s3-951748", 355116818),
        ("state:s2-13169800-s3-789320", 355112590),
    ]
    assert result["STRICT_GAIN"] == 4228 and result["REMAINING_GAP"] == 41852930
    credits = {"existing": 4000000, "hunter": 3992870}
    assert cert.combine_corrections(credits) == max(credits.values()) < sum(credits.values())
    assert cert.adopt_state_bound(355121046, 354603232) == 354603232
    assert cert.adopt_state_bound(354000000, 354603232) == 354000000
    assert result["COMPLETE_REGION_LEDGER_USED"] is False
    assert result["OWNER_REGION_CALLS"] == result["R7_CENSUS_CALLS"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "strict_S3",
        "type29",
        "dual",
        "raw_E",
        "root_floor",
        "missing_k",
        "hunter_minimum",
        "duplicate_attachment",
        "SUM_credits",
        "other_state",
        "missing_classified",
    ],
)
def test_required_semantic_result_negative_controls(result: dict[str, Any], mutation: str) -> None:
    bad = copy.deepcopy(result)
    if mutation == "strict_S3":
        bad["STATE_MEMBERSHIP_PROOF"]["joint_s3_min_inclusive"] -= 1
    elif mutation == "type29":
        bad["TYPE_COEFFICIENT_PROOF"]["type29_excluded"] = False
    elif mutation == "dual":
        bad["TYPE_COEFFICIENT_PROOF"]["dual"][1] += 1
    elif mutation == "raw_E":
        bad["ROOT_PAIR_PROOF"]["root_residual_floor"] = 107800
    elif mutation == "root_floor":
        bad["ROOT_PAIR_PROOF"]["root_residual_floor"] += 1
    elif mutation == "missing_k":
        bad["HUNTER_NINE_ROW_PROOF"]["rows"].pop()
    elif mutation == "hunter_minimum":
        bad["HUNTER_NINE_ROW_PROOF"]["rows"][0][3] += 1
    elif mutation == "duplicate_attachment":
        topology = bad["HUNTER_NINE_ROW_PROOF"]["cores"][0]["extension_topology_example"]
        topology["attachments"][0] = topology["core"][0]
    elif mutation == "SUM_credits":
        bad["ADOPTED_STATE_BOUND"] -= 3992870
        bad["CORRECTION_COMBINATION"] = "SUM"
    elif mutation == "other_state":
        bad["FINAL_STATE_TERMS"][0]["bound"] -= 1
    else:
        bad["FINAL_CLASSIFIED_TERMS"].pop()
    with pytest.raises(AssertionError, match="deterministic replay/source binding"):
        cert.verify_result(bad)


def test_live_wrong_domain_type29_dual_and_missing_k_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coefficients = tuple(
        (p.triple_recovery - 9485, p.pair_recovery_cost - p.triple_recovery - 206115)
        for p in cert.hunter.r5.anchor_incidence_profiles()
    )
    with pytest.raises(AssertionError, match="type29 exclusion"):
        cert.validate_coefficients(coefficients, exclude_type29=False)
    with monkeypatch.context() as patch:
        patch.setattr(cert, "S3_MIN", 1005536)
        with pytest.raises(AssertionError, match="strict S3"):
            cert.membership_proof()
    with monkeypatch.context() as patch:
        patch.setattr(cert, "DUAL", (39137, 13733226361, 154447))
        with pytest.raises(AssertionError, match="dual coefficients"):
            cert.validate_coefficients(coefficients)
    with monkeypatch.context() as patch:
        patch.setattr(cert, "KS", tuple(range(9, 17)))
        with pytest.raises(AssertionError, match="nine legal k"):
            cert.scalar_proof()


def test_live_overstrong_hunter_and_family_mutations_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = cert.hunter.minimum_tree_correction

    def too_strong(phi: cert.hunter.Cells, mass: int, k: int = 18) -> cert.hunter.TreeMinimum:
        row = original(phi, mass, k)
        return replace(row, correction=row.correction + 1)

    with monkeypatch.context() as patch:
        patch.setattr(cert.hunter, "minimum_tree_correction", too_strong)
        with pytest.raises(AssertionError, match="nine exact"):
            cert.scalar_proof()
    terms = cert.family_terms()
    for wrong in (terms[:-2] + terms[-1:], ((terms[0][0], terms[0][1] - 1), *terms[1:])):
        with pytest.raises(AssertionError, match="must remain unchanged"):
            cert.replace_state(wrong, 354603232)

    def summed(a: int, b: int) -> int:
        return a + b

    with monkeypatch.context() as patch:
        patch.setattr(cert, "adopt_state_bound", summed)
        with pytest.raises(AssertionError, match="State-bound MIN"):
            cert.replace_state(terms, 354603232)


@pytest.mark.parametrize(
    "name,old,new,args,expected",
    [
        (
            "ceil_div",
            "return -(-numerator // denominator)",
            "return numerator // denominator",
            (1, 39137),
            1,
        ),
        (
            "combine_corrections",
            "return max(credits.values())",
            "return sum(credits.values())",
            ({"existing": 7, "hunter": 11},),
            11,
        ),
        (
            "adopt_state_bound",
            "return min(existing, universal)",
            "return max(existing, universal)",
            (355121046, 354603232),
            354603232,
        ),
    ],
)
def test_non_equivalent_source_mutants_killed_in_memory(
    name: str, old: str, new: str, args: tuple[Any, ...], expected: int
) -> None:
    original = cast(Callable[..., int], getattr(cert, name))
    assert original(*args) == expected
    source = inspect.getsource(original)
    assert source.count(old) == 1
    namespace = dict(vars(cert))
    exec(compile(source.replace(old, new), "<targeted-source-mutant>", "exec"), namespace)
    mutant = cast(Callable[..., int], namespace[name])
    with pytest.raises(AssertionError):
        assert mutant(*args) == expected
    assert original(*args) == expected


@pytest.mark.parametrize(
    "relative",
    [
        cert.BASE_RESULT,
        cert.R10_RESULT,
        "src/lottolab/research/b649_k20_r3_state_tail_owner_chase_r14.py",
        cert.SOURCE_RELATIVE,
        cert.TEST_RELATIVE,
    ],
)
def test_live_byte_tampering_rejected_with_warm_caches(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    original = Path.read_bytes
    target = cert.REPO_ROOT / relative

    def tampered(path: Path) -> bytes:
        data = original(path)
        return data + b"\n" if path == target else data

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", tampered)
        with pytest.raises(AssertionError, match=r"identity|source binding"):
            cert.verify_result(result)
    assert cert.verify_result(result)["status"] == "PASS"


def test_deterministic_stored_result_bytes_and_implementation_binding(
    result: dict[str, Any],
) -> None:
    stored = cert.RESULT_PATH.read_bytes()
    assert stored == cert.encode(result).encode()
    assert json.loads(stored) == result
    for relative, expected in result["SOURCE_AUTHORITY"]["implementation_sha256"].items():
        assert sha256((cert.REPO_ROOT / relative).read_bytes()).hexdigest() == expected
    assert cert.verify_stored_result()["status"] == "PASS"
