# Forecast Risk Adjustment

Forecast Risk Adjustment creates a new forecast sensor by copying a source
sensor's forecast and applying configurable bias to each forecast point.

The source sensor must expose a `forecast` attribute containing points with a
`time` and numeric `value`. Valid points are adjusted; invalid forecast points
are passed through unchanged.

## Use Case Being Replicated

This helper replicates the Energy Assistant grid price risk model:

```yaml
grid_price_bias_pct: 25.0
grid_price_risk:
  bias_pct: 20.0
  ramp_start_after_minutes: 30
  ramp_duration_minutes: 90
  curve: linear
```

That behavior was used to make future forecast prices more conservative. A
known baseline correction was applied across the whole forecast horizon, while
an additional risk margin ramped in as forecast points got further away from
now.

This is useful because near-term prices are usually more reliable than prices
several hours away. The helper lets HAEO consume a risk-adjusted forecast
without changing the upstream forecast entity.

## Practical Uses

- Add a baseline correction to Amber-style price forecasts.
- Increase conservatism as forecast points move further into the future.
- Model uncertainty in electricity price, load, solar, or any numeric forecast.
- Drive the bias values from `input_number` or `number` entities so dashboards
and automations can change risk posture at runtime.
- Produce a planning forecast for HAEO while preserving the original source
forecast for visibility and comparison.

## Configuration

- `Forecast source sensor`: sensor entity with a `forecast` list attribute.
- `Basis bias`: constant percent or numeric entity; applies to the whole
forecast horizon.
- `Risk bias`: constant percent or numeric entity; ramps in over time.
- `Ramp start after`: minutes from now before risk bias starts applying.
- `Ramp duration`: minutes over which risk bias ramps from `0%` to full effect.
- `Curve`: currently `linear`.

## Calculation

For each valid forecast point:

```text
risk_factor = 0 before ramp start
risk_factor = 0..1 during ramp duration
risk_factor = 1 after ramp end
total_bias_pct = basis_bias_pct + (risk_bias_pct * risk_factor)
adjusted_value = value * (1 + total_bias_pct / 100)
```

Past points do not receive ramped risk effect. A zero-minute ramp duration acts
as a step: no risk effect before the start offset, full risk effect at and
after the start offset.

## Output Behavior

The helper sensor:

- Replaces the source `forecast` attribute with adjusted forecast values.
- Preserves non-forecast attributes from the source sensor.
- Uses the adjusted point closest to now as the native sensor value.
- Updates when the source or configured bias entities change.
- Becomes unavailable when a required bias entity is missing or non-numeric.
- Exposes diagnostic attributes with applied bias values and ramp settings.

