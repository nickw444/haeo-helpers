"""Sensor entity for realtime forecast smoothing helper kind."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Final, NamedTuple

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_APPLIED_REALTIME_VALUE,
    ATTR_FORECAST,
    ATTR_SMOOTHING_WINDOW_MINUTES,
    CONF_FORECAST_ENTITY,
    CONF_REALTIME_ENTITY,
    CONF_SMOOTHING_WINDOW_MINUTES,
    DEFAULT_SMOOTHING_WINDOW_MINUTES,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


MIN_POINTS_FOR_INTERVAL: Final = 2


class _SmoothingContext(NamedTuple):
    """Inputs used to smooth one forecast point."""

    realtime_value: float
    now: datetime
    window_end: datetime
    interval_duration: timedelta


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up realtime forecast smoothing helper sensor from a config entry."""
    async_add_entities([RealtimeForecastSmoothingSensor(hass, entry)])


class RealtimeForecastSmoothingSensor(SensorEntity):
    """Helper sensor that smooths a realtime value into a forecast."""

    _attr_icon = "mdi:chart-bell-curve"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_realtime_forecast_smoothing"
        self._attr_name = entry.title

        self._forecast_entity = self._get_config(CONF_FORECAST_ENTITY)
        self._realtime_entity = self._get_config(CONF_REALTIME_ENTITY)
        self._smoothing_window_minutes = float(
            self._get_config(
                CONF_SMOOTHING_WINDOW_MINUTES,
                DEFAULT_SMOOTHING_WINDOW_MINUTES,
            )
        )

        self._refresh_forecast_metadata()

    def _get_config(self, key: str, default: Any | None = None) -> Any:
        """Return a config value with options taking precedence."""
        if key in self._entry.options:
            return self._entry.options[key]
        return self._entry.data.get(key, default)

    def _tracked_entity_ids(self) -> list[str]:
        """Return entity IDs that should trigger recalculation."""
        return list(dict.fromkeys([self._forecast_entity, self._realtime_entity]))

    def _refresh_forecast_metadata(self) -> None:
        """Refresh unit/device_class metadata from the forecast source sensor."""
        forecast_state = self._hass.states.get(self._forecast_entity)
        if forecast_state is None:
            return

        unit = forecast_state.attributes.get("unit_of_measurement")
        if isinstance(unit, str):
            self._attr_native_unit_of_measurement = unit

        device_class = forecast_state.attributes.get("device_class")
        if isinstance(device_class, str):
            self._attr_device_class = device_class

        state_class = forecast_state.attributes.get("state_class")
        if isinstance(state_class, str):
            self._attr_state_class = state_class

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added to Home Assistant."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._tracked_entity_ids(),
                self._handle_state_change,
            )
        )

    @callback
    def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:  # noqa: ARG002
        """Handle forecast/realtime source updates."""
        self._refresh_forecast_metadata()
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if both source entities are available."""
        forecast_state = self._hass.states.get(self._forecast_entity)
        realtime_state = self._hass.states.get(self._realtime_entity)
        if forecast_state is None or realtime_state is None:
            return False

        if forecast_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return False
        if realtime_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return False

        if not isinstance(forecast_state.attributes.get(ATTR_FORECAST), list):
            return False

        return _parse_numeric_value(realtime_state.state) is not None

    @property
    def native_value(self) -> Any:  # type: ignore[override]
        """Return the realtime source entity's current state."""
        realtime_state = self._hass.states.get(self._realtime_entity)
        if realtime_state is None or realtime_state.state in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            return None

        parsed = _parse_numeric_value(realtime_state.state)
        if parsed is not None:
            return parsed

        return realtime_state.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return forecast attributes with a realtime-smoothed forecast list."""
        forecast_state = self._hass.states.get(self._forecast_entity)
        if forecast_state is None:
            return {}

        attrs = dict(forecast_state.attributes)
        smoothed_forecast, _ = self._build_smoothed_forecast()
        if smoothed_forecast is None:
            return attrs

        realtime_value = self._resolved_realtime_value()
        attrs[ATTR_FORECAST] = smoothed_forecast
        attrs[ATTR_APPLIED_REALTIME_VALUE] = realtime_value
        attrs[ATTR_SMOOTHING_WINDOW_MINUTES] = self._smoothing_window_minutes
        return attrs

    def _resolved_realtime_value(self) -> float | None:
        """Return the current realtime value."""
        realtime_state = self._hass.states.get(self._realtime_entity)
        if realtime_state is None:
            return None
        if realtime_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        return _parse_numeric_value(realtime_state.state)

    def _build_smoothed_forecast(
        self,
    ) -> tuple[list[dict[str, Any]] | None, float | None]:
        """Return realtime-smoothed forecast and the point closest to now."""
        forecast_state = self._hass.states.get(self._forecast_entity)
        realtime_value = self._resolved_realtime_value()
        if forecast_state is None or realtime_value is None:
            return None, None

        source_forecast = forecast_state.attributes.get(ATTR_FORECAST)
        if not isinstance(source_forecast, list):
            return None, None

        now = dt_util.now()
        valid_point_times = [
            point_time
            for point_time, _ in _extract_valid_forecast_points(source_forecast, now)
        ]
        interval_minutes = _infer_interval_minutes(valid_point_times)
        interval_duration = timedelta(minutes=interval_minutes)
        window = timedelta(minutes=self._smoothing_window_minutes)
        window_end = now + window
        context = _SmoothingContext(
            realtime_value=realtime_value,
            now=now,
            window_end=window_end,
            interval_duration=interval_duration,
        )

        smoothed_forecast: list[Any] = []
        closest_value: float | None = None
        closest_diff: float | None = None

        for point in source_forecast:
            if not isinstance(point, dict):
                smoothed_forecast.append(point)
                continue

            smoothed_point = dict(point)
            value = _parse_numeric_value(point.get("value"))
            point_time = _parse_point_time(point.get("time"), now)
            if value is None or point_time is None:
                smoothed_forecast.append(smoothed_point)
                continue

            smoothed_value = self._smooth_value(
                forecast_value=value,
                point_time=point_time,
                context=context,
            )
            smoothed_point["value"] = smoothed_value
            smoothed_forecast.append(smoothed_point)

            time_diff_seconds = abs((point_time - now).total_seconds())
            if closest_diff is None or time_diff_seconds < closest_diff:
                closest_diff = time_diff_seconds
                closest_value = smoothed_value

        return smoothed_forecast, closest_value

    def _smooth_value(
        self,
        *,
        forecast_value: float,
        point_time: datetime,
        context: _SmoothingContext,
    ) -> float:
        """Raise forecast value toward realtime, fading back over the window."""
        if point_time + context.interval_duration <= context.now:
            return forecast_value

        if point_time >= context.window_end:
            return forecast_value

        progress = (point_time - context.now).total_seconds() / max(
            1.0,
            (context.window_end - context.now).total_seconds(),
        )
        progress = max(0.0, min(1.0, progress))
        smoothed_value = context.realtime_value + (
            (forecast_value - context.realtime_value) * progress
        )
        return max(forecast_value, smoothed_value)


def _extract_valid_forecast_points(
    source_forecast: list[Any],
    reference_now: datetime,
) -> list[tuple[datetime, float]]:
    """Return valid forecast points from a source forecast list."""
    valid_points: list[tuple[datetime, float]] = []
    for point in source_forecast:
        if not isinstance(point, dict):
            continue

        point_time = _parse_point_time(point.get("time"), reference_now)
        value = _parse_numeric_value(point.get("value"))
        if point_time is None or value is None:
            continue

        valid_points.append((point_time, value))

    valid_points.sort(key=lambda item: item[0])
    return valid_points


def _infer_interval_minutes(points: list[datetime]) -> int:
    """Infer an interval in minutes from forecast point timestamps."""
    if len(points) < MIN_POINTS_FOR_INTERVAL:
        return 30

    for prev, curr in pairwise(points):
        delta_minutes = int((curr - prev).total_seconds() / 60.0)
        if delta_minutes <= 0:
            continue
        if 1440 % delta_minutes == 0:
            return delta_minutes

    return 30


def _parse_point_time(raw_time: Any, reference_now: datetime) -> datetime | None:
    """Parse a forecast point time in ISO or datetime form."""
    parsed: datetime | None

    if isinstance(raw_time, datetime):
        parsed = raw_time
    elif isinstance(raw_time, str):
        parsed = dt_util.parse_datetime(raw_time)
    else:
        return None

    if parsed is None:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=reference_now.tzinfo)

    return parsed.astimezone(reference_now.tzinfo)


def _parse_numeric_value(raw_value: Any) -> float | None:
    """Parse a numeric value from a state or forecast point."""
    if isinstance(raw_value, bool):
        return None

    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    return value
