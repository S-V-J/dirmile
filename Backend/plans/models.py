import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models

from core.constants import RiskLevel


class TripPlan(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    INTERVAL_CHOICES = [
        (10, "10 miles"),
        (25, "25 miles"),
        (50, "50 miles"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trip_plans",
    )

    origin_name = models.CharField(max_length=255)
    origin_lat = models.FloatField()
    origin_lng = models.FloatField()
    origin_timezone = models.CharField(max_length=100, blank=True, default="")

    destination_name = models.CharField(max_length=255)
    destination_lat = models.FloatField()
    destination_lng = models.FloatField()
    destination_timezone = models.CharField(max_length=100, blank=True, default="")

    departure = models.DateTimeField()
    load_lb = models.PositiveIntegerField()
    interval_miles = models.PositiveSmallIntegerField(
        choices=INTERVAL_CHOICES,
        default=25,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.origin_name} -> {self.destination_name}"


class RouteOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    plan = models.ForeignKey(
        TripPlan,
        on_delete=models.CASCADE,
        related_name="route_options",
    )

    label = models.CharField(max_length=100)
    route_index = models.PositiveSmallIntegerField(default=0)

    distance_miles = models.FloatField(default=0)
    duration_seconds = models.FloatField(default=0)

    geometry = models.JSONField(default=dict, blank=True)

    average_risk_score = models.FloatField(default=0)

    low_miles = models.FloatField(default=0)
    moderate_miles = models.FloatField(default=0)
    high_miles = models.FloatField(default=0)
    severe_miles = models.FloatField(default=0)
    no_travel_miles = models.FloatField(default=0)

    is_recommended = models.BooleanField(default=False)
    recommendation_reasons = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["route_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "route_index"],
                name="unique_route_index_per_plan",
            ),
        ]
        indexes = [
            models.Index(fields=["plan"]),
            models.Index(fields=["is_recommended"]),
        ]

    def __str__(self):
        return f"{self.plan_id} - {self.label}"

    @property
    def arrival_datetime(self):
        """
        Estimated arrival time based on plan departure and route duration.
        """
        return self.plan.departure + timedelta(seconds=self.duration_seconds)


class Checkpoint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    route = models.ForeignKey(
        RouteOption,
        on_delete=models.CASCADE,
        related_name="checkpoints",
    )

    mile_marker = models.FloatField()
    lat = models.FloatField()
    lng = models.FloatField()
    eta_utc = models.DateTimeField()

    wind_mph = models.FloatField(default=0)
    wind_gust_mph = models.FloatField(null=True, blank=True)

    rain_in_hr = models.FloatField(default=0)
    snow_in_hr = models.FloatField(default=0)

    temperature_f = models.FloatField(null=True, blank=True)
    weather_code = models.PositiveSmallIntegerField(null=True, blank=True)

    wind_risk = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
    )
    rain_risk = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
    )
    snow_risk = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
    )
    overall_risk = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
    )

    load_override_applied = models.BooleanField(default=False)
    raw_weather = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["route", "mile_marker"]
        indexes = [
            models.Index(fields=["route", "mile_marker"]),
            models.Index(fields=["eta_utc"]),
            models.Index(fields=["overall_risk"]),
        ]

    def __str__(self):
        return f"{self.route_id} @ mile {self.mile_marker}"


class HeatmapPoint(models.Model):
    """
    Dense corridor point used for the 0-48 hour weather heatmap.

    The arrays are expected to contain hourly values.
    For MVP, frontend slider uses 0-48 hours from departure.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    route = models.ForeignKey(
        RouteOption,
        on_delete=models.CASCADE,
        related_name="heatmap_points",
    )

    mile_marker = models.FloatField()
    lat = models.FloatField()
    lng = models.FloatField()

    hourly_risk = models.JSONField(default=list, blank=True)
    hourly_wind = models.JSONField(default=list, blank=True)
    hourly_rain = models.JSONField(default=list, blank=True)
    hourly_snow = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["route", "mile_marker"]
        indexes = [
            models.Index(fields=["route", "mile_marker"]),
        ]

    def __str__(self):
        return f"Heatmap {self.route_id} @ mile {self.mile_marker}"
