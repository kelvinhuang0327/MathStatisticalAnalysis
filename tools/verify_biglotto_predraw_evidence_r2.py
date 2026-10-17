"""Minimal, standard-library RFC 3161 offline pre-draw evidence verifier (Python 3.9).

Directly reuses tools/score_biglotto_prospective_r1.py for prospective scoring.
Performs rigorous offline cryptographic verification of RFC 3161 timestamp tokens
using the host OpenSSL backend against caller-pinned trust anchors.

Public entry point:
    verify_predraw_evidence_boundary(
        predictions,
        outcomes,
        contract,
        *,
        evidence_bundle=None,
        pinned_tsa_cert_pem_path=None,
        pinned_tsa_cert_sha256=None,
        snapshot_files_by_sha256=None,
        require_independent_verification=False,
    )
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_UTC = timezone.utc  # noqa: UP017

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from tools.score_biglotto_prospective_r1 import (
        ContractError,
        score_biglotto_prospective,
    )
except ImportError:
    try:
        from score_biglotto_prospective_r1 import (
            ContractError,
            score_biglotto_prospective,
        )
    except ImportError:

        class ContractError(ValueError):
            """Fail-closed rejection with a stable machine-readable code."""

            def __init__(self, code: str, detail: str) -> None:
                self.code = code
                super().__init__(f"{code}: {detail}")


CANONICAL_BINDING_FIELDS = (
    "DRAW_ID",
    "EXPERIMENT_ID",
    "INPUT_CUTOFF",
    "INPUT_SNAPSHOT_SHA256",
    "PREDICTION_CAPTURE_ID",
    "SIX_PREDICTED_NUMBERS",
    "STRATEGY_IDENTITY",
)

FORBIDDEN_VERIFIED_VALUES = frozenset({"VERIFIED", "PROVED", "TRUE", "PASS"})
_OID_SIGNED_DATA = "1.2.840.113549.1.7.2"
_OID_TST_INFO_CONTENT_TYPE = "1.2.840.113549.1.9.16.1.4"
_OID_SHA256 = "2.16.840.1.101.3.4.2.1"
_OID_EKU_TIMESTAMPING = "1.3.6.1.5.5.7.3.8"

_TAG_BOOLEAN = 0x01
_TAG_INTEGER = 0x02
_TAG_OCTET_STRING = 0x04
_TAG_OID = 0x06
_TAG_GENERALIZED_TIME = 0x18
_TAG_SEQUENCE = 0x10
_CLASS_UNIVERSAL = 0
_CLASS_CONTEXT = 2


def _get_openssl_binary() -> str:
    candidates = [
        "/opt/homebrew/bin/openssl",
        shutil.which("openssl"),
        "/usr/bin/openssl",
    ]
    for cand in candidates:
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    raise ContractError("VERIFIER_BACKEND_UNAVAILABLE", "no usable OpenSSL binary found on system")


def _load_json(data_or_path: Any, label: str) -> Any:
    if isinstance(data_or_path, (str, Path)):
        p = Path(data_or_path)
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception as exc:
                raise ContractError(
                    "WRONG_INPUT_FORMAT", f"failed loading {label} from {p}: {exc}"
                ) from exc
        try:
            return json.loads(str(data_or_path))
        except Exception as exc:
            raise ContractError("WRONG_INPUT_FORMAT", f"invalid JSON for {label}: {exc}") from exc
    return data_or_path


def _parse_iso_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("INVALID_TIMESTAMP", f"{label} must be a nonblank string")
    raw = value.strip()
    try:
        dt = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
    except ValueError as exc:
        raise ContractError("INVALID_TIMESTAMP", f"{label} invalid ISO format: {raw}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ContractError("INVALID_TIMESTAMP", f"{label} requires timezone information")
    return dt.astimezone(_UTC)


def _check_forbidden_claims(container: Any, container_name: str) -> None:
    if isinstance(container, Mapping):
        for key in ("EVIDENCE_STATUS", "ORIGINAL_PARITY", "ORIGINAL_HISTORICAL_PARITY"):
            val = container.get(key)
            if (isinstance(val, str) and val.upper() in FORBIDDEN_VERIFIED_VALUES) or val is True:
                raise ContractError(
                    "FALSE_VERIFIED_STATUS",
                    f"{container_name} claims unauthorized verified status: {key}={val}",
                )
        for key in (
            "PREDICTIVE_IMPROVEMENT",
            "PREDICTIVE_SUCCESS_EVIDENCE",
            "SIGNIFICANT_LIFT",
            "ROI_IMPROVED",
        ):
            val = container.get(key)
            if (isinstance(val, str) and val.upper() in FORBIDDEN_VERIFIED_VALUES) or val is True:
                raise ContractError(
                    "FALSE_SUCCESS_CLAIM",
                    f"{container_name} claims unauthorized prospective success: {key}={val}",
                )
    elif isinstance(container, (list, tuple)):
        for item in container:
            _check_forbidden_claims(item, container_name)


def build_canonical_prediction_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    missing = [f for f in CANONICAL_BINDING_FIELDS if f not in row or row[f] is None]
    if missing:
        raise ContractError(
            "MISSING_FIELD",
            f"prediction missing canonical fields: {', '.join(sorted(missing))}",
        )
    numbers = row["SIX_PREDICTED_NUMBERS"]
    if not isinstance(numbers, (list, tuple)) or len(numbers) != 6:
        raise ContractError("INVALID_NUMBERS", "SIX_PREDICTED_NUMBERS must be 6 integers")
    if any(type(n) is not int for n in numbers) or any(n < 1 or n > 49 for n in numbers):
        raise ContractError("INVALID_NUMBERS", "numbers must be integers between 1 and 49")
    if len(set(numbers)) != 6:
        raise ContractError("DUPLICATE_NUMBERS", "SIX_PREDICTED_NUMBERS contains duplicates")
    return {
        "DRAW_ID": str(row["DRAW_ID"]).strip(),
        "EXPERIMENT_ID": str(row["EXPERIMENT_ID"]).strip(),
        "INPUT_CUTOFF": str(row["INPUT_CUTOFF"]).strip(),
        "INPUT_SNAPSHOT_SHA256": str(row["INPUT_SNAPSHOT_SHA256"]).strip().lower(),
        "PREDICTION_CAPTURE_ID": str(row["PREDICTION_CAPTURE_ID"]).strip(),
        "SIX_PREDICTED_NUMBERS": list(numbers),
        "STRATEGY_IDENTITY": str(row["STRATEGY_IDENTITY"]).strip(),
    }


def compute_canonical_payload_sha256(payload: dict[str, Any]) -> str:
    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


# --- Minimal ASN.1 DER Parser for RFC 3161 TSTInfo extraction ---


class _DerParseError(ValueError):
    pass


class _DerNode:
    __slots__ = ("content", "is_constructed", "tag_class", "tag_number")

    def __init__(
        self, tag_class: int, tag_number: int, is_constructed: bool, content: bytes
    ) -> None:
        self.tag_class = tag_class
        self.tag_number = tag_number
        self.is_constructed = is_constructed
        self.content = content


def _read_der_tlv(data: bytes, offset: int) -> tuple[_DerNode, int]:
    if offset >= len(data):
        raise _DerParseError("truncated DER: missing tag")
    first = data[offset]
    tag_class = (first & 0xC0) >> 6
    is_constructed = bool(first & 0x20)
    tag_number = first & 0x1F
    if tag_number == 0x1F:
        raise _DerParseError("unsupported high tag number")
    pos = offset + 1
    if pos >= len(data):
        raise _DerParseError("truncated DER: missing length")
    length_byte = data[pos]
    pos += 1
    if length_byte & 0x80:
        octet_count = length_byte & 0x7F
        if octet_count == 0:
            raise _DerParseError("indefinite-length DER unsupported")
        if pos + octet_count > len(data):
            raise _DerParseError("truncated DER: missing length octets")
        length = int.from_bytes(data[pos : pos + octet_count], "big")
        pos += octet_count
    else:
        length = length_byte
    if pos + length > len(data):
        raise _DerParseError("truncated DER: content exceeds buffer")
    return _DerNode(tag_class, tag_number, is_constructed, data[pos : pos + length]), pos + length


def _read_der_children(content: bytes) -> list[_DerNode]:
    children: list[_DerNode] = []
    offset = 0
    while offset < len(content):
        node, offset = _read_der_tlv(content, offset)
        children.append(node)
    return children


def _decode_oid(content: bytes) -> str:
    if not content:
        raise _DerParseError("empty OID")
    first = content[0]
    if first < 40:
        arcs = [0, first]
    elif first < 80:
        arcs = [1, first - 40]
    else:
        arcs = [2, first - 80]
    val = 0
    for b in content[1:]:
        val = (val << 7) | (b & 0x7F)
        if not (b & 0x80):
            arcs.append(val)
            val = 0
    if val != 0:
        raise _DerParseError("truncated OID arc")
    return ".".join(str(a) for a in arcs)


def _decode_generalized_time(content: bytes) -> datetime:
    try:
        text = content.decode("ascii")
    except UnicodeDecodeError as exc:
        raise _DerParseError("genTime is not ASCII") from exc
    for fmt in ("%Y%m%d%H%M%SZ", "%Y%m%d%H%M%S%z"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=_UTC)
        except ValueError:
            pass
    raise _DerParseError(f"unparseable GeneralizedTime: {text}")


class _ParsedToken:
    __slots__ = ("algorithm_oid", "gen_time", "hashed_message", "policy_oid")

    def __init__(
        self, algorithm_oid: str, hashed_message: bytes, gen_time: datetime, policy_oid: str
    ) -> None:
        self.algorithm_oid = algorithm_oid
        self.hashed_message = hashed_message
        self.gen_time = gen_time
        self.policy_oid = policy_oid


def _parse_timestamp_token(token_bytes: bytes) -> _ParsedToken:
    try:
        content_info, _ = _read_der_tlv(token_bytes, 0)
        if content_info.tag_class != _CLASS_UNIVERSAL or content_info.tag_number != _TAG_SEQUENCE:
            raise _DerParseError("ContentInfo must be SEQUENCE")
        top = _read_der_children(content_info.content)
        if len(top) != 2:
            raise _DerParseError("ContentInfo must contain contentType and content")
        if _decode_oid(top[0].content) != _OID_SIGNED_DATA:
            raise _DerParseError("ContentInfo.contentType is not signedData")
        signed_data_node, _ = _read_der_tlv(top[1].content, 0)
        sd_children = _read_der_children(signed_data_node.content)
        if len(sd_children) < 3:
            raise _DerParseError("SignedData missing encapContentInfo")
        encap_children = _read_der_children(sd_children[2].content)
        if len(encap_children) < 2:
            raise _DerParseError("encapContentInfo missing eContent")
        if _decode_oid(encap_children[0].content) != _OID_TST_INFO_CONTENT_TYPE:
            raise _DerParseError("encapContentInfo.eContentType is not id-ct-TSTInfo")
        econtent_octets, _ = _read_der_tlv(encap_children[1].content, 0)
        tst_node, _ = _read_der_tlv(econtent_octets.content, 0)
        tst_children = _read_der_children(tst_node.content)
        if len(tst_children) < 5:
            raise _DerParseError("TSTInfo missing required fields")

        policy_oid = _decode_oid(tst_children[1].content)
        mi_children = _read_der_children(tst_children[2].content)
        if len(mi_children) != 2:
            raise _DerParseError("messageImprint must carry hashAlgorithm and hashedMessage")
        alg_children = _read_der_children(mi_children[0].content)
        algorithm_oid = _decode_oid(alg_children[0].content)
        hashed_message = mi_children[1].content
        gen_time = _decode_generalized_time(tst_children[4].content)

        return _ParsedToken(
            algorithm_oid=algorithm_oid,
            hashed_message=hashed_message,
            gen_time=gen_time,
            policy_oid=policy_oid,
        )
    except _DerParseError as exc:
        raise ContractError(
            "INVALID_CMS_SIGNATURE", f"malformed token DER structure: {exc}"
        ) from exc
    except Exception as exc:
        raise ContractError("INVALID_CMS_SIGNATURE", f"unhandled DER parse failure: {exc}") from exc


def _parse_openssl_date(date_str: str) -> datetime:
    date_str = date_str.strip()
    for fmt in (
        "%b %d %H:%M:%S %Y %Z",
        "%b %d %H:%M:%S %Y GMT",
        "%b  %d %H:%M:%S %Y %Z",
        "%b  %d %H:%M:%S %Y GMT",
    ):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=_UTC)
        except ValueError:
            pass
    raise ValueError(f"unable to parse date string: {date_str}")


def _verify_openssl_token(
    *,
    token_bytes: bytes,
    canonical_sha256: str,
    ca_cert_path: Path,
    chain_path: Path | None = None,
    gen_time: datetime,
) -> None:
    openssl_bin = _get_openssl_binary()

    with tempfile.TemporaryDirectory(prefix="biglotto-verify-") as tmpdir:
        td = Path(tmpdir)
        token_path = td / "token.tst"
        token_path.write_bytes(token_bytes)

        # 1. Extract signer certificates using pkcs7
        proc_pkcs7 = subprocess.run(
            [
                openssl_bin,
                "pkcs7",
                "-in",
                str(token_path),
                "-inform",
                "DER",
                "-print_certs",
                "-text",
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
        if proc_pkcs7.returncode != 0:
            raise ContractError(
                "INVALID_CMS_SIGNATURE",
                f"failed extracting signer certs from token: {proc_pkcs7.stderr.decode()}",
            )

        cert_text = proc_pkcs7.stdout.decode("utf-8", errors="replace")
        if not cert_text.strip():
            raise ContractError(
                "UNTRUSTED_TSA_CERTIFICATE", "token does not embed signer certificate"
            )

        # 2. Check timeStamping EKU
        has_ts_eku = False
        if "X509v3 Extended Key Usage:" in cert_text:
            lines = cert_text.splitlines()
            for i, line in enumerate(lines):
                if "X509v3 Extended Key Usage:" in line:
                    following = " ".join(lines[i : min(i + 4, len(lines))])
                    if (
                        "Time Stamping" in following
                        or "timeStamping" in following
                        or _OID_EKU_TIMESTAMPING in following
                    ):
                        has_ts_eku = True
                        break
        if not has_ts_eku:
            raise ContractError(
                "WRONG_TSA_EKU", "TSA signer certificate missing timeStamping extended key usage"
            )

        # 3. Check certificate validity vs gen_time
        not_before_match = re.search(r"Not Before\s*:\s*([^\r\n]+)", cert_text)
        not_after_match = re.search(r"Not After\s*:\s*([^\r\n]+)", cert_text)
        not_before = not_after = None
        if not_before_match and not_after_match:
            try:
                not_before = _parse_openssl_date(not_before_match.group(1))
                not_after = _parse_openssl_date(not_after_match.group(1))
            except (ValueError, TypeError):
                pass
        if (
            not_before is not None
            and not_after is not None
            and (gen_time < not_before or gen_time > not_after)
        ):
            raise ContractError(
                "CERTIFICATE_TIME_INVALID",
                f"token timestamp {gen_time} outside TSA certificate validity "
                f"[{not_before}, {not_after}]",
            )

        # 4. Check ESSCertID / ESSCertIDv2 attribute in token
        proc_asn1 = subprocess.run(
            [openssl_bin, "asn1parse", "-in", str(token_path), "-inform", "DER"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        if proc_asn1.returncode != 0:
            raise ContractError("INVALID_CMS_SIGNATURE", "asn1parse failed on token")
        asn1_out = proc_asn1.stdout.decode("utf-8", errors="replace")
        if not (
            "signingCertificate" in asn1_out
            or "signingCertificateV2" in asn1_out
            or "1.2.840.113549.1.9.16.2.12" in asn1_out
            or "1.2.840.113549.1.9.16.2.47" in asn1_out
        ):
            raise ContractError(
                "INVALID_CMS_SIGNATURE", "token missing ESSCertID or ESSCertIDv2 attribute"
            )

        # 5. openssl ts -verify for CMS signature and trust chain to CAfile
        cmd = [
            openssl_bin,
            "ts",
            "-verify",
            "-digest",
            canonical_sha256,
            "-in",
            str(token_path),
            "-token_in",
            "-CAfile",
            str(ca_cert_path),
        ]
        if chain_path and chain_path.is_file():
            cmd += ["-untrusted", str(chain_path)]

        proc = subprocess.run(cmd, capture_output=True, timeout=15, check=False)
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace").lower()
            if (
                "untrusted" in err
                or "issuer" in err
                or "verify failed" in err
                or "self-signed" in err
                or "self signed" in err
            ):
                raise ContractError(
                    "UNTRUSTED_TSA_CERTIFICATE",
                    f"TSA certificate untrusted: {proc.stderr.decode()}",
                )
            if "purpose" in err:
                raise ContractError(
                    "WRONG_TSA_EKU", f"TSA certificate purpose invalid: {proc.stderr.decode()}"
                )
            if "expired" in err or "not yet valid" in err:
                raise ContractError(
                    "CERTIFICATE_TIME_INVALID",
                    f"TSA certificate expired or not yet valid: {proc.stderr.decode()}",
                )
            raise ContractError(
                "INVALID_CMS_SIGNATURE",
                f"OpenSSL ts -verify signature verification failed: {proc.stderr.decode()}",
            )


def _verify_snapshot_bytes(
    snapshot_bytes: bytes,
    expected_sha256: str,
    draw_id: str,
    cutoff_time: datetime,
) -> None:
    actual_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()
    if actual_sha256.lower() != expected_sha256.lower():
        raise ContractError(
            "SNAPSHOT_HASH_MISMATCH",
            f"snapshot bytes SHA-256 mismatch: {actual_sha256} != {expected_sha256}",
        )

    # Inspect snapshot content for future draws or records at/after cutoff
    try:
        decoded_text = snapshot_bytes.decode("utf-8")
        parsed = json.loads(decoded_text)
        records = parsed if isinstance(parsed, list) else parsed.get("draws", [])
        if isinstance(records, list):
            for rec in records:
                if isinstance(rec, Mapping):
                    did = rec.get("DRAW_ID") or rec.get("draw_id")
                    if did is not None and str(did) >= draw_id:
                        raise ContractError(
                            "TARGET_INSIDE_INPUT",
                            f"snapshot contains target or future draw: {did} >= {draw_id}",
                        )
                    dtime = rec.get("DRAW_TIME") or rec.get("draw_time") or rec.get("timestamp")
                    if dtime is not None:
                        try:
                            if _parse_iso_utc(str(dtime), "snapshot record time") >= cutoff_time:
                                raise ContractError(
                                    "TARGET_INSIDE_INPUT",
                                    f"snapshot contains record at {dtime} >= cutoff {cutoff_time}",
                                )
                        except Exception:
                            pass
        elif isinstance(parsed, Mapping):
            draw_ids = parsed.get("draw_ids") or parsed.get("DRAW_IDS")
            if isinstance(draw_ids, list):
                for did in draw_ids:
                    if str(did) >= draw_id:
                        raise ContractError(
                            "TARGET_INSIDE_INPUT",
                            f"snapshot contains target or future draw: {did} >= {draw_id}",
                        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        text = snapshot_bytes.decode("utf-8", errors="replace")
        if re.search(r"\b" + re.escape(draw_id) + r"\b", text):
            raise ContractError(
                "TARGET_INSIDE_INPUT", f"target draw {draw_id} found inside snapshot bytes"
            ) from None


def verify_predraw_evidence_boundary(
    predictions: Any,
    outcomes: Any,
    contract: Any,
    *,
    evidence_bundle: Any | None = None,
    pinned_tsa_cert_pem_path: str | Path | None = None,
    pinned_tsa_cert_sha256: str | None = None,
    snapshot_files_by_sha256: Mapping[str, str | Path | bytes] | None = None,
    require_independent_verification: bool = False,
) -> dict[str, Any]:
    """Verify BIG_LOTTO prospective predictions, outcomes, contract, and predraw evidence.

    Fails closed on any inconsistency, missing evidence, untrusted TSA, or invalid proof.
    Preserves verified mathematical scoring outputs and sets diagnostic boundary status.
    """
    # 1. Load inputs
    pred_data = _load_json(predictions, "predictions")
    out_data = _load_json(outcomes, "outcomes")
    contract_data = _load_json(contract, "contract")
    bundle_data = (
        _load_json(evidence_bundle, "evidence_bundle") if evidence_bundle is not None else None
    )

    if not isinstance(pred_data, (list, tuple)):
        raise ContractError("WRONG_INPUT_FORMAT", "predictions must be a sequence of mappings")
    if not isinstance(out_data, (list, tuple)):
        raise ContractError("WRONG_INPUT_FORMAT", "outcomes must be a sequence of mappings")
    if not isinstance(contract_data, Mapping):
        raise ContractError("WRONG_INPUT_FORMAT", "contract must be a mapping")

    # 2. Gate E: Fail-closed checks on forbidden verified / success claims
    _check_forbidden_claims(contract_data, "contract")
    _check_forbidden_claims(pred_data, "predictions")
    _check_forbidden_claims(out_data, "outcomes")
    if bundle_data is not None:
        _check_forbidden_claims(bundle_data, "evidence_bundle")

    # Contract required fields
    exp_id = contract_data.get("experiment_id") or contract_data.get("EXPERIMENT_ID")
    strat_id = contract_data.get("strategy_identity") or contract_data.get("STRATEGY_IDENTITY")
    draw_ids = contract_data.get("expected_draw_ids") or contract_data.get("EXPECTED_DRAW_IDS")

    if exp_id is None:
        raise ContractError("WRONG_INPUT_FORMAT", "contract missing experiment_id")
    if strat_id is None:
        raise ContractError("WRONG_INPUT_FORMAT", "contract missing strategy_identity")
    if draw_ids is None or not isinstance(draw_ids, (list, tuple)) or not draw_ids:
        raise ContractError("INVALID_DRAW_SET", "contract missing expected_draw_ids")

    contract_exp_id = str(exp_id).strip()
    contract_strat_id = str(strat_id).strip()
    if contract_strat_id.upper() in {"UNKNOWN", "UNVERIFIED", "NONE"}:
        raise ContractError(
            "WRONG_STRATEGY_IDENTITY", "contract strategy_identity cannot be UNKNOWN"
        )

    targets = [str(d).strip() for d in draw_ids]
    if len(set(targets)) != len(targets):
        raise ContractError("DUPLICATE_DRAW", "expected_draw_ids contains duplicates")

    # 3. Align predictions & outcomes
    pred_by_draw: dict[str, Mapping[str, Any]] = {}
    for p in pred_data:
        if not isinstance(p, Mapping):
            raise ContractError("INVALID_RECORD", "prediction record must be a mapping")
        did = str(p.get("DRAW_ID", "")).strip()
        if did in pred_by_draw:
            raise ContractError("DUPLICATE_DRAW", f"duplicate prediction for draw {did}")
        pred_by_draw[did] = p

    out_by_draw: dict[str, Mapping[str, Any]] = {}
    for o in out_data:
        if not isinstance(o, Mapping):
            raise ContractError("INVALID_RECORD", "outcome record must be a mapping")
        did = str(o.get("DRAW_ID", "")).strip()
        if did in out_by_draw:
            raise ContractError("DUPLICATE_DRAW", f"duplicate outcome for draw {did}")
        out_by_draw[did] = o

    if set(pred_by_draw) != set(targets):
        raise ContractError(
            "DRAW_SET_MISMATCH",
            f"prediction draws {sorted(pred_by_draw)} != targets {sorted(targets)}",
        )
    if set(out_by_draw) != set(targets):
        raise ContractError(
            "DRAW_SET_MISMATCH",
            f"outcome draws {sorted(out_by_draw)} != targets {sorted(targets)}",
        )

    # 4. Check Strategy Identity and Canonical Binding for every prediction
    canonical_payloads: dict[str, dict[str, Any]] = {}
    canonical_hashes: dict[str, str] = {}
    for did in targets:
        p = pred_by_draw[did]
        row_strat = str(p.get("STRATEGY_IDENTITY", "")).strip()
        if row_strat != contract_strat_id:
            raise ContractError(
                "STRATEGY_IDENTITY_MISMATCH",
                f"prediction strategy {row_strat} != contract {contract_strat_id}",
            )
        payload = build_canonical_prediction_payload(p)
        canonical_payloads[did] = payload
        canonical_hashes[did] = compute_canonical_payload_sha256(payload)

    # 5. AC3: Snapshot verification
    if snapshot_files_by_sha256 is not None:
        for did in targets:
            p = pred_by_draw[did]
            snap_hash = str(p.get("INPUT_SNAPSHOT_SHA256", "")).strip().lower()
            if snap_hash not in snapshot_files_by_sha256:
                raise ContractError(
                    "SNAPSHOT_HASH_MISMATCH",
                    f"snapshot {snap_hash} missing from snapshot_files_by_sha256",
                )
            val = snapshot_files_by_sha256[snap_hash]
            if isinstance(val, bytes):
                raw_snap_bytes = val
            elif isinstance(val, (str, Path)):
                sp = Path(val)
                if not sp.is_file():
                    raise ContractError("SNAPSHOT_HASH_MISMATCH", f"snapshot file not found: {sp}")
                raw_snap_bytes = sp.read_bytes()
            else:
                raise ContractError("SNAPSHOT_HASH_MISMATCH", "invalid snapshot entry type")
            cutoff_dt = _parse_iso_utc(str(p.get("INPUT_CUTOFF")), "INPUT_CUTOFF")
            _verify_snapshot_bytes(raw_snap_bytes, snap_hash, did, cutoff_dt)
    elif require_independent_verification:
        raise ContractError(
            "SNAPSHOT_HASH_MISMATCH",
            "snapshot_files_by_sha256 is required for independent verification",
        )

    # 6. Cryptographic Evidence Verification (if evidence bundle provided or required)
    if bundle_data is not None or require_independent_verification:
        if bundle_data is None:
            raise ContractError(
                "MISSING_EVIDENCE_FOR_DRAW",
                "evidence_bundle is required when verification is requested",
            )

        # Pinned trust anchor verification
        if pinned_tsa_cert_pem_path is None or pinned_tsa_cert_sha256 is None:
            raise ContractError(
                "MISSING_TRUST_ANCHOR", "pinned TSA certificate path and sha256 are required"
            )
        ca_cert_path = Path(pinned_tsa_cert_pem_path)
        if not ca_cert_path.is_file():
            raise ContractError(
                "MISSING_TRUST_ANCHOR", f"pinned TSA certificate file not found: {ca_cert_path}"
            )
        actual_ca_sha256 = hashlib.sha256(ca_cert_path.read_bytes()).hexdigest()
        if actual_ca_sha256.lower() != pinned_tsa_cert_sha256.lower():
            raise ContractError(
                "MISSING_TRUST_ANCHOR",
                f"pinned TSA certificate SHA-256 mismatch: "
                f"{actual_ca_sha256} != {pinned_tsa_cert_sha256}",
            )

        # Normalize evidence map
        if isinstance(bundle_data, Mapping):
            if "draws" in bundle_data and isinstance(bundle_data["draws"], Mapping):
                evidence_map = bundle_data["draws"]
            elif "EVIDENCE_BY_DRAW" in bundle_data and isinstance(
                bundle_data["EVIDENCE_BY_DRAW"], Mapping
            ):
                evidence_map = bundle_data["EVIDENCE_BY_DRAW"]
            else:
                evidence_map = bundle_data
        elif isinstance(bundle_data, (list, tuple)):
            evidence_map = {
                str(item.get("DRAW_ID", "")).strip(): item
                for item in bundle_data
                if isinstance(item, Mapping)
            }
        else:
            raise ContractError("WRONG_INPUT_FORMAT", "evidence_bundle must be a mapping or list")

        # Check for missing and extra evidence
        missing_draws = [d for d in targets if d not in evidence_map]
        if missing_draws:
            raise ContractError(
                "MISSING_EVIDENCE_FOR_DRAW",
                f"missing evidence for draw: {', '.join(sorted(missing_draws))}",
            )
        extra_draws = [d for d in evidence_map if d not in targets]
        if extra_draws:
            raise ContractError(
                "EXTRA_EVIDENCE_FOR_DRAW",
                f"extra evidence for unexpected draw: {', '.join(sorted(extra_draws))}",
            )

        # Accepted policies (if specified in contract or bundle)
        accepted_policies = (
            contract_data.get("ACCEPTED_TSA_POLICIES")
            or contract_data.get("accepted_tsa_policies")
            or (
                bundle_data.get("ACCEPTED_TSA_POLICIES")
                if isinstance(bundle_data, Mapping)
                else None
            )
        )

        for did in targets:
            ev = evidence_map[did]
            if not isinstance(ev, Mapping):
                raise ContractError(
                    "WRONG_INPUT_FORMAT", f"evidence entry for draw {did} must be a mapping"
                )

            # Check strategy identity in evidence
            if (
                "STRATEGY_IDENTITY" in ev
                and str(ev["STRATEGY_IDENTITY"]).strip() != contract_strat_id
            ):
                raise ContractError(
                    "STRATEGY_IDENTITY_MISMATCH",
                    f"evidence strategy {ev['STRATEGY_IDENTITY']} != contract {contract_strat_id}",
                )

            # Check canonical content hash if present in evidence
            content_hash_in_ev = (
                ev.get("CONTENT_SHA256")
                or ev.get("CANONICAL_PAYLOAD_SHA256")
                or ev.get("COMMITMENT_SHA256")
            )
            expected_content_hash = canonical_hashes[did]
            if (
                content_hash_in_ev is not None
                and str(content_hash_in_ev).strip().lower() != expected_content_hash.lower()
            ):
                raise ContractError(
                    "CONTENT_HASH_MISMATCH",
                    f"evidence content hash {content_hash_in_ev} != computed "
                    f"{expected_content_hash}",
                )

            # Extract token bytes
            token_bytes = ev.get("TOKEN_BYTES")
            if token_bytes is None:
                token_path_val = ev.get("TOKEN_PATH") or ev.get("RECEIPT_PATH")
                if token_path_val is not None:
                    tp = Path(token_path_val)
                    if not tp.is_file():
                        raise ContractError(
                            "INVALID_CMS_SIGNATURE", f"token file not found: {tp}"
                        )
                    token_bytes = tp.read_bytes()
                elif "TOKEN_HEX" in ev:
                    token_bytes = bytes.fromhex(ev["TOKEN_HEX"])
            if not isinstance(token_bytes, bytes) or not token_bytes:
                raise ContractError(
                    "INVALID_CMS_SIGNATURE", f"token bytes missing or empty for draw {did}"
                )

            # Check receipt hash
            expected_receipt_hash = ev.get("RECEIPT_SHA256") or ev.get("TOKEN_SHA256")
            if expected_receipt_hash is not None:
                actual_receipt_hash = hashlib.sha256(token_bytes).hexdigest()
                if actual_receipt_hash.lower() != str(expected_receipt_hash).strip().lower():
                    raise ContractError(
                        "RECEIPT_HASH_MISMATCH",
                        f"receipt SHA-256 mismatch: "
                        f"{actual_receipt_hash} != {expected_receipt_hash}",
                    )

            # Parse TSTInfo from token
            parsed_token = _parse_timestamp_token(token_bytes)

            # Check hash algorithm OID
            if parsed_token.algorithm_oid != _OID_SHA256:
                raise ContractError(
                    "IMPRINT_MISMATCH",
                    f"unsupported hash algorithm OID {parsed_token.algorithm_oid}",
                )

            # Check message imprint vs canonical content hash
            imprint_hex = parsed_token.hashed_message.hex().lower()
            if imprint_hex != expected_content_hash.lower():
                raise ContractError(
                    "IMPRINT_MISMATCH",
                    f"message imprint {imprint_hex} != canonical hash {expected_content_hash}",
                )

            # Check TSA policy
            if accepted_policies:
                acc_list = (
                    accepted_policies
                    if isinstance(accepted_policies, (list, tuple, set, frozenset))
                    else [accepted_policies]
                )
                if parsed_token.policy_oid not in acc_list:
                    raise ContractError(
                        "WRONG_TSA_POLICY",
                        f"token policy {parsed_token.policy_oid} not in "
                        f"accepted policies {acc_list}",
                    )

            # Treat INPUT_CUTOFF as the strict lower bound for the TSA time.
            cutoff_dt = _parse_iso_utc(str(pred_by_draw[did].get("INPUT_CUTOFF")), "INPUT_CUTOFF")
            if parsed_token.gen_time <= cutoff_dt:
                raise ContractError(
                    "TIMESTAMP_NOT_AFTER_INPUT_CUTOFF",
                    f"genTime {parsed_token.gen_time} is not after input cutoff {cutoff_dt}",
                )

            # DRAW_TIME comes from the outcome payload and has no authenticated,
            # fixed-identity official source in this verifier. Use it only as a
            # diagnostic upper bound; it is never a trusted draw cutoff.
            draw_cutoff_dt = _parse_iso_utc(
                str(out_by_draw[did].get("DRAW_TIME")), "DRAW_TIME"
            )
            if parsed_token.gen_time >= draw_cutoff_dt:
                raise ContractError(
                    "TIMESTAMP_AFTER_CUTOFF",
                    f"genTime {parsed_token.gen_time} is at or after untrusted outcome "
                    f"DRAW_TIME cutoff {draw_cutoff_dt}",
                )

            # Run OpenSSL verification
            chain_path = (
                Path(ev["CHAIN_PATH"]) if ev.get("CHAIN_PATH") else None
            )
            _verify_openssl_token(
                token_bytes=token_bytes,
                canonical_sha256=expected_content_hash,
                ca_cert_path=ca_cert_path,
                chain_path=chain_path,
                gen_time=parsed_token.gen_time,
            )

    # No current input provides an independently authenticated official draw
    # cutoff with a fixed source identity. A valid token and outcome.DRAW_TIME
    # therefore cannot satisfy independent verification.
    if require_independent_verification:
        raise ContractError(
            "TRUSTED_DRAW_CUTOFF_REQUIRED",
            "independent verification requires an externally authenticated, "
            "fixed-identity TRUSTED_DRAW_CUTOFF; outcomes.DRAW_TIME is untrusted",
        )

    # 7. Execute prospective scoring engine (directly reuses score_biglotto_prospective)
    scoring_result = score_biglotto_prospective(
        pred_data,
        out_data,
        experiment_id=contract_exp_id,
        strategy_identity=contract_strat_id,
        expected_draw_ids=targets,
    )

    # 8. AC5: Enforce diagnostic boundary status
    result = dict(scoring_result)
    result["EVIDENCE_STATUS"] = "DIAGNOSTIC_ONLY"
    result["CAPTURE_TIME_INDEPENDENTLY_VERIFIED"] = False
    result["ORIGINAL_HISTORICAL_PARITY"] = "NOT_VERIFIED"
    result["PREDICTIVE_SUCCESS_EVIDENCE"] = "NOT_ESTABLISHED"
    result["CRYPTO_TOKEN_VALID"] = bundle_data is not None
    result["DRAW_CUTOFF_SOURCE_VERIFIED"] = False
    result["PREDRAW_EVIDENCE_INDEPENDENTLY_VERIFIED"] = False
    result["PREDRAW_EVIDENCE_STATUS"] = "DIAGNOSTIC_ONLY"
    if bundle_data is not None:
        result["CRYPTOGRAPHIC_VERIFIER_STATUS"] = "PASS"
    return result
