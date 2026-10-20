from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from weather.forecast import (
    CM_PER_INCH,
    WeatherAPIError,
    WeatherError,
    build_forecast_url,
    fetch_forecast,
    get_weather_at_time,
    normalize_forecast_response,
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


def sample_forecast_payload(num_coords=1, num_hours=5):
    """
    Build a sample Open-Meteo forecast response.
    """
    base_time = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
    times = [(base_time + timedelta(hours=i)).isoformat() for i in range(num_hours)]

    items = []
    for coord_index in range(num_coords):
        items.append(
            {
                "latitude": 39.1031 + coord_index * 0.01,
                "longitude": -84.5120 - coord_index * 0.01,
                "hourly": {
                    "time": times,
                    "wind_speed_10m": [10.0 + i for i in range(num_hours)],
                    "wind_gusts_10m": [15.0 + i for i in range(num_hours)],
                    "rain": [0.0, 0.05, 0.12, 0.30, 0.0],
                    "snowfall": [0.0, 0.0, 0.5, 1.2, 0.0],
                    "temperature_2m": [55.0 + i for i in range(num_hours)],
                    "weather_code": [0, 1, 61, 71, 0],
                },
            }
        )

    if num_coords == 1:
        return items[0]
    return items


class ForecastUrlTests(SimpleTestCase):
    def test_build_forecast_url_single_coordinate(self):
        start = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)

        url = build_forecast_url(
            coordinates=[(39.1031, -84.5120)],
            start_time=start,
            end_time=end,
            base_url="https://api.open-meteo.com",
        )

        parsed = urlsplit(url)
        query = parse_qs(parsed.query)

        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "api.open-meteo.com")
        self.assertEqual(parsed.path, "/v1/forecast")
        self.assertEqual(query["latitude"], ["39.103100"])
        self.assertEqual(query["longitude"], ["-84.512000"])
        self.assertIn("wind_speed_10m", query["hourly"][0])
        self.assertIn("snowfall", query["hourly"][0])
        self.assertEqual(query["wind_speed_unit"], ["mph"])
        self.assertEqual(query["precipitation_unit"], ["inch"])
        self.assertEqual(query["temperature_unit"], ["fahrenheit"])
        self.assertEqual(query["timezone"], ["UTC"])

    def test_build_forecast_url_multiple_coordinates(self):
        start = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)

        url = build_forecast_url(
            coordinates=[
                (39.1031, -84.5120),
                (41.8781, -87.6298),
            ],
            start_time=start,
            end_time=end,
            base_url="https://api.open-meteo.com",
        )

        parsed = urlsplit(url)
        query = parse_qs(parsed.query)

        self.assertEqual(query["latitude"], ["39.103100,41.878100"])
        self.assertEqual(query["longitude"], ["-84.512000,-87.629800"])

    def test_build_forecast_url_rejects_empty_coordinates(self):
        start = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)

        with self.assertRaises(ValueError):
            build_forecast_url(
                coordinates=[],
                start_time=start,
                end_time=end,
            )

    def test_build_forecast_url_rejects_invalid_time_range(self):
        start = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)

        with self.assertRaises(ValueError):
            build_forecast_url(
                coordinates=[(39.1031, -84.5120)],
                start_time=start,
                end_time=end,
            )

    def test_build_forecast_url_rejects_invalid_coordinates(self):
        start = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)

        with self.assertRaises(ValueError):
            build_forecast_url(
                coordinates=[(91.0, 0.0)],
                start_time=start,
                end_time=end,
            )

        with self.assertRaises(ValueError):
            build_forecast_url(
                coordinates=[(0.0, 181.0)],
                start_time=start,
                end_time=end,
            )


class ForecastNormalizeTests(SimpleTestCase):
    def test_normalize_single_coordinate_response(self):
        payload = sample_forecast_payload(num_coords=1, num_hours=5)
        results = normalize_forecast_response(payload, expected_count=1)

        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0]["latitude"], 39.1031)
        self.assertAlmostEqual(results[0]["longitude"], -84.5120)

        hourly = results[0]["hourly"]
        self.assertEqual(len(hourly["time"]), 5)
        self.assertEqual(len(hourly["wind_speed_mph"]), 5)
        self.assertEqual(len(hourly["rain_in_hr"]), 5)
        self.assertEqual(len(hourly["snow_in_hr"]), 5)
        self.assertEqual(len(hourly["temperature_f"]), 5)
        self.assertEqual(len(hourly["weather_code"]), 5)

        # Snowfall conversion: 0.5 cm / 2.54 = ~0.1969 in
        self.assertAlmostEqual(hourly["snow_in_hr"][2], 0.5 / CM_PER_INCH, places=5)
        # 1.2 cm / 2.54 = ~0.4724 in
        self.assertAlmostEqual(hourly["snow_in_hr"][3], 1.2 / CM_PER_INCH, places=5)

        # Wind speed should be preserved as-is (already mph).
        self.assertAlmostEqual(hourly["wind_speed_mph"][0], 10.0)

        # Weather codes should be integers.
        self.assertEqual(hourly["weather_code"][0], 0)
        self.assertEqual(hourly["weather_code"][2], 61)

    def test_normalize_multi_coordinate_response(self):
        payload = sample_forecast_payload(num_coords=3, num_hours=5)
        results = normalize_forecast_response(payload, expected_count=3)

        self.assertEqual(len(results), 3)
        self.assertAlmostEqual(results[0]["latitude"], 39.1031)
        self.assertAlmostEqual(results[1]["latitude"], 39.1131)
        self.assertAlmostEqual(results[2]["latitude"], 39.1231)

    def test_normalize_raises_for_count_mismatch(self):
        payload = sample_forecast_payload(num_coords=2, num_hours=5)
        with self.assertRaises(WeatherError):
            normalize_forecast_response(payload, expected_count=1)

    def test_normalize_raises_for_non_dict_payload(self):
        with self.assertRaises(WeatherError):
            normalize_forecast_response("not a dict", expected_count=1)

    def test_normalize_raises_for_missing_hourly(self):
        with self.assertRaises(WeatherError):
            normalize_forecast_response(
                {"latitude": 39.0, "longitude": -84.0},
                expected_count=1,
            )

    def test_normalize_handles_null_values(self):
        payload = {
            "latitude": 39.0,
            "longitude": -84.0,
            "hourly": {
                "time": ["2026-10-20T08:00", "2026-10-20T09:00"],
                "wind_speed_10m": [10.0, None],
                "wind_gusts_10m": [None, 20.0],
                "rain": [0.0, None],
                "snowfall": [None, 0.5],
                "temperature_2m": [55.0, None],
                "weather_code": [0, None],
            },
        }
        results = normalize_forecast_response(payload, expected_count=1)
        hourly = results[0]["hourly"]
        self.assertAlmostEqual(hourly["wind_speed_mph"][0], 10.0)
        self.assertIsNone(hourly["wind_speed_mph"][1])
        self.assertIsNone(hourly["wind_gust_mph"][0])
        self.assertAlmostEqual(hourly["wind_gust_mph"][1], 20.0)
        self.assertIsNone(hourly["snow_in_hr"][0])
        self.assertAlmostEqual(hourly["snow_in_hr"][1], 0.5 / CM_PER_INCH, places=5)
        self.assertIsNone(hourly["weather_code"][1])


class GetWeatherAtTimeTests(SimpleTestCase):
    def setUp(self):
        self.payload = sample_forecast_payload(num_coords=1, num_hours=5)
        self.results = normalize_forecast_response(self.payload, expected_count=1)
        self.coord_data = self.results[0]

    def test_exact_hour_match(self):
        # First hour is 2026-10-20T08:00 UTC
        target = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
        weather = get_weather_at_time(self.coord_data, target)

        self.assertAlmostEqual(weather["wind_speed_mph"], 10.0)
        self.assertAlmostEqual(weather["rain_in_hr"], 0.0)
        self.assertAlmostEqual(weather["snow_in_hr"], 0.0)
        self.assertEqual(weather["weather_code"], 0)
        self.assertIsNotNone(weather["matched_time"])

    def test_interpolated_halfway(self):
        # Between hour 0 (wind=10) and hour 1 (wind=11)
        target = datetime(2026, 10, 20, 8, 30, tzinfo=timezone.utc)
        weather = get_weather_at_time(self.coord_data, target)

        # Should be approximately 10.5
        self.assertAlmostEqual(weather["wind_speed_mph"], 10.5, places=1)

    def test_before_all_data_uses_first(self):
        target = datetime(2026, 10, 20, 6, 0, tzinfo=timezone.utc)
        weather = get_weather_at_time(self.coord_data, target)

        # Should use first available value.
        self.assertAlmostEqual(weather["wind_speed_mph"], 10.0)

    def test_after_all_data_uses_last(self):
        target = datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc)
        weather = get_weather_at_time(self.coord_data, target)

        # Last hour wind is 14.0 (10 + 4)
        self.assertAlmostEqual(weather["wind_speed_mph"], 14.0)

    def test_empty_times_returns_defaults(self):
        empty_data = {"hourly": {"time": []}}
        target = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
        weather = get_weather_at_time(empty_data, target)

        self.assertEqual(weather["wind_speed_mph"], 0.0)
        self.assertEqual(weather["rain_in_hr"], 0.0)
        self.assertEqual(weather["snow_in_hr"], 0.0)
        self.assertIsNone(weather["matched_time"])

    def test_none_target_time_returns_defaults(self):
        weather = get_weather_at_time(self.coord_data, None)
        self.assertEqual(weather["wind_speed_mph"], 0.0)
        self.assertIsNone(weather["matched_time"])


@override_settings(
    WEATHER_BASE_URL="https://weather.example.test",
    WEATHER_TIMEOUT_SECONDS=12.0,
    WEATHER_CACHE_TTL_SECONDS=0,
)
class FetchForecastTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_fetch_forecast_success_single_coordinate(self):
        payload = sample_forecast_payload(num_coords=1, num_hours=5)
        session = FakeSession(
            response=FakeResponse(status_code=200, payload=payload)
        )

        start = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)

        results = fetch_forecast(
            coordinates=[(39.1031, -84.5120)],
            start_time=start,
            end_time=end,
            session=session,
            use_cache=False,
        )

        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0]["latitude"], 39.1031)

        self.assertIsNotNone(session.last_url)
        self.assertTrue(
            session.last_url.startswith("https://weather.example.test/v1/forecast?")
        )
        self.assertEqual(session.last_timeout, 12.0)
        self.assertEqual(session.last_headers["Accept"], "application/json")
        self.assertIn("Dirmile", session.last_headers["User-Agent"])

    def test_fetch_forecast_success_multiple_coordinates(self):
        payload = sample_forecast_payload(num_coords=3, num_hours=5)
        session = FakeSession(
            response=FakeResponse(status_code=200, payload=payload)
        )

        start = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)

        results = fetch_forecast(
            coordinates=[
                (39.1031, -84.5120),
                (40.0, -85.0),
                (41.8781, -87.6298),
            ],
            start_time=start,
            end_time=end,
            session=session,
            use_cache=False,
        )

        self.assertEqual(len(results), 3)

    def test_fetch_forecast_empty_coordinates_raises(self):
        start = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)

        with self.assertRaises(ValueError):
            fetch_forecast(
                coordinates=[],
                start_time=start,
                end_time=end,
            )

    def test_fetch_forecast_http_error_raises_weather_api_error(self):
        session = FakeSession(
            response=FakeResponse(
                status_code=429,
                text="rate limited",
            )
        )

        start = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)

        with self.assertRaises(WeatherAPIError) as cm:
            fetch_forecast(
                coordinates=[(39.1031, -84.5120)],
                start_time=start,
                end_time=end,
                session=session,
                use_cache=False,
            )

        self.assertEqual(cm.exception.status_code, 429)
        self.assertIn("429", str(cm.exception))

    def test_fetch_forecast_invalid_json_raises_weather_error(self):
        session = FakeSession(
            response=FakeResponse(status_code=200, payload=None)
        )

        start = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)

        with self.assertRaises(WeatherError):
            fetch_forecast(
                coordinates=[(39.1031, -84.5120)],
                start_time=start,
                end_time=end,
                session=session,
                use_cache=False,
            )

    def test_fetch_forecast_request_exception_raises_weather_error(self):
        session = FakeSession(
            exc=requests.exceptions.ConnectionError("network down")
        )

        start = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)

        with self.assertRaises(WeatherError):
            fetch_forecast(
                coordinates=[(39.1031, -84.5120)],
                start_time=start,
                end_time=end,
                session=session,
                use_cache=False,
            )

    @override_settings(WEATHER_CACHE_TTL_SECONDS=86400)
    def test_fetch_forecast_caches_results(self):
        payload = sample_forecast_payload(num_coords=1, num_hours=5)
        session = FakeSession(
            response=FakeResponse(status_code=200, payload=payload)
        )

        start = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)

        # First call: no cache, hits session.
        results_first = fetch_forecast(
            coordinates=[(39.1031, -84.5120)],
            start_time=start,
            end_time=end,
            session=session,
            use_cache=True,
        )

        self.assertEqual(len(results_first), 1)
        self.assertIsNotNone(session.last_url)

        # Second call: should hit cache.
        session2 = FakeSession(
            response=FakeResponse(status_code=200, payload=None)
        )

        results_second = fetch_forecast(
            coordinates=[(39.1031, -84.5120)],
            start_time=start,
            end_time=end,
            session=session2,
            use_cache=True,
        )

        self.assertEqual(len(results_second), 1)
        self.assertAlmostEqual(results_second[0]["latitude"], 39.1031)
        # session2.get was never called because cache returned the result.
        self.assertIsNone(session2.last_url)
