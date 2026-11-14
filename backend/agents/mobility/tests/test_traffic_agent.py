
from datetime import datetime, timezone

from agents.mobility.specialists.traffic_agent import analyze


def test_traffic_agent():

    now = datetime.now(timezone.utc).isoformat()

    context = {
        "traffic_data": {
            "max_age_minutes": 15,
            "conditions": [
                {
                    "road": "Via Marina",
                    "status": "normal",
                    "updated_at": now,
                    "source": "test_source"
                },
                {
                    "road": "Via Toledo",
                    "status": "slow",
                    "updated_at": now,
                    "source": "test_source"
                },
                {
                    "road": "Via Caracciolo",
                    "status": "closed",
                    "updated_at": now,
                    "source": "test_source"
                },
                {
                    "road": "Via Fuorigrotta",
                    "status": "flooded",
                    "updated_at": now,
                    "source": "test_source"
                },
                {
                    "road": "Strada non identificata",
                    "status": "unknown",
                    "updated_at": None,
                    "source": None
                }
            ],
            "affected_roads": [
                "Via Marina",
                "Via Toledo",
                "Via Caracciolo",
                "Via Fuorigrotta"
            ]
        }
    }

    result = analyze(context=context)

    conditions = result["traffic_conditions"]

    assert len(conditions) == 5

    assert conditions[0]["status"] == "normal"
    assert conditions[1]["status"] == "slow"
    assert conditions[2]["status"] == "closed"
    assert conditions[3]["status"] == "flooded"
    assert conditions[4]["status"] == "unknown"

    assert conditions[0]["data_outdated"] is False
    assert conditions[4]["data_outdated"] is True

    assert result["analysis_status"] == "partial"

    assert len(result["required_checks"]) > 0
    assert len(result["missing_information"]) > 0

    print("\n===== TRAFFIC AGENT =====")

    for condition in conditions:
        print(
            condition["road"],
            "|",
            condition["status"],
            "|",
            "Dati obsoleti:",
            condition["data_outdated"]
        )

    print("\nVerifiche richieste:")

    for check in result["required_checks"]:
        print("-", check)

    print("\nTEST SUPERATO")


if __name__ == "__main__":
    test_traffic_agent()
