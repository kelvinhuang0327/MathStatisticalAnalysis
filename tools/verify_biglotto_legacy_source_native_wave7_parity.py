"""Verify wave-7 ports against exact frozen Git bytes."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import random
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave7 import (
    APRIORI_BACKTEST_METHOD_ID,
    APRIORI_PREDICT_METHOD_ID,
    BEST_HYBRID_METHOD_ID,
    CLUSTER_6_METHOD_ID,
    CLUSTER_7_METHOD_ID,
    SOURCE_NATIVE_WAVE7_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE7_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE7_METHODS,
    LegacySourceNativeWave7Request,
    generate_legacy_source_native_wave7_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE7_FROZEN_PARITY_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
CASE_HISTORY_LENGTHS = (10, 150, 2148)


class FrozenParityError(ValueError):
    """Frozen source bytes or outputs differ from the wave-7 port."""


class _DatabaseManager:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass


def _git_show(
    *,
    source_repository: Path,
    source_commit: str,
    source_path: str,
) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{source_commit}:{source_path}"],
        cwd=source_repository,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise FrozenParityError(
            completed.stderr.decode("utf-8", errors="replace")
        )
    expected = SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE7_METHOD[
        source_path
    ]
    if hashlib.sha256(completed.stdout).hexdigest() != expected:
        raise FrozenParityError(
            f"frozen source SHA-256 changed: {source_path}"
        )
    return completed.stdout


def _install_dependency_modules() -> dict[str, ModuleType | None]:
    prior = {
        name: sys.modules.get(name)
        for name in (
            "common",
            "database",
            "tools.predict_biglotto_6bets_cluster",
            "tools.predict_biglotto_apriori",
        )
    }
    common = ModuleType("common")
    common.get_lottery_rules = lambda _lottery_type: {}  # type: ignore[attr-defined]
    database = ModuleType("database")
    database.DatabaseManager = _DatabaseManager  # type: ignore[attr-defined]
    sys.modules["common"] = common
    sys.modules["database"] = database
    return prior


def _restore_dependency_modules(
    prior: dict[str, ModuleType | None],
) -> None:
    for name, module in prior.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


def _load_module(
    *,
    source_bytes: bytes,
    source_path: str,
    module_name: str,
) -> ModuleType:
    module = ModuleType(module_name)
    module.__file__ = source_path
    module.__package__ = module_name.rpartition(".")[0]
    exec(
        compile(source_bytes, source_path, "exec"),
        module.__dict__,
    )
    return module


def _source_history(
    history: tuple[LegacyHistoryDraw, ...],
    *,
    newest_first: bool,
) -> list[dict[str, object]]:
    draws = reversed(history) if newest_first else iter(history)
    return [
        {
            "draw": draw.draw_number,
            "numbers": list(draw.numbers),
        }
        for draw in draws
    ]


def _frozen_cluster(
    module: ModuleType,
    history: tuple[LegacyHistoryDraw, ...],
    *,
    num_bets: int,
) -> list[list[int]]:
    predictor_class = cast(
        type[Any],
        module.BigLottoClusterPivotPredictor,
    )
    predictor = predictor_class()
    predictor.get_draws = lambda: _source_history(  # type: ignore[method-assign]
        history,
        newest_first=True,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        result = predictor.generate_bets(
            num_bets=num_bets,
            window=150,
        )
    tickets: list[list[int]] = []
    for row_raw in cast(list[object], result):
        row = cast(dict[str, object], row_raw)
        tickets.append(list(cast(list[int], row["numbers"])))
    return tickets


def _frozen_apriori_predict(
    module: ModuleType,
    history: tuple[LegacyHistoryDraw, ...],
) -> list[list[int]]:
    predictor_class = cast(
        type[Any],
        module.BigLottoAprioriPredictor,
    )
    predictor = predictor_class()
    predictor.get_draws = lambda: _source_history(  # type: ignore[method-assign]
        history,
        newest_first=True,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        result = predictor.predict_next_draw(
            num_bets=7,
            window=150,
        )
    tickets: list[list[int]] = []
    for row_raw in cast(list[object], result):
        row = cast(dict[str, object], row_raw)
        tickets.append(list(cast(list[int], row["numbers"])))
    return tickets


def _frozen_apriori_backtest(
    module: ModuleType,
    history: tuple[LegacyHistoryDraw, ...],
    *,
    seed_integer: int,
) -> list[list[int]]:
    predictor_class = cast(type[Any], module.BacktestApriori)
    predictor = predictor_class()
    source_history = _source_history(history, newest_first=False)
    random.seed(seed_integer, version=2)
    with contextlib.redirect_stdout(io.StringIO()):
        return [
            list(ticket)
            for num_bets in (1, 2, 3, 7)
            for ticket in predictor.predict_for_backtest(
                source_history,
                num_bets=num_bets,
                window=150,
            )
        ]


def _frozen_best(
    *,
    cluster_module: ModuleType,
    best_module: ModuleType,
    history: tuple[LegacyHistoryDraw, ...],
    seed_integer: int,
) -> list[list[int]]:
    random.seed(seed_integer, version=2)
    cluster = _frozen_cluster(
        cluster_module,
        history,
        num_bets=6,
    )
    skew = cast(
        dict[str, object],
        best_module.generate_skew_bet(),
    )
    return [*cluster, list(cast(list[int], skew["numbers"]))]


def verify_frozen_parity(
    *,
    source_repository: Path,
    source_commit: str,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    if source_commit != FROZEN_SOURCE_COMMIT:
        raise FrozenParityError("unexpected frozen source commit")
    pinned = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=expected_database_sha256,
        require_replay_authority=False,
    )
    history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in pinned.draws
    )
    source_bytes = {
        method_id: _git_show(
            source_repository=source_repository,
            source_commit=source_commit,
            source_path=method_id,
        )
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE7_METHODS
    }
    prior = _install_dependency_modules()
    try:
        cluster6 = _load_module(
            source_bytes=source_bytes[CLUSTER_6_METHOD_ID],
            source_path=CLUSTER_6_METHOD_ID,
            module_name="tools.predict_biglotto_6bets_cluster",
        )
        sys.modules["tools.predict_biglotto_6bets_cluster"] = cluster6
        cluster7 = _load_module(
            source_bytes=source_bytes[CLUSTER_7_METHOD_ID],
            source_path=CLUSTER_7_METHOD_ID,
            module_name="frozen_wave7_cluster7",
        )
        apriori = _load_module(
            source_bytes=source_bytes[APRIORI_PREDICT_METHOD_ID],
            source_path=APRIORI_PREDICT_METHOD_ID,
            module_name="tools.predict_biglotto_apriori",
        )
        sys.modules["tools.predict_biglotto_apriori"] = apriori
        backtest = _load_module(
            source_bytes=source_bytes[APRIORI_BACKTEST_METHOD_ID],
            source_path=APRIORI_BACKTEST_METHOD_ID,
            module_name="frozen_wave7_backtest_apriori",
        )
        best = _load_module(
            source_bytes=source_bytes[BEST_HYBRID_METHOD_ID],
            source_path=BEST_HYBRID_METHOD_ID,
            module_name="frozen_wave7_best",
        )
        modules = {
            CLUSTER_6_METHOD_ID: cluster6,
            CLUSTER_7_METHOD_ID: cluster7,
            APRIORI_PREDICT_METHOD_ID: apriori,
            APRIORI_BACKTEST_METHOD_ID: backtest,
            BEST_HYBRID_METHOD_ID: best,
        }
        cases: list[dict[str, object]] = []
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE7_METHODS:
            for history_length in CASE_HISTORY_LENGTHS:
                case_history = history[:history_length]
                request = LegacySourceNativeWave7Request(
                    legacy_method_id=method_id,
                    target_draw_number=f"parity-{history_length}",
                    history=case_history,
                )
                port = generate_legacy_source_native_wave7_portfolio(
                    request
                )
                if method_id == CLUSTER_6_METHOD_ID:
                    frozen = _frozen_cluster(
                        modules[method_id],
                        case_history,
                        num_bets=6,
                    )
                elif method_id == CLUSTER_7_METHOD_ID:
                    frozen = _frozen_cluster(
                        modules[method_id],
                        case_history,
                        num_bets=7,
                    )
                elif method_id == APRIORI_PREDICT_METHOD_ID:
                    frozen = _frozen_apriori_predict(
                        modules[method_id],
                        case_history,
                    )
                elif method_id == APRIORI_BACKTEST_METHOD_ID:
                    frozen = _frozen_apriori_backtest(
                        modules[method_id],
                        case_history,
                        seed_integer=port.metadata.seed_integer,
                    )
                else:
                    frozen = _frozen_best(
                        cluster_module=cluster6,
                        best_module=modules[method_id],
                        history=case_history,
                        seed_integer=port.metadata.seed_integer,
                    )
                actual = [list(ticket) for ticket in port.tickets]
                if frozen != actual:
                    raise FrozenParityError(
                        f"ticket parity failed: {method_id} "
                        f"history={history_length}"
                    )
                cases.append(
                    {
                        "history_draw_count": history_length,
                        "legacy_method_id": method_id,
                        "native_ticket_count": len(actual),
                        "seed_digest": port.metadata.seed_digest,
                        "ticket_sha256": hashlib.sha256(
                            json.dumps(
                                actual,
                                separators=(",", ":"),
                            ).encode("ascii")
                        ).hexdigest(),
                    }
                )
    finally:
        _restore_dependency_modules(prior)
    return {
        "case_count": len(cases),
        "cases": cases,
        "database_sha256": pinned.database_sha256_before,
        "execution_mode": (
            "PYTHON_COMPILE_EXEC_OF_EXACT_GIT_SHOW_BYTES_CALLING_"
            "FROZEN_SELECTION_FUNCTIONS_ONLY"
        ),
        "frozen_source_commit": source_commit,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "port_protocol": SOURCE_NATIVE_WAVE7_PROTOCOL,
        "random_parity_semantics": (
            "EXACT_FROZEN_RANDOM_CALL_ORDER_UNDER_INJECTED_VERSIONED_"
            "TARGET_STABLE_SEED_NOT_ORIGINAL_STATE_RECOVERY"
        ),
        "source_sha256": dict(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE7_METHOD
        ),
        "status": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-repository", type=Path, required=True)
    parser.add_argument(
        "--source-commit",
        default=FROZEN_SOURCE_COMMIT,
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument(
        "--expected-database-sha256",
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FrozenParityError(
            f"refusing to overwrite existing output: {args.output}"
        )
    document = verify_frozen_parity(
        source_repository=args.source_repository,
        source_commit=args.source_commit,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(
        json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


if __name__ == "__main__":
    main()
