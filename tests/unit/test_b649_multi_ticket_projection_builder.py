from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path
from types import FrameType
from typing import cast

import pytest

from lottolab.application.biglotto_multi_ticket_records import B649HistoryWindow
from lottolab.domain.biglotto_full_strategy_catalog import (
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.infrastructure.biglotto_multi_ticket_projection_builder import (
    METRICS_UNAVAILABLE_STRATEGY_IDS,
    B649ProjectionBuildError,
    build_b649_k5_projection_bytes,
    build_b649_k10_projection_bytes,
    build_b649_projection_bytes,
    expected_report_manifest,
)
from lottolab.infrastructure.biglotto_multi_ticket_record_reader import (
    K5_AUTHORITY,
    K5_PROJECTION_RESOURCE_NAME,
    K10_AUTHORITY,
    K10_PROJECTION_RESOURCE_NAME,
    B649ExactNativeRecordProjectionError,
    PackagedB649K5RecordReader,
    PackagedB649K10RecordReader,
    PackagedB649MultiTicketRecordReader,
    parse_b649_k5_projection,
    parse_b649_k10_projection,
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


# K10 uses published evidence only. These tests never regenerate historical metrics.


def test_k10_materialization_twice_preserves_every_source_byte_and_published_field() -> None:
    manifest = Path(str(K10_AUTHORITY["manifest_locator"]))
    ranking = Path(str(K10_AUTHORITY["source_ranking_locator"]))
    evidence = manifest.parent / "target_evidence.jsonl"
    if not manifest.exists():
        pytest.skip("offline materialization requires the explicitly pinned producer authority")
    paths = (manifest, evidence, ranking)
    before = tuple(p.read_bytes() for p in paths)
    calls: list[str] = []

    def profile(frame: FrameType, event: str, _arg: object) -> None:
        if event == "call":
            module = str(frame.f_globals.get("__name__", ""))
            if any(token in module for token in ("backtest", "replay", "baseline", "ranking")):
                calls.append(f"{module}.{frame.f_code.co_name}")

    sys.setprofile(profile)
    try:
        first = build_b649_k10_projection_bytes(*paths)
        second = build_b649_k10_projection_bytes(*paths)
    finally:
        sys.setprofile(None)
    assert calls == [], calls
    assert (
        first
        == second
        == (Path("src/lottolab/strategies/data") / K10_PROJECTION_RESOURCE_NAME).read_bytes()
    )
    assert tuple(p.read_bytes() for p in paths) == before
    producer = json.loads(before[2])["leaderboards"]["K10"]
    dataset = parse_b649_k10_projection(first)
    assert len(dataset.records) == 8
    for window, board in producer.items():
        rows = [asdict(row) for row in dataset.records if row.window.value == window]
        assert len(rows) == 2
        for order, (row, published) in enumerate(zip(rows, board["rankings"], strict=True), 1):
            assert {key: row[key] for key in published} == published
            assert row["source_order"] == order
            assert row["official_rank"] == published["rank"]
            assert row["position"] is None
            assert row["strategy_version"] == "v0.1"
            assert row["catalog_strategy_version"] != row["strategy_version"]


@pytest.mark.parametrize("source_index", [0, 1, 2])
def test_k10_materialization_rejects_each_bad_source_hash(
    monkeypatch: pytest.MonkeyPatch,
    source_index: int,
) -> None:
    manifest = Path(str(K10_AUTHORITY["manifest_locator"]))
    paths = (
        manifest,
        manifest.parent / "target_evidence.jsonl",
        Path(str(K10_AUTHORITY["source_ranking_locator"])),
    )
    if not manifest.exists():
        pytest.skip("offline materialization requires the explicitly pinned producer authority")
    read = Path.read_bytes
    def corrupted_read(path: Path) -> bytes:
        return b"corrupted" if path == paths[source_index] else read(path)

    monkeypatch.setattr(Path, "read_bytes", corrupted_read)
    with pytest.raises(B649ProjectionBuildError, match="checksum"):
        build_b649_k10_projection_bytes(*paths)


def _k10_document() -> dict[str, object]:
    return json.loads(
        (Path("src/lottolab/strategies/data") / K10_PROJECTION_RESOURCE_NAME).read_bytes()
    )


def _k10_encode(document: dict[str, object]) -> bytes:
    payload = {k: v for k, v in document.items() if k != "projection_sha256"}
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    document["projection_sha256"] = hashlib.sha256(canonical).hexdigest()
    return json.dumps(document).encode()


@pytest.mark.parametrize(
    "defect",
    [
        "checksum",
        "schema",
        "universe",
        "duplicate",
        "missing",
        "extra",
        "authority",
        "source_order",
        "position",
        "version",
        "decimal",
    ],
)
def test_k10_projection_rejects_corrupted_closed_contract(defect: str) -> None:
    document = _k10_document()
    rows = cast(list[dict[str, object]], document["records"])
    if defect == "checksum":
        document["projection_sha256"] = "0" * 64
    elif defect == "schema":
        document["projection_schema_version"] = "wrong"
    elif defect == "universe":
        rows[0]["strategy_id"] = "wrong"
    elif defect == "duplicate":
        rows[1] = rows[0].copy()
    elif defect == "missing":
        rows.pop()
    elif defect == "extra":
        rows[0]["unexpected"] = 0
    elif defect == "authority":
        cast(dict[str, object], rows[0]["provenance"])["authority_head"] = "0" * 40
    elif defect == "source_order":
        rows[0]["source_order"] = 2
    elif defect == "position":
        rows[0]["position"] = 1
    elif defect == "version":
        rows[0]["strategy_version"] = "legacy"
    elif defect == "decimal":
        rows[0]["official_any_prize_rate"] = 0.2
    raw = json.dumps(document).encode() if defect == "checksum" else _k10_encode(document)
    with pytest.raises(B649ExactNativeRecordProjectionError):
        parse_b649_k10_projection(raw)


def test_k10_selected_window_metric_failure_does_not_poison_other_windows() -> None:
    document = _k10_document()
    rows = cast(list[dict[str, object]], document["records"])
    rows[0]["official_any_prize_rate"] = "corrupt"
    raw = _k10_encode(document)
    with pytest.raises(B649ExactNativeRecordProjectionError):
        parse_b649_k10_projection(raw, B649HistoryWindow.FULL)
    assert len(parse_b649_k10_projection(raw, B649HistoryWindow.RECENT_50).records) == 2


def test_k10_available_full_exclusions_and_authoritative_zero_unranked_unavailable() -> None:
    dataset = PackagedB649K10RecordReader().read(B649HistoryWindow.FULL)
    assert [r.typed_replay_failures_count for r in dataset.records] == [1, 300]
    assert all(r.metric_status == "AVAILABLE" for r in dataset.records)
    document = _k10_document()
    rows = cast(list[dict[str, object]], document["records"])
    rows[0].update(
        rank=None,
        official_rank=None,
        unranked_reason="PRODUCER_UNRANKED",
        official_any_prize_rate="0.000000000000000000",
        official_any_prize_numerator=0,
    )
    rows[1].update(
        rank=None,
        official_rank=None,
        metric_status="UNAVAILABLE",
        unranked_reason="PRODUCER_UNAVAILABLE",
        unavailable_reason="METRIC_UNAVAILABLE",
    )
    for key in (
        "official_any_prize_rate",
        "official_random_baseline",
        "baseline_delta",
        "coverage",
        "official_any_prize_numerator",
        "official_any_prize_denominator",
        "best_prize_counts",
    ):
        rows[1][key] = None
    parsed = parse_b649_k10_projection(_k10_encode(document), B649HistoryWindow.FULL).records
    assert parsed[0].official_any_prize_numerator == 0
    assert parsed[0].official_any_prize_rate == "0.000000000000000000"
    assert parsed[0].official_rank is None and parsed[0].source_order == 1
    assert parsed[1].official_any_prize_rate is None
    assert parsed[1].unavailable_reason == "METRIC_UNAVAILABLE"


# K5 is a projection of a shared sealed publication, including an uncatalogued producer.
def _k5_paths() -> tuple[Path, Path, Path]:
    return (
        Path(str(K5_AUTHORITY["manifest_locator"])),
        Path(str(K5_AUTHORITY["target_evidence_locator"])),
        Path(str(K5_AUTHORITY["source_ranking_locator"])),
    )


def _k5_document() -> dict[str, object]:
    return json.loads(
        (Path("src/lottolab/strategies/data") / K5_PROJECTION_RESOURCE_NAME).read_bytes()
    )


def test_k5_materializes_twice_without_evaluation_and_copies_all_source_fields() -> None:
    paths = _k5_paths()
    if not paths[0].exists():
        pytest.skip("explicit offline K5 authorities are not installed")
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    calls: list[str] = []

    def profile(frame: FrameType, event: str, _arg: object) -> None:
        module = str(frame.f_globals.get("__name__", ""))
        if event == "call" and any(
            t in module for t in ("backtest", "replay", "baseline", "ranking", "evaluator")
        ):
            calls.append(f"{module}.{frame.f_code.co_name}")

    sys.setprofile(profile)
    try:
        first = build_b649_k5_projection_bytes(*paths)
        second = build_b649_k5_projection_bytes(*paths)
    finally:
        sys.setprofile(None)
    assert calls == []
    assert (
        first
        == second
        == (Path("src/lottolab/strategies/data") / K5_PROJECTION_RESOURCE_NAME).read_bytes()
    )
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths] == before
    published = json.loads(paths[2].read_bytes())["leaderboards"]["K5"]
    data = parse_b649_k5_projection(first)
    assert len(data.records) == 20
    assert all(row.metric_status == "AVAILABLE" for row in data.records)
    for window, board in published.items():
        rows = [asdict(r) for r in data.records if r.window.value == window]
        assert len(rows) == 5
        assert {r["strategy_id"] for r in rows} == set(
            cast(list[str], K5_AUTHORITY["strategy_universe"])
        )
        assert [asdict(t) for t in data.ties_by_window[window]] == board["ties"]
        for order, (row, producer) in enumerate(zip(rows, board["rankings"], strict=True), 1):
            assert {key: row[key] for key in producer} == producer
            assert row["official_rank"] == producer["rank"]
            assert row["source_order"] == order == producer["position"]
    composite = [r for r in data.records if r.strategy_id.startswith("legacy_composite__")]
    assert len(composite) == 4
    for row in composite:
        assert row.catalog_strategy_version is row.legacy_method_id is row.source_path is None
        assert row.method_family is row.reproduction_status is None
        assert row.metric_status == "AVAILABLE" and row.official_rank is not None
    recent = [r for r in data.records if r.window is B649HistoryWindow.RECENT_50]
    assert [r.rank for r in recent] == [1, 2, 2, 2, 5]
    assert [r.position for r in recent] == [1, 2, 3, 4, 5]
    assert [r.source_order for r in recent] == [1, 2, 3, 4, 5]
    assert data.provenance.sealed_manifest_k_values == (2, 3, 5)
    assert data.provenance.target_evidence_k_values == (2, 3, 5)
    assert data.provenance.source_ranking_k_values == (2, 3, 5, 10)


@pytest.mark.parametrize("source_index", [0, 1, 2])
def test_k5_refuses_wrong_source_bytes(monkeypatch: pytest.MonkeyPatch, source_index: int) -> None:
    paths = _k5_paths()
    read = Path.read_bytes
    def corrupted_read(path: Path) -> bytes:
        return b"corrupt" if path == paths[source_index] else read(path)

    monkeypatch.setattr(Path, "read_bytes", corrupted_read)
    with pytest.raises(B649ProjectionBuildError, match="checksum"):
        build_b649_k5_projection_bytes(*paths)


@pytest.mark.parametrize(
    "source,field,value",
    [
        ("manifest", "schema_version", "bad"),
        ("ranking", "schema_version", "bad"),
        ("manifest", "run_id", "bad"),
        ("ranking", "run_id", "bad"),
        ("ranking", "cutoff", "115000083"),
        ("ranking", "budgets", [5]),
        ("ranking", "partition_keys", ["strategy_id"]),
    ],
)
def test_k5_checks_source_semantics_even_with_matching_hash(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    field: str,
    value: object,
) -> None:
    paths = _k5_paths()
    path = paths[0 if source == "manifest" else 2]
    document = json.loads(path.read_bytes())
    document[field] = value
    raw = json.dumps(document).encode()
    read = Path.read_bytes
    def replaced_read(candidate: Path) -> bytes:
        return raw if candidate == path else read(candidate)
    monkeypatch.setattr(Path, "read_bytes", replaced_read)
    monkeypatch.setitem(
        K5_AUTHORITY,
        "sealed_manifest_sha256" if source == "manifest" else "source_ranking_sha256",
        hashlib.sha256(raw).hexdigest(),
    )
    with pytest.raises(B649ProjectionBuildError):
        build_b649_k5_projection_bytes(*paths)


@pytest.mark.parametrize(
    "defect",
    [
        "checksum",
        "schema",
        "universe",
        "duplicate",
        "missing",
        "K",
        "cutoff",
        "run_id",
        "scope",
        "ties",
        "position",
        "source_order",
        "rank",
        "decimal",
    ],
)
def test_k5_rejects_corrupted_projection(defect: str) -> None:
    document = _k5_document()
    rows = cast(list[dict[str, object]], document["records"])
    provenance = cast(dict[str, object], document["provenance"])
    if defect == "checksum":
        document["projection_sha256"] = "0" * 64
    elif defect == "schema":
        document["projection_schema_version"] = "bad"
    elif defect == "universe":
        rows[0]["strategy_id"] = "bad"
    elif defect == "duplicate":
        rows[1] = rows[0].copy()
    elif defect == "missing":
        rows.pop()
    elif defect == "K":
        rows[0]["ticket_count"] = 10
    elif defect in ("cutoff", "run_id"):
        provenance[defect] = "bad"
    elif defect == "scope":
        provenance["sealed_manifest_k_values"] = [5]
    elif defect == "ties":
        cast(dict[str, object], document["ties_by_window"])["RECENT_50"] = []
    elif defect in ("position", "source_order"):
        rows[0][defect] = 2
    elif defect == "rank":
        rows[0]["official_rank"] = 5
    else:
        rows[0]["official_any_prize_rate"] = 0.2
    with pytest.raises(B649ExactNativeRecordProjectionError):
        parse_b649_k5_projection(
            json.dumps(document).encode() if defect == "checksum" else _k10_encode(document)
        )


def test_k5_incomplete_observations_zero_null_and_selected_window_failures() -> None:
    rows = PackagedB649K5RecordReader().read(B649HistoryWindow.FULL).records
    assert rows[0].typed_replay_failures_count == 500
    assert rows[0].evaluated_draws == rows[0].official_any_prize_denominator == 1666
    assert rows[0].metric_status == "AVAILABLE"
    document = _k5_document()
    values = cast(list[dict[str, object]], document["records"])
    values[0].update(
        official_any_prize_numerator=0,
        official_any_prize_rate="0.000000000000000000",
        best_prize_counts={"GENERAL": 0},
    )
    values[1].update(
        metric_status="UNAVAILABLE",
        metric_unavailable_reason="EXECUTION_FAILURE",
        rank=None,
        official_rank=None,
    )
    for key in (
        "official_any_prize_rate",
        "official_random_baseline",
        "baseline_delta",
        "coverage",
        "official_any_prize_numerator",
        "official_any_prize_denominator",
        "best_prize_counts",
    ):
        values[1][key] = None
    parsed = parse_b649_k5_projection(_k10_encode(document), B649HistoryWindow.FULL).records
    assert parsed[0].official_any_prize_numerator == 0
    assert parsed[0].official_any_prize_rate == "0.000000000000000000"
    assert parsed[0].best_prize_counts == {"GENERAL": 0}
    assert parsed[0].replay_status_counts == rows[0].replay_status_counts
    assert parsed[1].official_any_prize_rate is None
    assert parsed[1].metric_unavailable_reason == "EXECUTION_FAILURE"
    values[0]["official_any_prize_rate"] = "corrupt"
    raw = _k10_encode(document)
    with pytest.raises(B649ExactNativeRecordProjectionError):
        parse_b649_k5_projection(raw, B649HistoryWindow.FULL)
    assert len(parse_b649_k5_projection(raw, B649HistoryWindow.RECENT_50).records) == 5


@pytest.mark.parametrize("mask", [1, 2, 3, 4, 5, 6])
def test_k5_cli_requires_all_three_inputs(mask: int) -> None:
    from tools.build_b649_multi_ticket_historical_records import main

    args = ["--output", "unused.json"]
    for index, flag in enumerate(("--k5-manifest", "--k5-evidence", "--k5-ranking")):
        if mask & (1 << index):
            args.extend((flag, "unused"))
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2


@pytest.mark.parametrize(
    "other",
    [
        "--report",
        "--source-projection",
        "--replay-input",
        "--dataset-source",
        "--k10-manifest",
        "--k10-evidence",
        "--k10-ranking",
    ],
)
def test_k5_cli_modes_are_exclusive(other: str) -> None:
    from tools.build_b649_multi_ticket_historical_records import main

    with pytest.raises(SystemExit) as error:
        main(
            [
                "--output",
                "unused",
                "--k5-manifest",
                "unused",
                "--k5-evidence",
                "unused",
                "--k5-ranking",
                "unused",
                other,
                "unused",
            ]
        )
    assert error.value.code == 2


def test_k5_cli_refuses_overwrite(tmp_path: Path) -> None:
    from tools.build_b649_multi_ticket_historical_records import main

    output = tmp_path / "projection.json"
    output.write_bytes(b"existing")
    args = ["--output", str(output)]
    for flag, path in zip(
        ("--k5-manifest", "--k5-evidence", "--k5-ranking"), _k5_paths(), strict=True
    ):
        args.extend((flag, str(path)))
    assert main(args) == 2
    assert output.read_bytes() == b"existing"
