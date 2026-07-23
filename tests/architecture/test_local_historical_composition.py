"""Architecture guards for the explicit local Historical Results composition seam."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_APP = ROOT / "src/lottolab/interfaces/api/local_app.py"
GENERIC_APP = ROOT / "src/lottolab/interfaces/api/app.py"
LOCAL_RUNTIME = ROOT / "src/lottolab/application/local_runtime.py"


def test_generic_app_remains_free_of_local_historical_environment_composition() -> None:
    source = GENERIC_APP.read_text(encoding="utf-8")

    assert "LOTTOLAB_HISTORICAL_RESULTS_DB" not in source
    assert "local_historical_composition" not in source
    assert (
        "historical_query_repository_factory: HistoricalResultQueryRepositoryFactory | None = None"
        in source
    )
    assert "HistoricalPrefixSuccessWindowSourceReaderFactory | None" in source


def test_local_composition_has_one_exact_environment_contract_and_no_draw_data_fallback() -> None:
    source = LOCAL_APP.read_text(encoding="utf-8")

    assert source.count('"LOTTOLAB_HISTORICAL_RESULTS_DB"') == 1
    assert "LOTTOLAB_DATA_DIR" not in source
    assert "glob(" not in source
    assert ".resolve(" not in source
    assert ".strip(" not in source
    assert "initialize_schema" not in source
    assert "SQLiteHistoricalResultRepository" not in source
    assert "verify_schema_read_only" in source
    assert "SQLiteHistoricalResultQueryRepository(self.database)" in source
    assert "SQLiteHistoricalPrefixSuccessWindowSourceReader(self.database)" in source


def test_local_runtime_uses_only_the_narrow_local_factory() -> None:
    source = LOCAL_RUNTIME.read_text(encoding="utf-8")

    assert "lottolab.interfaces.api.local_app:create_local_app" in source
    assert "lottolab.interfaces.api.app:create_app" not in source
