"""Public APIs for scenario testing utilities."""

from tools.scenario_runner.comparison import compare_scenario_outputs
from tools.scenario_runner.energy_assistant_importer import import_energy_assistant_capture
from tools.scenario_runner.fixtures import load_native_fixture
from tools.scenario_runner.models import HaeoScenarioResult, NativeScenarioFixture, ScenarioComparison
from tools.scenario_runner.runner import CliHaeoRunner, run_haeo_scenario

__all__ = [
    "CliHaeoRunner",
    "HaeoScenarioResult",
    "NativeScenarioFixture",
    "ScenarioComparison",
    "compare_scenario_outputs",
    "import_energy_assistant_capture",
    "load_native_fixture",
    "run_haeo_scenario",
]
