"""R2 source, interpreter, dataset and one-shot child boundaries.

No LottoLab module is imported at module scope. The only application imports
are in native_replay(), after a verified, source-only import finder is active.
This module does not open a production database implicitly or start a replay
on import. Every database path and output root must be explicitly supplied.
"""

from __future__ import annotations

import _thread
import fcntl
import importlib
import importlib.abc
import importlib.machinery
import importlib.metadata
import importlib.util
import os
import platform
import random
import select
import shutil
import sqlite3
import struct
import subprocess
import sys
import sysconfig
import threading
import time
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import CodeType, ModuleType
from typing import Any, cast

from tools import next_draw_54_replay_r2_lib as c

RUNNER_FILES = c.RUNNER_PATHS
RUNNER_ROOT = Path(__file__).resolve().parents[1]


def file_hash(path: Path) -> str:
    with path.open("rb") as handle:
        import hashlib

        return hashlib.file_digest(handle, "sha256").hexdigest()


def exec_capture(argv: Sequence[str], environment: Mapping[str, str] | None = None) -> bytes:
    """Capture stdout from a real posix_spawn/exec; diagnostics never become data."""
    c.require(hasattr(os, "posix_spawn"), "POSIX_SPAWN required")
    executable = shutil.which(argv[0])
    c.require(executable is not None, f"required executable unavailable: {argv[0]}")
    stdout_read, stdout_write = os.pipe()
    stderr_read, stderr_write = os.pipe()
    try:
        pid = os.posix_spawn(
            cast(str, executable),
            list(argv),
            dict(environment or os.environ),
            file_actions=[
                (os.POSIX_SPAWN_DUP2, stdout_write, 1),
                (os.POSIX_SPAWN_DUP2, stderr_write, 2),
                (os.POSIX_SPAWN_CLOSE, stdout_read),
                (os.POSIX_SPAWN_CLOSE, stdout_write),
                (os.POSIX_SPAWN_CLOSE, stderr_read),
                (os.POSIX_SPAWN_CLOSE, stderr_write),
            ],
        )
    except BaseException:
        for descriptor in (stdout_read, stdout_write, stderr_read, stderr_write):
            os.close(descriptor)
        raise
    os.close(stdout_write)
    os.close(stderr_write)
    stdout = bytearray()
    stderr = bytearray()
    active = {stdout_read: stdout, stderr_read: stderr}
    try:
        while active:
            ready, _, _ = select.select(tuple(active), (), ())
            for descriptor in ready:
                chunk = os.read(descriptor, 65_536)
                if chunk:
                    active[descriptor].extend(chunk)
                else:
                    os.close(descriptor)
                    del active[descriptor]
    finally:
        for descriptor in active:
            os.close(descriptor)
        _, status = os.waitpid(pid, 0)
    code = os.waitstatus_to_exitcode(status)
    diagnostic = stderr.decode("utf-8", errors="replace").strip()
    c.require(
        code == 0,
        f"required command failed: {argv[0]}" + (f" ({diagnostic[:500]})" if diagnostic else ""),
    )
    return bytes(stdout)


def _git(root: Path, *args: str) -> bytes:
    return exec_capture(
        ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(root), *args],
        {**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def verify_source(root: Path, *, runner_root: Path = RUNNER_ROOT) -> dict[str, Any]:
    root = root.resolve(strict=True)
    c.require(root != runner_root.resolve(), "replay source must be separately materialized")
    c.equal(
        _git(root, "rev-parse", "--show-toplevel").decode().strip(), str(root), "source worktree"
    )
    c.equal(_git(root, "rev-parse", "HEAD").decode().strip(), c.HEAD, "source HEAD")
    c.equal(_git(root, "rev-parse", "HEAD^{tree}").decode().strip(), c.TREE, "source tree")
    c.require(
        not _git(root, "status", "--porcelain=v1", "--untracked-files=all"),
        "replay source worktree must be clean",
    )
    metadata = _git(
        root,
        "ls-tree",
        "-rz",
        "--full-tree",
        c.HEAD,
        "--",
        "src/lottolab",
        "uv.lock",
        "pyproject.toml",
    )
    inventory: list[dict[str, str]] = []
    for entry in metadata.rstrip(b"\x00").split(b"\x00"):
        prefix, raw_path = entry.split(b"\t", 1)
        mode, kind, blob = prefix.decode().split()
        relative = raw_path.decode("utf-8")
        c.require(kind == "blob" and mode in ("100644", "100755"), "nonregular source object")
        path = root / relative
        c.require(not path.is_symlink() and path.resolve().is_relative_to(root), "source symlink")
        raw = path.read_bytes()
        import hashlib

        actual_blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\x00" + raw).hexdigest()
        c.equal(actual_blob, blob, "replay source working bytes")
        c.equal(bool(path.stat().st_mode & 0o111), mode == "100755", "source executable mode")
        inventory.append(
            {"path": relative, "git_blob": blob, "mode": mode, "sha256": c.sha256(raw)}
        )
    inventory.sort(key=lambda row: row["path"])
    expected = {row["path"] for row in inventory if row["path"].startswith("src/")}
    actual: set[str] = set()
    for path in (root / "src/lottolab").rglob("*"):
        c.require(not path.is_symlink(), "source symlink or import overlay")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    c.equal(sorted(actual), sorted(expected), "source extras/bytecode/import overlay")
    result = {
        "repository_head": c.HEAD,
        "repository_tree": c.TREE,
        "catalog_git_blob": c.CATALOG_BLOB,
        "catalog_sha256": c.CATALOG_SHA256,
        "uv_lock_sha256": c.LOCK_SHA256,
        "load_bearing_blobs": inventory,
        "source_inventory_sha256": c.digest(inventory),
    }
    c.validate_authority(result)
    return result


class _VerifiedLoader(importlib.machinery.SourceFileLoader):
    def __init__(self, name: str, path: Path, expected: str) -> None:
        super().__init__(name, str(path))
        self.source_path = path
        self.expected = expected

    def get_code(self, fullname: str) -> CodeType:
        # -B only prevents writes; it does not prevent stale/forged pyc reads.
        # Always compile verified source bytes, never consult a bytecode cache.
        c.require(not self.source_path.is_symlink(), "import source symlink")
        raw = self.source_path.read_bytes()
        c.equal(c.sha256(raw), self.expected, "import-source hash")
        return compile(raw, str(self.source_path), "exec", dont_inherit=True)


class ImportAnchor(importlib.abc.MetaPathFinder):
    def __init__(self, root: Path, authority: Mapping[str, Any]) -> None:
        self.root = root.resolve(strict=True)
        self.inventory = {row["path"]: row["sha256"] for row in authority["load_bearing_blobs"]}

    def find_spec(
        self, fullname: str, path: Sequence[str] | None = None, target: ModuleType | None = None
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname.split(".")[0] in {"numpy", "scipy", "secrets"}:
            raise c.ProtocolError("unclassified RNG/numeric runtime import")
        if fullname != "lottolab" and not fullname.startswith("lottolab."):
            return None
        stem = "src/" + fullname.replace(".", "/")
        candidates = [stem + "/__init__.py", stem + ".py"]
        relative = next((item for item in candidates if item in self.inventory), None)
        c.require(relative is not None, "LottoLab import outside frozen source inventory")
        absolute = self.root / cast(str, relative)
        c.require(absolute.resolve().is_relative_to(self.root), "import source escaped anchor")
        loader = _VerifiedLoader(fullname, absolute, self.inventory[cast(str, relative)])
        return importlib.util.spec_from_file_location(
            fullname,
            absolute,
            loader=loader,
            submodule_search_locations=[str(absolute.parent)]
            if absolute.name == "__init__.py"
            else None,
        )

    def install(self) -> None:
        c.require(
            not any(name == "lottolab" or name.startswith("lottolab.") for name in sys.modules),
            "LottoLab already imported before replay-source anchor",
        )
        c.require(
            not any(name.split(".")[0] in {"numpy", "scipy", "secrets"} for name in sys.modules),
            "unclassified RNG already imported",
        )
        sys.meta_path.insert(0, self)

    def records(self) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for name, module in sorted(sys.modules.items()):
            if name != "lottolab" and not name.startswith("lottolab."):
                continue
            module_file = getattr(module, "__file__", None)
            c.require(
                module_file is not None,
                "LottoLab import lacks source origin",
            )
            path = Path(cast(str, module_file))
            c.require(
                not path.is_symlink() and path.resolve().is_relative_to(self.root),
                "LottoLab import-source mismatch",
            )
            relative = path.relative_to(self.root).as_posix()
            c.require(relative in self.inventory, "LottoLab import outside inventory")
            c.equal(file_hash(path), self.inventory[relative], "loaded source integrity")
            spec = module.__spec__
            c.require(
                spec is not None
                and spec.origin == str(path)
                and isinstance(spec.loader, _VerifiedLoader),
                "unverified module loader",
            )
            if hasattr(module, "__path__"):
                c.equal(list(module.__path__), [str(path.parent)], "package import path")
            result.append({"module": name, "path": relative, "sha256": self.inventory[relative]})
        return result


def runtime_file_inventory(root: Path) -> list[dict[str, str]]:
    root = root.resolve(strict=True)
    result: list[dict[str, str]] = []
    for current, directories, files in os.walk(root):
        directories[:] = sorted(d for d in directories if d not in {"__pycache__", "site-packages"})
        for directory in directories:
            path = Path(current) / directory
            if path.is_symlink():
                target = path.resolve(strict=True)
                c.require(
                    target.is_dir() and target.is_relative_to(root),
                    "runtime directory symlink escapes its root",
                )
        for name in sorted(files):
            if name.endswith((".pyc", ".pyo")):
                continue
            path = Path(current) / name
            c.require(path.resolve().is_relative_to(root), "runtime bundle escapes its root")
            c.require(path.is_file(), "runtime bundle contains a special file")
            result.append({"path": path.relative_to(root).as_posix(), "sha256": file_hash(path)})
    return sorted(result, key=lambda item: item["path"])


def _distributions() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    prefix = Path(sys.prefix).resolve()
    for distribution in importlib.metadata.distributions():
        c.require(distribution.files is not None, "distribution lacks wheel/source file inventory")
        files: list[dict[str, str]] = []
        for entry in distribution.files or ():
            if str(entry).endswith((".pyc", ".pyo")):
                continue
            path = Path(str(distribution.locate_file(str(entry)))).resolve()
            c.require(
                path.is_file() and path.is_relative_to(prefix),
                "distribution file missing or outside frozen environment",
            )
            files.append({"path": path.relative_to(prefix).as_posix(), "sha256": file_hash(path)})
        files.sort(key=lambda item: item["path"])
        result.append(
            {
                "name": distribution.metadata["Name"].lower().replace("_", "-"),
                "version": distribution.version,
                "installer": (distribution.read_text("INSTALLER") or "UNKNOWN").strip(),
                "files": files,
                "files_sha256": c.digest(files),
            }
        )
    return sorted(result, key=lambda item: item["name"])


def _platform() -> dict[str, Any]:
    uname = os.uname()
    if uname.sysname == "Darwin":
        model_keys = (
            ("hw.model", "machdep.cpu.brand_string")
            if uname.machine in {"arm64", "aarch64"}
            else ("machdep.cpu.brand_string", "hw.model")
        )
        model = ""
        for key in model_keys:
            try:
                model = exec_capture(["/usr/sbin/sysctl", "-n", key]).decode().strip()
            except c.ProtocolError:
                continue
            if model:
                break
        if not model:
            processor = platform.processor().strip()
            model = processor or f"UNAME_MACHINE:{uname.machine}"
        try:
            features = sorted(
                set(exec_capture(["/usr/sbin/sysctl", "hw.optional"]).decode().splitlines())
            )
        except c.ProtocolError:
            features = [f"SYSCTL_HW_OPTIONAL_UNAVAILABLE:{uname.machine}"]
        if not features:
            features = [f"SYSCTL_HW_OPTIONAL_EMPTY:{uname.machine}"]
        macos = platform.mac_ver()[0]
        libc = ""
    elif uname.sysname == "Linux":
        text = Path("/proc/cpuinfo").read_text()
        model = next(
            (
                line.split(":", 1)[1].strip()
                for line in text.splitlines()
                if line.startswith("model name")
            ),
            uname.machine,
        )
        features = sorted(
            set(
                next(
                    (
                        line.split(":", 1)[1].split()
                        for line in text.splitlines()
                        if line.startswith(("flags", "Features"))
                    ),
                    list[str](),
                )
            )
        )
        macos = ""
        libc = " ".join(platform.libc_ver())
    else:
        raise c.ProtocolError("unsupported exact runtime/CPU fingerprint platform")
    return {
        "system": uname.sysname,
        "release": uname.release,
        "version": uname.version,
        "machine": uname.machine,
        "processor": uname.machine,
        "cpu_model": model,
        "cpu_features": features,
        "byteorder": sys.byteorder,
        "pointer_bits": struct.calcsize("P") * 8,
        "libc": libc,
        "macos_version": macos,
    }


def validate_environment() -> None:
    for key, value in c.ENVIRONMENT.items():
        c.equal(os.environ.get(key, ""), value, f"environment {key}")
    c.require(
        sys.flags.utf8_mode == 1 and sys.flags.hash_randomization == 0,
        "PYTHONUTF8/PYTHONHASHSEED must be set before interpreter startup",
    )
    c.require(
        sys.flags.dont_write_bytecode == 1 and sys.flags.no_user_site == 1 and sys.flags.safe_path,
        "child requires -B -s -P",
    )
    c.require(threading.active_count() == 1, "runtime must be single threaded")


def capture_runtime(
    authority: Mapping[str, Any], *, runner_root: Path = RUNNER_ROOT
) -> dict[str, Any]:
    validate_environment()
    c.require(
        sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 13),
        "CPython 3.13 required",
    )
    c.require(
        not any(name.split(".")[0] in {"numpy", "scipy"} for name in sys.modules),
        "unclassified numeric/BLAS runtime",
    )
    bundle = runtime_file_inventory(Path(sys.base_prefix).resolve())
    uv = shutil.which("uv")
    c.require(uv is not None, "uv installer identity is required")
    native: list[dict[str, str]] = []
    for name in ("math", "_random", "_hashlib", "_sqlite3"):
        module = importlib.import_module(name)
        c.require(module.__file__ is not None, "native runtime library origin missing")
        native.append({"path": name, "sha256": file_hash(Path(cast(str, module.__file__)))})

    def struct_strings(value: Any, names: str) -> dict[str, str]:
        return {
            name: (
                getattr(value, name).hex()
                if type(getattr(value, name)) is float
                else str(getattr(value, name))
            )
            for name in names.split()
        }

    result = {
        "schema_version": "NEXT_DRAW_54_REPLAY_RUNTIME_V2",
        "python": {
            "version": sys.version,
            "version_info": list(sys.version_info),
            "hexversion": sys.hexversion,
            "implementation": sys.implementation.name,
            "cache_tag": sys.implementation.cache_tag,
            "abiflags": sys.abiflags,
            "soabi": sysconfig.get_config_var("SOABI"),
            "build": list(platform.python_build()),
            "compiler": platform.python_compiler(),
            "executable_sha256": file_hash(Path(sys.executable)),
            "runtime_bundle_sha256": c.digest(bundle),
            "runtime_bundle_files": bundle,
            "stdlib_random_sha256": file_hash(Path(random.__file__)),
            "rng_state_version": 3,
        },
        "platform": _platform(),
        "numeric": {
            "float_info": struct_strings(
                sys.float_info,
                "max max_exp max_10_exp min min_exp min_10_exp dig mant_dig epsilon radix rounds",
            ),
            "hash_info": struct_strings(
                sys.hash_info, "width modulus inf nan imag algorithm hash_bits seed_bits cutoff"
            ),
            "native_libraries": sorted(native, key=lambda item: item["path"]),
            "blas": "NOT_LOADED_FOR_FROZEN_STDLIB_STRATEGIES",
        },
        "distributions": _distributions(),
        "installer": {
            "name": "uv",
            "version": exec_capture([cast(str, uv), "--version"]).decode().strip(),
            "executable_sha256": file_hash(Path(cast(str, uv))),
        },
        "environment": [
            {"name": key, "value": value} for key, value in sorted(c.ENVIRONMENT.items())
        ],
        "source_inventory_sha256": authority["source_inventory_sha256"],
        "runner_files": [
            {"path": relative, "sha256": file_hash(runner_root / relative)}
            for relative in RUNNER_FILES
        ],
    }
    c.validate_runtime(result)
    return result


def read_snapshot(path: Path) -> tuple[dict[str, Any], str, int]:
    """Read an already sealed SQLite file; no schema creation, WAL or DB writes."""
    c.require(path.is_file() and not path.is_symlink(), "source DB must be a regular sealed file")
    for suffix in ("-wal", "-shm", "-journal"):
        c.require(not Path(str(path) + suffix).exists(), "source DB has live SQLite sidecars")
    before = path.stat()
    before_hash = file_hash(path)
    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.set_authorizer(
            lambda action, _a, _b, _db, _trigger: (
                sqlite3.SQLITE_OK
                if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION)
                else sqlite3.SQLITE_DENY
            )
        )
        values = connection.execute(
            "SELECT id, draw_number, draw_date, main_numbers_json, special_numbers_json "
            "FROM draws WHERE lottery_type = ? "
            "ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC",
            ("BIG_LOTTO",),
        ).fetchall()
        selected = connection.execute(
            "SELECT draw_date, draw_number FROM draws WHERE lottery_type = ? "
            "ORDER BY draw_date DESC, draw_number DESC, id DESC LIMIT 800",
            ("BIG_LOTTO",),
        ).fetchall()
    import json

    rows: list[dict[str, Any]] = []
    for rid, number, draw_date, mains, specials in values:
        special = json.loads(specials)
        c.require(type(special) is list and len(special) == 1, "source special-number shape")
        rows.append(
            {
                "source_row_id": rid,
                "draw_number": number,
                "draw_date": draw_date,
                "main_numbers": json.loads(mains),
                "special_number": special[0],
            }
        )
    snapshot = {
        "snapshot_schema_version": "NEXT_DRAW_54_SOURCE_SNAPSHOT_V2",
        "kind": c.REAL_DATA,
        "lottery_type": "BIG_LOTTO",
        "draws": rows,
    }
    c.validate_snapshot(snapshot)
    c.equal(
        c.frozen_targets(rows),
        [{"draw_date": d, "draw_number": n} for d, n in reversed(selected)],
        "repository page-1 target selection",
    )
    after = path.stat()
    c.require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        "source DB stat stability",
    )
    c.equal(before_hash, file_hash(path), "source DB bytes unchanged")
    return snapshot, before_hash, before.st_size


def verify_database(path: Path, plan: Mapping[str, Any]) -> None:
    snapshot, sha, size = read_snapshot(path)
    c.equal(snapshot, plan["dataset"]["snapshot"], "sealed logical dataset")
    c.equal(sha, plan["dataset"]["source_db"]["sha256"], "sealed source DB hash")
    c.equal(size, plan["dataset"]["source_db"]["size_bytes"], "sealed source DB size")


def verify_database_file(path: Path, plan: Mapping[str, Any]) -> None:
    """Verify sealed database bytes without querying or deriving child targets."""
    c.require(path.is_file() and not path.is_symlink(), "source DB must be a regular sealed file")
    for suffix in ("-wal", "-shm", "-journal"):
        c.require(not Path(str(path) + suffix).exists(), "source DB has live SQLite sidecars")
    before = path.stat()
    database_sha256 = file_hash(path)
    after = path.stat()
    c.require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        "source DB stat stability",
    )
    c.equal(database_sha256, plan["dataset"]["source_db"]["sha256"], "sealed source DB hash")
    c.equal(before.st_size, plan["dataset"]["source_db"]["size_bytes"], "sealed source DB size")


@contextmanager
def serial_lock(target: Path | None = None) -> Generator[None]:
    """Nonblocking workstation lock, on a read-only interpreter handle.

    All R2 coordinators using the frozen interpreter serialize even when their
    campaign directories differ. No lock file is written into replay source.
    """
    with (target or Path(sys.executable).resolve()).open("rb") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise c.ProtocolError("SERIAL_ONLY: another R2 coordinator is active") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class ExecutionGuard:
    """Reject cache, reseed, entropy and nested process/thread use, even if caught."""

    def __init__(
        self,
        cache_class: type[Any] | None = None,
        *,
        allow_private_random: bool = False,
    ) -> None:
        self.cache_class = cache_class
        self.allow_private_random = allow_private_random
        self.saved: list[tuple[Any, str, Any]] = []
        self.violations = 0

    def _deny(self, *args: Any, **kwargs: Any) -> Any:
        self.violations += 1
        raise c.ProtocolError("forbidden cache/RNG reseed/entropy/nested concurrency activity")

    def __enter__(self) -> ExecutionGuard:
        c.require(threading.active_count() == 1, "nested threads forbidden")
        surfaces: list[tuple[Any, tuple[str, ...]]] = [
            (random, ("seed", "setstate", "SystemRandom")),
            (threading.Thread, ("start",)),
            (_thread, ("start_new_thread", "start_new", "start_joinable_thread")),
            (
                os,
                (
                    "fork",
                    "forkpty",
                    "posix_spawn",
                    "posix_spawnp",
                    "system",
                    "urandom",
                    "getrandom",
                ),
            ),
            (subprocess, ("Popen",)),
            (time, ("time", "time_ns", "monotonic", "perf_counter")),
        ]
        if not self.allow_private_random:
            surfaces.append((random, ("Random",)))
        if self.cache_class is not None:
            surfaces.append((self.cache_class, ("__init__", "lookup", "store", "clear")))
        for owner, names in surfaces:
            for name in names:
                if hasattr(owner, name):
                    self.saved.append((owner, name, getattr(owner, name)))
                    setattr(owner, name, self._deny)
        return self

    def __exit__(self, *_exc: Any) -> None:
        for owner, name, value in reversed(self.saved):
            setattr(owner, name, value)
        c.require(self.violations == 0, "forbidden execution activity observed")
        c.require(threading.active_count() == 1, "nested threads observed")


class CellLedger:
    def __init__(self, plan: dict[str, Any], identity: dict[str, Any]) -> None:
        self.plan = plan
        self.identity = identity
        self.contexts = c.target_contexts(plan)
        self.cells: list[dict[str, Any]] = []
        self.previous = ""
        self.pending = ""

    def before(self, history: list[dict[str, Any]]) -> None:
        c.require(
            bool(self.previous) and not self.pending and len(self.cells) < c.TARGET_COUNT,
            "adapter invocation outside the one continuous stream",
        )
        context = self.contexts[len(self.cells)]
        c.equal(c.digest(history), context["adapter_input_sha256"], "adapter input causal history")
        state = c.rng_state_digest(random.getstate())
        c.equal(state, self.previous, "RNG consumption outside adapter calls")
        self.pending = state

    def after(self, emitted: list[int], legal: list[int]) -> None:
        c.require(bool(self.pending), "adapter completion without matching invocation")
        state = c.rng_state_digest(random.getstate())
        cell = c.make_cell(
            self.plan,
            self.identity,
            self.contexts[len(self.cells)],
            emitted,
            legal,
            self.pending,
            state,
        )
        self.cells.append(cell)
        self.previous, self.pending = state, ""


@dataclass(frozen=True)
class PreparedReplay:
    execute: Callable[[], None]
    strategy_ids: tuple[str, ...]
    targets: list[dict[str, Any]]
    cache: object | None
    cache_class: type[Any] | None = None


def execute_seeded(
    plan: dict[str, Any], strategy_ids: list[str], factory: Callable[[CellLedger], PreparedReplay]
) -> dict[str, Any]:
    """Testable sequencing seam; the CLI always supplies native_replay, never a fake."""
    c.validate_plan(plan)
    identity = c.child_identity(plan, strategy_ids)
    seed = c.seed_record(plan["common_manifest_sha256"], identity)
    expected_post_seed = c.seeded_state_digest(seed)
    ledger = CellLedger(plan, identity)
    b0 = random.getstate()
    prepared = factory(ledger)
    c.equal(prepared.strategy_ids, tuple(strategy_ids), "one strategy per prepared child")
    c.equal(prepared.targets, plan["targets"]["vector"], "prepared frozen targets")
    c.require(prepared.cache is None, "ReplayHistoricalPredictions(cache=None) required")
    c.require(random.getstate() == b0, "bootstrap RNG drift before seeding")
    bootstrap = c.rng_state_digest(b0)
    random.seed(int(seed["seed_integer"]), version=2)
    post = c.rng_state_digest(random.getstate())
    c.equal(post, expected_post_seed, "module-global post-seed state")
    ledger.previous = post
    with ExecutionGuard(
        prepared.cache_class,
        allow_private_random=identity["strategy_id"] in c.PRIVATE_IDS,
    ):
        prepared.execute()  # Exactly one replay call, all 800 targets, no cell retries.
    c.require(
        len(ledger.cells) == c.TARGET_COUNT and not ledger.pending, "partial output/invocations"
    )
    final = c.rng_state_digest(random.getstate())
    c.equal(final, ledger.previous, "RNG consumption after last adapter call")
    return {
        "cells": ledger.cells,
        "post_seed_rng_sha256": post,
        "final_rng_sha256": final,
        "bootstrap_before_sha256": bootstrap,
        "bootstrap_after_sha256": bootstrap,
    }


def native_replay(ledger: CellLedger) -> PreparedReplay:
    """Import and construct one selected adapter only, behind ImportAnchor."""
    from lottolab.application.use_cases.build_causal_history import BuildCausalHistory
    from lottolab.application.use_cases.generate_bet import (
        GenerateOneBet,
        GenerateOneBetInput,
        GenerateOneBetResult,
        instantiate_adapter,
    )
    from lottolab.application.use_cases.replay_historical_predictions import (
        ReplayHistoricalPredictions,
        ReplayHistoricalPredictionsInput,
        ReplayResearchCache,
    )
    from lottolab.domain.draws import LotteryType
    from lottolab.domain.replay_history import ReplayCausalDrawRow
    from lottolab.domain.replay_predictions import ReplayTarget
    from lottolab.evidence.replay_artifact import recompute_snapshot_result_sha256
    from lottolab.strategies.catalog import StrategyCatalog, production_catalog

    plan, identity = ledger.plan, ledger.identity
    full_catalog = production_catalog()
    descriptor = full_catalog.get(identity["strategy_id"])
    normalized = {
        "strategy_id": descriptor.strategy_id,
        "strategy_version": descriptor.version,
        "adapter_path": descriptor.adapter_path,
        "min_history": descriptor.min_history,
        "native_ticket_count": descriptor.native_ticket_count,
        "response_shape": descriptor.response_shape.value,
    }
    c.equal(normalized, identity, "runtime selected descriptor")
    catalog = StrategyCatalog((descriptor,))
    module_name, class_name = identity["adapter_path"].split(":")
    adapter_class = getattr(importlib.import_module(module_name), class_name)
    adapter = instantiate_adapter(descriptor.strategy_id, adapter_class)

    class ObservedGenerateOneBet(GenerateOneBet):
        def execute(self, request: GenerateOneBetInput) -> GenerateOneBetResult:
            c.require(request.seed is None, "request seed must remain unset")
            c.equal(request.strategy_id, identity["strategy_id"], "adapter call identity")
            c.require(request.lottery_type is LotteryType.BIG_LOTTO, "adapter lottery identity")
            ledger.before(
                [
                    {"draw": row.draw, "date": row.date, "numbers": list(row.numbers)}
                    for row in request.history
                ]
            )
            execution = self.execute_with_emission(request)
            c.equal(execution.legal_bet.status.value, "OK", "prediction must be OK")
            c.require(execution.legal_bet.reason_code is None, "prediction reason must be absent")
            emitted = list(cast(tuple[int, ...], execution.emitted_main_numbers))
            legal = list(cast(tuple[int, ...], execution.legal_bet.numbers))
            ledger.after(emitted, legal)
            return execution.legal_bet

    rows = tuple(
        ReplayCausalDrawRow(
            lottery_type=LotteryType.BIG_LOTTO,
            draw_number=r["draw_number"],
            draw_date=date.fromisoformat(r["draw_date"]),
            main_numbers=tuple(r["main_numbers"]),
            special_number=r["special_number"],
        )
        for r in plan["dataset"]["snapshot"]["draws"]
    )

    class SealedHistoryReader:
        def read_causal_history(
            self,
            lottery_type: LotteryType,
            target_draw_number: str,
            *,
            maximum_history_draws: int | None = None,
        ) -> tuple[ReplayCausalDrawRow, ...]:
            c.require(
                lottery_type is LotteryType.BIG_LOTTO and maximum_history_draws is None,
                "full causal prefix required",
            )
            target = next(row for row in rows if row.draw_number == target_draw_number)
            return tuple(
                row
                for row in rows
                if (row.draw_date, int(row.draw_number))
                < (target.draw_date, int(target.draw_number))
            )

    replay = ReplayHistoricalPredictions(
        BuildCausalHistory(SealedHistoryReader),
        ObservedGenerateOneBet(catalog, {descriptor.strategy_id: adapter}),
        catalog,
        cache=None,
    )
    cache_value = vars(replay).get("_cache", object())
    request = ReplayHistoricalPredictionsInput(
        lottery_type=LotteryType.BIG_LOTTO,
        dataset_id=plan["dataset"]["dataset_id"],
        dataset_version=plan["dataset"]["dataset_version"],
        targets=tuple(
            ReplayTarget(draw_number=t["draw_number"], draw_date=date.fromisoformat(t["draw_date"]))
            for t in plan["targets"]["vector"]
        ),
        strategy_ids=(descriptor.strategy_id,),
        maximum_history_draws=None,
        minimum_history_draws=descriptor.min_history,
    )

    def execute() -> None:
        c.require(vars(replay).get("_cache", object()) is None, "cache configuration changed")
        snapshots = replay.execute(request).snapshots
        c.require(len(snapshots) == c.TARGET_COUNT == len(ledger.cells), "partial replay snapshots")
        for snapshot, cell in zip(snapshots, ledger.cells, strict=True):
            c.equal(snapshot.history_status, "OK", "history status")
            c.equal(
                snapshot.result_sha256,
                recompute_snapshot_result_sha256(snapshot),
                "replay self hash",
            )
            c.equal(
                snapshot.result_sha256, cell["replay_result_sha256"], "snapshot/context identity"
            )
        c.require(vars(replay).get("_cache", object()) is None, "cache configuration changed")

    return PreparedReplay(
        execute=execute,
        strategy_ids=request.strategy_ids,
        targets=plan["targets"]["vector"],
        cache=cache_value,
        cache_class=ReplayResearchCache,
    )


def execute_native_child(
    plan: dict[str, Any], source: Path, database: Path, strategy_ids: list[str]
) -> dict[str, Any]:
    c.validate_plan(plan)
    c.child_identity(plan, strategy_ids)
    c.equal(plan["dataset"]["snapshot"]["kind"], c.REAL_DATA, "real child requires sealed DB data")
    authority = verify_source(source)
    c.equal(authority, plan["authority"], "child source authority")
    verify_database_file(database, plan)
    c.equal(capture_runtime(authority), plan["runtime_fingerprint"], "child runtime fingerprint")
    anchor = ImportAnchor(source, authority)
    anchor.install()
    try:
        observation = execute_seeded(plan, strategy_ids, native_replay)
        modules = anchor.records()
        c.equal(verify_source(source), authority, "source integrity after replay")
        verify_database_file(database, plan)
        c.equal(
            capture_runtime(authority),
            plan["runtime_fingerprint"],
            "runtime integrity after replay",
        )
        source_record = {
            "repository_head": c.HEAD,
            "repository_tree": c.TREE,
            "source_inventory_sha256_before": authority["source_inventory_sha256"],
            "source_inventory_sha256_after": authority["source_inventory_sha256"],
            "source_draw_db_sha256_before": plan["dataset"]["source_db"]["sha256"],
            "source_draw_db_sha256_after": file_hash(database),
            "import_anchor_verified": True,
            "imported_modules": modules,
        }
        identity = c.child_identity(plan, strategy_ids)
        result = c.make_strategy_result(
            plan,
            identity,
            observation["cells"],
            source_record,
            observation["post_seed_rng_sha256"],
            observation["final_rng_sha256"],
        )
        c.validate_strategy_result(plan, identity, result, c.target_contexts(plan))
        child = c.make_child_result(
            result,
            observation["bootstrap_before_sha256"],
            observation["bootstrap_after_sha256"],
        )
        c.validate_child_result(plan, identity, child)
        return child
    finally:
        sys.meta_path.remove(anchor)
