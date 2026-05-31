"""Data models for HAEO scenario testing fixtures and results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True, frozen=True)
class NativeScenarioFixture:
    """Canonical scenario fixture used by haeo-helpers."""

    metadata: dict[str, Any]
    config: dict[str, Any]
    environment: dict[str, Any]
    inputs: list[dict[str, Any]]
    outputs: dict[str, Any]
    source: dict[str, Any]
    path: Path


@dataclass(slots=True, frozen=True)
class HaeoScenarioResult:
    """Result payload from a scenario runner execution."""

    diagnostics_path: Path
    return_code: int
    stdout: str
    stderr: str
    outputs: dict[str, Any]


@dataclass(slots=True, frozen=True)
class ScenarioComparison:
    """Simple comparison metrics between EA and HAEO outputs."""

    scenario_name: str
    haeo_output_points: int
    ea_output_points: int
    notes: list[str]
