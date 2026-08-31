"""Closed R2 replay contracts. Importing this module never imports LottoLab.

The coordinator must not inherit an editable installation's strategy code.
The small stdlib-only LCJ-1 codec below is checked against the repository codec
in tests; only the separately anchored child imports the frozen application.
Builders and readers use the same strict, recursively closed contracts. A
valid self hash alone is never sufficient to admit a document.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from fractions import Fraction
from pathlib import PurePosixPath
from typing import Any, cast

PROTOCOL = "NEXT_DRAW_54_REACHABLE_FULL_REPLAY_PROTOCOL_R2"
SUPERSEDED = (
    "NEXT_DRAW_54_REACHABLE_FULL_REPLAY_PROTOCOL_R1",
    "NEXT_DRAW_REPLAY_STRATEGY_ISOLATED_MANIFEST_SEED_V1",
)
HEAD = "ba2f88f2622c278b358b2513bac3369196399439"
TREE = "9fed7b2e1f258fd7c80efbfa74d75d2000b16d04"
CATALOG_BLOB = "0c44bededa43ae9cad5cde7fc412424ffcde7560"
CATALOG_SHA256 = "8e3a7a60b9c5b25bbf0c71bfa3a158bdd7ee40e11ab7dd6ef43d5bef9c83a448"
LOCK_SHA256 = "1566430ccbfeca9dc0613c58a743c7684a0648b466ede6d3fc7763c4a5a7ead8"
ORDER_SHA256 = "1efeba5519693c58f1b407f859d5b37f54647efcd4a34b424b9eed71ff7c9493"
UNIVERSE_SHA256 = "02cf7c5403e4714416824ae1a71ef7478a4a975ff973b7f237f9992b6f9dd0a9"
RNG_SHA256 = "cda9f5ff34784da35ef762425d1e5e6b3539a20e6bdd5fcad82bbb10f92c86d7"
EXCLUDED = "legacy_biglotto__zone_momentum_predict__9e89f2b41add"
TARGET_COUNT = 800
STRATEGY_COUNT = 54
PLAN_SCHEMA = "NEXT_DRAW_54_REPLAY_PLAN_MANIFEST_V2"
RUN_SCHEMA = "NEXT_DRAW_54_REPLAY_RUN_MANIFEST_V2"
ACCEPTANCE_SCHEMA = "NEXT_DRAW_54_REPLAY_ACCEPTANCE_MANIFEST_V2"
CHILD_SCHEMA = "NEXT_DRAW_54_REPLAY_CHILD_RESULT_V2"
CANONICALIZATION = "LCJ-1"
SEED_TIMING = "POST_IMPORT_CATALOG_ADAPTER_CONSTRUCTION_PRE_TARGET_1"
GLOBAL_POLICY = "PER_STRATEGY_STDLIB_MODULE_GLOBAL_RANDOM_CONTINUOUS_800_TARGET_STREAM"
SEED_POLICY = "MANIFEST_BOUND_PER_STRATEGY_SHA256"
PRIVATE_POLICY = "PRIVATE_RNG_SOURCE_SEMANTICS_PRESERVED_EXACTLY"
PROCESS_MODEL = "ONE_PROCESS_PER_STRATEGY"
CACHE_POLICY = "NO_REPLAY_RESULT_CACHE"
RESTART = "ENTIRE_STRATEGY_PROCESS"
TARGET_ORDER = "BOUND_800_VECTOR_OLDEST_FIRST"
REAL_DATA = "SEALED_READ_ONLY_DB"
SYNTHETIC_DATA = "SYNTHETIC_TEST_ONLY"
EVALUATOR_VERSION = "base_method_evaluation/1.0.0"
WINDOW_ORDER = ["WINDOW_50", "WINDOW_300", "WINDOW_750", "FULL_HISTORY"]
WINDOW_SIZES = [
    ("WINDOW_50", 50),
    ("WINDOW_300", 300),
    ("WINDOW_750", 750),
    ("FULL_HISTORY", 800),
]
PRIVATE_IDS = (
    "biglotto_zone_split_3bet_bet1",
    "biglotto_zone_split_3bet_bet2",
    "biglotto_zone_split_3bet_bet3",
    "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8",
    "legacy_biglotto__test_dms_biglotto__10e39919c3a1",
)
RUNNER_PATHS = (
    "tools/next_draw_54_replay_r2.py",
    "tools/next_draw_54_replay_r2_lib.py",
    "tools/next_draw_54_replay_r2_runtime.py",
)
GLOBAL_IDS = (
    "legacy_biglotto__frontend_number_pairs_strategy__72ebb17b5a96",
    "legacy_biglotto__frontend_monte_carlo_strategy__9d8fe030546e",
    "legacy_biglotto__frontend_statistical_analysis_strategy__a9364825de2a",
    "legacy_biglotto__frontend_wheeling_strategy__ce978baff05b",
    "legacy_biglotto__frontend_unified_ensemble_weighted__8f1183a9d8a7",
    "legacy_biglotto__frontend_unified_ensemble_advanced__8f1183a9d8a7",
    "legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
    "legacy_biglotto__frontend_ml_forest__3a4324bc2aa9",
    "legacy_biglotto__frontend_ml_genetic__3a4324bc2aa9",
    "legacy_biglotto__frontend_collaborative_hybrid__97d79db161ba",
    "legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6",
)
ENVIRONMENT = {
    "PYTHONHASHSEED": "0",
    "PYTHONUTF8": "1",
    "TZ": "UTC",
    "LC_ALL": "C.UTF-8",
    "LANG": "C.UTF-8",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
}
EXECUTION = {
    "process_model": PROCESS_MODEL,
    "launch_method": "POSIX_SPAWN_EXEC",
    "strategies_per_child": 1,
    "targets_per_child": TARGET_COUNT,
    "replay_calls_per_child": 1,
    "seed_timing": SEED_TIMING,
    "global_random_policy": GLOBAL_POLICY,
    "cache_policy": CACHE_POLICY,
    "cache_configured": False,
    "strategy_parallelization": "SERIAL_ONLY",
    "max_concurrency": 1,
    "failure_restart_boundary": RESTART,
    "checkpoint_resume": False,
    "cell_retry": False,
    "nested_parallelism": False,
    "maximum_history_draws": "NONE",
    "minimum_history_draws": "DESCRIPTOR_MIN_HISTORY",
    "preflight_all_cells": True,
    "old_84_reuse": False,
}
EVALUATION = {
    "metric_contract": "M3_PLUS",
    "evaluator_version": EVALUATOR_VERSION,
    "window_order": WINDOW_ORDER,
    "random_reference": {"numerator": "4654", "denominator": "249711"},
}
RULE = {
    "lottery_type": "BIG_LOTTO",
    "main_number_count": 6,
    "main_number_min": 1,
    "main_number_max": 49,
    "main_numbers_unique": True,
    "special_number_count": 1,
    "special_number_min": 1,
    "special_number_max": 49,
    "main_special_overlap": False,
}
CACHE_ZERO = {
    "cache_configured": False,
    "lookups": 0,
    "stores": 0,
    "hits": 0,
    "misses": 0,
    "entries": 0,
    "evictions": 0,
}
IDENTITY_FIELDS = (
    "strategy_id strategy_version adapter_path min_history native_ticket_count response_shape"
)
PLAN_FIELDS = (
    "manifest_schema_version canonicalization_version protocol_version plan_manifest_sha256 "
    "common_manifest common_manifest_sha256 authority dataset targets strategies rng "
    "runtime_fingerprint runtime_fingerprint_sha256 execution evaluation"
)
RUN_FIELDS = (
    "manifest_schema_version canonicalization_version protocol_version run_manifest_sha256 "
    "plan_manifest_sha256 common_manifest_sha256 campaign_label operational_envelope "
    "deterministic_payload deterministic_payload_sha256"
)
ACCEPTANCE_FIELDS = (
    "manifest_schema_version canonicalization_version protocol_version acceptance_manifest_sha256 "
    "plan_manifest_sha256 common_manifest_sha256 run_a_manifest_file_sha256 "
    "run_b_manifest_file_sha256 run_a_deterministic_payload_sha256 "
    "run_b_deterministic_payload_sha256 comparison_contract comparison_results "
    "old_84_reuse_attestation final_status"
)
CHILD_FIELDS = "child_result_schema_version result bootstrap_before_sha256 bootstrap_after_sha256"
_KEY = re.compile(r"[a-z][a-z0-9_]*\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class ProtocolError(ValueError):
    """A closed protocol invariant failed; partial work is not acceptable."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProtocolError(message)


def _domain(value: Any) -> None:
    if type(value) in (str, bool):
        return
    if type(value) is int:
        require(abs(value) <= 9007199254740991, "LCJ-1 integer out of range")
    elif type(value) in (list, tuple):
        for item in cast(Sequence[Any], value):
            _domain(item)
    elif type(value) is dict:
        for key, item in cast(dict[Any, Any], value).items():
            require(type(key) is str and _KEY.fullmatch(key) is not None, "LCJ-1 object key")
            _domain(item)
    else:
        raise ProtocolError("LCJ-1 forbids null, floats, NaN/Infinity and non-JSON values")


def canonical_bytes(value: Any) -> bytes:
    _domain(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    except UnicodeError as exc:
        raise ProtocolError("LCJ-1 invalid UTF-8 string") from exc


def file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(value: Any) -> str:
    return sha256(canonical_bytes(value))


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def parse_file(raw: bytes) -> dict[str, Any]:
    require(
        raw.endswith(b"\n") and raw.count(b"\n") == 1 and b"\r" not in raw,
        "canonical file requires exactly one LF",
    )
    require(not raw.startswith(b"\xef\xbb\xbf"), "BOM forbidden")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (ValueError, UnicodeError) as exc:
        raise ProtocolError("invalid canonical JSON file") from exc
    require(type(value) is dict, "manifest must be an object")
    require(file_bytes(value) == raw, "noncanonical bytes or trailing bytes")
    return cast(dict[str, Any], value)


def fields(value: Any, names: str, label: str) -> dict[str, Any]:
    require(type(value) is dict, f"{label}: expected object")
    expected = set(names.split())
    require(set(value) == expected, f"{label}: unknown or missing fields")
    return cast(dict[str, Any], value)


def array(value: Any, label: str) -> list[Any]:
    require(type(value) is list, f"{label}: expected array")
    return cast(list[Any], value)


def string(value: Any, label: str, *, empty: bool = False) -> str:
    require(
        type(value) is str and (empty or bool(value)) and "\x00" not in value,
        f"{label}: expected NUL-free string",
    )
    return cast(str, value)


def integer(value: Any, label: str, *, minimum: int = 0) -> int:
    require(
        type(value) is int and minimum <= value <= 9007199254740991,
        f"{label}: expected integer >= {minimum}",
    )
    return cast(int, value)


def hex_digest(value: Any, label: str) -> str:
    require(type(value) is str and _SHA.fullmatch(value) is not None, f"{label}: SHA-256")
    return cast(str, value)


def equal(actual: Any, expected: Any, label: str) -> None:
    require(canonical_bytes(actual) == canonical_bytes(expected), f"{label}: mismatch")


def seal(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    result = {k: v for k, v in payload.items() if k != key}
    result[key] = digest(result)
    return result


def check_seal(payload: dict[str, Any], key: str) -> None:
    hex_digest(payload.get(key), key)
    equal(payload[key], digest({k: v for k, v in payload.items() if k != key}), key)


def protocol(value: Any) -> None:
    require(value == PROTOCOL, "only R2 is accepted; R1/V1 and hybrid protocols are forbidden")


def rng_class(strategy_id: str) -> str:
    if strategy_id in PRIVATE_IDS:
        return "ADAPTER_LOCAL_DETERMINISTIC_RNG"
    return "PROCESS_GLOBAL_PYTHON_RANDOM" if strategy_id in GLOBAL_IDS else "NO_RNG"


def private_exceptions() -> list[dict[str, str]]:
    return [
        {
            "strategy_id": sid,
            "policy": (
                "DONOR_HISTORY_JSON_SHA256_PRIVATE_RANDOM_THREE_SEQUENTIAL_SAMPLES"
                if index < 3
                else "PRIVATE_RANDOM_LEN_HISTORY_EVERY_TRANSITIVE_INVOCATION"
            ),
        }
        for index, sid in enumerate(PRIVATE_IDS)
    ]


def strategy_manifest(raw_catalog: bytes) -> dict[str, Any]:
    """Read the pinned declaration using AST only; never instantiate an adapter."""
    equal(sha256(raw_catalog), CATALOG_SHA256, "catalog source")
    module = ast.parse(raw_catalog)
    declaration = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_PRODUCTION_DESCRIPTORS"
            for target in node.targets
        )
    )
    require(isinstance(declaration.value, ast.Tuple), "catalog declaration")
    records: list[dict[str, Any]] = []
    names: list[dict[str, str]] = []
    excluded: dict[str, Any] = {}
    for expression in cast(ast.Tuple, declaration.value).elts:
        require(isinstance(expression, ast.Call), "catalog descriptor call")
        kw = {item.arg: item.value for item in cast(ast.Call, expression).keywords}
        lotteries = cast(ast.Tuple, kw["lottery_types"])
        if not any(
            isinstance(item, ast.Attribute) and item.attr == "BIG_LOTTO" for item in lotteries.elts
        ):
            continue
        if cast(ast.Attribute, kw["lifecycle_status"]).attr != "ONLINE":
            continue
        if ast.literal_eval(kw["executable"]) is not True:
            continue
        shape = (
            cast(ast.Attribute, kw["response_shape"]).attr
            if "response_shape" in kw
            else ("SINGLE_TICKET")
        )
        native = ast.literal_eval(kw["native_ticket_count"]) if "native_ticket_count" in kw else 1
        if shape != "SINGLE_TICKET" or native != 1:
            continue
        sid = ast.literal_eval(kw["strategy_id"])
        name = ast.literal_eval(kw["strategy_name"])
        if sid == EXCLUDED:
            excluded = {
                "strategy_id": sid,
                "strategy_name": name,
                "filtered_catalog_ordinal": len(records) + 1,
                "status": "DRIVER_ERROR",
                "windows": [],
            }
            continue
        records.append(
            {
                "strategy_id": sid,
                "strategy_version": ast.literal_eval(kw["version"]),
                "adapter_path": ast.literal_eval(kw["adapter_path"]),
                "min_history": ast.literal_eval(kw["min_history"]),
                "native_ticket_count": native,
                "response_shape": shape,
            }
        )
        names.append({"strategy_id": sid, "strategy_name": name})
    classifications = [
        {
            "strategy_id": r["strategy_id"],
            "strategy_version": r["strategy_version"],
            "rng_class": rng_class(r["strategy_id"]),
        }
        for r in records
    ]
    result = {
        "count": len(records),
        "records": records,
        "names": names,
        "excluded": excluded,
        "strategy_order_sha256": digest([r["strategy_id"] for r in records]),
        "strategy_universe_sha256": digest(records),
        "rng_classification": classifications,
        "rng_classification_sha256": digest(classifications),
    }
    validate_strategies(result)
    return result


def validate_strategies(value: Any) -> None:
    s = fields(
        value,
        "count records names excluded strategy_order_sha256 "
        "strategy_universe_sha256 rng_classification rng_classification_sha256",
        "strategies",
    )
    equal(s["count"], STRATEGY_COUNT, "strategy count")
    rows = array(s["records"], "strategy records")
    require(len(rows) == STRATEGY_COUNT, "exactly 54 strategies required")
    for row in rows:
        fields(row, IDENTITY_FIELDS, "strategy identity")
        for key in ("strategy_id", "strategy_version", "adapter_path"):
            string(row[key], key)
        integer(row["min_history"], "min_history", minimum=1)
        equal(row["native_ticket_count"], 1, "native ticket count")
        equal(row["response_shape"], "SINGLE_TICKET", "response shape")
    equal(digest([r["strategy_id"] for r in rows]), ORDER_SHA256, "frozen strategy order")
    equal(digest(rows), UNIVERSE_SHA256, "frozen strategy universe")
    equal(s["strategy_order_sha256"], ORDER_SHA256, "strategy order hash")
    equal(s["strategy_universe_sha256"], UNIVERSE_SHA256, "strategy universe hash")
    classifications = [
        {
            "strategy_id": r["strategy_id"],
            "strategy_version": r["strategy_version"],
            "rng_class": rng_class(r["strategy_id"]),
        }
        for r in rows
    ]
    equal(s["rng_classification"], classifications, "RNG classifications")
    equal(digest(classifications), RNG_SHA256, "frozen RNG classification hash")
    equal(s["rng_classification_sha256"], RNG_SHA256, "RNG classification hash")
    names = array(s["names"], "strategy names")
    require(len(names) == STRATEGY_COUNT, "strategy names count")
    for name, row in zip(names, rows, strict=True):
        fields(name, "strategy_id strategy_name", "strategy name")
        equal(name["strategy_id"], row["strategy_id"], "strategy name order")
        string(name["strategy_name"], "strategy_name")
    excluded = fields(
        s["excluded"],
        "strategy_id strategy_name filtered_catalog_ordinal status windows",
        "excluded strategy",
    )
    equal(excluded["strategy_id"], EXCLUDED, "exact zone exclusion")
    equal(excluded["filtered_catalog_ordinal"], 19, "zone ordinal")
    equal(excluded["status"], "DRIVER_ERROR", "zone status")
    equal(excluded["windows"], [], "zone windows")
    string(excluded["strategy_name"], "excluded strategy_name")


def validate_inventory(value: Any, *, git: bool = False) -> None:
    rows = array(value, "file inventory")
    require(bool(rows), "empty file inventory")
    paths: list[str] = []
    for row in rows:
        fields(row, "path sha256 git_blob mode" if git else "path sha256", "file inventory row")
        path = string(row["path"], "inventory path")
        require(
            not PurePosixPath(path).is_absolute() and ".." not in PurePosixPath(path).parts,
            "inventory path must be relative and contained",
        )
        paths.append(path)
        hex_digest(row["sha256"], "inventory file hash")
        if git:
            require(re.fullmatch(r"[0-9a-f]{40}", row["git_blob"]) is not None, "Git blob hash")
            require(row["mode"] in ("100644", "100755"), "Git mode must be regular file")
    require(paths == sorted(set(paths)), "file inventory must be unique and sorted")


def validate_authority(value: Any) -> None:
    a = fields(
        value,
        "repository_head repository_tree catalog_git_blob catalog_sha256 "
        "uv_lock_sha256 load_bearing_blobs source_inventory_sha256",
        "authority",
    )
    for key, expected in (
        ("repository_head", HEAD),
        ("repository_tree", TREE),
        ("catalog_git_blob", CATALOG_BLOB),
        ("catalog_sha256", CATALOG_SHA256),
        ("uv_lock_sha256", LOCK_SHA256),
    ):
        equal(a[key], expected, key)
    validate_inventory(a["load_bearing_blobs"], git=True)
    equal(a["source_inventory_sha256"], digest(a["load_bearing_blobs"]), "source inventory")
    lookup = {r["path"]: r for r in a["load_bearing_blobs"]}
    require(
        "src/lottolab/strategies/catalog.py" in lookup and "uv.lock" in lookup,
        "source inventory lacks catalog/lock",
    )
    equal(lookup["src/lottolab/strategies/catalog.py"]["git_blob"], CATALOG_BLOB, "catalog blob")
    equal(lookup["src/lottolab/strategies/catalog.py"]["sha256"], CATALOG_SHA256, "catalog SHA")
    equal(lookup["uv.lock"]["sha256"], LOCK_SHA256, "lock SHA")


def validate_runtime(value: Any) -> None:
    r = fields(
        value,
        "schema_version python platform numeric distributions installer environment "
        "source_inventory_sha256 runner_files",
        "runtime fingerprint",
    )
    equal(r["schema_version"], "NEXT_DRAW_54_REPLAY_RUNTIME_V2", "runtime schema")
    p = fields(
        r["python"],
        "version version_info hexversion implementation cache_tag abiflags "
        "soabi build compiler executable_sha256 runtime_bundle_sha256 "
        "runtime_bundle_files stdlib_random_sha256 rng_state_version",
        "Python fingerprint",
    )
    vi = array(p["version_info"], "version_info")
    require(len(vi) == 5 and vi[:2] == [3, 13], "CPython 3.13 exact build required")
    for index in (0, 1, 2, 4):
        integer(vi[index], "Python version component")
    string(vi[3], "Python release level")
    equal(p["implementation"], "cpython", "Python implementation")
    equal(p["rng_state_version"], 3, "random state version")
    integer(p["hexversion"], "hexversion", minimum=1)
    for key in ("version", "cache_tag", "soabi", "compiler"):
        string(p[key], key)
    string(p["abiflags"], "abiflags", empty=True)
    require(len(array(p["build"], "Python build")) == 2, "Python build pair")
    for part in p["build"]:
        string(part, "Python build")
    for key in ("executable_sha256", "runtime_bundle_sha256", "stdlib_random_sha256"):
        hex_digest(p[key], key)
    validate_inventory(p["runtime_bundle_files"])
    equal(p["runtime_bundle_sha256"], digest(p["runtime_bundle_files"]), "runtime bundle")
    plat = fields(
        r["platform"],
        "system release version machine processor cpu_model cpu_features "
        "byteorder pointer_bits libc macos_version",
        "platform",
    )
    for key in ("system", "release", "version", "machine", "processor", "cpu_model"):
        string(plat[key], key)
    require(plat["byteorder"] in ("little", "big"), "byte order")
    equal(plat["pointer_bits"], 64, "pointer width")
    require(bool(array(plat["cpu_features"], "CPU features")), "CPU features unavailable")
    for item in plat["cpu_features"]:
        string(item, "CPU feature")
    require(plat["cpu_features"] == sorted(set(plat["cpu_features"])), "CPU feature order")
    for key in ("libc", "macos_version"):
        string(plat[key], key, empty=True)
    require(bool(plat["libc"] or plat["macos_version"]), "libc/macOS identity unavailable")
    n = fields(r["numeric"], "float_info hash_info native_libraries blas", "numeric fingerprint")
    for key, members in (
        (
            "float_info",
            "max max_exp max_10_exp min min_exp min_10_exp dig mant_dig epsilon radix rounds",
        ),
        ("hash_info", "width modulus inf nan imag algorithm hash_bits seed_bits cutoff"),
    ):
        for item in fields(n[key], members, key).values():
            string(item, key)
    validate_inventory(n["native_libraries"])
    equal(n["blas"], "NOT_LOADED_FOR_FROZEN_STDLIB_STRATEGIES", "BLAS identity")
    distributions = array(r["distributions"], "installed distributions")
    ids: list[str] = []
    for distribution in distributions:
        d = fields(distribution, "name version installer files files_sha256", "distribution")
        ids.append(string(d["name"], "distribution name"))
        string(d["version"], "distribution version")
        string(d["installer"], "distribution installer")
        validate_inventory(d["files"])
        equal(d["files_sha256"], digest(d["files"]), "distribution source/wheel files")
    require(ids == sorted(set(ids)), "distribution inventory must be unique and sorted")
    installer = fields(r["installer"], "name version executable_sha256", "installer")
    equal(installer["name"], "uv", "installer name")
    string(installer["version"], "installer version")
    hex_digest(installer["executable_sha256"], "installer binary")
    equal(
        r["environment"],
        [{"name": k, "value": v} for k, v in sorted(ENVIRONMENT.items())],
        "pre-interpreter environment",
    )
    hex_digest(r["source_inventory_sha256"], "runtime source inventory")
    validate_inventory(r["runner_files"])
    equal(
        [row["path"] for row in r["runner_files"]],
        list(RUNNER_PATHS),
        "exact runner file inventory",
    )


def target_identity(row: Mapping[str, Any]) -> dict[str, Any]:
    return {"draw_date": row["draw_date"], "draw_number": row["draw_number"]}


def causal_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ("draw_date", "draw_number", "main_numbers", "special_number")}


def adapter_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {"draw": row["draw_number"], "date": row["draw_date"], "numbers": row["main_numbers"]}


def draw_key(row: Mapping[str, Any]) -> tuple[str, int]:
    return row["draw_date"], int(row["draw_number"])


def legal_ticket(value: Any) -> list[int]:
    ticket = array(value, "ticket")
    require(
        len(ticket) == 6 and all(type(n) is int and 1 <= n <= 49 for n in ticket),
        "ticket must contain six integers from 1 to 49",
    )
    require(len(set(ticket)) == 6, "ticket numbers must be unique")
    return cast(list[int], ticket)


def validate_snapshot(value: Any) -> list[dict[str, Any]]:
    s = fields(value, "snapshot_schema_version kind lottery_type draws", "dataset snapshot")
    equal(s["snapshot_schema_version"], "NEXT_DRAW_54_SOURCE_SNAPSHOT_V2", "snapshot schema")
    require(s["kind"] in (REAL_DATA, SYNTHETIC_DATA), "dataset kind")
    equal(s["lottery_type"], "BIG_LOTTO", "lottery")
    rows = array(s["draws"], "draws")
    require(len(rows) >= TARGET_COUNT, "insufficient source draw rows")
    ids: set[int] = set()
    numbers: set[str] = set()
    numeric_numbers: set[int] = set()
    for row in rows:
        fields(row, "source_row_id draw_date draw_number main_numbers special_number", "draw row")
        rid = integer(row["source_row_id"], "source row id", minimum=1)
        number = string(row["draw_number"], "draw number")
        require(number.isascii() and number.isdecimal() and int(number) > 0, "draw number format")
        require(
            rid not in ids and number not in numbers and int(number) not in numeric_numbers,
            "duplicate source row or target identity",
        )
        ids.add(rid)
        numbers.add(number)
        numeric_numbers.add(int(number))
        text = string(row["draw_date"], "draw date")
        try:
            equal(date.fromisoformat(text).isoformat(), text, "ISO draw date")
        except ValueError as exc:
            raise ProtocolError("invalid draw date") from exc
        legal_ticket(row["main_numbers"])
        special = integer(row["special_number"], "special number", minimum=1)
        require(special <= 49 and special not in row["main_numbers"], "illegal special number")
    require(rows == sorted(rows, key=draw_key), "snapshot causal rows must be oldest first")
    return cast(list[dict[str, Any]], rows)


def frozen_targets(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    # Deliberately TEXT order, exactly the pinned repository's page-1 query.
    newest = sorted(
        rows, key=lambda r: (r["draw_date"], r["draw_number"], r["source_row_id"]), reverse=True
    )[:TARGET_COUNT]
    return [target_identity(row) for row in reversed(newest)]


def dataset_manifest(snapshot: dict[str, Any], db_sha256: str, db_size: int) -> dict[str, Any]:
    validate_snapshot(snapshot)
    return {
        "dataset_id": "NEXT_DRAW_BIG_LOTTO_R2",
        "dataset_version": digest(snapshot),
        "snapshot": snapshot,
        "dataset_snapshot_sha256": digest(snapshot),
        "source_db": {
            "sha256": db_sha256,
            "size_bytes": db_size,
            "read_only": True,
            "sqlite_mode": "ro_immutable_no_wal",
        },
        "rule_contract": RULE,
        "rule_contract_sha256": digest(RULE),
    }


def validate_dataset(value: Any) -> list[dict[str, Any]]:
    d = fields(
        value,
        "dataset_id dataset_version snapshot dataset_snapshot_sha256 source_db "
        "rule_contract rule_contract_sha256",
        "dataset",
    )
    rows = validate_snapshot(d["snapshot"])
    equal(d["dataset_id"], "NEXT_DRAW_BIG_LOTTO_R2", "dataset id")
    equal(d["dataset_version"], digest(d["snapshot"]), "dataset version")
    equal(d["dataset_snapshot_sha256"], digest(d["snapshot"]), "dataset snapshot hash")
    equal(d["rule_contract"], RULE, "rule contract")
    equal(d["rule_contract_sha256"], digest(RULE), "rule contract hash")
    db = fields(d["source_db"], "sha256 size_bytes read_only sqlite_mode", "source DB")
    hex_digest(db["sha256"], "source DB hash")
    integer(db["size_bytes"], "source DB size", minimum=1)
    equal(db["read_only"], True, "source DB read-only")
    equal(db["sqlite_mode"], "ro_immutable_no_wal", "SQLite contract")
    return rows


def seed_record(
    common_hash: str, identity: Mapping[str, Any], *, token: str = PROTOCOL
) -> dict[str, Any]:
    protocol(token)
    hex_digest(common_hash, "common manifest hash")
    parts = [token, common_hash] + [
        string(identity[k], k) for k in ("strategy_id", "strategy_version", "adapter_path")
    ]
    require(all("\x00" not in p for p in parts), "NUL seed component")
    seed = sha256(b"\x00".join(p.encode("utf-8") for p in parts))
    return {
        "strategy_id": identity["strategy_id"],
        "strategy_version": identity["strategy_version"],
        "adapter_path": identity["adapter_path"],
        "seed_digest": seed,
        "seed_integer": str(int(seed, 16)),
    }


def common_manifest(
    dataset: Mapping[str, Any], target_hash: str, runtime_hash: str
) -> dict[str, Any]:
    return {
        "canonicalization_version": CANONICALIZATION,
        "protocol_version": PROTOCOL,
        "repository_head": HEAD,
        "repository_tree": TREE,
        "source_draw_db_sha256": dataset["source_db"]["sha256"],
        "dataset_snapshot_sha256": dataset["dataset_snapshot_sha256"],
        "target_count": TARGET_COUNT,
        "target_order_sha256": target_hash,
        "strategy_count": STRATEGY_COUNT,
        "strategy_order_sha256": ORDER_SHA256,
        "strategy_universe_sha256": UNIVERSE_SHA256,
        "rng_classification_sha256": RNG_SHA256,
        "runtime_fingerprint_sha256": runtime_hash,
        "process_model": PROCESS_MODEL,
        "seed_timing": SEED_TIMING,
        "global_random_policy": GLOBAL_POLICY,
        "cache_policy": CACHE_POLICY,
        "strategy_parallelization": "SERIAL_ONLY",
        "max_concurrency": 1,
        "failure_restart_boundary": RESTART,
        "metric_contract": "M3_PLUS",
        "window_order": WINDOW_ORDER,
        "excluded_strategy_id": EXCLUDED,
        "old_84_reuse": False,
    }


def make_plan(
    *,
    authority: dict[str, Any],
    dataset: dict[str, Any],
    strategies: dict[str, Any],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    rows = validate_dataset(dataset)
    targets = frozen_targets(rows)
    runtime_hash = digest(runtime)
    common = common_manifest(dataset, digest(targets), runtime_hash)
    common_hash = digest(common)
    result = seal(
        {
            "manifest_schema_version": PLAN_SCHEMA,
            "canonicalization_version": CANONICALIZATION,
            "protocol_version": PROTOCOL,
            "common_manifest": common,
            "common_manifest_sha256": common_hash,
            "authority": authority,
            "dataset": dataset,
            "targets": {
                "order": TARGET_ORDER,
                "count": TARGET_COUNT,
                "vector": targets,
                "target_order_sha256": digest(targets),
            },
            "strategies": strategies,
            "rng": {
                "seed_policy": SEED_POLICY,
                "seed_timing": SEED_TIMING,
                "global_random_policy": GLOBAL_POLICY,
                "private_rng_policy": PRIVATE_POLICY,
                "private_rng_exceptions": private_exceptions(),
                "seeds": [seed_record(common_hash, row) for row in strategies["records"]],
            },
            "runtime_fingerprint": runtime,
            "runtime_fingerprint_sha256": runtime_hash,
            "execution": EXECUTION,
            "evaluation": EVALUATION,
        },
        "plan_manifest_sha256",
    )
    validate_plan(result)
    return result


def validate_plan(plan: Any) -> dict[str, Any]:
    p = fields(plan, PLAN_FIELDS, "plan manifest")
    protocol(p["protocol_version"])
    equal(p["manifest_schema_version"], PLAN_SCHEMA, "plan schema")
    equal(p["canonicalization_version"], CANONICALIZATION, "canonicalization")
    check_seal(p, "plan_manifest_sha256")
    validate_authority(p["authority"])
    validate_runtime(p["runtime_fingerprint"])
    equal(
        p["runtime_fingerprint"]["source_inventory_sha256"],
        p["authority"]["source_inventory_sha256"],
        "runtime/source binding",
    )
    equal(p["runtime_fingerprint_sha256"], digest(p["runtime_fingerprint"]), "runtime hash")
    rows = validate_dataset(p["dataset"])
    validate_strategies(p["strategies"])
    t = fields(p["targets"], "order count vector target_order_sha256", "targets")
    equal(t["order"], TARGET_ORDER, "target order policy")
    equal(t["count"], TARGET_COUNT, "target count")
    equal(t["vector"], frozen_targets(rows), "exact frozen 800-target vector")
    equal(t["target_order_sha256"], digest(t["vector"]), "target vector hash")
    largest_minimum = max(r["min_history"] for r in p["strategies"]["records"])
    require(
        all(
            sum(draw_key(row) < draw_key(target) for row in rows) >= largest_minimum
            for target in t["vector"]
        ),
        "all 43,200 cells must be eligible before execution",
    )
    common = common_manifest(
        p["dataset"], t["target_order_sha256"], p["runtime_fingerprint_sha256"]
    )
    equal(p["common_manifest"], common, "closed common manifest")
    equal(p["common_manifest_sha256"], digest(common), "common manifest hash")
    equal(
        p["rng"],
        {
            "seed_policy": SEED_POLICY,
            "seed_timing": SEED_TIMING,
            "global_random_policy": GLOBAL_POLICY,
            "private_rng_policy": PRIVATE_POLICY,
            "private_rng_exceptions": private_exceptions(),
            "seeds": [seed_record(digest(common), row) for row in p["strategies"]["records"]],
        },
        "RNG contract and seeds",
    )
    equal(p["execution"], EXECUTION, "execution contract")
    equal(p["evaluation"], EVALUATION, "evaluation contract")
    return p


def child_identity(plan: Mapping[str, Any], strategy_ids: Any) -> dict[str, Any]:
    ids = array(strategy_ids, "child strategy_ids")
    require(len(ids) == 1, "exactly one strategy per child")
    require(ids[0] != EXCLUDED, "zone-momentum execution forbidden")
    matches = [r for r in plan["strategies"]["records"] if r["strategy_id"] == ids[0]]
    require(len(matches) == 1, "child strategy not in the frozen 54-strategy universe")
    return matches[0]


def target_contexts(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    """All hashes derive from the sealed snapshot; never requery targets mid-run."""
    rows = plan["dataset"]["snapshot"]["draws"]
    by_number = {r["draw_number"]: r for r in rows}
    result: list[dict[str, Any]] = []
    for target in plan["targets"]["vector"]:
        history = [r for r in rows if draw_key(r) < draw_key(target)]
        outcome = causal_row(by_number[target["draw_number"]])
        result.append(
            {
                "target": target,
                "outcome": outcome,
                "outcome_sha256": digest(outcome),
                "causal_history_count": len(history),
                "cutoff": target_identity(history[-1]),
                "causal_history_sha256": digest([causal_row(r) for r in history]),
                "adapter_input_sha256": digest([adapter_row(r) for r in history]),
            }
        )
    return result


def rng_state_digest(state: tuple[Any, ...]) -> str:
    require(
        len(state) == 3 and state[0] == 3 and state[2] is None,
        "unclassified RNG state/version or Gaussian cache",
    )
    return digest({"state_version": 3, "mt19937_state": list(state[1]), "gaussian_cache": "NONE"})


def seeded_state_digest(seed: Mapping[str, Any]) -> str:
    import random

    # This independent private instance observes the expected initial state;
    # it never changes the module singleton or any donor's private instance.
    return rng_state_digest(random.Random(int(seed["seed_integer"])).getstate())


def snapshot_hash(
    plan: Mapping[str, Any],
    identity: Mapping[str, Any],
    context: Mapping[str, Any],
    ticket: list[int],
) -> str:
    name = next(
        n["strategy_name"]
        for n in plan["strategies"]["names"]
        if n["strategy_id"] == identity["strategy_id"]
    )
    return digest(
        {
            "snapshot_schema_version": "1.0.0",
            "dataset_id": plan["dataset"]["dataset_id"],
            "dataset_version": plan["dataset"]["dataset_version"],
            "lottery_type": "BIG_LOTTO",
            "source_mode": "TARGET_NATIVE",
            "target_draw_number": context["target"]["draw_number"],
            "target_draw_date": context["target"]["draw_date"],
            "cutoff_draw_number": context["cutoff"]["draw_number"],
            "cutoff_draw_date": context["cutoff"]["draw_date"],
            "strategy_id": identity["strategy_id"],
            "strategy_version": identity["strategy_version"],
            "adapter_strategy_id": identity["strategy_id"],
            "adapter_strategy_name": name,
            "adapter_strategy_version": identity["strategy_version"],
            "history_status": "OK",
            "causal_history_count": context["causal_history_count"],
            "causal_history_sha256": context["causal_history_sha256"],
            "prediction_status": "OK",
            "predicted_main_numbers": ticket,
        }
    )


def make_cell(
    plan: Mapping[str, Any],
    identity: Mapping[str, Any],
    context: Mapping[str, Any],
    emitted: list[int],
    legal: list[int],
    before: str,
    after: str,
) -> dict[str, Any]:
    legal_ticket(emitted)
    equal(legal, sorted(emitted), "emitted/legal ticket relationship")
    return seal(
        {
            **context,
            "strategy_id": identity["strategy_id"],
            "strategy_version": identity["strategy_version"],
            "history_status": "OK",
            "history_reason": "NONE",
            "prediction_status": "OK",
            "prediction_reason": "NONE",
            "emitted_ticket": emitted,
            "legal_ticket": legal,
            "hit_count": len(set(legal) & set(context["outcome"]["main_numbers"])),
            "rng_before_sha256": before,
            "rng_after_sha256": after,
            "replay_result_sha256": snapshot_hash(plan, identity, context, legal),
        },
        "cell_sha256",
    )


def validate_source_integrity(plan: Mapping[str, Any], value: Any) -> None:
    record = fields(
        value,
        "repository_head repository_tree source_inventory_sha256_before "
        "source_inventory_sha256_after source_draw_db_sha256_before "
        "source_draw_db_sha256_after import_anchor_verified imported_modules",
        "source integrity",
    )
    equal(record["repository_head"], HEAD, "child replay source HEAD")
    equal(record["repository_tree"], TREE, "child replay source tree")
    for when in ("before", "after"):
        equal(
            record[f"source_inventory_sha256_{when}"],
            plan["authority"]["source_inventory_sha256"],
            "child source integrity",
        )
        equal(
            record[f"source_draw_db_sha256_{when}"],
            plan["dataset"]["source_db"]["sha256"],
            "child DB integrity",
        )
    equal(record["import_anchor_verified"], True, "import anchor")
    modules = array(record["imported_modules"], "imported modules")
    inventory = {r["path"]: r["sha256"] for r in plan["authority"]["load_bearing_blobs"]}
    names: list[str] = []
    for module in modules:
        fields(module, "module path sha256", "import source record")
        name = string(module["module"], "module name")
        names.append(name)
        require(name == "lottolab" or name.startswith("lottolab."), "non-LottoLab source record")
        stem = "src/" + name.replace(".", "/")
        require(module["path"] in (stem + ".py", stem + "/__init__.py"), "module source mismatch")
        require(module["path"] in inventory, "module outside frozen inventory")
        equal(module["sha256"], inventory[module["path"]], "module source hash")
    require(names == sorted(set(names)), "import module inventory order")
    require(
        {
            "lottolab",
            "lottolab.strategies.catalog",
            "lottolab.application.use_cases.replay_historical_predictions",
        }.issubset(names),
        "incomplete import source evidence",
    )


def make_strategy_result(
    plan: Mapping[str, Any],
    identity: dict[str, Any],
    cells: list[dict[str, Any]],
    source_integrity: dict[str, Any],
    post_seed: str,
    final_rng: str,
) -> dict[str, Any]:
    return seal(
        {
            "result_schema_version": "NEXT_DRAW_54_STRATEGY_RESULT_V2",
            "strategy_identity": identity,
            "seed": seed_record(plan["common_manifest_sha256"], identity),
            "rng_class": rng_class(identity["strategy_id"]),
            # B0 contains OS entropy. Its two raw hashes belong to the operational
            # attempt; deterministic evidence is the checked equality predicate.
            "bootstrap_rng_guard": {"unchanged": True, "state_version": 3},
            "post_seed_rng_sha256": post_seed,
            "final_rng_sha256": final_rng,
            "adapter_invocation_count": len(cells),
            "cache": CACHE_ZERO,
            "source_integrity": source_integrity,
            "runtime_fingerprint_sha256": plan["runtime_fingerprint_sha256"],
            "cells": cells,
            "final_status": "COMPLETE",
        },
        "strategy_output_sha256",
    )


def make_child_result(
    result: dict[str, Any], bootstrap_before: str, bootstrap_after: str
) -> dict[str, Any]:
    """Close the one-strategy child stdout document before the coordinator sees it."""
    hex_digest(bootstrap_before, "bootstrap RNG before")
    hex_digest(bootstrap_after, "bootstrap RNG after")
    equal(bootstrap_before, bootstrap_after, "bootstrap RNG drift")
    return {
        "child_result_schema_version": CHILD_SCHEMA,
        "result": result,
        "bootstrap_before_sha256": bootstrap_before,
        "bootstrap_after_sha256": bootstrap_after,
    }


def validate_child_result(
    plan: Mapping[str, Any], identity: dict[str, Any], value: Any
) -> dict[str, Any]:
    child = fields(value, CHILD_FIELDS, "child result envelope")
    equal(child["child_result_schema_version"], CHILD_SCHEMA, "child result schema")
    before = hex_digest(child["bootstrap_before_sha256"], "bootstrap RNG before")
    after = hex_digest(child["bootstrap_after_sha256"], "bootstrap RNG after")
    equal(before, after, "bootstrap RNG drift")
    result = fields(
        child["result"],
        "result_schema_version strategy_identity seed rng_class bootstrap_rng_guard "
        "post_seed_rng_sha256 final_rng_sha256 adapter_invocation_count cache source_integrity "
        "runtime_fingerprint_sha256 cells final_status strategy_output_sha256",
        "child result",
    )
    validate_strategy_result(plan, identity, result, target_contexts(plan))
    return child


def validate_strategy_result(
    plan: Mapping[str, Any],
    identity: dict[str, Any],
    value: Any,
    contexts: Sequence[dict[str, Any]],
) -> None:
    r = fields(
        value,
        "result_schema_version strategy_identity seed rng_class bootstrap_rng_guard "
        "post_seed_rng_sha256 final_rng_sha256 adapter_invocation_count cache source_integrity "
        "runtime_fingerprint_sha256 cells final_status strategy_output_sha256",
        "child result",
    )
    equal(r["result_schema_version"], "NEXT_DRAW_54_STRATEGY_RESULT_V2", "child result schema")
    check_seal(r, "strategy_output_sha256")
    equal(r["strategy_identity"], identity, "child single strategy identity")
    equal(r["seed"], seed_record(plan["common_manifest_sha256"], identity), "child seed")
    equal(r["rng_class"], rng_class(identity["strategy_id"]), "child RNG classification")
    equal(r["bootstrap_rng_guard"], {"unchanged": True, "state_version": 3}, "bootstrap RNG drift")
    equal(r["post_seed_rng_sha256"], seeded_state_digest(r["seed"]), "post-seed RNG state")
    equal(r["adapter_invocation_count"], TARGET_COUNT, "800 adapter invocations")
    equal(r["cache"], CACHE_ZERO, "zero cache activity")
    validate_source_integrity(plan, r["source_integrity"])
    module = identity["adapter_path"].split(":")[0]
    require(
        module in {m["module"] for m in r["source_integrity"]["imported_modules"]},
        "selected adapter import missing",
    )
    equal(r["runtime_fingerprint_sha256"], plan["runtime_fingerprint_sha256"], "child runtime")
    equal(r["final_status"], "COMPLETE", "child completion")
    cells = array(r["cells"], "child cells")
    require(len(cells) == TARGET_COUNT and len(contexts) == TARGET_COUNT, "partial child output")
    previous = r["post_seed_rng_sha256"]
    for cell, context in zip(cells, contexts, strict=True):
        require(type(cell) is dict, "cell object required")
        hex_digest(cell.get("rng_after_sha256"), "cell RNG after")
        equal(cell.get("rng_before_sha256"), previous, "continuous RNG ledger")
        if r["rng_class"] != "PROCESS_GLOBAL_PYTHON_RANDOM":
            equal(
                cell["rng_after_sha256"], previous, "private/no-RNG global state must be unchanged"
            )
        expected = make_cell(
            plan,
            identity,
            context,
            cell.get("emitted_ticket"),
            cell.get("legal_ticket"),
            previous,
            cell["rng_after_sha256"],
        )
        equal(cell, expected, "closed cell, history/outcome, ticket, status and result hash")
        previous = cell["rng_after_sha256"]
    equal(r["final_rng_sha256"], previous, "terminal RNG state")


def _fraction(value: Fraction) -> dict[str, str]:
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def assemble_evaluation(
    plan: Mapping[str, Any], results: Sequence[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    evaluations: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    reference = Fraction(4654, 249711)
    for result, name in zip(results, plan["strategies"]["names"], strict=True):
        counts: list[dict[str, Any]] = []
        windows: list[dict[str, Any]] = []
        for label, size in WINDOW_SIZES:
            success = sum(cell["hit_count"] >= 3 for cell in result["cells"][-size:])
            rate = Fraction(success, size)
            counts.append(
                {
                    "window": label,
                    "success_count": success,
                    "eligible_draw_count": size,
                    "observed_value": _fraction(rate),
                }
            )
            windows.append(
                {
                    "window_kind": label,
                    "window_status": "COMPLETE",
                    "eligible_draw_count": size,
                    "observed_value": _fraction(rate),
                    "random_reference": _fraction(reference),
                    "delta_vs_random": _fraction(rate - reference),
                }
            )
        sid = result["strategy_identity"]["strategy_id"]
        evaluations.append({"strategy_id": sid, "windows": counts})
        records.append(
            {
                **name,
                "native_ticket_count": 1,
                "status": "EVALUATED",
                "hit_tier_id": "M3_PLUS",
                "windows": windows,
            }
        )
    excluded = plan["strategies"]["excluded"]
    records.insert(
        18,
        {
            "strategy_id": EXCLUDED,
            "strategy_name": excluded["strategy_name"],
            "native_ticket_count": 1,
            "status": "DRIVER_ERROR",
            "hit_tier_id": "M3_PLUS",
            "windows": [],
        },
    )
    snapshot = plan["dataset"]["snapshot"]
    artifact = seal(
        {
            "artifact_schema_version": "1.0.0",
            "evaluator_version": EVALUATOR_VERSION,
            "window_order": WINDOW_ORDER,
            "computation_status": (
                "FRESH_UNREVIEWED" if snapshot["kind"] == REAL_DATA else SYNTHETIC_DATA
            ),
            "lottery_type": "BIG_LOTTO",
            "source_draw_db_sha256": plan["dataset"]["source_db"]["sha256"],
            "source_draw_count": len(snapshot["draws"]),
            "last_causal_draw_id": plan["targets"]["vector"][-1]["draw_number"],
            "replay_depth": TARGET_COUNT,
            "hit_tier_id": "M3_PLUS",
            "records": records,
        },
        "artifact_sha256",
    )
    return evaluations, artifact


def deterministic_payload(plan: Mapping[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    require(len(results) == STRATEGY_COUNT, "exactly 54 complete strategy results required")
    contexts = target_contexts(plan)
    for identity, result in zip(plan["strategies"]["records"], results, strict=True):
        validate_strategy_result(plan, identity, result, contexts)
    matrix = [
        result["cells"][index]["cell_sha256"] for index in range(TARGET_COUNT) for result in results
    ]
    evaluations, artifact = assemble_evaluation(plan, results)
    return {
        "runtime_fingerprint": plan["runtime_fingerprint"],
        "authority": plan["authority"],
        "strategy_results": results,
        "matrix_order": "TARGET_MAJOR_STRATEGY_MINOR",
        "matrix_cell_count": TARGET_COUNT * STRATEGY_COUNT,
        "matrix": matrix,
        "matrix_sha256": digest(matrix),
        "evaluation_records": evaluations,
        "evaluation_sha256": digest(evaluations),
        "excluded_strategy": plan["strategies"]["excluded"],
        "artifact": artifact,
        "artifact_content_sha256": artifact["artifact_sha256"],
        "artifact_file_sha256": sha256(file_bytes(artifact)),
        "old_84_reuse": False,
        "final_status": "PASS"
        if plan["dataset"]["snapshot"]["kind"] == REAL_DATA
        else SYNTHETIC_DATA,
    }


def utc_timestamp(value: Any) -> datetime:
    text = string(value, "UTC timestamp")
    require(text.endswith("Z"), "timestamp must use UTC Z")
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ProtocolError("invalid UTC timestamp") from exc


def validate_operational(
    plan: Mapping[str, Any], envelope: Any, results: Sequence[dict[str, Any]]
) -> None:
    e = fields(
        envelope,
        "run_id output_root source_root source_db_path host_label started_at_utc "
        "ended_at_utc elapsed_ns attempts",
        "operational envelope",
    )
    for key in ("run_id", "output_root", "source_root", "source_db_path", "host_label"):
        string(e[key], key)
    start, end = utc_timestamp(e["started_at_utc"]), utc_timestamp(e["ended_at_utc"])
    require(end >= start, "run timestamp order")
    integer(e["elapsed_ns"], "run duration")
    attempts = array(e["attempts"], "attempt lineage")
    ids: set[str] = set()
    index = 0
    ordinal = 0
    previous_id = ""
    last_end = start
    for attempt in attempts:
        a = fields(
            attempt,
            "attempt_id strategy_id ordinal pid started_at_utc ended_at_utc "
            "elapsed_ns exit_status status failure_kind previous_attempt_id result_sha256 "
            "partial_output_sha256 bootstrap_before_sha256 bootstrap_after_sha256",
            "attempt",
        )
        require(index < STRATEGY_COUNT, "extra success/attempt after campaign completion")
        sid = plan["strategies"]["records"][index]["strategy_id"]
        equal(a["strategy_id"], sid, "serial strategy attempt order")
        aid = string(a["attempt_id"], "attempt id")
        require(aid not in ids, "duplicate attempt id")
        ids.add(aid)
        equal(a["ordinal"], ordinal + 1, "whole-strategy restart ordinal")
        equal(a["previous_attempt_id"], previous_id, "failure lineage link")
        integer(a["pid"], "child PID", minimum=1)
        integer(a["elapsed_ns"], "attempt duration")
        integer(a["exit_status"], "exit status", minimum=-255)
        attempt_start = utc_timestamp(a["started_at_utc"])
        attempt_end = utc_timestamp(a["ended_at_utc"])
        require(
            last_end <= attempt_start <= attempt_end <= end, "overlapping/out-of-order children"
        )
        last_end = attempt_end
        for key in ("partial_output_sha256", "bootstrap_before_sha256", "bootstrap_after_sha256"):
            string(a[key], key, empty=True)
            if a[key]:
                hex_digest(a[key], key)
        if a["status"] == "SUCCEEDED":
            equal(a["exit_status"], 0, "successful child exit")
            equal(a["failure_kind"], "", "successful failure kind")
            equal(a["partial_output_sha256"], "", "success cannot reuse partial output")
            hex_digest(a["bootstrap_before_sha256"], "bootstrap before")
            equal(a["bootstrap_before_sha256"], a["bootstrap_after_sha256"], "bootstrap drift")
            equal(a["result_sha256"], results[index]["strategy_output_sha256"], "accepted attempt")
            index += 1
            ordinal, previous_id = 0, ""
        else:
            equal(a["status"], "FAILED", "attempt status")
            string(a["failure_kind"], "failure kind")
            equal(a["result_sha256"], "", "failed attempt cannot contribute cells")
            ordinal += 1
            previous_id = aid
    require(
        index == STRATEGY_COUNT and not previous_id,
        "lineage must end with exactly one success for every strategy",
    )


def make_run(
    plan: dict[str, Any],
    results: list[dict[str, Any]],
    operational: dict[str, Any],
    campaign_label: str,
) -> dict[str, Any]:
    validate_plan(plan)
    string(campaign_label, "campaign label")
    payload = deterministic_payload(plan, results)
    validate_operational(plan, operational, results)
    return seal(
        {
            "manifest_schema_version": RUN_SCHEMA,
            "canonicalization_version": CANONICALIZATION,
            "protocol_version": PROTOCOL,
            "plan_manifest_sha256": plan["plan_manifest_sha256"],
            "common_manifest_sha256": plan["common_manifest_sha256"],
            "campaign_label": campaign_label,
            "operational_envelope": operational,
            "deterministic_payload": payload,
            "deterministic_payload_sha256": digest(payload),
        },
        "run_manifest_sha256",
    )


def validate_run(plan: dict[str, Any], value: Any) -> dict[str, Any]:
    validate_plan(plan)
    r = fields(value, RUN_FIELDS, "run manifest")
    protocol(r["protocol_version"])
    equal(r["manifest_schema_version"], RUN_SCHEMA, "run schema")
    equal(r["canonicalization_version"], CANONICALIZATION, "canonicalization")
    check_seal(r, "run_manifest_sha256")
    equal(r["plan_manifest_sha256"], plan["plan_manifest_sha256"], "run/plan binding")
    equal(r["common_manifest_sha256"], plan["common_manifest_sha256"], "run/common binding")
    string(r["campaign_label"], "campaign label")
    payload = r["deterministic_payload"]
    require(type(payload) is dict and "strategy_results" in payload, "deterministic payload shape")
    results = array(payload["strategy_results"], "strategy results")
    equal(payload, deterministic_payload(plan, results), "closed deterministic payload")
    equal(r["deterministic_payload_sha256"], digest(payload), "deterministic payload hash")
    validate_operational(plan, r["operational_envelope"], results)
    return r


def make_acceptance(plan: dict[str, Any], run_a_bytes: bytes, run_b_bytes: bytes) -> dict[str, Any]:
    a = validate_run(plan, parse_file(run_a_bytes))
    b = validate_run(plan, parse_file(run_b_bytes))
    require(a["campaign_label"] != b["campaign_label"], "two distinct campaign labels required")
    for key in ("run_id", "output_root"):
        require(
            a["operational_envelope"][key] != b["operational_envelope"][key],
            "two fresh campaigns and separate output roots required",
        )
    attempts_a = {r["attempt_id"] for r in a["operational_envelope"]["attempts"]}
    attempts_b = {r["attempt_id"] for r in b["operational_envelope"]["attempts"]}
    require(attempts_a.isdisjoint(attempts_b), "reused attempt across campaigns")
    # Compare actual bytes, not just digests, tolerances or metric summaries.
    equal(a["deterministic_payload"], b["deterministic_payload"], "two-campaign byte comparison")
    return seal(
        {
            "manifest_schema_version": ACCEPTANCE_SCHEMA,
            "canonicalization_version": CANONICALIZATION,
            "protocol_version": PROTOCOL,
            "plan_manifest_sha256": plan["plan_manifest_sha256"],
            "common_manifest_sha256": plan["common_manifest_sha256"],
            "run_a_manifest_file_sha256": sha256(run_a_bytes),
            "run_b_manifest_file_sha256": sha256(run_b_bytes),
            "run_a_deterministic_payload_sha256": a["deterministic_payload_sha256"],
            "run_b_deterministic_payload_sha256": b["deterministic_payload_sha256"],
            "comparison_contract": "EXACT_LF_FREE_LCJ1_DETERMINISTIC_PAYLOAD_BYTES",
            "comparison_results": {
                "equal": True,
                "run_a_accepted_cell_count": 43200,
                "run_b_accepted_cell_count": 43200,
                "total_empirical_cell_count": 86400,
                "evaluated_strategy_count": 54,
                "source_db_unchanged": True,
                "artifact_bytes_equal": True,
            },
            "old_84_reuse_attestation": False,
            "final_status": a["deterministic_payload"]["final_status"],
        },
        "acceptance_manifest_sha256",
    )


def validate_acceptance(
    plan: dict[str, Any], value: Any, run_a_bytes: bytes, run_b_bytes: bytes
) -> dict[str, Any]:
    a = fields(value, ACCEPTANCE_FIELDS, "acceptance manifest")
    protocol(a["protocol_version"])
    check_seal(a, "acceptance_manifest_sha256")
    equal(a, make_acceptance(plan, run_a_bytes, run_b_bytes), "closed acceptance manifest")
    return a
