# Homevolt Home Assistant Integration - Design Document

**Date**: 2026-02-12
**Domain**: `homevolt`
**Status**: Approved

## Overview

A custom Home Assistant integration for the Homevolt (Tibber) battery system that communicates with the local HTTP API exposed by the ECU. Initial release is sensor-only (read-only) with the architecture designed to support control entities in future releases.

## System Context

- **Device**: Homevolt battery system (Tibber ECU)
- **API**: Local HTTP JSON API at `http://<host>/` (no auth or HTTP Basic Auth)
- **Protocol**: `local_polling` via HTTP GET/POST
- **Hardware**: 1 EMS/inverter (6kW rated), 2 BMS battery modules (13.3 kWh total), CT clamp sensors (grid, solar, load)
- **Network**: WiFi + LTE, mDNS advertised as `Homevolt`

## Architecture

### Approach: Single Coordinator with Tiered Polling

One `DataUpdateCoordinator` manages all data fetching:
- **Every cycle (30s default)**: `GET /ems.json` (real-time battery/energy data)
- **Every 4th cycle (~2 min)**: `GET /error_report.json` (diagnostic data)
- **Every 10th cycle (~5 min)**: `GET /status.json` (firmware, connectivity)

### File Structure

```
custom_components/homevolt/
    __init__.py          # Entry setup, platform forwarding
    manifest.json        # Integration metadata, Zeroconf config
    config_flow.py       # Config flow (manual + Zeroconf discovery)
    const.py             # Domain, endpoints, defaults
    coordinator.py       # DataUpdateCoordinator with tiered polling
    api.py               # HomevoltApiClient (HTTP client with retry)
    models.py            # Dataclass models for API responses
    entity.py            # Base entity classes
    sensor.py            # Sensor entity descriptions + setup
    strings.json         # UI translations
    icons.json           # Entity icons
    diagnostics.py       # Diagnostic data export
```

### API Client (`api.py`)

Standalone `HomevoltApiClient` class:
- Uses `aiohttp.ClientSession` (from HA's `async_get_clientsession`)
- Methods: `get_ems_data()`, `get_status()`, `get_params()`, `get_error_report()`
- HTTP Basic Auth (admin:<password>) when password is configured
- Retry: 3 attempts with exponential backoff (2s, 4s, 8s) on 502/503/504 and connection errors
- Timeouts: connect 5s, read 20s (configurable)

### Data Models (`models.py`)

Python dataclasses matching API response structure:

```
HomevoltData
    ems: list[EmsDevice]
    aggregated: EmsDevice
    sensors: list[SensorData]

EmsDevice
    ecu_id, ecu_host, ecu_version
    error, error_str, op_state, op_state_str
    ems_info: EmsInfo (protocol_version, fw_version, rated_capacity, rated_power)
    bms_info: list[BmsInfo] (fw_version, serial_number, rated_cap, id)
    inv_info: InvInfo (fw_version, serial_number)
    ems_data: EmsData (state, power, energy, temp, soc, frequency, warnings, alarms)
    bms_data: list[BmsData] (soc, cycle_count, temps, state, energy_avail)
    ems_prediction: EmsPrediction (available charge/discharge power and energy)
    ems_voltage: EmsVoltage (L1, L2, L3 phase voltages)
    ems_current: EmsCurrent (L1, L2, L3 phase currents)
    ems_aggregate: EmsAggregate (imported_kwh, exported_kwh)

SensorData (per CT clamp)
    type, euid, available, rssi, pdr
    phase: list[PhaseData] (voltage, amp, power, power_factor)
    total_power, energy_imported, energy_exported

StatusData (from /status.json)
    up_time, firmware (esp, efr)
    wifi_status (ip, ssid, rssi, connected)
    mqtt_status (connected)
    lte_status (operator, rssi, band)

ErrorReport (from /error_report.json)
    list of: sub_system_name, error_name, activated, message, details
```

### Unit Conversions

The API returns values in non-standard units that need conversion:
- **Temperature**: decicelsius (e.g., `60` -> `6.0 C`)
- **Voltage**: decivolts (e.g., `2303` -> `230.3 V`)
- **Frequency**: centi-Hz (e.g., `50040` -> `50.04 Hz`)
- **Line-to-line voltage**: decivolts (e.g., `3982` -> `398.2 V`)
- **Current**: deciamps (e.g., values / 10)

## Sensors

### System-level (aggregated EMS data)

| Sensor | Device Class | State Class | Unit | Source |
|--------|-------------|-------------|------|--------|
| Status | enum | - | - | `aggregated.op_state_str` |
| State | enum | - | - | `aggregated.ems_data.state_str` |
| SOC | battery | measurement | % | `aggregated.ems_data.soc_avg` |
| Power | power | measurement | W | `aggregated.ems_data.power` |
| Apparent Power | apparent_power | measurement | VA | `aggregated.ems_data.apparent_power` |
| Reactive Power | reactive_power | measurement | var | `aggregated.ems_data.reactive_power` |
| System Temperature | temperature | measurement | C | `aggregated.ems_data.sys_temp` (/ 10) |
| Grid Frequency | frequency | measurement | Hz | `aggregated.ems_data.frequency` (/ 1000) |
| Energy Produced | energy | total_increasing | Wh | `aggregated.ems_data.energy_produced` |
| Energy Consumed | energy | total_increasing | Wh | `aggregated.ems_data.energy_consumed` |
| Energy Imported | energy | total_increasing | kWh | `aggregated.ems_aggregate.imported_kwh` |
| Energy Exported | energy | total_increasing | kWh | `aggregated.ems_aggregate.exported_kwh` |
| Available Charge Power | power | measurement | W | `aggregated.ems_prediction.avail_ch_pwr` |
| Available Discharge Power | power | measurement | W | `aggregated.ems_prediction.avail_di_pwr` |
| Available Charge Energy | energy | measurement | Wh | `aggregated.ems_prediction.avail_ch_energy` |
| Available Discharge Energy | energy | measurement | Wh | `aggregated.ems_prediction.avail_di_energy` |
| Rated Capacity | energy | - | Wh | `aggregated.ems_info.rated_capacity` |
| Rated Power | power | - | W | `aggregated.ems_info.rated_power` |
| Voltage L1 | voltage | measurement | V | `aggregated.ems_voltage.l1` (/ 10) |
| Voltage L2 | voltage | measurement | V | `aggregated.ems_voltage.l2` (/ 10) |
| Voltage L3 | voltage | measurement | V | `aggregated.ems_voltage.l3` (/ 10) |
| Current L1 | current | measurement | A | `aggregated.ems_current.l1` (/ 10) |
| Current L2 | current | measurement | A | `aggregated.ems_current.l2` (/ 10) |
| Current L3 | current | measurement | A | `aggregated.ems_current.l3` (/ 10) |

### Per-BMS Battery Module

| Sensor | Device Class | State Class | Unit | Source |
|--------|-------------|-------------|------|--------|
| SOC | battery | measurement | % | `bms_data[n].soc` |
| State | enum | - | - | `bms_data[n].state_str` |
| Min Temperature | temperature | measurement | C | `bms_data[n].tmin` (/ 10) |
| Max Temperature | temperature | measurement | C | `bms_data[n].tmax` (/ 10) |
| Cycle Count | - | total_increasing | cycles | `bms_data[n].cycle_count` |
| Energy Available | energy | measurement | Wh | `bms_data[n].energy_avail` |

### Per-CT Sensor (grid, solar, load)

| Sensor | Device Class | State Class | Unit | Source |
|--------|-------------|-------------|------|--------|
| Power | power | measurement | W | `sensors[n].total_power` |
| Energy Imported | energy | total_increasing | kWh | `sensors[n].energy_imported` |
| Energy Exported | energy | total_increasing | kWh | `sensors[n].energy_exported` |
| RSSI | signal_strength | measurement | dBm | `sensors[n].rssi` |
| Packet Delivery Rate | - | measurement | % | `sensors[n].pdr` |
| Available | connectivity (binary) | - | - | `sensors[n].available` |

### Diagnostic Sensors

| Sensor | Entity Category | Source |
|--------|----------------|--------|
| EMS Info | diagnostic | `aggregated.ems_data.info_str` (joined) |
| EMS Warning | diagnostic | `aggregated.ems_data.warning_str` (joined) |
| EMS Alarm | diagnostic | `aggregated.ems_data.alarm_str` (joined) |
| Error Count | diagnostic | `aggregated.error_cnt` |
| Uptime | diagnostic | `status.up_time` |
| WiFi RSSI | diagnostic | `status.wifi_status.rssi` |
| WiFi Connected | diagnostic | `status.wifi_status.connected` |
| MQTT Connected | diagnostic | `status.mqtt_status.connected` |
| Firmware ESP | diagnostic | `status.firmware.esp` |
| Firmware EFR | diagnostic | `status.firmware.efr` |
| Error Report | diagnostic | Subsystem error statuses from `/error_report.json` |

## Device Registry

| Device | Identifiers | Via Device |
|--------|------------|------------|
| Homevolt Battery System | `(homevolt, {ecu_id})` | - |
| Battery Module N | `(homevolt, {serial_number})` | Battery System |
| Grid/Solar/Load Sensor | `(homevolt, {euid})` | Battery System |

## Config Flow

### Manual Setup
1. Step "user": Host (required), Password (optional), Scan interval (default 30s)
2. Validation: Fetch `/ems.json` to verify connection
3. Unique ID: `ecu_id` from EMS response

### Zeroconf Discovery
1. Listen for `_http._tcp.local.` services matching `homevolt*`
2. Pre-fill host from discovered address
3. Ask for password, proceed to validation

### Options Flow
- Reconfigure scan interval and timeout settings

## Power Sign Conventions

- Battery: positive = discharging, negative = charging
- Grid: positive = importing, negative = exporting
- Solar: always positive (generating)
- Load: always positive (consuming)

## Future Extensions (not in initial release)

- **Buttons**: Set charge/discharge/idle mode, clear schedule, reboot
- **Switches**: Toggle local mode, OTA toggles
- **Numbers**: Fuse sizes, LED brightness, SOC limits
- **Selects**: LED strip mode
- **Schedule management**: Add/delete/clear schedules via services
- **Multi-host support**: Multiple linked Homevolt controllers

## Dependencies

- `aiohttp` (bundled with HA)
- No external PyPI packages needed

## HACS Distribution

- Repository structured with `custom_components/homevolt/` at root
- `hacs.json` for HACS metadata
- Brand registration at `home-assistant/brands` (when going public)
