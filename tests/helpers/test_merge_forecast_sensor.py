"""Behavior-focused tests for merge forecast helper sensor."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from homeassistant.const import STATE_UNAVAILABLE

from custom_components.haeo_helpers.helpers.merge_forecast import (
    sensor as merge_sensor_module,
)
from custom_components.haeo_helpers.helpers.merge_forecast.const import (
    ATTR_FORECAST,
    ATTR_INTERPOLATION_MODE,
    ATTR_MERGED_SOURCE_COUNT,
    ATTR_SOURCE_ENTITIES,
    CONF_INTERPOLATION_MODE,
    CONF_SOURCE_ENTITIES,
    INTERPOLATION_MODE_LINEAR,
    INTERPOLATION_MODE_PREVIOUS,
)
from custom_components.haeo_helpers.helpers.merge_forecast.sensor import (
    MergeForecastSensor,
)


def _create_sensor(
    hass,
    mock_entry_factory,
    *,
    source_entities: list[str] | None = None,
    interpolation_mode: str = INTERPOLATION_MODE_PREVIOUS,
):
    """Create a merge forecast sensor for tests."""
    data = {
        CONF_SOURCE_ENTITIES: source_entities
        or ["sensor.primary_forecast", "sensor.secondary_forecast"],
        CONF_INTERPOLATION_MODE: interpolation_mode,
    }
    entry = mock_entry_factory(data=data, title="Merge")
    return MergeForecastSensor(hass, entry)


@pytest.fixture
def patch_merge_now(monkeypatch, fixed_now):
    """Patch dt_util.now used in merge sensor module to a fixed time."""
    monkeypatch.setattr(merge_sensor_module.dt_util, "now", lambda: fixed_now)


async def test_primary_source_wins_overlapping_segments_and_secondary_fills_tail(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    assert_forecast_values,
    patch_merge_now,
):
    """Earlier sources take precedence, later sources fill uncovered segments."""
    source_state_factory(
        "sensor.primary_forecast",
        forecast=forecast_points_factory([(0, 1.0), (60, 2.0), (120, 3.0)]),
    )
    source_state_factory(
        "sensor.secondary_forecast",
        forecast=forecast_points_factory([(60, 20.0), (120, 30.0), (180, 40.0)]),
    )
    sensor = _create_sensor(hass, mock_entry_factory)

    attrs = sensor.extra_state_attributes

    assert sensor.available is True
    assert_forecast_values(attrs[ATTR_FORECAST], [1.0, 2.0, 30.0, 40.0])
    assert [point["source"] for point in attrs[ATTR_FORECAST]] == [
        "primary_forecast",
        "primary_forecast",
        "secondary_forecast",
        "secondary_forecast",
    ]
    assert attrs[ATTR_MERGED_SOURCE_COUNT] == 2


async def test_primary_source_granularity_is_preserved_when_values_repeat(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    assert_forecast_values,
    patch_merge_now,
):
    """High-resolution source boundaries are kept even when values repeat."""
    source_state_factory(
        "sensor.primary_forecast",
        forecast=forecast_points_factory(
            [
                (0, 1.0),
                (30, 1.0),
                (60, 1.0),
                (90, 1.0),
                (120, 2.0),
            ]
        ),
    )
    source_state_factory(
        "sensor.secondary_forecast",
        forecast=forecast_points_factory([(0, 10.0), (120, 20.0), (180, 30.0)]),
    )
    sensor = _create_sensor(hass, mock_entry_factory)

    forecast = sensor.extra_state_attributes[ATTR_FORECAST]

    assert [point["time"] for point in forecast[:5]] == [
        point["time"]
        for point in forecast_points_factory(
            [(0, 0), (30, 0), (60, 0), (90, 0), (120, 0)]
        )
    ]
    assert_forecast_values(forecast, [1.0, 1.0, 1.0, 1.0, 20.0, 30.0])


async def test_past_forecast_points_are_trimmed_to_now(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    assert_forecast_values,
    fixed_now,
    patch_merge_now,
):
    """Forecast output should not include timestamps earlier than now."""
    source_state_factory(
        "sensor.primary_forecast",
        forecast=forecast_points_factory([(-60, 1.0), (60, 2.0)]),
    )
    source_state_factory(
        "sensor.secondary_forecast",
        forecast=forecast_points_factory([(-120, 10.0), (120, 20.0)]),
    )
    sensor = _create_sensor(hass, mock_entry_factory)

    forecast = sensor.extra_state_attributes[ATTR_FORECAST]

    assert forecast[0]["time"] == fixed_now.isoformat()
    assert all(point["time"] >= fixed_now.isoformat() for point in forecast)
    assert_forecast_values(forecast, [1.0, 10.0, 20.0])
    assert [point["source"] for point in forecast] == [
        "primary_forecast",
        "secondary_forecast",
        "secondary_forecast",
    ]


async def test_three_sources_respect_order_precedence(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    assert_forecast_values,
    patch_merge_now,
):
    """Each segment is sourced from the earliest configured covering forecast."""
    source_state_factory(
        "sensor.primary_forecast",
        forecast=forecast_points_factory([(0, 1.0), (60, 2.0)]),
    )
    source_state_factory(
        "sensor.secondary_forecast",
        forecast=forecast_points_factory([(0, 10.0), (120, 20.0)]),
    )
    source_state_factory(
        "sensor.tertiary_forecast",
        forecast=forecast_points_factory([(120, 100.0), (180, 200.0)]),
    )
    sensor = _create_sensor(
        hass,
        mock_entry_factory,
        source_entities=[
            "sensor.primary_forecast",
            "sensor.secondary_forecast",
            "sensor.tertiary_forecast",
        ],
    )

    attrs = sensor.extra_state_attributes

    assert_forecast_values(attrs[ATTR_FORECAST], [1.0, 10.0, 100.0, 200.0])
    assert attrs[ATTR_MERGED_SOURCE_COUNT] == 3


async def test_first_source_value_and_metadata_are_passed_through(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_merge_now,
):
    """The merged sensor keeps current value and metadata from the first source."""
    source_state_factory(
        "sensor.primary_forecast",
        state="12.5",
        forecast=forecast_points_factory([(0, 1.0), (60, 2.0)]),
        attributes={
            "unit_of_measurement": "$/kWh",
            "device_class": "monetary",
            "state_class": "measurement",
            "region": "NSW1",
        },
    )
    source_state_factory(
        "sensor.secondary_forecast",
        state="99",
        forecast=forecast_points_factory([(60, 20.0), (120, 30.0)]),
        attributes={"unit_of_measurement": "ignored"},
    )
    sensor = _create_sensor(hass, mock_entry_factory)

    attrs = sensor.extra_state_attributes

    assert sensor.native_value == pytest.approx(12.5, rel=1e-6, abs=1e-6)
    assert sensor.native_unit_of_measurement == "$/kWh"
    assert sensor.device_class == "monetary"
    assert sensor.state_class == "measurement"
    assert attrs["region"] == "NSW1"
    assert attrs[ATTR_SOURCE_ENTITIES] == [
        "sensor.primary_forecast",
        "sensor.secondary_forecast",
    ]


async def test_configured_interpolation_mode_is_exposed_and_used_for_boundaries(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    assert_forecast_values,
    patch_merge_now,
):
    """Linear mode interpolates values at boundaries introduced by other sources."""
    source_state_factory(
        "sensor.primary_forecast",
        forecast=forecast_points_factory([(0, 0.0), (120, 12.0)]),
    )
    source_state_factory(
        "sensor.secondary_forecast",
        forecast=forecast_points_factory([(60, 100.0), (180, 200.0)]),
    )
    sensor = _create_sensor(
        hass,
        mock_entry_factory,
        interpolation_mode=INTERPOLATION_MODE_LINEAR,
    )

    attrs = sensor.extra_state_attributes

    assert attrs[ATTR_INTERPOLATION_MODE] == INTERPOLATION_MODE_LINEAR
    assert_forecast_values(attrs[ATTR_FORECAST], [0.0, 6.0, 150.0, 200.0])
    assert [point["source"] for point in attrs[ATTR_FORECAST]] == [
        "primary_forecast",
        "primary_forecast",
        "secondary_forecast",
        "secondary_forecast",
    ]


async def test_invalid_forecast_points_are_ignored(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    assert_forecast_values,
    patch_merge_now,
):
    """Only valid timestamped numeric forecast points participate in the merge."""
    source_state_factory(
        "sensor.primary_forecast",
        forecast=[
            "unexpected",
            {"time": "not-a-time", "value": 1.0},
            {"time": forecast_points_factory([(0, 1.0)])[0]["time"], "value": "bad"},
            *forecast_points_factory([(0, 1.0), (60, 2.0)]),
        ],
    )
    source_state_factory(
        "sensor.secondary_forecast",
        forecast=forecast_points_factory([(60, 20.0), (120, 30.0)]),
    )
    sensor = _create_sensor(hass, mock_entry_factory)

    attrs = sensor.extra_state_attributes

    assert_forecast_values(attrs[ATTR_FORECAST], [1.0, 20.0, 30.0])


async def test_lower_priority_unavailable_source_does_not_break_valid_merge(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    assert_forecast_values,
    patch_merge_now,
):
    """Unavailable lower-priority sources are ignored."""
    source_state_factory(
        "sensor.primary_forecast",
        forecast=forecast_points_factory([(0, 1.0), (60, 2.0)]),
    )
    source_state_factory(
        "sensor.secondary_forecast",
        state=STATE_UNAVAILABLE,
        forecast=forecast_points_factory([(60, 20.0), (120, 30.0)]),
    )
    sensor = _create_sensor(hass, mock_entry_factory)

    attrs = sensor.extra_state_attributes

    assert sensor.available is True
    assert_forecast_values(attrs[ATTR_FORECAST], [1.0, 2.0])
    assert attrs[ATTR_MERGED_SOURCE_COUNT] == 1


async def test_first_source_unavailable_makes_helper_unavailable(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    patch_merge_now,
):
    """The first source controls the helper's current state availability."""
    source_state_factory(
        "sensor.primary_forecast",
        state=STATE_UNAVAILABLE,
        forecast=forecast_points_factory([(0, 1.0), (60, 2.0)]),
    )
    source_state_factory(
        "sensor.secondary_forecast",
        forecast=forecast_points_factory([(60, 20.0), (120, 30.0)]),
    )
    sensor = _create_sensor(hass, mock_entry_factory)

    assert sensor.available is False
    assert sensor.native_value is None


async def test_source_state_change_tracks_all_configured_sources(
    hass,
    mock_entry_factory,
):
    """All configured sources should trigger state refreshes."""
    sensor = _create_sensor(
        hass,
        mock_entry_factory,
        source_entities=[
            "sensor.primary_forecast",
            "sensor.secondary_forecast",
            "sensor.primary_forecast",
        ],
    )
    write_mock = Mock()
    sensor.async_write_ha_state = write_mock

    assert sensor._tracked_entity_ids() == [
        "sensor.primary_forecast",
        "sensor.secondary_forecast",
    ]

    sensor._handle_state_change(Mock())

    write_mock.assert_called_once_with()
