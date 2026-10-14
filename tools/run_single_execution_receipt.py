#!/usr/bin/env python3
"""Run one pinned candidate recorder and accept its exact observed receipt.

Invoke this runner with Python >= 3.9 and -I -B. All path and hash arguments
are required for a receipt run; --output-directory names a new directory under an existing
parent. The recorder exclusively creates receipt.jsonl; this runner exclusively
reserves result.json before launching the recorder. Never retry or reuse a run.

result.json and stdout contain the same JSON summary. Binary stdout, stderr and
receipt evidence are losslessly base64 encoded. recorder.returncode is the raw
subprocess return code (negative means a signal on POSIX), or null if unavailable.
Runner exit 0 means receipt acceptance ONLY, including a valid MISMATCH; exit 1
means rejection/infrastructure failure, and argparse errors use exit 2. Candidate
comparison is independent and never proves historical identity or original parity.

--preflight-only --dependency-root /absolute/site-packages checks only the pinned
CPython/NumPy/SciPy runtime and emits JSON to stdout without creating files.
Both modes explicitly add the dependency root without processing .pth files;
receipt mode checks distribution metadata without importing numerical modules;
the pinned recorder loads them only after its fresh-interpreter/input guards.
A passing preflight establishes candidate readiness only, never original parity.

Use a trusted, quiescent filesystem/runtime, as required by the recorder. Hash
checks before/after execution are evidence checks, not a filesystem race sandbox.
A crash may leave reserved/partial output; it does not authorize another call.
"""
from __future__ import annotations

import sys

if __name__ == "__main__" and (not sys.flags.isolated or not sys.dont_write_bytecode):
    raise SystemExit("Run this entrypoint with an explicit Python interpreter and -I -B")

import argparse
import base64
import hashlib
import importlib
import importlib.metadata
import json
import os
import re
import stat
import subprocess
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, TypedDict, cast

RECORDER_SHA256 = "95b2689af528ec294eabca272e0537bd572175edc1ed7203ccce53a6f289cb20"


class BinaryEvidence(TypedDict):
    bytes: int
    sha256: str
    raw_base64: str


class DependencyMetadata(TypedDict):
    dependency_root: str
    packages: dict[str, str]


class PackageEvidence(TypedDict):
    version: str
    path: str
    sha256: str


class FileEvidence(TypedDict):
    path: str
    sha256: str


class ModuleEvidence(FileEvidence):
    module: str


class DependencyEvidence(TypedDict):
    dependency_root: str
    packages: dict[str, PackageEvidence]
    imported_modules: list[ModuleEvidence]
    binary_sources: list[FileEvidence]


class DistributionMetadata(Protocol):
    def __getitem__(self, key: str, /) -> str | None: ...


class DistributionLike(Protocol):
    metadata: DistributionMetadata


class NumericModule(Protocol):
    __file__: str
    __version__: str


class FFTModule(Protocol):
    fft: object
    fftfreq: object


class RecordedDependency(TypedDict):
    module_version: str
    distribution_version: str
    __file__: str


class RecordedRuntime(TypedDict):
    dependencies: dict[str, RecordedDependency]


class DependencyRow(TypedDict):
    phase: str
    runtime: RecordedRuntime


class ComparisonFields(TypedDict):
    status: str
    scope: str


class Comparison(ComparisonFields, total=False):
    mismatched_fields: list[str]
    historical_reproduction_proven: bool


class ReceiptAcceptance(TypedDict):
    accepted: bool
    reason: str | None
    execution_id: str | None


class ReceiptVerdict(ReceiptAcceptance):
    comparison: Comparison
    candidate_only: bool
    original_source_identity_established: bool
    original_reproduction_claimed: bool


class RecorderAPI(Protocol):
    # This contract is local: the verified recorder snapshot is the runtime provider.
    def accept_receipt(self, receipt_bytes: bytes, expected_sha256: str,
                       observed_exit_code: int | None = None) -> ReceiptVerdict: ...


class DependencyArguments(Protocol):
    dependency_root: str


class RunArguments(DependencyArguments, Protocol):
    interpreter: str
    recorder: str
    history: str
    target: str
    identity: str
    source_root: str
    output_directory: str
    recorder_sha256: str
    history_sha256: str
    target_sha256: str
    identity_sha256: str


class InterpreterFields(TypedDict):
    executable: str
    version: str
    implementation: str
    flags: str
    isolated: int
    dont_write_bytecode: bool


class InterpreterEvidence(InterpreterFields, total=False):
    sha256: str


class PreflightSummary(TypedDict):
    schema: str
    status: str
    candidate_only: bool
    historical_runtime_identity: str
    original_reproduction_claimed: bool
    invocation_attempts: int
    argv: list[str]
    dependency_root: str
    expected_versions: dict[str, str]
    interpreter: InterpreterEvidence
    calls: dict[str, int]
    dependencies: DependencyEvidence | None
    error: str | None


class RecorderEvidence(TypedDict):
    path: str
    expected_sha256: str
    loaded_snapshot_sha256: str
    post_call_sha256: str | None
    argv: list[str]
    invocation_attempts: int
    returncode: int | None
    stdout: BinaryEvidence | None
    stderr: BinaryEvidence | None
    launch_error: str | None


class ReceiptEvidence(TypedDict):
    path: str
    evidence: BinaryEvidence | None
    read_error: str | None


class RunSummary(TypedDict):
    schema: str
    started_at_utc: str
    finished_at_utc: str | None
    request: dict[str, object]
    result_path: str
    candidate_only: bool
    scope: str
    original_source_identity_established: bool
    original_reproduction_claimed: bool
    historical_reproduction_proven: bool
    historical_input_identity: str
    historical_runtime_identity: str
    recorder: RecorderEvidence
    receipt: ReceiptEvidence
    receipt_acceptance: ReceiptAcceptance
    comparison: Comparison
    dependency_metadata: DependencyMetadata
    dependency_pins_verified: bool
    errors: list[str]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def binary_evidence(data: bytes) -> BinaryEvidence:
    return {"bytes": len(data), "sha256": digest(data),
            "raw_base64": base64.b64encode(data).decode("ascii")}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()  # noqa: UP017 -- Python 3.9 compatibility.


def sha256_argument(value: str) -> str:
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise argparse.ArgumentTypeError("SHA256 must be 64 lowercase hexadecimal characters")
    return value


def required_path(value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("An explicit absolute path is required")
    return str(path)



NUMERIC_PINS: dict[str, str] = {"numpy": "1.26.2", "scipy": "1.12.0"}


def numeric_dependency_metadata(dependency_root: str) -> DependencyMetadata:
    """Check only metadata from the explicit root; do not import numeric modules."""
    if sys.implementation.name != "cpython" or sys.version_info[:3] != (3, 9, 6):
        raise ValueError("Candidate interpreter pin requires CPython 3.9.6")
    if not sys.flags.isolated or not sys.dont_write_bytecode:
        raise ValueError("Candidate dependencies require -I -B")
    root = Path(required_path(dependency_root)).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Dependency root must be an existing directory")
    packages: dict[str, str] = {}
    for distribution in importlib.metadata.distributions(path=[str(root)]):
        distribution_metadata = cast(DistributionLike, distribution).metadata
        name = (distribution_metadata["Name"] or "").lower()
        if name not in NUMERIC_PINS:
            continue
        if name in packages or distribution.version != NUMERIC_PINS[name]:
            raise ValueError("Missing, ambiguous or mismatched dependency metadata: " + name)
        packages[name] = distribution.version
    if set(packages) != set(NUMERIC_PINS):
        raise ValueError("Pinned dependency metadata missing from explicit root")
    return {"dependency_root": str(root), "packages": packages}


def prepare_recorder_dependencies(dependency_root: str) -> None:
    metadata = numeric_dependency_metadata(dependency_root)
    # The recorder owns the first numeric import, after its unchanged guards.
    sys.path.insert(0, metadata["dependency_root"])


def verify_recorded_dependencies(receipt_bytes: bytes, metadata: DependencyMetadata) -> None:
    root = Path(metadata["dependency_root"])
    # The accepted journal is consumed through the pinned recorder's dependency fields.
    for row in (cast(DependencyRow, json.loads(line)) for line in receipt_bytes.splitlines()):
        if row["phase"] not in ("READY_TO_INVOKE", "TERMINAL"):
            continue
        actual = row["runtime"]["dependencies"]
        for name, version in metadata["packages"].items():
            if (actual[name]["module_version"] != version
                    or actual[name]["distribution_version"] != version):
                raise ValueError("Recorded dependency differs from pinned metadata: " + name)
        for name in ("numpy", "scipy", "scipy.fft"):
            Path(actual[name]["__file__"]).resolve(strict=True).relative_to(
                root / name.split(".")[0])


def load_numeric_dependencies(dependency_root: str) -> DependencyEvidence:
    """Load fixed candidate dependencies; never import a strategy or recorder."""
    if sys.implementation.name != "cpython" or sys.version_info[:3] != (3, 9, 6):
        raise ValueError("Candidate interpreter pin requires CPython 3.9.6")
    if not sys.flags.isolated or not sys.dont_write_bytecode:
        raise ValueError("Candidate dependencies require -I -B")
    root = Path(required_path(dependency_root)).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Dependency root must be an existing directory")
    if any(name.split(".")[0] in NUMERIC_PINS for name in sys.modules):
        raise ValueError("Numeric dependencies must not be preloaded")
    sys.path.insert(0, str(root))  # Explicit path; no site/.pth execution or installation.
    packages: dict[str, PackageEvidence] = {}
    for name, version in NUMERIC_PINS.items():
        module = cast(NumericModule, importlib.import_module(name))
        path = Path(module.__file__).resolve(strict=True)
        path.relative_to(root / name)
        packages[name] = {"version": module.__version__, "path": str(path),
                          "sha256": digest(path.read_bytes())}
        if module.__version__ != version:
            raise ValueError(f"{name} version pin mismatch: {module.__version__} != {version}")
    # Match the frozen source's numerical import surface without executing it.
    fft = cast(FFTModule, importlib.import_module("scipy.fft"))
    if not callable(fft.fft) or not callable(fft.fftfreq):
        raise ValueError("Frozen scipy.fft imports are unavailable")
    modules: list[ModuleEvidence] = []
    for name, loaded_module in sorted(sys.modules.items()):
        if name.split(".")[0] not in NUMERIC_PINS or not getattr(loaded_module, "__file__", None):
            continue
        path = Path(cast(str, loaded_module.__file__)).resolve(strict=True)
        path.relative_to(root / name.split(".")[0])
        modules.append({"module": name, "path": str(path), "sha256": digest(path.read_bytes())})
    # These are on-disk binary sources, not a claim that every library was loaded.
    binaries: list[FileEvidence] = []
    for name in NUMERIC_PINS:
        for path in sorted((root / name).rglob("*")):
            if path.is_file() and path.suffix in (".so", ".dylib", ".dll", ".pyd"):
                binaries.append({"path": str(path.resolve()), "sha256": digest(path.read_bytes())})
    return {"dependency_root": str(root), "packages": packages,
            "imported_modules": modules, "binary_sources": binaries}


def preflight_main() -> int:
    parser = argparse.ArgumentParser(description="One candidate dependency-only preflight")
    parser.add_argument("--preflight-only", action="store_true", required=True)
    parser.add_argument("--dependency-root", type=required_path, required=True)
    args = cast(DependencyArguments, parser.parse_args())
    summary: PreflightSummary = {
        "schema": "biglotto-runtime-preflight-v1", "status": "BLOCKED",
        "candidate_only": True, "historical_runtime_identity": "UNKNOWN",
        "original_reproduction_claimed": False, "invocation_attempts": 1,
        "argv": list(sys.argv), "dependency_root": args.dependency_root,
        "expected_versions": {"cpython": "3.9.6", **NUMERIC_PINS},
        "interpreter": {"executable": sys.executable, "version": sys.version,
                        "implementation": sys.implementation.name, "flags": repr(sys.flags),
                        "isolated": sys.flags.isolated,
                        "dont_write_bytecode": sys.dont_write_bytecode},
        "calls": {"strategy": 0, "adapter": 0, "recorder": 0, "receipt": 0},
        "dependencies": None, "error": None,
    }
    try:
        summary["interpreter"]["sha256"] = digest(Path(sys.executable).read_bytes())
        summary["dependencies"] = load_numeric_dependencies(args.dependency_root)
        summary["status"] = "PASS"
    except Exception as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True, allow_nan=False, indent=2))
    return 0 if summary["status"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("interpreter", "recorder", "history", "target", "identity",
                 "source-root", "output-directory", "dependency-root"):
        parser.add_argument("--" + name, type=required_path, required=True)
    for name in ("recorder-sha256", "history-sha256", "target-sha256", "identity-sha256"):
        parser.add_argument("--" + name, type=sha256_argument, required=True)
    args = cast(RunArguments, parser.parse_args())
    if args.recorder_sha256 != RECORDER_SHA256:
        raise ValueError("Recorder pin differs from this entrypoint's fixed source pin")

    # Preserve a virtualenv interpreter symlink: resolving it can change the runtime.
    interpreter = Path(args.interpreter)
    if not interpreter.is_file() or not os.access(str(interpreter), os.X_OK):
        raise ValueError("Interpreter must be an existing executable file")
    recorder = Path(args.recorder).resolve(strict=True)
    source_bytes = recorder.read_bytes()
    if digest(source_bytes) != RECORDER_SHA256:
        raise ValueError("Recorder source SHA256 mismatch")
    # Execute the verified snapshot with a non-main name; its main/adapter never runs here.
    module = types.ModuleType("_pinned_single_receipt_acceptance")
    module.__file__ = str(recorder)
    exec(compile(source_bytes, str(recorder), "exec", dont_inherit=True), module.__dict__)

    source_root = Path(args.source_root).resolve(strict=True)
    if not source_root.is_dir():
        raise ValueError("Source root must be an existing directory")
    metadata = numeric_dependency_metadata(args.dependency_root)
    # Pass fixed inputs and pins through unchanged; the recorder validates their bytes.
    bootstrap = ("import runpy,sys; "
                 "runner=runpy.run_path(sys.argv[1]); "
                 "runner['prepare_recorder_dependencies'](sys.argv[2]); "
                 "sys.argv=sys.argv[3:]; "
                 "runpy.run_path(sys.argv[0],run_name='__main__')")
    command = [str(interpreter), "-I", "-B", "-c", bootstrap,
               str(Path(__file__).resolve(strict=True)), args.dependency_root, str(recorder),
               "--history", args.history, "--history-sha256", args.history_sha256,
               "--target", args.target, "--target-sha256", args.target_sha256,
               "--identity", args.identity, "--identity-sha256", args.identity_sha256,
               "--source-root", str(source_root)]
    requested = Path(args.output_directory)
    output = requested.parent.resolve(strict=True) / requested.name
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    receipt = output / "receipt.jsonl"
    result = output / "result.json"
    command.extend(["--output", str(receipt)])

    # Reserve the result before invocation; O_EXCL also refuses an existing symlink.
    result_fd = os.open(str(result), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(result_fd, "wb") as result_file:
        if os.path.lexists(str(receipt)):
            raise FileExistsError("Receipt leaf already exists; refusing invocation")
        if digest(recorder.read_bytes()) != RECORDER_SHA256:
            raise ValueError("Recorder source changed before invocation")
        summary: RunSummary = {
            "schema": "biglotto-single-execution-run-v1",
            "started_at_utc": utc_now(), "finished_at_utc": None,
            "request": vars(args), "result_path": str(result),
            "candidate_only": True, "scope": "candidate_output_fields_only",
            "original_source_identity_established": False,
            "original_reproduction_claimed": False,
            "historical_reproduction_proven": False,
            "historical_input_identity": "UNKNOWN", "historical_runtime_identity": "UNKNOWN",
            "recorder": {
                "path": str(recorder), "expected_sha256": RECORDER_SHA256,
                "loaded_snapshot_sha256": digest(source_bytes),
                "post_call_sha256": None, "argv": command,
                "invocation_attempts": 1, "returncode": None,
                "stdout": None, "stderr": None, "launch_error": None,
            },
            "receipt": {"path": str(receipt), "evidence": None, "read_error": None},
            "receipt_acceptance": {
                "accepted": False, "reason": "Receipt not evaluated", "execution_id": None,
            },
            "comparison": {"status": "NOT_EVALUATED", "scope": "candidate_output_fields_only"},
            "dependency_metadata": metadata, "dependency_pins_verified": False,
            "errors": [],
        }
        completed = None
        try:
            completed = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                       check=False)  # The ONLY recorder invocation; no retries.
        except OSError as exc:
            launch_error = f"{type(exc).__name__}: {exc}"
            summary["recorder"]["launch_error"] = launch_error
            summary["errors"].append(launch_error)
        if completed is not None:
            summary["recorder"]["returncode"] = completed.returncode
            summary["recorder"]["stdout"] = binary_evidence(completed.stdout)
            summary["recorder"]["stderr"] = binary_evidence(completed.stderr)

        # One read supplies both the stored evidence/hash and accept_receipt input.
        receipt_bytes = None
        try:
            receipt_fd = os.open(str(receipt), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(receipt_fd, "rb") as receipt_file:
                if not stat.S_ISREG(os.fstat(receipt_file.fileno()).st_mode):
                    raise ValueError("Receipt leaf is not a regular file")
                receipt_bytes = receipt_file.read()
            summary["receipt"]["evidence"] = binary_evidence(receipt_bytes)
        except (OSError, ValueError) as exc:
            read_error = f"{type(exc).__name__}: {exc}"
            summary["receipt"]["read_error"] = read_error
            summary["errors"].append(read_error)

        if completed is not None and receipt_bytes is not None:
            verdict = cast(RecorderAPI, module).accept_receipt(
                receipt_bytes, cast(BinaryEvidence, summary["receipt"]["evidence"])["sha256"],
                completed.returncode)
            summary["receipt_acceptance"] = {
                "accepted": verdict["accepted"], "reason": verdict["reason"],
                "execution_id": verdict["execution_id"],
            }
            summary["comparison"] = verdict["comparison"]
            if verdict["accepted"]:
                try:
                    if numeric_dependency_metadata(args.dependency_root) != metadata:
                        raise ValueError("Dependency metadata changed during invocation")
                    verify_recorded_dependencies(receipt_bytes, metadata)
                    summary["dependency_pins_verified"] = True
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    summary["errors"].append(f"{type(exc).__name__}: {exc}")
                    summary["receipt_acceptance"]["accepted"] = False
                    summary["receipt_acceptance"]["reason"] = (
                        "Recorded dependency pins not established")
        else:
            summary["receipt_acceptance"]["reason"] = (
                "Observed process exit code or receipt bytes unavailable")

        try:
            observed = digest(recorder.read_bytes())
            summary["recorder"]["post_call_sha256"] = observed
            if observed != RECORDER_SHA256:
                raise ValueError("Recorder source changed during invocation")
        except (OSError, ValueError) as exc:
            summary["errors"].append(f"{type(exc).__name__}: {exc}")
            summary["receipt_acceptance"]["accepted"] = False
            summary["receipt_acceptance"]["reason"] = (
                "Recorder source pin not established after invocation")

        summary["finished_at_utc"] = utc_now()
        # MISMATCH stays MISMATCH even when the receipt itself is accepted.
        encoded = (json.dumps(summary, ensure_ascii=True, sort_keys=True,
                              allow_nan=False, indent=2) + "\n").encode("utf-8")
        result_file.write(encoded)
        result_file.flush()
        os.fsync(result_file.fileno())
    directory_fd = os.open(str(output), os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    # Never announce acceptance before the exclusive result file was written/fsynced.
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()
    return 0 if summary["receipt_acceptance"]["accepted"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(preflight_main() if "--preflight-only" in sys.argv[1:] else main())
    except (OSError, ValueError) as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}; do not reuse or retry output", file=sys.stderr)
        raise SystemExit(1) from exc
