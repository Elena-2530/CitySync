import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from agents.civil_protection.specialists.official_alert_agent import (
    parse_alert_datetime,
    determine_validity,
    analyze_one_alert,
)


ROME = ZoneInfo("Europe/Rome")


class OfficialAlertAgentTests(unittest.TestCase):

    def test_parse_italian_month(self):
        result = parse_alert_datetime("06:00 15 novembre 2026")
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 11)
        self.assertEqual(result.day, 15)

    def test_active_alert(self):
        now = datetime(2026, 11, 15, 12, 0, tzinfo=ROME)
        status = determine_validity(
            "06:00 15 novembre 2026",
            "06:00 16 novembre 2026",
            now,
        )
        self.assertEqual(status, "active")

    def test_upcoming_alert(self):
        now = datetime(2026, 11, 14, 12, 0, tzinfo=ROME)
        status = determine_validity(
            "06:00 15 novembre 2026",
            "06:00 16 novembre 2026",
            now,
        )
        self.assertEqual(status, "upcoming")

    def test_expired_alert(self):
        now = datetime(2026, 11, 17, 12, 0, tzinfo=ROME)
        status = determine_validity(
            "06:00 15 novembre 2026",
            "06:00 16 novembre 2026",
            now,
        )
        self.assertEqual(status, "expired")

    def test_unparseable_dates_are_unknown(self):
        self.assertEqual(determine_validity("data errata", None), "unknown")

    def test_normalize_alert(self):
        now = datetime(2026, 11, 15, 12, 0, tzinfo=ROME)
        result = analyze_one_alert({
            "alert_number": "094/2026",
            "valid_from": "06:00 15 novembre 2026",
            "valid_until": "06:00 16 novembre 2026",
            "zones": [{
                "zone": 1,
                "territory": "Piana campana, Napoli, Isole, Area Vesuviana",
                "alert_level": "GIALLA",
                "risks": ["Idrogeologico"],
            }],
        }, now=now)

        self.assertEqual(result["validity_status"], "active")
        self.assertEqual(result["zones"][0]["alert_level"], "gialla")
        self.assertEqual(result["zones"][0]["risks"], ["idrogeologico"])


if __name__ == "__main__":
    unittest.main()
