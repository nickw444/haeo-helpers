"""Config helpers for forecast statistic helper kind."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    AGGREGATION_MEAN,
    AGGREGATION_PERCENTILE,
    ATTR_FORECAST,
    CONF_ADJUSTMENT,
    CONF_AGGREGATION,
    CONF_PERCENTILE,
    CONF_SOURCE_ENTITY,
    DEFAULT_ADJUSTMENT,
    DEFAULT_AGGREGATION,
    DEFAULT_NAME,
    DEFAULT_PERCENTILE,
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
                CONF_AGGREGATION,
                default=current.get(CONF_AGGREGATION, DEFAULT_AGGREGATION),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=AGGREGATION_PERCENTILE,
                            label="Percentile",
                        ),
                        selector.SelectOptionDict(
                            value=AGGREGATION_MEAN,
                            label="Mean",
                        ),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            ),
            vol.Required(
                CONF_PERCENTILE,
                default=current.get(CONF_PERCENTILE, DEFAULT_PERCENTILE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            vol.Required(
                CONF_ADJUSTMENT,
                default=current.get(CONF_ADJUSTMENT, DEFAULT_ADJUSTMENT),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-1000,
                    max=1000,
                    step=0.01,
                    mode=selector.NumberSelectorMode.BOX,
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
        CONF_AGGREGATION: user_input[CONF_AGGREGATION],
        CONF_PERCENTILE: float(user_input[CONF_PERCENTILE]),
        CONF_ADJUSTMENT: float(user_input[CONF_ADJUSTMENT]),
    }


def options_defaults_from_entry(entry: ConfigEntry) -> dict[str, Any]:
    """Build current values for options form defaults."""
    return {
        CONF_NAME: entry.title,
        CONF_SOURCE_ENTITY: entry.options.get(
            CONF_SOURCE_ENTITY,
            entry.data.get(CONF_SOURCE_ENTITY),
        ),
        CONF_AGGREGATION: entry.options.get(
            CONF_AGGREGATION,
            entry.data.get(CONF_AGGREGATION, DEFAULT_AGGREGATION),
        ),
        CONF_PERCENTILE: entry.options.get(
            CONF_PERCENTILE,
            entry.data.get(CONF_PERCENTILE, DEFAULT_PERCENTILE),
        ),
        CONF_ADJUSTMENT: entry.options.get(
            CONF_ADJUSTMENT,
            entry.data.get(CONF_ADJUSTMENT, DEFAULT_ADJUSTMENT),
        ),
    }
