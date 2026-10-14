"""TEST_ONLY synthetic fixtures for the fixed B649 C2 result contract.

No fixture in this file represents a measurement or candidate/checker input.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from lottolab.research.b649_c2_equality_seven_pair_result_contract_r1 import (
    BATCH_ORBIT_WEIGHT_TOTAL,
    BATCH_PAIR_SPECS,
    EXPECTED_HISTOGRAM_TOTAL,
    BatchStatus,
    PairResult,
    PairStatus,
    complementary_contributions,
    exact_equality_sum,
    validate_batch,
    validate_pair_result,
)

# TEST_ONLY: fabricated histogram values, never imported from a measured result.
TEST_ONLY_ZERO_HISTOGRAM = ((0, EXPECTED_HISTOGRAM_TOTAL),)
TEST_ONLY_ZERO_RESULTS = tuple(
    PairResult(
        ordered_pair=spec.ordered_pair,
        engine_pair=spec.engine_pair,
        orbit_index=spec.orbit_index,
        orbit_size=spec.orbit_size,
        status=PairStatus.COMPLETE,
        target_gain_sum=1,
        histogram=TEST_ONLY_ZERO_HISTOGRAM,
        exact_equality_count=0,
    )
    for spec in BATCH_PAIR_SPECS
)


def make_test_only_result(
    index: int,
    status: PairStatus,
    *,
    target_gain_sum: int | None = None,
    histogram: tuple[tuple[int, int], ...] | None = None,
    exact_equality_count: int | None = None,
) -> PairResult:
    spec = BATCH_PAIR_SPECS[index]
    return PairResult(
        ordered_pair=spec.ordered_pair,
        engine_pair=spec.engine_pair,
        orbit_index=spec.orbit_index,
        orbit_size=spec.orbit_size,
        status=status,
        target_gain_sum=target_gain_sum,
        histogram=histogram,
        exact_equality_count=exact_equality_count,
    )


def make_test_only_partial_batch() -> tuple[PairResult, ...]:
    return (
        TEST_ONLY_ZERO_RESULTS[0],
        TEST_ONLY_ZERO_RESULTS[1],
        make_test_only_result(
            2,
            PairStatus.INCOMPLETE,
            target_gain_sum=1,
            histogram=((0, 10),),
        ),
        *(make_test_only_result(index, PairStatus.NOT_RUN) for index in range(3, 7)),
    )


class SevenPairContractTests(unittest.TestCase):
    def test_complete_batch_accepts_zero_e_for_every_pair(self) -> None:
        summary = validate_batch(TEST_ONLY_ZERO_RESULTS)

        self.assertIs(summary.status, BatchStatus.COMPLETE)
        self.assertEqual(summary.completed_pair_count, 7)
        self.assertEqual(summary.coverage_orbit_size, 37)
        self.assertEqual(summary.coverage_orbit_size, BATCH_ORBIT_WEIGHT_TOTAL)
        self.assertTrue(all(row.exact_equality_count == 0 for row in summary.results))

    def test_positive_e_needs_no_candidate_rows_or_checker_input(self) -> None:
        histogram = ((0, 1), (1, EXPECTED_HISTOGRAM_TOTAL - 1))
        exact_e = exact_equality_sum(histogram, 1)
        result = replace(
            TEST_ONLY_ZERO_RESULTS[0],
            histogram=histogram,
            exact_equality_count=exact_e,
        )

        validate_pair_result(result)
        self.assertGreater(exact_e, 0)
        self.assertFalse(hasattr(result, "candidate_rows"))
        self.assertFalse(hasattr(result, "candidate_x"))
        self.assertFalse(hasattr(result, "candidate_y"))

    def test_interruption_preserves_completed_rows_and_null_future_e(self) -> None:
        rows = make_test_only_partial_batch()
        summary = validate_batch(rows)

        self.assertIs(summary.status, BatchStatus.PARTIAL)
        self.assertEqual(summary.results, rows)
        self.assertEqual(summary.completed_ordered_pairs, ((0, 6), (0, 12)))
        self.assertEqual(summary.completed_pair_count, 2)
        self.assertEqual(summary.coverage_orbit_size, 7)
        self.assertEqual(summary.results[0].exact_equality_count, 0)
        self.assertEqual(summary.results[1].exact_equality_count, 0)
        self.assertIs(summary.results[2].status, PairStatus.INCOMPLETE)
        self.assertIsNone(summary.results[2].exact_equality_count)
        self.assertTrue(all(row.exact_equality_count is None for row in summary.results[3:]))

    def test_ordered_pair_six_does_not_map_to_engine_pair_six(self) -> None:
        bad_mapping = replace(TEST_ONLY_ZERO_RESULTS[0], engine_pair=(0, 6))

        with self.assertRaisesRegex(ValueError, "engine pair mismatch"):
            validate_pair_result(bad_mapping)

    def test_batch_rejects_missing_duplicate_or_eighth_pair(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly 7"):
            validate_batch(TEST_ONLY_ZERO_RESULTS[:-1])

        duplicate = list(TEST_ONLY_ZERO_RESULTS)
        duplicate[2] = duplicate[0]
        with self.assertRaisesRegex(ValueError, "duplicate ordered pair"):
            validate_batch(duplicate)

        with self.assertRaisesRegex(ValueError, "exactly 7"):
            validate_batch((*TEST_ONLY_ZERO_RESULTS, TEST_ONLY_ZERO_RESULTS[0]))

    def test_complete_status_rejects_a_partial_histogram(self) -> None:
        result = replace(
            TEST_ONLY_ZERO_RESULTS[0],
            histogram=((0, EXPECTED_HISTOGRAM_TOTAL - 1),),
        )

        with self.assertRaisesRegex(ValueError, "histogram total"):
            validate_pair_result(result)

    def test_complete_status_requires_a_non_null_exact_e(self) -> None:
        result = replace(TEST_ONLY_ZERO_RESULTS[0], exact_equality_count=None)

        with self.assertRaisesRegex(ValueError, "non-null exact E"):
            validate_pair_result(result)

    def test_histogram_rejects_duplicate_or_unsorted_gain_keys(self) -> None:
        for histogram in (
            ((0, 1), (0, EXPECTED_HISTOGRAM_TOTAL - 1)),
            ((1, 1), (0, EXPECTED_HISTOGRAM_TOTAL - 1)),
        ):
            with self.subTest(histogram=histogram):
                with self.assertRaisesRegex(ValueError, "unique and strictly increasing"):
                    validate_pair_result(
                        replace(TEST_ONLY_ZERO_RESULTS[0], histogram=histogram)
                    )

    def test_same_gain_bucket_uses_choose_two_and_rejects_product_formula(self) -> None:
        contributions = complementary_contributions(((2, 3),), 4)
        self.assertEqual(len(contributions), 1)
        self.assertEqual(contributions[0].formula, "CHOOSE_2_DISTINCT")
        self.assertEqual(contributions[0].contribution, 3)

        wrong_product_e = replace(
            TEST_ONLY_ZERO_RESULTS[0],
            target_gain_sum=4,
            histogram=((2, EXPECTED_HISTOGRAM_TOTAL),),
            exact_equality_count=EXPECTED_HISTOGRAM_TOTAL * EXPECTED_HISTOGRAM_TOTAL,
        )
        with self.assertRaisesRegex(ValueError, "exact E mismatch"):
            validate_pair_result(wrong_product_e)

    def test_big_integer_complement_sum_remains_exact_instead_of_float(self) -> None:
        huge = 2**54 + 3
        histogram = ((1, huge), (2, huge + 1))
        exact = exact_equality_sum(histogram, 3)
        float_derived = float(huge) * float(huge + 1)

        self.assertEqual(exact, huge * (huge + 1))
        self.assertIs(type(exact), int)
        self.assertNotEqual(int(float_derived), exact)

    def test_empty_complement_table_does_not_make_incomplete_histogram_e_zero(self) -> None:
        incomplete = make_test_only_result(
            0,
            PairStatus.INCOMPLETE,
            target_gain_sum=99,
            histogram=((0, 10),),
        )
        self.assertEqual(complementary_contributions(incomplete.histogram or (), 99), ())
        validate_pair_result(incomplete)

        fabricated_zero = replace(
            incomplete,
            status=PairStatus.COMPLETE,
            exact_equality_count=0,
        )
        with self.assertRaisesRegex(ValueError, "histogram total"):
            validate_pair_result(fabricated_zero)

    def test_incomplete_and_not_run_results_require_null_e(self) -> None:
        incomplete_with_zero = make_test_only_result(
            2,
            PairStatus.INCOMPLETE,
            target_gain_sum=1,
            histogram=((0, 10),),
            exact_equality_count=0,
        )
        not_run_with_zero = make_test_only_result(
            3, PairStatus.NOT_RUN, exact_equality_count=0
        )

        with self.assertRaisesRegex(ValueError, "must have null exact E"):
            validate_pair_result(incomplete_with_zero)
        with self.assertRaisesRegex(ValueError, "must have null exact E"):
            validate_pair_result(not_run_with_zero)

    def test_histogram_gain_keys_counts_and_e_reject_float_values(self) -> None:
        bad_values = (
            replace(TEST_ONLY_ZERO_RESULTS[0], histogram=((0.0, EXPECTED_HISTOGRAM_TOTAL),)),
            replace(TEST_ONLY_ZERO_RESULTS[0], histogram=((0, float(EXPECTED_HISTOGRAM_TOTAL)),)),
            replace(TEST_ONLY_ZERO_RESULTS[0], histogram=((0, 0),)),
            replace(TEST_ONLY_ZERO_RESULTS[0], exact_equality_count=0.0),
            replace(TEST_ONLY_ZERO_RESULTS[0], status="UNKNOWN"),
        )

        for result in bad_values:
            with self.subTest(result=result):
                with self.assertRaises(ValueError):
                    validate_pair_result(result)

    def test_completed_orbit_weights_are_37_and_legacy_pilot_is_separate(self) -> None:
        summary = validate_batch(TEST_ONLY_ZERO_RESULTS)
        # TEST_ONLY comparison: the existing (0, 1) pilot remains outside this batch.
        legacy_pilot_orbit_weight = 1

        self.assertEqual(
            summary.coverage_orbit_size,
            sum(spec.orbit_size for spec in BATCH_PAIR_SPECS),
        )
        self.assertEqual(summary.coverage_orbit_size, 37)
        self.assertEqual(summary.coverage_orbit_size + legacy_pilot_orbit_weight, 38)


if __name__ == "__main__":
    unittest.main()
