"""Golden-slice integration test: the real production catalog and registry-loaded
adapters, driven end to end through ReplayHistoricalPredictions against a
committed synthetic BIG_LOTTO causal-history fixture.

"Integration" here means cross-use-case composition — BuildCausalHistory,
GenerateOneBet, and the real ``production_catalog()``/``ExecutableRegistry``
wired together — never real SQLite or I/O; the causal-history boundary is
still a fake reader over the committed fixture, exactly as the golden-slice
scope requires (target-native evidence, not LotteryNew parity).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from lottolab.application.ports import TargetDrawNotFoundError
from lottolab.application.use_cases.build_causal_history import BuildCausalHistory
from lottolab.application.use_cases.generate_bet import build_production_generate_one_bet
from lottolab.application.use_cases.replay_historical_predictions import (
    ReplayHistoricalPredictions,
    ReplayHistoricalPredictionsInput,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_history import ReplayCausalDrawRow
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.evidence.replay_artifact import (
    build_replay_artifact,
    deserialize_replay_artifact,
    serialize_replay_artifact,
)
from lottolab.strategies.adapters.biglotto_selected import (
    BigLottoDeviation2BetAdapter,
    BigLottoSocialWisdomAntiPopularityAdapter,
    BigLottoZoneSplit3BetBet1Adapter,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "replay" / "synthetic_biglotto_causal_history.json"
)

_STRATEGY_IDS = (
    BigLottoSocialWisdomAntiPopularityAdapter.strategy_id,
    BigLottoZoneSplit3BetBet1Adapter.strategy_id,
    BigLottoDeviation2BetAdapter.strategy_id,
)


class _FixtureDrawHistoryReader:
    """A fake, target-native reader over the committed synthetic fixture.

    Deliberately mirrors the real ``DrawHistoryReader`` causal contract: it
    only ever returns rows strictly before the target — rows beyond
    ``pre_target_row_count`` in the fixture exist precisely so a leakage bug
    would be caught (see ``test_no_future_leakage_...`` below).
    """

    def __init__(self, fixture: dict[str, Any]) -> None:
        self._all_rows = tuple(
            ReplayCausalDrawRow(
                draw_number=row["draw_number"],
                draw_date=date.fromisoformat(row["draw_date"]),
                main_numbers=tuple(row["main_numbers"]),
                special_number=row["special_number"],
            )
            for row in fixture["history_rows"]
        )
        self._pre_target_row_count = {
            target["draw_number"]: target["pre_target_row_count"] for target in fixture["targets"]
        }
        self.calls: list[tuple[LotteryType, str, int | None]] = []

    def read_causal_history(
        self,
        lottery_type: LotteryType,
        target_draw_number: str,
        *,
        maximum_history_draws: int | None = None,
    ) -> tuple[ReplayCausalDrawRow, ...]:
        self.calls.append((lottery_type, target_draw_number, maximum_history_draws))
        if target_draw_number not in self._pre_target_row_count:
            raise TargetDrawNotFoundError(target_draw_number)
        causal = self._all_rows[: self._pre_target_row_count[target_draw_number]]
        if maximum_history_draws is None:
            return causal
        return causal[-maximum_history_draws:]


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _targets(fixture: dict[str, Any]) -> tuple[ReplayTarget, ...]:
    return tuple(
        ReplayTarget(
            draw_number=entry["draw_number"],
            draw_date=date.fromisoformat(entry["draw_date"]),
        )
        for entry in fixture["targets"]
    )


def _use_case(reader: _FixtureDrawHistoryReader) -> ReplayHistoricalPredictions:
    catalog = production_catalog()
    generate_one_bet = build_production_generate_one_bet()
    build_causal_history = BuildCausalHistory(lambda: reader)
    return ReplayHistoricalPredictions(build_causal_history, generate_one_bet, catalog)


def test_fixture_declares_the_expected_golden_slice_shape() -> None:
    fixture = _load_fixture()
    assert fixture["lottery_type"] == "BIG_LOTTO"
    assert len(fixture["targets"]) >= 2
    short, long_ = fixture["targets"]
    assert short["pre_target_row_count"] < 100  # exercises deviation's INSUFFICIENT_HISTORY
    assert long_["pre_target_row_count"] >= 100  # exercises deviation's OK path
    # Extra rows beyond the longest target's cutoff exist in the fixture on
    # purpose, to prove a leakage bug would have real data available to leak.
    assert len(fixture["history_rows"]) > long_["pre_target_row_count"]


def test_golden_slice_produces_one_snapshot_per_target_times_strategy() -> None:
    fixture = _load_fixture()
    reader = _FixtureDrawHistoryReader(fixture)
    use_case = _use_case(reader)
    targets = _targets(fixture)

    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="SYNTHETIC_BIG_LOTTO_REPLAY_GOLDEN_R1",
            dataset_version="1",
            targets=targets,
            strategy_ids=_STRATEGY_IDS,
        )
    )

    assert len(result.snapshots) == len(targets) * len(_STRATEGY_IDS)
    for snapshot in result.snapshots:
        assert snapshot.history_status == "OK"
        assert snapshot.strategy_version is not None
        assert snapshot.adapter_strategy_id == snapshot.strategy_id


def test_deviation_strategy_insufficient_on_short_target_ok_on_long_target() -> None:
    fixture = _load_fixture()
    reader = _FixtureDrawHistoryReader(fixture)
    use_case = _use_case(reader)
    short_target, long_target = _targets(fixture)

    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="SYNTHETIC_BIG_LOTTO_REPLAY_GOLDEN_R1",
            dataset_version="1",
            targets=(short_target, long_target),
            strategy_ids=(BigLottoDeviation2BetAdapter.strategy_id,),
        )
    )

    short_snapshot, long_snapshot = result.snapshots
    assert short_snapshot.target_draw_number == short_target.draw_number
    assert short_snapshot.prediction_status == "INSUFFICIENT_HISTORY"
    assert short_snapshot.predicted_main_numbers is None
    assert long_snapshot.target_draw_number == long_target.draw_number
    assert long_snapshot.prediction_status == "OK"
    assert long_snapshot.predicted_main_numbers is not None
    assert len(long_snapshot.predicted_main_numbers) == 6


def test_social_and_zone_split_strategies_succeed_on_both_targets() -> None:
    fixture = _load_fixture()
    reader = _FixtureDrawHistoryReader(fixture)
    use_case = _use_case(reader)
    targets = _targets(fixture)

    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="SYNTHETIC_BIG_LOTTO_REPLAY_GOLDEN_R1",
            dataset_version="1",
            targets=targets,
            strategy_ids=(
                BigLottoSocialWisdomAntiPopularityAdapter.strategy_id,
                BigLottoZoneSplit3BetBet1Adapter.strategy_id,
            ),
        )
    )

    for snapshot in result.snapshots:
        assert snapshot.prediction_status == "OK"
        assert snapshot.predicted_main_numbers is not None


def test_no_future_leakage_history_count_matches_pre_target_row_count_exactly() -> None:
    fixture = _load_fixture()
    reader = _FixtureDrawHistoryReader(fixture)
    use_case = _use_case(reader)
    targets = _targets(fixture)

    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="SYNTHETIC_BIG_LOTTO_REPLAY_GOLDEN_R1",
            dataset_version="1",
            targets=targets,
            strategy_ids=(BigLottoZoneSplit3BetBet1Adapter.strategy_id,),
        )
    )
    expected_counts = {
        entry["draw_number"]: entry["pre_target_row_count"] for entry in fixture["targets"]
    }
    for snapshot in result.snapshots:
        assert snapshot.causal_history_count == expected_counts[snapshot.target_draw_number]


def test_history_is_built_once_per_target_across_all_three_strategies() -> None:
    fixture = _load_fixture()
    reader = _FixtureDrawHistoryReader(fixture)
    use_case = _use_case(reader)
    targets = _targets(fixture)

    use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="SYNTHETIC_BIG_LOTTO_REPLAY_GOLDEN_R1",
            dataset_version="1",
            targets=targets,
            strategy_ids=_STRATEGY_IDS,
        )
    )
    called_targets = [call[1] for call in reader.calls]
    assert called_targets == [target.draw_number for target in targets]


def test_golden_slice_artifact_round_trips_and_detects_tampering() -> None:
    fixture = _load_fixture()
    reader = _FixtureDrawHistoryReader(fixture)
    use_case = _use_case(reader)
    targets = _targets(fixture)

    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="SYNTHETIC_BIG_LOTTO_REPLAY_GOLDEN_R1",
            dataset_version="1",
            targets=targets,
            strategy_ids=_STRATEGY_IDS,
        )
    )
    artifact = build_replay_artifact(
        dataset_id="SYNTHETIC_BIG_LOTTO_REPLAY_GOLDEN_R1",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=_STRATEGY_IDS,
        targets=targets,
        snapshots=result.snapshots,
    )
    assert artifact.snapshot_count == 6

    first_bytes = serialize_replay_artifact(artifact)
    second_bytes = serialize_replay_artifact(artifact)
    assert first_bytes == second_bytes

    restored = deserialize_replay_artifact(first_bytes)
    assert restored == artifact

    tampered = first_bytes.replace(b'"dataset_version":"1"', b'"dataset_version":"2"')
    import pytest

    from lottolab.evidence.replay_artifact import ReplayArtifactTamperError

    with pytest.raises(ReplayArtifactTamperError):
        deserialize_replay_artifact(tampered)


def test_two_full_golden_slice_runs_produce_byte_identical_artifacts() -> None:
    fixture = _load_fixture()
    targets = _targets(fixture)

    def _run() -> bytes:
        reader = _FixtureDrawHistoryReader(fixture)
        use_case = _use_case(reader)
        result = use_case.execute(
            ReplayHistoricalPredictionsInput(
                lottery_type=LotteryType.BIG_LOTTO,
                dataset_id="SYNTHETIC_BIG_LOTTO_REPLAY_GOLDEN_R1",
                dataset_version="1",
                targets=targets,
                strategy_ids=_STRATEGY_IDS,
            )
        )
        artifact = build_replay_artifact(
            dataset_id="SYNTHETIC_BIG_LOTTO_REPLAY_GOLDEN_R1",
            dataset_version="1",
            lottery_type=LotteryType.BIG_LOTTO,
            strategy_ids=_STRATEGY_IDS,
            targets=targets,
            snapshots=result.snapshots,
        )
        return serialize_replay_artifact(artifact)

    assert _run() == _run()


def test_this_module_never_imports_sqlite_cli_or_network_modules() -> None:
    import ast

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {
        "sqlite3",
        "subprocess",
        "socket",
        "urllib",
        "urllib.request",
        "http.client",
        "httpx",
        "lottolab.infrastructure.persistence.draw_schema",
        "lottolab.infrastructure.persistence.replay_history_reader",
    }
    assert imported.isdisjoint(forbidden)
