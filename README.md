# HAEO Helpers

HAEO Helpers is a Home Assistant helper integration for creating derived sensor
entities that pair with [HAEO](https://github.com/hass-energy/haeo).

The integration focuses on helper workflows that previously lived inside
[Energy Assistant](https://github.com/nickw444/energy-assistant), making those
behaviors available as Home Assistant entities that HAEO and normal
automations can consume.

## Current Helpers

Helper | Use case
-- | --
Forecast Statistic | Reduce a source sensor's `forecast` attribute to one representative value using percentile or mean aggregation. This replicates the Energy Assistant median-style terminal planning behavior.
Forecast Risk Adjustment | Create a risk-adjusted forecast by applying a baseline bias and a ramped future-risk bias to each forecast point. This replicates the Energy Assistant `grid_price_bias_pct` and `grid_price_risk` behavior.

See the helper-specific README files for details:

- [Forecast Statistic](custom_components/haeo_helpers/helpers/forecast_statistic/README.md)
- [Forecast Risk Adjustment](custom_components/haeo_helpers/helpers/forecast_risk_adjustment/README.md)

## Project Layout

File | Purpose
-- | --
`custom_components/haeo_helpers/*` | Home Assistant integration source code.
`custom_components/haeo_helpers/helpers/*` | Helper-specific implementation, flow, sensor, constants, and documentation.
`tools/scenario_runner/*` | Native scenario fixture loader/importer, diagnostics builder, and HAEO runner wrappers.
`tools/run_scenario.py` | CLI to import energy-assistant captures and execute native scenarios.
`tests/*` | Pytest suite for sensor behavior, config flows, dispatch, and lifecycle.
`tests/data/scenarios/*` | Native scenario fixtures used for migration and behavior regression tests.
`docs/scenario_runner/diagnostics_schema.md` | HAEO diagnostics mapping reference used by scenario tooling.
`scripts/*` | Development and test command wrappers.
`config/configuration.yaml` | Development Home Assistant config.

## Development

1. Install runtime and test dependencies.
1. Run `scripts/test` for the pytest suite.
1. Run `scripts/lint` or `ruff check .` before opening a pull request.

## Scenario Runner Commands

- Import one EA fixture directory:
  - `python3 -m tools.run_scenario import-ea /path/to/ea/scenario /path/to/fixture/scenario.json --name my-scenario`
- Bulk import EA fixtures:
  - `python3 -m tools.run_scenario import-ea-batch /path/to/ea/fixtures /path/to/haeo-helpers/tests/data/scenarios/ea_nwhass --timezone Australia/Sydney`
- Run a single scenario and save HAEO outputs:
  - `python3 -m tools.run_scenario run tests/data/scenarios/ea_nwhass/<scenario>/scenario.json --outputs-file tmp/<scenario>/haeo_outputs.json`
- Run a scenario batch and persist outputs:
  - `python3 -m tools.run_scenario run-batch tests/data/scenarios/ea_nwhass --outputs-dir tmp/haeo_outputs`
- Run a scenario batch and write outputs alongside scenarios (with graphs):
  - `python3 -m tools.run_scenario run-batch tests/data/scenarios/ea_nwhass --diag-command ./.venv_scenarios/bin/diag --render-graphs`
- Compare imported EA outputs vs HAEO outputs:
  - `python3 -m tools.run_scenario compare tests/data/scenarios/ea_nwhass/<scenario>/scenario.json tmp/haeo_outputs/<scenario>/haeo_outputs.json`
