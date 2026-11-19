import tempfile
import unittest
from pathlib import Path

import network_health_checker as checker


class NetworkHealthCheckerTests(unittest.TestCase):
    def test_load_hosts_accepts_valid_yaml(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hosts.yaml"
            path.write_text(
                "hosts:\n  - host: example.com\n    ports: [80, 443]\n",
                encoding="utf-8",
            )
            self.assertEqual(
                checker.load_hosts(path),
                [{"host": "example.com", "ports": [80, 443]}],
            )

    def test_load_hosts_rejects_invalid_port(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hosts.yaml"
            path.write_text(
                "hosts:\n  - host: example.com\n    ports: [70000]\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                checker.load_hosts(path)

    def test_check_dns_returns_resolved_status(self):
        original = checker.socket.getaddrinfo
        try:
            checker.socket.getaddrinfo = lambda *args, **kwargs: [
                (2, 1, 6, "", ("203.0.113.10", 0))
            ]
            result = checker.check_dns("example.com")
            self.assertEqual(result["status"], "resolved")
            self.assertEqual(result["addresses"], ["203.0.113.10"])
        finally:
            checker.socket.getaddrinfo = original


if __name__ == "__main__":
    unittest.main()
