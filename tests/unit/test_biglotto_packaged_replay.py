"""Compare every emitted position and closure with digests derived from the original artifacts."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lottolab.application.biglotto_packaged_replay import packaged_panel, packaged_replay_sources
from lottolab.domain.biglotto_full_strategy_catalog import load_full_strategy_catalog
from lottolab.domain.draws import LotteryType
from lottolab.interfaces.cli.main import app

_GOLDEN = Path(__file__).parents[1] / "fixtures/replay/biglotto_packaged_replay_digests.json"
_RECIPE_HOLDS = {
    "tools/historical_audit_rigorous.py": 1901,
    "tools/predict_consensus_ensemble.py": 2051,
    "tools/predict_evolutionary_gum.py": 1951,
}


def test_all_versions_preserve_ordered_frozen_results_and_guard_recipe_availability() -> None:
    panel = packaged_panel()
    registry = packaged_replay_sources()
    goldens = json.loads(_GOLDEN.read_bytes())
    catalog = load_full_strategy_catalog()
    assert len(panel) == 2149
    assert len(registry) == 55
    assert {sid for sid, _ in registry} == set(goldens)
    assert len({s.wave for s in registry.values()}) == 20
    assert all(
        (r.strategy_id, r.strategy_version) not in registry
        for r in catalog.records
        if r.duplicate_alias_target is not None
    )
    total: Counter[str] = Counter()
    for (sid, version), source in registry.items():
        assert (sid, version) == (source.record.strategy_id, source.record.strategy_version)
        digest = sha256()
        held = 0
        for i, target in enumerate(panel):
            prefix = panel[:i]
            usable = source.replay_target(prefix, target)
            if source.record.source_path in _RECIPE_HOLDS:
                frozen = source.inspect_target(prefix, target)
                if frozen.status == "OK" and int(target.draw_number) < 115000026:
                    assert usable.status == "BLOCKED_SOURCE_AVAILABILITY"
                    assert usable.reason and "UNVERIFIED_RECIPE" in usable.reason
                    assert usable.tickets == ()
                    held += 1
                else:
                    assert usable == frozen
            else:
                frozen = usable
            assert all(t.ticket_position == k for k, t in enumerate(frozen.tickets, 1))
            assert bool(frozen.tickets) == (frozen.status == "OK")
            total[frozen.status] += 1
            total["positions"] += len(frozen.tickets)
            row = [
                target.draw_number,
                frozen.status,
                frozen.reason,
                [t.main_numbers for t in frozen.tickets],
            ]
            digest.update(json.dumps(row, separators=(",", ":")).encode() + b"\n")
        assert held == _RECIPE_HOLDS.get(source.record.source_path, 0)
        assert digest.hexdigest() == goldens[sid], sid
    assert total == {
        "OK": 82934,
        "CLOSED_INSUFFICIENT_HISTORY": 21144,
        "CLOSED_REJECTED": 14103,
        "CLOSED_EXECUTION_ERROR": 14,
        "positions": 915707,
    }


def test_closed_and_open_targets_require_full_prefix_but_ignore_target_outcome() -> None:
    panel = packaged_panel()
    for source in packaged_replay_sources().values():
        for i in (1, len(panel) - 1):
            target = panel[i]
            prefix = panel[:i]
            assert source.inspect_target(
                prefix, replace(target, main_numbers=(0,), special_number=None)
            ) == source.inspect_target(prefix, target)
            for altered in (
                replace(prefix[0], special_number=0),
                replace(prefix[0], main_numbers=prefix[0].main_numbers[::-1]),
                replace(prefix[0], draw_number="0"),
                replace(prefix[0], draw_date=prefix[0].draw_date + timedelta(days=1)),
                replace(prefix[0], lottery_type=LotteryType.POWER_LOTTO),
            ):
                with pytest.raises(ValueError, match="strict prefix"):
                    source.replay_target((altered, *prefix[1:]), target)
            with pytest.raises(ValueError, match="wrong length"):
                source.replay_target((*prefix, target), target)
        with pytest.raises(ValueError, match="outside the frozen panel"):
            source.replay_target(panel, replace(panel[-1], draw_number="115000074"))
        with pytest.raises(ValueError, match="outside the frozen panel"):
            source.replay_target((), replace(panel[0], draw_date=panel[1].draw_date))


def test_operator_selects_exact_version_and_reports_original_closure() -> None:
    source = next(s for s in packaged_replay_sources().values() if s.wave == 57)
    args = [
        "historical-replay-biglotto",
        "--strategy-id",
        source.record.strategy_id,
        "--strategy-version",
        source.record.strategy_version,
        "--cutoff-draw-number",
        "96000002",
    ]
    runner = CliRunner()
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["status_counts"] == {"OK": 1, "CLOSED_INSUFFICIENT_HISTORY": 1}
    assert summary["native_ticket_positions"] == 1
    assert summary["donor_blob"] == source.record.source_blob_id
    result = runner.invoke(app, [*args, "--output-mode", "RECORDS_JSONL"])
    assert result.exit_code == 0
    closed, emitted = [json.loads(line) for line in result.stdout.splitlines()]
    assert closed["reason"] == "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF" and closed["tickets"] == []
    assert emitted["tickets"][0]["ticket_position"] == 1
    args[4] = "unknown"
    result = runner.invoke(app, args)
    assert result.exit_code == 1 and "unknown packaged" in result.stderr
