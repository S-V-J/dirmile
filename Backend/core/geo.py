import math
from typing import Sequence

EARTH_RADIUS_MILES = 3958.7613

# Internal coordinate format:
# (latitude, longitude)
Coordinate = tuple[float, float]


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Return great-circle distance in miles between two coordinates.
    """
    lat1_rad = math.radians(float(lat1))
    lng1_rad = math.radians(float(lng1))
    lat2_rad = math.radians(float(lat2))
    lng2_rad = math.radians(float(lng2))

    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad

    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return EARTH_RADIUS_MILES * c


def cumulative_distances(points: Sequence[Coordinate]) -> list[float]:
    """
    Return cumulative route distance in miles for each point.

    Example:
        points = [(lat0, lng0), (lat1, lng1), (lat2, lng2)]

    Returns:
        [0.0, distance(point0 -> point1), distance(point0 -> point2)]
    """
    if not points:
        return []

    distances = [0.0]
    total = 0.0

    for i in range(1, len(points)):
        prev_lat, prev_lng = points[i - 1]
        curr_lat, curr_lng = points[i]

        total += haversine_miles(prev_lat, prev_lng, curr_lat, curr_lng)
        distances.append(total)

    return distances


def total_route_miles(points: Sequence[Coordinate]) -> float:
    """
    Return total route distance in miles.
    """
    distances = cumulative_distances(points)

    if not distances:
        return 0.0

    return distances[-1]


def interpolate_point(points: Sequence[Coordinate], target_mile: float) -> dict:
    """
    Return the coordinate at a specific mile marker along the route.

    Returns:
        {
            "lat": float,
            "lng": float,
            "mile": float,
        }
    """
    if not points:
        raise ValueError("Cannot interpolate an empty route.")

    if len(points) == 1:
        lat, lng = points[0]
        return {
            "lat": lat,
            "lng": lng,
            "mile": 0.0,
        }

    distances = cumulative_distances(points)
    total = distances[-1]
    target = float(target_mile)

    if target <= 0.0:
        lat, lng = points[0]
        return {
            "lat": lat,
            "lng": lng,
            "mile": 0.0,
        }

    if total <= 1e-9 or target >= total:
        lat, lng = points[-1]
        return {
            "lat": lat,
            "lng": lng,
            "mile": total,
        }

    for i in range(1, len(points)):
        start_mile = distances[i - 1]
        end_mile = distances[i]

        if target <= end_mile + 1e-9:
            segment_length = end_mile - start_mile

            if segment_length <= 1e-9:
                continue

            fraction = (target - start_mile) / segment_length

            lat1, lng1 = points[i - 1]
            lat2, lng2 = points[i]

            lat = lat1 + (lat2 - lat1) * fraction
            lng = lng1 + (lng2 - lng1) * fraction

            return {
                "lat": lat,
                "lng": lng,
                "mile": target,
            }

    lat, lng = points[-1]
    return {
        "lat": lat,
        "lng": lng,
        "mile": total,
    }


def generate_checkpoints(
    points: Sequence[Coordinate],
    interval_miles: int | float,
) -> list[dict]:
    """
    Generate route checkpoints at the requested mile interval.

    Always includes:
        - origin at mile 0
        - destination at total route miles

    Example:
        100-mile route with interval 25:
        [0, 25, 50, 75, 100]
    """
    if not points:
        return []

    interval = float(interval_miles)

    if interval <= 0:
        raise ValueError("interval_miles must be greater than zero.")

    total = total_route_miles(points)

    if total <= 1e-9:
        point = interpolate_point(points, 0.0)
        return [
            {
                "mile": 0.0,
                "lat": point["lat"],
                "lng": point["lng"],
            }
        ]

    mile_markers = [0.0]

    mile = interval
    while mile < total - 1e-9:
        mile_markers.append(mile)
        mile += interval

    mile_markers.append(total)

    unique_mile_markers = []
    for marker in sorted(mile_markers):
        if not unique_mile_markers or abs(marker - unique_mile_markers[-1]) > 1e-6:
            unique_mile_markers.append(marker)

    checkpoints = []

    for marker in unique_mile_markers:
        point = interpolate_point(points, marker)

        checkpoints.append(
            {
                "mile": marker,
                "lat": point["lat"],
                "lng": point["lng"],
            }
        )

    return checkpoints


def generate_heatmap_points(
    points: Sequence[Coordinate],
    max_points: int = 500,
) -> list[dict]:
    """
    Generate dense corridor points for the weather heatmap.

    The frontend slider should use these points with hourly weather arrays.
    """
    if not points:
        return []

    total = total_route_miles(points)

    if total <= 1e-9:
        point = interpolate_point(points, 0.0)
        return [
            {
                "mile": 0.0,
                "lat": point["lat"],
                "lng": point["lng"],
            }
        ]

    max_points = int(max_points)

    if max_points <= 1:
        point = interpolate_point(points, 0.0)
        return [
            {
                "mile": 0.0,
                "lat": point["lat"],
                "lng": point["lng"],
            }
        ]

    heatmap_points = []

    for i in range(max_points):
        target_mile = total * (i / float(max_points - 1))
        point = interpolate_point(points, target_mile)

        heatmap_points.append(
            {
                "mile": target_mile,
                "lat": point["lat"],
                "lng": point["lng"],
            }
        )

    return heatmap_points


def geojson_linestring_to_points(geometry: dict) -> list[Coordinate]:
    """
    Convert a GeoJSON LineString to Dirmile internal points.

    GeoJSON coordinates:
        [longitude, latitude]

    Dirmile coordinates:
        (latitude, longitude)
    """
    if not isinstance(geometry, dict):
        raise ValueError("Geometry must be a dictionary.")

    if geometry.get("type") != "LineString":
        raise ValueError("Only GeoJSON LineString geometry is supported.")

    coordinates = geometry.get("coordinates")

    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise ValueError("GeoJSON LineString must contain at least two coordinates.")

    points: list[Coordinate] = []

    for coordinate in coordinates:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
            raise ValueError("Each GeoJSON coordinate must contain [longitude, latitude].")

        lng = float(coordinate[0])
        lat = float(coordinate[1])

        points.append((lat, lng))

    return points


def points_to_geojson_linestring(points: Sequence[Coordinate]) -> dict:
    """
    Convert Dirmile internal points to GeoJSON LineString.

    Dirmile coordinates:
        (latitude, longitude)

    GeoJSON coordinates:
        [longitude, latitude]
    """
    return {
        "type": "LineString",
        "coordinates": [
            [float(lng), float(lat)]
            for lat, lng in points
        ],
    }
