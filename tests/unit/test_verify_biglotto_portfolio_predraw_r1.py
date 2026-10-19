"""Unit and integration tests for tools/verify_biglotto_portfolio_predraw_r1.py.

Validates:
- AC1: Git source commits/trees, byte-exact identity of K235 source/test, unchanged original files.
- AC2: Full portfolio validation for m in {2, 3, 5} with valid synthetic data and fail-closed gates.
- AC3: Full portfolio payload cryptographic binding and fail-closed matrix for 12 mutations.
- AC4: Multivariate exact hypergeometric baselines and multi-draw aggregation.
- AC5: Temporal boundaries (INPUT_CUTOFF < genTime < DRAW_CUTOFF) and DIAGNOSTIC_ONLY evidence.
- AC6: Experiment contract integrity and fixed draw sets.
- AC7: Python 3.9 compatibility.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tests.unit.test_verify_biglotto_predraw_evidence_r2 import _SyntheticTsaHarness
from tools.score_biglotto_portfolio_prospective_r1 import (
    OUTCOME_DENOMINATOR,
    ContractError,
    portfolio_exact_baseline,
)
from tools.verify_biglotto_portfolio_predraw_r1 import (
    PORTFOLIO_PAYLOAD_FIELDS,
    build_canonical_portfolio_payload,
    compute_canonical_contract_sha256,
    compute_canonical_portfolio_payload_sha256,
    verify_biglotto_portfolio_predraw_boundary,
)

EXPECTED_BASE_VERIFIER_COMMIT = "1ad5d858ae84e0ec7e47b084754e73c9d2cc4e65"
EXPECTED_BASE_VERIFIER_TREE = "ea4e5afddcd3a414a86c776532a84372391757e5"
EXPECTED_K235_SOURCE_COMMIT = "ab74c49a95cde10e521cb17f4b57f44ad74b8092"
EXPECTED_K235_SOURCE_TREE = "be6d7120d12201808b2f272d7aeaff36489d5c2e"
EXPECTED_K235_SOURCE_SHA256 = (
    "9eb3c0e60afa60d11b6d020bf78dffc9e39723a62e72eab0794dbcea8eccb055"
)
BASE_R2_SOURCE_IDENTITY = {
    "commit": "0855d7b01973c3e3b663f3ce2abc5788f9fd0f84",
    "path": "tools/verify_biglotto_predraw_evidence_r2.py",
    "sha256": "c19144d9ad1f8bb88452524e18fc29588e66909d8957123ff91b7a542f6f2e2c",
}
FIXED_HEAD_R2_SOURCE_IDENTITY = {
    "commit": "1bffdd6087c79a138b64d7970b7bc9b7c3cc43f5",
    "path": "tools/verify_biglotto_predraw_evidence_r2.py",
    "sha256": "e59979c63be9d8e10b9c22ec2dd961363a3fc13e1faa94347f8eaabe6b1d6f07",
}
CANDIDATE_R2_SOURCE_IDENTITY = {
    "path": "tools/verify_biglotto_predraw_evidence_r2.py",
    "sha256": "f77efa014a834d1831513da11f9279698ac2602a74c7081ef07a0751e022e497",
}


def _assert_source_sha256_identity(
    actual_sha256: str,
    expected_sha256: str,
    identity_name: str,
) -> None:
    if actual_sha256 != expected_sha256:
        raise AssertionError(
            f"{identity_name} SHA256 mismatch: expected {expected_sha256}, "
            f"got {actual_sha256}"
        )


def _make_contract_fixture(
    draws: list[str] | None = None,
    *,
    experiment_id: str = "SYNTHETIC_PORTFOLIO_EXP_R1",
    strategy_id: str = "synthetic-portfolio@version:1",
    ticket_count: int = 2,
) -> dict[str, Any]:
    c = {
        "EXPERIMENT_ID": experiment_id,
        "STRATEGY_IDENTITY": strategy_id,
        "EXPECTED_DRAW_IDS": draws or ["199000001"],
        "TICKET_COUNT": ticket_count,
    }
    c["EXPERIMENT_CONTRACT_SHA256"] = compute_canonical_contract_sha256(c)
    return c


def _synthetic_tickets(ticket_count: int, pattern: str = "disjoint") -> list[list[int]]:
    if pattern == "disjoint":
        base = [
            [1, 2, 3, 4, 5, 6],
            [7, 8, 9, 10, 11, 12],
            [13, 14, 15, 16, 17, 18],
            [19, 20, 21, 22, 23, 24],
            [25, 26, 27, 28, 29, 30],
        ]
        return copy.deepcopy(base[:ticket_count])
    if pattern == "shared_core_3":
        core = [1, 2, 3]
        return [
            [*core, 4, 5, 6],
            [*core, 7, 8, 9],
            [*core, 10, 11, 12],
            [*core, 13, 14, 15],
            [*core, 16, 17, 18],
        ][:ticket_count]
    raise ValueError(f"unknown pattern: {pattern}")


def _make_prediction_fixture(
    draw_id: str = "199000001",
    *,
    ticket_count: int = 2,
    pattern: str = "disjoint",
    tickets: list[list[int]] | None = None,
    experiment_id: str = "SYNTHETIC_PORTFOLIO_EXP_R1",
    strategy_id: str = "synthetic-portfolio@version:1",
    contract_sha: str | None = None,
    snapshot_hash: str = "a" * 64,
    cutoff: str = "2000-01-01T12:00:00+00:00",
    capture_time: str = "2000-01-01T12:01:00+00:00",
) -> dict[str, Any]:
    t = tickets if tickets is not None else _synthetic_tickets(ticket_count, pattern)
    if contract_sha is None:
        c = _make_contract_fixture(
            [draw_id],
            experiment_id=experiment_id,
            strategy_id=strategy_id,
            ticket_count=ticket_count,
        )
        contract_sha = c["EXPERIMENT_CONTRACT_SHA256"]

    return {
        "SCHEMA_VERSION": 1,
        "EXPERIMENT_ID": experiment_id,
        "DRAW_ID": draw_id,
        "TICKET_COUNT": len(t),
        "PREDICTED_TICKETS": copy.deepcopy(t),
        "STRATEGY_IDENTITY": strategy_id,
        "INPUT_SNAPSHOT_SHA256": snapshot_hash,
        "INPUT_CUTOFF": cutoff,
        "PREDICTION_CAPTURE_ID": f"cap-{draw_id}",
        "PREDICTION_CAPTURE_TIME": capture_time,
        "PREDRAW_EVIDENCE_LOCATOR": f"evidence://{draw_id}",
        "EXPERIMENT_CONTRACT_SHA256": contract_sha,
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


class VerifyBigLottoPortfolioPredrawTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)
        self.tsa = _SyntheticTsaHarness(self.tmp / "tsa")
        self.ca_pem_path = self.tsa.ca_cert
        self.ca_sha256 = hashlib.sha256(self.ca_pem_path.read_bytes()).hexdigest()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _issue_evidence_bundle(
        self,
        predictions: list[dict[str, Any]],
        contract: dict[str, Any],
        *,
        tsa_harness: _SyntheticTsaHarness | None = None,
        include_content_sha: bool = False,
    ) -> dict[str, Any]:
        harness = tsa_harness or self.tsa
        bundle = {}
        for p in predictions:
            did = p["DRAW_ID"]
            payload = build_canonical_portfolio_payload(
                p,
                fallback_contract_sha256=contract.get("EXPERIMENT_CONTRACT_SHA256"),
            )
            payload_sha = compute_canonical_portfolio_payload_sha256(payload)
            token_bytes = harness.issue_token(payload_sha)
            entry: dict[str, Any] = {
                "DRAW_ID": did,
                "STRATEGY_IDENTITY": p["STRATEGY_IDENTITY"],
                "TOKEN_BYTES": token_bytes,
                "TOKEN_SHA256": hashlib.sha256(token_bytes).hexdigest(),
            }
            if include_content_sha:
                entry["CONTENT_SHA256"] = payload_sha
            bundle[did] = entry
        return {"EVIDENCE_BY_DRAW": bundle}

    # --- AC1: Git Source and Blob Byte-Exactness ---
    def test_ac1_git_sources_and_blob_identities(self) -> None:
        base_commit = subprocess.check_output(
            ["git", "rev-parse", f"{EXPECTED_BASE_VERIFIER_COMMIT}^{{commit}}"]
        ).decode().strip()
        base_tree = subprocess.check_output(
            ["git", "rev-parse", f"{EXPECTED_BASE_VERIFIER_COMMIT}^{{tree}}"]
        ).decode().strip()
        self.assertEqual(base_commit, EXPECTED_BASE_VERIFIER_COMMIT)
        self.assertEqual(base_tree, EXPECTED_BASE_VERIFIER_TREE)

        k235_commit = subprocess.check_output(
            ["git", "rev-parse", f"{EXPECTED_K235_SOURCE_COMMIT}^{{commit}}"]
        ).decode().strip()
        k235_tree = subprocess.check_output(
            ["git", "rev-parse", f"{EXPECTED_K235_SOURCE_COMMIT}^{{tree}}"]
        ).decode().strip()
        self.assertEqual(k235_commit, EXPECTED_K235_SOURCE_COMMIT)
        self.assertEqual(k235_tree, EXPECTED_K235_SOURCE_TREE)

        scorer_path = Path("tools/score_biglotto_portfolio_prospective_r1.py")
        self.assertTrue(scorer_path.is_file())
        scorer_sha = hashlib.sha256(scorer_path.read_bytes()).hexdigest()
        self.assertEqual(scorer_sha, EXPECTED_K235_SOURCE_SHA256)

        base_r2_source = subprocess.check_output(
            [
                "git",
                "show",
                f"{BASE_R2_SOURCE_IDENTITY['commit']}:{BASE_R2_SOURCE_IDENTITY['path']}",
            ]
        )
        base_r2_sha = hashlib.sha256(base_r2_source).hexdigest()
        _assert_source_sha256_identity(
            base_r2_sha,
            BASE_R2_SOURCE_IDENTITY["sha256"],
            "previous base R2 source",
        )

        fixed_head_r2_source = subprocess.check_output(
            [
                "git",
                "show",
                f"{FIXED_HEAD_R2_SOURCE_IDENTITY['commit']}:{FIXED_HEAD_R2_SOURCE_IDENTITY['path']}",
            ]
        )
        fixed_head_r2_sha = hashlib.sha256(fixed_head_r2_source).hexdigest()
        _assert_source_sha256_identity(
            fixed_head_r2_sha,
            FIXED_HEAD_R2_SOURCE_IDENTITY["sha256"],
            "fixed task HEAD R2 source",
        )

        candidate_r2_path = Path(CANDIDATE_R2_SOURCE_IDENTITY["path"])
        self.assertTrue(candidate_r2_path.is_file())
        candidate_r2_sha = hashlib.sha256(candidate_r2_path.read_bytes()).hexdigest()
        _assert_source_sha256_identity(
            candidate_r2_sha,
            CANDIDATE_R2_SOURCE_IDENTITY["sha256"],
            "working-tree Accuracy candidate R2 source",
        )

        wrong_sha256 = "0" * 64
        for identity_name, actual_sha256, expected_sha256 in (
            (
                "previous base R2 source",
                base_r2_sha,
                BASE_R2_SOURCE_IDENTITY["sha256"],
            ),
            (
                "fixed task HEAD R2 source",
                fixed_head_r2_sha,
                FIXED_HEAD_R2_SOURCE_IDENTITY["sha256"],
            ),
            (
                "working-tree Accuracy candidate R2 source",
                candidate_r2_sha,
                CANDIDATE_R2_SOURCE_IDENTITY["sha256"],
            ),
        ):
            with self.subTest(identity=identity_name, mismatch="wrong expected SHA"):
                with self.assertRaisesRegex(AssertionError, "SHA256 mismatch"):
                    _assert_source_sha256_identity(
                        actual_sha256,
                        wrong_sha256,
                        identity_name,
                    )
            with self.subTest(identity=identity_name, mismatch="wrong actual SHA"):
                with self.assertRaisesRegex(AssertionError, "SHA256 mismatch"):
                    _assert_source_sha256_identity(
                        wrong_sha256,
                        expected_sha256,
                        identity_name,
                    )

    # --- AC2: Valid Portfolios for m in {2, 3, 5} ---
    def test_ac2_valid_synthetic_portfolios_m2_m3_m5(self) -> None:
        for m in (2, 3, 5):
            contract = _make_contract_fixture(["199000001"], ticket_count=m)
            pred = _make_prediction_fixture(
                "199000001",
                ticket_count=m,
                contract_sha=contract["EXPERIMENT_CONTRACT_SHA256"],
            )
            out = _make_outcome_fixture("199000001")
            bundle = self._issue_evidence_bundle([pred], contract)

            result = verify_biglotto_portfolio_predraw_boundary(
                [pred],
                [out],
                contract,
                evidence_bundle=bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )

            self.assertEqual(result["TICKET_COUNT"], m)
            self.assertEqual(result["TARGET_COUNT"], 1)
            self.assertEqual(result["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
            self.assertFalse(result["PREDRAW_EVIDENCE_INDEPENDENTLY_VERIFIED"])
            self.assertTrue(result["CRYPTO_TOKEN_VALID"])
            self.assertEqual(result["CRYPTOGRAPHIC_VERIFIER_STATUS"], "PASS")

    # --- AC2: Fail-Closed Ticket and Structure Validations ---
    def test_ac2_fail_closed_ticket_validations(self) -> None:
        # 1. Invalid ticket count (e.g. 1, 4, 6 tickets)
        for invalid_count in (1, 4, 6):
            pred = _make_prediction_fixture("199000001", ticket_count=2)
            pred["PREDICTED_TICKETS"] = [[1, 2, 3, 4, 5, 6]] * invalid_count
            pred["TICKET_COUNT"] = invalid_count
            with self.assertRaises(ContractError) as ctx:
                build_canonical_portfolio_payload(pred)
            self.assertIn(
                ctx.exception.code,
                ("INVALID_TICKET_COUNT", "TICKET_COUNT_CHANGED"),
            )

        # 2. Number not an integer (float or string)
        pred = _make_prediction_fixture("199000001", ticket_count=2)
        pred["PREDICTED_TICKETS"][0][0] = 1.5
        with self.assertRaises(ContractError) as ctx:
            build_canonical_portfolio_payload(pred)
        self.assertIn(ctx.exception.code, ("INVALID_NUMBER_TYPE", "INVALID_NUMBERS"))

        # 3. Number out of range (< 1 or > 49)
        pred = _make_prediction_fixture("199000001", ticket_count=2)
        pred["PREDICTED_TICKETS"][0][0] = 0
        with self.assertRaises(ContractError) as ctx:
            build_canonical_portfolio_payload(pred)
        self.assertIn(ctx.exception.code, ("OUT_OF_RANGE_NUMBER", "INVALID_NUMBERS"))

        pred = _make_prediction_fixture("199000001", ticket_count=2)
        pred["PREDICTED_TICKETS"][0][0] = 50
        with self.assertRaises(ContractError) as ctx:
            build_canonical_portfolio_payload(pred)
        self.assertIn(ctx.exception.code, ("OUT_OF_RANGE_NUMBER", "INVALID_NUMBERS"))

        # 4. Duplicate numbers within a ticket
        pred = _make_prediction_fixture("199000001", ticket_count=2)
        pred["PREDICTED_TICKETS"][0] = [1, 1, 2, 3, 4, 5]
        with self.assertRaises(ContractError) as ctx:
            build_canonical_portfolio_payload(pred)
        self.assertEqual(ctx.exception.code, "DUPLICATE_NUMBERS")

        # 5. Missing required field
        pred = _make_prediction_fixture("199000001", ticket_count=2)
        del pred["EXPERIMENT_CONTRACT_SHA256"]
        with self.assertRaises(ContractError) as ctx:
            build_canonical_portfolio_payload(pred)
        self.assertEqual(ctx.exception.code, "MISSING_FIELD")

    # --- AC3: Sensitivity of Canonical Portfolio Imprint to All Fields ---
    def test_ac3_full_portfolio_imprint_gate(self) -> None:
        self.assertEqual(
            set(PORTFOLIO_PAYLOAD_FIELDS),
            {
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
            },
        )
        base_pred = _make_prediction_fixture("199000001", ticket_count=3)
        base_payload = build_canonical_portfolio_payload(base_pred)
        base_sha = compute_canonical_portfolio_payload_sha256(base_payload)

        # Mutate ticket 0, middle ticket 1, last ticket 2
        for t_idx in (0, 1, 2):
            mutated = copy.deepcopy(base_pred)
            mutated["PREDICTED_TICKETS"][t_idx][0] = 35
            payload = build_canonical_portfolio_payload(mutated)
            sha = compute_canonical_portfolio_payload_sha256(payload)
            self.assertNotEqual(
                base_sha,
                sha,
                f"Mutating ticket {t_idx} must alter canonical hash",
            )

        # Swap ticket order (preserves tickets, changes outer order)
        mutated_order = copy.deepcopy(base_pred)
        mutated_order["PREDICTED_TICKETS"][0], mutated_order["PREDICTED_TICKETS"][1] = (
            mutated_order["PREDICTED_TICKETS"][1],
            mutated_order["PREDICTED_TICKETS"][0],
        )
        payload_order = build_canonical_portfolio_payload(mutated_order)
        sha_order = compute_canonical_portfolio_payload_sha256(payload_order)
        self.assertNotEqual(
            base_sha,
            sha_order,
            "Swapping ticket order must alter canonical hash",
        )

        # Contract hash mutation
        mutated_contract = copy.deepcopy(base_pred)
        mutated_contract["EXPERIMENT_CONTRACT_SHA256"] = "f" * 64
        payload_c = build_canonical_portfolio_payload(mutated_contract)
        sha_c = compute_canonical_portfolio_payload_sha256(payload_c)
        self.assertNotEqual(
            base_sha,
            sha_c,
            "Mutating contract hash must alter canonical hash",
        )

    # --- AC3: Fail-Closed Matrix for All 12 Mandatory Mutations ---
    def test_ac3_fail_closed_matrix(self) -> None:
        contract = _make_contract_fixture(["199000001"], ticket_count=5)
        base_pred = _make_prediction_fixture(
            "199000001",
            ticket_count=5,
            contract_sha=contract["EXPERIMENT_CONTRACT_SHA256"],
        )
        base_out = _make_outcome_fixture("199000001")
        # Issue bundle without redundant CONTENT_SHA256 so token imprint is exercised directly
        valid_bundle = self._issue_evidence_bundle(
            [base_pred],
            contract,
            include_content_sha=False,
        )

        # Baseline verification passes
        res = verify_biglotto_portfolio_predraw_boundary(
            [base_pred],
            [base_out],
            contract,
            evidence_bundle=valid_bundle,
            pinned_tsa_cert_pem_path=self.ca_pem_path,
            pinned_tsa_cert_sha256=self.ca_sha256,
        )
        self.assertEqual(res["CRYPTOGRAPHIC_VERIFIER_STATUS"], "PASS")

        # Mutation 1: FIRST_TICKET_MUTATED
        p1 = copy.deepcopy(base_pred)
        p1["PREDICTED_TICKETS"][0] = [31, 32, 33, 34, 35, 36]
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [p1],
                [base_out],
                contract,
                evidence_bundle=valid_bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(ctx.exception.code, "TOKEN_IMPRINT_MISMATCH")

        # Mutation 2: MIDDLE_TICKET_MUTATED (ticket index 2 in 5-ticket set)
        p2 = copy.deepcopy(base_pred)
        p2["PREDICTED_TICKETS"][2] = [31, 32, 33, 34, 35, 36]
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [p2],
                [base_out],
                contract,
                evidence_bundle=valid_bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(ctx.exception.code, "TOKEN_IMPRINT_MISMATCH")

        # Mutation 3: LAST_TICKET_MUTATED (ticket index 4 in 5-ticket set)
        p3 = copy.deepcopy(base_pred)
        p3["PREDICTED_TICKETS"][4] = [31, 32, 33, 34, 35, 36]
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [p3],
                [base_out],
                contract,
                evidence_bundle=valid_bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(ctx.exception.code, "TOKEN_IMPRINT_MISMATCH")

        # Mutation 4: TICKET_COUNT_CHANGED (reduced to 3 tickets)
        p4 = copy.deepcopy(base_pred)
        p4["PREDICTED_TICKETS"] = p4["PREDICTED_TICKETS"][:3]
        p4["TICKET_COUNT"] = 3
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [p4],
                [base_out],
                contract,
                evidence_bundle=valid_bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertIn(
            ctx.exception.code,
            ("TICKET_COUNT_CHANGED", "INVALID_TICKET_COUNT", "TOKEN_IMPRINT_MISMATCH"),
        )

        # Mutation 5: TICKET_ORDER_CHANGED
        p5 = copy.deepcopy(base_pred)
        p5["PREDICTED_TICKETS"][0], p5["PREDICTED_TICKETS"][1] = (
            p5["PREDICTED_TICKETS"][1],
            p5["PREDICTED_TICKETS"][0],
        )
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [p5],
                [base_out],
                contract,
                evidence_bundle=valid_bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(ctx.exception.code, "TOKEN_IMPRINT_MISMATCH")

        # Mutation 6: DRAW_ID_CHANGED
        p6 = copy.deepcopy(base_pred)
        p6["DRAW_ID"] = "199000002"
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [p6],
                [base_out],
                contract,
                evidence_bundle=valid_bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(ctx.exception.code, "DRAW_SET_MISMATCH")

        # Mutation 7: STRATEGY_IDENTITY_CHANGED
        p7 = copy.deepcopy(base_pred)
        p7["STRATEGY_IDENTITY"] = "mutated-strategy@version:2"
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [p7],
                [base_out],
                contract,
                evidence_bundle=valid_bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(ctx.exception.code, "STRATEGY_IDENTITY_MISMATCH")

        # Mutation 8: EXPERIMENT_CONTRACT_HASH_CHANGED
        p8 = copy.deepcopy(base_pred)
        p8["EXPERIMENT_CONTRACT_SHA256"] = "0" * 64
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [p8],
                [base_out],
                contract,
                evidence_bundle=valid_bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(ctx.exception.code, "EXPERIMENT_CONTRACT_HASH_CHANGED")

        # Mutation 9: SNAPSHOT_HASH_CHANGED
        snap_files = {"a" * 64: b'{"draws": []}'}
        p9 = copy.deepcopy(base_pred)
        p9["INPUT_SNAPSHOT_SHA256"] = "c" * 64
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [p9],
                [base_out],
                contract,
                evidence_bundle=valid_bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
                snapshot_files_by_sha256=snap_files,
            )
        self.assertEqual(ctx.exception.code, "SNAPSHOT_HASH_CHANGED")

        # Mutation 10: TOKEN_IMPRINT_MISMATCH
        bundle10 = copy.deepcopy(valid_bundle)
        unrelated_token = self.tsa.issue_token("9" * 64)
        bundle10["EVIDENCE_BY_DRAW"]["199000001"]["TOKEN_BYTES"] = unrelated_token
        bundle10["EVIDENCE_BY_DRAW"]["199000001"]["TOKEN_SHA256"] = hashlib.sha256(
            unrelated_token
        ).hexdigest()
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [base_pred],
                [base_out],
                contract,
                evidence_bundle=bundle10,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(ctx.exception.code, "TOKEN_IMPRINT_MISMATCH")

        # Mutation 11: INVALID_CMS_SIGNATURE
        bundle11 = copy.deepcopy(valid_bundle)
        corrupted_token = bytearray(
            valid_bundle["EVIDENCE_BY_DRAW"]["199000001"]["TOKEN_BYTES"]
        )
        corrupted_token[-10:] = b"BADSIG1234"
        bundle11["EVIDENCE_BY_DRAW"]["199000001"]["TOKEN_BYTES"] = bytes(corrupted_token)
        bundle11["EVIDENCE_BY_DRAW"]["199000001"]["TOKEN_SHA256"] = hashlib.sha256(
            bytes(corrupted_token)
        ).hexdigest()
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [base_pred],
                [base_out],
                contract,
                evidence_bundle=bundle11,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(ctx.exception.code, "INVALID_CMS_SIGNATURE")

        # Mutation 12: UNTRUSTED_TSA_CERTIFICATE
        other_tsa = _SyntheticTsaHarness(self.tmp / "other_tsa")
        other_bundle = self._issue_evidence_bundle(
            [base_pred],
            contract,
            tsa_harness=other_tsa,
        )
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [base_pred],
                [base_out],
                contract,
                evidence_bundle=other_bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(ctx.exception.code, "UNTRUSTED_TSA_CERTIFICATE")

    # --- AC4: Multivariate Baseline Exact Weights & Multi-draw Aggregation ---
    def test_ac4_multivariate_baseline_weights_and_multidraw_aggregation(self) -> None:
        self.assertEqual(OUTCOME_DENOMINATOR, 13983816)

        # 5 disjoint tickets weights
        t_disjoint = _synthetic_tickets(5, "disjoint")
        base_disjoint = portfolio_exact_baseline(t_disjoint)
        expected_disjoint_weights = [27132, 5093064, 7564500, 1230100, 67725, 1290, 5]
        self.assertEqual(base_disjoint["MAX_HIT_WEIGHTS"], expected_disjoint_weights)
        self.assertEqual(sum(expected_disjoint_weights), 13983816)

        # 5 tickets sharing 3-number core weights
        t_core3 = _synthetic_tickets(5, "shared_core_3")
        base_core3 = portfolio_exact_baseline(t_core3)
        expected_core3_weights = [736281, 7299756, 4917834, 964705, 63945, 1290, 5]
        self.assertEqual(base_core3["MAX_HIT_WEIGHTS"], expected_core3_weights)
        self.assertEqual(sum(expected_core3_weights), 13983816)

        # Dynamic per-draw baselines aggregated across multi-draw batch
        draw_ids = ["199000001", "199000002"]
        contract = _make_contract_fixture(draw_ids, ticket_count=5)
        p1 = _make_prediction_fixture(
            "199000001",
            ticket_count=5,
            tickets=t_disjoint,
            contract_sha=contract["EXPERIMENT_CONTRACT_SHA256"],
        )
        p2 = _make_prediction_fixture(
            "199000002",
            ticket_count=5,
            tickets=t_core3,
            contract_sha=contract["EXPERIMENT_CONTRACT_SHA256"],
        )
        o1 = _make_outcome_fixture("199000001")
        o2 = _make_outcome_fixture("199000002")
        bundle = self._issue_evidence_bundle([p1, p2], contract)

        res = verify_biglotto_portfolio_predraw_boundary(
            [p1, p2],
            [o1, o2],
            contract,
            evidence_bundle=bundle,
            pinned_tsa_cert_pem_path=self.ca_pem_path,
            pinned_tsa_cert_sha256=self.ca_sha256,
        )

        self.assertEqual(res["TARGET_COUNT"], 2)
        self.assertEqual(res["TICKET_COUNT"], 5)
        self.assertEqual(len(res["PER_DRAW"]), 2)
        self.assertEqual(
            res["PER_DRAW"][0]["DRAW_EXACT_BASELINE"]["MAX_HIT_WEIGHTS"],
            expected_disjoint_weights,
        )
        self.assertEqual(
            res["PER_DRAW"][1]["DRAW_EXACT_BASELINE"]["MAX_HIT_WEIGHTS"],
            expected_core3_weights,
        )

        # Aggregated baseline in PORTFOLIO_BASELINE (sum of probabilities across all draws)
        baseline = res["PORTFOLIO_BASELINE"]
        self.assertEqual(baseline["TARGET_COUNT"], 2)
        self.assertEqual(baseline["TICKET_COUNT"], 5)
        for k in range(7):
            expected_sum_prob = (
                expected_disjoint_weights[k] + expected_core3_weights[k]
            ) / 13983816
            self.assertAlmostEqual(
                baseline["EXPECTED_MAX_HIT_HISTOGRAM_0_TO_6"][k],
                expected_sum_prob,
                places=7,
            )

    # --- AC5: Temporal Boundaries and Diagnostic-Only Gates ---
    def test_ac5_temporal_boundaries_and_diagnostic_only(self) -> None:
        contract = _make_contract_fixture(["199000001"], ticket_count=2)
        pred = _make_prediction_fixture(
            "199000001",
            ticket_count=2,
            contract_sha=contract["EXPERIMENT_CONTRACT_SHA256"],
        )
        out = _make_outcome_fixture("199000001")
        bundle = self._issue_evidence_bundle([pred], contract)

        # 1. genTime not after INPUT_CUTOFF: set INPUT_CUTOFF to future
        p_late_cutoff = copy.deepcopy(pred)
        p_late_cutoff["INPUT_CUTOFF"] = "2099-01-01T00:00:00+00:00"
        bundle_late = self._issue_evidence_bundle([p_late_cutoff], contract)
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [p_late_cutoff],
                [out],
                contract,
                evidence_bundle=bundle_late,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(ctx.exception.code, "TIMESTAMP_NOT_AFTER_INPUT_CUTOFF")

        # 2. genTime at or after DRAW_CUTOFF: set DRAW_TIME to past
        out_early_draw = copy.deepcopy(out)
        out_early_draw["DRAW_TIME"] = "1999-01-01T00:00:00+00:00"
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [pred],
                [out_early_draw],
                contract,
                evidence_bundle=bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(ctx.exception.code, "TIMESTAMP_AFTER_CUTOFF")

        # 3. require_independent_verification=True fails closed without trusted external anchor
        snap_bytes = b'{"draws": []}'
        snap_hash = hashlib.sha256(snap_bytes).hexdigest()
        snap_files = {snap_hash: snap_bytes}
        pred_valid_snap = _make_prediction_fixture(
            "199000001",
            ticket_count=2,
            contract_sha=contract["EXPERIMENT_CONTRACT_SHA256"],
            snapshot_hash=snap_hash,
        )
        bundle_valid_snap = self._issue_evidence_bundle([pred_valid_snap], contract)

        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [pred_valid_snap],
                [out],
                contract,
                evidence_bundle=bundle_valid_snap,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
                snapshot_files_by_sha256=snap_files,
                require_independent_verification=True,
            )
        self.assertEqual(ctx.exception.code, "TRUSTED_DRAW_CUTOFF_REQUIRED")

        # 4. Without evidence bundle, evidence status is DIAGNOSTIC_ONLY
        res_no_bundle = verify_biglotto_portfolio_predraw_boundary(
            [pred], [out], contract, evidence_bundle=None
        )
        self.assertEqual(res_no_bundle["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
        self.assertFalse(res_no_bundle["PREDRAW_EVIDENCE_INDEPENDENTLY_VERIFIED"])
        self.assertFalse(res_no_bundle["CRYPTO_TOKEN_VALID"])

    # --- AC6: Experiment Contract Integrity ---
    def test_ac6_experiment_contract_integrity(self) -> None:
        contract = _make_contract_fixture(["199000001", "199000002"], ticket_count=2)
        p1 = _make_prediction_fixture(
            "199000001",
            ticket_count=2,
            contract_sha=contract["EXPERIMENT_CONTRACT_SHA256"],
        )
        o1 = _make_outcome_fixture("199000001")
        o2 = _make_outcome_fixture("199000002")

        # Missing draw in predictions
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary([p1], [o1, o2], contract)
        self.assertEqual(ctx.exception.code, "DRAW_SET_MISMATCH")

        # Forbidden claims in contract
        c_bad = copy.deepcopy(contract)
        c_bad["EVIDENCE_STATUS"] = "VERIFIED"
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary([p1], [o1], c_bad)
        self.assertEqual(ctx.exception.code, "FALSE_VERIFIED_STATUS")

        # Missing evidence for one draw in bundle
        p2 = _make_prediction_fixture(
            "199000002",
            ticket_count=2,
            contract_sha=contract["EXPERIMENT_CONTRACT_SHA256"],
        )
        partial_bundle = self._issue_evidence_bundle([p1], contract)
        with self.assertRaises(ContractError) as ctx:
            verify_biglotto_portfolio_predraw_boundary(
                [p1, p2],
                [o1, o2],
                contract,
                evidence_bundle=partial_bundle,
                pinned_tsa_cert_pem_path=self.ca_pem_path,
                pinned_tsa_cert_sha256=self.ca_sha256,
            )
        self.assertEqual(ctx.exception.code, "MISSING_EVIDENCE_FOR_DRAW")

    # --- AC7: Python 3.9 Compatibility ---
    def test_ac7_python39_compatibility(self) -> None:
        tool_src = Path("tools/verify_biglotto_portfolio_predraw_r1.py").read_text(
            encoding="utf-8"
        )
        test_src = Path("tests/unit/test_verify_biglotto_portfolio_predraw_r1.py").read_text(
            encoding="utf-8"
        )
        ast.parse(tool_src, feature_version=(3, 9))
        ast.parse(test_src, feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
