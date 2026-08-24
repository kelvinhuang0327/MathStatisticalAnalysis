"""Frozen BigLotto Bayes + temporal-profile clustering union candidates.

This research-only module binds the exact nine V1 parent pairs selected by the
authoritative semantic freeze.  Each parent independently produces its native
matched-K portfolio from the same strictly-prior history.  Composition removes
only exact whole-ticket duplicates and returns every remaining ticket in global
lexicographic order.  There is no scoring, truncation, padding, randomness,
database access, current-date access, outcome access, catalog wiring, or forward
registration.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import islice, pairwise
from pathlib import Path
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import (
    biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate_batch_r1 as _bayes,
)
from lottolab.research import (
    biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1 as _cluster,
)

type Ticket = tuple[int, int, int, int, int, int]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type TicketPortfolio = tuple[Ticket, ...]

TASK_ID: Final[str] = (
    "BIGLOTTO_CROSS_FAMILY_R2_BAYES_CLUSTER_UNION_V1_CANDIDATE_BATCH_R1"
)
HYPOTHESIS_ID: Final[str] = (
    "BIGLOTTO_R2_H_BAYESIAN_CLUSTERING_UNIQUE_SUCCESS_UNION"
)
FAMILY_ID: Final[str] = "B649_BAYES_CLUSTER_UNION"
SEMANTIC_VERSION: Final[str] = "B649_BAYES_CLUSTER_UNION_V1_41e6eefa2cbe0006"
COMMON_SEMANTICS_SIGNATURE_HASH: Final[str] = (
    "41e6eefa2cbe000611bf5641d470f0b84b14045623035c703ee415bb572bca70"
)
IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research."
    "biglotto_cross_family_r2_bayes_cluster_union_v1_candidate_batch_r1"
)
IMPLEMENTATION_SOURCE_IDENTITY: Final[str] = (
    f"{IMPLEMENTATION_MODULE}:produce_candidate_portfolio"
)

LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
MINIMUM_HISTORY: Final[int] = 750
CAUSAL_CUTOFF_RULE: Final[str] = "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
PARENT_OUTPUT_BINDING: Final[str] = "POST_BUDGET_NATIVE_PARENT_PORTFOLIO"
CARDINALITY_MODE: Final[str] = "FULL_DEDUPLICATED_UNION"
EXACT_TICKET_DEDUP: Final[str] = "YES"
NUMBER_LEVEL_DEDUP: Final[str] = "NO"
FINAL_CARDINALITY_RULE: Final[str] = "K_THROUGH_2K"
OUTPUT_ORDER: Final[str] = (
    "LEXICOGRAPHIC_ASCENDING_UNIQUE_CANONICAL_TICKET_TUPLES"
)
TRUNCATION: Final[str] = "NONE"
PADDING: Final[str] = "NONE"
OVERFLOW_RULE: Final[str] = "NOT_APPLICABLE"
UNDERFLOW_RULE: Final[str] = "NOT_APPLICABLE"
RNG: Final[str] = "NONE"
FALLBACK: Final[str] = "FAIL_CLOSED"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"

CONSTRUCTORS: Final[tuple[str, str, str]] = (
    "LOW_OVERLAP",
    "EXPOSURE_BALANCED",
    "HYBRID_DIVERSITY",
)
CONSTRUCTOR_IDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "LOW_OVERLAP": "B649_CANDIDATE_SET_LOW_OVERLAP_V1",
        "EXPOSURE_BALANCED": "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
        "HYBRID_DIVERSITY": "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1",
    }
)
MATCHED_K_VALUES: Final[tuple[int, int, int]] = (5, 10, 20)

BAYES_PARENT_FAMILY: Final[str] = "MULTISCALE_BAYES_CHANGEPOINT_BMA"
CLUSTER_PARENT_FAMILY: Final[str] = "TEMPORAL_PROFILE_CLUSTERING"
BAYES_PARENT_AUTHORITY_ROOT: Final[str] = (
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "BIGLOTTO_MULTISCALE_BAYES_CHANGEPOINT_BMA_MULTI_TICKET_CANDIDATE_BATCH_R1"
)
CLUSTER_PARENT_AUTHORITY_ROOT: Final[str] = (
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "BIGLOTTO_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MULTI_TICKET_CANDIDATE_BATCH_R1"
)
FINAL_SEMANTICS_ROOT: Final[str] = (
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "BIGLOTTO_CROSS_FAMILY_R2_BAYES_CLUSTER_UNION_FINAL_SEMANTICS_FREEZE_R1"
)
DISCOVERY_CUTOFF_DRAW: Final[int] = 115000073

SEMANTIC_AUTHORITY_SHA256SUMS_SHA256: Final[str] = (
    "9b03972bcf1c5c61dd70085d077a0b20c6335fc050e4ce5f5e80648143716821"
)
BAYES_AUTHORITY_SHA256SUMS_SHA256: Final[str] = (
    "76662e072e9c9950f126b0a49218ef16ee5da722f9296681953fdb94fc7fdc73"
)
CLUSTER_AUTHORITY_SHA256SUMS_SHA256: Final[str] = (
    "0b293ab4491969f82234b238868488f82ec809e28587838e103deedb84905cd7"
)
BAYES_PARENT_IMPLEMENTATION_COMMIT: Final[str] = (
    "7845d0296a2512ec6d8bdc82d208057c06f732c7"
)
BAYES_PARENT_IMPLEMENTATION_TREE: Final[str] = (
    "22b1096fa54cbc5ff248591f51e434746a60bd68"
)
BAYES_PARENT_PRODUCER_BLOB: Final[str] = (
    "420ac4331386f9837cd2c7abe85ee1cec93627e9"
)
BAYES_PARENT_PRODUCER_SHA256: Final[str] = (
    "b4a2b5263e0888cad33e17f2e080d157269436baf610e53677e4de7a6566798e"
)
CLUSTER_PARENT_IMPLEMENTATION_COMMIT: Final[str] = (
    "ee8d5299c71e3b0f60e211b815fff1b33c853c57"
)
CLUSTER_PARENT_IMPLEMENTATION_TREE: Final[str] = (
    "1e6b178ff8286c32448289a9dde2e377b90c97d7"
)
CLUSTER_PARENT_PRODUCER_BLOB: Final[str] = (
    "dfa41c1248c716268c85c726a46be44741d0dc6a"
)
CLUSTER_PARENT_PRODUCER_SHA256: Final[str] = (
    "6c40d127a68c47f70cf5cc2d2873cd2c98a758aa5636e87446f2211b35392a24"
)
SHARED_CONSTRUCTOR_BLOB: Final[str] = "c5025b01d8ab1bcd1a706c09bd839cc80b9873c0"
SHARED_CONSTRUCTOR_SHA256: Final[str] = (
    "970a9a1215b9c08cf5f2192073692761cc218b8bfea4051abb3aa5222e8cc2d2"
)

SEMANTIC_AUTHORITY_FILE_SHA256: Final[Mapping[str, str]] = MappingProxyType(
    {
        "cardinality_contract.json": (
            "4ffc4f84b5c5f9c9d9dda5345beb9508a393630b59dccd9acd156e15f59e9e67"
        ),
        "candidate_variant_matrix.csv": (
            "eafc3ada91de53b60d7f1a8f8ef683b8648054a67e67dff3dc064846f20f4cb3"
        ),
        "contamination_boundary.json": (
            "f9fc3b82b54afcc77f62d83efa89079cabcde7de4051820c9103d1f551122a7f"
        ),
        "final_semantics.json": (
            "2bcfc84f3b51c7a7229205fabacfc362341bb95918ad3ba924ea46b29ebe43f1"
        ),
        "final_semantics.md": (
            "830d88ffd2ff8087cd750ca553082bf37deba758bfe4ca3d3d3299719ec2f066"
        ),
        "implementation_handoff.json": (
            "e97f9d05f020871745d2fc2b53db47e50ed1cd79fa492f935ac352c2f566b5f4"
        ),
        "ordering_and_tiebreak_contract.json": (
            "89d1970e9fa8e2f753af77b2c3f341144d5e64c0b94226c3742e5316c2c28485"
        ),
        "owner_cardinality_decision_snapshot.json": (
            "414d824f86b35205ae25a3135755c6308b9c81854fa61612b3adba0b70fad517"
        ),
        "parent_binding_contract.json": (
            "935d3f86fab1efaf77920c6d23c39c3c53bd72698b159ab3611b6268afe60dfa"
        ),
        "run_manifest.json": (
            "63051787684451aa0097ebfefd54977054d05dedc63b5d82ae5ebcc7980089ad"
        ),
    }
)


class AuthorityMismatchError(ValueError):
    """Raised when frozen candidate or parent identity material does not match."""


class InsufficientHistoryError(ValueError):
    """Raised when fewer than 750 strictly-prior draws are supplied."""


@dataclass(frozen=True, slots=True)
class CandidateMetadata:
    """Exact frozen identity and post-budget parent binding for one candidate."""

    MATRIX_INDEX: int
    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CONSTRUCTOR: str
    CONSTRUCTOR_ID: str
    MATCHED_K: int
    PARENT_A_CANDIDATE_ID: str
    PARENT_A_SIGNATURE_HASH: str
    PARENT_B_CANDIDATE_ID: str
    PARENT_B_SIGNATURE_HASH: str


_CANDIDATE_ROWS: Final[tuple[tuple[object, ...], ...]] = (
    (
        1,
        "BMSGV1_BCU_4e7d61f26f300458",
        "4e7d61f26f3004585a8e90474efff094ef8d4b47b804ecc2c85d7fbc5b526574",
        "LOW_OVERLAP",
        5,
        "BMSGV1_BY_c5baba803a5b02b2",
        "c5baba803a5b02b2237f12396d9704257766bc38c312a895b69bc70c749b874a",
        "BMSGV1_CL_87042665810ec02e",
        "87042665810ec02ec623eb1ac7e797a5bbc2ff3dd470b1554898c8308c58db10",
    ),
    (
        2,
        "BMSGV1_BCU_6d1c587273d742e3",
        "6d1c587273d742e33373616914388a03525160144be432a073ea058be246f56a",
        "LOW_OVERLAP",
        10,
        "BMSGV1_BY_2d6a81202848d0dc",
        "2d6a81202848d0dcae17519a570b60fba21e5a7ed894749419f1196850132f4b",
        "BMSGV1_CL_00fcf892ae80281e",
        "00fcf892ae80281e9339e87f1816c38d9605d61f29f93f3aef090d42f1a325c5",
    ),
    (
        3,
        "BMSGV1_BCU_7f162cc77d7e46e5",
        "7f162cc77d7e46e59c2a46672dddcca8020d1811c1d5a0a5438adff63279676a",
        "LOW_OVERLAP",
        20,
        "BMSGV1_BY_88b5bf7d96119f7e",
        "88b5bf7d96119f7ebcfd1a02dfce8bb62fab543c4faf332a5b5d665937fa10e9",
        "BMSGV1_CL_921b703832dc3a71",
        "921b703832dc3a715d702b80a6a02e3efd344244bec0f3f3f90cc0eba5064853",
    ),
    (
        4,
        "BMSGV1_BCU_5d32cca92cf6c7ea",
        "5d32cca92cf6c7eac0bc16e52b80dc0a185b8a540b33be7f83bdf56ebd49d0cc",
        "EXPOSURE_BALANCED",
        5,
        "BMSGV1_BY_e5cf21a37b8aa958",
        "e5cf21a37b8aa9587603ac8304c6c07077c800de4a144a6d2bfa47e1209b0c60",
        "BMSGV1_CL_7296027ce0f0fc75",
        "7296027ce0f0fc7518eb77c76bf7b25cecc20859adb0ed3ca6250ad495d7e96a",
    ),
    (
        5,
        "BMSGV1_BCU_052424120e14ec66",
        "052424120e14ec666a835894eced835ce0410a55e0f82ec46590a23dceeeebba",
        "EXPOSURE_BALANCED",
        10,
        "BMSGV1_BY_7c0307f6bbcd9e11",
        "7c0307f6bbcd9e117ef23955a42c1d9616a3ca4b5f575ab3e8f148dbe81553c7",
        "BMSGV1_CL_d07a0be23e8057a3",
        "d07a0be23e8057a381649a18f3a7ab229175e6c16ff2b5bdb695095cc4e66d3a",
    ),
    (
        6,
        "BMSGV1_BCU_d45edd29a192b37d",
        "d45edd29a192b37d73ab125cf6c991bd6d03371b530c72aeea6e1c286aa9db70",
        "EXPOSURE_BALANCED",
        20,
        "BMSGV1_BY_ab3fbabb0bfe27c3",
        "ab3fbabb0bfe27c3e912f63a34205157459461006ac94b1114665da39f8adadd",
        "BMSGV1_CL_2b9226c777b5110d",
        "2b9226c777b5110d9f85f7e5fb410c03556a1943d250f729b68b0e28bf898674",
    ),
    (
        7,
        "BMSGV1_BCU_636542e0273b2706",
        "636542e0273b27061a90d9d3e9f84324840aecbc956f899a4d28a26076d8a1ae",
        "HYBRID_DIVERSITY",
        5,
        "BMSGV1_BY_c74d0be13ed84609",
        "c74d0be13ed84609e29192131222ece975729ba4f88d74fd20eab2c128dc6b44",
        "BMSGV1_CL_85ad12e9aea85ca6",
        "85ad12e9aea85ca6b9f56cbf96ddb83e30d3f5d7f90d664f77c1e1225504e387",
    ),
    (
        8,
        "BMSGV1_BCU_e57e85d0095f138e",
        "e57e85d0095f138e6b2e249075de9dbee1e2a3520c4d525d74d3b0f53763d44d",
        "HYBRID_DIVERSITY",
        10,
        "BMSGV1_BY_83004ab5716e2b4f",
        "83004ab5716e2b4fcb4222dfeabcfe8c9232bb6f83c01afe3434e8df976db752",
        "BMSGV1_CL_b4b88dc1416e46e9",
        "b4b88dc1416e46e92a46fb6b69fe56697313acd426b9d22dc8428a681e385262",
    ),
    (
        9,
        "BMSGV1_BCU_44934fb9b3c30499",
        "44934fb9b3c30499ae36dfe41f11100645c5e5890b3f5edf18bfbc4c52d1d445",
        "HYBRID_DIVERSITY",
        20,
        "BMSGV1_BY_6bfe10141393a016",
        "6bfe10141393a016a1dec3526b2616095607614b5fed9f9cac1afc6a259718f2",
        "BMSGV1_CL_7b825e5de2dd1c4b",
        "7b825e5de2dd1c4be0def6985b7f23e3964573f6626ca07ea8ba91bec2c795e1",
    ),
)


def _build_candidate_authority() -> tuple[
    tuple[CandidateMetadata, ...], Mapping[str, CandidateMetadata]
]:
    candidates: list[CandidateMetadata] = []
    by_id: dict[str, CandidateMetadata] = {}
    for row in _CANDIDATE_ROWS:
        (
            matrix_index,
            candidate_id,
            signature_hash,
            constructor,
            matched_k,
            parent_a_id,
            parent_a_hash,
            parent_b_id,
            parent_b_hash,
        ) = row
        metadata = CandidateMetadata(
            MATRIX_INDEX=cast(int, matrix_index),
            CANDIDATE_ID=cast(str, candidate_id),
            SIGNATURE_HASH=cast(str, signature_hash),
            CONSTRUCTOR=constructor,
            CONSTRUCTOR_ID=CONSTRUCTOR_IDS[constructor],
            MATCHED_K=cast(int, matched_k),
            PARENT_A_CANDIDATE_ID=cast(str, parent_a_id),
            PARENT_A_SIGNATURE_HASH=cast(str, parent_a_hash),
            PARENT_B_CANDIDATE_ID=cast(str, parent_b_id),
            PARENT_B_SIGNATURE_HASH=cast(str, parent_b_hash),
        )
        if metadata.CANDIDATE_ID in by_id:
            raise RuntimeError("duplicate frozen union candidate ID")
        candidates.append(metadata)
        by_id[metadata.CANDIDATE_ID] = metadata
    return tuple(candidates), MappingProxyType(by_id)


CANDIDATE_AUTHORITIES, CANDIDATE_METADATA = _build_candidate_authority()
CANDIDATE_IDS: Final[tuple[str, ...]] = tuple(
    metadata.CANDIDATE_ID for metadata in CANDIDATE_AUTHORITIES
)
CANDIDATE_SIGNATURE_HASHES: Final[tuple[str, ...]] = tuple(
    metadata.SIGNATURE_HASH for metadata in CANDIDATE_AUTHORITIES
)


def validate_frozen_parent_authority() -> None:
    """Fail closed unless all nine exact parent IDs and signatures are present."""

    if len(CANDIDATE_AUTHORITIES) != 9:
        raise AuthorityMismatchError("frozen union authority must contain exactly 9 candidates")
    if tuple(metadata.MATRIX_INDEX for metadata in CANDIDATE_AUTHORITIES) != tuple(
        range(1, 10)
    ):
        raise AuthorityMismatchError("frozen union matrix indexes must be exactly 1 through 9")
    expected_pairs = tuple(
        (constructor, matched_k)
        for constructor in CONSTRUCTORS
        for matched_k in MATCHED_K_VALUES
    )
    actual_pairs = tuple(
        (metadata.CONSTRUCTOR, metadata.MATCHED_K)
        for metadata in CANDIDATE_AUTHORITIES
    )
    if actual_pairs != expected_pairs:
        raise AuthorityMismatchError("frozen constructor and matched-K matrix is not exact")
    if len(set(CANDIDATE_IDS)) != 9 or len(set(CANDIDATE_SIGNATURE_HASHES)) != 9:
        raise AuthorityMismatchError("frozen union identities are not unique")
    if _bayes.MINIMUM_HISTORY != MINIMUM_HISTORY:
        raise AuthorityMismatchError("Bayesian parent minimum history mismatch")
    if _cluster.MINIMUM_HISTORY != MINIMUM_HISTORY:
        raise AuthorityMismatchError("Clustering parent minimum history mismatch")

    for metadata in CANDIDATE_AUTHORITIES:
        bayes_metadata = _bayes.CANDIDATE_METADATA.get(
            metadata.PARENT_A_CANDIDATE_ID
        )
        if bayes_metadata is None:
            raise AuthorityMismatchError(
                f"Bayesian parent is unavailable: {metadata.PARENT_A_CANDIDATE_ID}"
            )
        if (
            bayes_metadata.SIGNATURE_HASH != metadata.PARENT_A_SIGNATURE_HASH
            or bayes_metadata.CONSTRUCTOR_ID != metadata.CONSTRUCTOR_ID
            or bayes_metadata.TICKET_COUNT != metadata.MATCHED_K
        ):
            raise AuthorityMismatchError(
                f"Bayesian parent identity mismatch: {metadata.PARENT_A_CANDIDATE_ID}"
            )

        cluster_metadata = _cluster.CANDIDATE_METADATA.get(
            metadata.PARENT_B_CANDIDATE_ID
        )
        if cluster_metadata is None:
            raise AuthorityMismatchError(
                f"Clustering parent is unavailable: {metadata.PARENT_B_CANDIDATE_ID}"
            )
        if (
            cluster_metadata.SIGNATURE_HASH != metadata.PARENT_B_SIGNATURE_HASH
            or cluster_metadata.CONSTRUCTOR_ID != metadata.CONSTRUCTOR_ID
            or cluster_metadata.TICKET_COUNT != metadata.MATCHED_K
        ):
            raise AuthorityMismatchError(
                f"Clustering parent identity mismatch: {metadata.PARENT_B_CANDIDATE_ID}"
            )


validate_frozen_parent_authority()


def _metadata_for_candidate(candidate_id: object) -> CandidateMetadata:
    if not isinstance(candidate_id, str):
        raise TypeError("candidate_id must be a string")
    try:
        return CANDIDATE_METADATA[candidate_id]
    except KeyError as error:
        raise KeyError(f"unknown frozen candidate ID: {candidate_id!r}") from error


def _read_prior_prefix(history: HistoryInput, target_index: int) -> tuple[object, ...]:
    if type(target_index) is not int or target_index < 0:
        raise ValueError("target_index must be a non-negative integer")
    if target_index < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"target_index provides {target_index} strictly prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    try:
        if isinstance(history, Sequence):
            if target_index > len(history):
                raise ValueError("target_index must not exceed history length")
            return tuple(history[:target_index])
        prefix = tuple(islice(iter(history), target_index))
        if len(prefix) != target_index:
            raise ValueError("target_index must not exceed history length")
        return prefix
    except ValueError:
        raise
    except (IndexError, TypeError) as error:
        raise ValueError("history must supply a finite chronological prefix") from error


def _validate_ticket(raw_ticket: object, location: str) -> Ticket:
    if type(raw_ticket) is not tuple:
        raise ValueError(f"{location} must be an immutable tuple")
    values = cast(tuple[object, ...], raw_ticket)
    if len(values) != PICK_COUNT:
        raise ValueError(f"{location} must contain exactly {PICK_COUNT} numbers")
    if not all(type(number) is int for number in values):
        raise ValueError(f"{location} must contain built-in integers, not booleans")
    ticket = cast(Ticket, values)
    if any(number < NUMBER_DOMAIN[0] or number > NUMBER_DOMAIN[1] for number in ticket):
        raise ValueError(f"{location} contains a number outside 1..49")
    if any(left >= right for left, right in pairwise(ticket)):
        raise ValueError(f"{location} must be strictly ascending with unique numbers")
    return ticket


def _validate_parent_portfolio(
    raw_portfolio: object, parent_name: str, matched_k: int
) -> TicketPortfolio:
    if type(raw_portfolio) is not tuple:
        raise ValueError(f"{parent_name} portfolio must be an immutable tuple")
    raw_tickets = cast(tuple[object, ...], raw_portfolio)
    if len(raw_tickets) != matched_k:
        raise ValueError(
            f"{parent_name} portfolio must contain exactly {matched_k} tickets; "
            f"received {len(raw_tickets)}"
        )
    tickets = tuple(
        _validate_ticket(raw_ticket, f"{parent_name}[{index}]")
        for index, raw_ticket in enumerate(raw_tickets)
    )
    if len(set(tickets)) != matched_k:
        raise ValueError(f"{parent_name} portfolio must contain exactly K unique tickets")
    return tickets


@dataclass(frozen=True, slots=True)
class TicketProvenance:
    """Ordered parent provenance for one final exact ticket."""

    TICKET: Ticket
    PARENTS: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidatePortfolio:
    """One fully validated frozen union generation."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CONSTRUCTOR: str
    MATCHED_K: int
    PARENT_A_CANDIDATE_ID: str
    PARENT_B_CANDIDATE_ID: str
    PARENT_A_TICKETS: TicketPortfolio
    PARENT_B_TICKETS: TicketPortfolio
    TICKETS: TicketPortfolio
    PROVENANCE: tuple[TicketProvenance, ...]

    @property
    def FINAL_CARDINALITY(self) -> int:
        return len(self.TICKETS)

    @property
    def EXACT_DUPLICATE_COUNT(self) -> int:
        return (2 * self.MATCHED_K) - self.FINAL_CARDINALITY


def compose_full_deduplicated_union(
    parent_a_portfolio: object,
    parent_b_portfolio: object,
    matched_k: int,
) -> tuple[TicketPortfolio, tuple[TicketProvenance, ...]]:
    """Return the full exact-ticket union in frozen global lexicographic order."""

    if type(matched_k) is not int or matched_k not in MATCHED_K_VALUES:
        raise ValueError(f"matched_k must be one of {MATCHED_K_VALUES}")
    parent_a = _validate_parent_portfolio(
        parent_a_portfolio, "PARENT_A_BAYESIAN", matched_k
    )
    parent_b = _validate_parent_portfolio(
        parent_b_portfolio, "PARENT_B_CLUSTERING", matched_k
    )
    tickets = tuple(sorted(set(parent_a) | set(parent_b)))
    if not matched_k <= len(tickets) <= 2 * matched_k:
        raise ValueError("final union cardinality must be between K and 2K")
    provenance: list[TicketProvenance] = []
    parent_a_set = set(parent_a)
    parent_b_set = set(parent_b)
    for ticket in tickets:
        parents: list[str] = []
        if ticket in parent_a_set:
            parents.append("PARENT_A_BAYESIAN")
        if ticket in parent_b_set:
            parents.append("PARENT_B_CLUSTERING")
        provenance.append(TicketProvenance(TICKET=ticket, PARENTS=tuple(parents)))
    return tickets, tuple(provenance)


def build_candidate_portfolio(
    candidate_id: str, history: HistoryInput, target_index: int
) -> CandidatePortfolio:
    """Generate one exact frozen candidate from identical strictly-prior history."""

    metadata = _metadata_for_candidate(candidate_id)
    validate_frozen_parent_authority()
    prior_history = _read_prior_prefix(history, target_index)
    parent_a = _bayes.produce_biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate(
        metadata.PARENT_A_CANDIDATE_ID,
        prior_history,
        target_index,
    )
    parent_b = _cluster.produce_candidate_portfolio(
        metadata.PARENT_B_CANDIDATE_ID,
        prior_history,
        target_index,
    )
    validated_a = _validate_parent_portfolio(
        parent_a, "PARENT_A_BAYESIAN", metadata.MATCHED_K
    )
    validated_b = _validate_parent_portfolio(
        parent_b, "PARENT_B_CLUSTERING", metadata.MATCHED_K
    )
    tickets, provenance = compose_full_deduplicated_union(
        validated_a, validated_b, metadata.MATCHED_K
    )
    return CandidatePortfolio(
        CANDIDATE_ID=metadata.CANDIDATE_ID,
        SIGNATURE_HASH=metadata.SIGNATURE_HASH,
        CONSTRUCTOR=metadata.CONSTRUCTOR,
        MATCHED_K=metadata.MATCHED_K,
        PARENT_A_CANDIDATE_ID=metadata.PARENT_A_CANDIDATE_ID,
        PARENT_B_CANDIDATE_ID=metadata.PARENT_B_CANDIDATE_ID,
        PARENT_A_TICKETS=validated_a,
        PARENT_B_TICKETS=validated_b,
        TICKETS=tickets,
        PROVENANCE=provenance,
    )


def produce_candidate_portfolio(
    candidate_id: str, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Return one frozen native union portfolio."""

    return build_candidate_portfolio(candidate_id, history, target_index).TICKETS


produce_biglotto_cross_family_r2_bayes_cluster_union_v1_candidate = (
    produce_candidate_portfolio
)


def _ticket_json(ticket: Ticket) -> list[int]:
    return list(ticket)


def candidate_portfolio_payload(portfolio: CandidatePortfolio) -> dict[str, object]:
    """Return the complete canonical-serialization payload for one candidate."""

    return {
        "CANDIDATE_ID": portfolio.CANDIDATE_ID,
        "SIGNATURE_HASH": portfolio.SIGNATURE_HASH,
        "SEMANTIC_VERSION": SEMANTIC_VERSION,
        "CONSTRUCTOR": portfolio.CONSTRUCTOR,
        "MATCHED_K": portfolio.MATCHED_K,
        "CARDINALITY_MODE": CARDINALITY_MODE,
        "PARENT_A": {
            "FAMILY": BAYES_PARENT_FAMILY,
            "CANDIDATE_ID": portfolio.PARENT_A_CANDIDATE_ID,
            "TICKETS": [_ticket_json(ticket) for ticket in portfolio.PARENT_A_TICKETS],
        },
        "PARENT_B": {
            "FAMILY": CLUSTER_PARENT_FAMILY,
            "CANDIDATE_ID": portfolio.PARENT_B_CANDIDATE_ID,
            "TICKETS": [_ticket_json(ticket) for ticket in portfolio.PARENT_B_TICKETS],
        },
        "FINAL_TICKETS": [_ticket_json(ticket) for ticket in portfolio.TICKETS],
        "FINAL_CARDINALITY": portfolio.FINAL_CARDINALITY,
        "EXACT_DUPLICATE_COUNT": portfolio.EXACT_DUPLICATE_COUNT,
        "PROVENANCE": [
            {
                "TICKET": _ticket_json(item.TICKET),
                "PARENTS": list(item.PARENTS),
            }
            for item in portfolio.PROVENANCE
        ],
        "OUTPUT_ORDER": OUTPUT_ORDER,
        "TRUNCATION": TRUNCATION,
        "PADDING": PADDING,
        "RNG": RNG,
    }


def canonical_json_bytes(payload: object, *, pretty: bool = False) -> bytes:
    """Serialize JSON-ready data deterministically as UTF-8 with one final newline."""

    if pretty:
        text = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
    else:
        text = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return (text + "\n").encode("utf-8")


SYNTHETIC_FIXTURE_ID: Final[str] = "B649_NON_OUTCOME_SLIDING_SIX_V1"


def build_synthetic_non_outcome_history() -> tuple[HistoryDraw, ...]:
    """Build a fixed 750-draw structural fixture containing no lottery outcomes."""

    draws: list[HistoryDraw] = []
    for draw_index in range(MINIMUM_HISTORY):
        start = (draw_index % 44) + 1
        draws.append(cast(HistoryDraw, tuple(range(start, start + PICK_COUNT))))
    return tuple(draws)


def _synthetic_history_sha256(history: Sequence[HistoryDraw]) -> str:
    return hashlib.sha256(canonical_json_bytes([list(draw) for draw in history])).hexdigest()


def build_synthetic_candidate_batch_payload() -> dict[str, object]:
    """Generate all nine candidates against the frozen non-outcome fixture."""

    history = build_synthetic_non_outcome_history()
    generations = tuple(
        build_candidate_portfolio(candidate_id, history, len(history))
        for candidate_id in CANDIDATE_IDS
    )
    candidate_payloads = [candidate_portfolio_payload(item) for item in generations]
    return {
        "SCHEMA_VERSION": "B649_BAYES_CLUSTER_UNION_V1_CANDIDATE_BATCH_V1",
        "TASK_ID": TASK_ID,
        "HYPOTHESIS": HYPOTHESIS_ID,
        "SEMANTIC_VERSION": SEMANTIC_VERSION,
        "CANDIDATE_COUNT": len(candidate_payloads),
        "CARDINALITY_MODE": CARDINALITY_MODE,
        "FIXTURE": {
            "FIXTURE_ID": SYNTHETIC_FIXTURE_ID,
            "KIND": "SYNTHETIC_NON_OUTCOME",
            "DRAW_COUNT": len(history),
            "TARGET_INDEX": len(history),
            "SHA256": _synthetic_history_sha256(history),
        },
        "CANDIDATES": candidate_payloads,
        "SCORING": "NOT_RUN",
        "HISTORICAL_CONFIRMATION": "NOT_RUN",
    }


def canonical_synthetic_candidate_batch_bytes() -> bytes:
    return canonical_json_bytes(build_synthetic_candidate_batch_payload())


def canonical_synthetic_candidate_batch_sha256() -> str:
    return hashlib.sha256(canonical_synthetic_candidate_batch_bytes()).hexdigest()


def _candidate_authority_rows() -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for metadata in CANDIDATE_AUTHORITIES:
        rows.append(
            {
                "MATRIX_INDEX": str(metadata.MATRIX_INDEX),
                "SEMANTIC_VERSION": SEMANTIC_VERSION,
                "CANDIDATE_ID": metadata.CANDIDATE_ID,
                "SIGNATURE_HASH": metadata.SIGNATURE_HASH,
                "CONSTRUCTOR": metadata.CONSTRUCTOR,
                "CONSTRUCTOR_ID": metadata.CONSTRUCTOR_ID,
                "MATCHED_K": str(metadata.MATCHED_K),
                "CARDINALITY_MODE": CARDINALITY_MODE,
                "PARENT_BINDING": PARENT_OUTPUT_BINDING,
                "PARENT_A_CANDIDATE_ID": metadata.PARENT_A_CANDIDATE_ID,
                "PARENT_A_SIGNATURE_HASH": metadata.PARENT_A_SIGNATURE_HASH,
                "PARENT_B_CANDIDATE_ID": metadata.PARENT_B_CANDIDATE_ID,
                "PARENT_B_SIGNATURE_HASH": metadata.PARENT_B_SIGNATURE_HASH,
                "EXACT_TICKET_DEDUP": EXACT_TICKET_DEDUP,
                "FINAL_CARDINALITY_RULE": FINAL_CARDINALITY_RULE,
                "IMPLEMENTATION_SOURCE_IDENTITY": IMPLEMENTATION_SOURCE_IDENTITY,
            }
        )
    return tuple(rows)


def _csv_bytes(rows: Sequence[Mapping[str, str]]) -> bytes:
    if not rows:
        raise ValueError("CSV rows must not be empty")
    stream = io.StringIO(newline="")
    fieldnames = tuple(rows[0])
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _semantic_authority_snapshot(verification: Mapping[str, str]) -> dict[str, object]:
    return {
        "SCHEMA_VERSION": "B649_BAYES_CLUSTER_UNION_SEMANTIC_AUTHORITY_SNAPSHOT_V1",
        "AUTHORITY_ROOT": FINAL_SEMANTICS_ROOT,
        "SHA256SUMS_SHA256": SEMANTIC_AUTHORITY_SHA256SUMS_SHA256,
        "SHA256_VERIFICATION": verification.get("FINAL_SEMANTICS_SHA", "NOT_RUN"),
        "HYPOTHESIS": HYPOTHESIS_ID,
        "SEMANTIC_VERSION": SEMANTIC_VERSION,
        "COMMON_SEMANTICS_SIGNATURE_HASH": COMMON_SEMANTICS_SIGNATURE_HASH,
        "CANDIDATE_COUNT": len(CANDIDATE_AUTHORITIES),
        "CANDIDATE_IDS": list(CANDIDATE_IDS),
        "AUTHORITY_FILE_SHA256": dict(SEMANTIC_AUTHORITY_FILE_SHA256),
        "CARDINALITY_MODE": CARDINALITY_MODE,
        "PARENT_BINDING": PARENT_OUTPUT_BINDING,
        "TRUNCATION": TRUNCATION,
        "PADDING": PADDING,
        "RNG": RNG,
        "SEMANTIC_CHANGE": "NONE",
    }


def _parent_execution_contracts(verification: Mapping[str, str]) -> dict[str, object]:
    return {
        "SCHEMA_VERSION": "B649_BAYES_CLUSTER_UNION_PARENT_EXECUTION_CONTRACTS_V1",
        "STATUS": verification.get("PARENT_CONTRACT/PARITY", "NOT_RUN"),
        "COMMON": {
            "MINIMUM_HISTORY": MINIMUM_HISTORY,
            "INPUT_SHAPE": (
                "FINITE_CHRONOLOGICAL_SEQUENCE_OR_ITERABLE_OF_SIX_UNIQUE_INTS_1_TO_49"
            ),
            "TARGET_INDEX": "STRICTLY_PRIOR_PREFIX_LENGTH_EXCLUSIVE_TARGET",
            "NATIVE_PORTFOLIO_SHAPE": "IMMUTABLE_TUPLE_OF_EXACTLY_K_UNIQUE_TICKETS",
            "PARENT_ORDER_PRESERVED_BEFORE_UNION": "YES",
            "DETERMINISM": DETERMINISM_CLASS,
            "FAIL_CLOSED": "YES",
            "SHARED_CONSTRUCTOR_BLOB": SHARED_CONSTRUCTOR_BLOB,
            "SHARED_CONSTRUCTOR_SHA256": SHARED_CONSTRUCTOR_SHA256,
        },
        "BAYES": {
            "BAYES_PARENT_AUTHORITY": BAYES_PARENT_AUTHORITY_ROOT,
            "AUTHORITY_SHA256SUMS_SHA256": BAYES_AUTHORITY_SHA256SUMS_SHA256,
            "BAYES_PARENT_PRODUCER": (
                "lottolab.research.biglotto_multiscale_bayes_changepoint_bma_"
                "multi_ticket_candidate_batch_r1:"
                "produce_biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate"
            ),
            "BAYES_PARENT_MIN_HISTORY": _bayes.MINIMUM_HISTORY,
            "IMPLEMENTATION_COMMIT": BAYES_PARENT_IMPLEMENTATION_COMMIT,
            "IMPLEMENTATION_TREE": BAYES_PARENT_IMPLEMENTATION_TREE,
            "PRODUCER_BLOB": BAYES_PARENT_PRODUCER_BLOB,
            "PRODUCER_SHA256": BAYES_PARENT_PRODUCER_SHA256,
            "NATIVE_ORDER": "FROZEN_CONSTRUCTOR_GREEDY_SELECTION_ORDER",
        },
        "CLUSTER": {
            "CLUSTER_PARENT_AUTHORITY": CLUSTER_PARENT_AUTHORITY_ROOT,
            "AUTHORITY_SHA256SUMS_SHA256": CLUSTER_AUTHORITY_SHA256SUMS_SHA256,
            "CLUSTER_PARENT_PRODUCER": (
                "lottolab.research.biglotto_multiscale_temporal_profile_cluster_"
                "multi_ticket_candidate_batch_r1:produce_candidate_portfolio"
            ),
            "CLUSTER_PARENT_MIN_HISTORY": _cluster.MINIMUM_HISTORY,
            "IMPLEMENTATION_COMMIT": CLUSTER_PARENT_IMPLEMENTATION_COMMIT,
            "IMPLEMENTATION_TREE": CLUSTER_PARENT_IMPLEMENTATION_TREE,
            "PRODUCER_BLOB": CLUSTER_PARENT_PRODUCER_BLOB,
            "PRODUCER_SHA256": CLUSTER_PARENT_PRODUCER_SHA256,
            "NATIVE_ORDER": "FROZEN_CONSTRUCTOR_GREEDY_SELECTION_ORDER",
        },
    }


def _source_contract() -> dict[str, object]:
    return {
        "SCHEMA_VERSION": "B649_BAYES_CLUSTER_UNION_V1_SOURCE_CONTRACT_V1",
        "IMPLEMENTATION_SOURCE_IDENTITY": IMPLEMENTATION_SOURCE_IDENTITY,
        "CALL_SIGNATURE": "produce_candidate_portfolio(candidate_id,history,target_index)",
        "INPUT": {
            "LOTTERY_TYPE": LOTTERY_TYPE,
            "HISTORY_ORDER": HISTORY_ORDER,
            "MINIMUM_HISTORY": MINIMUM_HISTORY,
            "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
            "CANDIDATE_ID": "ONE_OF_EXACTLY_9_FROZEN_IDENTITIES",
        },
        "OUTPUT": {
            "SHAPE": "IMMUTABLE_VARIABLE_CARDINALITY_TICKET_PORTFOLIO",
            "TICKET": "TUPLE_OF_6_UNIQUE_BUILTIN_INTS_1_TO_49_STRICTLY_ASCENDING",
            "ORDER": OUTPUT_ORDER,
            "CARDINALITY": FINAL_CARDINALITY_RULE,
        },
        "COMPOSITION": {
            "PARENT_BINDING": PARENT_OUTPUT_BINDING,
            "EXACT_TICKET_DEDUP": EXACT_TICKET_DEDUP,
            "NUMBER_LEVEL_DEDUP": NUMBER_LEVEL_DEDUP,
            "TRUNCATION": TRUNCATION,
            "PADDING": PADDING,
            "RNG": RNG,
            "FALLBACK": FALLBACK,
        },
        "DEPENDENCIES": {
            "DATABASE": "NONE",
            "CURRENT_DATE": "NONE",
            "TARGET_OUTCOME": "NONE",
            "PRODUCTION_CATALOG": "NONE",
            "FORWARD_REGISTRY": "NONE",
        },
    }


def _contamination_boundary() -> dict[str, object]:
    return {
        "SCHEMA_VERSION": "B649_BAYES_CLUSTER_UNION_CONTAMINATION_BOUNDARY_V1",
        "HYPOTHESIS": HYPOTHESIS_ID,
        "SEMANTIC_VERSION": SEMANTIC_VERSION,
        "HISTORICALLY_DISCOVERED": "YES",
        "DISCOVERY_CUTOFF_DRAW": DISCOVERY_CUTOFF_DRAW,
        "HISTORICAL_CONFIRMATION": "NOT_RUN",
        "ROLLING": "NOT_RUN",
        "FORWARD_REGISTRATION": "NOT_RUN",
        "REAL_HISTORICAL_CAUSAL_INPUT_USED": "NO",
        "IMPLEMENTATION_FIXTURE": SYNTHETIC_FIXTURE_ID,
        "IMPLEMENTATION_FIXTURE_KIND": "SYNTHETIC_NON_OUTCOME",
        "POST_DISCOVERY_OUTCOMES_READ": "NO",
        "DRAW_115000082_OUTCOME_ACCESSED": "NO",
        "FORWARD_ELIGIBILITY": (
            "PROSPECTIVE_ONLY_UNLESS_UNTOUCHED_HOLDOUT_SEPARATELY_PROVEN"
        ),
    }


def _implementation_handoff(
    batch: Mapping[str, object], final_head: str, final_tree: str
) -> dict[str, object]:
    candidates = cast(list[Mapping[str, object]], batch["CANDIDATES"])
    return {
        "SCHEMA_VERSION": "B649_BAYES_CLUSTER_UNION_IMPLEMENTATION_HANDOFF_V1",
        "HYPOTHESIS": HYPOTHESIS_ID,
        "SEMANTIC_VERSION": SEMANTIC_VERSION,
        "CANDIDATE_COUNT": 9,
        "CONSTRUCTORS": 3,
        "MATCHED_K_VALUES": [5, 10, 20],
        "CARDINALITY_MODE": CARDINALITY_MODE,
        "IMPLEMENTATION_FROZEN": "YES",
        "HISTORICAL_CONFIRMATION": "FORBIDDEN",
        "FORWARD_ELIGIBILITY": (
            "PROSPECTIVE_ONLY_UNLESS_UNTOUCHED_HOLDOUT_SEPARATELY_PROVEN"
        ),
        "NEXT_STAGE": "FORWARD_PROTOCOL_FREEZE_OR_PROVEN_HOLDOUT_EVALUATION",
        "CANDIDATE_IDS": list(CANDIDATE_IDS),
        "FINAL_CARDINALITIES": {
            cast(str, item["CANDIDATE_ID"]): cast(int, item["FINAL_CARDINALITY"])
            for item in candidates
        },
        "IMPLEMENTATION_SOURCE_IDENTITY": IMPLEMENTATION_SOURCE_IDENTITY,
        "FINAL_HEAD": final_head,
        "FINAL_TREE": final_tree,
    }


def write_freeze_artifacts(
    output_root: str | Path,
    *,
    implementation_commit: str,
    final_head: str,
    final_tree: str,
    base_head: str,
    base_tree: str,
    verification_results: Mapping[str, str],
    command_summaries: Mapping[str, str],
    changed_paths: Sequence[str],
    attempt_ledger: Sequence[Mapping[str, object]] = (),
) -> tuple[Path, ...]:
    """Generate and SHA-seal the exact ten-file local implementation freeze."""

    validate_frozen_parent_authority()
    batch = build_synthetic_candidate_batch_payload()
    canonical_batch = canonical_json_bytes(batch)
    canonical_batch_sha = hashlib.sha256(canonical_batch).hexdigest()
    candidates = cast(list[Mapping[str, object]], batch["CANDIDATES"])
    if len(candidates) != 9:
        raise RuntimeError("candidate batch must contain exactly 9 candidates")

    deterministic_manifest = {
        "SCHEMA_VERSION": "B649_BAYES_CLUSTER_UNION_DETERMINISTIC_MANIFEST_V1",
        "CANDIDATE_COUNT": 9,
        "EXECUTIONS": 2,
        "EXECUTION_ISOLATION": "INDEPENDENT_PROCESSES_VIA_FOCUSED_UNIT_TEST",
        "COMMAND": f"uv run --frozen python -m {IMPLEMENTATION_MODULE}",
        "EXACT_EQUALITY_REQUIRED": [
            "CANDIDATE_IDENTITY",
            "NATIVE_TICKET_ORDER",
            "NATIVE_TICKET_CONTENT",
            "TICKET_COUNT",
            "CANONICAL_SERIALIZATION",
        ],
        "CANONICAL_BATCH_SHA256": canonical_batch_sha,
        "DOUBLE_GENERATION": verification_results.get("DOUBLE_GENERATION", "NOT_RUN"),
        "SCORING": "NOT_RUN",
        "RNG": RNG,
    }
    run_manifest = {
        "SCHEMA_VERSION": "B649_BAYES_CLUSTER_UNION_V1_RUN_MANIFEST_V1",
        "TASK_ID": TASK_ID,
        "STATUS": "IMPLEMENTATION_FREEZE_COMPLETE",
        "TASK_CLASS": "STATE_CHANGING_IMPLEMENTATION",
        "WORKER_ROUTE": "STANDARD",
        "JUDGE_MODE": "NOT_APPLICABLE",
        "BASE_HEAD": base_head,
        "BASE_TREE": base_tree,
        "FINAL_HEAD": final_head,
        "FINAL_TREE": final_tree,
        "COMMIT_SHA": implementation_commit,
        "SEMANTIC_VERSION": SEMANTIC_VERSION,
        "CANDIDATE_COUNT": 9,
        "CANDIDATE_IDS": list(CANDIDATE_IDS),
        "FINAL_CARDINALITIES": {
            cast(str, item["CANDIDATE_ID"]): cast(int, item["FINAL_CARDINALITY"])
            for item in candidates
        },
        "VERIFICATION": dict(verification_results),
        "COMMAND_SUMMARIES": dict(command_summaries),
        "CHANGED_PATHS": list(changed_paths),
        "ATTEMPT_LEDGER": [dict(item) for item in attempt_ledger],
        "HISTORICAL_CONFIRMATION": "NOT_RUN",
        "ROLLING": "NOT_RUN",
        "FORWARD_REGISTRATION": "NOT_RUN",
        "PRODUCTION_CATALOG_RUNTIME_MUTATION": "NONE",
        "DATABASE_ACCESS": "NONE",
        "PUSH": "NO",
        "PR": "NO",
    }

    payloads: dict[str, bytes] = {
        "candidate_authority.csv": _csv_bytes(_candidate_authority_rows()),
        "candidate_batch.json": canonical_json_bytes(batch, pretty=True),
        "contamination_boundary.json": canonical_json_bytes(
            _contamination_boundary(), pretty=True
        ),
        "deterministic_generation_manifest.json": canonical_json_bytes(
            deterministic_manifest, pretty=True
        ),
        "implementation_handoff.json": canonical_json_bytes(
            _implementation_handoff(batch, final_head, final_tree), pretty=True
        ),
        "parent_execution_contracts.json": canonical_json_bytes(
            _parent_execution_contracts(verification_results), pretty=True
        ),
        "run_manifest.json": canonical_json_bytes(run_manifest, pretty=True),
        "semantic_authority_snapshot.json": canonical_json_bytes(
            _semantic_authority_snapshot(verification_results), pretty=True
        ),
        "source_contract.json": canonical_json_bytes(_source_contract(), pretty=True),
    }
    expected_names = set(payloads) | {"SHA256SUMS"}
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    existing_names = {path.name for path in root.iterdir()}
    unexpected = existing_names - expected_names
    if unexpected:
        raise FileExistsError(f"output root contains unrelated paths: {sorted(unexpected)}")
    for name, payload in sorted(payloads.items()):
        (root / name).write_bytes(payload)
    checksum_bytes = "".join(
        f"{hashlib.sha256(payloads[name]).hexdigest()}  {name}\n"
        for name in sorted(payloads)
    ).encode("utf-8")
    (root / "SHA256SUMS").write_bytes(checksum_bytes)
    return tuple(root / name for name in sorted(expected_names))


__all__ = [
    "BAYES_PARENT_AUTHORITY_ROOT",
    "BAYES_PARENT_PRODUCER_BLOB",
    "CANDIDATE_AUTHORITIES",
    "CANDIDATE_IDS",
    "CANDIDATE_METADATA",
    "CARDINALITY_MODE",
    "CLUSTER_PARENT_AUTHORITY_ROOT",
    "CLUSTER_PARENT_PRODUCER_BLOB",
    "COMMON_SEMANTICS_SIGNATURE_HASH",
    "CONSTRUCTORS",
    "DISCOVERY_CUTOFF_DRAW",
    "FINAL_CARDINALITY_RULE",
    "FINAL_SEMANTICS_ROOT",
    "HYPOTHESIS_ID",
    "IMPLEMENTATION_SOURCE_IDENTITY",
    "MATCHED_K_VALUES",
    "MINIMUM_HISTORY",
    "OUTPUT_ORDER",
    "PADDING",
    "PARENT_OUTPUT_BINDING",
    "RNG",
    "SEMANTIC_VERSION",
    "SYNTHETIC_FIXTURE_ID",
    "TASK_ID",
    "TRUNCATION",
    "AuthorityMismatchError",
    "CandidateMetadata",
    "CandidatePortfolio",
    "InsufficientHistoryError",
    "Ticket",
    "TicketPortfolio",
    "TicketProvenance",
    "build_candidate_portfolio",
    "build_synthetic_candidate_batch_payload",
    "build_synthetic_non_outcome_history",
    "candidate_portfolio_payload",
    "canonical_json_bytes",
    "canonical_synthetic_candidate_batch_bytes",
    "canonical_synthetic_candidate_batch_sha256",
    "compose_full_deduplicated_union",
    "produce_biglotto_cross_family_r2_bayes_cluster_union_v1_candidate",
    "produce_candidate_portfolio",
    "validate_frozen_parent_authority",
    "write_freeze_artifacts",
]


if __name__ == "__main__":
    sys.stdout.buffer.write(canonical_synthetic_candidate_batch_bytes())
