"""Math-focused tests for forecast statistic helper sensor."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from custom_components.haeo_helpers.helpers.forecast_statistic.const import (
    AGGREGATION_MEAN,
    AGGREGATION_PERCENTILE,
    ATTR_BASE_VALUE,
    ATTR_SAMPLE_COUNT,
    CONF_ADJUSTMENT,
    CONF_AGGREGATION,
    CONF_PERCENTILE,
    CONF_SOURCE_ENTITY,
)
from custom_components.haeo_helpers.helpers.forecast_statistic.sensor import (
    ForecastStatisticSensor,
    _calculate_percentile,
)


def _create_sensor(
    hass,
    mock_entry_factory,
    *,
    source_entity="sensor.stat_source",
    aggregation=AGGREGATION_PERCENTILE,
    percentile=50,
    adjustment=0.0,
):
    data = {
        CONF_SOURCE_ENTITY: source_entity,
        CONF_AGGREGATION: aggregation,
        CONF_PERCENTILE: percentile,
        CONF_ADJUSTMENT: adjustment,
    }
    entry = mock_entry_factory(data=data, title="Statistic")
    return ForecastStatisticSensor(hass, entry)


async def test_percentile_linear_interpolation_even_count(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
):
    """Median percentile interpolates correctly for an even number of points."""
    source_state_factory(
        "sensor.stat_source",
        forecast=forecast_points_factory([(0, 1.0), (5, 2.0), (10, 3.0), (15, 4.0)]),
    )
    sensor = _create_sensor(hass, mock_entry_factory, percentile=50)

    assert sensor.native_value == 2.5


async def test_percentile_linear_interpolation_odd_count(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
):
    """Median percentile returns the middle item for odd point counts."""
    source_state_factory(
        "sensor.stat_source",
        forecast=forecast_points_factory(
            [(0, 1.0), (5, 2.0), (10, 3.0), (15, 4.0), (20, 5.0)]
        ),
    )
    sensor = _create_sensor(hass, mock_entry_factory, percentile=50)

    assert sensor.native_value == 3.0


def test_percentile_clamps_below_zero_and_above_hundred():
    """Percentile helper clamps out-of-range percentile values."""
    values = [1.0, 2.0, 3.0, 4.0]

    assert _calculate_percentile(values, -10) == 1.0
    assert _calculate_percentile(values, 120) == 4.0


def test_percentile_single_value_returns_same_value():
    """Percentile helper returns the only value for singleton inputs."""
    assert _calculate_percentile([7.25], 75) == 7.25


async def test_mean_mode_uses_fmean(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
):
    """Mean mode returns arithmetic mean of valid forecast values."""
    source_state_factory(
        "sensor.stat_source",
        forecast=forecast_points_factory([(0, 2.0), (5, 4.0), (10, 8.0)]),
    )
    sensor = _create_sensor(hass, mock_entry_factory, aggregation=AGGREGATION_MEAN)

    assert sensor.native_value == 14.0 / 3.0


async def test_adjustment_is_added_after_aggregation(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
):
    """Adjustment is applied after percentile/mean computation."""
    source_state_factory(
        "sensor.stat_source",
        forecast=forecast_points_factory([(0, 1.0), (5, 3.0), (10, 5.0)]),
    )
    sensor = _create_sensor(
        hass,
        mock_entry_factory,
        aggregation=AGGREGATION_MEAN,
        adjustment=1.5,
    )

    assert sensor.native_value == pytest.approx(4.5, rel=1e-6, abs=1e-6)


async def test_ignores_invalid_forecast_points(
    hass, mock_entry_factory, source_state_factory
):
    """Invalid forecast points are ignored while valid numeric points are used."""
    source_state_factory(
        "sensor.stat_source",
        forecast=[
            {"time": "2026-01-01T12:00:00+00:00", "value": 1.0},
            {"time": "2026-01-01T12:05:00+00:00"},
            {"time": "2026-01-01T12:10:00+00:00", "value": True},
            {"time": "2026-01-01T12:15:00+00:00", "value": float("nan")},
            {"time": "2026-01-01T12:20:00+00:00", "value": float("inf")},
            {"time": "2026-01-01T12:25:00+00:00", "value": 3.0},
            "not_a_dict",
        ],
    )
    sensor = _create_sensor(hass, mock_entry_factory, aggregation=AGGREGATION_MEAN)

    assert sensor.native_value == 2.0


async def test_returns_none_when_no_valid_points(
    hass, mock_entry_factory, source_state_factory
):
    """Sensor returns None when forecast contains no usable numeric values."""
    source_state_factory(
        "sensor.stat_source",
        forecast=[{"time": "2026-01-01T12:00:00+00:00", "value": "bad"}],
    )
    sensor = _create_sensor(hass, mock_entry_factory)

    assert sensor.native_value is None


async def test_extra_attributes_include_base_and_sample_count(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
):
    """Extra attributes expose base value and sample count."""
    source_state_factory(
        "sensor.stat_source",
        forecast=forecast_points_factory([(0, 10.0), (5, 20.0), (10, 30.0)]),
    )
    sensor = _create_sensor(hass, mock_entry_factory, percentile=50, adjustment=5.0)

    assert sensor.native_value == 25.0
    attrs = sensor.extra_state_attributes

    assert attrs[ATTR_SAMPLE_COUNT] == 3
    assert attrs[ATTR_BASE_VALUE] == 20.0


async def test_available_false_for_missing_unknown_unavailable_source(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
):
    """Availability tracks missing and unavailable source states."""
    sensor = _create_sensor(hass, mock_entry_factory)
    assert sensor.available is False

    source_state_factory("sensor.stat_source", state=STATE_UNKNOWN, forecast=[])
    assert sensor.available is False

    source_state_factory("sensor.stat_source", state=STATE_UNAVAILABLE, forecast=[])
    assert sensor.available is False

    source_state_factory(
        "sensor.stat_source",
        state="10",
        forecast=forecast_points_factory([(0, 1.0)]),
    )
    assert sensor.available is True


async def test_source_unit_and_device_class_are_propagated(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
):
    """Unit and device_class are copied from source state attributes."""
    source_state_factory(
        "sensor.stat_source",
        forecast=forecast_points_factory([(0, 1.0)]),
        attributes={"unit_of_measurement": "$/kWh", "device_class": "monetary"},
    )

    sensor = _create_sensor(hass, mock_entry_factory)

    assert sensor.native_unit_of_measurement == "$/kWh"
    assert sensor.device_class == "monetary"


async def test_state_updates_on_source_state_change_event(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
):
    """Source-change callback refreshes metadata and schedules state write."""
    source_state_factory(
        "sensor.stat_source",
        forecast=forecast_points_factory([(0, 1.0)]),
        attributes={"unit_of_measurement": "$/kWh"},
    )
    sensor = _create_sensor(hass, mock_entry_factory)

    source_state_factory(
        "sensor.stat_source",
        forecast=forecast_points_factory([(0, 1.0)]),
        attributes={"unit_of_measurement": "c/kWh"},
    )

    with patch.object(sensor, "async_write_ha_state") as mock_write:
        sensor._handle_source_state_change(None)

    assert sensor.native_unit_of_measurement == "c/kWh"
    mock_write.assert_called_once()
