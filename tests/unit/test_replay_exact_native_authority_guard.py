"""Deterministic tests for the frozen-authority / safe-resume guard on the
canonical exact-native replay path
(:func:`lottolab.application.use_cases.replay_exact_native_targets.replay_exact_native_target_range`).

Every scenario below monkeypatches ``source_freeze``/``catalog_freeze``/
``load_authoritative_draws``/``runtime_bindings`` at the module level, so no
test touches a real git worktree, the real production strategy catalog, or
any real draw-authority database -- only test-owned ``tmp_path`` runtime
roots, per this task's constraint. Bindings are constructed with
``binding_error`` pre-set so ``replay_cell`` always takes its cheapest,
fully-deterministic failure path without executing any adapter.

Every drift test (C-G) inline-asserts evidence- and authority-byte invariance
(the H and I acceptance items) rather than repeating that check in one more
consolidated test: each already captures pre-call bytes and re-checks them
after the raised ``ReplayAuthorityDriftError``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

import pytest

import lottolab.application.use_cases.replay_exact_native_targets as replay_module
from lottolab.application.use_cases.replay_exact_native_targets import (
    ExactNativeReplayRuntimeError,
    ReplayAuthorityDriftError,
    ReplayTargetRangeRequest,
    ReplayTargetRangeResult,
    replay_exact_native_target_range,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import Draw, RuntimeBinding
from lottolab.domain.strategies import LifecycleStatus, ResponseShape, StrategyDescriptor
from lottolab.evidence.exact_native_replay_manifest import (
    AUTHORITY_FILENAME,
    EVIDENCE_FILENAME,
    diff_replay_authority,
)

_SOURCE_A: dict[str, str] = {
    "branch": "main",
    "head": "a" * 40,
    "tree": "1" * 40,
    "status": "clean",
}
_SOURCE_B: dict[str, str] = {
    "branch": "main",
    "head": "b" * 40,
    "tree": "2" * 40,
    "status": "clean",
}


def _descriptor(strategy_id: str, **overrides: object) -> StrategyDescriptor:
    fields: dict[str, object] = {
        "strategy_id": strategy_id,
        "strategy_name": f"Test {strategy_id}",
        "version": "v1",
        "lottery_types": (LotteryType.BIG_LOTTO,),
        "lifecycle_status": LifecycleStatus.ONLINE,
        "executable": True,
        "adapter_path": "lottolab.strategies.adapters.base:PortfolioBetAdapter",
        "response_shape": ResponseShape.PORTFOLIO,
        "native_ticket_count": 5,
    }
    fields.update(overrides)
    return StrategyDescriptor(**fields)  # type: ignore[arg-type]


def _binding(strategy_id: str, **overrides: object) -> RuntimeBinding:
    return RuntimeBinding(
        descriptor=_descriptor(strategy_id, **overrides),
        implementation=None,
        adapter_class_name="StubAdapter",
        binding_error="STUB_BINDING_NOT_EXECUTED",
    )


def _draws(count: int) -> tuple[Draw, ...]:
    return tuple(
        Draw(
            draw_number=str(2000 + i),
            draw_date=date(2024, 1, 1) + timedelta(days=i),
            main_numbers=(1, 2, 3, 4, 5, 6),
            special_number=7,
        )
        for i in range(count)
    )


def _draw_authority(tag: str) -> dict[str, object]:
    return {
        "capability": "DRAW_DATA",
        "schema": "DRAW_DATA_V3",
        "verification": {"exists": True, "query_only": True, "readable": True},
        "sha256_before": f"sha_{tag}",
        "sha256_after": f"sha_{tag}",
        "draw_count": 6,
        "first_draw": {"draw_number": "2000", "draw_date": "2024-01-01"},
        "last_draw": {"draw_number": "2005", "draw_date": "2024-01-06"},
        "draw_payload_sha256": f"payload_sha_{tag}",
    }


def _window_sizes_for(order: tuple[str, ...]) -> dict[str, int | None]:
    return {name: (None if name == "FULL" else int(name.rsplit("_", 1)[1])) for name in order}


def _install_freezes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source: dict[str, str],
    bindings: tuple[RuntimeBinding, ...],
    draws: tuple[Draw, ...],
    draw_authority: dict[str, object],
) -> None:
    def fake_source_freeze(repo: Path) -> dict[str, str]:
        return dict(source)

    def fake_catalog_freeze(
        *, native_ticket_counts: Sequence[int]
    ) -> tuple[tuple[StrategyDescriptor, ...], dict[str, object]]:
        return (_descriptor("catalog-universe-stub"),), {"catalog_fingerprint": "stub"}

    def fake_load_authoritative_draws(
        draw_authority_db: Path,
    ) -> tuple[tuple[Draw, ...], dict[str, object]]:
        return draws, dict(draw_authority)

    def fake_runtime_bindings(
        descriptors: Sequence[StrategyDescriptor],
    ) -> tuple[RuntimeBinding, ...]:
        return bindings

    monkeypatch.setattr(replay_module, "source_freeze", fake_source_freeze)
    monkeypatch.setattr(replay_module, "catalog_freeze", fake_catalog_freeze)
    monkeypatch.setattr(replay_module, "load_authoritative_draws", fake_load_authoritative_draws)
    monkeypatch.setattr(replay_module, "runtime_bindings", fake_runtime_bindings)


def _run(
    monkeypatch: pytest.MonkeyPatch,
    output_path: Path,
    *,
    end_index: int = 2,
    source: dict[str, str] | None = None,
    bindings: tuple[RuntimeBinding, ...] | None = None,
    draws: tuple[Draw, ...] | None = None,
    draw_authority: dict[str, object] | None = None,
    native_ticket_counts: tuple[int, ...] | None = None,
    max_visible_draw: str | None = None,
    window_order: tuple[str, ...] | None = None,
) -> ReplayTargetRangeResult:
    resolved_window_order = window_order if window_order is not None else ("FULL",)
    _install_freezes(
        monkeypatch,
        source=source if source is not None else _SOURCE_A,
        bindings=bindings if bindings is not None else (_binding("s1"),),
        draws=draws if draws is not None else _draws(6),
        draw_authority=draw_authority if draw_authority is not None else _draw_authority("A"),
    )
    request = ReplayTargetRangeRequest(
        run_id="TEST_RUN",
        draw_authority_db=output_path.parent / "fake.db",
        repository_root=output_path.parent,
        output_path=output_path,
        start_index=0,
        end_index=end_index,
        native_ticket_counts=native_ticket_counts if native_ticket_counts is not None else (5,),
        max_visible_draw=max_visible_draw if max_visible_draw is not None else "2005",
        expected_main_numbers=None,
        expected_special_number=None,
        window_order=resolved_window_order,
        window_sizes=_window_sizes_for(resolved_window_order),
    )
    return replay_exact_native_target_range(request)


def _authority_path(output_path: Path) -> Path:
    return output_path.parent / AUTHORITY_FILENAME


# --- pure diff-function tests ------------------------------------------------


def test_diff_replay_authority_empty_when_identical() -> None:
    payload = {"a": 1, "b": {"c": [1, 2, 3]}}
    assert diff_replay_authority(payload, payload) == {}


def test_diff_replay_authority_reports_dotted_field_paths() -> None:
    frozen = {"a": 1, "b": {"c": [1, 2, 3]}}
    current = {"a": 2, "b": {"c": [1, 9, 3]}}
    diff = diff_replay_authority(frozen, current)
    assert diff["a"] == {"frozen": 1, "current": 2}
    assert diff["b.c[1]"] == {"frozen": 2, "current": 9}


# --- A: authority written before first target evidence ----------------------


def test_authority_written_before_first_target_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "root" / EVIDENCE_FILENAME
    observed: dict[str, bool] = {}
    real_write_json_file = replay_module.write_json_file

    def spy_write_json_file(path: Path, value: object) -> None:
        if path.name == AUTHORITY_FILENAME:
            observed["evidence_had_bytes_before_authority_write"] = (
                output_path.exists() and output_path.stat().st_size > 0
            )
        real_write_json_file(path, value)

    monkeypatch.setattr(replay_module, "write_json_file", spy_write_json_file)

    result = _run(monkeypatch, output_path, end_index=1)

    assert observed["evidence_had_bytes_before_authority_write"] is False
    assert _authority_path(output_path).is_file()
    assert output_path.is_file()
    assert result.actual_rows == 1
    frozen = json.loads(_authority_path(output_path).read_text(encoding="utf-8"))
    assert frozen["source"] == _SOURCE_A
    assert frozen["binding_identity"]["binding_count"] == 1


# --- B: exact authority resumes ----------------------------------------------


def test_exact_authority_resumes_and_reproduces_the_uninterrupted_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "root" / EVIDENCE_FILENAME
    first = _run(monkeypatch, output_path, end_index=3)
    assert first.actual_rows == 3
    full_evidence_bytes = output_path.read_bytes()
    authority_bytes_after_first = _authority_path(output_path).read_bytes()

    # Simulate a crash after exactly one target's worth of rows landed.
    first_line = full_evidence_bytes.decode("utf-8").splitlines()[0]
    output_path.write_text(first_line + "\n", encoding="utf-8")

    second = _run(monkeypatch, output_path, end_index=3)

    assert second.actual_rows == 3
    assert output_path.read_bytes() == full_evidence_bytes
    assert _authority_path(output_path).read_bytes() == authority_bytes_after_first


# --- C: binding-count drift fails before mutation ----------------------------


def test_binding_count_drift_fails_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "root" / EVIDENCE_FILENAME
    _run(monkeypatch, output_path)
    pre_evidence = output_path.read_bytes()
    pre_authority = _authority_path(output_path).read_bytes()

    with pytest.raises(ReplayAuthorityDriftError) as excinfo:
        _run(monkeypatch, output_path, bindings=(_binding("s1"), _binding("s2")))

    assert "binding_identity.binding_count" in excinfo.value.differences
    assert output_path.read_bytes() == pre_evidence
    assert _authority_path(output_path).read_bytes() == pre_authority


# --- D: same-count binding swap fails before mutation ------------------------


def test_same_count_binding_swap_fails_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "root" / EVIDENCE_FILENAME
    _run(monkeypatch, output_path)
    pre_evidence = output_path.read_bytes()
    pre_authority = _authority_path(output_path).read_bytes()

    with pytest.raises(ReplayAuthorityDriftError) as excinfo:
        _run(monkeypatch, output_path, bindings=(_binding("s2"),))

    differences = excinfo.value.differences
    assert len(differences) > 0
    assert all(
        path.startswith("binding_identity.ordered_binding_identities[0]") for path in differences
    )
    assert "binding_identity.binding_count" not in differences
    assert output_path.read_bytes() == pre_evidence
    assert _authority_path(output_path).read_bytes() == pre_authority


# --- E: source HEAD/tree drift fails -----------------------------------------


def test_source_head_and_tree_drift_fails_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "root" / EVIDENCE_FILENAME
    _run(monkeypatch, output_path)
    pre_evidence = output_path.read_bytes()
    pre_authority = _authority_path(output_path).read_bytes()

    with pytest.raises(ReplayAuthorityDriftError) as excinfo:
        _run(monkeypatch, output_path, source=_SOURCE_B)

    differences = excinfo.value.differences
    assert differences["source.head"] == {"frozen": _SOURCE_A["head"], "current": _SOURCE_B["head"]}
    assert differences["source.tree"] == {"frozen": _SOURCE_A["tree"], "current": _SOURCE_B["tree"]}
    assert output_path.read_bytes() == pre_evidence
    assert _authority_path(output_path).read_bytes() == pre_authority


# --- F: draw-authority content drift fails -----------------------------------


def test_draw_authority_content_drift_fails_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "root" / EVIDENCE_FILENAME
    _run(monkeypatch, output_path)
    pre_evidence = output_path.read_bytes()
    pre_authority = _authority_path(output_path).read_bytes()

    with pytest.raises(ReplayAuthorityDriftError) as excinfo:
        _run(monkeypatch, output_path, draw_authority=_draw_authority("B"))

    differences = excinfo.value.differences
    assert any(path.startswith("draw_authority_identity.") for path in differences)
    assert output_path.read_bytes() == pre_evidence
    assert _authority_path(output_path).read_bytes() == pre_authority


# --- G: cutoff/window/config drift fails -------------------------------------


def test_native_ticket_count_budget_drift_fails_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "root" / EVIDENCE_FILENAME
    _run(monkeypatch, output_path)
    pre_evidence = output_path.read_bytes()
    pre_authority = _authority_path(output_path).read_bytes()

    with pytest.raises(ReplayAuthorityDriftError) as excinfo:
        _run(monkeypatch, output_path, native_ticket_counts=(10,))

    differences = excinfo.value.differences
    assert differences["run_config.native_ticket_counts[0]"] == {"frozen": 5, "current": 10}
    assert output_path.read_bytes() == pre_evidence
    assert _authority_path(output_path).read_bytes() == pre_authority


def test_window_config_drift_fails_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "root" / EVIDENCE_FILENAME
    _run(monkeypatch, output_path)
    pre_evidence = output_path.read_bytes()
    pre_authority = _authority_path(output_path).read_bytes()

    with pytest.raises(ReplayAuthorityDriftError) as excinfo:
        _run(monkeypatch, output_path, window_order=("FULL", "RECENT_2"))

    differences = excinfo.value.differences
    assert any(path.startswith("run_config.window") for path in differences)
    assert output_path.read_bytes() == pre_evidence
    assert _authority_path(output_path).read_bytes() == pre_authority


def test_cutoff_drift_fails_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "root" / EVIDENCE_FILENAME
    _run(monkeypatch, output_path)
    pre_evidence = output_path.read_bytes()
    pre_authority = _authority_path(output_path).read_bytes()

    with pytest.raises(ReplayAuthorityDriftError) as excinfo:
        _run(monkeypatch, output_path, max_visible_draw="2004")

    differences = excinfo.value.differences
    assert differences["run_config.max_visible_draw"] == {"frozen": "2005", "current": "2004"}
    assert output_path.read_bytes() == pre_evidence
    assert _authority_path(output_path).read_bytes() == pre_authority


# --- J: progress is calculated only after authority match --------------------


def test_progress_is_calculated_only_after_authority_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If progress were derived before the authority compare, the unparseable
    existing line below would raise ``json.JSONDecodeError`` instead of the
    clean drift error -- this falsifies premature progress derivation."""

    output_path = tmp_path / "root" / EVIDENCE_FILENAME
    _run(monkeypatch, output_path)
    corrupt_bytes = b"{not valid json\n"
    output_path.write_bytes(corrupt_bytes)

    with pytest.raises(ReplayAuthorityDriftError):
        _run(monkeypatch, output_path, source=_SOURCE_B)

    assert output_path.read_bytes() == corrupt_bytes


# --- defensive: fails closed when evidence exists with no authority ---------


def test_missing_authority_artifact_with_existing_evidence_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "root" / EVIDENCE_FILENAME
    _run(monkeypatch, output_path)
    _authority_path(output_path).unlink()
    pre_evidence = output_path.read_bytes()

    with pytest.raises(ExactNativeReplayRuntimeError, match="REPLAY_AUTHORITY_MISSING"):
        _run(monkeypatch, output_path)

    assert output_path.read_bytes() == pre_evidence
    assert not _authority_path(output_path).exists()
