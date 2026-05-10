# Recent Days Forecast

Recent Days Forecast creates a Home Assistant sensor with a HAEO-compatible
`forecast` attribute from a numeric source entity's recorder statistics.

The helper is inspired by HAFO's historical forecasters, but instead of
shifting an entire historical week forward, it builds a time-of-day profile
from the previous full days. Each future hour receives the weighted average
for the same hour of day across the configured history window.

## Configuration

- `Source sensor`: numeric sensor entity to forecast.
- `History days`: number of previous full days to use.
- `Forecast horizon`: number of future hours to generate.
- `Recent bias`: optional linear weighting toward newer days.

## Recent Bias

Recent bias is expressed as a percent. `0%` means all days are weighted
equally. `100%` means the newest historical day is weighted twice as strongly
as the oldest historical day, with days in between weighted linearly.

## Output Behavior

The helper sensor:

- Uses hourly recorder `mean` statistics.
- Generates hourly forecast points.
- Reports the forecast value closest to now as its current state.
- Exposes `source_entity`, `history_days`, `forecast_horizon_hours`,
  `recent_bias_pct`, `last_forecast_update`, and `forecast` attributes.
