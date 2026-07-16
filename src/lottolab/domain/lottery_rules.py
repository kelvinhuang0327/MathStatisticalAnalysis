"""Authoritative, immutable lottery-rule contracts used at runtime."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from types import MappingProxyType
from urllib.parse import urlparse

from lottolab.domain.draws import LotteryType


class LotteryLifecycleStatus(StrEnum):
    """Whether an authoritative rule contract is eligible for current imports."""

    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class CanonicalNumberOrder(StrEnum):
    """LottoLab's deterministic storage order for an order-insensitive number set."""

    ASCENDING_NUMERIC = "ASCENDING_NUMERIC"


class ProvenanceStatus(StrEnum):
    """Authority classification for a rule-contract source."""

    PRIMARY = "PRIMARY"
    CORROBORATING = "CORROBORATING"
    SUPERSEDED = "SUPERSEDED"
    AMBIGUOUS = "AMBIGUOUS"


AUTHORITATIVE_SOURCE_HOSTS = frozenset(
    {
        "lotto.ctbcbank.com",
        "taiwanlottery.com",
        "www.nta.gov.tw",
        "www.taiwanlottery.com",
    }
)

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


@dataclass(frozen=True, slots=True)
class LotteryRuleContract:
    """Complete game mechanics and provenance for one lottery type."""

    lottery_type: LotteryType
    contract_version: str
    lifecycle_status: LotteryLifecycleStatus
    effective_from: date | None
    effective_to: date | None
    main_number_count: int
    main_number_min: int
    main_number_max: int
    main_numbers_unique: bool
    special_number_count: int
    special_number_min: int
    special_number_max: int
    special_number_required: bool
    special_numbers_unique: bool
    main_special_overlap_allowed: bool
    canonical_number_order: CanonicalNumberOrder
    source_publisher: str
    source_title: str
    source_url: str
    source_sha256: str
    source_locator: str
    source_accessed_at: datetime
    provenance_status: ProvenanceStatus

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Raise ``ValueError`` when any required rule or provenance field is incomplete."""

        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if type(self.lifecycle_status) is not LotteryLifecycleStatus:
            raise ValueError("lifecycle_status must be a LotteryLifecycleStatus")
        if type(self.canonical_number_order) is not CanonicalNumberOrder:
            raise ValueError("canonical_number_order must be a CanonicalNumberOrder")
        if type(self.provenance_status) is not ProvenanceStatus:
            raise ValueError("provenance_status must be a ProvenanceStatus")

        text_fields = {
            "contract_version": self.contract_version,
            "source_publisher": self.source_publisher,
            "source_title": self.source_title,
            "source_url": self.source_url,
            "source_sha256": self.source_sha256,
            "source_locator": self.source_locator,
        }
        for name, value in text_fields.items():
            if type(value) is not str:
                raise ValueError(f"{name} must be a string")
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")

        for name, value in (
            ("main_number_count", self.main_number_count),
            ("main_number_min", self.main_number_min),
            ("main_number_max", self.main_number_max),
            ("special_number_count", self.special_number_count),
            ("special_number_min", self.special_number_min),
            ("special_number_max", self.special_number_max),
        ):
            if type(value) is not int:
                raise ValueError(f"{name} must be an integer")

        for name, value in (
            ("main_numbers_unique", self.main_numbers_unique),
            ("special_number_required", self.special_number_required),
            ("special_numbers_unique", self.special_numbers_unique),
            ("main_special_overlap_allowed", self.main_special_overlap_allowed),
        ):
            if type(value) is not bool:
                raise ValueError(f"{name} must be a boolean")

        if self.effective_from is not None and type(self.effective_from) is not date:
            raise ValueError("effective_from must be a date or None")
        if self.effective_to is not None and type(self.effective_to) is not date:
            raise ValueError("effective_to must be a date or None")
        if type(self.source_accessed_at) is not datetime:
            raise ValueError("source_accessed_at must be a datetime")

        if (
            self.effective_from
            and self.effective_to
            and self.effective_from > self.effective_to
        ):
            raise ValueError("effective_from must not be after effective_to")

        if self.main_number_count <= 0:
            raise ValueError("main_number_count must be positive")
        if self.main_number_min > self.main_number_max:
            raise ValueError("main number range is inverted")
        main_capacity = self.main_number_max - self.main_number_min + 1
        if self.main_numbers_unique and self.main_number_count > main_capacity:
            raise ValueError("unique main numbers exceed the configured range")

        if self.special_number_count < 0:
            raise ValueError("special_number_count must not be negative")
        if self.special_number_min > self.special_number_max:
            raise ValueError("special number range is inverted")
        if self.special_number_required and self.special_number_count == 0:
            raise ValueError("a required special number must have a positive count")
        special_capacity = self.special_number_max - self.special_number_min + 1
        if self.special_numbers_unique and self.special_number_count > special_capacity:
            raise ValueError("unique special numbers exceed the configured range")
        if self.canonical_number_order is not CanonicalNumberOrder.ASCENDING_NUMERIC:
            raise ValueError("canonical_number_order is not supported")

        parsed_url = urlparse(self.source_url)
        if parsed_url.scheme != "https" or parsed_url.hostname not in AUTHORITATIVE_SOURCE_HOSTS:
            raise ValueError("source_url must use an accepted authoritative HTTPS host")
        if _SHA256.fullmatch(self.source_sha256) is None:
            raise ValueError("source_sha256 must be a lowercase SHA-256 digest")
        if self.source_accessed_at.tzinfo is None:
            raise ValueError("source_accessed_at must be timezone-aware")
        if self.source_accessed_at.utcoffset() != UTC.utcoffset(self.source_accessed_at):
            raise ValueError("source_accessed_at must use UTC")

    def canonical_dict(self) -> dict[str, bool | int | str | None]:
        """Return a stable, JSON-ready representation of every required field."""

        accessed_at = self.source_accessed_at.isoformat().replace("+00:00", "Z")
        return {
            "canonical_number_order": self.canonical_number_order.value,
            "contract_version": self.contract_version,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "lifecycle_status": self.lifecycle_status.value,
            "lottery_type": self.lottery_type.value,
            "main_number_count": self.main_number_count,
            "main_number_max": self.main_number_max,
            "main_number_min": self.main_number_min,
            "main_numbers_unique": self.main_numbers_unique,
            "main_special_overlap_allowed": self.main_special_overlap_allowed,
            "provenance_status": self.provenance_status.value,
            "source_accessed_at": accessed_at,
            "source_locator": self.source_locator,
            "source_publisher": self.source_publisher,
            "source_sha256": self.source_sha256,
            "source_title": self.source_title,
            "source_url": self.source_url,
            "special_number_count": self.special_number_count,
            "special_number_max": self.special_number_max,
            "special_number_min": self.special_number_min,
            "special_number_required": self.special_number_required,
            "special_numbers_unique": self.special_numbers_unique,
        }

    def canonical_json(self) -> str:
        """Serialize the contract deterministically for audit or hashing."""

        return json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


BIG_LOTTO_RULE_CONTRACT = LotteryRuleContract(
    lottery_type=LotteryType.BIG_LOTTO,
    contract_version="2026-07-16.1",
    lifecycle_status=LotteryLifecycleStatus.ACTIVE,
    effective_from=None,
    effective_to=None,
    main_number_count=6,
    main_number_min=1,
    main_number_max=49,
    main_numbers_unique=True,
    special_number_count=1,
    special_number_min=1,
    special_number_max=49,
    special_number_required=True,
    special_numbers_unique=True,
    main_special_overlap_allowed=False,
    canonical_number_order=CanonicalNumberOrder.ASCENDING_NUMERIC,
    source_publisher="台灣彩券股份有限公司",
    source_title="台灣彩券 /_nuxt/_game_.1_0_8_04.js",
    source_url="https://www.taiwanlottery.com/_nuxt/_game_.1_0_8_04.js",
    source_sha256="397639210969faba3002ffbd309dba10c44ead2063dd51ed47def98624994c15",
    source_locator=(
        "BaseRule component, lotto649.text, beginning near UTF-8 byte 6690"
    ),
    source_accessed_at=datetime(2026, 7, 16, 5, 19, 34, tzinfo=UTC),
    provenance_status=ProvenanceStatus.PRIMARY,
)

LOTTERY_RULE_CONTRACTS: Mapping[LotteryType, LotteryRuleContract] = MappingProxyType(
    {LotteryType.BIG_LOTTO: BIG_LOTTO_RULE_CONTRACT}
)


def resolve_lottery_rule_contract(
    lottery_type: LotteryType,
    contracts: Mapping[LotteryType, LotteryRuleContract],
) -> LotteryRuleContract | None:
    """Resolve only a complete, active, primary contract; otherwise fail closed."""

    candidate = contracts.get(lottery_type)
    if type(candidate) is not LotteryRuleContract:
        return None
    if candidate.lottery_type is not lottery_type:
        return None
    if candidate.lifecycle_status is not LotteryLifecycleStatus.ACTIVE:
        return None
    if candidate.provenance_status is not ProvenanceStatus.PRIMARY:
        return None
    try:
        candidate.validate()
    except (AttributeError, TypeError, ValueError):
        return None
    return candidate
