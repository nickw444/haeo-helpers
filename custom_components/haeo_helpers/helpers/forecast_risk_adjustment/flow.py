"""Config helpers for forecast risk adjustment helper kind."""

from __future__ import annotations

from numbers import Real
from typing import TYPE_CHECKING, Any, Final

import voluptuous as vol
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import selector

from .const import (
    ATTR_FORECAST,
    BIAS_SOURCE_CONSTANT,
    BIAS_SOURCE_ENTITY,
    CONF_BASIS_BIAS_ENTITY,
    CONF_BASIS_BIAS_PCT,
    CONF_BASIS_BIAS_SOURCE,
    CONF_CURVE,
    CONF_RAMP_DURATION_MINUTES,
    CONF_RAMP_START_AFTER_MINUTES,
    CONF_RISK_BIAS_ENTITY,
    CONF_RISK_BIAS_PCT,
    CONF_RISK_BIAS_SOURCE,
    CONF_SOURCE_ENTITY,
    CURVE_LINEAR,
    DEFAULT_BASIS_BIAS_PCT,
    DEFAULT_BASIS_BIAS_SOURCE,
    DEFAULT_CURVE,
    DEFAULT_NAME,
    DEFAULT_RAMP_DURATION_MINUTES,
    DEFAULT_RAMP_START_AFTER_MINUTES,
    DEFAULT_RISK_BIAS_PCT,
    DEFAULT_RISK_BIAS_SOURCE,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


CONF_BASIS_BIAS_INPUT = "basis_bias_input"
CONF_RISK_BIAS_INPUT = "risk_bias_input"

BIAS_INPUT_KEYS: Final[dict[str, tuple[str, str, str]]] = {
    CONF_BASIS_BIAS_INPUT: (
        CONF_BASIS_BIAS_SOURCE,
        CONF_BASIS_BIAS_PCT,
        CONF_BASIS_BIAS_ENTITY,
    ),
    CONF_RISK_BIAS_INPUT: (
        CONF_RISK_BIAS_SOURCE,
        CONF_RISK_BIAS_PCT,
        CONF_RISK_BIAS_ENTITY,
    ),
}


def _has_forecast_attribute(entity_state: Any) -> bool:
    """Return True if a state looks like a forecast source."""
    return isinstance(entity_state.attributes.get(ATTR_FORECAST), list)


def _required_source_entity_marker(current: dict[str, Any]) -> vol.Marker:
    """Build source entity marker with default if available."""
    if current.get(CONF_SOURCE_ENTITY):
        return vol.Required(
            CONF_SOURCE_ENTITY,
            default=current[CONF_SOURCE_ENTITY],
        )
    return vol.Required(CONF_SOURCE_ENTITY)


def _bias_entity_selector() -> selector.EntitySelector:
    """Build entity selector used for bias source entity mode."""
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["input_number", "number"]),
    )


def _bias_pct_selector() -> selector.NumberSelector:
    """Build numeric selector used for constant bias mode."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=-500,
            max=500,
            step=0.1,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement="%",
        ),
    )


def _bias_input_default(
    current: dict[str, Any],
    *,
    field_key: str,
    default_pct: float,
) -> Any:
    """Build default value for choose-selector input."""
    source_key, pct_key, entity_key = BIAS_INPUT_KEYS[field_key]
    value = current.get(field_key)
    if isinstance(value, dict):
        choice = value.get("active_choice")
        choice_value = value.get(choice)
        if choice == BIAS_SOURCE_ENTITY:
            if isinstance(choice_value, str):
                return choice_value
            return current.get(entity_key, current.get(pct_key, default_pct))
        if choice == BIAS_SOURCE_CONSTANT:
            if isinstance(choice_value, Real) and not isinstance(choice_value, bool):
                return choice_value
            return current.get(pct_key, default_pct)

    source = current.get(source_key, BIAS_SOURCE_CONSTANT)
    if source == BIAS_SOURCE_ENTITY and current.get(entity_key):
        return current[entity_key]
    return current.get(pct_key, default_pct)


def _build_bias_choose_selector(
    preferred_source: str,
) -> selector.ChooseSelector:
    """Build choose selector for entity-vs-constant input."""
    choice_order = [BIAS_SOURCE_ENTITY, BIAS_SOURCE_CONSTANT]
    if preferred_source in choice_order:
        choice_order.remove(preferred_source)
        choice_order.insert(0, preferred_source)

    choice_map: dict[str, selector.ChooseSelectorChoiceConfig] = {
        BIAS_SOURCE_ENTITY: selector.ChooseSelectorChoiceConfig(
            selector=_bias_entity_selector().serialize()["selector"],
        ),
        BIAS_SOURCE_CONSTANT: selector.ChooseSelectorChoiceConfig(
            selector=_bias_pct_selector().serialize()["selector"],
        ),
    }
    choices = {key: choice_map[key] for key in choice_order}

    return selector.ChooseSelector(
        selector.ChooseSelectorConfig(
            choices=choices,
            translation_key="input_source",
        ),
    )


def build_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    """Build form schema for create/edit operations."""
    current = current or {}

    source_entity_key = _required_source_entity_marker(current)
    basis_source = current.get(CONF_BASIS_BIAS_SOURCE, DEFAULT_BASIS_BIAS_SOURCE)
    risk_source = current.get(CONF_RISK_BIAS_SOURCE, DEFAULT_RISK_BIAS_SOURCE)
    schema_dict: dict[vol.Marker, Any] = {
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
    }
    schema_dict[
        vol.Required(
            CONF_BASIS_BIAS_INPUT,
            default=_bias_input_default(
                current,
                field_key=CONF_BASIS_BIAS_INPUT,
                default_pct=DEFAULT_BASIS_BIAS_PCT,
            ),
        )
    ] = _build_bias_choose_selector(basis_source)
    schema_dict[
        vol.Required(
            CONF_RISK_BIAS_INPUT,
            default=_bias_input_default(
                current,
                field_key=CONF_RISK_BIAS_INPUT,
                default_pct=DEFAULT_RISK_BIAS_PCT,
            ),
        )
    ] = _build_bias_choose_selector(risk_source)

    schema_dict.update(
        {
            vol.Required(
                CONF_RAMP_START_AFTER_MINUTES,
                default=current.get(
                    CONF_RAMP_START_AFTER_MINUTES,
                    DEFAULT_RAMP_START_AFTER_MINUTES,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=10080,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                ),
            ),
            vol.Required(
                CONF_RAMP_DURATION_MINUTES,
                default=current.get(
                    CONF_RAMP_DURATION_MINUTES,
                    DEFAULT_RAMP_DURATION_MINUTES,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=10080,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                ),
            ),
            vol.Required(
                CONF_CURVE,
                default=current.get(CONF_CURVE, DEFAULT_CURVE),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=CURVE_LINEAR,
                            label="Linear",
                        ),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            ),
        }
    )

    return vol.Schema(schema_dict)


def _validate_numeric_entity_state(
    hass: HomeAssistant,
    entity_id: str,
) -> str | None:
    """Return config-flow error key if an entity state is not numeric."""
    entity_state = hass.states.get(entity_id)
    if entity_state is None:
        return "entity_not_found"

    if entity_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return "entity_not_number"

    try:
        float(entity_state.state)
    except (TypeError, ValueError):
        return "entity_not_number"

    return None


def _resolve_choose_bias(
    *,
    value: Any,
    default_pct: float,
) -> tuple[str, float, str | None, str | None]:
    """Resolve choose-selector value to source mode and payload."""
    source = ""
    pct = default_pct
    entity: str | None = None
    source_error = "value_required"

    if isinstance(value, dict):
        choice = value.get("active_choice")
        selected_value = value.get(choice)
        if choice == BIAS_SOURCE_ENTITY:
            if isinstance(selected_value, str) and selected_value:
                source = BIAS_SOURCE_ENTITY
                entity = selected_value
                source_error = ""
            else:
                source_error = "entity_required"
        elif choice == BIAS_SOURCE_CONSTANT:
            if isinstance(selected_value, Real) and not isinstance(
                selected_value, bool
            ):
                source = BIAS_SOURCE_CONSTANT
                pct = float(selected_value)
                source_error = ""
        else:
            source_error = "value_required"

    if isinstance(value, str):
        if not value:
            source_error = "entity_required"
        else:
            source = BIAS_SOURCE_ENTITY
            entity = value
            source_error = ""

    elif isinstance(value, Real) and not isinstance(value, bool):
        source = BIAS_SOURCE_CONSTANT
        pct = float(value)
        source_error = ""

    return source, pct, entity, source_error


def _validate_choose_bias(
    hass: HomeAssistant,
    *,
    field_key: str,
    value: Any,
    default_pct: float,
) -> tuple[dict[str, str], tuple[str, float, str | None]]:
    """Validate a choose-selector bias field."""
    source, pct, entity, source_error = _resolve_choose_bias(
        value=value,
        default_pct=default_pct,
    )
    if source_error:
        return {field_key: source_error}, (source, pct, entity)

    if source == BIAS_SOURCE_ENTITY and entity is not None:
        entity_error = _validate_numeric_entity_state(hass, entity)
        if entity_error:
            return {field_key: entity_error}, (source, pct, entity)

    return {}, (source, pct, entity)


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

    errors: dict[str, str] = {}
    basis_errors, _ = _validate_choose_bias(
        hass,
        field_key=CONF_BASIS_BIAS_INPUT,
        value=user_input.get(CONF_BASIS_BIAS_INPUT),
        default_pct=DEFAULT_BASIS_BIAS_PCT,
    )
    risk_errors, _ = _validate_choose_bias(
        hass,
        field_key=CONF_RISK_BIAS_INPUT,
        value=user_input.get(CONF_RISK_BIAS_INPUT),
        default_pct=DEFAULT_RISK_BIAS_PCT,
    )
    errors.update(basis_errors)
    errors.update(risk_errors)

    return errors


def normalize_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize form input into persisted entry data/options."""
    basis_source, basis_pct, basis_entity, _ = _resolve_choose_bias(
        value=user_input.get(CONF_BASIS_BIAS_INPUT),
        default_pct=DEFAULT_BASIS_BIAS_PCT,
    )
    risk_source, risk_pct, risk_entity, _ = _resolve_choose_bias(
        value=user_input.get(CONF_RISK_BIAS_INPUT),
        default_pct=DEFAULT_RISK_BIAS_PCT,
    )

    return {
        CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
        CONF_BASIS_BIAS_SOURCE: basis_source or DEFAULT_BASIS_BIAS_SOURCE,
        CONF_BASIS_BIAS_PCT: basis_pct,
        CONF_BASIS_BIAS_ENTITY: basis_entity,
        CONF_RISK_BIAS_SOURCE: risk_source or DEFAULT_RISK_BIAS_SOURCE,
        CONF_RISK_BIAS_PCT: risk_pct,
        CONF_RISK_BIAS_ENTITY: risk_entity,
        CONF_RAMP_START_AFTER_MINUTES: int(user_input[CONF_RAMP_START_AFTER_MINUTES]),
        CONF_RAMP_DURATION_MINUTES: int(user_input[CONF_RAMP_DURATION_MINUTES]),
        CONF_CURVE: user_input[CONF_CURVE],
    }


def options_defaults_from_entry(entry: ConfigEntry) -> dict[str, Any]:
    """Build current values for options form defaults."""
    return {
        CONF_NAME: entry.title,
        CONF_SOURCE_ENTITY: entry.options.get(
            CONF_SOURCE_ENTITY,
            entry.data.get(CONF_SOURCE_ENTITY),
        ),
        CONF_BASIS_BIAS_SOURCE: entry.options.get(
            CONF_BASIS_BIAS_SOURCE,
            entry.data.get(CONF_BASIS_BIAS_SOURCE, DEFAULT_BASIS_BIAS_SOURCE),
        ),
        CONF_BASIS_BIAS_PCT: entry.options.get(
            CONF_BASIS_BIAS_PCT,
            entry.data.get(CONF_BASIS_BIAS_PCT, DEFAULT_BASIS_BIAS_PCT),
        ),
        CONF_BASIS_BIAS_ENTITY: entry.options.get(
            CONF_BASIS_BIAS_ENTITY,
            entry.data.get(CONF_BASIS_BIAS_ENTITY),
        ),
        CONF_RISK_BIAS_SOURCE: entry.options.get(
            CONF_RISK_BIAS_SOURCE,
            entry.data.get(CONF_RISK_BIAS_SOURCE, DEFAULT_RISK_BIAS_SOURCE),
        ),
        CONF_RISK_BIAS_PCT: entry.options.get(
            CONF_RISK_BIAS_PCT,
            entry.data.get(CONF_RISK_BIAS_PCT, DEFAULT_RISK_BIAS_PCT),
        ),
        CONF_RISK_BIAS_ENTITY: entry.options.get(
            CONF_RISK_BIAS_ENTITY,
            entry.data.get(CONF_RISK_BIAS_ENTITY),
        ),
        CONF_RAMP_START_AFTER_MINUTES: entry.options.get(
            CONF_RAMP_START_AFTER_MINUTES,
            entry.data.get(
                CONF_RAMP_START_AFTER_MINUTES,
                DEFAULT_RAMP_START_AFTER_MINUTES,
            ),
        ),
        CONF_RAMP_DURATION_MINUTES: entry.options.get(
            CONF_RAMP_DURATION_MINUTES,
            entry.data.get(
                CONF_RAMP_DURATION_MINUTES,
                DEFAULT_RAMP_DURATION_MINUTES,
            ),
        ),
        CONF_CURVE: entry.options.get(
            CONF_CURVE,
            entry.data.get(CONF_CURVE, DEFAULT_CURVE),
        ),
    }
