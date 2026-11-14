import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from agents.civil_protection.civil_protection_agent import (
    analyze_civil_protection_request,
)


class CivilProtectionAgentTests(unittest.TestCase):

    def test_full_analysis_with_active_alert(self):
        now = datetime(2026, 11, 15, 12, 0, tzinfo=ZoneInfo("Europe/Rome"))

        result = analyze_civil_protection_request(
            alerts=[{
                "id": 1,
                "alert_number": "094/2026",
                "source_name": "Protezione Civile Regione Campania",
                "source_url": "https://portaleprotezionecivile.regione.campania.it/",
                "valid_from": "06:00 15 novembre 2026",
                "valid_until": "06:00 16 novembre 2026",
                "zones": [{
                    "zone": 1,
                    "territory": "Piana campana, Napoli, Isole, Area Vesuviana",
                    "alert_level": "gialla",
                    "risks": ["idrogeologico"],
                }],
            }],
            now=now,
        )

        self.assertEqual(result["agent"], "civil_protection_agent")
        self.assertEqual(result["summary"]["active_alerts"], 1)
        self.assertEqual(
            result["official_alert_analysis"]["alerts"][0]["validity_status"],
            "active",
        )
        self.assertEqual(
            result["risk_analysis"]["risk_types"],
            ["idrogeologico"],
        )
        self.assertEqual(
            len(result["territorial_impact_analysis"]["naples_related_areas"]),
            1,
        )

    def test_empty_input_does_not_invent_alerts(self):
        result = analyze_civil_protection_request(alerts=[])
        self.assertEqual(result["summary"]["total_alerts"], 0)
        self.assertEqual(result["analysis_status"], "insufficient_data")


if __name__ == "__main__":
    unittest.main()
