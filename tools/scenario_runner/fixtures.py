"""Helpers for loading and validating native scenario fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from tools.scenario_runner.models import NativeScenarioFixture

SCENARIO_FILENAME = "scenario.json"
SUPPORTED_SCHEMA_VERSION = 1


def load_native_fixture(path: Path) -> NativeScenarioFixture:
    """Load a native scenario fixture from directory or file path."""
    fixture_path = path / SCENARIO_FILENAME if path.is_dir() else path
    payload = json.loads(fixture_path.read_text())
    _validate_payload(payload=payload, fixture_path=fixture_path)
    haeo_payload = payload["haeo"]
    return NativeScenarioFixture(
        metadata=payload.get("metadata", {}),
        config=haeo_payload["config"],
        environment=haeo_payload["environment"],
        inputs=haeo_payload["inputs"],
        outputs=haeo_payload.get("outputs", {}),
        source=payload.get("source", {}),
        path=fixture_path,
    )


def _validate_payload(*, payload: dict[str, Any], fixture_path: Path) -> None:
    """Validate basic required fields in a native fixture payload."""
    version = payload.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        msg = (
            f"Unsupported schema version in {fixture_path}: "
            f"expected {SUPPORTED_SCHEMA_VERSION}, got {version!r}."
        )
        raise ValueError(msg)

    if "haeo" not in payload or not isinstance(payload["haeo"], dict):
        msg = f"Fixture {fixture_path} is missing top-level 'haeo' object."
        raise ValueError(msg)

    haeo_payload = payload["haeo"]
    for field in ("config", "environment", "inputs"):
        if field not in haeo_payload:
            msg = f"Fixture {fixture_path} is missing haeo.{field}."
            raise ValueError(msg)
