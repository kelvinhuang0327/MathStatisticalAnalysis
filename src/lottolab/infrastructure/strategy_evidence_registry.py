"""Read the committed canonical-evidence registry and D3 definition lazily."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from lottolab.application.strategy_evidence import (
    CanonicalEvidenceIdentity,
    D3AvailabilityStatus,
    D3DefinitionSnapshot,
    StrategyEvidenceRegistrySnapshot,
    StrategyEvidenceRegistryUnavailableError,
)

#: Repo-relative locator for the canonical D3 definition, exposed to API consumers
#: so the frontend never needs its own copy of this path.
_D3_DEFINITION_AUTHORITY_PATH = "contracts/evidence/metric_definitions/d3.json"


class CommittedStrategyEvidenceRegistry:
    def __init__(
        self,
        registry: Path,
        d3_definition: Path,
        d3_authority_path: str = _D3_DEFINITION_AUTHORITY_PATH,
    ) -> None:
        self._registry = registry
        self._d3_definition = d3_definition
        self._d3_authority_path = d3_authority_path

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
            d3_definition = _d3_definition_snapshot(d3, self._d3_authority_path)
        except StrategyEvidenceRegistryUnavailableError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise StrategyEvidenceRegistryUnavailableError(
                "committed strategy evidence registry is unavailable"
            ) from exc
        return StrategyEvidenceRegistrySnapshot(
            identities=frozenset(identities),
            d3_status=d3_status,
            d3_definition=d3_definition,
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


def _d3_definition_snapshot(payload: object, authority_path: str) -> D3DefinitionSnapshot:
    if not isinstance(payload, dict):
        raise StrategyEvidenceRegistryUnavailableError("D3 definition is invalid")
    mapping = cast(dict[object, object], payload)

    metric_id = mapping.get("metric_id")
    metric_version = mapping.get("metric_version")
    schema_id = mapping.get("schema_id")
    schema_version = mapping.get("schema_version")
    formula_status = mapping.get("formula_status")
    direction = mapping.get("direction")
    aggregation = mapping.get("aggregation")
    sample_unit = mapping.get("sample_unit")
    decimal_scale = mapping.get("decimal_scale")
    rounding_mode = mapping.get("rounding_mode")
    unit = mapping.get("unit")
    definition_prose = mapping.get("definition_prose")

    if not isinstance(metric_id, str) or metric_id != "D3":
        raise StrategyEvidenceRegistryUnavailableError("D3 definition is invalid")
    if not isinstance(metric_version, str) or not metric_version:
        raise StrategyEvidenceRegistryUnavailableError("D3 definition is invalid")
    if not isinstance(schema_id, str) or schema_id != "lottolab.evidence.metric_definition":
        raise StrategyEvidenceRegistryUnavailableError("D3 definition is invalid")
    if not isinstance(schema_version, str) or not schema_version:
        raise StrategyEvidenceRegistryUnavailableError("D3 definition is invalid")
    if not isinstance(formula_status, str):
        raise StrategyEvidenceRegistryUnavailableError("D3 definition is invalid")
    if not isinstance(direction, str):
        raise StrategyEvidenceRegistryUnavailableError("D3 definition is invalid")
    if not isinstance(aggregation, str):
        raise StrategyEvidenceRegistryUnavailableError("D3 definition is invalid")
    if not isinstance(sample_unit, str):
        raise StrategyEvidenceRegistryUnavailableError("D3 definition is invalid")
    if type(decimal_scale) is not int or decimal_scale < 0:
        raise StrategyEvidenceRegistryUnavailableError("D3 definition is invalid")
    if not isinstance(rounding_mode, str):
        raise StrategyEvidenceRegistryUnavailableError("D3 definition is invalid")
    if not isinstance(unit, str):
        raise StrategyEvidenceRegistryUnavailableError("D3 definition is invalid")
    if not isinstance(definition_prose, str) or not definition_prose:
        raise StrategyEvidenceRegistryUnavailableError("D3 definition is invalid")

    return D3DefinitionSnapshot(
        metric_id=metric_id,
        metric_version=metric_version,
        schema_id=schema_id,
        schema_version=schema_version,
        formula_status=formula_status,
        direction=direction,
        aggregation=aggregation,
        sample_unit=sample_unit,
        decimal_scale=decimal_scale,
        rounding_mode=rounding_mode,
        unit=unit,
        definition_prose=definition_prose,
        authority_path=authority_path,
    )


__all__ = ["CommittedStrategyEvidenceRegistry"]
