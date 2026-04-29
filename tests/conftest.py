"""Shared pytest fixtures for HAEO Helpers tests."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haeo_helpers.const import DOMAIN

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> None:
    """Enable loading custom integrations in tests."""


@pytest.fixture
def fixed_now() -> datetime:
    """Return a fixed timezone-aware datetime for deterministic tests."""
    return datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def forecast_points_factory(
    fixed_now: datetime,
) -> Any:
    """Create forecast point lists from minute offsets and values."""

    def _build(
        offsets_to_values: Iterable[tuple[float, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "time": (fixed_now + timedelta(minutes=offset_minutes)).isoformat(),
                "value": value,
            }
            for offset_minutes, value in offsets_to_values
        ]

    return _build


@pytest.fixture
def source_state_factory(hass: Any) -> Any:
    """Set helper source state with optional forecast and extra attributes."""

    def _set(
        entity_id: str,
        *,
        state: str = "0",
        forecast: list[dict[str, Any]] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        attrs = dict(attributes or {})
        if forecast is not None:
            attrs["forecast"] = forecast
        hass.states.async_set(entity_id, state, attrs)

    return _set


@pytest.fixture
def mock_entry_factory(hass: Any) -> Any:
    """Create and register a mock config entry."""
    ids = count(1)

    def _create(
        *,
        data: dict[str, Any],
        options: dict[str, Any] | None = None,
        title: str = "Test Helper",
        entry_id: str | None = None,
    ) -> MockConfigEntry:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=title,
            data=data,
            options=options or {},
            entry_id=entry_id or f"test_entry_{next(ids)}",
        )
        entry.add_to_hass(hass)
        return entry

    return _create


@pytest.fixture
def assert_forecast_values() -> Any:
    """Assert forecast point values with tight floating-point tolerance."""

    def _assert(forecast: list[dict[str, Any]], expected_values: list[float]) -> None:
        values = [float(point["value"]) for point in forecast]
        assert len(values) == len(expected_values)
        for value, expected in zip(values, expected_values, strict=True):
            assert value == pytest.approx(expected, rel=1e-6, abs=1e-6)

    return _assert
