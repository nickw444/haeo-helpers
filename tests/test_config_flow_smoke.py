"""Smoke tests for create/options flows across helper kinds."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haeo_helpers.const import (
    CONF_HELPER_KIND,
    DOMAIN,
    HELPER_KIND_EXTEND_FORECAST,
    HELPER_KIND_FORECAST_RISK_ADJUSTMENT,
    HELPER_KIND_FORECAST_STATISTIC,
    HELPER_KIND_MERGE_FORECAST,
    HELPER_KIND_REALTIME_FORECAST_SMOOTHING,
    HELPER_KIND_RECENT_DAYS_FORECAST,
)
from custom_components.haeo_helpers.helpers.extend_forecast.const import (
    CONF_FORECAST_HORIZON_HOURS,
    CONF_HISTORY_DAYS,
)
from custom_components.haeo_helpers.helpers.extend_forecast.const import (
    CONF_SOURCE_ENTITY as CONF_EXTEND_SOURCE_ENTITY,
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
    CONF_RISK_BIAS_ENTITY,
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
from custom_components.haeo_helpers.helpers.merge_forecast.const import (
    CONF_INTERPOLATION_MODE,
    CONF_SOURCE_ENTITIES,
    INTERPOLATION_MODE_PREVIOUS,
)
from custom_components.haeo_helpers.helpers.realtime_forecast_smoothing.const import (
    CONF_FORECAST_ENTITY,
    CONF_REALTIME_ENTITY,
    CONF_SMOOTHING_WINDOW_MINUTES,
)
from custom_components.haeo_helpers.helpers.recent_days_forecast.const import (
    CONF_FORECAST_HORIZON_HOURS as CONF_RECENT_FORECAST_HORIZON_HOURS,
)
from custom_components.haeo_helpers.helpers.recent_days_forecast.const import (
    CONF_HISTORY_DAYS as CONF_RECENT_HISTORY_DAYS,
)
from custom_components.haeo_helpers.helpers.recent_days_forecast.const import (
    CONF_RECENT_BIAS_PCT,
)
from custom_components.haeo_helpers.helpers.recent_days_forecast.const import (
    CONF_SOURCE_ENTITY as CONF_RECENT_SOURCE_ENTITY,
)
from custom_components.haeo_helpers.helpers.recent_days_forecast.flow import (
    normalize_user_input as normalize_recent_days_user_input,
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


def _choose_selector_config(data_schema, key_name: str) -> dict[str, object]:
    """Return serialized choose-selector config for a schema field."""
    return _schema_selector(data_schema, key_name).serialize()["selector"]["choose"]


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


async def test_create_forecast_risk_adjustment_happy_path_constant_choices(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Creating a risk-adjustment helper succeeds with constant choose values."""
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

    form_data = {
        CONF_NAME: "Risk Helper",
        CONF_RISK_SOURCE_ENTITY: "sensor.risk_forecast",
        CONF_BASIS_BIAS_INPUT: {
            "active_choice": BIAS_SOURCE_CONSTANT,
            BIAS_SOURCE_CONSTANT: 5.0,
        },
        CONF_RISK_BIAS_INPUT: {
            "active_choice": BIAS_SOURCE_CONSTANT,
            BIAS_SOURCE_CONSTANT: 20.0,
        },
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


async def test_risk_form_uses_choose_selector_for_entity_constant_inputs(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Risk flow exposes choose selectors for basis and risk inputs."""
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

    basis_choose = _choose_selector_config(
        kind_result["data_schema"], CONF_BASIS_BIAS_INPUT
    )
    risk_choose = _choose_selector_config(
        kind_result["data_schema"], CONF_RISK_BIAS_INPUT
    )

    schema_keys = _schema_key_names(kind_result["data_schema"])
    assert CONF_BASIS_BIAS_SOURCE not in schema_keys
    assert CONF_BASIS_BIAS_PCT not in schema_keys
    assert CONF_BASIS_BIAS_ENTITY not in schema_keys
    assert CONF_RISK_BIAS_SOURCE not in schema_keys
    assert CONF_RISK_BIAS_PCT not in schema_keys
    assert CONF_RISK_BIAS_ENTITY not in schema_keys

    assert basis_choose["translation_key"] == "input_source"
    assert risk_choose["translation_key"] == "input_source"
    assert set(basis_choose["choices"]) == {BIAS_SOURCE_ENTITY, BIAS_SOURCE_CONSTANT}
    assert set(risk_choose["choices"]) == {BIAS_SOURCE_ENTITY, BIAS_SOURCE_CONSTANT}
    assert set(basis_choose["choices"][BIAS_SOURCE_ENTITY]["selector"]) == {"entity"}
    assert set(risk_choose["choices"][BIAS_SOURCE_ENTITY]["selector"]) == {"entity"}
    assert set(basis_choose["choices"][BIAS_SOURCE_CONSTANT]["selector"]) == {"number"}
    assert set(risk_choose["choices"][BIAS_SOURCE_CONSTANT]["selector"]) == {"number"}


async def test_risk_form_requires_entity_when_entity_choice_is_selected(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Choose selector requires an entity value when entity is selected."""
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
    assert CONF_BASIS_BIAS_INPUT in initial_keys
    assert CONF_BASIS_BIAS_SOURCE not in initial_keys
    assert CONF_BASIS_BIAS_ENTITY not in initial_keys

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            kind_result["flow_id"],
            {
                CONF_NAME: "Risk Helper",
                CONF_RISK_SOURCE_ENTITY: "sensor.risk_forecast",
                CONF_BASIS_BIAS_INPUT: {
                    "active_choice": BIAS_SOURCE_ENTITY,
                    BIAS_SOURCE_ENTITY: "",
                },
                CONF_RISK_BIAS_INPUT: {
                    "active_choice": BIAS_SOURCE_CONSTANT,
                    BIAS_SOURCE_CONSTANT: 20.0,
                },
                CONF_RAMP_START_AFTER_MINUTES: 30,
                CONF_RAMP_DURATION_MINUTES: 90,
                CONF_CURVE: CURVE_LINEAR,
            },
        )


async def test_create_extend_forecast_happy_path(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Creating an extend-forecast helper succeeds for a forecast source."""
    source_state_factory(
        "sensor.extend_forecast_source",
        state="12.5",
        forecast=forecast_points_factory([(0, 10.0), (60, 11.0)]),
    )

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_EXTEND_FORECAST},
    )

    assert kind_result["type"] == FlowResultType.FORM
    assert kind_result["step_id"] == HELPER_KIND_EXTEND_FORECAST

    create_result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        {
            CONF_NAME: "Extend Helper",
            CONF_EXTEND_SOURCE_ENTITY: "sensor.extend_forecast_source",
            CONF_FORECAST_HORIZON_HOURS: 48,
            CONF_HISTORY_DAYS: 7,
        },
    )

    assert create_result["type"] == FlowResultType.CREATE_ENTRY
    assert create_result["title"] == "Extend Helper"
    assert create_result["data"][CONF_HELPER_KIND] == HELPER_KIND_EXTEND_FORECAST


async def test_create_realtime_forecast_smoothing_happy_path(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Creating a realtime forecast smoothing helper succeeds."""
    source_state_factory(
        "sensor.smoothing_forecast",
        state="1.0",
        forecast=forecast_points_factory([(0, 1.0), (30, 0.5)]),
    )
    hass.states.async_set(
        "sensor.smoothing_realtime", "4.0", {"unit_of_measurement": "kW"}
    )

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_REALTIME_FORECAST_SMOOTHING},
    )

    assert kind_result["type"] == FlowResultType.FORM
    assert kind_result["step_id"] == HELPER_KIND_REALTIME_FORECAST_SMOOTHING

    create_result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        {
            CONF_NAME: "Realtime Smoothing",
            CONF_FORECAST_ENTITY: "sensor.smoothing_forecast",
            CONF_REALTIME_ENTITY: "sensor.smoothing_realtime",
            CONF_SMOOTHING_WINDOW_MINUTES: 180,
        },
    )

    assert create_result["type"] == FlowResultType.CREATE_ENTRY
    assert create_result["title"] == "Realtime Smoothing"
    assert (
        create_result["data"][CONF_HELPER_KIND]
        == HELPER_KIND_REALTIME_FORECAST_SMOOTHING
    )


async def test_realtime_forecast_smoothing_rejects_non_finite_realtime_source(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Realtime smoothing flow rejects non-finite realtime states."""
    source_state_factory(
        "sensor.smoothing_forecast",
        forecast=forecast_points_factory([(0, 1.0), (30, 0.5)]),
    )
    hass.states.async_set("sensor.smoothing_realtime", "nan", {})

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_REALTIME_FORECAST_SMOOTHING},
    )

    result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        {
            CONF_NAME: "Realtime Smoothing",
            CONF_FORECAST_ENTITY: "sensor.smoothing_forecast",
            CONF_REALTIME_ENTITY: "sensor.smoothing_realtime",
            CONF_SMOOTHING_WINDOW_MINUTES: 180,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_REALTIME_ENTITY: "entity_not_number"}


async def test_create_recent_days_forecast_happy_path(hass):
    """Creating a recent-days forecast helper succeeds for a numeric source."""
    hass.states.async_set(
        "sensor.recent_load",
        "1.5",
        {"unit_of_measurement": "kW"},
    )

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_RECENT_DAYS_FORECAST},
    )

    assert kind_result["type"] == FlowResultType.FORM
    assert kind_result["step_id"] == HELPER_KIND_RECENT_DAYS_FORECAST

    create_result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        {
            CONF_NAME: "Recent Forecast",
            CONF_RECENT_SOURCE_ENTITY: "sensor.recent_load",
            CONF_RECENT_HISTORY_DAYS: 3,
            CONF_RECENT_FORECAST_HORIZON_HOURS: 48,
            CONF_RECENT_BIAS_PCT: 100,
        },
    )

    assert create_result["type"] == FlowResultType.CREATE_ENTRY
    assert create_result["title"] == "Recent Forecast"
    assert create_result["data"][CONF_HELPER_KIND] == HELPER_KIND_RECENT_DAYS_FORECAST
    assert create_result["data"][CONF_RECENT_SOURCE_ENTITY] == "sensor.recent_load"
    assert create_result["data"][CONF_RECENT_HISTORY_DAYS] == 3
    assert create_result["data"][CONF_RECENT_FORECAST_HORIZON_HOURS] == 48
    assert create_result["data"][CONF_RECENT_BIAS_PCT] == 100.0


async def test_create_merge_forecast_happy_path(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Creating a merge-forecast helper succeeds for ordered forecast sources."""
    source_state_factory(
        "sensor.merge_primary",
        forecast=forecast_points_factory([(0, 1.0), (60, 2.0)]),
    )
    source_state_factory(
        "sensor.merge_secondary",
        forecast=forecast_points_factory([(60, 20.0), (120, 30.0)]),
    )

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_MERGE_FORECAST},
    )

    assert kind_result["type"] == FlowResultType.FORM
    assert kind_result["step_id"] == HELPER_KIND_MERGE_FORECAST

    create_result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        {
            CONF_NAME: "Merge Forecast",
            CONF_SOURCE_ENTITIES: [
                "sensor.merge_primary",
                "sensor.merge_secondary",
            ],
            CONF_INTERPOLATION_MODE: INTERPOLATION_MODE_PREVIOUS,
        },
    )

    assert create_result["type"] == FlowResultType.CREATE_ENTRY
    assert create_result["title"] == "Merge Forecast"
    assert create_result["data"][CONF_HELPER_KIND] == HELPER_KIND_MERGE_FORECAST
    assert create_result["data"][CONF_SOURCE_ENTITIES] == [
        "sensor.merge_primary",
        "sensor.merge_secondary",
    ]
    assert create_result["data"][CONF_INTERPOLATION_MODE] == INTERPOLATION_MODE_PREVIOUS


async def test_merge_forecast_rejects_empty_source_list(hass):
    """Merge flow requires at least one forecast source."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_MERGE_FORECAST},
    )

    result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        {
            CONF_NAME: "Merge Forecast",
            CONF_SOURCE_ENTITIES: [],
            CONF_INTERPOLATION_MODE: INTERPOLATION_MODE_PREVIOUS,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_SOURCE_ENTITIES: "entities_required"}


async def test_merge_forecast_rejects_duplicate_sources(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Merge flow rejects duplicate source entities."""
    source_state_factory(
        "sensor.merge_primary",
        forecast=forecast_points_factory([(0, 1.0), (60, 2.0)]),
    )

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_MERGE_FORECAST},
    )

    result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        {
            CONF_NAME: "Merge Forecast",
            CONF_SOURCE_ENTITIES: [
                "sensor.merge_primary",
                "sensor.merge_primary",
            ],
            CONF_INTERPOLATION_MODE: INTERPOLATION_MODE_PREVIOUS,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_SOURCE_ENTITIES: "duplicate_entities"}


async def test_merge_forecast_rejects_non_forecast_source(hass):
    """Merge flow requires every selected source to expose a forecast list."""
    hass.states.async_set("sensor.not_forecast", "1", {"unit_of_measurement": "$"})

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    kind_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {CONF_HELPER_KIND: HELPER_KIND_MERGE_FORECAST},
    )

    result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        {
            CONF_NAME: "Merge Forecast",
            CONF_SOURCE_ENTITIES: ["sensor.not_forecast"],
            CONF_INTERPOLATION_MODE: INTERPOLATION_MODE_PREVIOUS,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_SOURCE_ENTITIES: "entity_not_forecast"}


def test_recent_days_normalize_clamps_recent_bias():
    """Recent-days normalization clamps bias to the documented percentage range."""
    base_input = {
        CONF_RECENT_SOURCE_ENTITY: "sensor.recent_load",
        CONF_RECENT_HISTORY_DAYS: 3,
        CONF_RECENT_FORECAST_HORIZON_HOURS: 48,
    }

    high_result = normalize_recent_days_user_input(
        {**base_input, CONF_RECENT_BIAS_PCT: 250}
    )
    low_result = normalize_recent_days_user_input(
        {**base_input, CONF_RECENT_BIAS_PCT: -5}
    )

    assert high_result[CONF_RECENT_BIAS_PCT] == 100.0
    assert low_result[CONF_RECENT_BIAS_PCT] == 0.0


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
    """Choose selector requires a selected entity payload."""
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

    form_data = {
        CONF_NAME: "Risk Helper",
        CONF_RISK_SOURCE_ENTITY: "sensor.risk_forecast",
        CONF_BASIS_BIAS_INPUT: {
            "active_choice": BIAS_SOURCE_ENTITY,
            BIAS_SOURCE_ENTITY: "",
        },
        CONF_RISK_BIAS_INPUT: {
            "active_choice": BIAS_SOURCE_CONSTANT,
            BIAS_SOURCE_CONSTANT: 20.0,
        },
        CONF_RAMP_START_AFTER_MINUTES: 30,
        CONF_RAMP_DURATION_MINUTES: 90,
        CONF_CURVE: CURVE_LINEAR,
    }
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            kind_result["flow_id"],
            form_data,
        )


async def test_risk_create_rejects_non_numeric_entity_state(
    hass,
    forecast_points_factory,
    source_state_factory,
):
    """Choose selector rejects non-numeric entity states."""
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

    form_data = {
        CONF_NAME: "Risk Helper",
        CONF_RISK_SOURCE_ENTITY: "sensor.risk_forecast",
        CONF_BASIS_BIAS_INPUT: {
            "active_choice": BIAS_SOURCE_ENTITY,
            BIAS_SOURCE_ENTITY: "input_number.bias",
        },
        CONF_RISK_BIAS_INPUT: {
            "active_choice": BIAS_SOURCE_CONSTANT,
            BIAS_SOURCE_CONSTANT: 20.0,
        },
        CONF_RAMP_START_AFTER_MINUTES: 30,
        CONF_RAMP_DURATION_MINUTES: 90,
        CONF_CURVE: CURVE_LINEAR,
    }
    expected_error = {CONF_BASIS_BIAS_INPUT: "entity_not_number"}
    result = await hass.config_entries.flow.async_configure(
        kind_result["flow_id"],
        form_data,
    )

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


async def test_options_flow_routes_to_correct_step_for_merge_forecast(
    hass, mock_entry_factory
):
    """Options flow for merge entries opens merge-forecast step."""
    entry = mock_entry_factory(
        title="Merge",
        data={
            CONF_HELPER_KIND: HELPER_KIND_MERGE_FORECAST,
            CONF_SOURCE_ENTITIES: [
                "sensor.primary_forecast",
                "sensor.secondary_forecast",
            ],
            CONF_INTERPOLATION_MODE: INTERPOLATION_MODE_PREVIOUS,
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == HELPER_KIND_MERGE_FORECAST


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
