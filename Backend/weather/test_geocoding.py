from urllib.parse import parse_qs, urlsplit

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from weather.geocoding import (
    GeocodingAPIError,
    GeocodingError,
    build_geocoding_url,
    normalize_geocoding_response,
    search_places,
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


def sample_geocoding_payload(result_count=2):
    results = []

    for index in range(result_count):
        results.append(
            {
                "id": 4517009 + index,
                "name": f"Cincinnati {index}",
                "latitude": 39.1620 + index * 0.01,
                "longitude": -84.4569 - index * 0.01,
                "elevation": 149.0,
                "feature_code": "PCL",
                "country_code": "US",
                "admin1_id": 4517008,
                "admin2_id": 4513934,
                "timezone": "America/New_York",
                "population": 305841,
                "country_id": 6252001,
                "country": "United States",
                "admin1": "Ohio",
                "admin2": "Hamilton County",
                "place_id": 252935 + index,
            }
        )

    return {"results": results}


class GeocodingUrlTests(SimpleTestCase):
    def test_build_geocoding_url_formats_query_and_params(self):
        url = build_geocoding_url(
            query="Cincinnati",
            count=5,
            language="en",
            base_url="https://geocoding-api.open-meteo.com",
        )

        parsed = urlsplit(url)
        query = parse_qs(parsed.query)

        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "geocoding-api.open-meteo.com")
        self.assertEqual(parsed.path, "/v1/search")
        self.assertEqual(query["name"], ["Cincinnati"])
        self.assertEqual(query["count"], ["5"])
        self.assertEqual(query["language"], ["en"])
        self.assertEqual(query["format"], ["json"])

    def test_build_geocoding_url_rejects_empty_query(self):
        with self.assertRaises(ValueError):
            build_geocoding_url(query="")

        with self.assertRaises(ValueError):
            build_geocoding_url(query="   ")

    def test_build_geocoding_url_clamps_count(self):
        url = build_geocoding_url(query="Test", count=100)
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        self.assertEqual(query["count"], ["20"])

        url = build_geocoding_url(query="Test", count=0)
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        self.assertEqual(query["count"], ["1"])


class GeocodingNormalizeTests(SimpleTestCase):
    def test_normalize_geocoding_response_basic(self):
        payload = sample_geocoding_payload(result_count=2)

        results = normalize_geocoding_response(payload)

        self.assertEqual(len(results), 2)

        first = results[0]
        self.assertEqual(first["id"], 4517009)
        self.assertEqual(first["name"], "Cincinnati 0")
        self.assertAlmostEqual(first["latitude"], 39.1620)
        self.assertAlmostEqual(first["longitude"], -84.4569)
        self.assertEqual(first["timezone"], "America/New_York")
        self.assertEqual(first["country_code"], "US")
        self.assertEqual(first["country"], "United States")
        self.assertEqual(first["admin1"], "Ohio")
        self.assertEqual(first["admin2"], "Hamilton County")
        self.assertEqual(first["population"], 305841)
        self.assertAlmostEqual(first["elevation"], 149.0)
        self.assertEqual(first["feature_code"], "PCL")
        self.assertIn("Cincinnati 0", first["display_name"])
        self.assertIn("Ohio", first["display_name"])
        self.assertIn("United States", first["display_name"])

    def test_normalize_geocoding_response_filters_by_country(self):
        payload = {
            "results": [
                {
                    "id": 1,
                    "name": "Paris",
                    "latitude": 48.8566,
                    "longitude": 2.3522,
                    "country_code": "FR",
                    "country": "France",
                    "admin1": "Île-de-France",
                    "admin2": "",
                    "timezone": "Europe/Paris",
                    "population": 2148000,
                    "elevation": 35.0,
                    "feature_code": "PPLC",
                },
                {
                    "id": 2,
                    "name": "Paris",
                    "latitude": 33.6609,
                    "longitude": -95.5428,
                    "country_code": "US",
                    "country": "United States",
                    "admin1": "Texas",
                    "admin2": "Lamar County",
                    "timezone": "America/Chicago",
                    "population": 25000,
                    "elevation": 180.0,
                    "feature_code": "PPL",
                },
            ]
        }

        us_results = normalize_geocoding_response(payload, country_code="US")
        self.assertEqual(len(us_results), 1)
        self.assertEqual(us_results[0]["country_code"], "US")
        self.assertEqual(us_results[0]["admin1"], "Texas")

        fr_results = normalize_geocoding_response(payload, country_code="FR")
        self.assertEqual(len(fr_results), 1)
        self.assertEqual(fr_results[0]["country_code"], "FR")

        all_results = normalize_geocoding_response(payload, country_code="")
        self.assertEqual(len(all_results), 2)

    def test_normalize_geocoding_response_handles_missing_results(self):
        results = normalize_geocoding_response({})
        self.assertEqual(results, [])

        results = normalize_geocoding_response({"results": None})
        self.assertEqual(results, [])

    def test_normalize_geocoding_response_skips_invalid_items(self):
        payload = {
            "results": [
                {
                    "id": 1,
                    "name": "Valid",
                    "latitude": 39.0,
                    "longitude": -84.0,
                    "country_code": "US",
                },
                {
                    "id": 2,
                    "name": "NoLat",
                    "longitude": -84.0,
                    "country_code": "US",
                },
                "not-a-dict",
                {
                    "id": 3,
                    "name": "NoLng",
                    "latitude": 39.0,
                    "country_code": "US",
                },
            ]
        }

        results = normalize_geocoding_response(payload)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Valid")

    def test_normalize_geocoding_response_raises_for_non_dict_payload(self):
        with self.assertRaises(GeocodingError):
            normalize_geocoding_response("not a dict")

        with self.assertRaises(GeocodingError):
            normalize_geocoding_response([1, 2, 3])

    def test_normalize_geocoding_response_raises_for_non_list_results(self):
        with self.assertRaises(GeocodingError):
            normalize_geocoding_response({"results": "not a list"})


@override_settings(
    GEOCODING_BASE_URL="https://geocoding.example.test",
    GEOCODING_TIMEOUT_SECONDS=7.0,
    GEOCODING_CACHE_TTL_SECONDS=0,
)
class GeocodingSearchTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_search_places_success_uses_session_and_timeout(self):
        payload = sample_geocoding_payload(result_count=2)
        session = FakeSession(
            response=FakeResponse(status_code=200, payload=payload)
        )

        results = search_places(
            query="Cincinnati",
            count=5,
            language="en",
            country_code="",
            session=session,
            use_cache=False,
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "Cincinnati 0")

        self.assertIsNotNone(session.last_url)
        self.assertTrue(
            session.last_url.startswith("https://geocoding.example.test/v1/search?")
        )
        self.assertEqual(session.last_timeout, 7.0)
        self.assertEqual(session.last_headers["Accept"], "application/json")
        self.assertIn("Dirmile", session.last_headers["User-Agent"])

    def test_search_places_filters_by_country_code(self):
        payload = {
            "results": [
                {
                    "id": 1,
                    "name": "Paris",
                    "latitude": 48.8566,
                    "longitude": 2.3522,
                    "country_code": "FR",
                    "country": "France",
                    "admin1": "Île-de-France",
                    "admin2": "",
                    "timezone": "Europe/Paris",
                    "population": 2148000,
                    "elevation": 35.0,
                    "feature_code": "PPLC",
                },
                {
                    "id": 2,
                    "name": "Paris",
                    "latitude": 33.6609,
                    "longitude": -95.5428,
                    "country_code": "US",
                    "country": "United States",
                    "admin1": "Texas",
                    "admin2": "Lamar County",
                    "timezone": "America/Chicago",
                    "population": 25000,
                    "elevation": 180.0,
                    "feature_code": "PPL",
                },
            ]
        }

        session = FakeSession(
            response=FakeResponse(status_code=200, payload=payload)
        )

        results = search_places(
            query="Paris",
            country_code="US",
            session=session,
            use_cache=False,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["country_code"], "US")

    def test_search_places_empty_query_raises_value_error(self):
        with self.assertRaises(ValueError):
            search_places(query="")

        with self.assertRaises(ValueError):
            search_places(query="   ")

    def test_search_places_http_error_raises_geocoding_api_error(self):
        session = FakeSession(
            response=FakeResponse(
                status_code=429,
                text="rate limited",
            )
        )

        with self.assertRaises(GeocodingAPIError) as cm:
            search_places(
                query="Cincinnati",
                session=session,
                use_cache=False,
            )

        self.assertEqual(cm.exception.status_code, 429)
        self.assertIn("429", str(cm.exception))

    def test_search_places_invalid_json_raises_geocoding_error(self):
        session = FakeSession(
            response=FakeResponse(status_code=200, payload=None)
        )

        with self.assertRaises(GeocodingError):
            search_places(
                query="Cincinnati",
                session=session,
                use_cache=False,
            )

    def test_search_places_request_exception_raises_geocoding_error(self):
        session = FakeSession(
            exc=requests.exceptions.ConnectionError("network down")
        )

        with self.assertRaises(GeocodingError):
            search_places(
                query="Cincinnati",
                session=session,
                use_cache=False,
            )

    def test_search_places_returns_empty_list_for_no_results(self):
        session = FakeSession(
            response=FakeResponse(
                status_code=200,
                payload={"results": []},
            )
        )

        results = search_places(
            query="NonexistentPlace12345",
            session=session,
            use_cache=False,
        )

        self.assertEqual(results, [])

    @override_settings(GEOCODING_CACHE_TTL_SECONDS=86400)
    def test_search_places_caches_results(self):
        payload = sample_geocoding_payload(result_count=1)
        session = FakeSession(
            response=FakeResponse(status_code=200, payload=payload)
        )

        # First call: no cache, hits session.
        results_first = search_places(
            query="Cincinnati",
            session=session,
            use_cache=True,
        )

        self.assertEqual(len(results_first), 1)
        self.assertEqual(session.last_url is not None, True)

        # Second call: should hit cache, session.get should not be called again.
        session2 = FakeSession(
            response=FakeResponse(status_code=200, payload={"results": []})
        )

        results_second = search_places(
            query="Cincinnati",
            session=session2,
            use_cache=True,
        )

        self.assertEqual(len(results_second), 1)
        self.assertEqual(results_second[0]["name"], "Cincinnati 0")
        # session2.get was never called because cache returned the result.
        self.assertIsNone(session2.last_url)
