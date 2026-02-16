"""Tests for Homevolt coordinator."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Stubs are set up by conftest.py before this module is imported
from custom_components.homevolt.api import (
    HomevoltApiClient,
    HomevoltAuthError,
    HomevoltConnectionError,
)
from custom_components.homevolt.coordinator import HomevoltCoordinator
from custom_components.homevolt.models import (
    ErrorReportEntry,
    HomevoltData,
    HomevoltEmsResponse,
    HomevoltStatusResponse,
    NodeInfo,
    NodeMetrics,
)

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

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
def nodes_response() -> list[NodeInfo]:
    """Return parsed nodes from fixture data."""
    data = _load_fixture("nodes_response.json")
    return [NodeInfo.from_dict(n) for n in data]


@pytest.fixture
def node_metrics_responses() -> dict[int, NodeMetrics]:
    """Return parsed node metrics from fixture data."""
    m2 = NodeMetrics.from_dict(_load_fixture("node_metrics_2_response.json"))
    m3 = NodeMetrics.from_dict(_load_fixture("node_metrics_3_response.json"))
    return {2: m2, 3: m3}


@pytest.fixture
def mock_client(
    ems_response, status_response, error_report_response,
    nodes_response, node_metrics_responses,
) -> MagicMock:
    """Create a mock HomevoltApiClient with all methods returning fixture data."""
    client = MagicMock(spec=HomevoltApiClient)
    client.async_get_ems_data = AsyncMock(return_value=ems_response)
    client.async_get_status = AsyncMock(return_value=status_response)
    client.async_get_error_report = AsyncMock(return_value=error_report_response)
    client.async_get_nodes = AsyncMock(return_value=nodes_response)
    client.async_get_node_metrics = AsyncMock(
        side_effect=lambda node_id: node_metrics_responses[node_id]
    )
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
    first_result = await coordinator._async_update_data()
    coordinator.data = first_result
    original_status = first_result.status
    original_errors = first_result.error_report

    mock_client.reset_mock()

    second_result = await coordinator._async_update_data()
    coordinator.data = second_result

    assert second_result.status is original_status
    assert second_result.error_report is original_errors
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


# ---------------------------------------------------------------------------
# Tests: Nodes and node metrics polling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_fetch_gets_nodes_and_metrics(coordinator, mock_client):
    """First fetch should fetch nodes and node_metrics for configured CT sensors."""
    result = await coordinator._async_update_data()

    mock_client.async_get_nodes.assert_called_once()
    # EMS fixture has 2 configured sensors (node 2 and 3), so 2 calls
    assert mock_client.async_get_node_metrics.call_count == 2
    assert len(result.nodes) == 2
    assert 2 in result.node_metrics
    assert 3 in result.node_metrics
    assert result.node_metrics[2].battery_voltage == pytest.approx(2.73)


@pytest.mark.asyncio
async def test_nodes_polled_every_10th_cycle(coordinator, mock_client):
    """Nodes should be fetched on cycle 1 (None) and 10."""
    for i in range(10):
        result = await coordinator._async_update_data()
        coordinator.data = result

    assert mock_client.async_get_nodes.call_count == 2


@pytest.mark.asyncio
async def test_node_metrics_cached_between_polls(coordinator, mock_client):
    """Node metrics should be cached between poll cycles."""
    first_result = await coordinator._async_update_data()
    coordinator.data = first_result

    mock_client.reset_mock()

    second_result = await coordinator._async_update_data()
    coordinator.data = second_result

    mock_client.async_get_nodes.assert_not_called()
    mock_client.async_get_node_metrics.assert_not_called()
    assert second_result.nodes is first_result.nodes
    assert second_result.node_metrics is first_result.node_metrics


@pytest.mark.asyncio
async def test_node_metrics_failure_non_fatal(coordinator, mock_client):
    """Failure to fetch node_metrics should not prevent coordinator from returning data."""
    mock_client.async_get_node_metrics.side_effect = Exception("Connection lost")

    result = await coordinator._async_update_data()

    assert isinstance(result, HomevoltData)
    assert result.ems is not None
    assert len(result.node_metrics) == 0  # No metrics due to failure
    assert len(result.nodes) == 2  # Nodes still fetched


# ---------------------------------------------------------------------------
# Tests: Event firing on alarm/warning/info changes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alarm_event_fired_on_change(coordinator, mock_hass, mock_client, ems_response):
    """When alarm_str changes between polls, a homevolt_alarm event should fire."""
    mock_hass.bus.async_fire = MagicMock()

    # First fetch: baseline (no event because self.data is None)
    first_result = await coordinator._async_update_data()
    coordinator.data = first_result
    mock_hass.bus.async_fire.assert_not_called()

    # Modify the alarm_str for the second fetch
    import copy
    modified_ems = copy.deepcopy(ems_response)
    modified_ems.aggregated.ems_data.alarm_str = ["BMS_OVER_VOLTAGE"]
    mock_client.async_get_ems_data = AsyncMock(return_value=modified_ems)
    mock_client.reset_mock()
    mock_client.async_get_ems_data = AsyncMock(return_value=modified_ems)

    # Second fetch: alarm changed -> event fires
    second_result = await coordinator._async_update_data()
    coordinator.data = second_result

    mock_hass.bus.async_fire.assert_any_call(
        "homevolt_alarm",
        {"previous": first_result.ems.aggregated.ems_data.alarm_str, "current": ["BMS_OVER_VOLTAGE"]},
    )


@pytest.mark.asyncio
async def test_warning_event_fired_on_change(coordinator, mock_hass, mock_client, ems_response):
    """When warning_str changes between polls, a homevolt_warning event should fire."""
    mock_hass.bus.async_fire = MagicMock()

    # First fetch: baseline
    first_result = await coordinator._async_update_data()
    coordinator.data = first_result
    mock_hass.bus.async_fire.assert_not_called()

    # Modify the warning_str for the second fetch
    import copy
    modified_ems = copy.deepcopy(ems_response)
    modified_ems.aggregated.ems_data.warning_str = ["LOW_BATTERY"]
    mock_client.async_get_ems_data = AsyncMock(return_value=modified_ems)

    # Second fetch: warning changed -> event fires
    second_result = await coordinator._async_update_data()
    coordinator.data = second_result

    mock_hass.bus.async_fire.assert_any_call(
        "homevolt_warning",
        {"previous": first_result.ems.aggregated.ems_data.warning_str, "current": ["LOW_BATTERY"]},
    )


@pytest.mark.asyncio
async def test_no_event_when_unchanged(coordinator, mock_hass):
    """When alarm/warning/info stay the same, no events should fire."""
    mock_hass.bus.async_fire = MagicMock()

    # First fetch: baseline
    first_result = await coordinator._async_update_data()
    coordinator.data = first_result
    mock_hass.bus.async_fire.assert_not_called()

    # Second fetch: identical data -> no events
    second_result = await coordinator._async_update_data()
    coordinator.data = second_result

    mock_hass.bus.async_fire.assert_not_called()
