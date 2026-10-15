"""Focused checks for the C2 slots (12, 13, 15) full-domain N3 adapter."""

from __future__ import annotations

import itertools
import os
import subprocess
from math import comb
from pathlib import Path

from lottolab.research import b649_c2_n3_121315_full_domain_r1 as adapter

ROOT = Path(__file__).resolve().parents[2]


def test_c2_identity_and_remainder_sha() -> None:
    ordered = adapter.ordered_tickets(ROOT)
    kept = adapter.remainder_tickets(ROOT)
    assert len(ordered) == 20
    removed = [tuple(ordered[slot]) for slot in adapter.DESTROY_SLOTS]
    assert removed == list(adapter.REMOVED_TICKETS)
    expected = [
        ticket for index, ticket in enumerate(ordered) if index not in adapter.DESTROY_SLOTS
    ]
    assert kept == expected
    assert adapter.sha256_text(ordered) == adapter.ORDERED_SHA256
    assert adapter.sha256_text(kept) == adapter.REMAINDER_SHA256
    assert adapter.sha256_text(kept) != adapter.SEALED_121314_REMAINDER_SHA256
    zeros = adapter.zero_support_numbers(kept)
    assert zeros == [29, 34]
    assert all(number in adapter.legal_number_universe() for number in zeros)
    assert adapter.C49_6 == 13_983_816
    assert 29 in adapter.legal_number_universe() and 34 in adapter.legal_number_universe()
    assert adapter.CLASS_ID == "e4b1941183c0583d479c1467d7ce9aadf164190a07734ec592a8cf6f45ee07d7"
    assert adapter.START_COUNT == 313_263_888


def test_domain_integers_and_four_way_sum() -> None:
    domain = adapter.domain_integers()
    assert domain["LEGAL_POOL"] == comb(49, 6) - 17
    assert domain["RAW_LEGAL_N3_DOMAIN"] == comb(domain["LEGAL_POOL"], 3)
    closed_size = comb(domain["LEGAL_POOL"], 3) - comb(domain["FRESH_POOL"], 3)
    assert domain["N1_N2_CLOSED_CANDIDATES"] == closed_size
    assert domain["FRESH_CANDIDATES"] == comb(domain["FRESH_POOL"], 3)
    closed = _closed_summary()
    kept = adapter.remainder_tickets(ROOT)
    accounted = adapter.account_kernel(closed, certificate_ok=True, kept=kept)
    buckets = accounted["buckets"]
    assert sum(buckets.values()) == adapter.RAW_LEGAL_N3_DOMAIN
    assert buckets["UNRESOLVED_FRONTIER"] == 0
    assert buckets["N1_N2_CERTIFIED_NO_GAIN"] == adapter.N1_N2_CLOSED_CANDIDATES
    assert buckets["PROVEN_BOUND_PRUNED"] == adapter.FRESH_CANDIDATES
    assert adapter.status_from_accounting(buckets, stop_reason="CLOSED", verified_gain=False) == (
        "EXHAUSTIVE_NO_GAIN_CLOSED"
    )


def test_reuse_classification_uses_archived_n1_n2_scope() -> None:
    certificate = adapter.n1_n2_certificate(ROOT)
    assert certificate["applies"] is True
    assert certificate["closed_candidates"] == adapter.N1_N2_CLOSED_CANDIDATES
    kept = adapter.remainder_tickets(ROOT)
    refused = adapter.account_kernel(_timeout_summary(), certificate_ok=False, kept=kept)
    assert refused["buckets"]["N1_N2_CERTIFIED_NO_GAIN"] == 0
    assert refused["buckets"]["UNRESOLVED_FRONTIER"] >= adapter.N1_N2_CLOSED_CANDIDATES
    assert sum(refused["buckets"].values()) == adapter.RAW_LEGAL_N3_DOMAIN
    assert all(row["kind"] != "N1_N2_REUSE" for row in refused["certificates"])


def test_seven_set_canonical_conversion_does_not_mix_start_count() -> None:
    assert adapter.canonical_outcome_delta(0) == 0
    assert adapter.canonical_outcome_delta(4) == 28
    assert adapter.canonical_outcome_delta(4) != adapter.START_COUNT + 4
    assert adapter.COUNTING_UNIT == "7_SET"


def test_marginal_and_pair_tail_bounds_reject_incomplete_tails() -> None:
    assert adapter.marginal_excludes_strict_gain(3, 3, 3, 9) is True
    assert adapter.marginal_excludes_strict_gain(3, 3, 4, 9) is False
    assert adapter.delta7_of(3, 3, 3, 0, 0, 0, 0, 9) == 0
    incomplete = adapter.pair_tail_decision(5, 5, 0, 0, 10, None)
    assert incomplete["safe_exclusion"] is False
    assert incomplete["reason"] == "INCOMPLETE_TAIL"
    unsafe = adapter.pair_tail_decision(5, 5, 0, 0, 10, [0, 6])
    assert unsafe["safe_exclusion"] is False
    assert unsafe["reason"] == "M_BELOW_PROVEN_CAP"
    safe = adapter.pair_tail_decision(5, 5, 0, 6, 16, [0, 6])
    assert safe["safe_exclusion"] is True
    assert safe["bound"] == 16


def test_toy_enumeration_matches_inclusion_exclusion() -> None:
    tickets = (
        {"id": "a", "r": 9, "original_removed": True},
        {"id": "b", "r": 5, "original_removed": False},
        {"id": "c", "r": 5, "original_removed": False},
        {"id": "d", "r": 5, "original_removed": False},
        {"id": "e", "r": 1, "original_removed": False},
    )
    names = [ticket["id"] for ticket in tickets]
    overlaps = {tuple(sorted(pair)): 0 for pair in itertools.combinations(names, 2)}
    triples = {tuple(sorted(triple)): 0 for triple in itertools.combinations(names, 3)}
    classified = adapter.classify_toy_domain(tickets, 12, overlaps, triples)
    by_id = {ticket["id"]: int(ticket["r"]) for ticket in tickets}
    removed = {ticket["id"] for ticket in tickets if ticket["original_removed"]}
    positives = []
    for triple in itertools.combinations([ticket["id"] for ticket in tickets], 3):
        if removed.intersection(triple):
            continue
        delta7 = adapter.delta7_of(
            by_id[triple[0]],
            by_id[triple[1]],
            by_id[triple[2]],
            overlaps[tuple(sorted(triple[:2]))],
            overlaps[tuple(sorted((triple[0], triple[2])))],
            overlaps[tuple(sorted(triple[1:]))],
            triples[tuple(sorted(triple))],
            12,
        )
        if delta7 > 0:
            positives.append(list(triple))
            assert list(triple) not in [row.get("triple") for row in classified["certificates"]]
    assert positives
    assert classified["positive"] == positives
    assert classified["buckets"]["PROVEN_BOUND_PRUNED"] > 0
    assert sum(classified["buckets"].values()) == comb(len(tickets), 3)
    timed = adapter.classify_toy_domain(tickets, 12, overlaps, triples, exact_budget=0)
    assert timed["buckets"]["UNRESOLVED_FRONTIER"] > 0
    assert timed["status_if_no_recount"] == "INCOMPLETE_FRONTIER_OPEN"


def test_timeout_and_checkpoint_are_not_closure() -> None:
    kept = adapter.remainder_tickets(ROOT)
    accounted = adapter.account_kernel(_timeout_summary(), certificate_ok=True, kept=kept)
    assert accounted["buckets"]["UNRESOLVED_FRONTIER"] > 0
    assert accounted["first_unfinished_frontier"]
    status = adapter.status_from_accounting(
        accounted["buckets"],
        stop_reason="TIME_LIMIT",
        verified_gain=False,
    )
    assert status == "INCOMPLETE_FRONTIER_OPEN"
    assert status != "EXHAUSTIVE_NO_GAIN_CLOSED"


def test_novelty_bijection_counts_are_computed_not_copied() -> None:
    report = adapter.novelty_report(ROOT)
    kept = adapter.remainder_tickets(ROOT)
    assert adapter.sha256_text(kept) != report["SEALED_121314_REMAINDER_SHA256"]
    assert report["REMAINDER_SHA_DIFFERS_FROM_SEALED_121314"] is True
    assert report["SEALED_121314_ISOMORPHIC"] is False
    triples = [tuple(slots) for slots in report["C2_EQUIVALENT_SLOT_TRIPLES"]]
    assert report["EQUIVALENT_C2_CASES"] == len(triples)
    assert report["EQUIVALENT_C2_CASES"] == len(set(triples))
    assert tuple(adapter.DESTROY_SLOTS) in triples
    assert adapter.SEALED_121314_SLOTS not in triples
    assert report["C2_AUTOMORPHISM_GROUP_ORDER"] > 1
    if report["C4_STATUS"] == "COMPUTED_FROM_LOCAL_C4_PORTFOLIO":
        assert isinstance(report["EQUIVALENT_C4_CASES"], int)
        assert isinstance(report["C4_DEGREE_MATCHES"], int)
        assert report["REMAINDER_CLASS_MAPPING_STATUS"] == (
            "COMPUTED_49_NUMBER_AND_17_TICKET_BIJECTION"
        )
    else:
        assert report["EQUIVALENT_C4_CASES"] is None
        assert report["REMAINDER_CLASS_MAPPING_STATUS"] == "C2_COMPUTED_C4_UNVERIFIED"
    assert report["PILOT_64_STATUS"] == "ABSENT_NO_LOCAL_64_CASE_N3_PILOT"
    assert report["PRIOR_CLOSURE_NOVELTY_STATUS"]
    assert all(not row["same_remainder"] for row in report["COMPARED_FULL_N3_CLOSURES"])


def test_positive_claim_is_accepted_only_by_pinned_recount() -> None:
    ordered = adapter.ordered_tickets(ROOT)
    kept = adapter.remainder_tickets(ROOT)
    removed = [list(ticket) for ticket in adapter.REMOVED_TICKETS]
    claimed = adapter.accept_verified_gain(ordered, kept, removed, 1, ROOT)
    assert claimed["accepted"] is False
    assert claimed["recount"]["evaluator_sha256"] == adapter.EVALUATOR_SHA256
    assert claimed["recount"]["count"] == adapter.START_COUNT
    assert claimed["canonical_delta"] == 0
    illegal = adapter.accept_verified_gain(ordered, kept, [kept[0], kept[0], kept[1]], 1, ROOT)
    assert illegal["accepted"] is False
    assert illegal["recount"] is None
    assert adapter.decision_from_recount(
        count=adapter.START_COUNT + 14,
        delta7=2,
        structural_ok=True,
        evaluator_sha256=adapter.EVALUATOR_SHA256,
    )
    assert not adapter.decision_from_recount(
        count=adapter.START_COUNT + 14,
        delta7=2,
        structural_ok=True,
        evaluator_sha256="0" * 64,
    )


def test_listed_gain_stays_exact_and_does_not_close_the_domain() -> None:
    kept = adapter.remainder_tickets(ROOT)
    summary = _timeout_summary()
    summary["improved"] = True
    summary["best_f"] = int(summary["f0"]) + 2
    summary["tie_count"] = 4
    summary["ties_stored"] = 1
    summary["ties"] = [_fresh_triple(kept)]
    accounted = adapter.account_kernel(summary, certificate_ok=True, kept=kept)
    assert accounted["listed_gain"] == summary["ties"][0]
    assert accounted["buckets"]["EXACT_EVALUATED"] == 1
    assert accounted["buckets"]["UNRESOLVED_FRONTIER"] > 0
    status = adapter.status_from_accounting(
        accounted["buckets"],
        stop_reason="TIME_LIMIT",
        verified_gain=False,
        positive_exact=True,
    )
    assert status == "INCOMPLETE_FRONTIER_OPEN"


def test_truncated_tie_json_keeps_one_triple_and_the_kernel_count(tmp_path: Path) -> None:
    triple = "[[1,2,3,4,5,6],[1,2,3,4,5,7],[1,2,3,4,5,8]]"
    other = "[[1,2,3,4,5,9],[1,2,3,4,5,10],[1,2,3,4,5,11]]"
    body = (
        '{"SOLVER":{"RAN":true,"TIES_STORED":2,"OPTIMAL_TRIPLE_COUNT":2,'
        f'"TIES":[{triple},{other}],"ANCHORS_COMPLETED":1}}}}'
    ).replace("1}}}}", "1}}")
    path = tmp_path / "kernel-result.json"
    path.write_text(body, encoding="utf-8")
    loaded = adapter._load_kernel_document(path, truncate_after=10)
    assert loaded["SOLVER"]["TIES_STORED"] == 2
    assert loaded["SOLVER"]["TIES"] == [
        [[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 7], [1, 2, 3, 4, 5, 8]]
    ]


def test_kernel_blob_accepts_kept_and_removed_and_memory_is_not_an_os_cap() -> None:
    source = subprocess.check_output(
        ["git", "show", f"{adapter.KERNEL_COMMIT}:src/lottolab/research/b649_n3_exact/n3_main.c"],
        cwd=ROOT,
        text=True,
    )
    assert adapter.kernel_interface_accepts_kept_removed(source)
    memory = adapter.memory_limit_capability()
    assert memory["OS_HARD_LIMIT_AVAILABLE"] is False
    assert memory["MONITOR_IS_OS_HARD_CAP"] is False
    assert memory["MONITOR_STOP_LOSS_BYTES"] == 2 * 1024 * 1024 * 1024
    assert adapter.heavy_slot_blocked(["999 n3-exact --kept 1"], False) is True
    own = str(os.getpid())
    padded = f"  {own} /usr/bin/python -m lottolab.research.b649_c2_n3_121315_full_domain_r1 solve"
    assert adapter.heavy_slot_blocked([padded], False) is False
    foreign = "  999 /usr/bin/python -m lottolab.research.b649_c2_n3_121315_full_domain_r1 solve"
    assert adapter.heavy_slot_blocked([foreign], False) is True
    shell = "  999 /bin/zsh -c python -m lottolab.research.b649_c2_n3_121315_full_domain_r1 solve"
    assert adapter.heavy_slot_blocked([shell], False) is False


def _fresh_triple(kept: list[list[int]]) -> list[list[int]]:
    used = {tuple(ticket) for ticket in kept}
    used.update(adapter.REMOVED_TICKETS)
    found: list[list[int]] = []
    for extra in range(6, 49):
        ticket = (1, 2, 3, 4, 5, extra)
        if ticket in used or len(set(ticket)) != 6:
            continue
        found.append(list(ticket))
        if len(found) == 3:
            return found
    raise AssertionError("could not build a fresh triple")


def _base_summary() -> dict[str, object]:
    f0 = 1000
    usize = f0 + (adapter.C49_7 - adapter.START_COVERAGE_7SET)
    return {
        "ran": True,
        "closed": False,
        "stop_reason": "TIME_LIMIT",
        "improved": False,
        "f0": f0,
        "f0_ie": f0,
        "best_f": f0,
        "rho": 400,
        "rmin": 200,
        "prefix_l": adapter.C49_6 - 27,
        "removed_r": [500, 500, 500],
        "usize": usize,
        "identities_ok": True,
        "accounted": 10,
        "total": comb(adapter.C49_6, 3),
        "open_upper_bound": 1500,
        "tie_count": 0,
        "ties_stored": 0,
        "ties": [],
        "a_last": 3,
        "prune_audit_failures": 0,
        "leaf_audit_failures": 0,
    }


def _timeout_summary() -> dict[str, object]:
    return _base_summary()


def _closed_summary() -> dict[str, object]:
    summary = _base_summary()
    summary["closed"] = True
    summary["stop_reason"] = "CLOSED"
    summary["accounted"] = comb(adapter.C49_6, 3)
    return summary
