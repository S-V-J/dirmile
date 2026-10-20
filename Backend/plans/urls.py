from django.urls import path

from plans.api import TripPlanCreateListView, TripPlanDetailView

urlpatterns = [
    path(
        "plans/",
        TripPlanCreateListView.as_view(),
        name="plan-create-list",
    ),
    path(
        "plans/<uuid:pk>/",
        TripPlanDetailView.as_view(),
        name="plan-detail",
    ),
]
