from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.fixtures.legacy_reference_corpus import (
    build_legacy_reference_corpus,
)

from lottolab.application.legacy_reference_import import (
    CorpusChecksumMismatchError,
    LegacyCausalCutoffError,
    UnsupportedLegacyLotteryTypeError,
    map_big_lotto_legacy_row,
    prepare_legacy_corpus,
)


def test_prepare_verifies_and_maps_big_lotto_while_typing_deferred_rows(
    tmp_path: Path,
) -> None:
    root = build_legacy_reference_corpus(tmp_path)

    prepared = prepare_legacy_corpus(root)

    assert prepared.big_lotto_rows == 500
    assert prepared.deferred_rows == (("DAILY_539", 1), ("POWER_LOTTO", 1))
    assert len(prepared.targets) == 2
    assert len(prepared.strategies) == 1
    assert prepared.duplicate_ticket_rows == 498
    assert prepared.scoring.sample_size == 500
    assert prepared.scoring.agreements == 500
    assert prepared.scoring.disagreements == 0
    assert prepared.scoring.main_hit_agreements == 500
    assert prepared.scoring.special_hit_agreements == 500
    assert [row.bet_index for row in prepared.targets[0].rows] == list(
        range(1, 251)
    )


def test_checksum_mismatch_aborts_before_row_mapping(
    tmp_path: Path,
) -> None:
    root = build_legacy_reference_corpus(tmp_path)
    replay = root / "tables" / "strategy_prediction_replays.jsonl"
    replay.write_text(replay.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")

    with pytest.raises(CorpusChecksumMismatchError, match="SHA-256 mismatch"):
        prepare_legacy_corpus(root)


@pytest.mark.parametrize("lottery_type", ["POWER_LOTTO", "DAILY_539"])
def test_non_big_lotto_row_is_refused_with_typed_reason(
    lottery_type: str,
) -> None:
    with pytest.raises(
        UnsupportedLegacyLotteryTypeError,
        match="no reviewed lottery rule contract",
    ) as raised:
        map_big_lotto_legacy_row({"lottery_type": lottery_type})

    assert raised.value.lottery_type == lottery_type


def test_causal_cutoff_violation_is_not_adjusted(
    tmp_path: Path,
) -> None:
    root = build_legacy_reference_corpus(tmp_path, causal_violation=True)

    with pytest.raises(LegacyCausalCutoffError, match="is not before"):
        prepare_legacy_corpus(root)


def test_raw_legacy_values_remain_present_in_ticket_record(
    tmp_path: Path,
) -> None:
    prepared = prepare_legacy_corpus(build_legacy_reference_corpus(tmp_path))
    first = prepared.targets[0].rows[0]

    raw = json.loads(first.raw_record_json)
    assert raw["provenance_hash"] == first.provenance_hash
    assert raw["provenance_source"] == first.provenance_source
    assert raw["hit_numbers"] == "[1,2]"
    assert raw["special_hit"] == 1
