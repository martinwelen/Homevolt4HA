# Homevolt HA Integration - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Home Assistant custom integration that polls a Homevolt battery system's local HTTP API and exposes battery, energy, and diagnostic data as HA sensors.

**Architecture:** Single DataUpdateCoordinator with tiered polling - `/ems.json` every cycle (30s), `/error_report.json` every 4th cycle, `/status.json` every 10th cycle. Standalone API client class handles HTTP with retry. Dataclass models parse API responses. Config flow supports manual entry and Zeroconf discovery.

**Tech Stack:** Python 3.12+, Home Assistant 2025.1+, aiohttp, voluptuous, pytest + pytest-homeassistant-custom-component

**Live API reference:** The device at `http://192.168.70.12` is accessible for testing. No password required.

**IMPORTANT - Dynamic Hardware:** Not all Homevolt systems have the same hardware configuration. Some have 1 battery module, others have 2. Some have CT clamps (grid, solar, load), others have none. The integration MUST:
- Dynamically create BMS entities based on `len(ems.aggregated.bms_data)` -- not hardcoded to 2
- Dynamically create CT sensor entities based on `len(ems.sensors)` and check each sensor's `type` and `euid` -- skip sensors with `euid == "0000000000000000"` (unconfigured) or where `type == "unspecified"`
- Handle the case where `bms_info` and `bms_data` arrays have different lengths gracefully
- Handle missing/empty fields in all API responses with safe defaults

---

## Task 1: Project Scaffolding

**Files:**
- Create: `custom_components/homevolt/manifest.json`
- Create: `custom_components/homevolt/const.py`
- Create: `custom_components/homevolt/__init__.py` (stub)
- Create: `hacs.json`
- Create: `.gitignore`
- Create: `requirements_test.txt`

**Step 1: Create .gitignore**

```
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.eggs/
*.egg
.venv/
venv/
.env
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
```

**Step 2: Create manifest.json**

```json
{
  "domain": "homevolt",
  "name": "Homevolt",
  "codeowners": ["@martinwelen"],
  "config_flow": true,
  "documentation": "https://github.com/martinwelen/Homevolt4HA",
  "integration_type": "hub",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/martinwelen/Homevolt4HA/issues",
  "requirements": [],
  "version": "0.1.0",
  "zeroconf": [
    {
      "type": "_http._tcp.local.",
      "name": "homevolt*"
    }
  ]
}
```

**Step 3: Create const.py**

```python
"""Constants for the Homevolt integration."""

from typing import Final

DOMAIN: Final = "homevolt"

# API endpoints
ENDPOINT_EMS: Final = "/ems.json"
ENDPOINT_STATUS: Final = "/status.json"
ENDPOINT_PARAMS: Final = "/params.json"
ENDPOINT_ERROR_REPORT: Final = "/error_report.json"
ENDPOINT_SCHEDULE: Final = "/schedule.json"
ENDPOINT_CONSOLE: Final = "/console.json"
ENDPOINT_NODES: Final = "/nodes.json"

# Config keys
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Defaults
DEFAULT_SCAN_INTERVAL: Final = 30
DEFAULT_PORT: Final = 80
DEFAULT_CONNECT_TIMEOUT: Final = 5
DEFAULT_READ_TIMEOUT: Final = 20

# Tiered polling intervals (in number of cycles)
STATUS_POLL_INTERVAL: Final = 10  # Every 10th cycle (~5 min at 30s)
ERROR_REPORT_POLL_INTERVAL: Final = 4  # Every 4th cycle (~2 min at 30s)

# Manufacturer info
MANUFACTURER: Final = "Tibber / Polarium"
```

**Step 4: Create stub __init__.py**

```python
"""The Homevolt integration."""
```

**Step 5: Create hacs.json**

```json
{
  "name": "Homevolt",
  "render_readme": true
}
```

**Step 6: Create requirements_test.txt**

```
pytest==8.3.4
pytest-asyncio==0.24.0
pytest-homeassistant-custom-component==0.13.196
aioresponses==0.7.7
```

**Step 7: Commit**

```bash
git add .gitignore hacs.json requirements_test.txt \
  custom_components/homevolt/manifest.json \
  custom_components/homevolt/const.py \
  custom_components/homevolt/__init__.py
git commit -m "feat: scaffold project with manifest, constants, and config"
```

---

## Task 2: Data Models

**Files:**
- Create: `custom_components/homevolt/models.py`
- Create: `tests/__init__.py`
- Create: `tests/test_models.py`
- Create: `tests/fixtures/ems_response.json` (copy of live API response)

**Step 1: Save a fixture of the live API response**

Fetch `http://192.168.70.12/ems.json` and save to `tests/fixtures/ems_response.json` (formatted).

Also fetch `http://192.168.70.12/status.json` -> `tests/fixtures/status_response.json`
Also fetch `http://192.168.70.12/error_report.json` -> `tests/fixtures/error_report_response.json`

**Step 2: Write the models**

Create `models.py` with dataclasses that parse the API JSON. Use `@dataclass` with a `from_dict` classmethod pattern for each model:

```python
"""Data models for the Homevolt API responses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmsInfo:
    """EMS system information."""

    protocol_version: int = 0
    fw_version: str = ""
    rated_capacity: int = 0  # Wh
    rated_power: int = 0  # W

    @classmethod
    def from_dict(cls, data: dict) -> EmsInfo:
        return cls(
            protocol_version=data.get("protocol_version", 0),
            fw_version=data.get("fw_version", ""),
            rated_capacity=data.get("rated_capacity", 0),
            rated_power=data.get("rated_power", 0),
        )


@dataclass
class BmsInfo:
    """Battery Management System info."""

    fw_version: str = ""
    serial_number: str = ""
    rated_cap: int = 0  # Wh
    id: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> BmsInfo:
        return cls(
            fw_version=data.get("fw_version", ""),
            serial_number=data.get("serial_number", ""),
            rated_cap=data.get("rated_cap", 0),
            id=data.get("id", 0),
        )


@dataclass
class InvInfo:
    """Inverter information."""

    fw_version: str = ""
    serial_number: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> InvInfo:
        return cls(
            fw_version=data.get("fw_version", ""),
            serial_number=data.get("serial_number", ""),
        )


@dataclass
class EmsConfig:
    """EMS configuration."""

    grid_code_preset: int = 0
    grid_code_preset_str: str = ""
    control_timeout: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> EmsConfig:
        return cls(
            grid_code_preset=data.get("grid_code_preset", 0),
            grid_code_preset_str=data.get("grid_code_preset_str", ""),
            control_timeout=data.get("control_timeout", False),
        )


@dataclass
class EmsControl:
    """EMS control state."""

    mode_sel: int = 0
    mode_sel_str: str = ""
    pwr_ref: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> EmsControl:
        return cls(
            mode_sel=data.get("mode_sel", 0),
            mode_sel_str=data.get("mode_sel_str", ""),
            pwr_ref=data.get("pwr_ref", 0),
        )


@dataclass
class EmsData:
    """Real-time EMS data."""

    timestamp_ms: int = 0
    state: int = 0
    state_str: str = ""
    info: int = 0
    info_str: list[str] = field(default_factory=list)
    warning: int = 0
    warning_str: list[str] = field(default_factory=list)
    alarm: int = 0
    alarm_str: list[str] = field(default_factory=list)
    phase_angle: int = 0
    frequency: int = 0  # centi-Hz (50040 = 50.040 Hz)
    phase_seq: int = 0
    power: int = 0  # W (positive=discharge, negative=charge)
    apparent_power: int = 0  # VA
    reactive_power: int = 0  # var
    energy_produced: int = 0  # Wh
    energy_consumed: int = 0  # Wh
    sys_temp: int = 0  # decicelsius (60 = 6.0 C)
    avail_cap: int = 0  # Wh
    freq_res_state: int = 0
    soc_avg: int = 0  # percentage

    @classmethod
    def from_dict(cls, data: dict) -> EmsData:
        return cls(
            timestamp_ms=data.get("timestamp_ms", 0),
            state=data.get("state", 0),
            state_str=data.get("state_str", ""),
            info=data.get("info", 0),
            info_str=data.get("info_str", []),
            warning=data.get("warning", 0),
            warning_str=data.get("warning_str", []),
            alarm=data.get("alarm", 0),
            alarm_str=data.get("alarm_str", []),
            phase_angle=data.get("phase_angle", 0),
            frequency=data.get("frequency", 0),
            phase_seq=data.get("phase_seq", 0),
            power=data.get("power", 0),
            apparent_power=data.get("apparent_power", 0),
            reactive_power=data.get("reactive_power", 0),
            energy_produced=data.get("energy_produced", 0),
            energy_consumed=data.get("energy_consumed", 0),
            sys_temp=data.get("sys_temp", 0),
            avail_cap=data.get("avail_cap", 0),
            freq_res_state=data.get("freq_res_state", 0),
            soc_avg=data.get("soc_avg", 0),
        )


@dataclass
class BmsData:
    """Per-battery module data."""

    energy_avail: int = 0  # Wh
    cycle_count: int = 0
    soc: int = 0  # percentage
    state: int = 0
    state_str: str = ""
    alarm: int = 0
    alarm_str: list[str] = field(default_factory=list)
    tmin: int = 0  # decicelsius
    tmax: int = 0  # decicelsius

    @classmethod
    def from_dict(cls, data: dict) -> BmsData:
        return cls(
            energy_avail=data.get("energy_avail", 0),
            cycle_count=data.get("cycle_count", 0),
            soc=data.get("soc", 0),
            state=data.get("state", 0),
            state_str=data.get("state_str", ""),
            alarm=data.get("alarm", 0),
            alarm_str=data.get("alarm_str", []),
            tmin=data.get("tmin", 0),
            tmax=data.get("tmax", 0),
        )


@dataclass
class EmsPrediction:
    """Available charge/discharge predictions."""

    avail_ch_pwr: int = 0  # W
    avail_di_pwr: int = 0  # W
    avail_ch_energy: int = 0  # Wh
    avail_di_energy: int = 0  # Wh
    avail_inv_ch_pwr: int = 0  # W
    avail_inv_di_pwr: int = 0  # W
    avail_group_fuse_ch_pwr: int = 0  # W
    avail_group_fuse_di_pwr: int = 0  # W

    @classmethod
    def from_dict(cls, data: dict) -> EmsPrediction:
        return cls(
            avail_ch_pwr=data.get("avail_ch_pwr", 0),
            avail_di_pwr=data.get("avail_di_pwr", 0),
            avail_ch_energy=data.get("avail_ch_energy", 0),
            avail_di_energy=data.get("avail_di_energy", 0),
            avail_inv_ch_pwr=data.get("avail_inv_ch_pwr", 0),
            avail_inv_di_pwr=data.get("avail_inv_di_pwr", 0),
            avail_group_fuse_ch_pwr=data.get("avail_group_fuse_ch_pwr", 0),
            avail_group_fuse_di_pwr=data.get("avail_group_fuse_di_pwr", 0),
        )


@dataclass
class EmsVoltage:
    """Phase voltages (in decivolts, e.g. 2303 = 230.3V)."""

    l1: int = 0
    l2: int = 0
    l3: int = 0
    l1_l2: int = 0
    l2_l3: int = 0
    l3_l1: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> EmsVoltage:
        return cls(
            l1=data.get("l1", 0),
            l2=data.get("l2", 0),
            l3=data.get("l3", 0),
            l1_l2=data.get("l1_l2", 0),
            l2_l3=data.get("l2_l3", 0),
            l3_l1=data.get("l3_l1", 0),
        )


@dataclass
class EmsCurrent:
    """Phase currents (in deciamps)."""

    l1: int = 0
    l2: int = 0
    l3: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> EmsCurrent:
        return cls(
            l1=data.get("l1", 0),
            l2=data.get("l2", 0),
            l3=data.get("l3", 0),
        )


@dataclass
class EmsAggregate:
    """Aggregated energy data."""

    imported_kwh: float = 0.0
    exported_kwh: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> EmsAggregate:
        return cls(
            imported_kwh=data.get("imported_kwh", 0.0),
            exported_kwh=data.get("exported_kwh", 0.0),
        )


@dataclass
class EmsDevice:
    """A single EMS device (inverter + batteries)."""

    ecu_id: int = 0
    ecu_host: str = ""
    ecu_version: str = ""
    error: int = 0
    error_str: str = ""
    op_state: int = 0
    op_state_str: str = ""
    ems_info: EmsInfo = field(default_factory=EmsInfo)
    bms_info: list[BmsInfo] = field(default_factory=list)
    inv_info: InvInfo = field(default_factory=InvInfo)
    ems_config: EmsConfig = field(default_factory=EmsConfig)
    ems_control: EmsControl = field(default_factory=EmsControl)
    ems_data: EmsData = field(default_factory=EmsData)
    bms_data: list[BmsData] = field(default_factory=list)
    ems_prediction: EmsPrediction = field(default_factory=EmsPrediction)
    ems_voltage: EmsVoltage = field(default_factory=EmsVoltage)
    ems_current: EmsCurrent = field(default_factory=EmsCurrent)
    ems_aggregate: EmsAggregate = field(default_factory=EmsAggregate)
    error_cnt: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> EmsDevice:
        return cls(
            ecu_id=data.get("ecu_id", 0),
            ecu_host=data.get("ecu_host", ""),
            ecu_version=data.get("ecu_version", ""),
            error=data.get("error", 0),
            error_str=data.get("error_str", ""),
            op_state=data.get("op_state", 0),
            op_state_str=data.get("op_state_str", ""),
            ems_info=EmsInfo.from_dict(data.get("ems_info", {})),
            bms_info=[BmsInfo.from_dict(b) for b in data.get("bms_info", [])],
            inv_info=InvInfo.from_dict(data.get("inv_info", {})),
            ems_config=EmsConfig.from_dict(data.get("ems_config", {})),
            ems_control=EmsControl.from_dict(data.get("ems_control", {})),
            ems_data=EmsData.from_dict(data.get("ems_data", {})),
            bms_data=[BmsData.from_dict(b) for b in data.get("bms_data", [])],
            ems_prediction=EmsPrediction.from_dict(data.get("ems_prediction", {})),
            ems_voltage=EmsVoltage.from_dict(data.get("ems_voltage", {})),
            ems_current=EmsCurrent.from_dict(data.get("ems_current", {})),
            ems_aggregate=EmsAggregate.from_dict(data.get("ems_aggregate", {})),
            error_cnt=data.get("error_cnt", 0),
        )


@dataclass
class PhaseData:
    """Per-phase CT clamp measurement."""

    voltage: float = 0.0
    amp: float = 0.0
    power: float = 0.0
    pf: float = 0.0  # power factor

    @classmethod
    def from_dict(cls, data: dict) -> PhaseData:
        return cls(
            voltage=data.get("voltage", 0.0),
            amp=data.get("amp", 0.0),
            power=data.get("power", 0.0),
            pf=data.get("pf", 0.0),
        )


@dataclass
class SensorData:
    """CT clamp sensor data (grid, solar, load)."""

    type: str = ""
    node_id: int = 0
    euid: str = ""
    interface: int = 0
    available: bool = False
    rssi: float = 0.0
    average_rssi: float = 0.0
    pdr: float = 0.0  # packet delivery rate %
    phase: list[PhaseData] = field(default_factory=list)
    frequency: float = 0.0
    total_power: int = 0  # W
    energy_imported: float = 0.0  # kWh
    energy_exported: float = 0.0  # kWh
    timestamp: int = 0
    timestamp_str: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> SensorData:
        return cls(
            type=data.get("type", ""),
            node_id=data.get("node_id", 0),
            euid=data.get("euid", ""),
            interface=data.get("interface", 0),
            available=data.get("available", False),
            rssi=data.get("rssi", 0.0),
            average_rssi=data.get("average_rssi", 0.0),
            pdr=data.get("pdr", 0.0),
            phase=[PhaseData.from_dict(p) for p in data.get("phase", [])],
            frequency=data.get("frequency", 0.0),
            total_power=data.get("total_power", 0),
            energy_imported=data.get("energy_imported", 0.0),
            energy_exported=data.get("energy_exported", 0.0),
            timestamp=data.get("timestamp", 0),
            timestamp_str=data.get("timestamp_str", ""),
        )


@dataclass
class HomevoltEmsResponse:
    """Top-level response from /ems.json."""

    type: str = ""
    ts: int = 0
    ems: list[EmsDevice] = field(default_factory=list)
    aggregated: EmsDevice = field(default_factory=EmsDevice)
    sensors: list[SensorData] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> HomevoltEmsResponse:
        return cls(
            type=data.get("$type", ""),
            ts=data.get("ts", 0),
            ems=[EmsDevice.from_dict(e) for e in data.get("ems", [])],
            aggregated=EmsDevice.from_dict(data.get("aggregated", {})),
            sensors=[SensorData.from_dict(s) for s in data.get("sensors", [])],
        )


@dataclass
class WifiStatus:
    """WiFi status from /status.json."""

    wifi_mode: str = ""
    ip: str = ""
    ssid: str = ""
    rssi: int = 0
    connected: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> WifiStatus:
        return cls(
            wifi_mode=data.get("wifi_mode", ""),
            ip=data.get("ip", ""),
            ssid=data.get("ssid", ""),
            rssi=data.get("rssi", 0),
            connected=data.get("connected", False),
        )


@dataclass
class MqttStatus:
    """MQTT status from /status.json."""

    connected: bool = False
    subscribed: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> MqttStatus:
        return cls(
            connected=data.get("connected", False),
            subscribed=data.get("subscribed", False),
        )


@dataclass
class LteStatus:
    """LTE status from /status.json."""

    operator_name: str = ""
    band: str = ""
    rssi_db: int = 0
    pdp_active: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> LteStatus:
        return cls(
            operator_name=data.get("operator_name", ""),
            band=data.get("band", ""),
            rssi_db=data.get("rssi_db", 0),
            pdp_active=data.get("pdp_active", False),
        )


@dataclass
class FirmwareInfo:
    """Firmware versions from /status.json."""

    esp: str = ""
    efr: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> FirmwareInfo:
        return cls(
            esp=data.get("esp", ""),
            efr=data.get("efr", ""),
        )


@dataclass
class HomevoltStatusResponse:
    """Response from /status.json."""

    up_time: int = 0
    firmware: FirmwareInfo = field(default_factory=FirmwareInfo)
    wifi_status: WifiStatus = field(default_factory=WifiStatus)
    mqtt_status: MqttStatus = field(default_factory=MqttStatus)
    lte_status: LteStatus = field(default_factory=LteStatus)

    @classmethod
    def from_dict(cls, data: dict) -> HomevoltStatusResponse:
        return cls(
            up_time=data.get("up_time", 0),
            firmware=FirmwareInfo.from_dict(data.get("firmware", {})),
            wifi_status=WifiStatus.from_dict(data.get("wifi_status", {})),
            mqtt_status=MqttStatus.from_dict(data.get("mqtt_status", {})),
            lte_status=LteStatus.from_dict(data.get("lte_status", {})),
        )


@dataclass
class ErrorReportEntry:
    """Single entry from /error_report.json."""

    sub_system_id: int = 0
    sub_system_name: str = ""
    error_id: int = 0
    error_name: str = ""
    activated: str = ""  # "ok", "warning", "error", "unknown"
    message: str = ""
    details: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> ErrorReportEntry:
        return cls(
            sub_system_id=data.get("sub_system_id", 0),
            sub_system_name=data.get("sub_system_name", ""),
            error_id=data.get("error_id", 0),
            error_name=data.get("error_name", ""),
            activated=data.get("activated", ""),
            message=data.get("message", ""),
            details=data.get("details", []),
        )


@dataclass
class HomevoltData:
    """Combined data from all API endpoints."""

    ems: HomevoltEmsResponse = field(default_factory=HomevoltEmsResponse)
    status: HomevoltStatusResponse | None = None
    error_report: list[ErrorReportEntry] = field(default_factory=list)
```

**Step 3: Write tests for model parsing**

Create `tests/test_models.py`:

```python
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

    assert voltage.l1 == 2303  # 230.3V
    assert voltage.l2 == 2281
    assert voltage.l3 == 2284


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
    assert status.firmware.esp != ""
    assert status.wifi_status.connected is True
    assert status.mqtt_status.connected is True


def test_parse_error_report():
    """Test parsing /error_report.json response."""
    data = json.loads((FIXTURES / "error_report_response.json").read_text())
    entries = [ErrorReportEntry.from_dict(e) for e in data]

    assert len(entries) > 0
    # Find the EMS warning
    ems_warnings = [e for e in entries if e.sub_system_name == "EMS" and e.activated == "warning"]
    assert len(ems_warnings) >= 1


def test_parse_empty_data():
    """Test models handle missing/empty data gracefully."""
    response = HomevoltEmsResponse.from_dict({})
    assert response.type == ""
    assert response.ts == 0
    assert len(response.ems) == 0
    assert response.aggregated.ems_info.rated_capacity == 0
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/martin.welen/visualstudiocode/Homevolt4HA
python -m pytest tests/test_models.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add custom_components/homevolt/models.py tests/
git commit -m "feat: add data models for Homevolt API responses

Dataclasses with from_dict() parsing for /ems.json, /status.json,
and /error_report.json endpoints. Includes test fixtures from live
API and comprehensive model parsing tests."
```

---

## Task 3: API Client

**Files:**
- Create: `custom_components/homevolt/api.py`
- Create: `tests/test_api.py`

**Step 1: Write the API client**

```python
"""API client for communicating with the Homevolt local HTTP API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_READ_TIMEOUT,
    ENDPOINT_EMS,
    ENDPOINT_ERROR_REPORT,
    ENDPOINT_STATUS,
)
from .models import (
    ErrorReportEntry,
    HomevoltEmsResponse,
    HomevoltStatusResponse,
)

_LOGGER = logging.getLogger(__name__)

RETRY_STATUS_CODES = {502, 503, 504}
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


class HomevoltApiError(Exception):
    """Base exception for Homevolt API errors."""


class HomevoltConnectionError(HomevoltApiError):
    """Error connecting to the Homevolt device."""


class HomevoltAuthError(HomevoltApiError):
    """Authentication error."""


class HomevoltApiClient:
    """Client for the Homevolt local HTTP API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        password: str | None = None,
        port: int = 80,
        use_ssl: bool = False,
        connect_timeout: int = DEFAULT_CONNECT_TIMEOUT,
        read_timeout: int = DEFAULT_READ_TIMEOUT,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._host = host
        self._port = port
        self._password = password
        self._use_ssl = use_ssl
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        scheme = "https" if use_ssl else "http"
        self._base_url = f"{scheme}://{host}:{port}"

    @property
    def host(self) -> str:
        """Return the host."""
        return self._host

    async def _request(self, endpoint: str, method: str = "GET", **kwargs: Any) -> dict | list:
        """Make an HTTP request with retry logic."""
        url = f"{self._base_url}{endpoint}"
        auth = None
        if self._password:
            auth = aiohttp.BasicAuth("admin", self._password)

        timeout = aiohttp.ClientTimeout(
            connect=self._connect_timeout,
            total=self._read_timeout,
        )

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                async with self._session.request(
                    method, url, auth=auth, timeout=timeout, **kwargs
                ) as resp:
                    if resp.status == 401:
                        raise HomevoltAuthError("Invalid credentials")
                    if resp.status in RETRY_STATUS_CODES:
                        last_error = HomevoltApiError(
                            f"Server error {resp.status} from {endpoint}"
                        )
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(BACKOFF_BASE ** (attempt + 1))
                            continue
                        raise last_error
                    resp.raise_for_status()
                    return await resp.json()
            except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as err:
                last_error = HomevoltConnectionError(
                    f"Connection error to {self._host}: {err}"
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BACKOFF_BASE ** (attempt + 1))
                    continue
                raise last_error from err

        # Should not reach here, but just in case
        raise last_error or HomevoltApiError("Unknown error")

    async def async_get_ems_data(self) -> HomevoltEmsResponse:
        """Fetch EMS data from /ems.json."""
        data = await self._request(ENDPOINT_EMS)
        return HomevoltEmsResponse.from_dict(data)

    async def async_get_status(self) -> HomevoltStatusResponse:
        """Fetch system status from /status.json."""
        data = await self._request(ENDPOINT_STATUS)
        return HomevoltStatusResponse.from_dict(data)

    async def async_get_error_report(self) -> list[ErrorReportEntry]:
        """Fetch error report from /error_report.json."""
        data = await self._request(ENDPOINT_ERROR_REPORT)
        return [ErrorReportEntry.from_dict(e) for e in data]

    async def async_validate_connection(self) -> HomevoltEmsResponse:
        """Validate connectivity by fetching EMS data. Used in config flow."""
        return await self.async_get_ems_data()
```

**Step 2: Write API client tests**

Create `tests/test_api.py`:

```python
"""Tests for Homevolt API client."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.homevolt.api import (
    HomevoltApiClient,
    HomevoltAuthError,
    HomevoltConnectionError,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    return aiohttp.ClientSession()


@pytest.fixture
def api_client(mock_session):
    """Create an API client for testing."""
    return HomevoltApiClient(
        session=mock_session,
        host="192.168.70.12",
    )


@pytest.fixture
def api_client_with_password(mock_session):
    """Create an API client with password."""
    return HomevoltApiClient(
        session=mock_session,
        host="192.168.70.12",
        password="secret",
    )


@pytest.fixture
def ems_fixture():
    """Load EMS response fixture."""
    return json.loads((FIXTURES / "ems_response.json").read_text())


@pytest.fixture
def status_fixture():
    """Load status response fixture."""
    return json.loads((FIXTURES / "status_response.json").read_text())


@pytest.fixture
def error_report_fixture():
    """Load error report fixture."""
    return json.loads((FIXTURES / "error_report_response.json").read_text())


@pytest.mark.asyncio
async def test_get_ems_data(api_client, ems_fixture, mock_session):
    """Test fetching EMS data."""
    with aioresponses() as m:
        m.get("http://192.168.70.12:80/ems.json", payload=ems_fixture)
        result = await api_client.async_get_ems_data()
        assert result.type == "ems_data"
        assert result.aggregated.ems_info.rated_capacity == 13304
    await mock_session.close()


@pytest.mark.asyncio
async def test_get_status(api_client, status_fixture, mock_session):
    """Test fetching status data."""
    with aioresponses() as m:
        m.get("http://192.168.70.12:80/status.json", payload=status_fixture)
        result = await api_client.async_get_status()
        assert result.up_time > 0
        assert result.wifi_status.connected is True
    await mock_session.close()


@pytest.mark.asyncio
async def test_get_error_report(api_client, error_report_fixture, mock_session):
    """Test fetching error report."""
    with aioresponses() as m:
        m.get("http://192.168.70.12:80/error_report.json", payload=error_report_fixture)
        result = await api_client.async_get_error_report()
        assert len(result) > 0
        assert any(e.sub_system_name == "EMS" for e in result)
    await mock_session.close()


@pytest.mark.asyncio
async def test_auth_error(api_client, mock_session):
    """Test 401 raises HomevoltAuthError."""
    with aioresponses() as m:
        m.get("http://192.168.70.12:80/ems.json", status=401)
        with pytest.raises(HomevoltAuthError):
            await api_client.async_get_ems_data()
    await mock_session.close()


@pytest.mark.asyncio
async def test_retry_on_503(api_client, ems_fixture, mock_session):
    """Test retry logic on 503 status."""
    with aioresponses() as m:
        m.get("http://192.168.70.12:80/ems.json", status=503)
        m.get("http://192.168.70.12:80/ems.json", payload=ems_fixture)
        result = await api_client.async_get_ems_data()
        assert result.type == "ems_data"
    await mock_session.close()


@pytest.mark.asyncio
async def test_connection_error(api_client, mock_session):
    """Test connection error raises HomevoltConnectionError."""
    with aioresponses() as m:
        m.get(
            "http://192.168.70.12:80/ems.json",
            exception=aiohttp.ClientConnectionError("refused"),
        )
        m.get(
            "http://192.168.70.12:80/ems.json",
            exception=aiohttp.ClientConnectionError("refused"),
        )
        m.get(
            "http://192.168.70.12:80/ems.json",
            exception=aiohttp.ClientConnectionError("refused"),
        )
        with pytest.raises(HomevoltConnectionError):
            await api_client.async_get_ems_data()
    await mock_session.close()
```

**Step 3: Run tests**

```bash
python -m pytest tests/test_api.py -v
```

Expected: All tests PASS

**Step 4: Commit**

```bash
git add custom_components/homevolt/api.py tests/test_api.py
git commit -m "feat: add API client with retry logic and error handling

HomevoltApiClient handles HTTP GET to /ems.json, /status.json, and
/error_report.json. Includes 3-retry exponential backoff on 502/503/504
and connection errors. Raises typed exceptions for auth and connection
failures."
```

---

## Task 4: Data Coordinator

**Files:**
- Create: `custom_components/homevolt/coordinator.py`
- Create: `tests/test_coordinator.py`

**Step 1: Write the coordinator**

```python
"""DataUpdateCoordinator for Homevolt."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import HomevoltApiClient, HomevoltAuthError, HomevoltConnectionError
from .const import (
    DEFAULT_SCAN_INTERVAL,
    ERROR_REPORT_POLL_INTERVAL,
    STATUS_POLL_INTERVAL,
)
from .models import HomevoltData

_LOGGER = logging.getLogger(__name__)

type HomevoltConfigEntry = ConfigEntry[HomevoltCoordinator]


class HomevoltCoordinator(DataUpdateCoordinator[HomevoltData]):
    """Coordinator for Homevolt data updates with tiered polling."""

    config_entry: HomevoltConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HomevoltConfigEntry,
        client: HomevoltApiClient,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Homevolt",
            config_entry=config_entry,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self._poll_count = 0

    async def _async_update_data(self) -> HomevoltData:
        """Fetch data from the Homevolt API with tiered polling."""
        self._poll_count += 1

        try:
            # Always fetch EMS data (primary data source)
            ems = await self.client.async_get_ems_data()

            # Build the combined data object
            combined = HomevoltData(ems=ems)

            # Fetch status data every Nth cycle
            if self._poll_count % STATUS_POLL_INTERVAL == 0 or self.data is None:
                combined.status = await self.client.async_get_status()
            elif self.data is not None:
                combined.status = self.data.status

            # Fetch error report every Nth cycle
            if self._poll_count % ERROR_REPORT_POLL_INTERVAL == 0 or self.data is None:
                combined.error_report = await self.client.async_get_error_report()
            elif self.data is not None:
                combined.error_report = self.data.error_report

        except HomevoltAuthError as err:
            raise ConfigEntryAuthFailed("Invalid credentials") from err
        except HomevoltConnectionError as err:
            raise UpdateFailed(f"Error communicating with Homevolt: {err}") from err

        return combined
```

**Step 2: Write coordinator tests**

Create `tests/test_coordinator.py` that mocks the API client and verifies:
- First fetch gets all data (EMS + status + error report)
- Subsequent fetches only get EMS data (reuses cached status/error_report)
- Every Nth fetch refreshes status/error_report
- Auth errors trigger ConfigEntryAuthFailed
- Connection errors trigger UpdateFailed

**Step 3: Run tests**

```bash
python -m pytest tests/test_coordinator.py -v
```

**Step 4: Commit**

```bash
git add custom_components/homevolt/coordinator.py tests/test_coordinator.py
git commit -m "feat: add DataUpdateCoordinator with tiered polling

Polls /ems.json every cycle, /status.json every 10th cycle, and
/error_report.json every 4th cycle. First fetch always gets all data.
Auth errors trigger reauth flow, connection errors mark as unavailable."
```

---

## Task 5: Config Flow

**Files:**
- Create: `custom_components/homevolt/config_flow.py`
- Create: `custom_components/homevolt/strings.json`
- Create: `tests/test_config_flow.py`

**Step 1: Write the config flow**

```python
"""Config flow for Homevolt integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HomevoltApiClient, HomevoltAuthError, HomevoltConnectionError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=10, max=300)
        ),
    }
)


class HomevoltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homevolt."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._port: int = DEFAULT_PORT

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step (manual entry)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            password = user_input.get(CONF_PASSWORD)

            session = async_get_clientsession(self.hass)
            client = HomevoltApiClient(
                session=session, host=host, port=port, password=password
            )

            try:
                ems_data = await client.async_validate_connection()
            except HomevoltAuthError:
                errors["base"] = "invalid_auth"
            except HomevoltConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"
            else:
                # Use ecu_id from first EMS device as unique ID
                ecu_id = str(ems_data.ems[0].ecu_id) if ems_data.ems else host
                await self.async_set_unique_id(ecu_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Homevolt ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_PASSWORD: password,
                    },
                    options={
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: Any
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery."""
        host = str(discovery_info.host)
        port = discovery_info.port or DEFAULT_PORT
        self._host = host
        self._port = port

        # Try to connect and get unique ID
        session = async_get_clientsession(self.hass)
        client = HomevoltApiClient(session=session, host=host, port=port)

        try:
            ems_data = await client.async_validate_connection()
        except (HomevoltConnectionError, HomevoltAuthError, Exception):
            return self.async_abort(reason="cannot_connect")

        ecu_id = str(ems_data.ems[0].ecu_id) if ems_data.ems else host
        await self.async_set_unique_id(ecu_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self.context["title_placeholders"] = {"name": f"Homevolt ({host})"}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Zeroconf discovery."""
        if user_input is not None:
            password = user_input.get(CONF_PASSWORD)
            return self.async_create_entry(
                title=f"Homevolt ({self._host})",
                data={
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_PASSWORD: password,
                },
                options={
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                },
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={"host": self._host},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return HomevoltOptionsFlow()


class HomevoltOptionsFlow(OptionsFlow):
    """Handle options for Homevolt."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options step."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                        int, vol.Range(min=10, max=300)
                    ),
                }
            ),
        )
```

**Step 2: Create strings.json**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to Homevolt",
        "description": "Enter the connection details for your Homevolt battery system.",
        "data": {
          "host": "Host",
          "password": "Password (optional)",
          "port": "Port",
          "scan_interval": "Scan interval (seconds)"
        }
      },
      "zeroconf_confirm": {
        "title": "Homevolt Discovered",
        "description": "A Homevolt battery system was found at {host}.",
        "data": {
          "password": "Password (optional)"
        }
      }
    },
    "error": {
      "cannot_connect": "Failed to connect to the Homevolt device",
      "invalid_auth": "Invalid password",
      "unknown": "Unexpected error occurred"
    },
    "abort": {
      "already_configured": "This Homevolt device is already configured",
      "cannot_connect": "Cannot connect to the discovered device"
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Homevolt Options",
        "data": {
          "scan_interval": "Scan interval (seconds)"
        }
      }
    }
  }
}
```

**Step 3: Write config flow tests**

Test all paths: successful manual setup, auth error, connection error, zeroconf discovery, duplicate abort, options flow.

**Step 4: Run tests**

```bash
python -m pytest tests/test_config_flow.py -v
```

**Step 5: Commit**

```bash
git add custom_components/homevolt/config_flow.py \
  custom_components/homevolt/strings.json \
  tests/test_config_flow.py
git commit -m "feat: add config flow with manual and Zeroconf discovery

Supports manual host/password entry with connection validation,
Zeroconf auto-discovery for _http._tcp.local. homevolt* services,
and options flow for scan interval. Uses ecu_id as unique identifier."
```

---

## Task 6: Base Entity and Device Info

**Files:**
- Create: `custom_components/homevolt/entity.py`

**Step 1: Write base entity classes**

```python
"""Base entity classes for Homevolt."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HomevoltCoordinator


class HomevoltEntity(CoordinatorEntity[HomevoltCoordinator]):
    """Base entity for Homevolt integration."""

    has_entity_name = True

    def __init__(self, coordinator: HomevoltCoordinator, ecu_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._ecu_id = ecu_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the main battery system."""
        agg = self.coordinator.data.ems.aggregated
        return DeviceInfo(
            identifiers={(DOMAIN, self._ecu_id)},
            name="Homevolt Battery System",
            manufacturer=MANUFACTURER,
            model="Homevolt",
            sw_version=agg.ems_info.fw_version,
            hw_version=agg.inv_info.fw_version,
        )


class HomevoltBmsEntity(CoordinatorEntity[HomevoltCoordinator]):
    """Entity for a BMS battery module."""

    has_entity_name = True

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
        bms_index: int,
        serial_number: str,
    ) -> None:
        """Initialize the BMS entity."""
        super().__init__(coordinator)
        self._ecu_id = ecu_id
        self._bms_index = bms_index
        self._serial_number = serial_number

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the battery module."""
        bms_info = self.coordinator.data.ems.aggregated.bms_info
        fw = bms_info[self._bms_index].fw_version if self._bms_index < len(bms_info) else ""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            name=f"Battery Module {self._bms_index + 1}",
            manufacturer=MANUFACTURER,
            model="Homevolt BMS",
            sw_version=fw,
            via_device=(DOMAIN, self._ecu_id),
        )


class HomevoltSensorDeviceEntity(CoordinatorEntity[HomevoltCoordinator]):
    """Entity for a CT clamp sensor device (grid, solar, load)."""

    has_entity_name = True

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
        sensor_index: int,
        sensor_type: str,
        euid: str,
    ) -> None:
        """Initialize the sensor device entity."""
        super().__init__(coordinator)
        self._ecu_id = ecu_id
        self._sensor_index = sensor_index
        self._sensor_type = sensor_type
        self._euid = euid

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the CT sensor."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._euid)},
            name=f"{self._sensor_type.title()} Sensor",
            manufacturer=MANUFACTURER,
            model="Tibber Pulse Clamp",
            via_device=(DOMAIN, self._ecu_id),
        )
```

**Step 2: Commit**

```bash
git add custom_components/homevolt/entity.py
git commit -m "feat: add base entity classes with device registry info

Three entity bases: HomevoltEntity (main system), HomevoltBmsEntity
(per battery module via main device), HomevoltSensorDeviceEntity
(per CT clamp via main device)."
```

---

## Task 7: Sensor Platform

**Files:**
- Create: `custom_components/homevolt/sensor.py`
- Create: `custom_components/homevolt/icons.json`

**Step 1: Write the sensor platform**

This is the largest file. It defines `SensorEntityDescription` instances for all sensors and maps them to data accessor functions.

Key patterns:
- Use `translation_key` for all sensor names (not hardcoded `name`)
- Use `entity_category=EntityCategory.DIAGNOSTIC` for status/error sensors
- Use value accessor lambdas/functions that extract the value from `HomevoltData`
- Apply unit conversions (decivolts -> V, decicelsius -> C, centi-Hz -> Hz)

The sensor descriptions should be organized in groups:
1. `SYSTEM_SENSORS` - aggregated EMS data (SOC, power, energy, status, etc.)
2. `VOLTAGE_SENSORS` - L1/L2/L3 phase voltages
3. `CURRENT_SENSORS` - L1/L2/L3 phase currents
4. `PREDICTION_SENSORS` - available charge/discharge power/energy
5. `BMS_SENSORS` - per battery module (SOC, temps, cycles, state)
6. `CT_SENSORS` - per CT clamp (power, energy, RSSI, availability)
7. `DIAGNOSTIC_SENSORS` - EMS info/warning/alarm strings, error count
8. `STATUS_SENSORS` - from /status.json (uptime, WiFi RSSI, firmware, connectivity)

Each sensor entity class accesses data from `self.coordinator.data`.

For the complete sensor entity description list, use the design document as reference (docs/plans/2026-02-12-homevolt-ha-integration-design.md).

Important implementation detail: Create a custom `HomevoltSensorEntityDescription` that extends `SensorEntityDescription` with a `value_fn` field:

```python
@dataclass(frozen=True, kw_only=True)
class HomevoltSensorEntityDescription(SensorEntityDescription):
    """Describes a Homevolt sensor entity."""
    value_fn: Callable[[HomevoltData], StateType] = None
```

Then in `async_setup_entry`, iterate over all descriptions, create sensor entities, and add them.

**Step 2: Create icons.json**

Map `translation_key` values to Material Design Icons:

```json
{
  "entity": {
    "sensor": {
      "battery_status": { "default": "mdi:battery" },
      "battery_state": { "default": "mdi:battery-heart-variant" },
      "battery_soc": { "default": "mdi:battery-medium" },
      "battery_power": { "default": "mdi:flash" },
      "system_temperature": { "default": "mdi:thermometer" },
      "grid_frequency": { "default": "mdi:sine-wave" },
      "energy_produced": { "default": "mdi:battery-arrow-up" },
      "energy_consumed": { "default": "mdi:battery-arrow-down" },
      "energy_imported": { "default": "mdi:transmission-tower-import" },
      "energy_exported": { "default": "mdi:transmission-tower-export" },
      "available_charge_power": { "default": "mdi:battery-charging" },
      "available_discharge_power": { "default": "mdi:battery-minus" },
      "uptime": { "default": "mdi:clock-outline" },
      "firmware_esp": { "default": "mdi:chip" },
      "firmware_efr": { "default": "mdi:chip" },
      "ems_info": { "default": "mdi:information-outline" },
      "ems_warning": { "default": "mdi:alert-outline" },
      "ems_alarm": { "default": "mdi:alert-circle-outline" },
      "bms_min_temperature": { "default": "mdi:thermometer-low" },
      "bms_max_temperature": { "default": "mdi:thermometer-high" },
      "bms_cycle_count": { "default": "mdi:counter" }
    }
  }
}
```

**Step 3: Update strings.json**

Add `entity.sensor` translation keys for all sensor names.

**Step 4: Commit**

```bash
git add custom_components/homevolt/sensor.py \
  custom_components/homevolt/icons.json \
  custom_components/homevolt/strings.json
git commit -m "feat: add sensor platform with all entity descriptions

System sensors (SOC, power, energy, voltage, current, frequency),
per-BMS sensors (SOC, temps, cycles), per-CT sensors (power, energy,
RSSI), diagnostic sensors (warnings, alarms, firmware, uptime).
Handles unit conversions from API units."
```

---

## Task 8: Integration Entry Point

**Files:**
- Modify: `custom_components/homevolt/__init__.py`

**Step 1: Write the full __init__.py**

```python
"""The Homevolt integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HomevoltApiClient
from .const import CONF_SCAN_INTERVAL, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import HomevoltCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type HomevoltConfigEntry = ConfigEntry[HomevoltCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HomevoltConfigEntry) -> bool:
    """Set up Homevolt from a config entry."""
    session = async_get_clientsession(hass)

    client = HomevoltApiClient(
        session=session,
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        password=entry.data.get(CONF_PASSWORD),
    )

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = HomevoltCoordinator(hass, entry, client, scan_interval)

    # First refresh - raises ConfigEntryNotReady on failure
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload on options change
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    return True


async def _async_update_options(hass: HomeAssistant, entry: HomevoltConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HomevoltConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

**Step 2: Commit**

```bash
git add custom_components/homevolt/__init__.py
git commit -m "feat: add integration entry point with setup/unload

Creates API client and coordinator from config entry, performs first
refresh, forwards sensor platform setup, and handles options reload."
```

---

## Task 9: Diagnostics

**Files:**
- Create: `custom_components/homevolt/diagnostics.py`

**Step 1: Write diagnostics**

```python
"""Diagnostics support for Homevolt."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import HomevoltCoordinator

REDACT_KEYS = {CONF_PASSWORD, "serial_number", "ssid", "psk", "ip", "mqtt_topic", "mqtt_topic_sub", "mqtt_client_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: HomevoltCoordinator = entry.runtime_data

    # Redact sensitive config data
    config_data = dict(entry.data)
    for key in REDACT_KEYS:
        if key in config_data:
            config_data[key] = "**REDACTED**"

    diag: dict[str, Any] = {
        "config": config_data,
        "options": dict(entry.options),
    }

    if coordinator.data:
        diag["ems"] = asdict(coordinator.data.ems)
        if coordinator.data.status:
            status_dict = asdict(coordinator.data.status)
            # Redact WiFi credentials
            if "wifi_status" in status_dict:
                status_dict["wifi_status"]["ssid"] = "**REDACTED**"
                status_dict["wifi_status"]["ip"] = "**REDACTED**"
            diag["status"] = status_dict
        if coordinator.data.error_report:
            diag["error_report"] = [asdict(e) for e in coordinator.data.error_report]

    return diag
```

**Step 2: Commit**

```bash
git add custom_components/homevolt/diagnostics.py
git commit -m "feat: add diagnostics with sensitive data redaction

Exports EMS, status, and error report data for debugging.
Redacts passwords, serial numbers, WiFi SSID/IP, and MQTT topics."
```

---

## Task 10: Integration Test and Final Wiring

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_init.py`

**Step 1: Create conftest.py with shared fixtures**

Shared pytest fixtures for HomeAssistant test setup, mock config entries, and mock API responses.

**Step 2: Write integration tests**

Test `async_setup_entry` and `async_unload_entry` with mocked API responses. Verify:
- Entry loads successfully with mocked API data
- Sensors are created with correct unique IDs
- Entry unloads cleanly
- ConfigEntryNotReady raised when API is unreachable

**Step 3: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: All tests PASS

**Step 4: Final commit**

```bash
git add tests/
git commit -m "feat: add integration tests and shared test fixtures

Tests for setup/unload lifecycle and ConfigEntryNotReady handling."
```

---

## Task 11: README and Final Polish

**Files:**
- Create: `README.md`

**Step 1: Write README**

Include: Installation instructions (HACS custom repo or manual copy), configuration steps, supported sensors list, troubleshooting (enable webserver, check connectivity).

**Step 2: Run full test suite one final time**

```bash
python -m pytest tests/ -v
```

**Step 3: Final commit**

```bash
git add README.md
git commit -m "docs: add README with installation and configuration guide"
```

---

## Task 12: Push to Remote Repository

**Step 1: Create private GitHub repository**

```bash
gh repo create Homevolt4HA --private --source=. --push
```

Or if the repo already exists:

```bash
git remote add origin git@github.com:martinwelen/Homevolt4HA.git
git push -u origin main
```

**Step 2: Verify**

```bash
gh repo view --web
```

---

## Summary

| Task | Component | Estimated Steps |
|------|-----------|----------------|
| 1 | Project scaffolding | 7 |
| 2 | Data models + tests | 5 |
| 3 | API client + tests | 4 |
| 4 | Coordinator + tests | 4 |
| 5 | Config flow + strings + tests | 5 |
| 6 | Base entity classes | 2 |
| 7 | Sensor platform + icons | 4 |
| 8 | Integration entry point | 2 |
| 9 | Diagnostics | 2 |
| 10 | Integration tests | 4 |
| 11 | README | 3 |
| 12 | Push to remote | 2 |

**Total: 12 tasks, ~44 steps**

Each task produces a git commit. The integration is fully functional after Task 10.
