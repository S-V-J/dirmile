"""Guards the Open-Meteo request-line limit.

A 414 from nginx is invisible to unit tests that mock the HTTP layer, so this
test asserts the *built URL length* directly. If anybody raises the batch cap
or the coordinate format again, this fails loudly instead of the API failing
silently in production.
"""
from datetime import datetime, timedelta, timezone

from django.test import TestCase

from weather.forecast import MAX_COORDINATES_PER_REQUEST, build_forecast_url


class ForecastUrlLengthTests(TestCase):
    def test_full_batch_url_stays_well_under_nginx_request_line_limit(self):
        # Worst realistic case: 6-decimal coords, negative longitudes.
        coords = [
            (39.0 + i * 0.001, -84.0 - i * 0.001)
            for i in range(MAX_COORDINATES_PER_REQUEST)
        ]
        start = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=48)
        url = build_forecast_url(coords, start, end)
        # nginx default large_client_header_buffers = 8k; keep 25% headroom.
        self.assertLess(
            len(url),
            6144,
            f"forecast URL is {len(url)} bytes — too close to the 8 KB limit",
        )

    def test_builder_rejects_oversized_batches(self):
        coords = [(39.0, -84.0)] * (MAX_COORDINATES_PER_REQUEST + 1)
        start = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            build_forecast_url(coords, start, start + timedelta(hours=1))
