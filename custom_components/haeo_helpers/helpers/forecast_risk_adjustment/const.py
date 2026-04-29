"""Constants for the forecast risk adjustment helper kind."""

from typing import Final

DEFAULT_NAME: Final = "Forecast Risk Adjustment"

# Config keys
CONF_SOURCE_ENTITY: Final = "source_entity"

CONF_BASIS_BIAS_SOURCE: Final = "basis_bias_source"
CONF_BASIS_BIAS_PCT: Final = "basis_bias_pct"
CONF_BASIS_BIAS_ENTITY: Final = "basis_bias_entity"

CONF_RISK_BIAS_SOURCE: Final = "risk_bias_source"
CONF_RISK_BIAS_PCT: Final = "risk_bias_pct"
CONF_RISK_BIAS_ENTITY: Final = "risk_bias_entity"

CONF_RAMP_START_AFTER_MINUTES: Final = "ramp_start_after_minutes"
CONF_RAMP_DURATION_MINUTES: Final = "ramp_duration_minutes"
CONF_CURVE: Final = "curve"

# Selector options
BIAS_SOURCE_CONSTANT: Final = "constant"
BIAS_SOURCE_ENTITY: Final = "entity"

CURVE_LINEAR: Final = "linear"

# Defaults
DEFAULT_BASIS_BIAS_SOURCE: Final = BIAS_SOURCE_CONSTANT
DEFAULT_BASIS_BIAS_PCT: Final = 0.0

DEFAULT_RISK_BIAS_SOURCE: Final = BIAS_SOURCE_CONSTANT
DEFAULT_RISK_BIAS_PCT: Final = 0.0

DEFAULT_RAMP_START_AFTER_MINUTES: Final = 30
DEFAULT_RAMP_DURATION_MINUTES: Final = 90
DEFAULT_CURVE: Final = CURVE_LINEAR

# Shared/source attributes
ATTR_FORECAST: Final = "forecast"

# Diagnostic attributes
ATTR_APPLIED_BASIS_BIAS_PCT: Final = "haeo_helpers_basis_bias_pct"
ATTR_APPLIED_RISK_BIAS_PCT: Final = "haeo_helpers_risk_bias_pct"
ATTR_RAMP_START_AFTER_MINUTES: Final = "haeo_helpers_ramp_start_after_minutes"
ATTR_RAMP_DURATION_MINUTES: Final = "haeo_helpers_ramp_duration_minutes"
ATTR_CURVE: Final = "haeo_helpers_curve"
