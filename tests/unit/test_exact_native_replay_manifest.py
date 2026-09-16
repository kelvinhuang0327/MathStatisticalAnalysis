"""Physical shard provenance contract; no strategy, database, or filesystem replay."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from lottolab.application.use_cases import shard_exact_native_replay as orchestrator
from lottolab.evidence.exact_native_replay_manifest import (
    EVIDENCE_FILENAME,
    METADATA_FILENAME,
    build_sealed_manifest,
    canonical_json_bytes,
)


def _boundary(index: int, start: int, end: int) -> dict[str, object]:
    return {"shard_index": index, "start_target_index": start, "end_target_index": end}


def _manifest_arguments(**topology: object) -> dict[str, object]:
    return {
        "run_id": "manifest-contract",
        "source": {},
        "catalog": {},
        "draw_authority": {},
        "max_visible_draw": "5",
        "later_draws_present_in_authority": False,
        "visible_draw_count": 5,
        "target_windows": {},
        "evidence_sha256": "evidence-hash",
        "evidence_byte_size": 0,
        "evidence_record_count": 0,
        "evidence_status_counts": {},
        "universe": {},
        **topology,
    }


def _manifest(**topology: object) -> dict[str, object]:
    return build_sealed_manifest(**_manifest_arguments(**topology))  # type: ignore[arg-type]


def _parallel_sharding(manifest: Mapping[str, object]) -> Mapping[str, object]:
    contract = cast(Mapping[str, object], manifest["execution_contract"])
    return cast(Mapping[str, object], contract["parallel_sharding"])


@pytest.mark.parametrize("explicit_status", [False, True])
def test_recorded_topology_preserves_actual_uneven_boundaries(explicit_status: bool) -> None:
    boundaries = [_boundary(0, 0, 1), _boundary(1, 1, 5)]
    status = {"provenance_status": "RECORDED"} if explicit_status else {}
    manifest = _manifest(shard_count=2, shard_boundaries=boundaries, **status)
    topology = _parallel_sharding(manifest)
    assert topology == {
        "provenance_status": "RECORDED",
        "shard_count": 2,
        "shard_boundaries": boundaries,
        "sharding_dimension": "OUTER_TARGET_INDEX_RANGE",
        "inner_binding_order_preserved": True,
    }
    boundaries[0]["end_target_index"] = 99
    assert topology["shard_boundaries"] == [_boundary(0, 0, 1), _boundary(1, 1, 5)]


def test_not_recorded_serializes_exactly_with_null_topology() -> None:
    manifest = _manifest(provenance_status="NOT_RECORDED", shard_count=None, shard_boundaries=None)
    expected = {"provenance_status": "NOT_RECORDED", "shard_count": None, "shard_boundaries": None}
    assert _parallel_sharding(manifest) == expected
    assert canonical_json_bytes(_parallel_sharding(manifest)) == (
        b'{"provenance_status":"NOT_RECORDED","shard_boundaries":null,"shard_count":null}\n'
    )
    assert _parallel_sharding(json.loads(canonical_json_bytes(manifest))) == expected


@pytest.mark.parametrize(
    ("status", "count", "boundaries"),
    [
        pytest.param("NOT_RECORDED", 1, None, id="unknown-count-only"),
        pytest.param("NOT_RECORDED", None, [_boundary(0, 0, 5)], id="unknown-boundaries-only"),
        pytest.param("NOT_RECORDED", 1, [_boundary(0, 0, 5)], id="unknown-both-present"),
        pytest.param("NOT_RECORDED", 0, [], id="unknown-falsy-topology"),
        pytest.param("RECORDED", None, None, id="recorded-both-null"),
        pytest.param("RECORDED", 1, None, id="recorded-count-only"),
        pytest.param("RECORDED", None, [_boundary(0, 0, 5)], id="recorded-boundaries-only"),
    ],
)
def test_contradictory_or_partial_topology_is_rejected(
    status: str, count: object, boundaries: object
) -> None:
    with pytest.raises(ValueError, match=status):
        _manifest(provenance_status=status, shard_count=count, shard_boundaries=boundaries)


@pytest.mark.parametrize("missing", ["shard_count", "shard_boundaries"])
@pytest.mark.parametrize("status", ["RECORDED", "NOT_RECORDED"])
def test_omitting_one_topology_argument_is_rejected(missing: str, status: str) -> None:
    arguments = _manifest_arguments(
        provenance_status=status,
        shard_count=1 if status == "RECORDED" else None,
        shard_boundaries=[_boundary(0, 0, 5)] if status == "RECORDED" else None,
    )
    del arguments[missing]
    with pytest.raises(TypeError, match=missing):
        build_sealed_manifest(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize("count", [0, -1, True, 1.0, "1"])
def test_recorded_shard_count_must_be_a_positive_integer(count: object) -> None:
    with pytest.raises(ValueError, match="integer shard_count"):
        _manifest(shard_count=count, shard_boundaries=[_boundary(0, 0, 5)])


@pytest.mark.parametrize(
    "boundaries",
    [
        [],
        "invalid",
        [_boundary(0, 0, 5)],
        [None, _boundary(1, 1, 5)],
        [{}, _boundary(1, 1, 5)],
        [_boundary(1, 0, 1), _boundary(0, 1, 5)],
        [_boundary(0, -1, 1), _boundary(1, 1, 5)],
        [_boundary(0, 0, 2), _boundary(1, 1, 5)],
        [_boundary(0, 0, 1), _boundary(1, 2, 5)],
        [_boundary(0, 0, 1), _boundary(1, 1, 0)],
        [_boundary(0, 0, 1), _boundary(1, 1, 4)],
        [_boundary(0, 0, 1), _boundary(1, 1, 6)],
        [_boundary(False, 0, 1), _boundary(1, 1, 5)],
        [_boundary(0, 0, 1), {**_boundary(1, 1, 5), "end_target_index": 5.0}],
    ],
)
def test_invalid_recorded_boundaries_are_rejected(boundaries: object) -> None:
    with pytest.raises(ValueError, match="RECORDED"):
        _manifest(shard_count=2, shard_boundaries=boundaries)


@pytest.mark.parametrize("status", ["UNKNOWN", "recorded", "", None])
def test_only_two_provenance_states_are_accepted(status: object) -> None:
    with pytest.raises(ValueError, match="provenance_status"):
        _manifest(provenance_status=status, shard_count=1, shard_boundaries=[_boundary(0, 0, 5)])


@pytest.mark.parametrize("shard_count", [1, 2, 7])
def test_orchestrator_seals_recorded_topology_without_replay(
    monkeypatch: pytest.MonkeyPatch, shard_count: int
) -> None:
    """Exercise the existing caller, replacing all external work with memory-only mocks."""

    output = MagicMock(spec=Path)
    shards = MagicMock(spec=Path)
    merged = MagicMock(spec=Path)
    manifest_path = MagicMock(spec=Path)
    output.__truediv__.side_effect = {
        "shards": shards,
        EVIDENCE_FILENAME: merged,
        "sealed_manifest.json": manifest_path,
    }.__getitem__
    expected_boundaries = [
        _boundary(index, index * 5 // shard_count, (index + 1) * 5 // shard_count)
        for index in range(shard_count)
    ]
    shard_paths: dict[str, MagicMock] = {}
    for boundary in expected_boundaries:
        index = cast(int, boundary["shard_index"])
        row_count = cast(int, boundary["end_target_index"]) - cast(
            int, boundary["start_target_index"]
        )
        shard = MagicMock(spec=Path)
        evidence = MagicMock(spec=Path)
        metadata = MagicMock(spec=Path)
        metadata.read_text.return_value = '{"binding_count":1}'
        evidence.is_file.return_value = metadata.is_file.return_value = True
        text_input = MagicMock()
        text_input.__enter__.return_value = ['{"replay_status":"COMPLETE"}\n'] * row_count
        binary_input = MagicMock()
        binary_input.__enter__.return_value.read.side_effect = [b"evidence", b""]
        evidence.open.side_effect = [text_input, binary_input]
        shard.__truediv__.side_effect = {
            EVIDENCE_FILENAME: evidence,
            METADATA_FILENAME: metadata,
            "stdout.log": MagicMock(spec=Path),
            "stderr.log": MagicMock(spec=Path),
        }.__getitem__
        shard_paths[f"shard_{index:03d}"] = shard
    shards.__truediv__.side_effect = shard_paths.__getitem__
    monkeypatch.setattr(orchestrator, "source_freeze", MagicMock(return_value={}))
    monkeypatch.setattr(orchestrator, "catalog_freeze", MagicMock(return_value=((object(),), {})))
    monkeypatch.setattr(orchestrator, "load_authoritative_draws", MagicMock(return_value=((), {})))
    monkeypatch.setattr(orchestrator, "freeze_visible_draws", MagicMock(return_value=(None,) * 5))
    monkeypatch.setattr(orchestrator, "compute_target_windows", MagicMock(return_value={}))
    monkeypatch.setattr(orchestrator, "sha256_file", MagicMock(return_value="unchanged-hash"))
    process = MagicMock()
    process.wait.return_value = 0
    popen = MagicMock(return_value=process)
    monkeypatch.setattr(orchestrator.subprocess, "Popen", popen)
    write_manifest = MagicMock()
    monkeypatch.setattr(orchestrator, "write_json_file", write_manifest)

    result = orchestrator.run_sharded_exact_native_replay(
        orchestrator.ShardExactNativeReplayRequest(
            run_id="manifest-contract",
            draw_authority_db=Path("unused-draw-authority"),
            repository_root=Path("unused-repository"),
            output_root=output,
            shard_count=shard_count,
        )
    )

    assert popen.call_count == shard_count
    assert result.total_rows == 5
    assert result.manifest_path is manifest_path
    write_manifest.assert_called_once()
    assert write_manifest.call_args.args[0] is manifest_path
    assert _parallel_sharding(write_manifest.call_args.args[1]) == {
        "provenance_status": "RECORDED",
        "shard_count": shard_count,
        "shard_boundaries": expected_boundaries,
        "sharding_dimension": "OUTER_TARGET_INDEX_RANGE",
        "inner_binding_order_preserved": True,
    }
