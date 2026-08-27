"""Fail-closed boundary coverage for the V1C canonical evaluation runner.

Everything here is decided before any replay runs, so these tests need no
database at all: they pin the guards that stop a malformed or out-of-scope
request from ever reaching the replay stack, plus the window-order constants
the runner re-asserts against the evaluator's own ``WINDOW_SIZES``.

The full vertical -- real replay, real evaluator, real materializer, real
validator, and parity with hand composition -- lives in
tests/integration/test_canonical_evaluation_evidence_runner.py, where a
task-owned SQLite database makes those assertions honest.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.strategies import (
    LifecycleStatus,
    ResponseShape,
    StrategyDescriptor,
)
from lottolab.evidence import canonical_json
from lottolab.evidence.method_evaluation_materialization import EvidenceProducerIdentity
from lottolab.evidence.models import (
    DatasetSnapshot,
    DrawEntry,
    EvidenceStatus,
    RuleParameters,
)
from lottolab.infrastructure.persistence.draw_schema import LocalDataPaths
from lottolab.research.base_method_evaluation import WINDOW_SIZES, ReplayStatus, WindowKind
from lottolab.research.canonical_evaluation_evidence_runner import (
    EXPECTED_ARTIFACT_COUNT,
    EXPECTED_WINDOW_ORDER,
    RUNNER_LOTTERY_TYPE,
    RUNNER_MATCH_CONTRACT,
    CanonicalEvaluationEvidenceRunnerError,
    CanonicalEvaluationRequest,
    resolve_single_ticket_descriptor,
    run_canonical_evaluation_evidence,
)
from lottolab.strategies.catalog import StrategyCatalog, production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "replay" / "synthetic_biglotto_causal_history.json"
)

_DATASET_ID = "SYNTHETIC_BIG_LOTTO_CANONICAL_EVALUATION_V1C_UNIT"
_DATASET_VERSION = "1"
_STRATEGY_ID = "biglotto_social_wisdom_anti_popularity"
_METHOD_FAMILY = "SYNTHETIC_CANONICAL_EVALUATION_V1C"
_TARGET_DRAW_NUMBERS = tuple(str(1000100 + offset) for offset in range(10))


def _fixture_rows() -> list[dict[str, Any]]:
    fixture: dict[str, Any] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return cast("list[dict[str, Any]]", fixture["history_rows"])


def _rule_binding_payload() -> dict[str, Any]:
    contract = BIG_LOTTO_RULE_CONTRACT
    payload: dict[str, Any] = {
        "main_number_count": contract.main_number_count,
        "main_number_min": contract.main_number_min,
        "main_number_max": contract.main_number_max,
        "main_numbers_unique": contract.main_numbers_unique,
        "special_number_count": contract.special_number_count,
        "special_number_min": contract.special_number_min,
        "special_number_max": contract.special_number_max,
        "special_numbers_unique": contract.special_numbers_unique,
        "main_special_overlap_allowed": contract.main_special_overlap_allowed,
        "rule_contract_version": contract.contract_version,
    }
    payload["rule_parameters_sha256"] = canonical_json.self_key_removed_sha256(
        RuleParameters.model_validate(
            {**payload, "rule_parameters_sha256": "0" * 64}
        ).model_dump(mode="json", exclude_none=True),
        "rule_parameters_sha256",
    )
    return payload


def _dataset_snapshot(
    *,
    lottery_type: LotteryType = LotteryType.BIG_LOTTO,
    draws: tuple[DrawEntry, ...] | None = None,
) -> DatasetSnapshot:
    resolved_draws = (
        tuple(
            DrawEntry(
                draw_id=row["draw_number"],
                draw_sequence=index,
                draw_date=date.fromisoformat(row["draw_date"]),
                main_numbers=tuple(row["main_numbers"]),
                special_numbers=(row["special_number"],),
            )
            for index, row in enumerate(_fixture_rows())
        )
        if draws is None
        else draws
    )
    payload: dict[str, Any] = {
        "schema_id": "lottolab.evidence.dataset_snapshot",
        "schema_version": "1.0.0",
        "dataset_id": _DATASET_ID,
        "dataset_version": _DATASET_VERSION,
        "lottery_type": lottery_type.value,
        "rule_binding": _rule_binding_payload(),
        "source_provenance": {
            "kind": "SYNTHETIC",
            "declared_description": "committed synthetic BIG_LOTTO causal-history fixture",
        },
        "draws": [draw.model_dump(mode="json", exclude_none=True) for draw in resolved_draws],
    }
    payload["dataset_sha256"] = canonical_json.sha256_hex(canonical_json.canonical_bytes(payload))
    return DatasetSnapshot.model_validate(payload)


def _producer() -> EvidenceProducerIdentity:
    definition = REPO_ROOT / "contracts/evidence/metric_definitions/avg_match.json"
    return EvidenceProducerIdentity(
        artifact_id_prefix="SYNTHETIC_V1C_UNIT",
        evidence_status=EvidenceStatus.SYNTHETIC_TEST_ONLY,
        produced_at=datetime(2026, 8, 27, tzinfo=UTC),
        producer_name="lottolab-canonical-evaluation-evidence-runner",
        method_source_git_oid="c" * 40,
        feature_version="v1",
        feature_definition_path="contracts/evidence/metric_definitions/avg_match.json",
        feature_definition_sha256=canonical_json.sha256_hex(definition.read_bytes()),
    )


def _existing_database(tmp_path: Path) -> LocalDataPaths:
    """A path whose database file exists, so the file guard is not what fires."""

    directory = tmp_path / "v1c-unit"
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "lottolab.db"
    database.touch()
    return LocalDataPaths(data_directory=directory, database=database)


def _request(tmp_path: Path, **overrides: Any) -> CanonicalEvaluationRequest:
    fields: dict[str, Any] = {
        "database_paths": _existing_database(tmp_path),
        "dataset": _dataset_snapshot(),
        "repo_root": REPO_ROOT,
        "strategy_id": _STRATEGY_ID,
        "target_draw_numbers": _TARGET_DRAW_NUMBERS,
        "method_family": _METHOD_FAMILY,
        "replay_status": ReplayStatus.BASELINE_RECORDED,
        "producer": _producer(),
    }
    fields.update(overrides)
    return CanonicalEvaluationRequest(**fields)


# --------------------------------------------------------------------------
# Window contract: the runner re-asserts the evaluator's order, never its own
# --------------------------------------------------------------------------


def test_expected_window_order_is_the_evaluators_own_order() -> None:
    assert tuple(kind for kind, _ in WINDOW_SIZES) == EXPECTED_WINDOW_ORDER
    assert EXPECTED_WINDOW_ORDER == (
        WindowKind.WINDOW_50,
        WindowKind.WINDOW_300,
        WindowKind.WINDOW_750,
        WindowKind.FULL_HISTORY,
    )
    assert EXPECTED_ARTIFACT_COUNT == 4


def test_runner_is_pinned_to_big_lotto_single_ticket() -> None:
    assert RUNNER_LOTTERY_TYPE is LotteryType.BIG_LOTTO
    assert RUNNER_MATCH_CONTRACT.lottery_type == LotteryType.BIG_LOTTO.value
    assert RUNNER_MATCH_CONTRACT.ticket_number_count == 6


# --------------------------------------------------------------------------
# Request construction fails closed
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"strategy_id": "   "}, "strategy_id must be a non-empty string"),
        ({"method_family": ""}, "method_family must be a non-empty string"),
        ({"target_draw_numbers": ()}, "target_draw_numbers must not be empty"),
        (
            {"target_draw_numbers": ("1000100", "  ")},
            "must not contain a blank draw number",
        ),
        (
            {"target_draw_numbers": ("1000100", "1000101", "1000100")},
            "target_draw_numbers contain duplicates: 1000100",
        ),
        (
            {"expected_strategy_version": " "},
            "expected_strategy_version must be omitted or a non-empty string",
        ),
    ],
)
def test_request_rejects_malformed_inputs(
    tmp_path: Path, overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(CanonicalEvaluationEvidenceRunnerError, match=message):
        _request(tmp_path, **overrides)


# --------------------------------------------------------------------------
# The strategy gate: one BIG_LOTTO SINGLE_TICKET strategy, or nothing
# --------------------------------------------------------------------------


def _descriptor(
    strategy_id: str,
    *,
    lottery_types: tuple[LotteryType, ...] = (LotteryType.BIG_LOTTO,),
    response_shape: ResponseShape = ResponseShape.SINGLE_TICKET,
    native_ticket_count: int = 1,
) -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id=strategy_id,
        strategy_name=f"synthetic {strategy_id}",
        version="v0.1",
        lottery_types=lottery_types,
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=f"tests.synthetic:{strategy_id}",
        response_shape=response_shape,
        native_ticket_count=native_ticket_count,
    )


def test_gate_accepts_a_real_big_lotto_single_ticket_strategy() -> None:
    descriptor = resolve_single_ticket_descriptor(_STRATEGY_ID)

    assert descriptor.strategy_id == _STRATEGY_ID
    assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
    assert LotteryType.BIG_LOTTO in descriptor.lottery_types
    assert descriptor.native_ticket_count_bounds == (1, 1)


def test_gate_rejects_an_unregistered_strategy() -> None:
    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError, match="is not registered in the replay catalog"
    ):
        resolve_single_ticket_descriptor("no_such_strategy_at_all")


def test_gate_rejects_a_strategy_registered_for_another_lottery() -> None:
    catalog = StrategyCatalog(
        (_descriptor("synthetic_power_only", lottery_types=(LotteryType.POWER_LOTTO,)),)
    )

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError, match="is not registered for BIG_LOTTO"
    ):
        resolve_single_ticket_descriptor("synthetic_power_only", catalog=catalog)


def test_gate_rejects_a_portfolio_strategy() -> None:
    catalog = StrategyCatalog(
        (
            _descriptor(
                "synthetic_portfolio",
                response_shape=ResponseShape.PORTFOLIO,
                native_ticket_count=5,
            ),
        )
    )

    with pytest.raises(CanonicalEvaluationEvidenceRunnerError, match="has response_shape"):
        resolve_single_ticket_descriptor("synthetic_portfolio", catalog=catalog)


def test_single_ticket_shape_already_guarantees_exactly_one_native_ticket() -> None:
    """The gate needs no ticket-count check: the descriptor contract enforces it.

    ``StrategyDescriptor`` refuses to construct a SINGLE_TICKET strategy whose
    native ticket bounds are anything but ``(1, 1)``, which is the invariant
    V1A's fixed one-ticket exposure rests on.
    """

    with pytest.raises(ValueError, match="SINGLE_TICKET strategies must declare"):
        _descriptor("synthetic_multi", native_ticket_count=3)

    single_ticket = [
        descriptor
        for descriptor in production_catalog()
        if descriptor.response_shape is ResponseShape.SINGLE_TICKET
    ]
    assert single_ticket
    assert all(
        descriptor.native_ticket_count_bounds == (1, 1) for descriptor in single_ticket
    )


def test_runner_rejects_a_real_portfolio_strategy(tmp_path: Path) -> None:
    """The runner's own gate is not injectable: it resolves the production catalog."""

    portfolio_id = next(
        descriptor.strategy_id
        for descriptor in production_catalog()
        if descriptor.response_shape is ResponseShape.PORTFOLIO
        and LotteryType.BIG_LOTTO in descriptor.lottery_types
    )

    with pytest.raises(CanonicalEvaluationEvidenceRunnerError, match="has response_shape"):
        run_canonical_evaluation_evidence(_request(tmp_path, strategy_id=portfolio_id))


# --------------------------------------------------------------------------
# Hermetic-input guards, all decided before any replay runs
# --------------------------------------------------------------------------


def test_runner_rejects_a_dataset_for_another_lottery(tmp_path: Path) -> None:
    request = _request(tmp_path, dataset=_dataset_snapshot(lottery_type=LotteryType.DAILY_539))

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError, match="this vertical evaluates BIG_LOTTO only"
    ):
        run_canonical_evaluation_evidence(request)


def test_runner_rejects_an_unreadable_repo_root(tmp_path: Path) -> None:
    request = _request(tmp_path, repo_root=tmp_path / "not-a-directory")

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError, match="is not a readable directory"
    ):
        run_canonical_evaluation_evidence(request)


def test_runner_never_falls_back_to_the_production_database(tmp_path: Path) -> None:
    """An absent task-owned database is a hard stop, never a production replay."""

    directory = tmp_path / "absent"
    directory.mkdir()
    paths = LocalDataPaths(data_directory=directory, database=directory / "lottolab.db")

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError,
        match="never falls back to the production database",
    ):
        run_canonical_evaluation_evidence(_request(tmp_path, database_paths=paths))


def test_runner_rejects_a_target_absent_from_the_dataset(tmp_path: Path) -> None:
    request = _request(tmp_path, target_draw_numbers=("1000100", "9999999"))

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError,
        match="target draws are absent from the dataset snapshot: 9999999",
    ):
        run_canonical_evaluation_evidence(request)


def test_runner_rejects_a_dataset_that_repeats_a_draw(tmp_path: Path) -> None:
    duplicated = DrawEntry(
        draw_id="1000100",
        draw_sequence=110,
        draw_date=date(2020, 4, 20),
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_numbers=(7,),
    )
    dataset = _dataset_snapshot()
    request = _request(tmp_path, dataset=_dataset_snapshot(draws=(*dataset.draws, duplicated)))

    with pytest.raises(
        CanonicalEvaluationEvidenceRunnerError,
        match="dataset snapshot contains a duplicate draw 1000100",
    ):
        run_canonical_evaluation_evidence(request)
