import json
import sqlite3
import unittest

from unittest.mock import patch

from agents.social_intelligence_agent import (
    get_social_intelligence,
    analyze_social_reports
)


class TestSocialIntelligenceAgent(unittest.TestCase):

    def setUp(self):

        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row

        # Tabella incidenti
        self.connection.execute(
            """
            CREATE TABLE incidents (
                id INTEGER PRIMARY KEY,
                event_type TEXT,
                description TEXT,
                location TEXT,
                latitude REAL,
                longitude REAL,
                priority TEXT,
                verification_status TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        # Tabella segnalazioni social
        self.connection.execute(
            """
            CREATE TABLE social_reports (
                id INTEGER PRIMARY KEY,
                post_uri TEXT,
                incident_id INTEGER,
                source TEXT,
                author_did TEXT,
                text TEXT,
                categories TEXT,
                locations TEXT,
                published_at TEXT,
                received_at TEXT
            )
            """
        )

        # Inserimento incidente di prova
        self.connection.execute(
            """
            INSERT INTO incidents (
                id,
                event_type,
                description,
                location,
                latitude,
                longitude,
                priority,
                verification_status,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "environment",
                "Segnalazione di incendio a Bagnoli",
                "Bagnoli",
                40.8173,
                14.1670,
                "pending",
                "unverified",
                "open",
                "2026-11-14T09:00:00+00:00",
                "2026-11-14T09:00:00+00:00"
            )
        )

        # Inserimento prima segnalazione
        self.connection.execute(
            """
            INSERT INTO social_reports (
                id,
                post_uri,
                incident_id,
                source,
                author_did,
                text,
                categories,
                locations,
                published_at,
                received_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "at://test/1",
                1,
                "bluesky",
                "did:example:autore1",
                "Incendio segnalato a Bagnoli",
                json.dumps([
                    {
                        "category": "environment",
                        "matched_keywords": ["incendio"]
                    }
                ]),
                json.dumps(["napoli", "bagnoli"]),
                "2026-11-14T09:10:00+00:00",
                "2026-11-14T09:11:00+00:00"
            )
        )

        # Inserimento seconda segnalazione
        self.connection.execute(
            """
            INSERT INTO social_reports (
                id,
                post_uri,
                incident_id,
                source,
                author_did,
                text,
                categories,
                locations,
                published_at,
                received_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                "at://test/2",
                1,
                "bluesky",
                "did:example:autore2",
                "Fumo visibile nella zona di Bagnoli",
                json.dumps([
                    {
                        "category": "environment",
                        "matched_keywords": ["fumo"]
                    }
                ]),
                json.dumps(["napoli", "bagnoli"]),
                "2026-11-14T09:20:00+00:00",
                "2026-11-14T09:21:00+00:00"
            )
        )

        self.connection.commit()

        # Sostituiamo la connessione reale con quella di test
        self.connection_patch = patch(
            "agents.social_intelligence_agent.get_connection",
            return_value=self.connection
        )

        self.connection_patch.start()

    def tearDown(self):

        self.connection_patch.stop()
        self.connection.close()

    def test_analisi_incidente(self):

        result = get_social_intelligence(1)

        self.assertIsNotNone(result)

        self.assertEqual(
            result["agent"],
            "social_intelligence_agent"
        )

        self.assertEqual(
            result["incident"]["location"],
            "Bagnoli"
        )

        self.assertEqual(
            result["social_analysis"]["total_reports"],
            2
        )

        self.assertEqual(
            result["social_analysis"]["distinct_authors"],
            2
        )

        self.assertEqual(
            result["social_analysis"]["categories"]["environment"],
            2
        )

        self.assertEqual(
            result["social_analysis"]["locations"]["bagnoli"],
            2
        )

        self.assertEqual(
            len(result["reports"]),
            2
        )

        print("\nTEST ANALISI INCIDENTE SUPERATO!")

    def test_incidente_inesistente(self):

        result = get_social_intelligence(999)

        self.assertIsNone(result)

        print("TEST INCIDENTE INESISTENTE SUPERATO!")

    def test_nessuna_segnalazione(self):

        self.connection.execute(
            "DELETE FROM social_reports"
        )

        self.connection.commit()

        result = get_social_intelligence(1)

        self.assertEqual(
            result["social_analysis"]["total_reports"],
            0
        )

        self.assertTrue(
            result["social_analysis"]["limitations"]
        )

        print("TEST INCIDENTE SENZA SEGNALAZIONI SUPERATO!")

    def test_autori_distinti_non_sono_conferme(self):

        reports = [
            {
                "author_did": "did:example:autore1",
                "categories": "[]",
                "locations": "[]",
                "published_at": None
            },
            {
                "author_did": "did:example:autore2",
                "categories": "[]",
                "locations": "[]",
                "published_at": None
            }
        ]

        result = analyze_social_reports(reports)

        self.assertEqual(
            result["distinct_authors"],
            2
        )

        self.assertTrue(
            any(
                "fonti indipendenti" in limitation
                for limitation in result["limitations"]
            )
        )

        print("TEST AUTORI DISTINTI SUPERATO!")


if __name__ == "__main__":

    unittest.main(verbosity=2)