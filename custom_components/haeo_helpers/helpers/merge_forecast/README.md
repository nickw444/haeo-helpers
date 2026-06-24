# Merge Forecast

Merge Forecast creates a new Home Assistant sensor that combines multiple
forecast sensors into one ordered forecast.

The source sensors must expose a `forecast` attribute containing a list of
points with `time` and `value` fields. Sources are applied in the order they are
configured: earlier sources take precedence for overlapping forecast segments,
and later sources fill only gaps or longer-horizon periods.

## Use Case

This helper is useful when a near-term dynamic forecast should override a
longer baseline forecast. For example, Amber price forecasts can be used where
they exist, while a NEM seven-day tariff forecast fills the remaining horizon.

## Configuration

- `Forecast source sensors`: one or more sensor entities with a `forecast` list
  attribute, ordered from highest to lowest precedence.
- `Interpolation mode`: the interpolation mode to expose with the merged
  forecast. The default is `previous`, which is suitable for segment/tariff
  forecasts.

## Output Behavior

The helper sensor:

- Preserves the first source sensor's current state.
- Preserves metadata and non-forecast attributes from the first source sensor.
- Replaces the `forecast` attribute with the merged forecast.
- Sets the configured `interpolation_mode` attribute.
- Updates when any configured source entity changes.
