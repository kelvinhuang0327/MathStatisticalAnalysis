"""Read the committed canonical-evidence registry and D3 definition lazily."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from lottolab.application.strategy_evidence import (
    CanonicalEvidenceIdentity,
    D3AvailabilityStatus,
    StrategyEvidenceRegistrySnapshot,
    StrategyEvidenceRegistryUnavailableError,
)


class CommittedStrategyEvidenceRegistry:
    def __init__(self, registry: Path, d3_definition: Path) -> None:
        self._registry = registry
        self._d3_definition = d3_definition

    @classmethod
    def from_repository(cls, repository: Path) -> CommittedStrategyEvidenceRegistry:
        evidence = repository / "contracts" / "evidence"
        return cls(
            evidence / "canonical_evidence_registry.json",
            evidence / "metric_definitions" / "d3.json",
        )

    @classmethod
    def default(cls) -> CommittedStrategyEvidenceRegistry:
        return cls.from_repository(Path(__file__).resolve().parents[3])

    def read(self) -> StrategyEvidenceRegistrySnapshot:
        try:
            registry: object = json.loads(self._registry.read_text(encoding="utf-8"))
            d3: object = json.loads(self._d3_definition.read_text(encoding="utf-8"))
            identities = _registry_identities(registry)
            d3_status = _d3_status(d3)
        except StrategyEvidenceRegistryUnavailableError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise StrategyEvidenceRegistryUnavailableError(
                "committed strategy evidence registry is unavailable"
            ) from exc
        return StrategyEvidenceRegistrySnapshot(
            identities=frozenset(identities),
            d3_status=d3_status,
        )


def _registry_identities(payload: object) -> set[CanonicalEvidenceIdentity]:
    if not isinstance(payload, dict):
        raise StrategyEvidenceRegistryUnavailableError("canonical registry is invalid")
    mapping = cast(dict[object, object], payload)
    if mapping.get("schema_id") != "lottolab.evidence.canonical_evidence_registry":
        raise StrategyEvidenceRegistryUnavailableError("canonical registry is invalid")
    entries = mapping.get("entries")
    if not isinstance(entries, list):
        raise StrategyEvidenceRegistryUnavailableError("canonical registry is invalid")
    identities: set[CanonicalEvidenceIdentity] = set()
    for raw in cast(list[object], entries):
        if not isinstance(raw, dict):
            raise StrategyEvidenceRegistryUnavailableError("canonical registry entry is invalid")
        entry = cast(dict[object, object], raw)
        strategy_id = entry.get("strategy_id")
        strategy_version = entry.get("strategy_version")
        replicate = entry.get("replicate")
        if not isinstance(strategy_id, str) or not strategy_id:
            raise StrategyEvidenceRegistryUnavailableError("canonical registry entry is invalid")
        if not isinstance(strategy_version, str) or not strategy_version:
            raise StrategyEvidenceRegistryUnavailableError("canonical registry entry is invalid")
        if replicate is not None and (type(replicate) is not int or replicate < 0):
            raise StrategyEvidenceRegistryUnavailableError("canonical registry entry is invalid")
        identities.add(
            CanonicalEvidenceIdentity(
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                replicate=replicate,
            )
        )
    return identities


def _d3_status(payload: object) -> D3AvailabilityStatus:
    if not isinstance(payload, dict):
        return D3AvailabilityStatus.DEFINITION_MISSING
    mapping = cast(dict[object, object], payload)
    if mapping.get("metric_id") != "D3":
        return D3AvailabilityStatus.DEFINITION_MISSING
    formula_status = mapping.get("formula_status")
    if formula_status == "RESERVED_UNAVAILABLE":
        return D3AvailabilityStatus.RESERVED_UNAVAILABLE
    return D3AvailabilityStatus.EVIDENCE_MISSING


__all__ = ["CommittedStrategyEvidenceRegistry"]
