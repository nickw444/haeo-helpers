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
`tests/*` | Pytest suite for sensor behavior, config flows, dispatch, and lifecycle.
`scripts/*` | Development and test command wrappers.
`config/configuration.yaml` | Development Home Assistant config.

## Development

1. Install runtime and test dependencies.
1. Run `scripts/test` for the pytest suite.
1. Run `scripts/lint` or `ruff check .` before opening a pull request.
