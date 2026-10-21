import tempfile
from pathlib import Path

from django.http import Http404
from django.test import Client, SimpleTestCase, override_settings

from core.frontend import _safe_dist_path


def _body(response):
    """
    Return response body bytes for both normal and streaming responses.
    """
    if hasattr(response, "streaming_content"):
        return b"".join(response.streaming_content)
    return response.content


class FrontendServingTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def _dist(self, tmp: str, files: dict[str, str]) -> Path:
        dist = Path(tmp)
        for relative, content in files.items():
            target = dist / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return dist

    def test_root_serves_index_when_build_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = self._dist(
                tmp,
                {"index.html": "<html><body>Dirmile test</body></html>"},
            )

            with override_settings(FRONTEND_DIST_DIR=dist):
                response = self.client.get("/")

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response["Content-Type"].startswith("text/html"))
                self.assertIn(b"Dirmile test", _body(response))

    def test_extensionless_route_serves_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = self._dist(tmp, {"index.html": "<html>SPA</html>"})

            with override_settings(FRONTEND_DIST_DIR=dist):
                response = self.client.get("/app")

                self.assertEqual(response.status_code, 200)
                self.assertIn(b"SPA", _body(response))

    def test_hashed_asset_is_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = self._dist(
                tmp,
                {"assets/index-abc123.js": "console.log(1);"},
            )

            with override_settings(FRONTEND_DIST_DIR=dist):
                response = self.client.get("/assets/index-abc123.js")

                self.assertEqual(response.status_code, 200)
                self.assertIn("immutable", response["Cache-Control"])
                self.assertIn(b"console.log(1);", _body(response))

    def test_service_worker_is_no_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = self._dist(
                tmp,
                {"sw.js": "self.addEventListener('install', () => {});"},
            )

            with override_settings(FRONTEND_DIST_DIR=dist):
                response = self.client.get("/sw.js")

                self.assertEqual(response.status_code, 200)
                self.assertIn("no-cache", response["Cache-Control"])

    def test_manifest_content_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = self._dist(tmp, {"manifest.webmanifest": '{"name":"Dirmile"}'})

            with override_settings(FRONTEND_DIST_DIR=dist):
                response = self.client.get("/manifest.webmanifest")

                self.assertEqual(response.status_code, 200)
                self.assertTrue(
                    response["Content-Type"].startswith("application/manifest+json")
                )

    def test_png_asset_is_served_as_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            icons = dist / "icons"
            icons.mkdir()
            # Minimal valid PNG signature bytes only; content is not parsed.
            (icons / "icon-192.png").write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
            )

            with override_settings(FRONTEND_DIST_DIR=dist):
                response = self.client.get("/icons/icon-192.png")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "image/png")
                self.assertIn("max-age=86400", response["Cache-Control"])
                self.assertTrue(_body(response).startswith(b"\x89PNG"))

    def test_missing_asset_returns_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = self._dist(tmp, {"index.html": "<html></html>"})

            with override_settings(FRONTEND_DIST_DIR=dist):
                response = self.client.get("/missing.js")

                self.assertEqual(response.status_code, 404)

    def test_missing_build_returns_503_for_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "does-not-exist"

            with override_settings(FRONTEND_DIST_DIR=dist):
                response = self.client.get("/")

                self.assertEqual(response.status_code, 503)
                self.assertIn(b"npm run build", _body(response))

    def test_path_traversal_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = root / "dist"
            dist.mkdir()

            outside = root / "outside.txt"
            outside.write_text("secret", encoding="utf-8")

            with override_settings(FRONTEND_DIST_DIR=dist):
                with self.assertRaises(Http404):
                    _safe_dist_path("../outside.txt")

                response = self.client.get("/..%2Foutside.txt")

                self.assertEqual(response.status_code, 404)
                self.assertNotIn(b"secret", _body(response))

    def test_unknown_api_path_is_not_served_as_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = self._dist(tmp, {"index.html": "<html>SPA</html>"})

            with override_settings(FRONTEND_DIST_DIR=dist):
                response = self.client.get("/api/this-endpoint-does-not-exist/")

                self.assertEqual(response.status_code, 404)
                self.assertNotIn(b"SPA", _body(response))

    def test_health_endpoint_is_not_shadowed_by_spa_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = self._dist(tmp, {"index.html": "<html>SPA</html>"})

            with override_settings(FRONTEND_DIST_DIR=dist):
                response = self.client.get("/api/health/")

                self.assertEqual(response.status_code, 200)
                self.assertTrue(
                    response["Content-Type"].startswith("application/json")
                )
                self.assertEqual(response.json()["status"], "ok")

    def test_spa_fallback_rejects_missing_build_for_real_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "nope"

            with override_settings(FRONTEND_DIST_DIR=dist):
                response = self.client.get("/settings")

                self.assertEqual(response.status_code, 503)
