"""R26 proof authority, signature coverage, model and complete-ledger regression."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_six_owner_batch_refinement_r26 as r26
from lottolab.research.b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    bound_from_cap,
    profile_id,
)


@pytest.fixture(scope="module")
def state() -> r26.State:
    return r26.current_state()


def synthetic_proof(group: Sequence[Certificate]) -> dict[str, object]:
    cap = r26.target_cap(group[0])
    return {
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
        "PROFILE_IDS": [profile_id(c.profile) for c in group],
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": cap,
        "REFUTED_GRAPH_TRIANGLE_COUNT": cap + 1,
        "OPEN_WEDGE_CEILING_REFUTED": r26.overlap_wedge_count(group[0].profile) - 3 * (cap + 1),
    }


def test_exact_six_and_full_ledger(state: r26.State) -> None:
    assert len(state.bounds) == len(state.certificates) == 408
    assert r26.family_state(state.bounds) == (313_650_504, r26.OWNERS)
    assert r26.NEXT_CURSOR_PROFILE not in state.bounds
    assert sum(b > r26.NEXT_CURSOR_BOUND for b in state.bounds.values()) == 144
    assert not any(sum(d * d for d in p) == 318 for p in state.bounds)


def test_six_certificate_provenance(state: r26.State) -> None:
    sources = [r26.certificate_row(state.certificates[p]) for p in r26.OWNERS]
    assert sources[0]["SOURCE_ROW"] == "PROFILE_BOUNDS[0]"
    assert [s["SOURCE_ROW"] for s in sources[1:]] == [f"OWNER_ATTEMPTS[{i}]" for i in range(3, 8)]
    for row in sources:
        assert row["CURRENT_BOUND"] == 313_650_504
        assert row["TRIANGLE_CAP"] == 271
        assert row["NONCORE_TRIANGLE_CAP"] == 249
        assert row["S3"] == 5_260_528
        assert row["S4_FLOOR"] == 112
        witness = r26.object_row(row["REALIZABILITY_WITNESS"])
        assert witness["STATUS"] == "PASS"
        assert (witness["TRIPLE_SUPPORT_COUNT"], witness["DOUBLE_SUPPORT_COUNT"]) == (22, 27)


def test_structural_grouping_and_histogram_union(state: r26.State) -> None:
    certificates = [state.certificates[p] for p in r26.OWNERS]
    groups = r26.signature_groups(certificates)
    assert len(groups) == 1
    assert tuple(c.profile for c in groups[0]) == r26.OWNERS
    assert r26.signature(groups[0][0]) == (20, 22, 27, 93, 342, 834, 271, 5260528, 112, 313650504)
    # Changing one structural certificate value must separate its group.
    changed = [*certificates[:-1], replace(certificates[-1], s4=1680)]
    assert len(r26.signature_groups(changed)) == 2
    assert len({c.profile for c in groups[0]}) == 6


def test_two_triangle_reduction_required(state: r26.State) -> None:
    for p in r26.OWNERS:
        c = state.certificates[p]
        assert c.bound - r26.NEXT_CURSOR_BOUND == 12_656
        assert r26.target_cap(c) == 269
        assert bound_from_cap(p, 270, 112)[1] == 313_638_632 > r26.NEXT_CURSOR_BOUND
        assert bound_from_cap(p, 269, 112) == (5_236_784, 313_626_760)


def test_canonical_primitives_and_s4() -> None:
    assert r26.canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert r26.K20_S2 == 63_838_600
    assert r26.k20_min_s2_s4_lower_bound_certificate().s4_lower_bound == 112


@pytest.mark.parametrize("status", ["FEASIBLE", "OPTIMAL", "UNKNOWN", "EXTERNAL_TIMEOUT"])
def test_feasible_is_never_a_refutation(state: r26.State, status: str) -> None:
    group = [state.certificates[p] for p in r26.OWNERS]
    proof = synthetic_proof(group)
    proof["STATUS"] = status
    assert r26.accepted_cap(proof, r26.OWNERS, 269) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("PROFILE_IDS", list(r26.OWNER_IDS[:-1])),
        ("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND", 270),
        ("REFUTED_GRAPH_TRIANGLE_COUNT", 271),
        ("OPEN_WEDGE_CEILING_REFUTED", 25),
        ("CERTIFICATE_KIND", "FEASIBLE_OBJECTIVE"),
    ],
)
def test_refutation_certificate_identity(state: r26.State, field: str, value: object) -> None:
    proof = synthetic_proof([state.certificates[p] for p in r26.OWNERS])
    proof[field] = value
    with pytest.raises(AssertionError, match="identity"):
        r26.accepted_cap(proof, r26.OWNERS, 269)


def test_generic_attempt_precedes_newly_exposed_owners(state: r26.State) -> None:
    calls: list[tuple[r26.DegreeProfile, ...]] = []

    def prove(
        group: Sequence[Certificate], bounds: Mapping[r26.DegreeProfile, int]
    ) -> dict[str, object]:
        profiles = tuple(c.profile for c in group)
        r26.assert_solver_scope(profiles, bounds)
        calls.append(profiles)
        return synthetic_proof(group) if len(calls) == 1 else {"STATUS": "PROOF_BUDGET_EXHAUSTED"}

    result = r26.run_batch(state, prove)
    assert calls[0] == r26.OWNERS
    assert tuple(map(profile_id, calls[1])) == ("66665555554440000000", "66655555555530000000")
    assert len(calls) == 2
    assert result["TASK_STATUS"] == r26.SUCCESS_C
    assert result["FAMILY_UPPER_BOUND"] == result["MAX_RESOLVED_BOUND"] == 313_649_608
    assert result["NEWLY_EXPOSED_RESOLVED_OWNER_COUNT"] == 2
    assert result["CURRENT_BOUND_OWNER_SET"] == list(map(profile_id, calls[1]))


def test_full_resolved_ledger_recomputed_after_every_group(state: r26.State) -> None:
    result = r26.run_batch(state, lambda group, _bounds: synthetic_proof(group))
    assert result["TASK_STATUS"] == r26.SUCCESS_B
    assert result["FAMILY_UPPER_BOUND"] == r26.NEXT_CURSOR_BOUND
    assert result["CURRENT_BOUND_OWNER_SET"] == [profile_id(r26.NEXT_CURSOR_PROFILE)]
    ledger = r26.rows(result["FINAL_RESOLVED_LEDGER"])
    assert len(ledger) == 408
    assert (
        max(r26.integer(r26.object_row(r)["CURRENT_BOUND"]) for r in ledger)
        <= r26.NEXT_CURSOR_BOUND
    )
    steps = [r26.object_row(r) for r in r26.rows(result["GROUP_REFINEMENT_STEPS"])]
    assert steps[0]["FAMILY_BOUND_AFTER"] == 313_649_608
    assert steps[1]["FAMILY_BOUND_AFTER"] == 313_649_048
    assert all(s["COMPLETE_LEDGER_ROW_COUNT"] == 408 for s in steps)
    assert all(
        r26.integer(s["FAMILY_BOUND_AFTER"]) < r26.integer(s["FAMILY_BOUND_BEFORE"]) for s in steps
    )


def test_no_drop_cannot_claim_success(state: r26.State) -> None:
    result = r26.run_batch(state, lambda _g, _b: {"STATUS": "FEASIBLE"})
    assert result["TASK_STATUS"] == r26.NO_DROP
    assert result["FAMILY_UPPER_BOUND"] == 313_650_504
    assert result["GROUP_REFINEMENT_STEPS"] == []


def test_cursor_plateau_and_stale_owner_guards(state: r26.State) -> None:
    with pytest.raises(AssertionError, match="current resolved"):
        r26.assert_solver_scope((r26.NEXT_CURSOR_PROFILE,), state.bounds)
    plateau = r26.decode_profile("66666665432211111111")
    with pytest.raises(AssertionError, match="current resolved"):
        r26.assert_solver_scope((plateau,), state.bounds)
    bounds = {**state.bounds, r26.OWNERS[0]: 313626760}
    with pytest.raises(AssertionError, match="current resolved"):
        r26.assert_solver_scope((r26.OWNERS[0],), bounds)
    with pytest.raises(AssertionError, match="forbidden"):
        r26.union_support_model((r26.NEXT_CURSOR_PROFILE,), 1)


def test_no_plateau_or_cheap_chase_rerun(state: r26.State, monkeypatch: pytest.MonkeyPatch) -> None:
    from lottolab.research import b649_k20_min_s2_cursor_dynamic_owner_chase_r25 as r25
    from lottolab.research import b649_k20_min_s2_next_distinct_plateau_r10 as r10

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("forbidden plateau or cheap chase rerun")

    monkeypatch.setattr(r25, "cheap_certificate", forbidden)
    monkeypatch.setattr(r25, "run_chase", forbidden)
    monkeypatch.setattr(r25, "plateau_certificate", forbidden)
    monkeypatch.setattr(r10, "enumerate_current_top_plateau", forbidden)
    monkeypatch.setattr(r10, "find_next_distinct_profile", forbidden)
    rebuilt = r26.current_state()
    assert rebuilt.bounds == state.bounds
    result = r26.run_batch(rebuilt, lambda g, _b: synthetic_proof(g))
    assert result["TASK_STATUS"] == r26.SUCCESS_B


@pytest.mark.parametrize("mutation", ["omit", "duplicate", "bound", "owner"])
def test_authority_reconstruction_rejects_drift(mutation: str) -> None:
    inputs, hashes = r26.committed_inputs()
    changed = copy.deepcopy(inputs)
    r25 = changed["R25"]
    ledger = r26.rows(r25["FINAL_RESOLVED_LEDGER"])
    if mutation == "omit":
        ledger.pop()
    elif mutation == "duplicate":
        ledger.append(ledger[0])
    elif mutation == "bound":
        r26.object_row(ledger[0])["CURRENT_BOUND"] = 313650505
    else:
        r25["CURRENT_BOUND_OWNER_SET"] = list(r26.OWNER_IDS[:-1])
    with pytest.raises(AssertionError):
        r26.reconstruct_state(changed, hashes)


def test_union_model_accepts_all_six_real_witnesses(state: r26.State) -> None:
    result = r26.witness_model_check([state.certificates[p] for p in r26.OWNERS])
    assert result["STATUS"] == "PASS"
    assert len(r26.rows(result["CHECKS"])) == 6


def test_sealed_proof_complete_ledger_and_guards(state: r26.State) -> None:
    path: Path = r26.repo_root() / r26.RESULT_DIRECTORY / r26.RESULT_FILENAME
    sealed = r26.object_row(json.loads(path.read_text()))
    assert sealed["BASE_HEAD"] == r26.BASE_HEAD
    assert sealed["OWNER_PROFILES"] == list(r26.OWNER_IDS)
    assert sealed["OWNER_SIGNATURE_GROUP_COUNT"] == 1
    for guard in (
        "NO_76_PLATEAU_RERUN_GUARD",
        "NO_48_OWNER_CHEAP_CHASE_RERUN_GUARD",
        "NO_CURSOR_WORK_GUARD",
    ):
        assert sealed[guard] == "PASS"
    assert (
        sealed["PLATEAU_RERUN_COUNT"]
        == sealed["CHEAP_CHASE_RERUN_COUNT"]
        == sealed["CURSOR_PROFILE_SOLVES"]
        == 0
    )
    bounds = dict(state.bounds)
    for raw in r26.rows(sealed["GROUP_ATTEMPTS"]):
        attempt = r26.object_row(raw)
        profiles = tuple(r26.decode_profile(p) for p in r26.rows(attempt["PROFILE_IDS"]))
        r26.assert_solver_scope(profiles, bounds)
        if attempt["STATUS"] != "INFEASIBLE":
            continue
        cap = r26.integer(attempt["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
        assert r26.accepted_cap(attempt, profiles, cap) == cap
        for p in profiles:
            cert = state.certificates[p]
            bounds[p] = bound_from_cap(p, cap, r26.integer(cert.s4))[1]
    observed = {
        r26.decode_profile(row["PROFILE_ID"]): r26.integer(row["CURRENT_BOUND"])
        for row in map(r26.object_row, r26.rows(sealed["FINAL_RESOLVED_LEDGER"]))
    }
    assert observed == bounds
    family, owners = r26.family_state(observed)
    assert sealed["FAMILY_UPPER_BOUND"] == family
    assert sealed["MAX_RESOLVED_BOUND"] == max(observed.values())
    assert sealed["CURRENT_BOUND_OWNER_SET"] == list(map(profile_id, owners))
    assert sealed["REMAINING_GAP"] == family - r26.INCUMBENT
    assert cast(float, sealed["PROOF_ACTUAL_WALL_SECONDS"]) <= 3600


def test_failed_generic_precedes_six_independent_proofs(state: r26.State) -> None:
    calls: list[tuple[r26.DegreeProfile, ...]] = []

    def prove(
        group: Sequence[Certificate], _bounds: Mapping[r26.DegreeProfile, int]
    ) -> dict[str, object]:
        calls.append(tuple(c.profile for c in group))
        return {"STATUS": "UNKNOWN"} if len(calls) == 1 else synthetic_proof(group)

    result = r26.run_batch(state, prove)
    assert calls[0] == r26.OWNERS
    assert calls[1:7] == [(p,) for p in r26.OWNERS]
    steps = [r26.object_row(r) for r in r26.rows(result["GROUP_REFINEMENT_STEPS"])]
    assert [s["FAMILY_BOUND_AFTER"] for s in steps[:6]] == [313650504] * 5 + [313649608]
    assert result["TASK_STATUS"] == r26.SUCCESS_B
