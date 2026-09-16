"""CLI acceptance for preview-first, explicit T539/P638 certificate application."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from lottolab.application.schedule_certificate import (
    OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION,
    OWNER_SCHEDULE_CERTIFYING_AUTHORITY,
)
from lottolab.application.schedule_sync import T539_SCHEDULE_GAME_CODE
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    initialize_schema,
    resolve_local_data_paths,
)
from lottolab.interfaces.cli.main import app


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def _owner_files(tmp_path: Path) -> tuple[Path, Path, str]:
    artifact = b"Official Taiwan Lottery schedule explicitly identifies draw 9001."
    artifact_path = tmp_path / "official-support.bin"
    artifact_path.write_bytes(artifact)
    artifact_path.chmod(0o600)
    certificate_input = {
        "certification_reason": "OFFICIAL_AUTHORITY_ABSENT",
        "certified_at": "2099-01-01T01:00:00Z",
        "certifying_authority": OWNER_SCHEDULE_CERTIFYING_AUTHORITY,
        "draw_date": "2099-01-02",
        "draw_number": "9001",
        "lottery_type": "DAILY_539",
        "official_game_code": T539_SCHEDULE_GAME_CODE,
        "official_source_id": "TAIWAN_LOTTERY_OFFICIAL_SCHEDULE",
        "official_source_locator": (
            "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/NextDrawDate"
        ),
        "official_source_observed_at": "2099-01-01T00:00:00Z",
        "official_source_version": "taiwan-lottery-official-schedule-v1",
        "schedule_timezone": "Asia/Taipei",
        "scheduled_at": "2099-01-02T12:30:00Z",
        "scheduled_local_time": "20:30:00",
        "source_period_identifier": "9001",
        "supporting_artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "supporting_artifact_type": "OFFICIAL_TAIWAN_LOTTERY_HTTPS_PAYLOAD",
    }
    document = {
        "certificate_input": certificate_input,
        "certificate_input_sha256": _canonical_sha256(certificate_input),
        "schema_version": OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION,
    }
    encoded = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    certificate_path = tmp_path / "owner-certificate.json"
    certificate_path.write_bytes(encoded)
    certificate_path.chmod(0o600)
    return certificate_path, artifact_path, hashlib.sha256(encoded).hexdigest()


def test_cli_defaults_to_zero_write_preview_and_requires_explicit_apply(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "canonical-data"
    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(data_root)})
    initialize_schema(paths)
    certificate_path, artifact_path, certificate_sha256 = _owner_files(tmp_path)
    runner = CliRunner()
    arguments = [
        "t539-p638-schedule-certificate",
        "--certificate",
        str(certificate_path),
        "--supporting-artifact",
        str(artifact_path),
        "--expected-certificate-sha256",
        certificate_sha256,
    ]
    before = paths.database.read_bytes()

    preview = runner.invoke(app, arguments, env={DATA_DIRECTORY_ENV: str(data_root)})

    assert preview.exit_code == 0, preview.output
    preview_payload = json.loads(preview.stdout)
    assert preview_payload["status"] == "PREVIEW_ONLY"
    assert preview_payload["zero_write"] is True
    assert preview_payload["apply_certificate_requested"] is False
    assert paths.database.read_bytes() == before

    applied = runner.invoke(
        app,
        [*arguments, "--apply-certificate"],
        env={DATA_DIRECTORY_ENV: str(data_root)},
    )

    assert applied.exit_code == 0, applied.output
    applied_payload = json.loads(applied.stdout)
    assert applied_payload["status"] == "SUCCESS"
    assert applied_payload["disposition"] == "INSERTED"
    assert applied_payload["zero_write"] is False
    assert applied_payload["apply_certificate_requested"] is True


def test_cli_rejects_non_owner_only_certificate(tmp_path: Path) -> None:
    data_root = tmp_path / "canonical-data"
    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(data_root)})
    initialize_schema(paths)
    certificate_path, artifact_path, certificate_sha256 = _owner_files(tmp_path)
    certificate_path.chmod(0o644)

    result = CliRunner().invoke(
        app,
        [
            "t539-p638-schedule-certificate",
            "--certificate",
            str(certificate_path),
            "--supporting-artifact",
            str(artifact_path),
            "--expected-certificate-sha256",
            certificate_sha256,
        ],
        env={DATA_DIRECTORY_ENV: str(data_root)},
    )

    assert result.exit_code == 1
    assert "OWNER_SCHEDULE_CERTIFICATE_INVALID" in result.stderr


def test_cli_rejects_wrong_certificate_document_hash_pin(tmp_path: Path) -> None:
    data_root = tmp_path / "canonical-data"
    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(data_root)})
    initialize_schema(paths)
    certificate_path, artifact_path, _ = _owner_files(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "t539-p638-schedule-certificate",
            "--certificate",
            str(certificate_path),
            "--supporting-artifact",
            str(artifact_path),
            "--expected-certificate-sha256",
            "0" * 64,
        ],
        env={DATA_DIRECTORY_ENV: str(data_root)},
    )

    assert result.exit_code == 1
    assert "OWNER_SCHEDULE_CERTIFICATE_INVALID" in result.stderr
