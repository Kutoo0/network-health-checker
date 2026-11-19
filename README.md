# Network Health Checker

A small Python tool that reads hosts and TCP ports from YAML, then reports DNS resolution, ping reachability, and port status as JSON.

## Features

- YAML host configuration
- DNS resolution checks
- Cross-platform ping checks
- TCP connection checks
- Timestamped JSON reports
- Optional file logging
- Cron-ready exit codes

## Requirements

- Python 3.9+
- PyYAML
- `ping` available on the system PATH

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Configure Hosts

Edit `hosts.yaml`:

```yaml
hosts:
  - host: google.com
    ports:
      - 80
      - 443
  - host: github.com
    ports:
      - 22
      - 443
```

## Run

Print JSON to the terminal:

```bash
python network_health_checker.py
```

Write a JSON report and append a log:

```bash
python network_health_checker.py \
  --config hosts.yaml \
  --output report.json \
  --log network-health.log
```

The script returns exit code `0` when all hosts are healthy and `1` when one or more hosts are unhealthy. Configuration errors return `2`.

## Cron Scheduling

Run every 15 minutes and log output:

```cron
*/15 * * * * cd /opt/network-health-checker && /usr/bin/python3 network_health_checker.py --config hosts.yaml --output reports/$(date +\%Y-\%m-\%d-\%H-\%M).json --log network-health.log >> /var/log/network-health-cron.log 2>&1
```

The cron command uses `date` for unique report filenames. If you do not need per-run files, replace the output path with a fixed `report.json`.

## Example Report

```json
{
  "generated_at": "2026-11-19T14:55:08Z",
  "summary": {
    "hosts": 2,
    "healthy": 2,
    "unhealthy": 0
  },
  "hosts": [
    {
      "host": "github.com",
      "checked_at": "2026-11-19T14:55:08Z",
      "healthy": true,
      "dns": {
        "status": "resolved",
        "addresses": ["140.82.112.3"],
        "error": null
      },
      "ping": {
        "status": "reachable",
        "error": null,
        "output": "ping output"
      },
      "tcp_ports": [
        {
          "port": 443,
          "status": "open",
          "error": null
        }
      ]
    }
  ]
}
```
