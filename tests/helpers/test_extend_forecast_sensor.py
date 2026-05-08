"""Behavior-focused tests for extend forecast helper sensor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import State

from custom_components.haeo_helpers.helpers.extend_forecast import (
    sensor as extend_sensor_module,
)
from custom_components.haeo_helpers.helpers.extend_forecast.const import (
    ATTR_FORECAST,
    CONF_FORECAST_HORIZON_HOURS,
    CONF_HISTORY_DAYS,
    CONF_SOURCE_ENTITY,
)
from custom_components.haeo_helpers.helpers.extend_forecast.sensor import (
    ExtendForecastSensor,
)


def _create_sensor(
    hass,
    mock_entry_factory,
    *,
    source_entity: str = "sensor.extend_source",
    forecast_horizon_hours: int = 8,
    history_days: int = 1,
):
    data = {
        CONF_SOURCE_ENTITY: source_entity,
        CONF_FORECAST_HORIZON_HOURS: forecast_horizon_hours,
        CONF_HISTORY_DAYS: history_days,
    }
    entry = mock_entry_factory(data=data, title="Extend")
    return ExtendForecastSensor(hass, entry)


@pytest.fixture
def patch_extend_now(monkeypatch, fixed_now):
    """Patch dt_util.now used in extend sensor module to a fixed time."""
    monkeypatch.setattr(extend_sensor_module.dt_util, "now", lambda: fixed_now)


def _history_state_series(start, end):
    """Build hourly state history entries covering a single day."""
    states = []
    cursor = start
    while cursor < end:
        states.append(
            State(
                "sensor.extend_source",
                str(cursor.hour),
                {},
                last_changed=cursor,
                last_reported=cursor,
                last_updated=cursor,
            )
        )
        cursor += timedelta(hours=1)
    return states


async def test_extra_attributes_preserve_source_attrs_and_extend_forecast(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    assert_forecast_values,
    fixed_now,
    patch_extend_now,
    monkeypatch,
):
    """History-backed projection is cached by async_update, not property access."""
    source_state_factory(
        "sensor.extend_source",
        state="42.5",
        forecast=forecast_points_factory(
            [(0, 100.0), (60, 101.0), (120, 102.0), (180, 103.0)]
        ),
        attributes={
            "unit_of_measurement": "$/kWh",
            "device_class": "monetary",
            "region": "nsw1",
        },
    )

    history_mock = Mock(
        return_value={
            "sensor.extend_source": _history_state_series(
                fixed_now - timedelta(days=1),
                fixed_now,
            )
        }
    )
    monkeypatch.setattr(
        extend_sensor_module,
        "state_changes_during_period",
        history_mock,
    )

    executor_mock = AsyncMock(side_effect=lambda func, *args: func(*args))
    monkeypatch.setattr(hass, "async_add_executor_job", executor_mock)

    sensor = _create_sensor(hass, mock_entry_factory)

    _ = sensor.available
    _ = sensor.native_value
    _ = sensor.extra_state_attributes
    history_mock.assert_not_called()
    executor_mock.assert_not_awaited()

    await sensor.async_update()

    executor_mock.assert_awaited_once()
    assert sensor.available is True
    assert sensor.native_value == pytest.approx(42.5, rel=1e-6, abs=1e-6)

    attrs = sensor.extra_state_attributes

    history_mock.assert_called_once()
    call_args = history_mock.call_args
    assert call_args.args[0] is hass
    assert call_args.args[1] == fixed_now - timedelta(days=1)
    assert call_args.args[2] == fixed_now
    assert call_args.kwargs["entity_id"] == "sensor.extend_source"
    assert call_args.kwargs["no_attributes"] is True
    assert call_args.kwargs["include_start_time_state"] is True

    assert attrs["unit_of_measurement"] == "$/kWh"
    assert attrs["device_class"] == "monetary"
    assert attrs["region"] == "nsw1"
    assert_forecast_values(
        attrs[ATTR_FORECAST],
        [100.0, 101.0, 102.0, 103.0, 16.0, 17.0, 18.0, 19.0],
    )


async def test_async_setup_entry_requests_update_before_add(
    hass,
    mock_entry_factory,
):
    """Entity setup should request a pre-add update for initial cache fill."""
    entry = mock_entry_factory(
        data={
            CONF_SOURCE_ENTITY: "sensor.extend_source",
            CONF_FORECAST_HORIZON_HOURS: 8,
            CONF_HISTORY_DAYS: 1,
        },
        title="Extend",
    )

    async_add_entities = Mock()

    await extend_sensor_module.async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    call_args = async_add_entities.call_args
    assert len(call_args.args[0]) == 1
    assert isinstance(call_args.args[0][0], ExtendForecastSensor)
    assert call_args.kwargs["update_before_add"] is True


async def test_source_state_change_schedules_forced_refresh(
    hass,
    mock_entry_factory,
):
    """Source changes should trigger a forced async update."""
    sensor = _create_sensor(hass, mock_entry_factory)
    schedule_mock = Mock()
    sensor.async_schedule_update_ha_state = schedule_mock

    sensor._handle_source_state_change(Mock())

    schedule_mock.assert_called_once_with(force_refresh=True)


async def test_available_false_when_source_forecast_is_missing(
    hass,
    mock_entry_factory,
    source_state_factory,
    monkeypatch,
):
    """Availability is false when the source does not expose a forecast list."""
    source_state_factory(
        "sensor.extend_source",
        state="42.5",
        attributes={"unit_of_measurement": "$/kWh"},
    )

    executor_mock = AsyncMock(side_effect=lambda func, *args: func(*args))
    monkeypatch.setattr(hass, "async_add_executor_job", executor_mock)

    sensor = _create_sensor(hass, mock_entry_factory)

    await sensor.async_update()

    executor_mock.assert_not_awaited()
    assert sensor.available is False
    assert sensor.native_value == pytest.approx(42.5, rel=1e-6, abs=1e-6)
    attrs = sensor.extra_state_attributes
    assert attrs["unit_of_measurement"] == "$/kWh"
    assert "forecast" not in attrs


async def test_projection_profile_uses_total_minutes_for_large_intervals(
    hass,
    mock_entry_factory,
    fixed_now,
):
    """Intervals longer than an hour should align buckets from midnight."""
    sensor = _create_sensor(hass, mock_entry_factory)

    profile = sensor._build_projection_profile(
        reference_now=fixed_now.replace(hour=3),
        interval_minutes=90,
        history_entries=[
            (fixed_now.replace(hour=0, minute=45), 10.0),
            (fixed_now.replace(hour=1, minute=30), 20.0),
        ],
    )

    assert profile[0] == pytest.approx(10.0, rel=1e-6, abs=1e-6)
    assert profile[1] == pytest.approx(20.0, rel=1e-6, abs=1e-6)


async def test_history_and_forecast_times_normalize_to_reference_timezone(
    hass,
    mock_entry_factory,
    fixed_now,
    monkeypatch,
):
    """History and forecast timestamps should use the same daily bucket timezone."""
    reference_now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=10)))
    utc_timestamp = datetime(2026, 1, 1, 1, 30, tzinfo=UTC)
    history_mock = Mock(
        return_value={
            "sensor.extend_source": [
                State(
                    "sensor.extend_source",
                    "5",
                    {},
                    last_changed=utc_timestamp,
                    last_reported=utc_timestamp,
                    last_updated=utc_timestamp,
                )
            ]
        }
    )
    monkeypatch.setattr(
        extend_sensor_module,
        "state_changes_during_period",
        history_mock,
    )

    history_entries = extend_sensor_module._history_entries(
        hass=hass,
        entity_id="sensor.extend_source",
        history_days=1,
        reference_now=reference_now,
    )
    parsed_forecast_time = extend_sensor_module._parse_point_time(
        "2026-01-01T01:30:00+00:00",
        reference_now,
    )

    assert history_entries[0][0].tzinfo == reference_now.tzinfo
    assert history_entries[0][0].hour == 11
    assert parsed_forecast_time is not None
    assert parsed_forecast_time.tzinfo == reference_now.tzinfo
    assert parsed_forecast_time.hour == 11


async def test_stale_source_forecast_does_not_append_past_projection_points(
    hass,
    mock_entry_factory,
    forecast_points_factory,
    source_state_factory,
    fixed_now,
    patch_extend_now,
    monkeypatch,
):
    """Projection starts no earlier than now when the source forecast is stale."""
    source_state_factory(
        "sensor.extend_source",
        state="42.5",
        forecast=forecast_points_factory([(-180, 100.0), (-120, 101.0)]),
    )
    history_mock = Mock(
        return_value={
            "sensor.extend_source": _history_state_series(
                fixed_now - timedelta(days=1),
                fixed_now,
            )
        }
    )
    monkeypatch.setattr(
        extend_sensor_module,
        "state_changes_during_period",
        history_mock,
    )
    monkeypatch.setattr(
        hass,
        "async_add_executor_job",
        AsyncMock(side_effect=lambda func, *args: func(*args)),
    )

    sensor = _create_sensor(hass, mock_entry_factory, forecast_horizon_hours=2)

    await sensor.async_update()

    projected_points = sensor.extra_state_attributes[ATTR_FORECAST][2:]
    assert projected_points
    assert all(
        extend_sensor_module._parse_point_time(point["time"], fixed_now) >= fixed_now
        for point in projected_points
    )
