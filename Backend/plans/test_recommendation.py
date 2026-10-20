from django.test import SimpleTestCase

from core.constants import RiskLevel
from plans.recommendation import (
    aggregate_route_metrics,
    rank_routes,
    recommend_routes,
)


def make_route(label, **overrides):
    route = {
        "label": label,
        "has_no_travel": False,
        "no_travel_miles": 0.0,
        "severe_miles": 0.0,
        "high_miles": 0.0,
        "average_risk_score": 0.0,
        "duration_seconds": 0.0,
        "distance_miles": 0.0,
    }

    route.update(overrides)

    return route


class RouteRecommendationTests(SimpleTestCase):
    def test_aggregate_basic_segments_use_conservative_max_risk(self):
        checkpoints = [
            {
                "mile": 0,
                "overall_risk": RiskLevel.LOW,
            },
            {
                "mile": 25,
                "overall_risk": RiskLevel.MODERATE,
            },
            {
                "mile": 50,
                "overall_risk": RiskLevel.HIGH,
            },
            {
                "mile": 100,
                "overall_risk": RiskLevel.SEVERE,
            },
        ]

        metrics = aggregate_route_metrics(
            checkpoints=checkpoints,
            distance_miles=100,
            duration_seconds=3600,
        )

        self.assertAlmostEqual(metrics["moderate_miles"], 25.0)
        self.assertAlmostEqual(metrics["high_miles"], 25.0)
        self.assertAlmostEqual(metrics["severe_miles"], 50.0)

        self.assertEqual(metrics["worst_risk"], RiskLevel.SEVERE)
        self.assertFalse(metrics["has_no_travel"])

        # (25 * 1 + 25 * 2 + 50 * 3) / 100 = 2.25
        self.assertAlmostEqual(metrics["average_risk_score"], 2.25)

    def test_aggregate_no_travel_checkpoint_spreads_across_segments(self):
        checkpoints = [
            {
                "mile": 0,
                "overall_risk": RiskLevel.LOW,
            },
            {
                "mile": 50,
                "overall_risk": RiskLevel.NO_TRAVEL,
            },
            {
                "mile": 100,
                "overall_risk": RiskLevel.LOW,
            },
        ]

        metrics = aggregate_route_metrics(
            checkpoints=checkpoints,
            distance_miles=100,
            duration_seconds=0,
        )

        self.assertTrue(metrics["has_no_travel"])
        self.assertAlmostEqual(metrics["no_travel_miles"], 100.0)
        self.assertEqual(metrics["worst_risk"], RiskLevel.NO_TRAVEL)

        # Whole route is treated as No Travel because the middle checkpoint
        # contaminates both adjacent segments conservatively.
        self.assertAlmostEqual(metrics["average_risk_score"], 4.0)

    def test_aggregate_sorts_unsorted_checkpoints_and_deduplicates_close_miles(self):
        checkpoints = [
            {
                "mile": 100,
                "overall_risk": "LOW",
            },
            {
                "mile": 0,
                "overall_risk": "LOW",
            },
            {
                "mile": 50,
                "overall_risk": "MODERATE",
            },
            {
                "mile": 50,
                "overall_risk": "HIGH",
            },
        ]

        metrics = aggregate_route_metrics(
            checkpoints=checkpoints,
            distance_miles=100,
            duration_seconds=0,
        )

        self.assertAlmostEqual(metrics["high_miles"], 100.0)
        self.assertEqual(metrics["worst_risk"], RiskLevel.HIGH)

    def test_aggregate_adds_missing_origin_and_destination_coverage(self):
        checkpoints = [
            {
                "mile": 25,
                "overall_risk": "MODERATE",
            },
            {
                "mile": 75,
                "overall_risk": "HIGH",
            },
        ]

        metrics = aggregate_route_metrics(
            checkpoints=checkpoints,
            distance_miles=100,
            duration_seconds=0,
        )

        # 0-25 uses first checkpoint risk: Moderate.
        # 25-75 uses higher of Moderate/High: High.
        # 75-100 uses last checkpoint risk: High.
        self.assertAlmostEqual(metrics["moderate_miles"], 25.0)
        self.assertAlmostEqual(metrics["high_miles"], 75.0)
        self.assertEqual(metrics["worst_risk"], RiskLevel.HIGH)

    def test_aggregate_empty_checkpoints_treats_route_as_low(self):
        metrics = aggregate_route_metrics(
            checkpoints=[],
            distance_miles=100,
            duration_seconds=3600,
        )

        self.assertAlmostEqual(metrics["low_miles"], 100.0)
        self.assertEqual(metrics["worst_risk"], RiskLevel.LOW)
        self.assertFalse(metrics["has_no_travel"])
        self.assertAlmostEqual(metrics["average_risk_score"], 0.0)

    def test_aggregate_zero_distance_no_travel_checkpoint_marks_has_no_travel(self):
        metrics = aggregate_route_metrics(
            checkpoints=[
                {
                    "mile": 0,
                    "overall_risk": "NO_TRAVEL",
                }
            ],
            distance_miles=0,
            duration_seconds=0,
        )

        self.assertTrue(metrics["has_no_travel"])
        self.assertAlmostEqual(metrics["no_travel_miles"], 0.0)
        self.assertEqual(metrics["worst_risk"], RiskLevel.NO_TRAVEL)

    def test_rank_routes_prefers_safe_route_over_no_travel_route(self):
        unsafe_fast = make_route(
            "unsafe-fast",
            has_no_travel=True,
            no_travel_miles=1.0,
            severe_miles=0.0,
            high_miles=0.0,
            average_risk_score=0.0,
            duration_seconds=1.0,
            distance_miles=1.0,
        )

        safe_slow = make_route(
            "safe-slow",
            has_no_travel=False,
            no_travel_miles=0.0,
            severe_miles=100.0,
            high_miles=0.0,
            average_risk_score=3.0,
            duration_seconds=1000.0,
            distance_miles=100.0,
        )

        ranked = rank_routes([unsafe_fast, safe_slow])

        self.assertEqual(ranked[0]["label"], "safe-slow")
        self.assertEqual(ranked[1]["label"], "unsafe-fast")

    def test_rank_routes_priority_order(self):
        # Severe miles beat high miles, average risk, and time.
        severe_route = make_route(
            "severe",
            severe_miles=10.0,
            high_miles=0.0,
            average_risk_score=0.0,
            duration_seconds=1.0,
        )

        high_route = make_route(
            "high",
            severe_miles=0.0,
            high_miles=100.0,
            average_risk_score=0.0,
            duration_seconds=100.0,
        )

        ranked = rank_routes([severe_route, high_route])
        self.assertEqual(ranked[0]["label"], "high")

        # High miles beat average risk and time.
        high_miles_route = make_route(
            "high-miles",
            severe_miles=0.0,
            high_miles=10.0,
            average_risk_score=0.0,
            duration_seconds=1.0,
        )

        average_route = make_route(
            "average",
            severe_miles=0.0,
            high_miles=0.0,
            average_risk_score=5.0,
            duration_seconds=100.0,
        )

        ranked = rank_routes([high_miles_route, average_route])
        self.assertEqual(ranked[0]["label"], "average")

        # Average risk beats time.
        lower_average_slow = make_route(
            "lower-average-slow",
            average_risk_score=1.0,
            duration_seconds=100.0,
        )

        higher_average_fast = make_route(
            "higher-average-fast",
            average_risk_score=2.0,
            duration_seconds=1.0,
        )

        ranked = rank_routes([lower_average_slow, higher_average_fast])
        self.assertEqual(ranked[0]["label"], "lower-average-slow")

        # Time beats distance when all risk metrics tie.
        slow_short = make_route(
            "slow-short",
            average_risk_score=1.0,
            duration_seconds=100.0,
            distance_miles=10.0,
        )

        fast_long = make_route(
            "fast-long",
            average_risk_score=1.0,
            duration_seconds=50.0,
            distance_miles=20.0,
        )

        ranked = rank_routes([slow_short, fast_long])
        self.assertEqual(ranked[0]["label"], "fast-long")

        # Distance breaks time ties.
        longer = make_route(
            "longer",
            duration_seconds=50.0,
            distance_miles=20.0,
        )

        shorter = make_route(
            "shorter",
            duration_seconds=50.0,
            distance_miles=10.0,
        )

        ranked = rank_routes([longer, shorter])
        self.assertEqual(ranked[0]["label"], "shorter")

        # Label is final deterministic tie-breaker.
        z_label = make_route(
            "z",
            duration_seconds=50.0,
            distance_miles=10.0,
        )

        a_label = make_route(
            "a",
            duration_seconds=50.0,
            distance_miles=10.0,
        )

        ranked = rank_routes([z_label, a_label])
        self.assertEqual(ranked[0]["label"], "a")

    def test_recommend_routes_marks_best_and_adds_reasons(self):
        safer_slower = make_route(
            "Safer",
            severe_miles=0.0,
            high_miles=0.0,
            average_risk_score=0.0,
            duration_seconds=100.0,
        )

        faster_riskier = make_route(
            "Faster",
            severe_miles=10.0,
            high_miles=0.0,
            average_risk_score=1.0,
            duration_seconds=50.0,
        )

        result = recommend_routes([faster_riskier, safer_slower])

        self.assertEqual(result["recommended"]["label"], "Safer")
        self.assertTrue(result["recommended"]["is_recommended"])
        self.assertFalse(result["ranked_routes"][1]["is_recommended"])

        reasons = result["recommended"]["recommendation_reasons"]

        self.assertIn("No No-Travel segments", reasons)
        self.assertIn("No severe miles", reasons)
        self.assertIn("No high-risk miles", reasons)

        self.assertTrue(
            any(
                "Fewer severe miles than Faster" in reason
                for reason in reasons
            )
        )

        self.assertTrue(
            any(
                "Trades" in reason and "extra time" in reason
                for reason in reasons
            )
        )

    def test_recommend_routes_explains_earlier_arrival(self):
        faster = make_route(
            "Faster",
            duration_seconds=10.0,
        )

        slower = make_route(
            "Slower",
            duration_seconds=100.0,
        )

        result = recommend_routes([slower, faster])

        reasons = result["recommended"]["recommendation_reasons"]

        self.assertEqual(result["recommended"]["label"], "Faster")

        self.assertTrue(
            any(
                "Arrives" in reason and "earlier than Slower" in reason
                for reason in reasons
            )
        )

    def test_recommend_routes_handles_empty_routes(self):
        result = recommend_routes([])

        self.assertIsNone(result["recommended"])
        self.assertEqual(result["ranked_routes"], [])
