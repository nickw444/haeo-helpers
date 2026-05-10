"""Constants for the recent days forecast helper kind."""

from typing import Final

DEFAULT_NAME: Final = "Recent Days Forecast"

# Config keys
CONF_SOURCE_ENTITY: Final = "source_entity"
CONF_HISTORY_DAYS: Final = "history_days"
CONF_FORECAST_HORIZON_HOURS: Final = "forecast_horizon_hours"
CONF_RECENT_BIAS_PCT: Final = "recent_bias_pct"

# Defaults
DEFAULT_HISTORY_DAYS: Final = 7
DEFAULT_FORECAST_HORIZON_HOURS: Final = 48
DEFAULT_RECENT_BIAS_PCT: Final = 0
INTERVAL_MINUTES: Final = 60

# Attributes
ATTR_FORECAST: Final = "forecast"
ATTR_SOURCE_ENTITY: Final = "source_entity"
ATTR_HISTORY_DAYS: Final = "history_days"
ATTR_FORECAST_HORIZON_HOURS: Final = "forecast_horizon_hours"
ATTR_RECENT_BIAS_PCT: Final = "recent_bias_pct"
ATTR_LAST_FORECAST_UPDATE: Final = "last_forecast_update"
