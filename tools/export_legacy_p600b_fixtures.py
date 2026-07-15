"""Export P600B metadata fixtures by statically parsing pinned legacy source."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import cast

PINNED_LEGACY_COMMIT = "520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f"
P541F_SOURCE_COMMIT = "915cf6b0d42ee85bc00fe5d1e171879c5652af50"
REGISTRY_SOURCE = Path("lottery_api/models/replay_strategy_registry.py")
TARGET_IDS = (
    "biglotto_social_wisdom_anti_popularity",
    "biglotto_zone_split_3bet_bet1",
)
EXPECTED_METADATA: dict[str, dict[str, object]] = {
    "biglotto_social_wisdom_anti_popularity": {
        "strategy_id": "biglotto_social_wisdom_anti_popularity",
        "strategy_name": "大樂透 Social Wisdom Anti-Popularity",
        "strategy_version": "v0.1",
        "supported_lottery_types": ["BIG_LOTTO"],
        "min_history": 1,
        "lifecycle_status": "OBSERVATION",
    },
    "biglotto_zone_split_3bet_bet1": {
        "strategy_id": "biglotto_zone_split_3bet_bet1",
        "strategy_name": "大樂透 Zone Split 3注（Replay Bet 1）",  # noqa: RUF001
        "strategy_version": "v0.1",
        "supported_lottery_types": ["BIG_LOTTO"],
        "min_history": 1,
        "lifecycle_status": "OBSERVATION",
    },
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def _git(root: Path, *arguments: str) -> str:
    environment = dict(os.environ)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return result.stdout.strip()


def _assignment_value(tree: ast.Module, target_name: str) -> ast.expr:
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == target_name
                for target in statement.targets
            ):
                return statement.value
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == target_name
            and statement.value is not None
        ):
            return statement.value
    raise RuntimeError(f"legacy assignment not found: {target_name}")


def _literal_keywords(call: ast.Call) -> dict[str, object]:
    values: dict[str, object] = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            raise RuntimeError("legacy lifecycle stub uses unsupported **kwargs")
        values[keyword.arg] = cast(object, ast.literal_eval(keyword.value))
    return values


def _require_string(values: dict[str, object], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str):
        raise RuntimeError(f"legacy lifecycle stub has invalid {name}: {value!r}")
    return value


def _require_string_list(values: dict[str, object], name: str) -> list[str]:
    value = values.get(name)
    if not isinstance(value, list):
        raise RuntimeError(f"legacy lifecycle stub has invalid {name}: {value!r}")
    items = cast(list[object], value)
    if not all(isinstance(item, str) for item in items):
        raise RuntimeError(f"legacy lifecycle stub has invalid {name}: {value!r}")
    return [cast(str, item) for item in items]


def _require_positive_int(values: dict[str, object], name: str, default: int) -> int:
    value = values.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RuntimeError(f"legacy lifecycle stub has invalid {name}: {value!r}")
    return value


def _extract_metadata(registry_path: Path) -> list[dict[str, object]]:
    tree = ast.parse(registry_path.read_text(encoding="utf-8"), filename=str(registry_path))
    assignment = _assignment_value(tree, "_NON_EXECUTABLE_STUBS")
    if not isinstance(assignment, (ast.List, ast.Tuple)):
        raise RuntimeError("legacy _NON_EXECUTABLE_STUBS is not a literal sequence")

    selected: list[dict[str, object]] = []
    for element in assignment.elts:
        if not (
            isinstance(element, ast.Call)
            and isinstance(element.func, ast.Name)
            and element.func.id == "_LifecycleStub"
        ):
            raise RuntimeError("legacy non-executable registry contains a non-stub expression")
        values = _literal_keywords(element)
        strategy_id = _require_string(values, "strategy_id")
        if strategy_id not in TARGET_IDS:
            continue
        record: dict[str, object] = {
            "strategy_id": strategy_id,
            "strategy_name": _require_string(values, "strategy_name"),
            "strategy_version": _require_string(values, "strategy_version"),
            "supported_lottery_types": _require_string_list(
                values, "supported_lottery_types"
            ),
            "min_history": _require_positive_int(values, "min_history", 100),
            "lifecycle_status": _require_string(values, "status"),
        }
        if record != EXPECTED_METADATA[strategy_id]:
            raise RuntimeError(f"pinned legacy metadata mismatch for {strategy_id}: {record!r}")
        selected.append(record)

    if [record["strategy_id"] for record in selected] != list(TARGET_IDS):
        raise RuntimeError("pinned legacy target ordering or membership changed")
    return selected


def _canonical_files(metadata: list[dict[str, object]]) -> dict[str, bytes]:
    catalog = [
        {
            "strategy_id": record["strategy_id"],
            "strategy_name": record["strategy_name"],
            "version": record["strategy_version"],
            "lottery_types": record["supported_lottery_types"],
            "lifecycle_status": record["lifecycle_status"],
            "executable": False,
        }
        for record in metadata
    ]
    lifecycle = {
        "legacy_contract": "GET /api/replay/strategy-lifecycle (filtered P600B subset)",
        "ordering": "legacy _ALL_ADAPTERS insertion order filtered to TARGET_IDS",
        "strategies": [
            {
                "strategy_id": record["strategy_id"],
                "strategy_name": record["strategy_name"],
                "strategy_version": record["strategy_version"],
                "supported_lottery_types": record["supported_lottery_types"],
                "min_history": record["min_history"],
                "lifecycle_status": record["lifecycle_status"],
                "is_executable": False,
            }
            for record in metadata
        ],
        "executable_strategy_ids": [],
        "non_executable_strategy_ids": list(TARGET_IDS),
    }
    return {
        "strategy_catalog.json": _json_bytes(catalog),
        "lifecycle_metadata.json": _json_bytes(lifecycle),
    }


def _aggregate_digest(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(files[name])
    return digest.hexdigest()


def _run_hashes(files: dict[str, bytes]) -> dict[str, object]:
    return {
        "files": {
            name: {"sha256": _sha256_bytes(data), "bytes": len(data)}
            for name, data in files.items()
        },
        "aggregate_sha256": _aggregate_digest(files),
    }


def _read_run(directory: Path, names: tuple[str, ...]) -> dict[str, bytes]:
    return {name: (directory / name).read_bytes() for name in names}


def export_fixtures(
    *,
    legacy_root: Path,
    output_dir: Path,
    verification_dirs: list[Path],
    write_manifest: bool,
) -> dict[str, object] | None:
    legacy_root = legacy_root.resolve()
    output_dir = output_dir.resolve()
    try:
        output_dir.relative_to(legacy_root)
    except ValueError:
        pass
    else:
        raise ValueError("fixture output must be outside the legacy clone")

    if _git(legacy_root, "rev-parse", "HEAD") != PINNED_LEGACY_COMMIT:
        raise ValueError("legacy clone does not match the P600B pin")
    if _git(legacy_root, "status", "--porcelain"):
        raise ValueError("legacy clone must be clean")

    registry_path = legacy_root / REGISTRY_SOURCE
    metadata = _extract_metadata(registry_path)
    files = _canonical_files(metadata)
    file_names = tuple(files)
    verified_runs: list[dict[str, object]] = []
    for index, directory in enumerate(verification_dirs, start=1):
        candidate_files = _read_run(directory.resolve(), file_names)
        if candidate_files != files:
            raise RuntimeError(f"fixture run {index} is not byte reproducible")
        verified_runs.append({"run": index, **_run_hashes(candidate_files)})
    if write_manifest and len(verified_runs) != 2:
        raise ValueError("manifest mode requires exactly two verification runs")

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (output_dir / name).write_bytes(data)
    if not write_manifest:
        return None

    requirements_path = legacy_root / "lottery_api" / "requirements.txt"
    exporter_path = Path(__file__).resolve()
    canonical_hashes = _run_hashes(files)
    manifest: dict[str, object] = {
        "schema_version": 2,
        "purpose": "LottoLab P600B DB-free migration parity fixtures",
        "legacy_commit": PINNED_LEGACY_COMMIT,
        "p541f_source_commit": P541F_SOURCE_COMMIT,
        "source_paths": [REGISTRY_SOURCE.as_posix()],
        "source_sha256": {REGISTRY_SOURCE.as_posix(): _sha256_file(registry_path)},
        "extraction": {
            "method": (
                "Python ast.parse/ast.literal_eval of _NON_EXECUTABLE_STUBS "
                "_LifecycleStub keyword literals"
            ),
            "legacy_module_imported": False,
            "legacy_runtime_executed": False,
            "prediction_adapters_executed": False,
            "database_access": "NONE",
            "database_arguments_or_path_resolution": False,
            "writes": "explicit output directories only",
        },
        "runtime": {
            "python_version": platform.python_version(),
            "dependency_lock": None,
            "dependency_lock_status": "ABSENT_AT_PIN",
            "requirements_sha256": (
                _sha256_file(requirements_path) if requirements_path.is_file() else None
            ),
            "dependency_install_performed": False,
        },
        "scope": {
            "strategy_ids": list(TARGET_IDS),
            "excluded": [
                "database and snapshots",
                "prediction algorithms",
                "replay execution",
                "evaluation",
                "research artifacts",
                "ONLINE adapter execution",
            ],
        },
        "canonicalization_rules": [
            "filter _NON_EXECUTABLE_STUBS to TARGET_IDS",
            "preserve pinned legacy declaration order (Social Wisdom then Zone Split)",
            "emit object keys in declared schema order",
            "UTF-8 JSON, two-space indentation, trailing newline",
        ],
        "byte_exact_files": list(file_names),
        "canonical_output": canonical_hashes,
        "verification_runs": verified_runs,
        "two_run_reproducibility": {
            "result": "PASS",
            "canonical_aggregate_sha256": canonical_hashes["aggregate_sha256"],
        },
        "exporter": {
            "path": "tools/export_legacy_p600b_fixtures.py",
            "sha256": _sha256_file(exporter_path),
        },
    }
    (output_dir / "manifest.json").write_bytes(_json_bytes(manifest))
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-run-dir", type=Path, action="append", default=[])
    parser.add_argument("--write-manifest", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = export_fixtures(
        legacy_root=args.legacy_root,
        output_dir=args.output_dir,
        verification_dirs=cast(list[Path], args.verify_run_dir),
        write_manifest=args.write_manifest,
    )
    if manifest is None:
        print(f"P600B_DB_FREE_FIXTURE_EXPORT_PASS output={args.output_dir}")
    else:
        reproducibility = cast(dict[str, object], manifest["two_run_reproducibility"])
        print(
            "P600B_DB_FREE_FIXTURE_REPRODUCIBILITY_PASS "
            f"aggregate_sha256={reproducibility['canonical_aggregate_sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
