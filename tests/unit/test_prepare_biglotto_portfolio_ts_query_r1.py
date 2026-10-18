"""Focused acceptance tests for offline BIG_LOTTO RFC 3161 request preparation."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.prepare_biglotto_portfolio_ts_query_r1 import (
    prepare_biglotto_portfolio_ts_query,
)
from tools.score_biglotto_portfolio_prospective_r1 import ContractError
from tools.verify_biglotto_portfolio_predraw_r1 import (
    build_canonical_portfolio_payload,
    compute_canonical_contract_sha256,
    compute_canonical_portfolio_payload_sha256,
)


def _make_inputs(ticket_count: int = 3) -> tuple[dict[str, Any], dict[str, Any]]:
    tickets = [
        [1, 2, 3, 4, 5, 6],
        [7, 8, 9, 10, 11, 12],
        [13, 14, 15, 16, 17, 18],
        [19, 20, 21, 22, 23, 24],
        [25, 26, 27, 28, 29, 30],
    ][:ticket_count]
    contract: dict[str, Any] = {
        "EXPERIMENT_ID": "SYNTHETIC_TSQ_EXP_R1",
        "STRATEGY_IDENTITY": "synthetic-portfolio@version:1",
        "EXPECTED_DRAW_IDS": ["199000001"],
        "TICKET_COUNT": ticket_count,
    }
    contract_sha256 = compute_canonical_contract_sha256(contract)
    contract["EXPERIMENT_CONTRACT_SHA256"] = contract_sha256
    prediction: dict[str, Any] = {
        "SCHEMA_VERSION": 1,
        "EXPERIMENT_ID": contract["EXPERIMENT_ID"],
        "DRAW_ID": "199000001",
        "TICKET_COUNT": ticket_count,
        "PREDICTED_TICKETS": tickets,
        "STRATEGY_IDENTITY": contract["STRATEGY_IDENTITY"],
        "INPUT_SNAPSHOT_SHA256": "a" * 64,
        "INPUT_CUTOFF": "2000-01-01T12:00:00+00:00",
        "PREDICTION_CAPTURE_ID": "cap-199000001",
        "EXPERIMENT_CONTRACT_SHA256": contract_sha256,
    }
    return prediction, contract


def _refresh_contract_hash(
    prediction: dict[str, Any], contract: dict[str, Any]
) -> None:
    contract_sha256 = compute_canonical_contract_sha256(contract)
    contract["EXPERIMENT_CONTRACT_SHA256"] = contract_sha256
    prediction["EXPERIMENT_CONTRACT_SHA256"] = contract_sha256


class PrepareBigLottoPortfolioTsQueryTests(unittest.TestCase):
    def _prepare(
        self, prediction: dict[str, Any], contract: dict[str, Any]
    ) -> dict[str, Any]:
        return prepare_biglotto_portfolio_ts_query(prediction, contract)

    def test_ticket_counts_2_3_5_produce_openssl_parsed_der(self) -> None:
        observed_counts: list[int] = []
        for ticket_count in (2, 3, 5):
            with self.subTest(ticket_count=ticket_count):
                prediction, contract = _make_inputs(ticket_count)
                result = self._prepare(prediction, contract)
                payload = build_canonical_portfolio_payload(
                    prediction,
                    fallback_contract_sha256=contract["EXPERIMENT_CONTRACT_SHA256"],
                    expected_ticket_count=ticket_count,
                )
                self.assertEqual(payload["TICKET_COUNT"], ticket_count)
                self.assertEqual(len(payload["PREDICTED_TICKETS"]), ticket_count)
                for ticket in payload["PREDICTED_TICKETS"]:
                    self.assertEqual(len(ticket), 6)
                    self.assertEqual(len(set(ticket)), 6)
                    self.assertTrue(all(1 <= number <= 49 for number in ticket))
                self.assertEqual(
                    compute_canonical_portfolio_payload_sha256(payload),
                    result["CANONICAL_PAYLOAD_SHA256"],
                )
                self.assertIsInstance(result["TSQUERY_DER_BYTES"], bytes)
                self.assertTrue(result["TSQUERY_DER_BYTES"].startswith(b"\x30"))
                self.assertEqual(
                    result["CANONICAL_PAYLOAD_SHA256"], result["MESSAGE_IMPRINT_SHA256"]
                )
                self.assertEqual(
                    result["TSQUERY_SHA256"],
                    hashlib.sha256(result["TSQUERY_DER_BYTES"]).hexdigest(),
                )
                self.assertTrue(result["REQUEST_PREPARED"])
                self.assertEqual(result["REQUEST_STATUS"], "PREPARED_OFFLINE")
                self.assertFalse(result["REAL_TSA_TOKEN_ISSUED"])
                self.assertEqual(result["TRUSTED_DRAW_CUTOFF"], "NOT_ESTABLISHED")
                self.assertEqual(result["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
                observed_counts.append(ticket_count)
        self.assertEqual(observed_counts, [2, 3, 5])

    def test_cli_writes_der_and_reports_diagnostic_status(self) -> None:
        prediction, contract = _make_inputs(2)
        script_path = (
            Path(__file__).resolve().parents[2]
            / "tools"
            / "prepare_biglotto_portfolio_ts_query_r1.py"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.json"
            output_path = temp_path / "portfolio.tsq"
            input_path.write_text(
                json.dumps(
                    {"PREDICTION": prediction, "EXPERIMENT_CONTRACT": contract}
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--input-json",
                    str(input_path),
                    "--output-tsq",
                    str(output_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            report = json.loads(result.stdout)
            request_der = output_path.read_bytes()
            self.assertEqual(report["TSQUERY_DER_BYTES_HEX"], request_der.hex())
            self.assertEqual(
                report["TSQUERY_SHA256"], hashlib.sha256(request_der).hexdigest()
            )
            self.assertEqual(report["REQUEST_STATUS"], "PREPARED_OFFLINE")
            self.assertFalse(report["REAL_TSA_TOKEN_ISSUED"])
            self.assertEqual(report["TRUSTED_DRAW_CUTOFF"], "NOT_ESTABLISHED")
            self.assertEqual(report["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
            self.assertTrue(report["OPENSSL_VERSION"].startswith("OpenSSL "))

    def test_fail_closed_matrix(self) -> None:
        base_prediction, base_contract = _make_inputs(3)
        base_result = self._prepare(base_prediction, base_contract)
        valid_mutations: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

        prediction = copy.deepcopy(base_prediction)
        contract = copy.deepcopy(base_contract)
        prediction["PREDICTED_TICKETS"][0][0] = 31
        valid_mutations.append(("FIRST_TICKET_MUTATED", prediction, contract))

        prediction = copy.deepcopy(base_prediction)
        contract = copy.deepcopy(base_contract)
        prediction["PREDICTED_TICKETS"][1][0] = 37
        valid_mutations.append(("MIDDLE_TICKET_MUTATED", prediction, contract))

        prediction = copy.deepcopy(base_prediction)
        contract = copy.deepcopy(base_contract)
        prediction["PREDICTED_TICKETS"][2][0] = 43
        valid_mutations.append(("LAST_TICKET_MUTATED", prediction, contract))

        prediction = copy.deepcopy(base_prediction)
        contract = copy.deepcopy(base_contract)
        prediction["PREDICTED_TICKETS"][0], prediction["PREDICTED_TICKETS"][1] = (
            prediction["PREDICTED_TICKETS"][1],
            prediction["PREDICTED_TICKETS"][0],
        )
        valid_mutations.append(("TICKET_ORDER_CHANGED", prediction, contract))

        prediction = copy.deepcopy(base_prediction)
        contract = copy.deepcopy(base_contract)
        prediction["PREDICTED_TICKETS"] = prediction["PREDICTED_TICKETS"][:2]
        prediction["TICKET_COUNT"] = 2
        contract["TICKET_COUNT"] = 2
        _refresh_contract_hash(prediction, contract)
        valid_mutations.append(("TICKET_COUNT_CHANGED", prediction, contract))

        prediction = copy.deepcopy(base_prediction)
        contract = copy.deepcopy(base_contract)
        prediction["DRAW_ID"] = "199000002"
        contract["EXPECTED_DRAW_IDS"] = ["199000002"]
        _refresh_contract_hash(prediction, contract)
        valid_mutations.append(("DRAW_ID_CHANGED", prediction, contract))

        prediction = copy.deepcopy(base_prediction)
        contract = copy.deepcopy(base_contract)
        prediction["STRATEGY_IDENTITY"] = "synthetic-portfolio@version:2"
        contract["STRATEGY_IDENTITY"] = prediction["STRATEGY_IDENTITY"]
        _refresh_contract_hash(prediction, contract)
        valid_mutations.append(("STRATEGY_IDENTITY_CHANGED", prediction, contract))

        prediction = copy.deepcopy(base_prediction)
        contract = copy.deepcopy(base_contract)
        contract["EXPERIMENT_PURPOSE"] = "offline-ts-query-r2"
        _refresh_contract_hash(prediction, contract)
        valid_mutations.append(("EXPERIMENT_CONTRACT_CHANGED", prediction, contract))

        prediction = copy.deepcopy(base_prediction)
        contract = copy.deepcopy(base_contract)
        prediction["INPUT_SNAPSHOT_SHA256"] = "b" * 64
        valid_mutations.append(("INPUT_SNAPSHOT_CHANGED", prediction, contract))

        for case, prediction, contract in valid_mutations:
            try:
                result = self._prepare(prediction, contract)
                actual = (
                    "IMPRINT_CHANGED"
                    if result["MESSAGE_IMPRINT_SHA256"]
                    != base_result["MESSAGE_IMPRINT_SHA256"]
                    else "IMPRINT_UNCHANGED"
                )
                detail = result["MESSAGE_IMPRINT_SHA256"]
            except ContractError as exc:
                actual = "REJECTED"
                detail = exc.code
            print(
                f"FAIL_CLOSED_MATRIX CASE={case} EXPECTED=IMPRINT_CHANGED "
                f"ACTUAL={actual} DETAIL={detail}"
            )
            self.assertEqual(actual, "IMPRINT_CHANGED", msg=f"{case}: {detail}")

        invalid_mutations: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

        prediction = copy.deepcopy(base_prediction)
        contract = copy.deepcopy(base_contract)
        prediction["PREDICTED_TICKETS"][0] = [1, 1, 2, 3, 4, 5]
        invalid_mutations.append(("MALFORMED_TICKETS", prediction, contract))

        prediction = copy.deepcopy(base_prediction)
        contract = copy.deepcopy(base_contract)
        del prediction["PREDICTION_CAPTURE_ID"]
        invalid_mutations.append(("MISSING_REQUIRED_FIELD", prediction, contract))

        prediction = copy.deepcopy(base_prediction)
        contract = copy.deepcopy(base_contract)
        del prediction["TICKET_COUNT"]
        invalid_mutations.append(("TICKET_COUNT_MISSING", prediction, contract))

        prediction = copy.deepcopy(base_prediction)
        contract = copy.deepcopy(base_contract)
        contract["EXPERIMENT_PURPOSE"] = "hash-mismatch"
        invalid_mutations.append(("EXPERIMENT_CONTRACT_CHANGED_STALE_HASH", prediction, contract))

        for case, prediction, contract in invalid_mutations:
            try:
                self._prepare(prediction, contract)
                actual = "ACCEPTED"
                detail = "no validation error"
            except ContractError as exc:
                actual = "REJECTED"
                detail = exc.code
            print(
                f"FAIL_CLOSED_MATRIX CASE={case} EXPECTED=REJECTED "
                f"ACTUAL={actual} DETAIL={detail}"
            )
            self.assertEqual(actual, "REJECTED", msg=f"{case}: {detail}")


if __name__ == "__main__":
    unittest.main()
