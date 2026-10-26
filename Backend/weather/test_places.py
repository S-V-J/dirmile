from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User

FAKE_PLACES = [
    {
        "id": 4508722,
        "name": "Cincinnati",
        "display_name": "Cincinnati, Ohio, Hamilton, United States",
        "latitude": 39.12711,
        "longitude": -84.51439,
        "country_code": "US",
        "country": "United States",
        "admin1": "Ohio",
        "admin2": "Hamilton",
        "timezone": "America/New_York",
        "elevation": 150.0,
        "feature_code": "PPL",
        "population": 300000,
    }
]


class PlacesSearchApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="places@example.com",
            username="placesuser",
            password="Sup3rSecretPass123",
            name="Places User",
        )

    def test_unauthenticated_returns_401(self):
        response = self.client.get("/api/places/", {"q": "Cin"})
        self.assertEqual(response.status_code, 401)

    def test_short_query_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.get("/api/places/", {"q": "C"})
        self.assertEqual(response.status_code, 400)

    @patch("weather.views.search_places")
    def test_success_returns_slim_places(self, mock_search):
        mock_search.return_value = FAKE_PLACES
        self.client.force_login(self.user)
        response = self.client.get("/api/places/", {"q": "Cincinnati"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["display_name"],
            "Cincinnati, Ohio, Hamilton, United States",
        )
        self.assertNotIn("elevation", response.data[0])
        self.assertNotIn("population", response.data[0])
        mock_search.assert_called_once()
        self.assertEqual(mock_search.call_args.args[0], "Cincinnati")

    @patch("weather.views.search_places")
    def test_upstream_failure_returns_502(self, mock_search):
        from weather.geocoding import GeocodingAPIError

        mock_search.side_effect = GeocodingAPIError("boom", status_code=500)
        self.client.force_login(self.user)
        response = self.client.get("/api/places/", {"q": "Nowhere"})
        self.assertEqual(response.status_code, 502)
