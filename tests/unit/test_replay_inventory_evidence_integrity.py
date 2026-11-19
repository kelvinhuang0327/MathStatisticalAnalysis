from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from lottolab.application import replay_strategy_inventory as inventory_module
from lottolab.domain.biglotto_full_strategy_catalog import FullStrategyCatalog


def test_inventory_loads_only_catalog_verified_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(inventory_module, "_DATA_ROOT", tmp_path)

    def canonical(value: object) -> bytes:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

    original = {"legacy_method_id": "verified", "successful_execution_count": 17}
    expected = hashlib.sha256(canonical(original)).hexdigest()
    (tmp_path / "canonical.json").write_bytes(canonical({**original, "evidence_sha256": expected}))
    (tmp_path / "tampered.json").write_bytes(
        canonical({**original, "successful_execution_count": 999, "evidence_sha256": expected})
    )
    (tmp_path / "wrong_embedded.json").write_bytes(
        canonical({**original, "evidence_sha256": "0" * 64})
    )
    (tmp_path / "invalid.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "duplicate.json").write_text(
        '{"legacy_method_id":"untrusted","legacy_method_id":"verified",'
        f'"successful_execution_count":17,"evidence_sha256":"{expected}"}}',
        encoding="utf-8",
    )
    raw = canonical({"legacy_method_id": "raw", "successful_execution_count": 5})
    (tmp_path / "raw.json").write_bytes(raw)
    artifacts = (
        ("canonical.json", expected, "CAUSAL_BACKTEST"),
        ("tampered.json", expected, "CAUSAL_BACKTEST"),
        ("wrong_embedded.json", expected, "CAUSAL_BACKTEST"),
        ("invalid.json", expected, "CAUSAL_BACKTEST"),
        ("duplicate.json", expected, "CAUSAL_BACKTEST"),
        ("missing.json", expected, "CAUSAL_BACKTEST"),
        ("raw.json", hashlib.sha256(raw).hexdigest(), "CAUSAL_BACKTEST"),
    )
    catalog = cast(FullStrategyCatalog, SimpleNamespace(source_artifacts=artifacts))

    evidence_loader = inventory_module._historical_evidence  # pyright: ignore[reportPrivateUsage]
    counts, _, _, loaded, missing, issues, _ = evidence_loader(catalog)

    assert loaded == 2
    assert missing == 1
    assert counts["verified"].execution_count == 17
    assert counts["raw"].execution_count == 5
    assert "SHA256_MISMATCH:tampered.json" in issues
    assert "SHA256_MISMATCH:wrong_embedded.json" in issues
    assert "SHA256_MISMATCH:invalid.json" in issues
    assert "SHA256_MISMATCH:duplicate.json" in issues
    assert "MISSING_MANIFEST_ARTIFACT:missing.json" in issues
