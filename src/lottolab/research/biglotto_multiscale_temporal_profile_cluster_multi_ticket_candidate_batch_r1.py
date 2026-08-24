"""Causal BigLotto multiscale temporal profile cluster candidate batch R1.

This module freezes one history-only source-ticket universe:
B649_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MEDOID_POOL_V1.

Represent every legal number 1..49 by an exact three-dimensional temporal
occurrence-rate profile based on fixed strictly-prior windows: 50, 300, 750.

Cluster all 49 number profiles using deterministic complete-link hierarchical
agglomerative clustering with exact mean L1 distances, stopping at exactly 10
clusters. Choose exactly one deterministic medoid representative from every
cluster, order the ten representatives by a frozen cluster-native ordering, and
use them as the source number pool.

Generate all C(10,6) = 210 ordered source tickets, and pass the exact 210-ticket
universe through the three frozen multi-ticket constructors at native budgets
5, 10, and 20 to create exactly 9 frozen hypotheses.

The producer has no outcome access, fitted parameters, I/O, randomness, or
production catalog registration.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, islice, pairwise
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import biglotto_multi_ticket_constructors_r1 as _constructors

type Ticket = tuple[int, int, int, int, int, int]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type TemporalProfile = tuple[Fraction, Fraction, Fraction]
type TicketPortfolio = tuple[Ticket, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
SOURCE_UNIVERSE_ID: Final[str] = (
    "B649_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MEDOID_POOL_V1"
)
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"
METHOD_FAMILY: Final[str] = "CLUSTERING"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
FEATURE_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
WINDOWS: Final[tuple[int, int, int]] = FEATURE_WINDOWS
SOURCE_WINDOWS: Final[tuple[int, int, int]] = FEATURE_WINDOWS
FEATURE_DIMENSION: Final[int] = 3
MINIMUM_HISTORY: Final[int] = 750
TARGET_CLUSTER_COUNT: Final[int] = 10
REPRESENTATIVES_PER_CLUSTER: Final[int] = 1
SOURCE_NUMBER_POOL_COUNT: Final[int] = 10
SOURCE_CANDIDATE_TICKET_COUNT: Final[int] = 210
SOURCE_TICKET_ORDER: Final[str] = "LEXICOGRAPHIC_RANK_POSITION_COMBINATION_ORDER"

TEMPORAL_PROFILE_RULE: Final[str] = "EXACT_OCCURRENCE_RATE_VECTOR_50_300_750"
PROFILE_COORDINATE_WEIGHT_RULE: Final[str] = "EXACT_EQUAL_ONE_THIRD"
POINT_DISTANCE_RULE: Final[str] = "EXACT_MEAN_L1"
CLUSTERING_ALGORITHM: Final[str] = "HIERARCHICAL_AGGLOMERATIVE"
LINKAGE_RULE: Final[str] = "COMPLETE_LINK"
INITIAL_CLUSTER_RULE: Final[str] = "49_SINGLETON_NUMBER_CLUSTERS"
MERGE_TIE_BREAK_RULE: Final[str] = (
    "DISTANCE_LEFT_MEMBERS_RIGHT_MEMBERS_LEXICOGRAPHIC"
)
MEDOID_RULE: Final[str] = "MINIMUM_TOTAL_EXACT_L1_DISTANCE_THEN_NUMBER_ASCENDING"
CLUSTER_COMPACTNESS_RULE: Final[str] = "MEAN_UNORDERED_PAIRWISE_EXACT_L1_DISTANCE"
CLUSTER_ORDER_RULE: Final[str] = (
    "SIZE_DESC_COMPACTNESS_ASC_MEDOID_COST_ASC_REPRESENTATIVE_ASC"
)

CAUSAL_CUTOFF_RULE: Final[str] = "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
PARAMETER_SELECTION_RULE: Final[str] = "FIXED_PREREGISTERED_NO_OUTCOME_TUNING"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
NATIVE_TICKET_COUNT: Final[str] = "TICKET_COUNT"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "MULTISCALE_TEMPORAL_PROFILE_DIVERSITY_VIA_CLUSTER_MEDOID_COVERAGE"
)

CONSTRUCTOR_IDS: Final[tuple[str, str, str]] = (
    "B649_CANDIDATE_SET_LOW_OVERLAP_V1",
    "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
    "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1",
)
TICKET_COUNTS: Final[tuple[int, int, int]] = (5, 10, 20)

_CONSTRUCTOR_SYMBOL_SLUGS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "low_overlap",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "exposure_balanced",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": "hybrid_diversity",
    }
)
_CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS: Final[Mapping[str, str]] = (
    MappingProxyType(
        {
            "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "TICKET_PAIRWISE_DIVERSITY",
            "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": (
                "NUMBER_EXPOSURE_DIVERSITY"
            ),
            "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": (
                "PAIRWISE_AND_NUMBER_EXPOSURE_DIVERSITY"
            ),
        }
    )
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the preregistered 750 prior draws are available."""


@dataclass(frozen=True, slots=True)
class SourceUniverseMetadata:
    """Immutable authority metadata for the temporal profile cluster source universe."""

    SOURCE_UNIVERSE_ID: str
    VERSION: str
    METHOD_FAMILY: str
    LOTTERY_TYPE: str
    PICK_COUNT: int
    NUMBER_DOMAIN: tuple[int, int]
    HISTORY_ORDER: str
    FEATURE_WINDOWS: tuple[int, int, int]
    MINIMUM_HISTORY: int
    FEATURE_DIMENSION: int
    TEMPORAL_PROFILE_RULE: str
    PROFILE_COORDINATE_WEIGHT_RULE: str
    POINT_DISTANCE_RULE: str
    CLUSTERING_ALGORITHM: str
    LINKAGE_RULE: str
    INITIAL_CLUSTER_RULE: str
    TARGET_CLUSTER_COUNT: int
    MERGE_TIE_BREAK_RULE: str
    MEDOID_RULE: str
    CLUSTER_COMPACTNESS_RULE: str
    CLUSTER_ORDER_RULE: str
    REPRESENTATIVES_PER_CLUSTER: int
    SOURCE_NUMBER_POOL_COUNT: int
    SOURCE_CANDIDATE_TICKET_COUNT: int
    SOURCE_TICKET_ORDER: str
    CAUSAL_CUTOFF_RULE: str
    PARAMETER_SELECTION_RULE: str
    DETERMINISM_CLASS: str
    RNG_SEMANTICS: str
    EXPECTED_IMPROVEMENT_CHANNEL: str


SOURCE_UNIVERSE_METADATA: Final[SourceUniverseMetadata] = (
    SourceUniverseMetadata(
        SOURCE_UNIVERSE_ID=SOURCE_UNIVERSE_ID,
        VERSION=SOURCE_UNIVERSE_VERSION,
        METHOD_FAMILY=METHOD_FAMILY,
        LOTTERY_TYPE=LOTTERY_TYPE,
        PICK_COUNT=PICK_COUNT,
        NUMBER_DOMAIN=NUMBER_DOMAIN,
        HISTORY_ORDER=HISTORY_ORDER,
        FEATURE_WINDOWS=FEATURE_WINDOWS,
        MINIMUM_HISTORY=MINIMUM_HISTORY,
        FEATURE_DIMENSION=FEATURE_DIMENSION,
        TEMPORAL_PROFILE_RULE=TEMPORAL_PROFILE_RULE,
        PROFILE_COORDINATE_WEIGHT_RULE=PROFILE_COORDINATE_WEIGHT_RULE,
        POINT_DISTANCE_RULE=POINT_DISTANCE_RULE,
        CLUSTERING_ALGORITHM=CLUSTERING_ALGORITHM,
        LINKAGE_RULE=LINKAGE_RULE,
        INITIAL_CLUSTER_RULE=INITIAL_CLUSTER_RULE,
        TARGET_CLUSTER_COUNT=TARGET_CLUSTER_COUNT,
        MERGE_TIE_BREAK_RULE=MERGE_TIE_BREAK_RULE,
        MEDOID_RULE=MEDOID_RULE,
        CLUSTER_COMPACTNESS_RULE=CLUSTER_COMPACTNESS_RULE,
        CLUSTER_ORDER_RULE=CLUSTER_ORDER_RULE,
        REPRESENTATIVES_PER_CLUSTER=REPRESENTATIVES_PER_CLUSTER,
        SOURCE_NUMBER_POOL_COUNT=SOURCE_NUMBER_POOL_COUNT,
        SOURCE_CANDIDATE_TICKET_COUNT=SOURCE_CANDIDATE_TICKET_COUNT,
        SOURCE_TICKET_ORDER=SOURCE_TICKET_ORDER,
        CAUSAL_CUTOFF_RULE=CAUSAL_CUTOFF_RULE,
        PARAMETER_SELECTION_RULE=PARAMETER_SELECTION_RULE,
        DETERMINISM_CLASS=DETERMINISM_CLASS,
        RNG_SEMANTICS=RNG_SEMANTICS,
        EXPECTED_IMPROVEMENT_CHANNEL=EXPECTED_IMPROVEMENT_CHANNEL,
    )
)

SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = MappingProxyType(
    {
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "CLUSTERING_ALGORITHM": CLUSTERING_ALGORITHM,
        "CLUSTER_COMPACTNESS_RULE": CLUSTER_COMPACTNESS_RULE,
        "CLUSTER_ORDER_RULE": CLUSTER_ORDER_RULE,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FEATURE_DIMENSION": FEATURE_DIMENSION,
        "FEATURE_WINDOWS": FEATURE_WINDOWS,
        "HISTORY_ORDER": HISTORY_ORDER,
        "INITIAL_CLUSTER_RULE": INITIAL_CLUSTER_RULE,
        "LINKAGE_RULE": LINKAGE_RULE,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "MEDOID_RULE": MEDOID_RULE,
        "MERGE_TIE_BREAK_RULE": MERGE_TIE_BREAK_RULE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PICK_COUNT": PICK_COUNT,
        "POINT_DISTANCE_RULE": POINT_DISTANCE_RULE,
        "PROFILE_COORDINATE_WEIGHT_RULE": PROFILE_COORDINATE_WEIGHT_RULE,
        "REPRESENTATIVES_PER_CLUSTER": REPRESENTATIVES_PER_CLUSTER,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_NUMBER_POOL_COUNT": SOURCE_NUMBER_POOL_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "TARGET_CLUSTER_COUNT": TARGET_CLUSTER_COUNT,
        "TEMPORAL_PROFILE_RULE": TEMPORAL_PROFILE_RULE,
        "WINDOWS": WINDOWS,
    }
)


@dataclass(frozen=True, slots=True)
class TemporalProfileState:
    """Exact multiscale temporal profile vectors and distance matrix for numbers 1..49."""

    OCCURRENCE_COUNTS: tuple[tuple[int, int, int], ...]
    RATES: tuple[TemporalProfile, ...]
    PAIRWISE_DISTANCES: tuple[tuple[Fraction, ...], ...]

    def count_50(self, number: int) -> int:
        _validate_number(number)
        return self.OCCURRENCE_COUNTS[number - 1][0]

    def count_300(self, number: int) -> int:
        _validate_number(number)
        return self.OCCURRENCE_COUNTS[number - 1][1]

    def count_750(self, number: int) -> int:
        _validate_number(number)
        return self.OCCURRENCE_COUNTS[number - 1][2]

    def rate_50(self, number: int) -> Fraction:
        _validate_number(number)
        return self.RATES[number - 1][0]

    def rate_300(self, number: int) -> Fraction:
        _validate_number(number)
        return self.RATES[number - 1][1]

    def rate_750(self, number: int) -> Fraction:
        _validate_number(number)
        return self.RATES[number - 1][2]

    def profile(self, number: int) -> TemporalProfile:
        _validate_number(number)
        return self.RATES[number - 1]

    def profile_distance(self, number_a: int, number_b: int) -> Fraction:
        _validate_number(number_a)
        _validate_number(number_b)
        return self.PAIRWISE_DISTANCES[number_a - 1][number_b - 1]


@dataclass(frozen=True, slots=True)
class ClusterPartition:
    """Deterministic complete-link clustering partition into exactly 10 clusters."""

    CLUSTERS: tuple[tuple[int, ...], ...]
    REPRESENTATIVES: tuple[int, ...]
    MEDOID_COSTS: tuple[Fraction, ...]
    COMPACTNESS_SCORES: tuple[Fraction, ...]
    ORDERED_CLUSTERS: tuple[tuple[int, ...], ...]
    ORDERED_REPRESENTATIVES: tuple[int, ...]

    @property
    def SOURCE_NUMBER_POOL(self) -> tuple[int, ...]:
        return self.ORDERED_REPRESENTATIVES

    def cluster_size(self, cluster_index: int) -> int:
        return len(self.ORDERED_CLUSTERS[cluster_index])

    def representative(self, cluster_index: int) -> int:
        return self.ORDERED_REPRESENTATIVES[cluster_index]


def _validate_number(number: int) -> None:
    if (
        type(number) is not int
        or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]
    ):
        raise ValueError(
            f"number must be an integer in {NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}"
        )


def _validate_target_index(target_index: int) -> None:
    if type(target_index) is not int or target_index < 0:
        raise ValueError("target_index must be a non-negative integer")


def _read_history_prefix(
    history: HistoryInput, target_index: int
) -> tuple[object, ...]:
    _validate_target_index(target_index)
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
    except (TypeError, IndexError) as error:
        raise ValueError(
            "history must be a finite chronological sequence of draws"
        ) from error


def _validate_draw(raw_draw: object, draw_index: int) -> HistoryDraw:
    try:
        values: tuple[object, ...] = tuple(cast(Iterable[object], raw_draw))
    except TypeError as error:
        raise ValueError(
            f"history[{draw_index}] must contain exactly six integers"
        ) from error

    if len(values) != PICK_COUNT:
        raise ValueError(
            f"history[{draw_index}] must contain exactly {PICK_COUNT} numbers"
        )

    numbers: list[int] = []
    for position, raw_number in enumerate(values):
        if type(raw_number) is not int:
            raise ValueError(
                f"history[{draw_index}][{position}] must be an integer"
            )
        if not NUMBER_DOMAIN[0] <= raw_number <= NUMBER_DOMAIN[1]:
            raise ValueError(
                f"history[{draw_index}][{position}] must be in "
                f"{NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}"
            )
        numbers.append(raw_number)

    sorted_numbers = tuple(sorted(numbers))
    for left, right in pairwise(sorted_numbers):
        if left == right:
            raise ValueError(
                f"history[{draw_index}] contains duplicate number {left}"
            )
    return cast(HistoryDraw, sorted_numbers)


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Validate and return the immutable strictly-prior history prefix."""

    prefix = _read_history_prefix(history, target_index)
    if len(prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"target_index {target_index} provides {len(prefix)} draws, "
            f"which is fewer than the required minimum {MINIMUM_HISTORY}"
        )

    return tuple(
        _validate_draw(raw_draw, draw_index)
        for draw_index, raw_draw in enumerate(prefix)
    )


def calculate_temporal_profiles(
    history: HistoryInput, target_index: int
) -> TemporalProfileState:
    """Calculate exact occurrence rates and pairwise L1 distances for all 49 numbers."""

    valid_history = validate_prior_history(history, target_index)

    # Window slices: W in (50, 300, 750)
    history_50 = valid_history[target_index - 50 : target_index]
    history_300 = valid_history[target_index - 300 : target_index]
    history_750 = valid_history[target_index - 750 : target_index]

    counts_50 = [0] * 49
    for draw in history_50:
        for num in draw:
            counts_50[num - 1] += 1

    counts_300 = [0] * 49
    for draw in history_300:
        for num in draw:
            counts_300[num - 1] += 1

    counts_750 = [0] * 49
    for draw in history_750:
        for num in draw:
            counts_750[num - 1] += 1

    occurrence_counts: list[tuple[int, int, int]] = []
    rates: list[TemporalProfile] = []

    for num in range(1, 50):
        c50 = counts_50[num - 1]
        c300 = counts_300[num - 1]
        c750 = counts_750[num - 1]
        occurrence_counts.append((c50, c300, c750))
        rates.append((Fraction(c50, 50), Fraction(c300, 300), Fraction(c750, 750)))

    # Pairwise mean L1 distances
    dist_matrix: list[tuple[Fraction, ...]] = []
    for a in range(1, 50):
        row: list[Fraction] = []
        pa = rates[a - 1]
        for b in range(1, 50):
            if a == b:
                row.append(Fraction(0, 1))
            elif b < a:
                row.append(dist_matrix[b - 1][a - 1])
            else:
                pb = rates[b - 1]
                diff50 = abs(pa[0] - pb[0])
                diff300 = abs(pa[1] - pb[1])
                diff750 = abs(pa[2] - pb[2])
                mean_l1 = (diff50 + diff300 + diff750) / 3
                row.append(mean_l1)
        dist_matrix.append(tuple(row))

    return TemporalProfileState(
        OCCURRENCE_COUNTS=tuple(occurrence_counts),
        RATES=tuple(rates),
        PAIRWISE_DISTANCES=tuple(dist_matrix),
    )


def compute_point_distance(
    profile_a: TemporalProfile, profile_b: TemporalProfile
) -> Fraction:
    """Compute exact mean L1 distance between two 3D temporal profiles."""

    diff50 = abs(profile_a[0] - profile_b[0])
    diff300 = abs(profile_a[1] - profile_b[1])
    diff750 = abs(profile_a[2] - profile_b[2])
    return (diff50 + diff300 + diff750) / 3


def perform_hierarchical_clustering(
    profile_state: TemporalProfileState,
) -> ClusterPartition:
    """Perform deterministic complete-link agglomerative clustering to 10 clusters."""

    # 1. Start with 49 singleton clusters: (1,), (2,), ..., (49,)
    clusters: list[tuple[int, ...]] = [(num,) for num in range(1, 50)]
    pair_dist = profile_state.PAIRWISE_DISTANCES

    # 2. Agglomerate until TARGET_CLUSTER_COUNT (10) remain
    while len(clusters) > TARGET_CLUSTER_COUNT:
        best_candidate: (
            tuple[tuple[Fraction, tuple[int, ...], tuple[int, ...]], int, int] | None
        ) = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                cluster_a = clusters[i]
                cluster_b = clusters[j]
                # Complete-linkage: maximum pairwise member distance
                c_dist = max(
                    pair_dist[a - 1][b - 1]
                    for a in cluster_a
                    for b in cluster_b
                )
                left = min(cluster_a, cluster_b)
                right = max(cluster_a, cluster_b)
                key = (c_dist, left, right)
                if best_candidate is None or key < best_candidate[0]:
                    best_candidate = (key, i, j)

        if best_candidate is None:
            raise RuntimeError("clustering failed to find valid merge pair")

        _, i_best, j_best = best_candidate
        merged = tuple(sorted(set(clusters[i_best]) | set(clusters[j_best])))
        # Retain all clusters except i_best and j_best, append merged
        clusters = [
            clusters[k]
            for k in range(len(clusters))
            if k != i_best and k != j_best
        ] + [merged]

    # Verify partition invariants
    if len(clusters) != TARGET_CLUSTER_COUNT:
        raise RuntimeError(
            f"clustering produced {len(clusters)} clusters, expected {TARGET_CLUSTER_COUNT}"
        )
    union_members = sorted(num for c in clusters for num in c)
    if union_members != list(range(1, 50)):
        raise RuntimeError("cluster partition does not partition numbers 1..49")

    # 3. Calculate medoid, compactness, and sort key for each cluster
    cluster_records: list[dict[str, object]] = []
    for cluster in clusters:
        # Medoid selection
        medoid_costs: dict[int, Fraction] = {}
        for num in cluster:
            cost = sum((pair_dist[num - 1][m - 1] for m in cluster), start=Fraction(0, 1))
            medoid_costs[num] = cost

        best_rep = min(cluster, key=lambda n: (medoid_costs[n], n))
        best_cost = medoid_costs[best_rep]

        # Compactness calculation
        if len(cluster) <= 1:
            compactness = Fraction(0, 1)
        else:
            pairwise_sum = sum(
                (pair_dist[a - 1][b - 1] for a, b in combinations(cluster, 2)),
                start=Fraction(0, 1),
            )
            num_pairs = Fraction(len(cluster) * (len(cluster) - 1), 2)
            compactness = pairwise_sum / num_pairs

        sort_key = (-len(cluster), compactness, best_cost, best_rep)
        cluster_records.append(
            {
                "cluster": cluster,
                "representative": best_rep,
                "medoid_cost": best_cost,
                "compactness": compactness,
                "sort_key": sort_key,
            }
        )

    # Sort clusters by CLUSTER_ORDER_RULE:
    # 1. CLUSTER_SIZE descending
    # 2. CLUSTER_COMPACTNESS ascending
    # 3. MEDOID_COST ascending
    # 4. representative number ascending
    cluster_records.sort(key=lambda x: cast(tuple[object, ...], x["sort_key"]))

    ordered_clusters = tuple(
        cast(tuple[int, ...], rec["cluster"]) for rec in cluster_records
    )
    ordered_representatives = tuple(
        cast(int, rec["representative"]) for rec in cluster_records
    )
    medoid_costs_tuple = tuple(
        cast(Fraction, rec["medoid_cost"]) for rec in cluster_records
    )
    compactness_tuple = tuple(
        cast(Fraction, rec["compactness"]) for rec in cluster_records
    )

    if len(set(ordered_representatives)) != TARGET_CLUSTER_COUNT:
        raise RuntimeError("cluster representatives contain duplicates")

    return ClusterPartition(
        CLUSTERS=tuple(clusters),
        REPRESENTATIVES=tuple(
            cast(int, rec["representative"]) for rec in cluster_records
        ),
        MEDOID_COSTS=medoid_costs_tuple,
        COMPACTNESS_SCORES=compactness_tuple,
        ORDERED_CLUSTERS=ordered_clusters,
        ORDERED_REPRESENTATIVES=ordered_representatives,
    )


def calculate_cluster_partition(
    history: HistoryInput, target_index: int
) -> ClusterPartition:
    """Calculate the complete-link cluster partition from strictly-prior history."""

    profile_state = calculate_temporal_profiles(history, target_index)
    return perform_hierarchical_clustering(profile_state)


def produce_b649_multiscale_temporal_profile_cluster_medoid_pool_v1(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce the ordered 210-ticket temporal profile cluster source universe."""

    partition = calculate_cluster_partition(history, target_index)
    source_pool = partition.SOURCE_NUMBER_POOL
    if len(source_pool) != SOURCE_NUMBER_POOL_COUNT:
        raise RuntimeError(
            f"source pool produced {len(source_pool)} numbers, expected {SOURCE_NUMBER_POOL_COUNT}"
        )

    tickets: list[Ticket] = []
    for rank_positions in combinations(range(SOURCE_NUMBER_POOL_COUNT), PICK_COUNT):
        ticket = cast(
            Ticket,
            tuple(sorted(source_pool[pos] for pos in rank_positions)),
        )
        tickets.append(ticket)

    source_tickets = tuple(tickets)
    if len(source_tickets) != SOURCE_CANDIDATE_TICKET_COUNT:
        raise RuntimeError(
            f"source universe produced {len(source_tickets)} tickets, "
            f"expected {SOURCE_CANDIDATE_TICKET_COUNT}"
        )
    if len(set(source_tickets)) != len(source_tickets):
        raise RuntimeError("source universe produced duplicate tickets")
    return source_tickets


produce_source_ticket_universe = (
    produce_b649_multiscale_temporal_profile_cluster_medoid_pool_v1
)
build_source_ticket_universe = (
    produce_b649_multiscale_temporal_profile_cluster_medoid_pool_v1
)


def _json_ready(value: object) -> object:
    if isinstance(value, Mapping):
        converted: dict[str, object] = {}
        mapping = cast(Mapping[object, object], value)
        for key, item in mapping.items():
            if not isinstance(key, str):
                raise TypeError("semantic-record keys must be strings")
            converted[key] = _json_ready(item)
        return converted
    if isinstance(value, tuple):
        return [_json_ready(item) for item in cast(tuple[object, ...], value)]
    if isinstance(value, list):
        return [_json_ready(item) for item in cast(list[object], value)]
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    return value


def canonicalize_semantic_record(record: object) -> bytes:
    """Return sorted-key, compact UTF-8 JSON for a complete semantic record."""

    if not isinstance(record, Mapping):
        raise TypeError("semantic record must be a mapping")
    json_ready_record = _json_ready(cast(Mapping[object, object], record))
    return json.dumps(
        json_ready_record,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_semantic_json(record: Mapping[str, object]) -> str:
    """Return canonical semantic JSON as text."""

    return canonicalize_semantic_record(record).decode("utf-8")


def signature_hash_for_semantics(record: Mapping[str, object]) -> str:
    """Return the SHA-256 hash of canonical semantic JSON."""

    return hashlib.sha256(canonicalize_semantic_record(record)).hexdigest()


def candidate_id_for_semantics(record: Mapping[str, object]) -> str:
    """Derive the frozen clustering candidate ID."""

    return f"BMSGV1_CL_{signature_hash_for_semantics(record)[:16]}"


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """Deterministic identity material for one temporal profile cluster hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    """Derive candidate ID and full signature hash together."""

    canonical_json = canonical_semantic_json(record)
    signature_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return CandidateIdentity(
        CANDIDATE_ID=f"BMSGV1_CL_{signature_hash[:16]}",
        SIGNATURE_HASH=signature_hash,
        CANONICAL_SEMANTIC_JSON=canonical_json,
    )


@dataclass(frozen=True, slots=True)
class CandidateMetadata:
    """Immutable authority metadata for one frozen research hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    SEMANTICS: Mapping[str, object]
    CONSTRUCTOR_ID: str
    TICKET_COUNT: int
    IMPLEMENTATION_SYMBOL: str


def _implementation_symbol(constructor_id: str, ticket_count: int) -> str:
    return (
        "produce_b649_multiscale_temporal_profile_cluster_multiticket_"
        f"{_CONSTRUCTOR_SYMBOL_SLUGS[constructor_id]}_v1_k{ticket_count}"
    )


def _candidate_semantic_record(
    constructor_id: str, ticket_count: int
) -> dict[str, object]:
    constructor_metadata = _constructors.CONSTRUCTOR_METADATA[constructor_id]
    return {
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "CLUSTERING_ALGORITHM": CLUSTERING_ALGORITHM,
        "CLUSTER_COMPACTNESS_RULE": CLUSTER_COMPACTNESS_RULE,
        "CLUSTER_ORDER_RULE": CLUSTER_ORDER_RULE,
        "CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNEL": (
            _CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS[constructor_id]
        ),
        "CONSTRUCTOR_ID": constructor_id,
        "CONSTRUCTOR_VERSION": constructor_metadata.VERSION,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FEATURE_DIMENSION": FEATURE_DIMENSION,
        "FEATURE_WINDOWS": FEATURE_WINDOWS,
        "HISTORY_ORDER": HISTORY_ORDER,
        "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
        "INITIAL_CLUSTER_RULE": INITIAL_CLUSTER_RULE,
        "LINKAGE_RULE": LINKAGE_RULE,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "MEDOID_RULE": MEDOID_RULE,
        "MERGE_TIE_BREAK_RULE": MERGE_TIE_BREAK_RULE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NATIVE_TICKET_COUNT": ticket_count,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "OUTPUT_SHAPE": OUTPUT_SHAPE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PICK_COUNT": PICK_COUNT,
        "POINT_DISTANCE_RULE": POINT_DISTANCE_RULE,
        "PROFILE_COORDINATE_WEIGHT_RULE": PROFILE_COORDINATE_WEIGHT_RULE,
        "REPRESENTATIVES_PER_CLUSTER": REPRESENTATIVES_PER_CLUSTER,
        "RNG_SEED": None,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_NUMBER_POOL_COUNT": SOURCE_NUMBER_POOL_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "TARGET_CLUSTER_COUNT": TARGET_CLUSTER_COUNT,
        "TEMPORAL_PROFILE_RULE": TEMPORAL_PROFILE_RULE,
        "TICKET_COUNT": ticket_count,
        "WINDOWS": WINDOWS,
    }


def _build_candidate_authority() -> tuple[
    tuple[CandidateMetadata, ...],
    Mapping[str, CandidateMetadata],
    Mapping[str, Mapping[str, object]],
    Mapping[tuple[str, int], str],
]:
    authorities: list[CandidateMetadata] = []
    metadata_by_id: dict[str, CandidateMetadata] = {}
    semantics_by_id: dict[str, Mapping[str, object]] = {}
    ids_by_pair: dict[tuple[str, int], str] = {}

    for constructor_id in CONSTRUCTOR_IDS:
        for ticket_count in TICKET_COUNTS:
            semantic_record = _candidate_semantic_record(
                constructor_id, ticket_count
            )
            identity = derive_candidate_identity(semantic_record)
            if identity.CANDIDATE_ID in metadata_by_id:
                raise RuntimeError(
                    "candidate ID collision in frozen temporal profile cluster hypothesis matrix"
                )
            semantic_proxy: Mapping[str, object] = MappingProxyType(
                semantic_record
            )
            metadata = CandidateMetadata(
                CANDIDATE_ID=identity.CANDIDATE_ID,
                SIGNATURE_HASH=identity.SIGNATURE_HASH,
                SEMANTICS=semantic_proxy,
                CONSTRUCTOR_ID=constructor_id,
                TICKET_COUNT=ticket_count,
                IMPLEMENTATION_SYMBOL=_implementation_symbol(
                    constructor_id, ticket_count
                ),
            )
            authorities.append(metadata)
            metadata_by_id[identity.CANDIDATE_ID] = metadata
            semantics_by_id[identity.CANDIDATE_ID] = semantic_proxy
            ids_by_pair[(constructor_id, ticket_count)] = identity.CANDIDATE_ID

    expected_count = len(CONSTRUCTOR_IDS) * len(TICKET_COUNTS)
    if len(authorities) != expected_count:
        raise RuntimeError(
            f"expected {expected_count} candidates, built {len(authorities)}"
        )

    return (
        tuple(authorities),
        MappingProxyType(metadata_by_id),
        MappingProxyType(semantics_by_id),
        MappingProxyType(ids_by_pair),
    )


(
    CANDIDATE_AUTHORITIES,
    CANDIDATE_METADATA,
    CANDIDATE_SEMANTICS,
    CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT,
) = _build_candidate_authority()

CANDIDATE_AUTHORITY: Final[Mapping[str, CandidateMetadata]] = (
    CANDIDATE_METADATA
)
CANDIDATE_IDS: Final[tuple[str, ...]] = tuple(
    metadata.CANDIDATE_ID for metadata in CANDIDATE_AUTHORITIES
)
CANDIDATE_SIGNATURE_HASHES: Final[Mapping[str, str]] = MappingProxyType(
    {
        metadata.CANDIDATE_ID: metadata.SIGNATURE_HASH
        for metadata in CANDIDATE_AUTHORITIES
    }
)


def candidate_id_for(constructor_id: str, ticket_count: int) -> str:
    """Return the candidate ID for a given constructor and native ticket count."""

    try:
        return CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT[
            (constructor_id, ticket_count)
        ]
    except KeyError as error:
        raise KeyError(
            f"unknown constructor/ticket_count pair: {(constructor_id, ticket_count)}"
        ) from error


def _produce_named_candidate(
    constructor_id: str,
    ticket_count: int,
    history: HistoryInput,
    target_index: int,
) -> TicketPortfolio:
    universe = produce_source_ticket_universe(history, target_index)
    if constructor_id == "B649_CANDIDATE_SET_LOW_OVERLAP_V1":
        return _constructors.construct_b649_candidate_set_low_overlap_v1(
            universe, ticket_count
        )
    if constructor_id == "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1":
        return _constructors.construct_b649_candidate_set_exposure_balanced_v1(
            universe, ticket_count
        )
    if constructor_id == "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1":
        return _constructors.construct_b649_candidate_set_hybrid_diversity_v1(
            universe, ticket_count
        )
    raise KeyError(f"unknown constructor ID: {constructor_id}")


def produce_candidate_portfolio(
    candidate_id: str, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce the portfolio for any of the 9 candidate IDs."""

    try:
        metadata = CANDIDATE_METADATA[candidate_id]
    except KeyError as error:
        raise KeyError(f"unknown candidate ID: {candidate_id}") from error

    return _produce_named_candidate(
        metadata.CONSTRUCTOR_ID, metadata.TICKET_COUNT, history, target_index
    )


produce_biglotto_multi_ticket_candidate = produce_candidate_portfolio
produce_multi_ticket_candidate = produce_candidate_portfolio
produce_biglotto_temporal_profile_cluster_multi_ticket_candidate = (
    produce_candidate_portfolio
)
produce_biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate = (
    produce_candidate_portfolio
)


def produce_b649_multiscale_temporal_profile_cluster_multiticket_low_overlap_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[0], 5, history, target_index
    )


def produce_b649_multiscale_temporal_profile_cluster_multiticket_low_overlap_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[0], 10, history, target_index
    )


def produce_b649_multiscale_temporal_profile_cluster_multiticket_low_overlap_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[0], 20, history, target_index
    )


def produce_b649_multiscale_temporal_profile_cluster_multiticket_exposure_balanced_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[1], 5, history, target_index
    )


def produce_b649_multiscale_temporal_profile_cluster_multiticket_exposure_balanced_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[1], 10, history, target_index
    )


def produce_b649_multiscale_temporal_profile_cluster_multiticket_exposure_balanced_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[1], 20, history, target_index
    )


def produce_b649_multiscale_temporal_profile_cluster_multiticket_hybrid_diversity_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[2], 5, history, target_index
    )


def produce_b649_multiscale_temporal_profile_cluster_multiticket_hybrid_diversity_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[2], 10, history, target_index
    )


def produce_b649_multiscale_temporal_profile_cluster_multiticket_hybrid_diversity_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[2], 20, history, target_index
    )


__all__ = [
    "CANDIDATE_AUTHORITIES",
    "CANDIDATE_AUTHORITY",
    "CANDIDATE_IDS",
    "CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT",
    "CANDIDATE_METADATA",
    "CANDIDATE_SEMANTICS",
    "CANDIDATE_SIGNATURE_HASHES",
    "CAUSAL_CUTOFF_RULE",
    "CLUSTERING_ALGORITHM",
    "CLUSTER_COMPACTNESS_RULE",
    "CLUSTER_ORDER_RULE",
    "CONSTRUCTOR_IDS",
    "DETERMINISM_CLASS",
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "FEATURE_DIMENSION",
    "FEATURE_WINDOWS",
    "HISTORY_ORDER",
    "HYPOTHESIS_VERSION",
    "INITIAL_CLUSTER_RULE",
    "LINKAGE_RULE",
    "LOTTERY_TYPE",
    "MEDOID_RULE",
    "MERGE_TIE_BREAK_RULE",
    "METHOD_FAMILY",
    "MINIMUM_HISTORY",
    "NATIVE_TICKET_COUNT",
    "NUMBER_DOMAIN",
    "OUTPUT_SHAPE",
    "PARAMETER_SELECTION_RULE",
    "PICK_COUNT",
    "POINT_DISTANCE_RULE",
    "PROFILE_COORDINATE_WEIGHT_RULE",
    "REPRESENTATIVES_PER_CLUSTER",
    "RNG_SEMANTICS",
    "SOURCE_CANDIDATE_TICKET_COUNT",
    "SOURCE_NUMBER_POOL_COUNT",
    "SOURCE_TICKET_ORDER",
    "SOURCE_UNIVERSE_CONTRACT",
    "SOURCE_UNIVERSE_ID",
    "SOURCE_UNIVERSE_METADATA",
    "SOURCE_UNIVERSE_VERSION",
    "SOURCE_WINDOWS",
    "TARGET_CLUSTER_COUNT",
    "TEMPORAL_PROFILE_RULE",
    "TICKET_COUNTS",
    "WINDOWS",
    "CandidateIdentity",
    "CandidateMetadata",
    "ClusterPartition",
    "InsufficientHistoryError",
    "SourceUniverseMetadata",
    "TemporalProfileState",
    "build_source_ticket_universe",
    "calculate_cluster_partition",
    "calculate_temporal_profiles",
    "candidate_id_for",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "compute_point_distance",
    "derive_candidate_identity",
    "perform_hierarchical_clustering",
    "produce_b649_multiscale_temporal_profile_cluster_medoid_pool_v1",
    "produce_b649_multiscale_temporal_profile_cluster_multiticket_exposure_balanced_v1_k5",
    "produce_b649_multiscale_temporal_profile_cluster_multiticket_exposure_balanced_v1_k10",
    "produce_b649_multiscale_temporal_profile_cluster_multiticket_exposure_balanced_v1_k20",
    "produce_b649_multiscale_temporal_profile_cluster_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_multiscale_temporal_profile_cluster_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_multiscale_temporal_profile_cluster_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_multiscale_temporal_profile_cluster_multiticket_low_overlap_v1_k5",
    "produce_b649_multiscale_temporal_profile_cluster_multiticket_low_overlap_v1_k10",
    "produce_b649_multiscale_temporal_profile_cluster_multiticket_low_overlap_v1_k20",
    "produce_biglotto_multi_ticket_candidate",
    "produce_biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate",
    "produce_biglotto_temporal_profile_cluster_multi_ticket_candidate",
    "produce_candidate_portfolio",
    "produce_multi_ticket_candidate",
    "produce_source_ticket_universe",
    "signature_hash_for_semantics",
    "validate_prior_history",
]
