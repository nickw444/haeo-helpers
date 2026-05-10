"""Config helpers for recent days forecast helper kind."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import selector

from .const import (
    CONF_FORECAST_HORIZON_HOURS,
    CONF_HISTORY_DAYS,
    CONF_RECENT_BIAS_PCT,
    CONF_SOURCE_ENTITY,
    DEFAULT_FORECAST_HORIZON_HOURS,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_NAME,
    DEFAULT_RECENT_BIAS_PCT,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def _has_numeric_state(entity_state: Any) -> bool:
    """Return True if a state has a usable numeric state value."""
    if entity_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return False

    try:
        value = float(entity_state.state)
    except (TypeError, ValueError):
        return False

    return math.isfinite(value)


def build_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    """Build form schema for create/edit operations."""
    current = current or {}
    source_entity_key = (
        vol.Required(
            CONF_SOURCE_ENTITY,
            default=current[CONF_SOURCE_ENTITY],
        )
        if CONF_SOURCE_ENTITY in current
        else vol.Required(CONF_SOURCE_ENTITY)
    )

    return vol.Schema(
        {
            vol.Required(
                CONF_NAME,
                default=current.get(CONF_NAME, DEFAULT_NAME),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
            source_entity_key: selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"]),
            ),
            vol.Required(
                CONF_HISTORY_DAYS,
                default=current.get(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=30,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="days",
                ),
            ),
            vol.Required(
                CONF_FORECAST_HORIZON_HOURS,
                default=current.get(
                    CONF_FORECAST_HORIZON_HOURS,
                    DEFAULT_FORECAST_HORIZON_HOURS,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=168,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="h",
                ),
            ),
            vol.Required(
                CONF_RECENT_BIAS_PCT,
                default=current.get(CONF_RECENT_BIAS_PCT, DEFAULT_RECENT_BIAS_PCT),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=500,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="%",
                ),
            ),
        },
    )


def validate_user_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str]:
    """Validate helper config from a config/options flow form."""
    source_entity = user_input[CONF_SOURCE_ENTITY]
    source_state = hass.states.get(source_entity)

    if source_state is None:
        return {CONF_SOURCE_ENTITY: "entity_not_found"}

    if not _has_numeric_state(source_state):
        return {CONF_SOURCE_ENTITY: "entity_not_number"}

    return {}


def normalize_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize form input into persisted entry data/options."""
    return {
        CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
        CONF_HISTORY_DAYS: int(user_input[CONF_HISTORY_DAYS]),
        CONF_FORECAST_HORIZON_HOURS: int(user_input[CONF_FORECAST_HORIZON_HOURS]),
        CONF_RECENT_BIAS_PCT: float(user_input[CONF_RECENT_BIAS_PCT]),
    }


def options_defaults_from_entry(entry: ConfigEntry) -> dict[str, Any]:
    """Build current values for options form defaults."""
    return {
        CONF_NAME: entry.title,
        CONF_SOURCE_ENTITY: entry.options.get(
            CONF_SOURCE_ENTITY,
            entry.data.get(CONF_SOURCE_ENTITY),
        ),
        CONF_HISTORY_DAYS: entry.options.get(
            CONF_HISTORY_DAYS,
            entry.data.get(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS),
        ),
        CONF_FORECAST_HORIZON_HOURS: entry.options.get(
            CONF_FORECAST_HORIZON_HOURS,
            entry.data.get(
                CONF_FORECAST_HORIZON_HOURS,
                DEFAULT_FORECAST_HORIZON_HOURS,
            ),
        ),
        CONF_RECENT_BIAS_PCT: entry.options.get(
            CONF_RECENT_BIAS_PCT,
            entry.data.get(CONF_RECENT_BIAS_PCT, DEFAULT_RECENT_BIAS_PCT),
        ),
    }
