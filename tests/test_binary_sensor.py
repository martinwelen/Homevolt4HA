"""Tests for Homevolt binary sensor platform."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.homevolt.coordinator import HomevoltCoordinator
from custom_components.homevolt.models import (
    HomevoltData,
    HomevoltEmsResponse,
    HomevoltStatusResponse,
    ErrorReportEntry,
    NodeInfo,
    NodeMetrics,
    ScheduleData,
)
from custom_components.homevolt.binary_sensor import (
    SYSTEM_BINARY_SENSORS,
    CT_BINARY_SENSORS,
    CT_NODE_BINARY_SENSORS,
    HomevoltBinarySensor,
    HomevoltCtBinarySensor,
    HomevoltCtNodeBinarySensor,
)

FIXTURES = Path(__file__).parent / "fixtures"

ECU_ID = "9731192375880"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


def _make_coordinator_with_data() -> MagicMock:
    """Create a mock coordinator with real fixture data."""
    ems = HomevoltEmsResponse.from_dict(_load_fixture("ems_response.json"))
    status = HomevoltStatusResponse.from_dict(_load_fixture("status_response.json"))
    error_report = [
        ErrorReportEntry.from_dict(e)
        for e in _load_fixture("error_report_response.json")
    ]
    nodes = [NodeInfo.from_dict(n) for n in _load_fixture("nodes_response.json")]
    node_metrics = {
        2: NodeMetrics.from_dict(_load_fixture("node_metrics_2_response.json")),
        3: NodeMetrics.from_dict(_load_fixture("node_metrics_3_response.json")),
    }
    schedule = ScheduleData.from_dict(_load_fixture("schedule_response.json"))
    data = HomevoltData(
        ems=ems, status=status, error_report=error_report,
        nodes=nodes, node_metrics=node_metrics, schedule=schedule,
    )

    coordinator = MagicMock(spec=HomevoltCoordinator)
    coordinator.data = data
    return coordinator


# ---------------------------------------------------------------------------
# CT availability binary sensor tests
# ---------------------------------------------------------------------------

class TestCtAvailableBinarySensor:
    """Test CT clamp availability binary sensor."""

    def test_ct_available_grid_online(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_BINARY_SENSORS if d.key == "ct_available")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtBinarySensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.is_on is True

    def test_ct_available_solar_online(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_BINARY_SENSORS if d.key == "ct_available")
        euid = "a46dd4fffea284c2"
        sensor = HomevoltCtBinarySensor(coord, ECU_ID, 1, "solar", euid, desc)
        assert sensor.is_on is True

    def test_ct_available_offline(self):
        """Unconfigured sensor at index 2 should be False."""
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_BINARY_SENSORS if d.key == "ct_available")
        euid = "0000000000000000"
        sensor = HomevoltCtBinarySensor(coord, ECU_ID, 2, "unspecified", euid, desc)
        assert sensor.is_on is False

    def test_ct_available_out_of_range(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_BINARY_SENSORS if d.key == "ct_available")
        sensor = HomevoltCtBinarySensor(coord, ECU_ID, 99, "grid", "fake", desc)
        assert sensor.is_on is None

    def test_ct_available_unique_id(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_BINARY_SENSORS if d.key == "ct_available")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtBinarySensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor._attr_unique_id == f"{euid}_ct_available"


# ---------------------------------------------------------------------------
# System binary sensor tests
# ---------------------------------------------------------------------------

class TestSystemBinarySensors:
    """Test system-level binary sensors."""

    def test_wifi_connected_true(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_BINARY_SENSORS if d.key == "wifi_connected")
        sensor = HomevoltBinarySensor(coord, ECU_ID, desc)
        assert sensor.is_on is True

    def test_mqtt_connected_true(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_BINARY_SENSORS if d.key == "mqtt_connected")
        sensor = HomevoltBinarySensor(coord, ECU_ID, desc)
        assert sensor.is_on is True

    def test_wifi_connected_when_status_none(self):
        """When status data is None, binary sensors return None."""
        ems = HomevoltEmsResponse.from_dict(_load_fixture("ems_response.json"))
        data = HomevoltData(ems=ems, status=None)
        coord = MagicMock(spec=HomevoltCoordinator)
        coord.data = data

        desc = next(d for d in SYSTEM_BINARY_SENSORS if d.key == "wifi_connected")
        sensor = HomevoltBinarySensor(coord, ECU_ID, desc)
        assert sensor.is_on is None

    def test_mqtt_connected_when_status_none(self):
        ems = HomevoltEmsResponse.from_dict(_load_fixture("ems_response.json"))
        data = HomevoltData(ems=ems, status=None)
        coord = MagicMock(spec=HomevoltCoordinator)
        coord.data = data

        desc = next(d for d in SYSTEM_BINARY_SENSORS if d.key == "mqtt_connected")
        sensor = HomevoltBinarySensor(coord, ECU_ID, desc)
        assert sensor.is_on is None

    def test_wifi_unique_id(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_BINARY_SENSORS if d.key == "wifi_connected")
        sensor = HomevoltBinarySensor(coord, ECU_ID, desc)
        assert sensor._attr_unique_id == f"{ECU_ID}_wifi_connected"

    def test_mqtt_unique_id(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_BINARY_SENSORS if d.key == "mqtt_connected")
        sensor = HomevoltBinarySensor(coord, ECU_ID, desc)
        assert sensor._attr_unique_id == f"{ECU_ID}_mqtt_connected"

    def test_schedule_local_mode_false(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_BINARY_SENSORS if d.key == "schedule_local_mode")
        sensor = HomevoltBinarySensor(coord, ECU_ID, desc)
        assert sensor.is_on is False

    def test_schedule_local_mode_true(self):
        coord = _make_coordinator_with_data()
        coord.data.schedule.local_mode = True
        desc = next(d for d in SYSTEM_BINARY_SENSORS if d.key == "schedule_local_mode")
        sensor = HomevoltBinarySensor(coord, ECU_ID, desc)
        assert sensor.is_on is True

    def test_schedule_local_mode_when_schedule_none(self):
        coord = _make_coordinator_with_data()
        coord.data.schedule = None
        desc = next(d for d in SYSTEM_BINARY_SENSORS if d.key == "schedule_local_mode")
        sensor = HomevoltBinarySensor(coord, ECU_ID, desc)
        assert sensor.is_on is None

    def test_schedule_local_mode_unique_id(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_BINARY_SENSORS if d.key == "schedule_local_mode")
        sensor = HomevoltBinarySensor(coord, ECU_ID, desc)
        assert sensor._attr_unique_id == f"{ECU_ID}_schedule_local_mode"


# ---------------------------------------------------------------------------
# CT node binary sensor tests
# ---------------------------------------------------------------------------

class TestCtNodeBinarySensors:
    """Test CT clamp node binary sensors."""

    def test_usb_powered_false(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_NODE_BINARY_SENSORS if d.key == "ct_usb_powered")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtNodeBinarySensor(coord, ECU_ID, 0, "grid", euid, 2, desc)
        assert sensor.is_on is False

    def test_firmware_update_not_available_node2(self):
        """Node 2 version matches manifest -> no update."""
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_NODE_BINARY_SENSORS if d.key == "ct_firmware_update_available")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtNodeBinarySensor(coord, ECU_ID, 0, "grid", euid, 2, desc)
        assert sensor.is_on is False

    def test_firmware_update_available_node3(self):
        """Node 3 version differs from manifest -> update available."""
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_NODE_BINARY_SENSORS if d.key == "ct_firmware_update_available")
        euid = "a46dd4fffea284c2"
        sensor = HomevoltCtNodeBinarySensor(coord, ECU_ID, 1, "solar", euid, 3, desc)
        assert sensor.is_on is True

    def test_missing_data_returns_none(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_NODE_BINARY_SENSORS if d.key == "ct_usb_powered")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtNodeBinarySensor(coord, ECU_ID, 0, "grid", euid, 99, desc)
        assert sensor.is_on is None


# ---------------------------------------------------------------------------
# Platform setup tests
# ---------------------------------------------------------------------------

class TestBinarySensorPlatformSetup:
    """Test async_setup_entry for binary sensor platform."""

    @pytest.mark.asyncio
    async def test_setup_creates_entities(self):
        from custom_components.homevolt.binary_sensor import async_setup_entry

        coord = _make_coordinator_with_data()
        entry = MagicMock()
        entry.runtime_data = coord

        entities = []

        def capture_entities(ents):
            entities.extend(ents)

        await async_setup_entry(MagicMock(), entry, capture_entities)

        # System: 3 (wifi_connected, mqtt_connected, schedule_local_mode)
        # CT: 2 configured clamps * 1 (ct_available) = 2
        # CT Node: 2 configured clamps * 2 (usb_powered, firmware_update) = 4
        # Total: 9
        assert len(entities) == 9

    @pytest.mark.asyncio
    async def test_setup_skips_unconfigured_ct(self):
        from custom_components.homevolt.binary_sensor import async_setup_entry

        coord = _make_coordinator_with_data()
        entry = MagicMock()
        entry.runtime_data = coord

        entities = []

        def capture_entities(ents):
            entities.extend(ents)

        await async_setup_entry(MagicMock(), entry, capture_entities)

        ct_entities = [e for e in entities if hasattr(e, '_euid')]
        for ent in ct_entities:
            assert ent._euid != "0000000000000000"

    @pytest.mark.asyncio
    async def test_returns_bool_not_string(self):
        """Binary sensors must return bool, not 'on'/'off' strings."""
        from custom_components.homevolt.binary_sensor import async_setup_entry

        coord = _make_coordinator_with_data()
        entry = MagicMock()
        entry.runtime_data = coord

        entities = []

        def capture_entities(ents):
            entities.extend(ents)

        await async_setup_entry(MagicMock(), entry, capture_entities)

        for entity in entities:
            value = entity.is_on
            assert value is None or isinstance(value, bool), (
                f"{entity._attr_unique_id} returned {type(value).__name__}, expected bool"
            )
