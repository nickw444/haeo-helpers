"""Config helpers for extend forecast helper kind."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    ATTR_FORECAST,
    CONF_FORECAST_HORIZON_HOURS,
    CONF_HISTORY_DAYS,
    CONF_SOURCE_ENTITY,
    DEFAULT_FORECAST_HORIZON_HOURS,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_NAME,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def _has_forecast_attribute(entity_state: Any) -> bool:
    """Return True if a state looks like a forecast source."""
    return isinstance(entity_state.attributes.get(ATTR_FORECAST), list)


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
                CONF_HISTORY_DAYS,
                default=current.get(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=90,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="days",
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

    if not _has_forecast_attribute(source_state):
        return {CONF_SOURCE_ENTITY: "entity_not_forecast"}

    return {}


def normalize_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize form input into persisted entry data/options."""
    return {
        CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
        CONF_FORECAST_HORIZON_HOURS: int(user_input[CONF_FORECAST_HORIZON_HOURS]),
        CONF_HISTORY_DAYS: int(user_input[CONF_HISTORY_DAYS]),
    }


def options_defaults_from_entry(entry: ConfigEntry) -> dict[str, Any]:
    """Build current values for options form defaults."""
    return {
        CONF_NAME: entry.title,
        CONF_SOURCE_ENTITY: entry.options.get(
            CONF_SOURCE_ENTITY,
            entry.data.get(CONF_SOURCE_ENTITY),
        ),
        CONF_FORECAST_HORIZON_HOURS: entry.options.get(
            CONF_FORECAST_HORIZON_HOURS,
            entry.data.get(
                CONF_FORECAST_HORIZON_HOURS, DEFAULT_FORECAST_HORIZON_HOURS
            ),
        ),
        CONF_HISTORY_DAYS: entry.options.get(
            CONF_HISTORY_DAYS,
            entry.data.get(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS),
        ),
    }
