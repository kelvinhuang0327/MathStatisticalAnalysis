# pyright: reportPrivateUsage=false

"""Contract tests for the task-owned B649 exact-native replay harness."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from tools import b649_exact_native_replay as replay

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape, StrategyDescriptor
from lottolab.strategies.adapters.base import BetAdapterExecution


def _descriptor(
    strategy_id: str = "fixture_strategy",
    *,
    native_ticket_count: int = 2,
    min_history: int = 1,
) -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id=strategy_id,
        strategy_name=strategy_id,
        version="fixture-v1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path="fixture:Adapter",
        min_history=min_history,
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=native_ticket_count,
    )


def _draw(draw_number: int, *, day: int | None = None) -> replay.Draw:
    return replay.Draw(
        draw_number=str(draw_number),
        draw_date=date(2026, 1, 1) + timedelta(days=day if day is not None else draw_number),
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=7,
    )


def _windows(target: replay.Draw) -> dict[str, dict[str, object]]:
    return {
        name: {"draw_numbers": [target.draw_number]}
        for name, _size in replay.WINDOWS
    }


class _Adapter:
    def __init__(
        self,
        executions: tuple[BetAdapterExecution, ...] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.executions = executions or ()
        self.error = error

    def get_bets_with_emission(
        self,
        history: object,
        lottery_type: LotteryType,
    ) -> tuple[BetAdapterExecution, ...]:
        if self.error is not None:
            raise self.error
        return self.executions


def _two_executions() -> tuple[BetAdapterExecution, ...]:
    return (
        BetAdapterExecution(
            emitted_main_numbers=(6, 5, 4, 3, 2, 1),
            legal_main_numbers=(1, 2, 3, 4, 5, 6),
            special_number=None,
        ),
        BetAdapterExecution(
            emitted_main_numbers=(8, 9, 10, 11, 12, 13),
            legal_main_numbers=(8, 9, 10, 11, 12, 13),
            special_number=None,
        ),
    )


def test_catalog_freeze_has_the_authorized_disjoint_exact_native_universe() -> None:
    descriptors, metadata = replay._catalog_freeze()

    assert len(descriptors) == 38
    assert metadata["k2_count"] == 19
    assert metadata["k3_count"] == 19
    assert metadata["intersection"] == []
    assert all(descriptor.response_shape is ResponseShape.PORTFOLIO for descriptor in descriptors)
    assert {descriptor.native_ticket_count for descriptor in descriptors} == {2, 3}


def test_target_windows_select_latest_common_draws() -> None:
    draws = tuple(_draw(index, day=index) for index in range(1, 801))

    windows = replay._target_windows(draws)

    assert windows["RECENT_50"]["first_target"] == "751"
    assert windows["RECENT_50"]["last_target"] == "800"
    assert len(cast(list[str], windows["RECENT_300"]["draw_numbers"])) == 300
    assert windows["RECENT_750"]["first_target"] == "51"


def test_causal_cutoff_rejects_target_or_future_draws() -> None:
    target = _draw(3, day=3)

    replay._assert_causal_history(target, (_draw(1, day=1), _draw(2, day=2)))
    with pytest.raises(replay.ReplayTaskError, match="CAUSAL_CUTOFF_VIOLATION"):
        replay._assert_causal_history(target, (_draw(1, day=1), target))


def test_replay_cell_preserves_native_order_and_scores_any_prize_at_draw_level() -> None:
    descriptor = _descriptor(native_ticket_count=2, min_history=2)
    target = _draw(3, day=3)
    history = (_draw(1, day=1), _draw(2, day=2))
    binding = replay.RuntimeBinding(
        descriptor=descriptor,
        implementation=_Adapter(_two_executions()),
        adapter_class_name="_Adapter",
        binding_error=None,
    )

    row = replay._replay_cell(binding, target, history, _windows(target))

    assert row["replay_status"] == "COMPLETE"
    assert row["target_outcome_excluded"] is True
    assert row["causal_cutoff_draw_number"] == "2"
    assert row["actual_native_ticket_count"] == 2
    assert row["native_emitted_portfolio"] == [[6, 5, 4, 3, 2, 1], [8, 9, 10, 11, 12, 13]]
    assert row["official_any_prize"] is True
    assert row["best_official_prize"] == "FIRST"
    evaluations = cast(list[dict[str, Any]], row["ticket_evaluations"])
    assert evaluations[0]["official_prize"] == "FIRST"
    assert evaluations[1]["is_winner"] is False


@pytest.mark.parametrize(
    ("descriptor", "adapter", "expected_status"),
    (
        (
            _descriptor(native_ticket_count=2, min_history=3),
            _Adapter(_two_executions()),
            "WINDOW_INELIGIBLE_INCOMPLETE_OBSERVATIONS",
        ),
        (
            _descriptor(native_ticket_count=2),
            _Adapter(_two_executions()[:1]),
            "NATIVE_TICKET_COUNT_VIOLATION",
        ),
        (
            _descriptor(native_ticket_count=2),
            _Adapter(error=RuntimeError("fixture failure")),
            "EXECUTION_FAILURE",
        ),
    ),
)
def test_replay_cell_uses_typed_failure_statuses(
    descriptor: StrategyDescriptor,
    adapter: _Adapter,
    expected_status: str,
) -> None:
    target = _draw(2, day=2)
    history = (_draw(1, day=1),)
    binding = replay.RuntimeBinding(descriptor, adapter, "_Adapter", None)

    row = replay._replay_cell(binding, target, history, _windows(target))

    assert row["replay_status"] == expected_status
    assert row["official_any_prize"] is None
    assert row["native_portfolio"] is None


def _ranking_fixture_manifest_and_rows() -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    k2 = tuple(
        {
            "strategy_id": f"k2_{index}",
            "display_name": f"K2 {index}",
            "native_ticket_count": 2,
        }
        for index in range(5)
    )
    k3 = tuple(
        {
            "strategy_id": f"k3_{index}",
            "display_name": f"K3 {index}",
            "native_ticket_count": 3,
        }
        for index in range(5)
    )
    targets = ["t1", "t2"]
    windows = {
        name: {
            "draw_numbers": targets,
            "first_target": targets[0],
            "last_target": targets[-1],
        }
        for name, _size in replay.WINDOWS
    }
    manifest: dict[str, Any] = {
        "evidence": {"sha256": "e" * 64},
        "catalog": {"strategies": {"k2": list(k2), "k3": list(k3)}},
        "universe": {
            "k2_strategy_ids": [descriptor["strategy_id"] for descriptor in k2],
            "k3_strategy_ids": [descriptor["strategy_id"] for descriptor in k3],
        },
        "target_windows": windows,
    }
    rows: list[dict[str, Any]] = []
    for category in (k2, k3):
        for index, descriptor in enumerate(category):
            for target in targets:
                rows.append(
                    {
                        "strategy_id": descriptor["strategy_id"],
                        "target_draw_number": target,
                        "replay_status": "COMPLETE",
                        "actual_native_ticket_count": descriptor["native_ticket_count"],
                        "official_any_prize": index == 0 or (index == 1 and target == "t1"),
                        "best_official_prize": "FIRST"
                        if index == 0 or (index == 1 and target == "t1")
                        else None,
                    }
                )
    return manifest, tuple(rows)


def test_ranking_aggregates_one_success_per_distinct_target_draw() -> None:
    manifest, rows = _ranking_fixture_manifest_and_rows()

    ranking = cast(dict[str, Any], replay._rank_from_rows(manifest, rows))
    top = cast(
        list[dict[str, Any]],
        ranking["leaderboards"]["K2"]["RECENT_50"]["top5"],
    )

    assert top[0]["strategy_id"] == "k2_0"
    assert top[0]["successful_draws"] == 2
    assert top[0]["observations"] == 2
    assert top[0]["official_any_prize_fraction"] == "1/1"
    assert top[1]["successful_draws"] == 1
    assert ranking["leaderboards"]["K3"]["RECENT_750"]["eligible_count"] == 5


def test_sealed_bundle_detects_evidence_mutation(tmp_path: Path) -> None:
    evidence_path = tmp_path / replay.EVIDENCE_FILENAME
    row = {
        "schema_version": replay.EVIDENCE_SCHEMA,
        "strategy_id": "fixture",
        "target_draw_number": "1",
    }
    evidence_path.write_bytes(replay._canonical_json_bytes(row))
    manifest = {
        "schema_version": replay.MANIFEST_SCHEMA,
        "evidence": {
            "file": replay.EVIDENCE_FILENAME,
            "sha256": replay._sha256_file(evidence_path),
            "byte_size": evidence_path.stat().st_size,
            "record_count": 1,
        },
    }
    replay._write_json(tmp_path / replay.MANIFEST_FILENAME, manifest)

    loaded_manifest, rows, _manifest_sha = replay._load_sealed_bundle(tmp_path)
    assert loaded_manifest["schema_version"] == replay.MANIFEST_SCHEMA
    assert len(rows) == 1

    with evidence_path.open("ab") as handle:
        handle.write(replay._canonical_json_bytes({**row, "target_draw_number": "2"}))
    with pytest.raises(replay.ReplayTaskError, match="FINGERPRINT_MISMATCH"):
        replay._load_sealed_bundle(tmp_path)


def test_canonical_json_hash_is_order_independent() -> None:
    first = replay._canonical_json_bytes({"b": 2, "a": [1, True]})
    second = replay._canonical_json_bytes({"a": [1, True], "b": 2})

    assert first == second
    assert replay._sha256_bytes(first) == replay._sha256_bytes(second)
