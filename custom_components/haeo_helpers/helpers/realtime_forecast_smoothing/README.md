# Realtime Forecast Smoothing

Realtime Forecast Smoothing creates a Home Assistant sensor that reports a
realtime source entity's current state while preserving a forecast source
entity's non-forecast attributes, then raises near-term forecast points toward
the realtime value before linearly tapering back to the original forecast.

This is useful when a short-lived local condition is visible in realtime but
is not represented in the forecast yet. For example, a load forecast might
expect 1 kW while the realtime load is 4 kW because an appliance is currently
running. The helper can carry that spike into the near-term forecast for a
configured smoothing window, then fade back to the upstream forecast.

## Configuration

- `Forecast source sensor`: sensor entity with a `forecast` list attribute.
- `Realtime source sensor`: sensor entity with a numeric current state.
- `Smoothing window`: how long the realtime value should influence future
  forecast points.

## Output Behavior

The helper sensor:

- Reports the realtime source sensor's current state.
- Preserves non-forecast attributes from the forecast source sensor.
- Replaces the source `forecast` attribute with a smoothed list.
- Updates when either the forecast source or realtime source changes.
- Only raises forecast values toward realtime values; it does not reduce a
  forecast when realtime is below the forecast.
