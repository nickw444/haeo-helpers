"""Behavior-focused tests for recent days forecast helper sensor."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.haeo_helpers.helpers.recent_days_forecast import (
    sensor as recent_sensor_module,
)
from custom_components.haeo_helpers.helpers.recent_days_forecast.const import (
    ATTR_FORECAST,
    ATTR_FORECAST_HORIZON_HOURS,
    ATTR_HISTORY_DAYS,
    ATTR_LAST_FORECAST_UPDATE,
    ATTR_RECENT_BIAS_PCT,
    ATTR_SOURCE_ENTITY,
    CONF_FORECAST_HORIZON_HOURS,
    CONF_HISTORY_DAYS,
    CONF_RECENT_BIAS_PCT,
    CONF_SOURCE_ENTITY,
)
from custom_components.haeo_helpers.helpers.recent_days_forecast.sensor import (
    RecentDaysForecastSensor,
)


def _create_sensor(
    hass,
    mock_entry_factory,
    *,
    source_entity: str = "sensor.recent_load",
    history_days: int = 2,
    forecast_horizon_hours: int = 2,
    recent_bias_pct: float = 0.0,
):
    data = {
        CONF_SOURCE_ENTITY: source_entity,
        CONF_HISTORY_DAYS: history_days,
        CONF_FORECAST_HORIZON_HOURS: forecast_horizon_hours,
        CONF_RECENT_BIAS_PCT: recent_bias_pct,
    }
    entry = mock_entry_factory(data=data, title="Recent Forecast")
    return RecentDaysForecastSensor(hass, entry)


@pytest.fixture
def patch_recent_now(monkeypatch, fixed_now):
    """Patch dt_util.now used in recent-days sensor module to a fixed time."""
    monkeypatch.setattr(recent_sensor_module.dt_util, "now", lambda: fixed_now)


def _stats_for_previous_days(fixed_now):
    """Build two full previous days of hourly statistics for noon and 1pm."""
    end_day = fixed_now.replace(hour=0, minute=0, second=0, microsecond=0)
    oldest_day = end_day - timedelta(days=2)
    newest_day = end_day - timedelta(days=1)
    return [
        {"start": oldest_day.replace(hour=12), "mean": 1.0},
        {"start": oldest_day.replace(hour=13), "mean": 2.0},
        {"start": newest_day.replace(hour=12), "mean": 3.0},
        {"start": newest_day.replace(hour=13), "mean": 4.0},
    ]


async def test_recent_days_forecast_averages_previous_full_days(
    hass,
    mock_entry_factory,
    source_state_factory,
    assert_forecast_values,
    fixed_now,
    patch_recent_now,
    monkeypatch,
):
    """Forecast points are hourly averages for matching times across previous days."""
    source_state_factory(
        "sensor.recent_load",
        state="1.5",
        attributes={
            "unit_of_measurement": "kW",
            "device_class": "power",
            "state_class": "measurement",
        },
    )
    statistics_mock = Mock(
        return_value={"sensor.recent_load": _stats_for_previous_days(fixed_now)}
    )
    monkeypatch.setattr(
        recent_sensor_module, "statistics_during_period", statistics_mock
    )
    executor_mock = AsyncMock(side_effect=lambda func, *args: func(*args))
    monkeypatch.setattr(hass, "async_add_executor_job", executor_mock)

    sensor = _create_sensor(hass, mock_entry_factory)

    await sensor.async_update()

    executor_mock.assert_awaited_once()
    statistics_mock.assert_called_once()
    call_args = statistics_mock.call_args
    assert call_args.args[0] is hass
    assert call_args.args[1] == fixed_now.replace(hour=0, minute=0) - timedelta(days=2)
    assert call_args.args[2] == fixed_now.replace(hour=0, minute=0)
    assert call_args.args[3] == {"sensor.recent_load"}
    assert call_args.args[4] == "hour"
    assert call_args.args[6] == {"mean"}

    assert sensor.available is True
    assert sensor.native_value == pytest.approx(2.0, rel=1e-6, abs=1e-6)
    assert sensor.native_unit_of_measurement == "kW"
    assert sensor.device_class == "power"

    attrs = sensor.extra_state_attributes
    assert attrs[ATTR_SOURCE_ENTITY] == "sensor.recent_load"
    assert attrs[ATTR_HISTORY_DAYS] == 2
    assert attrs[ATTR_FORECAST_HORIZON_HOURS] == 2
    assert attrs[ATTR_RECENT_BIAS_PCT] == 0.0
    assert attrs[ATTR_LAST_FORECAST_UPDATE] == fixed_now.isoformat()
    assert_forecast_values(attrs[ATTR_FORECAST], [2.0, 3.0])


async def test_recent_bias_weights_newer_days_more_heavily(
    hass,
    mock_entry_factory,
    source_state_factory,
    assert_forecast_values,
    fixed_now,
    patch_recent_now,
    monkeypatch,
):
    """Recent bias applies a linear weight toward newer historical days."""
    source_state_factory("sensor.recent_load", state="1.5")
    monkeypatch.setattr(
        recent_sensor_module,
        "statistics_during_period",
        Mock(return_value={"sensor.recent_load": _stats_for_previous_days(fixed_now)}),
    )
    monkeypatch.setattr(
        hass,
        "async_add_executor_job",
        AsyncMock(side_effect=lambda func, *args: func(*args)),
    )
    sensor = _create_sensor(hass, mock_entry_factory, recent_bias_pct=100.0)

    await sensor.async_update()

    attrs = sensor.extra_state_attributes
    assert_forecast_values(attrs[ATTR_FORECAST], [2.3333333333, 3.3333333333])
    assert sensor.native_value == pytest.approx(2.3333333333, rel=1e-6, abs=1e-6)


async def test_recent_days_forecast_unavailable_without_statistics(
    hass,
    mock_entry_factory,
    source_state_factory,
    patch_recent_now,
    monkeypatch,
):
    """Sensor is unavailable when recorder statistics produce no forecast."""
    source_state_factory("sensor.recent_load", state="1.5")
    monkeypatch.setattr(
        recent_sensor_module,
        "statistics_during_period",
        Mock(return_value={"sensor.recent_load": []}),
    )
    monkeypatch.setattr(
        hass,
        "async_add_executor_job",
        AsyncMock(side_effect=lambda func, *args: func(*args)),
    )
    sensor = _create_sensor(hass, mock_entry_factory)

    await sensor.async_update()

    assert sensor.available is False
    assert sensor.native_value is None
    assert sensor.extra_state_attributes[ATTR_FORECAST] == []


async def test_source_state_change_updates_metadata_without_forced_refresh(
    hass,
    mock_entry_factory,
    source_state_factory,
):
    """Source changes update metadata without re-querying recorder."""
    source_state_factory(
        "sensor.recent_load",
        state="1.5",
        attributes={"unit_of_measurement": "W"},
    )
    sensor = _create_sensor(hass, mock_entry_factory)
    schedule_mock = Mock()
    write_mock = Mock()
    sensor.async_schedule_update_ha_state = schedule_mock
    sensor.async_write_ha_state = write_mock

    source_state_factory(
        "sensor.recent_load",
        state="1.6",
        attributes={"unit_of_measurement": "kW"},
    )

    sensor._handle_source_state_change(Mock())

    assert sensor.native_unit_of_measurement == "kW"
    schedule_mock.assert_not_called()
    write_mock.assert_called_once_with()


async def test_scheduled_refresh_schedules_forced_refresh(
    hass,
    mock_entry_factory,
):
    """Scheduled refreshes should trigger a forced async update."""
    sensor = _create_sensor(hass, mock_entry_factory)
    schedule_mock = Mock()
    sensor.async_schedule_update_ha_state = schedule_mock

    sensor._handle_scheduled_refresh(Mock())

    schedule_mock.assert_called_once_with(force_refresh=True)
