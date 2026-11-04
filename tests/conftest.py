from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_lottolab_database_environment(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest, tmp_path: Path
) -> None:
    if request.node.get_closest_marker("real_draw_authority_db") is not None:  # pyright: ignore[reportUnknownMemberType]
        monkeypatch.delenv("LOTTOLAB_DATA_DIR", raising=False)
    else:
        monkeypatch.setenv("LOTTOLAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOTTOLAB_DATABASE_CONFIG", "")
