"""Focused contract tests for the frozen R1 winner/default confirmation comparison."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.application.legacy_source_grid_native_portfolios_wave46 import (
    SUM_CONSTRAINT_METHOD_ID,
)
from lottolab.evidence import canonical_json
from lottolab.infrastructure.replay_backed_batch_import import (
    PinnedBigLottoDraw,
    PinnedBigLottoHistory,
)
from lottolab.research import native_study_campaign_confirmation_baseline_headtohead_r2 as r2
from lottolab.research.base_method_evaluation import (
    LotteryMatchContract,
    MethodDrawObservation,
    MethodEvaluationRecord,
    MethodIdentity,
)
from lottolab.research.base_method_evaluation import (
    evaluate_method as canonical_evaluate_method,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
R1_RESULT = (
    REPOSITORY_ROOT
    / "docs/research/matrix-native-results/native-study-first-strategy-campaign-r1-result.json"
)
R2_RESULT = (
    REPOSITORY_ROOT / "docs/research/matrix-native-results/"
    "native-study-campaign-confirmation-baseline-headtohead-r2-result.json"
)
R2_HASH = (
    REPOSITORY_ROOT / "docs/research/matrix-native-results/"
    "native-study-campaign-confirmation-baseline-headtohead-r2-hash.json"
)
R1_DATABASE_SHA256 = "e8a56e9f4979d3fbe91951be1f9d1ae4820ea1dcd92be47ef61cacd296c4b439"
R1_DATASET_CONTENT_SHA256 = "707f6a1f42321f0d9dc9d8139b91c0e748779ddc1b3e466b915c9a68dc458c04"
R1_FIRST_CONFIRMATION_SHA256 = "d5e4c0b616aa6840648aca9baf258806032df81b2f8203f605c14e5da1ba85cf"
R1_LAST_CONFIRMATION_SHA256 = "04bb9a2b5207b82c3e4a12103a4ae671d23403e3024e2c8be33b657111efc2d2"

type Ticket = tuple[int, int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class _FakeLedger:
    target_index_by_number: Mapping[str, int]
    context_sha256: tuple[str, ...]
    tickets_by_method: Mapping[
        str,
        tuple[tuple[Ticket, ...] | None, ...],
    ]


def _draw(draw_number: str, draw_date: date) -> PinnedBigLottoDraw:
    return PinnedBigLottoDraw(
        draw_number=draw_number,
        draw_date=draw_date,
        numbers=(1, 2, 3, 4, 5, 6),
        special=7,
    )


def _fake_history() -> tuple[PinnedBigLottoHistory, tuple[PinnedBigLottoDraw, ...]]:
    prefix_start = date(2010, 1, 1)
    prefix = tuple(
        _draw(str(100_000_000 + index), prefix_start + timedelta(days=index))
        for index in range(1_845)
    )
    confirmation_start = date(2024, 1, 19)
    confirmation = tuple(
        _draw(
            ("115000069" if index == 299 else str(113_000_006 + index)),
            (date(2026, 7, 10) if index == 299 else confirmation_start + timedelta(days=index * 3)),
        )
        for index in range(300)
    )
    history = PinnedBigLottoHistory(
        draws=prefix + confirmation,
        database_sha256_before=R1_DATABASE_SHA256,
        database_sha256_after=R1_DATABASE_SHA256,
        replay_truth_supplemented_draw_count=21,
    )
    return history, confirmation


def _fake_ledger(
    confirmation: tuple[PinnedBigLottoDraw, ...],
) -> _FakeLedger:
    filler: Ticket = (11, 12, 13, 14, 15, 16)
    three_hits: Ticket = (1, 2, 3, 7, 8, 9)
    two_hits: Ticket = (1, 2, 7, 8, 9, 10)
    zero_hits: Ticket = (21, 22, 23, 24, 25, 26)
    portfolio = (filler,) * 21 + (three_hits, two_hits, zero_hits)
    portfolios: tuple[tuple[Ticket, ...] | None, ...] = tuple(
        portfolio for _draw_item in confirmation
    )
    return _FakeLedger(
        target_index_by_number={draw.draw_number: index for index, draw in enumerate(confirmation)},
        context_sha256=tuple("synthetic-context" for _draw_item in confirmation),
        tickets_by_method={SUM_CONSTRAINT_METHOD_ID: portfolios},
    )


def _synthetic_draw_sha256(draw: PinnedBigLottoDraw) -> str:
    if draw.draw_number == "113000006":
        return R1_FIRST_CONFIRMATION_SHA256
    if draw.draw_number == "115000069":
        return R1_LAST_CONFIRMATION_SHA256
    identity = f"{draw.draw_number}|{draw.draw_date.isoformat()}".encode()
    return hashlib.sha256(identity).hexdigest()


def _synthetic_dataset_sha256(_history: PinnedBigLottoHistory) -> str:
    return R1_DATASET_CONTENT_SHA256


def _synthetic_context_sha256(_draws: tuple[PinnedBigLottoDraw, ...]) -> str:
    return "synthetic-context"


def test_r1_result_is_the_exact_task_sealed_authority() -> None:
    assert R1_RESULT.is_file()
    assert hashlib.sha256(R1_RESULT.read_bytes()).hexdigest() == r2.R1_EXPECTED_RESULT_SHA256


def test_wrong_r1_sha_fails_before_database_load_or_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    altered = tmp_path / R1_RESULT.name
    altered.write_bytes(R1_RESULT.read_bytes() + b"\n")
    database_loads: list[Path] = []

    def forbidden_database_load(
        *,
        database: Path,
        expected_database_sha256: str,
        require_replay_authority: bool = True,
    ) -> PinnedBigLottoHistory:
        del expected_database_sha256, require_replay_authority
        database_loads.append(database)
        raise AssertionError("database must not be read after an R1 SHA mismatch")

    monkeypatch.setattr(r2, "load_pinned_biglotto_history", forbidden_database_load)

    with pytest.raises(r2.BaselineHeadToHeadR2Error, match="R1 result SHA-256 mismatch"):
        r2.run_native_study_campaign_confirmation_baseline_headtohead_r2(
            r1_result=altered,
            archive_database=tmp_path / "must-not-be-read.db",
        )

    assert database_loads == []


def test_default_is_evaluated_once_on_the_reconstructed_r1_confirmation_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history, confirmation = _fake_history()
    ledger = _fake_ledger(confirmation)
    evaluation_method_ids: list[str] = []

    def load_history(
        *,
        database: Path,
        expected_database_sha256: str,
        require_replay_authority: bool = True,
    ) -> PinnedBigLottoHistory:
        assert database == tmp_path / "sealed-archive.db"
        assert expected_database_sha256 == R1_DATABASE_SHA256
        assert require_replay_authority is True
        return history

    def load_ledger() -> _FakeLedger:
        return ledger

    def recording_evaluate(
        contract: LotteryMatchContract,
        identity: MethodIdentity,
        observations: tuple[MethodDrawObservation, ...],
    ) -> MethodEvaluationRecord:
        evaluation_method_ids.append(identity.method_id)
        assert tuple(item.draw_id for item in observations) == tuple(
            draw.draw_number for draw in confirmation
        )
        return canonical_evaluate_method(contract, identity, observations)

    monkeypatch.setattr(r2, "load_pinned_biglotto_history", load_history)
    monkeypatch.setattr(
        r2,
        "load_legacy_source_grid_native_wave46_ledger_for_verification",
        load_ledger,
    )
    monkeypatch.setattr(r2, "_dataset_content_sha256", _synthetic_dataset_sha256)
    monkeypatch.setattr(r2, "_draw_sha256", _synthetic_draw_sha256)
    monkeypatch.setattr(r2, "_context_sha256", _synthetic_context_sha256)
    monkeypatch.setattr(r2, "evaluate_method", recording_evaluate)

    execution = r2.run_native_study_campaign_confirmation_baseline_headtohead_r2(
        r1_result=R1_RESULT,
        archive_database=tmp_path / "sealed-archive.db",
    )

    assert evaluation_method_ids == [r2.DEFAULT_CANDIDATE_ID]
    assert execution.winner_evaluation_count == 0
    assert execution.default_evaluation_count == 1
    assert execution.winner_confirmation_values == (Fraction(29, 14_700), Fraction(19, 300))
    assert execution.default_confirmation_values == (Fraction(137, 147), Fraction(1))
    assert execution.head_to_head_deltas == (Fraction(-4_557, 4_900), Fraction(-281, 300))
    assert execution.point_estimate_classification == "DEFAULT_BETTER"

    document = execution.result_document
    winner = cast(dict[str, object], document["winner_confirmation_result"])
    assert winner["objective_values"] == [
        {"denominator": 14_700, "numerator": 29},
        {"denominator": 300, "numerator": 19},
    ]
    assert winner["source"] == "SEALED_R1_ARTIFACT_REUSED"

    partition = cast(dict[str, object], document["confirmation_partition"])
    assert partition["confirmation_count"] == 300
    assert partition["identical_confirmation_ids"] == "PASS"
    assert (
        partition["winner_confirmation_identity_sha256"]
        == partition["default_confirmation_identity_sha256"]
        == partition["identity_sha256"]
    )
    identities = cast(list[dict[str, object]], partition["observation_identities"])
    assert tuple(item["draw_id"] for item in identities) == tuple(
        draw.draw_number for draw in confirmation
    )

    paired = cast(dict[str, object], document["paired_evidence"])
    significance = cast(dict[str, object], document["significance_result"])
    assert paired["status"] == "NOT_APPLICABLE"
    assert significance["status"] == "NOT_APPLICABLE"
    assert document["promotion_decision"] == "NOT_AUTHORIZED"
    assert execution.canonical_result_bytes() == execution.canonical_result_bytes()
    assert (
        execution.canonical_result_sha256()
        == hashlib.sha256(execution.canonical_result_bytes()).hexdigest()
    )


def test_sealed_r2_artifact_preserves_exact_results_and_control_counts() -> None:
    result_bytes = R2_RESULT.read_bytes()
    document = cast(dict[str, object], canonical_json.loads_canonical(result_bytes))
    hash_document = cast(
        dict[str, object],
        canonical_json.loads_canonical(R2_HASH.read_bytes()),
    )

    assert result_bytes == canonical_json.canonical_bytes(document)
    assert hashlib.sha256(result_bytes).hexdigest() == hash_document["canonical_result_sha256"]
    assert hash_document["deterministic_serialization"] == ("PASS_IDENTICAL_BYTES_AND_HASHES")
    assert hash_document["winner_evaluation_count"] == 0
    assert hash_document["default_evaluation_count"] == 1

    winner = cast(dict[str, object], document["winner_confirmation_result"])
    default = cast(dict[str, object], document["default_confirmation_result"])
    head_to_head = cast(dict[str, object], document["head_to_head"])
    partition = cast(dict[str, object], document["confirmation_partition"])
    assert winner["objective_values"] == [
        {"denominator": 14_700, "numerator": 29},
        {"denominator": 300, "numerator": 19},
    ]
    assert default["objective_values"] == [
        {"denominator": 11_025, "numerator": -211},
        {"denominator": 25, "numerator": 2},
    ]
    assert head_to_head["avg_match_head_to_head_delta"] == {
        "denominator": 900,
        "numerator": 19,
    }
    assert head_to_head["m3_plus_head_to_head_delta"] == {
        "denominator": 60,
        "numerator": -1,
    }
    assert head_to_head["point_estimate_classification"] == "WINNER_BETTER"
    assert partition["confirmation_count"] == 300
    assert partition["identical_confirmation_ids"] == "PASS"
    assert (
        partition["winner_confirmation_identity_sha256"]
        == partition["default_confirmation_identity_sha256"]
        == partition["identity_sha256"]
    )
    assert cast(dict[str, object], document["paired_evidence"])["status"] == ("NOT_APPLICABLE")
    assert cast(dict[str, object], document["significance_result"])["status"] == ("NOT_APPLICABLE")
    assert document["promotion_decision"] == "NOT_AUTHORIZED"
