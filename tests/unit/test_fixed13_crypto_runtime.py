"""fixed13 crypto-runtime resolver tests.

Every scenario here uses either a real host binary (the genuinely capable
runtime this repo is developed against, and -- where the host actually has
it -- the real LibreSSL that motivated this module) or a throwaway shell
script written into ``tmp_path`` that only answers ``<binary> version``
deterministically; no test depends on a specific old-OpenSSL install
existing at a fixed path.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from lottolab.application.fixed13_crypto_runtime import (
    LOTTOLAB_FIXED13_CRYPTO_RUNTIME_SCHEMA_VERSION,
    Fixed13CryptoRuntimeUnavailableError,
    Fixed13CryptoRuntimeUnavailableReason,
    _capability_cache,
    require_capable_openssl_binary,
    resolve_openssl_binary,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GOLDEN_VECTOR_DIR = _REPO_ROOT / "tests" / "fixtures" / "fixed13_rfc3161"
_SYSTEM_LIBRESSL_CANDIDATE = "/usr/bin/openssl"

pytestmark = pytest.mark.skipif(
    not resolve_openssl_binary(golden_vector_dir=_GOLDEN_VECTOR_DIR).capable,
    reason="fixed13 crypto runtime tests require a capable OpenSSL >=3 binary to be "
    "resolvable on this host via config/fixed13_crypto_runtime.toml",
)


@pytest.fixture(autouse=True)
def reset_capability_cache() -> None:
    """Every test proves its own scenario end-to-end rather than riding a
    warm cache entry left by an earlier test."""

    _capability_cache.clear()


@pytest.fixture(scope="module")
def capable_binary_path() -> str:
    resolution = resolve_openssl_binary(golden_vector_dir=_GOLDEN_VECTOR_DIR)
    assert resolution.capable is True
    assert resolution.binary_path is not None
    return resolution.binary_path


def _raw_version_text(binary_path: str) -> str | None:
    """Independent of the module under test: used only to decide whether a
    negative-control scenario is even meaningful on this host."""

    try:
        result = subprocess.run(
            [binary_path, "version"], capture_output=True, timeout=15, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("ascii", errors="replace").strip()


def _write_fake_openssl(
    directory: Path,
    *,
    version_line: str,
    verify_exit_code: int = 1,
    name: str = "fake-openssl",
) -> Path:
    """A throwaway executable that answers ``version`` deterministically and
    fails any other invocation (e.g. ``ts -verify``)."""

    directory.mkdir(parents=True, exist_ok=True)
    script_path = directory / name
    script_path.write_text(
        textwrap.dedent(f"""\
            #!/bin/sh
            if [ "$1" = "version" ]; then
                echo "{version_line}"
                exit 0
            fi
            exit {verify_exit_code}
            """),
        encoding="ascii",
    )
    script_path.chmod(0o755)
    return script_path


def _golden_vector_digest_hex() -> str:
    metadata = json.loads((_GOLDEN_VECTOR_DIR / "golden_vector.json").read_text(encoding="utf-8"))
    digest = metadata["message_imprint_sha256_hex"]
    assert type(digest) is str
    return digest


def _write_runtime_config(
    path: Path, *, pinned_binary_path: str = "", candidate_paths: tuple[str, ...] = ()
) -> Path:
    candidates_toml = ", ".join(f'"{item}"' for item in candidate_paths)
    path.write_text(
        f'schema = "{LOTTOLAB_FIXED13_CRYPTO_RUNTIME_SCHEMA_VERSION}"\n'
        f'pinned_binary_path = "{pinned_binary_path}"\n'
        f"candidate_paths = [{candidates_toml}]\n",
        encoding="utf-8",
    )
    return path


# --- OpenSSL >=3 capable binary: PASS ----------------------------------------


def test_explicit_capable_binary_passes(capable_binary_path: str) -> None:
    resolution = resolve_openssl_binary(capable_binary_path, golden_vector_dir=_GOLDEN_VECTOR_DIR)

    assert resolution.capable is True
    assert resolution.binary_path == str(Path(capable_binary_path).resolve())
    assert resolution.reason is None
    assert resolution.openssl_version_text is not None
    assert resolution.openssl_version_text.startswith("OpenSSL ")
    assert resolution.source_tier == "EXPLICIT_ARGUMENT"


# --- LibreSSL: REJECTED -------------------------------------------------------


def test_libressl_binary_is_rejected() -> None:
    version_text = _raw_version_text(_SYSTEM_LIBRESSL_CANDIDATE)
    if version_text is None or not version_text.startswith("LibreSSL"):
        pytest.skip(f"{_SYSTEM_LIBRESSL_CANDIDATE} is not LibreSSL on this host")

    resolution = resolve_openssl_binary(
        _SYSTEM_LIBRESSL_CANDIDATE, golden_vector_dir=_GOLDEN_VECTOR_DIR
    )

    assert resolution.capable is False
    assert resolution.binary_path is None
    assert resolution.reason is Fixed13CryptoRuntimeUnavailableReason.NOT_OPENSSL


# --- OpenSSL wrong major: REJECTED -------------------------------------------


def test_openssl_wrong_major_is_rejected(tmp_path: Path) -> None:
    fake = _write_fake_openssl(tmp_path, version_line="OpenSSL 1.1.1w  11 Sep 2023")

    resolution = resolve_openssl_binary(str(fake), golden_vector_dir=_GOLDEN_VECTOR_DIR)

    assert resolution.capable is False
    assert resolution.binary_path is None
    assert resolution.reason is Fixed13CryptoRuntimeUnavailableReason.OPENSSL_MAJOR_TOO_OLD


# --- missing binary: REJECTED -------------------------------------------------


def test_missing_binary_is_rejected(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist-openssl"

    resolution = resolve_openssl_binary(str(missing), golden_vector_dir=_GOLDEN_VECTOR_DIR)

    assert resolution.capable is False
    assert resolution.reason is Fixed13CryptoRuntimeUnavailableReason.BINARY_NOT_FOUND


# --- PATH containing only/first LibreSSL: does NOT cause LibreSSL selection --


def test_path_only_libressl_does_not_cause_libressl_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point PATH at a directory containing ONLY a fake ``openssl`` that
    reports LibreSSL, with nothing explicit/env/configured set. If the
    resolver ever fell back to a PATH search, it would find and select this
    fake. It must not: resolution must fail closed instead."""

    path_only_dir = tmp_path / "path-only"
    _write_fake_openssl(path_only_dir, version_line="LibreSSL 3.3.6", name="openssl")

    monkeypatch.setenv("PATH", str(path_only_dir))
    monkeypatch.delenv("LOTTOLAB_FIXED13_OPENSSL_BINARY", raising=False)
    empty_config = _write_runtime_config(tmp_path / "empty_crypto_runtime.toml")

    resolution = resolve_openssl_binary(
        config_path=empty_config, golden_vector_dir=_GOLDEN_VECTOR_DIR
    )

    assert resolution.capable is False
    assert resolution.binary_path is None
    assert resolution.reason is Fixed13CryptoRuntimeUnavailableReason.NO_RUNTIME_CONFIGURED


# --- env explicit capable binary: PASS ---------------------------------------


def test_env_explicit_capable_binary_passes(
    capable_binary_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOTTOLAB_FIXED13_OPENSSL_BINARY", capable_binary_path)

    resolution = resolve_openssl_binary(golden_vector_dir=_GOLDEN_VECTOR_DIR)

    assert resolution.capable is True
    assert resolution.binary_path == str(Path(capable_binary_path).resolve())
    assert resolution.source_tier == "ENVIRONMENT_OVERRIDE"


# --- configured capable binary: PASS -----------------------------------------


def test_configured_pinned_capable_binary_passes(
    capable_binary_path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LOTTOLAB_FIXED13_OPENSSL_BINARY", raising=False)
    config_path = _write_runtime_config(
        tmp_path / "crypto_runtime.toml", pinned_binary_path=capable_binary_path
    )

    resolution = resolve_openssl_binary(
        config_path=config_path, golden_vector_dir=_GOLDEN_VECTOR_DIR
    )

    assert resolution.capable is True
    assert resolution.binary_path == str(Path(capable_binary_path).resolve())
    assert resolution.source_tier == "CONFIGURED_PINNED_BINARY"


def test_configured_candidate_list_capable_binary_passes(
    capable_binary_path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LOTTOLAB_FIXED13_OPENSSL_BINARY", raising=False)
    config_path = _write_runtime_config(
        tmp_path / "crypto_runtime.toml",
        candidate_paths=("/nonexistent/path/openssl", capable_binary_path),
    )

    resolution = resolve_openssl_binary(
        config_path=config_path, golden_vector_dir=_GOLDEN_VECTOR_DIR
    )

    assert resolution.capable is True
    assert resolution.binary_path == str(Path(capable_binary_path).resolve())
    assert resolution.source_tier == "DECLARED_CANDIDATE"


# --- incapable configured binary: does NOT silently become authority --------


def test_incapable_configured_pinned_binary_does_not_become_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LOTTOLAB_FIXED13_OPENSSL_BINARY", raising=False)
    fake = _write_fake_openssl(tmp_path, version_line="OpenSSL 2.9.9  1 Jan 2020")
    config_path = _write_runtime_config(
        tmp_path / "crypto_runtime.toml", pinned_binary_path=str(fake)
    )

    resolution = resolve_openssl_binary(
        config_path=config_path, golden_vector_dir=_GOLDEN_VECTOR_DIR
    )

    assert resolution.capable is False
    assert resolution.binary_path is None
    assert resolution.reason is Fixed13CryptoRuntimeUnavailableReason.OPENSSL_MAJOR_TOO_OLD


def test_incapable_declared_candidate_is_skipped_not_selected(
    capable_binary_path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An earlier declared candidate that exists but fails capability must be
    skipped in favor of a later, genuinely capable one -- never treated as
    authoritative just because it was found first."""

    monkeypatch.delenv("LOTTOLAB_FIXED13_OPENSSL_BINARY", raising=False)
    incapable = _write_fake_openssl(
        tmp_path / "incapable", version_line="OpenSSL 1.0.2  1 Jan 2015"
    )
    config_path = _write_runtime_config(
        tmp_path / "crypto_runtime.toml",
        candidate_paths=(str(incapable), capable_binary_path),
    )

    resolution = resolve_openssl_binary(
        config_path=config_path, golden_vector_dir=_GOLDEN_VECTOR_DIR
    )

    assert resolution.capable is True
    assert resolution.binary_path == str(Path(capable_binary_path).resolve())


# --- no suitable runtime: fail closed ----------------------------------------


def test_no_runtime_configured_anywhere_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LOTTOLAB_FIXED13_OPENSSL_BINARY", raising=False)
    missing_config = tmp_path / "does-not-exist.toml"

    resolution = resolve_openssl_binary(
        config_path=missing_config, golden_vector_dir=_GOLDEN_VECTOR_DIR
    )

    assert resolution.capable is False
    assert resolution.binary_path is None
    assert resolution.reason is Fixed13CryptoRuntimeUnavailableReason.NO_RUNTIME_CONFIGURED


def test_all_declared_candidates_incapable_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LOTTOLAB_FIXED13_OPENSSL_BINARY", raising=False)
    fake_one = _write_fake_openssl(tmp_path / "a", version_line="OpenSSL 1.1.1  1 Jan 2020")
    fake_two = _write_fake_openssl(tmp_path / "b", version_line="LibreSSL 3.3.6")
    config_path = _write_runtime_config(
        tmp_path / "crypto_runtime.toml",
        candidate_paths=(str(fake_one), str(fake_two)),
    )

    resolution = resolve_openssl_binary(
        config_path=config_path, golden_vector_dir=_GOLDEN_VECTOR_DIR
    )

    assert resolution.capable is False
    assert resolution.binary_path is None
    assert resolution.reason is Fixed13CryptoRuntimeUnavailableReason.NO_CAPABLE_CANDIDATE_FOUND


# --- require_capable_openssl_binary convenience wrapper ----------------------


def test_require_capable_openssl_binary_returns_path_when_capable(
    capable_binary_path: str,
) -> None:
    result = require_capable_openssl_binary(
        capable_binary_path, golden_vector_dir=_GOLDEN_VECTOR_DIR
    )

    assert result == str(Path(capable_binary_path).resolve())


def test_require_capable_openssl_binary_raises_when_incapable(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"

    with pytest.raises(Fixed13CryptoRuntimeUnavailableError):
        require_capable_openssl_binary(str(missing), golden_vector_dir=_GOLDEN_VECTOR_DIR)


# --- golden vector: PASS on capable runtime ----------------------------------


def test_golden_vector_passes_on_capable_runtime(capable_binary_path: str) -> None:
    resolution = resolve_openssl_binary(capable_binary_path, golden_vector_dir=_GOLDEN_VECTOR_DIR)

    assert resolution.capable is True


def test_golden_vector_self_test_failure_is_rejected(tmp_path: Path) -> None:
    """A binary that passes the version gate (claims OpenSSL 3.x) but fails
    the actual golden-vector crypto self-test must still be rejected -- the
    version string alone is necessary but not sufficient."""

    fake = _write_fake_openssl(
        tmp_path, version_line="OpenSSL 3.0.0  1 Jan 2022", verify_exit_code=1
    )

    resolution = resolve_openssl_binary(str(fake), golden_vector_dir=_GOLDEN_VECTOR_DIR)

    assert resolution.capable is False
    assert resolution.reason is Fixed13CryptoRuntimeUnavailableReason.GOLDEN_VECTOR_REJECTED


# --- golden vector: LibreSSL negative control --------------------------------


def test_golden_vector_rejected_under_host_libressl_negative_control() -> None:
    """The exact committed golden-vector token/chain, run through the host's
    own LibreSSL -- the CTO-identified defect made falsifiable: a profile a
    genuinely capable runtime accepts must be rejected by LibreSSL, or this
    fixture fails to distinguish anything."""

    version_text = _raw_version_text(_SYSTEM_LIBRESSL_CANDIDATE)
    if version_text is None or not version_text.startswith("LibreSSL"):
        pytest.skip(f"{_SYSTEM_LIBRESSL_CANDIDATE} is not LibreSSL on this host")

    raw_verify = subprocess.run(
        [
            _SYSTEM_LIBRESSL_CANDIDATE,
            "ts",
            "-verify",
            "-digest",
            _golden_vector_digest_hex(),
            "-in",
            str(_GOLDEN_VECTOR_DIR / "token.tsr"),
            "-token_in",
            "-CAfile",
            str(_GOLDEN_VECTOR_DIR / "root_cert.pem"),
            "-untrusted",
            str(_GOLDEN_VECTOR_DIR / "intermediate_cert.pem"),
        ],
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert raw_verify.returncode != 0

    resolution = resolve_openssl_binary(
        _SYSTEM_LIBRESSL_CANDIDATE, golden_vector_dir=_GOLDEN_VECTOR_DIR
    )

    assert resolution.capable is False
    assert resolution.reason is Fixed13CryptoRuntimeUnavailableReason.NOT_OPENSSL


# --- process-local capability cache ------------------------------------------


def test_capability_cache_avoids_repeated_golden_vector_subprocess(
    capable_binary_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_run = subprocess.run
    call_count = {"n": 0}

    def _counting_run(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        call_count["n"] += 1
        return real_run(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "lottolab.application.fixed13_crypto_runtime.subprocess.run", _counting_run
    )

    first = resolve_openssl_binary(capable_binary_path, golden_vector_dir=_GOLDEN_VECTOR_DIR)
    calls_after_first = call_count["n"]
    second = resolve_openssl_binary(capable_binary_path, golden_vector_dir=_GOLDEN_VECTOR_DIR)

    assert first.capable is True
    assert second.capable is True
    assert calls_after_first >= 2  # version probe + golden-vector self-test
    assert call_count["n"] == calls_after_first
