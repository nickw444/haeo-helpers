"""Edge-case checks for bulk-imported energy-assistant scenarios."""

from __future__ import annotations

from pathlib import Path
import json

from tools.scenario_runner.diagnostics_builder import build_diagnostics_payload
from tools.scenario_runner.fixtures import load_native_fixture


def test_bulk_imported_ea_scenarios_are_loadable():
    root = Path("tests/data/scenarios/ea_nwhass")
    scenario_files = sorted(root.glob("*/scenario.json"))
    assert scenario_files, "Expected at least one imported scenario fixture."

    for scenario_file in scenario_files:
        payload = json.loads(scenario_file.read_text())
        assert payload["schema_version"] == 1
        assert payload["source"]["kind"] == "energy_assistant"
        fixture = load_native_fixture(scenario_file)
        diagnostics = build_diagnostics_payload(fixture)
        assert "config" in diagnostics
        assert "environment" in diagnostics
        assert isinstance(diagnostics["inputs"], list)
        assert diagnostics["inputs"], f"Expected non-empty inputs for {scenario_file}"


def test_bulk_imported_ea_scenarios_use_helper_transforms():
    """EA scenarios should exercise helper transforms before HAEO consumes inputs."""
    scenario_file = Path(
        "tests/data/scenarios/ea_nwhass/20260118-202748-grid-import-ev-charge/scenario.json"
    )
    payload = json.loads(scenario_file.read_text())
    config = payload["haeo"]["config"]
    inputs = {
        item["entity_id"]: item
        for item in payload["haeo"]["inputs"]
    }

    assert config["participants"]["Grid"]["pricing"]["price_source_target"] == {
        "type": "entity",
        "value": ["sensor.ea_grid_price_import_risk_adjusted"],
    }
    assert config["participants"]["Grid"]["pricing"]["price_target_source"] == {
        "type": "entity",
        "value": ["sensor.ea_grid_price_export_risk_adjusted"],
    }
    assert config["participants"]["Battery Primary"]["pricing"]["salvage_value"] == {
        "type": "entity",
        "value": ["sensor.ea_battery_primary_stored_energy_value"],
    }
    assert (
        inputs["sensor.ea_grid_price_import_risk_adjusted"]["attributes"]["haeo_helpers_transform"]
        == "forecast_risk_adjustment"
    )
    assert (
        inputs["sensor.ea_battery_primary_stored_energy_value"]["attributes"]["haeo_helpers_transform"]
        == "forecast_statistic"
    )
