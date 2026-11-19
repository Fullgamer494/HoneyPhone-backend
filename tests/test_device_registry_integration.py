"""Device registry lifecycle and revocation integration checks."""
import unittest
from uuid import uuid4

from test_wifi_metrics_integration import BASE, fixture, request


class DeviceRegistryIntegration(unittest.TestCase):
    def test_device_can_be_registered_listed_renamed_and_revoked(self):
        installation_id = str(uuid4())
        base = "/api/v1/devices"

        status, registered = request(
            "POST",
            f"{base}?installation_id={installation_id}&app_version=0.4.0",
        )
        assert status == 201
        assert registered["installation_id"] == installation_id
        assert registered["active"] is True

        status, listing = request("GET", base)
        assert status == 200
        assert any(item["installation_id"] == installation_id for item in listing["items"])

        status, detail = request("GET", f"{base}/{installation_id}")
        assert status == 200
        assert detail["active"] is True

        status, updated = request(
            "PATCH",
            f"{base}/{installation_id}",
            {"device_name": "integration fixture"},
        )
        assert status == 200
        assert updated["device_name"] == "integration fixture"

        status, revoked = request("DELETE", f"{base}/{installation_id}")
        assert status == 200
        assert revoked["active"] is False

        status, _ = request(
            "PATCH",
            f"{base}/{installation_id}",
            {"device_name": "must remain revoked"},
        )
        assert status == 409

        payload = fixture()
        payload["installation_id"] = installation_id
        status, response = request("POST", "/api/v1/network-checks", payload)
        assert status == 403
        assert response["code"] == "DEVICE_REVOKED"


if __name__ == "__main__":
    unittest.main(verbosity=2)
