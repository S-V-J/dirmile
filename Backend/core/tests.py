import math

from django.test import TestCase

from core.geo import (
    EARTH_RADIUS_MILES,
    cumulative_distances,
    generate_checkpoints,
    generate_heatmap_points,
    geojson_linestring_to_points,
    haversine_miles,
    interpolate_point,
    points_to_geojson_linestring,
    total_route_miles,
)


class GeoUtilityTests(TestCase):
    def one_degree_miles_at_equator(self):
        return EARTH_RADIUS_MILES * math.pi / 180.0

    def test_haversine_zero_distance(self):
        distance = haversine_miles(39.1031, -84.5120, 39.1031, -84.5120)
        self.assertAlmostEqual(distance, 0.0, places=10)

    def test_haversine_one_degree_longitude_at_equator(self):
        expected = self.one_degree_miles_at_equator()
        actual = haversine_miles(0.0, 0.0, 0.0, 1.0)

        self.assertAlmostEqual(actual, expected, places=6)

    def test_cumulative_distances(self):
        expected_one_degree = self.one_degree_miles_at_equator()

        points = [
            (0.0, 0.0),
            (0.0, 1.0),
            (0.0, 2.0),
        ]

        distances = cumulative_distances(points)

        self.assertEqual(len(distances), 3)
        self.assertAlmostEqual(distances[0], 0.0, places=10)
        self.assertAlmostEqual(distances[1], expected_one_degree, places=6)
        self.assertAlmostEqual(distances[2], expected_one_degree * 2.0, places=6)

    def test_total_route_miles(self):
        expected_one_degree = self.one_degree_miles_at_equator()

        points = [
            (0.0, 0.0),
            (0.0, 1.0),
            (0.0, 2.0),
        ]

        total = total_route_miles(points)

        self.assertAlmostEqual(total, expected_one_degree * 2.0, places=6)

    def test_interpolate_origin_destination_and_midpoint(self):
        points = [
            (0.0, 0.0),
            (0.0, 2.0),
        ]

        total = total_route_miles(points)

        origin = interpolate_point(points, 0.0)
        destination = interpolate_point(points, total)
        midpoint = interpolate_point(points, total / 2.0)

        self.assertAlmostEqual(origin["lat"], 0.0, places=10)
        self.assertAlmostEqual(origin["lng"], 0.0, places=10)
        self.assertAlmostEqual(origin["mile"], 0.0, places=10)

        self.assertAlmostEqual(destination["lat"], 0.0, places=10)
        self.assertAlmostEqual(destination["lng"], 2.0, places=10)
        self.assertAlmostEqual(destination["mile"], total, places=6)

        self.assertAlmostEqual(midpoint["lat"], 0.0, places=10)
        self.assertAlmostEqual(midpoint["lng"], 1.0, places=5)
        self.assertAlmostEqual(midpoint["mile"], total / 2.0, places=6)

    def test_interpolate_handles_duplicate_points(self):
        points = [
            (0.0, 0.0),
            (0.0, 0.0),
            (0.0, 1.0),
        ]

        total = total_route_miles(points)
        midpoint = interpolate_point(points, total / 2.0)

        self.assertAlmostEqual(midpoint["lat"], 0.0, places=10)
        self.assertAlmostEqual(midpoint["lng"], 0.5, places=5)
        self.assertAlmostEqual(midpoint["mile"], total / 2.0, places=6)

    def test_geojson_linestring_to_points(self):
        geometry = {
            "type": "LineString",
            "coordinates": [
                [-84.5120, 39.1031],
                [-87.6298, 41.8781],
            ],
        }

        points = geojson_linestring_to_points(geometry)

        self.assertEqual(
            points,
            [
                (39.1031, -84.5120),
                (41.8781, -87.6298),
            ],
        )

    def test_points_to_geojson_linestring_roundtrip(self):
        original_geometry = {
            "type": "LineString",
            "coordinates": [
                [-84.5120, 39.1031],
                [-87.6298, 41.8781],
            ],
        }

        points = geojson_linestring_to_points(original_geometry)
        converted_geometry = points_to_geojson_linestring(points)

        self.assertEqual(converted_geometry, original_geometry)

    def test_generate_checkpoints_for_100_mile_route(self):
        one_degree_miles = self.one_degree_miles_at_equator()
        degrees_for_100_miles = 100.0 / one_degree_miles

        points = [
            (0.0, 0.0),
            (0.0, degrees_for_100_miles),
        ]

        checkpoints = generate_checkpoints(points, interval_miles=25)

        self.assertEqual(len(checkpoints), 5)

        mile_markers = [checkpoint["mile"] for checkpoint in checkpoints]

        self.assertAlmostEqual(mile_markers[0], 0.0, places=6)
        self.assertAlmostEqual(mile_markers[1], 25.0, places=5)
        self.assertAlmostEqual(mile_markers[2], 50.0, places=5)
        self.assertAlmostEqual(mile_markers[3], 75.0, places=5)
        self.assertAlmostEqual(mile_markers[4], 100.0, places=5)

    def test_generate_checkpoints_short_route_includes_origin_and_destination(self):
        one_degree_miles = self.one_degree_miles_at_equator()
        degrees_for_10_miles = 10.0 / one_degree_miles

        points = [
            (0.0, 0.0),
            (0.0, degrees_for_10_miles),
        ]

        checkpoints = generate_checkpoints(points, interval_miles=25)

        self.assertEqual(len(checkpoints), 2)

        mile_markers = [checkpoint["mile"] for checkpoint in checkpoints]

        self.assertAlmostEqual(mile_markers[0], 0.0, places=6)
        self.assertAlmostEqual(mile_markers[1], 10.0, places=5)

    def test_generate_heatmap_points_count_and_endpoints(self):
        one_degree_miles = self.one_degree_miles_at_equator()
        degrees_for_100_miles = 100.0 / one_degree_miles

        points = [
            (0.0, 0.0),
            (0.0, degrees_for_100_miles),
        ]

        heatmap_points = generate_heatmap_points(points, max_points=10)

        self.assertEqual(len(heatmap_points), 10)

        self.assertAlmostEqual(heatmap_points[0]["mile"], 0.0, places=6)
        self.assertAlmostEqual(heatmap_points[-1]["mile"], 100.0, places=5)

        # With 10 points, indices are 0 through 9.
        # Index 3 should be 3 / 9 of the route.
        expected_third_mile = 100.0 * (3.0 / 9.0)
        self.assertAlmostEqual(heatmap_points[3]["mile"], expected_third_mile, places=5)
