from __future__ import annotations

import unittest
from dataclasses import replace
from typing import Any

from lottolab.research import b649_nine_event_eight_profile_local_authority_r1 as authority


class DonorCertificateGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.certificate = {
            "PROFILE_ID": "66665555555331000000",
            "T_CAP": 261,
            "OWNER_BOUND": 313_371_452,
            "PROOF_SCOPE": "FULL_PROFILE",
            "ROW_SOURCE": "git:head@tree:proof.json#PROOF:sha256=abc",
            "PROOF_SHA256": "abc",
        }

    def verify(self, certificate: dict[str, Any] | None = None) -> None:
        authority.verify_certificate(
            certificate or self.certificate,
            profile_id="66665555555331000000",
            cap=261,
            bound=313_371_452,
            source="git:head@tree:proof.json#PROOF:sha256=abc",
        )

    def test_wrong_source_rejected(self) -> None:
        altered = dict(self.certificate, ROW_SOURCE="git:other@tree:proof.json#PROOF:sha256=abc")
        with self.assertRaisesRegex(ValueError, "source identity mismatch"):
            self.verify(altered)

    def test_wrong_profile_rejected(self) -> None:
        altered = dict(self.certificate, PROFILE_ID="00000000000000000000")
        with self.assertRaisesRegex(ValueError, "profile mismatch"):
            self.verify(altered)

    def test_wrong_cap_rejected(self) -> None:
        altered = dict(self.certificate, T_CAP=262)
        with self.assertRaisesRegex(ValueError, "T cap mismatch"):
            self.verify(altered)

    def test_wrong_bound_rejected(self) -> None:
        altered = dict(self.certificate, OWNER_BOUND=313_371_453)
        with self.assertRaisesRegex(ValueError, "owner bound mismatch"):
            self.verify(altered)

    def test_missing_proof_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "donor proof is missing"):
            authority.proof_sha256(None)


class NineEventLocalAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result, cls.frozen, cls.after = authority.build_candidate()

    def test_nine_events_eight_profiles_and_expected_frontier(self) -> None:
        result = self.result
        self.assertEqual(result["UPDATE_EVENTS"], 9)
        self.assertEqual(result["DISTINCT_CHANGED_PROFILES"], 8)
        self.assertEqual(result["LEDGER_OVERLAY"]["ROWS_BEFORE"], 4_647)
        self.assertEqual(result["LEDGER_OVERLAY"]["ROWS_AFTER"], 4_647)
        self.assertEqual(result["LEDGER_OVERLAY"]["UNCHANGED_ROWS"], 4_639)
        self.assertEqual(result["NEW_FULL_DIGEST"], authority.EXPECTED_NEW_FULL_DIGEST)
        self.assertEqual(result["NEW_BOUNDS_DIGEST"], authority.EXPECTED_NEW_BOUNDS_DIGEST)
        self.assertEqual(result["FAMILY_AFTER"]["FAMILY_BOUND"], 313_395_448)
        self.assertEqual(
            result["FAMILY_AFTER"]["TIED_OWNERS"],
            ["66555555555441000000", "66555555555522000000"],
        )
        self.assertEqual(result["FAMILY_AFTER"]["NEXT_COMPETING_BOUND"], 313_395_344)
        self.assertEqual(
            result["FAMILY_AFTER"]["NEXT_COMPETING_OWNERS"],
            ["66655555555511100000", "66665555554431000000"],
        )
        self.assertEqual(result["RESOLVED_PROFILES_ABOVE_INCUMBENT"], 1_375)
        self.assertEqual(result["GLOBAL_K20_OPTIMUM"], "UNKNOWN")
        self.assertEqual(result["FORMAL_AUTHORITY_ACCEPTANCE"], "NOT_CLAIMED")

    def test_t258_is_a_separate_event_on_an_already_changed_profile(self) -> None:
        same_profile = [
            event
            for event in self.result["EVENT_HISTORY"]
            if event["PROFILE_ID"] == "66655555555521000000"
        ]
        self.assertEqual(len(same_profile), 2)
        self.assertNotEqual(same_profile[0]["EVENT_ID"], same_profile[1]["EVENT_ID"])
        self.assertEqual(self.result["DISTINCT_CHANGED_PROFILES"], 8)
        self.assertEqual(
            (same_profile[0]["BOUND_AFTER"], same_profile[1]["BOUND_BEFORE"]),
            (same_profile[1]["BOUND_BEFORE"], same_profile[0]["BOUND_AFTER"]),
        )

    def test_duplicate_event_id_rejected(self) -> None:
        identities = {
            pin.event_id: {
                "PROFILE_ID": pin.profile_id,
                "CAP_AFTER": pin.cap,
                "BOUND_AFTER": pin.bound,
                "PROOF_SCOPE": "FULL_PROFILE",
                "PROOF_SHA256": pin.proof_sha256,
                "ROW_SOURCE": authority.proof_source(pin),
            }
            for pin in authority.DONOR_PINS
        }
        with self.assertRaisesRegex(ValueError, "duplicate update event"):
            authority.apply_donor_events(self.frozen, [authority.DONOR_PINS[0]] * 2, identities)

    def test_unrelated_row_mutation_rejected(self) -> None:
        mutated = dict(self.after)
        unrelated = next(
            profile
            for profile in mutated
            if profile not in self.result["LEDGER_OVERLAY"]["DISTINCT_CHANGED_PROFILES"]
        )
        mutated[unrelated] = replace(mutated[unrelated], source="unrelated-mutation")
        with self.assertRaisesRegex(ValueError, "unrelated row mutation"):
            authority.verify_overlay(
                self.frozen,
                mutated,
                set(self.result["LEDGER_OVERLAY"]["DISTINCT_CHANGED_PROFILES"]),
            )

    def test_frozen_ledger_is_unchanged(self) -> None:
        self.assertEqual(
            authority.four.seven.two.full_digest(self.frozen),
            authority.four.SEVEN_ROW_FULL_DIGEST,
        )
        self.assertEqual(
            authority.four.seven.two.bounds_digest(self.frozen),
            authority.four.SEVEN_ROW_BOUNDS_DIGEST,
        )


if __name__ == "__main__":
    unittest.main()
