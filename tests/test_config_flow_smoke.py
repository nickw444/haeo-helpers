"""Smoke tests for create/options flows across helper kinds."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import selector
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haeo_helpers.const import (
    CONF_HELPER_KIND,
    DOMAIN,
    HELPER_KIND_FORECAST_RISK_ADJUSTMENT,
    HELPER_KIND_FORECAST_STATISTIC,
)
from custom_components.haeo_helpers.helpers.forecast_risk_adjustment.const import (
    BIAS_SOURCE_CONSTANT,
    BIAS_SOURCE_ENTITY,
    CONF_BASIS_BIAS_ENTITY,
    CONF_BASIS_BIAS_PCT,
    CONF_BASIS_BIAS_SOURCE,
    CONF_CURVE,
    CONF_RAMP_DURATION_MINUTES,
    CONF_RAMP_START_AFTER_MINUTES,
    CONF_RISK_BIAS_PCT,
    CONF_RISK_BIAS_SOURCE,
    CURVE_LINEAR,
)
from custom_components.haeo_helpers.helpers.forecast_risk_adjustment.const import (
    CONF_SOURCE_ENTITY as CONF_RISK_SOURCE_ENTITY,
)
from custom_components.haeo_helpers.helpers.forecast_risk_adjustment.flow import (
    CONF_BASIS_BIAS_INPUT,
    CONF_RISK_BIAS_INPUT,
    supports_choose_selector,
)
from custom_components.haeo_helpers.helpers.forecast_statistic.const import (
    AGGREGATION_PERCENTILE,
    CONF_ADJUSTMENT,
    CONF_AGGREGATION,
    CONF_PERCENTILE,
)
from custom_components.haeo_helpers.helpers.forecast_statistic.const import (
    CONF_SOURCE_ENTITY as CONF_STAT_SOURCE_ENTITY,
)

TRANSLATIONS_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "haeo_helpers"
    / "translations"
    / "en.json"
)


def _schema_key_names(data_schema) -> set[str]:
    """Return key names from a voluptuous schema."""
    names: set[str] = set()
    for key in data_schema.schema:
        names.add(getattr(key, "schema", key))
    return names


def _schema_selector(data_schema, key_name: str):
    """Return the selector object for a schema field name."""
    for key, value in data_schema.schema.items():
        if getattr(key, "schema", key) == key_name:
            return value
    msg = f"Missing schema key: {key_name}"
    raise AssertionError(msg)


def test_choose_selector_choice_labels_are_translated():
    """ChooseSelector uses choices, not options, for pill labels."""
    translations = json.loads(TRANSLATIONS_PATH.read_text())

    assert translations["selector"]["input_source"]["choices"] == {
        "entity": "Entity",
        "constant": "Constant",
    }


async def test_user_step_shows_helper_kind_selector(hass):
    """Initial flow step prompts for helper kind selection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_HELPER_KIND in _schema_key_names(result["data_schema"])


async def test_create_forecast_statistic_happy_path(
    hass, forecast_points_factory, source_state_factory
):
    """Creating a forecast-statistic helper succeeds for a forecast source."""
    source_state_factory(
        "sensor.stat_forecast",
        forecast=forecast_points_factory([(0, 1.0), (5, 2.0)]),
        attributes={"friendly_name": "Stat Source"},
    )

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_FORECAST_STATISTIC},
    )

    assert kind_result["type"] == FlowResultType.FORM
    assert kind_result["step_id"] == HELPER_KIND_FORECAST_STATISTIC

    create_result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        {
            CONF_NAME: "Statistic Helper",
            CONF_STAT_SOURCE_ENTITY: "sensor.stat_forecast",
            CONF_AGGREGATION: AGGREGATION_PERCENTILE,
            CONF_PERCENTILE: 50,
            CONF_ADJUSTMENT: 0.2,
        },
    )

    assert create_result["type"] == FlowResultType.CREATE_ENTRY
    assert create_result["title"] == "Statistic Helper"
    assert create_result["data"][CONF_HELPER_KIND] == HELPER_KIND_FORECAST_STATISTIC


async def test_create_forecast_risk_adjustment_happy_path_constant_sources(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Creating a risk-adjustment helper succeeds with constant bias sources."""
    source_state_factory(
        "sensor.risk_forecast",
        forecast=forecast_points_factory([(0, 10.0), (10, 11.0)]),
    )

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_FORECAST_RISK_ADJUSTMENT},
    )

    assert kind_result["type"] == FlowResultType.FORM
    assert kind_result["step_id"] == HELPER_KIND_FORECAST_RISK_ADJUSTMENT

    if supports_choose_selector():
        form_data = {
            CONF_NAME: "Risk Helper",
            CONF_RISK_SOURCE_ENTITY: "sensor.risk_forecast",
            CONF_BASIS_BIAS_INPUT: 5.0,
            CONF_RISK_BIAS_INPUT: 20.0,
            CONF_RAMP_START_AFTER_MINUTES: 30,
            CONF_RAMP_DURATION_MINUTES: 90,
            CONF_CURVE: CURVE_LINEAR,
        }
    else:
        form_data = {
            CONF_NAME: "Risk Helper",
            CONF_RISK_SOURCE_ENTITY: "sensor.risk_forecast",
            CONF_BASIS_BIAS_SOURCE: BIAS_SOURCE_CONSTANT,
            CONF_BASIS_BIAS_PCT: 5.0,
            CONF_RISK_BIAS_SOURCE: BIAS_SOURCE_CONSTANT,
            CONF_RISK_BIAS_PCT: 20.0,
            CONF_RAMP_START_AFTER_MINUTES: 30,
            CONF_RAMP_DURATION_MINUTES: 90,
            CONF_CURVE: CURVE_LINEAR,
        }

    create_result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        form_data,
    )

    assert create_result["type"] == FlowResultType.CREATE_ENTRY
    assert create_result["title"] == "Risk Helper"
    assert (
        create_result["data"][CONF_HELPER_KIND] == HELPER_KIND_FORECAST_RISK_ADJUSTMENT
    )


async def test_risk_form_uses_list_mode_for_entity_constant_source_selectors(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Risk flow source selectors should render in list mode (tab-like)."""
    source_state_factory(
        "sensor.risk_forecast",
        forecast=forecast_points_factory([(0, 10.0), (10, 11.0)]),
    )

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_FORECAST_RISK_ADJUSTMENT},
    )

    if supports_choose_selector():
        basis_selector = _schema_selector(
            kind_result["data_schema"],
            CONF_BASIS_BIAS_INPUT,
        )
        risk_selector = _schema_selector(
            kind_result["data_schema"],
            CONF_RISK_BIAS_INPUT,
        )
        assert "choose" in basis_selector.serialize()["selector"]
        assert "choose" in risk_selector.serialize()["selector"]
    else:
        basis_selector = _schema_selector(
            kind_result["data_schema"],
            CONF_BASIS_BIAS_SOURCE,
        )
        risk_selector = _schema_selector(
            kind_result["data_schema"],
            CONF_RISK_BIAS_SOURCE,
        )
        assert basis_selector.config["mode"] == selector.SelectSelectorMode.LIST
        assert risk_selector.config["mode"] == selector.SelectSelectorMode.LIST


async def test_risk_form_switches_fields_when_entity_mode_is_selected(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Selecting entity mode swaps percent input for entity input."""
    source_state_factory(
        "sensor.risk_forecast",
        forecast=forecast_points_factory([(0, 10.0), (10, 11.0)]),
    )

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_FORECAST_RISK_ADJUSTMENT},
    )

    initial_keys = _schema_key_names(kind_result["data_schema"])
    if supports_choose_selector():
        assert CONF_BASIS_BIAS_INPUT in initial_keys
        assert CONF_BASIS_BIAS_PCT not in initial_keys
        assert CONF_BASIS_BIAS_ENTITY not in initial_keys
    else:
        assert CONF_BASIS_BIAS_PCT in initial_keys
        assert CONF_BASIS_BIAS_ENTITY not in initial_keys

        result = await hass.config_entries.flow.async_configure(
            kind_result["flow_id"],
            {
                CONF_NAME: "Risk Helper",
                CONF_RISK_SOURCE_ENTITY: "sensor.risk_forecast",
                CONF_BASIS_BIAS_SOURCE: BIAS_SOURCE_ENTITY,
                CONF_RISK_BIAS_SOURCE: BIAS_SOURCE_CONSTANT,
                CONF_RISK_BIAS_PCT: 20.0,
                CONF_RAMP_START_AFTER_MINUTES: 30,
                CONF_RAMP_DURATION_MINUTES: 90,
                CONF_CURVE: CURVE_LINEAR,
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {CONF_BASIS_BIAS_ENTITY: "entity_required"}

        updated_keys = _schema_key_names(result["data_schema"])
        assert CONF_BASIS_BIAS_ENTITY in updated_keys
        assert CONF_BASIS_BIAS_PCT not in updated_keys


async def test_create_rejects_missing_forecast_source(hass):
    """Create flow errors when source entity does not exist."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_FORECAST_STATISTIC},
    )

    result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        {
            CONF_NAME: "Statistic Helper",
            CONF_STAT_SOURCE_ENTITY: "sensor.missing",
            CONF_AGGREGATION: AGGREGATION_PERCENTILE,
            CONF_PERCENTILE: 50,
            CONF_ADJUSTMENT: 0,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_STAT_SOURCE_ENTITY: "entity_not_found"}


async def test_create_rejects_non_forecast_source(hass):
    """Create flow errors when source entity has no forecast list attribute."""
    hass.states.async_set("sensor.not_forecast", "1", {"unit_of_measurement": "$"})

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_FORECAST_STATISTIC},
    )

    result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        {
            CONF_NAME: "Statistic Helper",
            CONF_STAT_SOURCE_ENTITY: "sensor.not_forecast",
            CONF_AGGREGATION: AGGREGATION_PERCENTILE,
            CONF_PERCENTILE: 50,
            CONF_ADJUSTMENT: 0,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_STAT_SOURCE_ENTITY: "entity_not_forecast"}


async def test_risk_create_requires_entity_when_entity_source_selected(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Entity source mode requires selecting an entity."""
    source_state_factory(
        "sensor.risk_forecast",
        forecast=forecast_points_factory([(0, 10.0), (10, 11.0)]),
    )

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_FORECAST_RISK_ADJUSTMENT},
    )

    if supports_choose_selector():
        form_data = {
            CONF_NAME: "Risk Helper",
            CONF_RISK_SOURCE_ENTITY: "sensor.risk_forecast",
            CONF_BASIS_BIAS_INPUT: "",
            CONF_RISK_BIAS_INPUT: 20.0,
            CONF_RAMP_START_AFTER_MINUTES: 30,
            CONF_RAMP_DURATION_MINUTES: 90,
            CONF_CURVE: CURVE_LINEAR,
        }
        expected_error = {CONF_BASIS_BIAS_INPUT: "entity_required"}
    else:
        form_data = {
            CONF_NAME: "Risk Helper",
            CONF_RISK_SOURCE_ENTITY: "sensor.risk_forecast",
            CONF_BASIS_BIAS_SOURCE: BIAS_SOURCE_ENTITY,
            CONF_BASIS_BIAS_PCT: 5.0,
            CONF_RISK_BIAS_SOURCE: BIAS_SOURCE_CONSTANT,
            CONF_RISK_BIAS_PCT: 20.0,
            CONF_RAMP_START_AFTER_MINUTES: 30,
            CONF_RAMP_DURATION_MINUTES: 90,
            CONF_CURVE: CURVE_LINEAR,
        }
        expected_error = {CONF_BASIS_BIAS_ENTITY: "entity_required"}

    result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        form_data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == expected_error


async def test_risk_create_rejects_non_numeric_entity_state(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Entity source mode rejects non-numeric entity states."""
    source_state_factory(
        "sensor.risk_forecast",
        forecast=forecast_points_factory([(0, 10.0), (10, 11.0)]),
    )
    hass.states.async_set("input_number.bias", "abc", {})

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_FORECAST_RISK_ADJUSTMENT},
    )

    if supports_choose_selector():
        form_data = {
            CONF_NAME: "Risk Helper",
            CONF_RISK_SOURCE_ENTITY: "sensor.risk_forecast",
            CONF_BASIS_BIAS_INPUT: "input_number.bias",
            CONF_RISK_BIAS_INPUT: 20.0,
            CONF_RAMP_START_AFTER_MINUTES: 30,
            CONF_RAMP_DURATION_MINUTES: 90,
            CONF_CURVE: CURVE_LINEAR,
        }
        expected_error = {CONF_BASIS_BIAS_INPUT: "entity_not_number"}
        result = await hass.config_entries.flow.async_configure(
            kind_result["flow_id"],
            form_data,
        )
    else:
        mode_switch_result = await hass.config_entries.flow.async_configure(
            kind_result["flow_id"],
            {
                CONF_NAME: "Risk Helper",
                CONF_RISK_SOURCE_ENTITY: "sensor.risk_forecast",
                CONF_BASIS_BIAS_SOURCE: BIAS_SOURCE_ENTITY,
                CONF_RISK_BIAS_SOURCE: BIAS_SOURCE_CONSTANT,
                CONF_RISK_BIAS_PCT: 20.0,
                CONF_RAMP_START_AFTER_MINUTES: 30,
                CONF_RAMP_DURATION_MINUTES: 90,
                CONF_CURVE: CURVE_LINEAR,
            },
        )
        assert mode_switch_result["type"] == FlowResultType.FORM
        assert mode_switch_result["errors"] == {
            CONF_BASIS_BIAS_ENTITY: "entity_required"
        }
        result = await hass.config_entries.flow.async_configure(
            mode_switch_result["flow_id"],
            {
                CONF_NAME: "Risk Helper",
                CONF_RISK_SOURCE_ENTITY: "sensor.risk_forecast",
                CONF_BASIS_BIAS_SOURCE: BIAS_SOURCE_ENTITY,
                CONF_BASIS_BIAS_ENTITY: "input_number.bias",
                CONF_RISK_BIAS_SOURCE: BIAS_SOURCE_CONSTANT,
                CONF_RISK_BIAS_PCT: 20.0,
                CONF_RAMP_START_AFTER_MINUTES: 30,
                CONF_RAMP_DURATION_MINUTES: 90,
                CONF_CURVE: CURVE_LINEAR,
            },
        )
        expected_error = {CONF_BASIS_BIAS_ENTITY: "entity_not_number"}

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == expected_error


async def test_options_flow_routes_to_correct_step_for_statistic(
    hass, mock_entry_factory
):
    """Options flow for statistic entries opens statistic step."""
    entry = mock_entry_factory(
        title="Statistic",
        data={
            CONF_HELPER_KIND: HELPER_KIND_FORECAST_STATISTIC,
            CONF_STAT_SOURCE_ENTITY: "sensor.source",
            CONF_AGGREGATION: AGGREGATION_PERCENTILE,
            CONF_PERCENTILE: 50,
            CONF_ADJUSTMENT: 0,
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == HELPER_KIND_FORECAST_STATISTIC


async def test_options_flow_routes_to_correct_step_for_risk_adjustment(
    hass, mock_entry_factory
):
    """Options flow for risk entries opens risk-adjustment step."""
    entry = mock_entry_factory(
        title="Risk",
        data={
            CONF_HELPER_KIND: HELPER_KIND_FORECAST_RISK_ADJUSTMENT,
            CONF_RISK_SOURCE_ENTITY: "sensor.source",
            CONF_BASIS_BIAS_SOURCE: BIAS_SOURCE_CONSTANT,
            CONF_BASIS_BIAS_PCT: 0,
            CONF_RISK_BIAS_SOURCE: BIAS_SOURCE_CONSTANT,
            CONF_RISK_BIAS_PCT: 0,
            CONF_RAMP_START_AFTER_MINUTES: 0,
            CONF_RAMP_DURATION_MINUTES: 1,
            CONF_CURVE: CURVE_LINEAR,
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == HELPER_KIND_FORECAST_RISK_ADJUSTMENT


async def test_options_flow_updates_entry_title_and_options_payload(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Options submit updates entry title and returns normalized options."""
    source_state_factory(
        "sensor.options_source",
        forecast=forecast_points_factory([(0, 1.0), (5, 2.0)]),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Old Title",
        data={
            CONF_HELPER_KIND: HELPER_KIND_FORECAST_STATISTIC,
            CONF_STAT_SOURCE_ENTITY: "sensor.options_source",
            CONF_AGGREGATION: AGGREGATION_PERCENTILE,
            CONF_PERCENTILE: 50,
            CONF_ADJUSTMENT: 0,
        },
        entry_id="options_stat",
    )
    entry.add_to_hass(hass)

    init_result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        init_result["flow_id"],
        {
            CONF_NAME: "New Title",
            CONF_STAT_SOURCE_ENTITY: "sensor.options_source",
            CONF_AGGREGATION: AGGREGATION_PERCENTILE,
            CONF_PERCENTILE: 75,
            CONF_ADJUSTMENT: 0.5,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PERCENTILE] == 75.0
    assert result["data"][CONF_ADJUSTMENT] == 0.5

    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.title == "New Title"
