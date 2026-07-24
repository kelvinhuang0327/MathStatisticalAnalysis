"""Pure application policy for Historical Success research qualification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

RANDOM_BASELINE_CAVEAT = (
    "Random/null benchmark unavailable; random advantage has not been evaluated."
)

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class HistoricalSuccessQualificationContractError(ValueError):
    """Supplied qualification evidence violates the closed application contract."""


class HistoricalSuccessQualificationPrimaryStatus(StrEnum):
    NOT_READY = "NOT_READY"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    RESEARCH_CANDIDATE = "RESEARCH_CANDIDATE"


class HistoricalSuccessQualificationInformationalFlag(StrEnum):
    CROSS_IMPORT_UNRESOLVED = "CROSS_IMPORT_UNRESOLVED"
    HISTORICAL_CONCORDANCE_OBSERVED = "HISTORICAL_CONCORDANCE_OBSERVED"
    RECENT_RELATIONSHIP_DIFFERENCE = "RECENT_RELATIONSHIP_DIFFERENCE"


INFORMATIONAL_FLAG_ORDER = (
    HistoricalSuccessQualificationInformationalFlag.CROSS_IMPORT_UNRESOLVED,
    HistoricalSuccessQualificationInformationalFlag.HISTORICAL_CONCORDANCE_OBSERVED,
    HistoricalSuccessQualificationInformationalFlag.RECENT_RELATIONSHIP_DIFFERENCE,
)


class HistoricalSuccessQualificationEvidenceStatus(StrEnum):
    COMPLETE = "COMPLETE"
    NOT_READY = "NOT_READY"


class HistoricalSuccessQualificationPairStatus(StrEnum):
    COMPLETE = "COMPLETE"
    LEFT_NOT_READY = "LEFT_NOT_READY"
    RIGHT_NOT_READY = "RIGHT_NOT_READY"
    BOTH_NOT_READY = "BOTH_NOT_READY"


class HistoricalSuccessQualificationOverlapRelation(StrEnum):
    DISJOINT = "DISJOINT"
    PARTIAL_OVERLAP = "PARTIAL_OVERLAP"
    IDENTICAL = "IDENTICAL"


class HistoricalSuccessQualificationCensusStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL_NOT_READY = "PARTIAL_NOT_READY"
    ALL_NOT_READY = "ALL_NOT_READY"


class HistoricalSuccessQualificationCensusSummary(StrEnum):
    ALL_AVAILABLE_HIGHER = "ALL_AVAILABLE_HIGHER"
    ALL_AVAILABLE_EQUAL = "ALL_AVAILABLE_EQUAL"
    ALL_AVAILABLE_LOWER = "ALL_AVAILABLE_LOWER"
    MIXED_AVAILABLE = "MIXED_AVAILABLE"
    PARTIAL_AVAILABILITY = "PARTIAL_AVAILABILITY"
    NO_AVAILABLE_EFFECT = "NO_AVAILABLE_EFFECT"


_QUALIFYING_CENSUS_SUMMARIES = frozenset(
    {
        HistoricalSuccessQualificationCensusSummary.ALL_AVAILABLE_HIGHER,
        HistoricalSuccessQualificationCensusSummary.ALL_AVAILABLE_EQUAL,
        HistoricalSuccessQualificationCensusSummary.ALL_AVAILABLE_LOWER,
    }
)


def _require_canonical_text(value: str, name: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise HistoricalSuccessQualificationContractError(
            f"{name} must be a non-empty canonical string"
        )


def _require_sha256(value: str, name: str) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise HistoricalSuccessQualificationContractError(
            f"{name} must be an exact lowercase SHA-256"
        )


def _require_non_negative_integer(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise HistoricalSuccessQualificationContractError(
            f"{name} must be a non-negative integer"
        )


@dataclass(frozen=True, slots=True)
class HistoricalSuccessQualificationIdentity:
    strategy_id: str
    strategy_version: str
    replicate: int
    prefix_count: int
    criterion: str

    def __post_init__(self) -> None:
        _require_canonical_text(self.strategy_id, "strategy_id")
        _require_canonical_text(self.strategy_version, "strategy_version")
        _require_canonical_text(self.criterion, "criterion")
        if type(self.replicate) is not int or self.replicate < 1:
            raise HistoricalSuccessQualificationContractError(
                "replicate must be an integer >= 1"
            )
        if type(self.prefix_count) is not int or self.prefix_count < 1:
            raise HistoricalSuccessQualificationContractError(
                "prefix_count must be an integer >= 1"
            )


@dataclass(frozen=True, slots=True)
class HistoricalSuccessQualificationImportEvidence:
    import_index: int
    import_identity_sha256: str
    dataset_sha256: str
    source_artifact_sha256: str
    source_observation_count: int
    strategy_window_status: HistoricalSuccessQualificationEvidenceStatus
    temporal_holdout_status: HistoricalSuccessQualificationEvidenceStatus
    recent_audit_status: HistoricalSuccessQualificationEvidenceStatus
    recent_relationship_difference_count: int

    def __post_init__(self) -> None:
        _require_non_negative_integer(self.import_index, "import_index")
        _require_sha256(self.import_identity_sha256, "import_identity_sha256")
        _require_sha256(self.dataset_sha256, "dataset_sha256")
        _require_sha256(self.source_artifact_sha256, "source_artifact_sha256")
        _require_non_negative_integer(
            self.source_observation_count, "source_observation_count"
        )
        _require_non_negative_integer(
            self.recent_relationship_difference_count,
            "recent_relationship_difference_count",
        )
        if (
            self.temporal_holdout_status
            is HistoricalSuccessQualificationEvidenceStatus.COMPLETE
        ) != (
            self.recent_audit_status
            is HistoricalSuccessQualificationEvidenceStatus.COMPLETE
        ):
            raise HistoricalSuccessQualificationContractError(
                "temporal holdout and recent audit readiness must agree"
            )
        if (
            self.recent_audit_status
            is HistoricalSuccessQualificationEvidenceStatus.NOT_READY
            and self.recent_relationship_difference_count != 0
        ):
            raise HistoricalSuccessQualificationContractError(
                "not-ready recent evidence cannot report relationship differences"
            )


@dataclass(frozen=True, slots=True)
class HistoricalSuccessQualificationPairInput:
    left_import_index: int
    right_import_index: int
    pair_status: HistoricalSuccessQualificationPairStatus
    confirmation_overlap_relation: (
        HistoricalSuccessQualificationOverlapRelation | None
    )

    def __post_init__(self) -> None:
        _require_non_negative_integer(self.left_import_index, "left_import_index")
        _require_non_negative_integer(self.right_import_index, "right_import_index")
        if self.left_import_index >= self.right_import_index:
            raise HistoricalSuccessQualificationContractError(
                "pair indexes must be in canonical ascending order"
            )
        if self.pair_status is HistoricalSuccessQualificationPairStatus.COMPLETE:
            if self.confirmation_overlap_relation is None:
                raise HistoricalSuccessQualificationContractError(
                    "complete pair requires a confirmation overlap relation"
                )
        elif self.confirmation_overlap_relation is not None:
            raise HistoricalSuccessQualificationContractError(
                "not-ready pair cannot carry a confirmation overlap relation"
            )


@dataclass(frozen=True, slots=True)
class HistoricalSuccessQualificationPairEvidence:
    left_import_index: int
    right_import_index: int
    pair_status: HistoricalSuccessQualificationPairStatus
    same_dataset_sha256: bool
    same_source_artifact_sha256: bool
    confirmation_overlap_relation: (
        HistoricalSuccessQualificationOverlapRelation | None
    )
    r1_comparable: bool

    def __post_init__(self) -> None:
        if self.left_import_index >= self.right_import_index:
            raise HistoricalSuccessQualificationContractError(
                "pair evidence indexes must be in canonical ascending order"
            )
        if type(self.same_dataset_sha256) is not bool:
            raise HistoricalSuccessQualificationContractError(
                "same_dataset_sha256 must be boolean"
            )
        if type(self.same_source_artifact_sha256) is not bool:
            raise HistoricalSuccessQualificationContractError(
                "same_source_artifact_sha256 must be boolean"
            )
        expected_comparable = (
            self.pair_status is HistoricalSuccessQualificationPairStatus.COMPLETE
            and not self.same_dataset_sha256
            and not self.same_source_artifact_sha256
            and self.confirmation_overlap_relation
            in {
                HistoricalSuccessQualificationOverlapRelation.PARTIAL_OVERLAP,
                HistoricalSuccessQualificationOverlapRelation.DISJOINT,
            }
        )
        if self.r1_comparable is not expected_comparable:
            raise HistoricalSuccessQualificationContractError(
                "pair R1 comparability is inconsistent"
            )


@dataclass(frozen=True, slots=True)
class HistoricalSuccessResearchQualification:
    identity: HistoricalSuccessQualificationIdentity
    imports: tuple[HistoricalSuccessQualificationImportEvidence, ...]
    primary_status: HistoricalSuccessQualificationPrimaryStatus
    informational_flags: tuple[
        HistoricalSuccessQualificationInformationalFlag, ...
    ]
    random_baseline_caveat: str | None
    comparable_import_count: int
    expected_pair_count: int
    actual_pair_count: int
    census_status: HistoricalSuccessQualificationCensusStatus
    cohort_census_count: int
    pairs: tuple[HistoricalSuccessQualificationPairEvidence, ...]

    def __post_init__(self) -> None:
        identities = tuple(item.import_identity_sha256 for item in self.imports)
        if tuple(item.import_index for item in self.imports) != tuple(
            range(len(self.imports))
        ) or len(set(identities)) != len(identities):
            raise HistoricalSuccessQualificationContractError(
                "imports must be distinct and preserve caller order"
            )
        expected_pair_count = len(self.imports) * (len(self.imports) - 1) // 2
        if self.expected_pair_count != expected_pair_count:
            raise HistoricalSuccessQualificationContractError(
                "expected pair count is inconsistent"
            )
        if self.actual_pair_count != len(self.pairs):
            raise HistoricalSuccessQualificationContractError(
                "actual pair count is inconsistent"
            )
        _require_non_negative_integer(
            self.comparable_import_count, "comparable_import_count"
        )
        _require_non_negative_integer(
            self.cohort_census_count, "cohort_census_count"
        )
        canonical_flags = tuple(
            flag for flag in INFORMATIONAL_FLAG_ORDER if flag in self.informational_flags
        )
        if (
            len(set(self.informational_flags)) != len(self.informational_flags)
            or self.informational_flags != canonical_flags
        ):
            raise HistoricalSuccessQualificationContractError(
                "informational flags must be unique and canonically ordered"
            )
        unresolved = (
            HistoricalSuccessQualificationInformationalFlag.CROSS_IMPORT_UNRESOLVED
            in self.informational_flags
        )
        concordant = (
            HistoricalSuccessQualificationInformationalFlag.HISTORICAL_CONCORDANCE_OBSERVED
            in self.informational_flags
        )
        if unresolved and concordant:
            raise HistoricalSuccessQualificationContractError(
                "unresolved and concordant flags cannot coexist"
            )
        if concordant and (
            self.primary_status
            is not HistoricalSuccessQualificationPrimaryStatus.RESEARCH_CANDIDATE
        ):
            raise HistoricalSuccessQualificationContractError(
                "historical concordance requires research-candidate status"
            )
        if (
            self.primary_status
            is HistoricalSuccessQualificationPrimaryStatus.RESEARCH_CANDIDATE
        ):
            if self.random_baseline_caveat != RANDOM_BASELINE_CAVEAT or not concordant:
                raise HistoricalSuccessQualificationContractError(
                    "research candidate requires concordance and the random-baseline caveat"
                )
        elif self.random_baseline_caveat is not None:
            raise HistoricalSuccessQualificationContractError(
                "non-candidate status cannot carry the random-baseline caveat"
            )


def qualify_historical_success(
    *,
    identity: HistoricalSuccessQualificationIdentity,
    imports: tuple[HistoricalSuccessQualificationImportEvidence, ...],
    pairs: tuple[HistoricalSuccessQualificationPairInput, ...],
    census_status: HistoricalSuccessQualificationCensusStatus,
    cohort_census_count: int,
    cohort_summaries: tuple[HistoricalSuccessQualificationCensusSummary, ...],
) -> HistoricalSuccessResearchQualification:
    """Return one deterministic fail-closed qualification projection."""

    import_identities = tuple(item.import_identity_sha256 for item in imports)
    if (
        tuple(item.import_index for item in imports) != tuple(range(len(imports)))
        or len(set(import_identities)) != len(import_identities)
        or len(imports) > 4
    ):
        raise HistoricalSuccessQualificationContractError(
            "qualification imports must be at most four distinct ordered identities"
        )
    pair_indexes = tuple(
        (pair.left_import_index, pair.right_import_index) for pair in pairs
    )
    if (
        len(set(pair_indexes)) != len(pair_indexes)
        or pair_indexes != tuple(sorted(pair_indexes))
        or any(right >= len(imports) for _, right in pair_indexes)
    ):
        raise HistoricalSuccessQualificationContractError(
            "qualification pairs must be unique, ordered, and reference selected imports"
        )
    _require_non_negative_integer(cohort_census_count, "cohort_census_count")
    if cohort_census_count != len(cohort_summaries):
        raise HistoricalSuccessQualificationContractError(
            "cohort census count does not match supplied summaries"
        )

    pair_evidence = tuple(
        HistoricalSuccessQualificationPairEvidence(
            left_import_index=pair.left_import_index,
            right_import_index=pair.right_import_index,
            pair_status=pair.pair_status,
            same_dataset_sha256=(
                imports[pair.left_import_index].dataset_sha256
                == imports[pair.right_import_index].dataset_sha256
            ),
            same_source_artifact_sha256=(
                imports[pair.left_import_index].source_artifact_sha256
                == imports[pair.right_import_index].source_artifact_sha256
            ),
            confirmation_overlap_relation=pair.confirmation_overlap_relation,
            r1_comparable=(
                pair.pair_status is HistoricalSuccessQualificationPairStatus.COMPLETE
                and imports[pair.left_import_index].dataset_sha256
                != imports[pair.right_import_index].dataset_sha256
                and imports[pair.left_import_index].source_artifact_sha256
                != imports[pair.right_import_index].source_artifact_sha256
                and pair.confirmation_overlap_relation
                in {
                    HistoricalSuccessQualificationOverlapRelation.PARTIAL_OVERLAP,
                    HistoricalSuccessQualificationOverlapRelation.DISJOINT,
                }
            ),
        )
        for pair in pairs
    )
    expected_pair_count = len(imports) * (len(imports) - 1) // 2

    if any(
        item.source_observation_count == 0
        or item.strategy_window_status
        is not HistoricalSuccessQualificationEvidenceStatus.COMPLETE
        or item.temporal_holdout_status
        is not HistoricalSuccessQualificationEvidenceStatus.COMPLETE
        for item in imports
    ):
        primary_status = HistoricalSuccessQualificationPrimaryStatus.NOT_READY
        flags: set[HistoricalSuccessQualificationInformationalFlag] = set()
    elif (
        len(imports) < 2
        or any(not pair.r1_comparable for pair in pair_evidence)
        or census_status is not HistoricalSuccessQualificationCensusStatus.COMPLETE
        or len(pair_evidence) != expected_pair_count
        or cohort_census_count != 64
        or len(cohort_summaries) != 64
        or any(
            summary not in _QUALIFYING_CENSUS_SUMMARIES
            for summary in cohort_summaries
        )
    ):
        primary_status = (
            HistoricalSuccessQualificationPrimaryStatus.EVIDENCE_INCOMPLETE
        )
        flags = {
            HistoricalSuccessQualificationInformationalFlag.CROSS_IMPORT_UNRESOLVED
        }
    else:
        primary_status = (
            HistoricalSuccessQualificationPrimaryStatus.RESEARCH_CANDIDATE
        )
        flags = {
            HistoricalSuccessQualificationInformationalFlag.HISTORICAL_CONCORDANCE_OBSERVED
        }

    if (
        primary_status
        is not HistoricalSuccessQualificationPrimaryStatus.NOT_READY
        and any(
            item.recent_audit_status
            is HistoricalSuccessQualificationEvidenceStatus.COMPLETE
            and item.recent_relationship_difference_count > 0
            for item in imports
        )
    ):
        flags.add(
            HistoricalSuccessQualificationInformationalFlag.RECENT_RELATIONSHIP_DIFFERENCE
        )

    comparable_indexes = {
        index
        for pair in pair_evidence
        if pair.r1_comparable
        for index in (pair.left_import_index, pair.right_import_index)
    }
    return HistoricalSuccessResearchQualification(
        identity=identity,
        imports=imports,
        primary_status=primary_status,
        informational_flags=tuple(
            flag for flag in INFORMATIONAL_FLAG_ORDER if flag in flags
        ),
        random_baseline_caveat=(
            RANDOM_BASELINE_CAVEAT
            if primary_status
            is HistoricalSuccessQualificationPrimaryStatus.RESEARCH_CANDIDATE
            else None
        ),
        comparable_import_count=len(comparable_indexes),
        expected_pair_count=expected_pair_count,
        actual_pair_count=len(pair_evidence),
        census_status=census_status,
        cohort_census_count=cohort_census_count,
        pairs=pair_evidence,
    )


__all__ = [
    "INFORMATIONAL_FLAG_ORDER",
    "RANDOM_BASELINE_CAVEAT",
    "HistoricalSuccessQualificationCensusStatus",
    "HistoricalSuccessQualificationCensusSummary",
    "HistoricalSuccessQualificationContractError",
    "HistoricalSuccessQualificationEvidenceStatus",
    "HistoricalSuccessQualificationIdentity",
    "HistoricalSuccessQualificationImportEvidence",
    "HistoricalSuccessQualificationInformationalFlag",
    "HistoricalSuccessQualificationOverlapRelation",
    "HistoricalSuccessQualificationPairEvidence",
    "HistoricalSuccessQualificationPairInput",
    "HistoricalSuccessQualificationPairStatus",
    "HistoricalSuccessQualificationPrimaryStatus",
    "HistoricalSuccessResearchQualification",
    "qualify_historical_success",
]
