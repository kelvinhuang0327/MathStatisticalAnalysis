"""Strict, deterministic parser for the closed synthetic CSV v1 format."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from itertools import pairwise

from lottolab.domain.lottery_rules import LotteryRuleContract
from lottolab.normalization.models import NormalizationFinding

MAX_SOURCE_BYTES = 1_048_576
MAX_DATA_RECORDS = 10_000
MAX_RECORD_BYTES = 512
MAX_FIELD_BYTES = 128
MAX_INTEGER_DIGITS = 10
EXPECTED_HEADER = "draw_id,draw_sequence,draw_date,main_numbers,special_numbers"

_DRAW_ID = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$", flags=re.ASCII)
_INTEGER = re.compile(r"^(0|[1-9][0-9]*)$", flags=re.ASCII)
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", flags=re.ASCII)


@dataclass(frozen=True, slots=True)
class ParsedRecord:
    draw_id: str
    draw_sequence: int
    draw_date: date
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ParseResult:
    source_record_count: int
    records: tuple[ParsedRecord, ...]
    findings: tuple[NormalizationFinding, ...]


def _finding(code: str, ordinal: int, field: str, message: str) -> NormalizationFinding:
    return NormalizationFinding(
        reason_code=code,
        source_record_ordinal=ordinal,
        field=field,
        message=message,
    )


def _ordered(findings: list[NormalizationFinding]) -> tuple[NormalizationFinding, ...]:
    return tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.source_record_ordinal,
                finding.reason_code,
                finding.field,
            ),
        )
    )


def _parse_integer(
    token: str,
    *,
    ordinal: int,
    field: str,
    lexical_code: str,
) -> tuple[int | None, list[NormalizationFinding]]:
    if len(token) > MAX_INTEGER_DIGITS:
        return None, [
            _finding(
                "NRM_REC_NUMERIC_TOKEN_TOO_LONG",
                ordinal,
                field,
                "numeric token exceeds the closed digit limit",
            )
        ]
    if _INTEGER.fullmatch(token) is None:
        return None, [
            _finding(lexical_code, ordinal, field, "integer token violates closed lexical form")
        ]
    return int(token), []


def _parse_number_list(
    value: str,
    *,
    ordinal: int,
    field: str,
) -> tuple[tuple[int, ...] | None, list[NormalizationFinding]]:
    findings: list[NormalizationFinding] = []
    parsed: list[int] = []
    for token in value.split("|"):
        number, token_findings = _parse_integer(
            token,
            ordinal=ordinal,
            field=field,
            lexical_code="NRM_REC_INTEGER_LEXICAL_INVALID",
        )
        findings.extend(token_findings)
        if number is not None:
            parsed.append(number)
    if findings:
        return None, findings
    return tuple(parsed), []


def _check_number_rules(
    main_numbers: tuple[int, ...],
    special_numbers: tuple[int, ...],
    *,
    ordinal: int,
    rule: LotteryRuleContract,
) -> list[NormalizationFinding]:
    findings: list[NormalizationFinding] = []
    if len(main_numbers) != rule.main_number_count:
        findings.append(
            _finding(
                "NRM_RULE_MAIN_COUNT_MISMATCH",
                ordinal,
                "main_numbers",
                "main number count does not match the bound rule contract",
            )
        )
    if len(special_numbers) != rule.special_number_count:
        findings.append(
            _finding(
                "NRM_RULE_SPECIAL_COUNT_MISMATCH",
                ordinal,
                "special_numbers",
                "special number count does not match the bound rule contract",
            )
        )
    if any(
        number < rule.main_number_min or number > rule.main_number_max
        for number in main_numbers
    ):
        findings.append(
            _finding(
                "NRM_RULE_NUMBER_OUT_OF_RANGE",
                ordinal,
                "main_numbers",
                "main number is outside the bound rule range",
            )
        )
    if any(
        number < rule.special_number_min or number > rule.special_number_max
        for number in special_numbers
    ):
        findings.append(
            _finding(
                "NRM_RULE_NUMBER_OUT_OF_RANGE",
                ordinal,
                "special_numbers",
                "special number is outside the bound rule range",
            )
        )
    if any(right < left for left, right in pairwise(main_numbers)):
        findings.append(
            _finding(
                "NRM_RULE_NUMBER_ORDER_INVALID",
                ordinal,
                "main_numbers",
                "main numbers must already be in ascending numeric order",
            )
        )
    if any(right < left for left, right in pairwise(special_numbers)):
        findings.append(
            _finding(
                "NRM_RULE_NUMBER_ORDER_INVALID",
                ordinal,
                "special_numbers",
                "special numbers must already be in ascending numeric order",
            )
        )
    if rule.main_numbers_unique and len(set(main_numbers)) != len(main_numbers):
        findings.append(
            _finding(
                "NRM_RULE_DUPLICATE_NUMBER",
                ordinal,
                "main_numbers",
                "main numbers contain a duplicate",
            )
        )
    if rule.special_numbers_unique and len(set(special_numbers)) != len(special_numbers):
        findings.append(
            _finding(
                "NRM_RULE_DUPLICATE_NUMBER",
                ordinal,
                "special_numbers",
                "special numbers contain a duplicate",
            )
        )
    if not rule.main_special_overlap_allowed and set(main_numbers) & set(special_numbers):
        findings.append(
            _finding(
                "NRM_RULE_MAIN_SPECIAL_OVERLAP",
                ordinal,
                "special_numbers",
                "main and special numbers overlap under the bound rule contract",
            )
        )
    return findings


def parse_synthetic_draw_csv(
    source_bytes: bytes,
    *,
    rule: LotteryRuleContract,
) -> ParseResult:
    """Parse exact synthetic CSV bytes without tolerance or partial output."""

    findings: list[NormalizationFinding] = []
    if len(source_bytes) > MAX_SOURCE_BYTES:
        return ParseResult(
            0,
            (),
            (
                _finding(
                    "NRM_SRC_TOO_LARGE",
                    0,
                    "source_bytes",
                    "source exceeds the closed byte limit",
                ),
            ),
        )
    if any(byte != 0x0A and not 0x20 <= byte <= 0x7E for byte in source_bytes):
        return ParseResult(
            0,
            (),
            (
                _finding(
                    "NRM_SRC_INVALID_BYTE_DOMAIN",
                    0,
                    "source_bytes",
                    "source contains a byte outside ASCII graphic or LF",
                ),
            ),
        )
    if not source_bytes.endswith(b"\n"):
        return ParseResult(
            0,
            (),
            (
                _finding(
                    "NRM_SRC_FINAL_LF_REQUIRED",
                    0,
                    "source_bytes",
                    "source must end with exactly one LF",
                ),
            ),
        )
    if source_bytes.endswith(b"\n\n"):
        return ParseResult(
            0,
            (),
            (
                _finding(
                    "NRM_SRC_EXTRA_FINAL_LF",
                    0,
                    "source_bytes",
                    "source contains an extra final LF",
                ),
            ),
        )

    text = source_bytes.decode("ascii")
    physical_lines = text[:-1].split("\n")
    if not physical_lines or physical_lines[0] != EXPECTED_HEADER:
        return ParseResult(
            max(0, len(physical_lines) - 1),
            (),
            (
                _finding(
                    "NRM_SRC_HEADER_MISMATCH",
                    0,
                    "header",
                    "header does not match the exact source format contract",
                ),
            ),
        )

    data_lines = physical_lines[1:]
    source_record_count = len(data_lines)
    if source_record_count == 0:
        return ParseResult(
            0,
            (),
            (
                _finding(
                    "NRM_SRC_BLANK_RECORD",
                    0,
                    "records",
                    "source must contain at least one data record",
                ),
            ),
        )
    if source_record_count > MAX_DATA_RECORDS:
        return ParseResult(
            source_record_count,
            (),
            (
                _finding(
                    "NRM_SRC_RECORD_LIMIT_EXCEEDED",
                    0,
                    "records",
                    "source exceeds the closed record limit",
                ),
            ),
        )

    records: list[ParsedRecord] = []
    seen_ids: dict[str, ParsedRecord] = {}
    seen_sequences: dict[int, ParsedRecord] = {}
    previous_sequence: int | None = None
    previous_date: date | None = None

    for ordinal, line in enumerate(data_lines, start=1):
        record_findings: list[NormalizationFinding] = []
        if line == "":
            findings.append(
                _finding(
                    "NRM_SRC_BLANK_RECORD",
                    ordinal,
                    "record",
                    "blank records are forbidden",
                )
            )
            continue
        if len(line) > MAX_RECORD_BYTES:
            findings.append(
                _finding(
                    "NRM_SRC_RECORD_TOO_LARGE",
                    ordinal,
                    "record",
                    "record exceeds the closed byte limit",
                )
            )
            continue
        if '"' in line:
            findings.append(
                _finding(
                    "NRM_SRC_QUOTING_FORBIDDEN",
                    ordinal,
                    "record",
                    "quoting and escaping are forbidden",
                )
            )
            continue
        fields = line.split(",")
        if len(fields) != 5:
            findings.append(
                _finding(
                    "NRM_SRC_FIELD_COUNT_MISMATCH",
                    ordinal,
                    "record",
                    "record must contain exactly five fields",
                )
            )
            continue
        names = (
            "draw_id",
            "draw_sequence",
            "draw_date",
            "main_numbers",
            "special_numbers",
        )
        oversized = [name for name, value in zip(names, fields, strict=True) if len(value) > 128]
        if oversized:
            findings.extend(
                _finding(
                    "NRM_SRC_FIELD_TOO_LARGE",
                    ordinal,
                    name,
                    "field exceeds the closed byte limit",
                )
                for name in oversized
            )
            continue

        draw_id, sequence_text, date_text, main_text, special_text = fields
        if _DRAW_ID.fullmatch(draw_id) is None:
            record_findings.append(
                _finding(
                    "NRM_REC_DRAW_ID_INVALID",
                    ordinal,
                    "draw_id",
                    "draw_id violates the closed lexical form",
                )
            )
        sequence, sequence_findings = _parse_integer(
            sequence_text,
            ordinal=ordinal,
            field="draw_sequence",
            lexical_code="NRM_REC_SEQUENCE_LEXICAL_INVALID",
        )
        record_findings.extend(sequence_findings)

        parsed_date: date | None = None
        if _DATE.fullmatch(date_text) is None:
            record_findings.append(
                _finding(
                    "NRM_REC_DATE_LEXICAL_INVALID",
                    ordinal,
                    "draw_date",
                    "draw_date violates exact YYYY-MM-DD lexical form",
                )
            )
        else:
            try:
                parsed_date = date.fromisoformat(date_text)
            except ValueError:
                record_findings.append(
                    _finding(
                        "NRM_REC_DATE_INVALID",
                        ordinal,
                        "draw_date",
                        "draw_date is not a real calendar date",
                    )
                )

        main_numbers, main_findings = _parse_number_list(
            main_text,
            ordinal=ordinal,
            field="main_numbers",
        )
        special_numbers, special_findings = _parse_number_list(
            special_text,
            ordinal=ordinal,
            field="special_numbers",
        )
        record_findings.extend(main_findings)
        record_findings.extend(special_findings)

        if sequence is not None:
            expected_sequence = ordinal - 1
            if sequence != expected_sequence:
                record_findings.append(
                    _finding(
                        "NRM_SEQ_ORDINAL_MISMATCH",
                        ordinal,
                        "draw_sequence",
                        "draw_sequence must equal source ordinal minus one",
                    )
                )
            if previous_sequence is not None and sequence != previous_sequence + 1:
                record_findings.append(
                    _finding(
                        "NRM_SEQ_GAP",
                        ordinal,
                        "draw_sequence",
                        "draw_sequence is not contiguous with the prior record",
                    )
                )
            previous_sequence = sequence

        if parsed_date is not None:
            if previous_date is not None and parsed_date < previous_date:
                record_findings.append(
                    _finding(
                        "NRM_SEQ_DATE_REGRESSION",
                        ordinal,
                        "draw_date",
                        "draw_date regresses relative to the prior record",
                    )
                )
            previous_date = parsed_date

        candidate: ParsedRecord | None = None
        if (
            _DRAW_ID.fullmatch(draw_id) is not None
            and sequence is not None
            and parsed_date is not None
            and main_numbers is not None
            and special_numbers is not None
        ):
            candidate = ParsedRecord(
                draw_id=draw_id,
                draw_sequence=sequence,
                draw_date=parsed_date,
                main_numbers=main_numbers,
                special_numbers=special_numbers,
            )
            record_findings.extend(
                _check_number_rules(
                    main_numbers,
                    special_numbers,
                    ordinal=ordinal,
                    rule=rule,
                )
            )
            prior_id = seen_ids.get(draw_id)
            prior_sequence = seen_sequences.get(sequence)
            if prior_id is not None:
                record_findings.append(
                    _finding(
                        "NRM_DUP_DRAW_ID",
                        ordinal,
                        "draw_id",
                        "draw_id duplicates an earlier source record",
                    )
                )
            if prior_sequence is not None:
                record_findings.append(
                    _finding(
                        "NRM_DUP_SEQUENCE",
                        ordinal,
                        "draw_sequence",
                        "draw_sequence duplicates an earlier source record",
                    )
                )
            if (prior_id is not None and prior_id != candidate) or (
                prior_sequence is not None and prior_sequence != candidate
            ):
                record_findings.append(
                    _finding(
                        "NRM_DUP_RECORD_CONFLICT",
                        ordinal,
                        "record",
                        "duplicate identity conflicts with an earlier source record",
                    )
                )
            seen_ids.setdefault(draw_id, candidate)
            seen_sequences.setdefault(sequence, candidate)

        findings.extend(record_findings)
        if not record_findings and candidate is not None:
            records.append(candidate)

    return ParseResult(source_record_count, tuple(records), _ordered(findings))
