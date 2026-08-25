"""Read-only access to the canonical BIG_LOTTO exact-native K2/K3 bundle."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from lottolab.infrastructure.persistence.storage_authorities import (
    StorageAuthority,
    StorageAuthorityRegistry,
    StorageAuthorityResolver,
)

EXACT_NATIVE_K2_K3_CAPABILITY: Final = "BIG_LOTTO_EXACT_NATIVE_K2_K3_REPLAY"
EXACT_NATIVE_SCHEMA: Final = "B649_EXACT_NATIVE_K2_K3_REPLAY_V1"
RUN_ID: Final = "B649_K2_K3_EXACT_NATIVE_FULL_REPLAY_R1"
MANIFEST_SCHEMA: Final = "B649_EXACT_NATIVE_REPLAY_SEALED_MANIFEST_V1"
RANKING_SCHEMA: Final = "B649_EXACT_NATIVE_RANKING_PROJECTION_V1"
PROVENANCE_SCHEMA: Final = "B649_EXACT_NATIVE_EVIDENCE_PROMOTION_PROVENANCE_V1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_WINDOW_SIZES: Final = {"RECENT_50": 50, "RECENT_300": 300, "RECENT_750": 750}
_FAMILY_TICKET_COUNTS: Final = {"K2": 2, "K3": 3}


class ExactNativeEvidenceError(RuntimeError):
    """The canonical exact-native evidence is malformed or inconsistent."""


class ExactNativeEvidenceUnavailableError(ExactNativeEvidenceError):
    """The named exact-native authority is not available for read-only access."""


@dataclass(frozen=True, slots=True)
class ExactNativeEvidenceBundle:
    """The sealed bundle reopened through the canonical authority."""

    manifest: dict[str, object]
    ranking: dict[str, object]
    provenance: dict[str, object]
    replay_sha256: str
    manifest_sha256: str
    ranking_sha256: str
    provenance_sha256: str


class ExactNativeEvidenceReader:
    """Resolve and reopen the exact-native bundle without replay or discovery."""

    def __init__(self, resolver: StorageAuthorityResolver | None = None) -> None:
        self._resolver = resolver or StorageAuthorityRegistry.from_file().resolver()

    def read(self) -> ExactNativeEvidenceBundle:
        verification = self._resolver.verify(EXACT_NATIVE_K2_K3_CAPABILITY, deep=True)
        if verification.passed is not True or verification.path is None:
            raise ExactNativeEvidenceUnavailableError(
                verification.error or "exact-native evidence authority is unavailable"
            )
        try:
            return _read_bundle(verification.path, verification.authority)
        except (OSError, UnicodeError, json.JSONDecodeError, ExactNativeEvidenceError):
            raise
        except Exception as exc:
            raise ExactNativeEvidenceError(
                "exact-native evidence could not be reopened safely"
            ) from exc

    def ranking(self, family: str, window: str) -> dict[str, object]:
        """Return one complete family/window ranking projection."""

        selected_family = _require_family(family)
        selected_window = _require_window(window)
        bundle = self.read()
        leaderboards = _mapping(bundle.ranking.get("leaderboards"), "leaderboards")
        family_boards = _mapping(leaderboards.get(selected_family), selected_family)
        return _mapping(family_boards.get(selected_window), selected_window)

    def top5(self, family: str, window: str) -> tuple[dict[str, object], ...]:
        """Return the sealed top five rows for one family/window projection."""

        ranking = self.ranking(family, window)
        rows = _list(ranking.get("top5"), "top5")
        return tuple(_mapping(row, f"top5[{index}]") for index, row in enumerate(rows))


def read_exact_native_k2_k3_bundle(
    *, resolver: StorageAuthorityResolver | None = None
) -> ExactNativeEvidenceBundle:
    """Read the canonical exact-native bundle through the named resolver entry."""

    return ExactNativeEvidenceReader(resolver).read()


def read_exact_native_k2_k3_ranking(
    family: str,
    window: str,
    *,
    resolver: StorageAuthorityResolver | None = None,
) -> dict[str, object]:
    """Read a complete canonical K2/K3 family/window ranking."""

    return ExactNativeEvidenceReader(resolver).ranking(family, window)


def _read_bundle(path: Path, authority: StorageAuthority) -> ExactNativeEvidenceBundle:
    if authority.capability != EXACT_NATIVE_K2_K3_CAPABILITY:
        raise ExactNativeEvidenceError(
            "resolved authority is not the exact-native K2/K3 capability"
        )
    manifest_path = path.parent / "sealed_manifest.json"
    ranking_path = path.parent / "ranking.json"
    provenance_path = path.parent / "promotion_provenance.json"
    replay_sha256 = _sha256_file(path)
    manifest_sha256 = _sha256_file(manifest_path)
    ranking_sha256 = _sha256_file(ranking_path)
    provenance_sha256 = _sha256_file(provenance_path)
    if authority.sha256 != replay_sha256:
        raise ExactNativeEvidenceError("canonical replay SHA-256 does not match the authority")
    if authority.manifest_sha256 != manifest_sha256:
        raise ExactNativeEvidenceError("canonical manifest SHA-256 does not match the authority")
    if authority.ranking_sha256 != ranking_sha256:
        raise ExactNativeEvidenceError("canonical ranking SHA-256 does not match the authority")
    if authority.provenance_sha256 != provenance_sha256:
        raise ExactNativeEvidenceError("canonical provenance SHA-256 does not match the authority")

    manifest = _read_json_object(manifest_path, "sealed manifest")
    ranking = _read_json_object(ranking_path, "ranking")
    provenance = _read_json_object(provenance_path, "promotion provenance")
    _validate_manifest(manifest, path, replay_sha256)
    _validate_ranking(ranking, manifest, manifest_sha256, replay_sha256)
    _validate_provenance(
        provenance,
        manifest,
        authority,
        replay_sha256,
        manifest_sha256,
        ranking_sha256,
    )
    return ExactNativeEvidenceBundle(
        manifest=manifest,
        ranking=ranking,
        provenance=provenance,
        replay_sha256=replay_sha256,
        manifest_sha256=manifest_sha256,
        ranking_sha256=ranking_sha256,
        provenance_sha256=provenance_sha256,
    )


def _validate_manifest(manifest: dict[str, object], path: Path, replay_sha256: str) -> None:
    if _text(manifest.get("schema_version"), "manifest.schema_version") != MANIFEST_SCHEMA:
        raise ExactNativeEvidenceError("sealed manifest schema is unsupported")
    if _text(manifest.get("run_id"), "manifest.run_id") != RUN_ID:
        raise ExactNativeEvidenceError("sealed manifest run identity is unsupported")
    evidence = _mapping(manifest.get("evidence"), "manifest.evidence")
    if _text(evidence.get("file"), "manifest.evidence.file") != path.name:
        raise ExactNativeEvidenceError("sealed evidence filename is not canonical")
    if _sha(evidence.get("sha256"), "manifest.evidence.sha256") != replay_sha256:
        raise ExactNativeEvidenceError("sealed evidence hash is inconsistent")
    if _integer(evidence.get("byte_size"), "manifest.evidence.byte_size") != path.stat().st_size:
        raise ExactNativeEvidenceError("sealed evidence byte size is inconsistent")
    source = _mapping(manifest.get("source"), "manifest.source")
    if not _text(source.get("head"), "manifest.source.head"):
        raise ExactNativeEvidenceError("sealed source HEAD is missing")
    if not _text(source.get("tree"), "manifest.source.tree"):
        raise ExactNativeEvidenceError("sealed source tree is missing")
    draw_authority = _mapping(manifest.get("draw_authority"), "manifest.draw_authority")
    if _integer(draw_authority.get("draw_count"), "manifest.draw_authority.draw_count") != 2163:
        raise ExactNativeEvidenceError("sealed draw count is not 2163")
    if _sha(draw_authority.get("sha256_before"), "manifest.draw_authority.sha256_before") != _sha(
        draw_authority.get("sha256_after"), "manifest.draw_authority.sha256_after"
    ):
        raise ExactNativeEvidenceError("draw authority changed across the sealed replay")
    universe = _mapping(manifest.get("universe"), "manifest.universe")
    k2_ids = _text_list(universe.get("k2_strategy_ids"), "manifest.universe.k2_strategy_ids")
    k3_ids = _text_list(universe.get("k3_strategy_ids"), "manifest.universe.k3_strategy_ids")
    if len(k2_ids) != 19 or len(k3_ids) != 19 or set(k2_ids) & set(k3_ids):
        raise ExactNativeEvidenceError("sealed K2/K3 universe is invalid")
    if (
        _integer(universe.get("attempted_cell_count"), "manifest.universe.attempted_cell_count")
        != 28500
    ):
        raise ExactNativeEvidenceError("sealed attempted cell count is invalid")
    contract = _mapping(manifest.get("execution_contract"), "manifest.execution_contract")
    if "OFFICIAL_ANY_PRIZE" not in _text(
        contract.get("primary_metric"), "manifest.execution_contract.primary_metric"
    ):
        raise ExactNativeEvidenceError("sealed scoring identity is not OFFICIAL_ANY_PRIZE")
    if contract.get("target_outcome_excluded") is not True:
        raise ExactNativeEvidenceError("sealed target outcome exclusion is invalid")
    target_windows = _mapping(manifest.get("target_windows"), "manifest.target_windows")
    if set(target_windows) != set(_WINDOW_SIZES):
        raise ExactNativeEvidenceError("sealed target windows are incomplete")
    for window, size in _WINDOW_SIZES.items():
        details = _mapping(target_windows.get(window), f"manifest.target_windows.{window}")
        if (
            _integer(details.get("observations_required"), f"{window}.observations_required")
            != size
        ):
            raise ExactNativeEvidenceError(f"sealed {window} observation count is invalid")
        draw_numbers = _text_list(details.get("draw_numbers"), f"{window}.draw_numbers")
        if len(draw_numbers) != size or not draw_numbers:
            raise ExactNativeEvidenceError(f"sealed {window} target sequence is invalid")
        if (
            details.get("first_target") != draw_numbers[0]
            or details.get("last_target") != draw_numbers[-1]
        ):
            raise ExactNativeEvidenceError(f"sealed {window} target boundary is invalid")


def _validate_ranking(
    ranking: dict[str, object],
    manifest: dict[str, object],
    manifest_sha256: str,
    replay_sha256: str,
) -> None:
    if _text(ranking.get("schema_version"), "ranking.schema_version") != RANKING_SCHEMA:
        raise ExactNativeEvidenceError("ranking schema is unsupported")
    if _text(ranking.get("run_id"), "ranking.run_id") != RUN_ID:
        raise ExactNativeEvidenceError("ranking run identity is unsupported")
    if (
        _sha(ranking.get("sealed_evidence_sha256"), "ranking.sealed_evidence_sha256")
        != replay_sha256
    ):
        raise ExactNativeEvidenceError("ranking evidence hash is inconsistent")
    if (
        _sha(ranking.get("sealed_manifest_sha256"), "ranking.sealed_manifest_sha256")
        != manifest_sha256
    ):
        raise ExactNativeEvidenceError("ranking manifest hash is inconsistent")
    contract = _mapping(ranking.get("ranking_contract"), "ranking.ranking_contract")
    if (
        _text(contract.get("primary_metric"), "ranking.ranking_contract.primary_metric")
        != "OFFICIAL_ANY_PRIZE_RATE"
    ):
        raise ExactNativeEvidenceError("ranking metric is not OFFICIAL_ANY_PRIZE_RATE")
    if not isinstance(ranking.get("coverage"), dict) or not isinstance(
        ranking.get("cross_window"), dict
    ):
        raise ExactNativeEvidenceError("ranking full representation is incomplete")
    manifest_universe = _mapping(manifest.get("universe"), "manifest.universe")
    universe_by_family = {
        "K2": set(
            _text_list(
                manifest_universe.get("k2_strategy_ids"), "manifest.universe.k2_strategy_ids"
            )
        ),
        "K3": set(
            _text_list(
                manifest_universe.get("k3_strategy_ids"), "manifest.universe.k3_strategy_ids"
            )
        ),
    }
    leaderboards = _mapping(ranking.get("leaderboards"), "ranking.leaderboards")
    if set(leaderboards) != set(_FAMILY_TICKET_COUNTS):
        raise ExactNativeEvidenceError("ranking family representation is incomplete")
    for family, ticket_count in _FAMILY_TICKET_COUNTS.items():
        family_board = _mapping(leaderboards.get(family), f"ranking.leaderboards.{family}")
        if set(family_board) != set(_WINDOW_SIZES):
            raise ExactNativeEvidenceError(f"ranking {family} windows are incomplete")
        for window, observations_required in _WINDOW_SIZES.items():
            projection = _mapping(family_board.get(window), f"ranking.{family}.{window}")
            if projection.get("status") != "COMPLETE":
                raise ExactNativeEvidenceError(f"ranking {family} {window} is not complete")
            eligible_count = _integer(
                projection.get("eligible_count"), f"ranking.{family}.{window}.eligible_count"
            )
            rows = _list(
                projection.get("eligible_rankings"),
                f"ranking.{family}.{window}.eligible_rankings",
            )
            top5 = _list(projection.get("top5"), f"ranking.{family}.{window}.top5")
            if len(rows) != eligible_count or len(top5) != min(5, eligible_count):
                raise ExactNativeEvidenceError(f"ranking {family} {window} row counts are invalid")
            if top5 != rows[: len(top5)]:
                raise ExactNativeEvidenceError(
                    f"ranking {family} {window} top5 is not a full-ranking prefix"
                )
            seen_ids: set[str] = set()
            for index, raw_row in enumerate(rows, start=1):
                row = _mapping(raw_row, f"ranking.{family}.{window}[{index}]")
                if _integer(row.get("rank"), "ranking.rank") != index:
                    raise ExactNativeEvidenceError(
                        f"ranking {family} {window} ranks are not contiguous"
                    )
                if (
                    _integer(row.get("native_ticket_count"), "ranking.native_ticket_count")
                    != ticket_count
                ):
                    raise ExactNativeEvidenceError(
                        f"ranking {family} {window} native ticket count is invalid"
                    )
                if (
                    _integer(row.get("observations"), "ranking.observations")
                    != observations_required
                ):
                    raise ExactNativeEvidenceError(
                        f"ranking {family} {window} observations are invalid"
                    )
                if (
                    _integer(row.get("observations_required"), "ranking.observations_required")
                    != observations_required
                ):
                    raise ExactNativeEvidenceError(
                        f"ranking {family} {window} required observations are invalid"
                    )
                strategy_id = _text(row.get("strategy_id"), "ranking.strategy_id")
                if strategy_id not in universe_by_family[family] or strategy_id in seen_ids:
                    raise ExactNativeEvidenceError(
                        f"ranking {family} {window} strategy identity is invalid"
                    )
                seen_ids.add(strategy_id)


def _validate_provenance(
    provenance: dict[str, object],
    manifest: dict[str, object],
    authority: StorageAuthority,
    replay_sha256: str,
    manifest_sha256: str,
    ranking_sha256: str,
) -> None:
    if _text(provenance.get("schema_version"), "provenance.schema_version") != PROVENANCE_SCHEMA:
        raise ExactNativeEvidenceError("promotion provenance schema is unsupported")
    if _text(provenance.get("source_task"), "provenance.source_task") != RUN_ID:
        raise ExactNativeEvidenceError("promotion provenance source task is invalid")
    source = _mapping(manifest.get("source"), "manifest.source")
    if provenance.get("source_branch") != source.get("branch"):
        raise ExactNativeEvidenceError("promotion provenance source branch is inconsistent")
    if provenance.get("source_head") != source.get("head"):
        raise ExactNativeEvidenceError("promotion provenance source HEAD is inconsistent")
    if provenance.get("source_tree") != source.get("tree"):
        raise ExactNativeEvidenceError("promotion provenance source tree is inconsistent")
    expected_hashes = {
        "draw_authority_sha256": _mapping(
            manifest.get("draw_authority"), "manifest.draw_authority"
        ).get("sha256_after"),
        "replay_sha256": replay_sha256,
        "manifest_sha256": manifest_sha256,
        "ranking_sha256": ranking_sha256,
    }
    for key, expected in expected_hashes.items():
        if provenance.get(key) != expected:
            raise ExactNativeEvidenceError(f"promotion provenance {key} is inconsistent")
    if (
        _integer(provenance.get("k2"), "provenance.k2") != 19
        or _integer(provenance.get("k3"), "provenance.k3") != 19
    ):
        raise ExactNativeEvidenceError("promotion provenance universe counts are invalid")
    if _text_list(provenance.get("windows"), "provenance.windows") != list(_WINDOW_SIZES):
        raise ExactNativeEvidenceError("promotion provenance windows are invalid")
    if _text(provenance.get("metric"), "provenance.metric") != "OFFICIAL_ANY_PRIZE":
        raise ExactNativeEvidenceError("promotion provenance metric is invalid")
    if _text(provenance.get("upstream_judge"), "provenance.upstream_judge") != "VERIFIED":
        raise ExactNativeEvidenceError("promotion provenance upstream Judge is invalid")
    if (
        _text(provenance.get("two_run_byte_identity"), "provenance.two_run_byte_identity")
        != "VERIFIED"
    ):
        raise ExactNativeEvidenceError("promotion provenance two-run identity is invalid")
    if _text(provenance.get("capability"), "provenance.capability") != authority.capability:
        raise ExactNativeEvidenceError("promotion provenance capability is inconsistent")
    if (
        _text(provenance.get("canonical_relative_path"), "provenance.canonical_relative_path")
        != authority.relative_path
    ):
        raise ExactNativeEvidenceError("promotion provenance locator is inconsistent")


def _require_family(value: str) -> str:
    if value not in _FAMILY_TICKET_COUNTS:
        raise ExactNativeEvidenceError("family must be K2 or K3")
    return value


def _require_window(value: str) -> str:
    if value not in _WINDOW_SIZES:
        raise ExactNativeEvidenceError("window must be RECENT_50, RECENT_300, or RECENT_750")
    return value


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExactNativeEvidenceError(f"{label} is not valid JSON") from exc
    return _mapping(value, label)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ExactNativeEvidenceError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ExactNativeEvidenceError(f"{label} must be a JSON array")
    return cast(list[object], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ExactNativeEvidenceError(f"{label} must be non-empty text")
    return value


def _text_list(value: object, label: str) -> list[str]:
    values = _list(value, label)
    if any(not isinstance(item, str) or not item for item in values):
        raise ExactNativeEvidenceError(f"{label} must contain non-empty text")
    return [cast(str, item) for item in values]


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExactNativeEvidenceError(f"{label} must be an integer")
    return value


def _sha(value: object, label: str) -> str:
    text = _text(value, label)
    if _SHA256.fullmatch(text) is None:
        raise ExactNativeEvidenceError(f"{label} must be a SHA-256 digest")
    return text


__all__ = [
    "EXACT_NATIVE_K2_K3_CAPABILITY",
    "EXACT_NATIVE_SCHEMA",
    "ExactNativeEvidenceBundle",
    "ExactNativeEvidenceError",
    "ExactNativeEvidenceReader",
    "ExactNativeEvidenceUnavailableError",
    "read_exact_native_k2_k3_bundle",
    "read_exact_native_k2_k3_ranking",
]
