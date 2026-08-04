"""Materialize the complete caller-ordered target x strategy attempt matrix."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from lottolab.application.ports import (
    OrderedCandidateMaterializationReaderFactory,
    OrderedCandidatePackageWriterFactory,
)
from lottolab.application.use_cases.generate_bet import GenerateOneBetStatus
from lottolab.application.use_cases.generate_ordered_candidate_emission import (
    GenerateOrderedCandidateEmission,
    GenerateOrderedCandidateEmissionInput,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_materialization import (
    OrderedCandidateMaterializationAttempt,
    OrderedCandidateMaterializationStatus,
    OrderedCandidateMaterializationSummary,
    OrderedCandidateSourceRow,
    attempt_from_emission,
)
from lottolab.evidence.canonical_json import sha256_hex
from lottolab.evidence.ordered_candidate_emission_artifact import (
    build_ordered_candidate_emission_artifact,
    serialize_ordered_candidate_emission_artifact,
)
from lottolab.evidence.ordered_candidate_emission_package import (
    OrderedCandidateEmissionFile,
    build_ordered_candidate_emission_package,
)
from lottolab.strategies.adapters.base import CausalDrawRow

_ASCII_DECIMAL = re.compile(r"[0-9]+", flags=re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_STRATEGY_ID = re.compile(r"[a-z0-9][a-z0-9_]{0,127}", flags=re.ASCII)

_STATUS_MAP = {
    GenerateOneBetStatus.REJECTED: OrderedCandidateMaterializationStatus.REJECTED,
    GenerateOneBetStatus.INSUFFICIENT_HISTORY: (
        OrderedCandidateMaterializationStatus.INSUFFICIENT_HISTORY
    ),
    GenerateOneBetStatus.STRATEGY_UNAVAILABLE: (
        OrderedCandidateMaterializationStatus.STRATEGY_UNAVAILABLE
    ),
    GenerateOneBetStatus.INVALID_OUTPUT: (
        OrderedCandidateMaterializationStatus.INVALID_OUTPUT
    ),
    GenerateOneBetStatus.REPLAY_ERROR: OrderedCandidateMaterializationStatus.REPLAY_ERROR,
    GenerateOneBetStatus.WRONG_RESPONSE_PATH: (
        OrderedCandidateMaterializationStatus.STRATEGY_UNAVAILABLE
    ),
}


class OrderedCandidateMaterializationError(RuntimeError):
    """Base caller-safe failure for package-fatal materialization errors."""


class OrderedCandidateMaterializationInputError(OrderedCandidateMaterializationError):
    """Caller input violates the frozen R1 contract."""


class SourceSnapshotMismatchError(OrderedCandidateMaterializationError):
    """The expected source identity differs from the exact current source."""


class OrderedCandidateMaterializationStorageError(
    OrderedCandidateMaterializationError
):
    """The reader or atomic writer failed before a valid seal was established."""


@dataclass(frozen=True, slots=True)
class MaterializeOrderedCandidateEmissionsInput:
    lottery_type: LotteryType
    dataset_id: str
    dataset_version: str
    expected_source_snapshot_sha256: str
    target_draws: tuple[str, ...]
    strategy_ids: tuple[str, ...]
    minimum_history_draws: int
    maximum_history_draws: int
    replicate: int
    output_directory: Path


class MaterializeOrderedCandidateEmissions:
    """Read one source snapshot, execute every attempt once, then seal once."""

    def __init__(
        self,
        *,
        reader_factory: OrderedCandidateMaterializationReaderFactory,
        writer_factory: OrderedCandidatePackageWriterFactory,
        generate_ordered_candidate_emission: GenerateOrderedCandidateEmission,
    ) -> None:
        self._reader_factory = reader_factory
        self._writer_factory = writer_factory
        self._generate = generate_ordered_candidate_emission

    def execute(
        self,
        request: MaterializeOrderedCandidateEmissionsInput,
    ) -> OrderedCandidateMaterializationSummary:
        _validate_request(request)

        try:
            snapshot = self._reader_factory().read_source_snapshot(
                request.lottery_type
            )
        except OrderedCandidateMaterializationError:
            raise
        except Exception as exc:
            raise OrderedCandidateMaterializationStorageError(
                "source snapshot could not be read safely"
            ) from exc
        if (
            snapshot.source_snapshot_sha256
            != request.expected_source_snapshot_sha256
        ):
            raise SourceSnapshotMismatchError(
                "source snapshot SHA-256 does not match the expected identity"
            )

        attempts: list[OrderedCandidateMaterializationAttempt] = []
        emission_files: list[OrderedCandidateEmissionFile] = []
        by_draw = {row.draw_number: index for index, row in enumerate(snapshot.rows)}
        ordinal = 0
        for target_ordinal, target_draw in enumerate(request.target_draws):
            target_index = by_draw.get(target_draw)
            if target_index is None:
                for strategy_ordinal, strategy_id in enumerate(
                    request.strategy_ids
                ):
                    attempts.append(
                        _failed_attempt(
                            ordinal=ordinal,
                            target_ordinal=target_ordinal,
                            strategy_ordinal=strategy_ordinal,
                            target_draw=target_draw,
                            strategy_id=strategy_id,
                            status=OrderedCandidateMaterializationStatus.TARGET_NOT_FOUND,
                            reason_code="TARGET_DRAW_NOT_FOUND",
                        )
                    )
                    ordinal += 1
                continue

            bounded_rows = snapshot.rows[:target_index][
                -request.maximum_history_draws :
            ]
            if len(bounded_rows) < request.minimum_history_draws:
                for strategy_ordinal, strategy_id in enumerate(
                    request.strategy_ids
                ):
                    attempts.append(
                        _failed_attempt(
                            ordinal=ordinal,
                            target_ordinal=target_ordinal,
                            strategy_ordinal=strategy_ordinal,
                            target_draw=target_draw,
                            strategy_id=strategy_id,
                            status=(
                                OrderedCandidateMaterializationStatus.INSUFFICIENT_HISTORY
                            ),
                            reason_code="AVAILABLE_HISTORY_BELOW_MINIMUM",
                        )
                    )
                    ordinal += 1
                continue

            history = tuple(_adapter_row(row) for row in bounded_rows)
            history_cutoff = bounded_rows[-1].draw_number
            for strategy_ordinal, strategy_id in enumerate(request.strategy_ids):
                attempt, emission_file = self._execute_attempt(
                    ordinal=ordinal,
                    target_ordinal=target_ordinal,
                    strategy_ordinal=strategy_ordinal,
                    target_draw=target_draw,
                    strategy_id=strategy_id,
                    history=history,
                    history_cutoff=history_cutoff,
                )
                attempts.append(attempt)
                if emission_file is not None:
                    emission_files.append(emission_file)
                ordinal += 1

        package = build_ordered_candidate_emission_package(
            dataset_id=request.dataset_id,
            dataset_version=request.dataset_version,
            source_snapshot_sha256_value=snapshot.source_snapshot_sha256,
            target_draws=request.target_draws,
            strategy_ids=request.strategy_ids,
            minimum_history_draws=request.minimum_history_draws,
            maximum_history_draws=request.maximum_history_draws,
            replicate=request.replicate,
            attempts=tuple(attempts),
            emission_files=tuple(emission_files),
        )
        try:
            self._writer_factory().write_package(
                request.output_directory,
                package,
            )
        except OrderedCandidateMaterializationError:
            raise
        except Exception as exc:
            raise OrderedCandidateMaterializationStorageError(
                "package could not be sealed safely"
            ) from exc

        counts = Counter(attempt.status for attempt in attempts)
        return OrderedCandidateMaterializationSummary(
            output_directory=str(request.output_directory),
            source_snapshot_sha256=snapshot.source_snapshot_sha256,
            attempt_count=len(attempts),
            ok_attempt_count=counts.get(
                OrderedCandidateMaterializationStatus.OK,
                0,
            ),
            status_counts=tuple(
                (status, counts.get(status, 0))
                for status in OrderedCandidateMaterializationStatus
            ),
        )

    def _execute_attempt(
        self,
        *,
        ordinal: int,
        target_ordinal: int,
        strategy_ordinal: int,
        target_draw: str,
        strategy_id: str,
        history: tuple[CausalDrawRow, ...],
        history_cutoff: str,
    ) -> tuple[
        OrderedCandidateMaterializationAttempt,
        OrderedCandidateEmissionFile | None,
    ]:
        try:
            result = self._generate.execute(
                GenerateOrderedCandidateEmissionInput(
                    strategy_id=strategy_id,
                    lottery_type=LotteryType.BIG_LOTTO,
                    history=history,
                    replicate=1,
                    target_draw=target_draw,
                    history_cutoff=history_cutoff,
                )
            )
        except Exception:
            return (
                _failed_attempt(
                    ordinal=ordinal,
                    target_ordinal=target_ordinal,
                    strategy_ordinal=strategy_ordinal,
                    target_draw=target_draw,
                    strategy_id=strategy_id,
                    status=OrderedCandidateMaterializationStatus.REPLAY_ERROR,
                    reason_code="REPLAY_ERROR",
                    history_cutoff=history_cutoff,
                ),
                None,
            )

        if result.legal_bet.status is not GenerateOneBetStatus.OK:
            reason = result.legal_bet.reason_code
            return (
                _failed_attempt(
                    ordinal=ordinal,
                    target_ordinal=target_ordinal,
                    strategy_ordinal=strategy_ordinal,
                    target_draw=target_draw,
                    strategy_id=strategy_id,
                    status=_STATUS_MAP[result.legal_bet.status],
                    reason_code=(
                        reason.value if reason is not None else result.legal_bet.status.value
                    ),
                    history_cutoff=history_cutoff,
                ),
                None,
            )

        emission = result.emission
        assert emission is not None
        artifact = build_ordered_candidate_emission_artifact(emission)
        data = serialize_ordered_candidate_emission_artifact(artifact)
        file_sha256 = sha256_hex(data)
        attempt = attempt_from_emission(
            ordinal=ordinal,
            target_ordinal=target_ordinal,
            strategy_ordinal=strategy_ordinal,
            emission=emission,
            emission_payload_sha256=artifact.payload_sha256,
            emission_file_sha256=file_sha256,
        )
        assert attempt.emission_relative_path is not None
        return (
            attempt,
            OrderedCandidateEmissionFile(
                relative_path=attempt.emission_relative_path,
                data=data,
                payload_sha256=artifact.payload_sha256,
                file_sha256=file_sha256,
            ),
        )


def _validate_request(request: MaterializeOrderedCandidateEmissionsInput) -> None:
    if type(request.replicate) is not int or request.replicate != 1:
        raise OrderedCandidateMaterializationInputError(
            "replicate must be exactly 1"
        )
    if request.lottery_type is not LotteryType.BIG_LOTTO:
        raise OrderedCandidateMaterializationInputError(
            "lottery_type must be BIG_LOTTO"
        )
    for value, name in (
        (request.dataset_id, "dataset_id"),
        (request.dataset_version, "dataset_version"),
    ):
        if type(value) is not str or not value or value != value.strip():
            raise OrderedCandidateMaterializationInputError(
                f"{name} must be a non-empty canonical string"
            )
    if (
        type(request.expected_source_snapshot_sha256) is not str
        or _SHA256.fullmatch(request.expected_source_snapshot_sha256) is None
    ):
        raise OrderedCandidateMaterializationInputError(
            "expected source snapshot SHA-256 is invalid"
        )
    if not request.target_draws or any(
        type(draw) is not str or _ASCII_DECIMAL.fullmatch(draw) is None
        for draw in request.target_draws
    ):
        raise OrderedCandidateMaterializationInputError(
            "target draws must be non-empty ASCII decimal identities"
        )
    if len(set(request.target_draws)) != len(request.target_draws):
        raise OrderedCandidateMaterializationInputError(
            "target draws must not contain duplicates"
        )
    if not request.strategy_ids or any(
        type(strategy_id) is not str
        or _STRATEGY_ID.fullmatch(strategy_id) is None
        for strategy_id in request.strategy_ids
    ):
        raise OrderedCandidateMaterializationInputError(
            "strategy IDs must be non-empty path-safe canonical ASCII"
        )
    if len(set(request.strategy_ids)) != len(request.strategy_ids):
        raise OrderedCandidateMaterializationInputError(
            "strategy IDs must not contain duplicates"
        )
    if (
        type(request.minimum_history_draws) is not int
        or request.minimum_history_draws <= 0
        or type(request.maximum_history_draws) is not int
        or request.maximum_history_draws <= 0
    ):
        raise OrderedCandidateMaterializationInputError(
            "history bounds must be positive integers"
        )
    if request.minimum_history_draws > request.maximum_history_draws:
        raise OrderedCandidateMaterializationInputError(
            "minimum history draws must not exceed maximum"
        )
    if not isinstance(cast(object, request.output_directory), Path) or not (
        request.output_directory.is_absolute()
    ):
        raise OrderedCandidateMaterializationInputError(
            "output directory must be an absolute path"
        )
    if request.output_directory.exists() or request.output_directory.is_symlink():
        raise OrderedCandidateMaterializationInputError(
            "output directory must be absent"
        )


def _adapter_row(row: OrderedCandidateSourceRow) -> CausalDrawRow:
    return CausalDrawRow(
        draw=row.draw_number,
        date=row.draw_date.isoformat(),
        numbers=row.main_numbers,
    )


def _failed_attempt(
    *,
    ordinal: int,
    target_ordinal: int,
    strategy_ordinal: int,
    target_draw: str,
    strategy_id: str,
    status: OrderedCandidateMaterializationStatus,
    reason_code: str,
    history_cutoff: str | None = None,
) -> OrderedCandidateMaterializationAttempt:
    return OrderedCandidateMaterializationAttempt(
        ordinal=ordinal,
        target_ordinal=target_ordinal,
        strategy_ordinal=strategy_ordinal,
        target_draw=target_draw,
        strategy_id=strategy_id,
        status=status,
        reason_code=reason_code,
        history_cutoff=history_cutoff,
    )


__all__ = [
    "MaterializeOrderedCandidateEmissions",
    "MaterializeOrderedCandidateEmissionsInput",
    "OrderedCandidateMaterializationError",
    "OrderedCandidateMaterializationInputError",
    "OrderedCandidateMaterializationStorageError",
    "SourceSnapshotMismatchError",
]
