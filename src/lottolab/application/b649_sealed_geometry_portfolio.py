"""Sealed uniform-geometry portfolios for the B649 operational K-buckets.

Under a fair BIG_LOTTO draw every single ticket has the same OFFICIAL_ANY_PRIZE
probability (``7729/249711``), so no ticket beats another one-for-one. What a
K-ticket set does change is how much its tickets overlap, and with it
P(at least one ticket wins). K5 is pairwise disjoint. For both OFFICIAL_ANY_PRIZE
and M3_PLUS, every pairwise-disjoint portfolio of size 1..8 attains the global
optimum proved in ``lottolab.research.b649_k1_k8_global_optimality``; that
optimum is not unique. K10 remains the frozen HARD_DIV pairwise-overlap
radius2 authority from sealed-geometry v2.
K10 OFFICIAL_ANY_PRIZE: PROVEN GLOBAL OPTIMUM by the canonical K10 proof
certificate. K10 M3_PLUS: GLOBAL OPTIMUM UNKNOWN. The v8 K20 is the exact
incumbent from the canonical two-ticket ascent result, with v7 retained in
the portfolio version history.
It is proven optimal only within its validated exact local neighborhoods.
K20 global optimality remains unknown.
K20: GLOBAL OPTIMUM UNKNOWN.
There is no historical outcome tuning or predictive signal: the portfolios do
not depend on the target draw, prediction streams, or historical outcomes.
Their probabilities are exact counts over the full outcome space, verified by
``lottolab.research.b649_official_any_prize_exact`` in
``tests/unit/test_b649_sealed_geometry_portfolio.py``.

Buckets are selected independently per K and are deliberately NOT nested:
the K10 tickets are not the first 10 of K20.
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
SEALED_GEOMETRY_METHOD_VERSION: Final = "8.0.0"
K20_V7_PORTFOLIO_VERSION: Final = "7.0.0"
K20_PORTFOLIO_VERSION: Final = "8.0.0"
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
    portfolio_version: str | None = None
    source_revision: str | None = None

    def provenance(self) -> dict[str, object]:
        """Canonical-JSON-safe provenance (exact fractions as ``"n/d"`` text)."""

        provenance: dict[str, object] = {
            "ticket_count": self.ticket_count,
            "portfolio_sha256": self.portfolio_sha256,
            "source_id": self.source_id,
            "source_locator": self.source_locator,
            "source_sha256": self.source_sha256,
            "m3_plus_probability": str(self.m3_plus_probability),
            "official_any_prize_probability": str(self.official_any_prize_probability),
        }
        if self.portfolio_version is not None:
            provenance["portfolio_version"] = self.portfolio_version
        if self.source_revision is not None:
            provenance["source_revision"] = self.source_revision
        return provenance


def canonical_portfolio_sha256(tickets: Sequence[Sequence[int]]) -> str:
    """Repository portfolio identity: SHA-256 of the compact JSON list of lists."""

    payload = json.dumps([list(ticket) for ticket in tickets], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# Reference E (GREEDY_MINMAX_THEN_SUM_OVERLAP_V1) method_e_20[:5]: five pairwise-disjoint
# tickets. Every such K5 portfolio has the same OFFICIAL_ANY_PRIZE and M3+ probabilities.
# This one is a proven global optimum for both events (ANY 547495/3579191, M3+ 54130/582659).
# The optimum is not unique.
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

# Frozen HARD_DIV pairwise-overlap radius2 authority selected by the canonical
# OFFICIAL_ANY_PRIZE frontier for sealed-geometry v2.
_K10 = SealedGeometryPortfolio(
    ticket_count=10,
    tickets=(
        (1, 2, 4, 8, 13, 21),
        (3, 6, 10, 15, 23, 42),
        (4, 5, 7, 11, 16, 24),
        (5, 8, 12, 17, 18, 25),
        (7, 13, 18, 26, 29, 41),
        (9, 11, 20, 28, 40, 44),
        (12, 16, 21, 29, 32, 36),
        (14, 22, 31, 37, 45, 47),
        (19, 27, 33, 34, 35, 43),
        (30, 38, 39, 46, 48, 49),
    ),
    portfolio_sha256="13b1126d5b26ce44c9aba24670142eeab49f4a4b51aaf3bbabe7a7f1659ac673",
    source_id="HARD_DIV_PAIRWISE_OVERLAP_R1_K10_RADIUS2",
    source_locator=(
        "docs/research/matrix-native-results/"
        "b649-official-any-prize-frontier-reconciliation-r1/frontier_reconciliation.json"
    ),
    source_sha256="5b0ccf7485c3db699b9bb9e398f04857d018ec7b1ca87700f86cbace5a719d3e",
    m3_plus_probability=Fraction(364025, 1997688),
    official_any_prize_probability=Fraction(536005, 1827672),
)

# Historical K20 v7 remains available so its identity and evidence are not
# silently redefined when the default portfolio advances.
_K20_V7 = SealedGeometryPortfolio(
    ticket_count=20,
    tickets=(
        (1, 2, 34, 41, 42, 45),
        (1, 17, 22, 30, 33, 43),
        (2, 5, 33, 35, 40, 48),
        (3, 4, 10, 15, 26, 27),
        (3, 8, 13, 28, 31, 36),
        (3, 9, 12, 16, 29, 39),
        (4, 7, 36, 39, 46, 49),
        (4, 18, 20, 24, 28, 29),
        (5, 17, 25, 32, 41, 47),
        (6, 7, 9, 13, 18, 26),
        (6, 10, 11, 16, 24, 36),
        (6, 14, 20, 31, 37, 39),
        (7, 8, 10, 14, 19, 29),
        (8, 9, 11, 15, 20, 46),
        (11, 12, 18, 23, 27, 49),
        (13, 15, 19, 24, 37, 49),
        (16, 19, 23, 26, 28, 46),
        (21, 25, 30, 38, 45, 48),
        (21, 32, 40, 42, 43, 44),
        (22, 34, 35, 38, 44, 47),
    ),
    portfolio_sha256="0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff",
    source_id="B649_K20_EXACT_TWO_TICKET_JOINT_REPLACEMENT_SWEEP_R1",
    source_locator=(
        "docs/research/matrix-native-results/"
        "b649-k20-exact-two-ticket-joint-replacement-terminal-r1.json"
    ),
    source_sha256="e7698ff0d76a91c69378bf9bf0badb4ed9ac4f4dd146c71e5c94300bcfbbff9e",
    m3_plus_probability=Fraction(4807367, 13983816),
    official_any_prize_probability=Fraction(44748523, 85900584),
)

# Canonical exact K20 incumbent from the two-ticket ascent result. The result
# proves the validated exact two-ticket neighborhood; global optimality is
# unknown. No historical outcomes were used for tuning.
_K20 = SealedGeometryPortfolio(
    ticket_count=20,
    tickets=(
        (1, 2, 3, 4, 5, 21),
        (1, 6, 7, 8, 9, 22),
        (1, 11, 14, 18, 19, 26),
        (2, 7, 14, 16, 17, 24),
        (2, 10, 11, 12, 13, 22),
        (3, 6, 10, 14, 15, 23),
        (3, 8, 13, 17, 20, 26),
        (4, 6, 12, 19, 20, 24),
        (4, 8, 10, 16, 18, 25),
        (5, 7, 11, 15, 20, 25),
        (5, 9, 12, 17, 18, 23),
        (9, 13, 15, 16, 19, 21),
        (27, 29, 30, 31, 32, 33),
        (27, 34, 35, 36, 37, 38),
        (27, 39, 40, 41, 42, 43),
        (28, 29, 34, 39, 44, 45),
        (28, 30, 35, 40, 46, 47),
        (28, 31, 36, 41, 48, 49),
        (32, 37, 42, 44, 46, 48),
        (33, 38, 43, 45, 47, 49),
    ),
    portfolio_sha256="eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c",
    source_id="B649_K20_12_8_WINNER_TWO_TICKET_ASCENT_R1",
    source_locator=(
        "docs/research/matrix-native-results/"
        "b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
    ),
    source_sha256="3d5d3f8f2389b66a9b2c45b0e345b81a0d9dc59d08ca9223519be70a055e5a00",
    m3_plus_probability=Fraction(1201973, 3495954),
    official_any_prize_probability=Fraction(1864666, 3579191),
    portfolio_version=K20_PORTFOLIO_VERSION,
    source_revision="da26b434499927f5611e3c3d12e50485f2e58a6a",
)

SEALED_GEOMETRY_K20_VERSIONS: Final[Mapping[str, SealedGeometryPortfolio]] = MappingProxyType(
    {
        K20_V7_PORTFOLIO_VERSION: _K20_V7,
        K20_PORTFOLIO_VERSION: _K20,
    }
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
    "K20_PORTFOLIO_VERSION",
    "K20_V7_PORTFOLIO_VERSION",
    "PRIZE_EVENT",
    "PROBABILITY_MODEL",
    "SEALED_GEOMETRY_K20_VERSIONS",
    "SEALED_GEOMETRY_METHOD_ID",
    "SEALED_GEOMETRY_METHOD_VERSION",
    "SEALED_GEOMETRY_PORTFOLIOS",
    "SealedGeometryIntegrityError",
    "SealedGeometryPortfolio",
    "canonical_portfolio_sha256",
    "sealed_geometry_buckets",
    "verify_sealed_geometry_portfolio",
]
