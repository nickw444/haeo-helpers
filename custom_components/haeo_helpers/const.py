"""Constants for HAEO Helpers."""

from logging import Logger, getLogger
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "haeo_helpers"

# Supported Home Assistant platforms for this integration
PLATFORMS: Final = (Platform.SENSOR,)

# Entry metadata
CONF_HELPER_KIND: Final = "helper_kind"

# Helper kinds
HELPER_KIND_FORECAST_STATISTIC: Final = "forecast_statistic"
HELPER_KIND_FORECAST_RISK_ADJUSTMENT: Final = "forecast_risk_adjustment"
HELPER_KIND_EXTEND_FORECAST: Final = "extend_forecast"
HELPER_KIND_REALTIME_FORECAST_SMOOTHING: Final = "realtime_forecast_smoothing"
DEFAULT_HELPER_KIND: Final = HELPER_KIND_FORECAST_STATISTIC

LOGGER: Logger = getLogger(__package__)
