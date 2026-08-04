"""Preview and persist legacy CSV/ZIP historical draw imports."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import date
from pathlib import PurePath

from lottolab.application.ports import HistoricalArchiveParser, HistoricalDrawImportRepository
from lottolab.domain.historical_archive import (
    ArchiveMember,
    DatasetClassification,
    ParsedDraw,
    StructuralIssue,
)
from lottolab.domain.historical_draw_import import (
    ExistingHistoricalDraw,
    HistoricalDrawCandidate,
    HistoricalImportBatchStatus,
    HistoricalImportChunkResult,
    HistoricalImportDisposition,
    HistoricalImportFileResult,
    HistoricalImportFileStatus,
    HistoricalImportFilter,
    HistoricalImportInput,
    HistoricalImportReason,
    HistoricalImportResult,
    HistoricalImportRowResult,
    HistoricalImportSummary,
    StoredImportRun,
)
from lottolab.domain.historical_results import HistoricalLotteryType

MAX_IMPORT_CHUNK_ROWS = 500


class HistoricalDrawImportError(RuntimeError):
    """The historical draw import could not complete safely."""


class HistoricalDrawImportInputError(ValueError):
    """The caller supplied an invalid display filename or empty input list."""


@dataclass(frozen=True, slots=True)
class _CandidateLink:
    candidate: HistoricalDrawCandidate
    row_index: int


def _new_string_set() -> set[str]:
    return set()


def _new_row_list() -> list[HistoricalImportRowResult]:
    return []


def _new_candidate_link_list() -> list[_CandidateLink]:
    return []


@dataclass(slots=True)
class _FileWork:
    input_file: HistoricalImportInput
    source_sha256: str
    discovered_members: int = 0
    accepted_member_paths: set[str] = field(default_factory=_new_string_set)
    rows: list[HistoricalImportRowResult] = field(default_factory=_new_row_list)
    candidate_links: list[_CandidateLink] = field(default_factory=_new_candidate_link_list)
    parsed_rows: int = 0
    valid_rows: int = 0
    excluded_rows: int = 0
    duplicate_rows: int = 0
    conflict_rows: int = 0
    imported_rows: int = 0
    failed_rows: int = 0
    has_parse_failure: bool = False


@dataclass(frozen=True, slots=True)
class _ParsedInput:
    source_sha256: str
    members: tuple[ArchiveMember, ...]
    draws: tuple[ParsedDraw, ...]
    issues: tuple[StructuralIssue, ...]
    corrupt: bool


@dataclass(frozen=True, slots=True)
class _Analysis:
    files: tuple[_FileWork, ...]
    candidates: tuple[_CandidateLink, ...]
    import_identity_sha256: str


_ISSUE_REASON: Mapping[str, HistoricalImportReason] = {
    "INVALID_DRAW_IDENTITY": HistoricalImportReason.INVALID_DRAW_IDENTITY,
    "INVALID_DRAW_DATE": HistoricalImportReason.INVALID_DRAW_DATE,
    "INVALID_INTEGER": HistoricalImportReason.INVALID_NUMBER_VALUE,
    "MISSING_MAIN_NUMBER_COLUMNS": HistoricalImportReason.INVALID_NUMBER_COUNT,
    "ZONE1_OUT_OF_RANGE": HistoricalImportReason.INVALID_NUMBER_RANGE,
    "DUPLICATE_ZONE1_VALUE": HistoricalImportReason.DUPLICATE_NUMBER,
    "MISSING_ZONE2": HistoricalImportReason.INVALID_SECOND_NUMBER,
    "UNEXPECTED_ZONE2": HistoricalImportReason.INVALID_SECOND_NUMBER,
    "ZONE2_OUT_OF_RANGE": HistoricalImportReason.INVALID_SECOND_NUMBER,
    "MISSING_SPECIAL_NUMBER": HistoricalImportReason.INVALID_SPECIAL_NUMBER,
    "SPECIAL_NUMBER_OUT_OF_RANGE": HistoricalImportReason.INVALID_SPECIAL_NUMBER,
    "SPECIAL_NUMBER_OVERLAP": HistoricalImportReason.INVALID_SPECIAL_NUMBER,
    "EXTRA_NON_EMPTY_FIELDS": HistoricalImportReason.PARSE_ERROR,
    "DUPLICATE_HEADER": HistoricalImportReason.PARSE_ERROR,
    "UNSUPPORTED_ENCODING": HistoricalImportReason.PARSE_ERROR,
    "CSV_PARSE_ERROR": HistoricalImportReason.PARSE_ERROR,
    "EMPTY_CSV": HistoricalImportReason.EMPTY_FILE,
    "UNSAFE_MEMBER_PATH": HistoricalImportReason.UNSAFE_ARCHIVE_MEMBER,
    "ENCRYPTED_MEMBER": HistoricalImportReason.ENCRYPTED_ARCHIVE_MEMBER,
    "CORRUPT_OR_UNSUPPORTED_MEMBER": HistoricalImportReason.CORRUPT_ZIP,
    "CORRUPT_ZIP_ARCHIVE": HistoricalImportReason.CORRUPT_ZIP,
}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256(encoded.encode("utf-8"))


def _validate_filename(filename: str) -> None:
    if not filename or not filename.strip():
        raise HistoricalDrawImportInputError("filename must contain display text")
    if len(filename) > 255 or any(ord(character) < 32 for character in filename):
        raise HistoricalDrawImportInputError("filename is not valid display text")
    if filename != PurePath(filename).name or filename in {".", ".."}:
        raise HistoricalDrawImportInputError("filename must not contain a path")


def _is_bingo(*values: str) -> bool:
    return any("賓果" in value or "bingo" in value.casefold() for value in values)


def _is_bonus(*values: str) -> bool:
    return any("加開" in value or "bonus" in value.casefold() for value in values)


def _classification_to_lottery(
    classification: DatasetClassification,
) -> HistoricalLotteryType | None:
    try:
        return HistoricalLotteryType(classification.value)
    except ValueError:
        return None


def _reason_for_issue(issue: StructuralIssue) -> HistoricalImportReason:
    return _ISSUE_REASON.get(issue.code, HistoricalImportReason.PARSE_ERROR)


def _first_error(issues: Sequence[StructuralIssue]) -> StructuralIssue | None:
    return next((issue for issue in issues if issue.severity == "ERROR"), None)


def _normalized_record_hash(
    lottery_type: HistoricalLotteryType,
    draw_number: str,
    draw_date: date,
    main_numbers: tuple[int, ...],
    special_numbers: tuple[int, ...],
) -> str:
    return _canonical_hash(
        {
            "draw_date": draw_date.isoformat(),
            "draw_number": draw_number,
            "lottery_type": lottery_type.value,
            "main_numbers": sorted(main_numbers),
            "special_numbers": sorted(special_numbers),
        }
    )


def _parsed_input(
    input_file: HistoricalImportInput,
    source_sha256: str,
    parser: HistoricalArchiveParser,
) -> _ParsedInput:
    suffix = PurePath(input_file.filename).suffix.casefold()
    if not input_file.content:
        return _ParsedInput(source_sha256, (), (), (), False)
    if suffix == ".csv":
        member, draws, issues = parser.parse_csv_bytes(
            input_file.content,
            archive_path=input_file.filename,
            member_path=input_file.filename,
        )
        return _ParsedInput(source_sha256, (member,), draws, issues, False)
    if suffix == ".zip":
        members, draws, issues, corrupt = parser.parse_zip_bytes(
            input_file.content,
            archive_path=input_file.filename,
        )
        return _ParsedInput(source_sha256, members, draws, issues, corrupt)
    return _ParsedInput(source_sha256, (), (), (), False)


def _file_status(work: _FileWork, *, preview: bool) -> HistoricalImportFileStatus:
    candidate_count = len(work.candidate_links)
    if candidate_count == 0:
        return (
            HistoricalImportFileStatus.FAILED
            if work.has_parse_failure
            else HistoricalImportFileStatus.EXCLUDED
        )
    if preview:
        return (
            HistoricalImportFileStatus.PARTIAL_SUCCESS
            if work.excluded_rows or work.has_parse_failure
            else HistoricalImportFileStatus.ACCEPTED
        )
    if work.failed_rows or work.has_parse_failure:
        return (
            HistoricalImportFileStatus.PARTIAL_SUCCESS
            if work.imported_rows
            else HistoricalImportFileStatus.FAILED
        )
    return (
        HistoricalImportFileStatus.PARTIAL_SUCCESS
        if work.excluded_rows
        else HistoricalImportFileStatus.ACCEPTED
    )


def _file_result(work: _FileWork, *, preview: bool) -> HistoricalImportFileResult:
    return HistoricalImportFileResult(
        filename=work.input_file.filename,
        source_sha256=work.source_sha256,
        status=_file_status(work, preview=preview),
        discovered_members=work.discovered_members,
        accepted_files=len(work.accepted_member_paths),
        excluded_files=max(work.discovered_members - len(work.accepted_member_paths), 0),
        parsed_rows=work.parsed_rows,
        valid_rows=work.valid_rows,
        excluded_rows=work.excluded_rows,
        duplicate_rows=work.duplicate_rows,
        conflict_rows=work.conflict_rows,
        imported_rows=0 if preview else work.imported_rows,
        failed_rows=0 if preview else work.failed_rows,
        rows=tuple(work.rows),
    )


def _summary(
    files: Sequence[HistoricalImportFileResult],
    chunks: Sequence[HistoricalImportChunkResult],
) -> HistoricalImportSummary:
    return HistoricalImportSummary(
        discovered_files=len(files),
        accepted_files=sum(item.accepted_files for item in files),
        excluded_files=sum(item.excluded_files for item in files),
        parsed_rows=sum(item.parsed_rows for item in files),
        valid_rows=sum(item.valid_rows for item in files),
        excluded_rows=sum(item.excluded_rows for item in files),
        duplicate_rows=sum(item.duplicate_rows for item in files),
        conflict_rows=sum(item.conflict_rows for item in files),
        imported_rows=sum(item.imported_rows for item in files),
        failed_rows=sum(item.failed_rows for item in files),
        committed_chunks=sum(item.status.value == "COMMITTED" for item in chunks),
        failed_chunks=sum(item.status.value == "FAILED" for item in chunks),
    )


def _result_from_stored(stored: StoredImportRun) -> HistoricalImportResult:
    files = stored.files
    return HistoricalImportResult(
        run_id=stored.run_id,
        status=stored.status,
        lottery_filter=stored.lottery_filter,
        files=files,
        chunks=stored.chunks,
        summary=_summary(files, stored.chunks),
        row_results=stored.rows,
    )


class HistoricalDrawImportService:
    """Application service shared by preview, import, and run retrieval."""

    def __init__(
        self,
        repository: HistoricalDrawImportRepository,
        parser: HistoricalArchiveParser,
        *,
        chunk_size: int = MAX_IMPORT_CHUNK_ROWS,
    ) -> None:
        if not 1 <= chunk_size <= MAX_IMPORT_CHUNK_ROWS:
            raise ValueError("chunk_size must be between 1 and 500")
        self._repository = repository
        self._parser = parser
        self._chunk_size = chunk_size

    def preview(
        self,
        inputs: Sequence[HistoricalImportInput],
        *,
        lottery_filter: HistoricalImportFilter = HistoricalImportFilter.ALL,
    ) -> HistoricalImportResult:
        analysis = self._analyze(inputs, lottery_filter=lottery_filter)
        files = tuple(_file_result(work, preview=True) for work in analysis.files)
        return HistoricalImportResult(
            run_id=None,
            status=HistoricalImportBatchStatus.PREVIEW,
            lottery_filter=lottery_filter,
            files=files,
            chunks=(),
            summary=_summary(files, ()),
            row_results=tuple(row for file_result in files for row in file_result.rows),
        )

    def import_inputs(
        self,
        inputs: Sequence[HistoricalImportInput],
        *,
        lottery_filter: HistoricalImportFilter = HistoricalImportFilter.ALL,
    ) -> HistoricalImportResult:
        self._repository.ensure_schema()
        analysis = self._analyze(inputs, lottery_filter=lottery_filter)
        initial_files = tuple(_file_result(work, preview=True) for work in analysis.files)
        storage = self._repository.create_run(
            lottery_filter=lottery_filter,
            import_identity_sha256=analysis.import_identity_sha256,
            files=initial_files,
            rows=tuple(row for file_result in initial_files for row in file_result.rows),
        )
        row_offsets: list[int] = []
        offset = 0
        for file_result in initial_files:
            row_offsets.append(offset)
            offset += len(file_result.rows)

        for chunk_index, start in enumerate(range(0, len(analysis.candidates), self._chunk_size)):
            links = analysis.candidates[start : start + self._chunk_size]
            candidate_rows = tuple(link.candidate for link in links)
            row_ids = tuple(
                storage.row_ids[
                    row_offsets[self._file_index(analysis.files, link)] + link.row_index
                ]
                for link in links
            )
            try:
                self._repository.commit_chunk(
                    run_id=storage.run_id,
                    chunk_index=chunk_index,
                    batch_identity_sha256=analysis.import_identity_sha256,
                    candidates=candidate_rows,
                    row_ids=row_ids,
                )
                for link in links:
                    self._work_for_link(analysis.files, link).imported_rows += 1
            except Exception as exc:
                with suppress(Exception):
                    self._repository.record_failed_chunk(
                        run_id=storage.run_id,
                        chunk_index=chunk_index,
                        candidate_rows=len(links),
                        row_ids=row_ids,
                        error_message=str(exc),
                    )
                for link in links:
                    self._work_for_link(analysis.files, link).failed_rows += 1

        final_files = tuple(_file_result(work, preview=False) for work in analysis.files)
        self._repository.update_files(run_id=storage.run_id, files=final_files)
        imported_rows = sum(item.imported_rows for item in final_files)
        failed_rows = sum(item.failed_rows for item in final_files)
        parse_failures = any(work.has_parse_failure for work in analysis.files)
        status = (
            HistoricalImportBatchStatus.PARTIAL_SUCCESS
            if imported_rows and (failed_rows or parse_failures)
            else HistoricalImportBatchStatus.FAILED
            if failed_rows or parse_failures
            else HistoricalImportBatchStatus.COMPLETED
        )
        self._repository.complete_run(run_id=storage.run_id, status=status)
        stored = self._repository.get_run(storage.run_id)
        if stored is None:
            raise HistoricalDrawImportError("completed historical import could not be read back")
        return _result_from_stored(stored)

    def get_run(self, run_id: str) -> HistoricalImportResult | None:
        stored = self._repository.get_run(run_id)
        return None if stored is None else _result_from_stored(stored)

    def _analyze(
        self,
        inputs: Sequence[HistoricalImportInput],
        *,
        lottery_filter: HistoricalImportFilter,
    ) -> _Analysis:
        if not inputs:
            raise HistoricalDrawImportInputError("at least one file is required")
        normalized_inputs = tuple(inputs)
        for input_file in normalized_inputs:
            _validate_filename(input_file.filename)
        ordered_inputs = tuple(
            sorted(
                normalized_inputs,
                key=lambda item: (item.filename.casefold(), _sha256(item.content)),
            )
        )
        existing = self._repository.load_existing_draws()
        seen: dict[tuple[HistoricalLotteryType, str], ExistingHistoricalDraw] = dict(existing)
        works: list[_FileWork] = []
        all_candidates: list[_CandidateLink] = []
        for input_file in ordered_inputs:
            source_sha256 = _sha256(input_file.content)
            work = _FileWork(input_file=input_file, source_sha256=source_sha256)
            works.append(work)
            parsed = _parsed_input(input_file, source_sha256, self._parser)
            work.discovered_members = len(parsed.members) or (1 if input_file.content else 0)
            self._analyze_input(
                work,
                parsed,
                lottery_filter=lottery_filter,
                seen=seen,
            )
            file_index = len(works) - 1
            all_candidates.extend(
                _CandidateLink(link.candidate, row_index=link.row_index)
                for link in work.candidate_links
            )
            del file_index
        identity = _canonical_hash(
            {
                "files": [
                    {"filename": work.input_file.filename, "sha256": work.source_sha256}
                    for work in works
                ],
                "lottery_filter": lottery_filter.value,
            }
        )
        return _Analysis(tuple(works), tuple(all_candidates), identity)

    def _analyze_input(
        self,
        work: _FileWork,
        parsed: _ParsedInput,
        *,
        lottery_filter: HistoricalImportFilter,
        seen: dict[tuple[HistoricalLotteryType, str], ExistingHistoricalDraw],
    ) -> None:
        filename = work.input_file.filename
        member_by_path = {member.member_path: member for member in parsed.members}
        fatal_member_issues: dict[str, list[StructuralIssue]] = {}
        for issue in parsed.issues:
            if issue.severity == "ERROR" and issue.row_number is None and issue.member_path:
                fatal_member_issues.setdefault(issue.member_path, []).append(issue)
        for issue in parsed.issues:
            if issue.severity != "ERROR" or issue.row_number is not None:
                continue
            if issue.member_path and issue.member_path in member_by_path:
                self._append_issue_row(work, issue, member_by_path[issue.member_path])
            elif not parsed.draws:
                self._append_issue_row(work, issue, None)
                work.has_parse_failure = True
        if not work.input_file.content:
            self._append_row(
                work,
                member_path=filename,
                member_sha256=None,
                source_row_number=None,
                disposition=HistoricalImportDisposition.EXCLUDED,
                reason_code=HistoricalImportReason.EMPTY_FILE,
                message="file is empty",
            )
            work.has_parse_failure = True
            return
        if PurePath(filename).suffix.casefold() not in {".csv", ".zip"}:
            self._append_row(
                work,
                member_path=filename,
                member_sha256=None,
                source_row_number=None,
                disposition=HistoricalImportDisposition.EXCLUDED,
                reason_code=HistoricalImportReason.UNSUPPORTED_FILE_TYPE,
                message="only CSV and ZIP files are supported",
            )
            work.has_parse_failure = True
            return
        if parsed.corrupt and not parsed.members:
            return

        draws_by_member: dict[str, list[ParsedDraw]] = {}
        for draw in parsed.draws:
            draws_by_member.setdefault(draw.member_path, []).append(draw)
        for member in parsed.members:
            member_errors = fatal_member_issues.get(member.member_path, [])
            member_draws = draws_by_member.get(member.member_path, [])
            if not member_draws:
                if member_errors:
                    continue
                reason = (
                    HistoricalImportReason.UNSUPPORTED_BONUS_DRAW
                    if _is_bonus(filename, member.member_path)
                    else HistoricalImportReason.UNKNOWN_GAME_TYPE
                    if member.classification is DatasetClassification.UNKNOWN
                    else HistoricalImportReason.UNSUPPORTED_TARGET_LOTTERY
                    if member.classification is DatasetClassification.OTHER
                    else HistoricalImportReason.UNSUPPORTED_FILE_TYPE
                )
                self._append_row(
                    work,
                    member_path=member.member_path,
                    member_sha256=member.member_sha256,
                    source_row_number=None,
                    disposition=HistoricalImportDisposition.EXCLUDED,
                    reason_code=reason,
                    message="archive member has no importable draw rows",
                )
                continue
            for draw in member_draws:
                self._analyze_draw(
                    work,
                    draw,
                    member,
                    lottery_filter=lottery_filter,
                    seen=seen,
                )

    def _analyze_draw(
        self,
        work: _FileWork,
        draw: ParsedDraw,
        member: ArchiveMember,
        *,
        lottery_filter: HistoricalImportFilter,
        seen: dict[tuple[HistoricalLotteryType, str], ExistingHistoricalDraw],
    ) -> None:
        work.parsed_rows += 1
        lottery_type = _classification_to_lottery(draw.classification)
        if _is_bingo(work.input_file.filename, draw.member_path, draw.raw_lottery_name):
            self._append_draw_rejection(
                work,
                draw,
                member,
                reason_code=HistoricalImportReason.BINGO_EXCLUDED,
                message="Bingo data is excluded from the historical draw import",
                lottery_type=lottery_type,
            )
            return
        if _is_bonus(work.input_file.filename, draw.member_path, draw.raw_lottery_name):
            self._append_draw_rejection(
                work,
                draw,
                member,
                reason_code=HistoricalImportReason.UNSUPPORTED_BONUS_DRAW,
                message="bonus draws are outside the Historical V2 target",
                lottery_type=lottery_type,
            )
            return
        if lottery_type is None:
            reason = (
                HistoricalImportReason.UNKNOWN_GAME_TYPE
                if draw.classification is DatasetClassification.UNKNOWN
                else HistoricalImportReason.UNSUPPORTED_TARGET_LOTTERY
            )
            self._append_draw_rejection(
                work,
                draw,
                member,
                reason_code=reason,
                message="draw classification is outside the Historical V2 target",
                lottery_type=None,
            )
            return
        if (
            lottery_filter is not HistoricalImportFilter.ALL
            and lottery_type.value != lottery_filter.value
        ):
            self._append_draw_rejection(
                work,
                draw,
                member,
                reason_code=HistoricalImportReason.LOTTERY_FILTER_MISMATCH,
                message=f"draw does not match requested filter {lottery_filter.value}",
                lottery_type=lottery_type,
            )
            return
        error = _first_error(draw.issues)
        if error is not None or draw.draw_identity is None or draw.draw_date is None:
            issue = error or StructuralIssue(
                code="INVALID_DRAW_DATE",
                message="draw could not be normalized",
                row_number=draw.row_number,
            )
            self._append_draw_rejection(
                work,
                draw,
                member,
                reason_code=_reason_for_issue(issue),
                message=issue.message,
                lottery_type=lottery_type,
            )
            return
        draw_date = date.fromisoformat(draw.draw_date)
        main_numbers = tuple(sorted(draw.zone1))
        if lottery_type is HistoricalLotteryType.DAILY_539:
            special_numbers: tuple[int, ...] = ()
        elif draw.zone2 is None:
            self._append_draw_rejection(
                work,
                draw,
                member,
                reason_code=HistoricalImportReason.INVALID_SPECIAL_NUMBER,
                message="special number is missing",
                lottery_type=lottery_type,
            )
            return
        else:
            special_numbers = (draw.zone2,)
        normalized_hash = _normalized_record_hash(
            lottery_type,
            draw.draw_identity,
            draw_date,
            main_numbers,
            tuple(int(value) for value in special_numbers),
        )
        candidate = HistoricalDrawCandidate(
            source_filename=work.input_file.filename,
            source_sha256=work.source_sha256,
            member_path=draw.member_path,
            member_sha256=member.member_sha256,
            source_row_number=draw.row_number,
            lottery_type=lottery_type,
            draw_number=draw.draw_identity,
            draw_date=draw_date,
            main_numbers=main_numbers,
            special_numbers=tuple(int(value) for value in special_numbers),
            normalized_record_hash=normalized_hash,
        )
        key = (lottery_type, draw.draw_identity)
        previous = seen.get(key)
        if previous is not None:
            if previous.normalized_record_hash == normalized_hash:
                work.duplicate_rows += 1
                self._append_row(
                    work,
                    member_path=draw.member_path,
                    member_sha256=member.member_sha256,
                    source_row_number=draw.row_number,
                    disposition=HistoricalImportDisposition.DUPLICATE_SKIPPED,
                    reason_code=HistoricalImportReason.DUPLICATE_SKIPPED,
                    normalized_record_hash=normalized_hash,
                    message="identical draw already exists or appeared earlier in this batch",
                    lottery_type=lottery_type,
                    draw_number=draw.draw_identity,
                    draw_date=draw_date,
                    main_numbers=main_numbers,
                    special_numbers=tuple(int(value) for value in special_numbers),
                    historical_run_id=previous.historical_run_id or None,
                )
            else:
                work.conflict_rows += 1
                self._append_row(
                    work,
                    member_path=draw.member_path,
                    member_sha256=member.member_sha256,
                    source_row_number=draw.row_number,
                    disposition=HistoricalImportDisposition.CONFLICT_REJECTED,
                    reason_code=HistoricalImportReason.CONFLICT_REJECTED,
                    normalized_record_hash=normalized_hash,
                    message="draw identity already exists with different normalized data",
                    lottery_type=lottery_type,
                    draw_number=draw.draw_identity,
                    draw_date=draw_date,
                    main_numbers=main_numbers,
                    special_numbers=tuple(int(value) for value in special_numbers),
                    historical_run_id=previous.historical_run_id or None,
                )
            work.excluded_rows += 1
            return
        work.valid_rows += 1
        work.accepted_member_paths.add(member.member_path)
        row = self._append_row(
            work,
            member_path=draw.member_path,
            member_sha256=member.member_sha256,
            source_row_number=draw.row_number,
            disposition=HistoricalImportDisposition.ACCEPTED,
            normalized_record_hash=normalized_hash,
            message=None,
            lottery_type=lottery_type,
            draw_number=draw.draw_identity,
            draw_date=draw_date,
            main_numbers=main_numbers,
            special_numbers=tuple(int(value) for value in special_numbers),
        )
        work.candidate_links.append(_CandidateLink(candidate, row_index=row))
        seen[key] = ExistingHistoricalDraw(
            lottery_type=lottery_type,
            draw_number=draw.draw_identity,
            draw_date=draw_date,
            main_numbers=main_numbers,
            special_numbers=tuple(int(value) for value in special_numbers),
            normalized_record_hash=normalized_hash,
            historical_run_id="",
        )

    def _append_draw_rejection(
        self,
        work: _FileWork,
        draw: ParsedDraw,
        member: ArchiveMember,
        *,
        reason_code: HistoricalImportReason,
        message: str,
        lottery_type: HistoricalLotteryType | None,
    ) -> None:
        work.excluded_rows += 1
        work.has_parse_failure |= reason_code in {
            HistoricalImportReason.PARSE_ERROR,
            HistoricalImportReason.CORRUPT_ZIP,
            HistoricalImportReason.UNSAFE_ARCHIVE_MEMBER,
            HistoricalImportReason.ENCRYPTED_ARCHIVE_MEMBER,
        }
        self._append_row(
            work,
            member_path=draw.member_path,
            member_sha256=member.member_sha256,
            source_row_number=draw.row_number,
            disposition=HistoricalImportDisposition.EXCLUDED,
            reason_code=reason_code,
            normalized_record_hash=None,
            message=message,
            lottery_type=lottery_type,
            draw_number=draw.draw_identity,
        )

    def _append_issue_row(
        self,
        work: _FileWork,
        issue: StructuralIssue,
        member: ArchiveMember | None,
    ) -> None:
        reason = _reason_for_issue(issue)
        work.excluded_rows += 1
        work.has_parse_failure = True
        self._append_row(
            work,
            member_path=issue.member_path or work.input_file.filename,
            member_sha256=None if member is None else member.member_sha256,
            source_row_number=issue.row_number,
            disposition=HistoricalImportDisposition.EXCLUDED,
            reason_code=reason,
            message=issue.message,
        )

    def _append_row(
        self,
        work: _FileWork,
        *,
        member_path: str,
        member_sha256: str | None = None,
        source_row_number: int | None = None,
        disposition: HistoricalImportDisposition,
        reason_code: HistoricalImportReason | None = None,
        normalized_record_hash: str | None = None,
        message: str | None = None,
        lottery_type: HistoricalLotteryType | None = None,
        draw_number: str | None = None,
        draw_date: date | None = None,
        main_numbers: tuple[int, ...] = (),
        special_numbers: tuple[int, ...] = (),
        historical_run_id: str | None = None,
    ) -> int:
        row = HistoricalImportRowResult(
            source_filename=work.input_file.filename,
            source_sha256=work.source_sha256,
            member_path=member_path,
            member_sha256=member_sha256,
            source_row_number=source_row_number,
            lottery_type=lottery_type,
            draw_number=draw_number,
            disposition=disposition,
            reason_code=reason_code,
            normalized_record_hash=normalized_record_hash,
            message=message,
            historical_run_id=historical_run_id,
            draw_date=draw_date,
            main_numbers=main_numbers,
            special_numbers=special_numbers,
        )
        work.rows.append(row)
        return len(work.rows) - 1

    @staticmethod
    def _file_index(files: Sequence[_FileWork], link: _CandidateLink) -> int:
        for index, work in enumerate(files):
            if link in work.candidate_links:
                return index
        raise HistoricalDrawImportError("candidate link does not belong to import")

    @staticmethod
    def _work_for_link(files: Sequence[_FileWork], link: _CandidateLink) -> _FileWork:
        for work in files:
            if link in work.candidate_links:
                return work
        raise HistoricalDrawImportError("candidate link does not belong to import")


__all__ = [
    "MAX_IMPORT_CHUNK_ROWS",
    "HistoricalDrawImportError",
    "HistoricalDrawImportInputError",
    "HistoricalDrawImportService",
]
