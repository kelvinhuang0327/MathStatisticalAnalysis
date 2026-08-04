"""Deterministic expansion and parsing of legacy files and ZIP members."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import stat
import zipfile
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from lottolab.domain.batch_imports import (
    BatchDrawImportPreview,
    ImportBatchSummary,
    ImportExclusionReason,
    ImportFilePayload,
    ImportFileResult,
    ImportFileStatus,
    ImportIssue,
    issues_from_errors,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import DrawCsvParseResult, NormalizedDrawInput
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.imports.legacy_files import (
    LegacyFileFormatError,
    classify_game_name,
    decode_legacy_text,
    is_known_other_game,
    parse_legacy_csv,
    parse_legacy_daily539_txt,
)

MAX_IMPORT_FILE_BYTES = 4 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 500
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
SUPPORTED_LEAF_EXTENSIONS = frozenset({".csv", ".txt"})


@dataclass(frozen=True, slots=True)
class _LeafPayload:
    filename: str
    locator: str
    content: bytes
    source_sha256: str


def preview_import_batch(
    payloads: tuple[ImportFilePayload, ...],
) -> BatchDrawImportPreview:
    """Expand and parse inputs without opening a database or writing files."""

    file_results: list[ImportFileResult] = []
    normalized_rows: list[NormalizedDrawInput] = []
    leaves: list[_LeafPayload] = []
    for payload in sorted(payloads, key=lambda item: (item.filename.casefold(), item.filename)):
        leaves.extend(_expand_payload(payload, file_results))

    for leaf in leaves:
        parsed, excluded = _parse_leaf(leaf)
        if excluded is not None:
            file_results.append(excluded)
            continue
        if parsed is None:
            continue
        valid_rows = _valid_rows(parsed)
        normalized_rows.extend(valid_rows)
        status = ImportFileStatus.ACCEPTED
        if parsed.errors:
            status = ImportFileStatus.PARTIAL if valid_rows else ImportFileStatus.INVALID
        file_results.append(
            ImportFileResult(
                source_filename=leaf.filename,
                source_locator=leaf.locator,
                source_sha256=leaf.source_sha256,
                status=status,
                lottery_type=_single_lottery_type(valid_rows),
                discovered_rows=parsed.total_rows,
                accepted_rows=len(valid_rows),
                excluded_rows=0,
                duplicate_rows=parsed.duplicate_input_rows,
                conflict_rows=parsed.conflicting_input_rows,
                failed_rows=parsed.validation_error_count,
                issues=issues_from_errors(parsed.errors),
            )
        )

    manifest_sha256 = _manifest_sha256(file_results)
    summary = _summary(file_results, imported_rows=0)
    return BatchDrawImportPreview(
        source_filename="batch-import",
        manifest_sha256=manifest_sha256,
        files=tuple(file_results),
        normalized_rows=tuple(normalized_rows),
        summary=summary,
    )


def _expand_payload(
    payload: ImportFilePayload,
    file_results: list[ImportFileResult],
) -> list[_LeafPayload]:
    filename = payload.filename.strip() or "<unnamed>"
    source_sha256 = hashlib.sha256(payload.content).hexdigest()
    suffix = _suffix(filename)
    if len(payload.content) > MAX_ARCHIVE_BYTES and suffix == ".zip":
        file_results.append(_excluded_file(payload, ImportExclusionReason.FILE_SIZE_LIMIT_EXCEEDED))
        return []
    if suffix != ".zip":
        if suffix not in SUPPORTED_LEAF_EXTENSIONS:
            file_results.append(
                _excluded_file(payload, ImportExclusionReason.UNSUPPORTED_EXTENSION)
            )
            return []
        if len(payload.content) > MAX_IMPORT_FILE_BYTES:
            file_results.append(
                _excluded_file(payload, ImportExclusionReason.FILE_SIZE_LIMIT_EXCEEDED)
            )
            return []
        return [_LeafPayload(filename, filename, payload.content, source_sha256)]

    leaves: list[_LeafPayload] = []
    seen_members: set[str] = set()
    try:
        with zipfile.ZipFile(io.BytesIO(payload.content)) as archive:
            infos = sorted(
                archive.infolist(), key=lambda info: (info.filename.casefold(), info.filename)
            )
            if len(infos) > MAX_ARCHIVE_MEMBERS:
                file_results.append(
                    _excluded_file(payload, ImportExclusionReason.ARCHIVE_MEMBER_LIMIT_EXCEEDED)
                )
                return []
            for info in infos:
                if info.is_dir():
                    continue
                safe_name = _safe_member_name(info.filename)
                if safe_name is None or _is_symlink(info):
                    file_results.append(
                        ImportFileResult(
                            source_filename=info.filename,
                            source_locator=f"{filename}!{info.filename}",
                            source_sha256="",
                            status=ImportFileStatus.EXCLUDED,
                            lottery_type=None,
                            discovered_rows=0,
                            accepted_rows=0,
                            excluded_rows=0,
                            duplicate_rows=0,
                            conflict_rows=0,
                            failed_rows=0,
                            issues=(
                                ImportIssue(
                                    code=ImportExclusionReason.UNSAFE_ARCHIVE_MEMBER.value,
                                    message="Archive member path is unsafe or is a symbolic link.",
                                    member_name=info.filename,
                                ),
                            ),
                        )
                    )
                    continue
                if safe_name in seen_members:
                    file_results.append(
                        ImportFileResult(
                            source_filename=safe_name,
                            source_locator=f"{filename}!{safe_name}",
                            source_sha256="",
                            status=ImportFileStatus.EXCLUDED,
                            lottery_type=None,
                            discovered_rows=0,
                            accepted_rows=0,
                            excluded_rows=0,
                            duplicate_rows=0,
                            conflict_rows=0,
                            failed_rows=0,
                            issues=(
                                ImportIssue(
                                    code=ImportExclusionReason.DUPLICATE_ARCHIVE_MEMBER.value,
                                    message="Archive member name is duplicated.",
                                    member_name=safe_name,
                                ),
                            ),
                        )
                    )
                    continue
                seen_members.add(safe_name)
                if _suffix(safe_name) not in SUPPORTED_LEAF_EXTENSIONS:
                    file_results.append(
                        _excluded_member(
                            filename, safe_name, ImportExclusionReason.UNSUPPORTED_EXTENSION
                        )
                    )
                    continue
                if info.file_size > MAX_IMPORT_FILE_BYTES:
                    file_results.append(
                        _excluded_member(
                            filename, safe_name, ImportExclusionReason.FILE_SIZE_LIMIT_EXCEEDED
                        )
                    )
                    continue
                content = archive.read(info)
                if len(content) > MAX_IMPORT_FILE_BYTES:
                    file_results.append(
                        _excluded_member(
                            filename, safe_name, ImportExclusionReason.FILE_SIZE_LIMIT_EXCEEDED
                        )
                    )
                    continue
                member_sha256 = hashlib.sha256(content).hexdigest()
                leaves.append(
                    _LeafPayload(
                        filename=safe_name,
                        locator=f"{filename}!{safe_name} [archive_sha256={source_sha256}]",
                        content=content,
                        source_sha256=member_sha256,
                    )
                )
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        file_results.append(
            _failed_file(payload, ImportExclusionReason.CORRUPT_ARCHIVE, str(exc))
        )
    return leaves


def _parse_leaf(leaf: _LeafPayload) -> tuple[DrawCsvParseResult | None, ImportFileResult | None]:
    suffix = _suffix(leaf.filename)
    try:
        text, _encoding = decode_legacy_text(leaf.content)
    except LegacyFileFormatError as exc:
        return None, _failed_leaf(leaf, "INVALID_ENCODING", str(exc))

    if suffix == ".txt":
        if "今彩539" not in leaf.filename and "539" not in leaf.filename and "今彩539" not in text:
            return None, _excluded_leaf(leaf, ImportExclusionReason.UNSUPPORTED_LOTTERY)
        return parse_legacy_daily539_txt(
            leaf.content,
            filename=leaf.filename,
            source_locator=leaf.locator,
        ), None

    if "加開" in leaf.filename:
        return None, _excluded_leaf(leaf, ImportExclusionReason.BIG_LOTTO_BONUS_EXCLUDED)
    if _looks_canonical_csv(text):
        return _with_source_provenance(
            parse_draw_csv(leaf.content, filename=leaf.filename), leaf
        ), None
    first_game = _first_legacy_game(text)
    if first_game is None:
        return None, _failed_leaf(
            leaf, "LEGACY_FORMAT_UNRECOGNIZED", "CSV header is not recognized."
        )
    if "加開" in first_game:
        return None, _excluded_leaf(leaf, ImportExclusionReason.BIG_LOTTO_BONUS_EXCLUDED)
    if "賓果" in first_game or "BINGO" in first_game.upper():
        return None, _excluded_leaf(leaf, ImportExclusionReason.BINGO_EXCLUDED)
    lottery_type = classify_game_name(first_game)
    if lottery_type is None or is_known_other_game(first_game):
        return None, _excluded_leaf(leaf, ImportExclusionReason.UNSUPPORTED_LOTTERY)
    parsed = parse_legacy_csv(
        leaf.content,
        filename=leaf.filename,
        source_locator=leaf.locator,
        expected_lottery_type=lottery_type,
    )
    return _with_source_provenance(parsed, leaf), None


def _with_source_provenance(
    result: DrawCsvParseResult,
    leaf: _LeafPayload,
) -> DrawCsvParseResult:
    rows = tuple(
        replace(
            row,
            source=(f"{leaf.locator}|source={row.source}" if row.source else leaf.locator),
            source_name=leaf.filename,
        )
        for row in result.normalized_rows
    )
    return replace(result, normalized_rows=rows)


def _valid_rows(result: DrawCsvParseResult) -> tuple[NormalizedDrawInput, ...]:
    invalid_rows = {error.row_number for error in result.errors if error.row_number is not None}
    return tuple(row for row in result.normalized_rows if row.source_row_number not in invalid_rows)


def _first_legacy_game(text: str) -> str | None:
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        next(reader)
        for row in reader:
            if row and any(value.strip() for value in row):
                return row[0].strip()
    except (csv.Error, StopIteration):
        return None
    return None


def _looks_canonical_csv(text: str) -> bool:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    return "lottery_type" in first_line.casefold() and "draw_number" in first_line.casefold()


def _single_lottery_type(rows: tuple[NormalizedDrawInput, ...]) -> LotteryType | None:
    types = {row.lottery_type for row in rows}
    return next(iter(types)) if len(types) == 1 else None


def _summary(files: list[ImportFileResult], *, imported_rows: int) -> ImportBatchSummary:
    return ImportBatchSummary(
        discovered_files=len(files),
        accepted_files=sum(
            file.status in {ImportFileStatus.ACCEPTED, ImportFileStatus.PARTIAL}
            for file in files
        ),
        excluded_files=sum(file.status is ImportFileStatus.EXCLUDED for file in files),
        parsed_rows=sum(file.discovered_rows for file in files),
        accepted_rows=sum(file.accepted_rows for file in files),
        excluded_rows=sum(file.excluded_rows for file in files),
        duplicate_rows=sum(file.duplicate_rows for file in files),
        conflict_rows=sum(file.conflict_rows for file in files),
        imported_rows=imported_rows,
        failed_rows=sum(file.failed_rows for file in files),
    )


def _manifest_sha256(files: list[ImportFileResult]) -> str:
    payload = [
        {
            "filename": file.source_filename,
            "locator": file.source_locator,
            "sha256": file.source_sha256,
            "status": file.status.value,
        }
        for file in files
    ]
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _safe_member_name(name: str) -> str | None:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or "\x00" in normalized:
        return None
    return str(path)


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_IFMT(mode) == stat.S_IFLNK


def _suffix(filename: str) -> str:
    return f".{filename.casefold().rsplit('.', 1)[-1]}" if "." in filename else ""


def _excluded_file(payload: ImportFilePayload, reason: ImportExclusionReason) -> ImportFileResult:
    return ImportFileResult(
        source_filename=payload.filename,
        source_locator=payload.filename,
        source_sha256=hashlib.sha256(payload.content).hexdigest(),
        status=ImportFileStatus.EXCLUDED,
        lottery_type=None,
        discovered_rows=0,
        accepted_rows=0,
        excluded_rows=0,
        duplicate_rows=0,
        conflict_rows=0,
        failed_rows=0,
        issues=(ImportIssue(code=reason.value, message=reason.value),),
    )


def _excluded_member(filename: str, member: str, reason: ImportExclusionReason) -> ImportFileResult:
    return ImportFileResult(
        source_filename=member,
        source_locator=f"{filename}!{member}",
        source_sha256="",
        status=ImportFileStatus.EXCLUDED,
        lottery_type=None,
        discovered_rows=0,
        accepted_rows=0,
        excluded_rows=0,
        duplicate_rows=0,
        conflict_rows=0,
        failed_rows=0,
        issues=(ImportIssue(code=reason.value, message=reason.value, member_name=member),),
    )


def _failed_file(
    payload: ImportFilePayload,
    reason: ImportExclusionReason,
    message: str,
) -> ImportFileResult:
    return ImportFileResult(
        source_filename=payload.filename,
        source_locator=payload.filename,
        source_sha256=hashlib.sha256(payload.content).hexdigest(),
        status=ImportFileStatus.FAILED,
        lottery_type=None,
        discovered_rows=0,
        accepted_rows=0,
        excluded_rows=0,
        duplicate_rows=0,
        conflict_rows=0,
        failed_rows=1,
        issues=(ImportIssue(code=reason.value, message=message),),
    )


def _excluded_leaf(leaf: _LeafPayload, reason: ImportExclusionReason) -> ImportFileResult:
    return ImportFileResult(
        source_filename=leaf.filename,
        source_locator=leaf.locator,
        source_sha256=leaf.source_sha256,
        status=ImportFileStatus.EXCLUDED,
        lottery_type=None,
        discovered_rows=0,
        accepted_rows=0,
        excluded_rows=0,
        duplicate_rows=0,
        conflict_rows=0,
        failed_rows=0,
        issues=(ImportIssue(code=reason.value, message=reason.value),),
    )


def _failed_leaf(leaf: _LeafPayload, code: str, message: str) -> ImportFileResult:
    return ImportFileResult(
        source_filename=leaf.filename,
        source_locator=leaf.locator,
        source_sha256=leaf.source_sha256,
        status=ImportFileStatus.FAILED,
        lottery_type=None,
        discovered_rows=0,
        accepted_rows=0,
        excluded_rows=0,
        duplicate_rows=0,
        conflict_rows=0,
        failed_rows=1,
        issues=(ImportIssue(code=code, message=message),),
    )


__all__ = [
    "MAX_ARCHIVE_BYTES",
    "MAX_ARCHIVE_MEMBERS",
    "MAX_IMPORT_FILE_BYTES",
    "ImportFilePayload",
    "preview_import_batch",
]
