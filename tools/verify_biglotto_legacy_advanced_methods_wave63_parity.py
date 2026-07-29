#!/usr/bin/env python3
"""Regenerate wave-63 causal advanced-method portfolios from frozen code."""

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
METHOD_ID = "tools/advanced_methods_benchmark.py"
SOURCE_SHA256 = (
    "87ee0d15033c8873c7cf4c1f7334fc154dbab434703195cc4e90810169ea620f"
)
LEDGER_SCHEMA_VERSION = (
    "BIG_LOTTO_ADVANCED_METHODS_WAVE63_TICKET_LEDGER_V1"
)
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_ADVANCED_METHODS_WAVE63_PARITY_V1"
)
CAUSAL_PROTOCOL = (
    "FROZEN_LOCAL_SELECTORS_TARGET_STABLE_SEED42_"
    "RECENT1000_METHOD_ORDER_X_2_THEN_3_BETS_V1"
)
CAUSAL_ELIGIBILITY_RULE = (
    "TARGET_USES_ONLY_STRICTLY_EARLIER_DRAWS_WITH_SOURCE_RECENT1000_LIMIT"
)
SOURCE_REFERENCE_RUNTIME = (
    "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_"
    "TARGET_STABLE_LOCAL_SELECTOR_REINSTANTIATION_SEED42"
)
FIRST_TARGET_REASON = "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF"
METHOD_ORDER = (
    "Contextual Bandit",
    "Copula Analysis",
    "Anomaly Detection",
    "Graph PageRank",
    "Attention Scorer",
)
_REFERENCE_SCRIPT = r"""
import contextlib
import hashlib
import io
import json
import os
import random
import sys

request = json.load(sys.stdin)
root = request["source_root"]
os.chdir(root)
sys.path[:0] = [root, os.path.join(root, "lottery_api")]

import numpy
import scipy
from tools.advanced_methods_benchmark import (
    AnomalyDetector,
    AttentionScorer,
    ContextualBandit,
    CopulaAnalyzer,
    GraphCooccurrence,
)

draws = request["draws"]
tickets = []
closed = []
contexts = []
history_input_counts = []
method_classes = [
    ("Contextual Bandit", ContextualBandit),
    ("Copula Analysis", CopulaAnalyzer),
    ("Anomaly Detection", AnomalyDetector),
    ("Graph PageRank", GraphCooccurrence),
    ("Attention Scorer", AttentionScorer),
]

for index, target in enumerate(draws):
    oldest_prefix = draws[:index]
    recent_prefix = list(reversed(oldest_prefix[-1000:]))
    contexts.append(
        hashlib.sha256(
            json.dumps(
                [draw["numbers"] for draw in oldest_prefix],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )
    history_input_counts.append(len(recent_prefix))
    if index == 0:
        tickets.append(None)
        closed.append(request["first_target_reason"])
        continue
    random.seed(42)
    numpy.random.seed(42)
    portfolio = []
    for num_bets in (2, 3):
        for _, method_class in method_classes:
            method = method_class(49)
            if hasattr(method, "train"):
                try:
                    method.train(recent_prefix[:200])
                except Exception:
                    pass
            for _ in range(num_bets):
                try:
                    selected = method.predict(recent_prefix, 6)
                except Exception:
                    selected = random.sample(range(1, 50), 6)
                values = sorted(int(number) for number in selected)
                if (
                    len(values) != 6
                    or len(set(values)) != 6
                    or values[0] < 1
                    or values[-1] > 49
                ):
                    raise RuntimeError(
                        "illegal advanced-method source ticket"
                    )
                portfolio.append(values)
    tickets.append(portfolio)
    closed.append(None)

json.dump(
    {
        "closed_reason": closed,
        "context_sha256": contexts,
        "history_input_draw_count": history_input_counts,
        "method_order": [name for name, _ in method_classes],
        "numpy_version": numpy.__version__,
        "python_version": ".".join(
            str(item) for item in sys.version_info[:3]
        ),
        "scipy_version": scipy.__version__,
        "targets": [draw["draw"] for draw in draws],
        "tickets": tickets,
    },
    sys.stdout,
    separators=(",", ":"),
    sort_keys=True,
)
"""


class ParityVerificationError(ValueError):
    """Frozen wave-63 source or output violates its contract."""


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
        raise ParityVerificationError(
            completed.stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()
            or "frozen Git query failed"
        )
    return completed.stdout


def _source_identity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
) -> dict[str, object]:
    frozen_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{METHOD_ID}",
    )
    extracted_raw = frozen_source_directory.joinpath(
        METHOD_ID
    ).read_bytes()
    if (
        hashlib.sha256(frozen_raw).hexdigest() != SOURCE_SHA256
        or hashlib.sha256(extracted_raw).hexdigest() != SOURCE_SHA256
        or frozen_raw != extracted_raw
    ):
        raise ParityVerificationError(
            "frozen advanced-method source identity changed"
        )
    text = extracted_raw.decode("utf-8")
    for fragment in (
        "random.seed(42)",
        "np.random.seed(42)",
        "'Contextual Bandit': ContextualBandit(max_num)",
        "'Copula Analysis': CopulaAnalyzer(max_num)",
        "'Anomaly Detection': AnomalyDetector(max_num)",
        "'Graph PageRank': GraphCooccurrence(max_num)",
        "'Attention Scorer': AttentionScorer(max_num)",
        "for nbets in [2, 3]:",
        "for i in range(periods):",
        "context = all_history[i+1:]",
        "method.train(context[:200])",
        "for _ in range(num_bets):",
        "bets.append(random.sample(range(1, max_num + 1), 6))",
    ):
        if fragment not in text:
            raise ParityVerificationError(
                "frozen advanced-method behavior changed"
            )
    return {
        "source_blob_id": (
            _git(
                frozen_root,
                "rev-parse",
                f"{FROZEN_SOURCE_COMMIT}:{METHOD_ID}",
            )
            .decode("ascii")
            .strip()
        ),
        "source_byte_size": len(frozen_raw),
        "source_sha256": SOURCE_SHA256,
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
                "first_target_reason": FIRST_TARGET_REASON,
                "source_root": str(frozen_source_directory),
            }
        ),
        check=False,
        capture_output=True,
        env=environment,
    )
    if completed.returncode != 0:
        raise ParityVerificationError(
            completed.stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()
            or "wave-63 frozen reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityVerificationError(
            "wave-63 frozen reference emitted invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise ParityVerificationError(
            "wave-63 frozen reference output changed"
        )
    document = cast(dict[str, Any], parsed)
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("scipy_version") != "1.12.0"
        or document.get("method_order") != list(METHOD_ORDER)
    ):
        raise ParityVerificationError(
            "wave-63 frozen reference runtime changed"
        )
    return document


def verify_wave63_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the wave-63 ledger and frozen-source parity proof."""

    source_artifact = _source_identity(
        frozen_root=frozen_root,
        frozen_source_directory=frozen_source_directory,
    )
    pinned = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=expected_database_sha256,
    )
    if (
        len(pinned.draws) != 2149
        or pinned.draws[0].draw_number != "96000001"
        or pinned.draws[-1].draw_number != "115000073"
    ):
        raise ParityVerificationError("wave-63 target set changed")
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
    targets_raw = reference.get("targets")
    contexts_raw = reference.get("context_sha256")
    counts_raw = reference.get("history_input_draw_count")
    tickets_raw = reference.get("tickets")
    closed_raw = reference.get("closed_reason")
    if not all(
        isinstance(value, list)
        for value in (
            targets_raw,
            contexts_raw,
            counts_raw,
            tickets_raw,
            closed_raw,
        )
    ):
        raise ParityVerificationError(
            "wave-63 reference layout changed"
        )
    targets = cast(list[object], targets_raw)
    contexts = cast(list[object], contexts_raw)
    counts = cast(list[object], counts_raw)
    tickets = cast(list[object], tickets_raw)
    closed = cast(list[object], closed_raw)
    if (
        not (
            len(targets)
            == len(contexts)
            == len(counts)
            == len(tickets)
            == len(closed)
            == 2149
        )
        or targets[0] != "96000001"
        or targets[-1] != "115000073"
    ):
        raise ParityVerificationError(
            "wave-63 reference coverage changed"
        )
    if (
        tickets[0] is not None
        or closed[0] != FIRST_TARGET_REASON
        or counts[0] != 0
    ):
        raise ParityVerificationError(
            "wave-63 first-target closure changed"
        )
    native_counts: dict[str, int] = {}
    duplicate_counts: dict[str, int] = {}
    for index in range(1, 2149):
        portfolio = tickets[index]
        if not isinstance(portfolio, list):
            raise ParityVerificationError(
                "wave-63 executable output changed"
            )
        typed_portfolio = cast(list[object], portfolio)
        if (
            len(typed_portfolio) != 25
            or closed[index] is not None
            or counts[index] != min(index, 1000)
        ):
            raise ParityVerificationError(
                "wave-63 executable output changed"
            )
        if not all(
            isinstance(ticket, list)
            and len(cast(list[object], ticket)) == 6
            for ticket in typed_portfolio
        ):
            raise ParityVerificationError(
                "wave-63 native ticket layout changed"
            )
        duplicates = len(typed_portfolio) - len(
            {
                tuple(cast(list[int], ticket))
                for ticket in typed_portfolio
            }
        )
        native_counts["25"] = native_counts.get("25", 0) + 1
        duplicate_counts[str(duplicates)] = (
            duplicate_counts.get(str(duplicates), 0) + 1
        )
    ledger: dict[str, object] = {
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "causal_protocol": CAUSAL_PROTOCOL,
        "closed_reason": closed,
        "context_numbers_sha256_by_target": contexts,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "history_input_draw_count": counts,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "legacy_method_id": METHOD_ID,
        "local_configuration_count": [
            None,
            *([10] * 2148),
        ],
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256": SOURCE_SHA256,
        "target_draw_numbers": targets,
        "tickets": tickets,
    }
    ledger["ledger_content_sha256"] = hashlib.sha256(
        _canonical_bytes(ledger)
    ).hexdigest()
    ledger_raw = _canonical_bytes(ledger) + b"\n"
    parity: dict[str, object] = {
        "causal_adapter_facts": {
            "history_input_order": "RECENT_FIRST",
            "history_input_upper_bound": 1000,
            "local_method_order": list(METHOD_ORDER),
            "native_position_order": (
                "NUM_BETS_2_METHOD_ORDER_THEN_NUM_BETS_3_METHOD_ORDER"
            ),
            "random_baseline_excluded": True,
            "source_main_reverse_chronological_state_reuse_excluded": True,
            "target_stable_reinstantiation": True,
        },
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_content_sha256": ledger["ledger_content_sha256"],
        "ledger_file_sha256": hashlib.sha256(ledger_raw).hexdigest(),
        "native_duplicate_ticket_count_distribution": (
            duplicate_counts
        ),
        "native_ticket_case_count": 2148 * 25,
        "native_ticket_count_distribution": native_counts,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifact": source_artifact,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "status": "PASS",
        "status_counts": {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
            "OK": 2148,
        },
        "ticket_sequence_sha256": hashlib.sha256(
            _canonical_bytes(tickets)
        ).hexdigest(),
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
            raise SystemExit(
                f"refusing to overwrite existing output: {path}"
            )
    ledger, parity = verify_wave63_parity(
        frozen_root=args.frozen_root,
        frozen_source_directory=args.frozen_source_directory,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
        reference_python=args.reference_python,
    )
    ledger_raw = _canonical_bytes(ledger) + b"\n"
    parity_raw = _canonical_bytes(parity) + b"\n"
    args.ledger_output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.ledger_output_file.write_bytes(ledger_raw)
    args.output_file.write_bytes(parity_raw)
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
                "parity_file_sha256": hashlib.sha256(
                    parity_raw
                ).hexdigest(),
                "parity_sha256": parity["parity_sha256"],
                "status": parity["status"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
