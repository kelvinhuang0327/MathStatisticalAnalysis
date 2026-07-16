"""DB-free import adapters for LottoLab-owned canonical formats."""

from lottolab.infrastructure.imports.csv_draws import (
    MAX_CSV_BYTES,
    MAX_CSV_ROWS,
    MAX_DRAW_NUMBER_LENGTH,
    NUMBER_DELIMITER,
    PARSER_VERSION,
    RULE_STATUS_BY_LOTTERY_TYPE,
    SUPPORTED_LOTTERY_TYPES,
    parse_draw_csv,
)

__all__ = [
    "MAX_CSV_BYTES",
    "MAX_CSV_ROWS",
    "MAX_DRAW_NUMBER_LENGTH",
    "NUMBER_DELIMITER",
    "PARSER_VERSION",
    "RULE_STATUS_BY_LOTTERY_TYPE",
    "SUPPORTED_LOTTERY_TYPES",
    "parse_draw_csv",
]
