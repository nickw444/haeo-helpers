"""Comparison helpers for EA source outputs vs generated HAEO outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from tools.scenario_runner.fixtures import load_native_fixture
from tools.scenario_runner.models import ScenarioComparison


def compare_scenario_outputs(*, scenario_path: Path, haeo_outputs_path: Path) -> ScenarioComparison:
    """Compare coarse output point counts between EA and HAEO payloads."""
    fixture = load_native_fixture(scenario_path)
    haeo_payload = json.loads(haeo_outputs_path.read_text())
    haeo_outputs = haeo_payload.get("outputs", haeo_payload.get("data", {}).get("outputs", {}))

    ea_raw = fixture.outputs.get("ea_output_payload", {}).get("attributes", {})
    ea_points = _count_points_in_any_timeseries(ea_raw)
    haeo_points = _count_points_in_any_timeseries(haeo_outputs)

    notes: list[str] = []
    if haeo_points == 0:
        notes.append("No HAEO output forecast points found.")
    if ea_points == 0:
        notes.append("No EA output points found in imported source payload.")

    return ScenarioComparison(
        scenario_name=fixture.metadata.get("name", scenario_path.parent.name),
        haeo_output_points=haeo_points,
        ea_output_points=ea_points,
        notes=notes,
    )


def _count_points_in_any_timeseries(payload: Any) -> int:
    """Count likely timeseries points recursively in dict/list payloads."""
    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict) and {"time", "grid"} <= payload[0].keys():
            return len(payload)
        if payload and isinstance(payload[0], dict) and {"time", "value"} <= payload[0].keys():
            return len(payload)
        return sum(_count_points_in_any_timeseries(item) for item in payload)
    if isinstance(payload, dict):
        return sum(_count_points_in_any_timeseries(value) for value in payload.values())
    return 0
