"""Sensor entity for extend forecast helper kind."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from functools import partial
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Final, NamedTuple

from homeassistant.components.recorder import get_instance as get_recorder_instance
from homeassistant.components.recorder.history import state_changes_during_period
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_FORECAST,
    CONF_FORECAST_HORIZON_HOURS,
    CONF_HISTORY_DAYS,
    CONF_SOURCE_ENTITY,
    DEFAULT_FORECAST_HORIZON_HOURS,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_INTERVAL_MINUTES,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


MIN_POINTS_FOR_INTERVAL: Final = 2


class _ForecastExtensionContext(NamedTuple):
    """Inputs used to extend a forecast with history-backed projections."""

    fill_value: float | None
    reference_now: datetime
    interval_minutes: int
    source_end: datetime
    history_entries: list[tuple[datetime, float]]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up extend forecast helper sensor from a config entry."""
    async_add_entities([ExtendForecastSensor(hass, entry)], update_before_add=True)


class ExtendForecastSensor(SensorEntity):
    """Helper sensor that extends a source forecast using history."""

    _attr_icon = "mdi:chart-timeline-variant"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_extend_forecast"
        self._attr_name = entry.title

        self._source_entity = self._get_config(CONF_SOURCE_ENTITY)
        self._forecast_horizon_hours = int(
            self._get_config(
                CONF_FORECAST_HORIZON_HOURS, DEFAULT_FORECAST_HORIZON_HOURS
            )
        )
        self._history_days = int(
            self._get_config(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS)
        )

        self._cached_available = False
        self._cached_native_value: Any | None = None
        self._cached_extra_state_attributes: dict[str, Any] = {}

        self._refresh_source_metadata()

    def _get_config(self, key: str, default: Any | None = None) -> Any:
        """Return a config value with options taking precedence."""
        if key in self._entry.options:
            return self._entry.options[key]
        return self._entry.data.get(key, default)

    def _refresh_source_metadata(self) -> None:
        """Refresh unit/device_class metadata from the source sensor."""
        source_state = self._hass.states.get(self._source_entity)
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
                [self._source_entity],
                self._handle_source_state_change,
            )
        )

    @callback
    def _handle_source_state_change(self, event: Event[EventStateChangedData]) -> None:  # noqa: ARG002
        """Handle source updates."""
        self.async_schedule_update_ha_state(force_refresh=True)

    async def async_update(self) -> None:
        """Refresh cached native value, attributes, and availability."""
        source_state = self._hass.states.get(self._source_entity)
        if source_state is None:
            self._cached_available = False
            self._cached_native_value = None
            self._cached_extra_state_attributes = {}
            return

        self._refresh_source_metadata()

        self._cached_native_value = _resolve_native_value(source_state)

        attrs = dict(source_state.attributes)
        source_forecast = attrs.get(ATTR_FORECAST)
        has_forecast = isinstance(source_forecast, list)
        self._cached_available = (
            source_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
            and has_forecast
        )

        if not has_forecast:
            self._cached_extra_state_attributes = attrs
            return

        reference_now = dt_util.now()
        valid_points = _extract_valid_forecast_points(source_forecast, reference_now)
        if valid_points:
            interval_minutes = _infer_interval_minutes(
                [point_time for point_time, _ in valid_points],
            )
            source_end = max(point_time for point_time, _ in valid_points) + timedelta(
                minutes=interval_minutes
            )
        else:
            interval_minutes = DEFAULT_INTERVAL_MINUTES
            source_end = reference_now

        target_end = reference_now + timedelta(hours=self._forecast_horizon_hours)
        history_entries: list[tuple[datetime, float]] = []
        if source_end < target_end:
            recorder = get_recorder_instance(self._hass)
            history_entries = await recorder.async_add_executor_job(
                partial(
                    _history_entries,
                    hass=self._hass,
                    entity_id=self._source_entity,
                    history_days=self._history_days,
                    reference_now=reference_now,
                )
            )

        attrs[ATTR_FORECAST] = self._extend_forecast(
            source_forecast,
            context=_ForecastExtensionContext(
                fill_value=_parse_numeric_value(source_state.state),
                reference_now=reference_now,
                interval_minutes=interval_minutes,
                source_end=source_end,
                history_entries=history_entries,
            ),
        )
        self._cached_extra_state_attributes = attrs

    @property
    def available(self) -> bool:
        """Return True if the source entity is available."""
        return self._cached_available

    @property
    def native_value(self) -> Any:  # type: ignore[override]
        """Return the source entity's current state."""
        return self._cached_native_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return source attributes with an extended forecast list."""
        return dict(self._cached_extra_state_attributes)

    def _extend_forecast(
        self,
        source_forecast: list[Any],
        *,
        context: _ForecastExtensionContext,
    ) -> list[Any]:
        """Return the source forecast with a projected tail appended."""
        extended_forecast: list[Any] = [
            dict(point) if isinstance(point, dict) else point
            for point in source_forecast
        ]

        target_end = context.reference_now + timedelta(
            hours=self._forecast_horizon_hours
        )
        if context.source_end >= target_end:
            return extended_forecast

        projection_profile = self._build_projection_profile(
            reference_now=context.reference_now,
            interval_minutes=context.interval_minutes,
            history_entries=context.history_entries,
        )

        current_time = max(context.source_end, context.reference_now)
        projected_value = context.fill_value
        while current_time < target_end:
            bucket_index = (
                (current_time.hour * 60) + current_time.minute
            ) // context.interval_minutes
            bucket_value = projection_profile[bucket_index]
            if bucket_value is None:
                bucket_value = projected_value
            if bucket_value is None:
                bucket_value = 0.0
            projected_value = bucket_value
            extended_forecast.append(
                {
                    "time": current_time.isoformat(),
                    "value": projected_value,
                }
            )
            current_time += timedelta(minutes=context.interval_minutes)

        return extended_forecast

    def _build_projection_profile(
        self,
        *,
        reference_now: datetime,
        interval_minutes: int,
        history_entries: list[tuple[datetime, float]],
    ) -> list[float | None]:
        """Build a daily average profile from source state history."""
        buckets_per_day = (24 * 60) // interval_minutes
        bucket_sums = [0.0] * buckets_per_day
        bucket_seconds = [0.0] * buckets_per_day

        if not history_entries:
            return [None] * buckets_per_day

        now = reference_now
        if now <= history_entries[-1][0]:
            now = history_entries[-1][0] + timedelta(minutes=interval_minutes)

        for idx, (start, value) in enumerate(history_entries):
            end = history_entries[idx + 1][0] if idx + 1 < len(history_entries) else now
            if end <= start:
                continue

            current = start
            while current < end:
                current_minute_of_day = (current.hour * 60) + current.minute
                interval_start_minute_of_day = (
                    current_minute_of_day // interval_minutes
                ) * interval_minutes
                interval_start_hour, interval_start_minute = divmod(
                    interval_start_minute_of_day, 60
                )
                interval_start = current.replace(
                    hour=interval_start_hour,
                    minute=interval_start_minute,
                    second=0,
                    microsecond=0,
                )
                interval_end = interval_start + timedelta(minutes=interval_minutes)
                overlap_end = min(end, interval_end)
                seconds = (overlap_end - current).total_seconds()
                bucket = (
                    (interval_start.hour * 60) + interval_start.minute
                ) // interval_minutes
                bucket_sums[bucket] += value * seconds
                bucket_seconds[bucket] += seconds
                current = overlap_end

        return [
            (bucket_sums[i] / bucket_seconds[i]) if bucket_seconds[i] > 0 else None
            for i in range(buckets_per_day)
        ]


def _resolve_native_value(source_state: State) -> Any:
    """Return a cached native value from the current source state."""
    if source_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None

    parsed = _parse_numeric_value(source_state.state)
    if parsed is not None:
        return parsed

    return source_state.state


def _history_entries(
    *,
    hass: HomeAssistant,
    entity_id: str,
    history_days: int,
    reference_now: datetime,
) -> list[tuple[datetime, float]]:
    """Return normalized numeric state history entries for an entity."""
    try:
        history = state_changes_during_period(
            hass,
            reference_now - timedelta(days=history_days),
            reference_now,
            entity_id=entity_id,
            no_attributes=True,
            include_start_time_state=True,
        )
    except (KeyError, RuntimeError):
        return []

    states = history.get(entity_id, [])
    entries: list[tuple[datetime, float]] = []
    for item in states:
        timestamp = item.last_updated or item.last_changed
        if timestamp is None:
            continue

        value = _parse_numeric_value(item.state)
        if value is None:
            continue

        entries.append((timestamp, value))

    if not entries:
        return []

    entries.sort(key=lambda item: item[0])
    tz = reference_now.tzinfo or UTC
    normalized: list[tuple[datetime, float]] = []
    for timestamp, value in entries:
        normalized_timestamp = (
            timestamp.replace(tzinfo=tz)
            if timestamp.tzinfo is None
            else timestamp.astimezone(tz)
        )
        normalized.append((normalized_timestamp, value))

    return normalized


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
        return DEFAULT_INTERVAL_MINUTES

    for prev, curr in pairwise(points):
        delta_minutes = int((curr - prev).total_seconds() / 60.0)
        if delta_minutes <= 0:
            continue
        if 1440 % delta_minutes == 0:
            return delta_minutes

    return DEFAULT_INTERVAL_MINUTES


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
        return parsed.replace(tzinfo=reference_now.tzinfo or UTC)

    return parsed.astimezone(reference_now.tzinfo or UTC)


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
