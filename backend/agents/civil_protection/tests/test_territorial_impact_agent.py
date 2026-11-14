import unittest

from agents.civil_protection.specialists.territorial_impact_agent import (
    analyze_territorial_impact,
)


class TerritorialImpactAgentTests(unittest.TestCase):

    def test_naples_area_is_detected_from_official_text(self):
        result = analyze_territorial_impact({
            "alerts": [{
                "alert_number": "094/2026",
                "validity_status": "active",
                "zones": [{
                    "zone": 1,
                    "territory": "Piana campana, Napoli, Isole, Area Vesuviana",
                    "alert_level": "gialla",
                    "risks": ["idrogeologico"],
                }],
            }]
        })

        self.assertEqual(len(result["affected_areas"]), 1)
        self.assertEqual(len(result["naples_related_areas"]), 1)
        self.assertEqual(
            result["affected_areas"][0]["geographic_precision"],
            "official_textual_zone",
        )

    def test_missing_territory_is_reported(self):
        result = analyze_territorial_impact({
            "alerts": [{
                "alert_number": "001/2026",
                "validity_status": "active",
                "zones": [{"zone": 1, "territory": None}],
            }]
        })
        self.assertTrue(result["missing_information"])


if __name__ == "__main__":
    unittest.main()
