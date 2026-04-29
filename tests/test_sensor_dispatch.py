"""Smoke tests for helper-kind sensor dispatch."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haeo_helpers.const import (
    CONF_HELPER_KIND,
    DOMAIN,
    HELPER_KIND_FORECAST_RISK_ADJUSTMENT,
    HELPER_KIND_FORECAST_STATISTIC,
)
from custom_components.haeo_helpers.sensor import (
    SENSOR_SETUP_BY_HELPER_KIND,
    async_setup_entry,
)


async def test_sensor_dispatch_calls_forecast_statistic_setup(hass, monkeypatch):
    """Dispatch routes statistic helper entries to statistic sensor setup."""
    setup_mock = AsyncMock()
    monkeypatch.setitem(
        SENSOR_SETUP_BY_HELPER_KIND, HELPER_KIND_FORECAST_STATISTIC, setup_mock
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Dispatch",
        data={CONF_HELPER_KIND: HELPER_KIND_FORECAST_STATISTIC},
        entry_id="dispatch_stat",
    )

    async_add_entities = AsyncMock()
    await async_setup_entry(hass, entry, async_add_entities)

    setup_mock.assert_awaited_once_with(hass, entry, async_add_entities)


async def test_sensor_dispatch_calls_forecast_risk_adjustment_setup(hass, monkeypatch):
    """Dispatch routes risk-adjustment helper entries to risk sensor setup."""
    setup_mock = AsyncMock()
    monkeypatch.setitem(
        SENSOR_SETUP_BY_HELPER_KIND,
        HELPER_KIND_FORECAST_RISK_ADJUSTMENT,
        setup_mock,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Dispatch",
        data={CONF_HELPER_KIND: HELPER_KIND_FORECAST_RISK_ADJUSTMENT},
        entry_id="dispatch_risk",
    )

    async_add_entities = AsyncMock()
    await async_setup_entry(hass, entry, async_add_entities)

    setup_mock.assert_awaited_once_with(hass, entry, async_add_entities)


async def test_sensor_dispatch_unknown_kind_logs_warning_and_does_not_crash(
    hass, caplog
):
    """Unknown helper kind logs warning and does not raise."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Dispatch",
        data={CONF_HELPER_KIND: "unknown_helper_kind"},
        entry_id="dispatch_unknown",
    )

    async_add_entities = AsyncMock()

    with caplog.at_level(logging.WARNING):
        await async_setup_entry(hass, entry, async_add_entities)

    assert any("Unsupported helper kind" in message for message in caplog.messages)
    async_add_entities.assert_not_awaited()
