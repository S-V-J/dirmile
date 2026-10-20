from datetime import datetime, timedelta, timezone

from django.test import TestCase

from routing.eta import (
    estimate_checkpoint_etas,
    estimate_eta,
)


class RoutingEtaTests(TestCase):
    def test_naive_departure_is_treated_as_utc(self):
        departure = datetime(2026, 10, 20, 8, 0, 0)

        eta = estimate_eta(
            departure=departure,
            mile_marker=50,
            total_miles=100,
            total_duration_seconds=3600,
        )

        expected = datetime(2026, 10, 20, 8, 30, 0, tzinfo=timezone.utc)

        self.assertEqual(eta, expected)
        self.assertEqual(eta.tzinfo, timezone.utc)

    def test_aware_departure_is_converted_to_utc(self):
        eastern = timezone(timedelta(hours=-4))

        departure = datetime(
            2026,
            10,
            20,
            8,
            0,
            0,
            tzinfo=eastern,
        )

        eta = estimate_eta(
            departure=departure,
            mile_marker=100,
            total_miles=100,
            total_duration_seconds=3600,
        )

        # 08:00 UTC-4 is 12:00 UTC.
        # Arrival is 13:00 UTC.
        expected = datetime(2026, 10, 20, 13, 0, 0, tzinfo=timezone.utc)

        self.assertEqual(eta, expected)
        self.assertEqual(eta.tzinfo, timezone.utc)

    def test_zero_distance_route_returns_departure(self):
        departure = datetime(2026, 10, 20, 8, 0, 0, tzinfo=timezone.utc)

        eta = estimate_eta(
            departure=departure,
            mile_marker=10,
            total_miles=0,
            total_duration_seconds=3600,
        )

        self.assertEqual(eta, departure)

    def test_linear_fallback_midpoint(self):
        departure = datetime(2026, 10, 20, 8, 0, 0, tzinfo=timezone.utc)

        eta = estimate_eta(
            departure=departure,
            mile_marker=25,
            total_miles=100,
            total_duration_seconds=1000,
        )

        expected = departure + timedelta(seconds=250)

        self.assertEqual(eta, expected)

    def test_clamps_before_origin_and_after_destination(self):
        departure = datetime(2026, 10, 20, 8, 0, 0, tzinfo=timezone.utc)

        before_origin = estimate_eta(
            departure=departure,
            mile_marker=-10,
            total_miles=100,
            total_duration_seconds=1000,
        )

        after_destination = estimate_eta(
            departure=departure,
            mile_marker=150,
            total_miles=100,
            total_duration_seconds=1000,
        )

        self.assertEqual(before_origin, departure)
        self.assertEqual(
            after_destination,
            departure + timedelta(seconds=1000),
        )

    def test_uses_step_durations_when_available(self):
        departure = datetime(2026, 10, 20, 8, 0, 0, tzinfo=timezone.utc)

        steps = [
            {
                "distance": 50,
                "duration": 900,
            },
            {
                "distance": 50,
                "duration": 100,
            },
        ]

        quarter_eta = estimate_eta(
            departure=departure,
            mile_marker=25,
            total_miles=100,
            total_duration_seconds=1000,
            steps=steps,
        )

        three_quarter_eta = estimate_eta(
            departure=departure,
            mile_marker=75,
            total_miles=100,
            total_duration_seconds=1000,
            steps=steps,
        )

        # First step covers 0-50 miles and 0-900 seconds.
        # At mile 25, fraction is 0.25, halfway through first step:
        # 450 seconds.
        self.assertEqual(quarter_eta, departure + timedelta(seconds=450))

        # Second step covers 50-100 miles and 900-1000 seconds.
        # At mile 75, fraction is 0.75, halfway through second step:
        # 950 seconds.
        self.assertEqual(three_quarter_eta, departure + timedelta(seconds=950))

    def test_step_durations_are_scaled_to_total_duration(self):
        departure = datetime(2026, 10, 20, 8, 0, 0, tzinfo=timezone.utc)

        steps = [
            {
                "distance": 50,
                "duration": 900,
            },
            {
                "distance": 50,
                "duration": 100,
            },
        ]

        quarter_eta = estimate_eta(
            departure=departure,
            mile_marker=25,
            total_miles=100,
            total_duration_seconds=2000,
            steps=steps,
        )

        destination_eta = estimate_eta(
            departure=departure,
            mile_marker=100,
            total_miles=100,
            total_duration_seconds=2000,
            steps=steps,
        )

        # Raw step duration sum is 1000 seconds.
        # Route duration is 2000 seconds, so step durations are scaled by 2.
        # First step becomes 0-1800 seconds.
        # At mile 25, halfway through first step: 900 seconds.
        self.assertEqual(quarter_eta, departure + timedelta(seconds=900))

        # Destination must exactly equal departure + total route duration.
        self.assertEqual(destination_eta, departure + timedelta(seconds=2000))

    def test_invalid_steps_fall_back_to_linear(self):
        departure = datetime(2026, 10, 20, 8, 0, 0, tzinfo=timezone.utc)

        eta = estimate_eta(
            departure=departure,
            mile_marker=50,
            total_miles=100,
            total_duration_seconds=1000,
            steps=[
                {"distance": "bad"},
                None,
                {},
            ],
        )

        expected = departure + timedelta(seconds=500)

        self.assertEqual(eta, expected)

    def test_estimate_checkpoint_etas_returns_sorted_monotonic_utc(self):
        departure = datetime(2026, 10, 20, 8, 0, 0, tzinfo=timezone.utc)

        checkpoints = [
            {
                "mile": 75,
                "lat": 40.5,
                "lng": -86.5,
            },
            {
                "mile": 0,
                "lat": 39.1031,
                "lng": -84.5120,
            },
            {
                "mile": 25,
                "lat": 39.4,
                "lng": -85.0,
            },
            {
                "mile": 100,
                "lat": 41.8781,
                "lng": -87.6298,
            },
        ]

        results = estimate_checkpoint_etas(
            departure=departure,
            checkpoints=checkpoints,
            total_miles=100,
            total_duration_seconds=1000,
        )

        mile_markers = [row["mile"] for row in results]
        etas = [row["eta_utc"] for row in results]

        self.assertEqual(mile_markers, [0.0, 25.0, 75.0, 100.0])

        self.assertEqual(etas, sorted(etas))

        self.assertTrue(
            all(row["eta_utc"].tzinfo == timezone.utc for row in results)
        )

        self.assertEqual(results[0]["eta_utc"], departure)
        self.assertEqual(
            results[-1]["eta_utc"],
            departure + timedelta(seconds=1000),
        )

        # Original checkpoint metadata should be preserved.
        self.assertEqual(results[0]["lat"], 39.1031)
        self.assertEqual(results[0]["lng"], -84.5120)

        self.assertEqual(results[1]["lat"], 39.4)
        self.assertEqual(results[1]["lng"], -85.0)

        self.assertEqual(results[2]["lat"], 40.5)
        self.assertEqual(results[2]["lng"], -86.5)

        self.assertEqual(results[3]["lat"], 41.8781)
        self.assertEqual(results[3]["lng"], -87.6298)

    def test_duplicate_mile_markers_get_same_eta(self):
        departure = datetime(2026, 10, 20, 8, 0, 0, tzinfo=timezone.utc)

        checkpoints = [
            {
                "mile": 50,
                "lat": 1.0,
                "lng": 2.0,
            },
            {
                "mile": 50,
                "lat": 3.0,
                "lng": 4.0,
            },
        ]

        results = estimate_checkpoint_etas(
            departure=departure,
            checkpoints=checkpoints,
            total_miles=100,
            total_duration_seconds=1000,
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["mile"], 50.0)
        self.assertEqual(results[1]["mile"], 50.0)
        self.assertEqual(results[0]["eta_utc"], results[1]["eta_utc"])
