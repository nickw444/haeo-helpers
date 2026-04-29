# Forecast Statistic

Forecast Statistic creates a Home Assistant sensor that reduces a forecast
attribute down to one planning value.

The source sensor must expose a `forecast` attribute containing a list of
points. Each valid point is expected to include a numeric `value`; invalid
points are ignored for the calculation.

## Use Case Being Replicated

This helper replicates the Energy Assistant pattern used for "terminal SoC"
style planning values: take a forecast stream, calculate a representative
value from the forecast horizon, then optionally shift that value by a fixed
adjustment.

The original use case was effectively "median forecast behavior", where the
planner wanted a single stable value from a noisy forecast rather than using
the current sensor state or a single forecast point. This helper generalizes
that behavior by supporting any percentile, including:

- `50th percentile`: median behavior.
- Lower percentiles: more pessimistic/conservative when low values matter.
- Higher percentiles: more conservative when high values matter.
- `mean`: average across all valid forecast values.

## Practical Uses

- Build a median price, load, solar, or SoC forecast sensor for automations.
- Feed HAEO a single representative forecast value where the upstream entity
only exposes a forecast list.
- Smooth noisy Amber-style forecast attributes into one value.
- Apply a known absolute calibration offset after the statistic is calculated.
- Create conservative planning inputs by choosing a percentile other than the
median.

## Configuration

- `Forecast source sensor`: sensor entity with a `forecast` list attribute.
- `Statistic`: `Percentile` or `Mean`.
- `Percentile`: percentile from `0` to `100`; only used for percentile mode.
- `Absolute adjustment`: fixed value added after aggregation.

## Calculation

For percentile mode, valid forecast values are sorted and linearly
interpolated. Percentiles below `0` clamp to the minimum value, and percentiles
above `100` clamp to the maximum value.

For mean mode, the helper uses the arithmetic mean of all valid values.

The final sensor value is:

```text
statistic_value + adjustment
```

## Output Behavior

The helper sensor:

- Uses `None` when there are no valid forecast values.
- Updates when the source entity changes.
- Propagates source unit and device class where available.
- Exposes diagnostic attributes including the base value and valid sample
count.

