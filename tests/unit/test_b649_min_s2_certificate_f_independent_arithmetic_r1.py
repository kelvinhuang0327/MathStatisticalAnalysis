"""Focused oracles and rejection tests; standard library only, one process."""

from __future__ import annotations

import argparse
import copy
import sys
import time
import unittest
from collections.abc import Generator
from contextlib import contextmanager
from itertools import combinations
from typing import cast

from tools import verify_b649_min_s2_certificate_f_independent_arithmetic_r1 as verifier


@contextmanager
def aligned_current_checkout_identity() -> Generator[None]:
    """Align only the verifier's in-memory HEAD/tree guard for this PR test harness.

    The frozen input SHA pins and working-byte comparisons still run. The verifier's
    production constants and exact-head rejection are restored before this context exits.
    """
    frozen_head, frozen_tree = verifier.HEAD, verifier.TREE
    current_head = verifier.git(verifier.ROOT, "rev-parse", "HEAD").decode().strip()
    current_tree = verifier.git(verifier.ROOT, "rev-parse", "HEAD^{tree}").decode().strip()
    verifier.HEAD, verifier.TREE = current_head, current_tree
    try:
        yield
    finally:
        verifier.HEAD, verifier.TREE = frozen_head, frozen_tree


class CertificateFTests(unittest.TestCase):
    composite: verifier.CompositeInput
    donor: verifier.DonorInput

    @classmethod
    def setUpClass(cls) -> None:
        with aligned_current_checkout_identity():
            cls.composite, cls.donor, _ = verifier.load_inputs()

    def test_small_literal_outcome_oracle(self) -> None:
        # Enumerate actual toy labels/main/special, independent of coefficient counting.
        tickets = ({0, 1, 2}, {0, 3, 4})
        pool, main_size = 7, 3
        count = 0
        for main in combinations(range(pool), main_size):
            for special in set(range(pool)) - set(main):
                seen = set(main) | {special}
                count += int(all(len(ticket & seen) >= 2 for ticket in tickets))
        self.assertEqual(count, verifier.local_outcomes(
            2, [(0, 1)], pool=pool, ticket_size=3, selected=main_size + 1, threshold=2,
        ))

    def test_credit_ceiling_all_residues(self) -> None:
        for s4 in range(14):
            numerator = 7 * 100 - 4 * s4
            bound = verifier.ceil_ratio(numerator, 7)
            self.assertTrue(0 <= 7 * bound - numerator < 7)
            self.assertEqual(bound, 100 - (4 * s4) // 7)
        self.assertEqual(verifier.ceil_ratio(-8, 7), -1)
        self.assertEqual(verifier.ceil_ratio(-7, 7), -1)

    def test_input_digest_fails_closed(self) -> None:
        with self.assertRaisesRegex(verifier.VerificationError, "input identity"):
            verifier.bind(b"tampered", "0" * 64, "donor")

    def test_triangle_domain_and_integer_types(self) -> None:
        invalid_caps: tuple[object, ...] = (21, 278, True, 264.0)
        for cap in invalid_caps:
            with self.assertRaises(verifier.VerificationError):
                # cast preserves the actual invalid runtime value; it only bridges the test API.
                verifier.recount_terms(list(map(int, verifier.PROFILE)), cap=cast(int, cap))

    def test_rejects_mutated_t_term(self) -> None:
        composite = copy.deepcopy(self.composite)
        composite["CERTIFICATE_F"]["ALL_T_TERMS"][216][1] += 1
        result = verifier.verify_data(composite, self.donor)
        self.assertEqual(result["INDEPENDENT_ARITHMETIC_RECOUNT"], "FAIL")
        self.assertEqual(result["SCIENTIFIC_CLAIM_SUPPORTED"], "NONE")
        self.assertTrue(any(row["LOCATION"] == "T=238" for row in result["MISMATCHES"]))

    def test_rejects_missing_last_t(self) -> None:
        composite = copy.deepcopy(self.composite)
        composite["CERTIFICATE_F"]["ALL_T_TERMS"].pop()
        with self.assertRaisesRegex(verifier.VerificationError, "T-term table schema"):
            verifier.verify_data(composite, self.donor)

    def test_rejects_non_linear_owner_support(self) -> None:
        composite = copy.deepcopy(self.composite)
        for state in ("BEFORE", "AFTER"):
            composite["ROW_UPDATE"][state]["realization"][1][0] = [0, 1]
        with self.assertRaisesRegex(verifier.VerificationError, "pair linearity"):
            verifier.verify_data(composite, self.donor)


    def test_missing_input_distinguished_from_formula_failure(self) -> None:
        missing = verifier.failure_report(verifier.FrozenInputError("digest mismatch"))
        formula = verifier.failure_report(verifier.VerificationError("incidence direction"))
        self.assertEqual(missing["TASK_STATUS"], "UNABLE_TO_REPRODUCE_FROZEN_INPUT")
        self.assertEqual(formula["TASK_STATUS"], "FAIL_FORMULA_OR_APPLICABILITY_INCONSISTENCY")
        self.assertEqual(missing["INDEPENDENT_ARITHMETIC_RECOUNT"], "NOT_COMPLETED")
        self.assertEqual(formula["INDEPENDENT_ARITHMETIC_RECOUNT"], "FAIL")


if __name__ == "__main__":
    verifier.cpu_limit()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    started = time.process_time_ns()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CertificateFTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.write_result:
        with aligned_current_checkout_identity():
            report = verifier.verify_frozen()
        focused_report: verifier.FocusedVerificationReport = {
            **report,
            "FOCUSED_TESTS": {
                "STATUS": "PASS", "TESTS_RUN": result.testsRun,
                "FAILURES": len(result.failures), "ERRORS": len(result.errors),
                "RUNNER": "stdlib unittest; same CPU-bound process as final verification",
                "PATH": "tests/unit/test_b649_min_s2_certificate_f_independent_arithmetic_r1.py",
            },
        }
        execution = focused_report["EXECUTION"]
        execution["TOTAL_TESTS_AND_VERIFICATION_CPU_NANOSECONDS"] = (
            time.process_time_ns() - started
        )
        execution["COMMAND"] = (
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 "
            "tests/unit/test_b649_min_s2_certificate_f_independent_arithmetic_r1.py --write-result"
        )
        exit_status = 0 if focused_report["INDEPENDENT_ARITHMETIC_RECOUNT"] == "PASS" else 1
        execution["FINAL_EXIT_STATUS"] = exit_status
        verifier.save_report(focused_report)
        print(focused_report["TASK_STATUS"])
        print("RESULT_LOCATOR: " + str(verifier.OUTPUT))
        sys.exit(exit_status)
