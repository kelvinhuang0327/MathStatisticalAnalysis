"""Read-only, exact-version BIG_LOTTO replay on the published 2,149-draw panel."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date
from functools import cache, lru_cache
from hashlib import sha256
from importlib.resources import files
from types import MappingProxyType
from typing import Any

from lottolab.domain.biglotto_full_strategy_catalog import (
    FullStrategyCatalogRecord,
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw, ReplayTicket

_CATALOG_SHA = "9e2d9f6c3cffbfe9867d4aaafbf8c9315922503fc0b806dfc84627699e0d82e3"
_PANEL_SHA = "0f7446c9662850fd5eed30e7c55376278f43a123ac4d1435ee396ff2d96f9fce"
_WAVES_SHA = "167713638b359503d054469bba2dbcbb18bf5960eb31d8845f7d60594a0777d5"
_MINIMUM = "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
# These learned files were both present at these exact blobs in donor commit
# e56ce9f196342e9d50edc9fd19c42f72c1fa2047, 2026-02-24 11:02:20 +08:00.
# Day-granular draws follow the checkpoint waves' strictly-later-day convention.
_LEARNED_RECIPE_FILES = {
    "tools/historical_audit_rigorous.py": "tools/data/best_config_BIG_LOTTO.json",
    "tools/predict_consensus_ensemble.py": "tools/data/best_config_BIG_LOTTO.json",
    "tools/predict_evolutionary_gum.py": "tools/data/frontier_library_BIG_LOTTO.json",
}
_RECIPE_AVAILABILITY = date(2026, 2, 24)
_CHECKPOINT = "TARGET_NOT_STRICTLY_AFTER_CHECKPOINT_GIT_INTRODUCTION_LOCAL_DATE"


def _read(name: str, digest: str) -> bytes:
    raw = files("lottolab.strategies.data").joinpath(name).read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError(f"packaged replay checksum mismatch: {name}")
    return raw


@cache
def packaged_panel() -> tuple[ReplayDraw, ...]:
    # Source fixture aa7098bf plus historical extension 20f7ccd5. The 20 frozen
    # ledgers independently attest to every available source-context fingerprint.
    raw = _read("biglotto_packaged_replay_panel_v1.csv", _PANEL_SHA)
    reader = csv.DictReader(io.StringIO(raw.decode()))
    return tuple(
        ReplayDraw(
            LotteryType.BIG_LOTTO,
            row["draw"],
            date.fromisoformat(row["date"]),
            tuple(int(row[f"n{i}"]) for i in range(1, 7)),
            int(row["special"]),
        )
        for row in reader
    )


def _index(history: tuple[ReplayDraw, ...], target: ReplayDraw) -> int:
    # The target's public identity is sufficient. Never inspect its outcome.
    panel = packaged_panel()
    index = len(history)
    if (
        index >= len(panel)
        or target.lottery_type is not LotteryType.BIG_LOTTO
        or target.draw_number != panel[index].draw_number
        or target.draw_date != panel[index].draw_date
    ):
        raise ValueError("target is outside the frozen panel or strict prefix has the wrong length")
    if history != panel[:index]:
        raise ValueError("history does not match the frozen strict prefix")
    return index


@dataclass(frozen=True, slots=True)
class FrozenResult:
    status: str
    reason: str | None
    tickets: tuple[ReplayTicket, ...]


@dataclass(frozen=True, slots=True)
class PackagedSource:
    record: FullStrategyCatalogRecord
    wave: int
    ledger: str
    ledger_sha256: str
    ledger_body_sha256: str
    evidence: str
    evidence_sha256: str
    closed_statuses: tuple[str, ...]

    def replay_target(self, history: tuple[ReplayDraw, ...], target: ReplayDraw) -> FrozenResult:
        """Apply per-target source availability on top of the frozen materializer's result."""
        frozen = self.inspect_target(history, target)
        recipe = _LEARNED_RECIPE_FILES.get(self.record.source_path)
        if frozen.status == "OK" and recipe and target.draw_date <= _RECIPE_AVAILABILITY:
            return FrozenResult(
                "BLOCKED_SOURCE_AVAILABILITY",
                f"UNVERIFIED_RECIPE_BEFORE_FIRST_PROVEN_DATE:{recipe}",
                (),
            )
        return frozen

    def inspect_target(self, history: tuple[ReplayDraw, ...], target: ReplayDraw) -> FrozenResult:
        """Read what the frozen source emitted, including original closure status and reason."""
        index = _index(history, target)
        ledger, by_target = _ledger(self.ledger, self.ledger_sha256, self.ledger_body_sha256)
        j = by_target.get(target.draw_number)
        method = self.record.legacy_method_id
        # Wave 57 captured an empty-history candidate but its materializer requires a cutoff.
        if self.wave == 57 and index == 0:
            return FrozenResult(
                "CLOSED_INSUFFICIENT_HISTORY", "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF", ()
            )
        raw = None
        if j is not None:
            if "tickets_by_method" in ledger:
                raw = ledger["tickets_by_method"][method][j]
            elif "tickets" in ledger:
                raw = ledger["tickets"][j]
            else:
                raw = ledger["native_tickets_by_target"][j]
        if raw is None:
            reason = self._closure_reason(ledger, method, j)
            if len(self.closed_statuses) == 1:
                status = self.closed_statuses[0]
            elif self.wave == 61:
                status = (
                    "CLOSED_EXECUTION_ERROR"
                    if reason.startswith("FROZEN_SOURCE_EXECUTION_ERROR:")
                    else "CLOSED_REJECTED"
                )
            else:
                raise ValueError(f"ambiguous frozen closure for {method}")
            return FrozenResult(status, reason, ())

        # Wave 44 encodes a single six-number ticket without a surrounding portfolio.
        portfolio = [raw] if self.wave == 44 else raw
        return FrozenResult(
            "OK",
            None,
            tuple(
                ReplayTicket(position, tuple(numbers))
                for position, numbers in enumerate(portfolio, start=1)
            ),
        )

    def _closure_reason(self, ledger: dict[str, Any], method: str, index: int | None) -> str:
        if self.wave in (44, 55):
            return _CHECKPOINT
        if 45 <= self.wave <= 54:
            return _MINIMUM
        if index is None:
            raise ValueError(f"target missing from full-panel ledger for {method}")
        if "closed_reason_by_method" in ledger:
            reason = ledger["closed_reason_by_method"][method][index]
        elif "closed_reason_by_target" in ledger:
            reason = ledger["closed_reason_by_target"][index]
        else:
            reason = ledger["closed_reason"][index]
        if not isinstance(reason, str) or not reason:
            raise ValueError(f"missing frozen closure reason for {method}")
        return reason


@lru_cache(maxsize=1)
def _ledger(name: str, digest: str, body_digest: str) -> tuple[dict[str, Any], dict[str, int]]:
    # Keep at most one decoded wave between selections. The file digest covers every
    # byte, including the body digest inherited from the separately pinned evidence.
    document = json.loads(_read(name, digest))
    if document["ledger_content_sha256"] != body_digest:
        raise ValueError(f"ledger and evidence disagree on body checksum: {name}")
    targets = document.get("targets", document.get("target_draw_numbers"))
    return document, {target: index for index, target in enumerate(targets)}


@cache
def packaged_replay_sources() -> MappingProxyType[tuple[str, str], PackagedSource]:
    """Return independent source versions only. Catalog aliases own no replay positions."""
    waves = json.loads(_read("biglotto_packaged_replay_waves_v1.json", _WAVES_SHA))
    catalog = load_full_strategy_catalog()
    if catalog.catalog_sha256 != _CATALOG_SHA:
        raise ValueError("frozen donor catalog checksum mismatch")
    records = {record.legacy_method_id: record for record in catalog.records}
    sources: dict[tuple[str, str], PackagedSource] = {}
    for wave, entry in waves.items():
        evidence = json.loads(_read(entry["evidence"], entry["evidence_sha256"]))
        for row in evidence["strategies"]:
            record = records[row["legacy_method_id"]]
            identity = record.strategy_id, record.strategy_version
            if (
                identity in sources
                or record.reproduction_status is not ReproductionStatus.BACKTESTED
                or record.source_sha256 != row["source_sha256"]
                or record.source_commit != evidence["frozen_source_commit"]
                or row.get("strategy_id", record.strategy_id) != record.strategy_id
                or record.strategy_version
                != f"legacy-source-{record.source_commit[:12]}-{record.source_sha256[:12]}"
            ):
                raise ValueError(f"catalog and frozen evidence identity conflict: {identity}")
            sources[identity] = PackagedSource(
                record,
                int(wave),
                entry["ledger"],
                evidence["ledger_file_sha256"],
                evidence["ledger_content_sha256"],
                entry["evidence"],
                entry["evidence_sha256"],
                tuple(status for status in row["execution_status_counts"] if status != "OK"),
            )
    return MappingProxyType(sources)
