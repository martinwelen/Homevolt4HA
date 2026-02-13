"""Tests for Homevolt data models."""

import json
from pathlib import Path

from custom_components.homevolt.models import (
    HomevoltEmsResponse,
    HomevoltStatusResponse,
    ErrorReportEntry,
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

    # All sensors are currently offline
    for sensor in sensors:
        assert sensor.available is False
        assert sensor.type == "unspecified"


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
