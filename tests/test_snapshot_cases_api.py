
def test_snapshot_cases_derive_from_asset(client):
    response = client.get("/v1/cases?asset_id=coastal_industrial_med")
    assert response.status_code == 200
    payload = response.json()
    assert payload["asset_id"] == "coastal_industrial_med"
    assert "open_count" in payload
    assert isinstance(payload["cases"], list)
    if payload["cases"]:
        case = payload["cases"][0]
        assert case["asset_id"] == "coastal_industrial_med"
        assert "events" in case
