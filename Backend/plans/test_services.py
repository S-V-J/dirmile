from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from core.geo import geojson_linestring_to_points, total_route_miles
from plans.models import TripPlan
from plans.services import (
    PlaceResolutionError,
    RouteGenerationError,
    WeatherSamplingError,
    create_trip_plan,
)
from routing.osrm import RoutingError
from weather.forecast import WeatherError


ORIGIN_PLACE = {
    "name": "Cincinnati",
    "display_name": "Cincinnati, Ohio, United States",
    "latitude": 39.1031,
    "longitude": -84.5120,
    "timezone": "America/New_York",
}

DESTINATION_PLACE = {
    "name": "Chicago",
    "display_name": "Chicago, Illinois, United States",
    "latitude": 41.8781,
    "longitude": -87.6298,
    "timezone": "America/Chicago",
}

ROUTE_A_GEOMETRY = {
    "type": "LineString",
    "coordinates": [
        [-84.5120, 39.1031],
        [-86.0000, 40.5000],
        [-87.6298, 41.8781],
    ],
}

ROUTE_B_GEOMETRY = {
    "type": "LineString",
    "coordinates": [
        [-84.5120, 39.1031],
        [-85.0000, 41.0000],
        [-87.6298, 41.8781],
    ],
}


def fake_geocode(query, country_code=None):
    places = {
        "Cincinnati, OH": ORIGIN_PLACE,
        "Chicago, IL": DESTINATION_PLACE,
    }

    place = places.get(query)

    if place is None:
        return []

    return [place]


def make_fake_routes():
    points_a = geojson_linestring_to_points(ROUTE_A_GEOMETRY)
    points_b = geojson_linestring_to_points(ROUTE_B_GEOMETRY)

    return [
        {
            "label": "Route A",
            "route_index": 0,
            "distance_miles": total_route_miles(points_a),
            "duration_seconds": 3600.0,
            "geometry": ROUTE_A_GEOMETRY,
            "steps": [],
        },
        {
            "label": "Route B",
            "route_index": 1,
            "distance_miles": total_route_miles(points_b),
            "duration_seconds": 7200.0,
            "geometry": ROUTE_B_GEOMETRY,
            "steps": [],
        },
    ]


def fake_route_fn(origin, destination, alternatives=3, **kwargs):
    return make_fake_routes()


def make_forecast_fn(wind=30.0, rain=0.0, snow=0.0):
    def forecast_fn(coordinates, start_time, end_time, **kwargs):
        total_seconds = (end_time - start_time).total_seconds()
        hours = max(1, int(total_seconds // 3600) + 1)

        times = [start_time + timedelta(hours=index) for index in range(hours)]

        results = []

        for lat, lng in coordinates:
            results.append(
                {
                    "latitude": float(lat),
                    "longitude": float(lng),
                    "hourly": {
                        "time": times,
                        "wind_speed_mph": [float(wind)] * hours,
                        "wind_gust_mph": [float(wind) + 5.0] * hours,
                        "rain_in_hr": [float(rain)] * hours,
                        "snow_in_hr": [float(snow)] * hours,
                        "temperature_f": [55.0] * hours,
                        "weather_code": [0] * hours,
                    },
                }
            )

        return results

    return forecast_fn


class TripPlanServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="service-test@example.com",
            username="servicetest",
            password="Sup3rSecretPass123",
            name="Service Test Driver",
            country_code="US",
        )

        self.departure = timezone.now() + timedelta(hours=1)

    def test_create_trip_plan_success_persists_and_returns_response(self):
        response = create_trip_plan(
            user=self.user,
            origin="Cincinnati, OH",
            destination="Chicago, IL",
            departure=self.departure,
            load_lb=36000,
            interval_miles=50,
            geocode_fn=fake_geocode,
            route_fn=fake_route_fn,
            forecast_fn=make_forecast_fn(wind=30.0),
            max_heatmap_points=5,
        )

        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["load_lb"], 36000)
        self.assertEqual(response["interval_miles"], 50)
        self.assertEqual(len(response["routes"]), 2)

        plan = TripPlan.objects.get(pk=response["plan_id"])

        self.assertEqual(plan.status, "completed")
        self.assertEqual(plan.route_options.count(), 2)
        self.assertEqual(plan.route_options.filter(is_recommended=True).count(), 1)

        recommended = plan.route_options.get(is_recommended=True)

        # Route A has the shorter duration and equal weather risk,
        # so it should be recommended.
        self.assertEqual(recommended.label, "Route A")

        route_a = next(
            route for route in response["routes"] if route["label"] == "Route A"
        )

        self.assertTrue(route_a["recommended"])
        self.assertGreaterEqual(len(route_a["checkpoints"]), 2)
        self.assertEqual(route_a["checkpoints"][0]["mile_marker"], 0.0)
        self.assertAlmostEqual(
            route_a["checkpoints"][-1]["mile_marker"],
            route_a["distance_miles"],
            places=3,
        )

        # 30 mph wind is Moderate for all checkpoints.
        self.assertAlmostEqual(route_a["average_risk"], 1.0, places=5)
        self.assertAlmostEqual(
            route_a["moderate_miles"],
            route_a["distance_miles"],
            places=3,
        )

        self.assertEqual(len(route_a["heatmap_points"]), 5)
        self.assertEqual(len(route_a["heatmap_points"][0]["hourly_risk"]), 49)
        self.assertEqual(route_a["heatmap_points"][0]["hourly_risk"][0], 1)
        self.assertAlmostEqual(
            route_a["heatmap_points"][0]["hourly_wind"][0],
            30.0,
            places=5,
        )

    def test_load_override_creates_no_travel_risk(self):
        response = create_trip_plan(
            user=self.user,
            origin="Cincinnati, OH",
            destination="Chicago, IL",
            departure=self.departure,
            load_lb=35000,
            interval_miles=50,
            geocode_fn=fake_geocode,
            route_fn=fake_route_fn,
            forecast_fn=make_forecast_fn(wind=50.0),
            max_heatmap_points=2,
        )

        self.assertEqual(response["status"], "completed")

        for route in response["routes"]:
            self.assertTrue(route["has_no_travel"])
            self.assertGreater(route["no_travel_miles"], 0.0)
            self.assertAlmostEqual(route["average_risk"], 4.0, places=5)
            self.assertEqual(route["heatmap_points"][0]["hourly_risk"][0], 4)

    def test_routing_failure_marks_plan_failed(self):
        def failing_route_fn(origin, destination, alternatives=3, **kwargs):
            raise RoutingError("no route found")

        with self.assertRaises(RouteGenerationError):
            create_trip_plan(
                user=self.user,
                origin="Cincinnati, OH",
                destination="Chicago, IL",
                departure=self.departure,
                load_lb=36000,
                interval_miles=50,
                geocode_fn=fake_geocode,
                route_fn=failing_route_fn,
                forecast_fn=make_forecast_fn(),
                max_heatmap_points=2,
            )

        plan = TripPlan.objects.get()

        self.assertEqual(plan.status, "failed")
        self.assertIn("no route found", plan.error_message)
        self.assertEqual(plan.route_options.count(), 0)

    def test_weather_failure_marks_plan_failed(self):
        def failing_forecast_fn(coordinates, start_time, end_time, **kwargs):
            raise WeatherError("rate limited")

        with self.assertRaises(WeatherSamplingError):
            create_trip_plan(
                user=self.user,
                origin="Cincinnati, OH",
                destination="Chicago, IL",
                departure=self.departure,
                load_lb=36000,
                interval_miles=50,
                geocode_fn=fake_geocode,
                route_fn=fake_route_fn,
                forecast_fn=failing_forecast_fn,
                max_heatmap_points=2,
            )

        plan = TripPlan.objects.get()

        self.assertEqual(plan.status, "failed")
        self.assertIn("rate limited", plan.error_message)
        self.assertEqual(plan.route_options.count(), 0)

    def test_geocoding_failure_does_not_create_plan(self):
        with self.assertRaises(PlaceResolutionError):
            create_trip_plan(
                user=self.user,
                origin="Nowhere, ZZ",
                destination="Chicago, IL",
                departure=self.departure,
                load_lb=36000,
                interval_miles=50,
                geocode_fn=fake_geocode,
                route_fn=fake_route_fn,
                forecast_fn=make_forecast_fn(),
                max_heatmap_points=2,
            )

        self.assertEqual(TripPlan.objects.count(), 0)

    def test_invalid_interval_raises_value_error(self):
        with self.assertRaises(ValueError):
            create_trip_plan(
                user=self.user,
                origin="Cincinnati, OH",
                destination="Chicago, IL",
                departure=self.departure,
                load_lb=36000,
                interval_miles=15,
                geocode_fn=fake_geocode,
                route_fn=fake_route_fn,
                forecast_fn=make_forecast_fn(),
                max_heatmap_points=2,
            )

        self.assertEqual(TripPlan.objects.count(), 0)
