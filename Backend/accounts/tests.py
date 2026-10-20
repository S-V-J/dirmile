from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.valid_payload = {
            "name": "Test Driver",
            "email": "driver@example.com",
            "username": "driver",
            "password": "Sup3rSecretPass123",
            "confirm_password": "Sup3rSecretPass123",
            "country_code": "US",
            "phone": "+15551234567",
            "otp_enabled": False,
        }

    def register(self, **overrides):
        payload = self.valid_payload.copy()
        payload.update(overrides)
        return self.client.post(
            "/api/auth/register/",
            data=payload,
            format="json",
        )

    def login(self, identifier, password):
        return self.client.post(
            "/api/auth/login/",
            data={
                "identifier": identifier,
                "password": password,
            },
            format="json",
        )

    def test_health_endpoint_still_works(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_csrf_token_endpoint_returns_token(self):
        response = self.client.get("/api/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrf_token", response.json())
        self.assertTrue(response.json()["csrf_token"])

    def test_register_success_and_auto_login(self):
        response = self.register()

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            User.objects.filter(email="driver@example.com").count(),
            1,
        )

        user = User.objects.get(email="driver@example.com")
        self.assertEqual(user.username, "driver")
        self.assertEqual(user.name, "Test Driver")
        self.assertEqual(user.country_code, "US")
        self.assertEqual(user.phone, "+15551234567")
        self.assertFalse(user.otp_enabled)

        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "driver@example.com")
        self.assertEqual(me.json()["username"], "driver")

    def test_register_password_mismatch(self):
        response = self.register(confirm_password="DifferentPass123")

        self.assertEqual(response.status_code, 400)
        self.assertIn("confirm_password", response.json())

    def test_register_duplicate_email_is_case_insensitive(self):
        first = self.register()
        self.assertEqual(first.status_code, 201)

        second = self.register(
            email="DRIVER@example.com",
            username="driver2",
        )

        self.assertEqual(second.status_code, 400)
        self.assertIn("email", second.json())

    def test_register_duplicate_username_is_case_insensitive(self):
        first = self.register()
        self.assertEqual(first.status_code, 201)

        second = self.register(
            email="other@example.com",
            username="DRIVER",
        )

        self.assertEqual(second.status_code, 400)
        self.assertIn("username", second.json())

    def test_login_with_email(self):
        self.register()

        logout_response = self.client.post("/api/auth/logout/")
        self.assertEqual(logout_response.status_code, 204)

        response = self.login(
            "driver@example.com",
            "Sup3rSecretPass123",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["email"], "driver@example.com")

        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)

    def test_login_with_username(self):
        self.register()

        logout_response = self.client.post("/api/auth/logout/")
        self.assertEqual(logout_response.status_code, 204)

        response = self.login(
            "driver",
            "Sup3rSecretPass123",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["username"], "driver")

    def test_login_invalid_credentials(self):
        self.register()

        logout_response = self.client.post("/api/auth/logout/")
        self.assertEqual(logout_response.status_code, 204)

        response = self.login(
            "driver",
            "wrong-password",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid credentials.")

    def test_me_requires_authentication(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_logout_requires_authentication(self):
        response = self.client.post("/api/auth/logout/")
        self.assertEqual(response.status_code, 401)

    def test_account_settings_update(self):
        self.register()

        response = self.client.patch(
            "/api/account/settings/",
            data={
                "preferred_interval_miles": 50,
                "default_load_lb": 36000,
                "theme": "dark",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["preferred_interval_miles"], 50)
        self.assertEqual(response.json()["default_load_lb"], 36000)
        self.assertEqual(response.json()["theme"], "dark")

        user = User.objects.get(email="driver@example.com")
        self.assertEqual(user.preferred_interval_miles, 50)
        self.assertEqual(user.default_load_lb, 36000)
        self.assertEqual(user.theme, "dark")

    def test_account_delete_requires_correct_password_and_confirmation(self):
        self.register()

        wrong_password = self.client.delete(
            "/api/account/",
            data={
                "password": "WrongPass123",
                "confirmation": "DELETE",
            },
            format="json",
        )

        self.assertEqual(wrong_password.status_code, 400)
        self.assertIn("password", wrong_password.json())

        wrong_confirmation = self.client.delete(
            "/api/account/",
            data={
                "password": "Sup3rSecretPass123",
                "confirmation": "delete",
            },
            format="json",
        )

        self.assertEqual(wrong_confirmation.status_code, 400)
        self.assertIn("confirmation", wrong_confirmation.json())

        successful_delete = self.client.delete(
            "/api/account/",
            data={
                "password": "Sup3rSecretPass123",
                "confirmation": "DELETE",
            },
            format="json",
        )

        self.assertEqual(successful_delete.status_code, 204)
        self.assertFalse(
            User.objects.filter(email="driver@example.com").exists()
        )

        me_after_delete = self.client.get("/api/auth/me/")
        self.assertEqual(me_after_delete.status_code, 401)
