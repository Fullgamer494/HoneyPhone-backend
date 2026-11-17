"""Integration checks against a dedicated, disposable PostgreSQL database."""
import copy
import json
import os
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BASE = os.environ["HP_TEST_BASE_URL"]
DATABASE = os.environ["DATABASE_URL"]
if not make_url(DATABASE).database.startswith("honeyphone_verify_"):
    raise RuntimeError("Use a dedicated honeyphone_verify_* PostgreSQL database.")
ROOT = Path(__file__).resolve().parents[2]
engine = create_engine(DATABASE)

def request(method, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, json.loads(raw) if raw else None

def fixture():
    data = json.loads((ROOT / "contracts/examples/live-incompleto.json").read_text())
    data["check_id"] = str(uuid4())
    data["installation_id"] = str(uuid4())
    for signal in data["signals"]:
        signal["signal_id"] = str(uuid4())
    return data

class WifiMetricsIntegration(unittest.TestCase):
    def test_metrics_roundtrip_conflict_and_cascading_delete(self):
        data = fixture()
        data.update(network_label="Sala A", wifi_metrics={"rssi_dbm": -55, "frequency_mhz": 5180,
            "wifi_standard": "WIFI_6", "link_speed_mbps": 600, "rx_link_speed_mbps": 600,
            "tx_link_speed_mbps": 288, "internet_validated": True})
        try:
            status, created = request("POST", "/api/v1/network-checks", data)
            self.assertEqual(201, status)
            self.assertEqual("Sala A", created["network_label"])
            self.assertEqual(-55, created["wifi_metrics"]["rssi_dbm"])
            self.assertEqual(200, request("POST", "/api/v1/network-checks", data)[0])
            changed = copy.deepcopy(data)
            changed["wifi_metrics"]["rssi_dbm"] = -60
            self.assertEqual(409, request("POST", "/api/v1/network-checks", changed)[0])
            with engine.connect() as db:
                row = db.execute(text("SELECT network_label, wifi_metrics FROM network_checks WHERE check_id=:id"), {"id": data["check_id"]}).one()
                self.assertEqual("Sala A", row[0])
                self.assertEqual(288, row[1]["tx_link_speed_mbps"])
            status, detail = request("GET", "/api/v1/network-checks/" + data["check_id"])
            self.assertEqual(200, status)
            self.assertEqual(created["wifi_metrics"], detail["wifi_metrics"])
            page = request("GET", "/api/v1/network-checks?installation_id=" + data["installation_id"])[1]
            self.assertEqual(1, len(page["items"]))
            self.assertEqual(204, request("DELETE", "/api/v1/network-checks/" + data["check_id"])[0])
            self.assertEqual(404, request("GET", "/api/v1/network-checks/" + data["check_id"])[0])
            with engine.connect() as db:
                self.assertEqual(0, db.scalar(text("SELECT count(*) FROM check_signals WHERE check_id=:id"), {"id": data["check_id"]}))
        finally:
            request("DELETE", "/api/v1/network-checks/" + data["check_id"])

    def test_invalid_metrics_and_sensitive_fields_are_rejected_atomically(self):
        data = fixture()
        invalid = [
            {"wifi_metrics": {"bssid": "forbidden"}},
            {"ssid": "forbidden"},
            {"network_label": "bad\nlabel"},
            {"network_label": "x" * 41},
            {"wifi_metrics": {"rssi_dbm": 0}},
            {"wifi_metrics": {"rssi_dbm": -127}},
            {"wifi_metrics": {"rssi_dbm": "-50"}},
            {"wifi_metrics": {"rssi_dbm": True}},
            {"wifi_metrics": {"rx_link_speed_mbps": -1}},
            {"wifi_metrics": {"internet_validated": "yes"}},
        ]
        for mutation in invalid:
            payload = {**data, **mutation}
            status, _ = request("POST", "/api/v1/network-checks", payload)
            self.assertEqual(422, status, str(mutation))
        with engine.connect() as db:
            self.assertEqual(0, db.scalar(text("SELECT count(*) FROM network_checks WHERE check_id=:id"), {"id": data["check_id"]}))
            self.assertEqual(0, db.scalar(text("SELECT count(*) FROM installations WHERE installation_id=:id"), {"id": data["installation_id"]}))

    def test_legacy_payload_remains_accepted_and_idempotent(self):
        data = fixture()
        try:
            status, created = request("POST", "/api/v1/network-checks", data)
            self.assertEqual(201, status)
            self.assertIsNone(created["network_label"])
            self.assertIsNone(created["wifi_metrics"])
            self.assertEqual(200, request("POST", "/api/v1/network-checks", data)[0])
        finally:
            request("DELETE", "/api/v1/network-checks/" + data["check_id"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
