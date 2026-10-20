from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from plans.models import Checkpoint, RouteOption, TripPlan

MAX_DEPARTURE_DAYS_AHEAD = 16
LOAD_WARN_THRESHOLD_LB = 80000
LOAD_ABSOLUTE_MAX_LB = 500000


class TripPlanCreateSerializer(serializers.Serializer):
    """
    Validates incoming trip plan request data.
    This serializer is write-only; it does not map to a model.
    """

    origin = serializers.CharField(max_length=255)
    destination = serializers.CharField(max_length=255)
    departure = serializers.DateTimeField()
    load_lb = serializers.IntegerField(min_value=0, max_value=LOAD_ABSOLUTE_MAX_LB)
    interval_miles = serializers.ChoiceField(choices=[10, 25, 50])

    def validate_origin(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Origin cannot be empty.")
        return value

    def validate_destination(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Destination cannot be empty.")
        return value

    def validate_departure(self, value):
        now = timezone.now()
        if value < now - timedelta(minutes=5):
            raise serializers.ValidationError(
                "Departure cannot be more than 5 minutes in the past."
            )
        max_future = now + timedelta(days=MAX_DEPARTURE_DAYS_AHEAD)
        if value > max_future:
            raise serializers.ValidationError(
                f"Departure cannot be more than {MAX_DEPARTURE_DAYS_AHEAD} "
                "days ahead."
            )
        return value

    def validate(self, attrs):
        origin = attrs.get("origin", "").strip().lower()
        destination = attrs.get("destination", "").strip().lower()
        if origin and destination and origin == destination:
            raise serializers.ValidationError(
                {
                    "destination": [
                        "Origin and destination cannot be identical."
                    ]
                }
            )
        return attrs


class CheckpointSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for checkpoint data inside a route.
    """

    class Meta:
        model = Checkpoint
        fields = [
            "id",
            "mile_marker",
            "lat",
            "lng",
            "eta_utc",
            "wind_mph",
            "wind_gust_mph",
            "rain_in_hr",
            "snow_in_hr",
            "temperature_f",
            "weather_code",
            "wind_risk",
            "rain_risk",
            "snow_risk",
            "overall_risk",
            "load_override_applied",
        ]
        read_only_fields = fields


class RouteOptionSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for a single route option including checkpoints.
    """

    checkpoints = CheckpointSerializer(many=True, read_only=True)

    class Meta:
        model = RouteOption
        fields = [
            "id",
            "label",
            "route_index",
            "distance_miles",
            "duration_seconds",
            "average_risk_score",
            "low_miles",
            "moderate_miles",
            "high_miles",
            "severe_miles",
            "no_travel_miles",
            "is_recommended",
            "recommendation_reasons",
            "geometry",
            "checkpoints",
        ]
        read_only_fields = fields


class TripPlanDetailSerializer(serializers.ModelSerializer):
    """
    Full plan response including all routes and their checkpoints.
    Used for GET /api/plans/{id}/.
    """

    routes = RouteOptionSerializer(
        source="route_options",
        many=True,
        read_only=True,
    )

    class Meta:
        model = TripPlan
        fields = [
            "id",
            "status",
            "error_message",
            "origin_name",
            "origin_lat",
            "origin_lng",
            "origin_timezone",
            "destination_name",
            "destination_lat",
            "destination_lng",
            "destination_timezone",
            "departure",
            "load_lb",
            "interval_miles",
            "created_at",
            "updated_at",
            "routes",
        ]
        read_only_fields = fields


class TripPlanListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the plan list endpoint.
    Does not include routes or checkpoints.
    """

    route_count = serializers.SerializerMethodField()
    recommended_label = serializers.SerializerMethodField()

    class Meta:
        model = TripPlan
        fields = [
            "id",
            "status",
            "origin_name",
            "destination_name",
            "departure",
            "load_lb",
            "interval_miles",
            "route_count",
            "recommended_label",
            "created_at",
        ]
        read_only_fields = fields

    def get_route_count(self, obj):
        return obj.route_options.count()

    def get_recommended_label(self, obj):
        recommended = obj.route_options.filter(is_recommended=True).first()
        return recommended.label if recommended else None
