"""One-shot executable CLI entrypoint and composition for BIG_LOTTO prospective campaign seals.

Usage:
    python -m tools.b649_prospective_campaign_seal \
        --campaign-ordinal 2 \
        --target-draw 115000087

    # With explicit paths
    python -m tools.b649_prospective_campaign_seal \
        --campaign-ordinal 2 \
        --target-draw 115000087 \
        --campaign-spec path/to/campaign_spec.json \
        --draw-seals-dir path/to/draw_seals/
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from lottolab.application.b649_prospective_campaign_seal import (
    EXPECTED_CAMPAIGN_ID,
    EXPECTED_CAMPAIGN_SPEC_SHA256,
    B649CampaignSealResult,
    CampaignSealRunnerError,
    CampaignSequenceError,
    execute_b649_prospective_campaign_seal,
    load_and_validate_campaign_spec,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    verify_schema_read_only,
)
from lottolab.infrastructure.pre_outcome_target_operational import (
    PreOutcomeTargetOperationalComposition,
    compose_pre_outcome_target_operational_service,
)
from lottolab.infrastructure.prospective_observer_store import (
    FileSystemProspectiveObservationStore,
)
from lottolab.strategies.adapters.base import CausalDrawRow

_DEFAULT_SPEC_PATH = Path(
    ".task-data/BRANCH2_TABU7_FIXED_K10_VS_10BET_PROSPECTIVE_104DRAW_CAMPAIGN_R1/campaign_spec.json"
)


class SQLiteB649PersistencePort:
    """Concrete SQLite persistence adapter for B649 campaign seal runner."""

    def __init__(self, paths: LocalDataPaths) -> None:
        self._paths = paths

    @property
    def history_authority_locator(self) -> str:
        return str(self._paths.database)

    def is_outcome_present(
        self,
        lottery_type: LotteryType,
        draw_number: str,
    ) -> bool:
        with open_database(self._paths, read_only=True) as conn:
            outcome_in_db = conn.execute(
                "SELECT 1 FROM draws WHERE lottery_type = ? AND draw_number = ?",
                (lottery_type.value, draw_number),
            ).fetchone()
            return outcome_in_db is not None

    def query_causal_history_rows(
        self,
        lottery_type: LotteryType,
        history_cutoff_draw: str,
    ) -> tuple[CausalDrawRow, ...]:
        with open_database(self._paths, read_only=True) as connection:
            cutoff_row = connection.execute(
                "SELECT draw_date, draw_number FROM draws "
                "WHERE lottery_type = ? AND draw_number = ?",
                (lottery_type.value, history_cutoff_draw),
            ).fetchone()
            if cutoff_row is None:
                raise CampaignSequenceError(
                    f"history cutoff draw {history_cutoff_draw} is not present in official draws"
                )
            cutoff_date, cutoff_num = str(cutoff_row[0]), int(cutoff_row[1])

            cursor = connection.execute(
                """
                SELECT draw_number, draw_date, main_numbers_json
                FROM draws
                WHERE lottery_type = ?
                  AND (
                      draw_date < ?
                      OR (draw_date = ? AND CAST(draw_number AS INTEGER) <= ?)
                  )
                ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC, draw_number ASC
                """,
                (lottery_type.value, cutoff_date, cutoff_date, cutoff_num),
            )
            rows: list[CausalDrawRow] = []
            for draw_num_obj, draw_date_obj, main_json in cursor.fetchall():
                main_list = cast(list[object], json.loads(str(main_json)))
                numbers = tuple(int(cast(int, x)) for x in main_list)
                rows.append(
                    CausalDrawRow(
                        draw=str(draw_num_obj),
                        date=str(draw_date_obj),
                        numbers=numbers,
                    )
                )
            return tuple(rows)

    def verify_read_only_integrity(self) -> bool:
        return verify_schema_read_only(self._paths)


@dataclass(frozen=True, slots=True)
class B649ProspectiveCampaignComposition:
    """Concrete composition bundle for BIG_LOTTO prospective campaign sealing."""

    operational_comp: PreOutcomeTargetOperationalComposition
    observation_store: FileSystemProspectiveObservationStore
    persistence_port: SQLiteB649PersistencePort


def compose_b649_prospective_campaign(
    *,
    data_directory: Path | None = None,
    observation_store_root: Path,
    clock: Callable[[], datetime] | None = None,
) -> B649ProspectiveCampaignComposition:
    """Compose the concrete persistence, observation store, and operational authority."""
    environ_map: dict[str, str] = {}
    if data_directory is not None:
        environ_map[DATA_DIRECTORY_ENV] = str(data_directory.resolve())

    operational_comp = compose_pre_outcome_target_operational_service(
        environ=environ_map if environ_map else None,
        clock=clock,
    )
    observation_store = FileSystemProspectiveObservationStore(
        observation_store_root.resolve()
    )
    persistence_port = SQLiteB649PersistencePort(operational_comp.paths.local_data)
    return B649ProspectiveCampaignComposition(
        operational_comp=operational_comp,
        observation_store=observation_store,
        persistence_port=persistence_port,
    )


def run_b649_prospective_campaign_seal(
    *,
    campaign_id: str,
    campaign_ordinal: int,
    target_draw: str,
    campaign_spec_path: Path,
    draw_seals_dir: Path | None = None,
    data_directory: Path | None = None,
    repo_root: Path | None = None,
    clock: Callable[[], datetime] | None = None,
    expected_campaign_spec_sha256: str = EXPECTED_CAMPAIGN_SPEC_SHA256,
) -> B649CampaignSealResult:
    """Execute one prospective prediction seal for campaign ordinals 2..104."""
    resolved_repo_root = (
        repo_root.resolve()
        if repo_root is not None
        else campaign_spec_path.resolve().parents[2]
    )
    spec = load_and_validate_campaign_spec(
        campaign_spec_path,
        expected_sha256=expected_campaign_spec_sha256,
    )
    resolved_draw_seals_dir = (
        draw_seals_dir.resolve()
        if draw_seals_dir is not None
        else (resolved_repo_root / spec.draw_seals_directory).resolve()
    )
    comp = compose_b649_prospective_campaign(
        data_directory=data_directory,
        observation_store_root=resolved_draw_seals_dir / "observation_store",
        clock=clock,
    )
    return execute_b649_prospective_campaign_seal(
        campaign_id=campaign_id,
        campaign_ordinal=campaign_ordinal,
        target_draw=target_draw,
        campaign_spec_path=campaign_spec_path,
        draw_seals_dir=resolved_draw_seals_dir,
        repo_root=resolved_repo_root,
        registration_service=comp.operational_comp.service,
        observation_store=comp.observation_store,
        persistence_port=comp.persistence_port,
        clock=clock,
        expected_campaign_spec_sha256=expected_campaign_spec_sha256,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="BIG_LOTTO 104-draw prospective campaign seal runner for ordinals 2..104"
    )
    parser.add_argument(
        "--campaign-id",
        type=str,
        default=EXPECTED_CAMPAIGN_ID,
        help="Campaign identifier (must match campaign spec authority)",
    )
    parser.add_argument(
        "--campaign-ordinal",
        type=int,
        required=True,
        help="Campaign ordinal (must be an integer 2..104)",
    )
    parser.add_argument(
        "--target-draw",
        type=str,
        required=True,
        help="Target BIG_LOTTO draw number (e.g. 115000087)",
    )
    parser.add_argument(
        "--campaign-spec",
        type=Path,
        default=_DEFAULT_SPEC_PATH,
        help="Path to frozen campaign_spec.json",
    )
    parser.add_argument(
        "--draw-seals-dir",
        type=Path,
        default=None,
        help="Directory to store draw seals (defaults to path in campaign_spec)",
    )
    parser.add_argument(
        "--data-directory",
        type=Path,
        default=None,
        help="Override SQLite local data directory",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root for relative path resolution",
    )
    return parser


def main(
    argv: list[str] | None = None,
    clock: Callable[[], datetime] | None = None,
    expected_campaign_spec_sha256: str = EXPECTED_CAMPAIGN_SPEC_SHA256,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result: B649CampaignSealResult = run_b649_prospective_campaign_seal(
            campaign_id=args.campaign_id,
            campaign_ordinal=args.campaign_ordinal,
            target_draw=args.target_draw,
            campaign_spec_path=args.campaign_spec,
            draw_seals_dir=args.draw_seals_dir,
            data_directory=args.data_directory,
            repo_root=args.repo_root,
            clock=clock,
            expected_campaign_spec_sha256=expected_campaign_spec_sha256,
        )
        receipt = {
            "status": result.status.value,
            "campaign_id": result.campaign_id,
            "campaign_ordinal": result.campaign_ordinal,
            "target_draw": result.target_draw,
            "history_cutoff_draw": result.history_cutoff_draw,
            "seal_path": str(result.seal_path),
            "seal_sha256": result.seal_sha256,
            "canonical_prediction_record_sha256": result.canonical_prediction_record_sha256,
        }
        sys.stdout.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        return 0
    except CampaignSealRunnerError as exc:
        sys.stderr.write(f"ERROR: {type(exc).__name__}: {exc}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"UNEXPECTED ERROR: {type(exc).__name__}: {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
