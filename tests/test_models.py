"""Tests for Homevolt data models."""

import json
from pathlib import Path

import pytest

from custom_components.homevolt.models import (
    HomevoltEmsResponse,
    HomevoltStatusResponse,
    ErrorReportEntry,
    NodeMetrics,
    NodeInfo,
    ScheduleData,
    ScheduleEntry,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_ems_response():
    """Test parsing a real /ems.json response."""
    data = json.loads((FIXTURES / "ems_response.json").read_text())
    response = HomevoltEmsResponse.from_dict(data)

    assert response.type == "ems_data"
    assert response.ts > 0
    assert len(response.ems) == 1
    assert response.aggregated.ecu_id == 0  # aggregated has ecu_id 0
    assert response.aggregated.ems_info.rated_capacity == 13304
    assert response.aggregated.ems_info.rated_power == 6000
    assert response.aggregated.ems_info.fw_version == "v31.4"


def test_parse_ems_device():
    """Test EMS device parsing."""
    data = json.loads((FIXTURES / "ems_response.json").read_text())
    device = HomevoltEmsResponse.from_dict(data).ems[0]

    assert device.ecu_id == 9731192375880
    assert device.op_state_str == "idle"
    assert device.error_str == "No error"
    assert len(device.bms_info) == 2
    assert device.bms_info[0].serial_number == "80000274099724441432"
    assert device.bms_info[1].serial_number == "80000274099724441534"
    assert device.inv_info.fw_version == "V1.10-97.0"


def test_parse_bms_data():
    """Test BMS battery module data parsing."""
    data = json.loads((FIXTURES / "ems_response.json").read_text())
    bms = HomevoltEmsResponse.from_dict(data).aggregated.bms_data

    assert len(bms) == 2
    assert bms[0].state_str == "Connected"
    assert bms[0].cycle_count == 295
    assert bms[1].cycle_count == 290


def test_parse_ems_voltage():
    """Test voltage parsing (decivolts)."""
    data = json.loads((FIXTURES / "ems_response.json").read_text())
    voltage = HomevoltEmsResponse.from_dict(data).aggregated.ems_voltage

    assert voltage.l1 == 2280
    assert voltage.l2 == 2265
    assert voltage.l3 == 2274


def test_parse_sensors():
    """Test CT clamp sensor parsing."""
    data = json.loads((FIXTURES / "ems_response.json").read_text())
    sensors = HomevoltEmsResponse.from_dict(data).sensors

    assert len(sensors) == 3
    # Energy values should be populated even when sensors are offline
    assert sensors[0].energy_imported == 14787.84
    assert sensors[0].energy_exported == 8059.11


def test_parse_status_response():
    """Test parsing /status.json response."""
    data = json.loads((FIXTURES / "status_response.json").read_text())
    status = HomevoltStatusResponse.from_dict(data)

    assert status.up_time > 0
    assert status.firmware.esp == "2929-a1e89e8d"
    assert status.wifi_status.connected is True
    assert status.mqtt_status.connected is True


def test_parse_error_report():
    """Test parsing /error_report.json response."""
    data = json.loads((FIXTURES / "error_report_response.json").read_text())
    entries = [ErrorReportEntry.from_dict(e) for e in data]

    assert len(entries) > 0
    # Find the EMS warning
    ems_warnings = [
        e for e in entries if e.sub_system_name == "EMS" and e.activated == "warning"
    ]
    assert len(ems_warnings) >= 1


def test_parse_empty_data():
    """Test models handle missing/empty data gracefully."""
    response = HomevoltEmsResponse.from_dict({})
    assert response.type == ""
    assert response.ts == 0
    assert len(response.ems) == 0
    assert response.aggregated.ems_info.rated_capacity == 0


def test_parse_ems_data_fields():
    """Test EMS real-time data fields parsing."""
    data = json.loads((FIXTURES / "ems_response.json").read_text())
    ems_data = HomevoltEmsResponse.from_dict(data).aggregated.ems_data

    assert ems_data.timestamp_ms > 0
    assert ems_data.state_str == "Throttled"
    assert "EMS_INFO_CONNECTED_TO_BACKEND" in ems_data.info_str
    assert "EMS_WARNING_UNDER_SOC_MIN_WARNING" in ems_data.warning_str
    assert ems_data.alarm_str == []
    assert ems_data.frequency == 49969  # centi-Hz
    assert ems_data.energy_produced == 3777576  # Wh
    assert ems_data.energy_consumed == 4290436  # Wh
    assert ems_data.sys_temp == 46  # decicelsius


def test_parse_ems_config():
    """Test EMS configuration parsing."""
    data = json.loads((FIXTURES / "ems_response.json").read_text())
    config = HomevoltEmsResponse.from_dict(data).ems[0].ems_config

    assert config.grid_code_preset == 9
    assert config.grid_code_preset_str == "Sweden"
    assert config.control_timeout is True


def test_parse_ems_prediction():
    """Test EMS prediction parsing."""
    data = json.loads((FIXTURES / "ems_response.json").read_text())
    prediction = HomevoltEmsResponse.from_dict(data).aggregated.ems_prediction

    assert prediction.avail_ch_pwr == 3528
    assert prediction.avail_di_pwr == 0
    assert prediction.avail_ch_energy == 12218
    assert prediction.avail_di_energy == 0


def test_parse_ems_aggregate():
    """Test EMS aggregate energy data parsing."""
    data = json.loads((FIXTURES / "ems_response.json").read_text())
    aggregate = HomevoltEmsResponse.from_dict(data).aggregated.ems_aggregate

    assert aggregate.imported_kwh == 3791.99
    assert aggregate.exported_kwh == 4350.4


def test_parse_sensor_phases():
    """Test that sensor phase data is properly parsed."""
    data = json.loads((FIXTURES / "ems_response.json").read_text())
    sensors = HomevoltEmsResponse.from_dict(data).sensors

    # All sensors should have 3 phases
    for sensor in sensors:
        assert len(sensor.phase) == 3

    # First two sensors are online (grid + solar), third is unconfigured
    assert sensors[0].available is True
    assert sensors[0].type == "grid"
    assert sensors[0].euid == "a46dd4fffea23d6a"
    assert sensors[0].phase[0].voltage == 253.4

    assert sensors[1].available is True
    assert sensors[1].type == "solar"
    assert sensors[1].euid == "a46dd4fffea284c2"

    assert sensors[2].available is False
    assert sensors[2].type == "unspecified"
    assert sensors[2].euid == "0000000000000000"


def test_parse_status_lte():
    """Test LTE status parsing."""
    data = json.loads((FIXTURES / "status_response.json").read_text())
    status = HomevoltStatusResponse.from_dict(data)

    assert status.lte_status.operator_name == "Telenor SE"
    assert status.lte_status.rssi_db == -45
    assert status.lte_status.pdp_active is True


def test_parse_status_wifi():
    """Test WiFi status parsing."""
    data = json.loads((FIXTURES / "status_response.json").read_text())
    status = HomevoltStatusResponse.from_dict(data)

    assert status.wifi_status.wifi_mode == "sta"
    assert status.wifi_status.ip == "192.168.70.12"
    assert status.wifi_status.rssi == -60


def test_parse_error_report_details():
    """Test error report entries with details."""
    data = json.loads((FIXTURES / "error_report_response.json").read_text())
    entries = [ErrorReportEntry.from_dict(e) for e in data]

    # Find the EMS info entry which has details
    ems_info = [
        e for e in entries if e.sub_system_name == "EMS" and e.error_name == "ems_info"
    ]
    assert len(ems_info) == 1
    assert "EMS_INFO_CONNECTED_TO_BACKEND" in ems_info[0].details
    assert "EMS_INFO_RTC_SYNCRONIZED" in ems_info[0].details
    assert "EMS_INFO_LOW_POWER_MODE" in ems_info[0].details


def test_parse_error_report_subsystems():
    """Test that all expected subsystems are present in error report."""
    data = json.loads((FIXTURES / "error_report_response.json").read_text())
    entries = [ErrorReportEntry.from_dict(e) for e in data]

    subsystems = {e.sub_system_name for e in entries}
    assert "ECU" in subsystems
    assert "EMS" in subsystems
    assert "CONNECTIVITY" in subsystems
    assert "OTA" in subsystems


def test_bms_info_rated_cap():
    """Test BMS info rated capacity."""
    data = json.loads((FIXTURES / "ems_response.json").read_text())
    device = HomevoltEmsResponse.from_dict(data).ems[0]

    assert device.bms_info[0].rated_cap == 6652
    assert device.bms_info[1].rated_cap == 6652
    assert device.bms_info[0].id == 0
    assert device.bms_info[1].id == 1


def test_parse_node_metrics():
    """Test parsing /node_metrics.json response."""
    data = json.loads((FIXTURES / "node_metrics_2_response.json").read_text())
    metrics = NodeMetrics.from_dict(data)

    assert metrics.node_id == 2
    assert metrics.battery_voltage == pytest.approx(2.73)
    assert metrics.temperature == pytest.approx(-2.28)
    assert metrics.usb_power is False
    assert metrics.node_uptime == 6552787
    assert metrics.radio_tx_power == 159
    assert metrics.packet_delivery_rate == pytest.approx(100.0)


def test_parse_node_metrics_empty():
    """Test NodeMetrics handles empty data gracefully."""
    metrics = NodeMetrics.from_dict({})

    assert metrics.node_id == 0
    assert metrics.battery_voltage == 0.0
    assert metrics.temperature == 0.0
    assert metrics.usb_power is False
    assert metrics.node_uptime == 0
    assert metrics.packet_delivery_rate == 0.0


def test_parse_nodes_response():
    """Test parsing /nodes.json response list."""
    data = json.loads((FIXTURES / "nodes_response.json").read_text())
    nodes = [NodeInfo.from_dict(n) for n in data]

    assert len(nodes) == 2
    assert nodes[0].node_id == 2
    assert nodes[0].eui == "a46dd4fffea23d6a"
    assert nodes[0].version == "1200-373138d6"
    assert nodes[0].ota_distribute_status == "up2date"
    assert nodes[0].manifest_version == "1200-373138d6"
    assert nodes[0].available is True

    assert nodes[1].node_id == 3
    assert nodes[1].eui == "a46dd4fffea284c2"
    assert nodes[1].version == "1186-5236fb04"
    assert nodes[1].ota_distribute_status == "firmware_unverified"
    assert nodes[1].manifest_version == "1200-373138d6"


def test_parse_node_info_empty():
    """Test NodeInfo handles empty data gracefully."""
    node = NodeInfo.from_dict({})

    assert node.node_id == 0
    assert node.eui == ""
    assert node.version == ""
    assert node.model == ""
    assert node.available is False
    assert node.ota_distribute_status == ""
    assert node.manifest_version == ""


# ---------------------------------------------------------------------------
# Schedule model tests
# ---------------------------------------------------------------------------


def test_parse_schedule_response():
    """Test parsing /schedule.json response."""
    data = json.loads((FIXTURES / "schedule_response.json").read_text())
    schedule = ScheduleData.from_dict(data)

    assert schedule.local_mode is False
    assert schedule.schedule_id == "tibber_schedule_2026-02-16T00:00:00Z"
    assert len(schedule.entries) == 6


def test_parse_schedule_entry_types():
    """Test schedule entry type parsing."""
    data = json.loads((FIXTURES / "schedule_response.json").read_text())
    schedule = ScheduleData.from_dict(data)

    assert schedule.entries[0].type == 0  # idle
    assert schedule.entries[0].type_name == "Idle"
    assert schedule.entries[1].type == 3  # grid-charge
    assert schedule.entries[1].type_name == "Grid Charge"
    assert schedule.entries[3].type == 4  # grid-discharge
    assert schedule.entries[3].type_name == "Grid Discharge"


def test_parse_schedule_entry_fields():
    """Test schedule entry field parsing."""
    data = json.loads((FIXTURES / "schedule_response.json").read_text())
    entry = ScheduleData.from_dict(data).entries[1]

    assert entry.id == 1
    assert entry.from_ts == 1739667600
    assert entry.to_ts == 1739674800
    assert entry.setpoint == 17250
    assert entry.main_fuse == 25000


def test_parse_schedule_empty():
    """Test ScheduleData handles empty data gracefully."""
    schedule = ScheduleData.from_dict({})

    assert schedule.local_mode is False
    assert schedule.schedule_id == ""
    assert len(schedule.entries) == 0


def test_parse_schedule_entry_empty():
    """Test ScheduleEntry handles empty data gracefully."""
    entry = ScheduleEntry.from_dict({})

    assert entry.id == 0
    assert entry.from_ts == 0
    assert entry.to_ts == 0
    assert entry.type == 0
    assert entry.setpoint == 0
    assert entry.main_fuse == 0
    assert entry.type_name == "Idle"


def test_schedule_entry_unknown_type():
    """Test ScheduleEntry returns descriptive string for unknown types."""
    entry = ScheduleEntry.from_dict({"type": 99})
    assert entry.type_name == "Unknown (99)"
