"""Math-focused tests for forecast risk adjustment helper sensor."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest

from custom_components.haeo_helpers.helpers.forecast_risk_adjustment import (
    sensor as risk_sensor_module,
)
from custom_components.haeo_helpers.helpers.forecast_risk_adjustment.const import (
    ATTR_APPLIED_BASIS_BIAS_PCT,
    ATTR_APPLIED_RISK_BIAS_PCT,
    ATTR_CURVE,
    ATTR_FORECAST,
    ATTR_RAMP_DURATION_MINUTES,
    ATTR_RAMP_START_AFTER_MINUTES,
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
)
from custom_components.haeo_helpers.helpers.forecast_risk_adjustment.sensor import (
    ForecastRiskAdjustmentSensor,
)


def _create_sensor(
    hass, mock_entry_factory, *, source_entity="sensor.risk_source", **overrides
):
    basis_bias_source = overrides.pop("basis_bias_source", BIAS_SOURCE_CONSTANT)
    basis_bias_pct = overrides.pop("basis_bias_pct", 0.0)
    basis_bias_entity = overrides.pop("basis_bias_entity", None)
    risk_bias_source = overrides.pop("risk_bias_source", BIAS_SOURCE_CONSTANT)
    risk_bias_pct = overrides.pop("risk_bias_pct", 0.0)
    risk_bias_entity = overrides.pop("risk_bias_entity", None)
    ramp_start_after_minutes = overrides.pop("ramp_start_after_minutes", 30)
    ramp_duration_minutes = overrides.pop("ramp_duration_minutes", 90)
    curve = overrides.pop("curve", CURVE_LINEAR)

    data = {
        CONF_SOURCE_ENTITY: source_entity,
        CONF_BASIS_BIAS_SOURCE: basis_bias_source,
        CONF_BASIS_BIAS_PCT: basis_bias_pct,
        CONF_BASIS_BIAS_ENTITY: basis_bias_entity,
        CONF_RISK_BIAS_SOURCE: risk_bias_source,
        CONF_RISK_BIAS_PCT: risk_bias_pct,
        CONF_RISK_BIAS_ENTITY: risk_bias_entity,
        CONF_RAMP_START_AFTER_MINUTES: ramp_start_after_minutes,
        CONF_RAMP_DURATION_MINUTES: ramp_duration_minutes,
        CONF_CURVE: curve,
    }
    data.update(overrides)
    entry = mock_entry_factory(data=data, title="Risk")
    return ForecastRiskAdjustmentSensor(hass, entry)


@pytest.fixture
def patch_risk_now(monkeypatch, fixed_now):
    """Patch dt_util.now used in risk sensor module to a fixed time."""
    monkeypatch.setattr(risk_sensor_module.dt_util, "now", lambda: fixed_now)


async def test_basis_bias_constant_applies_uniformly_to_all_points(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    assert_forecast_values,
    patch_risk_now,
):
    """Basis bias is applied evenly over all forecast points."""
    source_state_factory(
        "sensor.risk_source",
        forecast=forecast_points_factory([(0, 100.0), (60, 80.0)]),
        attributes={"currency": "AUD"},
    )
    sensor = _create_sensor(hass, mock_entry_factory, basis_bias_pct=10.0)

    attrs = sensor.extra_state_attributes
    assert_forecast_values(attrs[ATTR_FORECAST], [110.0, 88.0])


async def test_risk_bias_ramp_before_start_is_zero_effect(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_risk_now,
):
    """Risk bias has zero effect before configured ramp start."""
    source_state_factory(
        "sensor.risk_source", forecast=forecast_points_factory([(10, 100.0)])
    )
    sensor = _create_sensor(
        hass,
        mock_entry_factory,
        risk_bias_pct=20.0,
        ramp_start_after_minutes=30,
        ramp_duration_minutes=90,
    )

    assert sensor.native_value == pytest.approx(100.0, rel=1e-6, abs=1e-6)


async def test_risk_bias_ramp_midpoint_is_partial_effect(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_risk_now,
):
    """Risk bias at midpoint of linear ramp applies at 50% intensity."""
    source_state_factory(
        "sensor.risk_source", forecast=forecast_points_factory([(75, 100.0)])
    )
    sensor = _create_sensor(
        hass,
        mock_entry_factory,
        risk_bias_pct=20.0,
        ramp_start_after_minutes=30,
        ramp_duration_minutes=90,
    )

    assert sensor.native_value == pytest.approx(110.0, rel=1e-6, abs=1e-6)


async def test_risk_bias_after_ramp_end_is_full_effect(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_risk_now,
):
    """Risk bias applies at 100% once ramp period has elapsed."""
    source_state_factory(
        "sensor.risk_source", forecast=forecast_points_factory([(150, 100.0)])
    )
    sensor = _create_sensor(
        hass,
        mock_entry_factory,
        risk_bias_pct=20.0,
        ramp_start_after_minutes=30,
        ramp_duration_minutes=90,
    )

    assert sensor.native_value == pytest.approx(120.0, rel=1e-6, abs=1e-6)


async def test_combined_basis_and_risk_bias_formula(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_risk_now,
):
    """Adjusted value combines basis bias and full risk bias percentages."""
    source_state_factory(
        "sensor.risk_source", forecast=forecast_points_factory([(150, 100.0)])
    )
    sensor = _create_sensor(
        hass,
        mock_entry_factory,
        basis_bias_pct=25.0,
        risk_bias_pct=20.0,
        ramp_start_after_minutes=30,
        ramp_duration_minutes=90,
    )

    assert sensor.native_value == pytest.approx(145.0, rel=1e-6, abs=1e-6)


async def test_zero_ramp_duration_switches_to_full_after_start(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_risk_now,
):
    """Zero ramp duration applies full risk immediately after ramp start."""
    source_state_factory(
        "sensor.risk_source", forecast=forecast_points_factory([(31, 100.0)])
    )
    sensor = _create_sensor(
        hass,
        mock_entry_factory,
        risk_bias_pct=20.0,
        ramp_start_after_minutes=30,
        ramp_duration_minutes=0,
    )

    assert sensor.native_value == pytest.approx(120.0, rel=1e-6, abs=1e-6)


async def test_past_points_do_not_receive_risk_effect(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_risk_now,
):
    """Forecast points in the past keep zero ramp risk contribution."""
    source_state_factory(
        "sensor.risk_source", forecast=forecast_points_factory([(-10, 100.0)])
    )
    sensor = _create_sensor(
        hass,
        mock_entry_factory,
        basis_bias_pct=10.0,
        risk_bias_pct=20.0,
        ramp_start_after_minutes=30,
        ramp_duration_minutes=90,
    )

    assert sensor.native_value == pytest.approx(110.0, rel=1e-6, abs=1e-6)


async def test_entity_based_basis_bias_is_used_when_configured(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_risk_now,
):
    """Entity-backed basis bias overrides constant basis value."""
    hass.states.async_set("input_number.basis", "10", {})
    source_state_factory(
        "sensor.risk_source", forecast=forecast_points_factory([(0, 100.0)])
    )

    sensor = _create_sensor(
        hass,
        mock_entry_factory,
        basis_bias_source=BIAS_SOURCE_ENTITY,
        basis_bias_entity="input_number.basis",
        basis_bias_pct=0.0,
    )

    assert sensor.native_value == pytest.approx(110.0, rel=1e-6, abs=1e-6)


async def test_entity_based_risk_bias_is_used_when_configured(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_risk_now,
):
    """Entity-backed risk bias overrides constant risk value."""
    hass.states.async_set("input_number.risk", "20", {})
    source_state_factory(
        "sensor.risk_source", forecast=forecast_points_factory([(150, 100.0)])
    )

    sensor = _create_sensor(
        hass,
        mock_entry_factory,
        risk_bias_source=BIAS_SOURCE_ENTITY,
        risk_bias_entity="input_number.risk",
        risk_bias_pct=0.0,
    )

    assert sensor.native_value == pytest.approx(120.0, rel=1e-6, abs=1e-6)


async def test_available_false_when_required_bias_entity_missing_or_non_numeric(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_risk_now,
):
    """Availability is false for missing/non-numeric entity-based bias sources."""
    source_state_factory(
        "sensor.risk_source", forecast=forecast_points_factory([(0, 100.0)])
    )

    missing_entity_sensor = _create_sensor(
        hass,
        mock_entry_factory,
        basis_bias_source=BIAS_SOURCE_ENTITY,
        basis_bias_entity="input_number.missing",
    )
    assert missing_entity_sensor.available is False

    hass.states.async_set("input_number.bad", "not_a_number", {})
    non_numeric_sensor = _create_sensor(
        hass,
        mock_entry_factory,
        basis_bias_source=BIAS_SOURCE_ENTITY,
        basis_bias_entity="input_number.bad",
    )
    assert non_numeric_sensor.available is False


async def test_extra_attributes_proxy_source_and_replace_forecast(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_risk_now,
):
    """Extra attrs preserve source attrs and expose adjusted forecast diagnostics."""
    source_state_factory(
        "sensor.risk_source",
        forecast=forecast_points_factory([(150, 100.0)]),
        attributes={"currency": "AUD", "other_attr": 42},
    )
    sensor = _create_sensor(
        hass,
        mock_entry_factory,
        basis_bias_pct=10.0,
        risk_bias_pct=20.0,
    )

    attrs = sensor.extra_state_attributes

    assert attrs["currency"] == "AUD"
    assert attrs["other_attr"] == 42
    assert attrs[ATTR_APPLIED_BASIS_BIAS_PCT] == 10.0
    assert attrs[ATTR_APPLIED_RISK_BIAS_PCT] == 20.0
    assert attrs[ATTR_RAMP_START_AFTER_MINUTES] == 30.0
    assert attrs[ATTR_RAMP_DURATION_MINUTES] == 90.0
    assert attrs[ATTR_CURVE] == CURVE_LINEAR
    assert attrs[ATTR_FORECAST][0]["value"] == pytest.approx(130.0, rel=1e-6, abs=1e-6)


async def test_preserves_non_forecast_attributes_from_source(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_risk_now,
):
    """Non-forecast source attributes are passed through unchanged."""
    source_state_factory(
        "sensor.risk_source",
        forecast=forecast_points_factory([(0, 100.0)]),
        attributes={"region": "nsw1", "friendly_name": "Risk Source"},
    )
    sensor = _create_sensor(hass, mock_entry_factory)

    attrs = sensor.extra_state_attributes

    assert attrs["region"] == "nsw1"
    assert attrs["friendly_name"] == "Risk Source"


async def test_invalid_forecast_points_are_passed_through_unchanged(
    hass,
    mock_entry_factory,
    fixed_now,
    source_state_factory,
    patch_risk_now,
):
    """Invalid dict points are left unchanged in adjusted forecast output."""
    valid_time = (fixed_now + timedelta(minutes=60)).isoformat()
    source_forecast = [
        {"time": valid_time, "value": 100.0},
        {"time": valid_time, "value": "bad"},
        {"time": "not-a-time", "value": 200.0},
        {"time": valid_time},
    ]
    source_state_factory("sensor.risk_source", forecast=source_forecast)

    sensor = _create_sensor(hass, mock_entry_factory, basis_bias_pct=10.0)
    attrs = sensor.extra_state_attributes
    adjusted_forecast = attrs[ATTR_FORECAST]

    assert adjusted_forecast[0]["value"] == pytest.approx(110.0, rel=1e-6, abs=1e-6)
    assert adjusted_forecast[1] == source_forecast[1]
    assert adjusted_forecast[2] == source_forecast[2]
    assert adjusted_forecast[3] == source_forecast[3]


async def test_native_value_uses_point_closest_to_now(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_risk_now,
):
    """Native value resolves from adjusted forecast point nearest to current time."""
    source_state_factory(
        "sensor.risk_source",
        forecast=forecast_points_factory([(-5, 50.0), (2, 200.0), (15, 300.0)]),
    )
    sensor = _create_sensor(hass, mock_entry_factory, basis_bias_pct=10.0)

    assert sensor.native_value == pytest.approx(220.0, rel=1e-6, abs=1e-6)


async def test_parses_iso_time_and_datetime_objects_consistently(
    hass,
    mock_entry_factory,
    fixed_now,
    source_state_factory,
    assert_forecast_values,
    patch_risk_now,
):
    """ISO timestamp strings and datetime objects are both handled correctly."""
    point_dt = fixed_now + timedelta(minutes=60)
    source_state_factory(
        "sensor.risk_source",
        forecast=[
            {"time": point_dt.isoformat(), "value": 100.0},
            {"time": point_dt, "value": 200.0},
        ],
    )
    sensor = _create_sensor(hass, mock_entry_factory, basis_bias_pct=10.0)

    attrs = sensor.extra_state_attributes
    assert_forecast_values(attrs[ATTR_FORECAST], [110.0, 220.0])


async def test_state_updates_on_source_or_bias_entity_change_event(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_risk_now,
):
    """Change callback refreshes metadata and schedules state write."""
    source_state_factory(
        "sensor.risk_source",
        forecast=forecast_points_factory([(0, 1.0)]),
        attributes={"unit_of_measurement": "$/kWh"},
    )
    sensor = _create_sensor(hass, mock_entry_factory)

    source_state_factory(
        "sensor.risk_source",
        forecast=forecast_points_factory([(0, 1.0)]),
        attributes={"unit_of_measurement": "c/kWh"},
    )

    with patch.object(sensor, "async_write_ha_state") as mock_write:
        sensor._handle_state_change(None)

    assert sensor.native_unit_of_measurement == "c/kWh"
    mock_write.assert_called_once()
