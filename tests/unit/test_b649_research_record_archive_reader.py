from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from lottolab.infrastructure import b649_research_record_archive_reader as reader_module
from lottolab.infrastructure.b649_research_record_archive_reader import (
    B649ResearchRecordArchiveDataError,
    B649ResearchRecordArchiveReader,
    B649ResearchRecordInvalidFilter,
    B649ResearchRecordSourceNotFound,
)

ARCHIVE_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261102/"
    "NUMBER2_C_BACKTEST_RECOVERY_BUNDLE_20261102_R1"
)
EXPECTED_COUNTS = {
    "NUMBER2_D_NATIVE_SUBSET_W50_K235_20261101_R1": 15_804,
    "NUMBER2_D_DECISION_OBJECTIVE_W50_1317_20261101_R1": 15_804,
    "NUMBER2_D_GROUP_DRO_CAUSAL_W50_20261101_R1": 19_755,
    "NUMBER2_D_SPECIAL_LAG_BUCKET_W50_K235_20261102_R1": 15_804,
    "NUMBER2_D_DRAW_ORDER_POSITION_SIGNAL_V1_20261102_R1": 15_804,
}
SOURCE_FIELDS = {
    "NUMBER2_D_NATIVE_SUBSET_W50_K235_20261101_R1": (
        "tickets",
        ("strategy_id", "strategy_version"),
        ("ticket_prize_tiers", "ticket_special_hits"),
        "any_official_prize",
        "execution_status",
    ),
    "NUMBER2_D_DECISION_OBJECTIVE_W50_1317_20261101_R1": (
        "tickets",
        ("arm",),
        ("ticket_results",),
        "any_official_prize",
        None,
    ),
    "NUMBER2_D_GROUP_DRO_CAUSAL_W50_20261101_R1": (
        "tickets",
        ("strategy_id", "strategy_version"),
        ("best_prize_tier", "ticket_prize_tiers"),
        "any_official_prize",
        "execution_status",
    ),
    "NUMBER2_D_SPECIAL_LAG_BUCKET_W50_K235_20261102_R1": (
        "ticket_numbers",
        ("arm",),
        (
            "official_prize_tiers",
            "baseline_any_prize",
            "candidate_any_prize",
            "special_hit_per_ticket",
        ),
        None,
        "execution_status",
    ),
    "NUMBER2_D_DRAW_ORDER_POSITION_SIGNAL_V1_20261102_R1": (
        "tickets",
        ("strategy_id", "strategy_version"),
        ("ticket_prize_tiers",),
        "any_official_prize",
        "execution_status",
    ),
}


def test_verified_archive_exposes_exact_five_source_counts_and_caches() -> None:
    reader = B649ResearchRecordArchiveReader(ARCHIVE_ROOT)

    dataset = reader.read()

    assert dataset is reader.read()
    assert dataset.archive_sha256 == reader_module.B649_RESEARCH_RECORD_ARCHIVE_SHA256
    assert dataset.manifest_sha256 == reader_module.B649_RESEARCH_RECORD_MANIFEST_SHA256
    assert dataset.source_authority == "fe3aa81d3844ac11d4360447c243e90fe4a6613a"
    assert {source.source_task_id: source.record_count for source in dataset.sources} == (
        EXPECTED_COUNTS
    )
    assert sum(source.record_count for source in dataset.sources) == 82_971
    assert all(source._K_values == (2, 3, 5) for source in dataset.sources)
    assert all(source.research_class == "FORMAL_HISTORICAL_BACKTEST" for source in dataset.sources)
    assert all(source.availability_status == "AVAILABLE" for source in dataset.sources)


def test_every_normalized_record_matches_its_original_jsonl_fields() -> None:
    dataset = B649ResearchRecordArchiveReader(ARCHIVE_ROOT).read()
    manifest = json.loads((ARCHIVE_ROOT / "archive_manifest.json").read_text(encoding="utf-8"))
    specs = {
        item["source_task_id"]: item
        for item in manifest["raw_backtest_coverage"]["formal_primary_sources"]
    }

    with zipfile.ZipFile(ARCHIVE_ROOT / "backtest_bundle.zip") as archive:
        for source in dataset.sources:
            tickets_field, identity_fields, prize_fields, any_prize_field, status_field = (
                SOURCE_FIELDS[source.source_task_id]
            )
            spec = specs[source.source_task_id]
            raw_rows = archive.read(spec["archive_relative_path"]).splitlines()
            assert len(raw_rows) == EXPECTED_COUNTS[source.source_task_id]

            for line_number, (raw_line, normalized) in enumerate(
                zip(raw_rows, source._records, strict=True), start=1
            ):
                original = json.loads(raw_line)
                if len(identity_fields) == 1:
                    original_identity = original[identity_fields[0]]
                else:
                    original_identity = "@".join(str(original[name]) for name in identity_fields)
                assert normalized.source_record_identity == (
                    f"{source.source_task_id}:record:{line_number:06d}"
                )
                assert normalized.target_draw == original["target_draw"]
                assert normalized.arm_or_method_identity == original_identity
                assert original["K"] == normalized.K
                assert normalized.predicted_tickets == original[tickets_field]
                assert normalized.actual_main_numbers == original["actual_main_numbers"]
                assert normalized.actual_special_number == original["actual_special_number"]
                assert normalized.official_prize_result == {
                    name: original[name] for name in prize_fields
                }
                assert normalized.any_official_prize == (
                    original[any_prize_field] if any_prize_field is not None else None
                )
                assert normalized.execution_status == (
                    original[status_field] if status_field is not None else None
                )
                assert normalized.original_source_sha256 == source.artifact_sha256


def test_missing_source_invalid_K_and_missing_values_keep_explicit_meaning() -> None:
    dataset = B649ResearchRecordArchiveReader(ARCHIVE_ROOT).read()

    with pytest.raises(B649ResearchRecordSourceNotFound):
        dataset.source("not-an-authorized-source")
    with pytest.raises(B649ResearchRecordInvalidFilter):
        dataset.query_records(
            next(iter(EXPECTED_COUNTS)),
            target_draw=None,
            arm=None,
            K=4,
            limit=10,
            offset=0,
        )

    decision = dataset.source("NUMBER2_D_DECISION_OBJECTIVE_W50_1317_20261101_R1")._records[0]
    special = dataset.source("NUMBER2_D_SPECIAL_LAG_BUCKET_W50_K235_20261102_R1")._records[0]
    assert decision.execution_status is None
    assert "execution_status" in decision.null_reasons
    assert special.any_official_prize is None
    assert "any_official_prize" in special.null_reasons


def test_archive_checksum_and_member_escape_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reader_module, "B649_RESEARCH_RECORD_ARCHIVE_SHA256", "0" * 64)
    with pytest.raises(B649ResearchRecordArchiveDataError, match="archive checksum"):
        B649ResearchRecordArchiveReader(ARCHIVE_ROOT).read()

    for unsafe in ("../outside.jsonl", "/absolute/member.jsonl", "folder\\item.jsonl"):
        with pytest.raises(B649ResearchRecordArchiveDataError, match="unsafe member"):
            reader_module._validate_archive_member_name(unsafe)


def test_source_sha256_is_the_manifest_pinned_jsonl_hash() -> None:
    manifest = json.loads((ARCHIVE_ROOT / "archive_manifest.json").read_text(encoding="utf-8"))
    files = {item["archive_relative_path"]: item for item in manifest["files"]}
    coverage = manifest["raw_backtest_coverage"]["formal_primary_sources"]
    dataset = B649ResearchRecordArchiveReader(ARCHIVE_ROOT).read()

    with zipfile.ZipFile(ARCHIVE_ROOT / "backtest_bundle.zip") as archive:
        for item in coverage:
            source = dataset.source(item["source_task_id"])
            assert source.artifact_sha256 == files[item["archive_relative_path"]]["sha256"]
            assert (
                hashlib.sha256(archive.read(item["archive_relative_path"])).hexdigest()
                == source.artifact_sha256
            )
