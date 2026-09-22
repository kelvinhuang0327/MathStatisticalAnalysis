"""Generate and exact-score every unlabeled K=10 minimum-overlap multigraph.

Nauty lives outside the project. Pass ``--nauty-dir`` pointing at a scratch
build of ``geng``, ``multig``, and ``labelg``. This tool does not install them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import subprocess
import time
import tracemalloc
from functools import cmp_to_key
from pathlib import Path

from lottolab.research.b649_k10_min_overlap_exhaustive_r1 import (
    BASELINE_FRACTION,
    EDGE_COUNT,
    MAX_DEGREE,
    TICKET_COUNT,
    canonical_class_id,
    canonical_portfolio_sha256,
    class_set_sha256,
    comparison_label,
    edges_from_portfolio,
    enumerate_small_multigraphs,
    graph_is_admissible,
    number_frequency,
    overlap_mass,
    pair_intersection_histogram,
    parse_multig_line,
    portfolio_from_edges,
    produces_duplicate_ticket,
    structure_of_edges,
)
from lottolab.research.b649_official_any_prize_exact import (
    all_main_draw_masks,
    evaluate_portfolio,
)
from lottolab.research.b649_success_rate_frontier_r1 import load_frontier_record

RESEARCH = Path(__file__).resolve().parents[1] / "src" / "lottolab" / "research"
CLASS_PATH = RESEARCH / "b649_k10_min_overlap_classes.txt"
SCORE_PATH = RESEARCH / "b649_k10_min_overlap_scores.jsonl"
RECORD_PATH = RESEARCH / "b649_k10_min_overlap_exhaustive_r1.json"

_DRAWS = None


def graph6(vertex_count: int, edges: set[tuple[int, int]]) -> str:
    """Nauty graph6 for a simple undirected graph. ``edges`` uses ``i < j``."""

    if not 0 <= vertex_count <= 62:
        raise ValueError("graph6 helper only covers n<=62")
    bits: list[int] = []
    for right in range(1, vertex_count):
        for left in range(right):
            bits.append(1 if (left, right) in edges else 0)
    while len(bits) % 6:
        bits.append(0)
    characters = [chr(vertex_count + 63)]
    for start in range(0, len(bits), 6):
        value = 0
        for bit in bits[start : start + 6]:
            value = (value << 1) | bit
        characters.append(chr(value + 63))
    return "".join(characters)


def gadget_graph6(edges: tuple[tuple[int, int, int], ...], vertex_count: int = TICKET_COUNT) -> str:
    """Simple graph whose isomorphism type is the multigraph's isomorphism type.

    Each unit of multiplicity becomes a private vertex joined only to the two
    ticket-vertices it connects. Parallel copies are indistinguishable.
    """

    simple: set[tuple[int, int]] = set()
    cursor = vertex_count
    for left, right, multiplicity in edges:
        for _ in range(multiplicity):
            simple.add((left, cursor))
            simple.add((right, cursor))
            cursor += 1
    return graph6(cursor, simple)


def _run(command: list[str], stdin: str | None = None) -> str:
    completed = subprocess.run(
        command,
        input=stdin,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def generate_class_lines(nauty_dir: Path) -> list[str]:
    geng = nauty_dir / "geng"
    multig = nauty_dir / "multig"
    command = (
        f"{geng} -D{MAX_DEGREE} -q {TICKET_COUNT} 0:{EDGE_COUNT} | "
        f"{multig} -e{EDGE_COUNT} -D{MAX_DEGREE} -G -q"
    )
    completed = subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
        check=True,
    )
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return lines


def normalized_ids(lines: list[str]) -> list[str]:
    ids: list[str] = []
    for line in lines:
        group_size, edges = parse_multig_line(line)
        if not graph_is_admissible(edges):
            continue
        ids.append(canonical_class_id(TICKET_COUNT, edges, group_size))
    return ids


def nauty_small_count(nauty_dir: Path, vertices: int, edges: int, max_degree: int) -> int:
    command = (
        f"{nauty_dir / 'geng'} -D{max_degree} {vertices} 0:{edges} | "
        f"{nauty_dir / 'multig'} -e{edges} -D{max_degree} -u"
    )
    completed = subprocess.run(command, shell=True, text=True, capture_output=True, check=True)
    for line in completed.stderr.splitlines() + completed.stdout.splitlines():
        if "multigraphs generated" in line:
            return int(line.split("multigraphs generated", 1)[0].split()[-1])
    raise ValueError(completed.stderr or completed.stdout)


def _init_worker(draws) -> None:
    global _DRAWS
    _DRAWS = draws


def _score_class(class_id: str) -> dict[str, object]:
    group_size, edges = parse_multig_line(class_id)
    if not graph_is_admissible(edges) or produces_duplicate_ticket(edges):
        return {"class_id": class_id, "rejected": True}
    portfolio = portfolio_from_edges(edges)
    result = evaluate_portfolio(portfolio, draws=_DRAWS, chunk_size=1 << 16)
    fraction = result.official_any_prize
    return {
        "rejected": False,
        "class_id": class_id,
        "group_size_reported": group_size,
        "portfolio_sha256": canonical_portfolio_sha256(portfolio),
        "numerator": fraction.numerator,
        "denominator": fraction.denominator,
        "outcome_count": result.official_any_prize_outcome_count,
        "pair_histogram": pair_intersection_histogram(portfolio),
        "structure": structure_of_edges(edges),
    }


def load_checkpoint(checkpoint: Path) -> dict[str, dict[str, object]]:
    done: dict[str, dict[str, object]] = {}
    if not checkpoint.exists():
        return done
    for line in checkpoint.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        done[str(row["class_id"])] = row
    return done


def score_all(
    class_ids: list[str], workers: int, checkpoint: Path, *, append: bool
) -> list[dict[str, object]]:
    draws = all_main_draw_masks(49, 6)
    context = multiprocessing.get_context("fork")
    scored: list[dict[str, object]] = []
    with (
        checkpoint.open("a" if append else "w", encoding="utf-8") as handle,
        context.Pool(workers, initializer=_init_worker, initargs=(draws,)) as pool,
    ):
        for index, row in enumerate(
            pool.imap_unordered(_score_class, class_ids, chunksize=4), start=1
        ):
            scored.append(row)
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
            if index % 200 == 0:
                handle.flush()
                print(f"scored {index}/{len(class_ids)}", flush=True)
    return scored


def hard_div_portfolio() -> tuple[tuple[int, ...], ...]:
    record = load_frontier_record()
    row = next(item for item in record["baselines"] if item["k"] == 10)
    return tuple(tuple(ticket) for ticket in row["tickets"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nauty-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--cross-check-only", action="store_true")
    parser.add_argument(
        "--score-limit",
        type=int,
        default=0,
        help="Score only the first N classes and mark the decision bounded. 0 scores every class.",
    )
    args = parser.parse_args()
    nauty_dir = args.nauty_dir
    version = (
        (nauty_dir / "nauty.h").read_text(encoding="utf-8").split("Version ", 1)[1].split(" ", 1)[0]
    )

    cross = []
    for vertices, edges, max_degree in ((5, 4, 3), (6, 4, 3)):
        python_ids = enumerate_small_multigraphs(vertices, edges, max_degree)
        nauty_count = nauty_small_count(nauty_dir, vertices, edges, max_degree)
        cross.append(
            {
                "vertices": vertices,
                "edges": edges,
                "max_degree": max_degree,
                "python_count": len(python_ids),
                "nauty_count": nauty_count,
                "agree": len(python_ids) == nauty_count,
            }
        )
        print("cross", cross[-1], flush=True)
        if len(python_ids) != nauty_count:
            raise SystemExit("independent enumerator disagreed with nauty")
    if args.cross_check_only:
        return

    tracemalloc.start()
    enumeration_started = time.perf_counter()
    first = normalized_ids(generate_class_lines(nauty_dir))
    second = normalized_ids(generate_class_lines(nauty_dir))
    enumeration_seconds = time.perf_counter() - enumeration_started
    digest_1 = class_set_sha256(first)
    digest_2 = class_set_sha256(second)
    if digest_1 != digest_2 or len(first) != len(second) or len(set(first)) != len(first):
        raise SystemExit("class digest runs disagreed")
    rejected = 0
    print(f"classes {len(first)} digest {digest_1}", flush=True)

    labelg = nauty_dir / "labelg"
    gadgets = "\n".join(gadget_graph6(parse_multig_line(class_id)[1]) for class_id in first) + "\n"
    canonical_graphs = _run([str(labelg), "-q"], gadgets)
    canon_lines = [line.strip() for line in canonical_graphs.splitlines() if line.strip()]
    if len(canon_lines) != len(first) or len(set(canon_lines)) != len(first):
        raise SystemExit(
            f"labelg check failed: lines={len(canon_lines)} unique={len(set(canon_lines))}"
        )
    label_digest_1 = hashlib.sha256("\n".join(sorted(canon_lines)).encode()).hexdigest()
    canonical_graphs_2 = _run([str(labelg), "-q"], gadgets)
    label_digest_2 = hashlib.sha256(
        "\n".join(
            sorted(line.strip() for line in canonical_graphs_2.splitlines() if line.strip())
        ).encode()
    ).hexdigest()
    if label_digest_1 != label_digest_2:
        raise SystemExit("labelg digest runs disagreed")

    hard = hard_div_portfolio()
    hard_edges = edges_from_portfolio(hard)
    hard_canon = _run([str(labelg), "-q"], gadget_graph6(hard_edges) + "\n").strip()
    hard_index = canon_lines.index(hard_canon)

    candidates = [
        class_id
        for class_id in (first if args.score_limit <= 0 else first[: args.score_limit])
        if not produces_duplicate_ticket(parse_multig_line(class_id)[1])
    ]
    bounded = args.score_limit > 0 and args.score_limit < len(first)
    rejected = len(first) - len(
        [
            class_id
            for class_id in first
            if not produces_duplicate_ticket(parse_multig_line(class_id)[1])
        ]
    )
    already = load_checkpoint(SCORE_PATH)
    remaining = [class_id for class_id in candidates if class_id not in already]
    print(
        f"scoring {len(remaining)} remaining of {len(candidates)}; "
        f"rejected duplicates {rejected}; resumed {len(already)}",
        flush=True,
    )
    scoring_started = time.perf_counter()
    cpu_started = time.process_time()
    scored_now = (
        score_all(remaining, args.workers, SCORE_PATH, append=bool(already)) if remaining else []
    )
    scoring_seconds = time.perf_counter() - scoring_started
    cpu_seconds = time.process_time() - cpu_started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    accepted = [row for row in already.values() if not row.get("rejected")] + [
        row for row in scored_now if not row["rejected"]
    ]
    if len(accepted) != len(candidates):
        raise SystemExit(
            f"scoring dropped classes: accepted={len(accepted)} expected={len(candidates)}"
        )

    def compare_fractions(left: dict[str, object], right: dict[str, object]) -> int:
        left_value = int(left["numerator"]) * int(right["denominator"])
        right_value = int(right["numerator"]) * int(left["denominator"])
        return (left_value > right_value) - (left_value < right_value)

    accepted.sort(key=cmp_to_key(compare_fractions), reverse=True)
    best = accepted[0]
    best_fraction = f"{best['numerator']}/{best['denominator']}"
    label = comparison_label(int(best["numerator"]), int(best["denominator"]))
    if bounded:
        decision = "BOUNDED_SEARCH_ONLY"
    elif label == "STRICT_IMPROVEMENT":
        decision = "STRICT_IMPROVEMENT_FOUND"
    else:
        decision = "NO_IMPROVEMENT_WITHIN_EXHAUSTED_MIN_OVERLAP_K10_FAMILY"

    hard_class = first[hard_index]
    hard_scored = next((row for row in accepted if row["class_id"] == hard_class), None)
    if hard_scored is None:
        if not bounded:
            raise SystemExit("HARD_DIV class was enumerated but not scored")
        hard_fraction = None
    else:
        hard_fraction = f"{hard_scored['numerator']}/{hard_scored['denominator']}"
        if hard_fraction != f"{BASELINE_FRACTION[0]}/{BASELINE_FRACTION[1]}":
            raise SystemExit(f"HARD_DIV oracle failed: {hard_fraction}")

    top = []
    seen_fractions: set[str] = set()
    for row in accepted:
        fraction = f"{row['numerator']}/{row['denominator']}"
        if fraction in seen_fractions:
            continue
        seen_fractions.add(fraction)
        _group, edges = parse_multig_line(str(row["class_id"]))
        portfolio = portfolio_from_edges(edges)
        top.append(
            {
                "class_id": row["class_id"],
                "official_any_prize": fraction,
                "portfolio_sha256": row["portfolio_sha256"],
                "tickets": [list(ticket) for ticket in portfolio],
                "pair_histogram": row["pair_histogram"],
                "number_frequency": number_frequency(portfolio),
                "overlap_mass": overlap_mass(portfolio),
                "structure": row["structure"],
                "comparison_label": comparison_label(
                    int(row["numerator"]), int(row["denominator"])
                ),
            }
        )
        if len(top) == 20:
            break

    best_edges = parse_multig_line(str(best["class_id"]))[1]
    best_portfolio = portfolio_from_edges(best_edges)
    record = {
        "tool": "nauty",
        "tool_version": version,
        "tool_url": "https://pallini.di.uniroma1.it/nauty2_9_0.tar.gz",
        "commands": {
            "enumerate": (
                f"geng -D{MAX_DEGREE} -q {TICKET_COUNT} 0:{EDGE_COUNT} | "
                f"multig -e{EDGE_COUNT} -D{MAX_DEGREE} -G -q"
            ),
            "isomorphism_check": "labelg -q  on the private-vertex multiplicity gadget",
        },
        "labeled_search_definition": (
            "loopless multigraphs on 10 labeled tickets are not enumerated; "
            "geng enumerates unlabeled simple graphs with at most 11 edges and "
            "maximum degree 6, and multig replaces those edges by all multiplicity "
            "vectors whose multiplicities sum to 11 and whose degrees stay at most 6"
        ),
        "enumerator_raw_count": len(first),
        "canonical_unique_count": len(first) - rejected,
        "rejected_invalid_count": rejected,
        "unlabeled_class_count": len(first) - rejected,
        "class_set_sha256_run_1": digest_1,
        "class_set_sha256_run_2": digest_2,
        "labelg_class_set_sha256_run_1": label_digest_1,
        "labelg_class_set_sha256_run_2": label_digest_2,
        "parallel_edges_included": True,
        "exact_evaluation_count": len(accepted),
        "enumeration_wall_time_sec": enumeration_seconds,
        "scoring_wall_time_sec": scoring_seconds,
        "scoring_cpu_time_sec": cpu_seconds,
        "peak_memory_bytes": peak,
        "workers": args.workers,
        "small_enumeration_cross_check": cross,
        "baseline_in_family": True,
        "hard_div_class_id": hard_class,
        "hard_div_exact": hard_fraction,
        "hard_div_sha256": "13b1126d5b26ce44c9aba24670142eeab49f4a4b51aaf3bbabe7a7f1659ac673",
        "hard_div_overlap_mass": overlap_mass(hard),
        "hard_div_pair_histogram": pair_intersection_histogram(hard),
        "hard_div_number_frequency": number_frequency(hard),
        "hard_div_structure": structure_of_edges(hard_edges),
        "best_exact": best_fraction,
        "best_delta": str(
            __import__("fractions").Fraction(int(best["numerator"]), int(best["denominator"]))
            - __import__("fractions").Fraction(*BASELINE_FRACTION)
        ),
        "best_class_id": best["class_id"],
        "best_portfolio_sha256": best["portfolio_sha256"],
        "best_tickets": [list(ticket) for ticket in best_portfolio],
        "best_structure": best["structure"],
        "best_pair_histogram": best["pair_histogram"],
        "top_distinct_fractions": top,
        "global_optimum_status": "UNKNOWN",
        "exhaustive_status": "NOT_PROVEN" if bounded else "PROVEN",
        "final_decision": decision,
        "next_task": "B649_K20_UNLABELED_MIN_OVERLAP_CANONICAL_ENUMERATION_R1",
        "also_named_not_started": "K10 pairwise overlap mass 12, then 13",
        "next_task_started": False,
    }
    CLASS_PATH.write_text("\n".join(first) + "\n", encoding="utf-8")
    with SCORE_PATH.open("w", encoding="utf-8") as handle:
        for row in accepted:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    RECORD_PATH.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print("decision", decision, "best", best_fraction, "delta", record["best_delta"], flush=True)


if __name__ == "__main__":
    main()
