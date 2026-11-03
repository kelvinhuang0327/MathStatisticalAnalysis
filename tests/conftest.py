from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_lottolab_database_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOTTOLAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOTTOLAB_DATABASE_CONFIG", "")
