
from datetime import datetime, timezone

from agents.mobility.specialists.public_transport_agent import analyze


def test_public_transport_agent():

    now = datetime.now(timezone.utc).isoformat()

    context = {
        "transport_data": {
            "max_age_minutes": 15,
            "services": [
                {
                    "name": "Metro Linea 2",
                    "operator": "Trenitalia",
                    "status": "active",
                    "updated_at": now,
                    "source": "test_source"
                },
                {
                    "name": "Autobus linea 151",
                    "operator": "ANM",
                    "status": "delayed",
                    "updated_at": now,
                    "source": "test_source"
                },
                {
                    "name": "Tram",
                    "operator": "ANM",
                    "status": "suspended",
                    "updated_at": now,
                    "source": "test_source"
                },
                {
                    "name": "Servizio ferroviario",
                    "operator": "EAV",
                    "status": "unknown",
                    "updated_at": None,
                    "source": None
                }
            ]
        }
    }

    result = analyze(context=context)

    services = result["services"]

    assert len(services) == 4

    assert services[0]["status"] == "active"
    assert services[1]["status"] == "delayed"
    assert services[2]["status"] == "suspended"
    assert services[3]["status"] == "unknown"

    assert services[0]["data_outdated"] is False
    assert services[3]["data_outdated"] is True

    assert result["analysis_status"] == "insufficient_data"

    assert len(result["missing_information"]) > 0
    assert len(result["required_checks"]) > 0

    print("\n===== PUBLIC TRANSPORT AGENT =====")

    for service in services:
        print(
            service["service"],
            "|",
            service["status"],
            "|",
            "Dati obsoleti:",
            service["data_outdated"]
        )

    print("\nVerifiche richieste:")
    for check in result["required_checks"]:
        print("-", check)

    print("\nTEST SUPERATO")


if __name__ == "__main__":
    test_public_transport_agent()
