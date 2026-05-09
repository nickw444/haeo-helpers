"""Behavior-focused tests for realtime forecast smoothing helper sensor."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from custom_components.haeo_helpers.helpers.realtime_forecast_smoothing import (
    sensor as smoothing_sensor_module,
)
from custom_components.haeo_helpers.helpers.realtime_forecast_smoothing.const import (
    ATTR_APPLIED_REALTIME_VALUE,
    ATTR_FORECAST,
    ATTR_SMOOTHING_WINDOW_MINUTES,
    CONF_FORECAST_ENTITY,
    CONF_REALTIME_ENTITY,
    CONF_SMOOTHING_WINDOW_MINUTES,
)
from custom_components.haeo_helpers.helpers.realtime_forecast_smoothing.sensor import (
    RealtimeForecastSmoothingSensor,
)


def _create_sensor(
    hass,
    mock_entry_factory,
    *,
    forecast_entity: str = "sensor.smoothing_forecast",
    realtime_entity: str = "sensor.smoothing_realtime",
    smoothing_window_minutes: int = 180,
):
    data = {
        CONF_FORECAST_ENTITY: forecast_entity,
        CONF_REALTIME_ENTITY: realtime_entity,
        CONF_SMOOTHING_WINDOW_MINUTES: smoothing_window_minutes,
    }
    entry = mock_entry_factory(data=data, title="Realtime Smoothing")
    return RealtimeForecastSmoothingSensor(hass, entry)


@pytest.fixture
def patch_smoothing_now(monkeypatch, fixed_now):
    """Patch dt_util.now used in smoothing sensor module to a fixed time."""
    monkeypatch.setattr(smoothing_sensor_module.dt_util, "now", lambda: fixed_now)


async def test_realtime_value_is_smoothed_into_near_term_forecast(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    assert_forecast_values,
    patch_smoothing_now,
):
    """High realtime values are faded back to the source forecast over the window."""
    source_state_factory(
        "sensor.smoothing_forecast",
        state="1.0",
        forecast=forecast_points_factory(
            [(0, 1.0), (30, 0.5), (60, 0.8), (90, 0.7), (180, 0.6)]
        ),
        attributes={
            "unit_of_measurement": "kW",
            "device_class": "power",
            "region": "house",
        },
    )
    hass.states.async_set(
        "sensor.smoothing_realtime", "4.0", {"unit_of_measurement": "kW"}
    )
    sensor = _create_sensor(hass, mock_entry_factory, smoothing_window_minutes=180)

    assert sensor.available is True
    assert sensor.native_value == pytest.approx(4.0, rel=1e-6, abs=1e-6)

    attrs = sensor.extra_state_attributes

    assert attrs["unit_of_measurement"] == "kW"
    assert attrs["device_class"] == "power"
    assert attrs["region"] == "house"
    assert attrs[ATTR_APPLIED_REALTIME_VALUE] == pytest.approx(4.0)
    assert attrs[ATTR_SMOOTHING_WINDOW_MINUTES] == 180
    assert_forecast_values(
        attrs[ATTR_FORECAST],
        [4.0, 3.4166666667, 2.9333333333, 2.35, 0.6],
    )


async def test_realtime_below_forecast_does_not_reduce_forecast(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    assert_forecast_values,
    patch_smoothing_now,
):
    """Smoothing only raises forecasts toward realtime; it does not lower them."""
    source_state_factory(
        "sensor.smoothing_forecast",
        forecast=forecast_points_factory([(0, 3.0), (30, 2.0)]),
    )
    hass.states.async_set("sensor.smoothing_realtime", "1.0", {})
    sensor = _create_sensor(hass, mock_entry_factory, smoothing_window_minutes=180)

    attrs = sensor.extra_state_attributes

    assert_forecast_values(attrs[ATTR_FORECAST], [3.0, 2.0])
    assert sensor.native_value == pytest.approx(1.0, rel=1e-6, abs=1e-6)


async def test_invalid_forecast_points_are_preserved(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_smoothing_now,
):
    """Invalid forecast points pass through unchanged."""
    source_state_factory(
        "sensor.smoothing_forecast",
        forecast=[
            "unexpected",
            {"time": "not-a-time", "value": 1.0},
            {"time": forecast_points_factory([(0, 1.0)])[0]["time"], "value": "bad"},
            forecast_points_factory([(30, 0.5)])[0],
        ],
    )
    hass.states.async_set("sensor.smoothing_realtime", "4.0", {})
    sensor = _create_sensor(hass, mock_entry_factory, smoothing_window_minutes=180)

    forecast = sensor.extra_state_attributes[ATTR_FORECAST]

    assert forecast[0] == "unexpected"
    assert forecast[1] == {"time": "not-a-time", "value": 1.0}
    assert forecast[2]["value"] == "bad"
    assert forecast[3]["value"] == pytest.approx(3.4166666667, rel=1e-6, abs=1e-6)


async def test_available_false_when_realtime_source_is_not_numeric(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
):
    """Availability is false when realtime source cannot be parsed."""
    source_state_factory(
        "sensor.smoothing_forecast",
        forecast=forecast_points_factory([(0, 1.0)]),
    )
    hass.states.async_set("sensor.smoothing_realtime", "unknown", {})
    sensor = _create_sensor(hass, mock_entry_factory)

    assert sensor.available is False
    assert sensor.native_value is None
    assert ATTR_FORECAST in sensor.extra_state_attributes


async def test_source_state_change_tracks_forecast_and_realtime_entities(
    hass,
    mock_entry_factory,
):
    """Forecast and realtime source changes should refresh HA state."""
    sensor = _create_sensor(hass, mock_entry_factory)
    write_mock = Mock()
    sensor.async_write_ha_state = write_mock

    assert sensor._tracked_entity_ids() == [
        "sensor.smoothing_forecast",
        "sensor.smoothing_realtime",
    ]

    sensor._handle_state_change(Mock())

    write_mock.assert_called_once_with()
