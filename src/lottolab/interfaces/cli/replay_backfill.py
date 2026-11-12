"""Offline replay worker: python -m lottolab.interfaces.cli.replay_backfill."""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

from lottolab.application.historical_replay_adapters import (
    BigLottoReplayAdapter,
    Daily539ReplayAdapter,
    PowerLottoReplayAdapter,
    ReplayStrategyBinding,
    binding_from_p638_spec,
    t539_replay_bindings,
)
from lottolab.application.seeded_single_replay import SEED_CONTRACT, SeededSingleTicketReplay
from lottolab.application.use_cases.generate_bet import (
    instantiate_adapter,
    instantiate_portfolio_adapter,
)
from lottolab.application.use_cases.historical_replay_controller import HistoricalReplayAdapter
from lottolab.application.use_cases.replay_backfill import (
    BackfillSelection,
    JsonObject,
    ReplayBackfill,
    canonical_json,
    identity,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayBehavior, ReplayStrategy
from lottolab.domain.prize_evaluation import evaluate_lottery_prize
from lottolab.domain.strategies import ResponseShape
from lottolab.infrastructure.persistence.draw_schema import resolve_local_data_paths
from lottolab.infrastructure.persistence.replay_backfill_store import (
    SCHEMA_SQL,
    SQLiteBackfillStore,
    load_draw_snapshot,
    validate_database_path,
)
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_batch16 import _EvolutionEngine
from lottolab.strategies.adapters.biglotto_evolution_bounded import BigLottoBoundedEvolutionAdapter
from lottolab.strategies.adapters.biglotto_evolution_causal import BigLottoCausalEvolutionAdapter
from lottolab.strategies.adapters.biglotto_evolution_strict import BigLottoStrictEvolutionAdapter
from lottolab.strategies.adapters.powerlotto_wave1 import WAVE1_STRATEGIES
from lottolab.strategies.adapters.powerlotto_wave2 import WAVE2_STRATEGIES
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry


def native_strategy_inventory(
    lottery_type: LotteryType,
) -> tuple[tuple[ReplayStrategyBinding, ...], JsonObject]:
    """Account for every current catalog identity and every native replay binding.

    P638's complete replay specs retain genuine second-zone history. A catalog
    bridge which only emits a first-zone ticket is explicitly excluded unless
    an existing complete native spec supplies that same identity/version.
    """
    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    bindings: dict[str, ReplayStrategyBinding] = {}
    accounts: JsonObject = {}
    if lottery_type is LotteryType.DAILY_539:
        for binding in t539_replay_bindings():
            bindings[binding.strategy.strategy_id] = binding
    elif lottery_type is LotteryType.POWER_LOTTO:
        for spec in (*WAVE1_STRATEGIES, *WAVE2_STRATEGIES):
            binding = binding_from_p638_spec(spec)
            bindings[binding.strategy.strategy_id] = binding
    for key, binding in bindings.items():
        implementation = binding.implementation
        source_file = inspect.getsourcefile(type(implementation))
        accounts[key] = {
            "status": "EXECUTABLE",
            "strategy_version": binding.strategy.strategy_version,
            "source": "EXISTING_TARGET_NATIVE_REPLAY_BINDING",
            "source_module": type(implementation).__module__,
            "source_sha256": hashlib.sha256(Path(source_file).read_bytes()).hexdigest()
            if source_file
            else None,
            "provenance": getattr(implementation, "provenance", None),
            "model_version_or_null": getattr(implementation, "model_version", None),
            "fingerprint": binding.strategy.fingerprint,
            "behavior": binding.strategy.behavior.value,
        }
    for descriptor in catalog.list(lottery_type=lottery_type):
        sid = descriptor.strategy_id
        provenance = list(descriptor.provenance)
        if sid in bindings:
            if bindings[sid].strategy.strategy_version != descriptor.version:
                raise ValueError(f"native/catalog version conflict: {sid}")
            accounts[sid]["catalog_provenance"] = provenance
            continue
        if not descriptor.executable:
            accounts[sid] = {
                "status": "EXCLUDED",
                "reason": "CATALOG_NOT_EXECUTABLE",
                "catalog_provenance": provenance,
            }
            continue
        if lottery_type is LotteryType.POWER_LOTTO:
            accounts[sid] = {
                "status": "EXCLUDED",
                "reason": "NO_COMPLETE_SECOND_ZONE_REPLAY_SOURCE",
                "catalog_provenance": provenance,
            }
            continue
        try:
            cls = registry.load_adapter(sid)
            implementation = (
                instantiate_adapter(sid, cls)
                if descriptor.response_shape is ResponseShape.SINGLE_TICKET
                else instantiate_portfolio_adapter(sid, cls)
            )
            if (
                implementation.strategy_id,
                implementation.strategy_name,
                implementation.strategy_version,
            ) != (sid, descriptor.strategy_name, descriptor.version):
                raise ValueError("adapter/catalog identity mismatch")
            count = getattr(implementation, "native_ticket_count", 1)
            if count != descriptor.native_ticket_count:
                raise ValueError("adapter/catalog native ticket count mismatch")
            source_file = inspect.getsourcefile(type(implementation))
            if source_file is None:
                raise ValueError("adapter source is unavailable")
            source_sha = hashlib.sha256(Path(source_file).read_bytes()).hexdigest()
            unseeded_live_rng = (
                lottery_type is LotteryType.BIG_LOTTO
                and descriptor.response_shape is ResponseShape.SINGLE_TICKET
                and "randomness:PROCESS_GLOBAL_UNSEEDED_MATH_RANDOM_EQUIVALENT" in provenance
            )
            behavior = getattr(implementation, "replay_behavior", ReplayBehavior.DETERMINISTIC)
            seed_contract = getattr(implementation, "replay_seed_contract", None)
            wrapper_sha = None
            if unseeded_live_rng:
                wrapper_file = inspect.getsourcefile(SeededSingleTicketReplay)
                if wrapper_file is None:
                    raise ValueError("seeded replay wrapper source is unavailable")
                wrapper_sha = hashlib.sha256(Path(wrapper_file).read_bytes()).hexdigest()
                implementation = SeededSingleTicketReplay(
                    sid, descriptor.strategy_name, descriptor.version, descriptor.min_history, cls
                )
                behavior = ReplayBehavior.SEEDED_STOCHASTIC
                seed_contract = SEED_CONTRACT
            strategy_version = implementation.strategy_version
            fingerprint_payload = {"descriptor": asdict(descriptor), "source": source_sha}
            dependency_sha: dict[str, str] = {}
            if sid == "legacy_biglotto__evolution_engine__3df019c31ce4" and strategy_version in {
                "v0.3",
                "v0.4",
                "v0.5",
            }:
                dependencies = [_EvolutionEngine, BigLottoCausalEvolutionAdapter]
                if strategy_version in {"v0.4", "v0.5"}:
                    dependencies.append(BigLottoStrictEvolutionAdapter)
                if strategy_version == "v0.5":
                    dependencies.extend([BigLottoBoundedEvolutionAdapter, CausalDrawRow])
                for dependency in dependencies:
                    dependency_file = inspect.getsourcefile(dependency)
                    if dependency_file is None:
                        raise ValueError("evolution dependency source is unavailable")
                    dependency_sha[dependency.__module__] = hashlib.sha256(
                        Path(dependency_file).read_bytes()
                    ).hexdigest()
                fingerprint_payload["dependency_sha256"] = dependency_sha
            if seed_contract is not None:
                fingerprint_payload["seed_contract"] = seed_contract
            if unseeded_live_rng:
                fingerprint_payload.update(
                    {"seed_contract": seed_contract, "seed_wrapper_sha256": wrapper_sha}
                )
            strategy = ReplayStrategy(
                sid,
                descriptor.strategy_name,
                strategy_version,
                behavior,
                descriptor.native_ticket_count,
                max(descriptor.min_history, implementation.min_history),
                fingerprint=identity(fingerprint_payload),
                seed_contract=seed_contract,
            )
            bindings[sid] = ReplayStrategyBinding(strategy, implementation)
            accounts[sid] = {
                "status": "EXECUTABLE",
                "strategy_version": strategy_version,
                "source": descriptor.adapter_path,
                "source_sha256": source_sha,
                "dependency_sha256": dependency_sha,
                "seed_wrapper_sha256": wrapper_sha,
                "seed_contract": seed_contract,
                "behavior": behavior.value,
                "catalog_provenance": provenance,
                "model_version_or_null": None,
            }
        except Exception as exc:
            accounts[sid] = {
                "status": "BLOCKED",
                "reason": type(exc).__name__ + ": " + str(exc),
                "catalog_provenance": provenance,
            }
    descriptors = {item.strategy_id: item for item in catalog.list(lottery_type=lottery_type)}
    for strategy_id, binding in bindings.items():
        descriptor = descriptors.get(strategy_id)
        account = accounts[strategy_id]
        account["lifecycle_status"] = (
            descriptor.lifecycle_status.value if descriptor is not None else "UNREGISTERED"
        )
        account["data_status"] = "REBUILDABLE"
        account["source_kind"] = (
            "PRODUCTION_CATALOG" if descriptor is not None else "TARGET_NATIVE_REPLAY"
        )
        if (
            strategy_id == "legacy_biglotto__evolution_engine__3df019c31ce4"
            and binding.strategy.strategy_version in {"v0.2", "v0.3", "v0.4", "v0.5"}
        ):
            account["training_status"] = "CAUSAL_FIT_PER_TARGET"
            account["training_holdout_size"] = 50
        else:
            account["training_status"] = "NOT_TRAINABLE"
        account["source_identity"] = account.get("source_sha256") or binding.strategy.fingerprint
    return tuple(bindings[k] for k in sorted(bindings)), accounts


def build_adapter(
    lottery_type: LotteryType, bindings: tuple[ReplayStrategyBinding, ...]
) -> HistoricalReplayAdapter:
    if lottery_type is LotteryType.BIG_LOTTO:
        return BigLottoReplayAdapter(bindings)
    if lottery_type is LotteryType.DAILY_539:
        return Daily539ReplayAdapter(bindings)
    return PowerLottoReplayAdapter(bindings)


def execution_source_identity() -> str:
    """Pin the local code used by adapters, their helpers, scoring and this worker."""
    package = Path(__file__).resolve().parents[2]
    files = [
        *(package / "domain").rglob("*.py"),
        *(package / "strategies").rglob("*.py"),
        package / "application/historical_replay_adapters.py",
        package / "application/use_cases/historical_replay_controller.py",
        package / "application/use_cases/replay_backfill.py",
        package / "infrastructure/persistence/replay_backfill_store.py",
        Path(__file__),
    ]
    digest = hashlib.sha256()
    for file in sorted(set(files)):
        digest.update(str(file.relative_to(package)).encode() + b"\x00" + file.read_bytes())
    return digest.hexdigest()


def source_database_hash(database: Path) -> str:
    """Hash the exact source bytes, including an existing SQLite WAL sidecar."""

    def file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    wal = Path(str(database) + "-wal")
    main_hash = file_hash(database)
    if not wal.exists():
        return main_hash
    digest = hashlib.sha256()
    digest.update(b"main\x00" + main_hash.encode() + b"\x00wal\x00")
    digest.update(file_hash(wal).encode())
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


_KNOWN_RESEARCH_ARTIFACTS = (
    (
        "NUMBER2_A_H12_TEMPORAL_TRIPLE_MOTIF_K5_REPLAY_R1",
        "H12_TEMPORAL_TRIPLE_RESIDUAL_SWAP5_V1",
        "H12_tickets_json",
        "5e1b86d4a1fe35de5c1dd297a99bf0ff68680305bce7fdce9e9b5d295d119c8f",
        1974,
    ),
    (
        "NUMBER2_A_H13_TEMPORAL_PAIR_GRAPH_K5_REPLAY_R1",
        "H13_TEMPORAL_PAIR_RESIDUAL_SWAP5_V1",
        "H13_GRAPH_DELTA_SWAP_tickets_json",
        "fa88b175077151a9fab23885b5a2e97c55ec6da0e54cb6d7e9b4a4a8164c2c1e",
        1974,
    ),
    (
        "NUMBER2_A_H10_DIRECT_TICKET_INTERACTION_K5_REPLAY_R1",
        "H10_PAIR_TRIPLE_TICKET_SCORE_FIXED_V1",
        "H10_tickets_json",
        "9440f78197d101119cb5bb78316ce5bdf6338d586de8770f8ac6c7fe19577a3a",
        1974,
    ),
    (
        "NUMBER2_A_H09_DISPERSION_RELIABILITY_K5_REPLAY_R1",
        "H09_FIXED_DISPERSION_TWO_EXPERT_RELIABILITY_V1",
        "H09_DISPERSION_RELIABILITY_GATE_tickets_json",
        "a8a2731e1c4ca80b2d4b79acf67f8420f7f847908754cc32aa2ce1ac63547b58",
        1774,
    ),
    (
        "NUMBER2_A_H06_CONDITIONAL_MINORITY_K5_REPLAY_R1",
        "H06_STATE_PRIOR_ERROR_MINORITY_K5_V1",
        "H06_CONDITIONAL_MINORITY_tickets_json",
        "363b94cc358ff3a17d8643c8dd3115f4b8e8ccb3a150b7e8300eb249ef530708",
        1874,
    ),
    (
        "NUMBER2_A_H05_REGIME_CONSENSUS_K5_REPLAY_R1",
        "H05_FROZEN_STATE_THREE_EXPERT_CONSENSUS_V1",
        "H05_CONDITIONAL_CONSENSUS_tickets_json",
        "7646bb9c7e9bc9628e5056b28fc7cbd9c255cb0059674114d85922e0f1721c8d",
        1974,
    ),
    (
        "NUMBER2_A_H02_ERROR_GRAPH_PAIR_K5_REPLAY_R1",
        "H02_FIXED_THREE_NODE_ERROR_PAIR_K5_V1",
        "H02_tickets_json",
        "60415dedec5bb32c60d8ea63f7200bfd892f23ca0b2dbaf8792645a56a60a8c5",
        1874,
    ),
    (
        "NUMBER2_A_H21_CONDITIONAL_SUPPRESSION_K5_REPLAY_R1",
        "H21_STATE_CONDITIONAL_FP_SWAP5_V1",
        "H21_STATE_CONDITIONAL_SUPPRESS_tickets_json",
        "f9dd016c5a56ceff8c2fdfe09e54b47dd71592f21b222cb9cc53beec763f4aed",
        1974,
    ),
)


def _csv_integer_list(raw: str) -> list[int]:
    value = json.loads(raw)
    if type(value) is not list or any(type(number) is not int for number in value):
        raise ValueError("artifact integer list is malformed")
    return value


def _csv_integer(raw: str) -> int:
    value = raw.strip()
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        decoded = int(value)
    if type(decoded) is not int:
        raise ValueError("artifact integer is malformed")
    return decoded


def import_known_research_artifacts(database: Path, source_database: Path) -> JsonObject:
    """Import only the eight named H-series result/CSV pairs as artifact-only rows."""
    if not database.is_absolute() or database.resolve() == source_database.resolve():
        raise ValueError("candidate and source databases must be separate absolute paths")
    store = SQLiteBackfillStore(database)
    run_id = store.latest_run_id(LotteryType.BIG_LOTTO.value)
    if run_id is None:
        raise ValueError("a completed-source BIG_LOTTO run must exist before artifact import")
    manifest = store.run_manifest(run_id)
    before_hash = source_database_hash(source_database)
    if manifest.get("source_hash") != before_hash:
        raise ValueError("candidate run uses a different official source database snapshot")
    source_identity = f"{source_database.resolve()}#{before_hash}"
    draws = load_draw_snapshot(source_database, LotteryType.BIG_LOTTO)
    if source_database_hash(source_database) != before_hash:
        raise ValueError("source database changed while loading artifact targets")
    expected_dataset_identity = identity(
        {"source": source_identity, "draws": [asdict(draw) for draw in draws]}
    )
    if manifest.get("dataset_identity") != expected_dataset_identity:
        raise ValueError("candidate run uses a different official draw snapshot")
    draw_by_id = {draw.draw_number: draw for draw in draws}
    task_root = Path("/Users/kelvin/VibeCoding-WorkSpace/.task-data")
    imported_by_task: dict[str, int] = {}
    for (
        task_id,
        method_id,
        ticket_column,
        expected_hash,
        expected_rows,
    ) in _KNOWN_RESEARCH_ARTIFACTS:
        artifact_root = task_root / task_id
        receipt_path = artifact_root / "result.json"
        csv_path = artifact_root / "backtest_rows.csv"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("task_id") != task_id or receipt.get("task_lifecycle_state") != "COMPLETED":
            raise ValueError(f"research receipt is not a completed exact task: {task_id}")
        if receipt.get("METHOD_ID") != method_id:
            raise ValueError(f"research method identity mismatch: {task_id}")
        actual_hash = _sha256_file(csv_path)
        if actual_hash != expected_hash or receipt.get("BACKTEST_ROWS_SHA256") != expected_hash:
            raise ValueError(f"research CSV checksum mismatch: {task_id}")
        artifact_manifest = receipt.get("artifact_manifest", {})
        manifest_csv = artifact_manifest.get("backtest_rows.csv", {})
        if manifest_csv and manifest_csv.get("sha256") != expected_hash:
            raise ValueError(f"research artifact manifest checksum mismatch: {task_id}")
        payloads: list[JsonObject] = []
        seen_targets: set[str] = set()
        with csv_path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None or ticket_column not in reader.fieldnames:
                raise ValueError(f"research ticket field is absent: {task_id}")
            for row in reader:
                draw_id = str(row.get("official_draw_id", "")).strip()
                draw_date = str(row.get("draw_date", "")).strip()
                target = draw_by_id.get(draw_id)
                if target is None or target.draw_date.isoformat() != draw_date:
                    raise ValueError(f"research target is absent from official history: {task_id}")
                if draw_id in seen_targets:
                    raise ValueError(f"duplicate research target: {task_id} {draw_id}")
                seen_targets.add(draw_id)
                observed_main = _csv_integer_list(str(row["actual_main"]))
                observed_special = _csv_integer(str(row["actual_special"]))
                if set(observed_main) != set(target.main_numbers):
                    raise ValueError(f"research target main numbers disagree: {task_id} {draw_id}")
                if observed_special != target.special_number:
                    raise ValueError(
                        f"research target special number disagrees: {task_id} {draw_id}"
                    )
                raw_tickets = json.loads(row[ticket_column])
                if type(raw_tickets) is not list or len(raw_tickets) != 5:
                    raise ValueError(f"research ticket count is not native K5: {task_id} {draw_id}")
                tickets: list[JsonObject] = []
                evaluations: list[JsonObject] = []
                for position, raw_ticket in enumerate(raw_tickets, start=1):
                    if type(raw_ticket) is not list or any(type(n) is not int for n in raw_ticket):
                        raise ValueError(f"research ticket is malformed: {task_id} {draw_id}")
                    main_numbers = tuple(raw_ticket)
                    evaluated = evaluate_lottery_prize(
                        lottery_type=LotteryType.BIG_LOTTO,
                        predicted_main_numbers=main_numbers,
                        predicted_special_number=None,
                        winning_main_numbers=target.main_numbers,
                        winning_special_number=target.special_number,
                    )
                    tickets.append(
                        {
                            "ticket_position": position,
                            "main_numbers": list(main_numbers),
                            "special_number": None,
                        }
                    )
                    evaluations.append(
                        {
                            "zone1_hits": evaluated.zone1_hits,
                            "zone2_hit": evaluated.zone2_hit,
                            "is_winner": evaluated.is_winner,
                            "prize_tier": evaluated.prize_tier,
                            "prize_tier_order": evaluated.prize_tier_order,
                            "prize_rule_version": evaluated.prize_rule_version,
                            "prize_rule_provenance": evaluated.prize_rule_provenance,
                        }
                    )
                strategy_version = method_id.rsplit("_", 1)[-1].lower()
                source = {
                    "source_kind": "HISTORICAL_RESEARCH_ARTIFACT",
                    "source_locator": f"{task_id}/backtest_rows.csv#{ticket_column}",
                    "source_task_id": task_id,
                    "source_hash": expected_hash,
                    "source_identity": f"{task_id}:{method_id}:{expected_hash}",
                }
                cell_id = identity(
                    {
                        "run_id": run_id,
                        "source_identity": source["source_identity"],
                        "strategy_id": method_id,
                        "strategy_version": strategy_version,
                        "target_draw_id": draw_id,
                    }
                )
                payload: JsonObject = {
                    "cell_identity": cell_id,
                    "engine_version": "replay-backfill-v1",
                    "execution_version": f"artifact:{expected_hash}",
                    "lottery_type": LotteryType.BIG_LOTTO.value,
                    "strategy_id": method_id,
                    "strategy_name": method_id,
                    "strategy_version": strategy_version,
                    "strategy_fingerprint": expected_hash,
                    "strategy_source": source,
                    "model_version_or_null": None,
                    "target_draw_id": draw_id,
                    "target_draw_date": draw_date,
                    "cutoff_draw_id": None,
                    "cutoff_draw_date": None,
                    "training": {
                        "training_status": "HISTORICAL_ARTIFACT",
                        "model_version": None,
                        "training_cutoff": None,
                        "training_artifact_id": task_id,
                        "input_source_hash": None,
                        "trainer_identity": None,
                        "training_artifact_hash": expected_hash,
                    },
                    "dataset_identity": expected_dataset_identity,
                    "history_fingerprint": None,
                    "history_count": None,
                    "expected_native_ticket_count": 5,
                    "predicted_tickets": tickets,
                    "winning_numbers": {
                        "main_numbers": list(target.main_numbers),
                        "special_number": target.special_number,
                    },
                    "hit_details": evaluations,
                    "prize_results": [item["prize_tier"] for item in evaluations],
                    "combination_success": any(item["is_winner"] for item in evaluations),
                    "execution_status": "ARTIFACT_ONLY",
                    "error_reason": None,
                }
                payload["result_identity"] = identity(payload)
                payloads.append(payload)
        if len(payloads) != expected_rows:
            raise ValueError(f"research row count mismatch: {task_id}")
        for offset in range(0, len(payloads), 250):
            store.save_many(run_id, tuple(payloads[offset : offset + 250]), retry_failed=False)
        imported_by_task[task_id] = len(payloads)
    return {
        "run_id": run_id,
        "artifact_only_count": sum(imported_by_task.values()),
        "artifacts": imported_by_task,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lottery-type", choices=[lt.value for lt in LotteryType])
    parser.add_argument("--source-database", type=Path)
    parser.add_argument("--database", type=Path, help="Explicit standalone output DB; no default")
    parser.add_argument("--strategy-id", action="append", default=[])
    parser.add_argument("--all-strategies", action="store_true")
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--schema", action="store_true")
    parser.add_argument("--latest", type=int)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--all-draws", action="store_true")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--max-cells", type=int)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--import-known-artifacts", action="store_true")
    args = parser.parse_args(argv)
    if args.schema:
        print(SCHEMA_SQL.strip())
        return 0
    if not args.lottery_type:
        parser.error("--lottery-type is required")
    lottery_type = LotteryType(args.lottery_type)
    try:
        if args.import_known_artifacts:
            if (
                not args.database
                or args.strategy_id
                or args.all_strategies
                or lottery_type is not LotteryType.BIG_LOTTO
            ):
                raise ValueError(
                    "artifact import requires BIG_LOTTO, --database, and no strategy selector"
                )
            source = args.source_database or resolve_local_data_paths().database
            result = import_known_research_artifacts(args.database, source)
            print(canonical_json(result))
            return 0
        bindings, accounts = native_strategy_inventory(lottery_type)
        if args.inventory:
            print(
                canonical_json(
                    {
                        "lottery_type": lottery_type.value,
                        "executable_strategy_count": len(bindings),
                        "strategies": accounts,
                    }
                )
            )
            return 0
        if not args.database:
            raise ValueError("--database is required; formal writes require owner authorization")
        if bool(args.strategy_id) == args.all_strategies:
            raise ValueError("choose --strategy-id or --all-strategies")
        if len(set(args.strategy_id)) != len(args.strategy_id):
            raise ValueError("duplicate strategy ID")
        by_id = {b.strategy.strategy_id: b for b in bindings}
        if any(sid not in by_id for sid in args.strategy_id):
            raise ValueError("requested strategy unavailable; inspect --inventory")
        if args.all_strategies and any(a["status"] == "BLOCKED" for a in accounts.values()):
            raise ValueError("strategy binding failures; inspect --inventory before proceeding")
        selected = (
            bindings if args.all_strategies else tuple(by_id[sid] for sid in args.strategy_id)
        )
        source = args.source_database or resolve_local_data_paths().database
        validate_database_path(args.database)
        if source.resolve() == args.database.resolve():
            raise ValueError("source and output database must differ")
        selection = BackfillSelection(args.start_date, args.end_date, args.latest, args.all_draws)
        before_source_hash = source_database_hash(source)
        draws = load_draw_snapshot(source, lottery_type)
        after_source_hash = source_database_hash(source)
        if before_source_hash != after_source_hash:
            raise ValueError("source database changed while the immutable snapshot was read")
        worker = ReplayBackfill(
            adapter=build_adapter(lottery_type, selected),
            strategies=tuple(b.strategy for b in selected),
            draws=draws,
            source_identity=f"{source.resolve()}#{before_source_hash}",
            store=SQLiteBackfillStore(args.database),
            execution_version=execution_source_identity(),
            source_hash=before_source_hash,
            strategy_sources=accounts
            if args.all_strategies
            else {b.strategy.strategy_id: accounts[b.strategy.strategy_id] for b in selected},
        )
        summary = worker.execute(
            selection,
            batch_size=args.batch_size,
            max_cells=args.max_cells,
            retry_failed=args.retry_failed,
            progress=lambda value: print(
                canonical_json({k: v for k, v in value.items() if k != "manifest"}), file=sys.stderr
            ),
        )
        print(canonical_json({key: value for key, value in summary.items() if key != "manifest"}))
        return 0 if summary["status"] == "COMPLETED" else 2
    except Exception as exc:
        # Do not expose SQL, file paths, or raw adapter exceptions on a general CLI failure.
        print(
            f"replay-backfill error: {type(exc).__name__}; check inputs and --inventory",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
