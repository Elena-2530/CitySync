import unittest

from agents.civil_protection.specialists.risk_analysis_agent import analyze_risks


class RiskAnalysisAgentTests(unittest.TestCase):

    def test_extract_risks_and_highest_level(self):
        result = analyze_risks({
            "alerts": [{
                "alert_number": "094/2026",
                "validity_status": "active",
                "zones": [
                    {"zone": 1, "territory": "Napoli", "alert_level": "gialla", "risks": ["idrogeologico"]},
                    {"zone": 2, "territory": "Area interna", "alert_level": "arancione", "risks": ["idraulico"]},
                ],
            }]
        })

        self.assertEqual(len(result["risk_records"]), 2)
        self.assertEqual(result["highest_reported_alert_level"], "arancione")
        self.assertIn("idrogeologico", result["risk_types"])
        self.assertIn("idraulico", result["risk_types"])

    def test_missing_risk_is_reported(self):
        result = analyze_risks({
            "alerts": [{
                "alert_number": "001/2026",
                "validity_status": "active",
                "zones": [{
                    "zone": 1,
                    "territory": "Napoli",
                    "alert_level": "gialla",
                    "risks": [],
                }],
            }]
        })
        self.assertTrue(result["missing_information"])


if __name__ == "__main__":
    unittest.main()
