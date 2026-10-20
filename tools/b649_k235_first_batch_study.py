"""Create-once offline K235 study: prepare, run, verify and seal evidence.

Use the existing Python 3.13 environment, with this checkout's src first.
prepare alone opens the explicitly authorized DB read-only. run and verify
read only the frozen JSONL input. No production registration or adoption.
"""

# ruff: noqa: E402
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import traceback
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from b649_k235_predict import (
    _resolve_seed_metadata,  # pyright: ignore[reportPrivateUsage]
)
from lottolab.research.b649_k235_shared_evaluation import (
    ASSEMBLY,
    BASELINES,
    K_VALUES,
    MODEL_CONFIGS,
    MODELS,
    STATISTICS,
    canonical,
    causal_history,
    digest,
    generator,
    native_adapters,
    observation,
    verify_records,
)
from lottolab.strategies.catalog import production_catalog

TASK = "B649_K235_SHARED_EVAL_FIRST_BATCH_R1"
BASE_HEAD = "a7bc0b8d0202bc0562f8094d7f8f75c0434b5bed"
BASE_TREE = "29c2bb2dea6f284f149a767488ad3008166488f5"
OUTPUT = Path("/Users/kelvin/VibeCoding-WorkSpace/.task-data") / TASK
REFERENCE = Path("/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis") / (
    "B649_K235_STRATEGY_EFFECTIVENESS_RESEARCH_R1"
)
DB = Path("/Users/kelvin/Library/Application Support/LottoLab/lottolab.db")
SOURCE_PATHS = (
    "src/lottolab/research/b649_k235_shared_evaluation.py",
    "tools/b649_k235_first_batch_study.py",
    "tests/unit/test_b649_k235_shared_evaluation.py",
)
Record = dict[str, Any]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_lines(path: Path) -> list[Record]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def source_identity() -> Record:
    native_adapters()  # load all native implementation dependencies before pinning
    pins: dict[str, str] = {}
    modules: dict[str, str] = {}
    for name, module in list(sys.modules.items()):
        if not (name == "b649_k235_predict" or name.startswith("lottolab")):
            continue
        filename = getattr(module, "__file__", None)
        if filename is None:
            continue
        path = Path(filename).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError(f"Import outside fixed checkout: {name}: {path}")
        relative = str(path.relative_to(ROOT))
        pins[relative] = sha(path)
        modules[name] = str(path)
    for relative in (*SOURCE_PATHS, "pyproject.toml", "uv.lock", ".python-version"):
        pins[relative] = sha(ROOT / relative)
    if git("diff", "HEAD", "--", *pins):
        raise ValueError("Uncommitted source changes")
    return {
        "head": git("rev-parse", "HEAD"),
        "tree": git("rev-parse", "HEAD^{tree}"),
        "branch": git("branch", "--show-current"),
        "worktree": str(ROOT),
        "source_sha256": pins,
        "import_origins": modules,
    }


def snapshot_database(database: Path) -> tuple[list[Record], Record]:
    """R1's exact locator/query provenance, bounded to required B649 history.

    Sidecar-free immutable read avoids creating any DB sidecar. Physical
    stability is checked only over this short snapshot acquisition, not over
    the subsequent study, which never opens live data again.
    """
    if not database.is_absolute() or not database.is_file():
        raise ValueError("Explicit existing absolute database required")

    def physical() -> Record:
        for suffix in ("-wal", "-shm", "-journal"):
            if Path(str(database) + suffix).exists():
                raise ValueError("Live SQLite sidecar: cannot use immutable snapshot")
        stat = database.stat()
        return {
            "sha256": sha(database),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "inode": stat.st_ino,
        }

    before = physical()
    sql = (
        "SELECT d.draw_number,d.draw_date,d.main_numbers_json,d.special_numbers_json,"
        "d.normalized_record_hash,d.source_name,d.source_reference,d.ingestion_run_id,"
        "r.status,r.source_sha256,r.parser_version FROM draws d "
        "LEFT JOIN ingestion_runs r ON d.ingestion_run_id=r.id "
        "WHERE d.lottery_type='BIG_LOTTO' AND CAST(d.draw_number AS INTEGER)<=115000097 "
        "ORDER BY d.draw_date,CAST(d.draw_number AS INTEGER)"
    )
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        columns = [r[1] for r in connection.execute("PRAGMA table_info(draws)")]
        rows = connection.execute(sql).fetchall()
    finally:
        connection.close()
    if before != physical():
        raise ValueError("DB changed during consistent snapshot acquisition")
    snapshot: list[Record] = []
    for draw, day, main, special, row_hash, source, ref, run_id, status, source_sha, parser in rows:
        numbers, specials = json.loads(main), json.loads(special)
        if (
            not draw
            or not draw.isascii()
            or not draw.isdigit()
            or not source
            or not ref
            or status != "SUCCESS"
            or not parser
            or len(source_sha or "") != 64
            or len(row_hash or "") != 64
            or len(numbers) != 6
            or len(set(numbers)) != 6
            or len(specials) != 1
            or specials[0] in numbers
            or any(type(v) is not int or not 1 <= v <= 49 for v in numbers + specials)
        ):
            raise ValueError(f"Invalid/unidentifiable B649 row: {draw}")
        date.fromisoformat(day)
        if snapshot and (int(snapshot[-1]["draw"]) >= int(draw) or snapshot[-1]["date"] >= day):
            raise ValueError("Nonunique/nonchronological source")
        snapshot.append(
            {
                "draw": draw,
                "date": day,
                "numbers": sorted(numbers),
                "special": specials[0],
                "normalized_record_hash": row_hash,
                "source_name": source,
                "source_reference": ref,
                "ingestion_run_id": run_id,
                "source_sha256": source_sha,
                "parser_version": parser,
            }
        )
    return snapshot, {
        "locator": str(database),
        "physical_identity": before,
        "sql": sql,
        "read_mode": "mode=ro&immutable=1; query_only; BEGIN; absent sidecars",
        "draw_columns": columns,
        "timestamp_semantics": "created_at/updated_at are current import metadata, "
        "not original official publication/availability; no historical revision archive",
        "ordered_query_rows_hash": digest(rows),
        "historical_as_of": "UNPROVEN; current imported revisions; "
        "strict previous date and period only",
    }


def prepare(output: Path, database: Path) -> Record:
    if (output / "study_spec.json").exists() or (output / "input_snapshot.jsonl").exists():
        raise FileExistsError("Create-once frozen input already exists")
    protocol_path = (
        REFERENCE / ".task-data/B649_K235_STRATEGY_EFFECTIVENESS_RESEARCH_R1/protocol.json"
    )
    results_path = protocol_path.with_name("results.json")
    protocol, results = read_json(protocol_path), read_json(results_path)
    if Path(protocol["data"]["locator"]) != database:
        raise ValueError("R1 source locator mismatch")
    selected = {k: results["results"][f"K{k}"]["strategy_id"] for k in K_VALUES}
    if selected != BASELINES:
        raise ValueError("R1 frozen selected identities mismatch")
    source = source_identity()
    if git("rev-parse", f"{BASE_HEAD}^{{tree}}") != BASE_TREE:
        raise ValueError("Specified base tree mismatch")
    if set(git("diff", "--name-only", BASE_HEAD, "HEAD").splitlines()) != set(SOURCE_PATHS):
        raise ValueError("Candidate changed paths differ from authorized three files")
    snapshot, data = snapshot_database(database)
    targets = protocol["splits"]["test"]
    if not targets or targets[0]["draw"] != "112000014" or targets[-1]["draw"] != "115000097":
        raise ValueError("R1 period mismatch")
    target_ids = {t["draw"] for t in targets}
    observed_ids = {r["draw"] for r in snapshot if int(r["draw"]) >= 112000014}
    if observed_ids - target_ids:
        raise ValueError("Unexpected target IDs inside fixed period")
    observed_dates = {r["draw"]: r["date"] for r in snapshot}
    if any(t["draw"] in observed_dates and observed_dates[t["draw"]] != t["date"] for t in targets):
        raise ValueError("Target dates changed relative to the fixed R1 period")
    output.mkdir(parents=True, mode=0o700, exist_ok=True)
    with (output / "input_snapshot.jsonl").open("x") as stream:
        for row in snapshot:
            stream.write(canonical(row) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    spec: Record = {
        "task_id": TASK,
        "created_at": datetime.now(UTC).isoformat(),
        "base_head": BASE_HEAD,
        "base_tree": BASE_TREE,
        "source": source,
        "models": MODEL_CONFIGS,
        "assembly": ASSEMBLY,
        "K_values": K_VALUES,
        "statistics": STATISTICS,
        "targets": targets,
        "target_n": len(targets),
        "observed_target_n": len(observed_ids),
        "history_row_n": len(snapshot),
        "missing_target_ids": sorted(target_ids - observed_ids),
        "input_snapshot_hash": sha(output / "input_snapshot.jsonl"),
        "data": data,
        "event": "B649 official any general prize in at least one of K tickets; "
        "promotional prizes excluded",
        "budget": "K tickets per target; K compared separately",
        "M0_selection": {
            "rule": protocol["selection_rule"],
            "frozen_ids": selected,
            "train_validation_test": {
                k: {"n": len(v), "first": v[0], "last": v[-1]}
                for k, v in protocol["splits"].items()
            },
            "split_rule": protocol["split_rule"],
            "training": protocol["training"],
            "original_R1_verdict": "BLOCKED_UNVERIFIABLE",
            "original_execution_identity_restored": False,
        },
        "references": [
            {"path": str(p), "sha256": sha(p), "use": use}
            for p, use in (
                (protocol_path, "source, splits and selection contract"),
                (results_path, "frozen selected identities; counts compared AFTER run"),
                (
                    REFERENCE / "tools/b649_k235_effectiveness_study.py",
                    "read-only causal adapter and binomial-inversion reference",
                ),
                (
                    REFERENCE / "tests/unit/test_b649_k235_effectiveness_study.py",
                    "read-only test reference",
                ),
            )
        ],
        "environment": {
            "python": sys.version,
            "executable": sys.executable,
            "stdlib_only": True,
            "thread_limits": {
                k: os.environ.get(k)
                for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
            },
        },
        "commands": {
            "prepare": sys.argv,
            "run": [sys.executable, str(Path(__file__)), "run"],
            "verify": [sys.executable, str(Path(__file__)), "verify"],
        },
        "evidence": {
            "focused_tests": "focused-tests.json",
            "ruff": "ruff.json",
            "pyright": "pyright.json",
            "judge": "judge.json",
            "run": "run.json",
            "verify": "verify.json",
        },
        "EVIDENCE_CLASS": "RETROSPECTIVE_EXPLORATORY",
        "TEST_PERIOD_PREVIOUSLY_EXPOSED": True,
        "ADOPTION_STATUS": "NO_ADOPT",
        "PRODUCTION_CHANGE": "NONE",
        "write_ledger": {
            "source": list(SOURCE_PATHS),
            "retained_worktree": str(ROOT),
            "retained_output": str(output),
            "deleted": [],
            "other_scopes": "No R1, main, shared Skill, lockfile or DB writes",
        },
    }
    write_json(output / "study_spec.json", spec)
    return {
        "prepared": True,
        "target_n": len(targets),
        "history_row_n": len(snapshot),
        "input_snapshot_hash": spec["input_snapshot_hash"],
        "source": source["head"],
    }


def frozen_inputs(output: Path) -> tuple[Record, list[Record]]:
    spec = read_json(output / "study_spec.json")
    if (
        spec["source"] != source_identity()
        or spec["input_snapshot_hash"] != sha(output / "input_snapshot.jsonl")
        or canonical(spec["models"]) != canonical(MODEL_CONFIGS)
        or spec["statistics"] != STATISTICS
        or spec["assembly"] != ASSEMBLY
    ):
        raise ValueError("Frozen source/input/config changed")
    return spec, read_lines(output / "input_snapshot.jsonl")


def run(output: Path) -> Record:
    spec, snapshot = frozen_inputs(output)
    spec_hash = sha(output / "study_spec.json")
    write_json(
        output / "run_started.json",
        {
            "at": datetime.now(UTC).isoformat(),
            "command": sys.argv,
            "spec_hash": spec_hash,
            "generation_attempt": 1,
        },
    )
    generate = generator(native_adapters())
    catalog = production_catalog()
    with (output / "per_draw.jsonl").open("x") as stream:
        for index, target in enumerate(spec["targets"]):
            for model in MODELS:
                for k in K_VALUES:
                    row = observation(
                        snapshot, target, model, k, spec["input_snapshot_hash"], generate
                    )
                    if model == "M0":
                        row["native_seed_metadata"] = _resolve_seed_metadata(
                            catalog.get(BASELINES[k]), causal_history(snapshot, target)
                        )
                    stream.write(canonical(row) + "\n")
                    stream.flush()
            os.fsync(stream.fileno())
            if index % 25 == 0 or index + 1 == len(spec["targets"]):
                print(f"generated {index + 1}/{len(spec['targets'])} targets", flush=True)
    if spec_hash != sha(output / "study_spec.json"):
        raise ValueError("Spec changed during execution")
    frozen_inputs(output)
    write_json(
        output / "run_completed.json",
        {
            "at": datetime.now(UTC).isoformat(),
            "per_draw_hash": sha(output / "per_draw.jsonl"),
            "spec_hash": spec_hash,
        },
    )
    return verify(output, "summary.json")


def verify(output: Path, filename: str = "verification.json") -> Record:
    spec, snapshot = frozen_inputs(output)
    rows = read_lines(output / "per_draw.jsonl")
    summary = verify_records(snapshot, spec["targets"], rows, spec["input_snapshot_hash"])
    completed = read_json(output / "run_completed.json")
    if completed["per_draw_hash"] != sha(output / "per_draw.jsonl") or completed[
        "spec_hash"
    ] != sha(output / "study_spec.json"):
        raise ValueError("Completed-run artifact identity changed")
    summary.update(
        {
            "task_id": TASK,
            "source": spec["source"],
            "input_snapshot_hash": spec["input_snapshot_hash"],
            "per_draw_hash": sha(output / "per_draw.jsonl"),
            "study_spec_hash": sha(output / "study_spec.json"),
            "IMPLEMENTATION_STATUS": "PARTIAL",
            "independent_acceptance": "PENDING",
            "evidence": spec["evidence"],
            "generation_attempts": 1,
            "verification_kind": "ticket-only recomputation; causal implementation needs review",
        }
    )
    if filename == "verification.json":
        original = read_json(output / "summary.json")
        for field in ("metrics", "comparisons", "RESEARCH_RESULT", "record_n"):
            if summary[field] != original[field]:
                raise ValueError(f"Recomputed summary mismatch: {field}")
    # Only now compare historical Worker counts, with exact scope explicitly checked.
    r1 = read_json(
        REFERENCE / ".task-data/B649_K235_STRATEGY_EFFECTIVENESS_RESEARCH_R1/results.json"
    )
    summary["R1_scope_comparison"] = {
        "same_target_ids": spec["targets"]
        == read_json(
            REFERENCE / (".task-data/B649_K235_STRATEGY_EFFECTIVENESS_RESEARCH_R1/protocol.json")
        )["splits"]["test"],
        "counts": {
            f"K{k}": {
                "R1_worker_report": r1["results"][f"K{k}"]["success_n"],
                "new_M0": summary["metrics"][f"M0_K{k}"]["success_n"],
                "new_denominator": summary["metrics"][f"M0_K{k}"]["known_outcome_n"],
            }
            for k in K_VALUES
        },
        "boundary": "Agreement cannot verify the missing original R1 execution; "
        "R1 BLOCKED_UNVERIFIABLE retained",
    }
    write_json(output / filename, summary)
    return {
        "record_n": summary["record_n"],
        "RESEARCH_RESULT": summary["RESEARCH_RESULT"],
        "written": filename,
        "generation_replayed": False,
    }


def seal(output: Path) -> Record:
    frozen_inputs(output)
    summary = read_json(output / "summary.json")
    verification = read_json(output / "verification.json")
    judge = read_json(output / "judge.json")
    for name in ("focused-tests", "ruff", "pyright", "run", "verify"):
        evidence = read_json(output / f"{name}.json")
        if evidence["exit_code"] != 0:
            raise ValueError(f"Required evidence failed: {name}")
    if (
        judge["verdict"] not in {"VERIFIED", "VERIFIED_WITH_CAVEATS"}
        or judge["source_head"] != summary["source"]["head"]
        or judge["source_tree"] != summary["source"]["tree"]
        or judge["mode"] != "FRESH_CONTEXT"
        or verification["per_draw_hash"] != summary["per_draw_hash"]
    ):
        raise ValueError("Independent acceptance incomplete or wrong identity")
    summary.update(
        {
            "IMPLEMENTATION_STATUS": "COMPLETE",
            "independent_acceptance": judge,
            "evidence_hashes": {
                p.name: sha(p) for p in output.glob("*.json") if p.name != "summary.json"
            },
        }
    )
    # Preserve initial summary bytes before adding final acceptance references.
    write_json(output / "summary_before_acceptance.json", read_json(output / "summary.json"))
    temporary = output / "summary.finalizing.json"
    write_json(temporary, summary)
    temporary.replace(output / "summary.json")
    return {"IMPLEMENTATION_STATUS": "COMPLETE", "RESEARCH_RESULT": summary["RESEARCH_RESULT"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "verify", "seal"))
    parser.add_argument("--output-directory", type=Path, default=OUTPUT)
    parser.add_argument("--database", type=Path, default=DB)
    args = parser.parse_args()
    if args.output_directory.resolve() != OUTPUT:
        parser.error("Use exact task-owned output root")
    try:
        result = (
            prepare(args.output_directory, args.database)
            if args.action == "prepare"
            else run(args.output_directory)
            if args.action == "run"
            else verify(args.output_directory)
            if args.action == "verify"
            else seal(args.output_directory)
        )
        print(canonical(result), flush=True)
        return 0
    except Exception:
        if args.output_directory.is_dir():
            failure = (
                args.output_directory
                / f"failure-{args.action}-{datetime.now(UTC).strftime('%H%M%S%f')}.json"
            )
            write_json(
                failure,
                {
                    "at": datetime.now(UTC).isoformat(),
                    "action": args.action,
                    "traceback": traceback.format_exc(),
                    "command": sys.argv,
                },
            )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
