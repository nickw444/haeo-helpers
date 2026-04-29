"""Config flow for HAEO Helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_HELPER_KIND,
    DEFAULT_HELPER_KIND,
    DOMAIN,
    HELPER_KIND_FORECAST_RISK_ADJUSTMENT,
    HELPER_KIND_FORECAST_STATISTIC,
)
from .helpers.forecast_risk_adjustment import flow as forecast_risk_adjustment_flow
from .helpers.forecast_statistic import flow as forecast_statistic_flow

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    BuildSchemaFunction = Callable[[dict[str, Any] | None], vol.Schema]
    ValidateInputFunction = Callable[[HomeAssistant, dict[str, Any]], dict[str, str]]
    NormalizeInputFunction = Callable[[dict[str, Any]], dict[str, Any]]
    BuildDefaultsFunction = Callable[[config_entries.ConfigEntry], dict[str, Any]]

HELPER_KIND_OPTIONS: Final = [
    selector.SelectOptionDict(
        value=HELPER_KIND_FORECAST_STATISTIC,
        label="Forecast Statistic",
    ),
    selector.SelectOptionDict(
        value=HELPER_KIND_FORECAST_RISK_ADJUSTMENT,
        label="Forecast Risk Adjustment",
    ),
]

BUILD_SCHEMA_BY_KIND: Final[dict[str, BuildSchemaFunction]] = {
    HELPER_KIND_FORECAST_STATISTIC: forecast_statistic_flow.build_schema,
    HELPER_KIND_FORECAST_RISK_ADJUSTMENT: forecast_risk_adjustment_flow.build_schema,
}

VALIDATE_BY_KIND: Final[dict[str, ValidateInputFunction]] = {
    HELPER_KIND_FORECAST_STATISTIC: forecast_statistic_flow.validate_user_input,
    HELPER_KIND_FORECAST_RISK_ADJUSTMENT: (
        forecast_risk_adjustment_flow.validate_user_input
    ),
}

NORMALIZE_BY_KIND: Final[dict[str, NormalizeInputFunction]] = {
    HELPER_KIND_FORECAST_STATISTIC: forecast_statistic_flow.normalize_user_input,
    HELPER_KIND_FORECAST_RISK_ADJUSTMENT: (
        forecast_risk_adjustment_flow.normalize_user_input
    ),
}

OPTIONS_DEFAULTS_BY_KIND: Final[dict[str, BuildDefaultsFunction]] = {
    HELPER_KIND_FORECAST_STATISTIC: forecast_statistic_flow.options_defaults_from_entry,
    HELPER_KIND_FORECAST_RISK_ADJUSTMENT: (
        forecast_risk_adjustment_flow.options_defaults_from_entry
    ),
}


def _helper_kind_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    """Build schema for helper-kind selection."""
    current = current or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_HELPER_KIND,
                default=current.get(CONF_HELPER_KIND, DEFAULT_HELPER_KIND),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=HELPER_KIND_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            ),
        }
    )


def _get_entry_helper_kind(entry: config_entries.ConfigEntry) -> str:
    """Return helper kind for an existing config entry."""
    return entry.options.get(
        CONF_HELPER_KIND,
        entry.data.get(CONF_HELPER_KIND, DEFAULT_HELPER_KIND),
    )


class HaeoHelpersConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for HAEO Helpers."""

    VERSION = 1
    _selected_helper_kind: str | None = None

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow for this handler."""
        return HaeoHelpersOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select which helper kind to create."""
        if user_input is not None:
            self._selected_helper_kind = user_input[CONF_HELPER_KIND]
            return await self._async_step_selected_kind()

        return self.async_show_form(
            step_id="user",
            data_schema=_helper_kind_schema(user_input),
        )

    async def _async_step_selected_kind(self) -> config_entries.ConfigFlowResult:
        """Route the flow to the selected helper-kind step."""
        helper_kind = self._selected_helper_kind or DEFAULT_HELPER_KIND

        if helper_kind == HELPER_KIND_FORECAST_STATISTIC:
            return await self.async_step_forecast_statistic()

        if helper_kind == HELPER_KIND_FORECAST_RISK_ADJUSTMENT:
            return await self.async_step_forecast_risk_adjustment()

        return self.async_abort(reason="unsupported_helper_kind")

    async def async_step_forecast_statistic(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Configure a forecast statistic helper."""
        return await self._async_step_helper_kind(
            HELPER_KIND_FORECAST_STATISTIC,
            user_input,
        )

    async def async_step_forecast_risk_adjustment(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Configure a forecast risk adjustment helper."""
        return await self._async_step_helper_kind(
            HELPER_KIND_FORECAST_RISK_ADJUSTMENT,
            user_input,
        )

    async def _async_step_helper_kind(
        self,
        helper_kind: str,
        user_input: dict[str, Any] | None,
    ) -> config_entries.ConfigFlowResult:
        """Handle create flow for helper-kind configuration."""
        build_schema = BUILD_SCHEMA_BY_KIND.get(helper_kind)
        validate_input = VALIDATE_BY_KIND.get(helper_kind)
        normalize_input = NORMALIZE_BY_KIND.get(helper_kind)

        if build_schema is None or validate_input is None or normalize_input is None:
            return self.async_abort(reason="unsupported_helper_kind")

        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_input(self.hass, user_input)
            if not errors:
                data = normalize_input(user_input)
                data[CONF_HELPER_KIND] = helper_kind
                return self.async_create_entry(title=user_input[CONF_NAME], data=data)

        return self.async_show_form(
            step_id=helper_kind,
            data_schema=build_schema(user_input),
            errors=errors,
        )


class HaeoHelpersOptionsFlow(config_entries.OptionsFlowWithConfigEntry):
    """Options flow for HAEO Helpers."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Route options flow to the configured helper-kind step."""
        helper_kind = _get_entry_helper_kind(self.config_entry)

        if helper_kind == HELPER_KIND_FORECAST_STATISTIC:
            return await self.async_step_forecast_statistic(user_input)

        if helper_kind == HELPER_KIND_FORECAST_RISK_ADJUSTMENT:
            return await self.async_step_forecast_risk_adjustment(user_input)

        return self.async_abort(reason="unsupported_helper_kind")

    async def async_step_forecast_statistic(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle options for a forecast statistic helper."""
        return await self._async_step_helper_kind(
            HELPER_KIND_FORECAST_STATISTIC,
            user_input,
        )

    async def async_step_forecast_risk_adjustment(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle options for a forecast risk adjustment helper."""
        return await self._async_step_helper_kind(
            HELPER_KIND_FORECAST_RISK_ADJUSTMENT,
            user_input,
        )

    async def _async_step_helper_kind(
        self,
        helper_kind: str,
        user_input: dict[str, Any] | None,
    ) -> config_entries.ConfigFlowResult:
        """Handle options flow for helper-kind configuration."""
        build_schema = BUILD_SCHEMA_BY_KIND.get(helper_kind)
        validate_input = VALIDATE_BY_KIND.get(helper_kind)
        normalize_input = NORMALIZE_BY_KIND.get(helper_kind)
        build_defaults = OPTIONS_DEFAULTS_BY_KIND.get(helper_kind)

        if (
            build_schema is None
            or validate_input is None
            or normalize_input is None
            or build_defaults is None
        ):
            return self.async_abort(reason="unsupported_helper_kind")

        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_input(self.hass, user_input)
            if not errors:
                if user_input[CONF_NAME] != self.config_entry.title:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        title=user_input[CONF_NAME],
                    )

                data = normalize_input(user_input)
                data[CONF_HELPER_KIND] = helper_kind

                return self.async_create_entry(title="", data=data)

        return self.async_show_form(
            step_id=helper_kind,
            data_schema=build_schema(build_defaults(self.config_entry)),
            errors=errors,
        )
