"""Focused unit tests for BIG_LOTTO RFC 3161 offline pre-draw evidence verifier (Python 3.9).

Validates AC1 through AC8, including positive cryptographic verification with synthetic tokens,
canonical 7-field binding, snapshot byte verification, and the complete 17-case Negative Matrix.
No real predictions, no external TSA network calls, no replay mutations.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
REPO_ROOT = _REPO_ROOT

from tools.verify_biglotto_predraw_evidence_r2 import (  # noqa: E402
    ContractError,
    build_canonical_prediction_payload,
    compute_canonical_payload_sha256,
    _DerParseError,
    _build_timestamp_interval,
    _datetime_epoch_seconds,
    _decode_generalized_time_parts,
    _parse_tstinfo_accuracy,
    _read_der_children,
    _read_der_tlv,
    _timestamp_interval_after_lower_bound,
    _timestamp_interval_strictly_before_upper_cutoff,
    _parse_timestamp_token,
    verify_predraw_evidence_boundary,
)

EXPECTED_SCORER_SHA256 = "d67bd4232165339eacc5feeb579bf3c92016a29393173ffc20475784e12f1bc0"
EXPECTED_OFFLINE_CLI_SHA256 = "b119f0fcb62d48d1ad5f4a47ab9f36d4853d07c0a7135cd9bbd6e51ad9716c80"


class RFC3161AccuracyTests(unittest.TestCase):
    @staticmethod
    def _der_tlv(tag: int, content: bytes) -> bytes:
        if len(content) >= 128:
            length_bytes = len(content).to_bytes((len(content).bit_length() + 7) // 8, "big")
            length = bytes([0x80 | len(length_bytes)]) + length_bytes
        else:
            length = bytes([len(content)])
        return bytes([tag]) + length + content

    @classmethod
    def _der_integer(cls, value: int) -> bytes:
        if value < 0:
            length = max(1, (value.bit_length() + 8) // 8)
            encoded = value.to_bytes(length, "big", signed=True)
            while len(encoded) > 1 and int.from_bytes(encoded[1:], "big", signed=True) == value:
                encoded = encoded[1:]
        else:
            length = max(1, (value.bit_length() + 7) // 8)
            encoded = value.to_bytes(length, "big")
            if encoded[0] & 0x80:
                encoded = b"\x00" + encoded
        return cls._der_tlv(0x02, encoded)

    @classmethod
    def _accuracy_node(cls, *components: bytes) -> Any:
        encoded = cls._der_tlv(0x30, b"".join(components))
        node, end = _read_der_tlv(encoded, 0)
        if end != len(encoded):
            raise AssertionError("test accuracy DER contains trailing bytes")
        return node

    @classmethod
    def _synthetic_tstinfo(
        cls, policy_tlv: bytes | None = None, imprint_tlv: bytes | None = None,
        accuracy_tlv: bytes | None = None,
    ) -> bytes:
        if policy_tlv is None:
            policy_tlv = cls._der_tlv(0x06, b"\x2a")
        if imprint_tlv is None:
            algorithm = cls._der_tlv(
                0x30, cls._der_tlv(0x06, bytes.fromhex("608648016503040201"))
            )
            imprint_tlv = cls._der_tlv(
                0x30, algorithm + cls._der_tlv(0x04, b"\x11" * 32)
            )
        if accuracy_tlv is None:
            accuracy_tlv = cls._der_tlv(0x30, b"")

        content = (
            cls._der_tlv(0x02, b"\x01")
            + policy_tlv
            + imprint_tlv
            + cls._der_tlv(0x02, b"\x01")
            + cls._der_tlv(0x18, b"20261018123456Z")
            + accuracy_tlv
        )
        return cls._der_tlv(0x30, content)

    @classmethod
    def _synthetic_timestamp_token(
        cls, tstinfo: bytes, *, ber_content_info_length: bool = False
    ) -> bytes:
        signed_data_oid = cls._der_tlv(
            0x06, bytes.fromhex("2a864886f70d010702")
        )
        tstinfo_oid = cls._der_tlv(
            0x06, bytes.fromhex("2a864886f70d0109100104")
        )
        encapsulated = cls._der_tlv(
            0x30,
            tstinfo_oid + cls._der_tlv(0xA0, cls._der_tlv(0x04, tstinfo)),
        )
        signed_data = cls._der_tlv(
            0x30,
            cls._der_tlv(0x02, b"\x01") + cls._der_tlv(0x31, b"") + encapsulated,
        )
        content_info_content = signed_data_oid + cls._der_tlv(0xA0, signed_data)
        if ber_content_info_length:
            if len(content_info_content) >= 128:
                raise AssertionError("synthetic CMS ContentInfo no longer fits BER test")
            return b"\x30\x81" + bytes([len(content_info_content)]) + content_info_content
        return cls._der_tlv(0x30, content_info_content)

    def test_timestamp_parser_requires_minimal_tstinfo_der_lengths(self) -> None:
        legal_tstinfo = self._synthetic_tstinfo()
        self.assertEqual(len(legal_tstinfo), 0x4F)
        self.assertEqual(legal_tstinfo[:2], bytes.fromhex("30 4D"))
        tstinfo_content = legal_tstinfo[2:]

        algorithm = self._der_tlv(
            0x30, self._der_tlv(0x06, bytes.fromhex("608648016503040201"))
        )
        nested_nonminimal_imprint = self._der_tlv(
            0x30, algorithm + b"\x04\x81\x20" + b"\x11" * 32
        )
        cases = (
            (
                "VALID_DER_ROOT",
                legal_tstinfo,
                "30 4D (77 content octets)",
                "ACCEPT_TSTINFO_PARSING:accuracy=0",
            ),
            (
                "ROOT_NONMINIMAL_LENGTH",
                b"\x30\x81\x4d" + tstinfo_content,
                "30 4D -> 30 81 4D; identical 77 content octets",
                "REJECT_NONMINIMAL_DER_LENGTH",
            ),
            (
                "ACCURACY_NONMINIMAL_LENGTH",
                self._synthetic_tstinfo(
                    accuracy_tlv=self._der_tlv(0x30, b"\x80\x81\x01\x01")
                ),
                "accuracy component 80 01 01 -> 80 81 01 01; parent lengths minimal",
                "REJECT_NONMINIMAL_DER_LENGTH",
            ),
            (
                "TSTINFO_CHILD_NONMINIMAL_LENGTH",
                self._synthetic_tstinfo(policy_tlv=b"\x06\x81\x01\x2a"),
                "policy OID 06 01 2A -> 06 81 01 2A; root length minimal",
                "REJECT_NONMINIMAL_DER_LENGTH",
            ),
            (
                "MESSAGE_IMPRINT_CHILD_NONMINIMAL_LENGTH",
                self._synthetic_tstinfo(imprint_tlv=nested_nonminimal_imprint),
                "hashedMessage 04 20 -> 04 81 20; parent lengths minimal",
                "REJECT_NONMINIMAL_DER_LENGTH",
            ),
            (
                "INDEFINITE_DER_LENGTH",
                b"\x30\x80" + tstinfo_content + b"\x00\x00",
                "root length octet 4D -> 80; append EOC 00 00 after the same 77 content octets",
                "REJECT_INDEFINITE_DER_LENGTH",
            ),
            (
                "LEADING_ZERO_IN_LENGTH",
                b"\x30\x82\x00\x4d" + tstinfo_content,
                "TSTInfo root header 30 4D -> 30 82 00 4D",
                "REJECT_NONMINIMAL_DER_LENGTH",
            ),
            (
                "TRUNCATED_DER_LENGTH",
                bytes.fromhex("30 82 01"),
                "TSTInfo root header is 30 82 01 (second length octet absent)",
                "REJECT_TRUNCATED_DER_LENGTH",
            ),
        )

        for case, tstinfo, mutation, expected in cases:
            with self.subTest(case=case):
                try:
                    parsed = _parse_timestamp_token(
                        self._synthetic_timestamp_token(tstinfo)
                    )
                    actual = f"ACCEPT_TSTINFO_PARSING:accuracy={parsed.accuracy_microseconds}"
                except ContractError as exc:
                    detail = str(exc).lower()
                    if "nonminimal" in detail or "long form below 128" in detail:
                        actual = "REJECT_NONMINIMAL_DER_LENGTH"
                    elif "indefinite" in detail:
                        actual = "REJECT_INDEFINITE_DER_LENGTH"
                    elif "truncated" in detail:
                        actual = "REJECT_TRUNCATED_DER_LENGTH"
                    else:
                        actual = f"REJECT_{exc.code}"

                print(
                    json.dumps(
                        {
                            "CASE": case,
                            "RAW_BYTES_OR_EXACT_MUTATION": mutation,
                            "EXPECTED": expected,
                            "ACTUAL": actual,
                            "VERDICT": "PASS" if actual == expected else "FAIL",
                        },
                        sort_keys=True,
                    )
                )
                self.assertEqual(actual, expected)

    def test_timestamp_parser_preserves_cms_ber_wrapper_compatibility(self) -> None:
        tstinfo = self._synthetic_tstinfo()
        der_token = self._synthetic_timestamp_token(tstinfo)
        ber_token = self._synthetic_timestamp_token(
            tstinfo, ber_content_info_length=True
        )
        try:
            parsed = _parse_timestamp_token(ber_token)
            actual = f"ACCEPT_TSTINFO_PARSING:accuracy={parsed.accuracy_microseconds}"
        except ContractError as exc:
            actual = f"REJECT_{exc.code}"
        expected = "ACCEPT_TSTINFO_PARSING:accuracy=0"
        print(
            json.dumps(
                {
                    "CASE": "CMS_BER_CONTENTINFO_LENGTH",
                    "RAW_BYTES_OR_EXACT_MUTATION": (
                        f"ContentInfo root {der_token[:2].hex(' ').upper()} -> "
                        f"{ber_token[:3].hex(' ').upper()} (BER long form)"
                    ),
                    "EXPECTED": expected,
                    "ACTUAL": actual,
                    "VERDICT": "PASS" if actual == expected else "FAIL",
                },
                sort_keys=True,
            )
        )
        self.assertEqual(actual, expected)

    def test_der_length_canonicality_boundary_matrix(self) -> None:
        content_127 = b"\x00" * 127
        content_128 = b"\x00" * 128
        cases = (
            ("EMPTY_SEQUENCE", bytes.fromhex("30 00"), True, 0),
            ("KNOWN_COUNTEREXAMPLE", bytes.fromhex("30 81 00"), False, 0),
            ("SHORT_FORM_LENGTH_127", b"\x30\x7f" + content_127, True, 127),
            ("NONMINIMAL_LONG_FORM_LENGTH_127", b"\x30\x81\x7f" + content_127, False, 127),
            ("MINIMAL_LONG_FORM_LENGTH_128", b"\x30\x81\x80" + content_128, True, 128),
            (
                "NONMINIMAL_LEADING_ZERO_LENGTH_128",
                b"\x30\x82\x00\x80" + content_128,
                False,
                128,
            ),
            ("INDEFINITE_LENGTH", bytes.fromhex("30 80 00 00"), False, 0),
            ("TRUNCATED_LENGTH_OCTETS", bytes.fromhex("30 82 01"), False, 0),
            ("CONTENT_EXCEEDS_BUFFER", bytes.fromhex("30 02 00"), False, 2),
            ("RESERVED_LENGTH_OF_LENGTH", b"\x30\xff" + b"\x01" * 127, False, 0),
        )
        for case, raw, should_accept, expected_content_length in cases:
            with self.subTest(case=case):
                try:
                    nodes = _read_der_children(raw, require_minimal_length=True)
                    if len(nodes) != 1:
                        actual = f"ACCEPT_NODE_COUNT_{len(nodes)}"
                    elif case == "KNOWN_COUNTEREXAMPLE":
                        accuracy_microseconds = _parse_tstinfo_accuracy(nodes[0])
                        actual = f"ACCEPTED_{accuracy_microseconds}_MICROSECONDS"
                    else:
                        actual = f"ACCEPT_CONTENT_LENGTH_{len(nodes[0].content)}"
                    rejection_reason = ""
                except _DerParseError as exc:
                    rejection_reason = str(exc)
                    if case == "KNOWN_COUNTEREXAMPLE" and "nonminimal" in rejection_reason:
                        actual = "REJECT_NONMINIMAL_DER_LENGTH"
                    else:
                        actual = "REJECT"

                expected = (
                    f"ACCEPT_CONTENT_LENGTH_{expected_content_length}"
                    if should_accept
                    else "REJECT_NONMINIMAL_DER_LENGTH"
                    if case == "KNOWN_COUNTEREXAMPLE"
                    else "REJECT"
                )
                verdict = "PASS" if actual == expected else "FAIL"
                print(
                    json.dumps(
                        {
                            "CASE": case,
                            "RAW_BYTES": raw.hex(" ").upper(),
                            "EXPECTED": expected,
                            "ACTUAL": actual,
                            "REASON": rejection_reason,
                            "VERDICT": verdict,
                        },
                        sort_keys=True,
                    )
                )
                self.assertEqual(actual, expected)

    def test_accuracy_components_are_exact_integer_microseconds(self) -> None:
        cases = (
            ("SECONDS", (self._der_integer(7),), 7_000_000),
            ("MILLIS_ONLY", (self._der_tlv(0x80, b"\x02"),), 2_000),
            ("SECONDS_MILLIS", (self._der_integer(7), self._der_tlv(0x80, b"\x02")), 7_002_000),
            ("SECONDS_MICROS", (self._der_integer(7), self._der_tlv(0x81, b"\x03")), 7_000_003),
            ("EMPTY_PRESENT_ACCURACY", (), 0),
            (
                "ALL_COMPONENTS",
                (self._der_integer(7), self._der_tlv(0x80, b"\x02"), self._der_tlv(0x81, b"\x03")),
                7_002_003,
            ),
        )
        for case, components, expected in cases:
            with self.subTest(case=case):
                actual = _parse_tstinfo_accuracy(self._accuracy_node(*components))
                self.assertEqual(actual, expected)

    def test_missing_accuracy_is_unknown_not_zero(self) -> None:
        self.assertIsNone(_parse_tstinfo_accuracy(None))
        self.assertIsNone(_build_timestamp_interval(Fraction(1, 1), None))

    def test_accuracy_rejects_malformed_ranges_and_negative_seconds(self) -> None:
        invalid_cases = (
            ("MILLIS_ZERO", (self._der_tlv(0x80, b"\x00"),)),
            ("MILLIS_TOO_LARGE", (self._der_tlv(0x80, b"\x03\xe8"),)),
            ("MICROS_ZERO", (self._der_tlv(0x81, b"\x00"),)),
            ("MICROS_TOO_LARGE", (self._der_tlv(0x81, b"\x03\xe8"),)),
            ("NEGATIVE_SECONDS", (self._der_integer(-1),)),
            ("EMPTY_INTEGER", (self._der_tlv(0x80, b""),)),
            ("DUPLICATE_MILLIS", (self._der_tlv(0x80, b"\x01"), self._der_tlv(0x80, b"\x02"))),
            ("OUT_OF_ORDER", (self._der_tlv(0x81, b"\x01"), self._der_tlv(0x80, b"\x01"))),
        )
        for case, components in invalid_cases:
            with self.subTest(case=case):
                with self.assertRaises(_DerParseError):
                    _parse_tstinfo_accuracy(self._accuracy_node(*components))
        malformed_node, _ = _read_der_tlv(self._der_tlv(0x04, b"\x01"), 0)
        with self.assertRaises(_DerParseError):
            _parse_tstinfo_accuracy(malformed_node)

    def test_generalized_time_preserves_submicrosecond_precision_and_utc(self) -> None:
        parsed, exact = _decode_generalized_time_parts(b"20261018123456.1234567Z")
        whole = datetime(2026, 10, 18, 12, 34, 56, tzinfo=timezone.utc)
        expected = _datetime_epoch_seconds(whole) + Fraction(1_234_567, 10_000_000)
        self.assertEqual(parsed.microsecond, 123_456)
        self.assertEqual(exact, expected)

    def test_exact_interval_boundary_matrix(self) -> None:
        cutoff_local = datetime.fromisoformat("2026-10-18T20:00:00+08:00")
        cutoff_utc = datetime.fromisoformat("2026-10-18T12:00:00+00:00")
        cutoff_exact = _datetime_epoch_seconds(cutoff_local)
        self.assertEqual(cutoff_exact, _datetime_epoch_seconds(cutoff_utc))

        cases = (
            ("GEN_TIME_BEFORE_CUTOFF", Fraction(-1, 1), 100_000, "upper", True),
            ("UPPER_BOUND_BEFORE_CUTOFF", Fraction(-11, 10_000_000), 1, "upper", True),
            ("UPPER_BOUND_EQUAL_CUTOFF", Fraction(-1, 1_000_000), 1, "upper", False),
            ("UPPER_BOUND_AFTER_CUTOFF", Fraction(-9, 10_000_000), 1, "upper", False),
            ("UNCERTAINTY_CROSSES_CUTOFF", Fraction(-1, 2), 1_000_000, "upper", False),
            ("LOWER_BOUND_EQUAL_NOT_BEFORE", Fraction(1, 1_000_000), 1, "lower", True),
            ("LOWER_BOUND_BEFORE_NOT_BEFORE", Fraction(9, 10_000_000), 1, "lower", False),
            ("UNKNOWN_ACCURACY", Fraction(-10, 1), None, "upper", False),
        )
        for case, gen_time_offset, accuracy_microseconds, comparison, expected in cases:
            with self.subTest(case=case):
                interval = _build_timestamp_interval(
                    cutoff_exact + gen_time_offset, accuracy_microseconds
                )
                if comparison == "lower":
                    actual = _timestamp_interval_after_lower_bound(interval, cutoff_local)
                else:
                    actual = _timestamp_interval_strictly_before_upper_cutoff(
                        interval, cutoff_local
                    )
                print(
                    json.dumps(
                        {
                            "CASE": case,
                            "INPUT": {
                                "cutoff_utc": cutoff_utc.isoformat(),
                                "gen_time_offset_seconds": str(gen_time_offset),
                                "accuracy_microseconds": accuracy_microseconds,
                                "comparison": comparison,
                            },
                            "EXPECTED": expected,
                            "ACTUAL": actual,
                            "VERDICT": "PASS" if actual == expected else "FAIL",
                        },
                        sort_keys=True,
                    )
                )
                self.assertEqual(actual, expected)


def _get_openssl_bin() -> str:
    for cand in ("/opt/homebrew/bin/openssl", shutil.which("openssl"), "/usr/bin/openssl"):
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    raise RuntimeError("OpenSSL required for unit tests")


class _SyntheticTsaHarness:
    """Creates a local, throwaway CA and TSA using the system OpenSSL binary."""

    def __init__(
        self,
        work_dir: Path,
        *,
        eku_name: str = "timeStamping",
        policy_oid: str = "1.2.3.4.5.6.7.8.1",
        validity_days: int = 2,
    ) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.openssl = _get_openssl_bin()
        self.policy_oid = policy_oid

        # 1. Root CA
        self.ca_key = self.work_dir / "ca_key.pem"
        self.ca_cert = self.work_dir / "ca_cert.pem"
        subprocess.run(
            [
                self.openssl,
                "ecparam",
                "-name",
                "prime256v1",
                "-genkey",
                "-noout",
                "-out",
                str(self.ca_key),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                self.openssl,
                "req",
                "-x509",
                "-new",
                "-key",
                str(self.ca_key),
                "-sha256",
                "-days",
                str(validity_days),
                "-subj",
                "/CN=Test Root CA/O=Test",
                "-out",
                str(self.ca_cert),
            ],
            check=True,
            capture_output=True,
        )

        # 2. TSA cert
        self.tsa_key = self.work_dir / "tsa_key.pem"
        self.tsa_csr = self.work_dir / "tsa.csr"
        self.tsa_cert = self.work_dir / "tsa_cert.pem"
        subprocess.run(
            [
                self.openssl,
                "ecparam",
                "-name",
                "prime256v1",
                "-genkey",
                "-noout",
                "-out",
                str(self.tsa_key),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                self.openssl,
                "req",
                "-new",
                "-key",
                str(self.tsa_key),
                "-subj",
                "/CN=Test TSA/O=Test",
                "-out",
                str(self.tsa_csr),
            ],
            check=True,
            capture_output=True,
        )

        ext_cnf = self.work_dir / "tsa_ext.cnf"
        ext_cnf.write_text(
            f"basicConstraints=critical,CA:false\nkeyUsage=critical,digitalSignature\n"
            f"extendedKeyUsage=critical,{eku_name}\n",
            encoding="ascii",
        )
        subprocess.run(
            [
                self.openssl,
                "x509",
                "-req",
                "-in",
                str(self.tsa_csr),
                "-CA",
                str(self.ca_cert),
                "-CAkey",
                str(self.ca_key),
                "-CAcreateserial",
                "-days",
                str(validity_days),
                "-sha256",
                "-extfile",
                str(ext_cnf),
                "-out",
                str(self.tsa_cert),
            ],
            check=True,
            capture_output=True,
        )

        # 3. TSA config
        self.ts_cnf = self.work_dir / "ts.cnf"
        serial_file = self.work_dir / "tsaserial"
        serial_file.write_text("01\n", encoding="ascii")

        self.ts_cnf.write_text(
            f"[ tsa ]\ndefault_tsa = tsa_config1\n[ tsa_config1 ]\ndir = {self.work_dir}\n"
            f"serial = {serial_file}\ncrypto_device = builtin\nsigner_cert = {self.tsa_cert}\n"
            f"certs = {self.ca_cert}\nsigner_key = {self.tsa_key}\nsigner_digest = sha256\n"
            f"default_policy = {policy_oid}\ndigests = sha1, sha256\naccuracy = secs:0, millisecs:1\n"
            f"clock_precision_digits = 0\nordering = yes\ntsa_name = yes\ness_cert_id_chain = no\n"
            f"ess_cert_id_alg = sha256\n",
            encoding="ascii",
        )

    def issue_token(self, digest_hex: str, *, cert_req: bool = True) -> bytes:
        req_path = self.work_dir / f"req_{digest_hex[:12]}.tsq"
        tst_path = self.work_dir / f"token_{digest_hex[:12]}.tst"
        query_cmd = [self.openssl, "ts", "-query", "-digest", digest_hex, "-sha256"]
        if cert_req:
            query_cmd.append("-cert")
        query_cmd.extend(["-out", str(req_path)])
        subprocess.run(
            query_cmd,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                self.openssl,
                "ts",
                "-reply",
                "-config",
                str(self.ts_cnf),
                "-queryfile",
                str(req_path),
                "-token_out",
                "-out",
                str(tst_path),
            ],
            check=True,
            capture_output=True,
        )
        return tst_path.read_bytes()

    def issue_token_and_request(
        self, digest_hex: str, *, cert_req: bool = True
    ) -> tuple[bytes, bytes]:
        token = self.issue_token(digest_hex, cert_req=cert_req)
        req_path = self.work_dir / f"req_{digest_hex[:12]}.tsq"
        return token, req_path.read_bytes()

    def signer_der_sha256(self) -> str:
        der = subprocess.check_output(
            [self.openssl, "x509", "-in", str(self.tsa_cert), "-outform", "DER"]
        )
        return hashlib.sha256(der).hexdigest()


def _make_prediction_fixture(
    draw_id: str = "199000001",
    *,
    experiment_id: str = "SYNTHETIC_EXP_R2",
    strategy_id: str = "synthetic-strategy@version:2",
    snapshot_hash: str = "0" * 64,
    cutoff: str = "2000-01-01T12:00:00+00:00",
    capture_time: str = "2000-01-01T12:01:00+00:00",
    numbers: list[int] | None = None,
) -> dict[str, Any]:
    return {
        "EXPERIMENT_ID": experiment_id,
        "DRAW_ID": draw_id,
        "SIX_PREDICTED_NUMBERS": numbers or [1, 2, 3, 4, 5, 6],
        "STRATEGY_IDENTITY": strategy_id,
        "INPUT_SNAPSHOT_SHA256": snapshot_hash,
        "INPUT_CUTOFF": cutoff,
        "PREDICTION_CAPTURE_ID": f"cap-{draw_id}",
        "PREDICTION_CAPTURE_TIME": capture_time,
        "PREDRAW_EVIDENCE_LOCATOR": f"evidence://{draw_id}",
    }


def _make_outcome_fixture(
    draw_id: str = "199000001",
    *,
    draw_time: str = "2099-01-01T20:30:00+00:00",
    numbers: list[int] | None = None,
) -> dict[str, Any]:
    return {
        "DRAW_ID": draw_id,
        "SIX_OFFICIAL_MAIN_NUMBERS": numbers or [1, 2, 3, 7, 8, 9],
        "DRAW_TIME": draw_time,
        "OFFICIAL_RESULT_SOURCE": f"source://official/{draw_id}",
    }


def _make_contract_fixture(
    draws: list[str] | None = None,
    *,
    experiment_id: str = "SYNTHETIC_EXP_R2",
    strategy_id: str = "synthetic-strategy@version:2",
) -> dict[str, Any]:
    return {
        "EXPERIMENT_ID": experiment_id,
        "STRATEGY_IDENTITY": strategy_id,
        "EXPECTED_DRAW_IDS": draws or ["199000001"],
    }


class VerifyBigLottoPredrawEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)
        self.tsa = _SyntheticTsaHarness(self.tmp / "tsa")
        self.ca_pem_path = self.tsa.ca_cert
        self.ca_sha256 = hashlib.sha256(self.ca_pem_path.read_bytes()).hexdigest()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _evidence_bundle_for_token(
        self, pred: dict[str, Any], canonical_hash: str, token_bytes: bytes
    ) -> dict[str, Any]:
        draw_id = pred["DRAW_ID"]
        return {
            draw_id: {
                "CONTENT_SHA256": canonical_hash,
                "TOKEN_BYTES": token_bytes,
                "RECEIPT_SHA256": hashlib.sha256(token_bytes).hexdigest(),
                "STRATEGY_IDENTITY": pred["STRATEGY_IDENTITY"],
            }
        }

    def _issue_synthetic_evidence(
        self, pred: dict[str, Any]
    ) -> tuple[dict[str, Any], datetime, str]:
        payload = build_canonical_prediction_payload(pred)
        canonical_hash = compute_canonical_payload_sha256(payload)
        token_bytes = self.tsa.issue_token(canonical_hash)
        parsed_token = _parse_timestamp_token(token_bytes)
        self.assertEqual(parsed_token.accuracy_microseconds, 1_000)
        self.assertIsNotNone(parsed_token.time_interval)
        gen_time = parsed_token.gen_time
        return self._evidence_bundle_for_token(pred, canonical_hash, token_bytes), gen_time, canonical_hash

    def _issue_synthetic_evidence_at_input_cutoff(
        self, pred: dict[str, Any]
    ) -> tuple[dict[str, Any], datetime, str]:
        # OpenSSL stamps to whole seconds. Schedule a signed token at the
        # candidate second and retry only if process scheduling crosses it.
        for _ in range(12):
            input_cutoff = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(
                seconds=3
            )
            pred["INPUT_CUTOFF"] = input_cutoff.isoformat()
            payload = build_canonical_prediction_payload(pred)
            canonical_hash = compute_canonical_payload_sha256(payload)
            while datetime.now(timezone.utc) < input_cutoff:
                time.sleep(0.001)
            token_bytes = self.tsa.issue_token(canonical_hash)
            gen_time = _parse_timestamp_token(token_bytes).gen_time
            if gen_time == input_cutoff:
                return (
                    self._evidence_bundle_for_token(pred, canonical_hash, token_bytes),
                    gen_time,
                    canonical_hash,
                )
        self.fail("could not create a synthetic token at the exact input cutoff second")
        raise AssertionError("unreachable")

    def _assert_time_boundary_case(
        self,
        case_id: str,
        pred: dict[str, Any],
        out: dict[str, Any],
        evidence_bundle: dict[str, Any],
        gen_time: datetime,
        *,
        expected: str,
        expected_error_code: str | None = None,
    ) -> None:
        contract = _make_contract_fixture([pred["DRAW_ID"]])
        actual = "REJECT"
        error_code = None
        try:
            result = verify_predraw_evidence_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle=evidence_bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
            actual = "ACCEPT_SYNTHETIC_DIAGNOSTIC"
            self.assertEqual(result["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
            self.assertTrue(result["CRYPTO_TOKEN_VALID"])
            self.assertNotIn("TRUSTED_TIME_INTERVAL", result)
            self.assertNotIn("TSA_TIME_INTERVAL", result)
        except ContractError as exc:
            error_code = exc.code

        passed = actual == expected and error_code == expected_error_code
        print(
            json.dumps(
                {
                    "CASE": case_id,
                    "INPUT_CUTOFF": pred["INPUT_CUTOFF"],
                    "genTime": gen_time.isoformat(),
                    "DRAW_CUTOFF": out["DRAW_TIME"],
                    "EXPECTED": expected,
                    "ACTUAL": actual,
                    "ERROR_CODE": error_code,
                    "VERDICT": "PASS" if passed else "FAIL",
                },
                sort_keys=True,
            )
        )
        self.assertTrue(passed, f"{case_id}: {error_code or actual}")

    # --- AC1: Identity Tests ---
    def test_ac1_scorer_and_cli_unchanged(self) -> None:
        scorer_path = REPO_ROOT / "tools" / "score_biglotto_prospective_r1.py"
        cli_path = REPO_ROOT / "tools" / "run_biglotto_prospective_scoring_r1.py"
        self.assertEqual(
            hashlib.sha256(scorer_path.read_bytes()).hexdigest(), EXPECTED_SCORER_SHA256
        )
        self.assertEqual(
            hashlib.sha256(cli_path.read_bytes()).hexdigest(), EXPECTED_OFFLINE_CLI_SHA256
        )

    # --- AC2: Canonical Binding Tests ---
    def test_ac2_canonical_binding_deterministic_and_sensitive_to_all_seven_fields(self) -> None:
        base = _make_prediction_fixture("199000001")
        base_payload = build_canonical_prediction_payload(base)
        base_hash = compute_canonical_payload_sha256(base_payload)

        # Mutate each of the 7 core fields and assert hash changes
        mutations = [
            ("DRAW_ID", "199000002"),
            ("EXPERIMENT_ID", "MUTATED_EXP"),
            ("INPUT_CUTOFF", "2099-01-01T11:59:59+00:00"),
            ("INPUT_SNAPSHOT_SHA256", "1" * 64),
            ("PREDICTION_CAPTURE_ID", "mutated-cap"),
            ("SIX_PREDICTED_NUMBERS", [1, 2, 3, 4, 5, 7]),
            ("STRATEGY_IDENTITY", "mutated-strat@v2"),
        ]
        for field, new_val in mutations:
            mutated = copy.deepcopy(base)
            mutated[field] = new_val
            mutated_payload = build_canonical_prediction_payload(mutated)
            mutated_hash = compute_canonical_payload_sha256(mutated_payload)
            self.assertNotEqual(
                base_hash, mutated_hash, f"Field mutation {field} must alter canonical hash"
            )

    # --- AC4 & AC5: Cryptographic Verification and Evidence Boundary ---
    def test_ac4_and_ac5_positive_cryptographic_verification(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])

        payload = build_canonical_prediction_payload(pred)
        canon_hash = compute_canonical_payload_sha256(payload)
        token_bytes = self.tsa.issue_token(canon_hash)

        evidence_bundle = {
            "199000001": {
                "CONTENT_SHA256": canon_hash,
                "TOKEN_BYTES": token_bytes,
                "RECEIPT_SHA256": hashlib.sha256(token_bytes).hexdigest(),
                "STRATEGY_IDENTITY": pred["STRATEGY_IDENTITY"],
            }
        }

        # Valid snapshot
        snap_content = json.dumps(
            [{"DRAW_ID": "199000000", "DRAW_TIME": "1999-12-31T20:30:00+00:00"}]
        ).encode("utf-8")
        snap_hash = hashlib.sha256(snap_content).hexdigest()
        pred["INPUT_SNAPSHOT_SHA256"] = snap_hash
        # Re-issue token with updated snapshot hash in payload
        payload = build_canonical_prediction_payload(pred)
        canon_hash = compute_canonical_payload_sha256(payload)
        token_bytes = self.tsa.issue_token(canon_hash)
        evidence_bundle["199000001"]["CONTENT_SHA256"] = canon_hash
        evidence_bundle["199000001"]["TOKEN_BYTES"] = token_bytes
        evidence_bundle["199000001"]["RECEIPT_SHA256"] = hashlib.sha256(token_bytes).hexdigest()

        result = verify_predraw_evidence_boundary(
            [pred],
            [out],
            contract,
            evidence_bundle=evidence_bundle,
            pinned_tsa_cert_pem_path=self.ca_pem_path,
            pinned_tsa_cert_sha256=self.ca_sha256,
            snapshot_files_by_sha256={snap_hash: snap_content},
            require_independent_verification=False,
        )

        self.assertEqual(result["TARGET_COUNT"], 1)
        self.assertEqual(result["HIT_HISTOGRAM_0_TO_6"][3], 1)
        self.assertEqual(result["MEAN_HITS"], 3.0)
        self.assertEqual(result["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
        self.assertFalse(result["CAPTURE_TIME_INDEPENDENTLY_VERIFIED"])
        self.assertEqual(result["ORIGINAL_HISTORICAL_PARITY"], "NOT_VERIFIED")
        self.assertEqual(result["PREDICTIVE_SUCCESS_EVIDENCE"], "NOT_ESTABLISHED")
        self.assertEqual(result["CRYPTOGRAPHIC_VERIFIER_STATUS"], "PASS")
        self.assertTrue(result["CRYPTO_TOKEN_VALID"])
        self.assertFalse(result["DRAW_CUTOFF_SOURCE_VERIFIED"])
        self.assertFalse(result["PREDRAW_EVIDENCE_INDEPENDENTLY_VERIFIED"])
        self.assertEqual(result["PREDRAW_EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle=evidence_bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
                snapshot_files_by_sha256={snap_hash: snap_content},
                require_independent_verification=True,
            )
        self.assertEqual(caught.exception.code, "TRUSTED_DRAW_CUTOFF_REQUIRED")

    def test_external_signer_certreq_false_and_request_binding(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        payload = build_canonical_prediction_payload(pred)
        canon_hash = compute_canonical_payload_sha256(payload)
        token, request_bytes = self.tsa.issue_token_and_request(canon_hash, cert_req=False)
        self.assertEqual(_parse_timestamp_token(token).accuracy_microseconds, 1_000)
        entry = self._evidence_bundle_for_token(pred, canon_hash, token)["199000001"]
        entry["REQUEST_BYTES"] = request_bytes
        good_args = dict(
            evidence_bundle={"199000001": entry},
            pinned_tsa_cert_pem_path=self.ca_pem_path,
            pinned_tsa_cert_sha256=self.ca_sha256,
            pinned_tsa_signer_cert_pem_path=self.tsa.tsa_cert,
            pinned_tsa_signer_cert_sha256=self.tsa.signer_der_sha256(),
        )
        result = verify_predraw_evidence_boundary([pred], [out], contract, **good_args)
        self.assertEqual(result["CRYPTOGRAPHIC_VERIFIER_STATUS"], "PASS")
        self.assertEqual(result["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
        self.assertFalse(result["DRAW_CUTOFF_SOURCE_VERIFIED"])

        missing_signer_args = dict(good_args)
        missing_signer_args.pop("pinned_tsa_signer_cert_pem_path")
        missing_signer_args.pop("pinned_tsa_signer_cert_sha256")
        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary([pred], [out], contract, **missing_signer_args)
        self.assertEqual(caught.exception.code, "MISSING_EXTERNAL_SIGNER")

        wrong_pin_args = dict(good_args, pinned_tsa_signer_cert_sha256="0" * 64)
        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary([pred], [out], contract, **wrong_pin_args)
        self.assertEqual(caught.exception.code, "WRONG_TSA_SIGNER_FINGERPRINT")

        _, wrong_nonce_request = self.tsa.issue_token_and_request(canon_hash, cert_req=False)
        self.assertNotEqual(request_bytes, wrong_nonce_request)
        nonce_bundle = {"199000001": dict(entry, REQUEST_BYTES=wrong_nonce_request)}
        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred], [out], contract, **dict(good_args, evidence_bundle=nonce_bundle)
            )
        self.assertEqual(caught.exception.code, "REQUEST_NONCE_MISMATCH")

        _, wrong_imprint_request = self.tsa.issue_token_and_request("f" * 64, cert_req=False)
        imprint_bundle = {"199000001": dict(entry, REQUEST_BYTES=wrong_imprint_request)}
        with self.assertRaises(ContractError):
            verify_predraw_evidence_boundary(
                [pred], [out], contract, **dict(good_args, evidence_bundle=imprint_bundle)
            )

    def test_ac5_diagnostic_only_without_evidence_bundle(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])

        result = verify_predraw_evidence_boundary([pred], [out], contract, evidence_bundle=None)
        self.assertEqual(result["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
        self.assertFalse(result["CAPTURE_TIME_INDEPENDENTLY_VERIFIED"])
        self.assertFalse(result["CRYPTO_TOKEN_VALID"])
        self.assertFalse(result["DRAW_CUTOFF_SOURCE_VERIFIED"])
        self.assertFalse(result["PREDRAW_EVIDENCE_INDEPENDENTLY_VERIFIED"])

    def test_timestamp_boundary_matrix_uses_public_verifier(self) -> None:
        pred1 = _make_prediction_fixture("199000001", cutoff="2000-01-01T12:00:00+00:00")
        out1 = _make_outcome_fixture("199000001")
        bundle1, gen_time1, _ = self._issue_synthetic_evidence(pred1)
        self._assert_time_boundary_case(
            "TIME_01",
            pred1,
            out1,
            bundle1,
            gen_time1,
            expected="ACCEPT_SYNTHETIC_DIAGNOSTIC",
        )

        pred2 = _make_prediction_fixture("199000002")
        out2 = _make_outcome_fixture("199000002")
        bundle2, gen_time2, _ = self._issue_synthetic_evidence_at_input_cutoff(pred2)
        self._assert_time_boundary_case(
            "TIME_02",
            pred2,
            out2,
            bundle2,
            gen_time2,
            expected="REJECT",
            expected_error_code="TIMESTAMP_NOT_AFTER_INPUT_CUTOFF",
        )

        future_cutoff = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(
            minutes=10
        )
        pred3 = _make_prediction_fixture("199000003", cutoff=future_cutoff.isoformat())
        out3 = _make_outcome_fixture("199000003")
        bundle3, gen_time3, _ = self._issue_synthetic_evidence(pred3)
        self._assert_time_boundary_case(
            "TIME_03",
            pred3,
            out3,
            bundle3,
            gen_time3,
            expected="REJECT",
            expected_error_code="TIMESTAMP_NOT_AFTER_INPUT_CUTOFF",
        )

        pred4 = _make_prediction_fixture("199000004", cutoff="2000-01-01T12:00:00+00:00")
        bundle4, gen_time4, _ = self._issue_synthetic_evidence(pred4)
        out4 = _make_outcome_fixture("199000004", draw_time=gen_time4.isoformat())
        self._assert_time_boundary_case(
            "TIME_04",
            pred4,
            out4,
            bundle4,
            gen_time4,
            expected="REJECT",
            expected_error_code="TIMESTAMP_AFTER_CUTOFF",
        )

        pred5 = _make_prediction_fixture("199000005", cutoff="2000-01-01T12:00:00+00:00")
        bundle5, gen_time5, _ = self._issue_synthetic_evidence(pred5)
        draw_cutoff5 = (gen_time5 - timedelta(seconds=1)).isoformat()
        out5 = _make_outcome_fixture("199000005", draw_time=draw_cutoff5)
        self._assert_time_boundary_case(
            "TIME_05",
            pred5,
            out5,
            bundle5,
            gen_time5,
            expected="REJECT",
            expected_error_code="TIMESTAMP_AFTER_CUTOFF",
        )

    # --- AC6: Complete 17-Item Negative Matrix Tests ---

    def test_ac6_neg_01_missing_trust_anchor(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        token = self.tsa.issue_token("0" * 64)
        bundle = {"199000001": {"TOKEN_BYTES": token}}

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle=bundle,
                pinned_tsa_cert_pem_path=None,
                pinned_tsa_cert_sha256=None,
            )
        self.assertEqual(caught.exception.code, "MISSING_TRUST_ANCHOR")

    def test_ac6_neg_02_missing_evidence_for_draw(self) -> None:
        pred1 = _make_prediction_fixture("199000001")
        pred2 = _make_prediction_fixture("199000002")
        out1 = _make_outcome_fixture("199000001")
        out2 = _make_outcome_fixture("199000002")
        contract = _make_contract_fixture(["199000001", "199000002"])
        token = self.tsa.issue_token("0" * 64)
        bundle = {"199000001": {"TOKEN_BYTES": token}}  # Missing 199000002

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred1, pred2],
                [out1, out2],
                contract,
                evidence_bundle=bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(caught.exception.code, "MISSING_EVIDENCE_FOR_DRAW")

    def test_ac6_neg_03_extra_evidence_for_draw(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        token = self.tsa.issue_token("0" * 64)
        bundle = {"199000001": {"TOKEN_BYTES": token}, "199000002": {"TOKEN_BYTES": token}}

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle=bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(caught.exception.code, "EXTRA_EVIDENCE_FOR_DRAW")

    def test_ac6_neg_04_content_hash_mismatch(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        bundle = {"199000001": {"CONTENT_SHA256": "f" * 64, "TOKEN_BYTES": b"dummy"}}

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle=bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(caught.exception.code, "CONTENT_HASH_MISMATCH")

    def test_ac6_neg_05_imprint_mismatch(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        payload = build_canonical_prediction_payload(pred)
        canon_hash = compute_canonical_payload_sha256(payload)
        # Issue token for a different hash
        token_bytes = self.tsa.issue_token("b" * 64)
        bundle = {"199000001": {"TOKEN_BYTES": token_bytes, "CONTENT_SHA256": canon_hash}}

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle=bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(caught.exception.code, "IMPRINT_MISMATCH")

    def test_ac6_neg_06_receipt_hash_mismatch(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        token_bytes = self.tsa.issue_token("0" * 64)
        bundle = {"199000001": {"TOKEN_BYTES": token_bytes, "RECEIPT_SHA256": "d" * 64}}

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle=bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(caught.exception.code, "RECEIPT_HASH_MISMATCH")

    def test_ac6_neg_07_invalid_cms_signature(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        payload = build_canonical_prediction_payload(pred)
        canon_hash = compute_canonical_payload_sha256(payload)
        token_bytes = bytearray(self.tsa.issue_token(canon_hash))
        # Corrupt the signature bytes at the tail
        token_bytes[-10] ^= 0xFF
        bundle = {"199000001": {"TOKEN_BYTES": bytes(token_bytes)}}

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle=bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(caught.exception.code, "INVALID_CMS_SIGNATURE")

    def test_ac6_neg_08_untrusted_tsa_certificate(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        payload = build_canonical_prediction_payload(pred)
        canon_hash = compute_canonical_payload_sha256(payload)
        # Foreign TSA
        other_tsa = _SyntheticTsaHarness(self.tmp / "foreign_tsa")
        foreign_token = other_tsa.issue_token(canon_hash)
        bundle = {"199000001": {"TOKEN_BYTES": foreign_token}}

        # Pin self.ca_cert, but token was signed by foreign_tsa
        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle=bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(caught.exception.code, "UNTRUSTED_TSA_CERTIFICATE")

    def test_ac6_neg_09_wrong_tsa_eku(self) -> None:
        # TSA generated with serverAuth EKU instead of timeStamping
        bad_tsa = _SyntheticTsaHarness(self.tmp / "tsa_bad_eku", eku_name="serverAuth")
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        payload = build_canonical_prediction_payload(pred)
        canon_hash = compute_canonical_payload_sha256(payload)
        token = self.tsa.issue_token(canon_hash)

        with self.assertRaises(ContractError) as caught:
            bad_ca_sha = hashlib.sha256(bad_tsa.ca_cert.read_bytes()).hexdigest()
            verify_predraw_evidence_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle={"199000001": {"TOKEN_BYTES": token}},
                pinned_tsa_cert_pem_path=bad_tsa.ca_cert,
                pinned_tsa_cert_sha256=bad_ca_sha,
            )
        self.assertIn(caught.exception.code, ("UNTRUSTED_TSA_CERTIFICATE", "WRONG_TSA_EKU"))

    def test_ac6_neg_10_certificate_time_invalid(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        payload = build_canonical_prediction_payload(pred)
        canon_hash = compute_canonical_payload_sha256(payload)
        token = self.tsa.issue_token(canon_hash)

        # Mutate gen_time in token to 2010, which is outside the TSA cert's validity (2026)
        mod_token = token.replace(b"2026", b"2010", 1)

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle={"199000001": {"TOKEN_BYTES": mod_token}},
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(caught.exception.code, "CERTIFICATE_TIME_INVALID")

    def test_ac6_neg_11_wrong_tsa_policy(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        contract["ACCEPTED_TSA_POLICIES"] = ["2.999.888.777"]  # Token has 1.2.3.4.5.6.7.8.1

        payload = build_canonical_prediction_payload(pred)
        canon_hash = compute_canonical_payload_sha256(payload)
        token = self.tsa.issue_token(canon_hash)

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle={"199000001": {"TOKEN_BYTES": token}},
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(caught.exception.code, "WRONG_TSA_POLICY")

    def test_ac6_neg_12_timestamp_after_cutoff(self) -> None:
        # genTime is after the outcome's DRAW_TIME, while still after INPUT_CUTOFF.
        pred = _make_prediction_fixture("199000001", cutoff="2000-01-01T00:00:00+00:00")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])

        payload = build_canonical_prediction_payload(pred)
        canon_hash = compute_canonical_payload_sha256(payload)
        token = self.tsa.issue_token(canon_hash)
        gen_time = _parse_timestamp_token(token).gen_time
        out["DRAW_TIME"] = (gen_time - timedelta(seconds=1)).isoformat()

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle={"199000001": {"TOKEN_BYTES": token}},
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(caught.exception.code, "TIMESTAMP_AFTER_CUTOFF")

    def test_ac6_neg_13_snapshot_hash_mismatch(self) -> None:
        pred = _make_prediction_fixture("199000001", snapshot_hash="a" * 64)
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        bad_snap = b"different content"

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred], [out], contract, snapshot_files_by_sha256={"a" * 64: bad_snap}
            )
        self.assertEqual(caught.exception.code, "SNAPSHOT_HASH_MISMATCH")

    def test_ac6_neg_14_target_inside_input(self) -> None:
        # Snapshot contains the target draw 199000001
        pred = _make_prediction_fixture("199000001")
        snap_content = json.dumps(
            [{"DRAW_ID": "199000001", "DRAW_TIME": "2098-12-30T00:00:00+00:00"}]
        ).encode("utf-8")
        snap_hash = hashlib.sha256(snap_content).hexdigest()
        pred["INPUT_SNAPSHOT_SHA256"] = snap_hash
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary(
                [pred], [out], contract, snapshot_files_by_sha256={snap_hash: snap_content}
            )
        self.assertEqual(caught.exception.code, "TARGET_INSIDE_INPUT")

    def test_ac6_neg_15_strategy_identity_mismatch(self) -> None:
        pred = _make_prediction_fixture("199000001", strategy_id="strategy-a@v1")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"], strategy_id="strategy-b@v1")

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary([pred], [out], contract)
        self.assertEqual(caught.exception.code, "STRATEGY_IDENTITY_MISMATCH")

    def test_ac6_neg_16_false_verified_status(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        contract["EVIDENCE_STATUS"] = "VERIFIED"

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary([pred], [out], contract)
        self.assertEqual(caught.exception.code, "FALSE_VERIFIED_STATUS")

    def test_ac6_neg_17_false_success_claim(self) -> None:
        pred = _make_prediction_fixture("199000001")
        out = _make_outcome_fixture("199000001")
        contract = _make_contract_fixture(["199000001"])
        contract["PREDICTIVE_IMPROVEMENT"] = "PROVED"

        with self.assertRaises(ContractError) as caught:
            verify_predraw_evidence_boundary([pred], [out], contract)
        self.assertEqual(caught.exception.code, "FALSE_SUCCESS_CLAIM")


if __name__ == "__main__":
    unittest.main()
