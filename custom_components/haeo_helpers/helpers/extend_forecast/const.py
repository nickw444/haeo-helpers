"""Constants for the extend forecast helper kind."""

from typing import Final

DEFAULT_NAME: Final = "Extend Forecast"

# Config keys
CONF_SOURCE_ENTITY: Final = "source_entity"
CONF_FORECAST_HORIZON_HOURS: Final = "forecast_horizon_hours"
CONF_HISTORY_DAYS: Final = "history_days"

# Defaults
DEFAULT_FORECAST_HORIZON_HOURS: Final = 48
DEFAULT_HISTORY_DAYS: Final = 7
DEFAULT_INTERVAL_MINUTES: Final = 30

# Shared/source attributes
ATTR_FORECAST: Final = "forecast"
