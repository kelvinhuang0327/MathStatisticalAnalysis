"""Minimal, standard-library RFC 3161 offline pre-draw portfolio evidence verifier (Python 3.9).

Binds complete prospective BIG_LOTTO prediction portfolios (m in {2, 3, 5} tickets per draw)
into a single deterministic canonical payload and verifies RFC 3161 timestamp evidence.

Reuses tools/score_biglotto_portfolio_prospective_r1.py for multivariate exact scoring,
and cryptographic verification functions from tools/verify_biglotto_predraw_evidence_r2.py.

Public entry points:
    verify_biglotto_portfolio_predraw_boundary(...)
    build_canonical_portfolio_payload(...)
    compute_canonical_portfolio_payload_sha256(...)
    compute_canonical_contract_sha256(...)
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping
from datetime import timezone
from pathlib import Path
from typing import Any

_UTC = timezone.utc  # noqa: UP017

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from tools.score_biglotto_portfolio_prospective_r1 import (
        ALLOWED_TICKET_COUNTS,
        ContractError,
        _validate_single_ticket,
        score_biglotto_portfolio_prospective,
    )
except ImportError:
    try:
        from score_biglotto_portfolio_prospective_r1 import (  # type: ignore
            ALLOWED_TICKET_COUNTS,
            ContractError,
            _validate_single_ticket,
            score_biglotto_portfolio_prospective,
        )
    except ImportError:

        class ContractError(ValueError):  # type: ignore
            """Fail-closed rejection with a stable machine-readable code."""

            def __init__(self, code: str, detail: str) -> None:
                self.code = code
                super().__init__(f"{code}: {detail}")

        ALLOWED_TICKET_COUNTS = frozenset({2, 3, 5})

        def _validate_single_ticket(t: Any) -> tuple[int, ...]:  # type: ignore
            if not isinstance(t, (list, tuple)) or len(t) != 6:
                raise ContractError("INVALID_NUMBERS", "each ticket must have 6 numbers")
            if any(type(n) is not int for n in t) or any(n < 1 or n > 49 for n in t):
                raise ContractError("INVALID_NUMBERS", "numbers must be integers between 1 and 49")
            if len(set(t)) != 6:
                raise ContractError("DUPLICATE_NUMBERS", "ticket contains duplicate numbers")
            return tuple(sorted(t))

        def score_biglotto_portfolio_prospective(*args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore
            raise NotImplementedError("scorer not available")

try:
    from tools.verify_biglotto_predraw_evidence_r2 import (
        _OID_SHA256,
        _check_forbidden_claims,
        _load_json,
        _parse_iso_utc,
        _parse_timestamp_token,
        _verify_openssl_token,
        _verify_snapshot_bytes,
    )
except ImportError:
    try:
        from verify_biglotto_predraw_evidence_r2 import (  # type: ignore
            _OID_SHA256,
            _check_forbidden_claims,
            _load_json,
            _parse_iso_utc,
            _parse_timestamp_token,
            _verify_openssl_token,
            _verify_snapshot_bytes,
        )
    except ImportError:
        _OID_SHA256 = "2.16.840.1.101.3.4.2.1"


PORTFOLIO_PAYLOAD_FIELDS = (
    "SCHEMA_VERSION",
    "EXPERIMENT_ID",
    "DRAW_ID",
    "TICKET_COUNT",
    "PREDICTED_TICKETS",
    "STRATEGY_IDENTITY",
    "INPUT_SNAPSHOT_SHA256",
    "INPUT_CUTOFF",
    "PREDICTION_CAPTURE_ID",
    "EXPERIMENT_CONTRACT_SHA256",
)

CANONICAL_PORTFOLIO_BINDING_FIELDS = PORTFOLIO_PAYLOAD_FIELDS


def compute_canonical_contract_sha256(contract: Mapping[str, Any]) -> str:
    """Compute deterministic SHA-256 of the canonical experiment contract."""
    core = {
        str(k): v
        for k, v in contract.items()
        if str(k) not in ("EXPERIMENT_CONTRACT_SHA256", "ACCEPTED_TSA_POLICIES")
    }
    canonical_json = json.dumps(
        core,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def get_expected_contract_sha256(contract: Mapping[str, Any]) -> str:
    """Extract or compute the expected experiment contract SHA-256."""
    val = contract.get("EXPERIMENT_CONTRACT_SHA256") or contract.get("contract_sha256")
    if val is not None and isinstance(val, str) and val.strip():
        return val.strip().lower()
    return compute_canonical_contract_sha256(contract)


def build_canonical_portfolio_payload(
    row: Mapping[str, Any],
    *,
    fallback_contract_sha256: str | None = None,
    expected_ticket_count: int | None = None,
) -> dict[str, Any]:
    """Validate and build deterministic canonical portfolio prediction payload."""
    if not isinstance(row, Mapping):
        raise ContractError("WRONG_INPUT_FORMAT", "prediction row must be a mapping")

    # Locate ticket container
    ticket_field = None
    for cand in ("PREDICTED_TICKETS", "PORTFOLIO_PREDICTED_NUMBERS", "TICKETS"):
        if cand in row and row[cand] is not None:
            if ticket_field is not None:
                raise ContractError(
                    "UNEXPECTED_FIELD",
                    f"multiple ticket fields found in prediction: {ticket_field}, {cand}",
                )
            ticket_field = cand

    if ticket_field is None:
        raise ContractError(
            "MISSING_FIELD", "prediction missing canonical fields: PREDICTED_TICKETS"
        )

    contract_sha = row.get("EXPERIMENT_CONTRACT_SHA256")
    if contract_sha is None and fallback_contract_sha256 is not None:
        contract_sha = fallback_contract_sha256

    # Schema version validation
    schema_ver_raw = row.get("SCHEMA_VERSION", 1)
    if type(schema_ver_raw) is not int or schema_ver_raw != 1:
        raise ContractError(
            "INVALID_SCHEMA_VERSION",
            f"unsupported or invalid SCHEMA_VERSION {schema_ver_raw}; expected 1",
        )

    # Check for missing required canonical fields
    missing = []
    for f in (
        "DRAW_ID",
        "EXPERIMENT_ID",
        "INPUT_CUTOFF",
        "INPUT_SNAPSHOT_SHA256",
        "PREDICTION_CAPTURE_ID",
        "STRATEGY_IDENTITY",
    ):
        if f not in row or row[f] is None:
            missing.append(f)
    if contract_sha is None:
        missing.append("EXPERIMENT_CONTRACT_SHA256")
    if "TICKET_COUNT" not in row and expected_ticket_count is None:
        missing.append("TICKET_COUNT")

    if missing:
        raise ContractError(
            "MISSING_FIELD",
            f"prediction missing canonical fields: {', '.join(sorted(missing))}",
        )

    # Ticket list structure and cardinality
    raw_tickets = row[ticket_field]
    if not isinstance(raw_tickets, (list, tuple)):
        raise ContractError("INVALID_TICKET_COUNT", f"{ticket_field} must be a list or tuple")

    m = len(raw_tickets)
    if m not in ALLOWED_TICKET_COUNTS:
        raise ContractError(
            "INVALID_TICKET_COUNT",
            f"ticket count {m} not in allowed set (2, 3, 5)",
        )

    declared_tc = row.get("TICKET_COUNT")
    if declared_tc is not None:
        if type(declared_tc) is not int or declared_tc not in ALLOWED_TICKET_COUNTS:
            raise ContractError(
                "INVALID_TICKET_COUNT",
                f"TICKET_COUNT must be int in (2, 3, 5); got {declared_tc}",
            )
        if declared_tc != m:
            raise ContractError(
                "TICKET_COUNT_CHANGED",
                f"declared TICKET_COUNT {declared_tc} != length of tickets {m}",
            )

    if expected_ticket_count is not None and m != expected_ticket_count:
        raise ContractError(
            "TICKET_COUNT_CHANGED",
            f"prediction ticket count {m} != expected contract {expected_ticket_count}",
        )

    # Validate each individual ticket: 6 distinct integers 1..49
    canonical_tickets = []
    for t in raw_tickets:
        canonical_tickets.append(list(_validate_single_ticket(t)))

    # Strategy identity validation
    strat_id = str(row["STRATEGY_IDENTITY"]).strip()
    if strat_id.upper() in {"UNKNOWN", "UNVERIFIED", "NONE", ""}:
        raise ContractError(
            "WRONG_STRATEGY_IDENTITY",
            f"invalid strategy identity: {strat_id}",
        )

    # Snapshot hash format
    snap_hash = str(row["INPUT_SNAPSHOT_SHA256"]).strip().lower()
    if len(snap_hash) != 64 or any(c not in "0123456789abcdef" for c in snap_hash):
        raise ContractError(
            "SNAPSHOT_HASH_CHANGED",
            f"invalid snapshot SHA-256 format: {snap_hash}",
        )

    # Contract hash format
    c_sha = str(contract_sha).strip().lower()
    if len(c_sha) != 64 or any(c not in "0123456789abcdef" for c in c_sha):
        raise ContractError(
            "EXPERIMENT_CONTRACT_HASH_CHANGED",
            f"invalid contract SHA-256 format: {c_sha}",
        )

    # Input cutoff validation
    cutoff_str = str(row["INPUT_CUTOFF"]).strip()
    _parse_iso_utc(cutoff_str, "INPUT_CUTOFF")

    return {
        "DRAW_ID": str(row["DRAW_ID"]).strip(),
        "EXPERIMENT_CONTRACT_SHA256": c_sha,
        "EXPERIMENT_ID": str(row["EXPERIMENT_ID"]).strip(),
        "INPUT_CUTOFF": cutoff_str,
        "INPUT_SNAPSHOT_SHA256": snap_hash,
        "PREDICTED_TICKETS": canonical_tickets,
        "PREDICTION_CAPTURE_ID": str(row["PREDICTION_CAPTURE_ID"]).strip(),
        "SCHEMA_VERSION": schema_ver_raw,
        "STRATEGY_IDENTITY": strat_id,
        "TICKET_COUNT": m,
    }


def compute_canonical_portfolio_payload_sha256(payload: Mapping[str, Any]) -> str:
    """Compute the deterministic SHA-256 of the canonical portfolio prediction payload."""
    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def verify_biglotto_portfolio_predraw_boundary(
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
    """Verify prospective BIG_LOTTO portfolio predictions, outcomes, contract, and predraw evidence.

    Fails closed on any inconsistency, missing evidence, untrusted TSA, or invalid proof.
    Preserves exact multivariate portfolio scoring and sets diagnostic boundary status.
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

    # 2. Gate: Fail-closed checks on forbidden verified / success claims
    _check_forbidden_claims(contract_data, "contract")
    _check_forbidden_claims(pred_data, "predictions")
    _check_forbidden_claims(out_data, "outcomes")
    if bundle_data is not None:
        _check_forbidden_claims(bundle_data, "evidence_bundle")

    # Contract required fields
    exp_id = contract_data.get("experiment_id") or contract_data.get("EXPERIMENT_ID")
    strat_id = contract_data.get("strategy_identity") or contract_data.get("STRATEGY_IDENTITY")
    draw_ids = contract_data.get("expected_draw_ids") or contract_data.get("EXPECTED_DRAW_IDS")
    contract_tc = contract_data.get("ticket_count") or contract_data.get("TICKET_COUNT")

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

    if contract_tc is not None and (
        type(contract_tc) is not int or contract_tc not in ALLOWED_TICKET_COUNTS
    ):
        raise ContractError(
            "INVALID_TICKET_COUNT",
            f"contract ticket_count must be in (2, 3, 5); got {contract_tc}",
        )

    expected_contract_sha = get_expected_contract_sha256(contract_data)

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

    # 4. Check Strategy Identity, Contract Hash, and Canonical Binding for every prediction
    canonical_payloads: dict[str, dict[str, Any]] = {}
    canonical_hashes: dict[str, str] = {}
    observed_ticket_counts = set()

    for did in targets:
        p = pred_by_draw[did]
        row_strat = str(p.get("STRATEGY_IDENTITY", "")).strip()
        if row_strat != contract_strat_id:
            raise ContractError(
                "STRATEGY_IDENTITY_MISMATCH",
                f"prediction strategy {row_strat} != contract {contract_strat_id}",
            )

        p_contract_sha = str(p.get("EXPERIMENT_CONTRACT_SHA256", "")).strip().lower()
        if p_contract_sha and p_contract_sha != expected_contract_sha:
            raise ContractError(
                "EXPERIMENT_CONTRACT_HASH_CHANGED",
                f"prediction contract hash {p_contract_sha} != expected {expected_contract_sha}",
            )

        payload = build_canonical_portfolio_payload(
            p,
            fallback_contract_sha256=expected_contract_sha,
            expected_ticket_count=contract_tc,
        )
        canonical_payloads[did] = payload
        canonical_hashes[did] = compute_canonical_portfolio_payload_sha256(payload)
        observed_ticket_counts.add(payload["TICKET_COUNT"])

    if len(observed_ticket_counts) > 1:
        raise ContractError(
            "MIXED_TICKET_COUNTS",
            f"predictions have mixed ticket counts across draws: {observed_ticket_counts}",
        )

    resolved_ticket_count = next(iter(observed_ticket_counts))

    # 5. Snapshot verification
    if snapshot_files_by_sha256 is not None:
        for did in targets:
            p = pred_by_draw[did]
            snap_hash = str(p.get("INPUT_SNAPSHOT_SHA256", "")).strip().lower()
            if snap_hash not in snapshot_files_by_sha256:
                raise ContractError(
                    "SNAPSHOT_HASH_CHANGED",
                    f"snapshot {snap_hash} missing from snapshot_files_by_sha256",
                )
            val = snapshot_files_by_sha256[snap_hash]
            if isinstance(val, bytes):
                raw_snap_bytes = val
            elif isinstance(val, (str, Path)):
                sp = Path(val)
                if not sp.is_file():
                    raise ContractError("SNAPSHOT_HASH_CHANGED", f"snapshot file not found: {sp}")
                raw_snap_bytes = sp.read_bytes()
            else:
                raise ContractError("SNAPSHOT_HASH_CHANGED", "invalid snapshot entry type")
            cutoff_dt = _parse_iso_utc(str(p.get("INPUT_CUTOFF")), "INPUT_CUTOFF")
            actual_snap_hash = hashlib.sha256(raw_snap_bytes).hexdigest()
            if actual_snap_hash.lower() != snap_hash:
                raise ContractError(
                    "SNAPSHOT_HASH_CHANGED",
                    f"snapshot bytes SHA-256 mismatch: {actual_snap_hash} != {snap_hash}",
                )
            _verify_snapshot_bytes(raw_snap_bytes, snap_hash, did, cutoff_dt)
    elif require_independent_verification:
        raise ContractError(
            "SNAPSHOT_HASH_CHANGED",
            "snapshot_files_by_sha256 is required for independent verification",
        )

    # 6. Cryptographic Evidence Verification
    if bundle_data is not None or require_independent_verification:
        if bundle_data is None:
            raise ContractError(
                "MISSING_EVIDENCE_FOR_DRAW",
                "evidence_bundle is required when verification is requested",
            )

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
        if actual_ca_sha256.lower() != str(pinned_tsa_cert_sha256).strip().lower():
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

            if (
                "STRATEGY_IDENTITY" in ev
                and str(ev["STRATEGY_IDENTITY"]).strip() != contract_strat_id
            ):
                raise ContractError(
                    "STRATEGY_IDENTITY_MISMATCH",
                    f"evidence strategy {ev['STRATEGY_IDENTITY']} != contract {contract_strat_id}",
                )

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
                    f"evidence content hash {content_hash_in_ev} != "
                    f"computed {expected_content_hash}",
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

            expected_receipt_hash = ev.get("RECEIPT_SHA256") or ev.get("TOKEN_SHA256")
            if expected_receipt_hash is not None:
                actual_receipt_hash = hashlib.sha256(token_bytes).hexdigest()
                if actual_receipt_hash.lower() != str(expected_receipt_hash).strip().lower():
                    raise ContractError(
                        "RECEIPT_HASH_MISMATCH",
                        f"receipt SHA-256 mismatch: "
                        f"{actual_receipt_hash} != {expected_receipt_hash}",
                    )

            parsed_token = _parse_timestamp_token(token_bytes)

            if parsed_token.algorithm_oid != _OID_SHA256:
                raise ContractError(
                    "TOKEN_IMPRINT_MISMATCH",
                    f"unsupported hash algorithm OID {parsed_token.algorithm_oid}",
                )

            imprint_hex = parsed_token.hashed_message.hex().lower()
            if imprint_hex != expected_content_hash.lower():
                raise ContractError(
                    "TOKEN_IMPRINT_MISMATCH",
                    f"message imprint {imprint_hex} != canonical hash {expected_content_hash}",
                )

            if accepted_policies:
                acc_list = (
                    accepted_policies
                    if isinstance(accepted_policies, (list, tuple, set, frozenset))
                    else [accepted_policies]
                )
                if parsed_token.policy_oid not in acc_list:
                    raise ContractError(
                        "WRONG_TSA_POLICY",
                        f"token policy {parsed_token.policy_oid} not in accepted {acc_list}",
                    )

            cutoff_dt = _parse_iso_utc(str(pred_by_draw[did].get("INPUT_CUTOFF")), "INPUT_CUTOFF")
            if parsed_token.gen_time <= cutoff_dt:
                raise ContractError(
                    "TIMESTAMP_NOT_AFTER_INPUT_CUTOFF",
                    f"genTime {parsed_token.gen_time} is not after input cutoff {cutoff_dt}",
                )

            draw_cutoff_dt = _parse_iso_utc(
                str(out_by_draw[did].get("DRAW_TIME")), "DRAW_TIME"
            )
            if parsed_token.gen_time >= draw_cutoff_dt:
                raise ContractError(
                    "TIMESTAMP_AFTER_CUTOFF",
                    f"genTime {parsed_token.gen_time} is at or after cutoff {draw_cutoff_dt}",
                )

            chain_path = Path(ev["CHAIN_PATH"]) if ev.get("CHAIN_PATH") else None
            _verify_openssl_token(
                token_bytes=token_bytes,
                canonical_sha256=expected_content_hash,
                ca_cert_path=ca_cert_path,
                chain_path=chain_path,
                gen_time=parsed_token.gen_time,
            )

    if require_independent_verification:
        raise ContractError(
            "TRUSTED_DRAW_CUTOFF_REQUIRED",
            "independent verification requires an externally authenticated, "
            "fixed-identity TRUSTED_DRAW_CUTOFF; outcomes.DRAW_TIME is untrusted",
        )

    # 7. Execute prospective portfolio scoring engine
    scoring_predictions = []
    for p in pred_data:
        p_clean = dict(p)
        for extra in ("SCHEMA_VERSION", "TICKET_COUNT", "EXPERIMENT_CONTRACT_SHA256"):
            p_clean.pop(extra, None)
        scoring_predictions.append(p_clean)

    scoring_result = score_biglotto_portfolio_prospective(
        scoring_predictions,
        out_data,
        experiment_id=contract_exp_id,
        strategy_identity=contract_strat_id,
        expected_draw_ids=targets,
        ticket_count=resolved_ticket_count,
    )

    # 8. AC5: Enforce diagnostic boundary status
    result = dict(scoring_result)
    result["EVIDENCE_STATUS"] = "DIAGNOSTIC_ONLY"
    result["CAPTURE_TIME_INDEPENDENTLY_VERIFIED"] = False
    result["ORIGINAL_HISTORICAL_PARITY"] = "NOT_VERIFIED"
    result["PREDICTIVE_SUCCESS_EVIDENCE"] = "NOT_ESTABLISHED"
    result["PREDICTIVE_SUCCESS_IMPROVEMENT"] = "NOT_ESTABLISHED"
    result["CRYPTO_TOKEN_VALID"] = bundle_data is not None
    result["DRAW_CUTOFF_SOURCE_VERIFIED"] = False
    result["PREDRAW_EVIDENCE_INDEPENDENTLY_VERIFIED"] = False
    result["PREDRAW_EVIDENCE_STATUS"] = "DIAGNOSTIC_ONLY"
    if bundle_data is not None:
        result["CRYPTOGRAPHIC_VERIFIER_STATUS"] = "PASS"
    return result


# Public entry point aliases
verify_portfolio_predraw_evidence_boundary = verify_biglotto_portfolio_predraw_boundary
verify_predraw_evidence_boundary = verify_biglotto_portfolio_predraw_boundary
