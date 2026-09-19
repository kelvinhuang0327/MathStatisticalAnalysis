"""Outcome-free three-arm B649 portfolio adapter over the operational candidate pool.

Branch2 (strict causal OOS) and Branch6 (descriptive structural comparison)
share this one adapter. Every arm selects exactly K tickets from the same
canonical candidate pool:

* ``RAW_MAJORITY`` -- the operational raw-majority Top-K: the first K pool
  entries, identical to ``build_portfolio(candidates, {}, (K,))[K]``;
* ``SEEDED_RANDOM_K`` -- K entries drawn uniformly without replacement;
* ``KDPP`` -- one exact fixed-size k-DPP draw (``select_k_dpp``);
* ``MIN_OVERLAP`` -- a deterministic greedy minimum-overlap portfolio, the
  outcome-free geometry arm that isolates portfolio redundancy from sampling.

Candidate pool: the operational selector's own ``build_candidate_pool`` with
an empty supplied strategy-quality map (R1 infers and adds no performance
weight), so pool order is support_count DESC, then ticket ASC. Tickets must be
exactly six distinct integers in [1, 49]. The pool is hashed as
``SHA256(canonical_bytes(candidate manifest))`` -- LCJ-1 ``canonical_bytes``,
never ``canonical_file_bytes``.

k-DPP kernel -- no jitter, no tunable exponent or scale, no alternative kernel::

    w_i  = support_count(ticket_i),   q_i = sqrt(w_i)
    S_ij = phi_i . phi_j = |ticket_i & ticket_j| / 6,   phi_i = x_i / sqrt(6)
    L    = diag(sqrt(w)) @ S @ diag(sqrt(w))

where x_i is ticket i's 49-dimensional binary indicator. L is evaluated in its
exact closed form ``sqrt(w_i * w_j) * overlap_ij / 6``, which keeps L exactly
symmetric and makes L equal S bit-for-bit when every support count is 1.

Seed: ``SHA256(canonical_bytes(seed object))``; its first 16 digest bytes read
as an unsigned big-endian integer. KDPP and SEEDED_RANDOM_K put their own
method identity into the seed object, so their seed domains are disjoint.

``portfolio_order`` (selected candidate_pool_index values, ascending) is the
only order downstream ``ticket_position`` may use. ``sampling_order`` is the
selector's draw order, kept for audit; it is not a ranking.

Reproducibility: deterministic within the pinned runtime domain (the NumPy
version and BLAS/LAPACK backend recorded on every selection). Byte-identical
sampling across platforms or backends is not claimed.

The adapter never reads, accepts, or scores outcomes: its only inputs are
already-generated pre-draw strategy tickets, a causal source identity, and K.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Final, Literal

import numpy as np
import numpy.typing as npt

from lottolab.application.b649_operational_portfolio_selector import (
    CandidatePoolEntry,
    StrategyCandidate,
    Ticket,
    build_candidate_pool,
)
from lottolab.evidence.canonical_json import canonical_bytes, sha256_hex
from lottolab.research.k_dpp_ticket_portfolio import select_k_dpp

LIVE_PREDRAW_V1: Final = "LIVE_PREDRAW_V1"
HISTORICAL_CAUSAL_REPLAY_V1: Final = "HISTORICAL_CAUSAL_REPLAY_V1"
HISTORY_SHA256: Final = "HISTORY_SHA256"
HISTORY_FINGERPRINT: Final = "HISTORY_FINGERPRINT"
HISTORY_IDENTITY_KIND_BY_SOURCE_MODE: Final[Mapping[str, str]] = {
    LIVE_PREDRAW_V1: HISTORY_SHA256,
    HISTORICAL_CAUSAL_REPLAY_V1: HISTORY_FINGERPRINT,
}

#: The operational raw-majority selector, as materialized by
#: ``b649_operational_portfolio_materializer`` (PORTFOLIO_METHOD_ID/VERSION).
RAW_MAJORITY_METHOD_ID: Final = "B649_OPERATIONAL_PORTFOLIO_SELECTOR"
RAW_MAJORITY_METHOD_VERSION: Final = "1.0.0"
RANDOM_K_METHOD_ID: Final = "B649_SEEDED_RANDOM_K_CONTROL"
RANDOM_K_METHOD_VERSION: Final = "1.0.0"
KDPP_METHOD_ID: Final = "B649_KDPP_RAW_MAJORITY_QUALITY_DIVERSITY"
KDPP_METHOD_VERSION: Final = "1.1.0"
MIN_OVERLAP_METHOD_ID: Final = "B649_DETERMINISTIC_MIN_OVERLAP"
MIN_OVERLAP_METHOD_VERSION: Final = "1.0.0"

ALLOWED_K: Final = (2, 3, 5, 10, 20)
TICKET_SIZE: Final = 6
MIN_NUMBER: Final = 1
MAX_NUMBER: Final = 49
CANDIDATE_POOL_SCHEMA_VERSION: Final = "b649-kdpp-candidate-pool-v1"
PORTFOLIO_SCHEMA_VERSION: Final = "b649-kdpp-arm-portfolio-v1"
REPRODUCIBILITY_CLAIM: Final = "DETERMINISTIC_WITHIN_PINNED_RUNTIME_DOMAIN"
#: The NumPy version the runtime domain is pinned to (uv.lock).
EXPECTED_NUMPY_VERSION: Final = "2.5.2"

type Arm = Literal["RAW_MAJORITY", "SEEDED_RANDOM_K", "KDPP", "MIN_OVERLAP"]
type FeasibilityStatus = Literal[
    "FEASIBLE",
    "INFEASIBLE_CANDIDATE_COUNT",
    "INFEASIBLE_NUMERICAL_RANK",
    "SELECTOR_HARD_FAILURE",
]

_ARM_METHODS: Final[Mapping[Arm, tuple[str, str]]] = {
    "RAW_MAJORITY": (RAW_MAJORITY_METHOD_ID, RAW_MAJORITY_METHOD_VERSION),
    "SEEDED_RANDOM_K": (RANDOM_K_METHOD_ID, RANDOM_K_METHOD_VERSION),
    "KDPP": (KDPP_METHOD_ID, KDPP_METHOD_VERSION),
    "MIN_OVERLAP": (MIN_OVERLAP_METHOD_ID, MIN_OVERLAP_METHOD_VERSION),
}
_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
_DRAW_NUMBER_PATTERN = re.compile(r"[1-9][0-9]*")


@dataclass(frozen=True, slots=True)
class CausalSourceIdentity:
    """Pre-draw identity of one target and of the causal history that fed it.

    ``history_identity`` is the history's lowercase SHA-256 hex digest: its
    ``history_sha256`` under ``LIVE_PREDRAW_V1`` and its ``history_fingerprint``
    under ``HISTORICAL_CAUSAL_REPLAY_V1``. Draw numbers are canonical decimal
    strings and dates canonical ``YYYY-MM-DD``; the history cutoff must
    strictly precede the target by both draw date and draw number.
    """

    source_mode: str
    target_draw_number: str
    target_draw_date: str
    history_cutoff_draw_number: str
    history_cutoff_date: str
    history_identity_kind: str
    history_identity: str

    def __post_init__(self) -> None:
        for name, value in self.manifest().items():
            if type(value) is not str:
                raise ValueError(f"{name} must be a string, got {type(value).__name__}")
        expected_kind = HISTORY_IDENTITY_KIND_BY_SOURCE_MODE.get(self.source_mode)
        if expected_kind is None:
            raise ValueError(f"unsupported source_mode {self.source_mode!r}")
        if self.history_identity_kind != expected_kind:
            raise ValueError(
                f"{self.source_mode} requires history_identity_kind {expected_kind}, "
                f"got {self.history_identity_kind!r}"
            )
        if _DIGEST_PATTERN.fullmatch(self.history_identity) is None:
            raise ValueError("history_identity must be a lowercase SHA-256 hex digest")
        target_number = _draw_number(self.target_draw_number, "target_draw_number")
        cutoff_number = _draw_number(self.history_cutoff_draw_number, "history_cutoff_draw_number")
        target_date = _iso_date(self.target_draw_date, "target_draw_date")
        cutoff_date = _iso_date(self.history_cutoff_date, "history_cutoff_date")
        if not (cutoff_date < target_date and cutoff_number < target_number):
            raise ValueError("history cutoff must strictly precede the target draw")

    def manifest(self) -> dict[str, str]:
        return {
            "source_mode": self.source_mode,
            "target_draw_number": self.target_draw_number,
            "target_draw_date": self.target_draw_date,
            "history_cutoff_draw_number": self.history_cutoff_draw_number,
            "history_cutoff_date": self.history_cutoff_date,
            "history_identity_kind": self.history_identity_kind,
            "history_identity": self.history_identity,
        }


@dataclass(frozen=True, slots=True)
class CandidatePool:
    """The canonical candidate pool and its canonical manifest bytes and SHA-256."""

    entries: tuple[CandidatePoolEntry, ...]
    manifest_bytes: bytes
    sha256: str

    @property
    def candidate_count(self) -> int:
        return len(self.entries)


@dataclass(frozen=True, slots=True)
class ArmSelection:
    """One arm's fixed-K portfolio over the shared candidate pool.

    ``tickets`` follow ``portfolio_order``. RAW_MAJORITY is a deterministic
    prefix, so its ``seed`` and ``sampling_order`` are None. Selections that
    are not FEASIBLE carry no tickets and no ``portfolio_sha256``;
    ``min_relative_eigengap`` is a KDPP-only diagnostic (see
    :func:`select_kdpp`).
    """

    arm: Arm
    method_id: str
    method_version: str
    source: CausalSourceIdentity
    k: int
    candidate_count: int
    candidate_pool_sha256: str
    seed: int | None
    feasibility_status: FeasibilityStatus
    sampling_order: tuple[int, ...] | None
    portfolio_order: tuple[int, ...]
    tickets: tuple[Ticket, ...]
    portfolio_sha256: str | None
    numpy_version: str
    lapack_backend: str
    min_relative_eigengap: float | None
    failure_detail: str | None
    reproducibility_claim: str

    def portfolio_manifest(self) -> dict[str, object]:
        """The canonical document ``portfolio_sha256`` is the SHA-256 of."""

        return {
            "schema_version": PORTFOLIO_SCHEMA_VERSION,
            "arm": self.arm,
            "method_id": self.method_id,
            "method_version": self.method_version,
            "source": self.source.manifest(),
            "candidate_pool_sha256": self.candidate_pool_sha256,
            "candidate_count": self.candidate_count,
            "k": self.k,
            "seed_decimal": "NOT_APPLICABLE" if self.seed is None else str(self.seed),
            "portfolio_order": list(self.portfolio_order),
            "tickets": [list(ticket) for ticket in self.tickets],
        }


def build_kdpp_candidate_pool(candidates: Sequence[StrategyCandidate]) -> CandidatePool:
    """Build the exact operational candidate pool with an empty quality map."""

    for candidate in candidates:
        if type(candidate.strategy_id) is not str or not candidate.strategy_id:
            raise ValueError(f"strategy_id must be a non-empty string: {candidate.strategy_id!r}")
        for raw in candidate.tickets:
            _validate_ticket_domain(raw, candidate.strategy_id)
    entries = build_candidate_pool(candidates, {})
    manifest_bytes = canonical_bytes(_candidate_manifest(entries))
    return CandidatePool(entries, manifest_bytes, sha256_hex(manifest_bytes))


def ticket_similarity_matrix(pool: CandidatePool) -> npt.NDArray[np.float64]:
    """``S_ij = |ticket_i & ticket_j| / 6`` over the pool, in candidate-pool order."""

    return _overlap_counts(pool) / TICKET_SIZE


def build_kdpp_kernel(pool: CandidatePool) -> npt.NDArray[np.float64]:
    """``L = diag(sqrt(w)) @ S @ diag(sqrt(w))`` with ``w_i = support_count(ticket_i)``."""

    support = np.array([entry.support_count for entry in pool.entries], dtype=np.float64)
    return np.sqrt(np.outer(support, support)) * _overlap_counts(pool) / TICKET_SIZE


def derive_arm_seed(
    arm: Literal["SEEDED_RANDOM_K", "KDPP"],
    *,
    source: CausalSourceIdentity,
    candidate_pool_sha256: str,
    k: int,
) -> int:
    """Unsigned big-endian integer of the first 16 bytes of
    ``SHA256(canonical_bytes(seed object))`` in the arm's own method domain."""

    _require_allowed_k(k)
    if _DIGEST_PATTERN.fullmatch(candidate_pool_sha256) is None:
        raise ValueError("candidate_pool_sha256 must be a lowercase SHA-256 hex digest")
    method_id, method_version = _ARM_METHODS[arm]
    seed_object: dict[str, object] = {
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
    digest = hashlib.sha256(canonical_bytes(seed_object)).digest()
    return int.from_bytes(digest[:16], "big")


def select_raw_majority_top_k(
    candidates: Sequence[StrategyCandidate],
    *,
    source: CausalSourceIdentity,
    k: int,
) -> ArmSelection:
    """The first K candidates in canonical candidate-pool order."""

    _require_allowed_k(k)
    pool = build_kdpp_candidate_pool(candidates)
    if pool.candidate_count < k:
        return _selection(
            "RAW_MAJORITY", pool, source, k, seed=None, status="INFEASIBLE_CANDIDATE_COUNT"
        )
    return _selection(
        "RAW_MAJORITY",
        pool,
        source,
        k,
        seed=None,
        status="FEASIBLE",
        portfolio_order=tuple(range(k)),
    )


def select_seeded_random_k(
    candidates: Sequence[StrategyCandidate],
    *,
    source: CausalSourceIdentity,
    k: int,
) -> ArmSelection:
    """K candidates drawn uniformly without replacement from the candidate pool
    by ``numpy.random.default_rng(seed).choice(candidate_count, K, replace=False)``."""

    _require_allowed_k(k)
    pool = build_kdpp_candidate_pool(candidates)
    seed = derive_arm_seed("SEEDED_RANDOM_K", source=source, candidate_pool_sha256=pool.sha256, k=k)
    if pool.candidate_count < k:
        return _selection(
            "SEEDED_RANDOM_K",
            pool,
            source,
            k,
            seed=seed,
            status="INFEASIBLE_CANDIDATE_COUNT",
            sampling_order=(),
        )
    rng = np.random.default_rng(seed)
    drawn = rng.choice(pool.candidate_count, size=k, replace=False)
    sampling_order = tuple(int(index) for index in drawn.tolist())
    return _selection(
        "SEEDED_RANDOM_K",
        pool,
        source,
        k,
        seed=seed,
        status="FEASIBLE",
        sampling_order=sampling_order,
        portfolio_order=tuple(sorted(sampling_order)),
    )


def select_kdpp(
    candidates: Sequence[StrategyCandidate],
    *,
    source: CausalSourceIdentity,
    k: int,
) -> ArmSelection:
    """One exact fixed-size k-DPP draw from the support-weighted kernel.

    Feasibility is prechecked with ``select_k_dpp``'s own numeric conventions
    (``numpy.linalg.eigh`` of the float64 kernel; rank = count of eigenvalues
    above ``max_eigenvalue * n * float64 eps``). If the precheck passes and
    ``select_k_dpp`` still raises, the selection is SELECTOR_HARD_FAILURE; the
    kernel is never modified and no failure is reclassified.

    ``min_relative_eigengap`` is the smallest gap between consecutive
    eigenvalues above the rank tolerance, divided by the largest eigenvalue;
    it is None when fewer than two eigenvalues clear the tolerance or when
    the eigenvalues were never computed.
    """

    _require_allowed_k(k)
    pool = build_kdpp_candidate_pool(candidates)
    seed = derive_arm_seed("KDPP", source=source, candidate_pool_sha256=pool.sha256, k=k)
    n = pool.candidate_count
    if n < k:
        return _selection(
            "KDPP",
            pool,
            source,
            k,
            seed=seed,
            status="INFEASIBLE_CANDIDATE_COUNT",
            sampling_order=(),
        )

    kernel = build_kdpp_kernel(pool)
    eigenvalues, _ = np.linalg.eigh(kernel)
    rank_tolerance = float(eigenvalues.max()) * n * float(np.finfo(np.float64).eps)
    rank = int(np.count_nonzero(eigenvalues > rank_tolerance))
    eigengap = _min_relative_eigengap(eigenvalues, rank_tolerance)
    if rank < k:
        return _selection(
            "KDPP",
            pool,
            source,
            k,
            seed=seed,
            status="INFEASIBLE_NUMERICAL_RANK",
            sampling_order=(),
            min_relative_eigengap=eigengap,
        )

    try:
        drawn = select_k_dpp(tuple(range(n)), l_kernel=kernel, k=k, seed=seed)
    except Exception as exc:
        return _selection(
            "KDPP",
            pool,
            source,
            k,
            seed=seed,
            status="SELECTOR_HARD_FAILURE",
            sampling_order=(),
            min_relative_eigengap=eigengap,
            failure_detail=f"{type(exc).__name__}: {exc}",
        )
    if len(drawn) != k or len(set(drawn)) != k:
        return _selection(
            "KDPP",
            pool,
            source,
            k,
            seed=seed,
            status="SELECTOR_HARD_FAILURE",
            sampling_order=(),
            min_relative_eigengap=eigengap,
            failure_detail=f"select_k_dpp returned {drawn!r}, not {k} distinct candidates",
        )
    return _selection(
        "KDPP",
        pool,
        source,
        k,
        seed=seed,
        status="FEASIBLE",
        sampling_order=drawn,
        portfolio_order=tuple(sorted(drawn)),
        min_relative_eigengap=eigengap,
    )


def select_deterministic_min_overlap(
    candidates: Sequence[StrategyCandidate],
    *,
    source: CausalSourceIdentity,
    k: int,
) -> ArmSelection:
    """Deterministic greedy minimum-overlap portfolio over the candidate pool.

    The geometry arm. It uses no randomness, no seed, no outcome and no prize
    history: only the pre-draw candidate pool and K. Its whole objective is to
    reduce portfolio redundancy, so that a lift over RAW_MAJORITY is
    attributable to portfolio geometry rather than to sampling or to any
    predictive signal.

    Frozen construction, from ``overlap_ij = |ticket_i & ticket_j|`` in 0..6:

    1. seed the portfolio with ``candidate_pool_index`` 0, the operational
       incumbent's own top-ranked ticket, so the arm starts from exactly the
       incumbent's information and only its geometry differs;
    2. repeatedly append the not-yet-selected candidate minimising the frozen
       key ``(max overlap with the selected set ASC, summed overlap with the
       selected set ASC, candidate_pool_index ASC)``.

    The minimax term caps the worst redundant pair, the minisum term breaks
    minimax plateaus, and the pool index makes every remaining tie exact, so
    the result is a pure function of the candidate pool. Greedy append makes
    the K buckets nested exactly as ``build_portfolio`` nests them, which keeps
    K10 a prefix of K20 for both the incumbent and this arm.
    """

    _require_allowed_k(k)
    pool = build_kdpp_candidate_pool(candidates)
    if pool.candidate_count < k:
        return _selection(
            "MIN_OVERLAP",
            pool,
            source,
            k,
            seed=None,
            status="INFEASIBLE_CANDIDATE_COUNT",
            sampling_order=(),
        )
    overlap = _overlap_counts(pool)
    chosen: list[int] = [0]
    remaining = set(range(1, pool.candidate_count))
    while len(chosen) < k:
        best_key: tuple[float, float, int] | None = None
        best_index = -1
        for index in sorted(remaining):
            pair = overlap[index, chosen]
            key = (float(pair.max()), float(pair.sum()), index)
            if best_key is None or key < best_key:
                best_key, best_index = key, index
        chosen.append(best_index)
        remaining.discard(best_index)
    sampling_order = tuple(chosen)
    return _selection(
        "MIN_OVERLAP",
        pool,
        source,
        k,
        seed=None,
        status="FEASIBLE",
        sampling_order=sampling_order,
        portfolio_order=tuple(sorted(sampling_order)),
    )


def _selection(
    arm: Arm,
    pool: CandidatePool,
    source: CausalSourceIdentity,
    k: int,
    *,
    seed: int | None,
    status: FeasibilityStatus,
    sampling_order: tuple[int, ...] | None = None,
    portfolio_order: tuple[int, ...] = (),
    min_relative_eigengap: float | None = None,
    failure_detail: str | None = None,
) -> ArmSelection:
    method_id, method_version = _ARM_METHODS[arm]
    selection = ArmSelection(
        arm=arm,
        method_id=method_id,
        method_version=method_version,
        source=source,
        k=k,
        candidate_count=pool.candidate_count,
        candidate_pool_sha256=pool.sha256,
        seed=seed,
        feasibility_status=status,
        sampling_order=sampling_order,
        portfolio_order=portfolio_order,
        tickets=tuple(pool.entries[index].ticket for index in portfolio_order),
        portfolio_sha256=None,
        numpy_version=np.__version__,
        lapack_backend=_lapack_backend_description(),
        min_relative_eigengap=min_relative_eigengap,
        failure_detail=failure_detail,
        reproducibility_claim=REPRODUCIBILITY_CLAIM,
    )
    if status != "FEASIBLE":
        return selection
    return replace(
        selection,
        portfolio_sha256=sha256_hex(canonical_bytes(selection.portfolio_manifest())),
    )


def _candidate_manifest(entries: Sequence[CandidatePoolEntry]) -> dict[str, object]:
    return {
        "schema_version": CANDIDATE_POOL_SCHEMA_VERSION,
        "candidate_order": ["SUPPORT_COUNT_DESC", "SUPPLIED_QUALITY_SUM_DESC", "TICKET_ASC"],
        "quality_by_strategy": {},
        "candidates": [
            {
                "candidate_pool_index": entry.candidate_pool_index,
                "ticket": list(entry.ticket),
                "supporters": list(entry.supporters),
                "support_count": entry.support_count,
            }
            for entry in entries
        ],
    }


def _overlap_counts(pool: CandidatePool) -> npt.NDArray[np.float64]:
    indicators = np.zeros((pool.candidate_count, MAX_NUMBER), dtype=np.float64)
    for row, entry in enumerate(pool.entries):
        indicators[row, [number - MIN_NUMBER for number in entry.ticket]] = 1.0
    return indicators @ indicators.T


def _min_relative_eigengap(
    eigenvalues: npt.NDArray[np.float64], rank_tolerance: float
) -> float | None:
    nonzero = np.sort(eigenvalues[eigenvalues > rank_tolerance])
    if nonzero.size < 2:
        return None
    return float(np.diff(nonzero).min() / nonzero[-1])


def _validate_ticket_domain(raw: Sequence[object], strategy_id: str) -> None:
    numbers = tuple(raw)
    if (
        len(numbers) != TICKET_SIZE
        or any(
            type(number) is not int or not MIN_NUMBER <= number <= MAX_NUMBER for number in numbers
        )
        or len(set(numbers)) != TICKET_SIZE
    ):
        raise ValueError(
            f"ticket from {strategy_id} must be {TICKET_SIZE} distinct integers in "
            f"[{MIN_NUMBER}, {MAX_NUMBER}]: {raw!r}"
        )


def _require_allowed_k(k: int) -> None:
    if type(k) is not int or k not in ALLOWED_K:
        raise ValueError(f"K must be one of {ALLOWED_K}, got {k!r}")


def _draw_number(value: str, name: str) -> int:
    if _DRAW_NUMBER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical decimal draw number, got {value!r}")
    return int(value)


def _iso_date(value: str, name: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a YYYY-MM-DD date, got {value!r}") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{name} must be a YYYY-MM-DD date, got {value!r}")
    return parsed


def _lapack_backend_description() -> str:
    try:
        dependencies = np.show_config(mode="dicts")["Build Dependencies"]
        blas = dependencies["blas"]
        lapack = dependencies["lapack"]
        return f"blas={blas['name']} {blas['version']}; lapack={lapack['name']} {lapack['version']}"
    except Exception:
        # Build introspection is descriptive only; its absence must not block selection.
        return "UNAVAILABLE"


__all__ = [
    "ALLOWED_K",
    "CANDIDATE_POOL_SCHEMA_VERSION",
    "EXPECTED_NUMPY_VERSION",
    "HISTORICAL_CAUSAL_REPLAY_V1",
    "HISTORY_FINGERPRINT",
    "HISTORY_IDENTITY_KIND_BY_SOURCE_MODE",
    "HISTORY_SHA256",
    "KDPP_METHOD_ID",
    "KDPP_METHOD_VERSION",
    "LIVE_PREDRAW_V1",
    "PORTFOLIO_SCHEMA_VERSION",
    "RANDOM_K_METHOD_ID",
    "RANDOM_K_METHOD_VERSION",
    "RAW_MAJORITY_METHOD_ID",
    "RAW_MAJORITY_METHOD_VERSION",
    "REPRODUCIBILITY_CLAIM",
    "Arm",
    "ArmSelection",
    "CandidatePool",
    "CausalSourceIdentity",
    "FeasibilityStatus",
    "build_kdpp_candidate_pool",
    "build_kdpp_kernel",
    "derive_arm_seed",
    "select_kdpp",
    "select_raw_majority_top_k",
    "select_seeded_random_k",
    "ticket_similarity_matrix",
]
