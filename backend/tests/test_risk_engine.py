import unittest

from app.services.risk_engine import (
    calculate_operations_remaining_hours,
    calculate_queue_delay_hours,
    calculate_risk_level,
    calculate_testing_capacity_per_hour,
    compute_clinic_metrics,
    recommended_transfer_quantity,
)


class RiskEngineTest(unittest.TestCase):
    def test_capacity_uses_twelve_tests_per_nurse_hour(self):
        self.assertEqual(calculate_testing_capacity_per_hour(3), 36)

    def test_queue_delay_handles_zero_nurses(self):
        self.assertIsNone(calculate_queue_delay_hours(20, 0))

    def test_operations_remaining_for_clinic_b_scenario(self):
        self.assertEqual(calculate_operations_remaining_hours(35, 2), 1.46)

    def test_critical_when_zero_nurses_and_queue_waiting(self):
        risk = calculate_risk_level(
            test_kits_available=40,
            people_waiting=12,
            nurses_available=0,
            threshold_min_kits=30,
            operations_remaining_hours=None,
            queue_delay_hours=None,
        )
        self.assertEqual(risk, "critical")

    def test_high_risk_for_low_operations(self):
        metrics = compute_clinic_metrics(
            {
                "test_kits_available": 35,
                "people_waiting": 96,
                "nurses_available": 2,
                "threshold_min_kits": 50,
            }
        )
        self.assertEqual(metrics["testing_capacity_per_hour"], 24)
        self.assertEqual(metrics["queue_delay_hours"], 4)
        self.assertEqual(metrics["operations_remaining_hours"], 1.46)
        self.assertEqual(metrics["risk_level"], "high")

    def test_transfer_quantity_restores_four_hours(self):
        self.assertEqual(
            recommended_transfer_quantity(
                {"nurses_available": 2, "test_kits_available": 35}
            ),
            61,
        )

if __name__ == "__main__":
    unittest.main()
