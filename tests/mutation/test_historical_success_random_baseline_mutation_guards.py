"""Source-level guards for load-bearing R1 random-baseline mutations."""

from __future__ import annotations

import inspect
from pathlib import Path

import lottolab.application.use_cases.evaluate_historical_prefix_success_windows as module
from lottolab.application.historical_success_random_baseline import (
    binomial_upper_tail,
    evaluate_historical_success_random_baseline,
    portfolio_success_probability,
)
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "src/lottolab/application/historical_success_random_baseline.py"
USE_CASE = (
    ROOT
    / "src/lottolab/application/use_cases/evaluate_historical_prefix_success_windows.py"
)
READER = (
    ROOT
    / "src/lottolab/infrastructure/persistence/"
    "historical_prefix_success_window_reader.py"
)
QUALIFICATION = ROOT / "src/lottolab/application/historical_success_qualification.py"
API_ROOT = ROOT / "src/lottolab/interfaces/api"


def test_guard_iid_with_replacement_formula_and_exact_upper_tail_direction() -> None:
    portfolio_source = inspect.getsource(portfolio_success_probability)
    tail_source = inspect.getsource(binomial_upper_tail)

    assert "LEGAL_TICKET_COUNT**prefix_count - failure_count**prefix_count" in portfolio_source
    assert "LEGAL_TICKET_COUNT**prefix_count" in portfolio_source
    assert "observed_success_count, observation_count + 1" in tail_source
    assert "range(observed_success_count)" in tail_source
    assert "Fraction(numerator, denominator)" in tail_source


def test_guard_official_special_main_hit_mismatch_and_six_plus_special_checks() -> None:
    source = inspect.getsource(evaluate_historical_success_random_baseline)

    assert "observation.target_special_number in ticket.main_numbers" in source
    assert "set(ticket.main_numbers) & set(observation.target_main_numbers)" in source
    assert "recomputed_main_hits != ticket.persisted_main_hit_count" in source
    assert "recomputed_main_hits == 6 and official_special_hit" in source
    assert source.count("persisted_legacy_special_hit") == 1
    assert "type(ticket.persisted_legacy_special_hit) is not bool" in source
    assert "observation.tickets[: cell.prefix_count]" in source
    assert "len(observations) * cell.prefix_count" in source


def test_guard_one_factory_reader_load_strategy_lookup_and_window_evaluation() -> None:
    method = inspect.getsource(
        EvaluateHistoricalPrefixSuccessWindows.get_random_null_baseline
    )
    evaluator = inspect.getsource(
        module._evaluate_random_baseline_window  # pyright: ignore[reportPrivateUsage]
    )

    assert method.count("self._reader_factory()") == 1
    assert method.count("self._load_with_reader(") == 1
    assert method.count("_find_exact_strategy(") == 1
    assert method.count("_evaluate_strategy(") == 1
    assert method.count("_evaluate_random_baseline_window(") == 1
    assert evaluator.count("_selected_window_observations(") == 1
    assert "load_source(" not in method


def test_guard_window_slicing_and_raw_forwarding_stay_on_existing_source_load() -> None:
    use_case_source = USE_CASE.read_text(encoding="utf-8")
    reader_source = READER.read_text(encoding="utf-8")

    assert "ordered[-window.requested_draw_count :]" in use_case_source
    assert "main_numbers=main_numbers" in reader_source
    assert "target_main_numbers=target.main_numbers" in reader_source
    assert "target_special_number=target.special_numbers[0]" in reader_source
    assert "main_numbers_json" in reader_source
    assert "special_numbers_json" in reader_source


def test_guard_baseline_has_one_descriptive_get_api_and_no_qualification_feed() -> None:
    qualification_source = QUALIFICATION.read_text(encoding="utf-8")
    api_sources = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(API_ROOT.glob("*.py"))
    }
    baseline_source = BASELINE.read_text(encoding="utf-8")
    baseline_api = api_sources["historical_prefix_success_windows.py"]

    assert "historical_success_random_baseline" not in qualification_source
    assert baseline_api.count("get_random_null_baseline(") == 1
    assert baseline_api.count("/random-null-baseline") == 1
    assert all(
        "historical_success_random_baseline" not in source
        for name, source in api_sources.items()
        if name != "historical_prefix_success_windows.py"
    )
    assert "@router.post" not in baseline_api
    assert "@router.put" not in baseline_api
    assert "@router.patch" not in baseline_api
    assert "@router.delete" not in baseline_api
    for forbidden in ("numpy", "scipy", "Monte Carlo", "alpha threshold"):
        assert forbidden not in baseline_source
