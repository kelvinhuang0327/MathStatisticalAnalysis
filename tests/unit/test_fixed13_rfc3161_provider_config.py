"""Fixed-13 RFC3161 production provider/trust-anchor config tests.

All root certificates used for fail-closed/negative fixtures are throwaway
self-signed CAs generated with the host's own ``openssl`` binary into
``tmp_path``-rooted directories; no network call is made in this file.  The
canonical-production-config tests below do read the two real committed PEMs
under ``config/`` (no network call there either -- both files are already
on disk) to prove the shipped config matches its own pinned fingerprints.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from lottolab.application.fixed13_crypto_runtime import resolve_openssl_binary
from lottolab.application.fixed13_pre_outcome_timing_receipt import (
    RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
    PinnedTrustAnchorSet,
)
from lottolab.application.fixed13_rfc3161_provider_config import (
    FIXED13_RFC3161_ISSUANCE_STRATEGY,
    FIXED13_RFC3161_MESSAGE_IMPRINT_ALGORITHM,
    LOTTOLAB_FIXED13_RFC3161_PROVIDER_SET_SCHEMA_VERSION,
    Fixed13Rfc3161ProviderConfig,
    Fixed13Rfc3161ProviderConfigError,
    bind_archived_chain_root,
    compute_der_sha256,
    load_fixed13_rfc3161_provider_set,
)

pytestmark = pytest.mark.skipif(
    not resolve_openssl_binary().capable,
    reason="fixed13 RFC3161 provider config requires a capable fixed13 OpenSSL "
    "runtime to be resolvable on this host (see config/fixed13_crypto_runtime.toml)",
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRODUCTION_CONFIG_PATH = _REPO_ROOT / "config" / "fixed13_rfc3161_tsa.toml"
_FREETSA_ENDPOINT = "https://freetsa.org/tsr"
_DIGICERT_ENDPOINT = "http://timestamp.digicert.com"


def _run_openssl(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(args, cwd=cwd, capture_output=True, timeout=30, check=False)
    return result


def _der_sha256_via_openssl(pem_path: Path) -> str:
    """An independent (non-module) DER/SHA-256 computation used only to seed
    "known correct" fixture fingerprints and as a ground truth to compare
    ``compute_der_sha256`` against."""

    result = subprocess.run(
        ["openssl", "x509", "-in", str(pem_path), "-outform", "DER"],
        capture_output=True,
        timeout=30,
        check=True,
    )
    return hashlib.sha256(result.stdout).hexdigest()


def _generate_self_signed_root_ca(directory: Path, *, common_name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    key_path = directory / "key.pem"
    cert_path = directory / "root.pem"
    result = _run_openssl(
        ["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(key_path)],
        cwd=directory,
    )
    assert result.returncode == 0, result.stderr.decode()
    result = _run_openssl(
        [
            "openssl",
            "req",
            "-x509",
            "-new",
            "-key",
            str(key_path),
            "-sha256",
            "-days",
            "2",
            "-subj",
            f"/CN={common_name}/O=LottoLabTest",
            "-addext",
            "basicConstraints=critical,CA:true",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
            "-out",
            str(cert_path),
        ],
        cwd=directory,
    )
    assert result.returncode == 0, result.stderr.decode()
    return cert_path


@pytest.fixture(scope="module")
def root_ca_pems(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    directory = tmp_path_factory.mktemp("fixed13-rfc3161-root-cas")
    correct = _generate_self_signed_root_ca(
        directory / "correct", common_name="LottoLab Test Root A"
    )
    wrong = _generate_self_signed_root_ca(directory / "wrong", common_name="LottoLab Test Root B")
    return {
        "correct": correct.read_text(encoding="ascii"),
        "correct_der_sha256": _der_sha256_via_openssl(correct),
        "wrong": wrong.read_text(encoding="ascii"),
        "wrong_der_sha256": _der_sha256_via_openssl(wrong),
    }


def _write_cert(repo_root: Path, relative_path: str, pem_text: str) -> None:
    target = repo_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(pem_text, encoding="ascii")


def _providers_block(
    *,
    freetsa_der_sha256: str,
    digicert_der_sha256: str,
    freetsa_endpoint: str = _FREETSA_ENDPOINT,
    digicert_endpoint: str = _DIGICERT_ENDPOINT,
    freetsa_enabled: str = "true",
    digicert_enabled: str = "true",
) -> str:
    return (
        "[[providers]]\n"
        'provider_id = "freetsa"\n'
        f'official_endpoint = "{freetsa_endpoint}"\n'
        f"enabled = {freetsa_enabled}\n"
        'policy_status = "SUPPORTED"\n'
        'root_certificate_path = "config/freetsa_root.pem"\n'
        f'root_certificate_der_sha256 = "{freetsa_der_sha256}"\n'
        "\n"
        "[[providers]]\n"
        'provider_id = "digicert"\n'
        f'official_endpoint = "{digicert_endpoint}"\n'
        f"enabled = {digicert_enabled}\n"
        'policy_status = "SUPPORTED"\n'
        'root_certificate_path = "config/digicert_root.pem"\n'
        f'root_certificate_der_sha256 = "{digicert_der_sha256}"\n'
    )


def _write_config(
    tmp_path: Path,
    *,
    providers_toml: str,
    schema: str = LOTTOLAB_FIXED13_RFC3161_PROVIDER_SET_SCHEMA_VERSION,
    proof_type: str = RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
    message_imprint_algorithm: str = FIXED13_RFC3161_MESSAGE_IMPRINT_ALGORITHM,
    issuance_strategy: str = FIXED13_RFC3161_ISSUANCE_STRATEGY,
    minimum_valid_receipts: int = 1,
) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "fixed13_rfc3161_tsa.toml"
    config_path.write_text(
        f'schema = "{schema}"\n'
        f'proof_type = "{proof_type}"\n'
        f'message_imprint_algorithm = "{message_imprint_algorithm}"\n'
        f'issuance_strategy = "{issuance_strategy}"\n'
        f"minimum_valid_receipts = {minimum_valid_receipts}\n"
        "\n"
        f"{providers_toml}",
        encoding="utf-8",
    )
    return config_path


def _valid_repo(tmp_path: Path, root_ca_pems: dict[str, str]) -> Path:
    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["correct"])
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256=root_ca_pems["correct_der_sha256"],
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    return _write_config(tmp_path, providers_toml=providers)


# --------------------------------------------------------------------------
# Canonical production config
# --------------------------------------------------------------------------


def test_production_config_file_exists() -> None:
    assert _PRODUCTION_CONFIG_PATH.is_file()


def test_production_config_schema_exact() -> None:
    provider_set = load_fixed13_rfc3161_provider_set(_PRODUCTION_CONFIG_PATH)
    assert provider_set.schema == "LOTTOLAB_FIXED13_RFC3161_PROVIDER_SET_V1"


def test_production_config_proof_type_exact() -> None:
    provider_set = load_fixed13_rfc3161_provider_set(_PRODUCTION_CONFIG_PATH)
    assert provider_set.proof_type == "RFC3161_TSA_TOKEN_V1"
    assert provider_set.proof_type == RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE


def test_production_config_message_imprint_algorithm_exact() -> None:
    provider_set = load_fixed13_rfc3161_provider_set(_PRODUCTION_CONFIG_PATH)
    assert provider_set.message_imprint_algorithm == "SHA256"


def test_production_config_issuance_strategy_exact() -> None:
    provider_set = load_fixed13_rfc3161_provider_set(_PRODUCTION_CONFIG_PATH)
    assert provider_set.issuance_strategy == "ISSUE_TO_ALL"


def test_production_config_minimum_valid_receipts_exact() -> None:
    provider_set = load_fixed13_rfc3161_provider_set(_PRODUCTION_CONFIG_PATH)
    assert provider_set.minimum_valid_receipts == 1


def test_production_config_has_exactly_two_providers() -> None:
    provider_set = load_fixed13_rfc3161_provider_set(_PRODUCTION_CONFIG_PATH)
    assert len(provider_set.providers) == 2


def test_production_config_provider_ids_exact() -> None:
    provider_set = load_fixed13_rfc3161_provider_set(_PRODUCTION_CONFIG_PATH)
    assert {provider.provider_id for provider in provider_set.providers} == {"freetsa", "digicert"}


def test_production_config_endpoints_exact() -> None:
    provider_set = load_fixed13_rfc3161_provider_set(_PRODUCTION_CONFIG_PATH)
    assert provider_set.provider("freetsa").official_endpoint == _FREETSA_ENDPOINT
    assert provider_set.provider("digicert").official_endpoint == _DIGICERT_ENDPOINT


def test_production_config_root_fingerprints_match_committed_pem_files() -> None:
    provider_set = load_fixed13_rfc3161_provider_set(_PRODUCTION_CONFIG_PATH)
    freetsa = provider_set.provider("freetsa")
    digicert = provider_set.provider("digicert")
    assert freetsa.root_certificate_der_sha256 == _der_sha256_via_openssl(
        _REPO_ROOT / freetsa.root_certificate_path
    )
    assert digicert.root_certificate_der_sha256 == _der_sha256_via_openssl(
        _REPO_ROOT / digicert.root_certificate_path
    )


def test_production_config_loads_and_verifies_end_to_end() -> None:
    provider_set = load_fixed13_rfc3161_provider_set(_PRODUCTION_CONFIG_PATH, verify_roots=True)
    freetsa_anchor = provider_set.pinned_trust_anchor("freetsa")
    digicert_anchor = provider_set.pinned_trust_anchor("digicert")
    assert isinstance(freetsa_anchor, PinnedTrustAnchorSet)
    assert isinstance(digicert_anchor, PinnedTrustAnchorSet)
    assert "BEGIN CERTIFICATE" in freetsa_anchor.bundle_text()
    assert "BEGIN CERTIFICATE" in digicert_anchor.bundle_text()


# --------------------------------------------------------------------------
# Root pinning
# --------------------------------------------------------------------------


def test_root_pem_parses_and_pins(tmp_path: Path, root_ca_pems: dict[str, str]) -> None:
    config_path = _valid_repo(tmp_path, root_ca_pems)
    provider_set = load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)
    anchor = provider_set.pinned_trust_anchor("freetsa")
    assert anchor.ca_certificates_pem == (root_ca_pems["correct"],)


def test_der_conversion_is_deterministic(root_ca_pems: dict[str, str]) -> None:
    first = compute_der_sha256(root_ca_pems["correct"])
    second = compute_der_sha256(root_ca_pems["correct"])
    assert first == second == root_ca_pems["correct_der_sha256"]


def test_compute_der_sha256_matches_independent_openssl_computation(
    tmp_path: Path, root_ca_pems: dict[str, str]
) -> None:
    cert_path = tmp_path / "independent.pem"
    cert_path.write_text(root_ca_pems["correct"], encoding="ascii")
    assert compute_der_sha256(root_ca_pems["correct"]) == _der_sha256_via_openssl(cert_path)


def test_different_certificate_substitution_fails_closed(
    tmp_path: Path, root_ca_pems: dict[str, str]
) -> None:
    """The PEM on disk is the WRONG root even though the config's declared
    fingerprint is well-formed; the mismatch must be caught at verify time."""

    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["wrong"])
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256=root_ca_pems["correct_der_sha256"],  # pinned to the CORRECT root...
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    config_path = _write_config(tmp_path, providers_toml=providers)
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="fingerprint mismatch"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_malformed_certificate_fails_closed(tmp_path: Path, root_ca_pems: dict[str, str]) -> None:
    _write_cert(
        tmp_path,
        "config/freetsa_root.pem",
        "-----BEGIN CERTIFICATE-----\nTk9UQUNFUlQ=\n-----END CERTIFICATE-----\n",
    )
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256="0" * 64,
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    config_path = _write_config(tmp_path, providers_toml=providers)
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="malformed"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_missing_certificate_fails_closed(tmp_path: Path, root_ca_pems: dict[str, str]) -> None:
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256=root_ca_pems["correct_der_sha256"],
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    config_path = _write_config(tmp_path, providers_toml=providers)
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="missing"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_non_ca_certificate_fails_closed(tmp_path: Path, root_ca_pems: dict[str, str]) -> None:
    """A validly-formed but CA:false leaf certificate must not pin as a root."""

    directory = tmp_path / "leaf-ca-src"
    directory.mkdir()
    root_ca = _generate_self_signed_root_ca(directory, common_name="LottoLab Test Root")
    key_path = directory / "key.pem"
    leaf_key = directory / "leaf_key.pem"
    leaf_csr = directory / "leaf.csr"
    leaf_cert = directory / "leaf.pem"
    subprocess.run(
        ["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(leaf_key)],
        cwd=directory,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "openssl", "req", "-new", "-key", str(leaf_key), "-subj", "/CN=LottoLab Test Leaf",
            "-out", str(leaf_csr),
        ],
        cwd=directory,
        check=True,
        capture_output=True,
    )
    ext_file = directory / "leaf_ext.cnf"
    ext_file.write_text("basicConstraints=critical,CA:false\n", encoding="ascii")
    subprocess.run(
        [
            "openssl", "x509", "-req", "-in", str(leaf_csr), "-CA", str(root_ca), "-CAkey",
            str(key_path), "-CAcreateserial", "-days", "2", "-sha256", "-extfile", str(ext_file),
            "-out", str(leaf_cert),
        ],
        cwd=directory,
        check=True,
        capture_output=True,
    )
    leaf_pem = leaf_cert.read_text(encoding="ascii")
    _write_cert(tmp_path, "config/freetsa_root.pem", leaf_pem)
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256=_der_sha256_via_openssl(leaf_cert),
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    config_path = _write_config(tmp_path, providers_toml=providers)
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="not a CA certificate"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


# --------------------------------------------------------------------------
# Provider-set fail closed
# --------------------------------------------------------------------------


def test_only_freetsa_present_fails_closed(tmp_path: Path, root_ca_pems: dict[str, str]) -> None:
    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["correct"])
    providers = (
        "[[providers]]\n"
        'provider_id = "freetsa"\n'
        f'official_endpoint = "{_FREETSA_ENDPOINT}"\n'
        "enabled = true\n"
        'policy_status = "SUPPORTED"\n'
        'root_certificate_path = "config/freetsa_root.pem"\n'
        f'root_certificate_der_sha256 = "{root_ca_pems["correct_der_sha256"]}"\n'
    )
    config_path = _write_config(tmp_path, providers_toml=providers)
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="exactly 2 providers"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_only_digicert_present_fails_closed(tmp_path: Path, root_ca_pems: dict[str, str]) -> None:
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = (
        "[[providers]]\n"
        'provider_id = "digicert"\n'
        f'official_endpoint = "{_DIGICERT_ENDPOINT}"\n'
        "enabled = true\n"
        'policy_status = "SUPPORTED"\n'
        'root_certificate_path = "config/digicert_root.pem"\n'
        f'root_certificate_der_sha256 = "{root_ca_pems["correct_der_sha256"]}"\n'
    )
    config_path = _write_config(tmp_path, providers_toml=providers)
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="exactly 2 providers"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_third_provider_fails_closed(tmp_path: Path, root_ca_pems: dict[str, str]) -> None:
    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["correct"])
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    _write_cert(tmp_path, "config/sectigo_root.pem", root_ca_pems["wrong"])
    providers = _providers_block(
        freetsa_der_sha256=root_ca_pems["correct_der_sha256"],
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    providers += (
        "\n[[providers]]\n"
        'provider_id = "sectigo"\n'
        'official_endpoint = "https://timestamp.sectigo.com"\n'
        "enabled = true\n"
        'policy_status = "SUPPORTED"\n'
        'root_certificate_path = "config/sectigo_root.pem"\n'
        f'root_certificate_der_sha256 = "{root_ca_pems["wrong_der_sha256"]}"\n'
    )
    config_path = _write_config(tmp_path, providers_toml=providers)
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match=r"unsupported .* provider_id"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_duplicate_provider_fails_closed(tmp_path: Path, root_ca_pems: dict[str, str]) -> None:
    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["correct"])
    one_provider = (
        "[[providers]]\n"
        'provider_id = "freetsa"\n'
        f'official_endpoint = "{_FREETSA_ENDPOINT}"\n'
        "enabled = true\n"
        'policy_status = "SUPPORTED"\n'
        'root_certificate_path = "config/freetsa_root.pem"\n'
        f'root_certificate_der_sha256 = "{root_ca_pems["correct_der_sha256"]}"\n'
    )
    providers = one_provider + "\n" + one_provider
    config_path = _write_config(tmp_path, providers_toml=providers)
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="unique"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_endpoint_alteration_fails_closed(tmp_path: Path, root_ca_pems: dict[str, str]) -> None:
    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["correct"])
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256=root_ca_pems["correct_der_sha256"],
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
        freetsa_endpoint="https://evil.example/tsr",
    )
    config_path = _write_config(tmp_path, providers_toml=providers)
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="official_endpoint"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_digicert_http_endpoint_is_accepted_as_qualified(
    tmp_path: Path, root_ca_pems: dict[str, str]
) -> None:
    """DigiCert's official endpoint is plain HTTP; the loader must not reject
    it solely for that -- integrity comes from the signed token, not TLS."""

    config_path = _valid_repo(tmp_path, root_ca_pems)
    provider_set = load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)
    assert provider_set.provider("digicert").official_endpoint.startswith("http://")


def test_root_fingerprint_alteration_fails_closed(
    tmp_path: Path, root_ca_pems: dict[str, str]
) -> None:
    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["correct"])
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256="ab" * 32,
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    config_path = _write_config(tmp_path, providers_toml=providers)
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="fingerprint mismatch"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_disabled_provider_fails_closed(tmp_path: Path, root_ca_pems: dict[str, str]) -> None:
    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["correct"])
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256=root_ca_pems["correct_der_sha256"],
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
        freetsa_enabled="false",
    )
    config_path = _write_config(tmp_path, providers_toml=providers)
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="enabled"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_wrong_proof_type_fails_closed(tmp_path: Path, root_ca_pems: dict[str, str]) -> None:
    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["correct"])
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256=root_ca_pems["correct_der_sha256"],
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    config_path = _write_config(
        tmp_path, providers_toml=providers, proof_type="SOME_OTHER_PROOF_TYPE_V1"
    )
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="proof_type"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_wrong_digest_algorithm_fails_closed(tmp_path: Path, root_ca_pems: dict[str, str]) -> None:
    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["correct"])
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256=root_ca_pems["correct_der_sha256"],
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    config_path = _write_config(
        tmp_path, providers_toml=providers, message_imprint_algorithm="SHA1"
    )
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="message_imprint_algorithm"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_unsupported_issuance_strategy_fails_closed(
    tmp_path: Path, root_ca_pems: dict[str, str]
) -> None:
    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["correct"])
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256=root_ca_pems["correct_der_sha256"],
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    config_path = _write_config(
        tmp_path, providers_toml=providers, issuance_strategy="ISSUE_TO_FIRST_AVAILABLE"
    )
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="issuance_strategy"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_unknown_schema_fails_closed(tmp_path: Path, root_ca_pems: dict[str, str]) -> None:
    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["correct"])
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256=root_ca_pems["correct_der_sha256"],
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    config_path = _write_config(tmp_path, providers_toml=providers, schema="SOME_OTHER_SCHEMA_V1")
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="schema"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_missing_config_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="cannot read"):
        load_fixed13_rfc3161_provider_set(
            tmp_path / "does-not-exist.toml", repository_root=tmp_path
        )


def test_minimum_valid_receipts_zero_fails_closed(
    tmp_path: Path, root_ca_pems: dict[str, str]
) -> None:
    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["correct"])
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256=root_ca_pems["correct_der_sha256"],
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    config_path = _write_config(tmp_path, providers_toml=providers, minimum_valid_receipts=0)
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="minimum_valid_receipts"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_minimum_valid_receipts_above_provider_count_fails_closed(
    tmp_path: Path, root_ca_pems: dict[str, str]
) -> None:
    _write_cert(tmp_path, "config/freetsa_root.pem", root_ca_pems["correct"])
    _write_cert(tmp_path, "config/digicert_root.pem", root_ca_pems["correct"])
    providers = _providers_block(
        freetsa_der_sha256=root_ca_pems["correct_der_sha256"],
        digicert_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    config_path = _write_config(tmp_path, providers_toml=providers, minimum_valid_receipts=3)
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="minimum_valid_receipts"):
        load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)


def test_root_certificate_path_may_not_escape_repository_root(
    tmp_path: Path, root_ca_pems: dict[str, str]
) -> None:
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="safe repository-root-relative"):
        Fixed13Rfc3161ProviderConfig(
            provider_id="freetsa",
            official_endpoint=_FREETSA_ENDPOINT,
            enabled=True,
            policy_status="SUPPORTED",
            root_certificate_path="../outside/root.pem",
            root_certificate_der_sha256=root_ca_pems["correct_der_sha256"],
        )


# --------------------------------------------------------------------------
# No system trust fallback / no network / no provider timestamp request
# --------------------------------------------------------------------------

_MODULE_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "lottolab"
    / "application"
    / "fixed13_rfc3161_provider_config.py"
).read_text(encoding="utf-8")

_FORBIDDEN_TRUST_TOKENS = (
    "create_default_context",
    "import certifi",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "truststore",
    "CAfile",
    "CApath",
    "/etc/ssl",
)
_FORBIDDEN_NETWORK_TOKENS = ("urllib", "requests", "httpx", "socket", " ts ", '"ts"', "'ts'")


def test_module_source_never_references_system_trust_store_apis() -> None:
    for token in _FORBIDDEN_TRUST_TOKENS:
        assert token not in _MODULE_SOURCE, f"forbidden system-trust token found: {token!r}"


def test_module_source_never_references_network_or_ts_request_apis() -> None:
    for token in _FORBIDDEN_NETWORK_TOKENS:
        assert token not in _MODULE_SOURCE, f"forbidden network/timestamp token found: {token!r}"


def test_loader_ignores_ssl_environment_overrides(
    tmp_path: Path, root_ca_pems: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even with SSL_CERT_FILE/SSL_CERT_DIR pointed at garbage, loading must
    still succeed using only the repo-pinned root -- proving those variables
    are never consulted."""

    config_path = _valid_repo(tmp_path, root_ca_pems)
    bogus = tmp_path / "does-not-exist-trust-store"
    monkeypatch.setenv("SSL_CERT_FILE", str(bogus / "nope.pem"))
    monkeypatch.setenv("SSL_CERT_DIR", str(bogus))
    provider_set = load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)
    assert len(provider_set.providers) == 2


# --------------------------------------------------------------------------
# Archived-chain binding
# --------------------------------------------------------------------------


def test_archived_chain_binding_correct_root_passes(
    tmp_path: Path, root_ca_pems: dict[str, str]
) -> None:
    config_path = _valid_repo(tmp_path, root_ca_pems)
    provider_set = load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)
    provider = provider_set.provider("freetsa")
    anchor = bind_archived_chain_root(
        provider,
        repository_root=tmp_path,
        archived_chain_root_der_sha256=root_ca_pems["correct_der_sha256"],
    )
    assert isinstance(anchor, PinnedTrustAnchorSet)


def test_archived_chain_binding_different_root_fails(
    tmp_path: Path, root_ca_pems: dict[str, str]
) -> None:
    config_path = _valid_repo(tmp_path, root_ca_pems)
    provider_set = load_fixed13_rfc3161_provider_set(config_path, repository_root=tmp_path)
    provider = provider_set.provider("freetsa")
    with pytest.raises(Fixed13Rfc3161ProviderConfigError, match="does not match"):
        bind_archived_chain_root(
            provider,
            repository_root=tmp_path,
            archived_chain_root_der_sha256=root_ca_pems["wrong_der_sha256"],
        )
