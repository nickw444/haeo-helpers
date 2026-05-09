"""Config helpers for realtime forecast smoothing helper kind."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import selector

from .const import (
    ATTR_FORECAST,
    CONF_FORECAST_ENTITY,
    CONF_REALTIME_ENTITY,
    CONF_SMOOTHING_WINDOW_MINUTES,
    DEFAULT_NAME,
    DEFAULT_SMOOTHING_WINDOW_MINUTES,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def _has_forecast_attribute(entity_state: Any) -> bool:
    """Return True if a state looks like a forecast source."""
    return isinstance(entity_state.attributes.get(ATTR_FORECAST), list)


def _has_numeric_state(entity_state: Any) -> bool:
    """Return True if a state has a usable numeric state value."""
    if entity_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return False

    try:
        float(entity_state.state)
    except (TypeError, ValueError):
        return False

    return True


def build_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    """Build form schema for create/edit operations."""
    current = current or {}
    forecast_entity_key = (
        vol.Required(
            CONF_FORECAST_ENTITY,
            default=current[CONF_FORECAST_ENTITY],
        )
        if CONF_FORECAST_ENTITY in current
        else vol.Required(CONF_FORECAST_ENTITY)
    )
    realtime_entity_key = (
        vol.Required(
            CONF_REALTIME_ENTITY,
            default=current[CONF_REALTIME_ENTITY],
        )
        if CONF_REALTIME_ENTITY in current
        else vol.Required(CONF_REALTIME_ENTITY)
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
            forecast_entity_key: selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"]),
            ),
            realtime_entity_key: selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"]),
            ),
            vol.Required(
                CONF_SMOOTHING_WINDOW_MINUTES,
                default=current.get(
                    CONF_SMOOTHING_WINDOW_MINUTES,
                    DEFAULT_SMOOTHING_WINDOW_MINUTES,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=1440,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                ),
            ),
        },
    )


def validate_user_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str]:
    """Validate helper config from a config/options flow form."""
    forecast_entity = user_input[CONF_FORECAST_ENTITY]
    forecast_state = hass.states.get(forecast_entity)
    if forecast_state is None:
        return {CONF_FORECAST_ENTITY: "entity_not_found"}
    if not _has_forecast_attribute(forecast_state):
        return {CONF_FORECAST_ENTITY: "entity_not_forecast"}

    realtime_entity = user_input[CONF_REALTIME_ENTITY]
    realtime_state = hass.states.get(realtime_entity)
    if realtime_state is None:
        return {CONF_REALTIME_ENTITY: "entity_not_found"}
    if not _has_numeric_state(realtime_state):
        return {CONF_REALTIME_ENTITY: "entity_not_number"}

    return {}


def normalize_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize form input into persisted entry data/options."""
    return {
        CONF_FORECAST_ENTITY: user_input[CONF_FORECAST_ENTITY],
        CONF_REALTIME_ENTITY: user_input[CONF_REALTIME_ENTITY],
        CONF_SMOOTHING_WINDOW_MINUTES: int(user_input[CONF_SMOOTHING_WINDOW_MINUTES]),
    }


def options_defaults_from_entry(entry: ConfigEntry) -> dict[str, Any]:
    """Build current values for options form defaults."""
    return {
        CONF_NAME: entry.title,
        CONF_FORECAST_ENTITY: entry.options.get(
            CONF_FORECAST_ENTITY,
            entry.data.get(CONF_FORECAST_ENTITY),
        ),
        CONF_REALTIME_ENTITY: entry.options.get(
            CONF_REALTIME_ENTITY,
            entry.data.get(CONF_REALTIME_ENTITY),
        ),
        CONF_SMOOTHING_WINDOW_MINUTES: entry.options.get(
            CONF_SMOOTHING_WINDOW_MINUTES,
            entry.data.get(
                CONF_SMOOTHING_WINDOW_MINUTES,
                DEFAULT_SMOOTHING_WINDOW_MINUTES,
            ),
        ),
    }
