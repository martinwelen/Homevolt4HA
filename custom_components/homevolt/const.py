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
ENDPOINT_NODE_METRICS: Final = "/node_metrics.json"

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
NODES_POLL_INTERVAL: Final = 10  # Every 10th cycle (~5 min at 30s)
SCHEDULE_POLL_INTERVAL: Final = 10  # Every 10th cycle (~5 min at 30s)

# Manufacturer info
MANUFACTURER: Final = "Tibber / Polarium"
