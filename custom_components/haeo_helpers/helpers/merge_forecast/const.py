"""Constants for the merge forecast helper kind."""

from typing import Final

DEFAULT_NAME: Final = "Merge Forecast"

# Config keys
CONF_SOURCE_ENTITIES: Final = "source_entities"
CONF_INTERPOLATION_MODE: Final = "interpolation_mode"

# Defaults
INTERPOLATION_MODE_LINEAR: Final = "linear"
INTERPOLATION_MODE_PREVIOUS: Final = "previous"
INTERPOLATION_MODE_NEXT: Final = "next"
INTERPOLATION_MODE_NEAREST: Final = "nearest"
INTERPOLATION_MODES: Final = (
    INTERPOLATION_MODE_LINEAR,
    INTERPOLATION_MODE_PREVIOUS,
    INTERPOLATION_MODE_NEXT,
    INTERPOLATION_MODE_NEAREST,
)
DEFAULT_INTERPOLATION_MODE: Final = INTERPOLATION_MODE_PREVIOUS

# Source/output attributes
ATTR_FORECAST: Final = "forecast"
ATTR_INTERPOLATION_MODE: Final = "interpolation_mode"
ATTR_SOURCE_ENTITIES: Final = "source_entities"
ATTR_MERGED_SOURCE_COUNT: Final = "merged_source_count"
