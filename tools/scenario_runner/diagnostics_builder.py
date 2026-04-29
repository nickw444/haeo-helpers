"""Build HAEO diagnostics payloads from native scenario fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from tools.scenario_runner.models import NativeScenarioFixture


def build_diagnostics_payload(fixture: NativeScenarioFixture) -> dict[str, Any]:
    """Convert a native fixture into HAEO diagnostics payload format."""
    return {
        "config": fixture.config,
        "environment": fixture.environment,
        "inputs": fixture.inputs,
        "outputs": fixture.outputs,
    }


def write_unified_diagnostics(path: Path, payload: dict[str, Any]) -> None:
    """Write diagnostics JSON with a top-level data wrapper."""
    wrapped = {"data": payload}
    path.write_text(json.dumps(wrapped, indent=2) + "\n")


def write_split_diagnostics(directory: Path, payload: dict[str, Any]) -> None:
    """Write diagnostics payload in split-file format."""
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("config", "environment", "inputs", "outputs"):
        file_path = directory / f"{name}.json"
        value = payload.get(name, {} if name == "outputs" else [])
        file_path.write_text(json.dumps(value, indent=2) + "\n")
