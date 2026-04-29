"""Sensor entity for forecast risk adjustment helper kind."""

from __future__ import annotations

import math
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_APPLIED_BASIS_BIAS_PCT,
    ATTR_APPLIED_RISK_BIAS_PCT,
    ATTR_CURVE,
    ATTR_FORECAST,
    ATTR_RAMP_DURATION_MINUTES,
    ATTR_RAMP_START_AFTER_MINUTES,
    BIAS_SOURCE_CONSTANT,
    BIAS_SOURCE_ENTITY,
    CONF_BASIS_BIAS_ENTITY,
    CONF_BASIS_BIAS_PCT,
    CONF_BASIS_BIAS_SOURCE,
    CONF_CURVE,
    CONF_RAMP_DURATION_MINUTES,
    CONF_RAMP_START_AFTER_MINUTES,
    CONF_RISK_BIAS_ENTITY,
    CONF_RISK_BIAS_PCT,
    CONF_RISK_BIAS_SOURCE,
    CONF_SOURCE_ENTITY,
    CURVE_LINEAR,
    DEFAULT_BASIS_BIAS_PCT,
    DEFAULT_BASIS_BIAS_SOURCE,
    DEFAULT_CURVE,
    DEFAULT_RAMP_DURATION_MINUTES,
    DEFAULT_RAMP_START_AFTER_MINUTES,
    DEFAULT_RISK_BIAS_PCT,
    DEFAULT_RISK_BIAS_SOURCE,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up forecast risk adjustment helper sensor from a config entry."""
    async_add_entities([ForecastRiskAdjustmentSensor(hass, entry)])


class ForecastRiskAdjustmentSensor(SensorEntity):
    """Helper sensor that applies risk-adjusted bias to forecast values."""

    _attr_icon = "mdi:chart-line-variant"
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_forecast_risk_adjustment"
        self._attr_name = entry.title

        self._source_entity = self._get_config(CONF_SOURCE_ENTITY)

        self._basis_bias_source = self._get_config(
            CONF_BASIS_BIAS_SOURCE,
            DEFAULT_BASIS_BIAS_SOURCE,
        )
        self._basis_bias_pct = float(
            self._get_config(CONF_BASIS_BIAS_PCT, DEFAULT_BASIS_BIAS_PCT)
        )
        self._basis_bias_entity = self._get_config(CONF_BASIS_BIAS_ENTITY)

        self._risk_bias_source = self._get_config(
            CONF_RISK_BIAS_SOURCE,
            DEFAULT_RISK_BIAS_SOURCE,
        )
        self._risk_bias_pct = float(
            self._get_config(CONF_RISK_BIAS_PCT, DEFAULT_RISK_BIAS_PCT)
        )
        self._risk_bias_entity = self._get_config(CONF_RISK_BIAS_ENTITY)

        self._ramp_start_after_minutes = float(
            self._get_config(
                CONF_RAMP_START_AFTER_MINUTES,
                DEFAULT_RAMP_START_AFTER_MINUTES,
            )
        )
        self._ramp_duration_minutes = float(
            self._get_config(
                CONF_RAMP_DURATION_MINUTES,
                DEFAULT_RAMP_DURATION_MINUTES,
            )
        )
        self._curve = self._get_config(CONF_CURVE, DEFAULT_CURVE)

        self._refresh_source_metadata()

    def _get_config(self, key: str, default: Any | None = None) -> Any:
        """Return a config value with options taking precedence."""
        if key in self._entry.options:
            return self._entry.options[key]
        return self._entry.data.get(key, default)

    def _tracked_entity_ids(self) -> list[str]:
        """Return entity IDs that should trigger recalculation."""
        tracked = [self._source_entity]

        if self._basis_bias_source == BIAS_SOURCE_ENTITY and self._basis_bias_entity:
            tracked.append(self._basis_bias_entity)

        if self._risk_bias_source == BIAS_SOURCE_ENTITY and self._risk_bias_entity:
            tracked.append(self._risk_bias_entity)

        # Preserve ordering while removing duplicates
        return list(dict.fromkeys(tracked))

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
                self._tracked_entity_ids(),
                self._handle_state_change,
            )
        )

    @callback
    def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:  # noqa: ARG002
        """Handle source/bias entity updates."""
        self._refresh_source_metadata()
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if source and configured bias entities are available."""
        source_state = self._hass.states.get(self._source_entity)
        if source_state is None:
            return False

        if source_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return False

        if not isinstance(source_state.attributes.get(ATTR_FORECAST), list):
            return False

        if self._resolved_basis_bias_pct() is None:
            return False

        return self._resolved_risk_bias_pct() is not None

    @property
    def native_value(self) -> float | None:  # type: ignore[override]
        """Return adjusted value at the point closest to now."""
        basis_bias_pct = self._resolved_basis_bias_pct()
        risk_bias_pct = self._resolved_risk_bias_pct()

        if basis_bias_pct is None or risk_bias_pct is None:
            return None

        _, closest_value = self._build_adjusted_forecast(basis_bias_pct, risk_bias_pct)
        return closest_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return source attributes with adjusted forecast and diagnostics."""
        source_state = self._hass.states.get(self._source_entity)
        if source_state is None:
            return {}

        attrs = dict(source_state.attributes)

        basis_bias_pct = self._resolved_basis_bias_pct()
        risk_bias_pct = self._resolved_risk_bias_pct()
        if basis_bias_pct is None or risk_bias_pct is None:
            return attrs

        adjusted_forecast, _ = self._build_adjusted_forecast(
            basis_bias_pct, risk_bias_pct
        )
        if adjusted_forecast is None:
            return attrs

        attrs[ATTR_FORECAST] = adjusted_forecast
        attrs[ATTR_APPLIED_BASIS_BIAS_PCT] = basis_bias_pct
        attrs[ATTR_APPLIED_RISK_BIAS_PCT] = risk_bias_pct
        attrs[ATTR_RAMP_START_AFTER_MINUTES] = self._ramp_start_after_minutes
        attrs[ATTR_RAMP_DURATION_MINUTES] = self._ramp_duration_minutes
        attrs[ATTR_CURVE] = self._curve

        return attrs

    def _resolved_basis_bias_pct(self) -> float | None:
        """Return basis bias pct from configured source."""
        return self._resolve_bias_pct(
            mode=self._basis_bias_source,
            constant_pct=self._basis_bias_pct,
            entity_id=self._basis_bias_entity,
        )

    def _resolved_risk_bias_pct(self) -> float | None:
        """Return risk bias pct from configured source."""
        return self._resolve_bias_pct(
            mode=self._risk_bias_source,
            constant_pct=self._risk_bias_pct,
            entity_id=self._risk_bias_entity,
        )

    def _resolve_bias_pct(
        self,
        mode: str,
        constant_pct: float,
        entity_id: str | None,
    ) -> float | None:
        """Resolve a bias percent from either constant or entity source."""
        value: float | None = None

        if mode == BIAS_SOURCE_CONSTANT:
            value = constant_pct
        elif mode == BIAS_SOURCE_ENTITY and entity_id:
            entity_state = self._hass.states.get(entity_id)
            if entity_state and entity_state.state not in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                try:
                    parsed = float(entity_state.state)
                except (TypeError, ValueError):
                    parsed = None

                if parsed is not None and math.isfinite(parsed):
                    value = parsed

        return value

    def _build_adjusted_forecast(
        self,
        basis_bias_pct: float,
        risk_bias_pct: float,
    ) -> tuple[list[dict[str, Any]] | None, float | None]:
        """Return adjusted forecast and the point closest to now."""
        source_state = self._hass.states.get(self._source_entity)
        if source_state is None:
            return None, None

        source_forecast = source_state.attributes.get(ATTR_FORECAST)
        if not isinstance(source_forecast, list):
            return None, None

        now = dt_util.now()
        adjusted_forecast: list[dict[str, Any]] = []
        closest_value: float | None = None
        closest_diff: float | None = None

        for point in source_forecast:
            if not isinstance(point, dict):
                continue

            adjusted_point = dict(point)
            value = point.get("value")
            point_time = _parse_point_time(point.get("time"), now)

            if not isinstance(value, int | float) or isinstance(value, bool):
                adjusted_forecast.append(adjusted_point)
                continue

            if point_time is None:
                adjusted_forecast.append(adjusted_point)
                continue

            if not math.isfinite(float(value)):
                adjusted_forecast.append(adjusted_point)
                continue

            minutes_from_now = (point_time - now).total_seconds() / 60.0
            adjusted_value = self._apply_bias(
                base_value=float(value),
                minutes_from_now=minutes_from_now,
                basis_bias_pct=basis_bias_pct,
                risk_bias_pct=risk_bias_pct,
            )
            adjusted_point["value"] = adjusted_value
            adjusted_forecast.append(adjusted_point)

            time_diff_seconds = abs((point_time - now).total_seconds())
            if closest_diff is None or time_diff_seconds < closest_diff:
                closest_diff = time_diff_seconds
                closest_value = adjusted_value

        return adjusted_forecast, closest_value

    def _apply_bias(
        self,
        base_value: float,
        minutes_from_now: float,
        basis_bias_pct: float,
        risk_bias_pct: float,
    ) -> float:
        """Apply basis and ramped risk bias to a single forecast value."""
        risk_factor = self._risk_factor(minutes_from_now)
        total_bias_pct = basis_bias_pct + (risk_bias_pct * risk_factor)
        return base_value * (1.0 + (total_bias_pct / 100.0))

    def _risk_factor(self, minutes_from_now: float) -> float:
        """Return ramp factor from 0.0 to 1.0 based on horizon distance."""
        start = self._ramp_start_after_minutes
        duration = self._ramp_duration_minutes

        if minutes_from_now <= start:
            return 0.0

        if duration <= 0:
            return 1.0

        ramp_end = start + duration
        if minutes_from_now >= ramp_end:
            return 1.0

        progress = (minutes_from_now - start) / duration

        if self._curve == CURVE_LINEAR:
            return progress

        return progress


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

    return parsed
