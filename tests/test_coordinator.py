"""Tests for Homevolt coordinator."""

from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub out homeassistant and aiohttp modules so the coordinator can be
# imported even when Home Assistant or compatible aiohttp is not installed
# (e.g. on system Python without a full HA venv).
# When running inside a real HA test environment these stubs are harmless
# because the real modules are already in sys.modules.
# ---------------------------------------------------------------------------


def _ensure_aiohttp_stub() -> None:
    """Stub out aiohttp if it cannot be imported (broken version etc.)."""
    try:
        import aiohttp  # noqa: F401

        return  # aiohttp works fine; nothing to do.
    except (ImportError, Exception):
        pass

    # Create a minimal aiohttp stub with what api.py needs
    aiohttp_mod = ModuleType("aiohttp")
    aiohttp_mod.ClientSession = MagicMock  # type: ignore[attr-defined]
    aiohttp_mod.BasicAuth = MagicMock  # type: ignore[attr-defined]
    aiohttp_mod.ClientTimeout = MagicMock  # type: ignore[attr-defined]
    aiohttp_mod.ClientConnectionError = type(  # type: ignore[attr-defined]
        "ClientConnectionError", (Exception,), {}
    )
    sys.modules["aiohttp"] = aiohttp_mod


def _ensure_ha_stubs() -> None:
    """Install lightweight stubs for homeassistant modules if not present."""
    if "homeassistant" in sys.modules:
        return  # Real HA is available; nothing to do.

    # --- homeassistant (top-level) ---
    ha = ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    # --- homeassistant.core ---
    ha_core = ModuleType("homeassistant.core")
    ha_core.HomeAssistant = MagicMock  # type: ignore[attr-defined]
    sys.modules["homeassistant.core"] = ha_core

    # --- homeassistant.config_entries ---
    ha_config = ModuleType("homeassistant.config_entries")
    ha_config.ConfigEntry = MagicMock  # type: ignore[attr-defined]
    sys.modules["homeassistant.config_entries"] = ha_config

    # --- homeassistant.exceptions ---
    ha_exc = ModuleType("homeassistant.exceptions")

    class _ConfigEntryAuthFailed(Exception):
        pass

    ha_exc.ConfigEntryAuthFailed = _ConfigEntryAuthFailed  # type: ignore[attr-defined]
    sys.modules["homeassistant.exceptions"] = ha_exc

    # --- homeassistant.helpers ---
    ha_helpers = ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = ha_helpers

    # --- homeassistant.helpers.update_coordinator ---
    ha_coord_mod = ModuleType("homeassistant.helpers.update_coordinator")

    class _UpdateFailed(Exception):
        pass

    class _StubDataUpdateCoordinator:
        """Minimal stand-in for DataUpdateCoordinator."""

        def __init__(self, hass, logger, *, name, config_entry=None, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.config_entry = config_entry
            self.update_interval = update_interval
            self.data = None  # matches real coordinator: None before first update

        def __class_getitem__(cls, item):
            """Support generic subscription (e.g. DataUpdateCoordinator[T])."""
            return cls

    ha_coord_mod.DataUpdateCoordinator = _StubDataUpdateCoordinator  # type: ignore[attr-defined]
    ha_coord_mod.UpdateFailed = _UpdateFailed  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_coord_mod


_ensure_aiohttp_stub()
_ensure_ha_stubs()

# Now safe to import the coordinator and its dependencies
from custom_components.homevolt.api import (  # noqa: E402
    HomevoltApiClient,
    HomevoltAuthError,
    HomevoltConnectionError,
)
from custom_components.homevolt.coordinator import HomevoltCoordinator  # noqa: E402
from custom_components.homevolt.models import (  # noqa: E402
    ErrorReportEntry,
    HomevoltData,
    HomevoltEmsResponse,
    HomevoltStatusResponse,
)

# Re-import the exception classes that the coordinator actually raises,
# so our assertions match the exact class object.
from homeassistant.exceptions import ConfigEntryAuthFailed  # noqa: E402
from homeassistant.helpers.update_coordinator import UpdateFailed  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _load_fixture(name: str):
    """Load a JSON fixture file."""
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def ems_response() -> HomevoltEmsResponse:
    """Return a parsed EMS response from fixture data."""
    return HomevoltEmsResponse.from_dict(_load_fixture("ems_response.json"))


@pytest.fixture
def status_response() -> HomevoltStatusResponse:
    """Return a parsed status response from fixture data."""
    return HomevoltStatusResponse.from_dict(_load_fixture("status_response.json"))


@pytest.fixture
def error_report_response() -> list[ErrorReportEntry]:
    """Return a parsed error report from fixture data."""
    data = _load_fixture("error_report_response.json")
    return [ErrorReportEntry.from_dict(e) for e in data]


@pytest.fixture
def mock_client(ems_response, status_response, error_report_response) -> MagicMock:
    """Create a mock HomevoltApiClient with all methods returning fixture data."""
    client = MagicMock(spec=HomevoltApiClient)
    client.async_get_ems_data = AsyncMock(return_value=ems_response)
    client.async_get_status = AsyncMock(return_value=status_response)
    client.async_get_error_report = AsyncMock(return_value=error_report_response)
    return client


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock HomeAssistant instance."""
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock ConfigEntry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {"host": "192.168.70.12"}
    return entry


@pytest.fixture
def coordinator(mock_hass, mock_config_entry, mock_client) -> HomevoltCoordinator:
    """Create a HomevoltCoordinator for testing."""
    return HomevoltCoordinator(
        hass=mock_hass,
        config_entry=mock_config_entry,
        client=mock_client,
    )


# ---------------------------------------------------------------------------
# Tests: First fetch behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_fetch_gets_all_data(coordinator, mock_client):
    """First fetch (self.data is None) should call ALL endpoints."""
    assert coordinator.data is None

    result = await coordinator._async_update_data()

    mock_client.async_get_ems_data.assert_called_once()
    mock_client.async_get_status.assert_called_once()
    mock_client.async_get_error_report.assert_called_once()

    assert isinstance(result, HomevoltData)
    assert result.ems is not None
    assert result.status is not None
    assert len(result.error_report) > 0


@pytest.mark.asyncio
async def test_first_fetch_populates_ems_data(coordinator):
    """First fetch should return valid EMS data from fixture."""
    result = await coordinator._async_update_data()

    assert result.ems.type == "ems_data"
    assert result.ems.aggregated.ems_info.rated_capacity == 13304
    assert len(result.ems.ems) == 1


@pytest.mark.asyncio
async def test_first_fetch_populates_status(coordinator):
    """First fetch should return valid status data from fixture."""
    result = await coordinator._async_update_data()

    assert result.status is not None
    assert result.status.up_time > 0
    assert result.status.wifi_status.connected is True


@pytest.mark.asyncio
async def test_first_fetch_populates_error_report(coordinator):
    """First fetch should return valid error report from fixture."""
    result = await coordinator._async_update_data()

    assert len(result.error_report) > 0
    assert any(e.sub_system_name == "EMS" for e in result.error_report)


# ---------------------------------------------------------------------------
# Tests: Subsequent fetch behaviour (tiered polling)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_second_fetch_only_gets_ems(coordinator, mock_client):
    """Second fetch should only call EMS (status/error reused from cache)."""
    # First fetch: gets everything
    first_result = await coordinator._async_update_data()
    coordinator.data = first_result  # Simulate HA setting .data after first update

    mock_client.reset_mock()

    # Second fetch: poll_count=2, not divisible by 4 or 10
    result = await coordinator._async_update_data()

    mock_client.async_get_ems_data.assert_called_once()
    mock_client.async_get_status.assert_not_called()
    mock_client.async_get_error_report.assert_not_called()

    # Should carry over cached status and error report
    assert result.status is first_result.status
    assert result.error_report is first_result.error_report


@pytest.mark.asyncio
async def test_ems_fetched_every_cycle(coordinator, mock_client):
    """EMS data should be fetched on every single cycle."""
    # Run 5 cycles
    for i in range(5):
        result = await coordinator._async_update_data()
        coordinator.data = result

    assert mock_client.async_get_ems_data.call_count == 5


@pytest.mark.asyncio
async def test_error_report_refreshed_every_4th_cycle(coordinator, mock_client):
    """Error report should be fetched on the 1st (None), 4th, and 8th cycles."""
    for i in range(8):
        result = await coordinator._async_update_data()
        coordinator.data = result

    # Poll counts: 1 (None->fetch), 2(skip), 3(skip), 4(fetch), 5(skip), 6(skip), 7(skip), 8(fetch)
    assert mock_client.async_get_error_report.call_count == 3


@pytest.mark.asyncio
async def test_status_refreshed_every_10th_cycle(coordinator, mock_client):
    """Status should be fetched on the 1st (None) and 10th cycles."""
    for i in range(10):
        result = await coordinator._async_update_data()
        coordinator.data = result

    # Poll counts: 1 (None->fetch), 10(fetch)
    assert mock_client.async_get_status.call_count == 2


@pytest.mark.asyncio
async def test_status_refreshed_at_20th_cycle(coordinator, mock_client):
    """Status should be fetched again at the 20th cycle."""
    for i in range(20):
        result = await coordinator._async_update_data()
        coordinator.data = result

    # Poll counts: 1 (None->fetch), 10(fetch), 20(fetch) = 3
    assert mock_client.async_get_status.call_count == 3


@pytest.mark.asyncio
async def test_cached_data_carried_forward(coordinator, mock_client):
    """When an endpoint is not polled, its previous value is carried forward."""
    # First fetch: get all
    first_result = await coordinator._async_update_data()
    coordinator.data = first_result
    original_status = first_result.status
    original_errors = first_result.error_report

    mock_client.reset_mock()

    # Second fetch: only EMS
    second_result = await coordinator._async_update_data()
    coordinator.data = second_result

    # Status and errors should be the exact same objects
    assert second_result.status is original_status
    assert second_result.error_report is original_errors

    # But EMS should be freshly fetched
    mock_client.async_get_ems_data.assert_called_once()


@pytest.mark.asyncio
async def test_poll_count_increments_correctly(coordinator):
    """Verify _poll_count increments by 1 on each call."""
    assert coordinator._poll_count == 0

    await coordinator._async_update_data()
    assert coordinator._poll_count == 1
    coordinator.data = HomevoltData()

    await coordinator._async_update_data()
    assert coordinator._poll_count == 2

    await coordinator._async_update_data()
    assert coordinator._poll_count == 3


# ---------------------------------------------------------------------------
# Tests: Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_error_triggers_config_entry_auth_failed(coordinator, mock_client):
    """HomevoltAuthError should be wrapped in ConfigEntryAuthFailed."""
    mock_client.async_get_ems_data.side_effect = HomevoltAuthError("Bad password")

    with pytest.raises(ConfigEntryAuthFailed, match="Invalid credentials"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_connection_error_triggers_update_failed(coordinator, mock_client):
    """HomevoltConnectionError should be wrapped in UpdateFailed."""
    mock_client.async_get_ems_data.side_effect = HomevoltConnectionError(
        "Connection refused"
    )

    with pytest.raises(UpdateFailed, match="Error communicating with Homevolt"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_auth_error_on_status_triggers_config_entry_auth_failed(
    coordinator, mock_client
):
    """Auth error during status fetch should also trigger ConfigEntryAuthFailed."""
    # EMS succeeds, but status raises auth error
    mock_client.async_get_status.side_effect = HomevoltAuthError("Token expired")

    with pytest.raises(ConfigEntryAuthFailed, match="Invalid credentials"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_connection_error_on_error_report_triggers_update_failed(
    coordinator, mock_client
):
    """Connection error during error_report fetch should trigger UpdateFailed."""
    mock_client.async_get_error_report.side_effect = HomevoltConnectionError(
        "Timeout"
    )

    with pytest.raises(UpdateFailed, match="Error communicating with Homevolt"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_auth_error_preserves_original_exception(coordinator, mock_client):
    """ConfigEntryAuthFailed should chain to the original HomevoltAuthError."""
    original_err = HomevoltAuthError("Invalid password")
    mock_client.async_get_ems_data.side_effect = original_err

    with pytest.raises(ConfigEntryAuthFailed) as exc_info:
        await coordinator._async_update_data()

    assert exc_info.value.__cause__ is original_err


@pytest.mark.asyncio
async def test_connection_error_preserves_original_exception(coordinator, mock_client):
    """UpdateFailed should chain to the original HomevoltConnectionError."""
    original_err = HomevoltConnectionError("Network down")
    mock_client.async_get_ems_data.side_effect = original_err

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert exc_info.value.__cause__ is original_err


# ---------------------------------------------------------------------------
# Tests: Coordinator initialisation
# ---------------------------------------------------------------------------


def test_coordinator_init_defaults(mock_hass, mock_config_entry, mock_client):
    """Test coordinator initialises with correct defaults."""
    coord = HomevoltCoordinator(
        hass=mock_hass,
        config_entry=mock_config_entry,
        client=mock_client,
    )
    assert coord.client is mock_client
    assert coord._poll_count == 0
    assert coord.update_interval == timedelta(seconds=30)
    assert coord.name == "Homevolt"


def test_coordinator_custom_scan_interval(mock_hass, mock_config_entry, mock_client):
    """Test coordinator can be created with a custom scan interval."""
    coord = HomevoltCoordinator(
        hass=mock_hass,
        config_entry=mock_config_entry,
        client=mock_client,
        scan_interval=60,
    )
    assert coord.update_interval == timedelta(seconds=60)


# ---------------------------------------------------------------------------
# Tests: Combined tiered polling scenario
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_polling_scenario(coordinator, mock_client):
    """Run through 12 cycles and verify the exact call counts.

    Expected fetch pattern (1-indexed poll_count):
        EMS:           every cycle                 -> 12 calls
        status:        cycle 1(None), 10           -> 2 calls
        error_report:  cycle 1(None), 4, 8, 12     -> 4 calls
    """
    for i in range(12):
        result = await coordinator._async_update_data()
        coordinator.data = result

    assert mock_client.async_get_ems_data.call_count == 12
    assert mock_client.async_get_status.call_count == 2
    assert mock_client.async_get_error_report.call_count == 4
