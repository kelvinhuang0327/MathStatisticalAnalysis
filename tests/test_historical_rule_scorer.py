from __future__ import annotations

import hashlib
import importlib
import importlib.util
import sys
from collections.abc import MutableSequence
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar, cast

import pytest

TASK_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_SRC = TASK_ROOT / "src"


class _AdapterPackageModule(ModuleType):
    __path__: MutableSequence[str]


def _extend_candidate_package_paths() -> None:
    """Use candidate modules first and the host package only for unchanged deps."""
    package_roots: list[Path] = []
    for entry in sys.path:
        root = Path(entry).resolve() / "lottolab"
        if root.is_dir() and root != (CANDIDATE_SRC / "lottolab").resolve():
            package_roots.append(root)

    for package_name in (
        "lottolab",
        "lottolab.domain",
        "lottolab.application",
        "lottolab.application.use_cases",
        "lottolab.strategies",
    ):
        package = importlib.import_module(package_name)
        package_path = cast(list[str] | None, getattr(package, "__path__", None))
        if package_path is None:
            continue
        relative = package_name.split(".")[1:]
        for root in package_roots:
            dependency_path = root.joinpath(*relative)
            if dependency_path.is_dir() and str(dependency_path) not in package_path:
                package_path.append(str(dependency_path))


import lottolab as _LOTTOLAB_PACKAGE  # noqa: E402

_extend_candidate_package_paths()


def _load_candidate_module(module_name: str, relative_path: str) -> ModuleType:
    parent_name, separator, attribute = module_name.rpartition(".")
    if not separator:
        raise AssertionError(f"module has no package parent: {module_name}")
    parent = importlib.import_module(parent_name)
    source = CANDIDATE_SRC / relative_path
    spec = importlib.util.spec_from_file_location(module_name, source)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load candidate module: {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    setattr(parent, attribute, module)
    spec.loader.exec_module(module)
    return module


# The overlay exists only in this test harness. Product modules use normal package imports.
_ERA = _load_candidate_module("lottolab.domain.era_scorer", "lottolab/domain/era_scorer.py")
_PRIZE = _load_candidate_module(
    "lottolab.domain.prize_evaluation", "lottolab/domain/prize_evaluation.py"
)
_REPLAY = _load_candidate_module(
    "lottolab.domain.historical_replay", "lottolab/domain/historical_replay.py"
)

if not (CANDIDATE_SRC / "lottolab/strategies/adapters/biglotto_frontend_auto_optimize.py").exists():
    # The package's production __init__ eagerly imports every adapter. A
    # partial candidate view needs only the three direct adapter modules below.
    _adapter_package = _AdapterPackageModule("lottolab.strategies.adapters")
    _adapter_package.__path__ = [str(CANDIDATE_SRC / "lottolab/strategies/adapters")]
    _strategy_package = importlib.import_module("lottolab.strategies")
    for _root in cast(list[str], getattr(_strategy_package, "__path__", ())):
        _fallback = Path(_root) / "adapters"
        if _fallback.is_dir() and str(_fallback) not in _adapter_package.__path__:
            _adapter_package.__path__.append(str(_fallback))
    sys.modules["lottolab.strategies.adapters"] = _adapter_package

_ADAPTERS = _load_candidate_module(
    "lottolab.application.historical_replay_adapters",
    "lottolab/application/historical_replay_adapters.py",
)
_BACKFILL = _load_candidate_module(
    "lottolab.application.use_cases.replay_backfill",
    "lottolab/application/use_cases/replay_backfill.py",
)

from lottolab.domain.draws import LotteryType  # noqa: E402

WINNING = (1, 2, 3, 4, 5, 6)
SPECIAL = 7


def _strategy(native_ticket_count: int = 1) -> Any:
    return _REPLAY.ReplayStrategy(
        strategy_id="candidate-acceptance",
        strategy_name="candidate acceptance",
        strategy_version="v1",
        behavior=_REPLAY.ReplayBehavior.DETERMINISTIC,
        native_ticket_count=native_ticket_count,
        min_history=0,
    )


def _target(draw_id: str) -> Any:
    return _REPLAY.ReplayDraw(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=draw_id,
        draw_date=date(2014, 1, 1),
        main_numbers=WINNING,
        special_number=SPECIAL,
    )


def _adapter_score(draw_id: str, main_numbers: tuple[int, ...]) -> Any:
    adapter = _ADAPTERS._PrizeEvaluatingAdapter()
    return adapter.evaluate(
        _strategy(),
        _REPLAY.ReplayTicket(1, main_numbers),
        _target(draw_id),
    )


# These synthetic cases preserve the exact C57 H1/H2 six-key distinctions:
# H1 (BIG_LOTTO, research_biglotto__k30_histseed_638ed055b80ff5e5_0038, v1,
# k30-era-rule-20140926-v1-20261123-r1,
# 6489ca53daf2f1d8e8bbd809e2ee8a28430d7f4cf4a9c919147ea164cd863744, 103000024)
# records a current SEVENTH that is absent under historical Rule-O. H2
# (BIG_LOTTO, research_biglotto__prize_event_coverage_greedy_native_k7,
# prize-event-coverage-greedy-v1, 607bc2dc1c114483ceba2a6d0afb811e6a5570afdb2781b8c3712dfd85fe67e3,
# 2de539e79d8c5ff43bf887f8f5130016ef007c360936bc593196b75006195a7e, 114000087)
# is a historical GENERAL win. They are historical rule/event differences, not
# evidence of an original scorer implementation defect.
@pytest.mark.parametrize(
    ("draw_id", "main_numbers", "expected_tier", "expected_success"),
    [
        ("103000024", (1, 2, 7, 8, 9, 10), None, False),
        ("114000087", (1, 2, 3, 8, 9, 10), "GENERAL", True),
    ],
)
def test_c57_h1_h2_historical_rule_semantics(
    draw_id: str,
    main_numbers: tuple[int, ...],
    expected_tier: str | None,
    expected_success: bool,
) -> None:
    result = _adapter_score(draw_id, main_numbers)

    assert result.prize_tier == expected_tier
    assert result.is_winner is expected_success


@pytest.mark.parametrize(
    ("main_numbers", "old_tier", "new_tier"),
    [
        ((1, 2, 3, 4, 5, 6), "FIRST", "FIRST"),
        ((1, 2, 3, 4, 5, 7), "SECOND", "SECOND"),
        ((1, 2, 3, 4, 5, 8), "THIRD", "THIRD"),
        ((1, 2, 3, 4, 7, 8), "FOURTH", "FOURTH"),
        ((1, 2, 3, 4, 8, 9), "FIFTH", "FIFTH"),
        ((1, 2, 3, 7, 8, 9), "SIXTH", "SIXTH"),
        ((1, 2, 3, 8, 9, 10), "GENERAL", "GENERAL"),
        ((1, 2, 7, 8, 9, 10), None, "SEVENTH"),
        ((1, 2, 8, 9, 10, 11), None, None),
    ],
)
def test_actual_replay_adapter_selects_rule_by_target_and_preserves_tiers(
    main_numbers: tuple[int, ...], old_tier: str | None, new_tier: str | None
) -> None:
    old = _adapter_score("103000080", main_numbers)
    new = _adapter_score("103000081", main_numbers)

    assert old.prize_tier == old_tier
    assert new.prize_tier == new_tier
    assert old.is_winner is (old_tier is not None)
    assert new.is_winner is (new_tier is not None)
    assert old.historical_rule_id == _PRIZE.HISTORICAL_BIG_LOTTO_RULE_O_ID
    assert new.historical_rule_id == _PRIZE.HISTORICAL_BIG_LOTTO_CURRENT_RULE_ID
    assert old.scorer_version == new.scorer_version == _PRIZE.HISTORICAL_BIG_LOTTO_SCORER_VERSION


def test_missing_or_malformed_historical_target_fails_closed() -> None:
    common = {
        "lottery_type": LotteryType.BIG_LOTTO,
        "predicted_main_numbers": (1, 2, 7, 8, 9, 10),
        "predicted_special_number": None,
        "winning_main_numbers": WINNING,
        "winning_special_number": SPECIAL,
    }
    for target_draw_id in (None, "", "not-a-draw", "0", 0, -1, True):
        with pytest.raises(ValueError, match="target_draw_id"):
            _PRIZE.evaluate_historical_lottery_prize(
                target_draw_id=target_draw_id,
                **common,
            )


def test_current_only_entry_and_other_lotteries_keep_their_contracts() -> None:
    current_big_lotto = _PRIZE.evaluate_lottery_prize(
        lottery_type=LotteryType.BIG_LOTTO,
        predicted_main_numbers=(1, 2, 7, 8, 9, 10),
        predicted_special_number=None,
        winning_main_numbers=WINNING,
        winning_special_number=SPECIAL,
    )
    assert current_big_lotto.prize_tier == "SEVENTH"
    assert "historical_rule_id" not in current_big_lotto.canonical_dict()
    assert "scorer_version" not in current_big_lotto.canonical_dict()

    for lottery_type, main, special in (
        (LotteryType.POWER_LOTTO, (1, 2, 3, 4, 5, 6), 7),
        (LotteryType.DAILY_539, (1, 2, 3, 4, 5), None),
    ):
        current = _PRIZE.evaluate_lottery_prize(
            lottery_type=lottery_type,
            predicted_main_numbers=main,
            predicted_special_number=special,
            winning_main_numbers=main,
            winning_special_number=special,
        )
        historical = _PRIZE.evaluate_historical_lottery_prize(
            lottery_type=lottery_type,
            target_draw_id="103000080",
            predicted_main_numbers=main,
            predicted_special_number=special,
            winning_main_numbers=main,
            winning_special_number=special,
        )
        assert historical.canonical_dict() == current.canonical_dict()


def test_backfill_payload_keeps_legacy_shape_and_ticket_identity() -> None:
    ReplayBackfill = _BACKFILL.ReplayBackfill
    ReplayCellStatus = _REPLAY.ReplayCellStatus
    ReplayEvaluation = _REPLAY.ReplayEvaluation
    ReplayTargetRecord = _REPLAY.ReplayTargetRecord
    ReplayTicket = _REPLAY.ReplayTicket
    SourceStatus = _REPLAY.SourceHistoryProvenanceStatus

    backfill = object.__new__(ReplayBackfill)
    backfill.sources = {}
    backfill.lottery_type = LotteryType.BIG_LOTTO
    backfill.execution_version = "candidate-execution"
    backfill.dataset_identity = "candidate-dataset"
    backfill.source_history_provenance_status = SourceStatus.VERIFIED
    target = _target("103000080")
    ticket = ReplayTicket(1, (1, 2, 7, 8, 9, 10))
    strategy = _strategy()

    historical_evaluation = _adapter_score("103000080", ticket.main_numbers)
    historical_record = ReplayTargetRecord(
        target=target,
        strategy=strategy,
        status=ReplayCellStatus.COMPLETE,
        pre_eligible=True,
        causal_history=(),
        tickets=(ticket,),
        evaluations=(historical_evaluation,),
    )
    historical = ReplayBackfill._payload(backfill, historical_record, "cell-identity")
    hit = historical["hit_details"][0]
    assert hit["ticket_position"] == 1
    assert hit["historical_rule_id"] == _PRIZE.HISTORICAL_BIG_LOTTO_RULE_O_ID
    assert hit["scorer_version"] == _PRIZE.HISTORICAL_BIG_LOTTO_SCORER_VERSION
    assert historical["combination_success"] is False

    legacy_record = ReplayTargetRecord(
        target=target,
        strategy=strategy,
        status=ReplayCellStatus.COMPLETE,
        pre_eligible=True,
        causal_history=(),
        tickets=(ticket,),
        evaluations=(ReplayEvaluation(2, True, False, None),),
    )
    legacy = ReplayBackfill._payload(backfill, legacy_record, "legacy-cell-identity")
    legacy_hit = legacy["hit_details"][0]
    assert set(legacy_hit) == {
        "ticket_position",
        "zone1_hits",
        "zone2_hit",
        "is_winner",
        "prize_tier",
    }
    assert legacy["combination_success"] is False
    assert legacy["result_identity"] != historical["result_identity"]


class _PriorResultStore:
    def __init__(self, hit_details: Any) -> None:
        self.prepared = False
        self.previous_result: dict[str, Any] = {
            "execution_version": "candidate-execution",
            "dataset_identity": "",
            "strategy_fingerprint": None,
            "expected_native_ticket_count": 1,
            "hit_details": hit_details,
        }

    def lookup_complete_by_logical_keys(self, keys: Any) -> Any:
        return {keys[0]: (self.previous_result,)}

    def prepare(self, manifest: Any) -> None:
        self.prepared = True


class _CompatiblePriorResultStore(_PriorResultStore):
    def lookup_many_by_unique_keys(self, keys: Any) -> Any:
        return {keys[0]: self.previous_result}

    def save_many(self, run_id: str, payloads: Any) -> None:
        self.saved = tuple(payloads)

    def summary(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id}


@pytest.mark.parametrize(
    "hit_details",
    [
        None,
        [{"historical_rule_id": "wrong-rule", "scorer_version": "rule-o-era-scorer-v1"}],
        [
            {
                "historical_rule_id": "BIG_LOTTO_RULE_O_BEFORE_103000081",
                "scorer_version": "older-scorer",
            }
        ],
    ],
)
def test_incompatible_complete_result_is_rejected_before_prepare(hit_details: Any) -> None:
    ReplayBackfill = _BACKFILL.ReplayBackfill
    BackfillSelection = _BACKFILL.BackfillSelection
    adapter = _ADAPTERS._PrizeEvaluatingAdapter()
    adapter.lottery_type = LotteryType.BIG_LOTTO
    store = _PriorResultStore(hit_details)
    backfill = ReplayBackfill(
        adapter=adapter,
        strategies=(_strategy(),),
        draws=(_target("103000080"),),
        source_identity="candidate-source",
        store=store,
        execution_version="candidate-execution",
    )
    store.previous_result["dataset_identity"] = backfill.dataset_identity

    with pytest.raises(ValueError, match="historical scoring identity"):
        backfill.execute(BackfillSelection(all_draws=True))
    assert store.prepared is False


def test_complete_result_with_same_scorer_identity_is_reused() -> None:
    ReplayBackfill = _BACKFILL.ReplayBackfill
    BackfillSelection = _BACKFILL.BackfillSelection
    adapter = _ADAPTERS._PrizeEvaluatingAdapter()
    adapter.lottery_type = LotteryType.BIG_LOTTO
    hit_details = [
        {
            "historical_rule_id": _PRIZE.HISTORICAL_BIG_LOTTO_RULE_O_ID,
            "scorer_version": _PRIZE.HISTORICAL_BIG_LOTTO_SCORER_VERSION,
        }
    ]
    store = _CompatiblePriorResultStore(hit_details)
    backfill = ReplayBackfill(
        adapter=adapter,
        strategies=(_strategy(),),
        draws=(_target("103000080"),),
        source_identity="candidate-source",
        store=store,
        execution_version="candidate-execution",
    )
    store.previous_result.update(
        {
            "dataset_identity": backfill.dataset_identity,
            "strategy_fingerprint": backfill.strategies[0].fingerprint,
        }
    )

    summary = backfill.execute(BackfillSelection(all_draws=True))

    assert store.prepared is True
    assert summary["existing_skipped_count"] == 1
    assert summary["newly_calculated_count"] == 0


class _NativeReplayImplementation:
    strategy_id: ClassVar[str] = "native-binding-acceptance"
    strategy_version: ClassVar[str] = "native-v1"
    min_history: ClassVar[int] = 4
    native_ticket_count: ClassVar[int] = 7


def test_native_replay_binding_preserves_classvar_contract() -> None:
    implementation = _NativeReplayImplementation()

    binding = _ADAPTERS.binding_from_implementation(implementation)

    assert binding.implementation is implementation
    assert binding.strategy.strategy_id == implementation.strategy_id
    assert binding.strategy.strategy_version == implementation.strategy_version
    assert binding.strategy.min_history == implementation.min_history
    assert binding.strategy.native_ticket_count == implementation.native_ticket_count


def test_candidate_modules_are_the_imported_runtime_and_have_no_temp_path_literals() -> None:
    modules = (_ERA, _PRIZE, _REPLAY, _ADAPTERS, _BACKFILL)
    package_path = _module_path(_LOTTOLAB_PACKAGE)
    assert package_path.is_relative_to(CANDIDATE_SRC)
    for module in modules:
        module_path = _module_path(module)
        assert module_path.is_relative_to(CANDIDATE_SRC)
        source = module_path.read_text(encoding="utf-8")
        assert ".task-data" not in source
        assert "/Users/" not in source
        assert "runtime_adapter_loader" not in source


def _module_path(module: ModuleType) -> Path:
    module_path = module.__file__
    assert module_path is not None
    return Path(module_path)


def test_saved_rule_o_scorer_stays_within_big_lotto_contract() -> None:
    assert _ERA.BOUNDARY == 103000081
    assert _PRIZE.RULE_O_SCORER_SOURCE_SHA256 == (
        "b4fbd21457ad06f6d092fa88e6dd18c353cbbce74afdd6c6a6011b459e9acd64"
    )
    assert (
        hashlib.sha256(_module_path(_ERA).read_bytes()).hexdigest()
        == _PRIZE.RULE_O_SCORER_CANDIDATE_SHA256
    )
    score = _ERA.score_ticket("103000080", (1, 2, 7, 8, 9, 10), WINNING, SPECIAL)
    assert score["prize_tier"] is None
    assert score["is_winner"] is False
