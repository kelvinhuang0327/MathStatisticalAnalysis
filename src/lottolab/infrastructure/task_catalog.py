"""Read-only derivation of task catalog, stage manifests, and tombstones."""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import lottolab
from lottolab.infrastructure.persistence.project_database_paths import canonical_project_root

BASELINE_WINDOW_START = "2026-11-18"
BASELINE_WINDOW_END = "2026-11-24"

REPORT_STRATA: tuple[str, ...] = ("S1", "S2", "S3", "S4", "S5", "S6")

STRATUM_LABELS: dict[str, str] = {
    "S1": "FAST",
    "S2": "STANDARD/NORMAL",
    "S3": "STANDARD/ENHANCED",
    "S4": "JUDGED",
    "S5": "RESEARCH",
    "S6": "RELEASE_CLOSEOUT",
}

TEN_INDICATORS: tuple[str, ...] = (
    "FIRST_PASS_ACCEPTANCE_RATE",
    "FINAL_GOAL_COMPLETION_RATE",
    "AVOIDABLE_BLOCK_RATE",
    "UNPRODUCTIVE_CONTINUATION_COUNT",
    "OWNER_INTERVENTION_COUNT",
    "DISPATCH_TO_ACCEPTANCE_TIME",
    "ACCEPTANCE_TO_ADOPTION_TIME",
    "MODEL_COST_PER_ACCEPTED_OUTCOME",
    "REGRESSION_ESCAPE_RATE",
    "RESOURCE_COST",
)

HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")
EXCLUDED_STATUSES = frozenset({"RETAINED", "KEPT", "HELD", "PRESERVED"})
MAX_JSON_SIZE_BYTES = 20 * 1024 * 1024  # 20 MiB


def _is_hex64(val: object) -> bool:
    return isinstance(val, str) and bool(HEX_64_RE.match(val.lower()))


def _is_int(val: object) -> bool:
    return type(val) is int


def _nonnegative_int(val: object) -> bool:
    return _is_int(val) and cast(int, val) >= 0


def _nonnegative_number(val: object) -> bool:
    return type(val) in (int, float) and math.isfinite(cast(float, val)) and cast(float, val) >= 0


def _has_explicit_route(task: dict[str, object]) -> bool:
    route_raw = task.get("route")
    route = cast(dict[str, object], route_raw) if isinstance(route_raw, dict) else {}
    worker_route = _clean_header_val(route.get("worker_route", task.get("worker_route")))
    depth = _clean_header_val(route.get("implementation_depth", task.get("implementation_depth")))
    judge_mode = _clean_header_val(route.get("judge_mode", task.get("judge_mode")))
    task_class = _clean_header_val(route.get("task_class", task.get("task_class")))
    lane = _clean_header_val(route.get("task_lane", task.get("task_lane")))
    has_stages = isinstance(task.get("stage_manifests"), list) and bool(
        cast(list[object], task["stage_manifests"])
    )

    if worker_route == "FAST":
        return True
    if "JUDGED" in worker_route or "JUDGE" in worker_route or judge_mode == "FRESH_CONTEXT":
        return True
    if "STANDARD" in worker_route:
        return depth in ("NORMAL", "ENHANCED")
    if (
        "RESEARCH" in task_class
        or has_stages
        or any(item in lane for item in ("L1", "L2", "L3", "支線1", "支線2", "支線3"))
    ):
        return True
    return "RELEASE" in task_class or "CLOSEOUT" in task_class


def _parse_date(value: object) -> str | None:
    """Return a validated calendar date in YYYYMMDD form; never parse timestamps."""
    if not isinstance(value, str):
        return None
    raw = value.strip()
    fmt = "%Y%m%d" if re.fullmatch(r"\d{8}", raw) else "%Y-%m-%d"
    try:
        return datetime.strptime(raw, fmt).strftime("%Y%m%d")
    except ValueError:
        return None


def _json_signature(value: object) -> str:
    """Canonicalize JSON-compatible task evidence for exact duplicate detection."""
    normalized = json.loads(json.dumps(value, ensure_ascii=False))
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _deduplicate_task_records(
    tasks: list[dict[str, object]],
) -> tuple[list[dict[str, object]], int, int]:
    """Collapse byte-equivalent task receipts by ID and mark conflicting IDs unknown."""
    output: list[dict[str, object]] = []
    by_id: dict[str, dict[str, object]] = {}
    signatures: dict[str, str] = {}
    conflicted: set[str] = set()
    duplicates = 0

    for raw_task in tasks:
        task = dict(raw_task)
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            task["metric_evidence_conflict"] = True
            output.append(task)
            continue
        try:
            signature = _json_signature(task)
        except (TypeError, ValueError):
            task["metric_evidence_conflict"] = True
            output.append(task)
            continue

        existing = by_id.get(task_id)
        if existing is None:
            by_id[task_id] = task
            signatures[task_id] = signature
            output.append(task)
        elif signatures[task_id] == signature:
            duplicates += 1
        elif task_id not in conflicted:
            existing["metric_evidence_conflict"] = True
            existing["task_lifecycle_state"] = None
            for field in (
                "first_pass_accepted",
                "goal_72h_completed",
                "acceptance_confirmed",
                "regression_escape",
                "avoidable_block",
                "tokens",
                "model_identity",
                "model_tier",
                "adopted_outcome",
                "unproductive_continuation_count",
                "owner_intervention_count",
                "dispatch_to_acceptance_seconds",
                "acceptance_to_adoption_seconds",
                "resource_cost_measured",
            ):
                existing.pop(field, None)
            conflicted.add(task_id)

    return output, duplicates, len(conflicted)


def _read_head_str(path: Path, max_bytes: int = 65536) -> str | None:
    try:
        with open(path, "rb") as f:
            chunk = f.read(max_bytes)
        return chunk.decode("utf-8", errors="replace")
    except OSError:
        return None


@dataclass(frozen=True)
class TaskFolderInfo:
    task_id: str
    root: str
    path: str
    date_folder: str | None


def find_task_folders(roots: list[Path]) -> list[TaskFolderInfo]:
    """Find candidate task folders directly under root or root/<8-digits>."""
    results: list[TaskFolderInfo] = []
    for root in roots:
        try:
            if not root.is_dir() or root.is_symlink():
                continue
            root_abs = str(root.resolve())
            for child in sorted(root.iterdir(), key=lambda p: p.name):
                if child.is_symlink() or not child.is_dir():
                    continue
                cname = child.name
                if len(cname) == 8 and cname.isdigit():
                    # Date folder: candidates are child/<name>
                    for task_dir in sorted(child.iterdir(), key=lambda p: p.name):
                        if task_dir.is_symlink() or not task_dir.is_dir():
                            continue
                        has_res = (task_dir / "result.json").is_file() and not (
                            task_dir / "result.json"
                        ).is_symlink()
                        has_pkt = (task_dir / "packet.md").is_file() and not (
                            task_dir / "packet.md"
                        ).is_symlink()
                        if has_res or has_pkt:
                            results.append(
                                TaskFolderInfo(
                                    task_id=task_dir.name,
                                    root=root_abs,
                                    path=str(task_dir.resolve()),
                                    date_folder=cname,
                                )
                            )
                elif not cname.startswith("_") and not cname.startswith("."):
                    # Non-date candidate directly under root
                    has_res = (child / "result.json").is_file() and not (
                        child / "result.json"
                    ).is_symlink()
                    has_pkt = (child / "packet.md").is_file() and not (
                        child / "packet.md"
                    ).is_symlink()
                    if has_res or has_pkt:
                        results.append(
                            TaskFolderInfo(
                                task_id=child.name,
                                root=root_abs,
                                path=str(child.resolve()),
                                date_folder=None,
                            )
                        )
        except OSError:
            continue
    return results


def determine_project(folder_path: Path, msa_root: Path) -> str:
    """Determine whether task folder belongs to MSA, OTHER, or UNKNOWN."""
    try:
        f_resolved = folder_path.resolve()
        msa_resolved = msa_root.resolve()
        if f_resolved == msa_resolved or msa_resolved in f_resolved.parents:
            return "MSA"
    except OSError:
        pass

    pkt_text = _read_head_str(folder_path / "packet.md", 65536)
    res_text = _read_head_str(folder_path / "result.json", 65536)

    if (pkt_text is not None and "MathStatisticalAnalysis" in pkt_text) or (
        res_text is not None and "MathStatisticalAnalysis" in res_text
    ):
        return "MSA"

    if pkt_text is not None and res_text is not None:
        return "OTHER"

    if pkt_text is None and res_text is None:
        return "UNKNOWN"

    return "UNKNOWN"


def _extract_run_ids_from_dict(obj: object) -> set[str]:
    found: set[str] = set()

    def _recurse(curr: object) -> None:
        if isinstance(curr, dict):
            curr_dict = cast(dict[str, object], curr)
            for k, v in curr_dict.items():
                if k in ("run_id", "formal_run_id"):
                    if isinstance(v, str) and _is_hex64(v):
                        found.add(v.lower())
                elif k == "run_ids":
                    if isinstance(v, list):
                        v_list = cast(list[object], v)
                        for item in v_list:
                            if isinstance(item, str) and _is_hex64(item):
                                found.add(item.lower())
                    elif isinstance(v, str) and _is_hex64(v):
                        found.add(v.lower())
                _recurse(cast(object, v))
        elif isinstance(curr, list):
            curr_list = cast(list[object], curr)
            for item in curr_list:
                _recurse(item)

    _recurse(obj)
    return found


@dataclass(frozen=True)
class StageEntry:
    manifest_path: str
    task_id: str | None
    db_path: str | None
    db_exists: bool
    db_sha256_recorded: str | None
    created_at: str | None
    run_ids: list[str]
    strategies: list[dict[str, object]]
    lottery_types: object
    formal_run_ids_present: int | None
    fact_state: str


def find_stage_manifests(scratch_dir: Path) -> list[Path]:
    """Find MERGE_PENDING.json files with relative depth <= 5 under scratch_dir."""
    manifests: list[Path] = []
    if not scratch_dir.is_dir():
        return manifests

    def _walk(curr: Path, depth: int) -> None:
        if depth > 5:
            return
        try:
            for entry in curr.iterdir():
                if entry.is_symlink():
                    continue
                if entry.is_file() and entry.name == "MERGE_PENDING.json":
                    manifests.append(entry.resolve())
                elif entry.is_dir():
                    _walk(entry, depth + 1)
        except OSError:
            pass

    _walk(scratch_dir, 1)
    return sorted(manifests, key=lambda p: str(p))


def parse_stage_manifest(
    manifest_path: Path,
    formal_run_ids: set[str] | None,
) -> StageEntry:
    manifest_path_abs = str(manifest_path.resolve())
    try:
        with open(manifest_path, encoding="utf-8") as f:
            data: object = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("not a dict")
        data_dict = cast(dict[str, object], data)
    except Exception:
        return StageEntry(
            manifest_path=manifest_path_abs,
            task_id=None,
            db_path=None,
            db_exists=False,
            db_sha256_recorded=None,
            created_at=None,
            run_ids=[],
            strategies=[],
            lottery_types=None,
            formal_run_ids_present=None,
            fact_state="UNKNOWN",
        )

    task_id_raw = data_dict.get("task_id")
    task_id = task_id_raw if isinstance(task_id_raw, str) else None

    db_path_raw = data_dict.get("db_path")
    db_path = db_path_raw if isinstance(db_path_raw, str) else None
    db_exists = False
    if db_path is not None:
        target_p = Path(db_path) if os.path.isabs(db_path) else manifest_path.parent / db_path
        db_exists = os.path.lexists(target_p)

    db_sha256 = data_dict.get("db_sha256") or data_dict.get("db_sha256_recorded")
    db_sha256_recorded = str(db_sha256) if _is_hex64(db_sha256) else None

    created_at_raw = data_dict.get("created_at")
    created_at = created_at_raw if isinstance(created_at_raw, str) else None

    raw_run_ids = data_dict.get("run_ids")
    run_ids: list[str] = []
    if isinstance(raw_run_ids, list):
        for r in cast(list[object], raw_run_ids):
            if isinstance(r, str):
                run_ids.append(r)

    raw_strategies = data_dict.get("strategies")
    strategies: list[dict[str, object]] = []
    if isinstance(raw_strategies, list):
        for s in cast(list[object], raw_strategies):
            if isinstance(s, dict):
                s_dict = cast(dict[str, object], s)
                strategies.append(
                    {
                        "strategy_id": s_dict.get("strategy_id"),
                        "strategy_version": s_dict.get("strategy_version"),
                    }
                )

    lottery_types = data_dict.get("lottery_types")

    formal_run_ids_present: int | None = None
    if formal_run_ids is not None:
        formal_run_ids_present = sum(1 for r in run_ids if r in formal_run_ids)

    # fact_state calculation:
    # - MERGED_STAGE_PRESENT: run_ids all in formal db, and DB exists
    # - MERGED_DB_MISSING: run_ids all in formal db, DB does not exist
    # - MERGE_PENDING: run_ids not all in formal db
    # - UNKNOWN: no run_ids, formal db not looked up, or invalid JSON
    if formal_run_ids is None or not run_ids:
        fact_state = "UNKNOWN"
    elif all(r in formal_run_ids for r in run_ids):
        fact_state = "MERGED_STAGE_PRESENT" if db_exists else "MERGED_DB_MISSING"
    else:
        fact_state = "MERGE_PENDING"

    return StageEntry(
        manifest_path=manifest_path_abs,
        task_id=task_id,
        db_path=db_path,
        db_exists=db_exists,
        db_sha256_recorded=db_sha256_recorded,
        created_at=created_at,
        run_ids=run_ids,
        strategies=strategies,
        lottery_types=lottery_types,
        formal_run_ids_present=formal_run_ids_present,
        fact_state=fact_state,
    )


@dataclass(frozen=True)
class RawTombstone:
    path: str
    sha256: str | None
    bytes: int | None
    deleted_at: str | None
    deleted_at_source: str
    status_recorded: str | None
    source_file: str
    json_pointer: str
    task_id: str | None


def extract_tombstones_from_json(
    file_path: Path,
    task_id: str | None,
    max_size_bytes: int = MAX_JSON_SIZE_BYTES,
) -> tuple[list[RawTombstone], list[dict[str, object]], str | None]:
    """Parse a single JSON file for tombstones and path-exists claims."""
    tombstones: list[RawTombstone] = []
    path_exists_claims: list[dict[str, object]] = []

    try:
        st = file_path.stat()
        if st.st_size > max_size_bytes:
            return [], [], "TOO_LARGE"
    except OSError as exc:
        return [], [], f"STAT_ERROR: {exc}"

    try:
        with open(file_path, encoding="utf-8") as f:
            root_data: object = json.load(f)
    except Exception as exc:
        return [], [], f"PARSE_ERROR: {exc}"

    file_abs = str(file_path.resolve())
    doc_task_id = task_id
    if isinstance(root_data, dict):
        tid = cast(dict[str, object], root_data).get("task_id")
        if isinstance(tid, str):
            doc_task_id = tid

    def _traverse(
        node: object,
        ancestor_dicts: list[dict[str, object]],
        ancestor_keys: list[str],
        current_pointer: str,
    ) -> None:
        if isinstance(node, dict):
            node_dict = cast(dict[str, object], node)
            status_val = node_dict.get("status")
            status_str = str(status_val).upper() if status_val is not None else None
            is_excluded_status = bool(status_str and status_str in EXCLUDED_STATUSES)

            # Determine if this dict O is considered deleted
            has_deleted_at_key = "deleted_at" in node_dict and node_dict["deleted_at"] is not None
            is_status_deleted = bool(status_str and status_str == "DELETED")
            has_delet_ancestor = any("delet" in k.lower() for k in ancestor_keys)

            is_deleted = (
                has_deleted_at_key or is_status_deleted or has_delet_ancestor
            ) and not is_excluded_status

            # Determine deleted_at and deleted_at_source for node O
            node_deleted_at: str | None = None
            node_deleted_at_source = "NONE"
            if node_dict.get("deleted_at") is not None:
                node_deleted_at = str(node_dict["deleted_at"])
                node_deleted_at_source = "RECORD"
            elif node_dict.get("at") is not None:
                node_deleted_at = str(node_dict["at"])
                node_deleted_at_source = "RECORD"
            else:
                for anc in reversed(ancestor_dicts):
                    if anc.get("deleted_at") is not None:
                        node_deleted_at = str(anc["deleted_at"])
                        node_deleted_at_source = "ANCESTOR"
                        break
                    if anc.get("at") is not None:
                        node_deleted_at = str(anc["at"])
                        node_deleted_at_source = "ANCESTOR"
                        break

            # Check filename list format:
            # If any ancestor key contains "delet", and node has "files" as list of strings
            files_list = node_dict.get("files")
            if (
                is_deleted
                and isinstance(files_list, list)
                and files_list
                and all(isinstance(f, str) for f in cast(list[object], files_list))
            ):
                typed_files = cast(list[str], files_list)
                file_deleted_at: str | None = None
                file_deleted_at_source = "NONE"
                if node_dict.get("at") is not None:
                    file_deleted_at = str(node_dict["at"])
                    file_deleted_at_source = "ANCESTOR"
                elif node_dict.get("deleted_at") is not None:
                    file_deleted_at = str(node_dict["deleted_at"])
                    file_deleted_at_source = "ANCESTOR"
                else:
                    file_deleted_at = node_deleted_at
                    file_deleted_at_source = node_deleted_at_source

                for f_idx, filename in enumerate(typed_files):
                    target_path = str((file_path.parent / filename).resolve())
                    sub_pointer = (
                        f"{current_pointer}/files/{f_idx}" if current_pointer else f"/files/{f_idx}"
                    )
                    claim_record: dict[str, object] = {
                        "path": target_path,
                        "source": {
                            "file": file_abs,
                            "json_pointer": sub_pointer,
                            "task_id": doc_task_id,
                        },
                    }
                    if os.path.lexists(target_path):
                        path_exists_claims.append(claim_record)
                    else:
                        tombstones.append(
                            RawTombstone(
                                path=target_path,
                                sha256=None,
                                bytes=None,
                                deleted_at=file_deleted_at,
                                deleted_at_source=file_deleted_at_source,
                                status_recorded=status_val if isinstance(status_val, str) else None,
                                source_file=file_abs,
                                json_pointer=sub_pointer,
                                task_id=doc_task_id,
                            )
                        )

            # Check standard path keys in node O
            if is_deleted:
                for k, v in node_dict.items():
                    if (
                        (k == "path" or k.endswith("_path"))
                        and isinstance(v, str)
                        and v.startswith("/")
                    ):
                        target_path = str(Path(v))
                        # Derive prefix X
                        prefix_x = "" if k == "path" else k[:-5]
                        # Derive sha256
                        raw_sha = (
                            node_dict.get("sha256")
                            if prefix_x == ""
                            else node_dict.get(f"{prefix_x}_sha256")
                        )
                        sha_val = str(raw_sha).lower() if _is_hex64(raw_sha) else None
                        # Derive bytes
                        bytes_keys = (
                            ["size_bytes", "bytes"]
                            if prefix_x == ""
                            else [f"{prefix_x}_size_bytes", f"{prefix_x}_bytes"]
                        )
                        bytes_val: int | None = None
                        for bk in bytes_keys:
                            bv = node_dict.get(bk)
                            if _is_int(bv):
                                bytes_val = cast(int, bv)
                                break

                        claim_record: dict[str, object] = {
                            "path": target_path,
                            "source": {
                                "file": file_abs,
                                "json_pointer": current_pointer or "/",
                                "task_id": doc_task_id,
                            },
                        }
                        if os.path.lexists(target_path):
                            path_exists_claims.append(claim_record)
                        else:
                            tombstones.append(
                                RawTombstone(
                                    path=target_path,
                                    sha256=sha_val,
                                    bytes=bytes_val,
                                    deleted_at=node_deleted_at,
                                    deleted_at_source=node_deleted_at_source,
                                    status_recorded=status_val
                                    if isinstance(status_val, str)
                                    else None,
                                    source_file=file_abs,
                                    json_pointer=current_pointer or "/",
                                    task_id=doc_task_id,
                                )
                            )

            # Recurse into child values
            next_ancestor_dicts = [*ancestor_dicts, node_dict]
            for k, v in node_dict.items():
                escaped_k = str(k).replace("~", "~0").replace("/", "~1")
                sub_ptr = f"{current_pointer}/{escaped_k}"
                _traverse(v, next_ancestor_dicts, [*ancestor_keys, str(k)], sub_ptr)

        elif isinstance(node, list):
            node_list = cast(list[object], node)
            for idx, item in enumerate(node_list):
                sub_ptr = f"{current_pointer}/{idx}"
                _traverse(item, ancestor_dicts, ancestor_keys, sub_ptr)

    _traverse(cast(object, root_data), [], [], "")
    return tombstones, path_exists_claims, None


@dataclass
class TombstoneRecord:
    bytes: int | None
    deleted_at: str | None
    deleted_at_source: str
    path: str
    sha256: str | None
    sources: list[dict[str, str | None]]
    status_recorded: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "bytes": self.bytes,
            "deleted_at": self.deleted_at,
            "deleted_at_source": self.deleted_at_source,
            "path": self.path,
            "sha256": self.sha256,
            "sources": self.sources,
            "status_recorded": self.status_recorded,
        }


@dataclass(frozen=True)
class BuildResult:
    tasks_count: int
    stages_count: int
    tombstones_count: int
    output_dir: Path
    skipped: list[dict[str, str]]
    deletion_claims_path_exists: dict[str, object]
    formal_db_info: dict[str, str]


def query_formal_run_ids(
    formal_db_path: Path,
    write_lease_path: Path | None = None,
    no_formal_lookup: bool = False,
) -> tuple[set[str] | None, dict[str, str]]:
    """Query run_ids from formal replay-backfill database."""
    formal_db_abs = str(formal_db_path.resolve())
    if no_formal_lookup:
        return None, {"path": formal_db_abs, "lookup": "SKIPPED_FLAG"}

    lease_file = write_lease_path or (
        formal_db_path.parent / "locks" / f"{formal_db_path.name}.lease.json"
    )
    if lease_file.is_file():
        return None, {"path": formal_db_abs, "lookup": "SKIPPED_WRITE_LEASE"}

    if not formal_db_path.is_file():
        return None, {"path": formal_db_abs, "lookup": "MISSING"}

    try:
        conn = sqlite3.connect(f"file:{formal_db_path.resolve()}?mode=ro", uri=True)
        try:
            conn.execute("BEGIN")
            cursor = conn.execute("SELECT run_id FROM replay_backfill_runs")
            run_ids: set[str] = {str(row[0]) for row in cursor.fetchall() if row[0]}
            conn.rollback()
        finally:
            conn.close()
        return run_ids, {"path": formal_db_abs, "lookup": "DONE"}
    except Exception as exc:
        return None, {"path": formal_db_abs, "lookup": f"ERROR: {exc}"}


def build_catalog(
    roots: list[Path],
    output_dir: Path,
    formal_db_path: Path,
    write_lease_path: Path | None = None,
    no_formal_lookup: bool = False,
    quarantine_manifest_paths: list[Path] | None = None,
    max_json_size_bytes: int = MAX_JSON_SIZE_BYTES,
) -> BuildResult:
    """Build tasks.jsonl, stages.jsonl, tombstones.jsonl, and catalog_meta.json."""
    output_dir.mkdir(parents=True, exist_ok=True)
    msa_root = canonical_project_root()
    skipped: list[dict[str, str]] = []
    total_path_exists_claims = 0
    path_exists_samples: list[dict[str, object]] = []

    # 1. Formal DB query
    formal_run_ids, formal_db_info = query_formal_run_ids(
        formal_db_path=formal_db_path,
        write_lease_path=write_lease_path,
        no_formal_lookup=no_formal_lookup,
    )

    # 2. Find stages
    scratch_dir = msa_root / ".task-data" / "_scratch"
    stage_manifest_paths = find_stage_manifests(scratch_dir)
    stage_entries = [parse_stage_manifest(sm, formal_run_ids) for sm in stage_manifest_paths]
    # Map task_id -> list of manifest_path
    task_to_stages: dict[str, list[str]] = {}
    for stg in stage_entries:
        if stg.task_id:
            task_to_stages.setdefault(stg.task_id, []).append(stg.manifest_path)
    for k in task_to_stages:
        task_to_stages[k].sort()

    # 3. Find task folders
    task_folders = find_task_folders(roots)

    # 4. Collect tombstones
    raw_tombstones: list[RawTombstone] = []

    # From each task folder: first level *.json
    for tf in task_folders:
        folder_p = Path(tf.path)
        try:
            for jf in sorted(folder_p.glob("*.json"), key=lambda p: p.name):
                if jf.is_symlink() or not jf.is_file():
                    continue
                extracted, claims, skip_reason = extract_tombstones_from_json(
                    jf, tf.task_id, max_size_bytes=max_json_size_bytes
                )
                if skip_reason:
                    skipped.append({"path": str(jf.resolve()), "reason": skip_reason})
                else:
                    raw_tombstones.extend(extracted)
                    total_path_exists_claims += len(claims)
                    if len(path_exists_samples) < 50:
                        path_exists_samples.extend(claims[: 50 - len(path_exists_samples)])
        except OSError:
            pass

    # From quarantine manifests
    if quarantine_manifest_paths is None:
        q_root = msa_root / "data" / "databases" / "backups"
        quarantine_manifest_paths = sorted(q_root.glob("_quarantine_*/QUARANTINE_MANIFEST.json"))

    for qm in quarantine_manifest_paths:
        if qm.is_file() and not qm.is_symlink():
            extracted, claims, skip_reason = extract_tombstones_from_json(
                qm, None, max_size_bytes=max_json_size_bytes
            )
            if skip_reason:
                skipped.append({"path": str(qm.resolve()), "reason": skip_reason})
            else:
                raw_tombstones.extend(extracted)
                total_path_exists_claims += len(claims)
                if len(path_exists_samples) < 50:
                    path_exists_samples.extend(claims[: 50 - len(path_exists_samples)])

    # Merge tombstones by (path, sha256)
    merged_tombstones: dict[tuple[str, str | None], TombstoneRecord] = {}
    for rt in raw_tombstones:
        key = (rt.path, rt.sha256)
        if key not in merged_tombstones:
            merged_tombstones[key] = TombstoneRecord(
                bytes=rt.bytes,
                deleted_at=rt.deleted_at,
                deleted_at_source=rt.deleted_at_source,
                path=rt.path,
                sha256=rt.sha256,
                sources=[],
                status_recorded=rt.status_recorded,
            )
        else:
            rec = merged_tombstones[key]
            if rec.bytes is None and rt.bytes is not None:
                rec.bytes = rt.bytes
            # prioritize RECORD deleted_at over ANCESTOR over NONE
            if (
                (rt.deleted_at_source == "RECORD" and rec.deleted_at_source != "RECORD")
                or (rt.deleted_at_source == "ANCESTOR" and rec.deleted_at_source == "NONE")
                or (rec.deleted_at is None and rt.deleted_at is not None)
            ):
                rec.deleted_at = rt.deleted_at
                rec.deleted_at_source = rt.deleted_at_source
            if rec.status_recorded is None and rt.status_recorded is not None:
                rec.status_recorded = rt.status_recorded

        src: dict[str, str | None] = {
            "file": rt.source_file,
            "json_pointer": rt.json_pointer,
            "task_id": rt.task_id,
        }
        if src not in merged_tombstones[key].sources:
            merged_tombstones[key].sources.append(src)

    # Sort sources for each tombstone
    for rec in merged_tombstones.values():
        rec.sources.sort(
            key=lambda s: (str(s["file"]), str(s["json_pointer"]), str(s["task_id"] or ""))
        )

    # Sort tombstones: path first, then sha256 (null last)
    sorted_tombstones = sorted(
        [t.to_dict() for t in merged_tombstones.values()],
        key=lambda r: (str(r["path"]), 1 if r["sha256"] is None else 0, str(r["sha256"] or "")),
    )

    # Build tombstone counts per task folder.
    # Counted if at least one source file is inside the folder.
    task_tombstone_counts: dict[str, int] = {}
    for tb in sorted_tombstones:
        seen_folders_for_tb: set[str] = set()
        tb_sources = cast(list[dict[str, str | None]], tb["sources"])
        for src in tb_sources:
            src_file_raw = src["file"]
            if src_file_raw:
                src_file_p = Path(src_file_raw)
                for tf in task_folders:
                    folder_p = Path(tf.path)
                    try:
                        if folder_p in src_file_p.parents:
                            seen_folders_for_tb.add(tf.path)
                    except OSError:
                        pass
        for f_path in seen_folders_for_tb:
            task_tombstone_counts[f_path] = task_tombstone_counts.get(f_path, 0) + 1

    # 5. Build tasks rows
    tasks_rows: list[dict[str, object]] = []
    for tf in task_folders:
        folder_p = Path(tf.path)
        project = determine_project(folder_p, msa_root)

        receipt_files: list[str] = []
        for rf in ["packet.md", "result.json", "final_reply.md"]:
            candidate_p = folder_p / rf
            if candidate_p.is_file() and not candidate_p.is_symlink():
                receipt_files.append(rf)

        res_path = folder_p / "result.json"
        result_json_status = "MISSING"
        task_lifecycle_state: str | None = None
        task_folder_bytes_reported: int | None = None
        run_ids: list[str] = []

        if res_path.is_file() and not res_path.is_symlink():
            try:
                st = res_path.stat()
                if st.st_size > max_json_size_bytes:
                    result_json_status = "TOO_LARGE"
                else:
                    with open(res_path, encoding="utf-8") as rf:
                        parsed_res: object = json.load(rf)
                    if isinstance(parsed_res, dict):
                        result_json_status = "OK"
                        parsed_dict = cast(dict[str, object], parsed_res)
                        tls = parsed_dict.get("task_lifecycle_state")
                        if isinstance(tls, str):
                            task_lifecycle_state = tls
                        raw_bytes = parsed_dict.get("task_folder_bytes")
                        if _is_int(raw_bytes):
                            task_folder_bytes_reported = cast(int, raw_bytes)
                        run_ids_set = _extract_run_ids_from_dict(cast(object, parsed_res))
                        run_ids = sorted(list(run_ids_set))
                    else:
                        result_json_status = "INVALID_JSON"
            except Exception:
                result_json_status = "INVALID_JSON"

        formal_run_ids_present: int | None = None
        if formal_run_ids is not None:
            formal_run_ids_present = sum(1 for r in run_ids if r in formal_run_ids)

        stage_manifests = task_to_stages.get(tf.task_id, [])
        tombstone_count = task_tombstone_counts.get(tf.path, 0)

        tasks_rows.append(
            {
                "date_folder": tf.date_folder,
                "formal_run_ids_present": formal_run_ids_present,
                "path": tf.path,
                "project": project,
                "receipt_files": receipt_files,
                "result_json_status": result_json_status,
                "root": tf.root,
                "run_ids": run_ids,
                "stage_manifests": stage_manifests,
                "task_folder_bytes_reported": task_folder_bytes_reported,
                "task_id": tf.task_id,
                "task_lifecycle_state": task_lifecycle_state,
                "tombstone_count": tombstone_count,
            }
        )

    # Sort tasks by path
    tasks_rows.sort(key=lambda r: str(r["path"]))

    # 6. Build stages rows
    stages_rows: list[dict[str, object]] = []
    for se in stage_entries:
        stages_rows.append(
            {
                "created_at": se.created_at,
                "db_exists": se.db_exists,
                "db_path": se.db_path,
                "db_sha256_recorded": se.db_sha256_recorded,
                "fact_state": se.fact_state,
                "formal_run_ids_present": se.formal_run_ids_present,
                "lottery_types": se.lottery_types,
                "manifest_path": se.manifest_path,
                "run_ids": se.run_ids,
                "strategies": se.strategies,
                "task_id": se.task_id,
            }
        )
    # Sort stages by manifest_path
    stages_rows.sort(key=lambda r: str(r["manifest_path"]))

    # 7. Write atomically
    def _write_jsonl_atomic(target_file: Path, rows: list[dict[str, object]]) -> None:
        tmp_file = output_dir / f".tmp_{target_file.name}_{os.getpid()}"
        with open(tmp_file, "w", encoding="utf-8") as f:
            for row in rows:
                line = json.dumps(row, sort_keys=True, ensure_ascii=False)
                f.write(line + "\n")
        os.replace(tmp_file, target_file)

    _write_jsonl_atomic(output_dir / "tasks.jsonl", tasks_rows)
    _write_jsonl_atomic(output_dir / "stages.jsonl", stages_rows)
    _write_jsonl_atomic(output_dir / "tombstones.jsonl", sorted_tombstones)

    # 8. Write catalog_meta.json atomically
    meta_content: dict[str, object] = {
        "built_at": datetime.now(UTC).isoformat(),
        "counts": {
            "stages": len(stages_rows),
            "tasks": len(tasks_rows),
            "tombstones": len(sorted_tombstones),
        },
        "deletion_claims_path_exists": {
            "count": total_path_exists_claims,
            "samples": path_exists_samples,
        },
        "formal_db": formal_db_info,
        "note": "Derived index. Do not hand-edit; rebuild with `lottolab task-catalog build`.",
        "output_dir": str(output_dir.resolve()),
        "roots": [str(r.resolve()) for r in roots],
        "skipped": skipped,
        "tool_version": getattr(lottolab, "__version__", "0.1.0"),
    }

    meta_tmp = output_dir / f".tmp_catalog_meta_{os.getpid()}.json"
    with open(meta_tmp, "w", encoding="utf-8") as f:
        json.dump(meta_content, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    os.replace(meta_tmp, output_dir / "catalog_meta.json")

    return BuildResult(
        tasks_count=len(tasks_rows),
        stages_count=len(stages_rows),
        tombstones_count=len(sorted_tombstones),
        output_dir=output_dir,
        skipped=skipped,
        deletion_claims_path_exists=cast(
            dict[str, object], meta_content["deletion_claims_path_exists"]
        ),
        formal_db_info=formal_db_info,
    )


def find_in_catalog(
    query: str,
    kind: str,
    catalog_dir: Path,
) -> tuple[int, list[tuple[str, str]]]:
    """Find query in catalog files. Returns (match_count, list of (kind, line))."""
    kinds_to_check: list[str] = []
    if kind == "all":
        kinds_to_check = ["tasks", "stages", "tombstones"]
    elif kind in ("tasks", "stages", "tombstones"):
        kinds_to_check = [kind]
    else:
        raise ValueError(f"Invalid kind: {kind}")

    # Check existence
    for k in kinds_to_check:
        file_p = catalog_dir / f"{k}.jsonl"
        if not file_p.is_file():
            raise FileNotFoundError(f"Catalog file not found: {file_p}")

    matches: list[tuple[str, str]] = []
    q_lower = query.lower()

    for k in kinds_to_check:
        file_p = catalog_dir / f"{k}.jsonl"
        with open(file_p, encoding="utf-8") as f:
            for line in f:
                stripped = line.rstrip("\r\n")
                if q_lower in stripped.lower():
                    matches.append((k, stripped))

    return len(matches), matches


@dataclass(frozen=True)
class MetricValue:
    indicator: str
    stratum: str
    status: str  # "MEASURED", "PARTIAL", "UNKNOWN"
    numerator: float | int | None
    denominator: float | int | None
    count: float | int | None
    eligible_count: int
    unknown_count: int
    value: float | str | None
    evidence_fields: list[str]
    notes: str | None = None
    components: dict[str, dict[str, int | float]] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "indicator": self.indicator,
            "stratum": self.stratum,
            "status": self.status,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "count": self.count,
            "eligible_count": self.eligible_count,
            "unknown_count": self.unknown_count,
            "value": self.value,
            "evidence_fields": self.evidence_fields,
            "notes": self.notes,
            "components": self.components,
        }


@dataclass(frozen=True)
class WorkflowMetricsReport:
    window_start: str
    window_end: str
    strata: list[str]
    total_tasks_evaluated: int
    tasks_by_stratum: dict[str, int]
    unknown_stratum_tasks: int
    unknown_window_date_tasks: int
    duplicate_receipts_ignored: int
    conflicting_task_ids: int
    metrics: list[MetricValue]
    unavailable_indicator_inputs: list[str]
    generated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "window_start": self.window_start,
            "window_end": self.window_end,
            "strata": self.strata,
            "total_tasks_evaluated": self.total_tasks_evaluated,
            "tasks_by_stratum": self.tasks_by_stratum,
            "unknown_stratum_tasks": self.unknown_stratum_tasks,
            "unknown_window_date_tasks": self.unknown_window_date_tasks,
            "duplicate_receipts_ignored": self.duplicate_receipts_ignored,
            "conflicting_task_ids": self.conflicting_task_ids,
            "metrics": [m.to_dict() for m in self.metrics],
            "unavailable_indicator_inputs": self.unavailable_indicator_inputs,
            "generated_at": self.generated_at,
        }


def _clean_header_val(val: object) -> str:
    if not isinstance(val, str):
        return ""
    return val.replace("\\", "").replace("`", "").strip().upper()


def _is_safe_receipt_dir(folder_path: str, expected_task_id: str | None = None) -> bool:
    """Validate that folder_path is a safe, non-symlink task directory matching expected_task_id."""
    try:
        fp = Path(folder_path)
        root = canonical_project_root()
        roots = (root / ".task-data", root.parent / ".task-data")
        if not fp.is_absolute() or not expected_task_id or fp.name != expected_task_id:
            return False
        for allowed in roots:
            try:
                relative = fp.relative_to(allowed)
            except ValueError:
                continue
            if len(relative.parts) not in (1, 2) or (
                len(relative.parts) == 2
                and not (len(relative.parts[0]) == 8 and relative.parts[0].isdigit())
            ):
                continue
            if any(part.is_symlink() for part in (allowed, *allowed.parents)):
                return False
            current = allowed
            for part in relative.parts:
                current = current / part
                if current.is_symlink():
                    return False
            return fp.is_dir() and allowed.resolve() in fp.resolve().parents
        return False
    except OSError:
        return False


def classify_task_stratum(
    task_record: dict[str, object],
    read_folder_receipts: bool = True,
) -> str | None:
    """Classify a task into S1..S6, or None if unknown."""
    if (
        task_record.get("metric_evidence_conflict") is True
        or task_record.get("route_evidence_conflict") is True
    ):
        return None

    raw_stratum = task_record.get("stratum")
    explicit_stratum: str | None = None
    if isinstance(raw_stratum, str) and raw_stratum.strip():
        s_upper = raw_stratum.upper().strip()
        if s_upper in REPORT_STRATA:
            explicit_stratum = s_upper
        else:
            explicit_stratum = next(
                (k for k, label in STRATUM_LABELS.items() if s_upper == label), None
            )
        if explicit_stratum is None:
            return None

    task_id = str(task_record.get("task_id") or "")
    stage_manifests = task_record.get("stage_manifests")
    has_stages = isinstance(stage_manifests, list) and len(cast(list[object], stage_manifests)) > 0

    route_info: dict[str, object] = {}
    raw_route = task_record.get("route")
    if isinstance(raw_route, dict):
        route_info.update(cast(dict[str, object], raw_route))

    for field in (
        "worker_route",
        "implementation_depth",
        "judge_mode",
        "task_class",
        "task_lane",
    ):
        if field in task_record and field not in route_info:
            route_info[field] = task_record[field]

    folder_path = task_record.get("path")
    if read_folder_receipts and isinstance(folder_path, str):  # noqa: SIM102
        if _is_safe_receipt_dir(folder_path, task_id if task_id else None):
            fp = Path(folder_path)
            res_file = fp / "result.json"
            if res_file.is_file() and not res_file.is_symlink():
                try:
                    if res_file.stat().st_size <= MAX_JSON_SIZE_BYTES:
                        with open(res_file, encoding="utf-8") as f:
                            r_data: object = json.load(f)
                        if isinstance(r_data, dict):
                            r_dict = cast(dict[str, object], r_data)
                            r_tid = r_dict.get("task_id")
                            if task_id and r_tid == task_id:
                                sub_route = r_dict.get("route")
                                if isinstance(sub_route, dict):
                                    route_info.update(cast(dict[str, object], sub_route))
                                if "task_class" in r_dict and "task_class" not in route_info:
                                    route_info["task_class"] = r_dict["task_class"]
                                if (
                                    "implementation_depth" in r_dict
                                    and "implementation_depth" not in route_info
                                ):
                                    route_info["implementation_depth"] = r_dict[
                                        "implementation_depth"
                                    ]
                                if "worker_route" in r_dict and "worker_route" not in route_info:
                                    route_info["worker_route"] = r_dict["worker_route"]
                                if "judge_mode" in r_dict and "judge_mode" not in route_info:
                                    route_info["judge_mode"] = r_dict["judge_mode"]
                except Exception:
                    pass

            pkt_file = fp / "packet.md"
            if (
                pkt_file.is_file()
                and not pkt_file.is_symlink()
                and pkt_file.stat().st_size <= MAX_JSON_SIZE_BYTES
            ):
                head_txt = _read_head_str(pkt_file, 16384)
                if head_txt and any(
                    line.strip() == f"TASK_ID: {task_id}" for line in head_txt.splitlines()
                ):
                    for line in head_txt.splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            k_clean = k.strip().upper()
                            v_clean = _clean_header_val(v)
                            if k_clean == "WORKER_ROUTE" and "worker_route" not in route_info:
                                route_info["worker_route"] = v_clean
                            elif (
                                k_clean == "IMPLEMENTATION_DEPTH"
                                and "implementation_depth" not in route_info
                            ):
                                route_info["implementation_depth"] = v_clean
                            elif k_clean == "JUDGE_MODE" and "judge_mode" not in route_info:
                                route_info["judge_mode"] = v_clean
                            elif k_clean == "TASK_CLASS" and "task_class" not in route_info:
                                route_info["task_class"] = v_clean
                            elif k_clean == "TASK_LANE" and "task_lane" not in route_info:
                                route_info["task_lane"] = v_clean

    wr = _clean_header_val(route_info.get("worker_route"))
    depth = _clean_header_val(route_info.get("implementation_depth"))
    jm = _clean_header_val(route_info.get("judge_mode"))
    tc = _clean_header_val(route_info.get("task_class"))
    lane = _clean_header_val(route_info.get("task_lane"))

    inferred: str | None = None
    if "FRESH_CONTEXT" in jm or "JUDGED" in wr or "JUDGE" in wr:
        inferred = "S4"
    elif (
        "RESEARCH" in tc
        or has_stages
        or any(x in lane for x in ("支線1", "支線2", "支線3", "L1", "L2", "L3"))
    ):
        inferred = "S5"
    elif "RELEASE" in tc or "CLOSEOUT" in tc:
        inferred = "S6"
    else:
        if wr == "FAST":
            inferred = "S1"
        elif "STANDARD" in wr and depth == "NORMAL":
            inferred = "S2"
        elif "STANDARD" in wr and "ENHANCED" in depth:
            inferred = "S3"

    if explicit_stratum is not None and inferred is not None and explicit_stratum != inferred:
        return None
    return inferred or explicit_stratum


def _enrich_task_data(t: dict[str, object], read_folder_receipts: bool) -> dict[str, object]:
    item = dict(t)
    folder_path = t.get("path")
    task_id = str(t.get("task_id") or "")
    if not read_folder_receipts or not isinstance(folder_path, str):
        return item
    if not _is_safe_receipt_dir(folder_path, task_id if task_id else None):
        return item

    folder = Path(folder_path)
    result_data: dict[str, object] | None = None
    result_file = folder / "result.json"
    if result_file.is_file() and not result_file.is_symlink():
        try:
            if result_file.stat().st_size <= MAX_JSON_SIZE_BYTES:
                with open(result_file, encoding="utf-8") as f:
                    loaded: object = json.load(f)
                if isinstance(loaded, dict):
                    candidate = cast(dict[str, object], loaded)
                    if task_id and candidate.get("task_id") == task_id:
                        result_data = candidate
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            result_data = None

    packet_fields: dict[str, str] = {}
    packet_file = folder / "packet.md"
    if packet_file.is_file() and not packet_file.is_symlink():
        try:
            if packet_file.stat().st_size <= MAX_JSON_SIZE_BYTES:
                packet_text = _read_head_str(packet_file, 16384)
                if packet_text and any(
                    line.strip() == f"TASK_ID: {task_id}" for line in packet_text.splitlines()
                ):
                    for line in packet_text.splitlines():
                        if ":" in line:
                            key, value = line.split(":", 1)
                            packet_fields[key.strip().upper()] = value.strip()
        except OSError:
            packet_fields = {}

    if result_data is not None:
        if item.get("task_lifecycle_state") is None:
            item["task_lifecycle_state"] = result_data.get("task_lifecycle_state")

        route_info: dict[str, object] = {}
        for source in (item.get("route"), result_data.get("route")):
            if isinstance(source, dict):
                for key, value in cast(dict[str, object], source).items():
                    if key in route_info and route_info[key] != value:
                        item["route_evidence_conflict"] = True
                    else:
                        route_info[key] = value
        for key in (
            "worker_route",
            "implementation_depth",
            "judge_mode",
            "task_class",
            "task_lane",
        ):
            value = result_data.get(key)
            if value is not None:
                if key in route_info and route_info[key] != value:
                    item["route_evidence_conflict"] = True
                else:
                    route_info[key] = value
        if route_info:
            item["route"] = route_info

        for field in (
            "goal_72h_completed",
            "avoidable_block",
            "acceptance_confirmed",
            "adopted_outcome",
            "same_original_task",
            "unproductive_continuation_count",
            "owner_intervention_count",
            "dispatch_to_acceptance_seconds",
            "acceptance_to_adoption_seconds",
            "resource_cost_measured",
        ):
            if field not in item and field in result_data:
                item[field] = result_data[field]

        cost = result_data.get("cost")
        cost_data = cast(dict[str, object], cost) if isinstance(cost, dict) else {}
        if "tokens" not in item:
            if "tokens" in result_data:
                item["tokens"] = result_data["tokens"]
            elif "tokens" in cost_data:
                item["tokens"] = cost_data["tokens"]
        for key in ("model_identity", "actual_model", "model_id"):
            if key in result_data and "model_identity" not in item:
                item["model_identity"] = result_data[key]
                break
        if "model_identity" not in item:
            for key in ("model_identity", "actual_model", "model_id"):
                if key in cost_data:
                    item["model_identity"] = cost_data[key]
                    break
        if "model_tier" not in item and isinstance(result_data.get("model_tier"), str):
            item["model_tier"] = result_data["model_tier"]

        signal = result_data.get("process_signal")
        if isinstance(signal, dict):
            issue = cast(dict[str, object], signal).get("issue")
            if isinstance(issue, dict) and "issue_type" not in item:
                item["issue_type"] = cast(dict[str, object], issue).get("type")

        regression_evidence = result_data.get("regression_escape_evidence")
        if isinstance(regression_evidence, dict):
            evidence = cast(dict[str, object], regression_evidence)
            confirmed = (
                str(evidence.get("status", "")).upper() == "CONFIRMED"
                and evidence.get("acceptance_before") is True
                and evidence.get("observed_after_acceptance") is True
                and str(evidence.get("issue_type", "")).upper() == "REGRESSION"
                and isinstance(evidence.get("evidence_locator"), str)
                and bool(cast(str, evidence.get("evidence_locator")).strip())
            )
            checked_clear = (
                str(evidence.get("status", "")).upper() == "CHECKED_NO_ESCAPE"
                and evidence.get("observation_window_closed") is True
            )
            if confirmed:
                item["regression_escape"] = True
            elif checked_clear:
                item["regression_escape"] = False
            else:
                item.pop("regression_escape", None)
        elif isinstance(result_data.get("confirmed_regression_escape"), bool):
            item["regression_escape"] = result_data["confirmed_regression_escape"]
        else:
            # A generic INCIDENT/process signal is not a confirmed escaped regression.
            item.pop("regression_escape", None)

    # Resolve the task's original/continuation marker from exact matching receipts.
    link_values: list[str] = []
    if result_data is not None:
        raw_link = result_data.get("continues_from", result_data.get("CONTINUES_FROM"))
        if isinstance(raw_link, str) and raw_link.strip():
            link_values.append(raw_link.strip())
    packet_link = packet_fields.get("CONTINUES_FROM")
    if packet_link:
        link_values.append(packet_link)
    existing_link = item.get("continues_from")
    if isinstance(existing_link, str) and existing_link.strip():
        link_values.append(existing_link.strip())

    normalized_links = {v.upper() if v.upper() == "NONE" else v for v in link_values}
    if len(normalized_links) > 1:
        item["lineage_evidence_conflict"] = True
        item.pop("first_pass_accepted", None)
    elif normalized_links:
        link = next(iter(normalized_links))
        continuation_markers = [
            item.get("is_continuation"),
            result_data.get("is_continuation") if result_data is not None else None,
            result_data.get("continuation_id") if result_data is not None else None,
        ]
        has_continuation_marker = any(
            value is True or (isinstance(value, str) and value.strip())
            for value in continuation_markers
        )
        marker_conflict = (link == "NONE" and has_continuation_marker) or (
            link != "NONE" and any(value is False for value in continuation_markers)
        )
        if marker_conflict:
            item["lineage_evidence_conflict"] = True
            item.pop("first_pass_accepted", None)
        elif link == "NONE":
            item["continues_from"] = "NONE"
            item["is_continuation"] = False
            item["original_task_confirmed"] = True
        else:
            item["continues_from"] = link
            item["is_continuation"] = True
            item["original_task_confirmed"] = False
    elif result_data is not None and result_data.get("continuation_id"):
        item["is_continuation"] = True
        item["original_task_confirmed"] = False

    for key, field in (
        ("WORKER_ROUTE", "worker_route"),
        ("IMPLEMENTATION_DEPTH", "implementation_depth"),
        ("JUDGE_MODE", "judge_mode"),
        ("TASK_CLASS", "task_class"),
        ("TASK_LANE", "task_lane"),
    ):
        value = packet_fields.get(key)
        if value:
            current_route = item.get("route")
            route = (
                dict(cast(dict[str, object], current_route))
                if isinstance(current_route, dict)
                else {}
            )
            if field in route and _clean_header_val(route[field]) != _clean_header_val(value):
                item["route_evidence_conflict"] = True
            else:
                route[field] = value
            item["route"] = route

    before_attempt = folder / "result.before_1.json"
    has_before_attempt = before_attempt.exists() or before_attempt.is_symlink()
    before_first_pass_failed = False
    before_first_pass_conflict = False
    if has_before_attempt and before_attempt.is_file() and not before_attempt.is_symlink():
        try:
            if before_attempt.stat().st_size <= MAX_JSON_SIZE_BYTES:
                with open(before_attempt, encoding="utf-8") as f:
                    before_loaded: object = json.load(f)
                if isinstance(before_loaded, dict):
                    before_data = cast(dict[str, object], before_loaded)
                    before_task_id = before_data.get("task_id")
                    if isinstance(task_id, str) and task_id and before_task_id == task_id:
                        explicit_first_pass = next(
                            (
                                before_data[key]
                                for key in ("first_pass_accepted", "first_pass_acceptance")
                                if isinstance(before_data.get(key), bool)
                            ),
                            None,
                        )
                        round_status = str(
                            before_data.get("first_round_ac_status", "")
                        ).upper()
                        lifecycle = str(
                            before_data.get("task_lifecycle_state", "")
                        ).upper()
                        failed_states = {
                            "BLOCKED",
                            "BLOCKED_OWNER_DISPOSITION",
                            "ABORTED",
                            "FAILED",
                            "FAIL",
                            "CANCELED",
                            "CANCELLED",
                        }
                        has_failure_status = (
                            round_status in failed_states or lifecycle in failed_states
                        )
                        before_first_pass_conflict = (
                            (explicit_first_pass is True and has_failure_status)
                            or (explicit_first_pass is False and round_status == "PASS")
                            or (round_status == "PASS" and lifecycle in failed_states)
                        )
                        before_first_pass_failed = not before_first_pass_conflict and (
                            explicit_first_pass is False or has_failure_status
                        )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            before_first_pass_failed = False
    first_pass_value: object = None
    if result_data is not None:
        for key in ("first_pass_accepted", "first_pass_acceptance"):
            if isinstance(result_data.get(key), bool):
                first_pass_value = result_data[key]
                break
        if first_pass_value is None and result_data.get("first_round_ac_status") in (
            "PASS",
            "FAIL",
        ):
            first_pass_value = result_data["first_round_ac_status"] == "PASS"
    if item.get("lineage_evidence_conflict"):
        item.pop("first_pass_accepted", None)
    elif has_before_attempt:
        # A before_1 snapshot proves that the task continued. Only matching,
        # non-conflicting first-round failure evidence distinguishes failure
        # from missing evidence; a later result cannot promote that first pass.
        if before_first_pass_conflict:
            item.pop("first_pass_accepted", None)
        elif before_first_pass_failed:
            item["first_pass_accepted"] = False
        else:
            item.pop("first_pass_accepted", None)
    elif item.get("original_task_confirmed") is True and isinstance(first_pass_value, bool):
        item["first_pass_accepted"] = first_pass_value
    elif item.get("original_task_confirmed") is not True:
        item.pop("first_pass_accepted", None)

    return item


def compute_workflow_metrics(
    catalog_dir: Path,
    start_date: str = BASELINE_WINDOW_START,
    end_date: str = BASELINE_WINDOW_END,
    read_folder_receipts: bool = True,
    tasks_data: list[dict[str, object]] | None = None,
) -> WorkflowMetricsReport:
    """Compute workflow effect metrics for fixed window and six strata S1..S6."""
    start_norm = _parse_date(start_date)
    end_norm = _parse_date(end_date)
    if start_norm is None or end_norm is None or start_norm > end_norm:
        raise ValueError("start_date and end_date must be valid ordered calendar dates")

    if tasks_data is not None:
        raw_tasks = tasks_data
    else:
        cat_file = catalog_dir / "tasks.jsonl"
        if not cat_file.is_file():
            raise FileNotFoundError(f"Catalog file not found: {cat_file}")
        raw_tasks: list[dict[str, object]] = []
        with open(cat_file, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    raw_tasks.append(cast(dict[str, object], json.loads(stripped)))

    window_tasks: list[dict[str, object]] = []
    unknown_window_date_tasks = 0
    for t in raw_tasks:
        task_date = _parse_date(t.get("date_folder"))
        if task_date is None:
            task_date = _parse_date(t.get("date"))
        if task_date is None:
            unknown_window_date_tasks += 1
        elif start_norm <= task_date <= end_norm:
            window_tasks.append(t)

    window_tasks, duplicate_receipts_ignored, conflicting_task_ids = _deduplicate_task_records(
        window_tasks
    )

    # An explicit link alone may name a related but distinct task. Only merge
    # when evidence also states that the original task identity is the same.
    window_tasks = [_enrich_task_data(t, read_folder_receipts) for t in window_tasks]
    by_id: dict[str, list[dict[str, object]]] = {}
    for task in window_tasks:
        tid = task.get("task_id")
        if isinstance(tid, str) and tid:
            by_id.setdefault(tid, []).append(task)
    linked: set[int] = set()
    children_by_parent: dict[str, list[dict[str, object]]] = {}

    def _has_parent(task: dict[str, object]) -> bool:
        parent_value = task.get("continues_from")
        return (
            isinstance(parent_value, str)
            and bool(parent_value.strip())
            and parent_value.strip().upper() != "NONE"
        )

    for task in window_tasks:
        parent = task.get("continues_from")
        if task.get("same_original_task") is True and _has_parent(task):
            parent_id = cast(str, parent).strip()
            children_by_parent.setdefault(parent_id, []).append(task)

    for task in window_tasks:
        if _has_parent(task):
            continue
        original_id = task.get("task_id")
        original_stratum = classify_task_stratum(task, False)
        original_is_confirmed = (
            task.get("original_task_confirmed") is True
            or task.get("is_continuation") is False
            or (
                isinstance(task.get("continues_from"), str)
                and cast(str, task["continues_from"]).strip().upper() == "NONE"
            )
        )
        if (
            not isinstance(original_id, str)
            or not original_id
            or len(by_id.get(original_id, [])) != 1
            or task.get("lineage_evidence_conflict") is True
            or task.get("route_evidence_conflict") is True
            or task.get("same_original_task") is False
            or not original_is_confirmed
            or original_stratum is None
            or not children_by_parent.get(original_id)
        ):
            continue

        chain = [task]
        seen_ids = {original_id}
        current = task
        chain_is_unambiguous = True
        while True:
            current_id = current.get("task_id")
            if not isinstance(current_id, str):
                chain_is_unambiguous = False
                break
            next_tasks = children_by_parent.get(current_id, [])
            if not next_tasks:
                break
            if len(next_tasks) != 1:
                chain_is_unambiguous = False
                break

            child = next_tasks[0]
            child_id = child.get("task_id")
            child_parent = child.get("continues_from")
            if (
                not isinstance(child_id, str)
                or not child_id
                or len(by_id.get(child_id, [])) != 1
                or child_id in seen_ids
                or not isinstance(child_parent, str)
                or child_parent.strip() != current_id
                or child.get("same_original_task") is not True
                or child.get("lineage_evidence_conflict") is True
                or child.get("route_evidence_conflict") is True
                or child.get("is_continuation") is False
                or child.get("original_task_confirmed") is True
                or classify_task_stratum(child, False) != original_stratum
            ):
                chain_is_unambiguous = False
                break

            chain.append(child)
            seen_ids.add(child_id)
            current = child

        if not chain_is_unambiguous or len(chain) < 2:
            continue

        # A verified linear chain is one original task. Later explicit terminal
        # observations supersede earlier snapshots; confirmed regression and
        # adoption evidence remains true once observed.
        for field in ("goal_72h_completed", "acceptance_confirmed"):
            latest = next(
                (
                    node[field]
                    for node in reversed(chain)
                    if isinstance(node.get(field), bool)
                ),
                None,
            )
            if isinstance(latest, bool):
                task[field] = latest
            else:
                task.pop(field, None)

        regression_values = [node.get("regression_escape") for node in chain]
        if any(value is True for value in regression_values):
            task["regression_escape"] = True
        elif any(value is False for value in regression_values):
            task["regression_escape"] = False
        else:
            task.pop("regression_escape", None)

        adoption_values = [node.get("adopted_outcome") for node in chain]
        if any(value is True for value in adoption_values):
            task["adopted_outcome"] = True
        elif any(value is False for value in adoption_values):
            task["adopted_outcome"] = False
        else:
            task.pop("adopted_outcome", None)

        # These observations are per execution, not necessarily totals or
        # elapsed times for the whole original task. Do not double count them.
        for field in (
            "tokens",
            "model_identity",
            "model_tier",
            "unproductive_continuation_count",
            "owner_intervention_count",
            "dispatch_to_acceptance_seconds",
            "acceptance_to_adoption_seconds",
            "resource_cost_measured",
        ):
            task.pop(field, None)
        linked.update(id(node) for node in chain[1:])

    # Missing parent evidence, conflicting links, cycles, and branched chains
    # stay visible as unknown instead of being counted as separate successes.
    ambiguous: set[int] = set()
    for task in window_tasks:
        parent = task.get("continues_from")
        has_parent = _has_parent(task)
        same_task_link_unresolved = (
            task.get("same_original_task") is True and id(task) not in linked
        )
        unverified_link = has_parent and task.get("same_original_task") is None
        continuation_without_parent = task.get("is_continuation") is True and not has_parent
        lineage_conflict = task.get("lineage_evidence_conflict") is True
        if id(task) not in linked and (
            same_task_link_unresolved
            or unverified_link
            or continuation_without_parent
            or lineage_conflict
        ):
            ambiguous.add(id(task))
            if has_parent:
                ambiguous.update(id(t) for t in by_id.get(cast(str, parent).strip(), []))
    for task in window_tasks:
        if id(task) in ambiguous:
            for field in (
                "first_pass_accepted",
                "goal_72h_completed",
                "acceptance_confirmed",
                "regression_escape",
                "avoidable_block",
                "task_lifecycle_state",
                "tokens",
                "model_identity",
                "model_tier",
                "adopted_outcome",
                "unproductive_continuation_count",
                "owner_intervention_count",
                "dispatch_to_acceptance_seconds",
                "acceptance_to_adoption_seconds",
                "resource_cost_measured",
            ):
                task.pop(field, None)
    window_tasks = [task for task in window_tasks if id(task) not in linked]

    tasks_by_stratum: dict[str, list[dict[str, object]]] = {s: [] for s in REPORT_STRATA}
    unknown_stratum_tasks: list[dict[str, object]] = []

    for t in window_tasks:
        st = classify_task_stratum(t, read_folder_receipts=read_folder_receipts)
        if st in tasks_by_stratum:
            tasks_by_stratum[st].append(t)
        else:
            unknown_stratum_tasks.append(t)

    metrics: list[MetricValue] = []

    for s in REPORT_STRATA:
        raw_s_tasks = tasks_by_stratum[s]
        s_tasks = raw_s_tasks
        eligible = len(s_tasks)

        # 1. FIRST_PASS_ACCEPTANCE_RATE
        fp_num = 0
        fp_den = 0
        fp_unknown = 0
        for t in s_tasks:
            # Explicit first-round AC evidence is required; lifecycle and suffixes are proxies.
            first_pass = t.get("first_pass_accepted")
            has_continuation_link = _has_parent(t)
            original_task_confirmed = t.get("original_task_confirmed") is True or (
                isinstance(t.get("continues_from"), str)
                and cast(str, t["continues_from"]).strip().upper() == "NONE"
            )
            continuation_unknown = (
                t.get("is_continuation") is True
                or t.get("original_task_confirmed") is False
                or t.get("lineage_evidence_conflict") is True
                or has_continuation_link
                or not original_task_confirmed
            )
            if continuation_unknown:
                fp_unknown += 1
            elif first_pass is True:
                fp_num += 1
                fp_den += 1
            elif first_pass is False:
                fp_den += 1
            else:
                fp_unknown += 1

        if fp_den > 0 and fp_unknown == 0:
            fp_status = "MEASURED"
            fp_val = round(fp_num / fp_den, 4)
        elif fp_den > 0:
            fp_status = "PARTIAL"
            fp_val = round(fp_num / fp_den, 4)
        else:
            fp_status = "UNKNOWN"
            fp_val = None

        metrics.append(
            MetricValue(
                indicator="FIRST_PASS_ACCEPTANCE_RATE",
                stratum=s,
                status=fp_status,
                numerator=fp_num,
                denominator=fp_den,
                count=None,
                eligible_count=eligible,
                unknown_count=fp_unknown,
                value=fp_val,
                evidence_fields=[
                    "first_pass_accepted",
                ],
                notes="Proportion of initial dispatches passing acceptance without continuation",
            )
        )

        # 2. FINAL_GOAL_COMPLETION_RATE
        fg_num = 0
        fg_den = 0
        fg_unknown = 0
        for t in s_tasks:
            goal = t.get("goal_72h_completed")
            if goal is True:
                fg_num += 1
                fg_den += 1
            elif goal is False:
                fg_den += 1
            else:
                fg_unknown += 1

        if fg_den > 0 and fg_unknown == 0:
            fg_status = "MEASURED"
            fg_val = round(fg_num / fg_den, 4)
        elif fg_den > 0:
            fg_status = "PARTIAL"
            fg_val = round(fg_num / fg_den, 4)
        else:
            fg_status = "UNKNOWN"
            fg_val = None

        metrics.append(
            MetricValue(
                indicator="FINAL_GOAL_COMPLETION_RATE",
                stratum=s,
                status=fg_status,
                numerator=fg_num,
                denominator=fg_den,
                count=None,
                eligible_count=eligible,
                unknown_count=fg_unknown,
                value=fg_val,
                evidence_fields=["goal_72h_completed"],
                notes="Explicit original project goal outcome within 72 hours",
            )
        )

        # 3. AVOIDABLE_BLOCK_RATE
        ab_num = 0
        ab_den = 0
        ab_unknown = 0
        for t in s_tasks:
            tls_value = t.get("task_lifecycle_state")
            tls = tls_value.upper().strip() if isinstance(tls_value, str) else None
            if tls in ("BLOCKED", "BLOCKED_OWNER_DISPOSITION"):
                is_avoidable = t.get("avoidable_block")
                if is_avoidable is True:
                    ab_num += 1
                    ab_den += 1
                elif is_avoidable is False:
                    ab_den += 1
                else:
                    ab_unknown += 1
            elif tls not in (
                "COMPLETED",
                "ABORTED",
                "IN_PROGRESS",
                "FAILED",
                "FAIL",
                "CANCELED",
                "CANCELLED",
            ):
                # Block eligibility itself is unknown.
                ab_unknown += 1

        if ab_den > 0 and ab_unknown == 0:
            ab_status = "MEASURED"
            ab_val = round(ab_num / ab_den, 4)
        elif ab_den > 0:
            ab_status = "PARTIAL"
            ab_val = round(ab_num / ab_den, 4)
        else:
            ab_status = "UNKNOWN"
            ab_val = None

        metrics.append(
            MetricValue(
                indicator="AVOIDABLE_BLOCK_RATE",
                stratum=s,
                status=ab_status,
                numerator=ab_num,
                denominator=ab_den,
                count=None,
                eligible_count=ab_den + ab_unknown,
                unknown_count=ab_unknown,
                value=ab_val,
                evidence_fields=[
                    "task_lifecycle_state",
                    "process_signal.issue.type",
                    "block_reason",
                ],
                notes="Proportion of BLOCKED tasks caused by preflight avoidable missing items",
            )
        )

        # 4. UNPRODUCTIVE_CONTINUATION_COUNT
        up_count = 0
        up_has_data = False
        up_unknown = 0
        for t in s_tasks:
            c = t.get("unproductive_continuation_count")
            if _nonnegative_int(c):
                up_count += cast(int, c)
                up_has_data = True
            else:
                up_unknown += 1

        if up_has_data and up_unknown == 0:
            up_status = "MEASURED"
            up_val: float | str | None = up_count
        elif up_has_data:
            up_status = "PARTIAL"
            up_val = up_count
        else:
            up_status = "UNKNOWN"
            up_val = None

        metrics.append(
            MetricValue(
                indicator="UNPRODUCTIVE_CONTINUATION_COUNT",
                stratum=s,
                status=up_status,
                numerator=None,
                denominator=None,
                count=up_val if isinstance(up_val, (int, float)) else None,
                eligible_count=eligible,
                unknown_count=up_unknown,
                value=up_val,
                evidence_fields=["continuation_evidence", "process_signal.issue"],
                notes="Cumulative continuation iterations with no progress or unblock evidence",
            )
        )

        # 5. OWNER_INTERVENTION_COUNT
        oi_count = 0
        oi_has_data = False
        oi_unknown = 0
        for t in s_tasks:
            c = t.get("owner_intervention_count")
            if _nonnegative_int(c):
                oi_count += cast(int, c)
                oi_has_data = True
            else:
                oi_unknown += 1

        if oi_has_data and oi_unknown == 0:
            oi_status = "MEASURED"
            oi_val: float | str | None = oi_count
        elif oi_has_data:
            oi_status = "PARTIAL"
            oi_val = oi_count
        else:
            oi_status = "UNKNOWN"
            oi_val = None

        metrics.append(
            MetricValue(
                indicator="OWNER_INTERVENTION_COUNT",
                stratum=s,
                status=oi_status,
                numerator=None,
                denominator=None,
                count=oi_val if isinstance(oi_val, (int, float)) else None,
                eligible_count=eligible,
                unknown_count=oi_unknown,
                value=oi_val,
                evidence_fields=["owner_interventions", "auth_grants"],
                notes="Cumulative manual owner intervention occurrences",
            )
        )

        # 6. DISPATCH_TO_ACCEPTANCE_TIME
        da_times: list[float] = []
        da_unknown = 0
        for t in s_tasks:
            secs = t.get("dispatch_to_acceptance_seconds")
            if _nonnegative_number(secs):
                da_times.append(float(cast(float, secs)))
            else:
                da_unknown += 1

        if da_times and da_unknown == 0:
            da_status = "MEASURED"
            da_val: float | str | None = round(sum(da_times) / len(da_times), 2)
        elif da_times:
            da_status = "PARTIAL"
            da_val = round(sum(da_times) / len(da_times), 2)
        else:
            da_status = "UNKNOWN"
            da_val = None

        metrics.append(
            MetricValue(
                indicator="DISPATCH_TO_ACCEPTANCE_TIME",
                stratum=s,
                status=da_status,
                numerator=round(sum(da_times), 2) if da_times else None,
                denominator=len(da_times) if da_times else None,
                count=len(da_times) if da_times else None,
                eligible_count=eligible,
                unknown_count=da_unknown,
                value=da_val,
                evidence_fields=["dispatch_timestamp", "acceptance_timestamp", "elapsed_seconds"],
                notes="Mean dispatch-to-acceptance time in seconds across measured tasks",
            )
        )

        # 7. ACCEPTANCE_TO_ADOPTION_TIME
        aa_times: list[float] = []
        aa_unknown = 0
        for t in s_tasks:
            secs = t.get("acceptance_to_adoption_seconds")
            if _nonnegative_number(secs):
                aa_times.append(float(cast(float, secs)))
            else:
                aa_unknown += 1

        if aa_times and aa_unknown == 0:
            aa_status = "MEASURED"
            aa_val: float | str | None = round(sum(aa_times) / len(aa_times), 2)
        elif aa_times:
            aa_status = "PARTIAL"
            aa_val = round(sum(aa_times) / len(aa_times), 2)
        else:
            aa_status = "UNKNOWN"
            aa_val = None

        metrics.append(
            MetricValue(
                indicator="ACCEPTANCE_TO_ADOPTION_TIME",
                stratum=s,
                status=aa_status,
                numerator=round(sum(aa_times), 2) if aa_times else None,
                denominator=len(aa_times) if aa_times else None,
                count=len(aa_times) if aa_times else None,
                eligible_count=eligible,
                unknown_count=aa_unknown,
                value=aa_val,
                evidence_fields=["acceptance_timestamp", "adoption_timestamp"],
                notes="Mean acceptance-to-adoption/merge time in seconds across measured tasks",
            )
        )

        # 8. MODEL_COST_PER_ACCEPTED_OUTCOME
        tot_tokens = 0
        tokens_measured_tasks = 0
        tok_unknown = 0
        accepted_outcomes = 0
        for t in s_tasks:
            adopted = t.get("adopted_outcome")
            if adopted is True:
                accepted_outcomes += 1
            tok = t.get("tokens")
            model_identity = t.get("model_identity")
            if (
                _nonnegative_int(tok)
                and isinstance(model_identity, str)
                and bool(model_identity.strip())
                and _has_explicit_route(t)
                and isinstance(adopted, bool)
            ):
                tot_tokens += cast(int, tok)
                tokens_measured_tasks += 1
            else:
                tok_unknown += 1

        if tokens_measured_tasks > 0 and tok_unknown == 0 and accepted_outcomes > 0:
            mc_status = "MEASURED"
            mc_val: float | str | None = round(tot_tokens / accepted_outcomes, 2)
        elif tokens_measured_tasks > 0 and accepted_outcomes > 0:
            mc_status = "PARTIAL"
            mc_val = round(tot_tokens / accepted_outcomes, 2)
        else:
            mc_status = "UNKNOWN"
            mc_val = None

        metrics.append(
            MetricValue(
                indicator="MODEL_COST_PER_ACCEPTED_OUTCOME",
                stratum=s,
                status=mc_status,
                numerator=tot_tokens if tokens_measured_tasks > 0 else None,
                denominator=accepted_outcomes if accepted_outcomes > 0 else None,
                count=tokens_measured_tasks if tokens_measured_tasks > 0 else None,
                eligible_count=eligible,
                unknown_count=tok_unknown,
                value=mc_val,
                evidence_fields=[
                    "cost.tokens",
                    "model_identity",
                    "route.worker_route",
                    "adopted_outcome",
                ],
                notes=(
                    "Total measured tokens divided by formally adopted outcomes; "
                    "continuation-chain costs remain UNKNOWN unless task-level totals are explicit"
                ),
            )
        )

        # 9. REGRESSION_ESCAPE_RATE
        esc_num = 0
        esc_den = 0
        esc_unknown = 0
        esc_eligible = 0
        for t in s_tasks:
            has_esc = t.get("regression_escape")
            accepted = t.get("acceptance_confirmed")
            if accepted is False:
                continue
            esc_eligible += 1
            if accepted is True:
                if has_esc is True:
                    esc_num += 1
                    esc_den += 1
                elif has_esc is False:
                    esc_den += 1
                else:
                    esc_unknown += 1
            else:
                esc_unknown += 1

        if esc_den > 0 and esc_unknown == 0:
            esc_status = "MEASURED"
            esc_val = round(esc_num / esc_den, 4)
        elif esc_den > 0:
            esc_status = "PARTIAL"
            esc_val = round(esc_num / esc_den, 4)
        else:
            esc_status = "UNKNOWN"
            esc_val = None

        metrics.append(
            MetricValue(
                indicator="REGRESSION_ESCAPE_RATE",
                stratum=s,
                status=esc_status,
                numerator=esc_num,
                denominator=esc_den,
                count=None,
                eligible_count=esc_eligible,
                unknown_count=esc_unknown,
                value=esc_val,
                evidence_fields=[
                    "acceptance_confirmed",
                    "regression_escape",
                ],
                notes=(
                    "Proportion of confirmed accepted tasks with confirmed later regression; "
                    "known unaccepted tasks are ineligible"
                ),
            )
        )

        # 10. RESOURCE_COST
        resource_fields = (
            "available_disk_bytes",
            "orphan_worktree_count",
            "temporary_residue_bytes",
        )
        resource_values: dict[str, list[int]] = {field: [] for field in resource_fields}
        resource_unknown = 0
        for t in s_tasks:
            raw_resource = t.get("resource_cost_measured")
            resource = (
                cast(dict[str, object], raw_resource) if isinstance(raw_resource, dict) else {}
            )
            task_complete = True
            for field in resource_fields:
                value = resource.get(field)
                if _nonnegative_int(value):
                    resource_values[field].append(cast(int, value))
                else:
                    task_complete = False
            if not task_complete:
                resource_unknown += 1

        resource_components: dict[str, dict[str, int | float]] = {}
        for field, values in resource_values.items():
            summary: dict[str, int | float] = {
                "observations": len(values),
                "unknown_count": eligible - len(values),
            }
            if values:
                summary["minimum"] = min(values)
                summary["maximum"] = max(values)
            resource_components[field] = summary

        resource_has_observations = any(resource_values.values())
        if eligible > 0 and resource_has_observations and resource_unknown == 0:
            rc_status = "MEASURED"
        elif resource_has_observations:
            rc_status = "PARTIAL"
        else:
            rc_status = "UNKNOWN"

        metrics.append(
            MetricValue(
                indicator="RESOURCE_COST",
                stratum=s,
                status=rc_status,
                numerator=None,
                denominator=None,
                count=None,
                eligible_count=eligible,
                unknown_count=resource_unknown,
                value=None,
                evidence_fields=[
                    "resource_cost_measured.available_disk_bytes",
                    "resource_cost_measured.orphan_worktree_count",
                    "resource_cost_measured.temporary_residue_bytes",
                ],
                notes=(
                    "Observed resource vector; per-component min/max are reported without "
                    "inventing a composite score"
                ),
                components=resource_components,
            )
        )

    # Determine unavailable indicator inputs across all strata
    unavailable_inputs: list[str] = []
    for ind in TEN_INDICATORS:
        strata_metrics = [m for m in metrics if m.indicator == ind]
        if all(m.status == "UNKNOWN" for m in strata_metrics):
            unavailable_inputs.append(ind)

    counts_by_stratum = {s: len(tasks_by_stratum[s]) for s in REPORT_STRATA}

    return WorkflowMetricsReport(
        window_start=f"{start_norm[:4]}-{start_norm[4:6]}-{start_norm[6:8]}",
        window_end=f"{end_norm[:4]}-{end_norm[4:6]}-{end_norm[6:8]}",
        strata=list(REPORT_STRATA),
        total_tasks_evaluated=len(window_tasks),
        tasks_by_stratum=counts_by_stratum,
        unknown_stratum_tasks=len(unknown_stratum_tasks),
        unknown_window_date_tasks=unknown_window_date_tasks,
        duplicate_receipts_ignored=duplicate_receipts_ignored,
        conflicting_task_ids=conflicting_task_ids,
        metrics=metrics,
        unavailable_indicator_inputs=unavailable_inputs,
        generated_at=datetime.now(UTC).isoformat(),
    )


def format_metrics_report_markdown(report: WorkflowMetricsReport) -> str:
    """Format workflow metrics report as GitHub-flavored Markdown."""
    lines = [
        "# Task Workflow Effect Metrics Baseline Report",
        "",
        f"- **Window**: `{report.window_start}` to `{report.window_end}`",
        f"- **Generated At**: `{report.generated_at}`",
        f"- **Total Tasks Evaluated in Window**: `{report.total_tasks_evaluated}`",
        f"- **Unknown Stratum Tasks**: `{report.unknown_stratum_tasks}`",
        f"- **Unknown Window Dates**: `{report.unknown_window_date_tasks}`",
        f"- **Duplicate Receipts Ignored**: `{report.duplicate_receipts_ignored}`",
        f"- **Conflicting Task IDs**: `{report.conflicting_task_ids}`",
        "",
        "## Strata Task Breakdown",
        "",
        "| Stratum | Label | Task Count |",
        "|---|---|---|",
    ]
    for s in report.strata:
        count = report.tasks_by_stratum.get(s, 0)
        label = STRATUM_LABELS.get(s, s)
        lines.append(f"| {s} | {label} | {count} |")

    lines.extend(
        [
            "",
            "## Workflow Effect Indicators",
            "",
            (
                "| Stratum | Indicator | Status | Value | Num / Den or Count | "
                "Eligible | Unknown | Evidence Fields | Notes |"
            ),
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for m in report.metrics:
        if m.components is not None:
            val_str = json.dumps(m.components, ensure_ascii=False, sort_keys=True)
        else:
            val_str = str(m.value) if m.value is not None else "UNKNOWN"
        if m.numerator is not None and m.denominator is not None:
            nd_str = f"{m.numerator}/{m.denominator}"
        elif m.count is not None:
            nd_str = f"count={m.count}"
        else:
            nd_str = "—"
        ev_str = ", ".join(m.evidence_fields)
        notes_str = m.notes or ""
        lines.append(
            f"| {m.stratum} | `{m.indicator}` | `{m.status}` | {val_str} | {nd_str} | "
            f"{m.eligible_count} | {m.unknown_count} | {ev_str} | {notes_str} |"
        )

    lines.extend(
        [
            "",
            "## Unavailable Indicator Inputs",
            "",
        ]
    )
    if report.unavailable_indicator_inputs:
        for u in report.unavailable_indicator_inputs:
            lines.append(
                f"- `{u}`: Input evidence absent in task catalog records; preserved as `UNKNOWN`."
            )
    else:
        lines.append("None; all indicators have measurable inputs.")
    lines.append("")
    return "\n".join(lines)


def format_metrics_report_text(report: WorkflowMetricsReport) -> str:
    """Format workflow metrics report as plain text."""
    lines = [
        "================================================================================",
        f"WORKFLOW EFFECT METRICS BASELINE: {report.window_start} -> {report.window_end}",
        (
            f"Total Tasks: {report.total_tasks_evaluated} | "
            f"Unknown Stratum Tasks: {report.unknown_stratum_tasks} | "
            f"Unknown Window Dates: {report.unknown_window_date_tasks} | "
            f"Duplicate Receipts Ignored: {report.duplicate_receipts_ignored} | "
            f"Conflicting Task IDs: {report.conflicting_task_ids}"
        ),
        "--------------------------------------------------------------------------------",
        "STRATA BREAKDOWN:",
    ]
    for s in report.strata:
        lines.append(
            f"  {s} ({STRATUM_LABELS.get(s, s)}): {report.tasks_by_stratum.get(s, 0)} tasks"
        )
    lines.extend(
        [
            "--------------------------------------------------------------------------------",
            "INDICATORS BY STRATUM:",
        ]
    )
    for m in report.metrics:
        if m.components is not None:
            val_str = json.dumps(m.components, ensure_ascii=False, sort_keys=True)
        else:
            val_str = str(m.value) if m.value is not None else "UNKNOWN"
        details = (
            f"num/den={m.numerator}/{m.denominator}"
            if m.numerator is not None
            else f"count={m.count}"
        )
        lines.append(
            f"  [{m.stratum}] {m.indicator}: status={m.status} val={val_str} "
            f"eligible={m.eligible_count} unknown={m.unknown_count} ({details})"
        )
    if report.unavailable_indicator_inputs:
        lines.extend(
            [
                "--------------------------------------------------------------------------------",
                f"UNAVAILABLE INPUTS ({len(report.unavailable_indicator_inputs)}):",
                "  " + ", ".join(report.unavailable_indicator_inputs),
            ]
        )
    lines.append("================================================================================")
    return "\n".join(lines)
