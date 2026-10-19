from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

from lottolab.research import b649_k20_hhl_full_family_certificate_r1 as cert
from lottolab.research import b649_official_any_prize_exact as official

CHECKOUT = Path(cert.__file__).resolve().parents[3]


def _random_portfolio(rng: np.random.Generator, tickets: int, pool: int) -> list[list[int]]:
    return [
        sorted(int(n) for n in rng.choice(pool, size=6, replace=False) + 1) for _ in range(tickets)
    ]


def _identity() -> list[int]:
    return list(range(1, cert.POOL_SIZE + 1))


def _swap(first: int, second: int) -> list[int]:
    row = _identity()
    row[first - 1], row[second - 1] = second, first
    return row


def test_vectorized_relabelling_matches_reference() -> None:
    rng = np.random.default_rng(20261019)
    portfolios = [_random_portfolio(rng, 20, cert.POOL_SIZE) for _ in range(64)]
    perms = np.array([rng.permutation(cert.POOL_SIZE) + 1 for _ in range(5)], dtype=np.int64)
    masks = np.array([[cert.ticket_mask(t) for t in p] for p in portfolios], dtype=np.uint64)
    which = rng.integers(0, len(perms), size=len(portfolios)).astype(np.int64)
    image = cert.apply_permutations(masks, cert.permutation_tables(perms), which)
    for row, portfolio in enumerate(portfolios):
        expected = cert.relabel(portfolio, perms[which[row]].tolist())
        assert cert.normalize_portfolio([cert.mask_numbers(int(m)) for m in image[row]]) == expected


def test_official_count_is_invariant_under_number_relabelling() -> None:
    # The certificate's carrying premise, exercised on the pinned evaluator itself.
    rng = np.random.default_rng(7)
    pool = 14
    draws = official.all_main_draw_masks(pool, 6)
    distinct: set[int] = set()
    for _ in range(12):
        portfolio = _random_portfolio(rng, 4, pool)
        perm = (rng.permutation(pool) + 1).tolist()
        relabelled = [[perm[n - 1] for n in ticket] for ticket in portfolio]
        before = official.evaluate_portfolio(portfolio, pool_size=pool, draws=draws)
        after = official.evaluate_portfolio(relabelled, pool_size=pool, draws=draws)
        assert after == before
        distinct.add(before.official_any_prize_outcome_count)
    assert len(distinct) > 1  # the portfolios genuinely differ, so equality is not vacuous


def _toy_cover() -> tuple[cert.MaskMatrix, cert.IntArray, dict[int, cert.Anchor]]:
    first = [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]]
    swapped = [[13, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]]
    other = [[1, 2, 3, 4, 5, 6], [6, 8, 9, 10, 11, 12]]
    masks = np.array(
        [[cert.ticket_mask(t) for t in p] for p in (first, swapped, other)], dtype=np.uint64
    )
    perms = np.array([_identity(), _swap(1, 13)], dtype=np.int64)
    anchors = {0: cert.Anchor(0, 100, 0, 100, 0), 2: cert.Anchor(2, 50, 0, 50, 2)}
    return masks, perms, anchors


def test_cover_accepts_explicit_maps_and_rejects_every_broken_one() -> None:
    masks, perms, anchors = _toy_cover()
    rep = np.array([0, 0, 2], dtype=np.int64)
    perm = np.array([0, 1, 0], dtype=np.int64)
    counts, stats = cert.verify_cover(masks, perms, rep, perm, anchors)
    assert counts.tolist() == [100, 100, 50]
    assert stats["MAPS_TO_ANOTHER_PORTFOLIO"] == 1

    cases = {
        "wrong permutation": (rep, np.array([0, 0, 0], dtype=np.int64), anchors),
        "wrong representative": (np.array([0, 2, 2], dtype=np.int64), perm, anchors),
        "unanchored representative": (rep, perm, {0: anchors[0]}),
        "anchor conflict": (rep, perm, {**anchors, 1: cert.Anchor(1, 99, 0, 99, 0)}),
    }
    for name, (case_rep, case_perm, case_anchors) in cases.items():
        with pytest.raises(ValueError):
            cert.verify_cover(masks, perms, case_rep, case_perm, case_anchors)
            pytest.fail(name)

    collapsing = perms.copy()
    collapsing[1, 0] = 2  # numbers 1 and 2 both map to 2: not a bijection
    with pytest.raises(ValueError, match="bijection"):
        cert.verify_cover(masks, collapsing, rep, perm, anchors)


def test_baseline_automorphism_group_has_order_288_and_fixes_baseline() -> None:
    assert len(cert.block_automorphisms(cert.BASELINE_TICKETS, cert.H_INDICES)) == 2
    assert len(cert.block_automorphisms(cert.BASELINE_TICKETS, cert.L_INDICES)) == 144
    perms = cert.baseline_automorphisms(cert.BASELINE_TICKETS)
    assert perms.shape == (288, cert.POOL_SIZE)
    assert perms[0].tolist() == _identity()
    assert len({tuple(row) for row in perms.tolist()}) == 288


def test_move_rules_reject_each_structure_failure() -> None:
    base = [cert.ticket_mask(t) for t in cert.BASELINE_TICKETS]

    def moved(changes: dict[int, list[int]]) -> list[int]:
        masks = list(base)
        for index, ticket in changes.items():
            masks[index] = cert.ticket_mask(ticket)
        return masks

    # Seed of the family's first key [0,1,12,2,22,27,0,...]: 22->T0, 27->T1, 2->T12.
    triple = (0, 1, 12)
    t0, t1, t12 = ([1, 3, 4, 5, 21, 22], [1, 6, 7, 8, 9, 27], [2, 29, 30, 31, 32, 33])
    assert cert.move_violation(base, moved({0: t0, 1: t1, 12: t12}), triple) is None
    assert cert.move_violation(base, moved({0: t0, 1: t1}), triple) == (
        "CHANGED_TICKETS_NOT_EXACTLY_THREE"
    )
    assert cert.move_violation(base, moved({0: [1, 3, 4, 5, 21], 1: t1, 12: t12}), triple) == (
        "TICKET_NOT_SIX_DISTINCT_LEGAL_NUMBERS"
    )
    duplicate = list(cert.BASELINE_TICKETS[2])
    assert cert.move_violation(base, moved({0: duplicate, 1: t1, 12: t12}), triple) == (
        "DUPLICATE_TICKET"
    )
    assert cert.move_violation(base, moved({0: [1, 3, 4, 5, 6, 21], 1: t1, 12: t12}), triple) == (
        "PAIR_OVERLAP_ABOVE_ONE"
    )


def test_anchor_parsing_rejects_bad_accounting_and_order() -> None:
    def section(rows: list[list[int]]) -> dict[str, Any]:
        columns = list(cert.ANCHOR_COLUMNS)
        return {"COLUMNS": columns, "ROWS": rows, "ROWS_SHA256": cert.compact_json_sha256(rows)}

    assert sorted(cert.parse_anchors(section([[0, 43 * 2 + 5, 2, 5, 0], [3, 43, 1, 0, 2]]), 4)) == [
        0,
        3,
    ]
    for rows in (
        [[0, 43 * 2 + 4, 2, 5, 0]],
        [[3, 43, 1, 0, 2], [0, 43, 1, 0, 0]],
        [[4, 43, 1, 0, 0]],
    ):
        with pytest.raises(ValueError):
            cert.parse_anchors(section(rows), 4)


def test_regenerated_family_matches_pinned_producer_and_best_portfolios() -> None:
    family, digests, record = cert.checked_family(cert.load_baseline(CHECKOUT))
    assert record["ORDERED_KEYS_SHA256"] == cert.EXPECTED_FAMILY_STATS["ORDERED_KEYS_SHA256"]
    assert record["FULL_STRUCTURE_RECHECK"] == {"OK": 112_728}
    index_of = {key: index for index, key in enumerate(family.keys)}
    # Producer-reported best portfolios of the random and guided samples.
    old_best = index_of[(9, 10, 15, 15, 23, 44, 0, 5, 21)]
    new_best = index_of[(9, 10, 16, 15, 23, 46, 0, 5, 21)]
    assert (old_best, new_best) == (107_799, 108_046)
    assert digests[old_best] == "fef0c12f2b084c31ccee2bf63291b599aad130e8fc065710864a6caf015b958c"
    assert digests[new_best] == "c2c0abcc715c4ea9d7613d8609e89d8b223eb4fa5767ca7332c2104a2609d9ac"


def test_committed_certificate_header_and_claims() -> None:
    path = CHECKOUT / cert.CERTIFICATE_RELATIVE_PATH
    certificate = cast(dict[str, Any], json.loads(gzip.decompress(path.read_bytes())))
    cert.require_header(certificate, CHECKOUT)
    claims = cast(dict[str, Any], certificate["CLAIMS"])
    assert claims["FAMILY_PORTFOLIOS"] == 112_728
    assert claims["UNRESOLVED_PORTFOLIOS"] == 0
    assert claims["FAMILY_MAXIMUM_EXACT_COUNT"] == cert.EXPECTED_FAMILY_MAXIMUM
    assert claims["FAMILY_MAXIMUM_DELTA"] == -231_105
    assert claims["STRICT_GAIN_COUNT"] == 0
    assert certificate["SCIENTIFIC_AUTHORITY"] == "PENDING_FRESH_JUDGE"
    cover = cast(dict[str, Any], certificate["COVER"])
    assert len(cover["REPRESENTATIVE_FAMILY_INDEX"]) == len(cover["PERMUTATION_INDEX"]) == 112_728
