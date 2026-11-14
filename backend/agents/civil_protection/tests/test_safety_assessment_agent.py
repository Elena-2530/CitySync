import unittest

from agents.civil_protection.specialists.safety_assessment_agent import assess_safety


class SafetyAssessmentAgentTests(unittest.TestCase):

    def test_active_alert_produces_cautious_recommendations(self):
        result = assess_safety(
            official_analysis={"alerts": [{
                "alert_number": "094/2026",
                "source_name": "Protezione Civile Regione Campania",
                "validity_status": "active",
            }]},
            risk_analysis={"risk_records": [{
                "validity_status": "active",
                "risk_type": "idrogeologico",
            }]},
            territorial_analysis={"affected_areas": [{
                "territory": "Napoli",
            }]},
        )

        self.assertEqual(result["active_alert_count"], 1)
        self.assertEqual(result["active_risk_count"], 1)
        self.assertTrue(result["recommendations"])
        self.assertNotIn("evacuare", " ".join(result["recommendations"]).lower())

    def test_no_alerts_is_insufficient(self):
        result = assess_safety({}, {}, {})
        self.assertEqual(result["assessment_status"], "insufficient_data")
        self.assertTrue(result["missing_information"])


if __name__ == "__main__":
    unittest.main()
