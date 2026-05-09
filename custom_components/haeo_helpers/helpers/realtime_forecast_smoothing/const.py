"""Constants for the realtime forecast smoothing helper kind."""

from typing import Final

DEFAULT_NAME: Final = "Realtime Forecast Smoothing"

# Config keys
CONF_FORECAST_ENTITY: Final = "forecast_entity"
CONF_REALTIME_ENTITY: Final = "realtime_entity"
CONF_SMOOTHING_WINDOW_MINUTES: Final = "smoothing_window_minutes"

# Defaults
DEFAULT_SMOOTHING_WINDOW_MINUTES: Final = 180

# Source attributes
ATTR_FORECAST: Final = "forecast"

# Diagnostics
ATTR_APPLIED_REALTIME_VALUE: Final = "applied_realtime_value"
ATTR_SMOOTHING_WINDOW_MINUTES: Final = "smoothing_window_minutes"
