from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from plans.models import Checkpoint, RouteOption, TripPlan
from plans.services import (
    PlaceResolutionError,
    PlanServiceError,
    RouteGenerationError,
    WeatherSamplingError,
)


def _future_departure(hours=2):
    return (timezone.now() + timedelta(hours=hours)).isoformat()


VALID_PAYLOAD = {
    "origin": "Cincinnati, OH",
    "destination": "Chicago, IL",
    "departure": _future_departure(),
    "load_lb": 36000,
    "interval_miles": 25,
}


SAMPLE_PLAN_RESPONSE = {
    "plan_id": "00000000-0000-0000-0000-000000000001",
    "status": "completed",
    "error_message": "",
    "origin": {
        "name": "Cincinnati, Ohio, United States",
        "latitude": 39.1031,
        "longitude": -84.5120,
        "timezone": "America/New_York",
    },
    "destination": {
        "name": "Chicago, Illinois, United States",
        "latitude": 41.8781,
        "longitude": -87.6298,
        "timezone": "America/Chicago",
    },
    "departure": "2026-10-21T08:00:00+00:00",
    "load_lb": 36000,
    "interval_miles": 25,
    "recommended_route_id": "00000000-0000-0000-0000-00000000000a",
    "routes": [
        {
            "id": "00000000-0000-0000-0000-00000000000a",
            "label": "Route A",
            "route_index": 0,
            "recommended": True,
            "distance_miles": 265.4,
            "duration_seconds": 15840.0,
            "duration_hours": 4.4,
            "arrival": "2026-10-21T12:24:00+00:00",
            "average_risk": 0.5,
            "low_miles": 200.0,
            "moderate_miles": 65.4,
            "high_miles": 0.0,
            "severe_miles": 0.0,
            "no_travel_miles": 0.0,
            "has_no_travel": False,
            "worst_risk": "MODERATE",
            "recommendation_reasons": [
                "No No-Travel segments",
                "No severe miles",
            ],
            "geometry": {
                "type": "LineString",
                "coordinates": [[-84.512, 39.1031], [-87.6298, 41.8781]],
            },
            "checkpoints": [
                {
                    "id": "00000000-0000-0000-0000-0000000000c1",
                    "mile_marker": 0.0,
                    "lat": 39.1031,
                    "lng": -84.5120,
                    "eta_utc": "2026-10-21T08:00:00+00:00",
                    "wind_mph": 10.0,
                    "wind_gust_mph": None,
                    "rain_in_hr": 0.0,
                    "snow_in_hr": 0.0,
                    "temperature_f": 55.0,
                    "weather_code": 0,
                    "wind_risk": "LOW",
                    "rain_risk": "LOW",
                    "snow_risk": "LOW",
                    "overall_risk": "LOW",
                    "load_override_applied": False,
                }
            ],
            "heatmap_points": [],
        }
    ],
}


class TripPlanApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="api-driver@example.com",
            username="apidriver",
            password="Sup3rSecretPass123",
            name="API Driver",
        )
        self.other_user = User.objects.create_user(
            email="other-driver@example.com",
            username="otherdriver",
            password="Sup3rSecretPass123",
            name="Other Driver",
        )

    def _login(self, user=None):
        self.client.force_login(user or self.user)

    def _create_db_plan(self, user=None, **overrides):
        defaults = {
            "user": user or self.user,
            "origin_name": "Cincinnati, OH",
            "origin_lat": 39.1031,
            "origin_lng": -84.5120,
            "origin_timezone": "America/New_York",
            "destination_name": "Chicago, IL",
            "destination_lat": 41.8781,
            "destination_lng": -87.6298,
            "destination_timezone": "America/Chicago",
            "departure": timezone.now() + timedelta(hours=2),
            "load_lb": 36000,
            "interval_miles": 25,
            "status": TripPlan.STATUS_COMPLETED,
        }
        defaults.update(overrides)
        return TripPlan.objects.create(**defaults)

    # ------------------------------------------------------------------ #
    #  POST /api/plans/ — authentication                                  #
    # ------------------------------------------------------------------ #

    def test_create_plan_requires_authentication(self):
        response = self.client.post(
            "/api/plans/",
            data=VALID_PAYLOAD,
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    # ------------------------------------------------------------------ #
    #  POST /api/plans/ — successful creation                             #
    # ------------------------------------------------------------------ #

    @patch("plans.api.create_trip_plan")
    def test_create_plan_valid_input_returns_201(self, mock_create):
        self._login()
        mock_create.return_value = SAMPLE_PLAN_RESPONSE

        response = self.client.post(
            "/api/plans/",
            data=VALID_PAYLOAD,
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(len(response.data["routes"]), 1)
        self.assertTrue(response.data["routes"][0]["recommended"])

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        self.assertEqual(call_kwargs.kwargs["user"], self.user)
        self.assertEqual(call_kwargs.kwargs["origin"], "Cincinnati, OH")
        self.assertEqual(call_kwargs.kwargs["destination"], "Chicago, IL")
        self.assertEqual(call_kwargs.kwargs["load_lb"], 36000)
        self.assertEqual(call_kwargs.kwargs["interval_miles"], 25)

    # ------------------------------------------------------------------ #
    #  POST /api/plans/ — input validation                                #
    # ------------------------------------------------------------------ #

    def test_create_plan_missing_origin_returns_400(self):
        self._login()
        payload = dict(VALID_PAYLOAD)
        del payload["origin"]

        response = self.client.post(
            "/api/plans/",
            data=payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("origin", response.data)

    def test_create_plan_missing_destination_returns_400(self):
        self._login()
        payload = dict(VALID_PAYLOAD)
        del payload["destination"]

        response = self.client.post(
            "/api/plans/",
            data=payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("destination", response.data)

    def test_create_plan_empty_origin_returns_400(self):
        self._login()
        payload = dict(VALID_PAYLOAD)
        payload["origin"] = "   "

        response = self.client.post(
            "/api/plans/",
            data=payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("origin", response.data)

    def test_create_plan_identical_origin_destination_returns_400(self):
        self._login()
        payload = dict(VALID_PAYLOAD)
        payload["destination"] = "cincinnati, oh"

        response = self.client.post(
            "/api/plans/",
            data=payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("destination", response.data)

    def test_create_plan_invalid_interval_returns_400(self):
        self._login()
        payload = dict(VALID_PAYLOAD)
        payload["interval_miles"] = 30

        response = self.client.post(
            "/api/plans/",
            data=payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("interval_miles", response.data)

    def test_create_plan_negative_load_returns_400(self):
        self._login()
        payload = dict(VALID_PAYLOAD)
        payload["load_lb"] = -100

        response = self.client.post(
            "/api/plans/",
            data=payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("load_lb", response.data)

    def test_create_plan_departure_too_far_ahead_returns_400(self):
        self._login()
        payload = dict(VALID_PAYLOAD)
        payload["departure"] = (
            timezone.now() + timedelta(days=17)
        ).isoformat()

        response = self.client.post(
            "/api/plans/",
            data=payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("departure", response.data)

    def test_create_plan_departure_in_past_returns_400(self):
        self._login()
        payload = dict(VALID_PAYLOAD)
        payload["departure"] = (
            timezone.now() - timedelta(hours=2)
        ).isoformat()

        response = self.client.post(
            "/api/plans/",
            data=payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("departure", response.data)

    # ------------------------------------------------------------------ #
    #  POST /api/plans/ — service error mapping                           #
    # ------------------------------------------------------------------ #

    @patch("plans.api.create_trip_plan")
    def test_create_plan_place_resolution_error_returns_400(self, mock_create):
        self._login()
        mock_create.side_effect = PlaceResolutionError(
            'No location found for "Nowhere, XX".'
        )

        response = self.client.post(
            "/api/plans/",
            data=VALID_PAYLOAD,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("No location found", response.data["detail"])

    @patch("plans.api.create_trip_plan")
    def test_create_plan_routing_error_returns_502(self, mock_create):
        self._login()
        mock_create.side_effect = RouteGenerationError(
            "OSRM could not find a route."
        )

        response = self.client.post(
            "/api/plans/",
            data=VALID_PAYLOAD,
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertIn("OSRM", response.data["detail"])

    @patch("plans.api.create_trip_plan")
    def test_create_plan_weather_error_returns_502(self, mock_create):
        self._login()
        mock_create.side_effect = WeatherSamplingError(
            "Open-Meteo returned HTTP 429."
        )

        response = self.client.post(
            "/api/plans/",
            data=VALID_PAYLOAD,
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertIn("429", response.data["detail"])

    @patch("plans.api.create_trip_plan")
    def test_create_plan_generic_service_error_returns_500(self, mock_create):
        self._login()
        mock_create.side_effect = PlanServiceError("Unexpected failure.")

        response = self.client.post(
            "/api/plans/",
            data=VALID_PAYLOAD,
            format="json",
        )

        self.assertEqual(response.status_code, 500)
        self.assertIn("Unexpected failure", response.data["detail"])

    # ------------------------------------------------------------------ #
    #  GET /api/plans/ — list                                             #
    # ------------------------------------------------------------------ #

    def test_list_plans_requires_authentication(self):
        response = self.client.get("/api/plans/")
        self.assertEqual(response.status_code, 401)

    def test_list_plans_returns_only_caller_plans(self):
        self._login()
        own_plan = self._create_db_plan(user=self.user)
        other_plan = self._create_db_plan(user=self.other_user)

        response = self.client.get("/api/plans/")

        self.assertEqual(response.status_code, 200)
        plan_ids = [item["id"] for item in response.data]
        self.assertIn(str(own_plan.id), plan_ids)
        self.assertNotIn(str(other_plan.id), plan_ids)

    def test_list_plans_empty_for_new_user(self):
        self._login()
        response = self.client.get("/api/plans/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_list_plans_includes_route_count(self):
        self._login()
        plan = self._create_db_plan(user=self.user)
        RouteOption.objects.create(
            plan=plan,
            label="Route A",
            route_index=0,
            is_recommended=True,
        )
        RouteOption.objects.create(
            plan=plan,
            label="Route B",
            route_index=1,
        )

        response = self.client.get("/api/plans/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["route_count"], 2)
        self.assertEqual(response.data[0]["recommended_label"], "Route A")

    # ------------------------------------------------------------------ #
    #  GET /api/plans/{id}/ — detail                                      #
    # ------------------------------------------------------------------ #

    def test_detail_plan_requires_authentication(self):
        plan = self._create_db_plan(user=self.user)
        response = self.client.get(f"/api/plans/{plan.id}/")
        self.assertEqual(response.status_code, 401)

    def test_detail_plan_returns_full_data(self):
        self._login()
        plan = self._create_db_plan(user=self.user)
        route = RouteOption.objects.create(
            plan=plan,
            label="Route A",
            route_index=0,
            distance_miles=265.4,
            duration_seconds=15840.0,
            average_risk_score=0.5,
            is_recommended=True,
            recommendation_reasons=["No No-Travel segments"],
            geometry={
                "type": "LineString",
                "coordinates": [[-84.512, 39.1031], [-87.6298, 41.8781]],
            },
        )
        Checkpoint.objects.create(
            route=route,
            mile_marker=0.0,
            lat=39.1031,
            lng=-84.5120,
            eta_utc=plan.departure,
            wind_mph=10.0,
            rain_in_hr=0.0,
            snow_in_hr=0.0,
            overall_risk="LOW",
        )

        response = self.client.get(f"/api/plans/{plan.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(plan.id))
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(len(response.data["routes"]), 1)
        self.assertEqual(response.data["routes"][0]["label"], "Route A")
        self.assertTrue(response.data["routes"][0]["is_recommended"])
        self.assertEqual(
            len(response.data["routes"][0]["checkpoints"]),
            1,
        )

    def test_detail_plan_other_user_returns_404(self):
        self._login(self.other_user)
        plan = self._create_db_plan(user=self.user)

        response = self.client.get(f"/api/plans/{plan.id}/")

        self.assertEqual(response.status_code, 404)

    def test_detail_plan_nonexistent_returns_404(self):
        self._login()
        fake_id = uuid4()
        response = self.client.get(f"/api/plans/{fake_id}/")
        self.assertEqual(response.status_code, 404)
