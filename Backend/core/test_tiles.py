"""
Regression coverage for the same-origin tile proxy (core.tiles).

Replaces the ad-hoc forced-failure probe, which could never run outside
pytest: Django's test Client sends Host: testserver, and production
ALLOWED_HOSTS does not include it (CommonMiddleware 400s before routing).
pytest-django's autouse django_test_environment fixture appends
'testserver' for the session, so the blank-tile no-store guarantee —
the thing commit f2a7e16 claimed but did not prove — is enforced here,
permanently.
"""
from unittest.mock import Mock, patch

import requests
from django.test import Client, TestCase

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _upstream(status_code=200, content=PNG_BYTES, content_type="image/png"):
    resp = Mock(spec=["status_code", "headers", "content"])
    resp.status_code = status_code
    resp.headers = {"Content-Type": content_type}
    resp.content = content
    return resp


class TileProxyTests(TestCase):
    def setUp(self):
        self.client = Client()

    # ── happy path ────────────────────────────────────────────────
    @patch("core.tiles.requests.get")
    def test_get_success_returns_png_with_immutable_cache(self, mock_get):
        mock_get.return_value = _upstream()
        response = self.client.get("/tiles/6/16/24.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PNG_BYTES)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertIn("max-age=604800", response["Cache-Control"])
        self.assertIn("immutable", response["Cache-Control"])

    @patch("core.tiles.requests.get")
    def test_head_request_is_allowed(self, mock_get):
        mock_get.return_value = _upstream()
        response = self.client.head("/tiles/6/16/24.png")
        self.assertEqual(response.status_code, 200)

    @patch("core.tiles.requests.get")
    def test_uppercase_extension_accepted(self, mock_get):
        mock_get.return_value = _upstream()
        response = self.client.get("/tiles/6/16/24.PNG")
        self.assertEqual(response.status_code, 200)

    # ── blank path: no-store, never a 7-day hole ──────────────────
    @patch("core.tiles.requests.get", side_effect=requests.ConnectionError("forced"))
    def test_upstream_network_error_returns_blank_no_store(self, mock_get):
        response = self.client.get("/tiles/6/16/24.png")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["Cache-Control"], "no-store")

    @patch("core.tiles.requests.get")
    def test_upstream_non_200_returns_blank_no_store(self, mock_get):
        mock_get.return_value = _upstream(status_code=500, content=b"boom", content_type="text/html")
        response = self.client.get("/tiles/6/16/24.png")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["Cache-Control"], "no-store")

    @patch("core.tiles.requests.get")
    def test_non_image_content_type_returns_blank_no_store(self, mock_get):
        mock_get.return_value = _upstream(content_type="text/html")
        response = self.client.get("/tiles/6/16/24.png")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["Cache-Control"], "no-store")

    # ── bounds guards (mirror the live curl results exactly) ──────
    def test_zoom_out_of_range_returns_400(self):
        self.assertEqual(self.client.get("/tiles/30/1/1.png").status_code, 400)

    def test_tile_coordinates_out_of_range_return_404(self):
        # z=3 → valid indices 0..7; 9 is outside.
        self.assertEqual(self.client.get("/tiles/3/9/9.png").status_code, 404)

    def test_bad_extension_returns_400(self):
        self.assertEqual(self.client.get("/tiles/6/16/24.exe").status_code, 400)
