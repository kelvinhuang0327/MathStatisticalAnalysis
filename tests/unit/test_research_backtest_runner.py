"""Unit contract for the deterministic BIG_LOTTO research-backtest manifest."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date

import pytest

from lottolab.application.research_backtest_runner import (
    BIG_LOTTO_RESEARCH_BACKTEST_RUN_MANIFEST_V1,
    BigLottoResearchBacktestManifest,
    ResearchBacktestInputError,
    RunBigLottoResearchBacktest,
    StrategySourceIdentity,
)
from lottolab.application.research_store import ResearchStore
from lottolab.application.use_cases.generate_ordered_candidate_emission import (
    build_production_generate_ordered_candidate_emission,
    build_production_generate_ordered_portfolio_emission,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_materialization import (
    OrderedCandidateSourceRow,
    OrderedCandidateSourceSnapshot,
)
from lottolab.domain.research import ResearchRunKind
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor
from lottolab.evidence.ordered_candidate_emission_package import (
    source_snapshot_sha256,
)
from lottolab.strategies.catalog import StrategyCatalog, production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

_STRATEGY = "biglotto_social_wisdom_anti_popularity"
_COMMIT = "a" * 40
_RUNTIME = (
    '{"implementation":"CPython","runner_version":"1.0.0",'
    '"schema_version":"TEST_RUNTIME_V1"}'
)


class _Reader:
    def __init__(self, snapshot: OrderedCandidateSourceSnapshot) -> None:
        self.snapshot = snapshot

    def read_source_snapshot(
        self,
        lottery_type: LotteryType,
    ) -> OrderedCandidateSourceSnapshot:
        assert lottery_type is LotteryType.BIG_LOTTO
        return self.snapshot


class _IdentityResolver:
    def __init__(self, digest: str = "b" * 64) -> None:
        self.digest = digest
        self.calls: list[str] = []

    def resolve(
        self,
        *,
        strategy_id: str,
        loaded_adapter: type[object],
    ) -> StrategySourceIdentity:
        assert loaded_adapter is not None
        self.calls.append(strategy_id)
        return StrategySourceIdentity(
            strategy_source_sha256=self.digest,
            runtime_fingerprint=_RUNTIME,
        )


def _row(index: int) -> OrderedCandidateSourceRow:
    main = tuple(range(index, index + 6))
    special = index + 6
    return OrderedCandidateSourceRow(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_date=date(2026, 1, index),
        draw_number=str(index),
        main_numbers=main,
        special_numbers=(special,),
        normalized_record_hash=f"{index:064x}",
    )


def _snapshot(count: int = 4) -> OrderedCandidateSourceSnapshot:
    rows = tuple(_row(index) for index in range(1, count + 1))
    return OrderedCandidateSourceSnapshot(
        lottery_type=LotteryType.BIG_LOTTO,
        rows=rows,
        source_snapshot_sha256=source_snapshot_sha256(rows),
    )


def _manifest(
    snapshot: OrderedCandidateSourceSnapshot,
    *,
    targets: tuple[str, ...] = ("2", "3"),
    strategies: tuple[str, ...] = (_STRATEGY,),
    minimum: int = 1,
    maximum: int = 3,
) -> BigLottoResearchBacktestManifest:
    return BigLottoResearchBacktestManifest(
        schema_version=BIG_LOTTO_RESEARCH_BACKTEST_RUN_MANIFEST_V1,
        lottery_type=LotteryType.BIG_LOTTO,
        run_kind=ResearchRunKind.HISTORICAL_BACKTEST,
        dataset_id="fixture",
        dataset_version="v1",
        expected_source_snapshot_sha256=snapshot.source_snapshot_sha256,
        target_draws=targets,
        strategy_ids=strategies,
        minimum_history_draws=minimum,
        maximum_history_draws=maximum,
        replicate=1,
    )


def _forbidden_repository() -> ResearchStore:
    raise AssertionError("research repository must not be created")


def _runner(
    snapshot: OrderedCandidateSourceSnapshot,
    *,
    catalog: StrategyCatalog | None = None,
    resolver: _IdentityResolver | None = None,
    source_commit_resolver: Callable[[], str] | None = None,
) -> RunBigLottoResearchBacktest:
    selected_catalog = catalog or production_catalog()
    identity_resolver = resolver or _IdentityResolver()
    commit_resolver = (
        (lambda: _COMMIT)
        if source_commit_resolver is None
        else source_commit_resolver
    )
    return RunBigLottoResearchBacktest(
        repository_factory=_forbidden_repository,
        source_reader=_Reader(snapshot),
        catalog=selected_catalog,
        executable_registry=ExecutableRegistry(selected_catalog),
        generate_ordered_candidate_emission=(
            build_production_generate_ordered_candidate_emission()
        ),
        generate_ordered_portfolio_emission=(
            build_production_generate_ordered_portfolio_emission()
        ),
        source_commit_resolver=commit_resolver,
        strategy_source_identity_resolver=identity_resolver,
    )


def test_manifest_canonical_parse_serialize_and_digest() -> None:
    snapshot = _snapshot()
    manifest = _manifest(snapshot)

    encoded = manifest.canonical_file_bytes()
    parsed = BigLottoResearchBacktestManifest.from_canonical_file_bytes(encoded)

    assert parsed == manifest
    assert parsed.canonical_file_bytes() == encoded
    assert parsed.manifest_sha256 == manifest.manifest_sha256
    assert encoded.endswith(b"\n")


def test_manifest_rejects_noncanonical_file_bytes() -> None:
    manifest = _manifest(_snapshot())

    with pytest.raises(
        ResearchBacktestInputError,
        match="canonical JSON encoding",
    ) as error:
        BigLottoResearchBacktestManifest.from_canonical_file_bytes(
            manifest.canonical_file_bytes().rstrip(b"\n")
        )

    assert error.value.reason_code == "NON_CANONICAL_MANIFEST_JSON"


@pytest.mark.parametrize(
    ("change", "reason_code"),
    [
        ({"schema_version": "v0"}, "INVALID_MANIFEST_SCHEMA_VERSION"),
        ({"lottery_type": "POWER_LOTTO"}, "UNSUPPORTED_LOTTERY_TYPE"),
        ({"replicate": 2}, "INVALID_REPLICATE"),
        ({"minimum_history_draws": 0}, "INVALID_HISTORY_BOUNDS"),
        (
            {"minimum_history_draws": 3, "maximum_history_draws": 2},
            "INVALID_HISTORY_BOUNDS",
        ),
        ({"target_draws": ("2", "2")}, "DUPLICATE_TARGET_DRAW"),
        ({"strategy_ids": (_STRATEGY, _STRATEGY)}, "DUPLICATE_STRATEGY_ID"),
    ],
)
def test_manifest_rejects_invalid_closed_contract_values(
    change: dict[str, object],
    reason_code: str,
) -> None:
    manifest = _manifest(_snapshot())

    with pytest.raises(ResearchBacktestInputError) as error:
        replace(manifest, **change)

    assert error.value.reason_code == reason_code


@pytest.mark.parametrize("lottery_type", [LotteryType.DAILY_539, LotteryType.POWER_LOTTO])
def test_manifest_accepts_every_lottery_type_with_an_active_rule_contract(
    lottery_type: LotteryType,
) -> None:
    manifest = replace(_manifest(_snapshot()), lottery_type=lottery_type)

    assert manifest.lottery_type is lottery_type


@pytest.mark.parametrize("lottery_type", [LotteryType.DAILY_539, LotteryType.POWER_LOTTO])
def test_non_biglotto_manifest_still_rejects_a_biglotto_only_strategy(
    lottery_type: LotteryType,
) -> None:
    """Accepting other lottery types at the manifest gate must not silently let a
    BIG_LOTTO-only strategy execute mislabeled as another lottery: the runner's
    separate per-strategy compatibility gate still closes that path."""

    snapshot = _snapshot()
    manifest = replace(_manifest(snapshot), lottery_type=lottery_type)

    with pytest.raises(ResearchBacktestInputError) as error:
        _runner(snapshot).execute(manifest)

    assert error.value.reason_code == "STRATEGY_NOT_LOTTERY_TYPE_COMPATIBLE"


def test_zero_prior_target_rejects_before_repository_provenance_or_strategy() -> None:
    snapshot = _snapshot()
    resolver = _IdentityResolver()
    source_commit_called = False

    def forbidden_source_commit() -> str:
        nonlocal source_commit_called
        source_commit_called = True
        raise AssertionError("source commit must not resolve")

    runner = _runner(
        snapshot,
        resolver=resolver,
        source_commit_resolver=forbidden_source_commit,
    )

    with pytest.raises(ResearchBacktestInputError) as error:
        runner.execute(_manifest(snapshot, targets=("1",)))

    assert error.value.reason_code == "TARGET_HAS_NO_STRICTLY_EARLIER_HISTORY"
    assert error.value.target_draw == "1"
    assert resolver.calls == []
    assert source_commit_called is False


def test_mixed_manifest_rejects_atomically_before_repository_or_strategy() -> None:
    snapshot = _snapshot()
    resolver = _IdentityResolver()

    with pytest.raises(ResearchBacktestInputError) as error:
        _runner(snapshot, resolver=resolver).execute(
            _manifest(snapshot, targets=("2", "1"))
        )

    assert error.value.reason_code == "TARGET_HAS_NO_STRICTLY_EARLIER_HISTORY"
    assert error.value.target_draw == "1"
    assert resolver.calls == []


def test_first_target_with_one_strictly_earlier_row_is_valid() -> None:
    snapshot = _snapshot()

    run_id = _runner(snapshot).deterministic_run_id(
        _manifest(snapshot, targets=("2",), minimum=2)
    )

    assert run_id.startswith("run-biglotto-backtest-")


def test_source_snapshot_mismatch_rejects_before_repository() -> None:
    snapshot = _snapshot()
    manifest = replace(
        _manifest(snapshot),
        expected_source_snapshot_sha256="f" * 64,
    )

    with pytest.raises(ResearchBacktestInputError) as error:
        _runner(snapshot).execute(manifest)

    assert error.value.reason_code == "SOURCE_SNAPSHOT_SHA256_MISMATCH"


def test_unknown_strategy_rejects_before_repository() -> None:
    snapshot = _snapshot()

    with pytest.raises(ResearchBacktestInputError) as error:
        _runner(snapshot).execute(
            _manifest(snapshot, strategies=("unknown_strategy",))
        )

    assert error.value.reason_code == "UNKNOWN_STRATEGY"


def test_non_executable_strategy_rejects_before_repository() -> None:
    snapshot = _snapshot()
    catalog = StrategyCatalog(
        (
            StrategyDescriptor(
                strategy_id="observation_only",
                strategy_name="Observation only",
                version="v1",
                lottery_types=(LotteryType.BIG_LOTTO,),
                lifecycle_status=LifecycleStatus.OBSERVATION,
                executable=False,
            ),
        )
    )

    with pytest.raises(ResearchBacktestInputError) as error:
        _runner(snapshot, catalog=catalog).execute(
            _manifest(snapshot, strategies=("observation_only",))
        )

    assert error.value.reason_code == "STRATEGY_NOT_EXECUTABLE"


def test_identical_manifest_and_source_identity_resolve_same_run_id() -> None:
    snapshot = _snapshot()
    manifest = _manifest(snapshot)

    first = _runner(snapshot).deterministic_run_id(manifest)
    second = _runner(snapshot).deterministic_run_id(manifest)

    assert first == second


def test_material_manifest_change_resolves_different_run_id() -> None:
    snapshot = _snapshot()
    manifest = _manifest(snapshot)

    first = _runner(snapshot).deterministic_run_id(manifest)
    second = _runner(snapshot).deterministic_run_id(
        replace(manifest, dataset_version="v2")
    )

    assert first != second


def test_material_strategy_source_change_resolves_different_run_id() -> None:
    snapshot = _snapshot()
    manifest = _manifest(snapshot)

    first = _runner(
        snapshot,
        resolver=_IdentityResolver("b" * 64),
    ).deterministic_run_id(manifest)
    second = _runner(
        snapshot,
        resolver=_IdentityResolver("c" * 64),
    ).deterministic_run_id(manifest)

    assert first != second
