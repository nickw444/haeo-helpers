"""Sensor entity for recent days forecast helper kind."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any, Final, NamedTuple

from homeassistant.components.recorder import get_instance as get_recorder_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_FORECAST,
    ATTR_FORECAST_HORIZON_HOURS,
    ATTR_HISTORY_DAYS,
    ATTR_LAST_FORECAST_UPDATE,
    ATTR_RECENT_BIAS_PCT,
    ATTR_SOURCE_ENTITY,
    CONF_FORECAST_HORIZON_HOURS,
    CONF_HISTORY_DAYS,
    CONF_RECENT_BIAS_PCT,
    CONF_SOURCE_ENTITY,
    DEFAULT_FORECAST_HORIZON_HOURS,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_RECENT_BIAS_PCT,
    INTERVAL_MINUTES,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


StatisticsLike = Mapping[str, Any]
STATISTIC_MEAN: Final = "mean"
STATISTIC_START: Final = "start"


class _ForecastBuildContext(NamedTuple):
    """Inputs used to build a recent-days forecast."""

    reference_now: datetime
    history_days: int
    forecast_horizon_hours: int
    recent_bias_pct: float
    statistics: list[StatisticsLike]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up recent days forecast helper sensor from a config entry."""
    async_add_entities([RecentDaysForecastSensor(hass, entry)], update_before_add=True)


class RecentDaysForecastSensor(SensorEntity):
    """Helper sensor that forecasts from recent full-day history."""

    _attr_icon = "mdi:calendar-clock"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_recent_days_forecast"
        self._attr_name = entry.title

        self._source_entity = self._get_config(CONF_SOURCE_ENTITY)
        self._history_days = int(
            self._get_config(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS)
        )
        self._forecast_horizon_hours = int(
            self._get_config(
                CONF_FORECAST_HORIZON_HOURS,
                DEFAULT_FORECAST_HORIZON_HOURS,
            )
        )
        self._recent_bias_pct = float(
            self._get_config(CONF_RECENT_BIAS_PCT, DEFAULT_RECENT_BIAS_PCT)
        )

        self._cached_available = False
        self._cached_native_value: float | None = None
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
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._handle_scheduled_refresh,
                timedelta(minutes=INTERVAL_MINUTES),
            )
        )

    @callback
    def _handle_source_state_change(self, event: Event[EventStateChangedData]) -> None:  # noqa: ARG002
        """Handle source updates."""
        self._refresh_source_metadata()
        self.async_write_ha_state()

    @callback
    def _handle_scheduled_refresh(self, now: datetime) -> None:  # noqa: ARG002
        """Refresh the forecast on the configured interval."""
        self.async_schedule_update_ha_state(force_refresh=True)

    async def async_update(self) -> None:
        """Refresh cached native value, attributes, and availability."""
        source_state = self._hass.states.get(self._source_entity)
        if source_state is None or source_state.state in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            self._cached_available = False
            self._cached_native_value = None
            self._cached_extra_state_attributes = {}
            return

        self._refresh_source_metadata()

        reference_now = dt_util.now()
        recorder = get_recorder_instance(self._hass)
        statistics = await recorder.async_add_executor_job(
            partial(
                _statistics_for_sensor,
                hass=self._hass,
                entity_id=self._source_entity,
                history_days=self._history_days,
                reference_now=reference_now,
            )
        )
        forecast = _build_forecast(
            _ForecastBuildContext(
                reference_now=reference_now,
                history_days=self._history_days,
                forecast_horizon_hours=self._forecast_horizon_hours,
                recent_bias_pct=self._recent_bias_pct,
                statistics=statistics,
            )
        )

        self._cached_available = bool(forecast)
        self._cached_native_value = _closest_forecast_value(forecast, reference_now)
        self._cached_extra_state_attributes = {
            ATTR_SOURCE_ENTITY: self._source_entity,
            ATTR_HISTORY_DAYS: self._history_days,
            ATTR_FORECAST_HORIZON_HOURS: self._forecast_horizon_hours,
            ATTR_RECENT_BIAS_PCT: self._recent_bias_pct,
            ATTR_LAST_FORECAST_UPDATE: reference_now.isoformat(),
            ATTR_FORECAST: [
                {"time": point_time.isoformat(), "value": value}
                for point_time, value in forecast
            ],
        }

    @property
    def available(self) -> bool:
        """Return True if a forecast is available."""
        return self._cached_available

    @property
    def native_value(self) -> float | None:  # type: ignore[override]
        """Return the forecast value closest to now."""
        return self._cached_native_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return forecast metadata and forecast list."""
        return dict(self._cached_extra_state_attributes)


def _statistics_for_sensor(
    *,
    hass: HomeAssistant,
    entity_id: str,
    history_days: int,
    reference_now: datetime,
) -> list[StatisticsLike]:
    """Return hourly mean statistics from the previous full local days."""
    local_now = reference_now
    end_time = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(days=history_days)

    try:
        statistics = statistics_during_period(
            hass,
            start_time,
            end_time,
            {entity_id},
            "hour",
            None,
            {STATISTIC_MEAN},
        )
    except (KeyError, RuntimeError):
        return []

    return list(statistics.get(entity_id, []))


def _build_forecast(context: _ForecastBuildContext) -> list[tuple[datetime, float]]:
    """Build a forecast from weighted time-of-day averages."""
    profile = _weighted_time_of_day_profile(
        statistics=context.statistics,
        reference_now=context.reference_now,
        history_days=context.history_days,
        recent_bias_pct=context.recent_bias_pct,
    )
    if not profile:
        return []

    start_time = context.reference_now.replace(minute=0, second=0, microsecond=0)
    forecast: list[tuple[datetime, float]] = []
    for offset in range(context.forecast_horizon_hours):
        point_time = start_time + timedelta(hours=offset)
        bucket = point_time.hour
        value = profile.get(bucket)
        if value is None:
            continue
        forecast.append((point_time, value))

    return forecast


def _weighted_time_of_day_profile(
    *,
    statistics: list[StatisticsLike],
    reference_now: datetime,
    history_days: int,
    recent_bias_pct: float,
) -> dict[int, float]:
    """Return weighted hourly average values keyed by hour of day."""
    sums: dict[int, float] = {}
    weights: dict[int, float] = {}
    end_day = reference_now.replace(hour=0, minute=0, second=0, microsecond=0)

    for stat in statistics:
        timestamp = _parse_stat_time(stat.get(STATISTIC_START), reference_now)
        value = _parse_numeric_value(stat.get(STATISTIC_MEAN))
        if timestamp is None or value is None:
            continue

        age_days = (end_day.date() - timestamp.date()).days - 1
        if age_days < 0 or age_days >= history_days:
            continue

        weight = _day_weight(
            age_days=age_days,
            history_days=history_days,
            recent_bias_pct=recent_bias_pct,
        )
        bucket = timestamp.hour
        sums[bucket] = sums.get(bucket, 0.0) + (value * weight)
        weights[bucket] = weights.get(bucket, 0.0) + weight

    return {
        bucket: sums[bucket] / weights[bucket]
        for bucket in sums
        if weights.get(bucket, 0.0) > 0
    }


def _day_weight(
    *,
    age_days: int,
    history_days: int,
    recent_bias_pct: float,
) -> float:
    """Return a linear recency weight for a historical day."""
    if history_days <= 1 or recent_bias_pct <= 0:
        return 1.0

    oldest_age = history_days - 1
    recency = (oldest_age - age_days) / oldest_age
    return 1.0 + (recency * (recent_bias_pct / 100.0))


def _closest_forecast_value(
    forecast: list[tuple[datetime, float]],
    reference_now: datetime,
) -> float | None:
    """Return the forecast value closest to reference_now."""
    closest_value: float | None = None
    closest_diff: float | None = None
    for point_time, value in forecast:
        diff = abs((point_time - reference_now).total_seconds())
        if closest_diff is None or diff < closest_diff:
            closest_diff = diff
            closest_value = value
    return closest_value


def _parse_stat_time(raw_time: Any, reference_now: datetime) -> datetime | None:
    """Parse a statistics timestamp."""
    parsed: datetime | None
    if isinstance(raw_time, datetime):
        parsed = raw_time
    else:
        try:
            parsed = datetime.fromtimestamp(
                float(raw_time),
                tz=reference_now.tzinfo or UTC,
            )
        except (TypeError, ValueError):
            return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=reference_now.tzinfo or UTC)

    return parsed.astimezone(reference_now.tzinfo or UTC)


def _parse_numeric_value(raw_value: Any) -> float | None:
    """Parse a numeric value."""
    if isinstance(raw_value, bool):
        return None

    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    return value
