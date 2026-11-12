"""RFC 3161 timestamp client for pre-draw evidence, using pinned FreeTSA trust.

Only hashes are submitted. A verified timestamp establishes that these exact
bytes existed by the TSA time; it does not establish truth of their contents.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

FREETSA_URL = "https://freetsa.org/tsr"
FREETSA_CA_SHA256 = "2151b61137ffa86bf664691ba67e7da0b19f98c758e3d228d5d8ebf27e044438"
_TIME = re.compile(r"^Time stamp: (.+ GMT)$", re.MULTILINE)
_MAX_RESPONSE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class TimestampProof:
    query: bytes
    response: bytes
    tsa_time: datetime


def _run(openssl: Path, *args: str) -> str:
    result = subprocess.run(
        (str(openssl), "ts", *args),
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return result.stdout


def _check_root(ca_file: Path) -> None:
    if hashlib.sha256(ca_file.read_bytes()).hexdigest() != FREETSA_CA_SHA256:
        raise ValueError("FreeTSA trust anchor does not match pinned SHA-256")


def verify_timestamp(
    payload: bytes,
    proof: TimestampProof,
    *,
    openssl: Path,
    ca_file: Path,
    scratch_root: Path,
) -> datetime:
    """Verify signature, request nonce, exact payload and returned TSA time."""
    _check_root(ca_file)
    if not payload or not proof.query or not proof.response:
        raise ValueError("timestamp evidence is incomplete")
    with tempfile.TemporaryDirectory(prefix="k3-ts-verify-", dir=scratch_root) as temp:
        directory = Path(temp)
        data_path = directory / "data"
        query_path = directory / "query.tsq"
        response_path = directory / "response.tsr"
        data_path.write_bytes(payload)
        query_path.write_bytes(proof.query)
        response_path.write_bytes(proof.response)
        common = ("-in", str(response_path), "-CAfile", str(ca_file))
        _run(openssl, "-verify", *common, "-queryfile", str(query_path))
        _run(openssl, "-verify", *common, "-data", str(data_path))
        details = _run(openssl, "-reply", "-in", str(response_path), "-text")
    match = _TIME.search(details)
    if match is None:
        raise ValueError("verified timestamp has no canonical GMT time")
    verified = datetime.strptime(match.group(1), "%b %d %H:%M:%S %Y GMT").replace(tzinfo=UTC)
    if proof.tsa_time != verified:
        raise ValueError("timestamp metadata does not match the signed response")
    return verified


def request_timestamp(
    payload: bytes, *, openssl: Path, ca_file: Path, scratch_root: Path
) -> TimestampProof:
    """Send a nonce-bearing request over authenticated HTTPS and verify its response."""
    _check_root(ca_file)
    if not payload:
        raise ValueError("cannot timestamp an empty payload")
    with tempfile.TemporaryDirectory(prefix="k3-ts-request-", dir=scratch_root) as temp:
        directory = Path(temp)
        data_path = directory / "data"
        query_path = directory / "query.tsq"
        response_path = directory / "response.tsr"
        data_path.write_bytes(payload)
        _run(
            openssl, "-query", "-data", str(data_path), "-sha256", "-cert", "-out", str(query_path)
        )
        query = query_path.read_bytes()
        request = Request(
            FREETSA_URL,
            data=query,
            headers={"Content-Type": "application/timestamp-query"},
            method="POST",
        )
        with urlopen(request, timeout=20) as result:
            if result.geturl() != FREETSA_URL:
                raise ValueError("timestamp service redirected to an unpinned endpoint")
            response = result.read(_MAX_RESPONSE + 1)
        if not response or len(response) > _MAX_RESPONSE:
            raise ValueError("timestamp response is empty or too large")
        response_path.write_bytes(response)
        details = _run(openssl, "-reply", "-in", str(response_path), "-text")
        match = _TIME.search(details)
        if match is None:
            raise ValueError("timestamp response has no GMT time")
        moment = datetime.strptime(match.group(1), "%b %d %H:%M:%S %Y GMT").replace(tzinfo=UTC)
    proof = TimestampProof(query, response, moment)
    verify_timestamp(payload, proof, openssl=openssl, ca_file=ca_file, scratch_root=scratch_root)
    return proof
