"""Tests for Homevolt integration setup and teardown."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.homevolt import async_setup_entry, async_unload_entry
from custom_components.homevolt.api import (
    HomevoltApiClient,
    HomevoltConnectionError,
)
from custom_components.homevolt.coordinator import HomevoltCoordinator
from custom_components.homevolt.models import (
    ErrorReportEntry,
    HomevoltData,
    HomevoltEmsResponse,
    HomevoltStatusResponse,
)

from homeassistant.exceptions import ConfigEntryNotReady

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_fixture(name: str):
    """Load a JSON fixture file."""
    return json.loads((FIXTURES / name).read_text())


def _make_ems_response() -> HomevoltEmsResponse:
    """Build an EMS response from the fixture."""
    return HomevoltEmsResponse.from_dict(_load_fixture("ems_response.json"))


def _make_status_response() -> HomevoltStatusResponse:
    """Build a status response from the fixture."""
    return HomevoltStatusResponse.from_dict(_load_fixture("status_response.json"))


def _make_error_report() -> list[ErrorReportEntry]:
    """Build an error report from the fixture."""
    data = _load_fixture("error_report_response.json")
    return [ErrorReportEntry.from_dict(e) for e in data]


def _make_mock_client(
    *,
    ems: HomevoltEmsResponse | None = None,
    status: HomevoltStatusResponse | None = None,
    error_report: list[ErrorReportEntry] | None = None,
) -> MagicMock:
    """Create a mock HomevoltApiClient that returns fixture data."""
    client = MagicMock(spec=HomevoltApiClient)
    client.async_get_ems_data = AsyncMock(
        return_value=ems or _make_ems_response()
    )
    client.async_get_status = AsyncMock(
        return_value=status or _make_status_response()
    )
    client.async_get_error_report = AsyncMock(
        return_value=error_report if error_report is not None else _make_error_report()
    )
    return client


def _make_config_entry() -> MagicMock:
    """Create a mock ConfigEntry with typical Homevolt data."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {"host": "192.168.70.12", "port": 80}
    entry.options = {}
    entry.runtime_data = None
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    return entry


def _make_hass() -> MagicMock:
    """Create a mock HomeAssistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_reload = AsyncMock()
    return hass


# ---------------------------------------------------------------------------
# Tests: async_setup_entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_entry_creates_coordinator_and_refreshes():
    """Entry loads successfully: coordinator is created and first refresh completes."""
    hass = _make_hass()
    entry = _make_config_entry()
    mock_client = _make_mock_client()

    with patch(
        "custom_components.homevolt.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.HomevoltApiClient",
        return_value=mock_client,
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True

    # Coordinator should be stored on entry.runtime_data
    coordinator = entry.runtime_data
    assert isinstance(coordinator, HomevoltCoordinator)

    # First refresh should have populated data
    assert coordinator.data is not None
    assert isinstance(coordinator.data, HomevoltData)
    assert coordinator.data.ems is not None
    assert coordinator.data.status is not None


@pytest.mark.asyncio
async def test_setup_entry_forwards_sensor_platform():
    """Setup should forward entry to the sensor platform."""
    hass = _make_hass()
    entry = _make_config_entry()
    mock_client = _make_mock_client()

    with patch(
        "custom_components.homevolt.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.HomevoltApiClient",
        return_value=mock_client,
    ):
        await async_setup_entry(hass, entry)

    hass.config_entries.async_forward_entry_setups.assert_called_once()
    call_args = hass.config_entries.async_forward_entry_setups.call_args
    assert call_args[0][0] is entry
    # Platforms list should contain "sensor"
    platforms = call_args[0][1]
    assert "sensor" in platforms


@pytest.mark.asyncio
async def test_setup_entry_registers_update_listener():
    """Setup should register an options update listener."""
    hass = _make_hass()
    entry = _make_config_entry()
    mock_client = _make_mock_client()

    with patch(
        "custom_components.homevolt.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.HomevoltApiClient",
        return_value=mock_client,
    ):
        await async_setup_entry(hass, entry)

    entry.async_on_unload.assert_called_once()
    entry.add_update_listener.assert_called_once()


@pytest.mark.asyncio
async def test_setup_entry_uses_config_data():
    """Setup should pass host/port/password from entry.data to the API client."""
    hass = _make_hass()
    entry = _make_config_entry()
    entry.data = {"host": "10.0.0.5", "port": 8080, "password": "secret"}
    mock_client = _make_mock_client()

    with patch(
        "custom_components.homevolt.async_get_clientsession",
        return_value=MagicMock(),
    ) as mock_session, patch(
        "custom_components.homevolt.HomevoltApiClient",
        return_value=mock_client,
    ) as mock_client_cls:
        await async_setup_entry(hass, entry)

    mock_client_cls.assert_called_once()
    call_kwargs = mock_client_cls.call_args
    assert call_kwargs.kwargs["host"] == "10.0.0.5"
    assert call_kwargs.kwargs["port"] == 8080
    assert call_kwargs.kwargs["password"] == "secret"


@pytest.mark.asyncio
async def test_setup_entry_uses_custom_scan_interval():
    """Setup should use scan_interval from entry.options if present."""
    hass = _make_hass()
    entry = _make_config_entry()
    entry.options = {"scan_interval": 60}
    mock_client = _make_mock_client()

    with patch(
        "custom_components.homevolt.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.HomevoltApiClient",
        return_value=mock_client,
    ):
        await async_setup_entry(hass, entry)

    coordinator = entry.runtime_data
    from datetime import timedelta
    assert coordinator.update_interval == timedelta(seconds=60)


# ---------------------------------------------------------------------------
# Tests: async_unload_entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unload_entry_returns_true():
    """Unload should return True when platforms unload successfully."""
    hass = _make_hass()
    entry = _make_config_entry()

    result = await async_unload_entry(hass, entry)

    assert result is True


@pytest.mark.asyncio
async def test_unload_entry_calls_unload_platforms():
    """Unload should call async_unload_platforms with the sensor platform."""
    hass = _make_hass()
    entry = _make_config_entry()

    await async_unload_entry(hass, entry)

    hass.config_entries.async_unload_platforms.assert_called_once()
    call_args = hass.config_entries.async_unload_platforms.call_args
    assert call_args[0][0] is entry
    platforms = call_args[0][1]
    assert "sensor" in platforms


@pytest.mark.asyncio
async def test_unload_entry_returns_false_on_failure():
    """Unload should return False if platform unload fails."""
    hass = _make_hass()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    entry = _make_config_entry()

    result = await async_unload_entry(hass, entry)

    assert result is False


@pytest.mark.asyncio
async def test_setup_then_unload_lifecycle():
    """Full lifecycle: setup then unload should both succeed."""
    hass = _make_hass()
    entry = _make_config_entry()
    mock_client = _make_mock_client()

    with patch(
        "custom_components.homevolt.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.HomevoltApiClient",
        return_value=mock_client,
    ):
        setup_result = await async_setup_entry(hass, entry)

    assert setup_result is True
    assert entry.runtime_data is not None

    unload_result = await async_unload_entry(hass, entry)
    assert unload_result is True


# ---------------------------------------------------------------------------
# Tests: ConfigEntryNotReady when API is unreachable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_entry_raises_not_ready_on_connection_error():
    """Setup raises ConfigEntryNotReady when the API client cannot connect."""
    hass = _make_hass()
    entry = _make_config_entry()

    mock_client = _make_mock_client()
    mock_client.async_get_ems_data.side_effect = HomevoltConnectionError(
        "Connection refused"
    )

    with patch(
        "custom_components.homevolt.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.HomevoltApiClient",
        return_value=mock_client,
    ):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_setup_entry_not_ready_does_not_store_coordinator():
    """When ConfigEntryNotReady is raised, runtime_data should not be set."""
    hass = _make_hass()
    entry = _make_config_entry()

    mock_client = _make_mock_client()
    mock_client.async_get_ems_data.side_effect = HomevoltConnectionError(
        "Timeout"
    )

    with patch(
        "custom_components.homevolt.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.HomevoltApiClient",
        return_value=mock_client,
    ):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)

    # runtime_data should still be the initial None (not set to a coordinator)
    assert entry.runtime_data is None


@pytest.mark.asyncio
async def test_setup_entry_not_ready_does_not_forward_platforms():
    """When ConfigEntryNotReady is raised, platforms should not be forwarded."""
    hass = _make_hass()
    entry = _make_config_entry()

    mock_client = _make_mock_client()
    mock_client.async_get_ems_data.side_effect = HomevoltConnectionError(
        "Unreachable"
    )

    with patch(
        "custom_components.homevolt.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.HomevoltApiClient",
        return_value=mock_client,
    ):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)

    hass.config_entries.async_forward_entry_setups.assert_not_called()
