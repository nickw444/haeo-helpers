"""Tests for scenario runner CLI helper commands."""

from __future__ import annotations

from pathlib import Path
import json

from tools.scenario_runner.comparison import compare_scenario_outputs


def test_compare_scenario_outputs_counts_points(tmp_path):
    scenario_path = Path("tests/data/scenarios/simple_native/scenario.json")
    haeo_outputs_path = tmp_path / "haeo_outputs.json"
    haeo_outputs_path.write_text(
        json.dumps(
            {
                "outputs": {
                    "sensor.grid_power_active": {
                        "attributes": {
                            "forecast": [
                                {"time": "2026-01-01T00:00:00+00:00", "value": 1.0},
                                {"time": "2026-01-01T01:00:00+00:00", "value": 2.0},
                            ]
                        }
                    }
                }
            },
            indent=2,
        )
        + "\n"
    )

    comparison = compare_scenario_outputs(
        scenario_path=scenario_path,
        haeo_outputs_path=haeo_outputs_path,
    )
    assert comparison.scenario_name == "simple_native"
    assert comparison.haeo_output_points == 2
