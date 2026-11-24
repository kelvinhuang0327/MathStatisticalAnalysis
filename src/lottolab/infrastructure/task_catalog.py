"""Read-only derivation of task catalog, stage manifests, and tombstones."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import lottolab
from lottolab.infrastructure.persistence.project_database_paths import canonical_project_root

HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")
EXCLUDED_STATUSES = frozenset({"RETAINED", "KEPT", "HELD", "PRESERVED"})
MAX_JSON_SIZE_BYTES = 20 * 1024 * 1024  # 20 MiB


def _is_hex64(val: object) -> bool:
    return isinstance(val, str) and bool(HEX_64_RE.match(val.lower()))


def _is_int(val: object) -> bool:
    return type(val) is int


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
                                deleted_at=node_deleted_at,
                                deleted_at_source=node_deleted_at_source,
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
            if (rt.deleted_at_source == "RECORD" and rec.deleted_at_source != "RECORD") or (
                rec.deleted_at is None and rt.deleted_at is not None
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
