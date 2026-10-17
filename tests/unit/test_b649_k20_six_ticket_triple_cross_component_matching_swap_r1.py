"""Focused unit tests for B649_K20_SIX_TICKET_TRIPLE_CROSS_COMPONENT_MATCHING_SWAP_R1."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest

from lottolab.research.b649_k20_six_ticket_triple_cross_component_matching_swap_r1 import (
    ALL49,
    BASELINE_EXACT_COUNT,
    BASELINE_GIT_BLOB,
    BASELINE_PORTFOLIO_SHA256,
    CANONICAL_BASELINE_TICKETS,
    EXPECTED_CANONICAL_KEYS,
    EXPECTED_CANONICAL_KEYS_SHA256,
    EXPECTED_FIRST_LAYER_KEYS,
    EXPECTED_FIXTURE_EVENTS,
    EXPECTED_FIXTURE_FORWARD_DELTA,
    EXPECTED_FIXTURE_FORWARD_GAIN,
    EXPECTED_FIXTURE_FORWARD_LOSS,
    EXPECTED_FIXTURE_FORWARD_NEW,
    EXPECTED_FIXTURE_FORWARD_OLD,
    EXPECTED_FIXTURE_IDENTITY_DELTA,
    EXPECTED_FIXTURE_IDENTITY_NEW,
    EXPECTED_FIXTURE_IDENTITY_OLD,
    EXPECTED_FIXTURE_REVERSE_DELTA,
    EXPECTED_FIXTURE_REVERSE_GAIN,
    EXPECTED_FIXTURE_REVERSE_LOSS,
    EXPECTED_FIXTURE_REVERSE_NEW,
    EXPECTED_FIXTURE_REVERSE_OLD,
    EXPECTED_H_FIXED_POINTS,
    EXPECTED_H_SUPPORT_TRIPLES,
    EXPECTED_ORDERED_GENERATOR_OUTPUT_SHA256,
    H_NUMBER_MAP,
    H_POSITION_MAP,
    INDEPENDENT_ORACLE_SHA256,
    L_ENDPOINTS,
    L_NUMBERS,
    OFFICIAL_EVALUATOR_SHA256,
    PINNED_SOURCE_HEAD,
    PINNED_SOURCE_TREE,
    CanonicalGenerator,
    SixTicketBaselineCache,
    SixTicketSwapError,
    build_journal_identity,
    build_subset_union_lookup,
    canonical,
    compute_six_ticket_slice_delta,
    compute_ticket_set_coverage_mask,
    legal_exchange,
    load_independent_seven_set_oracle,
    load_or_init_journal,
    mask_to_ticket,
    portfolio_wins_oracle,
    run_128_fixture_validation,
    ticket_to_mask,
    transform,
    validate_cache_identity,
    validate_generator_and_candidates,
    verify_source_identity,
    write_json_durably,
)

REPO_ROOT = Path("/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis")
WORKTREE_ROOT = Path(__file__).resolve().parents[2]


def test_ac1_source_identity_and_independent_oracle_sha256() -> None:
    report = verify_source_identity(REPO_ROOT, WORKTREE_ROOT)
    assert report.actual_head == PINNED_SOURCE_HEAD
    assert report.actual_tree == PINNED_SOURCE_TREE
    assert report.baseline_git_blob == BASELINE_GIT_BLOB
    assert report.baseline_sha256 == BASELINE_PORTFOLIO_SHA256
    assert report.evaluator_sha256 == OFFICIAL_EVALUATOR_SHA256
    assert Path(report.evaluator_file_path) == Path(report.evaluator_imported_path)

    oracle_mod, oracle_path, oracle_sha = load_independent_seven_set_oracle(REPO_ROOT)
    assert oracle_path.is_file()
    assert oracle_sha == INDEPENDENT_ORACLE_SHA256
    assert hasattr(oracle_mod, "outcome_count")
    assert hasattr(oracle_mod, "covered_subset_count")


def test_ac2_h_support_map_and_40_disjoint_triples() -> None:
    gen = CanonicalGenerator(CANONICAL_BASELINE_TICKETS)
    assert set(gen.supports.keys()) == set(range(1, 21))
    for h_num, positions in gen.supports.items():
        assert len(positions) == 3
        assert set(positions).issubset(set(range(12)))
        for pos in positions:
            assert h_num in CANONICAL_BASELINE_TICKETS[pos]

    assert len(gen.support_triples) == EXPECTED_H_SUPPORT_TRIPLES
    for a1, a2, a3 in gen.support_triples:
        assert a1 < a2 < a3
        s1, s2, s3 = set(gen.supports[a1]), set(gen.supports[a2]), set(gen.supports[a3])
        assert s1.isdisjoint(s2)
        assert s1.isdisjoint(s3)
        assert s2.isdisjoint(s3)


def test_ac2_involutions_and_2172_canonical_generator_hashes() -> None:
    for idx in range(12):
        mapped = H_POSITION_MAP[idx]
        assert 0 <= mapped < 12
        assert H_POSITION_MAP[mapped] == idx

    for num in range(1, 27):
        mapped_num = H_NUMBER_MAP.get(num, num)
        assert H_NUMBER_MAP.get(mapped_num, mapped_num) == num

    gen = CanonicalGenerator(CANONICAL_BASELINE_TICKETS)
    raw_keys = tuple(gen.raw_keys())
    assert len(raw_keys) == EXPECTED_FIRST_LAYER_KEYS
    assert len(set(raw_keys)) == EXPECTED_FIRST_LAYER_KEYS

    raw_set = set(raw_keys)
    fixed_points = [k for k in raw_keys if transform(k) == k]
    assert len(fixed_points) == EXPECTED_H_FIXED_POINTS

    for k in raw_keys:
        tk = transform(k)
        assert tk in raw_set
        assert transform(tk) == k
        assert canonical(k) == canonical(tk)

    can_keys = gen.canonical_keys()
    assert len(can_keys) == EXPECTED_CANONICAL_KEYS
    assert len(set(can_keys)) == EXPECTED_CANONICAL_KEYS
    assert list(can_keys) == sorted(can_keys)

    covered: set[object] = set()
    for ck in can_keys:
        covered.add(ck)
        covered.add(transform(ck))
    assert covered == raw_set

    _, specs, summary = validate_generator_and_candidates(CANONICAL_BASELINE_TICKETS)
    assert len(specs) == EXPECTED_CANONICAL_KEYS
    assert summary.h_support_triples == EXPECTED_H_SUPPORT_TRIPLES
    assert summary.raw_first_layer_keys == EXPECTED_FIRST_LAYER_KEYS
    assert summary.h_fixed_points == EXPECTED_H_FIXED_POINTS
    assert summary.canonical_keys == EXPECTED_CANONICAL_KEYS
    assert summary.involution_mismatches == 0
    assert summary.uncovered_keys == 0
    assert summary.duplicate_keys == 0
    assert summary.illegal_candidates == 0
    assert summary.distinct_portfolios == EXPECTED_CANONICAL_KEYS
    assert summary.canonical_keys_sha256 == EXPECTED_CANONICAL_KEYS_SHA256
    assert summary.ordered_generator_output_sha256 == EXPECTED_ORDERED_GENERATOR_OUTPUT_SHA256


def test_ac3_all_2172_candidates_satisfy_structural_invariants() -> None:
    _, specs, _ = validate_generator_and_candidates(CANONICAL_BASELINE_TICKETS)
    assert len(specs) == EXPECTED_CANONICAL_KEYS

    baseline_freq = Counter(n for t in CANONICAL_BASELINE_TICKETS for n in t)
    for spec in specs:
        assert legal_exchange(CANONICAL_BASELINE_TICKETS, spec.key, spec.slot_portfolio)
        assert len(spec.removed_indices) == 6
        assert len(spec.retained_indices) == 14
        assert set(spec.removed_indices).isdisjoint(set(spec.retained_indices))
        cand_freq = Counter(n for t in spec.slot_portfolio for n in t)
        assert cand_freq == baseline_freq


def test_ac3_rejects_illegal_swap_keys_and_illegal_portfolios() -> None:
    gen = CanonicalGenerator(CANONICAL_BASELINE_TICKETS)

    # Non-disjoint H support triple (1, 2, 3) is not in gen.support_triples
    bad_key_support = ((1, 2, 3), (0, 0, 5), (0, 0, 0))
    with pytest.raises(SixTicketSwapError, match="Invalid representative key"):
        gen.portfolio(bad_key_support)

    # H number not present in the specified H ticket for a valid support triple (1, 6, 11)
    bad_key_wrong_membership = ((1, 6, 11), (3, 1, 2), (0, 0, 0))
    with pytest.raises(SixTicketSwapError, match="Invalid representative key"):
        gen.portfolio(bad_key_wrong_membership)

    # First L bit not fixed to 0
    bad_key_e1_nonzero = ((1, 6, 11), (0, 1, 2), (1, 0, 0))
    with pytest.raises(SixTicketSwapError, match="Invalid representative key"):
        gen.portfolio(bad_key_e1_nonzero)

    # Unchanged baseline must fail legal_exchange
    first_key = gen.canonical_keys()[0]
    assert not legal_exchange(CANONICAL_BASELINE_TICKETS, first_key, CANONICAL_BASELINE_TICKETS)
    assert L_NUMBERS == (29, 35, 41)
    assert L_ENDPOINTS == ((12, 15), (13, 16), (14, 17))


def test_ac4_128_fixture_validation_and_oracle_parity() -> None:
    summary = run_128_fixture_validation()
    assert summary.event_count == EXPECTED_FIXTURE_EVENTS
    assert summary.fwd_old == EXPECTED_FIXTURE_FORWARD_OLD
    assert summary.fwd_new == EXPECTED_FIXTURE_FORWARD_NEW
    assert summary.fwd_gain == EXPECTED_FIXTURE_FORWARD_GAIN
    assert summary.fwd_loss == EXPECTED_FIXTURE_FORWARD_LOSS
    assert summary.fwd_delta == EXPECTED_FIXTURE_FORWARD_DELTA
    assert summary.rev_old == EXPECTED_FIXTURE_REVERSE_OLD
    assert summary.rev_new == EXPECTED_FIXTURE_REVERSE_NEW
    assert summary.rev_gain == EXPECTED_FIXTURE_REVERSE_GAIN
    assert summary.rev_loss == EXPECTED_FIXTURE_REVERSE_LOSS
    assert summary.rev_delta == EXPECTED_FIXTURE_REVERSE_DELTA
    assert summary.ident_old == EXPECTED_FIXTURE_IDENTITY_OLD
    assert summary.ident_new == EXPECTED_FIXTURE_IDENTITY_NEW
    assert summary.ident_delta == EXPECTED_FIXTURE_IDENTITY_DELTA
    assert summary.direct_oracle_mismatches == 0


def test_ac4_joint_six_ticket_or_is_not_sum_of_individual_pair_swaps() -> None:
    """Verify 6 added tickets are combined via joint OR and never by adding 3 pair deltas."""
    _, specs, _ = validate_generator_and_candidates(CANONICAL_BASELINE_TICKETS)
    spec = specs[0]
    base_masks = tuple(ticket_to_mask(t) for t in CANONICAL_BASELINE_TICKETS)
    fixed_masks = tuple(base_masks[i] for i in spec.retained_indices)
    added_masks = spec.added_masks

    t_a = mask_to_ticket(added_masks[0])
    t_b = mask_to_ticket(added_masks[3])
    shared_candidates = [
        n for n in range(1, 50) if n not in set(t_a[:2] + t_b[:2])
    ]
    d_draw = tuple(sorted(set(t_a[:2] + t_b[:2])))
    while len(d_draw) < 6:
        for c in shared_candidates:
            if c not in d_draw:
                d_draw = tuple(sorted((*d_draw, c)))
                break
    d_mask = ticket_to_mask(d_draw)
    res = compute_six_ticket_slice_delta(d_mask, fixed_masks, added_masks, base_masks)
    for s in range(1, 50):
        if s in d_draw:
            continue
        s_bit = 1 << (s - 1)
        oracle_old = portfolio_wins_oracle(CANONICAL_BASELINE_TICKETS, d_draw, s)
        oracle_new = portfolio_wins_oracle(spec.slot_portfolio, d_draw, s)
        assert bool(res.baseline_mask & s_bit) == oracle_old
        assert bool((res.fixed_mask | res.added_mask) & s_bit) == oracle_new


def test_ac4_rejects_illegal_numbers_draws_duplicates_and_special_bits() -> None:
    base_masks = tuple(ticket_to_mask(t) for t in CANONICAL_BASELINE_TICKETS)
    fixed_masks = base_masks[:14]
    added_masks = base_masks[14:]
    valid_d = ticket_to_mask((1, 2, 3, 4, 5, 6))

    # Illegal numbers in ticket_to_mask
    with pytest.raises(SixTicketSwapError, match=r"outside legal 1\.\.49 range"):
        ticket_to_mask((0, 2, 3, 4, 5, 6))
    with pytest.raises(SixTicketSwapError, match=r"outside legal 1\.\.49 range"):
        ticket_to_mask((1, 2, 3, 4, 5, 50))
    with pytest.raises(SixTicketSwapError, match="Duplicate"):
        ticket_to_mask((1, 1, 3, 4, 5, 6))
    with pytest.raises(SixTicketSwapError, match=r"outside legal 1\.\.49 range"):
        ticket_to_mask((True, 2, 3, 4, 5, 6))  # type: ignore[arg-type]

    # Illegal D mask (5 bits instead of 6, or bits outside 1..49)
    with pytest.raises(SixTicketSwapError, match="6 main numbers"):
        compute_six_ticket_slice_delta(0b11111, fixed_masks, added_masks, base_masks)
    with pytest.raises(SixTicketSwapError, match="outside legal 49-bit space"):
        compute_six_ticket_slice_delta(
            (1 << 50) | 0b11111, fixed_masks, added_masks, base_masks
        )

    # Duplicate tickets in added_masks or fixed_masks
    dup_added = (added_masks[0], added_masks[0], *added_masks[2:])
    with pytest.raises(SixTicketSwapError, match="6 distinct ticket masks"):
        compute_six_ticket_slice_delta(valid_d, fixed_masks, dup_added, base_masks)

    # Wrong ticket counts
    with pytest.raises(SixTicketSwapError, match="14 distinct ticket masks"):
        compute_six_ticket_slice_delta(valid_d, fixed_masks[:13], added_masks, base_masks)
    with pytest.raises(SixTicketSwapError, match="6 distinct ticket masks"):
        compute_six_ticket_slice_delta(valid_d, fixed_masks, added_masks[:5], base_masks)

    # Special ball mask overlapping D or outside 1..49
    with pytest.raises(SixTicketSwapError, match="overlaps main draw D"):
        compute_six_ticket_slice_delta(
            valid_d, fixed_masks, added_masks, base_masks, active_specials_mask=1
        )
    with pytest.raises(SixTicketSwapError, match=r"outside 1\.\.49"):
        compute_six_ticket_slice_delta(
            valid_d, fixed_masks, added_masks, base_masks, active_specials_mask=(1 << 49)
        )

    # Illegal ticket mask in compute_ticket_set_coverage_mask
    with pytest.raises(SixTicketSwapError, match="Illegal ticket mask"):
        compute_ticket_set_coverage_mask((0b111,), valid_d, ALL49 & ~valid_d)


def test_cache_identity_u_reuse_and_native_vs_numpy_parity() -> None:
    sample_draws = [
        ticket_to_mask(comb)
        for _, comb in zip(range(64), combinations(range(1, 25), 6), strict=False)
    ]
    draws_arr = np.array(sample_draws, dtype=np.uint64)

    cache_native = SixTicketBaselineCache(
        CANONICAL_BASELINE_TICKETS,
        draws=draws_arr,
        use_native_kernel=True,
        expected_baseline_count=None,
    )
    cache_numpy = SixTicketBaselineCache(
        CANONICAL_BASELINE_TICKETS,
        draws=draws_arr,
        use_native_kernel=False,
        expected_baseline_count=None,
    )

    assert cache_native.baseline_full_count == cache_numpy.baseline_full_count
    assert np.array_equal(cache_native.H2, cache_numpy.H2)
    assert np.array_equal(cache_native.H3, cache_numpy.H3)
    assert np.array_equal(cache_native.B, cache_numpy.B)
    assert np.array_equal(cache_native.L, cache_numpy.L)

    # Validate cache identity contract (rejects outcome-count-only or modified identity)
    assert validate_cache_identity(cache_native.identity.to_dict(), cache_native.identity)
    with pytest.raises(SixTicketSwapError, match="missing required keys"):
        validate_cache_identity({"outcome_count": 313263888}, cache_native.identity)
    tampered = cache_native.identity.to_dict()
    tampered["baseline_sha256"] = "0" * 64
    with pytest.raises(SixTicketSwapError, match="mismatch on key"):
        validate_cache_identity(tampered, cache_native.identity)

    # AC6 incomplete slice boundary check: require_full_draw_space=True must reject 64-slice cache
    _, specs, _ = validate_generator_and_candidates(CANONICAL_BASELINE_TICKETS)
    with pytest.raises(SixTicketSwapError, match="AC6 violation"):
        cache_native.score_candidate(
            specs[0].retained_indices,
            specs[0].added_masks,
            retained_bitmask=specs[0].retained_bitmask,
            require_full_draw_space=True,
        )

    # Test U reuse when retained_indices stay identical vs recompute when retained_indices change
    same_retained_spec = next(
        s for s in specs[1:] if s.retained_indices == specs[0].retained_indices
    )
    res0_native = cache_native.score_candidate(
        specs[0].retained_indices,
        specs[0].added_masks,
        retained_bitmask=specs[0].retained_bitmask,
        require_full_draw_space=False,
    )
    assert res0_native.u_reused is False
    res1_native = cache_native.score_candidate(
        same_retained_spec.retained_indices,
        same_retained_spec.added_masks,
        retained_bitmask=same_retained_spec.retained_bitmask,
        require_full_draw_space=False,
    )
    assert res1_native.u_reused is True

    # Find a spec with different retained_indices and verify U is recomputed
    diff_spec = next(s for s in specs if s.retained_indices != specs[0].retained_indices)
    res_diff_native = cache_native.score_candidate(
        diff_spec.retained_indices,
        diff_spec.added_masks,
        retained_bitmask=diff_spec.retained_bitmask,
        require_full_draw_space=False,
    )
    assert res_diff_native.u_reused is False

    # Verify native vs numpy vs direct slice-by-slice oracle parity
    for sp in (specs[0], same_retained_spec, diff_spec):
        r_nat = cache_native.score_candidate(
            sp.retained_indices,
            sp.added_masks,
            retained_bitmask=sp.retained_bitmask,
            require_full_draw_space=False,
        )
        r_num = cache_numpy.score_candidate(
            sp.retained_indices,
            sp.added_masks,
            retained_bitmask=sp.retained_bitmask,
            require_full_draw_space=False,
        )
        assert r_nat.gain == r_num.gain
        assert r_nat.loss == r_num.loss
        assert r_nat.delta == r_num.delta
        assert r_nat.new_count == r_num.new_count

        fixed_masks = tuple(cache_native.ticket_masks[i] for i in sp.retained_indices)
        slice_gain = 0
        slice_loss = 0
        for d_u64 in draws_arr:
            sr = compute_six_ticket_slice_delta(
                int(d_u64), fixed_masks, sp.added_masks, cache_native.ticket_masks
            )
            slice_gain += sr.gain
            slice_loss += sr.loss
        assert r_nat.gain == slice_gain
        assert r_nat.loss == slice_loss


def test_subset_union_lookup_small_and_journal_persistence(tmp_path: Path) -> None:
    small_masks = (0b0011, 0b0101, 0b1000)
    lookup = build_subset_union_lookup(small_masks)
    assert lookup.shape == (8,)
    assert int(lookup[0]) == 0
    assert int(lookup[0b001]) == 0b0011
    assert int(lookup[0b010]) == 0b0101
    assert int(lookup[0b011]) == 0b0111
    assert int(lookup[0b111]) == 0b1111

    draws_arr = np.array([ticket_to_mask((1, 2, 3, 4, 5, 6))], dtype=np.uint64)
    cache = SixTicketBaselineCache(
        CANONICAL_BASELINE_TICKETS,
        draws=draws_arr,
        use_native_kernel=False,
        expected_baseline_count=None,
    )
    j_id = build_journal_identity(
        cache.identity,
        EXPECTED_CANONICAL_KEYS_SHA256,
        EXPECTED_ORDERED_GENERATOR_OUTPUT_SHA256,
    )
    j_path = tmp_path / "journal.json"
    j1 = load_or_init_journal(j_path, j_id)
    assert j1["NEXT_UNTESTED_INDEX"] == 0
    assert j1["CUMULATIVE_CPU_SECONDS"] == 0.0

    # Persist progress and reload — must preserve cumulative CPU/wall and next index
    j1["NEXT_UNTESTED_INDEX"] = 10
    j1["CANDIDATES_PROCESSED"] = 10
    j1["CANDIDATES_EXACT_SCORED"] = 10
    j1["CUMULATIVE_CPU_SECONDS"] = 12.5
    j1["CUMULATIVE_WALL_SECONDS"] = 13.25
    write_json_durably(j_path, j1)

    j2 = load_or_init_journal(j_path, j_id)
    assert j2["NEXT_UNTESTED_INDEX"] == 10
    assert j2["CUMULATIVE_CPU_SECONDS"] == 12.5
    assert j2["CUMULATIVE_WALL_SECONDS"] == 13.25

    # Reject mismatched journal identity
    bad_id = dict(j_id)
    bad_id["generator_keys_sha256"] = "f" * 64
    with pytest.raises(SixTicketSwapError, match="identity mismatch"):
        load_or_init_journal(j_path, bad_id)
    assert BASELINE_EXACT_COUNT == 313263888
