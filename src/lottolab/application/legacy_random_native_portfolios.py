"""Deterministic ports of frozen random-native BIG_LOTTO portfolios.

The frozen sources use module-global ``random`` without a seed.  This module
preserves their CPython shuffle/sample call order and native three-ticket
ordering while adding an explicit outcome-blind seed protocol.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass

from lottolab.application.strategy_preserving_20_ticket import Ticket

RANDOM_NATIVE_PROTOCOL = "legacy_random_native/cpython_mt19937_v1"
DEFAULT_USER_SEED = "biglotto-full-universe-random-native-v1"
CORE_SATELLITE_METHOD_ID = "lottery_api/models/core_satellite.py"
ZONE_SPLIT_METHOD_ID = "lottery_api/models/zone_split.py"
CORE_SATELLITE_SOURCE_SHA256 = (
    "611284461323dbbca0b5959498bf3f0e86bfaa35c4b902fdb64aabfe5076a6e2"
)
ZONE_SPLIT_SOURCE_SHA256 = (
    "b6144f9d479feded3746d81e0d5682e7cfb28ba8d8aa03ff65f3706649996211"
)
SUPPORTED_RANDOM_NATIVE_METHODS = (
    CORE_SATELLITE_METHOD_ID,
    ZONE_SPLIT_METHOD_ID,
)
_SOURCE_SHA256_BY_METHOD = {
    CORE_SATELLITE_METHOD_ID: CORE_SATELLITE_SOURCE_SHA256,
    ZONE_SPLIT_METHOD_ID: ZONE_SPLIT_SOURCE_SHA256,
}
_NATIVE_TICKET_COUNT = 3
_PICK_COUNT = 6
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_CORE_SIZE = 2
_ZONE_OVERLAP_SIZE = 2


class LegacyRandomNativeError(ValueError):
    """A request cannot satisfy the frozen random-native strategy contract."""


@dataclass(frozen=True, slots=True)
class LegacyRandomNativeRequest:
    legacy_method_id: str
    target_draw_number: str
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacyRandomNativeMetadata:
    protocol: str
    legacy_method_id: str
    source_sha256: str
    target_draw_number: str
    replicate_id: int
    user_seed: str | int
    seed_material: str
    seed_digest: str
    seed_integer: int
    native_ticket_count: int
    native_ticket_order: str
    native_duplicate_ticket_count: int
    candidate_k: None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacyRandomNativeResult:
    tickets: tuple[Ticket, ...]
    metadata: LegacyRandomNativeMetadata


def _ticket(numbers: list[int]) -> Ticket:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(not _MIN_NUMBER <= number <= _MAX_NUMBER for number in values)
    ):
        raise LegacyRandomNativeError("frozen strategy emitted an invalid ticket")
    return values


def _seed(request: LegacyRandomNativeRequest) -> tuple[str, str, int]:
    if request.legacy_method_id not in _SOURCE_SHA256_BY_METHOD:
        raise LegacyRandomNativeError("legacy method is outside the random-native batch")
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacyRandomNativeError("target draw number must be non-empty")
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacyRandomNativeError("replicate_id must be a non-negative integer")
    if type(request.user_seed) not in (str, int):
        raise LegacyRandomNativeError("user_seed must be a string or integer")
    source_sha256 = _SOURCE_SHA256_BY_METHOD[request.legacy_method_id]
    material = "|".join(
        (
            RANDOM_NATIVE_PROTOCOL,
            request.legacy_method_id,
            source_sha256,
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _core_satellite(rng: random.Random) -> tuple[Ticket, ...]:
    candidate_pool = list(range(_MIN_NUMBER, _MAX_NUMBER + 1))
    rng.shuffle(candidate_pool)
    core = sorted(candidate_pool[:_CORE_SIZE])
    satellite_pool = candidate_pool[_CORE_SIZE:]
    satellite_count = _PICK_COUNT - _CORE_SIZE
    tickets: list[Ticket] = []
    for index in range(_NATIVE_TICKET_COUNT):
        start = index * satellite_count
        end = (index + 1) * satellite_count
        if end > len(satellite_pool):
            satellites = rng.sample(satellite_pool, satellite_count)
        else:
            satellites = satellite_pool[start:end]
        tickets.append(_ticket(core + satellites))
    return tuple(tickets)


def _zone_split(rng: random.Random) -> tuple[Ticket, ...]:
    full_range = _MAX_NUMBER - _MIN_NUMBER + 1
    zone_size = full_range // _NATIVE_TICKET_COUNT
    tickets: list[Ticket] = []
    for index in range(_NATIVE_TICKET_COUNT):
        start = _MIN_NUMBER + index * zone_size
        end = _MIN_NUMBER + (index + 1) * zone_size - 1
        if index == _NATIVE_TICKET_COUNT - 1:
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


def generate_legacy_random_native_portfolio(
    request: LegacyRandomNativeRequest,
) -> LegacyRandomNativeResult:
    """Return source-ordered native tickets without history or target outcome."""

    seed_material, seed_digest, seed_integer = _seed(request)
    rng = random.Random()
    rng.seed(seed_integer, version=2)
    if request.legacy_method_id == CORE_SATELLITE_METHOD_ID:
        tickets = _core_satellite(rng)
    else:
        tickets = _zone_split(rng)
    return LegacyRandomNativeResult(
        tickets=tickets,
        metadata=LegacyRandomNativeMetadata(
            protocol=RANDOM_NATIVE_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=_SOURCE_SHA256_BY_METHOD[request.legacy_method_id],
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            native_ticket_count=len(tickets),
            native_ticket_order="FROZEN_FACTORY_BET_ORDER",
            native_duplicate_ticket_count=len(tickets) - len(set(tickets)),
            candidate_k=None,
            combination_count=None,
        ),
    )


__all__ = [
    "CORE_SATELLITE_METHOD_ID",
    "CORE_SATELLITE_SOURCE_SHA256",
    "DEFAULT_USER_SEED",
    "RANDOM_NATIVE_PROTOCOL",
    "SUPPORTED_RANDOM_NATIVE_METHODS",
    "ZONE_SPLIT_METHOD_ID",
    "ZONE_SPLIT_SOURCE_SHA256",
    "LegacyRandomNativeError",
    "LegacyRandomNativeMetadata",
    "LegacyRandomNativeRequest",
    "LegacyRandomNativeResult",
    "generate_legacy_random_native_portfolio",
]
