from __future__ import annotations

import unittest
from dataclasses import replace
from typing import Any

from lottolab.research import b649_eleven_event_family_authority_r1 as authority


class DonorCertificateGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pin = authority.DONOR_PINS[0]
        self.source = authority.nine.proof_source(self.pin)
        self.certificate: dict[str, Any] = {
            "PROFILE_ID": self.pin.profile_id,
            "T_CAP": self.pin.cap,
            "OWNER_BOUND": self.pin.bound,
            "PROOF_SCOPE": "FULL_PROFILE",
            "ROW_SOURCE": self.source,
            "PROOF_SHA256": self.pin.proof_sha256,
        }

    def verify(self, certificate: dict[str, Any]) -> None:
        authority.nine.verify_certificate(
            certificate,
            profile_id=self.pin.profile_id,
            cap=self.pin.cap,
            bound=self.pin.bound,
            source=self.source,
        )

    def test_wrong_source_sha_rejected(self) -> None:
        altered = replace(self.pin, source_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "donor source SHA256 mismatch"):
            authority.verify_new_donor(authority.ROOT, altered)

    def test_wrong_profile_rejected(self) -> None:
        altered = replace(self.pin, profile_id="00000000000000000000")
        with self.assertRaisesRegex(ValueError, "profile, row, cap, or bound mismatch"):
            authority.verify_new_donor(authority.ROOT, altered)

    def test_wrong_t_cap_rejected(self) -> None:
        altered = replace(self.pin, cap=self.pin.cap - 1)
        with self.assertRaisesRegex(ValueError, "profile, row, cap, or bound mismatch"):
            authority.verify_new_donor(authority.ROOT, altered)

    def test_wrong_bound_rejected(self) -> None:
        altered = replace(self.pin, bound=self.pin.bound + 1)
        with self.assertRaisesRegex(ValueError, "profile, row, cap, or bound mismatch"):
            authority.verify_new_donor(authority.ROOT, altered)

    def test_wrong_proof_source_rejected(self) -> None:
        altered = dict(
            self.certificate,
            ROW_SOURCE="git:other@tree:proof.json#PROOF:sha256="
            + self.pin.proof_sha256,
        )
        with self.assertRaisesRegex(ValueError, "source identity mismatch"):
            self.verify(altered)

    def test_missing_proof_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "donor proof is missing"):
            authority.nine.proof_sha256(None)


class ElevenEventFamilyAuthorityTests(unittest.TestCase):
    result: dict[str, Any]
    frozen: dict[str, authority.Row]
    after: dict[str, authority.Row]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.result, cls.frozen, cls.after = authority.build_candidate()

    def test_11_event_ledger_digests_and_family_frontier(self) -> None:
        result = self.result
        overlay = result["LEDGER_OVERLAY"]
        self.assertEqual(result["UPDATE_EVENTS"], 11)
        self.assertEqual(result["ADDITIONAL_EVENTS_FROM_NINE"], 2)
        self.assertEqual(result["ADDITIONAL_CHANGED_PROFILES"], 2)
        self.assertEqual(result["UNCHANGED_ROWS_FROM_NINE"], 4_645)
        self.assertEqual(result["DISTINCT_CHANGED_PROFILES"], 10)
        self.assertEqual(overlay["ROWS_BEFORE"], 4_647)
        self.assertEqual(overlay["ROWS_AFTER"], 4_647)
        self.assertEqual(overlay["UPDATE_EVENTS"], 11)
        self.assertEqual(overlay["DISTINCT_CHANGED_PROFILE_COUNT"], 10)
        self.assertEqual(overlay["UNCHANGED_ROWS"], 4_637)
        self.assertEqual(result["NEW_FULL_DIGEST"], authority.EXPECTED_NEW_FULL_DIGEST)
        self.assertEqual(result["NEW_BOUNDS_DIGEST"], authority.EXPECTED_NEW_BOUNDS_DIGEST)
        self.assertEqual(
            result["EXPECTED_BOUND_ONLY_BOUNDS_DIGEST"],
            result["NEW_BOUNDS_DIGEST"],
        )
        self.assertEqual(result["FAMILY_BEFORE"]["FAMILY_BOUND"], 313_398_532)
        self.assertEqual(result["FAMILY_AFTER"]["FAMILY_BOUND"], 313_395_344)
        self.assertEqual(
            result["FAMILY_AFTER"]["TIED_OWNERS"],
            ["66655555555511100000", "66665555554431000000"],
        )
        self.assertEqual(result["FAMILY_AFTER"]["NEXT_COMPETING_BOUND"], 313_395_164)
        self.assertEqual(
            result["FAMILY_AFTER"]["NEXT_COMPETING_OWNERS"],
            [
                "65555555555532000000",
                "66555555554442000000",
                "66555555555333000000",
            ],
        )
        self.assertEqual(result["FAMILY_DELTA_FROM_NINE"], 104)
        self.assertEqual(result["FAMILY_DELTA_FROM_FROZEN"], 3_188)
        self.assertEqual(result["RESOLVED_PROFILES_ABOVE_INCUMBENT"], 1_373)
        self.assertEqual(
            result["UNRESOLVED_CURSOR"],
            {
                "PROFILE_COUNT": 197,
                "STATUS": "UNRESOLVED_AUTHORITY_UNCHANGED",
                "ID": authority.CURSOR_ID,
                "BOUND": authority.CURSOR_BOUND,
            },
        )
        self.assertEqual(result["GLOBAL_K20_OPTIMUM"], "UNKNOWN")
        self.assertEqual(result["NEW_WINNING_OUTCOMES"], 0)
        self.assertEqual(result["CURSOR_PRESERVED"], "YES")
        self.assertEqual(result["FORMAL_AUTHORITY_ACCEPTANCE"], "NOT_CLAIMED")

    def test_nine_event_source_and_result_are_exactly_pinned(self) -> None:
        prior = self.result["NINE_EVENT_AUTHORITY"]
        self.assertEqual(prior["HEAD"], authority.BASE_HEAD)
        self.assertEqual(prior["TREE"], authority.BASE_TREE)
        self.assertEqual(prior["RESULT_SHA256"], authority.NINE_RESULT_SHA256)
        self.assertEqual(prior["SOURCE_SHA256"], authority.NINE_SOURCE_SHA256)
        self.assertEqual(prior["TEST_SHA256"], authority.NINE_TEST_SHA256)
        self.assertEqual(prior["SOURCE_REPLAY_MATCH"], "YES")
        self.assertEqual(
            prior["NEW_BOUNDS_DIGEST"],
            "dff29de4b8732ad88a7906453a244406bc147343ff48a980f50dcd2d26d1b4d0",
        )
        self.assertEqual(
            self.result["T255_SOLE_DONOR"],
            "40a516aaa5a766c2312ef1402d70bdafdc22177e",
        )
        self.assertEqual(self.result["SECOND_T255_DONOR_ADOPTED"], "NO")

    def test_new_donor_pointers_bind_result_source_and_proof(self) -> None:
        identities = self.result["DONOR_IDENTITIES"]
        for pin in authority.DONOR_PINS:
            identity = identities[pin.event_id]
            self.assertEqual(identity["HEAD"], pin.head)
            self.assertEqual(identity["TREE"], pin.tree)
            self.assertEqual(identity["RESULT_SHA256"], pin.result_sha256)
            self.assertEqual(identity["SOURCE_SHA256"], pin.source_sha256)
            self.assertEqual(identity["TEST_SHA256"], pin.test_sha256)
            self.assertEqual(identity["PROOF_SCOPE"], "FULL_PROFILE")
            self.assertEqual(identity["PROOF_SHA256"], pin.proof_sha256)
            self.assertEqual(identity["ROW_SOURCE"], authority.nine.proof_source(pin))
            self.assertEqual(identity["FRESH_JUDGE_STATUS"], "VERIFIED_WITH_CAVEATS")

    def test_distinct_events_on_same_profile_are_applied_in_sequence(self) -> None:
        repeated = [
            event
            for event in self.result["EVENT_HISTORY"]
            if event["PROFILE_ID"] == "66655555555521000000"
        ]
        self.assertEqual(len(repeated), 2)
        self.assertNotEqual(repeated[0]["EVENT_ID"], repeated[1]["EVENT_ID"])
        self.assertEqual(repeated[1]["EVENT_ID"], "T258")
        self.assertEqual(repeated[0]["BOUND_AFTER"], repeated[1]["BOUND_BEFORE"])
        self.assertEqual(self.result["DISTINCT_CHANGED_PROFILES"], 10)

    def test_duplicate_event_id_rejected(self) -> None:
        pin = authority.DONOR_PINS[0]
        original = self.after[pin.profile_id]
        starting = replace(
            original,
            bound=pin.previous_bound,
            cap=pin.previous_cap,
            s4_base=pin.s4_base,
        )
        with self.assertRaisesRegex(ValueError, "duplicate update event"):
            authority.nine.apply_donor_events(
                {pin.profile_id: starting},
                [pin, pin],
                {pin.event_id: self.result["DONOR_IDENTITIES"][pin.event_id]},
            )

    def test_unrelated_row_mutation_rejected(self) -> None:
        changed = set(self.result["LEDGER_OVERLAY"]["DISTINCT_CHANGED_PROFILES"])
        mutated = dict(self.after)
        unrelated = next(profile_id for profile_id in mutated if profile_id not in changed)
        mutated[unrelated] = replace(mutated[unrelated], source="unrelated-mutation")
        with self.assertRaisesRegex(ValueError, "unrelated row mutation"):
            authority.verify_overlay(self.frozen, mutated, changed)

    def test_incorrect_family_max_rejected(self) -> None:
        wrong = dict(self.result["FAMILY_AFTER"])
        wrong["FAMILY_BOUND"] += 1
        with self.assertRaisesRegex(ValueError, "new family frontier mismatch"):
            authority.verify_family_frontier(wrong)

    def test_historical_caveats_and_frozen_ledger_are_preserved(self) -> None:
        caveats = self.result["CAVEATS"]
        self.assertEqual(caveats["EIGHT_ROW_HISTORICAL"], "BLOCKED_UNVERIFIABLE")
        self.assertEqual(caveats["FOUR_OWNER"], "VERIFIED_WITH_CAVEATS")
        self.assertEqual(caveats["T255"], "VERIFIED_WITH_CAVEATS")
        self.assertEqual(
            caveats["HISTORICAL_NB_CERTIFICATES_1444"],
            "UNRESOLVED_LOCATOR_PRESERVED",
        )
        self.assertEqual(caveats["HISTORICAL_MUTATION_RAW_LOGS"], "NOT_OBTAINED")
        self.assertEqual(
            self.result["HISTORICAL_AUTHORITY_CAVEATS"]["NB_CERTIFICATES_1444"][
                "FROZEN_HISTORY_REWRITTEN"
            ],
            "NO",
        )
        self.assertEqual(
            self.result["HISTORICAL_AUTHORITY_CAVEATS"]["MUTATION_RAW_LOGS"]["STATUS"],
            "NOT_OBTAINED",
        )
        self.assertEqual(self.result["FROZEN_LEDGER_MUTATED"], "NO")
        self.assertEqual(self.result["DONOR_WORKTREES_MUTATED"], "NO")
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
