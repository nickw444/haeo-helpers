"""Sensor platform dispatcher for HAEO Helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from .const import (
    CONF_HELPER_KIND,
    DEFAULT_HELPER_KIND,
    HELPER_KIND_EXTEND_FORECAST,
    HELPER_KIND_FORECAST_RISK_ADJUSTMENT,
    HELPER_KIND_FORECAST_STATISTIC,
    HELPER_KIND_REALTIME_FORECAST_SMOOTHING,
    HELPER_KIND_RECENT_DAYS_FORECAST,
    LOGGER,
)
from .helpers.extend_forecast.sensor import async_setup_entry as setup_extend_forecast
from .helpers.forecast_risk_adjustment.sensor import (
    async_setup_entry as setup_forecast_risk_adjustment,
)
from .helpers.forecast_statistic.sensor import (
    async_setup_entry as setup_forecast_statistic,
)
from .helpers.realtime_forecast_smoothing.sensor import (
    async_setup_entry as setup_realtime_forecast_smoothing,
)
from .helpers.recent_days_forecast.sensor import (
    async_setup_entry as setup_recent_days_forecast,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    SensorSetupFunction = Callable[
        [HomeAssistant, ConfigEntry, AddConfigEntryEntitiesCallback],
        Awaitable[None],
    ]

SENSOR_SETUP_BY_HELPER_KIND: Final[dict[str, SensorSetupFunction]] = {
    HELPER_KIND_FORECAST_STATISTIC: setup_forecast_statistic,
    HELPER_KIND_FORECAST_RISK_ADJUSTMENT: setup_forecast_risk_adjustment,
    HELPER_KIND_EXTEND_FORECAST: setup_extend_forecast,
    HELPER_KIND_REALTIME_FORECAST_SMOOTHING: setup_realtime_forecast_smoothing,
    HELPER_KIND_RECENT_DAYS_FORECAST: setup_recent_days_forecast,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities for the configured helper kind."""
    helper_kind = entry.options.get(
        CONF_HELPER_KIND,
        entry.data.get(CONF_HELPER_KIND, DEFAULT_HELPER_KIND),
    )

    if setup := SENSOR_SETUP_BY_HELPER_KIND.get(helper_kind):
        await setup(hass, entry, async_add_entities)
        return

    LOGGER.warning(
        "Unsupported helper kind '%s' for entry '%s'",
        helper_kind,
        entry.entry_id,
    )
