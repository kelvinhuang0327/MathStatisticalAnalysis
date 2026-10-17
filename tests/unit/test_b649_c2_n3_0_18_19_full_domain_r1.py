"""Only the new task boundary, clock, accounting and independent recount."""

import itertools
import subprocess
from math import comb

import pytest

from lottolab.research import b649_c2_n3_0_18_19_full_domain_r1 as task


def test_pinned_sources_destroy_domain_and_archived_certificate():
    report = task.verify_sources()
    kept = task.donor.remainder_tickets(task.ROOT)
    assert (
        report["C2_ORDERED_SHA256"]
        == "6a537ea56c2741e1208dbbb4abf1064bc74508f2d356712920d348d11e3a4a24"
    )
    assert (
        report["REMAINDER_SHA256"]
        == "e27578baabb0b6dac6c4b7ae79fa1ae386384ae5a4794a2586d6c36842ed4e81"
    )
    assert task.donor.DESTROY_SLOTS == (0, 18, 19)
    assert len(kept) == len(set(map(tuple, kept))) == 17
    assert set().union(*map(set, kept)) == set(range(1, 50))
    support = [sum(n in t for t in kept) for n in range(1, 50)]
    assert [support.count(i) for i in range(4)] == [0, 13, 19, 17]
    d = report["DOMAINS"]
    assert d["RAW_LEGAL_N3_DOMAIN"] == comb(comb(49, 6) - 17, 3) == 455747374158108530299
    assert d["N1_N2_CLOSED_CANDIDATES"] == 293319846830119
    assert d["FRESH_CANDIDATES"] == 455747080838261700180
    assert d["RAW_LEGAL_N3_DOMAIN"] > 2**64
    assert report["N1_N2_CERTIFICATE"]["applies"]


def clock():
    return {
        "original_start_epoch": task.ORIGINAL_START,
        "total_budget_seconds": 86400,
        "absolute_deadline_epoch": task.ORIGINAL_START + 86400,
        "solver_deadline_epoch": task.ORIGINAL_START + 82800,
    }


def test_clock_preserves_elapsed_blocked_time_and_rejects_extension():
    c = clock()
    assert task.remaining(c, task.ORIGINAL_START + 7200) == 75600
    assert task.remaining(c, task.ORIGINAL_START + 82801) == 0
    c["absolute_deadline_epoch"] += 1
    with pytest.raises(RuntimeError, match="absolute deadline changed"):
        task.remaining(c, task.ORIGINAL_START)


def test_unresolved_never_becomes_closure_or_duplicate_kernel_accounting():
    a = task.donor.account_kernel(
        None, certificate_ok=True, kept=task.donor.remainder_tickets(task.ROOT)
    )
    assert sum(a["buckets"].values()) == task.donor.RAW_LEGAL_N3_DOMAIN
    assert a["buckets"]["UNRESOLVED_FRONTIER"] == task.donor.FRESH_CANDIDATES
    assert a["buckets"]["EXACT_EVALUATED"] == a["buckets"]["PROVEN_BOUND_PRUNED"] == 0
    assert task.result_status(a, 0, True, False, "TIME_LIMIT") == "INCOMPLETE_FRONTIER_OPEN"
    assert (
        task.result_status(a, -15, False, False, "ABSOLUTE_SOLVER_DEADLINE")
        == "INCOMPLETE_FRONTIER_OPEN"
    )
    assert task.result_status(a, 1, True, False, "CLOSED") == "EXECUTION_ERROR"


def test_ie_triple_overlap_and_tail_bound_toy_parity():
    d = task.donor
    assert d.delta7_of(5, 5, 5, 3, 3, 3, 2, 7) == 1
    assert d.canonical_outcome_delta(1) == 7
    tickets = [
        {"id": str(i), "r": r, "original_removed": i == 0} for i, r in enumerate([8, 5, 4, 3, 1])
    ]
    ids = [t["id"] for t in tickets]
    pairs = {tuple(p): 0 for p in itertools.combinations(ids, 2)}
    triples = {tuple(t): 0 for t in itertools.combinations(ids, 3)}
    result = d.classify_toy_domain(tickets, 8, pairs, triples)
    positives = [
        list(t)
        for t in itertools.combinations(ids[1:], 3)
        if sum(tickets[int(i)]["r"] for i in t) > 8
    ]
    assert result["positive"] == positives
    assert sum(result["buckets"].values()) == comb(5, 3)
    assert not d.pair_tail_decision(5, 5, 0, 1, 12, [1, 4])["safe_exclusion"]
    assert not d.pair_tail_decision(5, 5, 0, 1, 12, None)["safe_exclusion"]


def test_gain_gate_requires_both_exact_counts_and_legal_twenty():
    kept = task.donor.remainder_tickets(task.ROOT)
    removed = list(task.donor.REMOVED_TICKETS)
    p = task.donor.ordered_tickets(task.ROOT)
    assert task.accept_gain(p, kept, removed, 1, 313263895, 44751985)
    assert not task.accept_gain(p, kept, removed, 1, 313263895, 44751984)
    assert not task.accept_gain(p, kept, removed, 1, 313263888, 44751984)
    assert not task.accept_gain(p, kept, [kept[0]] * 3, 1, 313263895, 44751985)


def test_direct_science_entry_rejected(monkeypatch):
    for key in list(task.os.environ):
        if key.startswith("FABLE_"):
            monkeypatch.delenv(key)
    with pytest.raises(RuntimeError, match="protected heavy lease scope"):
        task.inherited_protection()


def test_independent_recount_on_complete_small_outcome_space(tmp_path):
    source = task.ROOT / "src/lottolab/research/b649_c2_n3_0_18_19_recount.c"
    binary = tmp_path / "recount"
    subprocess.run(["clang", "-std=c11", "-O3", str(source), "-o", str(binary)], check=True)
    tickets = [(1, 2, 3, 4, 5, 6), (3, 6, 8, 9, 11, 12)]
    masks = [sum(1 << (n - 1) for n in t) for t in tickets]
    result = subprocess.run(
        [str(binary), "12", *map(str, masks)], capture_output=True, text=True, check=True
    )
    expected = sum(
        any(len(set(s) & set(t)) >= 3 for t in tickets)
        for s in itertools.combinations(range(1, 13), 7)
    )
    from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio

    canonical = evaluate_portfolio(tickets, pool_size=12, draw_size=6)
    assert int(result.stdout) == expected
    assert expected * 7 == canonical.official_any_prize_outcome_count
    invalid = subprocess.run([str(binary), "12", "3"], capture_output=True)
    assert invalid.returncode == 2


def test_journal_hash_chain_and_closure_require_contiguous_complete_anchors(tmp_path):
    path = tmp_path / "anchors.jsonl"
    body = (
        "N3RESUME1|DESTROY_SET=test|TOTAL_ANCHORS=1|F0=7|INPUT_SHA256="
        + "0" * 64
        + "|ENGINE_SHA256="
        + task.KERNEL_SHA
        + "|SOLVER_CONFIG_SHA256="
        + "0" * 64
    ).encode()
    prefix = task.digest(body)
    header = body + b"|JOURNAL_PREFIX_SHA256=" + prefix.encode() + b"\n"
    path.write_bytes(header)
    doc = {
        "INCUMBENT": {"F0_DIRECT": 7},
        "SOLVER": {
            "CHECKPOINT_ANCHORS_RECORDED": 0,
            "JOURNAL_PREFIX_SHA256": prefix,
            "CLOSED": True,
        },
    }
    with pytest.raises(RuntimeError, match="missing anchors"):
        task.validate_journal(path, doc)
    record = b"A|0|C|7|-|0|0|123|-"
    next_hash = task.digest(prefix.encode() + b"\n" + record)
    path.write_bytes(header + record + b"|" + next_hash.encode() + b"\n")
    doc["SOLVER"]["CHECKPOINT_ANCHORS_RECORDED"] = 1
    doc["SOLVER"]["JOURNAL_PREFIX_SHA256"] = next_hash
    assert task.validate_journal(path, doc)["status"] == "PASS"
    path.write_bytes(path.read_bytes().replace(b"|123|", b"|124|"))
    with pytest.raises(RuntimeError, match="chain mismatch"):
        task.validate_journal(path, doc)
