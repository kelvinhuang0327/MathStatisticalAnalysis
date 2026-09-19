"""Outcome-free characterization of the B649 three-arm k-DPP portfolio adapter.

Every fixture is a synthetic strategy ticket set or a synthetic causal source
identity; no draw outcome, winning number, or historical result is read.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import Literal, cast

import numpy as np
import pytest

from lottolab.application import b649_k_dpp_portfolio_selector as adapter
from lottolab.application import b649_operational_portfolio_selector as operational
from lottolab.application.b649_k_dpp_portfolio_selector import (
    ALLOWED_K,
    EXPECTED_NUMPY_VERSION,
    HISTORICAL_CAUSAL_REPLAY_V1,
    HISTORY_FINGERPRINT,
    HISTORY_IDENTITY_KIND_BY_SOURCE_MODE,
    HISTORY_SHA256,
    KDPP_METHOD_ID,
    KDPP_METHOD_VERSION,
    LIVE_PREDRAW_V1,
    RANDOM_K_METHOD_ID,
    RANDOM_K_METHOD_VERSION,
    RAW_MAJORITY_METHOD_ID,
    RAW_MAJORITY_METHOD_VERSION,
    REPRODUCIBILITY_CLAIM,
    ArmSelection,
    CandidatePool,
    CausalSourceIdentity,
    build_kdpp_candidate_pool,
    build_kdpp_kernel,
    derive_arm_seed,
    select_kdpp,
    select_raw_majority_top_k,
    select_seeded_random_k,
    ticket_similarity_matrix,
)
from lottolab.application.b649_operational_portfolio_selector import (
    CandidatePoolEntry,
    StrategyCandidate,
    Ticket,
    build_candidate_pool,
    build_portfolio,
)
from lottolab.evidence import canonical_json
from lottolab.evidence.canonical_json import canonical_bytes, canonical_file_bytes, sha256_hex
from lottolab.infrastructure import b649_operational_portfolio_materializer as materializer
from lottolab.research import k_dpp_ticket_portfolio
from lottolab.research.k_dpp_ticket_portfolio import select_k_dpp

_HISTORY_DIGEST = hashlib.sha256(b"synthetic outcome-free causal history").hexdigest()
_OUTCOME_TOKENS = (
    "outcome",
    "result",
    "winning",
    "prize",
    "hit",
    "score",
    "success",
    "actual",
    "main_numbers",
    "special_number",
)
_ARM_SELECTORS: tuple[Callable[..., ArmSelection], ...] = (
    select_raw_majority_top_k,
    select_seeded_random_k,
    select_kdpp,
)
_SEEDED_ARMS: tuple[tuple[Literal["SEEDED_RANDOM_K", "KDPP"], str, str], ...] = (
    ("KDPP", KDPP_METHOD_ID, KDPP_METHOD_VERSION),
    ("SEEDED_RANDOM_K", RANDOM_K_METHOD_ID, RANDOM_K_METHOD_VERSION),
)


def _source(mode: str = LIVE_PREDRAW_V1, **overrides: str) -> CausalSourceIdentity:
    fields = {
        "source_mode": mode,
        "target_draw_number": "990000002",
        "target_draw_date": "2099-01-09",
        "history_cutoff_draw_number": "990000001",
        "history_cutoff_date": "2099-01-06",
        "history_identity_kind": HISTORY_IDENTITY_KIND_BY_SOURCE_MODE[mode],
        "history_identity": _HISTORY_DIGEST,
    }
    fields.update(overrides)
    return CausalSourceIdentity(**fields)


def _consensus_candidates() -> list[StrategyCandidate]:
    """Six distinct tickets with support 3, 2, 2, 1, 1, 1 (numbers deliberately unsorted)."""

    return [
        StrategyCandidate("s03", [(6, 5, 4, 3, 2, 1), (19, 20, 21, 22, 23, 24)]),
        StrategyCandidate("s01", [(1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12)]),
        StrategyCandidate("s02", [(3, 1, 2, 6, 5, 4), (13, 14, 15, 16, 17, 18)]),
        StrategyCandidate("s04", [(12, 11, 10, 9, 8, 7), (1, 7, 13, 19, 25, 31)]),
        StrategyCandidate("s05", [(2, 8, 14, 20, 26, 32), (31, 25, 19, 13, 7, 1)]),
    ]


_CONSENSUS_ORDER: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5, 6),
    (1, 7, 13, 19, 25, 31),
    (7, 8, 9, 10, 11, 12),
    (2, 8, 14, 20, 26, 32),
    (13, 14, 15, 16, 17, 18),
    (19, 20, 21, 22, 23, 24),
)


def _live_like_candidates(*, shared_ticket: bool = True) -> list[StrategyCandidate]:
    """Eleven strategies x two tickets, shaped like a live pool: almost all support 1."""

    rng = random.Random(20260919)
    tickets: list[Ticket] = [tuple(sorted(rng.sample(range(1, 50), 6))) for _ in range(22)]
    candidates = [
        StrategyCandidate(f"S{index:02d}", [tickets[2 * index], tickets[2 * index + 1]])
        for index in range(10)
    ]
    last = tickets[0] if shared_ticket else tickets[21]
    candidates.append(StrategyCandidate("S10", [tickets[20], last]))
    return candidates


def _block_rank_four_candidates() -> list[StrategyCandidate]:
    """Six distinct tickets A|B, C|D, A|C, B|D, A|D, B|C over disjoint triples: rank 4."""

    a, b, c, d = (1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12)
    tickets = (a + b, c + d, a + c, b + d, a + d, b + c)
    return [StrategyCandidate(f"b{index}", [ticket]) for index, ticket in enumerate(tickets)]


def _pre_change_build_portfolio(
    candidates: Sequence[StrategyCandidate],
    quality_by_strategy: Mapping[str, float],
    bucket_sizes: Sequence[int] = (5, 10, 20),
) -> dict[int, list[Ticket]]:
    """Verbatim body of ``build_portfolio`` at base 947baf9d: the invariance oracle."""
    supporters: dict[Ticket, set[str]] = {}
    for candidate in candidates:
        for raw in candidate.tickets:
            ticket = tuple(sorted(raw))
            if len(ticket) != 6 or len(set(ticket)) != 6:
                raise ValueError(f"invalid ticket from {candidate.strategy_id}: {raw}")
            supporters.setdefault(ticket, set()).add(candidate.strategy_id)

    def quality(ticket: Ticket) -> float:
        return sum(quality_by_strategy.get(s, 0.0) for s in supporters[ticket])

    ranked = sorted(
        supporters,
        key=lambda t: (-len(supporters[t]), -quality(t), t),
    )

    buckets: dict[int, list[Ticket]] = {}
    for k in bucket_sizes:
        if k > len(ranked):
            raise ValueError(
                f"requested K{k} but only {len(ranked)} distinct candidate tickets are available"
            )
        buckets[k] = ranked[:k]
    return buckets


@dataclass(frozen=True)
class _Case:
    candidates: tuple[StrategyCandidate, ...]
    quality: dict[str, float]
    bucket_sizes: tuple[int, ...]


def _random_case(rng: random.Random, *, dyadic_quality: bool) -> _Case:
    strategy_ids = [f"q{index:02d}" for index in range(rng.randint(1, 12))]
    candidates: list[StrategyCandidate] = []
    for strategy_id in strategy_ids:
        tickets: list[Ticket] = []
        for _ in range(rng.randint(0, 4)):
            # A tiny number universe forces heavy cross-strategy duplication;
            # 44..55 keeps the legacy tolerance of numbers above 49 exercised.
            universe = range(1, 10) if rng.random() < 0.85 else range(44, 56)
            tickets.append(tuple(rng.sample(universe, 6)))
        if not dyadic_quality and rng.random() < 0.05:
            tickets.append(rng.choice(((1, 2, 3, 4, 5), (1, 1, 2, 3, 4, 5))))
        candidates.append(StrategyCandidate(strategy_id, tickets))
    weights = (0.0, 0.125, 0.25, 0.5, 1.0) if dyadic_quality else (0.0, 0.1, 0.2, 0.3, 0.7)
    quality = (
        {}
        if rng.random() < 0.25
        else {s: rng.choice(weights) for s in strategy_ids if rng.random() < 0.8}
    )
    bucket_sizes = tuple(sorted(rng.sample(range(13), rng.randint(1, 3))))
    return _Case(tuple(candidates), quality, bucket_sizes)


def _portfolio_or_error(
    builder: Callable[
        [Sequence[StrategyCandidate], Mapping[str, float], Sequence[int]],
        dict[int, list[Ticket]],
    ],
    case: _Case,
) -> dict[int, list[Ticket]] | str:
    try:
        return builder(case.candidates, case.quality, case.bucket_sizes)
    except ValueError as exc:
        return f"ValueError: {exc}"


def _independent_seed(
    method_id: str,
    method_version: str,
    source: CausalSourceIdentity,
    candidate_pool_sha256: str,
    k: int,
    *,
    trailing_lf: bool = False,
) -> int:
    seed_object = {
        "method_id": method_id,
        "method_version": method_version,
        "source_mode": source.source_mode,
        "target_draw_number": source.target_draw_number,
        "target_draw_date": source.target_draw_date,
        "history_cutoff_draw_number": source.history_cutoff_draw_number,
        "history_identity_kind": source.history_identity_kind,
        "history_identity": source.history_identity,
        "candidate_pool_sha256": candidate_pool_sha256,
        "k": k,
    }
    text = json.dumps(seed_object, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    seed_bytes = text.encode("utf-8") + (b"\n" if trailing_lf else b"")
    return int.from_bytes(hashlib.sha256(seed_bytes).digest()[:16], "big")


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)
        found = set(mapping)
        for item in mapping.values():
            found |= _keys(item)
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for item in cast(list[object], value):
            found |= _keys(item)
        return found
    return set()


def _module_imports(module: ModuleType) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(inspect.getsource(module))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


# 1. Existing raw-majority build_portfolio behavior remains unchanged.


def test_build_portfolio_matches_pre_change_implementation_on_random_corpus() -> None:
    rng = random.Random(947)
    for _ in range(400):
        case = _random_case(rng, dyadic_quality=False)
        assert _portfolio_or_error(build_portfolio, case) == _portfolio_or_error(
            _pre_change_build_portfolio, case
        )


def test_build_portfolio_keeps_legacy_ticket_tolerance() -> None:
    """The operational selector itself still only requires six distinct values."""

    candidates = [StrategyCandidate("a", [(52, 1, 2, 3, 4, 5)])]
    assert build_portfolio(candidates, {}, bucket_sizes=(1,)) == {1: [(1, 2, 3, 4, 5, 52)]}
    assert _pre_change_build_portfolio(candidates, {}, bucket_sizes=(1,)) == {
        1: [(1, 2, 3, 4, 5, 52)]
    }


# 2. Candidate pool exactly reproduces operational dedup/support/order semantics.


def test_candidate_pool_reproduces_operational_dedup_support_and_order() -> None:
    rng = random.Random(311)
    for _ in range(300):
        case = _random_case(rng, dyadic_quality=True)
        pool = build_candidate_pool(case.candidates, case.quality)
        expected_supporters: dict[Ticket, set[str]] = {}
        for candidate in case.candidates:
            for raw in candidate.tickets:
                expected_supporters.setdefault(tuple(sorted(raw)), set()).add(
                    candidate.strategy_id
                )
        assert [entry.ticket for entry in pool] == sorted(
            expected_supporters,
            key=lambda ticket: (
                -len(expected_supporters[ticket]),
                -sum(case.quality.get(s, 0.0) for s in expected_supporters[ticket]),
                ticket,
            ),
        )
        for index, entry in enumerate(pool):
            assert entry.candidate_pool_index == index
            assert entry.supporters == tuple(sorted(expected_supporters[entry.ticket]))
            assert entry.support_count == len(expected_supporters[entry.ticket])
            assert entry.quality_sum == sum(
                case.quality.get(strategy_id, 0.0) for strategy_id in entry.supporters
            )


def test_candidate_pool_entries_are_immutable() -> None:
    entry = build_candidate_pool(_consensus_candidates(), {})[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.support_count = 99  # pyright: ignore[reportAttributeAccessIssue]


# 3. An empty quality map reduces the order to support_count DESC, ticket ASC.


def test_empty_quality_map_orders_by_support_desc_then_ticket_asc() -> None:
    operational_pool = build_candidate_pool(_consensus_candidates(), {})
    adapter_pool = build_kdpp_candidate_pool(_consensus_candidates())
    for entries in (operational_pool, adapter_pool.entries):
        assert tuple(entry.ticket for entry in entries) == _CONSENSUS_ORDER
        assert [entry.support_count for entry in entries] == [3, 2, 2, 1, 1, 1]
        assert all(entry.quality_sum == 0.0 for entry in entries)

    rng = random.Random(649)
    for _ in range(200):
        case = _random_case(rng, dyadic_quality=True)
        pool = build_candidate_pool(case.candidates, {})
        assert list(pool) == sorted(pool, key=lambda entry: (-entry.support_count, entry.ticket))


def test_adapter_pool_is_the_operational_pool_with_an_empty_quality_map() -> None:
    candidates = _live_like_candidates()
    assert build_kdpp_candidate_pool(candidates).entries == build_candidate_pool(candidates, {})


def test_supplied_quality_breaks_support_ties_in_the_operational_helper() -> None:
    # (1,7,13,19,25,31) and (7,8,9,10,11,12) both have support 2, so only the
    # supplied quality of s01 can separate them -- and it must outrank ticket ASC.
    without_quality = [entry.ticket for entry in build_candidate_pool(_consensus_candidates(), {})]
    assert without_quality[1:3] == [(1, 7, 13, 19, 25, 31), (7, 8, 9, 10, 11, 12)]

    pool = build_candidate_pool(_consensus_candidates(), {"s01": 1.0})
    assert [entry.ticket for entry in pool] == [
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (1, 7, 13, 19, 25, 31),
        (2, 8, 14, 20, 26, 32),
        (13, 14, 15, 16, 17, 18),
        (19, 20, 21, 22, 23, 24),
    ]
    assert [entry.quality_sum for entry in pool] == [1.0, 1.0, 0.0, 0.0, 0.0, 0.0]


# 4. Candidate manifest canonical_bytes is deterministic.


def test_candidate_manifest_is_pinned_canonical_bytes() -> None:
    expected_manifest: dict[str, object] = {
        "schema_version": "b649-kdpp-candidate-pool-v1",
        "candidate_order": ["SUPPORT_COUNT_DESC", "SUPPLIED_QUALITY_SUM_DESC", "TICKET_ASC"],
        "quality_by_strategy": {},
        "candidates": [
            {
                "candidate_pool_index": 0,
                "ticket": [1, 2, 3, 4, 5, 6],
                "supporters": ["s01", "s02", "s03"],
                "support_count": 3,
            },
            {
                "candidate_pool_index": 1,
                "ticket": [1, 7, 13, 19, 25, 31],
                "supporters": ["s04", "s05"],
                "support_count": 2,
            },
            {
                "candidate_pool_index": 2,
                "ticket": [7, 8, 9, 10, 11, 12],
                "supporters": ["s01", "s04"],
                "support_count": 2,
            },
            {
                "candidate_pool_index": 3,
                "ticket": [2, 8, 14, 20, 26, 32],
                "supporters": ["s05"],
                "support_count": 1,
            },
            {
                "candidate_pool_index": 4,
                "ticket": [13, 14, 15, 16, 17, 18],
                "supporters": ["s02"],
                "support_count": 1,
            },
            {
                "candidate_pool_index": 5,
                "ticket": [19, 20, 21, 22, 23, 24],
                "supporters": ["s03"],
                "support_count": 1,
            },
        ],
    }
    independent_bytes = json.dumps(
        expected_manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")

    pool = build_kdpp_candidate_pool(_consensus_candidates())
    assert pool.manifest_bytes == independent_bytes
    assert pool.manifest_bytes == canonical_bytes(expected_manifest)
    assert pool.manifest_bytes != canonical_file_bytes(expected_manifest)
    assert not pool.manifest_bytes.endswith(b"\n")
    assert pool.sha256 == hashlib.sha256(independent_bytes).hexdigest()
    assert pool.candidate_count == 6


def test_candidate_manifest_is_deterministic_and_input_order_invariant() -> None:
    candidates = _live_like_candidates()
    reordered = [
        StrategyCandidate(candidate.strategy_id, [tuple(reversed(t)) for t in candidate.tickets])
        for candidate in reversed(candidates)
    ]
    first = build_kdpp_candidate_pool(candidates)
    assert build_kdpp_candidate_pool(candidates) == first
    assert build_kdpp_candidate_pool(reordered) == first
    assert first.sha256 == sha256_hex(first.manifest_bytes)
    assert canonical_bytes(json.loads(first.manifest_bytes)) == first.manifest_bytes


# 5-7. Causal source identities.


def test_live_source_identity_validates_history_sha256() -> None:
    source = _source(LIVE_PREDRAW_V1)
    assert source.history_identity_kind == HISTORY_SHA256
    assert source.manifest()["history_identity"] == _HISTORY_DIGEST
    with pytest.raises(ValueError, match="requires history_identity_kind HISTORY_SHA256"):
        _source(LIVE_PREDRAW_V1, history_identity_kind=HISTORY_FINGERPRINT)
    for malformed in (_HISTORY_DIGEST.upper(), _HISTORY_DIGEST[:-1], "g" * 64, ""):
        with pytest.raises(ValueError, match="lowercase SHA-256"):
            _source(LIVE_PREDRAW_V1, history_identity=malformed)


def test_historical_source_identity_validates_history_fingerprint() -> None:
    source = _source(HISTORICAL_CAUSAL_REPLAY_V1)
    assert source.history_identity_kind == HISTORY_FINGERPRINT
    with pytest.raises(ValueError, match="requires history_identity_kind HISTORY_FINGERPRINT"):
        _source(HISTORICAL_CAUSAL_REPLAY_V1, history_identity_kind=HISTORY_SHA256)
    for malformed in (_HISTORY_DIGEST.upper(), _HISTORY_DIGEST + "0", "not-a-fingerprint"):
        with pytest.raises(ValueError, match="lowercase SHA-256"):
            _source(HISTORICAL_CAUSAL_REPLAY_V1, history_identity=malformed)


@pytest.mark.parametrize("mode", [LIVE_PREDRAW_V1, HISTORICAL_CAUSAL_REPLAY_V1])
@pytest.mark.parametrize(
    ("cutoff_number", "cutoff_date"),
    [
        ("990000002", "2099-01-09"),  # cutoff is the target
        ("990000003", "2099-01-13"),  # cutoff after the target
        ("990000001", "2099-01-09"),  # same date as the target
        ("990000002", "2099-01-06"),  # earlier date, same draw number
        ("990000003", "2099-01-06"),  # earlier date, later draw number
    ],
)
def test_source_identity_rejects_cutoff_not_strictly_before_target(
    mode: str, cutoff_number: str, cutoff_date: str
) -> None:
    with pytest.raises(ValueError, match="strictly precede"):
        _source(mode, history_cutoff_draw_number=cutoff_number, history_cutoff_date=cutoff_date)


def test_source_identity_accepts_a_numbering_era_boundary() -> None:
    source = _source(
        HISTORICAL_CAUSAL_REPLAY_V1,
        target_draw_number="100000001",
        target_draw_date="2011-01-04",
        history_cutoff_draw_number="99000105",
        history_cutoff_date="2010-12-31",
    )
    assert source.history_cutoff_draw_number == "99000105"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_mode", "LIVE", "unsupported source_mode"),
        ("target_draw_date", "20990109", "YYYY-MM-DD"),
        ("target_draw_date", "2099-1-9", "YYYY-MM-DD"),
        ("history_cutoff_date", "2099-01-06T00:00:00", "YYYY-MM-DD"),
        ("target_draw_number", "0990000002", "canonical decimal"),
        ("target_draw_number", "99O000002", "canonical decimal"),
        ("history_cutoff_draw_number", "", "canonical decimal"),
        ("history_cutoff_draw_number", "\uff19\uff19", "canonical decimal"),
    ],
)
def test_source_identity_rejects_non_canonical_fields(field: str, value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _source(LIVE_PREDRAW_V1, **{field: value})


def test_source_identity_rejects_non_string_fields() -> None:
    with pytest.raises(ValueError, match="target_draw_number must be a string"):
        _source(LIVE_PREDRAW_V1, target_draw_number=cast(str, 990000002))


# 8-10. Seed derivation.


def test_seed_matches_the_exact_frozen_formula() -> None:
    source = _source(LIVE_PREDRAW_V1)
    pool = build_kdpp_candidate_pool(_live_like_candidates())
    for arm, method_id, method_version in _SEEDED_ARMS:
        for k in ALLOWED_K:
            seed = derive_arm_seed(arm, source=source, candidate_pool_sha256=pool.sha256, k=k)
            assert seed == _independent_seed(method_id, method_version, source, pool.sha256, k)
            assert seed != _independent_seed(
                method_id, method_version, source, pool.sha256, k, trailing_lf=True
            )
            assert 0 <= seed < 2**128


def test_same_source_pool_and_k_give_the_same_seed() -> None:
    pool = build_kdpp_candidate_pool(_live_like_candidates())
    first = derive_arm_seed("KDPP", source=_source(), candidate_pool_sha256=pool.sha256, k=5)
    again = derive_arm_seed("KDPP", source=_source(), candidate_pool_sha256=pool.sha256, k=5)
    assert first == again
    assert select_kdpp(_live_like_candidates(), source=_source(), k=5).seed == first
    assert derive_arm_seed("KDPP", source=_source(), candidate_pool_sha256=pool.sha256, k=10) != (
        first
    )
    other_pool = build_kdpp_candidate_pool(_consensus_candidates())
    assert (
        derive_arm_seed("KDPP", source=_source(), candidate_pool_sha256=other_pool.sha256, k=5)
        != first
    )


def test_changing_source_mode_changes_the_seed() -> None:
    pool = build_kdpp_candidate_pool(_live_like_candidates())
    live = _source(LIVE_PREDRAW_V1)
    historical = _source(HISTORICAL_CAUSAL_REPLAY_V1)
    assert live.history_identity == historical.history_identity
    for arm, _, _ in _SEEDED_ARMS:
        assert derive_arm_seed(
            arm, source=live, candidate_pool_sha256=pool.sha256, k=5
        ) != derive_arm_seed(arm, source=historical, candidate_pool_sha256=pool.sha256, k=5)


def test_random_and_kdpp_seed_domains_differ() -> None:
    candidates = _live_like_candidates()
    pool = build_kdpp_candidate_pool(candidates)
    assert RANDOM_K_METHOD_ID != KDPP_METHOD_ID
    for k in ALLOWED_K:
        kdpp_seed = derive_arm_seed(
            "KDPP", source=_source(), candidate_pool_sha256=pool.sha256, k=k
        )
        random_seed = derive_arm_seed(
            "SEEDED_RANDOM_K", source=_source(), candidate_pool_sha256=pool.sha256, k=k
        )
        assert kdpp_seed != random_seed
        assert select_kdpp(candidates, source=_source(), k=k).seed == kdpp_seed
        assert select_seeded_random_k(candidates, source=_source(), k=k).seed == random_seed


# 11-12. RANDOM_K and KDPP draws.


@pytest.mark.parametrize("k", ALLOWED_K)
def test_random_k_selects_k_distinct_candidates_deterministically(k: int) -> None:
    candidates = _live_like_candidates()
    selection = select_seeded_random_k(candidates, source=_source(), k=k)
    assert selection.feasibility_status == "FEASIBLE"
    assert selection.sampling_order is not None
    assert len(selection.portfolio_order) == k == len(set(selection.portfolio_order))
    assert len(selection.tickets) == k == len(set(selection.tickets))
    assert selection.seed is not None
    expected = np.random.default_rng(selection.seed).choice(
        selection.candidate_count, size=k, replace=False
    )
    assert selection.sampling_order == tuple(int(index) for index in expected.tolist())
    assert select_seeded_random_k(candidates, source=_source(), k=k) == selection


@pytest.mark.parametrize("k", ALLOWED_K)
def test_kdpp_selects_k_distinct_candidates_deterministically(k: int) -> None:
    candidates = _live_like_candidates()
    selection = select_kdpp(candidates, source=_source(), k=k)
    assert selection.feasibility_status == "FEASIBLE"
    assert len(selection.portfolio_order) == k == len(set(selection.portfolio_order))
    assert len(selection.tickets) == k == len(set(selection.tickets))
    assert selection.seed is not None
    pool = build_kdpp_candidate_pool(candidates)
    expected = select_k_dpp(
        tuple(range(pool.candidate_count)),
        l_kernel=build_kdpp_kernel(pool),
        k=k,
        seed=selection.seed,
    )
    assert selection.sampling_order == expected
    assert select_kdpp(candidates, source=_source(), k=k) == selection


def test_selection_runtime_domain_is_recorded_and_pinned() -> None:
    assert np.__version__ == EXPECTED_NUMPY_VERSION == "2.5.2"
    for selector in _ARM_SELECTORS:
        selection = selector(_live_like_candidates(), source=_source(), k=5)
        assert selection.numpy_version == EXPECTED_NUMPY_VERSION
        assert selection.lapack_backend
        assert selection.reproducibility_claim == REPRODUCIBILITY_CLAIM
    assert REPRODUCIBILITY_CLAIM == "DETERMINISTIC_WITHIN_PINNED_RUNTIME_DOMAIN"


def test_method_identities_are_the_frozen_values() -> None:
    assert (KDPP_METHOD_ID, KDPP_METHOD_VERSION) == (
        "B649_KDPP_RAW_MAJORITY_QUALITY_DIVERSITY",
        "1.1.0",
    )
    assert (RANDOM_K_METHOD_ID, RANDOM_K_METHOD_VERSION) == (
        "B649_SEEDED_RANDOM_K_CONTROL",
        "1.0.0",
    )
    assert (RAW_MAJORITY_METHOD_ID, RAW_MAJORITY_METHOD_VERSION) == (
        materializer.PORTFOLIO_METHOD_ID,
        materializer.PORTFOLIO_METHOD_VERSION,
    )
    assert ALLOWED_K == (2, 3, 5, 10, 20)
    for selector, method in zip(
        _ARM_SELECTORS,
        (
            (RAW_MAJORITY_METHOD_ID, RAW_MAJORITY_METHOD_VERSION),
            (RANDOM_K_METHOD_ID, RANDOM_K_METHOD_VERSION),
            (KDPP_METHOD_ID, KDPP_METHOD_VERSION),
        ),
        strict=True,
    ):
        selection = selector(_live_like_candidates(), source=_source(), k=3)
        assert (selection.method_id, selection.method_version) == method


@pytest.mark.parametrize("k", ALLOWED_K)
def test_raw_majority_arm_is_the_operational_build_portfolio_prefix(k: int) -> None:
    candidates = _live_like_candidates()
    selection = select_raw_majority_top_k(candidates, source=_source(), k=k)
    assert selection.feasibility_status == "FEASIBLE"
    assert selection.tickets == tuple(build_portfolio(candidates, {}, bucket_sizes=(k,))[k])
    assert selection.portfolio_order == tuple(range(k))
    assert selection.seed is None
    assert selection.sampling_order is None


def test_all_arms_share_the_identical_candidate_pool() -> None:
    candidates = _live_like_candidates()
    pool = build_kdpp_candidate_pool(candidates)
    for selector in _ARM_SELECTORS:
        for k in ALLOWED_K:
            selection = selector(candidates, source=_source(), k=k)
            assert selection.candidate_pool_sha256 == pool.sha256
            assert selection.candidate_count == pool.candidate_count == 21
            assert selection.source == _source()
            assert selection.k == k


def test_kdpp_pool_rejects_tickets_outside_the_six_of_forty_nine_domain() -> None:
    for bad in (
        (0, 1, 2, 3, 4, 5),
        (1, 2, 3, 4, 5, 50),
        (1, 2, 3, 4, 5),
        (1, 1, 2, 3, 4, 5),
        (True, 2, 3, 4, 5, 6),
        (1.0, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 6, 7),
    ):
        with pytest.raises(ValueError, match="distinct integers in"):
            build_kdpp_candidate_pool([StrategyCandidate("a", [cast(Ticket, bad)])])
    with pytest.raises(ValueError, match="non-empty string"):
        build_kdpp_candidate_pool([StrategyCandidate("", [(1, 2, 3, 4, 5, 6)])])


# 13-15. Kernel formula.


def test_kernel_equals_support_weighted_overlap_closed_form() -> None:
    pool = build_kdpp_candidate_pool(_consensus_candidates())
    kernel = build_kdpp_kernel(pool)
    similarity = ticket_similarity_matrix(pool)
    assert kernel.dtype == similarity.dtype == np.float64
    for i, left in enumerate(pool.entries):
        for j, right in enumerate(pool.entries):
            overlap = len(set(left.ticket) & set(right.ticket))
            assert float(similarity[i, j]) == overlap / 6
            assert float(kernel[i, j]) == (
                math.sqrt(left.support_count * right.support_count) * overlap / 6
            )
    quality = np.diag(np.sqrt([float(entry.support_count) for entry in pool.entries]))
    np.testing.assert_allclose(kernel, quality @ similarity @ quality, rtol=1e-15, atol=0.0)
    assert np.array_equal(kernel, kernel.T)


def test_unit_support_reduces_the_kernel_exactly_to_similarity() -> None:
    pool = build_kdpp_candidate_pool(_live_like_candidates(shared_ticket=False))
    assert {entry.support_count for entry in pool.entries} == {1}
    kernel = build_kdpp_kernel(pool)
    similarity = ticket_similarity_matrix(pool)
    assert np.array_equal(kernel, similarity)
    assert np.array_equal(np.diag(kernel), np.ones(pool.candidate_count))


def test_support_above_one_scales_only_the_quality_component() -> None:
    pool = build_kdpp_candidate_pool(_consensus_candidates())
    kernel = build_kdpp_kernel(pool)
    similarity = ticket_similarity_matrix(pool)
    supports = [entry.support_count for entry in pool.entries]
    assert supports == [3, 2, 2, 1, 1, 1]
    assert np.array_equal(np.diag(kernel), np.array(supports, dtype=np.float64))
    for i, left in enumerate(supports):
        for j, right in enumerate(supports):
            if left == right == 1 or similarity[i, j] == 0.0:
                assert kernel[i, j] == similarity[i, j]
            else:
                assert kernel[i, j] > similarity[i, j]
                assert kernel[i, j] / similarity[i, j] == pytest.approx(
                    math.sqrt(left * right), rel=1e-15
                )


# 16. K feasibility.


@pytest.mark.parametrize("selector", _ARM_SELECTORS)
def test_candidate_count_below_k_is_infeasible(selector: Callable[..., ArmSelection]) -> None:
    selection = selector(_consensus_candidates(), source=_source(), k=10)
    assert selection.feasibility_status == "INFEASIBLE_CANDIDATE_COUNT"
    assert selection.candidate_count == 6
    assert selection.tickets == selection.portfolio_order == ()
    assert selection.portfolio_sha256 is None
    assert selection.min_relative_eigengap is None


def test_numerical_rank_below_k_is_infeasible_only_for_kdpp() -> None:
    candidates = _block_rank_four_candidates()
    pool = build_kdpp_candidate_pool(candidates)
    kernel = build_kdpp_kernel(pool)
    with pytest.raises(ValueError, match="numerical rank=4"):
        select_k_dpp(tuple(range(pool.candidate_count)), l_kernel=kernel, k=5, seed=0)

    kdpp = select_kdpp(candidates, source=_source(), k=5)
    assert kdpp.feasibility_status == "INFEASIBLE_NUMERICAL_RANK"
    assert kdpp.candidate_count == 6
    assert kdpp.tickets == kdpp.portfolio_order == kdpp.sampling_order == ()
    assert kdpp.portfolio_sha256 is None
    assert kdpp.failure_detail is None
    assert select_kdpp(candidates, source=_source(), k=3).feasibility_status == "FEASIBLE"
    assert select_seeded_random_k(candidates, source=_source(), k=5).feasibility_status == (
        "FEASIBLE"
    )
    assert select_raw_majority_top_k(candidates, source=_source(), k=5).feasibility_status == (
        "FEASIBLE"
    )


def test_selector_raise_after_feasible_precheck_is_a_hard_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(*_args: object, **_kwargs: object) -> tuple[int, ...]:
        raise ValueError("injected selector failure")

    monkeypatch.setattr(adapter, "select_k_dpp", _raise)
    selection = select_kdpp(_live_like_candidates(), source=_source(), k=5)
    assert selection.feasibility_status == "SELECTOR_HARD_FAILURE"
    assert selection.failure_detail == "ValueError: injected selector failure"
    assert selection.tickets == selection.portfolio_order == selection.sampling_order == ()
    assert selection.portfolio_sha256 is None
    assert selection.min_relative_eigengap is not None


def test_malformed_selector_return_is_a_hard_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _duplicates(*_args: object, **_kwargs: object) -> tuple[int, ...]:
        return (0, 0, 1, 2, 3)

    monkeypatch.setattr(adapter, "select_k_dpp", _duplicates)
    selection = select_kdpp(_live_like_candidates(), source=_source(), k=5)
    assert selection.feasibility_status == "SELECTOR_HARD_FAILURE"
    assert selection.failure_detail is not None
    assert "not 5 distinct candidates" in selection.failure_detail


@pytest.mark.parametrize("k", [0, 1, 4, 6, 21, -5])
def test_k_outside_the_frozen_set_is_rejected(k: int) -> None:
    for selector in _ARM_SELECTORS:
        with pytest.raises(ValueError, match="K must be one of"):
            selector(_live_like_candidates(), source=_source(), k=k)


def test_min_relative_eigengap_is_a_kdpp_only_diagnostic() -> None:
    candidates = _live_like_candidates()
    pool = build_kdpp_candidate_pool(candidates)
    eigenvalues = np.linalg.eigh(build_kdpp_kernel(pool))[0]
    tolerance = float(eigenvalues.max()) * pool.candidate_count * float(np.finfo(np.float64).eps)
    nonzero = np.sort(eigenvalues[eigenvalues > tolerance])
    expected = float(np.diff(nonzero).min() / nonzero[-1])
    kdpp = select_kdpp(candidates, source=_source(), k=5)
    assert kdpp.min_relative_eigengap == expected > 0.0
    assert select_seeded_random_k(candidates, source=_source(), k=5).min_relative_eigengap is None
    assert select_raw_majority_top_k(candidates, source=_source(), k=5).min_relative_eigengap is (
        None
    )


# 17. portfolio_order is candidate-pool order; sampling_order is kept separately.


@pytest.mark.parametrize("selector", [select_seeded_random_k, select_kdpp])
def test_portfolio_order_is_pool_order_and_sampling_order_is_retained(
    selector: Callable[..., ArmSelection],
) -> None:
    candidates = _live_like_candidates()
    pool = build_kdpp_candidate_pool(candidates)
    selection = selector(candidates, source=_source(), k=5)
    assert selection.sampling_order is not None
    assert selection.portfolio_order == tuple(sorted(selection.sampling_order))
    assert selection.sampling_order != selection.portfolio_order
    assert selection.tickets == tuple(
        pool.entries[index].ticket for index in selection.portfolio_order
    )
    manifest = selection.portfolio_manifest()
    assert "sampling_order" not in manifest
    assert manifest["portfolio_order"] == list(selection.portfolio_order)
    assert selection.portfolio_sha256 == sha256_hex(canonical_bytes(manifest))
    reordered = dataclasses.replace(selection, sampling_order=selection.portfolio_order)
    assert sha256_hex(canonical_bytes(reordered.portfolio_manifest())) == (
        selection.portfolio_sha256
    )


def test_portfolio_hash_distinguishes_arms_and_records_the_seed() -> None:
    candidates = _live_like_candidates()
    hashes = {
        selector(candidates, source=_source(), k=5).portfolio_sha256 for selector in _ARM_SELECTORS
    }
    assert None not in hashes
    assert len(hashes) == 3
    raw = select_raw_majority_top_k(candidates, source=_source(), k=5)
    assert raw.portfolio_manifest()["seed_decimal"] == "NOT_APPLICABLE"
    kdpp = select_kdpp(candidates, source=_source(), k=5)
    assert kdpp.portfolio_manifest()["seed_decimal"] == str(kdpp.seed)


# 18. No outcome/result/prize/hit-rate field is accepted or consumed.


def test_adapter_accepts_and_consumes_no_outcome_fields() -> None:
    public_callables: tuple[Callable[..., object], ...] = (
        build_candidate_pool,
        build_kdpp_candidate_pool,
        ticket_similarity_matrix,
        build_kdpp_kernel,
        derive_arm_seed,
        *_ARM_SELECTORS,
    )
    parameters = {
        name
        for function in public_callables
        for name in inspect.signature(function).parameters
    }
    assert parameters == {
        "candidates",
        "quality_by_strategy",
        "pool",
        "arm",
        "source",
        "candidate_pool_sha256",
        "k",
    }

    field_names = {
        field.name
        for record in (
            StrategyCandidate,
            CandidatePoolEntry,
            CandidatePool,
            CausalSourceIdentity,
            ArmSelection,
        )
        for field in dataclasses.fields(record)
    }
    candidates = _live_like_candidates()
    manifests: list[object] = [
        json.loads(build_kdpp_candidate_pool(candidates).manifest_bytes),
        *(
            selector(candidates, source=_source(), k=5).portfolio_manifest()
            for selector in _ARM_SELECTORS
        ),
    ]
    names = parameters | field_names | set[str]().union(*map(_keys, manifests))
    assert not [name for name in names if any(token in name for token in _OUTCOME_TOKENS)]

    fields = _source().manifest() | {"winning_numbers": "1,2,3,4,5,6"}
    with pytest.raises(TypeError):
        CausalSourceIdentity(**fields)


def test_adapter_dependency_closure_has_no_data_or_outcome_path() -> None:
    assert _module_imports(adapter) == {
        "__future__",
        "collections.abc",
        "dataclasses",
        "datetime",
        "hashlib",
        "re",
        "typing",
        "numpy",
        "numpy.typing",
        "lottolab.application.b649_operational_portfolio_selector",
        "lottolab.evidence.canonical_json",
        "lottolab.research.k_dpp_ticket_portfolio",
    }
    for dependency in (operational, canonical_json, k_dpp_ticket_portfolio):
        imports = _module_imports(dependency)
        assert "sqlite3" not in imports
        assert not any(name.startswith("lottolab") for name in imports), dependency.__name__
