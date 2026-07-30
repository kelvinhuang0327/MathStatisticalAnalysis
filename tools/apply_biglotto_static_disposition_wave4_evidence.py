"""Apply the fourth-wave frozen-source dispositions to the BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "3df50a51a06df23bd260184b44e1fb0b6c6cf82af74ae96f5e37af549ead38d4"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE4_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V2"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 15,
    "CLOSED_UNEXECUTABLE": 6,
    "DUPLICATE_ALIAS": 3,
    "OWNER_DECISION_REQUIRED": 197,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 15,
    "CLOSED_UNEXECUTABLE": 21,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 181,
}
CLOSED_METHODS = {
    "analyze_proximity_115000019.py": (
        "55b5baedcc2c5eb91d2864b9ceba92c4d5ea3e596dc7f5c98abb9a944bfc5053",
        "NO_TICKET_SELECTION_ENTRYPOINT",
    ),
    "ai_lab/automl_biglotto/report.py": (
        "d44620e4a3b3bf6cc14b1328a27e774b89469e1edb12fc21fc8739c6c25f25b6",
        "NO_TICKET_SELECTION_ENTRYPOINT",
    ),
    "analysis/p540a_full_replay_regeneration_readiness.py": (
        "c4b73b3cf9d58e79f268c079fb996d4542bdb25b27f3555db79cb004d83a50a4",
        "NO_TICKET_SELECTION_ENTRYPOINT",
    ),
    "analysis/p540b_daily539_incremental_replay_generation.py": (
        "fd786b751d6de9f226d14c1ddab78ef24699cdf8a9f9734f8d54e917e4795d87",
        "FROZEN_SOURCE_SUPPORTS_DAILY_539_ONLY",
    ),
    "ai_lab/scripts/train_critic.py": (
        "e0cfda5699f849f8261d801666412085cc6a649500f7bb8e9c3f3b0d9a6103e1",
        "TRAINING_ONLY_NO_TICKET_SELECTION_ENTRYPOINT",
    ),
    "lottery_api/engine/predraw_ledger.py": (
        "5b2eb5d589e89b6d6a5123f7c7e4357ed3c7cf691e7e09aee993ebcdd83906ed",
        "CALLER_SUPPLIED_TICKETS_NO_SELECTION_ENTRYPOINT",
    ),
    "null_hypothesis_115000019.py": (
        "49c23be4d3407a07bf3bc2f10ccf7b6fb2ca94c711e51bcaeb70a489315398a4",
        "NO_TICKET_SELECTION_ENTRYPOINT",
    ),
    "tools/analyze_draw_115000019.py": (
        "acf606fdb2dea23d9a8ad9bddd8a0314316cb627485f2abdf200e41f3b8a92bb",
        "NO_TICKET_SELECTION_ENTRYPOINT",
    ),
    "tools/analyze_biglotto_special.py": (
        "d3f92b5b3209849da5a2c9f514c5c4dc66255f10e84ab03057694b9f38e30f5f",
        "NO_TICKET_SELECTION_ENTRYPOINT",
    ),
    "tools/arbitrage_analysis.py": (
        "2bb4dc75d414fe0a70367da14ba3bc1bbf55fe7d17f05b4df50b89be8a7b3fe8",
        "NO_TICKET_SELECTION_ENTRYPOINT",
    ),
    "tools/eval_traits_115000021.py": (
        "be2da602c46441f3efc1f10637e46b97223580c483f3c1bdf26caf28b8d0822a",
        "NO_TICKET_SELECTION_ENTRYPOINT",
    ),
    "tools/predict_superlotto_best.py": (
        "e0cc0edec9518246cac204548ff342e6f6f30dec200d87bf22f3a1fe4b869a2f",
        "FROZEN_SOURCE_SUPPORTS_POWER_LOTTO_ONLY",
    ),
    "tools/generate_realistic_data.py": (
        "bff44e409ab91ff60fee502c369efd616cc5f77587cb3b74d117fef17d4d349b",
        "SYNTHETIC_DATA_GENERATOR_NO_PREDICTION_ENTRYPOINT",
    ),
    "tools/negative_selector.py": (
        "80e79f80f9f5978ee2d7e71bb65e7b63bf101192a402ab8a9d0644796d4e3ff0",
        "NEGATIVE_FILTER_ONLY_NO_UPSTREAM_TICKET_SELECTOR",
    ),
    "tools/negative_selector_optimized.py": (
        "55cf2af964a9b5b1ad40f4c15f1c234a6cbaee987278e10b078d10675c286eba",
        "NEGATIVE_FILTER_ONLY_NO_UPSTREAM_TICKET_SELECTOR",
    ),
}
ALIAS_METHOD = "tools/biglotto_diversified_ensemble_v6_backup.py"
ALIAS_SOURCE_SHA256 = (
    "8caaac8fcb5d1976174e6def13bf01d47e0fb00edb6d555d838c662bb5daaf2d"
)
CANONICAL_METHOD = "tools/biglotto_diversified_ensemble_v6.py"
CANONICAL_STRATEGY_ID = (
    "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d"
)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class CatalogOverlayError(ValueError):
    """The base catalog or wave-4 evidence violates the overlay contract."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CatalogOverlayError(f"{path}: invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise CatalogOverlayError(f"{path}: top level must be an object")
    return cast(dict[str, Any], parsed), hashlib.sha256(raw).hexdigest()


def _catalog_hash(document: dict[str, Any]) -> str:
    reduced = {
        key: value
        for key, value in document.items()
        if key != "catalog_sha256"
    }
    return hashlib.sha256(_canonical_bytes(reduced)).hexdigest()


def _validate_digest(value: object, context: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CatalogOverlayError(f"{context} must be a lowercase SHA-256")


def _validate_facts(row: dict[str, Any], *, context: str) -> None:
    facts_raw = row.get("decisive_source_facts")
    if not isinstance(facts_raw, list):
        raise CatalogOverlayError(f"{context} decisive facts changed")
    facts = cast(list[object], facts_raw)
    if len(facts) < 2 or any(
        type(fact) is not str or not fact for fact in facts
    ):
        raise CatalogOverlayError(f"{context} decisive facts changed")


def _validate_evidence(
    evidence: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if (
        evidence.get("evidence_schema_version") != EVIDENCE_SCHEMA_VERSION
        or evidence.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or evidence.get("review_policy_version") != REVIEW_POLICY_VERSION
        or evidence.get("base_catalog_sha256") != BASE_CATALOG_SHA256
    ):
        raise CatalogOverlayError("wave-4 evidence identity changed")
    rows_raw = evidence.get("dispositions")
    if not isinstance(rows_raw, list):
        raise CatalogOverlayError(
            "wave-4 evidence must contain exactly sixteen dispositions"
        )
    rows = cast(list[object], rows_raw)
    if len(rows) != 16:
        raise CatalogOverlayError(
            "wave-4 evidence must contain exactly sixteen dispositions"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for index, candidate in enumerate(rows):
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                f"wave-4 dispositions[{index}] must be an object"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if (
            type(method_id) is not str
            or method_id in by_method
            or method_id not in {*CLOSED_METHODS, ALIAS_METHOD}
        ):
            raise CatalogOverlayError("wave-4 method identity is invalid")
        _validate_digest(row.get("source_sha256"), f"{method_id} source")
        _validate_facts(row, context=method_id)
        if (
            type(row.get("source_blob_id")) is not str
            or len(cast(str, row["source_blob_id"])) != 40
            or type(row.get("source_byte_size")) is not int
            or cast(int, row["source_byte_size"]) <= 0
            or type(row.get("status_reason")) is not str
            or not cast(str, row["status_reason"])
        ):
            raise CatalogOverlayError(
                f"{method_id} frozen-source identity changed"
            )
        if method_id in CLOSED_METHODS:
            source_sha256, reason_code = CLOSED_METHODS[method_id]
            if (
                row.get("reproduction_status") != "CLOSED_UNEXECUTABLE"
                or row.get("source_sha256") != source_sha256
                or row.get("reason_code") != reason_code
                or "canonical_legacy_method_id" in row
                or "canonical_strategy_id" in row
            ):
                raise CatalogOverlayError(
                    f"{method_id} closed disposition changed"
                )
        elif (
            row.get("reproduction_status") != "DUPLICATE_ALIAS"
            or row.get("source_sha256") != ALIAS_SOURCE_SHA256
            or row.get("reason_code")
            != "EXACT_FROZEN_SOURCE_BLOB_DUPLICATE"
            or row.get("canonical_legacy_method_id") != CANONICAL_METHOD
            or row.get("canonical_strategy_id") != CANONICAL_STRATEGY_ID
        ):
            raise CatalogOverlayError("wave-4 alias disposition changed")
        by_method[method_id] = row
    if set(by_method) != {*CLOSED_METHODS, ALIAS_METHOD}:
        raise CatalogOverlayError("wave-4 evidence omits a method")
    return by_method


def _validated_record_index(
    catalog: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise CatalogOverlayError("base catalog records changed")
    records = cast(list[object], records_raw)
    if len(records) != 221:
        raise CatalogOverlayError("base catalog records changed")
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in records:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError("base catalog record is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if type(method_id) is not str or method_id in by_method:
            raise CatalogOverlayError("base catalog record identity changed")
        by_method[method_id] = row
    return by_method


def _validate_pending_record(
    record: dict[str, Any] | None,
    evidence_row: dict[str, Any],
) -> None:
    if (
        record is None
        or record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or record.get("source_sha256")
        != evidence_row.get("source_sha256")
        or record.get("source_blob_id")
        != evidence_row.get("source_blob_id")
        or record.get("source_byte_size")
        != evidence_row.get("source_byte_size")
    ):
        raise CatalogOverlayError(
            "wave-4 evidence leaves the validated base universe"
        )


def apply_wave4_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    catalog, _raw_catalog_sha256 = _read_json(base_catalog_path)
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        catalog.get("catalog_schema_version") != CATALOG_SCHEMA_VERSION
        or catalog.get("catalog_policy_version") != CATALOG_POLICY_VERSION
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or _catalog_hash(catalog) != BASE_CATALOG_SHA256
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
    ):
        raise CatalogOverlayError("base catalog identity changed")
    _validate_digest(evidence_sha256, "evidence file digest")
    evidence_by_method = _validate_evidence(evidence)
    record_by_method = _validated_record_index(catalog)

    canonical = record_by_method.get(CANONICAL_METHOD)
    if (
        canonical is None
        or canonical.get("strategy_id") != CANONICAL_STRATEGY_ID
        or canonical.get("source_sha256") != ALIAS_SOURCE_SHA256
        or canonical.get("source_blob_id")
        != evidence_by_method[ALIAS_METHOD].get("source_blob_id")
        or canonical.get("source_byte_size")
        != evidence_by_method[ALIAS_METHOD].get("source_byte_size")
    ):
        raise CatalogOverlayError("canonical alias target identity changed")

    for method_id, (source_sha256, reason_code) in CLOSED_METHODS.items():
        record = record_by_method.get(method_id)
        evidence_row = evidence_by_method[method_id]
        _validate_pending_record(record, evidence_row)
        assert record is not None
        if record.get("source_sha256") != source_sha256:
            raise CatalogOverlayError("closed source identity changed")
        record.update(
            {
                "candidate_k_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "combination_count_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "native_ticket_semantics": (
                    "NO_EXECUTABLE_BIG_LOTTO_NATIVE_TICKETS"
                ),
                "reproduction_status": "CLOSED_UNEXECUTABLE",
                "status_reason": (
                    f"{evidence_row['status_reason']} Frozen-source wave-4 "
                    f"disposition evidence SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "ticket_order_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "unranked_reason": (
                    f"CLOSED_UNEXECUTABLE:{reason_code}"
                ),
            }
        )

    alias = record_by_method.get(ALIAS_METHOD)
    alias_evidence = evidence_by_method[ALIAS_METHOD]
    _validate_pending_record(alias, alias_evidence)
    assert alias is not None
    alias.update(
        {
            "candidate_k_semantics": (
                "NOT_APPLICABLE_DUPLICATE_ALIAS"
            ),
            "combination_count_semantics": (
                "NOT_APPLICABLE_DUPLICATE_ALIAS"
            ),
            "duplicate_alias_target": CANONICAL_STRATEGY_ID,
            "native_ticket_semantics": (
                "EXACT_FROZEN_SOURCE_BLOB_DUPLICATE_OF_CANONICAL_METHOD"
            ),
            "reproduction_status": "DUPLICATE_ALIAS",
            "status_reason": (
                f"{alias_evidence['status_reason']} Frozen-source wave-4 "
                f"disposition evidence SHA-256 is {evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "INHERITS_CANONICAL_SOURCE_BLOB_SEMANTICS"
            ),
            "ticket_order_semantics": (
                "INHERITS_CANONICAL_SOURCE_BLOB_SEMANTICS"
            ),
            "unranked_reason": "DUPLICATE_ALIAS",
        }
    )

    artifacts_raw = catalog.get("source_artifacts")
    if not isinstance(artifacts_raw, list):
        raise CatalogOverlayError("base source artifacts changed")
    cast(list[object], artifacts_raw).append(
        {
            "artifact_name": evidence_path.name,
            "artifact_sha256": evidence_sha256,
            "evidence_role": "STATIC_DISPOSITION_WAVE4_REVIEW",
        }
    )
    catalog["status_counts"] = EXPECTED_OUTPUT_STATUS_COUNTS
    catalog["catalog_sha256"] = _catalog_hash(catalog)
    return cast(dict[str, object], catalog)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = apply_wave4_evidence(
        base_catalog_path=args.base_catalog,
        evidence_path=args.evidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(catalog) + b"\n")


if __name__ == "__main__":
    main()
