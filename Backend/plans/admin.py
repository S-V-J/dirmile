from django.contrib import admin

from plans.models import Checkpoint, HeatmapPoint, RouteOption, TripPlan


@admin.register(TripPlan)
class TripPlanAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "origin_name",
        "destination_name",
        "departure",
        "load_lb",
        "interval_miles",
        "status",
        "created_at",
    ]
    list_filter = ["status", "interval_miles"]
    search_fields = [
        "origin_name",
        "destination_name",
        "user__email",
        "user__username",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(RouteOption)
class RouteOptionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "plan",
        "label",
        "route_index",
        "distance_miles",
        "duration_seconds",
        "average_risk_score",
        "is_recommended",
        "created_at",
    ]
    list_filter = ["is_recommended"]
    search_fields = ["label", "plan__origin_name", "plan__destination_name"]
    readonly_fields = ["id", "created_at"]


@admin.register(Checkpoint)
class CheckpointAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "route",
        "mile_marker",
        "eta_utc",
        "overall_risk",
        "wind_mph",
        "rain_in_hr",
        "snow_in_hr",
        "load_override_applied",
    ]
    list_filter = ["overall_risk", "wind_risk", "rain_risk", "snow_risk"]
    search_fields = ["route__label", "route__plan__origin_name"]
    readonly_fields = ["id", "created_at"]


@admin.register(HeatmapPoint)
class HeatmapPointAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "route",
        "mile_marker",
        "lat",
        "lng",
        "created_at",
    ]
    search_fields = ["route__label", "route__plan__origin_name"]
    readonly_fields = ["id", "created_at"]
