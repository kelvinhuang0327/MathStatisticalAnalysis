from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lottolab.domain.biglotto_full_strategy_catalog import (
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.infrastructure.biglotto_multi_ticket_projection_builder import (
    METRICS_UNAVAILABLE_STRATEGY_IDS,
    B649ProjectionBuildError,
    build_b649_projection_bytes,
    expected_report_manifest,
)
from lottolab.infrastructure.biglotto_multi_ticket_record_reader import (
    PackagedB649MultiTicketRecordReader,
)


def test_committed_evidence_pins_all_135_backtested_strategies() -> None:
    manifest = expected_report_manifest()

    assert len(manifest) == 53
    assert sum(len(report.strategy_ids) for report in manifest) == 135
    assert len({report.report_file_sha256 for report in manifest}) == 53
    assert len(
        {
            strategy_id
            for report in manifest
            for strategy_id in report.strategy_ids
        }
    ) == 135


def test_builder_refuses_incomplete_explicit_report_set() -> None:
    with pytest.raises(
        B649ProjectionBuildError,
        match=r"missing=133 unexpected=0",
    ):
        build_b649_projection_bytes(())


def test_metrics_unavailable_strategy_ids_are_pinned_backtested_replay_exact2() -> None:
    catalog = load_full_strategy_catalog()
    by_id = {record.strategy_id: record for record in catalog.records}

    assert len(METRICS_UNAVAILABLE_STRATEGY_IDS) == 2
    for strategy_id in METRICS_UNAVAILABLE_STRATEGY_IDS:
        record = by_id[strategy_id]
        assert record.reproduction_status is ReproductionStatus.BACKTESTED
        assert record.legacy_method_id in (
            "tools/backtest_biglotto_5bet_ts3markov.py",
            "tools/predict_biglotto_triple_strike.py",
        )


def test_manifest_still_pins_metrics_unavailable_strategy_provenance() -> None:
    manifest = expected_report_manifest()
    covered = {
        strategy_id for report in manifest for strategy_id in report.strategy_ids
    }
    # The manifest legitimately still carries exact2's pinned provenance
    # (used for the metrics-unavailable records' report_file_sha256); the
    # builder simply never requires it to be supplied through report_paths.
    assert covered >= METRICS_UNAVAILABLE_STRATEGY_IDS


def test_builder_rejects_symlinked_report_before_reading_it(
    tmp_path: Path,
) -> None:
    target = tmp_path / "report.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "report-link.json"
    link.symlink_to(target)

    with pytest.raises(
        B649ProjectionBuildError,
        match="regular non-symlink file",
    ):
        build_b649_projection_bytes((link,))


def test_packaged_projection_preserves_sealed_and_fresh_provenance() -> None:
    dataset = PackagedB649MultiTicketRecordReader().read()
    authority_by_strategy = {
        record.strategy_id: record.authority_mode
        for record in dataset.records
    }

    assert dataset.source_report_count == 52
    assert dataset.projection_sha256 == (
        "82f69939716e82d5896769b58886a300d890247c263f29f4df0c0eac534be2c4"
    )
    assert sum(
        authority == "HISTORICAL_SEALED_EVIDENCE_V1"
        for authority in authority_by_strategy.values()
    ) == 36
    assert sum(
        authority == "FRESH_CURRENT_CATALOG_REPRODUCTION_V1"
        for authority in authority_by_strategy.values()
    ) == 97


def test_packaged_k2_k3_successor_is_pinned_complete_and_legacy_preserving() -> None:
    data_root = Path("src/lottolab/strategies/data")
    source_raw = (
        data_root / "biglotto_multi_ticket_historical_records_v1.json"
    ).read_bytes()
    successor_raw = (
        data_root / "biglotto_multi_ticket_historical_records_v2.json"
    ).read_bytes()
    source = json.loads(source_raw)
    successor = json.loads(successor_raw)
    canonical_without_checksum = json.dumps(
        {
            key: value
            for key, value in successor.items()
            if key != "projection_sha256"
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    assert hashlib.sha256(successor_raw).hexdigest() == (
        "a3b22ae301d5f40568de77124aea6e3368af38e539623f4263aa87f20210c88a"
    )
    assert successor["projection_schema_version"] == (
        "B649_MULTI_TICKET_HISTORICAL_RECORDS_V3"
    )
    assert successor["projection_version"] == "2.0.0"
    assert hashlib.sha256(canonical_without_checksum).hexdigest() == successor[
        "projection_sha256"
    ]
    assert successor["source_projection"] == {
        "file_sha256": hashlib.sha256(source_raw).hexdigest(),
        "projection_schema_version": source["projection_schema_version"],
        "projection_sha256": source["projection_sha256"],
    }
    assert successor["records"] == source["records"]
    assert successor["source_reports"] == source["source_reports"]
    assert successor["ticket_counts"] == [2, 3, 5, 10, 15, 20]
    assert successor["criterion"] == "OFFICIAL_ANY_PRIZE"

    exact_records = successor["exact_native_records"]
    identities = {
        (row["strategy_id"], row["ticket_count"], row["window"])
        for row in exact_records
    }
    assert len(exact_records) == len(identities) == 221 * 2 * 4
    assert successor["available_strategy_count_by_exact_ticket_count"] == {
        "2": 19,
        "3": 27,
    }
    assert sum(row["metric_status"] == "AVAILABLE" for row in exact_records) == 181
    unavailable = [
        row for row in exact_records if row["metric_status"] == "UNAVAILABLE"
    ]
    assert all(row["rankable"] is False for row in unavailable)
    assert all(row["official_any_prize_count"] is None for row in unavailable)
    assert all(row["official_any_prize_rate"] is None for row in unavailable)
    assert all(row["coverage"] is None for row in unavailable)

    source_inputs = successor["source_inputs"]
    canonical_inputs = json.dumps(
        source_inputs,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert successor["source_input_count"] == len(source_inputs) == 52
    assert hashlib.sha256(canonical_inputs).hexdigest() == successor[
        "source_input_manifest_sha256"
    ]
    assert successor["dataset"] == {
        "cutoff_draw_date": "2026-07-24",
        "cutoff_draw_number": "115000073",
        "dataset_id": "b649-canonical-replay-universe-2149",
        "dataset_version": (
            "B649_CANONICAL_REPLAY_UNIVERSE_2149_2007-01-02_2026-07-24_V1"
        ),
        "first_draw_date": "2007-01-02",
        "first_draw_number": "96000001",
        "logical_dataset_sha256s": [
            "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b",
            "b62a7b71a0c445a1c3532a72aade92b63824bd483aa5d97e4bf6dd32f7f6752e",
        ],
        "source_sha256": (
            "b62a7b71a0c445a1c3532a72aade92b63824bd483aa5d97e4bf6dd32f7f6752e"
        ),
        "target_draw_count": 2149,
        "target_sequence_sha256": (
            "14876e0088513613125851700f6ae05772811a70a3f17c71550dd93817f6db75"
        ),
    }
    assert successor["windows"]["FULL"] == {
        "available_draws": 2149,
        "complete": True,
        "first_draw_date": "2007-01-02",
        "first_draw_number": "96000001",
        "last_draw_date": "2026-07-24",
        "last_draw_number": "115000073",
        "requested_draws": 2149,
    }


def test_packaged_k2_k3_successor_keeps_two_prior_unavailable_identities_null() -> None:
    path = Path(
        "src/lottolab/strategies/data/"
        "biglotto_multi_ticket_historical_records_v2.json"
    )
    successor = json.loads(path.read_bytes())
    unavailable = [
        row
        for row in successor["exact_native_records"]
        if row["strategy_id"] in METRICS_UNAVAILABLE_STRATEGY_IDS
    ]

    assert len(unavailable) == 2 * 2 * 4
    assert {row["metric_status"] for row in unavailable} == {"UNAVAILABLE"}
    assert {row["native_ticket_count_classification"] for row in unavailable} == {
        "SOURCE_METRICS_UNAVAILABLE"
    }
    assert {row["unavailable_reason"] for row in unavailable} == {
        "FROZEN_PREDICTION_OUTPUT_AND_PRODUCER_UNAVAILABLE"
    }
    assert all(row["official_any_prize_count"] is None for row in unavailable)
    assert all(row["official_any_prize_rate"] is None for row in unavailable)
