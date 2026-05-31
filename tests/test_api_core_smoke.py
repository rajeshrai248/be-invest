from fastapi.testclient import TestClient

from be_invest.api.server import app


def test_core_api_health_brokers_and_cost_tables():
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    brokers = client.get("/brokers")
    assert brokers.status_code == 200
    broker_payload = brokers.json()
    assert broker_payload
    assert {"name", "website", "country", "instruments", "data_sources", "news_sources"} <= set(broker_payload[0])

    cost_analysis = client.get("/cost-analysis")
    assert cost_analysis.status_code == 200
    assert isinstance(cost_analysis.json(), dict)

    tables = client.get("/cost-comparison-tables", params={"model": "gpt-4o", "force": False, "lang": "en"})
    assert tables.status_code == 200
    tables_payload = tables.json()
    assert "euronext_brussels" in tables_payload
    assert "stocks" in tables_payload["euronext_brussels"]
    assert "etfs" in tables_payload["euronext_brussels"]
    assert tables_payload["_validation"]["method"] == "deterministic"
