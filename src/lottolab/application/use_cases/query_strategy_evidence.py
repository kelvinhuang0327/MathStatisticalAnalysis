"""Query canonical evidence availability without replay or derived ranking logic."""

from __future__ import annotations

from lottolab.application.dto import (
    D3AvailabilityBlock,
    StrategyCombinationHitRateBlock,
    StrategyEvidenceBestStrategyBlock,
    StrategyEvidenceItem,
    StrategyEvidenceResponse,
)
from lottolab.application.ports import StrategyEvidenceRegistryReader
from lottolab.application.strategy_evidence import (
    CanonicalEvidenceIdentity,
    DefinitionAvailabilityStatus,
    EvidenceRegistrationStatus,
    EvidenceVerificationStatus,
)
from lottolab.strategies.catalog import StrategyCatalog


class QueryStrategyEvidence:
    def __init__(
        self,
        catalog: StrategyCatalog,
        registry_reader: StrategyEvidenceRegistryReader,
    ) -> None:
        self._catalog = catalog
        self._registry_reader = registry_reader

    def execute(self) -> StrategyEvidenceResponse:
        snapshot = self._registry_reader.read()
        items: list[StrategyEvidenceItem] = []
        for descriptor in self._catalog.list():
            identity = CanonicalEvidenceIdentity(
                strategy_id=descriptor.strategy_id,
                strategy_version=descriptor.version,
                replicate=None,
            )
            registered = identity in snapshot.identities
            items.append(
                StrategyEvidenceItem(
                    strategy_id=descriptor.strategy_id,
                    strategy_version=descriptor.version,
                    replicate="NOT_APPLICABLE",
                    display_name=descriptor.strategy_name,
                    lifecycle_status=descriptor.lifecycle_status,
                    executable=descriptor.executable,
                    supported_lottery_types=descriptor.lottery_types,
                    minimum_history=descriptor.min_history,
                    provenance=descriptor.provenance,
                    adapter_available=descriptor.adapter_path is not None,
                    registration_status=(
                        EvidenceRegistrationStatus.REGISTERED
                        if registered
                        else EvidenceRegistrationStatus.MISSING
                    ),
                    definition_status=DefinitionAvailabilityStatus.AVAILABLE,
                    verification_status=(
                        EvidenceVerificationStatus.DECLARED_NOT_RECOMPUTED
                        if registered
                        else EvidenceVerificationStatus.MISSING
                    ),
                    unavailable_reason_code=(
                        None
                        if registered
                        else "NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE"
                    ),
                )
            )
        return StrategyEvidenceResponse(
            items=tuple(items),
            best_strategy=StrategyEvidenceBestStrategyBlock(
                status="UNAVAILABLE",
                reason="NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE",
            ),
            strategy_combination_hit_rate=StrategyCombinationHitRateBlock(
                status="EXCLUDED_ACTIVE_MULTITICKET_SCOPE",
                value="NOT_AVAILABLE",
                owner="ACTIVE_MULTITICKET_AGENT",
            ),
            d3=D3AvailabilityBlock(
                status=snapshot.d3_status,
                value="NOT_AVAILABLE",
            ),
        )
