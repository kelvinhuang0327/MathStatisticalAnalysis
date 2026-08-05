"""BigLotto native-strategy wave 11: thin ports of three frozen legacy
BACKTESTED methods (donor commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``,
the same frozen snapshot as waves 1-10). No algorithm was changed, tuned, or
"improved" during the port.

* ``legacy_biglotto__core_satellite__611284461323`` -- donor
  ``lottery_api/models/core_satellite.py``. A pure random-native 3-ticket
  split: shuffle the full 1-49 pool, the first two shuffled numbers become a
  shared "core" pair on every ticket, and the remaining numbers are sliced
  into three disjoint 4-number "satellite" groups (falling back to a fresh
  sample only if a slice would run past the end of the shuffled pool, which
  never happens for a 49-number pool sliced into three 4-number groups after
  a 2-number core, but is preserved verbatim as a genuine frozen branch).
  Never reads causal history content.
* ``legacy_biglotto__zone_split__b6144f9d479f`` -- donor
  ``lottery_api/models/zone_split.py``. A pure random-native 3-ticket split:
  the 1-49 range is cut into three roughly-equal zones, each zone widened by
  2 numbers on both sides (clamped to 1-49, the last zone absorbing any
  remainder), and one ticket is sampled from each widened zone. Never reads
  causal history content.
* ``legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2`` -- donor
  ``tools/big_lotto_exhaustive_audit.py``. Ranks all 49 numbers by frequency
  over the most recent 50 causal draws (ties keep ascending numeric order,
  matching Python's stable ``sorted``), takes the top-15 ("hot") and
  bottom-15 ("cold") of that ranking, samples one 6-number ticket from each,
  then samples a third ticket from the 37 numbers excluded from both
  samples ("orthogonal"). Requires 50 causal draws; below that the frozen
  source has nothing to rank, matching the shared donor commit's own
  ``min_history=50`` gate.

Donor-exact logic for all three is re-derived inline here rather than
imported from ``lottolab.application.legacy_random_native_portfolios`` /
``lottolab.application.legacy_history_native_portfolios`` (the frozen-source
reference oracles these three were audited against, per
``strategies/data/biglotto_full_strategy_catalog_v1.json``): ``strategies``
importing ``application`` is a structural layer violation
``tests/architecture/test_dependency_rules.py`` forbids, exactly the same
boundary wave 3's docstring documents for its own ``_numpy_argsort`` port.

**Seed protocol.** All three donors are frozen-seeded via a SHA-256 digest
of ``protocol | method_id | source_sha256 | target_draw_number |
replicate_id | user_seed`` (the oracles' own ``_seed`` functions) fed into
``random.Random().seed(seed_integer, version=2)`` -- reproduced verbatim
below via ``_seed_integer``. The oracles' request objects accept an
explicit ``target_draw_number`` (the future draw being predicted); this
framework's ``PortfolioBetAdapter._predict_all(history, lottery_type)``
contract has no such slot. ``_target_after_causal_cutoff`` reproduces wave
8's identical-purpose helper (``biglotto_wave8.py``) to synthesize a
deterministic request identity from the causal history's own last draw --
never the wall clock, a random draw, or any I/O -- so the seed stays a pure
function of ``history`` alone, replicate_id fixed at ``0`` and user_seed
fixed at each oracle's own published default.

None of these three donors has a data-dependent execution-error branch once
``min_history`` is satisfied (unlike, say, wave 9's CAG anchor-companion
``IndexError``): core-satellite's satellite-slice fallback and zone-split's
zone-widening fallback are always large enough for this lottery's fixed
1-49/pick-6 shape, and exhaustive-audit's hot/cold/orthogonal pools (15,
15, 37 candidates against 6-number samples) can never run short. The only
non-``OK`` outcome any of the three can produce is ``InsufficientHistory``,
raised by the shared ``PortfolioBetAdapter`` base once below each
``min_history``.
"""

from __future__ import annotations

import hashlib
import random
from collections import Counter

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6

_RANDOM_NATIVE_PROTOCOL = "legacy_random_native/cpython_mt19937_v1"
_RANDOM_NATIVE_DEFAULT_USER_SEED = "biglotto-full-universe-random-native-v1"
_CORE_SATELLITE_METHOD_ID = "lottery_api/models/core_satellite.py"
_CORE_SATELLITE_SOURCE_SHA256 = "611284461323dbbca0b5959498bf3f0e86bfaa35c4b902fdb64aabfe5076a6e2"
_ZONE_SPLIT_METHOD_ID = "lottery_api/models/zone_split.py"
_ZONE_SPLIT_SOURCE_SHA256 = "b6144f9d479feded3746d81e0d5682e7cfb28ba8d8aa03ff65f3706649996211"
_RANDOM_NATIVE_TICKET_COUNT = 3
_CORE_SIZE = 2
_ZONE_OVERLAP_SIZE = 2

_HISTORY_NATIVE_PROTOCOL = "legacy_history_native/v1"
_HISTORY_NATIVE_DEFAULT_USER_SEED = "biglotto-full-universe-history-native-v1"
_EXHAUSTIVE_AUDIT_METHOD_ID = "tools/big_lotto_exhaustive_audit.py"
_EXHAUSTIVE_AUDIT_SOURCE_SHA256 = "694d353b7ca230af6a860f5ef8977fdecbab031a30ad4e6c51b3d0c0f98b910c"
_EXHAUSTIVE_AUDIT_MINIMUM_HISTORY = 50
_EXHAUSTIVE_AUDIT_WINDOW = 50
_EXHAUSTIVE_AUDIT_POOL_SIZE = 15

_REPLICATE_ID = 0


def _ticket(numbers: list[int]) -> tuple[int, ...]:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(
            type(number) is not int or not _MIN_NUMBER <= number <= _MAX_NUMBER for number in values
        )
    ):
        raise ValueError("FROZEN_WAVE11_INVALID_TICKET")
    return values


def _target_after_causal_cutoff(history: tuple[CausalDrawRow, ...]) -> str:
    """Return a deterministic request identity absent from the causal history.

    See the module docstring's "Seed protocol" section: the frozen donors'
    seed material is keyed off an externally supplied ``target_draw_number``
    this framework's adapter contract has no slot for, so this synthesizes
    one from the causal history's own last draw, exactly reproducing wave
    8's ``_target_after_causal_cutoff`` pattern.
    """
    draw_ids = {row.draw for row in history}
    target = f"{history[-1].draw}:lottolab-wave11-next-target"
    while target in draw_ids:
        target = f"{target}:next"
    return target


def _seed_integer(
    *,
    protocol: str,
    method_id: str,
    source_sha256: str,
    target_draw_number: str,
    user_seed: str,
) -> int:
    """Re-derive the frozen SHA-256 seed-material protocol inline.

    Byte-identical to the reference oracles' own ``_seed`` functions
    (``legacy_random_native_portfolios.py`` / ``legacy_history_native_portfolios.py``),
    copied rather than imported per the module docstring's layer-boundary note.
    """
    material = "|".join(
        (protocol, method_id, source_sha256, target_draw_number, str(_REPLICATE_ID), user_seed)
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return int(digest, 16)


def _core_satellite(rng: random.Random) -> tuple[tuple[int, ...], ...]:
    candidate_pool = list(range(_MIN_NUMBER, _MAX_NUMBER + 1))
    rng.shuffle(candidate_pool)
    core = sorted(candidate_pool[:_CORE_SIZE])
    satellite_pool = candidate_pool[_CORE_SIZE:]
    satellite_count = _PICK_COUNT - _CORE_SIZE
    tickets: list[tuple[int, ...]] = []
    for index in range(_RANDOM_NATIVE_TICKET_COUNT):
        start = index * satellite_count
        end = (index + 1) * satellite_count
        if end > len(satellite_pool):
            satellites = rng.sample(satellite_pool, satellite_count)
        else:
            satellites = satellite_pool[start:end]
        tickets.append(_ticket(core + satellites))
    return tuple(tickets)


def _zone_split(rng: random.Random) -> tuple[tuple[int, ...], ...]:
    full_range = _MAX_NUMBER - _MIN_NUMBER + 1
    zone_size = full_range // _RANDOM_NATIVE_TICKET_COUNT
    tickets: list[tuple[int, ...]] = []
    for index in range(_RANDOM_NATIVE_TICKET_COUNT):
        start = _MIN_NUMBER + index * zone_size
        end = _MIN_NUMBER + (index + 1) * zone_size - 1
        if index == _RANDOM_NATIVE_TICKET_COUNT - 1:
            end = _MAX_NUMBER
        zone_pool = list(
            range(
                max(_MIN_NUMBER, start - _ZONE_OVERLAP_SIZE),
                min(_MAX_NUMBER, end + _ZONE_OVERLAP_SIZE) + 1,
            )
        )
        if len(zone_pool) < _PICK_COUNT:
            zone_pool = list(range(_MIN_NUMBER, _MAX_NUMBER + 1))
        tickets.append(_ticket(rng.sample(zone_pool, _PICK_COUNT)))
    return tuple(tickets)


def _exhaustive_audit(
    history: tuple[CausalDrawRow, ...],
    *,
    seed_integer: int,
) -> tuple[tuple[int, ...], ...]:
    frequency = Counter(
        number for draw in history[-_EXHAUSTIVE_AUDIT_WINDOW:] for number in draw.numbers
    )
    ranked = sorted(
        range(_MIN_NUMBER, _MAX_NUMBER + 1),
        key=lambda number: frequency.get(number, 0),
        reverse=True,
    )
    hot_pool = ranked[:_EXHAUSTIVE_AUDIT_POOL_SIZE]
    cold_pool = ranked[-_EXHAUSTIVE_AUDIT_POOL_SIZE:]
    rng = random.Random()
    rng.seed(seed_integer, version=2)
    hot = rng.sample(hot_pool, _PICK_COUNT)
    cold = rng.sample(cold_pool, _PICK_COUNT)
    used = set(hot) | set(cold)
    candidate_pool = [
        number for number in range(_MIN_NUMBER, _MAX_NUMBER + 1) if number not in used
    ]
    orthogonal = rng.sample(candidate_pool, _PICK_COUNT)
    return (_ticket(hot), _ticket(cold), _ticket(orthogonal))


class BigLottoCoreSatelliteRandomNativeAdapter(PortfolioBetAdapter):
    """Random-native core/satellite 3-ticket split; never reads history
    content, only its own outcome-blind seed derived from the causal
    history's last draw (see module docstring)."""

    strategy_id = "legacy_biglotto__core_satellite__611284461323"
    strategy_name = "大樂透 Core-Satellite（隨機原生3注）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        seed_integer = _seed_integer(
            protocol=_RANDOM_NATIVE_PROTOCOL,
            method_id=_CORE_SATELLITE_METHOD_ID,
            source_sha256=_CORE_SATELLITE_SOURCE_SHA256,
            target_draw_number=_target_after_causal_cutoff(history),
            user_seed=_RANDOM_NATIVE_DEFAULT_USER_SEED,
        )
        rng = random.Random()
        rng.seed(seed_integer, version=2)
        return _core_satellite(rng)


class BigLottoZoneSplitRandomNativeAdapter(PortfolioBetAdapter):
    """Random-native zone-split 3-ticket generator; never reads history
    content, only its own outcome-blind seed derived from the causal
    history's last draw (see module docstring)."""

    strategy_id = "legacy_biglotto__zone_split__b6144f9d479f"
    strategy_name = "大樂透 Zone Split（隨機原生3注）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        seed_integer = _seed_integer(
            protocol=_RANDOM_NATIVE_PROTOCOL,
            method_id=_ZONE_SPLIT_METHOD_ID,
            source_sha256=_ZONE_SPLIT_SOURCE_SHA256,
            target_draw_number=_target_after_causal_cutoff(history),
            user_seed=_RANDOM_NATIVE_DEFAULT_USER_SEED,
        )
        rng = random.Random()
        rng.seed(seed_integer, version=2)
        return _zone_split(rng)


class BigLottoExhaustiveAuditAdapter(PortfolioBetAdapter):
    """History-native hot/cold/orthogonal 3-ticket audit over the trailing
    50 causal draws; requires 50 causal draws (see module docstring)."""

    strategy_id = "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2"
    strategy_name = "大樂透窮舉稽核（熱/冷/正交3注）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = _EXHAUSTIVE_AUDIT_MINIMUM_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        seed_integer = _seed_integer(
            protocol=_HISTORY_NATIVE_PROTOCOL,
            method_id=_EXHAUSTIVE_AUDIT_METHOD_ID,
            source_sha256=_EXHAUSTIVE_AUDIT_SOURCE_SHA256,
            target_draw_number=_target_after_causal_cutoff(history),
            user_seed=_HISTORY_NATIVE_DEFAULT_USER_SEED,
        )
        return _exhaustive_audit(history, seed_integer=seed_integer)


__all__ = [
    "BigLottoCoreSatelliteRandomNativeAdapter",
    "BigLottoExhaustiveAuditAdapter",
    "BigLottoZoneSplitRandomNativeAdapter",
]
