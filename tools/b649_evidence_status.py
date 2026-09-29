"""Bounded, read-only discovery of existing B649 (BIG_LOTTO) backtest evidence.

Run ``uv run python tools/b649_evidence_status.py --help``.  The default mode prints one
JSON report per ticket count: evidence status, locators, data cutoff, missing draws,
historical ranking and the refresh plan.  ``--write-readme`` rewrites only the generated
README block and ``--check-readme`` exits 1 when that block is stale.

Rules encoded here (see .ai/ai-context/RUNBOOK.md "B649 evidence-first"):

* README is a navigation index, never proof that evidence is absent.
* Old-cutoff evidence is ``AVAILABLE_STALE``, not ``ABSENT``.
* A stale historical ranking is reported first; delta refresh beats a full rerun, and a
  full rerun needs one explicit ``FullRerunReason``.

Only the fixed canonical roots below are read.  Task-owned files referenced from committed
provenance are reported by locator but never opened, so the README block is deterministic.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "src" / "lottolab" / "strategies" / "data"
RESEARCH_DIR = REPO_ROOT / "docs" / "research" / "matrix-native-results"
README_PATH = REPO_ROOT / "README.md"

BEGIN_MARKER = "<!-- BEGIN GENERATED B649 EVIDENCE STATUS -->"
END_MARKER = "<!-- END GENERATED B649 EVIDENCE STATUS -->"

MULTI_TICKET_GLOB = "biglotto_multi_ticket_historical_records_v*.json"
EXACT_NATIVE_GLOB = "biglotto_exact_native_k*_records_v*.json"
SEALED_GEOMETRY_GLOBS = ("b649-k20-*.json", "b649-sealed-*.json")
TICKET_COUNTS = (2, 3, 5, 10, 15, 20)
RANKING_WINDOW = "FULL"
TOP_N = 3
UNKNOWN = "UNKNOWN"
TASK_DATA_DIR = ".task-data"

_DRAW_RE = re.compile(r"^\d{9}$")
_README_LIST_RE = re.compile(r"(\d+(?:\s*[\uff0f/、,]\s*\d+)*)\s*(?:注|-ticket)")
_README_K_RE = re.compile(r"\bK(\d+)\b")

JsonObject = dict[str, object]


class EvidenceStatus(StrEnum):
    AVAILABLE_CURRENT = "AVAILABLE_CURRENT"
    AVAILABLE_STALE = "AVAILABLE_STALE"
    ABSENT = "ABSENT"
    UNAVAILABLE_INVALID = "UNAVAILABLE_INVALID"


class RefreshMode(StrEnum):
    NONE = "NONE"
    DELTA_REFRESH = "DELTA_REFRESH"
    FULL_RERUN = "FULL_RERUN"
    NO_EXISTING_EVIDENCE = "NO_EXISTING_EVIDENCE"


class FullRerunReason(StrEnum):
    INCOMPATIBLE_SCHEMA = "INCOMPATIBLE_SCHEMA"
    INVALID_EXISTING_EVIDENCE = "INVALID_EXISTING_EVIDENCE"
    NON_INCREMENTAL_ALGORITHM = "NON_INCREMENTAL_ALGORITHM"
    OWNER_REQUESTED_FULL_RERUN = "OWNER_REQUESTED_FULL_RERUN"
    OTHER_EXPLICIT_TECHNICAL_REASON = "OTHER_EXPLICIT_TECHNICAL_REASON"


@dataclass(frozen=True)
class RankEntry:
    rank: int
    strategy_id: str
    official_any_prize_rate: str
    coverage: str | None


@dataclass(frozen=True)
class EvidenceSource:
    """One artifact that carries evidence for one ticket count."""

    ticket_count: int
    locator: str
    cutoff: str | None
    packaged: bool
    schema_version: str
    method_id: str
    strategy_count: int | None
    ranking_declared: bool
    ranking: tuple[RankEntry, ...] = ()
    declared_by: str | None = None
    known_gap_draws: tuple[str, ...] = ()


@dataclass(frozen=True)
class RefreshPlan:
    historical_ranking_available: bool
    report_existing_ranking_first: bool
    refresh_recommended: bool
    refresh_required_for_validity: bool
    mode: RefreshMode
    full_rerun_reason: FullRerunReason | None


@dataclass(frozen=True)
class FamilyStatus:
    ticket_count: int
    status: EvidenceStatus
    evidence_locator: str | None
    evidence_packaged: bool
    data_cutoff: str | None
    known_missing_draws: tuple[str, ...] | None
    strategy_count: int | None
    ranking_available: bool
    ranking_locator: str | None
    historical_ranking: tuple[RankEntry, ...]
    historical_ranking_cutoff: str | None
    historical_ranking_locator: str | None
    schema_version: str
    method_id: str
    last_refreshed_at: str
    readme_mentions_ticket_count: bool
    other_locators: tuple[str, ...]
    refresh: RefreshPlan


@dataclass(frozen=True)
class EvidenceReport:
    freshness_reference_draw: str | None
    freshness_reference_kind: str
    lookup_roots: tuple[str, ...]
    readme_discovery_complete: bool
    invalid_locators: tuple[str, ...]
    families: tuple[FamilyStatus, ...]
    sealed_geometry_locators: tuple[str, ...] = field(default=())


# ── draws ────────────────────────────────────────────────────────────────────


def _is_draw(value: object) -> bool:
    return isinstance(value, str) and _DRAW_RE.match(value) is not None


def missing_draws(
    cutoff: str, latest: str, known_gap_draws: Iterable[str] = ()
) -> tuple[str, ...] | None:
    """Draws after ``cutoff`` up to ``latest`` plus known internal gaps, sorted.

    Draw numbers are only enumerable inside one ROC-year prefix; across a year boundary
    the draw count is not derivable from numbers alone, so ``None`` (UNKNOWN) is returned.
    """
    if not (_is_draw(cutoff) and _is_draw(latest)):
        raise ValueError(f"invalid draw number: {cutoff!r} / {latest!r}")
    gaps = {g for g in known_gap_draws if g <= cutoff}
    if latest <= cutoff:
        return tuple(sorted(gaps))
    if cutoff[:3] != latest[:3]:
        return None
    after = (f"{n:09d}" for n in range(int(cutoff) + 1, int(latest) + 1))
    return tuple(sorted(gaps.union(after)))


# ── refresh policy ──────────────────────────────────────────────────────────


def require_full_rerun_reason(reason: object) -> FullRerunReason:
    """A full rerun is only legal with one explicit technical or Owner reason."""
    if isinstance(reason, FullRerunReason):
        return reason
    if isinstance(reason, str) and reason in FullRerunReason.__members__:
        return FullRerunReason(reason)
    raise ValueError(
        f"full rerun requires one of {sorted(FullRerunReason.__members__)}; got {reason!r}"
    )


def plan_refresh(
    status: EvidenceStatus,
    *,
    ranking_available: bool,
    missing: tuple[str, ...] | None,
    schema_compatible: bool = True,
    incremental_algorithm: bool = True,
    owner_full_rerun_reason: FullRerunReason | None = None,
) -> RefreshPlan:
    """Existing evidence first; delta refresh before any full rerun."""
    if status is EvidenceStatus.ABSENT:
        return RefreshPlan(False, False, True, True, RefreshMode.NO_EXISTING_EVIDENCE, None)
    if status is EvidenceStatus.UNAVAILABLE_INVALID:
        reason = FullRerunReason.INVALID_EXISTING_EVIDENCE
        return RefreshPlan(False, False, True, True, RefreshMode.FULL_RERUN, reason)
    reason = owner_full_rerun_reason
    if reason is None and not schema_compatible:
        reason = FullRerunReason.INCOMPATIBLE_SCHEMA
    if reason is None and not incremental_algorithm:
        reason = FullRerunReason.NON_INCREMENTAL_ALGORITHM
    if reason is not None:
        reason = require_full_rerun_reason(reason)
        return RefreshPlan(ranking_available, True, True, False, RefreshMode.FULL_RERUN, reason)
    if status is EvidenceStatus.AVAILABLE_CURRENT:
        return RefreshPlan(ranking_available, True, False, False, RefreshMode.NONE, None)
    recommended = missing is None or len(missing) > 0
    mode = RefreshMode.DELTA_REFRESH if recommended else RefreshMode.NONE
    return RefreshPlan(ranking_available, True, recommended, False, mode, None)


def compare_rankings(
    historical: Sequence[str], refreshed: Sequence[str], *, stable_rank_delta: int = 1
) -> list[JsonObject]:
    """Side-by-side historical vs refreshed ranks; never picks a winner."""
    hist = {sid: i + 1 for i, sid in enumerate(historical)}
    new = {sid: i + 1 for i, sid in enumerate(refreshed)}
    rows: list[JsonObject] = []
    for sid in sorted(hist.keys() | new.keys(), key=lambda s: (hist.get(s, 10**9), s)):
        h, r = hist.get(sid), new.get(sid)
        change = None if h is None or r is None else h - r
        if change is None:
            stability = "ENTERED" if h is None else "DROPPED"
        else:
            stability = "STABLE" if abs(change) <= stable_rank_delta else "UNSTABLE"
        rows.append(
            {
                "strategy_id": sid,
                "historical_rank": h,
                "refreshed_rank": r,
                "rank_change": change,
                "strategy_stability": stability,
            }
        )
    return rows


# ── canonical artifact parsing ─────────────────────────────────────────────


def _obj(value: object) -> JsonObject:
    return cast(JsonObject, value) if isinstance(value, dict) else {}


def _objs(value: object) -> list[JsonObject]:
    return [_obj(v) for v in cast(list[object], value)] if isinstance(value, list) else []


def _str(value: object, default: str = UNKNOWN) -> str:
    return value if isinstance(value, str) else default


def _draw_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and _is_draw(value) else None


def _gaps(doc: JsonObject) -> tuple[str, ...]:
    raw = doc.get("known_gap_draws")
    items = cast(list[object], raw) if isinstance(raw, list) else []
    return tuple(sorted(v for v in items if isinstance(v, str) and _is_draw(v)))


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _task_owned_locator(raw: str, repo_root: Path) -> str:
    """Checkout-independent locator for a task-owned path recorded in provenance."""
    parts = Path(raw).parts
    if TASK_DATA_DIR in parts:
        return Path(*parts[parts.index(TASK_DATA_DIR) :]).as_posix()
    return _rel(Path(raw), repo_root)


def _dec(value: object) -> Decimal:
    return Decimal(value) if isinstance(value, str) else Decimal(-1)


def _rank_exact_native(records: list[JsonObject], k: int) -> tuple[tuple[RankEntry, ...], int]:
    rows = [
        r
        for r in records
        if r.get("ticket_count") == k and r.get("window") == RANKING_WINDOW and r.get("rankable")
    ]
    rows.sort(
        key=lambda r: (
            -_dec(r.get("official_any_prize_rate")),
            -_dec(r.get("official_random_baseline_delta")),
            -_dec(r.get("coverage")),
            _str(r.get("strategy_id")),
        )
    )
    top = tuple(
        RankEntry(
            i + 1,
            _str(r.get("strategy_id")),
            _str(r.get("official_any_prize_rate")),
            cast(str | None, r.get("coverage")) if isinstance(r.get("coverage"), str) else None,
        )
        for i, r in enumerate(rows[:TOP_N])
    )
    return top, len(rows)


def _rank_combinations(records: list[JsonObject], k: int) -> tuple[tuple[RankEntry, ...], int]:
    key = f"{k}|{RANKING_WINDOW}|M3_PLUS"
    rows: list[tuple[int, JsonObject, JsonObject]] = []
    for r in records:
        combo = _obj(_obj(r.get("combinations")).get(key))
        rank = combo.get("official_rank")
        if isinstance(rank, int):
            rows.append((rank, r, combo))
    rows.sort(key=lambda t: (t[0], _str(t[1].get("strategy_id"))))
    top = tuple(
        RankEntry(
            rank,
            _str(r.get("strategy_id")),
            _str(c.get("official_any_prize_rate")),
            cast(str | None, c.get("coverage")) if isinstance(c.get("coverage"), str) else None,
        )
        for rank, r, c in rows[:TOP_N]
    )
    return top, len(rows)


def _parse_multi_ticket(doc: JsonObject, locator: str) -> list[EvidenceSource]:
    records = _objs(doc.get("records"))
    if not records:
        raise ValueError("records missing")
    cutoff = _draw_or_none(_obj(doc.get("dataset")).get("cutoff_draw_number"))
    schema = _str(doc.get("projection_schema_version"))
    exact = _objs(doc.get("exact_native_records"))
    exact_method = _str(doc.get("exact_native_backtest_policy_version"))
    raw_counts = doc.get("ticket_counts")
    declared = cast(list[object], raw_counts) if isinstance(raw_counts, list) else []
    sources: list[EvidenceSource] = []
    for k in sorted({v for v in declared if isinstance(v, int)}):
        if any(r.get("ticket_count") == k for r in exact):
            ranking, count = _rank_exact_native(exact, k)
            method = exact_method
        else:
            ranking, count = _rank_combinations(records, k)
            method = UNKNOWN
        if count == 0:
            continue
        sources.append(
            EvidenceSource(
                k, locator, cutoff, True, schema, method, count, True, ranking,
                known_gap_draws=_gaps(doc),
            )
        )  # fmt: skip
    return sources


def _parse_exact_native(doc: JsonObject, locator: str, repo_root: Path) -> list[EvidenceSource]:
    prov = _obj(doc.get("provenance"))
    records = _objs(doc.get("records"))
    if not records:
        raise ValueError("records missing")
    k = records[0].get("ticket_count")
    if not isinstance(k, int):
        raise ValueError("ticket_count missing")
    cutoff = _draw_or_none(prov.get("cutoff")) or max(
        (d for r in records if (d := _draw_or_none(r.get("last_evaluated_draw")))), default=None
    )
    rows = sorted(
        (
            r
            for r in records
            if r.get("window") == RANKING_WINDOW and isinstance(r.get("rank"), int)
        ),
        key=lambda r: (cast(int, r["rank"]), _str(r.get("strategy_id"))),
    )
    ranking = tuple(
        RankEntry(
            cast(int, r["rank"]),
            _str(r.get("strategy_id")),
            _str(r.get("official_any_prize_rate")),
            cast(str | None, r.get("coverage")) if isinstance(r.get("coverage"), str) else None,
        )
        for r in rows[:TOP_N]
    )
    schema = _str(doc.get("projection_schema_version"))
    method = _str(prov.get("source_ranking_schema"))
    strategies = {_str(r.get("strategy_id")) for r in records}
    sources = [
        EvidenceSource(
            k, locator, cutoff, True, schema, method, len(strategies), bool(rows), ranking,
            known_gap_draws=_gaps(doc),
        )
    ]  # fmt: skip
    ranking_locator = prov.get("source_ranking_locator")
    raw_ks = prov.get("source_ranking_k_values")
    ranked_ks = cast(list[object], raw_ks) if isinstance(raw_ks, list) else []
    if isinstance(ranking_locator, str) and cutoff is not None:
        task_locator = _task_owned_locator(ranking_locator, repo_root)
        for other_k in sorted({v for v in ranked_ks if isinstance(v, int)}):
            sources.append(
                EvidenceSource(
                    other_k, task_locator, cutoff, False, _str(prov.get("source_ranking_schema")),
                    _str(prov.get("source_ranking_run_id")), None, True, (), declared_by=locator,
                )
            )  # fmt: skip
    return sources


def _load(path: Path) -> JsonObject:
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("top-level JSON is not an object")
    return cast(JsonObject, loaded)


def readme_ticket_counts(readme_text: str) -> set[int]:
    """Ticket counts a README happens to mention; discovery hint only, never authority."""
    found: set[int] = set()
    for match in _README_LIST_RE.finditer(readme_text):
        found.update(int(n) for n in re.findall(r"\d+", match.group(1)))
    found.update(int(n) for n in _README_K_RE.findall(readme_text))
    return found


def strip_generated_block(readme_text: str) -> str:
    start, end = readme_text.find(BEGIN_MARKER), readme_text.find(END_MARKER)
    if start == -1 or end == -1:
        return readme_text
    return readme_text[:start] + readme_text[end + len(END_MARKER) :]


def _pick_newest(sources: list[EvidenceSource]) -> EvidenceSource:
    return max(sources, key=lambda s: (s.cutoff or "", s.packaged, s.locator))


def discover(
    *,
    data_dir: Path = DATA_DIR,
    research_dir: Path = RESEARCH_DIR,
    readme_text: str = "",
    latest_draw: str | None = None,
    repo_root: Path = REPO_ROOT,
    ticket_counts: Sequence[int] = TICKET_COUNTS,
) -> EvidenceReport:
    """One bounded pass over the canonical evidence roots.

    ``ABSENT`` is only returned after this lookup found nothing for a ticket count; what
    the README mentions never changes a status (it is only reported as discovery gaps).
    """
    if latest_draw is not None and not _is_draw(latest_draw):
        raise ValueError(f"invalid latest draw: {latest_draw!r}")
    sources: list[EvidenceSource] = []
    invalid: list[str] = []
    paths = sorted(data_dir.glob(MULTI_TICKET_GLOB)) + sorted(data_dir.glob(EXACT_NATIVE_GLOB))
    for path in paths:
        locator = _rel(path, repo_root)
        try:
            doc = _load(path)
            if path.match(MULTI_TICKET_GLOB):
                sources.extend(_parse_multi_ticket(doc, locator))
            else:
                sources.extend(_parse_exact_native(doc, locator, repo_root))
        except (OSError, ValueError, ArithmeticError):
            invalid.append(locator)

    cutoffs = [s.cutoff for s in sources if s.cutoff]
    if latest_draw is not None:
        reference, kind = latest_draw, "SUPPLIED_LATEST_DRAW"
    elif cutoffs:
        reference, kind = max(cutoffs), "REPO_NEWEST_EVIDENCE_CUTOFF"
    else:
        reference, kind = None, UNKNOWN

    mentioned = readme_ticket_counts(strip_generated_block(readme_text))
    families = tuple(
        _family(k, [s for s in sources if s.ticket_count == k], invalid, reference, k in mentioned)
        for k in ticket_counts
    )
    sealed = sorted(
        {_rel(p, repo_root) for g in SEALED_GEOMETRY_GLOBS for p in research_dir.glob(g)}
    )
    return EvidenceReport(
        freshness_reference_draw=reference,
        freshness_reference_kind=kind,
        lookup_roots=(
            f"{_rel(data_dir, repo_root)}/{MULTI_TICKET_GLOB}",
            f"{_rel(data_dir, repo_root)}/{EXACT_NATIVE_GLOB}",
            *(f"{_rel(research_dir, repo_root)}/{g}" for g in SEALED_GEOMETRY_GLOBS),
        ),
        readme_discovery_complete=all(f.readme_mentions_ticket_count for f in families
                                      if f.status is not EvidenceStatus.ABSENT),
        invalid_locators=tuple(invalid),
        families=families,
        sealed_geometry_locators=tuple(sealed),
    )  # fmt: skip


def _family(
    k: int,
    sources: list[EvidenceSource],
    invalid: list[str],
    reference: str | None,
    readme_mentions: bool,
) -> FamilyStatus:
    if not sources:
        status = EvidenceStatus.UNAVAILABLE_INVALID if invalid else EvidenceStatus.ABSENT
        refresh = plan_refresh(status, ranking_available=False, missing=None)
        return FamilyStatus(
            k, status, None, False, None, None, None, False, None, (), None, None, UNKNOWN, UNKNOWN,
            UNKNOWN, readme_mentions, tuple(invalid), refresh,
        )  # fmt: skip
    newest = _pick_newest(sources)
    ranked = [s for s in sources if s.ranking_declared]
    ranking_source = _pick_newest(ranked) if ranked else None
    embedded = [s for s in sources if s.ranking]
    embedded_source = _pick_newest(embedded) if embedded else None
    counted = [s for s in sources if s.strategy_count is not None]
    count_source = _pick_newest(counted) if counted else None

    missing: tuple[str, ...] | None
    if newest.cutoff is None or reference is None:
        status, missing = EvidenceStatus.AVAILABLE_STALE, None
    else:
        missing = missing_draws(newest.cutoff, reference, newest.known_gap_draws)
        current = missing is not None and not missing
        status = EvidenceStatus.AVAILABLE_CURRENT if current else EvidenceStatus.AVAILABLE_STALE
    refresh = plan_refresh(status, ranking_available=ranking_source is not None, missing=missing)
    return FamilyStatus(
        ticket_count=k,
        status=status,
        evidence_locator=newest.locator,
        evidence_packaged=newest.packaged,
        data_cutoff=newest.cutoff,
        known_missing_draws=missing,
        strategy_count=count_source.strategy_count if count_source else None,
        ranking_available=ranking_source is not None,
        ranking_locator=ranking_source.locator if ranking_source else None,
        historical_ranking=embedded_source.ranking if embedded_source else (),
        historical_ranking_cutoff=embedded_source.cutoff if embedded_source else None,
        historical_ranking_locator=embedded_source.locator if embedded_source else None,
        schema_version=newest.schema_version,
        method_id=newest.method_id,
        last_refreshed_at=UNKNOWN,
        readme_mentions_ticket_count=readme_mentions,
        other_locators=tuple(sorted({s.locator for s in sources} - {newest.locator})),
        refresh=refresh,
    )


# ── README generated block ──────────────────────────────────────────────────


_README_HEADER = """\
### B649 回測證據現況（自動產生，請勿手改）

本區塊由 `uv run python tools/b649_evidence_status.py --write-readme` 產生，\
`--check-readme`（pytest 內亦執行）會在與 canonical evidence 不一致時失敗。
README 只是導覽索引，權威是下表 locator；README 沒列出某注數**不代表沒有回測**。
新鮮度參照為 repo 內最新證據 cutoff `{ref}`；repo 不追蹤線上最新期，判定實際缺期請加 \
`--latest-draw <期號>`。舊 cutoff 證據是 `AVAILABLE_STALE`，應先回報歷史排名，\
再以補期（delta refresh）而非全量重跑更新。

| 注數 | 狀態（相對參照） | 最新 cutoff | 缺期（相對參照） | 策略數 | 排名 | 權威 locator |
|---|---|---|---|---|---|---|"""  # noqa: RUF001
_README_RANKING = "；排名 `{locator}`"  # noqa: RUF001
_README_EMBEDDED = "；內嵌排名 `{locator}`（cutoff {cutoff}）"  # noqa: RUF001
_README_TASK_OWNED = (
    "未打包（task-owned、gitignored）的 locator 由已提交 provenance 宣告，"  # noqa: RUF001
    "本工具不讀取其內容：{locators}。"  # noqa: RUF001
)
_README_SEALED = (
    "Sealed-geometry K20 組合屬 outcome-independent 研究族，不是回測排名，"  # noqa: RUF001
    "不得以歷史開獎結果調參：{locators}。"  # noqa: RUF001
)
_README_INVALID = "無法解析：{locators}。"  # noqa: RUF001
_SPAN_DASH = "–"  # noqa: RUF001


def _draw_span(draws: tuple[str, ...] | None) -> str:
    if draws is None:
        return UNKNOWN
    if not draws:
        return "無"
    spans: list[str] = []
    start = prev = draws[0]
    for d in (*draws[1:], ""):
        if d and int(d) == int(prev) + 1:
            prev = d
            continue
        spans.append(start if start == prev else f"{start}{_SPAN_DASH}{prev}")
        start = prev = d
    return "、".join(spans)


def _code_list(paths: Iterable[str]) -> str:
    return "、".join(f"`{p}`" for p in paths)


def render_readme_block(report: EvidenceReport) -> str:
    ref = report.freshness_reference_draw or UNKNOWN
    lines = [BEGIN_MARKER, "", _README_HEADER.format(ref=ref)]
    for f in report.families:
        locator = f"`{f.evidence_locator}`" if f.evidence_locator else "—"
        if f.evidence_locator and f.ranking_locator and f.ranking_locator != f.evidence_locator:
            locator += _README_RANKING.format(locator=f.ranking_locator)
        if f.historical_ranking_locator and f.historical_ranking_locator != f.evidence_locator:
            locator += _README_EMBEDDED.format(
                locator=f.historical_ranking_locator,
                cutoff=f.historical_ranking_cutoff or UNKNOWN,
            )
        lines.append(
            f"| {f.ticket_count} | `{f.status.value}` | {f.data_cutoff or UNKNOWN} "
            f"| {_draw_span(f.known_missing_draws)} "
            f"| {f.strategy_count if f.strategy_count is not None else UNKNOWN} "
            f"| {'YES' if f.ranking_available else 'NO'} | {locator} |"
        )
    task_owned = sorted(
        {
            f.evidence_locator
            for f in report.families
            if f.evidence_locator and not f.evidence_packaged
        }
    )
    if task_owned:
        lines += ["", _README_TASK_OWNED.format(locators=_code_list(task_owned))]
    if report.sealed_geometry_locators:
        sealed = _code_list(report.sealed_geometry_locators)
        lines += ["", _README_SEALED.format(locators=sealed)]
    if report.invalid_locators:
        lines += ["", _README_INVALID.format(locators=_code_list(report.invalid_locators))]
    lines += ["", END_MARKER]
    return "\n".join(lines)


def replace_readme_block(readme_text: str, block: str) -> str:
    start, end = readme_text.find(BEGIN_MARKER), readme_text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise ValueError("README generated B649 evidence markers missing")
    return readme_text[:start] + block + readme_text[end + len(END_MARKER) :]


def expected_readme(
    readme_text: str,
    *,
    data_dir: Path = DATA_DIR,
    research_dir: Path = RESEARCH_DIR,
    repo_root: Path = REPO_ROOT,
) -> str:
    """README bytes with a freshly generated block; never uses a live latest draw."""
    report = discover(
        data_dir=data_dir, research_dir=research_dir, readme_text=readme_text, repo_root=repo_root
    )
    return replace_readme_block(readme_text, render_readme_block(report))


def _jsonable(report: EvidenceReport) -> JsonObject:
    return json.loads(json.dumps(asdict(report), ensure_ascii=False, default=str))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-readme", action="store_true", help="rewrite generated block")
    mode.add_argument("--check-readme", action="store_true", help="exit 1 if block is stale")
    parser.add_argument("--latest-draw", help="live latest draw for freshness, e.g. 115000091")
    args = parser.parse_args(argv)
    if args.write_readme or args.check_readme:
        current = README_PATH.read_text(encoding="utf-8")
        expected = expected_readme(current)
        if args.check_readme:
            ok = expected == current
            print("README_CHECK: PASS" if ok else "README_CHECK: FAIL (run --write-readme)")
            return 0 if ok else 1
        if expected != current:
            README_PATH.write_text(expected, encoding="utf-8")
        print("README generated B649 evidence block up to date")
        return 0
    text = README_PATH.read_text(encoding="utf-8")
    report = discover(readme_text=text, latest_draw=args.latest_draw)
    print(json.dumps(_jsonable(report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
