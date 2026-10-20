from rest_framework import generics, status, views
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from plans.models import TripPlan
from plans.serializers import (
    TripPlanCreateSerializer,
    TripPlanDetailSerializer,
    TripPlanListSerializer,
)
from plans.services import (
    PlaceResolutionError,
    PlanServiceError,
    RouteGenerationError,
    WeatherSamplingError,
    create_trip_plan,
)

UNAUTHENTICATED_DETAIL = "Authentication credentials were not provided."


def _unauthenticated_response():
    """
    Return an explicit 401 JSON response.
    This avoids DRF's permission-denied path which can produce 403
    depending on how SessionAuthentication handles AnonymousUser.
    """
    return Response(
        {"detail": UNAUTHENTICATED_DETAIL},
        status=status.HTTP_401_UNAUTHORIZED,
    )


def _is_authenticated(request):
    """
    Return True only when the request carries an active authenticated user.
    """
    user = getattr(request, "user", None)
    if user is None:
        return False
    is_authenticated = getattr(user, "is_authenticated", False)
    is_active = getattr(user, "is_active", True)
    return bool(is_authenticated and is_active)


class TripPlanCreateListView(views.APIView):
    """
    POST   /api/plans/   — create and process a new trip plan
    GET    /api/plans/   — list the authenticated user's plans
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        if not _is_authenticated(request):
            return _unauthenticated_response()

        serializer = TripPlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = create_trip_plan(
                user=request.user,
                origin=serializer.validated_data["origin"],
                destination=serializer.validated_data["destination"],
                departure=serializer.validated_data["departure"],
                load_lb=serializer.validated_data["load_lb"],
                interval_miles=serializer.validated_data["interval_miles"],
            )
        except PlaceResolutionError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (RouteGenerationError, WeatherSamplingError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except PlanServiceError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result, status=status.HTTP_201_CREATED)

    def get(self, request, *args, **kwargs):
        if not _is_authenticated(request):
            return _unauthenticated_response()

        plans = TripPlan.objects.filter(user=request.user)
        serializer = TripPlanListSerializer(plans, many=True)
        return Response(serializer.data)


class TripPlanDetailView(generics.RetrieveAPIView):
    """
    GET /api/plans/{id}/  — retrieve one stored plan.
    Only the owning user can see the plan.
    Other users receive 404 (not 403) to avoid leaking existence.
    """

    permission_classes = [AllowAny]
    serializer_class = TripPlanDetailSerializer
    lookup_field = "pk"

    def get_queryset(self):
        if not _is_authenticated(self.request):
            return TripPlan.objects.none()
        return TripPlan.objects.filter(user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        if not _is_authenticated(request):
            return _unauthenticated_response()
        return super().retrieve(request, *args, **kwargs)
