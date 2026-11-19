#!/usr/bin/env python3
"""Check DNS, ping, and TCP reachability for hosts listed in a YAML file."""

from __future__ import annotations

import argparse
import json
import logging
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_hosts(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict) or not isinstance(data.get("hosts"), list):
        raise ValueError("YAML must contain a top-level 'hosts' list")

    hosts: list[dict[str, Any]] = []
    for index, entry in enumerate(data["hosts"], start=1):
        if not isinstance(entry, dict) or not isinstance(entry.get("host"), str):
            raise ValueError(f"Host entry {index} must contain a string 'host'")

        ports = entry.get("ports", [])
        if not isinstance(ports, list):
            raise ValueError(f"'ports' for {entry['host']} must be a list")

        normalized_ports: list[int] = []
        for port in ports:
            if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
                raise ValueError(f"Invalid TCP port for {entry['host']}: {port!r}")
            normalized_ports.append(port)

        hosts.append({"host": entry["host"].strip(), "ports": normalized_ports})

    if not hosts:
        raise ValueError("The hosts list cannot be empty")
    return hosts


def check_dns(host: str) -> dict[str, Any]:
    try:
        answers = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        addresses = sorted({answer[4][0] for answer in answers})
        return {
            "status": "resolved",
            "addresses": addresses,
            "error": None,
        }
    except socket.gaierror as exc:
        return {"status": "failed", "addresses": [], "error": str(exc)}


def check_ping(host: str, count: int, timeout: int) -> dict[str, Any]:
    if sys.platform.startswith("win"):
        command = ["ping", "-n", str(count), "-w", str(timeout * 1000), host]
    else:
        command = ["ping", "-c", str(count), "-W", str(timeout), host]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout * count + 5,
            check=False,
        )
        return {
            "status": "reachable" if result.returncode == 0 else "unreachable",
            "error": None if result.returncode == 0 else (result.stderr.strip() or "ping returned non-zero"),
            "output": (result.stdout or result.stderr).strip(),
        }
    except FileNotFoundError:
        return {"status": "unknown", "error": "ping command not found", "output": None}
    except subprocess.TimeoutExpired:
        return {"status": "unreachable", "error": "ping timed out", "output": None}


def check_tcp(host: str, port: int, timeout: float) -> dict[str, Any]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"port": port, "status": "open", "error": None}
    except (socket.timeout, ConnectionRefusedError, socket.gaierror, OSError) as exc:
        return {"port": port, "status": "closed", "error": str(exc)}


def build_report(
    hosts: list[dict[str, Any]],
    ping_count: int,
    ping_timeout: int,
    tcp_timeout: float,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "generated_at": utc_timestamp(),
        "summary": {"hosts": 0, "healthy": 0, "unhealthy": 0},
        "hosts": [],
    }

    for entry in hosts:
        host = entry["host"]
        checked_at = utc_timestamp()
        dns = check_dns(host)
        ping = check_ping(host, ping_count, ping_timeout)
        tcp_ports = [check_tcp(host, port, tcp_timeout) for port in entry["ports"]]

        dns_ok = dns["status"] == "resolved"
        ping_ok = ping["status"] == "reachable"
        tcp_ok = all(port["status"] == "open" for port in tcp_ports)
        if not tcp_ports:
            tcp_ok = True
        healthy = dns_ok and ping_ok and tcp_ok

        report["hosts"].append(
            {
                "host": host,
                "checked_at": checked_at,
                "healthy": healthy,
                "dns": dns,
                "ping": ping,
                "tcp_ports": tcp_ports,
            }
        )

    report["summary"]["hosts"] = len(report["hosts"])
    report["summary"]["healthy"] = sum(host["healthy"] for host in report["hosts"])
    report["summary"]["unhealthy"] = (
        report["summary"]["hosts"] - report["summary"]["healthy"]
    )
    return report


def configure_logging(path: Path | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check DNS resolution, ping reachability, and TCP ports."
    )
    parser.add_argument("-c", "--config", type=Path, default=Path("hosts.yaml"))
    parser.add_argument("-o", "--output", type=Path, help="Write JSON report to this file")
    parser.add_argument("-l", "--log", type=Path, help="Append human-readable results to a log")
    parser.add_argument("--ping-count", type=int, default=1)
    parser.add_argument("--ping-timeout", type=int, default=2)
    parser.add_argument("--tcp-timeout", type=float, default=2.0)
    args = parser.parse_args()
    if args.ping_count < 1:
        parser.error("--ping-count must be at least 1")
    if args.ping_timeout < 1:
        parser.error("--ping-timeout must be at least 1")
    if args.tcp_timeout <= 0:
        parser.error("--tcp-timeout must be greater than 0")
    return args


def main() -> int:
    args = parse_args()
    configure_logging(args.log)

    try:
        hosts = load_hosts(args.config)
        report = build_report(
            hosts,
            ping_count=args.ping_count,
            ping_timeout=args.ping_timeout,
            tcp_timeout=args.tcp_timeout,
        )
    except (OSError, yaml.YAMLError, ValueError) as exc:
        logging.error("Cannot run health check: %s", exc)
        return 2

    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    summary = report["summary"]
    logging.info(
        "Health check complete: %d healthy, %d unhealthy",
        summary["healthy"],
        summary["unhealthy"],
    )
    if args.output:
        logging.info("JSON report written to %s", args.output)
    return 1 if summary["unhealthy"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
