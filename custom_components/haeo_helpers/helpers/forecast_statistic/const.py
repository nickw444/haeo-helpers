"""Constants for the forecast statistic helper kind."""

from typing import Final

DEFAULT_NAME: Final = "Forecast Statistic"

# Config keys
CONF_SOURCE_ENTITY: Final = "source_entity"
CONF_AGGREGATION: Final = "aggregation"
CONF_PERCENTILE: Final = "percentile"
CONF_ADJUSTMENT: Final = "adjustment"

# Aggregation modes
AGGREGATION_MEAN: Final = "mean"
AGGREGATION_PERCENTILE: Final = "percentile"

# Defaults
DEFAULT_AGGREGATION: Final = AGGREGATION_PERCENTILE
DEFAULT_PERCENTILE: Final = 50.0
DEFAULT_ADJUSTMENT: Final = 0.0

# Attribute names
ATTR_FORECAST: Final = "forecast"
ATTR_SAMPLE_COUNT: Final = "sample_count"
ATTR_BASE_VALUE: Final = "base_value"
