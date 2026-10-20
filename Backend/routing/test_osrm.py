from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import requests
from django.test import SimpleTestCase

from routing.osrm import (
    RoutingAPIError,
    RoutingError,
    RoutingNoRouteError,
    build_route_url,
    fetch_routes,
    normalize_osrm_response,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON")

        return self._payload


class FakeSession:
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc

        self.last_url = None
        self.last_timeout = None
        self.last_headers = None

    def get(self, url, timeout=None, headers=None):
        self.last_url = url
        self.last_timeout = timeout
        self.last_headers = headers

        if self.exc is not None:
            raise self.exc

        if self.response is None:
            raise AssertionError("FakeSession requires a response or exception.")

        return self.response


def sample_osrm_payload(route_count=1):
    routes = []

    for index in range(route_count):
        routes.append(
            {
                "distance": 160934.4 * (index + 1),
                "duration": 3600 * (index + 1),
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-84.5120, 39.1031],
                        [-87.6298, 41.8781],
                    ],
                },
                "legs": [
                    {
                        "steps": [
                            {
                                "distance": 80467.2,
                                "duration": 1800,
                                "name": f"I-75 {index}",
                            },
                            {
                                "distance": 80467.2,
                                "duration": 1800,
                                "name": f"I-80 {index}",
                            },
                        ]
                    }
                ],
            }
        )

    return {
        "code": "Ok",
        "routes": routes,
    }


class OsrmRoutingClientTests(SimpleTestCase):
    def test_build_route_url_formats_coordinates_and_params(self):
        url = build_route_url(
            origin=(39.1031, -84.5120),
            destination=(41.8781, -87.6298),
            alternatives=3,
            base_url="https://router.project-osrm.org",
        )

        parsed = urlsplit(url)
        query = parse_qs(parsed.query)

        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "router.project-osrm.org")
        self.assertEqual(
            parsed.path,
            "/route/v1/driving/-84.512,39.1031;-87.6298,41.8781",
        )

        self.assertEqual(query["alternatives"], ["3"])
        self.assertEqual(query["overview"], ["full"])
        self.assertEqual(query["geometries"], ["geojson"])
        self.assertEqual(query["steps"], ["true"])

    def test_build_route_url_rejects_invalid_coordinates(self):
        with self.assertRaises(ValueError):
            build_route_url(
                origin=(91.0, 0.0),
                destination=(0.0, 0.0),
            )

        with self.assertRaises(ValueError):
            build_route_url(
                origin=(0.0, 181.0),
                destination=(0.0, 0.0),
            )

    def test_build_route_url_rejects_identical_origin_destination(self):
        with self.assertRaises(ValueError):
            build_route_url(
                origin=(39.1031, -84.5120),
                destination=(39.1031, -84.5120),
            )

    def test_normalize_osrm_response_converts_units_and_extracts_steps(self):
        payload = sample_osrm_payload(route_count=1)

        routes = normalize_osrm_response(payload, max_routes=3)

        self.assertEqual(len(routes), 1)

        route = routes[0]

        self.assertEqual(route["label"], "Route A")
        self.assertEqual(route["route_index"], 0)
        self.assertAlmostEqual(route["distance_miles"], 100.0)
        self.assertEqual(route["duration_seconds"], 3600.0)
        self.assertEqual(route["geometry"]["type"], "LineString")

        self.assertEqual(len(route["steps"]), 2)
        self.assertEqual(route["steps"][0]["name"], "I-75 0")
        self.assertEqual(route["steps"][1]["name"], "I-80 0")

    def test_normalize_osrm_response_raises_for_no_route_code(self):
        with self.assertRaises(RoutingNoRouteError):
            normalize_osrm_response(
                {
                    "code": "NoRoute",
                    "routes": [],
                }
            )

    def test_normalize_osrm_response_raises_for_api_error_code(self):
        with self.assertRaises(RoutingAPIError):
            normalize_osrm_response(
                {
                    "code": "InvalidService",
                    "routes": [],
                }
            )

    def test_fetch_routes_success_uses_session_and_timeout(self):
        payload = sample_osrm_payload(route_count=1)
        session = FakeSession(response=FakeResponse(status_code=200, payload=payload))

        routes = fetch_routes(
            origin=(39.1031, -84.5120),
            destination=(41.8781, -87.6298),
            alternatives=3,
            base_url="https://routing.example.test",
            timeout=7,
            session=session,
        )

        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0]["label"], "Route A")
        self.assertAlmostEqual(routes[0]["distance_miles"], 100.0)

        self.assertIsNotNone(session.last_url)
        self.assertTrue(session.last_url.startswith("https://routing.example.test/route/v1/driving/"))
        self.assertEqual(session.last_timeout, 7.0)
        self.assertEqual(session.last_headers["Accept"], "application/json")
        self.assertIn("Dirmile", session.last_headers["User-Agent"])

    def test_fetch_routes_http_error_raises_routing_api_error(self):
        session = FakeSession(
            response=FakeResponse(
                status_code=500,
                text="internal server error",
            )
        )

        with self.assertRaises(RoutingAPIError) as cm:
            fetch_routes(
                origin=(39.1031, -84.5120),
                destination=(41.8781, -87.6298),
                base_url="https://routing.example.test",
                session=session,
            )

        self.assertEqual(cm.exception.status_code, 500)
        self.assertIn("500", str(cm.exception))

    def test_fetch_routes_invalid_json_raises_routing_error(self):
        session = FakeSession(
            response=FakeResponse(
                status_code=200,
                payload=None,
            )
        )

        with self.assertRaises(RoutingError):
            fetch_routes(
                origin=(39.1031, -84.5120),
                destination=(41.8781, -87.6298),
                base_url="https://routing.example.test",
                session=session,
            )

    def test_fetch_routes_request_exception_raises_routing_error(self):
        session = FakeSession(
            exc=requests.exceptions.ConnectionError("network down")
        )

        with self.assertRaises(RoutingError):
            fetch_routes(
                origin=(39.1031, -84.5120),
                destination=(41.8781, -87.6298),
                base_url="https://routing.example.test",
                session=session,
            )

    def test_fetch_routes_no_route_payload_raises_no_route_error(self):
        session = FakeSession(
            response=FakeResponse(
                status_code=200,
                payload={
                    "code": "NoRoute",
                    "routes": [],
                },
            )
        )

        with self.assertRaises(RoutingNoRouteError):
            fetch_routes(
                origin=(39.1031, -84.5120),
                destination=(41.8781, -87.6298),
                base_url="https://routing.example.test",
                session=session,
            )

    def test_fetch_routes_returns_fewer_routes_when_osrm_provides_fewer(self):
        payload = sample_osrm_payload(route_count=2)
        session = FakeSession(response=FakeResponse(status_code=200, payload=payload))

        routes = fetch_routes(
            origin=(39.1031, -84.5120),
            destination=(41.8781, -87.6298),
            alternatives=3,
            base_url="https://routing.example.test",
            session=session,
        )

        self.assertEqual(len(routes), 2)
        self.assertEqual(routes[0]["label"], "Route A")
        self.assertEqual(routes[1]["label"], "Route B")
