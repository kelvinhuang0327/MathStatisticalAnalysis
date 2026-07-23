"""Mutation-sensitive guards for exact feature-cohort diagnostics."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USE_CASE = (
    ROOT
    / "src/lottolab/application/use_cases/evaluate_historical_prefix_success_windows.py"
)
MODELS = ROOT / "src/lottolab/application/historical_prefix_success_windows.py"
API = ROOT / "src/lottolab/interfaces/api/historical_prefix_success_windows.py"
LOCAL_RUNTIME = ROOT / "src/lottolab/application/local_runtime.py"


def test_guard_disjoint_complement_and_fixed_complete_family() -> None:
    source = USE_CASE.read_text(encoding="utf-8")

    assert "baseline.observation_count - cohort.observation_count" in source
    assert "baseline.success_count - cohort.success_count" in source
    assert "baseline.failure_count - cohort.failure_count" in source
    assert "if result.cohort_count != 64 or len(result.cohorts) != 64" in source
    assert "if family_size != 64" in source
    assert "HistoricalPrefixExactProbability(1, 1)" in source


def test_guard_fisher_support_probability_ordering_and_exact_reduction() -> None:
    source = USE_CASE.read_text(encoding="utf-8")
    fisher = source.split("def _fisher_exact_two_sided(", 1)[1].split(
        "def _diagnostic_test_status(", 1
    )[0]

    assert "max(0, cohort_observations - (total_observations - total_successes))" in fisher
    assert "min(cohort_observations, total_successes)" in fisher
    assert "comb(total_observations, cohort_observations)" in fisher
    assert "candidate_weight := weight(successes)) <= observed_weight" in fisher
    assert "Fraction(numerator, denominator)" in fisher
    assert "* 2" not in fisher
    assert "float(" not in fisher
    assert "random" not in fisher


def test_guard_benjamini_yekutieli_harmonic_tie_break_and_monotonicity() -> None:
    source = USE_CASE.read_text(encoding="utf-8")
    adjustment = source.split("def _adjust_benjamini_yekutieli(", 1)[1].split(
        "def _feature_cohort_diagnostics(", 1
    )[0]

    assert "Fraction(1, rank) for rank in range(1, family_size + 1)" in adjustment
    assert "item[0]," in adjustment
    assert "* harmonic_factor" in adjustment
    assert "/ rank" in adjustment
    assert "min(\n            Fraction(1, 1)," in adjustment
    assert "for index in range(family_size - 1, -1, -1)" in adjustment
    assert "running_minimum = min(running_minimum, candidates[index])" in adjustment
    assert "BENJAMINI_HOCHBERG" not in source


def test_guard_test_status_precedence_and_effect_direction() -> None:
    source = USE_CASE.read_text(encoding="utf-8")
    status = source.split("def _diagnostic_test_status(", 1)[1].split(
        "def _adjust_benjamini_yekutieli(", 1
    )[0]

    assert status.index("cohort.observation_count == 0") < status.index(
        "outside.observation_count == 0"
    )
    assert status.index("outside.observation_count == 0") < status.index(
        "total_successes == 0"
    )
    assert (
        "_signed_rate_delta(\n            outside_rate,\n"
        "            cohort.success_rate,"
    ) in source


def test_guard_one_load_derivation_and_exact_method_identity() -> None:
    source = USE_CASE.read_text(encoding="utf-8")
    method = source.split("def get_feature_cohort_diagnostics(", 1)[1].split(
        "\n\n__all__", 1
    )[0]
    models = MODELS.read_text(encoding="utf-8")

    assert method.count("source = self._load(import_identity_sha256)") == 1
    assert method.count("_find_exact_strategy(") == 1
    assert method.count("cohorts = _feature_cohorts(") == 1
    assert "FISHER_EXACT_TWO_SIDED_PROBABILITY_ORDERING" in models
    assert 'BENJAMINI_YEKUTIELI_METHOD = "BENJAMINI_YEKUTIELI"' in models


def test_guard_api_uses_decimal_strings_and_one_get_route() -> None:
    api = API.read_text(encoding="utf-8")
    runtime = LOCAL_RUNTIME.read_text(encoding="utf-8")

    assert "numerator=str(probability.numerator)" in api
    assert "denominator=str(probability.denominator)" in api
    assert "canonical.fullmatch(self.numerator)" in api
    assert 'operation_id="getHistoricalPrefixStrategyFeatureCohortDiagnostics"' in api
    assert api.count("/feature-cohorts/diagnostics") == 1
    assert (
        '"{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/diagnostics"'
        in runtime
    )
