"""Focused contract tests for authoritative BIG_LOTTO mechanics."""

from __future__ import annotations

import json
import re
from dataclasses import FrozenInstanceError, fields, replace
from urllib.parse import urlparse

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import (
    AUTHORITATIVE_SOURCE_HOSTS,
    BIG_LOTTO_RULE_CONTRACT,
    LOTTERY_RULE_CONTRACTS,
    LotteryLifecycleStatus,
    LotteryRuleContract,
    ProvenanceStatus,
)

REQUIRED_FIELDS = {
    "lottery_type",
    "contract_version",
    "lifecycle_status",
    "effective_from",
    "effective_to",
    "main_number_count",
    "main_number_min",
    "main_number_max",
    "main_numbers_unique",
    "special_number_count",
    "special_number_min",
    "special_number_max",
    "special_number_required",
    "special_numbers_unique",
    "main_special_overlap_allowed",
    "canonical_number_order",
    "source_publisher",
    "source_title",
    "source_url",
    "source_sha256",
    "source_locator",
    "source_accessed_at",
    "provenance_status",
}


def test_rule_contract_has_every_required_field() -> None:
    assert {field.name for field in fields(LotteryRuleContract)} == REQUIRED_FIELDS


def test_rule_contract_is_immutable() -> None:
    setter = BIG_LOTTO_RULE_CONTRACT.__setattr__
    with pytest.raises(FrozenInstanceError):
        setter("main_number_count", 7)


def test_primary_source_provenance_is_complete_and_authoritative() -> None:
    contract = BIG_LOTTO_RULE_CONTRACT

    assert contract.lifecycle_status is LotteryLifecycleStatus.ACTIVE
    assert contract.provenance_status is ProvenanceStatus.PRIMARY
    assert contract.source_publisher.strip()
    assert contract.source_title.strip()
    assert contract.source_locator.strip()
    assert re.fullmatch(r"[0-9a-f]{64}", contract.source_sha256)

    source = urlparse(contract.source_url)
    assert source.scheme == "https"
    assert source.hostname == "www.taiwanlottery.com"
    assert source.hostname in AUTHORITATIVE_SOURCE_HOSTS
    assert contract.source_accessed_at.tzinfo is not None
    assert contract.source_accessed_at.utcoffset() is not None


def test_effective_dates_are_internally_consistent() -> None:
    contract = BIG_LOTTO_RULE_CONTRACT

    assert (
        contract.effective_from is None
        or contract.effective_to is None
        or contract.effective_from <= contract.effective_to
    )


def test_contract_supports_canonical_serialization() -> None:
    contract = BIG_LOTTO_RULE_CONTRACT

    first = contract.canonical_json()
    second = contract.canonical_json()
    decoded = json.loads(first)

    assert first == second
    assert json.dumps(decoded, ensure_ascii=False, separators=(",", ":"), sort_keys=True) == first
    assert set(decoded) == REQUIRED_FIELDS
    assert decoded["lottery_type"] == LotteryType.BIG_LOTTO.value
    assert decoded["source_accessed_at"].endswith("Z")


def test_invalid_effective_date_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="effective_from"):
        replace(
            BIG_LOTTO_RULE_CONTRACT,
            effective_from=BIG_LOTTO_RULE_CONTRACT.source_accessed_at.date(),
            effective_to=BIG_LOTTO_RULE_CONTRACT.source_accessed_at.date().replace(year=2025),
        )


def test_registry_contains_one_machine_readable_big_lotto_contract() -> None:
    assert tuple(LOTTERY_RULE_CONTRACTS) == (LotteryType.BIG_LOTTO,)
    assert tuple(LOTTERY_RULE_CONTRACTS.values()) == (BIG_LOTTO_RULE_CONTRACT,)
    assert LOTTERY_RULE_CONTRACTS[LotteryType.BIG_LOTTO] is BIG_LOTTO_RULE_CONTRACT
