"""Tests for Homevolt sensor platform."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

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
from custom_components.homevolt.sensor import (
    SYSTEM_SENSORS,
    VOLTAGE_SENSORS,
    CURRENT_SENSORS,
    BMS_SENSORS,
    CT_SENSORS,
    CT_NODE_SENSORS,
    DIAGNOSTIC_SENSORS,
    STATUS_SENSORS,
    SCHEDULE_SENSORS,
    HomevoltSystemSensor,
    HomevoltStatusSensor,
    HomevoltBmsSensor,
    HomevoltCtSensor,
    HomevoltCtNodeSensor,
    HomevoltScheduleSensor,
    HomevoltErrorReportSensor,
    _error_report_status,
    _error_report_attrs,
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
# System sensor tests
# ---------------------------------------------------------------------------

class TestSystemSensors:
    """Test system-level sensors."""

    def test_battery_soc(self):
        coord = _make_coordinator_with_data()
        # Override soc_avg to test centi-percent conversion
        coord.data.ems.aggregated.ems_data.soc_avg = 8590
        desc = next(d for d in SYSTEM_SENSORS if d.key == "battery_soc")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == pytest.approx(85.9)

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

    def test_phase_angle(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SYSTEM_SENSORS if d.key == "phase_angle")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == 90

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
        # Override soc to test centi-percent conversion
        coord.data.ems.aggregated.bms_data[0].soc = 5830
        desc = next(d for d in BMS_SENSORS if d.key == "bms_soc")
        serial = "80000274099724441432"
        sensor = HomevoltBmsSensor(coord, ECU_ID, 0, serial, desc)
        assert sensor.native_value == pytest.approx(58.3)

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

    def test_bms_alarm_empty(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in BMS_SENSORS if d.key == "bms_alarm")
        serial = "80000274099724441432"
        sensor = HomevoltBmsSensor(coord, ECU_ID, 0, serial, desc)
        assert sensor.native_value is None

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
# CT node sensor tests
# ---------------------------------------------------------------------------

class TestCtNodeSensors:
    """Test CT clamp node sensors (battery, temp, firmware, OTA)."""

    def test_ct_battery_level(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_NODE_SENSORS if d.key == "ct_battery_level")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtNodeSensor(coord, ECU_ID, 0, "grid", euid, 2, desc)
        # 2.73V → (2.73-1.8)/(3.0-1.8)*100 = 77.5%
        assert sensor.native_value == pytest.approx(77.5)

    def test_ct_battery_level_clamped(self):
        """Battery level clamps to 0-100 range."""
        from custom_components.homevolt.sensor import _ct_battery_level
        from custom_components.homevolt.models import NodeMetrics
        low = NodeMetrics(node_id=1, battery_voltage=1.5)
        assert _ct_battery_level(low, None) == 0.0
        high = NodeMetrics(node_id=1, battery_voltage=3.5)
        assert _ct_battery_level(high, None) == 100.0
        assert _ct_battery_level(None, None) is None

    def test_ct_battery_voltage(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_NODE_SENSORS if d.key == "ct_battery_voltage")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtNodeSensor(coord, ECU_ID, 0, "grid", euid, 2, desc)
        assert sensor.native_value == pytest.approx(2.73)

    def test_ct_temperature(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_NODE_SENSORS if d.key == "ct_temperature")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtNodeSensor(coord, ECU_ID, 0, "grid", euid, 2, desc)
        assert sensor.native_value == pytest.approx(-2.28)

    def test_ct_node_uptime(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_NODE_SENSORS if d.key == "ct_node_uptime")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtNodeSensor(coord, ECU_ID, 0, "grid", euid, 2, desc)
        assert sensor.native_value == 6552787

    def test_ct_firmware(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_NODE_SENSORS if d.key == "ct_firmware")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtNodeSensor(coord, ECU_ID, 0, "grid", euid, 2, desc)
        assert sensor.native_value == "1200-373138d6"

    def test_ct_ota_status(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_NODE_SENSORS if d.key == "ct_ota_status")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtNodeSensor(coord, ECU_ID, 0, "grid", euid, 2, desc)
        assert sensor.native_value == "up2date"

    def test_ct_node_missing_metrics_returns_none(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_NODE_SENSORS if d.key == "ct_battery_voltage")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtNodeSensor(coord, ECU_ID, 0, "grid", euid, 99, desc)
        assert sensor.native_value is None

    def test_ct_node_unique_id(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_NODE_SENSORS if d.key == "ct_battery_voltage")
        euid = "a46dd4fffea23d6a"
        sensor = HomevoltCtNodeSensor(coord, ECU_ID, 0, "grid", euid, 2, desc)
        assert sensor._attr_unique_id == f"{euid}_ct_battery_voltage"

    def test_ct_solar_node_temperature(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in CT_NODE_SENSORS if d.key == "ct_temperature")
        euid = "a46dd4fffea284c2"
        sensor = HomevoltCtNodeSensor(coord, ECU_ID, 1, "solar", euid, 3, desc)
        assert sensor.native_value == pytest.approx(17.19)


# ---------------------------------------------------------------------------
# Diagnostic sensor tests
# ---------------------------------------------------------------------------

class TestLineToLineVoltageSensors:
    """Test line-to-line voltage sensors."""

    def test_voltage_l1_l2(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in VOLTAGE_SENSORS if d.key == "voltage_l1_l2")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == pytest.approx(395.1)

    def test_voltage_l2_l3(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in VOLTAGE_SENSORS if d.key == "voltage_l2_l3")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == pytest.approx(392.4)

    def test_voltage_l3_l1(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in VOLTAGE_SENSORS if d.key == "voltage_l3_l1")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == pytest.approx(393.6)


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

    def test_ems_error(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in DIAGNOSTIC_SENSORS if d.key == "ems_error")
        sensor = HomevoltSystemSensor(coord, ECU_ID, desc)
        assert sensor.native_value == "No error"


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
# Error report sensor tests
# ---------------------------------------------------------------------------

class TestErrorReportSensor:
    """Test error report status sensor."""

    def test_state_is_error_with_fixture(self):
        """Fixture has OTA bg95 error + PULSE errors, so state should be 'error'."""
        coord = _make_coordinator_with_data()
        sensor = HomevoltErrorReportSensor(coord, ECU_ID)
        assert sensor.native_value == "error"

    def test_state_is_warning_when_only_warnings(self):
        """When only warnings present, state should be 'warning'."""
        coord = _make_coordinator_with_data()
        coord.data.error_report = [
            ErrorReportEntry(sub_system_name="EMS", error_name="test", activated="ok"),
            ErrorReportEntry(sub_system_name="EMS", error_name="warn", activated="warning", message="low soc"),
        ]
        sensor = HomevoltErrorReportSensor(coord, ECU_ID)
        assert sensor.native_value == "warning"

    def test_state_is_ok_when_all_ok(self):
        """When all entries are ok, state should be 'ok'."""
        coord = _make_coordinator_with_data()
        coord.data.error_report = [
            ErrorReportEntry(sub_system_name="ECU", error_name="power_24v", activated="ok"),
            ErrorReportEntry(sub_system_name="EMS", error_name="connectivity", activated="ok"),
        ]
        sensor = HomevoltErrorReportSensor(coord, ECU_ID)
        assert sensor.native_value == "ok"

    def test_state_is_none_when_empty(self):
        """When error_report is empty, state should be None."""
        coord = _make_coordinator_with_data()
        coord.data.error_report = []
        sensor = HomevoltErrorReportSensor(coord, ECU_ID)
        assert sensor.native_value is None

    def test_extra_attrs_with_fixture(self):
        """Fixture should have correct counts and error/warning details."""
        coord = _make_coordinator_with_data()
        sensor = HomevoltErrorReportSensor(coord, ECU_ID)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["ok_count"] == 24
        assert attrs["warning_count"] == 1
        assert attrs["error_count"] == 9
        assert len(attrs["warnings"]) == 1
        assert attrs["warnings"][0]["subsystem"] == "EMS"
        assert attrs["warnings"][0]["name"] == "ems_warning"
        assert len(attrs["errors"]) == 9
        # Check one specific error
        bg95_errors = [e for e in attrs["errors"] if e["name"] == "Firmware for bg95"]
        assert len(bg95_errors) == 1
        assert bg95_errors[0]["subsystem"] == "OTA"

    def test_extra_attrs_none_when_empty(self):
        """When error_report is empty, extra attrs should be None."""
        coord = _make_coordinator_with_data()
        coord.data.error_report = []
        sensor = HomevoltErrorReportSensor(coord, ECU_ID)
        assert sensor.extra_state_attributes is None

    def test_unique_id(self):
        coord = _make_coordinator_with_data()
        sensor = HomevoltErrorReportSensor(coord, ECU_ID)
        assert sensor._attr_unique_id == f"{ECU_ID}_error_report_status"

    def test_helper_error_report_status_ignores_unknown(self):
        """The 'unknown' status should not affect the worst-status calculation."""
        entries = [
            ErrorReportEntry(activated="ok"),
            ErrorReportEntry(activated="unknown"),
        ]
        assert _error_report_status(entries) == "ok"

    def test_helper_error_report_attrs_counts(self):
        """Test attr helper with mixed statuses."""
        entries = [
            ErrorReportEntry(sub_system_name="A", error_name="a1", activated="ok", message=""),
            ErrorReportEntry(sub_system_name="B", error_name="b1", activated="warning", message="warn msg"),
            ErrorReportEntry(sub_system_name="C", error_name="c1", activated="error", message="err msg"),
            ErrorReportEntry(sub_system_name="D", error_name="d1", activated="unknown", message="unk"),
        ]
        attrs = _error_report_attrs(entries)
        assert attrs["ok_count"] == 1
        assert attrs["warning_count"] == 1
        assert attrs["error_count"] == 1
        assert len(attrs["warnings"]) == 1
        assert attrs["warnings"][0] == {"subsystem": "B", "name": "b1", "message": "warn msg"}
        assert len(attrs["errors"]) == 1
        assert attrs["errors"][0] == {"subsystem": "C", "name": "c1", "message": "err msg"}


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
        # System: 19 + Voltage: 6 + Current: 3 + Diagnostic: 5 = 33 system sensors
        # Status: 4 (uptime, wifi_rssi, firmware_esp, firmware_efr)
        # Error report: 1
        # Schedule: 3 (current_action, next_action, entry_count)
        # BMS: 2 modules * 7 sensors = 14
        # CT: 2 configured clamps * 18 sensors = 36
        # CT Node: 2 configured clamps * 6 sensors = 12
        # Total: 33 + 4 + 1 + 3 + 14 + 36 + 12 = 103
        assert len(entities) == 103

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


# ---------------------------------------------------------------------------
# Schedule sensor tests
# ---------------------------------------------------------------------------

class TestScheduleSensors:
    """Test schedule sensors."""

    def test_schedule_entry_count(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SCHEDULE_SENSORS if d.key == "schedule_entry_count")
        sensor = HomevoltScheduleSensor(coord, ECU_ID, desc)
        assert sensor.native_value == 6

    def test_schedule_entry_count_none(self):
        """When schedule is None, entry count returns None."""
        coord = _make_coordinator_with_data()
        coord.data.schedule = None
        desc = next(d for d in SCHEDULE_SENSORS if d.key == "schedule_entry_count")
        sensor = HomevoltScheduleSensor(coord, ECU_ID, desc)
        assert sensor.native_value is None

    def test_schedule_current_action_during_grid_charge(self):
        """When time falls within a grid-charge entry, show the action."""
        coord = _make_coordinator_with_data()
        desc = next(d for d in SCHEDULE_SENSORS if d.key == "schedule_current_action")
        sensor = HomevoltScheduleSensor(coord, ECU_ID, desc)

        # Entry 1: from_ts=1739667600 to_ts=1739674800, type=3 (Grid Charge), setpoint=17250
        mock_now = datetime.fromtimestamp(1739670000, tz=timezone.utc)
        with patch("custom_components.homevolt.sensor.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.fromtimestamp = datetime.fromtimestamp
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert sensor.native_value == "Grid Charge (17250 W)"

    def test_schedule_current_action_during_idle(self):
        """When time falls within an idle entry, show Idle."""
        coord = _make_coordinator_with_data()
        desc = next(d for d in SCHEDULE_SENSORS if d.key == "schedule_current_action")
        sensor = HomevoltScheduleSensor(coord, ECU_ID, desc)

        # Entry 0: from_ts=1739664000 to_ts=1739667600, type=0 (Idle)
        mock_now = datetime.fromtimestamp(1739665000, tz=timezone.utc)
        with patch("custom_components.homevolt.sensor.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.fromtimestamp = datetime.fromtimestamp
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert sensor.native_value == "Idle"

    def test_schedule_current_action_no_match(self):
        """When time is outside all entries, return None."""
        coord = _make_coordinator_with_data()
        desc = next(d for d in SCHEDULE_SENSORS if d.key == "schedule_current_action")
        sensor = HomevoltScheduleSensor(coord, ECU_ID, desc)

        # Before all entries
        mock_now = datetime.fromtimestamp(1739660000, tz=timezone.utc)
        with patch("custom_components.homevolt.sensor.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.fromtimestamp = datetime.fromtimestamp
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert sensor.native_value is None

    def test_schedule_next_action_from_idle(self):
        """Next action from idle should show the next non-idle entry."""
        coord = _make_coordinator_with_data()
        desc = next(d for d in SCHEDULE_SENSORS if d.key == "schedule_next_action")
        sensor = HomevoltScheduleSensor(coord, ECU_ID, desc)

        # During entry 0 (idle), next should be entry 1 (grid charge)
        mock_now = datetime.fromtimestamp(1739665000, tz=timezone.utc)
        with patch("custom_components.homevolt.sensor.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.fromtimestamp = datetime.fromtimestamp
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            value = sensor.native_value
            assert value is not None
            assert "Grid Charge" in value

    def test_schedule_next_action_none_when_empty(self):
        """When schedule is empty, next action returns None."""
        coord = _make_coordinator_with_data()
        coord.data.schedule = ScheduleData()
        desc = next(d for d in SCHEDULE_SENSORS if d.key == "schedule_next_action")
        sensor = HomevoltScheduleSensor(coord, ECU_ID, desc)
        assert sensor.native_value is None

    def test_schedule_current_action_attrs(self):
        """Current action should include extra attributes."""
        coord = _make_coordinator_with_data()
        desc = next(d for d in SCHEDULE_SENSORS if d.key == "schedule_current_action")
        sensor = HomevoltScheduleSensor(coord, ECU_ID, desc)

        mock_now = datetime.fromtimestamp(1739670000, tz=timezone.utc)
        with patch("custom_components.homevolt.sensor.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.fromtimestamp = datetime.fromtimestamp
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            attrs = sensor.extra_state_attributes
            assert attrs is not None
            assert attrs["schedule_id"] == "tibber_schedule_2026-02-16T00:00:00Z"
            assert attrs["type"] == 3
            assert attrs["setpoint"] == 17250
            assert "from" in attrs
            assert "to" in attrs
            assert "schedule" in attrs
            assert len(attrs["schedule"]) == 6

    def test_schedule_current_action_attrs_none_schedule(self):
        """When schedule is None, attrs returns None."""
        coord = _make_coordinator_with_data()
        coord.data.schedule = None
        desc = next(d for d in SCHEDULE_SENSORS if d.key == "schedule_current_action")
        sensor = HomevoltScheduleSensor(coord, ECU_ID, desc)
        assert sensor.extra_state_attributes is None

    def test_schedule_no_extra_attrs_for_count(self):
        """Entry count sensor has no extra attributes."""
        coord = _make_coordinator_with_data()
        desc = next(d for d in SCHEDULE_SENSORS if d.key == "schedule_entry_count")
        sensor = HomevoltScheduleSensor(coord, ECU_ID, desc)
        assert sensor.extra_state_attributes is None

    def test_schedule_unique_id(self):
        coord = _make_coordinator_with_data()
        desc = next(d for d in SCHEDULE_SENSORS if d.key == "schedule_current_action")
        sensor = HomevoltScheduleSensor(coord, ECU_ID, desc)
        assert sensor._attr_unique_id == f"{ECU_ID}_schedule_current_action"
