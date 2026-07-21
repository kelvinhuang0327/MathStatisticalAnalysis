"""Focused contract tests for authoritative BIG_LOTTO mechanics."""

from __future__ import annotations

import json
import re
from dataclasses import FrozenInstanceError, fields, replace
from urllib.parse import urlparse

import pytest

import lottolab.domain.lottery_rules as lottery_rules_module
from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import (
    AUTHORITATIVE_SOURCE_HOSTS,
    BIG_LOTTO_RULE_CONTRACT,
    LOTTERY_RULE_CONTRACTS,
    BigLottoPrizeRuleContract,
    BigLottoPrizeTier,
    BigLottoPrizeTierId,
    LotteryLifecycleStatus,
    LotteryRuleContract,
    NoPrizeResult,
    ProvenanceStatus,
    resolve_big_lotto_prize_tier,
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
    "prize_rule",
}

PRIZE_RULE_REQUIRED_FIELDS = {
    "schema_version",
    "source_sha256",
    "source_locator",
    "source_accessed_at",
    "tiers",
}

PRIZE_TIER_REQUIRED_FIELDS = {
    "tier_id",
    "official_label",
    "main_hits",
    "special_hit",
}

EXPECTED_WINNING_ROWS = {
    (6, False): (BigLottoPrizeTierId.FIRST, "頭獎"),
    (5, True): (BigLottoPrizeTierId.SECOND, "貳獎"),
    (5, False): (BigLottoPrizeTierId.THIRD, "參獎"),
    (4, True): (BigLottoPrizeTierId.FOURTH, "肆獎"),
    (4, False): (BigLottoPrizeTierId.FIFTH, "伍獎"),
    (3, True): (BigLottoPrizeTierId.SIXTH, "陸獎"),
    (2, True): (BigLottoPrizeTierId.SEVENTH, "柒獎"),
    (3, False): (BigLottoPrizeTierId.GENERAL, "普獎"),
}

VALID_HIT_SIGNATURES = tuple(
    (main_hits, special_hit)
    for main_hits in range(BIG_LOTTO_RULE_CONTRACT.main_number_count + 1)
    for special_hit in (False, True)
    if main_hits + int(special_hit) <= BIG_LOTTO_RULE_CONTRACT.main_number_count
)


def test_rule_contract_has_every_required_field() -> None:
    assert {field.name for field in fields(LotteryRuleContract)} == REQUIRED_FIELDS
    assert {
        field.name for field in fields(BigLottoPrizeRuleContract)
    } == PRIZE_RULE_REQUIRED_FIELDS
    assert {field.name for field in fields(BigLottoPrizeTier)} == PRIZE_TIER_REQUIRED_FIELDS


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
    assert decoded["prize_rule"]["schema_version"] == "1.0.0"
    assert decoded["prize_rule"]["source_accessed_at"].endswith("Z")
    assert len(decoded["prize_rule"]["tiers"]) == len(BigLottoPrizeTierId)


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


def test_prize_rule_is_complete_ordered_source_bound_and_amount_free() -> None:
    contract = BIG_LOTTO_RULE_CONTRACT
    prize_rule = contract.prize_rule

    assert prize_rule.tiers
    assert tuple(tier.tier_id for tier in prize_rule.tiers) == tuple(BigLottoPrizeTierId)
    assert len({tier.tier_id for tier in prize_rule.tiers}) == len(prize_rule.tiers)
    assert len(
        {(tier.main_hits, tier.special_hit) for tier in prize_rule.tiers}
    ) == len(prize_rule.tiers)
    assert all(tier.official_label.strip() for tier in prize_rule.tiers)
    assert prize_rule.source_sha256 == contract.source_sha256
    assert prize_rule.source_locator == "lotto649.tableData, UTF-8 bytes 7446-8159"

    forbidden_monetary_fragments = {"amount", "jackpot", "payout", "price", "tax"}
    field_names = {
        field.name.casefold()
        for model in (BigLottoPrizeRuleContract, BigLottoPrizeTier)
        for field in fields(model)
    }
    assert not any(
        fragment in name
        for fragment in forbidden_monetary_fragments
        for name in field_names
    )


def test_resolver_uses_the_committed_contract_as_its_only_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prize_rule = BIG_LOTTO_RULE_CONTRACT.prize_rule
    first, second, *remaining = prize_rule.tiers
    altered_tiers = (
        replace(first, main_hits=second.main_hits, special_hit=second.special_hit),
        replace(second, main_hits=first.main_hits, special_hit=first.special_hit),
        *remaining,
    )
    altered_contract = replace(
        BIG_LOTTO_RULE_CONTRACT,
        prize_rule=replace(prize_rule, tiers=altered_tiers),
    )
    monkeypatch.setattr(
        lottery_rules_module,
        "BIG_LOTTO_RULE_CONTRACT",
        altered_contract,
    )

    for tier in altered_contract.prize_rule.tiers:
        assert (
            lottery_rules_module.resolve_big_lotto_prize_tier(
                tier.main_hits,
                tier.special_hit,
            )
            is tier
        )


def test_every_valid_hit_signature_resolves_once_to_a_tier_or_no_prize() -> None:
    assert len(VALID_HIT_SIGNATURES) == 13

    for signature in VALID_HIT_SIGNATURES:
        result = resolve_big_lotto_prize_tier(*signature)
        expected = EXPECTED_WINNING_ROWS.get(signature)
        if expected is None:
            assert result is NoPrizeResult.NO_PRIZE
        else:
            assert type(result) is BigLottoPrizeTier
            assert (result.tier_id, result.official_label) == expected


@pytest.mark.parametrize(
    ("signature", "expected_tier_id", "expected_label"),
    [
        (signature, expected[0], expected[1])
        for signature, expected in EXPECTED_WINNING_ROWS.items()
    ],
)
def test_every_official_winning_tier_is_pinned(
    signature: tuple[int, bool],
    expected_tier_id: BigLottoPrizeTierId,
    expected_label: str,
) -> None:
    result = resolve_big_lotto_prize_tier(*signature)

    assert type(result) is BigLottoPrizeTier
    assert result.main_hits == signature[0]
    assert result.special_hit is signature[1]
    assert result.tier_id is expected_tier_id
    assert result.official_label == expected_label


@pytest.mark.parametrize(
    ("main_hits", "special_hit", "message"),
    [
        (-1, False, "between"),
        (7, False, "between"),
        (True, False, "integer"),
        (3, 1, "boolean"),
        (3, "true", "boolean"),
        (6, True, "ticket size"),
    ],
)
def test_invalid_hit_signatures_fail_closed(
    main_hits: object,
    special_hit: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        resolve_big_lotto_prize_tier(main_hits, special_hit)  # type: ignore[arg-type]


def test_malformed_prize_tier_is_rejected() -> None:
    prize_rule = BIG_LOTTO_RULE_CONTRACT.prize_rule
    malformed = replace(prize_rule.tiers[0], official_label=" ")

    with pytest.raises(ValueError, match="official_label"):
        replace(
            BIG_LOTTO_RULE_CONTRACT,
            prize_rule=replace(prize_rule, tiers=(malformed, *prize_rule.tiers[1:])),
        )


def test_duplicate_tier_identifier_is_rejected() -> None:
    prize_rule = BIG_LOTTO_RULE_CONTRACT.prize_rule
    duplicate = replace(prize_rule.tiers[1], tier_id=BigLottoPrizeTierId.FIRST)

    with pytest.raises(ValueError, match="identifier"):
        replace(
            BIG_LOTTO_RULE_CONTRACT,
            prize_rule=replace(
                prize_rule,
                tiers=(prize_rule.tiers[0], duplicate, *prize_rule.tiers[2:]),
            ),
        )


def test_ambiguous_multiple_tier_match_is_rejected() -> None:
    prize_rule = BIG_LOTTO_RULE_CONTRACT.prize_rule
    ambiguous = replace(prize_rule.tiers[1], main_hits=6, special_hit=False)

    with pytest.raises(ValueError, match="ambiguous"):
        replace(
            BIG_LOTTO_RULE_CONTRACT,
            prize_rule=replace(
                prize_rule,
                tiers=(prize_rule.tiers[0], ambiguous, *prize_rule.tiers[2:]),
            ),
        )


def test_incomplete_official_tier_mapping_is_rejected() -> None:
    prize_rule = BIG_LOTTO_RULE_CONTRACT.prize_rule

    with pytest.raises(ValueError, match="every tier identifier"):
        replace(
            BIG_LOTTO_RULE_CONTRACT,
            prize_rule=replace(prize_rule, tiers=prize_rule.tiers[:-1]),
        )


def test_prize_source_digest_must_link_to_primary_provenance() -> None:
    prize_rule = BIG_LOTTO_RULE_CONTRACT.prize_rule

    with pytest.raises(ValueError, match="source digest"):
        replace(
            BIG_LOTTO_RULE_CONTRACT,
            prize_rule=replace(prize_rule, source_sha256="0" * 64),
        )


def test_existing_big_lotto_mechanics_and_provenance_tuple_are_unchanged() -> None:
    contract = BIG_LOTTO_RULE_CONTRACT

    assert contract.contract_version == "2026-07-16.1"
    assert (
        contract.main_number_count,
        contract.main_number_min,
        contract.main_number_max,
        contract.main_numbers_unique,
        contract.special_number_count,
        contract.special_number_min,
        contract.special_number_max,
        contract.special_number_required,
        contract.special_numbers_unique,
        contract.main_special_overlap_allowed,
    ) == (6, 1, 49, True, 1, 1, 49, True, True, False)
    assert (
        contract.source_publisher,
        contract.source_title,
        contract.source_url,
        contract.source_sha256,
        contract.source_locator,
        contract.source_accessed_at.isoformat(),
        contract.provenance_status,
    ) == (
        "台灣彩券股份有限公司",
        "台灣彩券 /_nuxt/_game_.1_0_8_04.js",
        "https://www.taiwanlottery.com/_nuxt/_game_.1_0_8_04.js",
        "397639210969faba3002ffbd309dba10c44ead2063dd51ed47def98624994c15",
        "BaseRule component, lotto649.text, beginning near UTF-8 byte 6690",
        "2026-07-16T05:19:34+00:00",
        ProvenanceStatus.PRIMARY,
    )
