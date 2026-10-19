"""K=9 minimum overlap mass, unlabeled census, and the mass>=6 bound."""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from math import comb
from typing import cast

import pytest

from lottolab.research.b649_k1_k8_global_optimality import (
    PrizeEvent,
    TheoremStatus,
    exchange_paired_coverage,
    global_upper_bound,
    outcome_space_size,
)
from lottolab.research.b649_k9_min_mass_and_global_bound_r1 import (
    compare_higher_mass,
    enumerate_unlabeled_multigraphs,
    labeled_orbit_total,
    load_record,
    mass5_class_ids,
    prove_k9_minimum_profile,
    residual_bonferroni_ceiling,
    witness_portfolio,
)
from lottolab.research.b649_k10_min_overlap_exhaustive_r1 import (
    assert_k10_minimum_profile,
    class_set_sha256,
    enumerate_small_multigraphs,
    minimum_overlap_derivation,
    number_frequency,
    overlap_mass,
    portfolio_from_edges,
)
from lottolab.research.b649_official_any_prize_exact import (
    all_main_draw_masks,
    evaluate_portfolio,
)

POOL_SIZE = 49
DRAW_SIZE = 6
TICKET_COUNT = 9


def test_existing_k8_and_k10_certificates_stay_in_place() -> None:
    certified = global_upper_bound(PrizeEvent.OFFICIAL_ANY_PRIZE, 8)
    assert certified.status is TheoremStatus.GLOBAL_OPTIMUM_CERTIFIED
    assert certified.probability == Fraction(145873056, 601304088)
    unknown = global_upper_bound(PrizeEvent.OFFICIAL_ANY_PRIZE, 9)
    assert unknown.status is TheoremStatus.GLOBAL_OPTIMUM_UNKNOWN_BY_THIS_THEOREM
    assert unknown.numerator is None
    derived = assert_k10_minimum_profile()
    assert derived["minimum_mass"] == 11
    assert derived["histogram"] == {"1": 38, "2": 11}
    assert derived["profile_unique"] is True


def test_k9_minimum_mass_is_five_with_the_unique_double_profile() -> None:
    derived = minimum_overlap_derivation(ticket_count=TICKET_COUNT)
    profile = prove_k9_minimum_profile()
    assert profile["minimum_mass"] == derived["minimum_mass"] == 5
    assert profile["histogram"] == derived["histogram"] == {"1": 44, "2": 5}
    assert profile["profile_unique"] is True
    assert derived["profile_unique"] is True
    assert derived["slots"] == DRAW_SIZE * TICKET_COUNT
    assert derived["pool_size"] == POOL_SIZE


@pytest.mark.parametrize(
    ("vertex_count", "edge_count", "max_degree"),
    [
        (1, 1, 1),
        (2, 3, 2),
        (4, 0, 2),
        (3, 4, 6),
        (4, 3, 2),
        (5, 2, 1),
        (5, 4, 3),
        (6, 3, 3),
        (6, 5, 6),
    ],
)
def test_census_matches_the_existing_small_enumerator(
    vertex_count: int, edge_count: int, max_degree: int
) -> None:
    got = enumerate_unlabeled_multigraphs(vertex_count, edge_count, max_degree)
    expected = enumerate_small_multigraphs(vertex_count, edge_count, max_degree)
    assert len(got) == len(set(got))
    assert list(got) == list(expected)


def test_mass5_census_is_complete_and_repeats() -> None:
    first = mass5_class_ids()
    second = mass5_class_ids()
    assert first == second
    assert len(first) == len(set(first))
    assert class_set_sha256(first) == class_set_sha256(second)
    labeled = comb(comb(TICKET_COUNT, 2) + 5 - 1, 5)
    assert labeled_orbit_total(first, TICKET_COUNT) == labeled
    for class_id in first:
        portfolio = witness_portfolio(class_id)
        assert len(portfolio) == TICKET_COUNT
        assert len(set(portfolio)) == TICKET_COUNT
        assert overlap_mass(portfolio) == 5
        assert number_frequency(portfolio) == {"1": 44, "2": 5}


def test_exchange_on_a_k9_repeat_does_not_decrease_coverage() -> None:
    edges = tuple((0, index, 1) for index in range(1, 7))
    portfolio = portfolio_from_edges(edges, vertex_count=TICKET_COUNT, draw_size=DRAW_SIZE)
    assert overlap_mass(portfolio) == 6
    used = {number for ticket in portfolio for number in ticket}
    unused = [number for number in range(1, POOL_SIZE + 1) if number not in used]
    assert len(unused) == 1
    counts = Counter(number for ticket in portfolio for number in ticket)
    repeated = min(number for number, count in counts.items() if count >= 2)
    ticket_index = next(index for index, ticket in enumerate(portfolio) if repeated in ticket)
    paired = exchange_paired_coverage(
        PrizeEvent.OFFICIAL_ANY_PRIZE,
        portfolio,
        ticket_index=ticket_index,
        remove=repeated,
        insert=unused[0],
    )
    assert paired.does_not_decrease
    edited_rows = [list(ticket) for ticket in portfolio]
    edited_rows[ticket_index] = [
        unused[0] if number == repeated else number for number in edited_rows[ticket_index]
    ]
    edited = tuple(tuple(sorted(ticket)) for ticket in edited_rows)
    assert len(set(edited)) == TICKET_COUNT
    assert overlap_mass(edited) < overlap_mass(portfolio)


def _object_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AssertionError("expected an object")
    row: dict[str, object] = {}
    for key, item in cast(dict[object, object], value).items():
        if not isinstance(key, str):
            raise AssertionError("expected a string key")
        row[key] = item
    return row


def _record_classes(record: dict[str, object]) -> list[dict[str, object]]:
    classes = record["classes"]
    if not isinstance(classes, list):
        raise AssertionError("record classes are missing")
    return [_object_dict(item) for item in cast(list[object], classes)]


def _tickets(raw: object) -> tuple[tuple[int, ...], ...]:
    if not isinstance(raw, list):
        raise AssertionError("tickets missing")
    parsed: list[tuple[int, ...]] = []
    for ticket in cast(list[object], raw):
        if not isinstance(ticket, list):
            raise AssertionError("ticket row is not a list")
        numbers: list[int] = []
        for number in cast(list[object], ticket):
            if type(number) is not int:
                raise AssertionError("ticket number is not an int")
            numbers.append(number)
        parsed.append(tuple(numbers))
    return tuple(parsed)


def _record_int(record: dict[str, object], key: str) -> int:
    value = record[key]
    if type(value) is not int:
        raise AssertionError(f"{key} is not an int")
    return value


def _record_str(record: dict[str, object], key: str) -> str:
    value = record[key]
    if not isinstance(value, str):
        raise AssertionError(f"{key} is not a string")
    return value


def test_record_witnesses_match_the_exact_evaluator_and_the_mass_bound() -> None:
    record = load_record()
    assert record["higher_mass_class_list"] is False
    assert all("mass_6" not in key and not key.startswith("mass6") for key in record)
    class_ids = mass5_class_ids()
    rows = _record_classes(record)
    assert [_record_str(row, "class_id") for row in rows] == list(class_ids)
    assert len(class_ids) == _record_int(record, "MASS5_CLASS_COUNT")
    assert class_set_sha256(class_ids) == _record_str(record, "class_set_sha256")
    draws = all_main_draw_masks(POOL_SIZE, DRAW_SIZE)
    denominator = outcome_space_size(PrizeEvent.OFFICIAL_ANY_PRIZE)
    scores: list[int] = []
    for row in rows:
        class_id = _record_str(row, "class_id")
        tickets = _tickets(row["tickets"])
        assert tickets == witness_portfolio(class_id)
        scored = evaluate_portfolio(tickets, draws=draws)
        assert scored.official_any_prize_outcome_count == _record_int(
            row, "official_any_prize_outcome_count"
        )
        scores.append(scored.official_any_prize_outcome_count)
    optimum = max(scores)
    ties = sum(1 for score in scores if score == optimum)
    assert optimum == _record_int(record, "MASS5_OPTIMUM_COUNT")
    assert ties == _record_int(record, "MASS5_TIE_COUNT")
    probability = Fraction(optimum, denominator)
    assert _record_str(record, "MASS5_OPTIMUM_PROBABILITY") == (
        f"{probability.numerator}/{probability.denominator}"
    )
    optimum_id = _record_str(record, "optimum_class_id")
    optimum_score = evaluate_portfolio(witness_portfolio(optimum_id), draws=draws)
    assert optimum_score.official_any_prize == probability
    assert optimum_score.official_any_prize_outcome_count == optimum
    ceiling = residual_bonferroni_ceiling()
    bound, status, gap = compare_higher_mass(optimum, ceiling)
    assert ceiling == _record_int(record, "residual_bonferroni_ceiling")
    assert bound == _record_int(record, "MASS_GE6_BOUND")
    assert status == _record_str(record, "GLOBAL_OPTIMUM_STATUS")
    assert gap == _record_int(record, "REMAINING_GAP")
    if ceiling <= optimum:
        assert status == "PROVEN"
        assert gap == 0
        assert bound == optimum
    else:
        assert status == "UNKNOWN"
        assert bound == ceiling
        assert gap == ceiling - optimum
        assert gap > 0
