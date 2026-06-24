"""Sensor entity for merge forecast helper kind."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, NamedTuple

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_FORECAST,
    ATTR_INTERPOLATION_MODE,
    ATTR_MERGED_SOURCE_COUNT,
    ATTR_SOURCE_ENTITIES,
    CONF_INTERPOLATION_MODE,
    CONF_SOURCE_ENTITIES,
    DEFAULT_INTERPOLATION_MODE,
    INTERPOLATION_MODE_LINEAR,
    INTERPOLATION_MODE_NEAREST,
    INTERPOLATION_MODE_NEXT,
    INTERPOLATION_MODE_PREVIOUS,
    INTERPOLATION_MODES,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import State
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


class _ForecastPoint(NamedTuple):
    """Normalized forecast point used while merging."""

    time: datetime
    value: float


class _SourceForecast(NamedTuple):
    """Forecast points for one configured source entity."""

    entity_id: str
    points: list[_ForecastPoint]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up merge forecast helper sensor from a config entry."""
    async_add_entities([MergeForecastSensor(hass, entry)])


class MergeForecastSensor(SensorEntity):
    """Helper sensor that merges ordered source forecasts."""

    _attr_icon = "mdi:source-merge"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_merge_forecast"
        self._attr_name = entry.title

        self._source_entities = _normalize_source_entities(
            self._get_config(CONF_SOURCE_ENTITIES, []),
        )
        interpolation_mode = self._get_config(
            CONF_INTERPOLATION_MODE,
            DEFAULT_INTERPOLATION_MODE,
        )
        self._interpolation_mode = (
            interpolation_mode
            if interpolation_mode in INTERPOLATION_MODES
            else DEFAULT_INTERPOLATION_MODE
        )

        self._refresh_source_metadata()

    def _get_config(self, key: str, default: Any | None = None) -> Any:
        """Return a config value with options taking precedence."""
        if key in self._entry.options:
            return self._entry.options[key]
        return self._entry.data.get(key, default)

    def _tracked_entity_ids(self) -> list[str]:
        """Return entity IDs that should trigger recalculation."""
        return list(dict.fromkeys(self._source_entities))

    def _first_source_state(self) -> State | None:
        """Return the first configured source state."""
        if not self._source_entities:
            return None
        return self._hass.states.get(self._source_entities[0])

    def _refresh_source_metadata(self) -> None:
        """Refresh unit/device_class metadata from the first source sensor."""
        source_state = self._first_source_state()
        if source_state is None:
            return

        unit = source_state.attributes.get("unit_of_measurement")
        if isinstance(unit, str):
            self._attr_native_unit_of_measurement = unit

        device_class = source_state.attributes.get("device_class")
        if isinstance(device_class, str):
            self._attr_device_class = device_class

        state_class = source_state.attributes.get("state_class")
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
        """Handle source entity updates."""
        self._refresh_source_metadata()
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if the first source is usable and a forecast can be merged."""
        source_state = self._first_source_state()
        if source_state is None or source_state.state in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            return False

        merged_forecast, merged_source_count = self._build_merged_forecast()
        return bool(merged_forecast) and merged_source_count > 0

    @property
    def native_value(self) -> Any:  # type: ignore[override]
        """Return the first source entity's current state."""
        source_state = self._first_source_state()
        if source_state is None:
            return None

        return _resolve_native_value(source_state)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return first-source attributes with a merged forecast list."""
        source_state = self._first_source_state()
        attrs = dict(source_state.attributes) if source_state is not None else {}

        merged_forecast, merged_source_count = self._build_merged_forecast()
        attrs[ATTR_FORECAST] = merged_forecast
        attrs[ATTR_INTERPOLATION_MODE] = self._interpolation_mode
        attrs[ATTR_SOURCE_ENTITIES] = list(self._source_entities)
        attrs[ATTR_MERGED_SOURCE_COUNT] = merged_source_count
        return attrs

    def _build_merged_forecast(self) -> tuple[list[dict[str, Any]], int]:
        """Return forecast points merged by configured source precedence."""
        reference_now = dt_util.now()
        source_forecasts = self._source_forecasts(reference_now)
        if not source_forecasts:
            return [], 0

        boundaries = sorted(
            {point.time for source in source_forecasts for point in source.points}
        )
        if not boundaries:
            return [], 0

        merged: list[dict[str, Any]] = []
        if len(boundaries) == 1:
            point = _point_for_boundary(
                source_forecasts,
                boundaries[0],
                self._interpolation_mode,
            )
            return ([point] if point is not None else []), len(source_forecasts)

        for start, end in zip(boundaries, boundaries[1:], strict=False):
            point = _point_for_segment(
                source_forecasts,
                start,
                end,
                self._interpolation_mode,
            )
            if point is not None:
                merged.append(point)

        final_point = _point_for_boundary(
            source_forecasts,
            boundaries[-1],
            self._interpolation_mode,
        )
        if final_point is not None:
            merged.append(final_point)

        return merged, len(source_forecasts)

    def _source_forecasts(
        self,
        reference_now: datetime,
    ) -> list[_SourceForecast]:
        """Return valid source forecast points in configured precedence order."""
        source_forecasts: list[_SourceForecast] = []
        for source_entity in self._source_entities:
            source_state = self._hass.states.get(source_entity)
            if source_state is None:
                continue
            if source_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                continue

            source_forecast = source_state.attributes.get(ATTR_FORECAST)
            if not isinstance(source_forecast, list):
                continue

            source_points = _extract_valid_forecast_points(
                source_forecast,
                reference_now,
            )
            source_points = _trim_forecast_points(
                source_points,
                reference_now,
                self._interpolation_mode,
            )
            if source_points:
                source_forecasts.append(_SourceForecast(source_entity, source_points))

        return source_forecasts


def _point_for_segment(
    source_forecasts: list[_SourceForecast],
    start: datetime,
    end: datetime,
    interpolation_mode: str,
) -> dict[str, Any] | None:
    """Return a merged forecast point for one segment."""
    for source in source_forecasts:
        source_points = source.points
        if source_points[0].time <= start and end <= source_points[-1].time:
            value = _value_at_time(source_points, start, interpolation_mode)
            if value is not None:
                return {
                    "time": start.isoformat(),
                    "value": value,
                    "source": _format_source(source.entity_id),
                }

    return None


def _point_for_boundary(
    source_forecasts: list[_SourceForecast],
    point_time: datetime,
    interpolation_mode: str,
) -> dict[str, Any] | None:
    """Return a merged forecast point for a boundary timestamp."""
    for source in source_forecasts:
        source_points = source.points
        if source_points[0].time <= point_time <= source_points[-1].time:
            value = _value_at_time(source_points, point_time, interpolation_mode)
            if value is not None:
                return {
                    "time": point_time.isoformat(),
                    "value": value,
                    "source": _format_source(source.entity_id),
                }

    return None


def _value_at_time(
    source_points: list[_ForecastPoint],
    point_time: datetime,
    interpolation_mode: str,
) -> float | None:
    """Return the source forecast value at a boundary."""
    for point in source_points:
        if point.time == point_time:
            return point.value

    if point_time < source_points[0].time or point_time > source_points[-1].time:
        return None

    previous_point = source_points[0]
    for next_point in source_points[1:]:
        if previous_point.time < point_time < next_point.time:
            if interpolation_mode == INTERPOLATION_MODE_PREVIOUS:
                return previous_point.value

            if interpolation_mode == INTERPOLATION_MODE_NEXT:
                return next_point.value

            if interpolation_mode == INTERPOLATION_MODE_NEAREST:
                previous_diff = point_time - previous_point.time
                next_diff = next_point.time - point_time
                return (
                    previous_point.value
                    if previous_diff <= next_diff
                    else next_point.value
                )

            if interpolation_mode == INTERPOLATION_MODE_LINEAR:
                span_seconds = (next_point.time - previous_point.time).total_seconds()
                if span_seconds <= 0:
                    return previous_point.value

                weight = (point_time - previous_point.time).total_seconds() / span_seconds
                return previous_point.value + (
                    (next_point.value - previous_point.value) * weight
                )

        previous_point = next_point

    return None


def _extract_valid_forecast_points(
    source_forecast: list[Any],
    reference_now: datetime,
) -> list[_ForecastPoint]:
    """Return valid forecast points from a source forecast list."""
    points_by_time: dict[datetime, _ForecastPoint] = {}
    for point in source_forecast:
        if not isinstance(point, dict):
            continue

        point_time = _parse_point_time(point.get("time"), reference_now)
        value = _parse_numeric_value(point.get("value"))
        if point_time is None or value is None:
            continue

        points_by_time[point_time] = _ForecastPoint(point_time, value)

    return [
        points_by_time[point_time]
        for point_time in sorted(points_by_time)
    ]


def _trim_forecast_points(
    source_points: list[_ForecastPoint],
    reference_now: datetime,
    interpolation_mode: str,
) -> list[_ForecastPoint]:
    """Remove past forecast points while preserving the current segment value."""
    if not source_points:
        return []

    if source_points[-1].time < reference_now:
        return []

    if source_points[0].time >= reference_now:
        return source_points

    future_points = [
        point for point in source_points if point.time > reference_now
    ]
    current_value = _value_at_time(
        source_points,
        reference_now,
        interpolation_mode,
    )
    if current_value is None:
        return future_points

    return [_ForecastPoint(reference_now, current_value), *future_points]


def _normalize_source_entities(raw_source_entities: Any) -> list[str]:
    """Return configured source entity IDs in order."""
    if isinstance(raw_source_entities, str):
        return [raw_source_entities] if raw_source_entities else []

    if not isinstance(raw_source_entities, list):
        return []

    return [
        source_entity
        for source_entity in raw_source_entities
        if isinstance(source_entity, str) and source_entity
    ]


def _format_source(entity_id: str) -> str:
    """Return a compact source label for a forecast point."""
    return entity_id.removeprefix("sensor.")


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

    tz = reference_now.tzinfo or UTC
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)

    return parsed.astimezone(tz)


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


def _resolve_native_value(source_state: State) -> Any:
    """Return a native value from the current source state."""
    if source_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None

    parsed = _parse_numeric_value(source_state.state)
    if parsed is not None:
        return parsed

    return source_state.state
