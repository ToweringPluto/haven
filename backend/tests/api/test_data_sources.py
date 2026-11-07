from fastapi.testclient import TestClient

from haven.datasets import load_registry


def test_data_sources_returns_the_registry(client: TestClient) -> None:
    response = client.get("/v1/data-sources")
    assert response.status_code == 200
    items = response.json()["items"]
    registry = load_registry()
    assert [i["id"] for i in items] == [d.id for d in registry.datasets]
    for item in items:
        assert set(item) == {"id", "name", "url", "licence_note", "as_of", "caveats"}
        assert item["url"] and item["licence_note"] and item["as_of"] and item["caveats"]
    osm = next(i for i in items if i["id"] == "osm_routes")
    assert "OpenStreetMap contributors" in osm["licence_note"]
