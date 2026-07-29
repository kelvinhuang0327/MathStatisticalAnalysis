#!/usr/bin/env python3
"""Verify wave-41 graph port against frozen source under NetworkX 3.2.1."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave41 import (
    FROZEN_NETWORKX_SEMANTICS,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE41_METHOD,
    GRAPH_METHOD_ID,
    SOURCE_NATIVE_WAVE41_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE41_METHOD,
    LegacySourceNativeWave41Request,
    generate_legacy_source_native_wave41_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE41_PARITY_V1"
_HISTORY_COUNTS = tuple(range(50, 115))
_REFERENCE_SCRIPT = r"""
import ast
import contextlib
import io
import json
import sys
import networkx as nx
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations

payload = json.loads(sys.stdin.buffer.read())
graph_tree = ast.parse(payload["graph_source"])
graph_class = next(
    node for node in graph_tree.body
    if isinstance(node, ast.ClassDef) and node.name == "BiglottoGraph"
)
graph_namespace = {
    "Counter": Counter,
    "defaultdict": defaultdict,
    "combinations": combinations,
    "np": np,
    "nx": nx,
}
exec(
    compile(
        ast.fix_missing_locations(ast.Module(body=[graph_class], type_ignores=[])),
        "lottery_api/models/biglotto_graph.py",
        "exec",
    ),
    graph_namespace,
)
wrapper_tree = ast.parse(payload["wrapper_source"])
wrapper_function = next(
    node for node in wrapper_tree.body
    if isinstance(node, ast.FunctionDef)
    and node.name == "graph_centrality_predict"
)
wrapper_namespace = {
    "BiglottoGraph": graph_namespace["BiglottoGraph"],
    "nx": nx,
}
exec(
    compile(
        ast.fix_missing_locations(
            ast.Module(body=[wrapper_function], type_ignores=[])
        ),
        "tools/backtest_graph_method.py",
        "exec",
    ),
    wrapper_namespace,
)
predict = wrapper_namespace["graph_centrality_predict"]
rules = {"minNumber": 1, "maxNumber": 49, "pickCount": 6}
outputs = []
with contextlib.redirect_stdout(io.StringIO()):
    for case in payload["cases"]:
        outputs.append(predict(case["history"], rules)["numbers"])
sys.stdout.write(
    json.dumps(
        {"networkx_version": nx.__version__, "outputs": outputs},
        separators=(",", ":"),
        sort_keys=True,
    )
)
"""


class ParityError(ValueError):
    """Frozen source identity or port output differs."""


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
        raise ParityError("cannot read frozen source artifact")
    return completed.stdout


def _behavior_facts(source_text: str) -> dict[str, object]:
    tree = ast.parse(source_text)
    methods = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "graph_centrality_predict"
    ]
    if len(methods) != 1:
        raise ParityError("frozen graph entrypoint changed")
    compact = "".join(ast.unparse(methods[0]).split())
    required = (
        "graph_builder.build_from_history(history,lookback=500)",
        "nx.degree_centrality(graph)",
        "nx.betweenness_centrality(graph,weight='weight')",
        "degree_cent.get(num,0)*2.0",
        "betweenness_cent.get(num,0)*1.5",
        "feat.get('frequency_ratio',0)*1.5",
        "iffeat.get('is_hot',False)else0.0)*0.8",
        "iffeat.get('is_cold',False)else0.0)*0.3",
        "sorted(scores.items(),key=lambdax:-x[1])[:pick_count]",
    )
    if any(marker not in compact for marker in required):
        raise ParityError("frozen graph scoring semantics changed")
    full_compact = "".join(source_text.split())
    if "engine.deviation_predict(hist,rules)" not in full_compact:
        raise ParityError("frozen deviation baseline order changed")
    return {
        "graph_lookback": 500,
        "native_ticket_order": [
            "graph_centrality",
            "unified_deviation_baseline",
        ],
        "networkx_calls": [
            "degree_centrality",
            "betweenness_centrality(weight=weight)",
        ],
        "networkx_semantics": FROZEN_NETWORKX_SEMANTICS,
        "source_history_cutoff": "STRICTLY_BEFORE_TARGET",
    }


def _reference_outputs(
    *,
    reference_python: Path,
    graph_source: str,
    wrapper_source: str,
    cases: list[dict[str, object]],
) -> tuple[str, list[list[int]]]:
    completed = subprocess.run(
        (str(reference_python), "-c", _REFERENCE_SCRIPT),
        input=_canonical_bytes(
            {
                "cases": cases,
                "graph_source": graph_source,
                "wrapper_source": wrapper_source,
            }
        ),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ParityError("frozen NetworkX reference execution failed")
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError("frozen reference emitted invalid JSON") from exc
    if not isinstance(document, dict):
        raise ParityError("frozen reference output changed")
    typed_document = cast(dict[str, object], document)
    version = typed_document.get("networkx_version")
    outputs = typed_document.get("outputs")
    typed_raw_outputs = (
        cast(list[object], outputs) if isinstance(outputs, list) else []
    )
    if (
        version != "3.2.1"
        or not isinstance(outputs, list)
        or len(typed_raw_outputs) != len(cases)
    ):
        raise ParityError("frozen NetworkX reference version changed")
    typed_outputs: list[list[int]] = []
    for candidate in typed_raw_outputs:
        typed_candidate = (
            cast(list[object], candidate)
            if isinstance(candidate, list)
            else []
        )
        if (
            not isinstance(candidate, list)
            or len(typed_candidate) != 6
            or any(type(number) is not int for number in typed_candidate)
        ):
            raise ParityError("frozen reference ticket changed")
        typed_outputs.append(cast(list[int], typed_candidate))
    return cast(str, version), typed_outputs


def verify_wave41_parity(
    *,
    frozen_root: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
) -> dict[str, object]:
    """Execute frozen graph source and compare every positional graph ticket."""

    source_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{GRAPH_METHOD_ID}",
    )
    source_sha256 = hashlib.sha256(source_raw).hexdigest()
    if source_sha256 != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE41_METHOD[GRAPH_METHOD_ID]:
        raise ParityError("frozen wave-41 source SHA changed")
    source_text = source_raw.decode("utf-8")
    behavior = _behavior_facts(source_text)
    support_artifacts: list[dict[str, str]] = []
    support_sources: dict[str, str] = {}
    for path, expected_sha256 in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE41_METHOD[
        GRAPH_METHOD_ID
    ]:
        raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{path}",
        )
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected_sha256:
            raise ParityError(f"frozen support SHA changed: {path}")
        support_artifacts.append({"path": path, "sha256": digest})
        support_sources[path] = raw.decode("utf-8")

    pinned = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=expected_database_sha256,
    )
    all_history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in pinned.draws
    )
    reference_cases: list[dict[str, object]] = []
    for history_count in _HISTORY_COUNTS:
        reference_cases.append(
            {
                "history": [
                    {
                        "draw": draw.draw_number,
                        "numbers": list(draw.numbers),
                    }
                    for draw in all_history[:history_count]
                ],
            }
        )
    networkx_version, reference_outputs = _reference_outputs(
        reference_python=reference_python,
        graph_source=support_sources["lottery_api/models/biglotto_graph.py"],
        wrapper_source=source_text,
        cases=reference_cases,
    )
    cases: list[dict[str, object]] = []
    for index, history_count in enumerate(_HISTORY_COUNTS):
        history = all_history[:history_count]
        target = pinned.draws[history_count].draw_number
        port = generate_legacy_source_native_wave41_portfolio(
            LegacySourceNativeWave41Request(
                legacy_method_id=GRAPH_METHOD_ID,
                target_draw_number=target,
                history=history,
            )
        )
        reference = tuple(reference_outputs[index])
        if reference != port.tickets[0]:
            raise ParityError("frozen graph positional parity failed")
        cases.append(
            {
                "graph_edge_count": port.metadata.graph_edge_count,
                "graph_ticket": list(port.tickets[0]),
                "history_draw_count": history_count,
                "status": "PASS",
                "target_draw_number": target,
            }
        )
    document: dict[str, object] = {
        "case_count": len(cases),
        "cases": cases,
        "dataset_sha256": pinned.database_sha256_before,
        "frozen_source_behavior_facts": behavior,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "networkx_reference_version": networkx_version,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifacts": [
            {
                "path": GRAPH_METHOD_ID,
                "sha256": source_sha256,
            }
        ],
        "source_native_protocol": SOURCE_NATIVE_WAVE41_PROTOCOL,
        "status": "PASS",
        "support_artifacts": support_artifacts,
    }
    document["parity_sha256"] = hashlib.sha256(_canonical_bytes(document)).hexdigest()
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--expected-database-sha256", required=True)
    parser.add_argument(
        "--reference-python",
        default=Path("/usr/bin/python3"),
        type=Path,
    )
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output_file}")
    document = verify_wave41_parity(
        frozen_root=args.frozen_root,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
        reference_python=args.reference_python,
    )
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(_canonical_bytes(document) + b"\n")
    print(
        json.dumps(
            {
                "case_count": document["case_count"],
                "output_file": str(args.output_file),
                "parity_sha256": document["parity_sha256"],
                "status": document["status"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
