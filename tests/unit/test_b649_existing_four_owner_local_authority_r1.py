from __future__ import annotations

import unittest
from dataclasses import replace
from typing import Any

from lottolab.research import b649_existing_four_owner_local_authority_r1 as authority


class OwnerCertificateGuardTests(unittest.TestCase):
    def test_wrong_t_cap_rejected(self) -> None:
        certificate = {
            "PROFILE_ID": "66555555555531000000",
            "T_CAP": 240,
            "OWNER_BOUND": 313_183_160,
            "PROOF_SCOPE": "FULL_PROFILE",
            "APPLICABILITY": "FULL_PROFILE",
            "ROW_SOURCE": "controlled-test-source",
        }
        with self.assertRaisesRegex(ValueError, "T cap mismatch"):
            authority.verify_certificate(
                certificate,
                profile_id="66555555555531000000",
                cap=241,
                bound=313_183_160,
                source="controlled-test-source",
            )


class ExistingFourOwnerLocalAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result, cls.before, cls.after, cls.certificates = authority.build_candidate()

    def test_complete_prospective_frontier(self) -> None:
        self.assertEqual(self.result["TASK_STATUS"], "PROSPECTIVE_LOCAL_INTEGRATION_COMPLETE")
        self.assertEqual(self.result["LEDGER_ROWS_BEFORE"], 4_647)
        self.assertEqual(self.result["LEDGER_ROWS_AFTER"], 4_647)
        self.assertEqual(self.result["CERTIFICATES_BEFORE"], 7)
        self.assertEqual(self.result["CERTIFICATES_PROSPECTIVE_AFTER"], 11)
        self.assertEqual(self.result["FAMILY_AFTER"]["FAMILY_BOUND"], 313_398_144)
        self.assertEqual(
            self.result["FAMILY_AFTER"]["TIED_OWNERS"],
            ["66665555555331000000", "66665555555411100000"],
        )
        self.assertEqual(self.result["FAMILY_AFTER"]["NEXT_COMPETING_BOUND"], 313_397_860)
        self.assertEqual(
            self.result["FAMILY_AFTER"]["NEXT_COMPETING_OWNERS"],
            ["66665555554421100000"],
        )
        self.assertEqual(self.result["ABOVE_INCUMBENT_PROFILE_COUNT_REMAINS"], 1_375)
        self.assertEqual(self.result["GLOBAL_K20_OPTIMUM"], "UNKNOWN")
        self.assertEqual(self.result["FORMAL_JUDGE_STATUS"], "NOT_UPGRADED")

    def test_frozen_ledger_remains_unchanged(self) -> None:
        full_before = authority.seven.two.full_digest(self.before)
        bounds_before = authority.seven.two.bounds_digest(self.before)
        authority.apply_four_updates(self.before, self.certificates)
        self.assertEqual(authority.seven.two.full_digest(self.before), full_before)
        self.assertEqual(authority.seven.two.bounds_digest(self.before), bounds_before)
        self.assertEqual(full_before, authority.SEVEN_ROW_FULL_DIGEST)
        self.assertEqual(bounds_before, authority.SEVEN_ROW_BOUNDS_DIGEST)

    def test_source_identity_tamper_rejected(self) -> None:
        expected = {"HEAD": authority.EIGHT_HEAD, "TREE": authority.EIGHT_TREE}
        tampered = dict(expected)
        tampered["TREE"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "source identity mismatch"):
            authority.verify_identity(tampered, expected)

    def test_profile_mismatch_rejected(self) -> None:
        certificate = dict(self.certificates[0])
        with self.assertRaisesRegex(ValueError, "profile mismatch"):
            authority.verify_certificate(
                certificate,
                profile_id="00000000000000000000",
                cap=authority.EIGHT_CAP,
                bound=authority.EIGHT_BOUND,
                source=certificate["ROW_SOURCE"],
            )

    def test_wrong_bound_rejected(self) -> None:
        certificate = dict(self.certificates[2])
        certificate["OWNER_BOUND"] = 313_174_393
        with self.assertRaisesRegex(ValueError, "owner bound mismatch"):
            authority.verify_certificate(
                certificate,
                profile_id="66655555554441000000",
                cap=240,
                bound=313_174_392,
                source=certificate["ROW_SOURCE"],
            )

    def test_duplicate_update_rejected(self) -> None:
        duplicated = [*self.certificates]
        duplicated[-1] = self.certificates[0]
        with self.assertRaisesRegex(ValueError, "duplicate owner update"):
            authority.apply_four_updates(self.before, duplicated)

    def test_non_target_row_mutation_rejected(self) -> None:
        mutated = dict(self.after)
        non_target = next(pid for pid in mutated if pid not in authority.TARGET_PROFILE_IDS)
        mutated[non_target] = replace(mutated[non_target], source="tampered-source")
        with self.assertRaisesRegex(ValueError, "non-target row"):
            authority.verify_ledger_overlay(self.before, mutated, self.certificates)

    def test_missing_proof_artifact_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "C235 proof artifact SHA256 mismatch"):
            authority.require_hash(b"", authority.C235_PROOF_SHA256, "C235 proof artifact")

    def test_incorrect_family_maximum_rejected(self) -> None:
        expected = authority.family_frontier(self.after)
        incorrect: dict[str, Any] = dict(expected)
        incorrect["FAMILY_BOUND"] += 1
        with self.assertRaisesRegex(ValueError, "family maximum or owner summary mismatch"):
            authority.verify_family_summary(incorrect, expected)

    def test_c235_seven_case_proof_and_remainder(self) -> None:
        table = authority.c235_case_table()
        self.assertEqual(table["CASE_COUNT"], 7)
        self.assertEqual(table["MAX_T"], 235)
        self.assertEqual(table["CASES"][1]["FORCED_P_MIN_FOR_TOP_CASE"], 2)
        self.assertEqual(table["CASES"][1]["T_BOUND_AFTER_P"], 235)
        self.assertEqual(self.result["C235_PROOF"]["ROUTE_B"]["TERM_COUNT"], 214)
        self.assertEqual(self.result["C235_PROOF"]["ROUTE_B"]["BOUND"], 313_129_388)


if __name__ == "__main__":
    unittest.main()
