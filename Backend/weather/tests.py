from django.test import TestCase

from core.constants import RiskLevel
from weather.risk import (
    classify_checkpoint,
    classify_rain,
    classify_snow,
    classify_wind,
)


class WeatherRiskEngineTests(TestCase):
    def test_wind_boundaries_without_load_override(self):
        risk, override = classify_wind(24.9, 0)
        self.assertEqual(risk, RiskLevel.LOW)
        self.assertFalse(override)

        risk, override = classify_wind(25, 0)
        self.assertEqual(risk, RiskLevel.MODERATE)
        self.assertFalse(override)

        risk, override = classify_wind(34.9, 0)
        self.assertEqual(risk, RiskLevel.MODERATE)
        self.assertFalse(override)

        risk, override = classify_wind(35, 0)
        self.assertEqual(risk, RiskLevel.HIGH)
        self.assertFalse(override)

        risk, override = classify_wind(44.9, 0)
        self.assertEqual(risk, RiskLevel.HIGH)
        self.assertFalse(override)

        risk, override = classify_wind(45, 0)
        self.assertEqual(risk, RiskLevel.SEVERE)
        self.assertFalse(override)

        risk, override = classify_wind(54.9, 0)
        self.assertEqual(risk, RiskLevel.SEVERE)
        self.assertFalse(override)

        risk, override = classify_wind(55, 0)
        self.assertEqual(risk, RiskLevel.NO_TRAVEL)
        self.assertTrue(override)

    def test_wind_load_override_45_to_54_mph(self):
        # 45-54 mph + >30,000 lb -> No Travel
        risk, override = classify_wind(50, 30001)
        self.assertEqual(risk, RiskLevel.NO_TRAVEL)
        self.assertTrue(override)

        # 45-54 mph + exactly 30,000 lb -> Severe
        risk, override = classify_wind(50, 30000)
        self.assertEqual(risk, RiskLevel.SEVERE)
        self.assertFalse(override)

        # 45-54 mph + <30,000 lb -> Severe
        risk, override = classify_wind(45, 29999)
        self.assertEqual(risk, RiskLevel.SEVERE)
        self.assertFalse(override)

    def test_wind_load_override_35_to_44_mph(self):
        # 35-44 mph + >40,000 lb -> Severe
        risk, override = classify_wind(40, 40001)
        self.assertEqual(risk, RiskLevel.SEVERE)
        self.assertTrue(override)

        # 35-44 mph + exactly 40,000 lb -> High
        risk, override = classify_wind(40, 40000)
        self.assertEqual(risk, RiskLevel.HIGH)
        self.assertFalse(override)

        # 35-44 mph + <40,000 lb -> High
        risk, override = classify_wind(35, 39999)
        self.assertEqual(risk, RiskLevel.HIGH)
        self.assertFalse(override)

    def test_wind_no_travel_for_any_load_at_55_mph_or_more(self):
        for load in (0, 10000, 30000, 30001, 40000, 40001, 80000):
            risk, override = classify_wind(55, load)
            self.assertEqual(risk, RiskLevel.NO_TRAVEL)
            self.assertTrue(override)

            risk, override = classify_wind(70, load)
            self.assertEqual(risk, RiskLevel.NO_TRAVEL)
            self.assertTrue(override)

    def test_rain_boundaries(self):
        self.assertEqual(classify_rain(0.09), RiskLevel.LOW)
        self.assertEqual(classify_rain(0.10), RiskLevel.MODERATE)
        self.assertEqual(classify_rain(0.249999), RiskLevel.MODERATE)
        self.assertEqual(classify_rain(0.25), RiskLevel.HIGH)
        self.assertEqual(classify_rain(0.499999), RiskLevel.HIGH)
        self.assertEqual(classify_rain(0.50), RiskLevel.SEVERE)
        self.assertEqual(classify_rain(1.00), RiskLevel.SEVERE)
        self.assertEqual(classify_rain(1.01), RiskLevel.NO_TRAVEL)

    def test_snow_boundaries(self):
        self.assertEqual(classify_snow(0.49), RiskLevel.LOW)
        self.assertEqual(classify_snow(0.50), RiskLevel.MODERATE)
        self.assertEqual(classify_snow(0.999999), RiskLevel.MODERATE)
        self.assertEqual(classify_snow(1.00), RiskLevel.HIGH)
        self.assertEqual(classify_snow(1.999999), RiskLevel.HIGH)
        self.assertEqual(classify_snow(2.00), RiskLevel.SEVERE)
        self.assertEqual(classify_snow(3.00), RiskLevel.SEVERE)
        self.assertEqual(classify_snow(3.01), RiskLevel.NO_TRAVEL)

    def test_overall_risk_uses_highest_risk(self):
        result = classify_checkpoint(
            wind_mph=30,
            rain_in_hr=0.6,
            snow_in_hr=0.2,
            load_lb=0,
        )

        self.assertEqual(result["wind_risk"], RiskLevel.MODERATE)
        self.assertEqual(result["rain_risk"], RiskLevel.SEVERE)
        self.assertEqual(result["snow_risk"], RiskLevel.LOW)
        self.assertEqual(result["overall_risk"], RiskLevel.SEVERE)
        self.assertFalse(result["load_override_applied"])

    def test_overall_risk_no_travel_dominates(self):
        result = classify_checkpoint(
            wind_mph=20,
            rain_in_hr=0.05,
            snow_in_hr=3.5,
            load_lb=0,
        )

        self.assertEqual(result["wind_risk"], RiskLevel.LOW)
        self.assertEqual(result["rain_risk"], RiskLevel.LOW)
        self.assertEqual(result["snow_risk"], RiskLevel.NO_TRAVEL)
        self.assertEqual(result["overall_risk"], RiskLevel.NO_TRAVEL)
        self.assertFalse(result["load_override_applied"])

    def test_checkpoint_load_override_is_reported(self):
        result = classify_checkpoint(
            wind_mph=50,
            rain_in_hr=0,
            snow_in_hr=0,
            load_lb=35000,
        )

        self.assertEqual(result["wind_risk"], RiskLevel.NO_TRAVEL)
        self.assertEqual(result["overall_risk"], RiskLevel.NO_TRAVEL)
        self.assertTrue(result["load_override_applied"])

        result = classify_checkpoint(
            wind_mph=40,
            rain_in_hr=0,
            snow_in_hr=0,
            load_lb=45000,
        )

        self.assertEqual(result["wind_risk"], RiskLevel.SEVERE)
        self.assertEqual(result["overall_risk"], RiskLevel.SEVERE)
        self.assertTrue(result["load_override_applied"])

    def test_missing_or_negative_values_are_treated_as_low(self):
        result = classify_checkpoint(
            wind_mph=None,
            rain_in_hr=None,
            snow_in_hr=None,
            load_lb=None,
        )

        self.assertEqual(result["wind_risk"], RiskLevel.LOW)
        self.assertEqual(result["rain_risk"], RiskLevel.LOW)
        self.assertEqual(result["snow_risk"], RiskLevel.LOW)
        self.assertEqual(result["overall_risk"], RiskLevel.LOW)
        self.assertFalse(result["load_override_applied"])

        result = classify_checkpoint(
            wind_mph=-10,
            rain_in_hr=-1,
            snow_in_hr=-5,
            load_lb=-1000,
        )

        self.assertEqual(result["wind_risk"], RiskLevel.LOW)
        self.assertEqual(result["rain_risk"], RiskLevel.LOW)
        self.assertEqual(result["snow_risk"], RiskLevel.LOW)
        self.assertEqual(result["overall_risk"], RiskLevel.LOW)
        self.assertFalse(result["load_override_applied"])
