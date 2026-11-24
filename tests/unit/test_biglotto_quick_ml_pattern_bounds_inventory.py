"""Registration and source-identity checks for the Quick ML bounds candidate."""

# pyright: reportPrivateUsage=false

import hashlib
import inspect
from pathlib import Path
from typing import Any, cast

from lottolab.application.native_replay_inventory import native_strategy_inventory
from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.application.use_cases.replay_backfill import identity
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_quick_ml_pattern_bounds import (
    BigLottoQuickMlPatternBoundsAdapter,
)
from lottolab.strategies.adapters.biglotto_quickml_corrected_successor import (
    BigLottoQuickMlCorrectedSuccessorAdapter,
)
from lottolab.strategies.adapters.biglotto_wave12 import _quick_ml_hybrid

SID = "research_biglotto__quick_ml_pattern_bounds_v1"


def source_hash(obj: object) -> str:
    source = inspect.getsourcefile(cast(Any, obj))
    assert source is not None
    return hashlib.sha256(Path(source).read_bytes()).hexdigest()


def test_candidate_is_pinned_to_actual_sources_and_registered_once() -> None:
    bindings, accounts = native_strategy_inventory(LotteryType.BIG_LOTTO)
    matches = [binding for binding in bindings if binding.strategy.strategy_id == SID]
    assert len(matches) == 1
    strategy = matches[0].strategy
    assert (strategy.strategy_version, strategy.native_ticket_count, strategy.min_history) == (
        "v0.1-research",
        2,
        1,
    )
    assert strategy.fingerprint == identity(
        {
            "candidate_adapter_sha256": hashlib.sha256(
                Path(inspect.getsourcefile(BigLottoQuickMlPatternBoundsAdapter) or "")
                .read_bytes()
                .replace(b"  # noqa: RUF001", b"")
            ).hexdigest(),
            "successor_sha256": source_hash(BigLottoQuickMlCorrectedSuccessorAdapter),
            "wave12_sha256": source_hash(_quick_ml_hybrid),
        }
    )
    assert accounts[SID]["status"] == "EXECUTABLE"
    rows = [item for item in load_replay_strategy_inventory().items if item.strategy_id == SID]
    assert len(rows) == 1
    assert rows[0].execution_capability.value == "EXECUTABLE"
    assert rows[0].backfill_native_binding is True


def test_candidate_and_corrected_successor_keep_same_native_semantics() -> None:
    rows = tuple(
        CausalDrawRow(
            draw=str(90000000 + index),
            date=f"2020-{index % 12 + 1:02}-{index % 28 + 1:02}",
            numbers=tuple(sorted((index + step * 8) % 49 + 1 for step in range(6))),
        )
        for index in range(10)
    )
    candidate = BigLottoQuickMlPatternBoundsAdapter()
    successor = BigLottoQuickMlCorrectedSuccessorAdapter()
    for length in (1, 2, 3, 4, 5, 6, 7, 8, 10):
        assert candidate.get_bets(rows[:length], LotteryType.BIG_LOTTO) == successor.get_bets(
            rows[:length], LotteryType.BIG_LOTTO
        )
