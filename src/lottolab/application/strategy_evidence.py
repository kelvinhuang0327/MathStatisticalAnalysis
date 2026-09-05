"""Read models for canonical strategy-evidence and D3 availability."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EvidenceRegistrationStatus(StrEnum):
    REGISTERED = "CANONICAL_EVIDENCE_REGISTERED"
    MISSING = "CANONICAL_EVIDENCE_MISSING"


class DefinitionAvailabilityStatus(StrEnum):
    AVAILABLE = "DEFINITION_AVAILABLE"
    UNAVAILABLE = "DEFINITION_UNAVAILABLE"


class EvidenceVerificationStatus(StrEnum):
    VERIFIED = "EVIDENCE_VERIFIED"
    DECLARED_NOT_RECOMPUTED = "EVIDENCE_DECLARED_NOT_RECOMPUTED"
    STALE = "EVIDENCE_STALE"
    INCOMPATIBLE = "EVIDENCE_INCOMPATIBLE"
    MISSING = "EVIDENCE_MISSING"


class D3AvailabilityStatus(StrEnum):
    RESERVED_UNAVAILABLE = "RESERVED_UNAVAILABLE"
    DEFINITION_MISSING = "DEFINITION_MISSING"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    VALUE_UNVERIFIED = "VALUE_UNVERIFIED"
    VALUE_PRESENT = "VALUE_PRESENT"
    STALE = "STALE"
    INCOMPATIBLE = "INCOMPATIBLE"


@dataclass(frozen=True, slots=True)
class CanonicalEvidenceIdentity:
    strategy_id: str
    strategy_version: str
    replicate: int | None


@dataclass(frozen=True, slots=True)
class D3DefinitionSnapshot:
    metric_id: str
    metric_version: str
    schema_id: str
    schema_version: str
    formula_status: str
    direction: str
    aggregation: str
    sample_unit: str
    decimal_scale: int
    rounding_mode: str
    unit: str
    definition_prose: str
    authority_path: str


@dataclass(frozen=True, slots=True)
class StrategyEvidenceRegistrySnapshot:
    identities: frozenset[CanonicalEvidenceIdentity]
    d3_status: D3AvailabilityStatus
    d3_definition: D3DefinitionSnapshot


class StrategyEvidenceRegistryUnavailableError(RuntimeError):
    """Committed evidence registry or D3 definition could not be read safely."""
