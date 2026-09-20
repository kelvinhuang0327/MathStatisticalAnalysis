"""Sealed uniform-geometry portfolios for the B649 operational K-buckets.

Under a fair BIG_LOTTO draw every single ticket has the same OFFICIAL_ANY_PRIZE
probability (``7729/249711``), so no ticket beats another one-for-one. What a
K-ticket set does change is how much its tickets overlap, and with it
P(at least one ticket wins). K10 and K20 are the P0c capture-gap solutions
authorized for production; K5 is the best-known disjoint construction. They
carry no predictive signal: they do not depend on the target draw, the
prediction streams, or any historical outcome. Their probabilities are exact
counts over the full outcome space, verified by
``lottolab.research.b649_official_any_prize_exact`` in
``tests/unit/test_b649_sealed_geometry_portfolio.py``.

Buckets are independently optimal per K, so they are deliberately NOT nested:
the best 10 tickets are not the first 10 of the best 20.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Final

type Ticket = tuple[int, ...]

SEALED_GEOMETRY_METHOD_ID: Final = "B649_SEALED_GEOMETRY_PORTFOLIO"
SEALED_GEOMETRY_METHOD_VERSION: Final = "1.0.0"
PROBABILITY_MODEL: Final = "BIG_LOTTO_UNIFORM_FAIR_DRAW"
PRIZE_EVENT: Final = "OFFICIAL_ANY_PRIZE"
POOL_SIZE: Final = 49
TICKET_SIZE: Final = 6


class SealedGeometryIntegrityError(ValueError):
    """A sealed portfolio no longer matches its recorded identity."""


@dataclass(frozen=True, slots=True)
class SealedGeometryPortfolio:
    """One sealed K-ticket portfolio and the exact evidence it was selected on."""

    ticket_count: int
    tickets: tuple[Ticket, ...]
    portfolio_sha256: str
    source_id: str
    source_locator: str
    source_sha256: str
    m3_plus_probability: Fraction
    official_any_prize_probability: Fraction

    def provenance(self) -> dict[str, object]:
        """Canonical-JSON-safe provenance (exact fractions as ``"n/d"`` text)."""

        return {
            "ticket_count": self.ticket_count,
            "portfolio_sha256": self.portfolio_sha256,
            "source_id": self.source_id,
            "source_locator": self.source_locator,
            "source_sha256": self.source_sha256,
            "m3_plus_probability": str(self.m3_plus_probability),
            "official_any_prize_probability": str(self.official_any_prize_probability),
        }


def canonical_portfolio_sha256(tickets: Sequence[Sequence[int]]) -> str:
    """Repository portfolio identity: SHA-256 of the compact JSON list of lists."""

    payload = json.dumps([list(ticket) for ticket in tickets], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# Reference E (GREEDY_MINMAX_THEN_SUM_OVERLAP_V1) method_e_20[:5]: five pairwise-disjoint
# tickets. Every family of five disjoint tickets is equivalent under relabeling, and this
# one reaches the sealed diversification-frontier best-found K5 M3+ (54130/582659) exactly.
_K5 = SealedGeometryPortfolio(
    ticket_count=5,
    tickets=(
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
        (19, 20, 21, 22, 23, 24),
        (25, 26, 27, 28, 29, 30),
    ),
    portfolio_sha256="ec858fe04075ee40931366c05617ad7d04d934c5f72ac35c9b74c26ba91f8d87",
    source_id="STRATEGY_MATRIX_REFERENCE_E_METHOD_E_20_PREFIX_K5",
    source_locator=(
        "docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-result.json"
    ),
    source_sha256="f2a48557dffb04a2ac13ed2b1286ef85bb5fffda97313728863680c67200ffec",
    m3_plus_probability=Fraction(54130, 582659),
    official_any_prize_probability=Fraction(547495, 3579191),
)

# P0c capture-gap search (B649_ANY_PRIZE_OBJECTIVE_CORRECTION_R1, 2026-09-19): the best
# K10 found; it beats the Phase-10 terminal K10 on exact OFFICIAL_ANY_PRIZE.
_K10 = SealedGeometryPortfolio(
    ticket_count=10,
    tickets=(
        (10, 17, 19, 23, 39, 48),
        (3, 6, 9, 13, 14, 49),
        (17, 26, 29, 34, 38, 40),
        (1, 11, 12, 18, 23, 40),
        (7, 37, 41, 42, 44, 45),
        (10, 11, 25, 29, 33, 47),
        (5, 8, 15, 24, 30, 31),
        (2, 18, 33, 35, 38, 39),
        (16, 20, 27, 28, 42, 46),
        (4, 21, 22, 32, 36, 43),
    ),
    portfolio_sha256="d73f37721e3378deb024e4b762a915dbfa125d462605c293bc764fef7ea487c2",
    source_id="B649_ANY_PRIZE_OBJECTIVE_CORRECTION_R1_P0C_CAPTURE_GAP_K10",
    source_locator=".task-data/B649_ANY_PRIZE_OBJECTIVE_CORRECTION_R1/p0c_capture_gap.json",
    source_sha256="8ae997ec1ed504b93fd80e5113660973774cd5d9fe6054d0989312940b942211",
    m3_plus_probability=Fraction(364025, 1997688),
    official_any_prize_probability=Fraction(1095245, 3734808),
)

# P0c capture-gap search, K20: the portfolio authorized for production. The Phase-10
# terminal one-exchange optimum scores slightly higher (7439615/14316764) but is a
# research reference comparator that is not authorized for production promotion.
_K20 = SealedGeometryPortfolio(
    ticket_count=20,
    tickets=(
        (8, 16, 19, 29, 38, 40),
        (5, 17, 23, 25, 42, 44),
        (1, 5, 30, 33, 39, 49),
        (7, 13, 15, 40, 43, 46),
        (9, 12, 20, 23, 30, 31),
        (8, 26, 27, 43, 45, 48),
        (8, 11, 14, 15, 36, 41),
        (3, 20, 27, 28, 37, 42),
        (14, 25, 34, 35, 39, 45),
        (11, 13, 24, 29, 45, 47),
        (18, 28, 29, 35, 41, 48),
        (1, 10, 12, 21, 24, 42),
        (6, 21, 22, 23, 37, 49),
        (11, 17, 19, 33, 34, 48),
        (16, 26, 34, 41, 46, 47),
        (3, 18, 22, 24, 32, 38),
        (1, 4, 6, 20, 32, 44),
        (2, 7, 25, 31, 33, 36),
        (2, 3, 4, 5, 9, 21),
        (10, 13, 19, 26, 35, 36),
    ),
    portfolio_sha256="a0126d34589f82945f5f8895b8812818293a2c04a957ab0a940eaff09fd70332",
    source_id="B649_ANY_PRIZE_OBJECTIVE_CORRECTION_R1_P0C_CAPTURE_GAP_K20",
    source_locator=".task-data/B649_ANY_PRIZE_OBJECTIVE_CORRECTION_R1/p0c_capture_gap.json",
    source_sha256="8ae997ec1ed504b93fd80e5113660973774cd5d9fe6054d0989312940b942211",
    m3_plus_probability=Fraction(2401225, 6991908),
    official_any_prize_probability=Fraction(44615213, 85900584),
)

SEALED_GEOMETRY_PORTFOLIOS: Final[Mapping[int, SealedGeometryPortfolio]] = MappingProxyType(
    {entry.ticket_count: entry for entry in (_K5, _K10, _K20)}
)


def verify_sealed_geometry_portfolio(entry: SealedGeometryPortfolio) -> None:
    """Re-check a sealed portfolio's legality and identity; raise on any drift."""

    tickets = entry.tickets
    if len(tickets) != entry.ticket_count or len(set(tickets)) != entry.ticket_count:
        raise SealedGeometryIntegrityError(
            f"K{entry.ticket_count}: sealed portfolio has invalid cardinality or duplicates"
        )
    for ticket in tickets:
        if (
            len(ticket) != TICKET_SIZE
            or list(ticket) != sorted(set(ticket))
            or any(type(number) is not int or not 1 <= number <= POOL_SIZE for number in ticket)
        ):
            raise SealedGeometryIntegrityError(
                f"K{entry.ticket_count}: sealed ticket is illegal: {ticket}"
            )
    if canonical_portfolio_sha256(tickets) != entry.portfolio_sha256:
        raise SealedGeometryIntegrityError(
            f"K{entry.ticket_count}: sealed portfolio identity does not match its digest"
        )


def sealed_geometry_buckets(bucket_sizes: Sequence[int]) -> dict[int, tuple[Ticket, ...]]:
    """Return the verified sealed tickets for every requested K."""

    buckets: dict[int, tuple[Ticket, ...]] = {}
    for size in bucket_sizes:
        entry = SEALED_GEOMETRY_PORTFOLIOS.get(size)
        if entry is None:
            raise SealedGeometryIntegrityError(f"no sealed geometry portfolio for K{size}")
        verify_sealed_geometry_portfolio(entry)
        buckets[size] = entry.tickets
    return buckets


__all__ = [
    "PRIZE_EVENT",
    "PROBABILITY_MODEL",
    "SEALED_GEOMETRY_METHOD_ID",
    "SEALED_GEOMETRY_METHOD_VERSION",
    "SEALED_GEOMETRY_PORTFOLIOS",
    "SealedGeometryIntegrityError",
    "SealedGeometryPortfolio",
    "canonical_portfolio_sha256",
    "sealed_geometry_buckets",
    "verify_sealed_geometry_portfolio",
]
