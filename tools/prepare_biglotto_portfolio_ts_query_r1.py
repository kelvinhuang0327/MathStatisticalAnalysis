#!/usr/bin/env python3
"""Prepare an offline RFC 3161 TimeStampReq for a complete BIG_LOTTO portfolio."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.score_biglotto_portfolio_prospective_r1 import (  # noqa: E402
    ALLOWED_TICKET_COUNTS,
    ContractError,
)
from tools.verify_biglotto_portfolio_predraw_r1 import (  # noqa: E402
    build_canonical_portfolio_payload,
    compute_canonical_contract_sha256,
    compute_canonical_portfolio_payload_sha256,
)


def _contract_value(contract: Mapping[str, Any], upper: str, lower: str) -> Any:
    value = contract.get(lower)
    return contract.get(upper) if value is None else value


def _nonempty_text(value: Any, field: str) -> str:
    if value is None:
        raise ContractError("MISSING_FIELD", f"missing required field: {field}")
    text = str(value).strip()
    if not text:
        raise ContractError("MISSING_FIELD", f"empty required field: {field}")
    return text


def _resolve_openssl_executable(requested: str | None) -> tuple[str, str]:
    if requested:
        candidates = [shutil.which(requested) or requested]
    else:
        candidates = [
            "/opt/homebrew/opt/openssl@3/bin/openssl",
            "/usr/local/opt/openssl@3/bin/openssl",
            shutil.which("openssl"),
        ]

    fallback: tuple[str, str] | None = None
    for candidate in candidates:
        if not candidate:
            continue
        try:
            version_result = subprocess.run(
                [candidate, "version"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            continue
        if version_result.returncode != 0:
            continue
        version = (version_result.stdout or version_result.stderr).strip()
        found = (candidate, version)
        if fallback is None:
            fallback = found
        if version.startswith("OpenSSL "):
            return found

    if fallback is not None:
        return fallback
    raise ContractError("OPENSSL_UNAVAILABLE", "could not run an OpenSSL executable")


@lru_cache(maxsize=16)
def _cached_openssl(requested: str | None) -> tuple[str, str]:
    return _resolve_openssl_executable(requested)


def _message_imprint_from_openssl_text(text: str) -> str:
    if not re.search(r"(?im)^Hash Algorithm:\s*sha256\s*$", text):
        raise ContractError(
            "INVALID_TSQUERY",
            "OpenSSL did not parse the request with the SHA-256 algorithm",
        )

    in_message_data = False
    octets: list[str] = []
    for line in text.splitlines():
        if line.strip() == "Message data:":
            in_message_data = True
            continue
        if not in_message_data:
            continue
        if re.match(r"^\s*(?:Policy OID|Nonce|Certificate required|Extensions):", line):
            break
        match = re.match(r"^\s*[0-9a-fA-F]{4}\s*-\s*(.*)$", line)
        if match:
            byte_column = match.group(1).split("  ", 1)[0]
            octets.extend(re.findall(r"(?<![0-9a-fA-F])[0-9a-fA-F]{2}(?![0-9a-fA-F])", byte_column))

    if len(octets) != 32:
        raise ContractError(
            "INVALID_TSQUERY",
            f"OpenSSL parsed {len(octets)} message-imprint bytes; expected 32",
        )
    return "".join(octets).lower()


def _create_and_parse_ts_query(
    payload_sha256: str, openssl_executable: str
) -> tuple[bytes, str]:
    generated = subprocess.run(
        [
            openssl_executable,
            "ts",
            "-query",
            "-digest",
            payload_sha256,
            "-sha256",
            "-out",
            "/dev/stdout",
        ],
        check=False,
        capture_output=True,
    )
    if generated.returncode != 0 or not generated.stdout:
        detail = generated.stderr.decode("utf-8", errors="replace").strip()
        raise ContractError(
            "OPENSSL_TS_QUERY_FAILED", detail or "OpenSSL did not produce request DER"
        )

    parsed = subprocess.run(
        [openssl_executable, "ts", "-query", "-in", "/dev/stdin", "-text"],
        input=generated.stdout,
        check=False,
        capture_output=True,
    )
    if parsed.returncode != 0:
        detail = parsed.stderr.decode("utf-8", errors="replace").strip()
        raise ContractError(
            "OPENSSL_TS_QUERY_PARSE_FAILED", detail or "OpenSSL rejected request DER"
        )

    parsed_text = parsed.stdout.decode("utf-8", errors="replace")
    imprint = _message_imprint_from_openssl_text(parsed_text)
    return generated.stdout, imprint


def prepare_biglotto_portfolio_ts_query(
    prediction: Mapping[str, Any],
    experiment_contract: Mapping[str, Any],
    *,
    openssl_executable: str | Path | None = None,
) -> dict[str, Any]:
    """Return an offline RFC 3161 request bound to the full canonical portfolio."""
    if not isinstance(prediction, Mapping):
        raise ContractError("WRONG_INPUT_FORMAT", "prediction must be a mapping")
    if not isinstance(experiment_contract, Mapping):
        raise ContractError("WRONG_INPUT_FORMAT", "experiment contract must be a mapping")
    if "TICKET_COUNT" not in prediction:
        raise ContractError("MISSING_FIELD", "missing required field: TICKET_COUNT")

    experiment_id = _nonempty_text(prediction.get("EXPERIMENT_ID"), "EXPERIMENT_ID")
    draw_id = _nonempty_text(prediction.get("DRAW_ID"), "DRAW_ID")
    strategy_identity = _nonempty_text(
        prediction.get("STRATEGY_IDENTITY"), "STRATEGY_IDENTITY"
    )
    _nonempty_text(prediction.get("PREDICTION_CAPTURE_ID"), "PREDICTION_CAPTURE_ID")
    provided_contract_sha256 = _nonempty_text(
        prediction.get("EXPERIMENT_CONTRACT_SHA256"), "EXPERIMENT_CONTRACT_SHA256"
    ).lower()

    calculated_contract_sha256 = compute_canonical_contract_sha256(experiment_contract)
    if provided_contract_sha256 != calculated_contract_sha256:
        raise ContractError(
            "EXPERIMENT_CONTRACT_HASH_CHANGED",
            "prediction contract SHA-256 does not match the supplied experiment contract",
        )

    contract_experiment_id = _nonempty_text(
        _contract_value(experiment_contract, "EXPERIMENT_ID", "experiment_id"),
        "EXPERIMENT_ID in experiment contract",
    )
    contract_strategy = _nonempty_text(
        _contract_value(experiment_contract, "STRATEGY_IDENTITY", "strategy_identity"),
        "STRATEGY_IDENTITY in experiment contract",
    )
    draw_ids = _contract_value(experiment_contract, "EXPECTED_DRAW_IDS", "expected_draw_ids")
    if not isinstance(draw_ids, (list, tuple)) or not draw_ids:
        raise ContractError("INVALID_DRAW_SET", "experiment contract needs expected draw IDs")
    expected_draw_ids = [_nonempty_text(value, "EXPECTED_DRAW_IDS entry") for value in draw_ids]
    if len(set(expected_draw_ids)) != len(expected_draw_ids):
        raise ContractError("DUPLICATE_DRAW", "experiment contract contains duplicate draw IDs")

    contract_ticket_count = _contract_value(
        experiment_contract, "TICKET_COUNT", "ticket_count"
    )
    if type(contract_ticket_count) is not int or contract_ticket_count not in ALLOWED_TICKET_COUNTS:
        raise ContractError(
            "INVALID_TICKET_COUNT",
            "experiment contract TICKET_COUNT must be 2, 3, or 5",
        )
    if experiment_id != contract_experiment_id:
        raise ContractError(
            "EXPERIMENT_ID_MISMATCH", "prediction and contract experiment IDs differ"
        )
    if strategy_identity != contract_strategy:
        raise ContractError(
            "STRATEGY_IDENTITY_MISMATCH", "prediction and contract strategy identities differ"
        )
    if draw_id not in expected_draw_ids:
        raise ContractError("DRAW_SET_MISMATCH", "prediction draw ID is not in the contract")

    payload = build_canonical_portfolio_payload(
        prediction,
        fallback_contract_sha256=calculated_contract_sha256,
        expected_ticket_count=contract_ticket_count,
    )
    payload_sha256 = compute_canonical_portfolio_payload_sha256(payload)

    requested_executable = str(openssl_executable) if openssl_executable is not None else None
    resolved_executable, openssl_version = _cached_openssl(requested_executable)
    request_der, parsed_imprint = _create_and_parse_ts_query(payload_sha256, resolved_executable)
    if parsed_imprint != payload_sha256:
        raise ContractError(
            "TSQUERY_IMPRINT_MISMATCH",
            "OpenSSL-parsed message imprint differs from the canonical portfolio SHA-256",
        )

    return {
        "CANONICAL_PAYLOAD_SHA256": payload_sha256,
        "MESSAGE_IMPRINT_SHA256": parsed_imprint,
        "OPENSSL_EXECUTABLE": resolved_executable,
        "OPENSSL_VERSION": openssl_version,
        "REQUEST_PREPARED": True,
        "REQUEST_STATUS": "PREPARED_OFFLINE",
        "REAL_TSA_TOKEN_ISSUED": False,
        "TRUSTED_DRAW_CUTOFF": "NOT_ESTABLISHED",
        "EVIDENCE_STATUS": "DIAGNOSTIC_ONLY",
        "TSQUERY_DER_BYTES": request_der,
        "TSQUERY_SHA256": hashlib.sha256(request_der).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a diagnostic-only offline RFC 3161 request for a BIG_LOTTO portfolio."
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        required=True,
        help="JSON object with PREDICTION and EXPERIMENT_CONTRACT mappings",
    )
    parser.add_argument("--output-tsq", type=Path, required=True, help="new DER output file")
    parser.add_argument(
        "--openssl",
        dest="openssl_executable",
        help="OpenSSL executable (defaults to an installed OpenSSL, then openssl on PATH)",
    )
    args = parser.parse_args(argv)

    try:
        input_record = json.loads(args.input_json.read_text(encoding="utf-8"))
        if not isinstance(input_record, Mapping):
            raise ContractError("WRONG_INPUT_FORMAT", "input JSON root must be an object")
        result = prepare_biglotto_portfolio_ts_query(
            input_record.get("PREDICTION"),
            input_record.get("EXPERIMENT_CONTRACT"),
            openssl_executable=args.openssl_executable,
        )
        with args.output_tsq.open("xb") as output_file:
            output_file.write(result["TSQUERY_DER_BYTES"])
    except (ContractError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    report = {key: value for key, value in result.items() if key != "TSQUERY_DER_BYTES"}
    report["TSQUERY_DER_BYTES_HEX"] = result["TSQUERY_DER_BYTES"].hex()
    report["TSQUERY_DER_BYTES_PATH"] = str(args.output_tsq)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
