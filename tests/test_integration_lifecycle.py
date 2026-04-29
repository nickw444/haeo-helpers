"""Smoke tests for integration setup, unload, and update listener."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components import haeo_helpers
from custom_components.haeo_helpers.const import DOMAIN, PLATFORMS


async def test_async_setup_entry_stores_data_and_forwards_platforms(hass):
    """Setup stores entry data and forwards supported platforms."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="Lifecycle", data={}, entry_id="lifecycle_1"
    )

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        AsyncMock(),
    ) as mock_forward:
        result = await haeo_helpers.async_setup_entry(hass, entry)

    assert result is True
    mock_forward.assert_awaited_once_with(entry, PLATFORMS)
    assert DOMAIN in hass.data
    assert hass.data[DOMAIN][entry.entry_id] == {}


async def test_async_unload_entry_unloads_platforms_and_cleans_data(hass):
    """Unload removes runtime data after successful platform unload."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="Lifecycle", data={}, entry_id="lifecycle_2"
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"created": True}

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=True),
    ) as mock_unload:
        result = await haeo_helpers.async_unload_entry(hass, entry)

    assert result is True
    mock_unload.assert_awaited_once_with(entry, PLATFORMS)
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_update_listener_requests_reload(hass):
    """Options update listener triggers config entry reload."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="Lifecycle", data={}, entry_id="lifecycle_3"
    )

    with patch.object(
        hass.config_entries,
        "async_reload",
        AsyncMock(),
    ) as mock_reload:
        await haeo_helpers.async_update_listener(hass, entry)

    mock_reload.assert_awaited_once_with(entry.entry_id)
