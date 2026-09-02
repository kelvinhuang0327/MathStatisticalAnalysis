"""Pre-outcome commitment envelope and offline RFC3161 receipt verifier tests.

All RFC3161 tokens used here are issued by a throwaway CA/TSA generated with
the host's own ``openssl`` binary into ``tmp_path``-rooted directories; no
network call is made and no key material is committed.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lottolab.application.fixed13_crypto_runtime import (
    Fixed13CryptoRuntimeResolution,
    Fixed13CryptoRuntimeUnavailableReason,
    resolve_openssl_binary,
)
from lottolab.application.fixed13_pre_outcome_timing_receipt import (
    RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
    Fixed13PreOutcomeCommitment,
    PinnedTrustAnchorSet,
    PreOutcomeTimingReceiptReasonCode,
    _parse_tst_info,
    verify_rfc3161_pre_outcome_receipt,
)
from lottolab.domain.draws import LotteryType

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GOLDEN_VECTOR_DIR = _REPO_ROOT / "tests" / "fixtures" / "fixed13_rfc3161"

pytestmark = pytest.mark.skipif(
    not resolve_openssl_binary().capable,
    reason="the offline RFC3161 verifier backend requires a capable fixed13 OpenSSL "
    "runtime to be resolvable on this host (see config/fixed13_crypto_runtime.toml)",
)

_BASE_SCHEDULED_AT = datetime(2026, 9, 10, 20, 30, tzinfo=UTC)


def _commitment(
    *,
    official_draw_identity: str = "115000083",
    target_scheduled_at: datetime = _BASE_SCHEDULED_AT,
    target_registration_digest: str = "1" * 64,
    prediction_record_digest: str = "2" * 64,
    freeze_artifact_file_sha256: str = "3" * 64,
    cohort_membership_strategy_ids_lcj1_sha256: str = "4" * 64,
) -> Fixed13PreOutcomeCommitment:
    return Fixed13PreOutcomeCommitment.create(
        official_draw_identity=official_draw_identity,
        target_scheduled_at=target_scheduled_at,
        target_registration_digest=target_registration_digest,
        prediction_record_digest=prediction_record_digest,
        freeze_artifact_file_sha256=freeze_artifact_file_sha256,
        cohort_membership_strategy_ids_lcj1_sha256=cohort_membership_strategy_ids_lcj1_sha256,
    )


def _run_openssl(args: list[str], *, cwd: Path) -> None:
    result = subprocess.run(
        args, cwd=cwd, capture_output=True, timeout=30, check=False
    )
    assert result.returncode == 0, (args, result.stdout.decode(), result.stderr.decode())


@dataclass(frozen=True)
class _TestTsa:
    """A throwaway local CA + TSA, entirely rooted under one tmp_path directory."""

    directory: Path
    ca_cert_pem: str
    tsa_cert_path: Path
    config_path: Path

    @property
    def trust_anchors(self) -> PinnedTrustAnchorSet:
        return PinnedTrustAnchorSet((self.ca_cert_pem,))

    def issue_token(
        self, *, digest_hex: str, digest_algorithm: str = "sha256", with_cert: bool = True
    ) -> bytes:
        tag = f"{digest_algorithm}-{digest_hex[:16]}-{'cert' if with_cert else 'nocert'}"
        request_path = self.directory / f"request-{tag}.tsq"
        token_path = self.directory / f"token-{tag}.tst"
        query_args = [
            "openssl",
            "ts",
            "-query",
            "-digest",
            digest_hex,
            f"-{digest_algorithm}",
            "-out",
            str(request_path),
        ]
        if with_cert:
            query_args.insert(-2, "-cert")
        _run_openssl(query_args, cwd=self.directory)
        _run_openssl(
            [
                "openssl",
                "ts",
                "-reply",
                "-config",
                str(self.config_path),
                "-queryfile",
                str(request_path),
                "-out",
                str(token_path),
                "-token_out",
            ],
            cwd=self.directory,
        )
        return token_path.read_bytes()


def _build_test_tsa(
    directory: Path, *, accuracy_seconds: int = 0, embed_chain: bool = True
) -> _TestTsa:
    directory.mkdir(parents=True, exist_ok=True)
    _run_openssl(
        ["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", "ca_key.pem"],
        cwd=directory,
    )
    _run_openssl(
        [
            "openssl",
            "req",
            "-x509",
            "-new",
            "-key",
            "ca_key.pem",
            "-sha256",
            "-days",
            "2",
            "-subj",
            "/CN=LottoLab Test Root CA/O=LottoLabTest",
            "-addext",
            "basicConstraints=critical,CA:true",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
            "-out",
            "ca_cert.pem",
        ],
        cwd=directory,
    )
    _run_openssl(
        ["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", "tsa_key.pem"],
        cwd=directory,
    )
    _run_openssl(
        [
            "openssl",
            "req",
            "-new",
            "-key",
            "tsa_key.pem",
            "-subj",
            "/CN=LottoLab Test TSA/O=LottoLabTest",
            "-out",
            "tsa.csr",
        ],
        cwd=directory,
    )
    (directory / "tsa_ext.cnf").write_text(
        "basicConstraints=critical,CA:false\n"
        "keyUsage=critical,digitalSignature\n"
        "extendedKeyUsage=critical,timeStamping\n",
        encoding="ascii",
    )
    _run_openssl(
        [
            "openssl",
            "x509",
            "-req",
            "-in",
            "tsa.csr",
            "-CA",
            "ca_cert.pem",
            "-CAkey",
            "ca_key.pem",
            "-CAcreateserial",
            "-days",
            "2",
            "-sha256",
            "-extfile",
            "tsa_ext.cnf",
            "-out",
            "tsa_cert.pem",
        ],
        cwd=directory,
    )
    config_path = directory / "ts.cnf"
    certs_line = "certs = ca_cert.pem\n" if embed_chain else ""
    config_path.write_text(
        "[ tsa ]\n"
        "default_tsa = tsa_config1\n"
        "[ tsa_config1 ]\n"
        "dir = .\n"
        "serial = tsaserial\n"
        "crypto_device = builtin\n"
        "signer_cert = tsa_cert.pem\n"
        f"{certs_line}"
        "signer_key = tsa_key.pem\n"
        "signer_digest = sha256\n"
        "default_policy = 1.2.3.4.5.6.7.8.1\n"
        "digests = sha1, sha256\n"
        f"accuracy = secs:{accuracy_seconds}\n"
        "clock_precision_digits = 0\n"
        "ordering = yes\n"
        "tsa_name = yes\n"
        "ess_cert_id_chain = no\n"
        "ess_cert_id_alg = sha256\n",
        encoding="ascii",
    )
    (directory / "tsaserial").write_text("01\n", encoding="ascii")
    return _TestTsa(
        directory=directory,
        ca_cert_pem=(directory / "ca_cert.pem").read_text(encoding="ascii"),
        tsa_cert_path=directory / "tsa_cert.pem",
        config_path=config_path,
    )


def _token_gen_time(token_bytes: bytes) -> datetime:
    return _parse_tst_info(token_bytes).gen_time


def _write_token(tmp_path: Path, name: str, token_bytes: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(token_bytes)
    return path


# --- commitment envelope -----------------------------------------------------


def test_commitment_canonical_bytes_are_deterministic() -> None:
    first = _commitment()
    second = _commitment()

    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.commitment_sha256() == second.commitment_sha256()


def test_commitment_canonical_dict_has_exactly_the_eight_signed_fields() -> None:
    commitment = _commitment()

    assert set(commitment.canonical_dict()) == {
        "schema_version",
        "lottery_type",
        "official_draw_identity",
        "target_scheduled_at",
        "target_registration_digest",
        "prediction_record_digest",
        "freeze_artifact_file_sha256",
        "cohort_membership_strategy_ids_lcj1_sha256",
    }


def test_commitment_canonical_bytes_are_compact_sorted_json() -> None:
    commitment = _commitment()
    canonical = commitment.canonical_bytes()

    import json

    assert canonical == json.dumps(
        json.loads(canonical), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    assert b" " not in canonical


@pytest.mark.parametrize(
    "field_name",
    [
        "official_draw_identity",
        "target_scheduled_at",
        "target_registration_digest",
        "prediction_record_digest",
        "freeze_artifact_file_sha256",
        "cohort_membership_strategy_ids_lcj1_sha256",
    ],
)
def test_commitment_hash_changes_when_any_bound_field_changes(field_name: str) -> None:
    baseline = _commitment()
    mutated_kwargs: dict[str, str | datetime] = {
        "official_draw_identity": "115000084",
        "target_scheduled_at": _BASE_SCHEDULED_AT + timedelta(seconds=1),
        "target_registration_digest": "9" * 64,
        "prediction_record_digest": "9" * 64,
        "freeze_artifact_file_sha256": "9" * 64,
        "cohort_membership_strategy_ids_lcj1_sha256": "9" * 64,
    }
    mutated = _commitment(**{field_name: mutated_kwargs[field_name]})  # type: ignore[arg-type]

    assert baseline.commitment_sha256() != mutated.commitment_sha256()


def test_commitment_rejects_non_big_lotto_lottery_type() -> None:
    commitment = _commitment()
    with pytest.raises(ValueError):
        Fixed13PreOutcomeCommitment(
            schema_version=commitment.schema_version,
            lottery_type=LotteryType.DAILY_539,
            official_draw_identity=commitment.official_draw_identity,
            target_scheduled_at=commitment.target_scheduled_at,
            target_registration_digest=commitment.target_registration_digest,
            prediction_record_digest=commitment.prediction_record_digest,
            freeze_artifact_file_sha256=commitment.freeze_artifact_file_sha256,
            cohort_membership_strategy_ids_lcj1_sha256=(
                commitment.cohort_membership_strategy_ids_lcj1_sha256
            ),
        )


# --- offline verifier: positive path -----------------------------------------


def test_valid_local_rfc3161_token_verifies(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    commitment = _commitment(target_scheduled_at=_BASE_SCHEDULED_AT)
    token_bytes = tsa.issue_token(digest_hex=commitment.commitment_sha256())
    gen_time = _token_gen_time(token_bytes)
    assert gen_time < commitment.target_scheduled_at
    token_path = _write_token(tmp_path, "good.tst", token_bytes)

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=hashlib.sha256(token_bytes).hexdigest(),
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is True
    assert verdict.reason_code is PreOutcomeTimingReceiptReasonCode.OK
    assert verdict.commitment_sha256 == commitment.commitment_sha256()
    assert verdict.gen_time == gen_time


def test_valid_token_verifies_with_explicit_chain_path(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    commitment = _commitment()
    token_bytes = tsa.issue_token(digest_hex=commitment.commitment_sha256())
    token_path = _write_token(tmp_path, "good.tst", token_bytes)
    chain_path = tmp_path / "chain.pem"
    chain_path.write_bytes(tsa.tsa_cert_path.read_bytes())

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=hashlib.sha256(token_bytes).hexdigest(),
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
        chain_path=chain_path,
    )

    assert verdict.verified is True


# --- offline verifier: failure dispositions ----------------------------------


def test_unsupported_proof_type_fails_closed(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    commitment = _commitment()
    token_bytes = tsa.issue_token(digest_hex=commitment.commitment_sha256())
    token_path = _write_token(tmp_path, "good.tst", token_bytes)

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type="EXTERNAL_APPEND_ONLY_RECEIPT",
        reference_sha256=hashlib.sha256(token_bytes).hexdigest(),
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert verdict.reason_code is PreOutcomeTimingReceiptReasonCode.UNSUPPORTED_PROOF_TYPE


def test_receipt_file_missing_fails_closed(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    commitment = _commitment()

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256="0" * 64,
        token_path=tmp_path / "does-not-exist.tst",
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert verdict.reason_code is PreOutcomeTimingReceiptReasonCode.RECEIPT_FILE_NOT_FOUND


def test_reference_sha256_mismatch_fails_closed(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    commitment = _commitment()
    token_bytes = tsa.issue_token(digest_hex=commitment.commitment_sha256())
    token_path = _write_token(tmp_path, "good.tst", token_bytes)

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256="f" * 64,
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert verdict.reason_code is PreOutcomeTimingReceiptReasonCode.REFERENCE_SHA256_MISMATCH


def test_tampered_token_bytes_fail_closed(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    commitment = _commitment()
    token_bytes = bytearray(tsa.issue_token(digest_hex=commitment.commitment_sha256()))
    token_bytes[-5] ^= 0xFF
    tampered = bytes(token_bytes)
    token_path = _write_token(tmp_path, "tampered.tst", tampered)

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=hashlib.sha256(tampered).hexdigest(),
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert verdict.reason_code is PreOutcomeTimingReceiptReasonCode.SIGNATURE_OR_CHAIN_INVALID


def test_malformed_der_fails_closed(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    commitment = _commitment()
    token_bytes = tsa.issue_token(digest_hex=commitment.commitment_sha256())
    truncated = token_bytes[:20]
    token_path = _write_token(tmp_path, "malformed.tst", truncated)

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=hashlib.sha256(truncated).hexdigest(),
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert verdict.reason_code is PreOutcomeTimingReceiptReasonCode.TOKEN_MALFORMED


def test_untrusted_issuer_fails_closed(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    other_tsa = _build_test_tsa(tmp_path / "other-tsa")
    commitment = _commitment()
    token_bytes = tsa.issue_token(digest_hex=commitment.commitment_sha256())
    token_path = _write_token(tmp_path, "good.tst", token_bytes)

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=hashlib.sha256(token_bytes).hexdigest(),
        token_path=token_path,
        trust_anchors=other_tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert verdict.reason_code is PreOutcomeTimingReceiptReasonCode.SIGNATURE_OR_CHAIN_INVALID


def test_missing_issuer_chain_fails_closed(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa", embed_chain=False)
    commitment = _commitment()
    token_bytes = tsa.issue_token(digest_hex=commitment.commitment_sha256(), with_cert=False)
    token_path = _write_token(tmp_path, "no-chain.tst", token_bytes)

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=hashlib.sha256(token_bytes).hexdigest(),
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert verdict.reason_code is PreOutcomeTimingReceiptReasonCode.SIGNATURE_OR_CHAIN_INVALID


def test_wrong_message_imprint_algorithm_fails_closed(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    commitment = _commitment()
    sha1_digest = hashlib.sha1(commitment.canonical_bytes()).hexdigest()
    token_bytes = tsa.issue_token(digest_hex=sha1_digest, digest_algorithm="sha1")
    token_path = _write_token(tmp_path, "sha1.tst", token_bytes)

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=hashlib.sha256(token_bytes).hexdigest(),
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert (
        verdict.reason_code
        is PreOutcomeTimingReceiptReasonCode.MESSAGE_IMPRINT_ALGORITHM_UNSUPPORTED
    )


def test_message_imprint_for_another_commitment_fails_closed(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    real_commitment = _commitment(prediction_record_digest="2" * 64)
    other_commitment = _commitment(prediction_record_digest="5" * 64)
    token_bytes = tsa.issue_token(digest_hex=other_commitment.commitment_sha256())
    token_path = _write_token(tmp_path, "rebound.tst", token_bytes)

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=real_commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=hashlib.sha256(token_bytes).hexdigest(),
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert verdict.reason_code is PreOutcomeTimingReceiptReasonCode.MESSAGE_IMPRINT_MISMATCH


def test_token_transplanted_to_another_draw_fails_closed(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    draw_a = _commitment(official_draw_identity="115000083")
    draw_b = _commitment(official_draw_identity="115000084")
    token_for_a = tsa.issue_token(digest_hex=draw_a.commitment_sha256())
    token_path = _write_token(tmp_path, "draw-a-token.tst", token_for_a)

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=draw_b,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=hashlib.sha256(token_for_a).hexdigest(),
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert verdict.reason_code is PreOutcomeTimingReceiptReasonCode.MESSAGE_IMPRINT_MISMATCH


def test_gentime_equal_to_cutoff_fails_closed(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    probe_commitment = _commitment(target_scheduled_at=_BASE_SCHEDULED_AT)
    probe_token = tsa.issue_token(digest_hex=probe_commitment.commitment_sha256())
    observed_gen_time = _token_gen_time(probe_token)

    commitment = _commitment(target_scheduled_at=observed_gen_time)
    token_bytes = tsa.issue_token(digest_hex=commitment.commitment_sha256())
    assert _token_gen_time(token_bytes) == observed_gen_time
    token_path = _write_token(tmp_path, "equal-cutoff.tst", token_bytes)

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=hashlib.sha256(token_bytes).hexdigest(),
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert (
        verdict.reason_code
        is PreOutcomeTimingReceiptReasonCode.GENTIME_NOT_BEFORE_TARGET_SCHEDULE
    )


def test_gentime_after_cutoff_fails_closed(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    probe_commitment = _commitment(target_scheduled_at=_BASE_SCHEDULED_AT)
    probe_token = tsa.issue_token(digest_hex=probe_commitment.commitment_sha256())
    observed_gen_time = _token_gen_time(probe_token)

    commitment = _commitment(target_scheduled_at=observed_gen_time - timedelta(seconds=1))
    token_bytes = tsa.issue_token(digest_hex=commitment.commitment_sha256())
    token_path = _write_token(tmp_path, "after-cutoff.tst", token_bytes)

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=hashlib.sha256(token_bytes).hexdigest(),
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert (
        verdict.reason_code
        is PreOutcomeTimingReceiptReasonCode.GENTIME_NOT_BEFORE_TARGET_SCHEDULE
    )


def test_conservative_accuracy_crossing_cutoff_fails_closed(tmp_path: Path) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa", accuracy_seconds=5)
    probe_commitment = _commitment(target_scheduled_at=_BASE_SCHEDULED_AT)
    probe_token = tsa.issue_token(digest_hex=probe_commitment.commitment_sha256())
    observed_gen_time = _token_gen_time(probe_token)

    # genTime alone is strictly before the cutoff, but genTime + the TSA's
    # stated 5s accuracy is not.
    commitment = _commitment(target_scheduled_at=observed_gen_time + timedelta(seconds=2))
    token_bytes = tsa.issue_token(digest_hex=commitment.commitment_sha256())
    assert _token_gen_time(token_bytes) < commitment.target_scheduled_at
    token_path = _write_token(tmp_path, "accuracy-margin.tst", token_bytes)

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=hashlib.sha256(token_bytes).hexdigest(),
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert (
        verdict.reason_code
        is PreOutcomeTimingReceiptReasonCode.GENTIME_ACCURACY_MARGIN_NOT_BEFORE_TARGET_SCHEDULE
    )


def _unavailable_resolution(
    *_args: object, **_kwargs: object
) -> Fixed13CryptoRuntimeResolution:
    return Fixed13CryptoRuntimeResolution(
        capable=False,
        binary_path=None,
        openssl_version_text=None,
        source_tier=None,
        reason=Fixed13CryptoRuntimeUnavailableReason.NO_RUNTIME_CONFIGURED,
    )


def test_verifier_backend_unavailable_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tsa = _build_test_tsa(tmp_path / "tsa")
    commitment = _commitment()
    token_bytes = tsa.issue_token(digest_hex=commitment.commitment_sha256())
    token_path = _write_token(tmp_path, "good.tst", token_bytes)

    monkeypatch.setattr(
        "lottolab.application.fixed13_pre_outcome_timing_receipt.resolve_openssl_binary",
        _unavailable_resolution,
    )

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=hashlib.sha256(token_bytes).hexdigest(),
        token_path=token_path,
        trust_anchors=tsa.trust_anchors,
    )

    assert verdict.verified is False
    assert verdict.reason_code is PreOutcomeTimingReceiptReasonCode.VERIFIER_BACKEND_UNAVAILABLE


# --- production-profile regression: committed ESSCertIDv2 + 3-tier golden vector


def _golden_vector_metadata() -> dict[str, object]:
    return json.loads(
        (_GOLDEN_VECTOR_DIR / "golden_vector.json").read_text(encoding="utf-8")
    )


def test_golden_vector_production_profile_receipt_verifies(tmp_path: Path) -> None:
    """Unlike every other verifier test above, this one does not mint its own
    token with whatever runtime happens to be ambient: it replays the
    committed root -> intermediate -> TSA-leaf / ESSCertIDv2 / root-not-embedded
    fixture from tests/fixtures/fixed13_rfc3161/ through the module's real,
    default-resolved runtime, with the root supplied as the only pinned trust
    anchor (the intermediate is supplied out-of-band via chain_path, exactly
    as production does for an archived receipt chain)."""

    metadata = _golden_vector_metadata()
    digest_hex = metadata["message_imprint_sha256_hex"]
    assert type(digest_hex) is str

    commitment = Fixed13PreOutcomeCommitment.create(
        official_draw_identity="115000083",
        target_scheduled_at=datetime(2126, 1, 1, tzinfo=UTC),
        target_registration_digest="a" * 64,
        prediction_record_digest="b" * 64,
        freeze_artifact_file_sha256="c" * 64,
        cohort_membership_strategy_ids_lcj1_sha256="d" * 64,
    )
    assert commitment.commitment_sha256() == digest_hex

    root_pem = (_GOLDEN_VECTOR_DIR / "root_cert.pem").read_text(encoding="ascii")
    token_path = _GOLDEN_VECTOR_DIR / "token.tsr"
    chain_path = _GOLDEN_VECTOR_DIR / "intermediate_cert.pem"
    reference_sha256 = hashlib.sha256(token_path.read_bytes()).hexdigest()

    verdict = verify_rfc3161_pre_outcome_receipt(
        commitment=commitment,
        proof_type=RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
        reference_sha256=reference_sha256,
        token_path=token_path,
        trust_anchors=PinnedTrustAnchorSet((root_pem,)),
        chain_path=chain_path,
    )

    assert verdict.verified is True
    assert verdict.reason_code is PreOutcomeTimingReceiptReasonCode.OK
    assert verdict.commitment_sha256 == digest_hex
