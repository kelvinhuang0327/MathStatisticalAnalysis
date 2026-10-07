"""Focused construction, quotient-coverage, selection, and record round-trip checks."""

from __future__ import annotations

import copy
import dataclasses
import itertools
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest

from lottolab.research import b649_k20_11_9_single_bridge_sts13_family_exact_r1 as family
from lottolab.research.b649_official_any_prize_exact import (
    ExactPortfolioProbability,
    all_main_draw_masks,
    evaluate_portfolio,
)


def test_sts13_inputs_are_pinned_to_the_12_8_source_and_nonisomorphic() -> None:
    assert family.sts13_designs_sha256() == family.STS13_DESIGNS_SHA256
    assert all(family.is_valid_sts13(design) for design in family.STS13_DESIGNS.values())
    assert family.pasch_count(family.STS13_DESIGNS["CYCLIC"]) == 13
    assert family.pasch_count(family.STS13_DESIGNS["NONCYCLIC"]) == 8
    orders = {
        name: len(family.sts13_automorphisms(design))
        for name, design in family.STS13_DESIGNS.items()
    }
    assert orders == {"CYCLIC": 39, "NONCYCLIC": 6}


def test_graph_templates_are_the_two_cubic_six_vertex_graphs() -> None:
    for edges in family.GRAPH_TEMPLATES.values():
        family.validate_cubic_template(edges)
        assert len(family.disjoint_edge_pairs(edges)) == 18
    assert family.triangle_count(family.GRAPH_TEMPLATES["K3_3"]) == 0
    assert family.triangle_count(family.GRAPH_TEMPLATES["TRIANGULAR_PRISM"]) == 2
    orders = {
        name: len(family.graph_automorphisms(edges))
        for name, edges in family.GRAPH_TEMPLATES.items()
    }
    assert orders == {"K3_3": 72, "TRIANGULAR_PRISM": 12}


def test_every_quotient_element_preserves_its_structure() -> None:
    quotient = family.build_family_quotient()
    for name, group in quotient.sts_groups.items():
        blocks = set(family.STS13_DESIGNS[name])
        for sigma in group:
            assert {tuple(sorted(sigma[point] for point in block)) for block in blocks} == blocks
    for name, group in quotient.graph_groups.items():
        edges = set(family.GRAPH_TEMPLATES[name])
        for tau in group:
            assert {tuple(sorted((tau[left], tau[right]))) for left, right in edges} == edges


def test_orbits_partition_and_cover_every_raw_construction() -> None:
    quotient = family.build_family_quotient()
    all_pairs = set(itertools.combinations(range(13), 2))
    for orbits in quotient.a_orbits.values():
        members = [pair for orbit in orbits for pair in orbit.members]
        assert len(members) == len(set(members)) and set(members) == all_pairs
    for name, orbits in quotient.b_orbits.items():
        members = [marked for orbit in orbits for marked in orbit.members]
        expected = set(family.disjoint_edge_pairs(family.GRAPH_TEMPLATES[name]))
        assert len(members) == len(set(members)) and set(members) == expected

    assert {name: len(orbits) for name, orbits in quotient.a_orbits.items()} == {
        "CYCLIC": 2,
        "NONCYCLIC": 17,
    }
    assert {name: len(orbits) for name, orbits in quotient.b_orbits.items()} == {
        "K3_3": 1,
        "TRIANGULAR_PRISM": 4,
    }
    assert family.expected_raw_construction_count() == 2 * 78 * 2 * 18 == 5616
    assert len(quotient.representatives) == 95
    assert sum(row.weight for row in quotient.representatives) == 5616
    assert quotient.raw_construction_count == 5616
    assert quotient.raw_keys_equal_full_product
    assert quotient.structural_invariant_passes == 5616
    assert quotient.relabeling_witnesses_verified == 5616


def test_construction_follows_the_packet_definition() -> None:
    edges = family.GRAPH_TEMPLATES["TRIANGULAR_PRISM"]
    marked = family.disjoint_edge_pairs(edges)[0]
    construction = family.build_construction("NONCYCLIC", (2, 9), "TRIANGULAR_PRISM", marked)
    bridge_a = family.third_point_table(family.STS13_DESIGNS["NONCYCLIC"])[(2, 9)]

    assert construction.bridge_a == bridge_a
    assert len(construction.slots) == 20
    assert [slot for slot in construction.slots if slot[0] == "A"] == [
        ("A", (point,)) for point in range(13) if point not in (2, 9)
    ]
    assert construction.blocks[-1] == ("BRIDGE", ())
    bridge_slots = {("A", (bridge_a,)), ("B", marked[0]), ("B", marked[1])}
    holders = {
        slot
        for slot, ticket in zip(construction.slots, construction.tickets, strict=True)
        if 49 in ticket
    }
    assert holders == bridge_slots
    assert family.structural_invariants(construction.tickets) == family.EXPECTED_INVARIANTS
    a_index = construction.slots.index(("A", (bridge_a,)))
    cross = {
        (left, right)
        for left in range(11)
        for right in range(11, 20)
        if set(construction.tickets[left]).intersection(construction.tickets[right])
    }
    assert cross == {
        (a_index, construction.slots.index(("B", marked[0]))),
        (a_index, construction.slots.index(("B", marked[1]))),
    }


def test_construction_rejects_adjacent_marked_edges_and_bad_pairs() -> None:
    with pytest.raises(ValueError, match="disjoint template edges"):
        family.build_construction("CYCLIC", (0, 1), "K3_3", ((0, 3), (0, 4)))
    with pytest.raises(ValueError, match="sorted pair"):
        family.build_construction("CYCLIC", (1, 0), "K3_3", ((0, 3), (1, 4)))


def test_relabeling_witness_requires_a_true_isomorphism() -> None:
    quotient = family.build_family_quotient()
    row = next(
        candidate
        for candidate in quotient.representatives
        if candidate.a_orbit.members[-1] != candidate.a_orbit.representative
        and candidate.construction.sts_class == "CYCLIC"
    )
    construction = row.construction
    raw = family.build_construction(
        construction.sts_class,
        row.a_orbit.members[-1],
        construction.template,
        row.b_orbit.members[-1],
    )
    sigma = row.a_orbit.witnesses[-1]
    tau = row.b_orbit.witnesses[-1]
    number_map = family.relabeling_witness(raw, construction, sigma, tau)
    assert number_map is not None and sorted(number_map.values()) == list(range(1, 50))
    assert family.relabeling_witness(raw, construction, tuple(range(13)), tau) is None

    # Same number blocks, but one number moved between tickets: no longer isomorphic.
    first, second = construction.tickets[0], construction.tickets[1]
    moved = next(number for number in first if number not in second)
    kept = next(number for number in second if number not in first)
    tampered_tickets = (
        tuple(sorted((set(first) - {moved}) | {kept})),
        tuple(sorted((set(second) - {kept}) | {moved})),
        *construction.tickets[2:],
    )
    tampered = dataclasses.replace(construction, tickets=tampered_tickets)
    assert family.relabeling_witness(raw, tampered, sigma, tau) is None


def test_relabeled_members_have_equal_official_counts() -> None:
    quotient = family.build_family_quotient()
    row = next(
        candidate
        for candidate in quotient.representatives
        if candidate.construction.template == "TRIANGULAR_PRISM" and candidate.weight > 1
    )
    raw = family.build_construction(
        row.construction.sts_class,
        row.a_orbit.members[-1],
        row.construction.template,
        row.b_orbit.members[-1],
    )
    assert sorted(raw.tickets) != sorted(row.construction.tickets)
    draws = all_main_draw_masks(49, 6)
    assert (
        evaluate_portfolio(raw.tickets, draws=draws).official_any_prize_outcome_count
        == evaluate_portfolio(
            row.construction.tickets, draws=draws
        ).official_any_prize_outcome_count
    )


def test_select_best_prefers_count_then_sha_then_identity() -> None:
    representatives = family.build_family_quotient().representatives[:3]
    rows = [
        family.ScoredRepresentative(representatives[0], "b" * 64, 10),
        family.ScoredRepresentative(representatives[1], "a" * 64, 10),
        family.ScoredRepresentative(representatives[2], "0" * 64, 9),
    ]
    assert family.select_best(rows) is rows[1]
    assert family.select_best(list(reversed(rows))) is rows[1]
    with pytest.raises(ValueError):
        family.select_best([])


def _synthetic_record() -> dict[str, object]:
    rows: list[dict[str, object]] = [
        {
            "STS_CLASS": "CYCLIC",
            "DELETED_PAIR": (0, index),
            "TEMPLATE": "K3_3",
            "MARKED_EDGE_PAIR": ((0, 3), (1, 4)),
            "ORBIT_WEIGHT": 2808,
            "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT": 100 + index,
        }
        for index in (1, 2)
    ]
    return {
        "TASK_ID": family.TASK_ID,
        "CANDIDATE_COUNTS": rows,
        "REPRESENTATIVES_EVALUATED": 2,
        "ORBIT_COVERAGE": {"RAW_CONSTRUCTIONS_EXPECTED": 5616},
        "BEST_COUNT": 102,
        "BEST_PORTFOLIO": ((1, 2, 3, 4, 5, 6),),
        "STRICT_GAIN": "NO",
    }


def test_record_round_trip_normalizes_tuples_but_rejects_drift(tmp_path: Path) -> None:
    record = _synthetic_record()
    path = tmp_path / "result.json"
    family.write_and_verify_record(path, record)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    family.verify_record_round_trip(record, loaded)

    def rows(value: dict[str, object]) -> list[dict[str, object]]:
        return value["CANDIDATE_COUNTS"]  # type: ignore[return-value]

    changed = copy.deepcopy(loaded)
    rows(changed)[0]["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"] = 999
    missing = copy.deepcopy(loaded)
    rows(missing).pop()
    duplicate = copy.deepcopy(loaded)
    rows(duplicate).append(copy.deepcopy(rows(duplicate)[0]))
    field_changed = copy.deepcopy(loaded)
    field_changed["BEST_PORTFOLIO"] = [[1, 2, 3, 4, 5, 7]]
    field_missing = copy.deepcopy(loaded)
    del field_missing["STRICT_GAIN"]
    for broken, message in (
        (changed, "changed candidate rows"),
        (missing, "missing candidate rows"),
        (duplicate, "duplicate candidate rows"),
        (field_changed, "BEST_PORTFOLIO"),
        (field_missing, "STRICT_GAIN"),
    ):
        with pytest.raises(family.RecordMismatchError, match=message):
            family.verify_record_round_trip(record, broken)

    inconsistent = _synthetic_record()
    inconsistent["BEST_COUNT"] = 101
    with pytest.raises(family.RecordMismatchError, match="internally consistent"):
        family.write_and_verify_record(tmp_path / "inconsistent.json", inconsistent)


def test_load_baseline_rejects_identity_drift(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    tickets = [[1 + 6 * index + offset for offset in range(6)] for index in range(8)]
    tickets += [[index, index + 1, 40, 41, 42, 43] for index in range(1, 13)]
    path.write_text(
        json.dumps(
            {
                "FINAL_COUNT": family.BASELINE_COUNT,
                "FINAL_SHA256": family.BASELINE_NORMALIZED_SHA256,
                "FINAL_TICKETS": tickets,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="FILE_SHA256_MISMATCH"):
        family.load_baseline(path)
    file_sha = family._file_sha256(path)  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ValueError, match="NORMALIZED_PORTFOLIO_SHA_MISMATCH"):
        family.load_baseline(path, expected_file_sha256=file_sha)


@pytest.mark.skipif(
    not family.BASELINE_AUTHORITY_PATH.exists(), reason="handoff baseline not on this host"
)
def test_handoff_baseline_identity() -> None:
    portfolio = family.load_baseline(family.BASELINE_AUTHORITY_PATH)
    assert family.normalized_portfolio_sha256(portfolio) == family.BASELINE_NORMALIZED_SHA256


def test_run_family_refuses_existing_output(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        family.run_family(output_path=path, baseline_path=tmp_path / "unused.json")


def test_run_family_assembles_a_verified_record_with_a_fake_evaluator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = tuple(tuple(range(start, start + 6)) for start in range(1, 41, 2))

    def fake_evaluate(
        portfolio: Sequence[Sequence[int]], *, draws: object = None
    ) -> ExactPortfolioProbability:
        count = family.BASELINE_COUNT if tuple(map(tuple, portfolio)) == baseline else 7
        return ExactPortfolioProbability(
            main_draw_count=0,
            special_count=43,
            m3_plus_draw_count=0,
            official_any_prize_outcome_count=count,
        )

    def fake_load_baseline(path: Path) -> tuple[tuple[int, ...], ...]:
        return baseline

    def fake_draws(pool_size: int, draw_size: int) -> np.ndarray[tuple[int], np.dtype[np.uint64]]:
        return np.zeros(1, dtype=np.uint64)

    monkeypatch.setattr(family, "load_baseline", fake_load_baseline)
    monkeypatch.setattr(family, "all_main_draw_masks", fake_draws)
    monkeypatch.setattr(family, "evaluate_portfolio", fake_evaluate)
    path = tmp_path / "result.json"
    record = family.run_family(output_path=path, baseline_path=tmp_path / "unused.json")

    assert record["REPRESENTATIVES_EVALUATED"] == 95
    assert record["STRICT_GAIN"] == "NO"
    assert record["FAMILY_RESULT"] == "NO_STRICT_GAIN_FOR_DEFINED_FAMILY"
    assert record["READY_FOR_N1_ASCENT"] == "NO"
    assert record["CANONICAL_EVALUATIONS"] == {
        "BASELINE_RECOUNT": 1,
        "REPRESENTATIVES": 95,
        "RELABELING_SPOT_CHECKS": 4,
        "BEST_FRESH_RECOUNT": 1,
        "TOTAL": 101,
    }
    coverage = record["ORBIT_COVERAGE"]
    assert isinstance(coverage, dict) and coverage["CTO_SCRATCH_REFERENCE_MATCH"] is True
    family.verify_record_round_trip(record, json.loads(path.read_text(encoding="utf-8")))
