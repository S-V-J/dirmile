from datetime import timedelta
from uuid import UUID

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from core.constants import RiskLevel
from plans.models import Checkpoint, HeatmapPoint, RouteOption, TripPlan


class TripPlanModelsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="plans-test@example.com",
            username="planstest",
            password="Sup3rSecretPass123",
            name="Plans Test Driver",
        )

        self.departure = timezone.now() + timedelta(hours=2)

        self.plan = TripPlan.objects.create(
            user=self.user,
            origin_name="Cincinnati, OH",
            origin_lat=39.1031,
            origin_lng=-84.5120,
            origin_timezone="America/New_York",
            destination_name="Chicago, IL",
            destination_lat=41.8781,
            destination_lng=-87.6298,
            destination_timezone="America/Chicago",
            departure=self.departure,
            load_lb=36000,
            interval_miles=25,
        )

    def test_trip_plan_creation(self):
        self.assertIsInstance(self.plan.id, UUID)
        self.assertEqual(self.plan.user, self.user)
        self.assertEqual(self.plan.status, TripPlan.STATUS_PENDING)
        self.assertEqual(self.plan.interval_miles, 25)
        self.assertEqual(self.plan.load_lb, 36000)
        self.assertEqual(
            str(self.plan),
            "Cincinnati, OH -> Chicago, IL",
        )

    def test_route_option_arrival_property(self):
        route = RouteOption.objects.create(
            plan=self.plan,
            label="Route A",
            route_index=0,
            distance_miles=265.4,
            duration_seconds=3600 * 4 + 1800,
            geometry={
                "type": "LineString",
                "coordinates": [
                    [-84.5120, 39.1031],
                    [-87.6298, 41.8781],
                ],
            },
        )

        expected_arrival = self.departure + timedelta(hours=4, minutes=30)

        self.assertEqual(route.arrival_datetime, expected_arrival)
        self.assertFalse(route.is_recommended)
        self.assertEqual(route.recommendation_reasons, [])
        self.assertEqual(route.geometry["type"], "LineString")

    def test_unique_route_index_per_plan(self):
        RouteOption.objects.create(
            plan=self.plan,
            label="Route A",
            route_index=0,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RouteOption.objects.create(
                    plan=self.plan,
                    label="Duplicate Route",
                    route_index=0,
                )

    def test_checkpoint_defaults_and_ordering(self):
        route = RouteOption.objects.create(
            plan=self.plan,
            label="Route A",
            route_index=0,
        )

        first = Checkpoint.objects.create(
            route=route,
            mile_marker=0,
            lat=39.1031,
            lng=-84.5120,
            eta_utc=self.departure,
        )

        second = Checkpoint.objects.create(
            route=route,
            mile_marker=25,
            lat=39.4,
            lng=-85.0,
            eta_utc=self.departure + timedelta(hours=1),
            wind_mph=30,
            rain_in_hr=0.15,
            snow_in_hr=0.2,
            wind_risk=RiskLevel.MODERATE,
            rain_risk=RiskLevel.MODERATE,
            snow_risk=RiskLevel.LOW,
            overall_risk=RiskLevel.MODERATE,
        )

        checkpoints = list(route.checkpoints.all())

        self.assertEqual(checkpoints[0].id, first.id)
        self.assertEqual(checkpoints[1].id, second.id)

        self.assertEqual(first.overall_risk, RiskLevel.LOW)
        self.assertEqual(first.wind_mph, 0)
        self.assertEqual(first.rain_in_hr, 0)
        self.assertEqual(first.snow_in_hr, 0)
        self.assertFalse(first.load_override_applied)

        self.assertEqual(second.overall_risk, RiskLevel.MODERATE)
        self.assertEqual(second.wind_risk, RiskLevel.MODERATE)
        self.assertEqual(second.rain_risk, RiskLevel.MODERATE)
        self.assertEqual(second.snow_risk, RiskLevel.LOW)

    def test_heatmap_point_array_defaults(self):
        route = RouteOption.objects.create(
            plan=self.plan,
            label="Route A",
            route_index=0,
        )

        heatmap_point = HeatmapPoint.objects.create(
            route=route,
            mile_marker=10,
            lat=39.2,
            lng=-84.7,
        )

        self.assertEqual(heatmap_point.hourly_risk, [])
        self.assertEqual(heatmap_point.hourly_wind, [])
        self.assertEqual(heatmap_point.hourly_rain, [])
        self.assertEqual(heatmap_point.hourly_snow, [])

        heatmap_point.hourly_risk = [0, 1, 2, 3, 4]
        heatmap_point.hourly_wind = [10.5, 20.1, 30.2, 40.3, 50.4]
        heatmap_point.hourly_rain = [0.0, 0.1, 0.2, 0.5, 1.1]
        heatmap_point.hourly_snow = [0.0, 0.2, 0.7, 1.5, 3.2]
        heatmap_point.save()

        heatmap_point.refresh_from_db()

        self.assertEqual(heatmap_point.hourly_risk, [0, 1, 2, 3, 4])
        self.assertEqual(heatmap_point.hourly_wind[0], 10.5)
        self.assertEqual(heatmap_point.hourly_rain[4], 1.1)
        self.assertEqual(heatmap_point.hourly_snow[4], 3.2)
