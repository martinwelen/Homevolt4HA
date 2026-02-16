"""Tests for Homevolt sensor platform."""

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
)
from custom_components.homevolt.sensor import (
    SYSTEM_SENSORS,
    VOLTAGE_SENSORS,
    CURRENT_SENSORS,
    BMS_SENSORS,
    CT_SENSORS,
    DIAGNOSTIC_SENSORS,
    STATUS_SENSORS,
    HomevoltSystemSensor,
    HomevoltStatusSensor,
    HomevoltBmsSensor,
    HomevoltCtSensor,
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
    data = HomevoltData(ems=ems, status=status, error_report=error_report)

    coordinator = MagicMock(spec=HomevoltCoordinator)
    coordinator.data = data
    return coordinator


# ---------------------------------------------------------------------------
# System sensor tests
# ---------------------------------------------------------------------------

class TestSystemSensors:
    """Test system-level sensors."""

    def test_battery_soc(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_SENSORS if d.key == "battery_soc")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == 0

    def test_battery_power(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_SENSORS if d.key == "battery_power")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == -13

    def test_system_temperature(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_SENSORS if d.key == "system_temperature")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == pytest.approx(4.6)

    def test_grid_frequency(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_SENSORS if d.key == "grid_frequency")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == pytest.approx(49.969)

    def test_energy_imported_kwh(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_SENSORS if d.key == "energy_imported")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == pytest.approx(3791.99)

    def test_energy_exported_kwh(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_SENSORS if d.key == "energy_exported")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == pytest.approx(4350.4)

    def test_unique_id_format(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_SENSORS if d.key == "battery_soc")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor._attr_unique_id == f"{ECU_ID}_battery_soc"


# ---------------------------------------------------------------------------
# Voltage & current sensor tests
# ---------------------------------------------------------------------------

class TestVoltageSensors:
    """Test voltage sensors (decivolts -> volts)."""

    def test_voltage_l1(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in VOLTAGE_SENSORS if d.key == "voltage_l1")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == pytest.approx(228.0)

    def test_voltage_l2(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in VOLTAGE_SENSORS if d.key == "voltage_l2")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == pytest.approx(226.5)

    def test_voltage_l3(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in VOLTAGE_SENSORS if d.key == "voltage_l3")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == pytest.approx(227.4)


class TestCurrentSensors:
    """Test current sensors (deciamps -> amps)."""

    def test_current_l1(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CURRENT_SENSORS if d.key == "current_l1")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# BMS sensor tests
# ---------------------------------------------------------------------------

class TestBmsSensors:
    """Test per-battery-module sensors."""

    def test_bms_soc_module_0(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in BMS_SENSORS if d.key == "bms_soc")
        serial = "80000274099724441432"
        sensor = HomevoltBmsSensor(coord, ECU_ID, 0, serial, desc)
        assert sensor.native_value == 0

    def test_bms_cycle_count_module_1(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in BMS_SENSORS if d.key == "bms_cycle_count")
        serial = "80000274099724441534"
        sensor = HomevoltBmsSensor(coord, ECU_ID, 1, serial, desc)
        assert sensor.native_value == 290

    def test_bms_min_temp_module_0(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in BMS_SENSORS if d.key == "bms_min_temperature")
        serial = "80000274099724441432"
        sensor = HomevoltBmsSensor(coord, ECU_ID, 0, serial, desc)
        assert sensor.native_value == pytest.approx(7.1)

    def test_bms_max_temp_module_0(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in BMS_SENSORS if d.key == "bms_max_temperature")
        serial = "80000274099724441432"
        sensor = HomevoltBmsSensor(coord, ECU_ID, 0, serial, desc)
        assert sensor.native_value == pytest.approx(9.2)

    def test_bms_out_of_range_returns_none(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in BMS_SENSORS if d.key == "bms_soc")
        sensor = HomevoltBmsSensor(coord, ECU_ID, 99, "fake_serial", desc)
        assert sensor.native_value is None

    def test_bms_unique_id_uses_serial(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in BMS_SENSORS if d.key == "bms_soc")
        serial = "80000274099724441432"
        sensor = HomevoltBmsSensor(coord, ECU_ID, 0, serial, desc)
        assert sensor._attr_unique_id == f"{serial}_bms_soc"


# ---------------------------------------------------------------------------
# CT sensor tests
# ---------------------------------------------------------------------------

class TestCtSensors:
    """Test CT clamp sensors."""

    def test_ct_total_power_grid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_power")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == -3921

    def test_ct_total_power_solar(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_power")
        euid = "a46dd4fffea284c2"
        sensor = HomevoltCtSensor(coord, ECU_ID, 1, "solar", euid, desc)
        assert sensor.native_value == 3874

    def test_ct_energy_imported(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_energy_imported")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(14787.84)

    def test_ct_energy_exported(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_energy_exported")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(8059.11)

    def test_ct_rssi(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_rssi")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(-55.0)

    def test_ct_pdr(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_pdr")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(98.5)

    def test_ct_frequency(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_frequency")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(50.04)

    def test_ct_out_of_range_returns_none(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_power")
        sensor = HomevoltCtSensor(coord, ECU_ID, 99, "grid", "fake_euid", desc)
        assert sensor.native_value is None

    def test_ct_unique_id_uses_euid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_power")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor._attr_unique_id == f"{euid}_ct_power"


# ---------------------------------------------------------------------------
# CT per-phase sensor tests
# ---------------------------------------------------------------------------

class TestCtPhaseSensors:
    """Test per-phase CT clamp sensors."""

    def test_ct_voltage_l1_grid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_voltage_l1")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(253.4)

    def test_ct_voltage_l2_grid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_voltage_l2")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(253.4)

    def test_ct_voltage_l3_grid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_voltage_l3")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(253.4)

    def test_ct_current_l1_grid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_current_l1")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(16.9)

    def test_ct_current_l2_grid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_current_l2")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(10.0)

    def test_ct_current_l3_grid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_current_l3")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(1.4)

    def test_ct_power_l1_grid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_power_l1")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(-2718.0)

    def test_ct_power_l2_grid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_power_l2")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(-1389.0)

    def test_ct_power_l3_grid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_power_l3")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(186.0)

    def test_ct_power_factor_l1_grid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_power_factor_l1")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(-0.64)

    def test_ct_power_factor_l2_grid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_power_factor_l2")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(-0.55)

    def test_ct_power_factor_l3_grid(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_power_factor_l3")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtSensor(coord, ECU_ID, 0, "grid", euid, desc)
        assert sensor.native_value == pytest.approx(0.53)

    def test_ct_solar_voltage_l1(self):
        """Solar clamp should return its own phase data."""
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_voltage_l1")
        euid = "a46dd4fffea284c2"
        sensor = HomevoltCtSensor(coord, ECU_ID, 1, "solar", euid, desc)
        assert sensor.native_value == pytest.approx(253.1)

    def test_ct_solar_power_l1(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_SENSORS if d.key == "ct_power_l1")
        euid = "a46dd4fffea284c2"
        sensor = HomevoltCtSensor(coord, ECU_ID, 1, "solar", euid, desc)
        assert sensor.native_value == pytest.approx(1318.0)


# ---------------------------------------------------------------------------
# Diagnostic sensor tests
# ---------------------------------------------------------------------------

class TestDiagnosticSensors:
    """Test diagnostic sensors."""

    def test_ems_info(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in DIAGNOSTIC_SENSORS if d.key == "ems_info")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        value = sensor.native_value
        assert "EMS_INFO_CONNECTED_TO_BACKEND" in value

    def test_error_count(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in DIAGNOSTIC_SENSORS if d.key == "error_count")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == 0


# ---------------------------------------------------------------------------
# Status sensor tests
# ---------------------------------------------------------------------------

class TestStatusSensors:
    """Test status sensors."""

    def test_uptime(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in STATUS_SENSORS if d.key == "uptime")
        sensor = HomevoltStatusSensor(coord, ECU_ID, desc)
        assert sensor.native_value == 308028358

    def test_wifi_rssi(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in STATUS_SENSORS if d.key == "wifi_rssi")
        sensor = HomevoltStatusSensor(coord, ECU_ID, desc)
        assert sensor.native_value == -60

    def test_firmware_esp(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in STATUS_SENSORS if d.key == "firmware_esp")
        sensor = HomevoltStatusSensor(coord, ECU_ID, desc)
        assert sensor.native_value == "2929-a1e89e8d"

    def test_status_none_returns_none(self):
        """When status data is None, status sensors return None."""
        ems = HomevoltEmsResponse.from_dict(_load_fixture("ems_response.json"))
        data = HomevoltData(ems=ems, status=None)
        coord = MagicMock(spec=HomevoltCoordinator)
        coord.data = data

        desc = next(d for d in STATUS_SENSORS if d.key == "uptime")
        sensor = HomevoltStatusSensor(coord, ECU_ID, desc)
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Platform setup tests
# ---------------------------------------------------------------------------

class TestSensorPlatformSetup:
    """Test async_setup_entry for sensor platform."""

    @pytest.mark.asyncio
    async def test_setup_creates_entities(self):
        """Verify correct entity count from fixture data."""
        from custom_components.homevolt.sensor import async_setup_entry

        coord = _make_coordinator_with_data()
        entry = MagicMock()
        entry.runtime_data = coord

        entities = []

        def capture_entities(ents):
            entities.extend(ents)

        await async_setup_entry(MagicMock(), entry, capture_entities)

        # Count expected entities:
        # System: 18 + Voltage: 3 + Current: 3 + Diagnostic: 4 = 28 system sensors
        # Status: 4 (uptime, wifi_rssi, firmware_esp, firmware_efr)
        # BMS: 2 modules * 6 sensors = 12
        # CT: 2 configured clamps * 18 sensors = 36 (power, energy_imp, energy_exp,
        #     rssi, pdr, frequency, 3x voltage, 3x current, 3x power, 3x pf)
        # Total: 28 + 4 + 12 + 36 = 80
        assert len(entities) == 80

    @pytest.mark.asyncio
    async def test_setup_skips_unconfigured_ct(self):
        """CT clamps with null euid should not create entities."""
        from custom_components.homevolt.sensor import async_setup_entry

        coord = _make_coordinator_with_data()
        entry = MagicMock()
        entry.runtime_data = coord

        entities = []

        def capture_entities(ents):
            entities.extend(ents)

        await async_setup_entry(MagicMock(), entry, capture_entities)

        # No entities should have the null euid
        ct_entities = [e for e in entities if hasattr(e, '_euid')]
        for ent in ct_entities:
            assert ent._euid != "0000000000000000"
