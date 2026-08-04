"""Read-only adapters for the LotteryNew historical CSV and TXT formats."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import replace
from datetime import date
from typing import Final

from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import DrawCsvParseResult, DrawImportError, DrawImportErrorCode
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv

LEGACY_ENCODINGS: Final[tuple[str, ...]] = ("utf-8-sig", "big5", "cp950")
LEGACY_GAME_NAMES: Final[dict[str, LotteryType]] = {
    "大樂透": LotteryType.BIG_LOTTO,
    "威力彩": LotteryType.POWER_LOTTO,
    "今彩539": LotteryType.DAILY_539,
}
LEGACY_OTHER_GAME_MARKERS: Final[tuple[str, ...]] = (
    "賓果",
    "BINGO",
    "樂合彩",
    "星彩",
    "雙贏彩",
    "6/38",
)
_DATE_RE = re.compile(
    r"(?:開獎日期\s*[:\uFF1A]\s*)?(\d{2,4})[/.\-](\d{1,2})[/.\-](\d{1,2})"
)
_DRAW_RE = re.compile(r"(?:第)?(\d{6,})(?:期)?")


class LegacyFileFormatError(ValueError):
    """A legacy document cannot be decoded or structurally interpreted."""


def decode_legacy_text(content: bytes) -> tuple[str, str]:
    """Decode one bounded legacy document using the donor's encoding order."""

    for encoding in LEGACY_ENCODINGS:
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise LegacyFileFormatError("legacy file encoding is not UTF-8, Big5, or CP950")


def classify_game_name(game_name: str) -> LotteryType | None:
    """Map official game labels to current supported draw types."""

    normalized = game_name.strip().upper()
    for label, lottery_type in LEGACY_GAME_NAMES.items():
        if label.upper() in normalized:
            return lottery_type
    return None


def is_known_other_game(game_name: str) -> bool:
    normalized = game_name.strip().upper()
    return any(marker.upper() in normalized for marker in LEGACY_OTHER_GAME_MARKERS)


def parse_legacy_csv(
    content: bytes,
    *,
    filename: str,
    source_locator: str,
    expected_lottery_type: LotteryType | None = None,
) -> DrawCsvParseResult:
    """Normalize the donor's official CSV into the current canonical parser."""

    try:
        text, _encoding = decode_legacy_text(content)
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader)
    except (LegacyFileFormatError, StopIteration, csv.Error) as exc:
        return _format_error_result(filename, DrawImportErrorCode.MALFORMED_CSV, str(exc))

    normalized_header = tuple(value.strip() for value in header)
    game_index = _find_column(normalized_header, "遊戲名稱")
    draw_index = _find_column(normalized_header, "期別")
    date_index = _find_column(normalized_header, "開獎日期")
    number_indexes = tuple(
        index for index, value in enumerate(normalized_header) if value.startswith("獎號")
    )
    special_index = next(
        (
            index
            for index, value in enumerate(normalized_header)
            if value in {"特別號", "第二區"} or value.startswith("第二區")
        ),
        None,
    )
    if game_index is None or draw_index is None or date_index is None or not number_indexes:
        return _format_error_result(
            filename,
            DrawImportErrorCode.MISSING_REQUIRED_COLUMN,
            "legacy CSV is missing 遊戲名稱、期別、開獎日期, or 獎號 columns",
        )

    canonical = io.StringIO(newline="")
    writer = csv.writer(canonical, lineterminator="\n")
    writer.writerow(
        ("lottery_type", "draw_number", "draw_date", "main_numbers", "special_numbers", "source")
    )
    for row in reader:
        values = [value.strip() for value in row]
        if all(not value for value in values):
            writer.writerow(("", "", "", "", "", source_locator))
            continue
        game_name = _cell(values, game_index)
        lottery_type = classify_game_name(game_name)
        draw_number = _cell(values, draw_index)
        draw_date = _normalize_legacy_date(_cell(values, date_index))
        raw_numbers = tuple(_cell(values, index) for index in number_indexes)
        if lottery_type is None or (
            expected_lottery_type is not None and lottery_type is not expected_lottery_type
        ):
            lottery_value = "UNKNOWN"
        else:
            lottery_value = lottery_type.value
        main_count = 5 if lottery_type is LotteryType.DAILY_539 else 6
        main_numbers = raw_numbers[:main_count]
        special_numbers = (
            (_cell(values, special_index),)
            if special_index is not None and _cell(values, special_index)
            else raw_numbers[main_count : main_count + 1]
        )
        writer.writerow(
            (
                lottery_value,
                draw_number,
                draw_date,
                "|".join(value for value in main_numbers if value),
                "|".join(value for value in special_numbers if value),
                source_locator,
            )
        )

    result = parse_draw_csv(canonical.getvalue(), filename=filename)
    return result


def parse_legacy_daily539_txt(
    content: bytes,
    *,
    filename: str,
    source_locator: str,
) -> DrawCsvParseResult:
    """Normalize the donor's official multi-line Daily 539 TXT format."""

    try:
        text, _encoding = decode_legacy_text(content)
    except LegacyFileFormatError as exc:
        return _format_error_result(filename, DrawImportErrorCode.INVALID_UTF8, str(exc))

    canonical = io.StringIO(newline="")
    writer = csv.writer(canonical, lineterminator="\n")
    writer.writerow(
        ("lottery_type", "draw_number", "draw_date", "main_numbers", "special_numbers", "source")
    )
    lines = [line.strip() for line in text.splitlines()]
    for index, line in enumerate(lines):
        if "期" not in line:
            continue
        draw_match = _DRAW_RE.search(line)
        if draw_match is None:
            continue
        draw_number = draw_match.group(1)
        date_value = _find_date(lines, index, limit=4)
        numbers_value = _find_compact_numbers(lines, index, limit=6)
        if date_value is None or numbers_value is None:
            continue
        writer.writerow((
            LotteryType.DAILY_539.value,
            draw_number,
            date_value,
            "|".join(numbers_value),
            "",
            source_locator,
        ))
    return parse_draw_csv(canonical.getvalue(), filename=filename)


def _find_column(header: tuple[str, ...], name: str) -> int | None:
    try:
        return header.index(name)
    except ValueError:
        return None


def _cell(row: list[str], index: int) -> str:
    return row[index].strip() if 0 <= index < len(row) else ""


def _normalize_legacy_date(value: str) -> str:
    match = _DATE_RE.fullmatch(value.strip())
    if match is None:
        return value.strip()
    year, month, day = (int(part) for part in match.groups())
    if year < 1000:
        year += 1911
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return value.strip()


def _find_date(lines: list[str], start: int, *, limit: int) -> str | None:
    for line in lines[start : start + limit]:
        match = _DATE_RE.search(line)
        if match is not None:
            return _normalize_legacy_date(match.group(0))
    return None


def _find_compact_numbers(lines: list[str], start: int, *, limit: int) -> tuple[str, ...] | None:
    draw_match = _DRAW_RE.search(lines[start])
    for line in lines[start : start + limit]:
        candidate = line
        if draw_match is not None:
            candidate = candidate.replace(draw_match.group(1), "", 1)
        candidate = _DATE_RE.sub("", candidate)
        digits = re.findall(r"\d+", candidate)
        if len(digits) == 1 and len(digits[0]) == 10:
            return tuple(digits[0][offset : offset + 2] for offset in range(0, 10, 2))
        if len(digits) >= 5:
            return tuple(digits[:5])
    return None


def _format_error_result(
    filename: str,
    code: DrawImportErrorCode,
    message: str,
) -> DrawCsvParseResult:
    result = parse_draw_csv(b"", filename=filename)
    return replace(
        result,
        errors=(DrawImportError(code=code, message=message),),
    )


__all__ = [
    "LEGACY_ENCODINGS",
    "LEGACY_GAME_NAMES",
    "LEGACY_OTHER_GAME_MARKERS",
    "LegacyFileFormatError",
    "classify_game_name",
    "decode_legacy_text",
    "is_known_other_game",
    "parse_legacy_csv",
    "parse_legacy_daily539_txt",
]
