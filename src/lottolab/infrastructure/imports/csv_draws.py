"""Parse LottoLab's canonical draw CSV without opening a database.

The CSV itself is comma-separated.  Values inside ``main_numbers`` and
``special_numbers`` use ``|``.  Required headers are ``lottery_type``,
``draw_number``, ``draw_date``, and ``main_numbers``; ``special_numbers`` and
``source`` are optional.  Headers are trimmed and case-insensitive.  Unknown
columns are deliberately ignored and reported in ``ignored_columns``.

Lottery-specific count, range, uniqueness, overlap, and ordering validation is
resolved from the immutable domain rule registry.  Missing or incomplete
contracts remain fail-closed.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections.abc import Mapping
from datetime import date
from types import MappingProxyType

from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import (
    DrawCsvParseResult,
    DrawImportError,
    DrawImportErrorCode,
    LotteryRuleStatus,
    NormalizedDrawInput,
)
from lottolab.domain.lottery_rules import (
    LOTTERY_RULE_CONTRACTS,
    CanonicalNumberOrder,
    LotteryRuleContract,
    resolve_lottery_rule_contract,
)

PARSER_VERSION = "lottolab-draw-csv-v2"
MAX_CSV_BYTES = 1024 * 1024
MAX_CSV_ROWS = 10_000
MAX_DRAW_NUMBER_LENGTH = 32
NUMBER_DELIMITER = "|"

REQUIRED_COLUMNS = ("lottery_type", "draw_number", "draw_date", "main_numbers")
OPTIONAL_COLUMNS = ("special_numbers", "source")
KNOWN_COLUMNS = frozenset((*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS))
UNKNOWN_COLUMNS_POLICY = "ignored-and-reported"

RULE_STATUS_BY_LOTTERY_TYPE: Mapping[LotteryType, LotteryRuleStatus] = MappingProxyType(
    {
        lottery_type: LotteryRuleStatus.PROVEN
        for lottery_type, contract in LOTTERY_RULE_CONTRACTS.items()
        if resolve_lottery_rule_contract(lottery_type, LOTTERY_RULE_CONTRACTS) is contract
    }
)
SUPPORTED_LOTTERY_TYPES: tuple[LotteryType, ...] = tuple(
    lottery_type
    for lottery_type, status in RULE_STATUS_BY_LOTTERY_TYPE.items()
    if status is LotteryRuleStatus.PROVEN
)

_ASCII_DECIMAL = re.compile(r"[0-9]+", flags=re.ASCII)
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", flags=re.ASCII)


def _result(
    *,
    filename: str,
    content_sha256: str,
    total_rows: int = 0,
    blank_rows: int = 0,
    duplicate_input_rows: int = 0,
    conflicting_input_rows: int = 0,
    ignored_columns: tuple[str, ...] = (),
    normalized_rows: tuple[NormalizedDrawInput, ...] = (),
    errors: tuple[DrawImportError, ...] = (),
) -> DrawCsvParseResult:
    return DrawCsvParseResult(
        source_filename=filename,
        content_sha256=content_sha256,
        parser_version=PARSER_VERSION,
        total_rows=total_rows,
        blank_rows=blank_rows,
        duplicate_input_rows=duplicate_input_rows,
        conflicting_input_rows=conflicting_input_rows,
        ignored_columns=ignored_columns,
        normalized_rows=normalized_rows,
        errors=errors,
    )


def _decode_content(content: str | bytes) -> tuple[bytes | None, str | None]:
    if isinstance(content, bytes):
        raw = content
        try:
            return raw, raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return raw, None
    try:
        raw = content.encode("utf-8")
    except UnicodeEncodeError:
        return None, None
    return raw, content.removeprefix("\ufeff")


def _normalize_header(header: list[str]) -> tuple[str, ...]:
    return tuple(value.strip().casefold() for value in header)


def _ordered_duplicates(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


def _normalize_draw_number(raw: str, row_number: int) -> tuple[str | None, DrawImportError | None]:
    if _ASCII_DECIMAL.fullmatch(raw) is None:
        return None, DrawImportError(
            code=DrawImportErrorCode.INVALID_DRAW_NUMBER,
            message="draw_number must contain ASCII decimal digits only.",
            row_number=row_number,
            field="draw_number",
        )
    if len(raw) > MAX_DRAW_NUMBER_LENGTH:
        return None, DrawImportError(
            code=DrawImportErrorCode.INVALID_DRAW_NUMBER,
            message=f"draw_number must not exceed {MAX_DRAW_NUMBER_LENGTH} characters.",
            row_number=row_number,
            field="draw_number",
        )
    return raw, None


def _normalize_draw_date(raw: str, row_number: int) -> tuple[date | None, DrawImportError | None]:
    if _ISO_DATE.fullmatch(raw) is None:
        return None, DrawImportError(
            code=DrawImportErrorCode.INVALID_DRAW_DATE,
            message="draw_date must use ISO YYYY-MM-DD.",
            row_number=row_number,
            field="draw_date",
        )
    try:
        normalized = date.fromisoformat(raw)
    except ValueError:
        return None, DrawImportError(
            code=DrawImportErrorCode.INVALID_DRAW_DATE,
            message="draw_date is not a valid calendar date.",
            row_number=row_number,
            field="draw_date",
        )
    return normalized, None


def _normalize_numbers(
    raw: str, *, field: str, row_number: int
) -> tuple[tuple[int, ...] | None, tuple[DrawImportError, ...]]:
    normalized: list[int] = []
    errors: list[DrawImportError] = []
    for position, token in enumerate(raw.split(NUMBER_DELIMITER), start=1):
        value = token.strip()
        if _ASCII_DECIMAL.fullmatch(value) is None:
            errors.append(
                DrawImportError(
                    code=DrawImportErrorCode.INVALID_NUMBER,
                    message=f"{field} item {position} must contain ASCII decimal digits only.",
                    row_number=row_number,
                    field=field,
                )
            )
            continue
        try:
            normalized.append(int(value))
        except ValueError:
            errors.append(
                DrawImportError(
                    code=DrawImportErrorCode.INVALID_NUMBER,
                    message=f"{field} item {position} is too large to normalize.",
                    row_number=row_number,
                    field=field,
                )
            )

    if errors:
        return None, tuple(errors)
    return tuple(normalized), ()


def _validate_and_canonicalize_numbers(
    main_numbers: tuple[int, ...],
    special_numbers: tuple[int, ...],
    *,
    contract: LotteryRuleContract,
    row_number: int,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[DrawImportError, ...]]:
    errors: list[DrawImportError] = []

    if len(main_numbers) != contract.main_number_count:
        errors.append(
            DrawImportError(
                code=DrawImportErrorCode.NUMBER_COUNT_MISMATCH,
                message=(
                    f"main_numbers must contain exactly {contract.main_number_count} values."
                ),
                row_number=row_number,
                field="main_numbers",
            )
        )
    if any(
        value < contract.main_number_min or value > contract.main_number_max
        for value in main_numbers
    ):
        errors.append(
            DrawImportError(
                code=DrawImportErrorCode.NUMBER_OUT_OF_RANGE,
                message=(
                    "main_numbers values must be between "
                    f"{contract.main_number_min} and {contract.main_number_max}."
                ),
                row_number=row_number,
                field="main_numbers",
            )
        )
    if contract.main_numbers_unique and len(set(main_numbers)) != len(main_numbers):
        errors.append(
            DrawImportError(
                code=DrawImportErrorCode.DUPLICATE_NUMBER,
                message="main_numbers must be unique after numeric normalization.",
                row_number=row_number,
                field="main_numbers",
            )
        )

    allowed_special_counts = {contract.special_number_count}
    if not contract.special_number_required:
        allowed_special_counts.add(0)
    if len(special_numbers) not in allowed_special_counts:
        if contract.special_number_required:
            message = (
                "special_numbers is required and must contain exactly "
                f"{contract.special_number_count} values."
            )
        else:
            message = (
                "special_numbers must be empty or contain exactly "
                f"{contract.special_number_count} values."
            )
        errors.append(
            DrawImportError(
                code=DrawImportErrorCode.NUMBER_COUNT_MISMATCH,
                message=message,
                row_number=row_number,
                field="special_numbers",
            )
        )
    if any(
        value < contract.special_number_min or value > contract.special_number_max
        for value in special_numbers
    ):
        errors.append(
            DrawImportError(
                code=DrawImportErrorCode.NUMBER_OUT_OF_RANGE,
                message=(
                    "special_numbers values must be between "
                    f"{contract.special_number_min} and {contract.special_number_max}."
                ),
                row_number=row_number,
                field="special_numbers",
            )
        )
    if contract.special_numbers_unique and len(set(special_numbers)) != len(special_numbers):
        errors.append(
            DrawImportError(
                code=DrawImportErrorCode.DUPLICATE_NUMBER,
                message="special_numbers must be unique after numeric normalization.",
                row_number=row_number,
                field="special_numbers",
            )
        )
    if (
        not contract.main_special_overlap_allowed
        and set(main_numbers).intersection(special_numbers)
    ):
        errors.append(
            DrawImportError(
                code=DrawImportErrorCode.MAIN_SPECIAL_OVERLAP,
                message="main_numbers and special_numbers must not overlap.",
                row_number=row_number,
                field="special_numbers",
            )
        )

    if contract.canonical_number_order is CanonicalNumberOrder.ASCENDING_NUMERIC:
        return tuple(sorted(main_numbers)), tuple(sorted(special_numbers)), tuple(errors)
    raise AssertionError("resolved contracts must use a supported canonical number order")


def _record_hash(
    *,
    lottery_type: LotteryType,
    draw_number: str,
    draw_date_value: date,
    main_numbers: tuple[int, ...],
    special_numbers: tuple[int, ...],
) -> str:
    canonical = json.dumps(
        {
            "draw_date": draw_date_value.isoformat(),
            "draw_number": draw_number,
            "lottery_type": str(lottery_type),
            "main_numbers": main_numbers,
            "special_numbers": special_numbers,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def parse_draw_csv(
    content: str | bytes,
    *,
    filename: str = "",
    rule_contracts: Mapping[LotteryType, LotteryRuleContract] | None = None,
) -> DrawCsvParseResult:
    """Return a bounded, deterministic parse result without filesystem or DB I/O."""

    raw, decoded = _decode_content(content)
    if raw is None:
        return _result(
            filename=filename,
            content_sha256="",
            errors=(
                DrawImportError(
                    code=DrawImportErrorCode.INVALID_UTF8,
                    message="CSV content is not valid UTF-8.",
                ),
            ),
        )

    content_sha256 = hashlib.sha256(raw).hexdigest()
    if len(raw) > MAX_CSV_BYTES:
        return _result(
            filename=filename,
            content_sha256=content_sha256,
            errors=(
                DrawImportError(
                    code=DrawImportErrorCode.FILE_TOO_LARGE,
                    message=f"CSV content exceeds the {MAX_CSV_BYTES}-byte limit.",
                ),
            ),
        )
    if decoded is None:
        return _result(
            filename=filename,
            content_sha256=content_sha256,
            errors=(
                DrawImportError(
                    code=DrawImportErrorCode.INVALID_UTF8,
                    message="CSV content is not valid UTF-8.",
                ),
            ),
        )

    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True, skipinitialspace=True)
    try:
        header = next(reader)
    except StopIteration:
        return _result(
            filename=filename,
            content_sha256=content_sha256,
            errors=(
                DrawImportError(
                    code=DrawImportErrorCode.EMPTY_FILE,
                    message="CSV content must include a header row.",
                ),
            ),
        )
    except csv.Error:
        return _result(
            filename=filename,
            content_sha256=content_sha256,
            errors=(
                DrawImportError(
                    code=DrawImportErrorCode.MALFORMED_CSV,
                    message="CSV header is malformed.",
                    row_number=1,
                ),
            ),
        )

    normalized_header = _normalize_header(header)
    if not normalized_header or all(not value for value in normalized_header):
        return _result(
            filename=filename,
            content_sha256=content_sha256,
            errors=(
                DrawImportError(
                    code=DrawImportErrorCode.EMPTY_FILE,
                    message="CSV content must include a non-blank header row.",
                    row_number=1,
                ),
            ),
        )

    ignored_columns = tuple(
        dict.fromkeys(value for value in normalized_header if value not in KNOWN_COLUMNS)
    )
    header_errors: list[DrawImportError] = []
    for duplicate in _ordered_duplicates(normalized_header):
        header_errors.append(
            DrawImportError(
                code=DrawImportErrorCode.DUPLICATE_HEADER,
                message=f"Header {duplicate!r} appears more than once after normalization.",
                row_number=1,
                field=duplicate or None,
            )
        )
    for required in REQUIRED_COLUMNS:
        if required not in normalized_header:
            header_errors.append(
                DrawImportError(
                    code=DrawImportErrorCode.MISSING_REQUIRED_COLUMN,
                    message=f"Required column {required!r} is missing.",
                    row_number=1,
                    field=required,
                )
            )
    if header_errors:
        return _result(
            filename=filename,
            content_sha256=content_sha256,
            ignored_columns=ignored_columns,
            errors=tuple(header_errors),
        )

    indexed_rows: list[tuple[int, list[str]]] = []
    while len(indexed_rows) <= MAX_CSV_ROWS:
        row_number = reader.line_num + 1
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error:
            return _result(
                filename=filename,
                content_sha256=content_sha256,
                total_rows=len(indexed_rows),
                blank_rows=sum(
                    all(not value.strip() for value in item) for _, item in indexed_rows
                ),
                ignored_columns=ignored_columns,
                errors=(
                    DrawImportError(
                        code=DrawImportErrorCode.MALFORMED_CSV,
                        message="CSV row structure is malformed.",
                        row_number=row_number,
                    ),
                ),
            )
        indexed_rows.append((row_number, row))

    if len(indexed_rows) > MAX_CSV_ROWS:
        return _result(
            filename=filename,
            content_sha256=content_sha256,
            total_rows=len(indexed_rows),
            blank_rows=sum(all(not value.strip() for value in row) for _, row in indexed_rows),
            ignored_columns=ignored_columns,
            errors=(
                DrawImportError(
                    code=DrawImportErrorCode.ROW_LIMIT_EXCEEDED,
                    message=f"CSV content exceeds the {MAX_CSV_ROWS}-row limit.",
                    row_number=indexed_rows[-1][0],
                ),
            ),
        )

    column_indexes = {
        name: normalized_header.index(name) for name in KNOWN_COLUMNS if name in normalized_header
    }
    normalized_rows: list[NormalizedDrawInput] = []
    errors: list[DrawImportError] = []
    blank_rows = 0
    duplicate_input_rows = 0
    conflicting_input_rows = 0
    seen_keys: dict[tuple[LotteryType, str], tuple[int, str]] = {}
    active_rule_contracts = (
        LOTTERY_RULE_CONTRACTS if rule_contracts is None else rule_contracts
    )

    for row_number, row in indexed_rows:
        if all(not value.strip() for value in row):
            blank_rows += 1
            continue
        if len(row) > len(normalized_header):
            errors.append(
                DrawImportError(
                    code=DrawImportErrorCode.COLUMN_COUNT_MISMATCH,
                    message="CSV row has more values than the header defines.",
                    row_number=row_number,
                )
            )
            continue

        padded = [*row, *("" for _ in range(len(normalized_header) - len(row)))]
        values = {name: padded[index].strip() for name, index in column_indexes.items()}
        row_errors: list[DrawImportError] = []
        missing_values = {name for name in REQUIRED_COLUMNS if not values[name]}
        for missing in REQUIRED_COLUMNS:
            if missing in missing_values:
                row_errors.append(
                    DrawImportError(
                        code=DrawImportErrorCode.MISSING_REQUIRED_VALUE,
                        message=f"Required value {missing!r} is blank.",
                        row_number=row_number,
                        field=missing,
                    )
                )

        lottery_type: LotteryType | None = None
        rule_status: LotteryRuleStatus | None = None
        rule_contract: LotteryRuleContract | None = None
        if "lottery_type" not in missing_values:
            normalized_lottery_type = values["lottery_type"].upper()
            try:
                parsed_lottery_type = LotteryType(normalized_lottery_type)
            except ValueError:
                parsed_lottery_type = None
            if (
                parsed_lottery_type is None
                or parsed_lottery_type not in RULE_STATUS_BY_LOTTERY_TYPE
            ):
                row_errors.append(
                    DrawImportError(
                        code=DrawImportErrorCode.UNSUPPORTED_LOTTERY_TYPE,
                        message=f"Lottery type {normalized_lottery_type!r} is not supported.",
                        row_number=row_number,
                        field="lottery_type",
                    )
                )
            else:
                lottery_type = parsed_lottery_type
                rule_contract = resolve_lottery_rule_contract(
                    parsed_lottery_type, active_rule_contracts
                )
                rule_status = (
                    LotteryRuleStatus.PROVEN
                    if rule_contract is not None
                    else LotteryRuleStatus.UNKNOWN
                )

        draw_number: str | None = None
        if "draw_number" not in missing_values:
            draw_number, draw_number_error = _normalize_draw_number(
                values["draw_number"], row_number
            )
            if draw_number_error is not None:
                row_errors.append(draw_number_error)

        draw_date_value: date | None = None
        if "draw_date" not in missing_values:
            draw_date_value, draw_date_error = _normalize_draw_date(values["draw_date"], row_number)
            if draw_date_error is not None:
                row_errors.append(draw_date_error)

        main_numbers: tuple[int, ...] | None = None
        if "main_numbers" not in missing_values:
            main_numbers, number_errors = _normalize_numbers(
                values["main_numbers"], field="main_numbers", row_number=row_number
            )
            row_errors.extend(number_errors)

        special_numbers: tuple[int, ...] | None = ()
        if values.get("special_numbers", ""):
            special_numbers, number_errors = _normalize_numbers(
                values["special_numbers"], field="special_numbers", row_number=row_number
            )
            row_errors.extend(number_errors)

        if (
            not row_errors
            and rule_contract is not None
            and main_numbers is not None
            and special_numbers is not None
        ):
            main_numbers, special_numbers, rule_errors = _validate_and_canonicalize_numbers(
                main_numbers,
                special_numbers,
                contract=rule_contract,
                row_number=row_number,
            )
            row_errors.extend(rule_errors)

        if rule_status is LotteryRuleStatus.UNKNOWN:
            row_errors.append(
                DrawImportError(
                    code=DrawImportErrorCode.RULE_CONTRACT_UNKNOWN,
                    message="No complete, active, primary rule contract is available.",
                    row_number=row_number,
                    field="lottery_type",
                )
            )

        candidate: NormalizedDrawInput | None = None
        if (
            not row_errors
            and lottery_type is not None
            and rule_status is LotteryRuleStatus.PROVEN
            and draw_number is not None
            and draw_date_value is not None
            and main_numbers is not None
            and special_numbers is not None
        ):
            source_value = values.get("source", "")
            source = unicodedata.normalize("NFC", source_value) or None
            normalized_record_hash = _record_hash(
                lottery_type=lottery_type,
                draw_number=draw_number,
                draw_date_value=draw_date_value,
                main_numbers=main_numbers,
                special_numbers=special_numbers,
            )
            candidate = NormalizedDrawInput(
                source_row_number=row_number,
                lottery_type=lottery_type,
                draw_number=draw_number,
                draw_date=draw_date_value,
                main_numbers=main_numbers,
                special_numbers=special_numbers,
                source=source,
                normalized_record_hash=normalized_record_hash,
                rule_status=rule_status,
            )
            normalized_rows.append(candidate)

            key = (lottery_type, draw_number)
            previous = seen_keys.get(key)
            if previous is None:
                seen_keys[key] = (row_number, normalized_record_hash)
            elif previous[1] == normalized_record_hash:
                duplicate_input_rows += 1
                row_errors.append(
                    DrawImportError(
                        code=DrawImportErrorCode.DUPLICATE_INPUT_ROW,
                        message=f"Row duplicates normalized row {previous[0]}.",
                        row_number=row_number,
                    )
                )
            else:
                conflicting_input_rows += 1
                row_errors.append(
                    DrawImportError(
                        code=DrawImportErrorCode.CONFLICTING_INPUT_ROW,
                        message=f"Row conflicts with draw identity from row {previous[0]}.",
                        row_number=row_number,
                    )
                )

        errors.extend(row_errors)

    return _result(
        filename=filename,
        content_sha256=content_sha256,
        total_rows=len(indexed_rows),
        blank_rows=blank_rows,
        duplicate_input_rows=duplicate_input_rows,
        conflicting_input_rows=conflicting_input_rows,
        ignored_columns=ignored_columns,
        normalized_rows=tuple(normalized_rows),
        errors=tuple(errors),
    )
