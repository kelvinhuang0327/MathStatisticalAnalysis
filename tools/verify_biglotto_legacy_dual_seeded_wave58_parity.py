#!/usr/bin/env python3
"""Regenerate wave-58 enhanced-dual and seeded-v6 native portfolios."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
ENHANCED_DUAL_METHOD_ID = (
    "lottery_api/models/enhanced_dual_bet_predictor.py"
)
SEEDED_V6_METHOD_ID = "tools/biglotto_diversified_ensemble_v6.py"
METHOD_IDS = (ENHANCED_DUAL_METHOD_ID, SEEDED_V6_METHOD_ID)
SOURCE_SHA256_BY_METHOD = {
    ENHANCED_DUAL_METHOD_ID: (
        "d5b3de348d01164c2e0079ec207c1a590c44b935217f81dfc9d704a825e50957"
    ),
    SEEDED_V6_METHOD_ID: (
        "8caaac8fcb5d1976174e6def13bf01d47e0fb00edb6d555d838c662bb5daaf2d"
    ),
}
NATIVE_TICKET_COUNT_BY_METHOD = {
    ENHANCED_DUAL_METHOD_ID: 2,
    SEEDED_V6_METHOD_ID: 3,
}
MINIMUM_HISTORY_BY_METHOD = {
    ENHANCED_DUAL_METHOD_ID: 100,
    SEEDED_V6_METHOD_ID: 1,
}
SUPPORT_ARTIFACTS = {
    "lottery_api/common.py": (
        "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2"
    ),
    "lottery_api/database.py": (
        "9fa60bd417050f630af1cbef059550d4ae4cfb7644dac20e0489a16a88b3478a"
    ),
    "lottery_api/models/biglotto_graph.py": (
        "4b5129659aa19628bb9d361b28ba35b65fd79f769f4bf00718c0cb7f45d62e90"
    ),
    "lottery_api/models/negative_selector.py": (
        "e977d50bcf3600ca04f66c2bc296164dda6dd35d0be0ecfbb7a901d5a57d111c"
    ),
    "lottery_api/models/unified_predictor.py": (
        "32d0112c95ce33306002b2f4e13e2c768ff7612c0eb8750cd453cba73575e004"
    ),
}
LEDGER_SCHEMA_VERSION = (
    "BIG_LOTTO_DUAL_SEEDED_WAVE58_TICKET_LEDGER_V1"
)
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_DUAL_SEEDED_WAVE58_PARITY_V1"
)
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"
CAUSAL_ELIGIBILITY_RULE = (
    "TARGET_USES_ONLY_THE_FULL_STRICTLY_EARLIER_DRAW_PREFIX"
)
SOURCE_REFERENCE_RUNTIME = (
    "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_NETWORKX_3_2_1_"
    "ENHANCED_DUAL_DETERMINISTIC_AND_V6_RANDOM_SEED_42_PER_TARGET"
)
INSUFFICIENT_HISTORY_REASON = (
    "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
)
_REFERENCE_SCRIPT = r"""
import contextlib
import io
import json
import os
import sys

request = json.load(sys.stdin)
root = request["source_root"]
os.chdir(root)
sys.path[:0] = [root, os.path.join(root, "lottery_api")]

import networkx
import numpy
import scipy
from lottery_api.models.enhanced_dual_bet_predictor import (
    EnhancedDualBetPredictor,
)
from tools.biglotto_diversified_ensemble_v6 import (
    DiversifiedEnsemble,
)

draws = request["draws"]
enhanced_id = "lottery_api/models/enhanced_dual_bet_predictor.py"
seeded_id = "tools/biglotto_diversified_ensemble_v6.py"
outputs = {enhanced_id: [], seeded_id: []}
errors = {enhanced_id: [], seeded_id: []}

class PrefixDatabase:
    def __init__(self, history):
        self.history = history

    def get_all_draws(self, lottery_type):
        if lottery_type != "BIG_LOTTO":
            raise ValueError("unexpected lottery type")
        return list(reversed(self.history))

for target_index in range(len(draws)):
    if target_index < 100:
        outputs[enhanced_id].append(None)
        errors[enhanced_id].append(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
        continue
    predictor = EnhancedDualBetPredictor()
    predictor.db = PrefixDatabase(draws[:target_index])
    result = predictor.predict("BIG_LOTTO")
    outputs[enhanced_id].append(
        [result["bet1"]["numbers"], result["bet2"]["numbers"]]
    )
    errors[enhanced_id].append(None)

for target_index in range(len(draws)):
    if target_index < 1:
        outputs[seeded_id].append(None)
        errors[seeded_id].append(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
        continue
    with contextlib.redirect_stdout(io.StringIO()):
        result = DiversifiedEnsemble().predict_3bets(
            history=list(reversed(draws[:target_index]))
        )
    outputs[seeded_id].append([row["numbers"] for row in result])
    errors[seeded_id].append(None)

json.dump(
    {
        "errors": errors,
        "networkx_version": networkx.__version__,
        "numpy_version": numpy.__version__,
        "outputs": outputs,
        "python_version": ".".join(str(item) for item in sys.version_info[:3]),
        "scipy_version": scipy.__version__,
    },
    sys.stdout,
    separators=(",", ":"),
    sort_keys=True,
)
"""


class ParityError(ValueError):
    """Frozen artifacts or source execution violate wave-58 parity."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _git(frozen_root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(frozen_root), *arguments),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ParityError(
            completed.stderr.decode("utf-8", errors="replace").strip()
            or "frozen Git query failed"
        )
    return completed.stdout


def _artifact(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    path: str,
    expected_sha256: str,
) -> dict[str, object]:
    git_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{path}",
    )
    extracted_raw = frozen_source_directory.joinpath(path).read_bytes()
    if (
        hashlib.sha256(git_raw).hexdigest() != expected_sha256
        or hashlib.sha256(extracted_raw).hexdigest() != expected_sha256
        or git_raw != extracted_raw
    ):
        raise ParityError(f"frozen artifact identity changed: {path}")
    return {
        "path": path,
        "sha256": expected_sha256,
        "source_blob_id": (
            _git(
                frozen_root,
                "rev-parse",
                f"{FROZEN_SOURCE_COMMIT}:{path}",
            )
            .decode("ascii")
            .strip()
        ),
    }


def _validate_ticket(value: object, *, context: str) -> list[int]:
    if not isinstance(value, list):
        raise ParityError(f"{context}: ticket is not an array")
    values = cast(list[object], value)
    integers = (
        cast(list[int], values)
        if all(type(number) is int for number in values)
        else []
    )
    if (
        len(integers) != 6
        or integers != sorted(integers)
        or len(set(integers)) != 6
        or any(not 1 <= number <= 49 for number in integers)
    ):
        raise ParityError(f"{context}: ticket is not a legal sorted 6/49")
    return integers


def _source_behavior_facts(
    frozen_source_directory: Path,
) -> dict[str, object]:
    enhanced = frozen_source_directory.joinpath(
        ENHANCED_DUAL_METHOD_ID
    ).read_text(encoding="utf-8")
    seeded = frozen_source_directory.joinpath(
        SEEDED_V6_METHOD_ID
    ).read_text(encoding="utf-8")
    negative = frozen_source_directory.joinpath(
        "lottery_api/models/negative_selector.py"
    ).read_text(encoding="utf-8")
    if any(
        fragment not in enhanced
        for fragment in (
            "if len(history) < 100:",
            "'method': 'zone_balance_predict'",
            "'method': 'bayesian_predict'",
            "history[:bet1_config['window']]",
            "history[:bet2_config['window']]",
            "self.negative_selector.filter_prediction",
        )
    ):
        raise ParityError("enhanced-dual frozen behavior changed")
    if any(
        fragment not in seeded
        for fragment in (
            "random.seed(self.seed); np.random.seed(self.seed)",
            "return [bet1, bet2, bet3]",
            "random.sample(pool_1, 6)",
            "random.sample(pool_2, 6)",
            "random.sample(pool_3, 6)",
        )
    ):
        raise ParityError("seeded-v6 frozen behavior changed")
    if (
        "available.sort(key=lambda n: -freq.get(n, 0))"
        not in negative
        or "return sorted(set(result))[:len(prediction)]"
        not in negative
    ):
        raise ParityError("negative-selector behavior changed")
    return {
        ENHANCED_DUAL_METHOD_ID: {
            "entrypoint": "EnhancedDualBetPredictor.predict",
            "history_order": "RECENT_FIRST",
            "minimum_history_draws": 100,
            "native_ticket_count": 2,
            "randomness_used": False,
            "source_configuration": (
                "BIG_LOTTO_ZONE_BALANCE_W500_THEN_BAYESIAN_W300_"
                "WITH_NEGATIVE_EXCLUSION"
            ),
        },
        SEEDED_V6_METHOD_ID: {
            "entrypoint": "DiversifiedEnsemble.predict_3bets",
            "history_order": "RECENT_FIRST",
            "minimum_history_draws": 1,
            "native_ticket_count": 3,
            "randomness_used": True,
            "source_rng_reset": "PYTHON_RANDOM_42_AND_NUMPY_RANDOM_42_PER_TARGET",
        },
    }


def _reference_outputs(
    *,
    reference_python: Path,
    frozen_source_directory: Path,
    draws: list[dict[str, object]],
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        (str(reference_python), "-c", _REFERENCE_SCRIPT),
        input=_canonical_bytes(
            {
                "draws": draws,
                "source_root": str(frozen_source_directory),
            }
        ),
        check=False,
        capture_output=True,
        env=environment,
    )
    if completed.returncode != 0:
        raise ParityError(
            completed.stderr.decode("utf-8", errors="replace").strip()
            or "wave-58 frozen reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError(
            "wave-58 frozen reference emitted invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise ParityError("wave-58 frozen reference output changed")
    document = cast(dict[str, Any], parsed)
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("scipy_version") != "1.12.0"
        or document.get("networkx_version") != "3.2.1"
    ):
        raise ParityError("wave-58 frozen reference runtime changed")
    return document


def verify_wave58_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the full wave-58 ledger and frozen-source parity proof."""

    source_artifacts = [
        _artifact(
            frozen_root=frozen_root,
            frozen_source_directory=frozen_source_directory,
            path=method_id,
            expected_sha256=SOURCE_SHA256_BY_METHOD[method_id],
        )
        for method_id in METHOD_IDS
    ]
    support_artifacts = [
        _artifact(
            frozen_root=frozen_root,
            frozen_source_directory=frozen_source_directory,
            path=path,
            expected_sha256=digest,
        )
        for path, digest in sorted(SUPPORT_ARTIFACTS.items())
    ]
    behavior_facts = _source_behavior_facts(frozen_source_directory)
    pinned = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=expected_database_sha256,
    )
    if (
        len(pinned.draws) != 2149
        or pinned.draws[0].draw_number != "96000001"
        or pinned.draws[-1].draw_number != "115000073"
    ):
        raise ParityError("wave-58 target set changed")
    draws: list[dict[str, object]] = [
        {
            "date": draw.draw_date.isoformat(),
            "draw": draw.draw_number,
            "numbers": list(draw.numbers),
            "special": draw.special,
        }
        for draw in pinned.draws
    ]
    reference = _reference_outputs(
        reference_python=reference_python,
        frozen_source_directory=frozen_source_directory,
        draws=draws,
    )
    outputs_raw = reference.get("outputs")
    errors_raw = reference.get("errors")
    if not isinstance(outputs_raw, dict) or not isinstance(errors_raw, dict):
        raise ParityError("wave-58 reference layout changed")
    outputs = cast(dict[str, object], outputs_raw)
    errors = cast(dict[str, object], errors_raw)
    if set(outputs) != set(METHOD_IDS) or set(errors) != set(METHOD_IDS):
        raise ParityError("wave-58 reference method set changed")
    typed_outputs: dict[str, list[list[list[int]] | None]] = {}
    typed_errors: dict[str, list[str | None]] = {}
    status_counts: dict[str, dict[str, int]] = {}
    sequence_sha256_by_method: dict[str, str] = {}
    for method_id in METHOD_IDS:
        rows_raw = outputs[method_id]
        reasons_raw = errors[method_id]
        if not isinstance(rows_raw, list) or not isinstance(
            reasons_raw, list
        ):
            raise ParityError("wave-58 method sequence changed")
        rows = cast(list[object], rows_raw)
        reasons = cast(list[object], reasons_raw)
        if len(rows) != 2149 or len(reasons) != 2149:
            raise ParityError("wave-58 target count changed")
        typed_rows: list[list[list[int]] | None] = []
        typed_reasons: list[str | None] = []
        for index, (candidate, reason) in enumerate(
            zip(rows, reasons, strict=True)
        ):
            if index < MINIMUM_HISTORY_BY_METHOD[method_id]:
                if (
                    candidate is not None
                    or reason != INSUFFICIENT_HISTORY_REASON
                ):
                    raise ParityError(
                        "wave-58 insufficient-history closure changed"
                    )
                typed_rows.append(None)
                typed_reasons.append(INSUFFICIENT_HISTORY_REASON)
                continue
            if reason is not None or not isinstance(candidate, list):
                raise ParityError("wave-58 executable output changed")
            portfolio = [
                _validate_ticket(
                    ticket,
                    context=f"{method_id} target {index} ticket {ticket_index}",
                )
                for ticket_index, ticket in enumerate(
                    cast(list[object], candidate)
                )
            ]
            if len(portfolio) != NATIVE_TICKET_COUNT_BY_METHOD[method_id]:
                raise ParityError(
                    "wave-58 native ticket count changed"
                )
            typed_rows.append(portfolio)
            typed_reasons.append(None)
        typed_outputs[method_id] = typed_rows
        typed_errors[method_id] = typed_reasons
        ok_count = 2149 - MINIMUM_HISTORY_BY_METHOD[method_id]
        status_counts[method_id] = {
            "CLOSED_INSUFFICIENT_HISTORY": (
                MINIMUM_HISTORY_BY_METHOD[method_id]
            ),
            "OK": ok_count,
        }
        sequence_sha256_by_method[method_id] = hashlib.sha256(
            _canonical_bytes(typed_rows)
        ).hexdigest()
    context_sha256 = [
        hashlib.sha256(
            json.dumps(
                [
                    list(draw.numbers)
                    for draw in pinned.draws[:index]
                ],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        for index in range(2149)
    ]
    ledger: dict[str, object] = {
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "closed_reason_by_method": typed_errors,
        "context_numbers_sha256_by_target": context_sha256,
        "context_policy": CONTEXT_POLICY,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "minimum_history_draws_by_method": MINIMUM_HISTORY_BY_METHOD,
        "native_ticket_count_by_method": NATIVE_TICKET_COUNT_BY_METHOD,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256_by_method": SOURCE_SHA256_BY_METHOD,
        "target_draw_numbers": [
            draw.draw_number for draw in pinned.draws
        ],
        "tickets_by_method": typed_outputs,
    }
    ledger["ledger_content_sha256"] = hashlib.sha256(
        _canonical_bytes(ledger)
    ).hexdigest()
    ledger_raw = _canonical_bytes(ledger) + b"\n"
    parity: dict[str, object] = {
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_behavior_facts": behavior_facts,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_content_sha256": ledger["ledger_content_sha256"],
        "ledger_file_sha256": hashlib.sha256(ledger_raw).hexdigest(),
        "native_ticket_case_count": sum(
            (
                2149 - MINIMUM_HISTORY_BY_METHOD[method_id]
            )
            * NATIVE_TICKET_COUNT_BY_METHOD[method_id]
            for method_id in METHOD_IDS
        ),
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifacts": source_artifacts,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "status": "PASS",
        "status_counts_by_method": status_counts,
        "support_artifacts": support_artifacts,
        "ticket_sequence_sha256_by_method": (
            sequence_sha256_by_method
        ),
    }
    parity["parity_sha256"] = hashlib.sha256(
        _canonical_bytes(parity)
    ).hexdigest()
    return ledger, parity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument(
        "--frozen-source-directory",
        required=True,
        type=Path,
    )
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--expected-database-sha256", required=True)
    parser.add_argument(
        "--reference-python",
        default=Path("/usr/bin/python3"),
        type=Path,
    )
    parser.add_argument("--ledger-output-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.ledger_output_file, args.output_file):
        if path.exists():
            raise SystemExit(f"refusing to overwrite existing output: {path}")
    ledger, parity = verify_wave58_parity(
        frozen_root=args.frozen_root,
        frozen_source_directory=args.frozen_source_directory,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
        reference_python=args.reference_python,
    )
    ledger_raw = _canonical_bytes(ledger) + b"\n"
    args.ledger_output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.ledger_output_file.write_bytes(ledger_raw)
    args.output_file.write_bytes(_canonical_bytes(parity) + b"\n")
    print(
        json.dumps(
            {
                "ledger_content_sha256": ledger[
                    "ledger_content_sha256"
                ],
                "ledger_file_sha256": hashlib.sha256(
                    ledger_raw
                ).hexdigest(),
                "native_ticket_case_count": parity[
                    "native_ticket_case_count"
                ],
                "output_file": str(args.output_file),
                "parity_sha256": parity["parity_sha256"],
                "status": parity["status"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
