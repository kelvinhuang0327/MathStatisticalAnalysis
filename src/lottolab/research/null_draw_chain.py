"""Deterministic exact-null synthetic draw-chain generation.

Produces draw sequences sampled independently and uniformly under a
lottery's authoritative rule contract (`lottolab.domain.lottery_rules`) —
the exact-null reference distribution the cross-lottery research program
will later use to calibrate multiple-comparison and power claims. This
module never reads real draw history and performs no statistical
inference; it only generates and canonically hashes synthetic chains.

Reuses `lottolab.evidence.models.RuleParameters` (self-hashed the same way
`lottolab.evidence.validator` hashes it) and `lottolab.evidence.canonical_json`
for every serialization and hash rather than defining a second canonical
format.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from random import Random
from typing import Any

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import LotteryRuleContract
from lottolab.evidence import canonical_json
from lottolab.evidence.models import RuleParameters


@dataclass(frozen=True, slots=True)
class NullDraw:
    """One synthetic draw: uniform, independent, no serial dependence."""

    draw_sequence: int
    draw_date: date
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class NullDrawChain:
    """An immutable, self-describing, content-hashed synthetic draw chain."""

    lottery_type: LotteryType
    rule_parameters: RuleParameters
    seed: int
    draw_count: int
    start_date: date
    draws: tuple[NullDraw, ...]
    chain_sha256: str


def generate_null_draw_chain(
    rule: LotteryRuleContract,
    *,
    draw_count: int,
    start_date: date,
    seed: int,
) -> NullDrawChain:
    """Generate `draw_count` iid uniform draws under `rule`, seeded deterministically.

    Each draw independently samples `main_number_count` numbers from
    [main_number_min, main_number_max] and, when the rule defines special
    numbers, independently samples `special_number_count` numbers from
    [special_number_min, special_number_max] — honoring both
    `*_numbers_unique` and `main_special_overlap_allowed`. There is no
    trend, no serial dependence, and no cross-draw correlation: this is the
    complete null model, not an approximation of it. A caller computing a
    test statistic against real history must compare it to the
    distribution of the same statistic across many independent chains from
    this function, not to a single chain.
    """

    if draw_count <= 0:
        raise ValueError("draw_count must be positive")

    rule_parameters = _build_rule_parameters(rule)
    rng = Random(seed)
    draws = tuple(
        _generate_one_draw(rng, rule_parameters, sequence, start_date)
        for sequence in range(draw_count)
    )
    chain_sha256 = canonical_json.sha256_hex(
        canonical_json.canonical_bytes(
            _chain_payload(
                rule.lottery_type, rule_parameters, seed, draw_count, start_date, draws
            )
        )
    )
    return NullDrawChain(
        lottery_type=rule.lottery_type,
        rule_parameters=rule_parameters,
        seed=seed,
        draw_count=draw_count,
        start_date=start_date,
        draws=draws,
        chain_sha256=chain_sha256,
    )


def chain_canonical_bytes(chain: NullDrawChain) -> bytes:
    """The exact canonical bytes `chain.chain_sha256` was computed over."""

    return canonical_json.canonical_bytes(
        _chain_payload(
            chain.lottery_type,
            chain.rule_parameters,
            chain.seed,
            chain.draw_count,
            chain.start_date,
            chain.draws,
        )
    )


def _chain_payload(
    lottery_type: LotteryType,
    rule_parameters: RuleParameters,
    seed: int,
    draw_count: int,
    start_date: date,
    draws: tuple[NullDraw, ...],
) -> dict[str, Any]:
    return {
        "lottery_type": lottery_type.value,
        "rule_parameters": rule_parameters.model_dump(mode="json", exclude_none=True),
        "seed": seed,
        "draw_count": draw_count,
        "start_date": start_date.isoformat(),
        "draws": [
            {
                "draw_sequence": draw.draw_sequence,
                "draw_date": draw.draw_date.isoformat(),
                "main_numbers": list(draw.main_numbers),
                "special_numbers": list(draw.special_numbers),
            }
            for draw in draws
        ],
    }


def _generate_one_draw(
    rng: Random,
    rule_parameters: RuleParameters,
    sequence: int,
    start_date: date,
) -> NullDraw:
    main_numbers = _sample_numbers(
        rng,
        count=rule_parameters.main_number_count,
        low=rule_parameters.main_number_min,
        high=rule_parameters.main_number_max,
        unique=rule_parameters.main_numbers_unique,
        forbidden=(),
    )
    special_numbers: tuple[int, ...] = ()
    if rule_parameters.special_number_count > 0:
        forbidden = () if rule_parameters.main_special_overlap_allowed else main_numbers
        special_numbers = _sample_numbers(
            rng,
            count=rule_parameters.special_number_count,
            low=rule_parameters.special_number_min,
            high=rule_parameters.special_number_max,
            unique=rule_parameters.special_numbers_unique,
            forbidden=forbidden,
        )
    return NullDraw(
        draw_sequence=sequence,
        draw_date=start_date + timedelta(days=sequence),
        main_numbers=main_numbers,
        special_numbers=special_numbers,
    )


def _sample_numbers(
    rng: Random,
    *,
    count: int,
    low: int,
    high: int,
    unique: bool,
    forbidden: tuple[int, ...],
) -> tuple[int, ...]:
    if count == 0:
        return ()
    pool = [number for number in range(low, high + 1) if number not in forbidden]
    if unique:
        if count > len(pool):
            raise ValueError("not enough eligible numbers to sample without replacement")
        sampled = rng.sample(pool, count)
    else:
        if not pool:
            raise ValueError("no eligible numbers to sample")
        sampled = [rng.choice(pool) for _ in range(count)]
    return tuple(sorted(sampled))


def _build_rule_parameters(rule: LotteryRuleContract) -> RuleParameters:
    payload: dict[str, Any] = {
        "main_number_count": rule.main_number_count,
        "main_number_min": rule.main_number_min,
        "main_number_max": rule.main_number_max,
        "main_numbers_unique": rule.main_numbers_unique,
        "special_number_count": rule.special_number_count,
        "special_number_min": rule.special_number_min,
        "special_number_max": rule.special_number_max,
        "special_numbers_unique": rule.special_numbers_unique,
        "main_special_overlap_allowed": rule.main_special_overlap_allowed,
        "rule_contract_version": rule.contract_version,
    }
    digest = canonical_json.sha256_hex(canonical_json.canonical_bytes(payload))
    return RuleParameters(**payload, rule_parameters_sha256=digest)
