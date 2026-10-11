"""Focused oracles and rejection tests; standard library only, one process."""

from __future__ import annotations

import argparse
import copy
import sys
import time
import unittest
from itertools import combinations

from tools import verify_b649_min_s2_certificate_f_independent_arithmetic_r1 as verifier


class CertificateFTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.composite, cls.donor, _ = verifier.load_inputs()

    def test_small_literal_outcome_oracle(self):
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

    def test_credit_ceiling_all_residues(self):
        for s4 in range(14):
            numerator = 7 * 100 - 4 * s4
            bound = verifier.ceil_ratio(numerator, 7)
            self.assertTrue(0 <= 7 * bound - numerator < 7)
            self.assertEqual(bound, 100 - (4 * s4) // 7)
        self.assertEqual(verifier.ceil_ratio(-8, 7), -1)
        self.assertEqual(verifier.ceil_ratio(-7, 7), -1)

    def test_input_digest_fails_closed(self):
        with self.assertRaisesRegex(verifier.VerificationError, "input identity"):
            verifier.bind(b"tampered", "0" * 64, "donor")

    def test_triangle_domain_and_integer_types(self):
        for cap in (21, 278, True, 264.0):
            with self.assertRaises(verifier.VerificationError):
                verifier.recount_terms(list(map(int, verifier.PROFILE)), cap=cap)

    def test_rejects_mutated_t_term(self):
        composite = copy.deepcopy(self.composite)
        composite["CERTIFICATE_F"]["ALL_T_TERMS"][216][1] += 1
        result = verifier.verify_data(composite, self.donor)
        self.assertEqual(result["INDEPENDENT_ARITHMETIC_RECOUNT"], "FAIL")
        self.assertEqual(result["SCIENTIFIC_CLAIM_SUPPORTED"], "NONE")
        self.assertTrue(any(row["LOCATION"] == "T=238" for row in result["MISMATCHES"]))

    def test_rejects_missing_last_t(self):
        composite = copy.deepcopy(self.composite)
        composite["CERTIFICATE_F"]["ALL_T_TERMS"].pop()
        with self.assertRaisesRegex(verifier.VerificationError, "T-term table schema"):
            verifier.verify_data(composite, self.donor)

    def test_rejects_non_linear_owner_support(self):
        composite = copy.deepcopy(self.composite)
        for state in ("BEFORE", "AFTER"):
            composite["ROW_UPDATE"][state]["realization"][1][0] = [0, 1]
        with self.assertRaisesRegex(verifier.VerificationError, "pair linearity"):
            verifier.verify_data(composite, self.donor)


    def test_missing_input_distinguished_from_formula_failure(self):
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
        report = verifier.verify_frozen()
        report["FOCUSED_TESTS"] = {
            "STATUS": "PASS", "TESTS_RUN": result.testsRun,
            "FAILURES": len(result.failures), "ERRORS": len(result.errors),
            "RUNNER": "stdlib unittest; same CPU-bound process as final verification",
            "PATH": "tests/unit/test_b649_min_s2_certificate_f_independent_arithmetic_r1.py",
        }
        report["EXECUTION"]["TOTAL_TESTS_AND_VERIFICATION_CPU_NANOSECONDS"] = (
            time.process_time_ns() - started
        )
        report["EXECUTION"]["COMMAND"] = (
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 "
            "tests/unit/test_b649_min_s2_certificate_f_independent_arithmetic_r1.py --write-result"
        )
        report["EXECUTION"]["FINAL_EXIT_STATUS"] = (
            0 if report["INDEPENDENT_ARITHMETIC_RECOUNT"] == "PASS" else 1
        )
        verifier.save_report(report)
        print(report["TASK_STATUS"])
        print("RESULT_LOCATOR: " + str(verifier.OUTPUT))
        sys.exit(report["EXECUTION"]["FINAL_EXIT_STATUS"])
