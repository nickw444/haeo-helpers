"""Sensor entity for forecast statistic helper kind."""

from __future__ import annotations

import math
from statistics import fmean
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    AGGREGATION_MEAN,
    ATTR_BASE_VALUE,
    ATTR_FORECAST,
    ATTR_SAMPLE_COUNT,
    CONF_ADJUSTMENT,
    CONF_AGGREGATION,
    CONF_PERCENTILE,
    CONF_SOURCE_ENTITY,
    DEFAULT_ADJUSTMENT,
    DEFAULT_AGGREGATION,
    DEFAULT_PERCENTILE,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up forecast statistic helper sensor from a config entry."""
    async_add_entities([ForecastStatisticSensor(hass, entry)])


class ForecastStatisticSensor(SensorEntity):
    """Helper sensor that aggregates values from a forecast attribute."""

    _attr_icon = "mdi:chart-bell-curve"
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_forecast_statistic"
        self._attr_name = entry.title

        self._source_entity = self._get_config(CONF_SOURCE_ENTITY)
        self._aggregation = self._get_config(CONF_AGGREGATION, DEFAULT_AGGREGATION)
        self._percentile = float(self._get_config(CONF_PERCENTILE, DEFAULT_PERCENTILE))
        self._adjustment = float(self._get_config(CONF_ADJUSTMENT, DEFAULT_ADJUSTMENT))

        self._last_base_value: float | None = None
        self._last_sample_count = 0

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
        """Handle source entity updates."""
        self._refresh_source_metadata()
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if the source entity is available."""
        source_state = self._hass.states.get(self._source_entity)
        if source_state is None:
            return False

        return source_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)

    @property
    def native_value(self) -> float | None:  # type: ignore[override]
        """Return the helper's current value."""
        values = self._extract_forecast_values()
        self._last_sample_count = len(values)

        if not values:
            self._last_base_value = None
            return None

        if self._aggregation == AGGREGATION_MEAN:
            base_value = fmean(values)
        else:
            base_value = _calculate_percentile(values, self._percentile)

        self._last_base_value = base_value
        return base_value + self._adjustment

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return helper metadata and calculation details."""
        return {
            CONF_SOURCE_ENTITY: self._source_entity,
            CONF_AGGREGATION: self._aggregation,
            CONF_PERCENTILE: self._percentile,
            CONF_ADJUSTMENT: self._adjustment,
            ATTR_SAMPLE_COUNT: self._last_sample_count,
            ATTR_BASE_VALUE: self._last_base_value,
        }

    def _extract_forecast_values(self) -> list[float]:
        """Return numeric values from the source forecast attribute."""
        source_state = self._hass.states.get(self._source_entity)
        if source_state is None:
            return []

        forecast = source_state.attributes.get(ATTR_FORECAST)
        if not isinstance(forecast, list):
            return []

        values: list[float] = []
        for point in forecast:
            if not isinstance(point, dict):
                continue

            value = point.get("value")
            if not isinstance(value, int | float) or isinstance(value, bool):
                continue

            numeric_value = float(value)
            if math.isfinite(numeric_value):
                values.append(numeric_value)

        return values


def _calculate_percentile(values: list[float], percentile: float) -> float:
    """Calculate percentile using linear interpolation between ranks."""
    sorted_values = sorted(values)

    if len(sorted_values) == 1:
        return sorted_values[0]

    percentile = max(0.0, min(100.0, percentile))
    rank = (percentile / 100.0) * (len(sorted_values) - 1)

    lower_index = math.floor(rank)
    upper_index = math.ceil(rank)

    if lower_index == upper_index:
        return sorted_values[lower_index]

    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    weight = rank - lower_index

    return lower_value + (upper_value - lower_value) * weight
