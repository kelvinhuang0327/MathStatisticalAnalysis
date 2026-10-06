"""Exact owner handoffs, bounded enumeration, and complete compressed coverage."""

from __future__ import annotations

import json
from fractions import Fraction
from itertools import pairwise, product
from math import comb
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_tail_state_owner_chase_r16 as r16


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(r16.RESULT_PATH.read_text(encoding="utf-8")))


def _chase(*, transition_limit: int = 8, drop_target: int = 50) -> r16.Chase:
    return r16.Chase(
        states=(("state:a", 100), ("state:b", 98)),
        baseline=1_000,
        next_loss=899,
        classified_maximum=("classified-vector", 90),
        start_bound=101,
        r4_reference=0,
        drop_target=drop_target,
        transition_limit=transition_limit,
    )


def _level(chase: r16.Chase, loss: int, next_loss: int) -> None:
    row = r16.r15.r13.ClassifiedVector(
        vector_id=f"synthetic:{loss}",
        counts=(0,),
        local_loss=loss,
        status=r16.r15.r12.ELIMINATED,
        pair_union_penalty=None,
        forest_floor=None,
        r6_correction=None,
        four_ticket_status=None,
        four_ticket_penalty=None,
        correction=None,
        vector_bound=None,
        witness=None,
    )
    chase.advance_tail(loss, ((0,),), next_loss, lambda _: row)


def _forbidden_proof(*_: object) -> NoReturn:
    pytest.fail("forbidden certificate dependency was dispatched")


def test_canonical_primitives_and_independent_first_crossover() -> None:
    assert r16.canonical_primitives() == {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert r16.canonical_baseline() == 356_598_858 + 8_449_770 == 365_048_628
    assert 365_048_628 - 356_551_580 == r16.START_CROSSOVER_LOSS == 8_497_048
    assert r16.TAIL_BASE_CONSTANT - (r16.START_CROSSOVER_LOSS - 1) == 356_551_581
    terms = dict(r16.initial_state_terms())
    assert sorted(terms.items(), key=lambda row: row[1], reverse=True)[:2] == [
        (r16.START_STATE_OWNER_ID, 356_551_580),
        (r16.NEXT_STATE_ID, 356_378_218),
    ]
    assert r16.r15.r14.joint_constant() - 13_169_800 + 789_320 == 356_378_218
    assert r16.initial_chase().owners == (r16.TAIL_ID,)


def test_interval_enumeration_and_next_loss_against_ticket_assignment_oracle() -> None:
    losses = (0, 11, 2, 5)
    tickets = 4
    assignments = set(product(range(len(losses)), repeat=tickets))
    all_counts = {tuple(row.count(index) for index in range(len(losses))) for row in assignments}
    attained = sorted({sum(losses[index] for index in row) for row in assignments})
    for lower, upper in ((0, 0), (1, 8), (10, 17), (23, 35), (44, 44)):
        expected = {
            counts
            for counts in all_counts
            if lower
            <= sum(count * loss for count, loss in zip(counts, losses, strict=True))
            <= upper
        }
        rows = tuple(r16.iter_interval_vectors(losses, tickets, lower, upper))
        assert len(rows) == len(set(rows))
        assert set(rows) == expected
    for lower in range(45):
        assert r16.next_attained_loss(losses, tickets, lower) == min(
            loss for loss in attained if loss >= lower
        )
    with pytest.raises(ValueError, match="finite type-count space"):
        r16.next_attained_loss(losses, tickets, 45)


def test_exact_integer_next_loss_for_large_values() -> None:
    cost = 10**18 + 3
    assert r16.next_attained_loss((0, cost), 2, cost + 1) == 2 * cost


def test_tail_state_switches_and_non_owner_refinement_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = _chase()
    _level(chase, 899, 901)
    assert chase.owners == ("state:a",)
    monkeypatch.setattr(r16.r15, "certify_state", _forbidden_proof)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r16.certify_state(chase, "state:b")
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        _level(chase, 901, 902)
    chase.improve_state("state:a", {"new_bound": 80})
    assert chase.owners == (r16.TAIL_ID,)
    _level(chase, 901, 903)
    assert chase.owners == ("state:b",)
    assert chase.transitions == 3


def test_tied_tail_and_state_selects_state_and_blocks_tail_descent() -> None:
    chase = _chase()
    chase.next_loss = 900
    assert chase.owners == ("state:a", r16.TAIL_ID)
    with pytest.raises(AssertionError, match="tail descent below"):
        _level(chase, 900, 901)
    chase.improve_state("state:a", {"new_bound": 80})
    assert chase.owners == (r16.TAIL_ID,)


def test_success_c_requires_eight_transitions_not_classified_owner_identification() -> None:
    chase = _chase()
    chase.classified_maximum = ("classified-vector", 105)
    assert chase.owners == ("classified-vector",)
    assert chase.transitions == 0
    assert chase.stop_condition() == r16.STOP_CLASSIFIED != r16.STOP_C
    budget = _chase(transition_limit=2)
    _level(budget, 899, 901)
    budget.improve_state("state:a", {"new_bound": 80})
    assert budget.transitions == 2
    assert budget.stop_condition() == r16.STOP_C
    with pytest.raises(AssertionError, match="stop condition"):
        _level(budget, 901, 903)


def test_no_prior_level_reclassification_before_dependency_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(r16.r15.r13, "classify_vector", _forbidden_proof)
    old = r16.dense([[0, 6], [1, 11], [17, 1]])
    with pytest.raises(AssertionError, match="must never be reclassified"):
        r16.classify_new_tail_vector(old, r16.TAIL_BASE_CONSTANT, r16.START_STATE_MAX_BOUND)
    with pytest.raises(AssertionError, match="active owner interval"):
        r16.tail_census(r16.START_LOSS - 1, r16.START_CROSSOVER_LOSS)


def test_prior_fingerprint_validation_never_classifies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r16.r15.r13, "classify_vector", _forbidden_proof)
    r16.verify_prior_level_fingerprints.cache_clear()
    assert r16.verify_prior_level_fingerprints() == {"R15_LEVELS": 397, "R15_VECTORS": 4586}


def test_prior_fingerprint_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    stored = json.loads(json.dumps(r16.authority()))
    stored["TAIL_LEVEL_CERTIFICATES"][0]["counts_sha256"] = "0" * 64
    monkeypatch.setattr(r16, "authority", lambda: stored)
    r16.verify_prior_level_fingerprints.cache_clear()
    with pytest.raises(AssertionError, match="level fingerprints changed"):
        r16.verify_prior_level_fingerprints()


def test_region_coverage_and_weakest_certificate_for_every_compressed_vector(
    result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (record,) = cast(list[dict[str, Any]], result["STATE_OWNER_CERTIFICATES"])
    owner = r16.START_STATE_OWNER_ID
    region = r16.r15.r14.owner_region(owner)
    inherited = r16.r15.r14_refined_members(owner, region)
    threshold = int(record["active_competing_threshold"])
    pending = tuple(
        row
        for row in region
        if r16.r15.r14.raw_bound(row) >= threshold and row.witness_counts not in inherited
    )
    vectors = r16.r15.represented_vectors(pending)
    refined = cast(list[dict[str, Any]], record["region_moment_certificates"])
    assert len(region) == len(record["complete_region_members"]) == 582
    assert sum(row.represented_vector_count for row in region) == 633
    assert len(inherited) == 40
    assert len(pending) == len(refined) == 74
    assert sum(row.represented_vector_count for row in pending) == 76
    assert sum(row.represented_vector_count > 1 for row in pending) == 2
    for state, stored in zip(pending, refined, strict=True):
        recovered = vectors[state.witness_counts]
        assert len(recovered) == state.represented_vector_count
        certificates = [r16.r15.r14.moment_certificate(counts) for counts in recovered]
        assert stored["vector_certificates"] == certificates
        correction = max(
            state.applied_residual_union_penalty,
            min(int(certificate["correction_lower_bound"]) for certificate in certificates),
        )
        bound = (
            r16.r15.r14.joint_constant()
            - state.anchor_pair_s2
            + state.anchor_triple_s3
            - correction
        )
        assert stored["certified_bound"] == bound <= r16.r15.r14.raw_bound(state)
    certified_keys = set(inherited) | {row.witness_counts for row in pending}
    carried = [
        r16.r15.r14.raw_bound(row) for row in region if row.witness_counts not in certified_keys
    ]
    assert len(certified_keys) + len(carried) == len(region)
    assert max(carried) == record["new_bound"] == 356_505_100 < threshold
    support = tuple(tuple(labels) for labels in record["support_witness"])
    assert r16.r15.r8.validate_support_assignment(
        r16.dense(record["support_witness_counts"]), support
    )

    calls: list[r16.CountVector] = []
    original = r16.r15.r14.moment_certificate

    def counted(counts: r16.CountVector) -> dict[str, Any]:
        calls.append(counts)
        return original(counts)

    monkeypatch.setattr(r16.r15.r14, "moment_certificate", counted)
    chase = r16.initial_chase()
    chase.next_loss = 8_497_076
    assert chase.owners == (owner,)
    replay, _ = r16.certify_state(chase, owner)
    assert replay["new_bound"] == record["new_bound"]
    assert set(calls) == {vector for recovered in vectors.values() for vector in recovered}
    assert len(calls) == 76


def test_attained_tail_conservation_first_crossover_and_exact_final_owner(
    result: dict[str, Any],
) -> None:
    phases = (
        r16.tail_census(r16.START_LOSS, r16.START_CROSSOVER_LOSS),
        r16.tail_census(8_497_076, r16.TAIL_BASE_CONSTANT - r16.START_CLASSIFIED_MAXIMUM),
        r16.tail_census(8_513_778, r16.TAIL_BASE_CONSTANT - 356_530_699),
    )
    expected = tuple(level for phase in phases for level in phase[:-1])
    records = cast(list[dict[str, Any]], result["TAIL_LEVEL_CERTIFICATES"])
    assert len(expected) == len(records) == 311
    assert sum(len(vectors) for _, vectors in expected) == result["TAIL_VECTORS_PROCESSED"] == 3411
    next_levels = (*expected[1:], phases[-1][-1])
    for (loss, vectors), (next_loss, _), record in zip(expected, next_levels, records, strict=True):
        assert record["local_loss"] == loss >= r16.START_LOSS
        assert record["next_unclassified_loss"] == next_loss
        assert record["vector_count"] == len(vectors)
        assert record["counts_sha256"] == r16.digest(vectors)
        assert record["realizable_count"] + record["unrealizable_count"] == len(vectors)
        assert record["unresolved_count"] == 0
        assert r16.TAIL_BASE_CONSTANT - loss > record["active_state_threshold"]
        assert r16.TAIL_BASE_CONSTANT - loss > record["active_competing_threshold"]
    transitions = result["OWNER_TRANSITIONS"]
    assert transitions[0]["next_unclassified_loss"] == 8_497_076 >= r16.START_CROSSOVER_LOSS
    assert transitions[0]["to"] == [r16.START_STATE_OWNER_ID]
    assert transitions[1]["to"] == [r16.TAIL_ID]
    assert transitions[2]["to"] == ["tail-vector:L6709346:0x6,1x11,17x1"]
    assert transitions[-1]["to"] == [r16.TAIL_ID]
    assert result["NEXT_UNCLASSIFIED_LOSS"] == phases[-1][-1][0] == 8_518_006
    assert (
        result["R3_BOUND"]
        == max(
            result["STATE_MAX_BOUND"],
            result["UNCLASSIFIED_TAIL_BOUND"],
            result["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
        )
        == 356_530_622
    )
    assert result["R3_DROP"] == 68_236
    assert result["SUCCESS_A"] is result["SUCCESS_B"] is False
    assert result["SUCCESS_C"] is True
    assert result["OWNER_TRANSITION_COUNT"] == result["OWNER_TRANSITION_LIMIT"] == 8
    assert result["STOP_CONDITION"] == r16.STOP_C
    trajectory = result["OWNER_ACTION_TRAJECTORY"]
    assert all(current["from"] == previous["to"] for previous, current in pairwise(trajectory))
    assert sum(row["from"] != row["to"] for row in trajectory) == 8
    assert len(trajectory) == 311 + 1 + 4
    assert len([row for row in trajectory if row["action"].startswith("classified:")]) == 4
    final = {row["stable_id"]: row["bound"] for row in result["CURRENT_STATE_TERMS"]}
    assert result["PROCESSED_STATE_OWNER_IDS"] == [r16.START_STATE_OWNER_ID]
    assert all(
        final[identifier] == bound
        for identifier, bound in r16.initial_state_terms()
        if identifier != r16.START_STATE_OWNER_ID
    )


def test_full_replay_guarded_against_prior_level_and_non_owner_work(
    result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    losses_seen: list[int] = []
    classified_owners_seen: list[str] = []
    original = r16.classify_new_tail_vector
    original_refine = r16.refine_classified_owner

    def guarded_refine(chase: r16.Chase, owner_id: str) -> None:
        assert owner_id in chase.owners
        assert chase.transitions < 8
        classified_owners_seen.append(owner_id)
        original_refine(chase, owner_id)

    def guarded(
        counts: r16.CountVector, baseline: int, threshold: int
    ) -> r16.r15.r13.ClassifiedVector:
        loss = r16.r15.r12.local_loss(
            counts, r16.r15.r6.local_losses(r16.r15.r5.anchor_incidence_profiles())
        )
        assert loss >= r16.START_LOSS
        losses_seen.append(loss)
        return original(counts, baseline, threshold)

    monkeypatch.setattr(r16, "classify_new_tail_vector", guarded)
    monkeypatch.setattr(r16, "refine_classified_owner", guarded_refine)
    replay = json.loads(json.dumps(r16.build_result()))
    assert len(losses_seen) == 3411
    assert classified_owners_seen == [
        record["owner_id"] for record in result["CLASSIFIED_OWNER_CERTIFICATES"]
    ]
    assert len(classified_owners_seen) == 4
    for key in (
        "R3_BOUND",
        "R3_DROP",
        "CURRENT_STATE_TERMS",
        "OWNER_TRANSITIONS",
        "OWNER_ACTION_TRAJECTORY",
        "STATE_OWNER_CERTIFICATES",
        "CLASSIFIED_OWNER_CERTIFICATES",
        "R12_OWNER_LEVEL_RECOVERY",
        "CURRENT_CLASSIFIED_TERMS",
        "TAIL_LEVEL_CERTIFICATES",
        "FINAL_OWNER_IDS",
        "NEXT_UNCLASSIFIED_LOSS",
        "STOP_CONDITION",
    ):
        assert replay[key] == result[key]


def test_r12_owner_level_recovery_reuses_bounds_without_classification_or_refinement(
    result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r16.initial_chase()
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r16.recover_r12_owner_level(chase)
    chase.states = tuple(
        (row["stable_id"], int(row["bound"])) for row in result["CURRENT_STATE_TERMS"]
    )
    chase.next_loss = 8_513_778
    monkeypatch.setattr(r16.r15.r12, "classify_vector", _forbidden_proof)
    monkeypatch.setattr(r16.r15.r13, "classify_vector", _forbidden_proof)
    monkeypatch.setattr(r16.r15.r12, "construct_support_witness", _forbidden_proof)
    monkeypatch.setattr(r16.r15.r14, "moment_certificate", _forbidden_proof)
    before = chase.bound, chase.owners
    r16.recover_r12_owner_level(chase)
    assert (chase.bound, chase.owners) == before
    assert len(chase.r12_member_counts) == 24
    assert chase.transitions == len(chase.classified_records) == 0
    assert chase.r12_recovery == result["R12_OWNER_LEVEL_RECOVERY"]
    assert chase.r12_recovery["recovery_counts_as_owner_transition"] is False


def test_classified_r14_dual_and_supports_independently_replay(
    result: dict[str, Any],
) -> None:
    records = cast(list[dict[str, Any]], result["CLASSIFIED_OWNER_CERTIFICATES"])
    assert len(records) == 4
    for record in records:
        counts = r16.dense(record["counts"])
        certificate = r16.r15.r14.moment_certificate(counts)
        slope = Fraction(*certificate["outside_slope"])
        minimum_sum = 0
        for pair in certificate["pair_table_rows"]:
            left, right = cast(list[int], pair["types"])
            amount = comb(counts[left], 2) if left == right else counts[left] * counts[right]
            api = "_pair_event_correction_table"
            table = getattr(r16.r15.r8, api)(left, right)
            minimum = min(int(row[4]) for row in table)
            assert pair["pair_count"] == amount
            assert pair["pair_minimum"] == minimum
            assert pair["exact_four_event_table_sha256"] == r16.digest(table)
            assert all(Fraction(row[4] - minimum) >= slope * row[3] for row in table)
            assert pair["s4_minimum"] == min(row[5] for row in table)
            minimum_sum += amount * minimum
        assert minimum_sum == certificate["pair_minimum_sum"]
        profiles = r16.r15.r5.anchor_incidence_profiles()
        outside_total = sum(
            count * profile.outside for count, profile in zip(counts, profiles, strict=True)
        )
        quotient, remainder = divmod(outside_total, 40)
        assert certificate["outside_incidence_total"] == outside_total
        assert (
            certificate["outside_pair_mass_floor"] == 40 * comb(quotient, 2) + remainder * quotient
        )
        credit = slope * int(certificate["outside_pair_mass_floor"])
        floor = minimum_sum + (credit.numerator + credit.denominator - 1) // credit.denominator
        assert floor == certificate["residual_s2_lower_bound"]
        correction = (floor + 8) // 9
        assert correction == certificate["correction_lower_bound"]
        for multiplicity in range(19):
            assert Fraction(comb(multiplicity, 2), 9) <= max(multiplicity - 1, 0)
        assert record["new_bound"] == min(
            record["prior_bound"], r16.TAIL_BASE_CONSTANT - r16.R12_OWNER_LOSS - correction
        )
        support = tuple(tuple(labels) for labels in record["support_witness"])
        assert r16.r15.r8.validate_support_assignment(counts, support)
        actual_pair_moment, _ = r16.r15.r8.witness_costs(counts, support)
        assert actual_pair_moment >= floor
        assert record["owner_id"] in record["owner_set_at_dispatch"]
        assert record["prior_level_classification_calls"] == 0
        assert certificate == record["certificate"]


def test_classified_non_owner_guard_and_unmodified_lower_members(
    result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(r16.r15.r14, "moment_certificate", _forbidden_proof)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r16.refine_classified_owner(r16.initial_chase(), "tail-vector:L6709346:0x6,1x11,17x1")
    refined = {record["owner_id"] for record in result["CLASSIFIED_OWNER_CERTIFICATES"]}
    assert len(refined) == 4
    terms = {row["stable_id"]: int(row["bound"]) for row in result["CURRENT_CLASSIFIED_TERMS"]}
    losses = r16.r15.r6.local_losses(r16.r15.r5.anchor_incidence_profiles())
    for counts in r16.iter_interval_vectors(losses, 18, r16.R12_OWNER_LOSS, r16.R12_OWNER_LOSS):
        identifier = r16.r15.r13.vector_id(counts, r16.R12_OWNER_LOSS)
        if identifier not in refined:
            envelope = r16.r15.r6.type_count_envelope(counts)
            assert (
                terms[identifier]
                == r16.TAIL_BASE_CONSTANT - r16.R12_OWNER_LOSS - envelope.combined_pair_penalty
            )
    assert max(terms.values()) == result["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"] == 356_527_168
