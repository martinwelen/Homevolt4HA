# Homevolt for Home Assistant

A custom [Home Assistant](https://www.home-assistant.io/) integration for the **Homevolt** battery system (manufactured by Tibber / Polarium). All communication is local over HTTP -- no cloud services required.

## Features

- **Local polling** -- communicates directly with your Homevolt EMS over your local network
- **Automatic discovery** -- finds your Homevolt device via Zeroconf (mDNS)
- **Dynamic hardware** -- automatically detects the number of BMS battery modules and CT clamp sensors
- **40+ sensors** -- system power, energy, voltage, current, battery module details, CT clamps, diagnostics, and status
- **Configurable scan interval** -- default 30 seconds, adjustable from 10 to 300 seconds
- **Diagnostics** -- download diagnostics data from the integration page for troubleshooting

## Requirements

- Home Assistant 2024.1 or newer
- A Homevolt battery system with the built-in web server enabled
- Network connectivity between Home Assistant and the Homevolt device (HTTP, port 80)

## Installation

### HACS (recommended)

1. Open **HACS** in your Home Assistant instance
2. Click the three-dot menu in the top-right corner and select **Custom repositories**
3. Add the repository URL: `https://github.com/martinwelen/Homevolt4HA`
4. Select **Integration** as the category
5. Click **Add**
6. Search for **Homevolt** in the HACS integrations list and install it
7. Restart Home Assistant

### Manual installation

1. Download the latest release from the [GitHub repository](https://github.com/martinwelen/Homevolt4HA)
2. Copy the `custom_components/homevolt` directory into your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

Your directory structure should look like:

```
config/
  custom_components/
    homevolt/
      __init__.py
      api.py
      config_flow.py
      const.py
      coordinator.py
      diagnostics.py
      entity.py
      icons.json
      manifest.json
      models.py
      sensor.py
      strings.json
```

## Configuration

### Automatic discovery

If Zeroconf (mDNS) is working on your network, Home Assistant will automatically discover your Homevolt device. You will see a notification to configure it. Click the notification and follow the prompts.

### Manual setup

1. Go to **Settings** > **Devices & services** > **Add Integration**
2. Search for **Homevolt**
3. Enter the following:
   - **Host** -- the IP address or hostname of your Homevolt device (e.g. `192.168.1.100`)
   - **Password** -- leave blank if your device does not require authentication (most do not)
   - **Port** -- default is `80`
   - **Scan interval** -- polling interval in seconds (default: `30`, range: `10`-`300`)
4. Click **Submit**

### Options

After setup, you can change the scan interval:

1. Go to **Settings** > **Devices & services**
2. Find the **Homevolt** integration and click **Configure**
3. Adjust the **Scan interval** as needed

## Sensors

The integration creates sensors organized into the following groups. The exact number of entities depends on your hardware configuration (number of BMS modules and CT clamp sensors).

### System sensors (18)

| Sensor | Unit | Description |
|--------|------|-------------|
| Status | -- | Operational status of the EMS |
| State | -- | Current EMS state |
| State of charge | % | Average battery state of charge |
| Power | W | Current battery power (positive = charging) |
| Apparent power | VA | Apparent power |
| Reactive power | var | Reactive power |
| System temperature | C | System temperature |
| Grid frequency | Hz | AC grid frequency |
| Energy produced | Wh | Total energy produced (discharging) |
| Energy consumed | Wh | Total energy consumed (charging) |
| Energy imported | kWh | Total grid energy imported |
| Energy exported | kWh | Total grid energy exported |
| Available charge power | W | Available power for charging |
| Available discharge power | W | Available power for discharging |
| Available charge energy | Wh | Available energy capacity for charging |
| Available discharge energy | Wh | Available energy capacity for discharging |
| Rated capacity | Wh | Rated total energy capacity |
| Rated power | W | Rated total power |

### Voltage sensors (3)

| Sensor | Unit | Description |
|--------|------|-------------|
| Voltage L1 | V | Phase 1 voltage |
| Voltage L2 | V | Phase 2 voltage |
| Voltage L3 | V | Phase 3 voltage |

### Current sensors (3)

| Sensor | Unit | Description |
|--------|------|-------------|
| Current L1 | A | Phase 1 current |
| Current L2 | A | Phase 2 current |
| Current L3 | A | Phase 3 current |

### Battery module sensors (6 per module)

These sensors are created for each BMS battery module detected. A typical installation has 2 modules.

| Sensor | Unit | Description |
|--------|------|-------------|
| State of charge | % | Module state of charge |
| State | -- | Module operational state |
| Min temperature | C | Minimum cell temperature |
| Max temperature | C | Maximum cell temperature |
| Cycle count | cycles | Number of charge/discharge cycles |
| Energy available | Wh | Currently available energy |

### CT clamp sensors (6 per clamp)

These sensors are created for each CT clamp sensor node detected. CT clamps are optional and used for monitoring mains current.

| Sensor | Unit | Description |
|--------|------|-------------|
| Power | W | Measured power |
| Energy imported | kWh | Total energy imported |
| Energy exported | kWh | Total energy exported |
| RSSI | dBm | Wireless signal strength |
| Packet delivery rate | % | Mesh network packet delivery rate |
| Available | -- | Whether the CT sensor is reachable |

### Diagnostic sensors (4)

| Sensor | Unit | Description |
|--------|------|-------------|
| EMS info | -- | Active informational messages |
| EMS warning | -- | Active warning messages |
| EMS alarm | -- | Active alarm messages |
| Error count | -- | Total number of errors from error report |

### Status sensors (6)

| Sensor | Unit | Description |
|--------|------|-------------|
| Uptime | s | System uptime |
| WiFi RSSI | dBm | WiFi signal strength |
| WiFi connected | -- | WiFi connection status |
| MQTT connected | -- | MQTT cloud connection status |
| Firmware ESP | -- | ESP firmware version |
| Firmware EFR | -- | EFR firmware version |

## Data sources

The integration polls three API endpoints with tiered intervals:

| Endpoint | Content | Poll frequency |
|----------|---------|----------------|
| `/ems.json` | System, voltage, current, BMS, CT data | Every cycle (default: 30s) |
| `/error_report.json` | Error and diagnostic data | Every 4th cycle (~2 min) |
| `/status.json` | Uptime, WiFi, MQTT, firmware | Every 10th cycle (~5 min) |

## Troubleshooting

### The Homevolt device is not discovered

- Ensure the Homevolt device is powered on and connected to the same network as Home Assistant
- Verify Zeroconf/mDNS is working on your network (some routers block mDNS between VLANs)
- Try adding the integration manually using the device's IP address

### Cannot connect to the device

1. Verify the Homevolt device's web server is enabled. Use the Tibber app or check with your installer.
2. Confirm you can reach the device by opening `http://<device-ip>/ems.json` in a browser
3. Check that no firewall rules are blocking port 80 between Home Assistant and the device
4. If the device requires a password, make sure you entered it correctly in the integration configuration

### Sensors show "unavailable"

- The integration may be waiting for initial data. Status and error report sensors update less frequently (see data sources above).
- If all sensors are unavailable, check the device connectivity.
- CT clamp sensors will be unavailable if no CT clamp nodes are connected to the Homevolt mesh network.
- BMS sensors will only appear for detected battery modules.

### Enable debug logging

To enable debug logging for troubleshooting, add the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.homevolt: debug
```

After restarting Home Assistant, debug logs will appear in the Home Assistant log (Settings > System > Logs).

### Download diagnostics

You can download a diagnostics report to share when reporting issues:

1. Go to **Settings** > **Devices & services**
2. Find the **Homevolt** integration
3. Click the three-dot menu on the device and select **Download diagnostics**

Sensitive information (passwords, serial numbers, WiFi credentials) is automatically redacted.

## Contributing

Contributions are welcome. Please open an issue or pull request on [GitHub](https://github.com/martinwelen/Homevolt4HA).

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
