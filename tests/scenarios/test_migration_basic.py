"""Scenario runner tests for native fixture flow."""

from __future__ import annotations

from pathlib import Path
import json

from tools.scenario_runner.energy_assistant_importer import import_energy_assistant_capture
from tools.scenario_runner.runner import CliHaeoRunner, run_haeo_scenario


def test_import_energy_assistant_capture_writes_native_fixture(tmp_path):
    source = Path("tests/data/energy_assistant_captures/simple_capture.json")
    destination = tmp_path / "scenario.json"

    output = import_energy_assistant_capture(
        source_path=source,
        destination_path=destination,
        scenario_name="imported_simple",
    )

    payload = json.loads(output.read_text())
    assert payload["schema_version"] == 1
    assert payload["metadata"]["name"] == "imported_simple"
    assert payload["source"]["kind"] == "energy_assistant"
    assert "config" in payload["haeo"]
    assert "environment" in payload["haeo"]
    assert isinstance(payload["haeo"]["inputs"], list)


def test_run_native_fixture_cli_mode_with_fake_runner(tmp_path):
    recorded: list[list[str]] = []

    class FakeCompletedProcess:
        """Minimal completed-process substitute."""

        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_runner(command: list[str]) -> FakeCompletedProcess:
        recorded.append(command)
        diagnostics_path = Path(command[-1])
        payload = json.loads(diagnostics_path.read_text())
        payload.setdefault("data", {})["outputs"] = {}
        diagnostics_path.write_text(json.dumps(payload, indent=2) + "\n")
        self_rows = "\n".join(
            [
                "  Time     Buy     Sell    Battery    Grid    Load    Solar    SoC    Profit",
                "------  ------  -------  ---------  ------  ------  -------  -----  --------",
                " 00:00  0.2500  0.1000        0.0     1.0     1.0      0.0    0.0    -$0.25",
            ]
        )
        fake_process.stdout = self_rows
        return fake_process

    fake_process = FakeCompletedProcess()

    fixture_path = Path("tests/data/scenarios/simple_native")
    result = run_haeo_scenario(
        fixture_path,
        runner="cli",
        cli_runner=CliHaeoRunner(
            command_runner=fake_runner,
            diag_command=("diag",),
        ),
    )

    assert recorded
    assert recorded[0][0] == "diag"
    assert result.return_code == 0
    assert "Time" in result.stdout
    rows = result.outputs.get("haeo_rows", [])
    assert isinstance(rows, list)
    assert rows
