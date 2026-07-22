"""Immutable cross-game contracts for strategy-success measurement.

The types in this module preserve measurement identity and validation only.
They do not load history, score tickets, promote strategies, or implement
official prize tables.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import StrEnum

from lottolab.domain.draws import LotteryType

DEFAULT_WINDOW_POLICY_VERSION = "STRATEGY_SUCCESS_WINDOWS_V1"


class MeasurementMode(StrEnum):
    """The mutually exclusive meaning of one measurement result."""

    CANDIDATE_COVERAGE = "CANDIDATE_COVERAGE"
    LEGAL_TICKET_PRIZE = "LEGAL_TICKET_PRIZE"
    OFFICIAL_PRIZE_TIER = "OFFICIAL_PRIZE_TIER"


class EvidenceStatus(StrEnum):
    """Evidence classification only; no status triggers promotion behavior."""

    DESCRIPTIVE_ONLY = "DESCRIPTIVE_ONLY"
    HISTORICAL_OOS_VERIFIED = "HISTORICAL_OOS_VERIFIED"
    CROSS_GAME_VERIFIED = "CROSS_GAME_VERIFIED"
    SHADOW_CAPTURE = "SHADOW_CAPTURE"
    PRODUCTION_ELIGIBLE = "PRODUCTION_ELIGIBLE"
    REJECTED = "REJECTED"
    NOT_READY = "NOT_READY"


class WindowRole(StrEnum):
    REFERENCE_ONLY = "REFERENCE_ONLY"
    PRIMARY_EVIDENCE = "PRIMARY_EVIDENCE"
    STABILITY_CONFIRMATION = "STABILITY_CONFIRMATION"
    DEGRADATION_VETO = "DEGRADATION_VETO"
    PROMOTION_FILTER = "PROMOTION_FILTER"


class OutcomeEligibility(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    MISSING_PREDICTED_SECOND_ZONE = "MISSING_PREDICTED_SECOND_ZONE"


def _require_optional_text(value: str | None, field_name: str) -> None:
    if value is not None and (type(value) is not str or not value.strip()):
        raise ValueError(f"{field_name} must be absent or a non-empty string")


def _require_positive_optional(value: int | None, field_name: str) -> None:
    if value is not None and (type(value) is not int or value <= 0):
        raise ValueError(f"{field_name} must be absent or a positive integer")


@dataclass(frozen=True, slots=True)
class SelectionIdentity:
    """The independent identity axes of one strategy selection."""

    lottery: LotteryType
    strategy_id: str
    strategy_version: str | None = None
    candidate_k: int | None = None
    max_bet_index: int | None = None
    ticket_count: int | None = None
    cost_units: int | float | None = None

    def __post_init__(self) -> None:
        if type(self.lottery) is not LotteryType:
            raise ValueError("lottery must be a LotteryType")
        if type(self.strategy_id) is not str or not self.strategy_id.strip():
            raise ValueError("strategy_id must be a non-empty string")
        _require_optional_text(self.strategy_version, "strategy_version")
        _require_positive_optional(self.candidate_k, "candidate_k")
        _require_positive_optional(self.max_bet_index, "max_bet_index")
        _require_positive_optional(self.ticket_count, "ticket_count")
        if self.cost_units is not None:
            if type(self.cost_units) not in (int, float):
                raise ValueError("cost_units must be absent or a finite non-negative number")
            if not math.isfinite(self.cost_units) or self.cost_units < 0:
                raise ValueError("cost_units must be absent or a finite non-negative number")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "candidate_k": self.candidate_k,
            "cost_units": self.cost_units,
            "lottery": self.lottery.value,
            "max_bet_index": self.max_bet_index,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "ticket_count": self.ticket_count,
        }


@dataclass(frozen=True, slots=True)
class MeasurementWindowPolicy:
    """Versioned roles for nested full/750/300/50-draw evidence windows."""

    policy_version: str = DEFAULT_WINDOW_POLICY_VERSION
    full_history_role: WindowRole = WindowRole.REFERENCE_ONLY
    long_draws: int = 750
    long_role: WindowRole = WindowRole.PRIMARY_EVIDENCE
    medium_draws: int = 300
    medium_role: WindowRole = WindowRole.STABILITY_CONFIRMATION
    short_draws: int = 50
    short_role: WindowRole = WindowRole.DEGRADATION_VETO
    nested_windows_independent: bool = False

    def __post_init__(self) -> None:
        if type(self.policy_version) is not str or not self.policy_version.strip():
            raise ValueError("policy_version must be a non-empty string")
        for name in ("full_history_role", "long_role", "medium_role", "short_role"):
            if type(getattr(self, name)) is not WindowRole:
                raise ValueError(f"{name} must be a WindowRole")
        for name in ("long_draws", "medium_draws", "short_draws"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not self.long_draws > self.medium_draws > self.short_draws:
            raise ValueError("window sizes must satisfy long > medium > short > 0")
        if self.full_history_role is not WindowRole.REFERENCE_ONLY:
            raise ValueError("full history must remain REFERENCE_ONLY")
        if self.short_role in (WindowRole.PRIMARY_EVIDENCE, WindowRole.PROMOTION_FILTER):
            raise ValueError("the short window cannot independently promote a strategy")
        if type(self.nested_windows_independent) is not bool:
            raise ValueError("nested_windows_independent must be a boolean")
        if self.nested_windows_independent:
            raise ValueError("nested 750/300/50 windows are not independent replications")

        default_shape = (
            WindowRole.REFERENCE_ONLY,
            750,
            WindowRole.PRIMARY_EVIDENCE,
            300,
            WindowRole.STABILITY_CONFIRMATION,
            50,
            WindowRole.DEGRADATION_VETO,
            False,
        )
        actual_shape = (
            self.full_history_role,
            self.long_draws,
            self.long_role,
            self.medium_draws,
            self.medium_role,
            self.short_draws,
            self.short_role,
            self.nested_windows_independent,
        )
        if self.policy_version == DEFAULT_WINDOW_POLICY_VERSION and actual_shape != default_shape:
            raise ValueError("custom window values require a new policy_version")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "full_history_role": self.full_history_role.value,
            "long_draws": self.long_draws,
            "long_role": self.long_role.value,
            "medium_draws": self.medium_draws,
            "medium_role": self.medium_role.value,
            "nested_windows_independent": self.nested_windows_independent,
            "policy_version": self.policy_version,
            "short_draws": self.short_draws,
            "short_role": self.short_role.value,
        }


DEFAULT_WINDOW_POLICY = MeasurementWindowPolicy()


@dataclass(frozen=True, slots=True)
class BigLottoOutcomeSignature:
    main_hits: int
    special_hit: bool

    def __post_init__(self) -> None:
        if type(self.main_hits) is not int or not 0 <= self.main_hits <= 6:
            raise ValueError("main_hits must be an integer between 0 and 6")
        if type(self.special_hit) is not bool:
            raise ValueError("special_hit must be a boolean")
        if self.main_hits + int(self.special_hit) > 6:
            raise ValueError("Big Lotto hit signature exceeds the six-number selection")

    @property
    def diagnostic_signature(self) -> str:
        suffix = "+SPECIAL" if self.special_hit else ""
        return f"M{self.main_hits}{suffix}"

    def canonical_dict(self) -> dict[str, object]:
        return {
            "diagnostic_signature": self.diagnostic_signature,
            "main_hits": self.main_hits,
            "special_hit": self.special_hit,
        }


@dataclass(frozen=True, slots=True)
class BigLottoPortfolioOutcomeSignature:
    """Source-ordered atomic outcomes for one legal-ticket portfolio."""

    tickets: tuple[BigLottoOutcomeSignature, ...]

    def __post_init__(self) -> None:
        if type(self.tickets) is not tuple:
            raise ValueError("tickets must be an immutable tuple")
        if not self.tickets:
            raise ValueError("tickets must not be empty")
        if any(type(ticket) is not BigLottoOutcomeSignature for ticket in self.tickets):
            raise ValueError("tickets must contain only BigLottoOutcomeSignature values")

    @property
    def ticket_count(self) -> int:
        return len(self.tickets)

    @property
    def maximum_main_hits(self) -> int:
        return max(ticket.main_hits for ticket in self.tickets)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "maximum_main_hits": self.maximum_main_hits,
            "ticket_count": self.ticket_count,
            "tickets": [ticket.canonical_dict() for ticket in self.tickets],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


@dataclass(frozen=True, slots=True)
class PowerLottoOutcomeSignature:
    zone1_hits: int
    zone2_hit: bool | None
    eligibility: OutcomeEligibility = OutcomeEligibility.ELIGIBLE

    def __post_init__(self) -> None:
        if type(self.zone1_hits) is not int or not 0 <= self.zone1_hits <= 6:
            raise ValueError("zone1_hits must be an integer between 0 and 6")
        if type(self.eligibility) is not OutcomeEligibility:
            raise ValueError("eligibility must be an OutcomeEligibility")
        if self.eligibility is OutcomeEligibility.ELIGIBLE:
            if type(self.zone2_hit) is not bool:
                raise ValueError("an eligible Power Lotto outcome requires a boolean zone2_hit")
        elif self.zone2_hit is not None:
            raise ValueError("missing predicted second-zone data requires zone2_hit=None")

    @property
    def diagnostic_signature(self) -> str:
        if self.zone2_hit is None:
            return f"ZONE1_M{self.zone1_hits}+ZONE2_MISSING"
        suffix = "+ZONE2" if self.zone2_hit else ""
        return f"ZONE1_M{self.zone1_hits}{suffix}"

    def canonical_dict(self) -> dict[str, object]:
        return {
            "diagnostic_signature": self.diagnostic_signature,
            "eligibility": self.eligibility.value,
            "zone1_hits": self.zone1_hits,
            "zone2_hit": self.zone2_hit,
        }


@dataclass(frozen=True, slots=True)
class Daily539OutcomeSignature:
    main_hits: int

    def __post_init__(self) -> None:
        if type(self.main_hits) is not int or not 0 <= self.main_hits <= 5:
            raise ValueError("main_hits must be an integer between 0 and 5")

    @property
    def diagnostic_signature(self) -> str:
        return f"M{self.main_hits}"

    def canonical_dict(self) -> dict[str, object]:
        return {
            "diagnostic_signature": self.diagnostic_signature,
            "main_hits": self.main_hits,
        }


OutcomeSignature = (
    BigLottoOutcomeSignature
    | BigLottoPortfolioOutcomeSignature
    | PowerLottoOutcomeSignature
    | Daily539OutcomeSignature
)


@dataclass(frozen=True, slots=True)
class MeasurementProvenance:
    strategy_version: str | None = None
    parameter_or_config_identity: str | None = None
    history_cutoff: str | None = None
    target_draw: str | None = None
    window_policy_version: str | None = None
    game_rule_version: str | None = None
    selection_family_identity: str | None = None
    source_artifact_identity: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "strategy_version",
            "parameter_or_config_identity",
            "history_cutoff",
            "target_draw",
            "window_policy_version",
            "game_rule_version",
            "selection_family_identity",
            "source_artifact_identity",
        ):
            _require_optional_text(getattr(self, name), name)

    @property
    def is_complete(self) -> bool:
        return all(
            getattr(self, name) is not None
            for name in (
                "strategy_version",
                "parameter_or_config_identity",
                "history_cutoff",
                "target_draw",
                "window_policy_version",
                "game_rule_version",
                "selection_family_identity",
                "source_artifact_identity",
            )
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "game_rule_version": self.game_rule_version,
            "history_cutoff": self.history_cutoff,
            "parameter_or_config_identity": self.parameter_or_config_identity,
            "selection_family_identity": self.selection_family_identity,
            "source_artifact_identity": self.source_artifact_identity,
            "strategy_version": self.strategy_version,
            "target_draw": self.target_draw,
            "window_policy_version": self.window_policy_version,
        }


@dataclass(frozen=True, slots=True)
class StrategySuccessMeasurement:
    """One typed result whose mode cannot be silently reinterpreted."""

    mode: MeasurementMode
    selection: SelectionIdentity
    outcome_signature: OutcomeSignature
    evidence_status: EvidenceStatus
    provenance: MeasurementProvenance
    window_policy: MeasurementWindowPolicy = DEFAULT_WINDOW_POLICY
    official_prize_tier_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.mode) is not MeasurementMode:
            raise ValueError("mode must be a MeasurementMode")
        if type(self.selection) is not SelectionIdentity:
            raise ValueError("selection must be a SelectionIdentity")
        if type(self.evidence_status) is not EvidenceStatus:
            raise ValueError("evidence_status must be an EvidenceStatus")
        if type(self.provenance) is not MeasurementProvenance:
            raise ValueError("provenance must be MeasurementProvenance")
        if type(self.window_policy) is not MeasurementWindowPolicy:
            raise ValueError("window_policy must be a MeasurementWindowPolicy")
        _require_optional_text(self.official_prize_tier_id, "official_prize_tier_id")

        if self.selection.lottery is LotteryType.BIG_LOTTO:
            expected_outcome_type = (
                BigLottoPortfolioOutcomeSignature
                if self.mode is MeasurementMode.LEGAL_TICKET_PRIZE
                else BigLottoOutcomeSignature
            )
        elif self.selection.lottery is LotteryType.POWER_LOTTO:
            expected_outcome_type = PowerLottoOutcomeSignature
        else:
            expected_outcome_type = Daily539OutcomeSignature
        if type(self.outcome_signature) is not expected_outcome_type:
            raise ValueError("outcome_signature does not match the selected lottery")

        if self.mode is MeasurementMode.CANDIDATE_COVERAGE:
            if self.selection.candidate_k is None:
                raise ValueError("candidate coverage requires candidate_k")
            if self.official_prize_tier_id is not None:
                raise ValueError("candidate coverage cannot carry an official prize tier")
        elif self.mode is MeasurementMode.LEGAL_TICKET_PRIZE:
            if self.selection.ticket_count is None:
                raise ValueError("legal-ticket prize measurement requires ticket_count")
            if (
                type(self.outcome_signature) is BigLottoPortfolioOutcomeSignature
                and self.selection.ticket_count != self.outcome_signature.ticket_count
            ):
                raise ValueError("selection ticket_count must match the portfolio ticket count")
            if self.official_prize_tier_id is not None:
                raise ValueError("legal-ticket prize mode is distinct from official-tier mode")
        else:
            if self.selection.ticket_count is None:
                raise ValueError("official prize-tier measurement requires ticket_count")
            if self.official_prize_tier_id is None:
                raise ValueError("official prize-tier mode requires official_prize_tier_id")

        if (
            self.selection.strategy_version is not None
            and self.provenance.strategy_version is not None
            and self.selection.strategy_version != self.provenance.strategy_version
        ):
            raise ValueError("selection and provenance strategy versions must match")
        if (
            self.provenance.window_policy_version is not None
            and self.provenance.window_policy_version != self.window_policy.policy_version
        ):
            raise ValueError("provenance window policy version must match the active policy")
        if (
            self.evidence_status is EvidenceStatus.PRODUCTION_ELIGIBLE
            and not self.provenance.is_complete
        ):
            raise ValueError("PRODUCTION_ELIGIBLE requires complete provenance")

    @property
    def production_eligible(self) -> bool:
        return self.evidence_status is EvidenceStatus.PRODUCTION_ELIGIBLE

    def canonical_dict(self) -> dict[str, object]:
        return {
            "evidence_status": self.evidence_status.value,
            "measurement_mode": self.mode.value,
            "official_prize_tier_id": self.official_prize_tier_id,
            "outcome_signature": self.outcome_signature.canonical_dict(),
            "provenance": self.provenance.canonical_dict(),
            "selection": self.selection.canonical_dict(),
            "window_policy": self.window_policy.canonical_dict(),
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


__all__ = [
    "DEFAULT_WINDOW_POLICY",
    "DEFAULT_WINDOW_POLICY_VERSION",
    "BigLottoOutcomeSignature",
    "BigLottoPortfolioOutcomeSignature",
    "Daily539OutcomeSignature",
    "EvidenceStatus",
    "MeasurementMode",
    "MeasurementProvenance",
    "MeasurementWindowPolicy",
    "OutcomeEligibility",
    "PowerLottoOutcomeSignature",
    "SelectionIdentity",
    "StrategySuccessMeasurement",
    "WindowRole",
]
