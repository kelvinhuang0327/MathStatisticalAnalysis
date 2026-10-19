#!/usr/bin/env python3
"""Capture ONE candidate adapter call; never run the original producer/backtest.

Explicit future invocation (Python >= 3.9; numpy and scipy already installed):
    python3 -I -B /absolute/path/capture_single_execution_receipt.py \
        --history /absolute/frozen-history.json --history-sha256 HEX \
        --target /absolute/target.json --target-sha256 HEX \
        --identity /absolute/identity.json --identity-sha256 HEX \
        --source-root /absolute/archive/source --output /absolute/new-receipt.jsonl

History is a JSON array of {draw: decimal string, date: YYYY/MM/DD,
  numbers: six distinct integers 1..49, special: integer 1..49 or null}.
Target is exactly {lottery_type, draw_number, draw_date, actual_numbers,
  actual_special}, using the capture's target/outcome. Inputs are not reordered,
coerced, repaired, or fetched. Caller-supplied SHA256 values freeze exact bytes.

The output is an exclusive-created, append-only JSONL journal, mode 0600.
Every record carries the same execution_id; PREPARED is fsynced before calling.
Success requires caller-observed exit code 0 AND acceptance of the exact receipt
bytes against the caller-supplied SHA256 by accept_receipt below. A complete
COMPLETED/MATCH line alone is insufficient (including after an fsync failure).
Truncation rejects the whole receipt; PREPARED means completion/call count UNKNOWN,
NOT that it is safe to retry. Never resume/reuse an existing output path.
A crash before the first durable record can leave an empty reserved file; no
adapter has run at that point. FAILED may also mean the adapter already ran.

MATCH, when present, is ONLY equality with the saved capture's output/derived
fields. Historical input, source and runtime identity remain unproven. This
is a local evidence recorder, not a sandbox, signature, historical attestation,
or a full dependency/build lock. Use a trusted, quiescent filesystem/runtime.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import importlib
import importlib.machinery
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import sys
import types
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import NoReturn, Protocol, cast

STRATEGY = "ts3_regime_3bet"
LOTTERY = "BIG_LOTTO"
COMMIT = "520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f"
TREE = "6e45b343df5e67f9891378f1b005dd7d149ef238"
PINS = {
    "lottery_api/models/__init__.py": (
        "2ffe2a4600851a8a1b316108d48961f76ac83012f735bb3189b9d2e02365e86e"
    ),
    "lottery_api/models/replay_strategy_registry.py": (
        "c6c0352868f93c27e68c230e14b1b1c8f8c6a4f2feb021574d2f7cc49170976e"
    ),
    "lottery_api/requirements.txt": (
        "2046dd0aa9cc084352a2fb1a664e032fba23ac81f0b1e7d3f1d70ff9d1a1e130"
    ),
    "tools/backtest_biglotto_enhancements.py": (
        "b0bf78ef7e32ef1e07825251af45846076dbd331f6a1f2f8c89a08a1f301696e"
    ),
    "scripts/p14b_biglotto_single_strategy_replay_dry_run.py": (
        "313e1741bd39eef068a13bf31cf7f0bbdc7bbe73997c67b4e3a8c2be74e60777"
    ),
    "outputs/replay/p14b_biglotto_single_strategy_replay_dry_run_20260520.json": (
        "accb87648f0d9f619c0c235566e8330d75fe7d71b40f08889f1128daa2f8d5a2"
    ),
}
CAPTURE_PATH = "outputs/replay/p14b_biglotto_single_strategy_replay_dry_run_20260520.json"
MODULE_PATHS = {
    "lottery_api.models": "lottery_api/models/__init__.py",
    "tools.backtest_biglotto_enhancements": "tools/backtest_biglotto_enhancements.py",
    "lottery_api.models.replay_strategy_registry": "lottery_api/models/replay_strategy_registry.py",
}
TARGET_KEYS = {"lottery_type", "draw_number", "draw_date", "actual_numbers", "actual_special"}


# Dynamic JSON stays object-valued until the existing runtime checks use it.
# Casts describe those boundaries without coercing, copying, or validating data.
class AdapterMetadata(Protocol):
    strategy_id: str
    strategy_version: str
    min_history: int
    status: str
    supported_lottery_types: list[str]


class Adapter(Protocol):
    meta: AdapterMetadata

    def get_one_bet(self, history: object, lottery: str) -> tuple[list[int], object]: ...


class AdapterFactory(Protocol):
    def __call__(self, strategy: str) -> Adapter: ...


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def decode_json(data: bytes) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key: " + key)
            result[key] = value
        return result

    def bad_constant(value: str) -> NoReturn:
        raise ValueError("Non-finite JSON value: " + value)

    return json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=bad_constant)


def accept_receipt(
    receipt_bytes: object, expected_sha256: object, observed_exit_code: object = None,
) -> dict[str, object]:
    """Read-only v1 journal acceptance; never infer an exit code or run/retry a call.

    The caller supplies immutable bytes, their independently pinned digest and
    the recorder process's observed exit code. Candidate comparison is separate
    from receipt acceptance; neither establishes original parity or durability.
    Invalid/incomplete evidence returns accepted=False, without reading files.
    """
    verdict: dict[str, object] = {
        "accepted": False, "reason": None, "execution_id": None,
        "comparison": {"status": "NOT_EVALUATED", "scope": "candidate_output_fields_only"},
        "candidate_only": True, "original_source_identity_established": False,
        "original_reproduction_claimed": False,
    }
    try:
        require(type(receipt_bytes) is bytes, "Receipt must be immutable bytes")
        receipt_bytes = cast(bytes, receipt_bytes)
        require(isinstance(expected_sha256, str)
                and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
                "Expected receipt SHA256 must be 64 lowercase hex characters")
        require(sha(receipt_bytes) == expected_sha256, "Receipt SHA256 mismatch")
        require(receipt_bytes.endswith(b"\n"), "Receipt is empty or truncated")
        lines = receipt_bytes[:-1].split(b"\n")
        phases = ("RESERVED", "INPUTS_VERIFIED", "READY_TO_INVOKE", "TERMINAL")
        require(len(lines) == len(phases), "Receipt must contain exactly four records")
        records = [decode_json(line) for line in lines]
        keys = {
            "schema", "execution_id", "status", "phase", "sequence", "output_path",
            "candidate_only",
            "original_source_identity_established", "original_reproduction_claimed",
            "historical_input_identity", "historical_runtime_identity", "comparison",
            "candidate_provenance", "adapter_call_attempts", "reserved_file", "request",
            "recorded_at_utc",
        }
        additions: tuple[set[str], ...] = (
            set(),
            {"recorder", "inputs", "source_root", "source_files", "candidate_source",
             "target", "reference_capture", "call", "runtime"},
            {"loaded_modules_before_call", "crash_semantics"},
            {"loaded_modules_after_call", "result"},
        )
        execution_id = None
        # The four-record length guard above makes indexed pairing exact on Python 3.9.
        for index, record in enumerate(records, 1):
            phase = phases[index - 1]
            keys |= additions[index - 1]
            require(isinstance(record, dict) and set(cast(dict[str, object], record)) == keys,
                    "Incomplete or unknown receipt record fields")
            record = cast(dict[str, object], record)
            require(canonical(record) == lines[index - 1], "Noncanonical receipt record")
            require(record["schema"] == "biglotto-single-execution-receipt-v1",
                    "Unknown receipt schema")
            require(type(record["sequence"]) is int and record["sequence"] == index,
                    "Receipt sequence is duplicated, skipped or out of order")
            require(record["phase"] == phase
                    and record["status"] == ("COMPLETED" if index == 4 else "PREPARED"),
                    "Illegal or ambiguous receipt state transition")
            identity = record["execution_id"]
            require(isinstance(identity, str) and str(uuid.UUID(identity)) == identity,
                    "Invalid execution_id")
            execution_id = identity if execution_id is None else execution_id
            require(identity == execution_id, "Receipt execution_id mismatch")
            require(record["candidate_only"] is True
                    and record["original_source_identity_established"] is False
                    and record["original_reproduction_claimed"] is False
                    and record["historical_input_identity"] == "UNKNOWN"
                    and record["historical_runtime_identity"] == "UNKNOWN",
                    "Receipt exceeds candidate-only identity claims")
            require(type(record["adapter_call_attempts"]) is int
                    and record["adapter_call_attempts"] == (1 if index == 4 else 0),
                    "Invalid adapter call count")
            require(record["candidate_provenance"] == (
                "VERIFIED_FOR_THIS_CANDIDATE_CALL" if index >= 3 else "NOT_VERIFIED"),
                "Invalid candidate provenance state")
            if index < 4:
                require(record["comparison"] == {
                    "status": "NOT_EVALUATED", "scope": "candidate_output_fields_only"},
                    "Comparison before completion")
        terminal = cast(dict[str, object], records[-1])
        snapshot_keys = {"path", "bytes", "sha256", "raw_base64", "parsed_canonical_sha256"}
        input_keys = {"identity", "history", "target"}
        inputs = cast(dict[str, dict[str, object]],
                      cast(dict[str, object], records[1])["inputs"])
        require(type(inputs) is dict and set(inputs) == input_keys,
                "Incomplete recorded input snapshots")
        require(all(canonical(cast(dict[str, object], record)["inputs"]) == canonical(inputs)
                    for record in records[2:]),
                "Recorded input snapshots changed during execution")

        def decode_recorded_snapshot(name: str) -> object:
            snapshot = inputs[name]
            require(type(snapshot) is dict and set(snapshot) == snapshot_keys,
                    "Incomplete recorded snapshot: " + name)
            require(isinstance(snapshot["path"], str) and Path(snapshot["path"]).is_absolute()
                    and type(snapshot["bytes"]) is int and snapshot["bytes"] > 0
                    and isinstance(snapshot["sha256"], str)
                    and re.fullmatch(r"[0-9a-f]{64}", snapshot["sha256"]) is not None
                    and isinstance(snapshot["raw_base64"], str)
                    and isinstance(snapshot["parsed_canonical_sha256"], str)
                    and re.fullmatch(
                        r"[0-9a-f]{64}", snapshot["parsed_canonical_sha256"]) is not None,
                    "Invalid recorded snapshot metadata: " + name)
            raw = base64.b64decode(cast(str, snapshot["raw_base64"]), validate=True)
            require(len(raw) == snapshot["bytes"] and sha(raw) == snapshot["sha256"],
                    "Recorded snapshot bytes/hash mismatch: " + name)
            value = decode_json(raw)
            require(sha(canonical(value)) == snapshot["parsed_canonical_sha256"],
                    "Recorded snapshot canonical hash mismatch: " + name)
            return value

        identity = cast(dict[str, object], decode_recorded_snapshot("identity"))
        history = cast(list[object], decode_recorded_snapshot("history"))
        target_snapshot = decode_recorded_snapshot("target")
        require(canonical(target_snapshot) == canonical(terminal["target"]),
                "Target differs from recorded input bytes")
        identity_source = cast(dict[str, object], identity["candidate_source"])
        identity_scope = cast(dict[str, object], identity["scope"])
        require(identity["schema"] == "biglotto-strategy-input-identity-r1"
                and identity_source["commit"] == COMMIT and identity_source["tree"] == TREE
                and identity_scope["strategy_id"] == STRATEGY
                and identity_scope["lottery_type"] == LOTTERY,
                "Recorded identity does not match the pinned candidate")
        reference_capture = cast(dict[str, object], terminal["reference_capture"])
        require(reference_capture["path"] == CAPTURE_PATH
                and reference_capture["sha256"] == PINS[CAPTURE_PATH]
                and reference_capture["json_pointer"] == "/candidates_sample/0"
                and reference_capture["row"]
                == cast(dict[str, object], identity["capture"])["target_row"],
                "Recorded capture reference does not match identity")
        target = cast(dict[str, object], terminal["target"])
        reference = cast(dict[str, object], reference_capture["row"])
        validate_inputs(history, target, reference)
        request = cast(dict[str, object], cast(dict[str, object], records[0])["request"])
        for name in input_keys:
            require(request[name + "_sha256"] == inputs[name]["sha256"],
                    "Request pin differs from recorded snapshot: " + name)
        call = cast(dict[str, object], terminal["call"])
        require(call["strategy_id"] == STRATEGY and call["method"] == "get_one_bet"
                and call["lottery_type"] == LOTTERY and call["history_count"] == len(history)
                and call["history_canonical_sha256"] == sha(canonical(history))
                and call["target_passed_to_adapter"] is False
                and call["outcome_passed_to_adapter"] is False,
                "Recorded adapter call does not match frozen inputs")
        result = terminal["result"]
        result_keys = {"predicted_numbers", "predicted_special", "prediction_status",
                       "hit_numbers", "hit_count", "special_hit", "source_trace", "provenance_hash"}
        require(isinstance(result, dict) and set(cast(dict[str, object], result)) == result_keys,
                "Incomplete completed result")
        result = cast(dict[str, object], result)
        predicted = cast(list[int], result["predicted_numbers"])
        require(numbers_ok(predicted) and predicted == sorted(predicted)
                and result["predicted_special"] is None and result["prediction_status"] == "READY"
                and result["special_hit"] is False, "Invalid completed prediction")
        hits = sorted(set(predicted) & set(cast(list[int], target["actual_numbers"])))
        require(type(result["hit_numbers"]) is list
                and all(type(number) is int for number in cast(list[object], result["hit_numbers"]))
                and result["hit_numbers"] == hits and type(result["hit_count"]) is int
                and result["hit_count"] == len(hits)
                and result["source_trace"] == f"{STRATEGY}:get_one_bet:hist=635"
                and result["provenance_hash"] == sha(
                    f"{STRATEGY}:{target['draw_number']}:{predicted}".encode())[:16],
                "Invalid completed derived fields")
        reference = cast(dict[str, object],
                         cast(dict[str, object], terminal["reference_capture"])["row"])
        mismatches = sorted(key for key in result_keys if result[key] != reference[key])
        comparison = terminal["comparison"]
        require(isinstance(comparison, dict) and set(cast(dict[str, object], comparison)) == {
            "status", "scope", "mismatched_fields", "historical_reproduction_proven"},
            "Incomplete completed comparison")
        comparison = cast(dict[str, object], comparison)
        require(comparison["scope"] == "candidate_output_fields_only"
                and comparison["historical_reproduction_proven"] is False
                and comparison["status"] == ("MISMATCH" if mismatches else "MATCH")
                and isinstance(comparison["mismatched_fields"], list)
                and all(isinstance(key, str)
                        for key in cast(list[object], comparison["mismatched_fields"]))
                and sorted(cast(list[str], comparison["mismatched_fields"])) == mismatches,
                "Invalid candidate comparison")
        verdict["execution_id"] = execution_id
        verdict["comparison"] = comparison
        require(type(observed_exit_code) is int and observed_exit_code == 0,
                "Caller-observed integer exit code 0 is required")
        verdict["accepted"] = True
        verdict["reason"] = "Completed candidate receipt accepted"
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError, binascii.Error) as exc:
        verdict["reason"] = str(exc)
    return verdict


def snapshot(path: str, expected: str) -> tuple[object, dict[str, object]]:
    require(re.fullmatch(r"[0-9a-f]{64}", expected) is not None,
            "Expected SHA256 must be 64 lowercase hex characters")
    resolved = Path(path).resolve(strict=True)
    data = resolved.read_bytes()
    require(sha(data) == expected, "Frozen input SHA256 mismatch: " + str(resolved))
    value = decode_json(data)
    return value, {"path": str(resolved), "bytes": len(data), "sha256": sha(data),
                   "raw_base64": base64.b64encode(data).decode("ascii"),
                   "parsed_canonical_sha256": sha(canonical(value))}


def numbers_ok(value: object) -> bool:
    return (isinstance(value, list) and len(cast(list[object], value)) == 6
            and all(type(n) is int and 1 <= n <= 49 for n in cast(list[object], value))
            and len(set(cast(list[int], value))) == 6)


def date_value(value: object) -> date:
    require(isinstance(value, str) and re.fullmatch(r"[0-9]{4}/[0-9]{2}/[0-9]{2}", value),
            "Date must be YYYY/MM/DD")
    return datetime.strptime(cast(str, value), "%Y/%m/%d").date()


def draw_value(value: object) -> int:
    require(isinstance(value, str) and re.fullmatch(r"[0-9]+", value),
            "Draw identity must be a decimal string")
    return int(cast(str, value))


def validate_inputs(history: object, target: object, reference: dict[str, object]) -> None:
    require(isinstance(target, dict) and set(cast(dict[str, object], target)) == TARGET_KEYS,
            "Target keys must exactly match documented schema")
    target = cast(dict[str, object], target)
    require(target == {key: reference[key] for key in TARGET_KEYS},
            "Target/outcome does not match this identity's capture")
    require(target["lottery_type"] == LOTTERY and numbers_ok(target["actual_numbers"]),
            "Invalid target lottery/numbers")
    special = target["actual_special"]
    require(type(special) is int and 1 <= special <= 49
            and special not in cast(list[int], target["actual_numbers"]), "Invalid target special")
    target_draw, target_date = draw_value(target["draw_number"]), date_value(target["draw_date"])
    require(isinstance(history, list) and len(cast(list[object], history)) == 635,
            "This capture comparison requires exactly 635 caller-frozen history rows")
    previous_draw, previous_date = -1, None
    for row in cast(list[object], history):
        require(isinstance(row, dict)
                and set(cast(dict[str, object], row)) == {"draw", "date", "numbers", "special"},
                "History row keys must exactly match documented schema")
        row = cast(dict[str, object], row)
        draw, date = draw_value(row["draw"]), date_value(row["date"])
        require(previous_draw < draw < target_draw,
                "History must be strictly ascending and pre-target")
        require(date < target_date and (previous_date is None or previous_date <= date),
                "History dates must be ordered and pre-target")
        require(numbers_ok(row["numbers"]), "Invalid history numbers")
        special = row["special"]
        require(special is None or (type(special) is int and 1 <= special <= 49
                                   and special not in cast(list[int], row["numbers"])),
                "Invalid history special")
        previous_draw, previous_date = draw, date


def pinned_sources(
    identity: dict[str, object], root: Path,
) -> tuple[dict[str, bytes], dict[str, dict[str, object]]]:
    require(identity.get("schema") == "biglotto-strategy-input-identity-r1",
            "Unknown identity schema")
    source = cast(dict[str, object], identity["candidate_source"])
    require(source["commit"] == COMMIT and source["tree"] == TREE,
            "UNKNOWN: identity differs from supported candidate commit/tree")
    require(cast(dict[str, object], identity["scope"])["strategy_id"] == STRATEGY
            and cast(dict[str, object], identity["scope"])["lottery_type"] == LOTTERY,
            "Identity strategy/lottery mismatch")
    entries = cast(list[dict[str, object]], identity["files"])
    require(len(entries) == len(PINS), "Identity must contain exactly six pinned files")
    by_path = {cast(str, item["source_path"]): item for item in entries}
    require(set(by_path) == set(PINS), "Identity pinned path set mismatch")
    blobs: dict[str, bytes] = {}
    evidence: dict[str, dict[str, object]] = {}
    for relative, expected in PINS.items():
        item = by_path[relative]
        require(item["sha256"] == expected and item["source_commit"] == COMMIT,
                "UNKNOWN: authoritative identity pin differs from supported candidate: " + relative)
        path = (root / relative).resolve(strict=True)
        require(root in path.parents, "Pinned path escapes source root: " + relative)
        data = path.read_bytes()
        require(sha(data) == item["sha256"] and len(data) == item["bytes"],
                "Pinned source bytes mismatch: " + relative)
        blobs[relative] = data
        evidence[relative] = {"path": str(path), "bytes": len(data), "sha256": sha(data),
                              "git_blob_id_claimed_by_identity": item["git_blob_id"]}
    return blobs, evidence


def namespace(name: str) -> None:
    # Empty search paths prevent loading unpinned package initializers.
    module = types.ModuleType(name)
    module.__path__ = []
    module.__package__ = name
    module.__spec__ = importlib.machinery.ModuleSpec(name, loader=None, is_package=True)
    module.__spec__.submodule_search_locations = []
    sys.modules[name] = module


def load_pinned(name: str, path: Path, data: bytes) -> types.ModuleType:
    # Compile the verified in-memory bytes; never execute cached .pyc or reread source.
    package = name == "lottery_api.models"
    spec = importlib.util.spec_from_file_location(
        name, str(path), submodule_search_locations=[] if package else None)
    module = importlib.util.module_from_spec(cast(importlib.machinery.ModuleSpec, spec))
    sys.modules[name] = module
    parent, _, child = name.rpartition(".")
    setattr(sys.modules[parent], child, module)
    exec(compile(data, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


def module_evidence(
    modules: dict[str, types.ModuleType], sources: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    observed: dict[str, dict[str, object]] = {}
    for name, relative in MODULE_PATHS.items():
        module = modules[name]
        expected = sources[relative]
        require(sys.modules.get(name) is module, "Loaded module was replaced: " + name)
        require(module.__file__ == expected["path"], "Loaded __file__ mismatch: " + name)
        require(cast(importlib.machinery.ModuleSpec, module.__spec__).origin == expected["path"],
                "Loaded origin mismatch: " + name)
        actual = sha(Path(cast(str, module.__file__)).read_bytes())
        require(actual == expected["sha256"], "Loaded source changed: " + name)
        observed[name] = {"__file__": module.__file__, "sha256": actual,
                          "executed_snapshot_sha256": expected["sha256"],
                          "load_method": "compile_verified_bytes_no_pyc"}
    return observed


def dependencies(root: Path) -> dict[str, dict[str, object]]:
    observed: dict[str, dict[str, object]] = {}
    for name in ("numpy", "scipy", "scipy.fft"):
        module = importlib.import_module(name)
        path = Path(cast(str, module.__file__)).resolve(strict=True)
        require(root not in path.parents, "Dependency resolved inside candidate source: " + name)
        observed[name] = {"__file__": str(path), "sha256": sha(path.read_bytes())}
        if name != "scipy.fft":
            observed[name]["module_version"] = module.__version__
            observed[name]["distribution_version"] = importlib.metadata.version(name)
            require(module.__version__ == observed[name]["distribution_version"],
                    "Dependency module/distribution version mismatch: " + name)
    observed["numpy"]["declared_version"] = "1.26.2"
    observed["numpy"]["matches_declared_version"] = observed["numpy"]["module_version"] == "1.26.2"
    observed["scipy"]["declared_version"] = "UNKNOWN"
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for argument in ("history", "history-sha256", "target", "target-sha256",
                     "identity", "identity-sha256", "source-root", "output"):
        parser.add_argument("--" + argument, required=True)
    args = parser.parse_args()
    # Resolve parent only: resolving the leaf could accidentally follow an existing symlink.
    requested = Path(args.output).absolute()
    output = requested.parent.resolve(strict=True) / requested.name
    fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND, 0o600)
    reserved_stat = os.fstat(fd)
    state: dict[str, object] = {
        "schema": "biglotto-single-execution-receipt-v1", "execution_id": str(uuid.uuid4()),
        "status": "PREPARED", "phase": "RESERVED", "sequence": 0,
        "output_path": str(output), "candidate_only": True,
        "original_source_identity_established": False, "original_reproduction_claimed": False,
        "historical_input_identity": "UNKNOWN", "historical_runtime_identity": "UNKNOWN",
        "comparison": {"status": "NOT_EVALUATED", "scope": "candidate_output_fields_only"},
        "candidate_provenance": "NOT_VERIFIED", "adapter_call_attempts": 0,
        "reserved_file": {"device": reserved_stat.st_dev, "inode": reserved_stat.st_ino},
        "request": vars(args),
    }
    append_failed = False

    def append() -> None:
        nonlocal append_failed
        visible_stat = output.lstat()
        require((visible_stat.st_dev, visible_stat.st_ino)
                == (reserved_stat.st_dev, reserved_stat.st_ino), "Reserved output identity changed")
        state["sequence"] = cast(int, state["sequence"]) + 1
        state["recorded_at_utc"] = datetime.now(
            timezone.utc,  # noqa: UP017 -- datetime.UTC is unavailable on Python 3.9.
        ).isoformat()
        encoded = canonical(state) + b"\n"
        try:
            remaining = memoryview(encoded)
            while remaining:
                written = os.write(fd, remaining)
                if written <= 0:
                    raise OSError("Receipt append made no progress")
                remaining = remaining[written:]
            os.fsync(fd)
        except BaseException:
            # Do not append after a partial write: that would splice invalid JSON lines.
            append_failed = True
            raise

    try:
        append()
        directory_fd = os.open(str(output.parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        require(sys.flags.isolated == 1, "Run in a fresh isolated interpreter: python3 -I -B ...")
        sys.dont_write_bytecode = True
        tool_path = Path(__file__).resolve(strict=True)
        state["recorder"] = {"path": str(tool_path), "sha256": sha(tool_path.read_bytes())}
        require(not any(name == prefix or name.startswith(prefix + ".")
                        for name in sys.modules
                        for prefix in ("lottery_api", "tools", "numpy", "scipy")),
                "Fresh interpreter required; candidate/dependency modules already loaded")
        root = Path(args.source_root).resolve(strict=True)
        require(root.is_dir(), "Source root must be a directory")
        identity_value, identity_snapshot = snapshot(args.identity, args.identity_sha256)
        identity = cast(dict[str, object], identity_value)
        history_value, history_snapshot = snapshot(args.history, args.history_sha256)
        history = cast(list[object], history_value)
        target_value, target_snapshot = snapshot(args.target, args.target_sha256)
        target = cast(dict[str, object], target_value)
        state["inputs"] = {"identity": identity_snapshot, "history": history_snapshot,
                           "target": target_snapshot}
        blobs, sources = pinned_sources(identity, root)
        capture = cast(dict[str, object], decode_json(blobs[CAPTURE_PATH]))
        reference = cast(list[dict[str, object]], capture["candidates_sample"])[0]
        require(reference == cast(dict[str, object], identity["capture"])["target_row"],
                "Identity/capture row mismatch")
        identity_scope = cast(dict[str, object], identity["scope"])
        require(reference["strategy_id"] == STRATEGY
                and target["draw_number"] == identity_scope["draw_number"],
                "Target identity mismatch")
        validate_inputs(history, target, reference)
        history_hash = sha(canonical(history))
        state.update({
            "phase": "INPUTS_VERIFIED", "source_root": str(root), "source_files": sources,
            "candidate_source": {"commit_claimed_by_identity": COMMIT,
                                 "tree_claimed_by_identity": TREE,
                                 "verification": "six_file_sha256_only_not_full_git_tree"},
            "target": target, "reference_capture": {"path": CAPTURE_PATH,
                "sha256": PINS[CAPTURE_PATH], "json_pointer": "/candidates_sample/0",
                "row": reference},
            "call": {"entrypoint": "lottery_api.models.replay_strategy_registry.get_adapter",
                "strategy_id": STRATEGY, "method": "get_one_bet", "lottery_type": LOTTERY,
                "history_count": len(history), "history_canonical_sha256": history_hash,
                "target_passed_to_adapter": False, "outcome_passed_to_adapter": False,
                "implicit_windows": {"fourier": 500, "cold": 100, "tail": 100},
                "random_seed": None,
                "random_seed_reason": "No RNG in inspected candidate call path"},
            "runtime": {"python_version": sys.version,
                "implementation": platform.python_implementation(),
                "executable": sys.executable,
                "executable_sha256": sha(Path(sys.executable).read_bytes()),
                "platform": platform.platform(), "machine": platform.machine(),
                "python_flags": str(sys.flags), "sys_path_before_candidate_imports": list(sys.path),
                "dependency_build_lock": (
                    "UNKNOWN; recorded package files/versions are not a full binary lock")},
        })
        append()
        state["phase"] = "IMPORTS"
        cast(dict[str, object], state["runtime"])["dependencies"] = dependencies(root)
        namespace("lottery_api")
        namespace("tools")
        modules: dict[str, types.ModuleType] = {}
        for name, relative in MODULE_PATHS.items():
            modules[name] = load_pinned(
                name, Path(cast(str, sources[relative]["path"])), blobs[relative])
        state["loaded_modules_before_call"] = module_evidence(modules, sources)
        registry = modules["lottery_api.models.replay_strategy_registry"]
        adapter = cast(AdapterFactory, registry.get_adapter)(STRATEGY)
        require(adapter.meta.strategy_id == STRATEGY and adapter.meta.strategy_version == "v0.1"
                and adapter.meta.min_history == 100 and adapter.meta.status == "ONLINE"
                and adapter.meta.supported_lottery_types == [LOTTERY], "Adapter metadata mismatch")
        require(type(adapter).__module__ == registry.__name__
                and type(adapter).__name__ == "_BigLottoTs3Regime3BetAdapter",
                "Unexpected adapter class")
        cast(dict[str, object], state["call"])["adapter_class"] = (
            type(adapter).__module__ + "." + type(adapter).__name__)
        cast(dict[str, object], state["call"])["strategy_version"] = adapter.meta.strategy_version
        cast(dict[str, object], state["runtime"])["sys_path_at_call"] = list(sys.path)
        state["candidate_provenance"] = "VERIFIED_FOR_THIS_CANDIDATE_CALL"
        state["phase"] = "READY_TO_INVOKE"
        state["crash_semantics"] = (
            "Without a terminal record, actual call count is UNKNOWN (0 or 1); do not retry")
        append()  # Durable PREPARED, including actual loaded provenance, BEFORE invocation.
        state["phase"] = "INVOKING"
        state["adapter_call_attempts"] = 1
        # ONLY strategy invocation.
        predicted_numbers, predicted_special = adapter.get_one_bet(history, LOTTERY)
        state["phase"] = "POST_CALL_VERIFICATION"
        require(sha(canonical(history)) == history_hash, "Adapter mutated history")
        state["loaded_modules_after_call"] = module_evidence(modules, sources)
        # Recheck all six pins and dependencies; a provenance failure must not yield MATCH.
        _, after_sources = pinned_sources(identity, root)
        require(after_sources == sources, "Pinned sources changed during call")
        require(dependencies(root) == cast(dict[str, object], state["runtime"])["dependencies"],
                "Dependencies changed during call")
        require(numbers_ok(predicted_numbers) and predicted_numbers == sorted(predicted_numbers)
                and predicted_special is None, "Unexpected adapter result")
        hits = sorted(set(predicted_numbers) & set(cast(list[int], target["actual_numbers"])))
        result: dict[str, object] = {
            "predicted_numbers": predicted_numbers, "predicted_special": predicted_special,
            "prediction_status": "READY", "hit_numbers": hits, "hit_count": len(hits),
            "special_hit": False, "source_trace": f"{STRATEGY}:get_one_bet:hist={len(history)}",
            "provenance_hash": sha(
                f"{STRATEGY}:{target['draw_number']}:{sorted(predicted_numbers)}".encode())[:16],
        }
        state["result"] = result
        mismatches = [key for key, value in result.items() if value != reference[key]]
        state["comparison"] = {"status": "MISMATCH" if mismatches else "MATCH",
                               "scope": "candidate_output_fields_only",
                               "mismatched_fields": mismatches,
                               "historical_reproduction_proven": False}
        state["status"], state["phase"] = "COMPLETED", "TERMINAL"
        append()
        print(str(output))
        return 0
    except BaseException as exc:
        state["status"] = "FAILED"
        state["comparison"] = {"status": "NOT_EVALUATED", "scope": "candidate_output_fields_only"}
        state["candidate_provenance"] = "NOT_ESTABLISHED_FOR_COMPLETED_EXECUTION"
        state["error"] = {"type": type(exc).__name__, "message": str(exc)}
        if not append_failed:
            try:
                append()
            except BaseException as write_error:
                print("FAILED to persist terminal receipt: " + str(write_error), file=sys.stderr)
        print("FAILED: " + str(exc) + "; reserved receipt: " + str(output), file=sys.stderr)
        return 1
    finally:
        os.close(fd)


if __name__ == "__main__":
    raise SystemExit(main())
