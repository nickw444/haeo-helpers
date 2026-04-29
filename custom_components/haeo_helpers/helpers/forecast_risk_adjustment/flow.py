"""Config helpers for forecast risk adjustment helper kind."""

from __future__ import annotations

from numbers import Real
from typing import TYPE_CHECKING, Any

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

try:
    from homeassistant.helpers.selector import (
        ChooseSelector,
        ChooseSelectorChoiceConfig,
        ChooseSelectorConfig,
    )

    _HAS_CHOOSE_SELECTOR = True
except ImportError:  # pragma: no cover - depends on HA core version
    _HAS_CHOOSE_SELECTOR = False

    ChooseSelector = Any  # type: ignore[assignment, misc]
    ChooseSelectorChoiceConfig = Any  # type: ignore[assignment, misc]
    ChooseSelectorConfig = Any  # type: ignore[assignment, misc]


CONF_BASIS_BIAS_INPUT = "basis_bias_input"
CONF_RISK_BIAS_INPUT = "risk_bias_input"


if _HAS_CHOOSE_SELECTOR:

    class _NormalizingChooseSelector(ChooseSelector):
        """Choose selector wrapper that accepts raw frontend payloads."""

        def __call__(self, data: Any) -> Any:
            """Normalize payload before choose-selector validation."""
            return super().__call__(self._normalize(data))  # type: ignore[misc]

        def _normalize(self, value: Any) -> Any:
            """Convert active-choice payload into nested selector value."""
            if not isinstance(value, dict) or "active_choice" not in value:
                return value

            choice = value.get("active_choice")
            if choice == BIAS_SOURCE_ENTITY:
                return value.get(BIAS_SOURCE_ENTITY)
            if choice == BIAS_SOURCE_CONSTANT:
                return value.get(BIAS_SOURCE_CONSTANT)
            return value


def _has_forecast_attribute(entity_state: Any) -> bool:
    """Return True if a state looks like a forecast source."""
    return isinstance(entity_state.attributes.get(ATTR_FORECAST), list)


def _required_entity_marker(
    key: str,
    current: dict[str, Any],
) -> vol.Marker:
    """Build a required entity marker with default if available."""
    if current.get(key):
        return vol.Required(key, default=current[key])
    return vol.Required(key)


def _required_source_entity_marker(current: dict[str, Any]) -> vol.Marker:
    """Build source entity marker with default if available."""
    if current.get(CONF_SOURCE_ENTITY):
        return vol.Required(
            CONF_SOURCE_ENTITY,
            default=current[CONF_SOURCE_ENTITY],
        )
    return vol.Required(CONF_SOURCE_ENTITY)


def _required_bias_pct_marker(
    key: str,
    current: dict[str, Any],
    default_value: float,
) -> vol.Marker:
    """Build a required constant bias marker with default fallback."""
    return vol.Required(
        key,
        default=current.get(key, default_value),
    )


def supports_choose_selector() -> bool:
    """Return whether the runtime supports HA's ChooseSelector."""
    return _HAS_CHOOSE_SELECTOR


def _bias_source_selector() -> selector.SelectSelector:
    """Build a source selector with HAEO-like list rendering."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(
                    value=BIAS_SOURCE_ENTITY,
                    label="Entity",
                ),
                selector.SelectOptionDict(
                    value=BIAS_SOURCE_CONSTANT,
                    label="Constant",
                ),
            ],
            mode=selector.SelectSelectorMode.LIST,
        ),
    )


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
    source_key: str,
    pct_key: str,
    entity_key: str,
    default_pct: float,
) -> Any:
    """Build default value for choose-selector input."""
    source = current.get(source_key, BIAS_SOURCE_CONSTANT)
    if source == BIAS_SOURCE_ENTITY and current.get(entity_key):
        return current[entity_key]
    return current.get(pct_key, default_pct)


def _build_bias_choose_selector(
    preferred_source: str,
) -> Any:
    """Build HAEO-style choose selector for entity-vs-constant input."""
    entity_selector = _bias_entity_selector()
    constant_selector = _bias_pct_selector()
    entity_choice = ChooseSelectorChoiceConfig(
        selector=entity_selector.serialize()["selector"],
    )
    constant_choice = ChooseSelectorChoiceConfig(
        selector=constant_selector.serialize()["selector"],
    )

    choice_order = [BIAS_SOURCE_ENTITY, BIAS_SOURCE_CONSTANT]
    if preferred_source in choice_order:
        choice_order.remove(preferred_source)
        choice_order.insert(0, preferred_source)

    choice_map = {
        BIAS_SOURCE_ENTITY: entity_choice,
        BIAS_SOURCE_CONSTANT: constant_choice,
    }
    choices = {key: choice_map[key] for key in choice_order}

    return _NormalizingChooseSelector(
        ChooseSelectorConfig(
            choices=choices,
            translation_key="input_source",
        )
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

    if supports_choose_selector():
        schema_dict[
            vol.Required(
                CONF_BASIS_BIAS_INPUT,
                default=_bias_input_default(
                    current,
                    source_key=CONF_BASIS_BIAS_SOURCE,
                    pct_key=CONF_BASIS_BIAS_PCT,
                    entity_key=CONF_BASIS_BIAS_ENTITY,
                    default_pct=DEFAULT_BASIS_BIAS_PCT,
                ),
            )
        ] = _build_bias_choose_selector(basis_source)
        schema_dict[
            vol.Required(
                CONF_RISK_BIAS_INPUT,
                default=_bias_input_default(
                    current,
                    source_key=CONF_RISK_BIAS_SOURCE,
                    pct_key=CONF_RISK_BIAS_PCT,
                    entity_key=CONF_RISK_BIAS_ENTITY,
                    default_pct=DEFAULT_RISK_BIAS_PCT,
                ),
            )
        ] = _build_bias_choose_selector(risk_source)
    else:
        schema_dict[vol.Required(CONF_BASIS_BIAS_SOURCE, default=basis_source)] = (
            _bias_source_selector()
        )

        if basis_source == BIAS_SOURCE_ENTITY:
            schema_dict[_required_entity_marker(CONF_BASIS_BIAS_ENTITY, current)] = (
                _bias_entity_selector()
            )
        else:
            schema_dict[
                _required_bias_pct_marker(
                    CONF_BASIS_BIAS_PCT,
                    current,
                    DEFAULT_BASIS_BIAS_PCT,
                )
            ] = _bias_pct_selector()

        schema_dict[vol.Required(CONF_RISK_BIAS_SOURCE, default=risk_source)] = (
            _bias_source_selector()
        )
        if risk_source == BIAS_SOURCE_ENTITY:
            schema_dict[_required_entity_marker(CONF_RISK_BIAS_ENTITY, current)] = (
                _bias_entity_selector()
            )
        else:
            schema_dict[
                _required_bias_pct_marker(
                    CONF_RISK_BIAS_PCT,
                    current,
                    DEFAULT_RISK_BIAS_PCT,
                )
            ] = _bias_pct_selector()

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


def _validate_bias_source(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    source_key: str,
    constant_key: str,
    entity_key: str,
) -> dict[str, str]:
    """Validate a bias source selector pair."""
    mode = user_input[source_key]
    if mode == BIAS_SOURCE_CONSTANT:
        if constant_key not in user_input:
            return {constant_key: "value_required"}
        return {}

    if mode != BIAS_SOURCE_ENTITY:
        return {}

    entity_id = user_input.get(entity_key)
    if not entity_id:
        return {entity_key: "entity_required"}

    entity_error = _validate_numeric_entity_state(hass, entity_id)
    if entity_error:
        return {entity_key: entity_error}
    return {}


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
    if isinstance(value, list):
        if len(value) != 1 or not isinstance(value[0], str):
            return "", default_pct, None, "entity_required"
        value = value[0]

    if isinstance(value, str):
        if not value:
            return "", default_pct, None, "entity_required"
        return BIAS_SOURCE_ENTITY, default_pct, value, None

    if isinstance(value, Real) and not isinstance(value, bool):
        return BIAS_SOURCE_CONSTANT, float(value), None, None

    return "", default_pct, None, "value_required"


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
    if supports_choose_selector() and (
        CONF_BASIS_BIAS_INPUT in user_input or CONF_RISK_BIAS_INPUT in user_input
    ):
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

    errors.update(
        _validate_bias_source(
            hass,
            user_input,
            CONF_BASIS_BIAS_SOURCE,
            CONF_BASIS_BIAS_PCT,
            CONF_BASIS_BIAS_ENTITY,
        )
    )
    errors.update(
        _validate_bias_source(
            hass,
            user_input,
            CONF_RISK_BIAS_SOURCE,
            CONF_RISK_BIAS_PCT,
            CONF_RISK_BIAS_ENTITY,
        )
    )

    return errors


def normalize_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize form input into persisted entry data/options."""
    if supports_choose_selector() and (
        CONF_BASIS_BIAS_INPUT in user_input or CONF_RISK_BIAS_INPUT in user_input
    ):
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
            CONF_RAMP_START_AFTER_MINUTES: int(
                user_input[CONF_RAMP_START_AFTER_MINUTES]
            ),
            CONF_RAMP_DURATION_MINUTES: int(user_input[CONF_RAMP_DURATION_MINUTES]),
            CONF_CURVE: user_input[CONF_CURVE],
        }

    basis_source = user_input[CONF_BASIS_BIAS_SOURCE]
    risk_source = user_input[CONF_RISK_BIAS_SOURCE]

    return {
        CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
        CONF_BASIS_BIAS_SOURCE: basis_source,
        CONF_BASIS_BIAS_PCT: float(
            user_input.get(CONF_BASIS_BIAS_PCT, DEFAULT_BASIS_BIAS_PCT)
        ),
        CONF_BASIS_BIAS_ENTITY: (
            user_input.get(CONF_BASIS_BIAS_ENTITY)
            if basis_source == BIAS_SOURCE_ENTITY
            else None
        ),
        CONF_RISK_BIAS_SOURCE: risk_source,
        CONF_RISK_BIAS_PCT: float(
            user_input.get(CONF_RISK_BIAS_PCT, DEFAULT_RISK_BIAS_PCT)
        ),
        CONF_RISK_BIAS_ENTITY: (
            user_input.get(CONF_RISK_BIAS_ENTITY)
            if risk_source == BIAS_SOURCE_ENTITY
            else None
        ),
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
