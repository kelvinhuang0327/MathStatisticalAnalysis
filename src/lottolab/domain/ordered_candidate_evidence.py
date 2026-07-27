"""Immutable, cross-game evidence for source-ordered strategy candidates.

The contracts in this module preserve target-native values only.  They do not
load replay history, import donor code, construct tickets, infer prize tiers,
or make strategy lifecycle decisions.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from lottolab.domain.draws import LotteryType

_ASCII_DECIMAL = re.compile(r"[0-9]+", flags=re.ASCII)
_GIT_OID = re.compile(r"[0-9a-f]{40}", flags=re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class DuplicateHandlingPolicy(StrEnum):
    """Stable interpretation of repeated values in one emitted sequence."""

    PRESERVE_FIRST_OCCURRENCE = "PRESERVE_FIRST_OCCURRENCE"


class Zone2OperandAvailability(StrEnum):
    PRESENT = "PRESENT"
    EXPLICITLY_MISSING = "EXPLICITLY_MISSING"


@dataclass(frozen=True, slots=True)
class CandidateGameRule:
    lottery_type: LotteryType
    main_pool_size: int
    main_draw_count: int
    candidate_k_max: int
    auxiliary_pool_size: int | None


_GAME_RULES = MappingProxyType(
    {
        LotteryType.BIG_LOTTO: CandidateGameRule(
            lottery_type=LotteryType.BIG_LOTTO,
            main_pool_size=49,
            main_draw_count=6,
            candidate_k_max=6,
            auxiliary_pool_size=49,
        ),
        LotteryType.DAILY_539: CandidateGameRule(
            lottery_type=LotteryType.DAILY_539,
            main_pool_size=39,
            main_draw_count=5,
            candidate_k_max=5,
            auxiliary_pool_size=None,
        ),
        LotteryType.POWER_LOTTO: CandidateGameRule(
            lottery_type=LotteryType.POWER_LOTTO,
            main_pool_size=38,
            main_draw_count=6,
            candidate_k_max=6,
            auxiliary_pool_size=8,
        ),
    }
)


def candidate_game_rule(lottery_type: LotteryType) -> CandidateGameRule:
    if type(lottery_type) is not LotteryType:
        raise ValueError("lottery_type must be a LotteryType")
    return _GAME_RULES[lottery_type]


def _require_canonical_text(value: str, name: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty canonical string")


def _require_decimal_draw(value: str, name: str) -> None:
    if type(value) is not str or _ASCII_DECIMAL.fullmatch(value) is None:
        raise ValueError(f"{name} must be an ASCII decimal draw identity")


@dataclass(frozen=True, slots=True)
class CandidateSourceArtifactIdentity:
    """Exact source identity for one already-materialized target observation."""

    repository: str
    commit_oid: str
    path: str
    sha256: str

    def __post_init__(self) -> None:
        _require_canonical_text(self.repository, "repository")
        _require_canonical_text(self.path, "path")
        if _GIT_OID.fullmatch(self.commit_oid) is None:
            raise ValueError("commit_oid must be an exact lowercase 40-character Git OID")
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("sha256 must be an exact lowercase SHA-256")

    def canonical_dict(self) -> dict[str, str]:
        return {
            "commit_oid": self.commit_oid,
            "path": self.path,
            "repository": self.repository,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class DonorSemanticReference:
    """Pinned provenance for semantics consulted during the target-native port."""

    repository: str
    commit_oid: str
    path: str
    symbol: str
    blob_oid: str

    def __post_init__(self) -> None:
        for name in ("repository", "path", "symbol"):
            _require_canonical_text(getattr(self, name), name)
        if _GIT_OID.fullmatch(self.commit_oid) is None:
            raise ValueError("commit_oid must be an exact lowercase 40-character Git OID")
        if _GIT_OID.fullmatch(self.blob_oid) is None:
            raise ValueError("blob_oid must be an exact lowercase 40-character Git blob OID")

    def canonical_dict(self) -> dict[str, str]:
        return {
            "blob_oid": self.blob_oid,
            "commit_oid": self.commit_oid,
            "path": self.path,
            "repository": self.repository,
            "symbol": self.symbol,
        }


P333_CANDIDATE_ORDER_REFERENCE: Final = DonorSemanticReference(
    repository="kelvinhuang0327/number-pattern-research",
    commit_oid="24617fe3bb7ec087acf121f302bffd638ccfa179",
    path="analysis/p333_strategy_pick_combination_scoreboard.py",
    symbol="select_strategy_numbers",
    blob_oid="f08b1d7dc3f974be53bf5bbe08b9dce285c04ac5",
)
P536C_BASELINE_REFERENCE: Final = DonorSemanticReference(
    repository="kelvinhuang0327/number-pattern-research",
    commit_oid="24617fe3bb7ec087acf121f302bffd638ccfa179",
    path="analysis/p536c_success_matrix_lift_extension.py",
    symbol="evaluate_strategy_pick_extended",
    blob_oid="1ae89e8dd6d82cabf0b4e97d270f6cb083f25c87",
)
DONOR_SEMANTIC_REFERENCES: Final = (
    P333_CANDIDATE_ORDER_REFERENCE,
    P536C_BASELINE_REFERENCE,
)


@dataclass(frozen=True, slots=True)
class PowerLottoZone2Operand:
    """A required operand that distinguishes an explicit absence from omission."""

    availability: Zone2OperandAvailability
    value: int | None

    def __post_init__(self) -> None:
        if type(self.availability) is not Zone2OperandAvailability:
            raise ValueError("availability must be a Zone2OperandAvailability")
        if self.availability is Zone2OperandAvailability.PRESENT:
            if type(self.value) is not int or not 1 <= self.value <= 8:
                raise ValueError("a present Power Lotto zone-2 operand must be in 1..8")
        elif self.value is not None:
            raise ValueError("an explicitly missing Power Lotto zone-2 operand has no value")

    @classmethod
    def present(cls, value: int) -> PowerLottoZone2Operand:
        return cls(Zone2OperandAvailability.PRESENT, value)

    @classmethod
    def explicitly_missing(cls) -> PowerLottoZone2Operand:
        return cls(Zone2OperandAvailability.EXPLICITLY_MISSING, None)

    @property
    def is_present(self) -> bool:
        return self.availability is Zone2OperandAvailability.PRESENT

    def canonical_dict(self) -> dict[str, int | str | None]:
        return {
            "availability": self.availability.value,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class CandidateKSelection:
    """The first K distinct emitted main numbers, with both K meanings explicit."""

    lottery_type: LotteryType
    requested_k: int
    effective_unique_k: int
    selected_main_numbers: tuple[int, ...]
    duplicate_handling_policy: DuplicateHandlingPolicy

    def __post_init__(self) -> None:
        rule = candidate_game_rule(self.lottery_type)
        if type(self.requested_k) is not int or not 1 <= self.requested_k <= rule.candidate_k_max:
            raise ValueError(f"requested_k must be in 1..{rule.candidate_k_max}")
        if (
            type(self.effective_unique_k) is not int
            or not 1 <= self.effective_unique_k <= self.requested_k
        ):
            raise ValueError("effective_unique_k must be in 1..requested_k")
        if (
            type(self.selected_main_numbers) is not tuple
            or len(self.selected_main_numbers) != self.effective_unique_k
            or any(type(number) is not int for number in self.selected_main_numbers)
            or len(set(self.selected_main_numbers)) != self.effective_unique_k
        ):
            raise ValueError("selected_main_numbers must be an immutable distinct K-prefix")
        if any(not 1 <= number <= rule.main_pool_size for number in self.selected_main_numbers):
            raise ValueError("selected_main_numbers contains an out-of-range number")
        if self.duplicate_handling_policy is not DuplicateHandlingPolicy.PRESERVE_FIRST_OCCURRENCE:
            raise ValueError("unsupported duplicate-handling policy")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "duplicate_handling_policy": self.duplicate_handling_policy.value,
            "effective_unique_k": self.effective_unique_k,
            "lottery_type": self.lottery_type.value,
            "requested_k": self.requested_k,
            "selected_main_numbers": list(self.selected_main_numbers),
        }


@dataclass(frozen=True, slots=True)
class OrderedCandidateObservation:
    """One source-ordered strategy observation with complete causal identity."""

    lottery_type: LotteryType
    strategy_id: str
    strategy_version: str
    replicate: int
    target_draw: str
    history_cutoff: str
    emitted_main_numbers: tuple[int, ...]
    duplicate_handling_policy: DuplicateHandlingPolicy
    predicted_big_lotto_special_operand: int | None
    predicted_power_lotto_zone2_operand: PowerLottoZone2Operand | None
    actual_main_numbers: tuple[int, ...]
    actual_special_or_zone2: int | None
    source_artifact_identity: CandidateSourceArtifactIdentity
    window_policy_version: str

    def __post_init__(self) -> None:
        rule = candidate_game_rule(self.lottery_type)
        _require_canonical_text(self.strategy_id, "strategy_id")
        _require_canonical_text(self.strategy_version, "strategy_version")
        _require_canonical_text(self.window_policy_version, "window_policy_version")
        if type(self.replicate) is not int or self.replicate < 1:
            raise ValueError("replicate must be an integer >= 1")
        _require_decimal_draw(self.target_draw, "target_draw")
        _require_decimal_draw(self.history_cutoff, "history_cutoff")
        if int(self.target_draw) <= int(self.history_cutoff):
            raise ValueError("target_draw must be after history_cutoff")
        if (
            type(self.emitted_main_numbers) is not tuple
            or not self.emitted_main_numbers
            or any(type(number) is not int for number in self.emitted_main_numbers)
        ):
            raise ValueError("emitted_main_numbers must be a non-empty immutable integer tuple")
        if any(not 1 <= number <= rule.main_pool_size for number in self.emitted_main_numbers):
            raise ValueError("emitted_main_numbers contains an out-of-range number")
        if self.duplicate_handling_policy is not DuplicateHandlingPolicy.PRESERVE_FIRST_OCCURRENCE:
            raise ValueError("unsupported duplicate-handling policy")
        if (
            type(self.actual_main_numbers) is not tuple
            or len(self.actual_main_numbers) != rule.main_draw_count
            or any(type(number) is not int for number in self.actual_main_numbers)
            or len(set(self.actual_main_numbers)) != rule.main_draw_count
        ):
            raise ValueError("actual_main_numbers has an invalid game-specific shape")
        if any(not 1 <= number <= rule.main_pool_size for number in self.actual_main_numbers):
            raise ValueError("actual_main_numbers contains an out-of-range number")
        if type(self.source_artifact_identity) is not CandidateSourceArtifactIdentity:
            raise ValueError("source_artifact_identity is malformed")

        if self.lottery_type is LotteryType.BIG_LOTTO:
            if self.predicted_big_lotto_special_operand is not None and (
                type(self.predicted_big_lotto_special_operand) is not int
                or not 1 <= self.predicted_big_lotto_special_operand <= 49
            ):
                raise ValueError("predicted Big Lotto special operand must be absent or in 1..49")
            if self.predicted_power_lotto_zone2_operand is not None:
                raise ValueError("Big Lotto cannot carry a Power Lotto zone-2 operand")
            if type(self.actual_special_or_zone2) is not int or not (
                1 <= self.actual_special_or_zone2 <= 49
            ):
                raise ValueError("Big Lotto requires an actual special number in 1..49")
            if self.actual_special_or_zone2 in self.actual_main_numbers:
                raise ValueError("Big Lotto actual special cannot overlap actual main numbers")
        elif self.lottery_type is LotteryType.DAILY_539:
            if (
                self.predicted_big_lotto_special_operand is not None
                or self.predicted_power_lotto_zone2_operand is not None
                or self.actual_special_or_zone2 is not None
            ):
                raise ValueError("Daily 539 carries main-number operands only")
        else:
            if self.predicted_big_lotto_special_operand is not None:
                raise ValueError("Power Lotto cannot carry a Big Lotto special operand")
            if type(self.predicted_power_lotto_zone2_operand) is not PowerLottoZone2Operand:
                raise ValueError(
                    "Power Lotto requires a present or explicitly-missing zone-2 operand"
                )
            if type(self.actual_special_or_zone2) is not int or not (
                1 <= self.actual_special_or_zone2 <= 8
            ):
                raise ValueError("Power Lotto requires an actual zone-2 number in 1..8")

    @property
    def strategy_identity(self) -> tuple[str, str, int]:
        return (self.strategy_id, self.strategy_version, self.replicate)

    @property
    def distinct_emitted_main_numbers(self) -> tuple[int, ...]:
        seen: set[int] = set()
        distinct: list[int] = []
        for number in self.emitted_main_numbers:
            if number not in seen:
                seen.add(number)
                distinct.append(number)
        return tuple(distinct)

    def select_candidate_k(self, requested_k: int) -> CandidateKSelection:
        rule = candidate_game_rule(self.lottery_type)
        if type(requested_k) is not int or not 1 <= requested_k <= rule.candidate_k_max:
            raise ValueError(f"requested_k must be in 1..{rule.candidate_k_max}")
        selected = self.distinct_emitted_main_numbers[:requested_k]
        return CandidateKSelection(
            lottery_type=self.lottery_type,
            requested_k=requested_k,
            effective_unique_k=len(selected),
            selected_main_numbers=selected,
            duplicate_handling_policy=self.duplicate_handling_policy,
        )

    def canonical_dict(self) -> dict[str, object]:
        zone2 = self.predicted_power_lotto_zone2_operand
        return {
            "actual_main_numbers": list(self.actual_main_numbers),
            "actual_special_or_zone2": self.actual_special_or_zone2,
            "duplicate_handling_policy": self.duplicate_handling_policy.value,
            "emitted_main_numbers": list(self.emitted_main_numbers),
            "history_cutoff": self.history_cutoff,
            "lottery_type": self.lottery_type.value,
            "predicted_big_lotto_special_operand": (
                self.predicted_big_lotto_special_operand
            ),
            "predicted_power_lotto_zone2_operand": (
                None if zone2 is None else zone2.canonical_dict()
            ),
            "replicate": self.replicate,
            "source_artifact_identity": self.source_artifact_identity.canonical_dict(),
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "target_draw": self.target_draw,
            "window_policy_version": self.window_policy_version,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


@dataclass(frozen=True, slots=True)
class CandidateCoverageOutcome:
    """Derived Candidate-K hit signature; impossible signatures fail closed."""

    selection: CandidateKSelection
    main_hits: int
    special_hit: bool | None
    zone2_hit: bool | None

    def __post_init__(self) -> None:
        if type(self.selection) is not CandidateKSelection:
            raise ValueError("selection is malformed")
        rule = candidate_game_rule(self.selection.lottery_type)
        if (
            type(self.main_hits) is not int
            or not 0
            <= self.main_hits
            <= min(rule.main_draw_count, self.selection.effective_unique_k)
        ):
            raise ValueError("main_hits is impossible for the effective Candidate-K selection")
        if self.selection.lottery_type is LotteryType.BIG_LOTTO:
            if type(self.special_hit) is not bool or self.zone2_hit is not None:
                raise ValueError("Big Lotto requires only a boolean special-hit operand")
            if self.main_hits + int(self.special_hit) > self.selection.effective_unique_k:
                raise ValueError("Big Lotto hit signature exceeds effective unique K")
        elif self.selection.lottery_type is LotteryType.DAILY_539:
            if self.special_hit is not None or self.zone2_hit is not None:
                raise ValueError("Daily 539 has no auxiliary hit operand")
        elif self.special_hit is not None or (
            self.zone2_hit is not None and type(self.zone2_hit) is not bool
        ):
            raise ValueError("Power Lotto uses only a boolean-or-missing zone-2 hit")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "main_hits": self.main_hits,
            "selection": self.selection.canonical_dict(),
            "special_hit": self.special_hit,
            "zone2_hit": self.zone2_hit,
        }


def evaluate_candidate_coverage(
    observation: OrderedCandidateObservation,
    requested_k: int,
) -> CandidateCoverageOutcome:
    if type(observation) is not OrderedCandidateObservation:
        raise ValueError("observation is malformed")
    selection = observation.select_candidate_k(requested_k)
    selected = set(selection.selected_main_numbers)
    main_hits = len(selected & set(observation.actual_main_numbers))
    if observation.lottery_type is LotteryType.BIG_LOTTO:
        auxiliary = observation.actual_special_or_zone2
        if type(auxiliary) is not int:
            raise AssertionError("validated Big Lotto observation lost its special number")
        return CandidateCoverageOutcome(
            selection=selection,
            main_hits=main_hits,
            special_hit=auxiliary in selected,
            zone2_hit=None,
        )
    if observation.lottery_type is LotteryType.DAILY_539:
        return CandidateCoverageOutcome(
            selection=selection,
            main_hits=main_hits,
            special_hit=None,
            zone2_hit=None,
        )
    operand = observation.predicted_power_lotto_zone2_operand
    actual_zone2 = observation.actual_special_or_zone2
    if type(operand) is not PowerLottoZone2Operand or type(actual_zone2) is not int:
        raise AssertionError("validated Power Lotto observation lost its zone-2 operands")
    return CandidateCoverageOutcome(
        selection=selection,
        main_hits=main_hits,
        special_hit=None,
        zone2_hit=(operand.value == actual_zone2) if operand.is_present else None,
    )


__all__ = [
    "DONOR_SEMANTIC_REFERENCES",
    "P333_CANDIDATE_ORDER_REFERENCE",
    "P536C_BASELINE_REFERENCE",
    "CandidateCoverageOutcome",
    "CandidateGameRule",
    "CandidateKSelection",
    "CandidateSourceArtifactIdentity",
    "DonorSemanticReference",
    "DuplicateHandlingPolicy",
    "OrderedCandidateObservation",
    "PowerLottoZone2Operand",
    "Zone2OperandAvailability",
    "candidate_game_rule",
    "evaluate_candidate_coverage",
]
