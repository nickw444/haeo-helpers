"""Scenario runners that execute HAEO diagnostics plans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from typing import Protocol
import json
import subprocess

from tools.scenario_runner.diagnostics_builder import (
    build_diagnostics_payload,
    write_unified_diagnostics,
)
from tools.scenario_runner.fixtures import load_native_fixture
from tools.scenario_runner.haeo_native import run_native_haeo
from tools.scenario_runner.models import HaeoScenarioResult


class CommandRunner(Protocol):
    """Protocol for command execution to simplify testing."""

    def __call__(self, command: list[str]) -> CompletedProcess[str]:
        """Run a command and return completed process metadata."""


def _default_subprocess_runner(command: list[str]) -> CompletedProcess[str]:
    """Default subprocess command runner implementation."""
    return subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603


@dataclass(slots=True)
class CliHaeoRunner:
    """Run HAEO via its external `diag` command."""

    command_runner: CommandRunner = _default_subprocess_runner
    diag_command: tuple[str, ...] = ("diag",)

    def run(self, fixture_path: Path) -> HaeoScenarioResult:
        """Execute HAEO for a native fixture path using CLI mode."""
        fixture = load_native_fixture(fixture_path)
        payload = build_diagnostics_payload(fixture)

        with TemporaryDirectory(prefix="haeo_scenario_") as temp_dir:
            diagnostics_path = Path(temp_dir) / "diagnostics.json"
            write_unified_diagnostics(diagnostics_path, payload)
            command = [*self.diag_command, "--file", str(diagnostics_path)]
            completed = self.command_runner(command)
            final_payload = json.loads(diagnostics_path.read_text()).get("data", {})
            outputs = _extract_outputs_from_diag_stdout(completed.stdout)
            if not outputs:
                raw_outputs = final_payload.get("outputs", {})
                outputs = raw_outputs if isinstance(raw_outputs, dict) else {}
            return HaeoScenarioResult(
                diagnostics_path=diagnostics_path,
                return_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                outputs=outputs if isinstance(outputs, dict) else {},
            )


def run_haeo_scenario(
    fixture_path: Path,
    *,
    runner: str = "native",
    diag_command: tuple[str, ...] = ("diag",),
    cli_runner: CliHaeoRunner | None = None,
) -> HaeoScenarioResult:
    """Run a native scenario using the selected execution strategy."""
    if runner == "native":
        fixture = load_native_fixture(fixture_path)
        outputs, _network = run_native_haeo(fixture)
        return HaeoScenarioResult(
            diagnostics_path=fixture.path,
            return_code=0,
            stdout="",
            stderr="",
            outputs=outputs,
        )
    if runner != "cli":
        msg = f"Unsupported runner '{runner}'. Supported: 'native', 'cli'."
        raise ValueError(msg)
    resolved_runner = cli_runner or CliHaeoRunner(diag_command=diag_command)
    return resolved_runner.run(fixture_path)


def _extract_outputs_from_diag_stdout(stdout: str) -> dict[str, object]:
    """Parse tabular diag stdout into structured row outputs."""
    row_pattern = re.compile(
        r"^\s*(\d{2}:\d{2})\s+"
        r"(-?\d+\.\d+)\s+"
        r"(-?\d+\.\d+)\s+"
        r"(-?\d+\.\d+)\s+"
        r"(-?\d+\.\d+)\s+"
        r"(-?\d+\.\d+)\s+"
        r"(-?\d+\.\d+)\s+"
        r"(-?\d+\.\d+)\s+"
        r"(-?\$?\d+\.\d+)\s*$"
    )
    rows: list[dict[str, object]] = []
    for line in stdout.splitlines():
        match = row_pattern.match(line)
        if not match:
            continue
        profit_str = match.group(9).replace("$", "")
        rows.append(
            {
                "time": match.group(1),
                "buy": float(match.group(2)),
                "sell": float(match.group(3)),
                "battery": float(match.group(4)),
                "grid": float(match.group(5)),
                "load": float(match.group(6)),
                "solar": float(match.group(7)),
                "soc": float(match.group(8)),
                "profit": float(profit_str),
            }
        )
    if not rows:
        return {}
    return {"haeo_rows": rows}
