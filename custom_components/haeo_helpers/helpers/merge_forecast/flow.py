"""Config helpers for merge forecast helper kind."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    ATTR_FORECAST,
    CONF_INTERPOLATION_MODE,
    CONF_SOURCE_ENTITIES,
    DEFAULT_INTERPOLATION_MODE,
    DEFAULT_NAME,
    INTERPOLATION_MODE_LINEAR,
    INTERPOLATION_MODE_NEAREST,
    INTERPOLATION_MODE_NEXT,
    INTERPOLATION_MODE_PREVIOUS,
    INTERPOLATION_MODES,
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
    source_entities_key = (
        vol.Required(
            CONF_SOURCE_ENTITIES,
            default=current[CONF_SOURCE_ENTITIES],
        )
        if CONF_SOURCE_ENTITIES in current
        else vol.Required(CONF_SOURCE_ENTITIES)
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
            source_entities_key: selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["sensor"],
                    multiple=True,
                ),
            ),
            vol.Required(
                CONF_INTERPOLATION_MODE,
                default=current.get(
                    CONF_INTERPOLATION_MODE,
                    DEFAULT_INTERPOLATION_MODE,
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=INTERPOLATION_MODE_PREVIOUS,
                            label="Previous",
                        ),
                        selector.SelectOptionDict(
                            value=INTERPOLATION_MODE_LINEAR,
                            label="Linear",
                        ),
                        selector.SelectOptionDict(
                            value=INTERPOLATION_MODE_NEXT,
                            label="Next",
                        ),
                        selector.SelectOptionDict(
                            value=INTERPOLATION_MODE_NEAREST,
                            label="Nearest",
                        ),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            ),
        },
    )


def validate_user_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str]:
    """Validate helper config from a config/options flow form."""
    source_entities = _normalize_source_entities(
        user_input.get(CONF_SOURCE_ENTITIES),
    )
    if not source_entities:
        return {CONF_SOURCE_ENTITIES: "entities_required"}

    if len(source_entities) != len(set(source_entities)):
        return {CONF_SOURCE_ENTITIES: "duplicate_entities"}

    for source_entity in source_entities:
        source_state = hass.states.get(source_entity)
        if source_state is None:
            return {CONF_SOURCE_ENTITIES: "entity_not_found"}

        if not _has_forecast_attribute(source_state):
            return {CONF_SOURCE_ENTITIES: "entity_not_forecast"}

    interpolation_mode = user_input.get(CONF_INTERPOLATION_MODE)
    if interpolation_mode not in INTERPOLATION_MODES:
        return {CONF_INTERPOLATION_MODE: "invalid_interpolation_mode"}

    return {}


def normalize_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize form input into persisted entry data/options."""
    interpolation_mode = user_input.get(
        CONF_INTERPOLATION_MODE,
        DEFAULT_INTERPOLATION_MODE,
    )
    if interpolation_mode not in INTERPOLATION_MODES:
        interpolation_mode = DEFAULT_INTERPOLATION_MODE

    return {
        CONF_SOURCE_ENTITIES: _normalize_source_entities(
            user_input.get(CONF_SOURCE_ENTITIES)
        ),
        CONF_INTERPOLATION_MODE: interpolation_mode,
    }


def options_defaults_from_entry(entry: ConfigEntry) -> dict[str, Any]:
    """Build current values for options form defaults."""
    return {
        CONF_NAME: entry.title,
        CONF_SOURCE_ENTITIES: entry.options.get(
            CONF_SOURCE_ENTITIES,
            entry.data.get(CONF_SOURCE_ENTITIES, []),
        ),
        CONF_INTERPOLATION_MODE: entry.options.get(
            CONF_INTERPOLATION_MODE,
            entry.data.get(CONF_INTERPOLATION_MODE, DEFAULT_INTERPOLATION_MODE),
        ),
    }


def _normalize_source_entities(raw_source_entities: Any) -> list[str]:
    """Return a list of source entity IDs in submitted order."""
    if isinstance(raw_source_entities, str):
        return [raw_source_entities] if raw_source_entities else []

    if not isinstance(raw_source_entities, list):
        return []

    return [
        source_entity
        for source_entity in raw_source_entities
        if isinstance(source_entity, str) and source_entity
    ]
