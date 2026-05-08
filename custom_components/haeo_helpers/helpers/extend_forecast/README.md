# Extend Forecast

Extend Forecast creates a new Home Assistant sensor that keeps a source
forecast entity's current state and non-forecast attributes, then extends the
`forecast` attribute to a configured horizon using historical source-state
patterns.

The source sensor must expose a `forecast` attribute containing a list of
points. The helper copies those points unchanged, then appends projected
points derived from the source entity's recorded state history until the
configured horizon is covered.

## Use Case

This helper is the HAEO Helpers version of the forecast-expansion behavior
used in Energy Assistant: a short forecast is kept intact, and missing future
coverage is filled from history-backed projections so planners can work with a
longer horizon.

## Practical Uses

- Extend a short price forecast to a planning horizon.
- Keep the upstream forecast entity untouched while exposing a longer derived
  forecast for automations.
- Build a forecast sensor that can survive short upstream horizons by leaning
  on historical state patterns.

## Configuration

- `Forecast source sensor`: sensor entity with a `forecast` list attribute.
- `Forecast horizon (hours)`: total horizon to cover.
- `History lookback (days)`: how much state history to use for the projection.

## Output Behavior

The helper sensor:

- Preserves the source sensor's current state.
- Preserves non-forecast attributes from the source sensor.
- Replaces the source `forecast` attribute with an extended list.
- Updates when the source entity changes.
