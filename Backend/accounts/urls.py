from django.urls import path

from accounts import views

urlpatterns = [
    path("auth/csrf/", views.csrf_token_view, name="csrf-token"),
    path("auth/register/", views.register_view, name="register"),
    path("auth/login/", views.login_view, name="login"),
    path("auth/logout/", views.logout_view, name="logout"),
    path("auth/me/", views.me_view, name="me"),
    path(
        "account/settings/",
        views.account_settings_view,
        name="account-settings",
    ),
    path("account/", views.account_delete_view, name="account-delete"),
]
