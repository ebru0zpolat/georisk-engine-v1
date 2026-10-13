def _valid_case_payload() -> dict:
    return {
        "title": "Validate flood exposure anomaly",
        "description": "Sustained flood-risk anomaly detected for the İzmir supplier site.",
        "asset_id": "asset_izmir_001",
        "severity": "high",
        "priority": "p2",
        "tags": ["flood", "supplier"],
    }


def test_cases_crud_and_lifecycle(client):
    create_response = client.post("/v1/cases", json=_valid_case_payload())
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"].startswith("case_")
    assert created["status"] == "open"
    assert created["severity"] == "high"

    list_response = client.get("/v1/cases?status=open")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["count"] >= 1
    assert any(case["id"] == created["id"] for case in listed["cases"])

    patch_response = client.patch(
        f"/v1/cases/{created['id']}",
        json={"priority": "p1", "assigned_to": "info@georiskengine.com"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["priority"] == "p1"
    assert patch_response.json()["assigned_to"] == "info@georiskengine.com"

    triage_response = client.patch(
        f"/v1/cases/{created['id']}/triage",
        json={"note": "Confirmed signal quality and assigned for response."},
    )
    assert triage_response.status_code == 200
    assert triage_response.json()["status"] == "triaged"

    escalate_response = client.patch(
        f"/v1/cases/{created['id']}/escalate",
        json={"note": "Executive review required."},
    )
    assert escalate_response.status_code == 200
    assert escalate_response.json()["status"] == "escalated"

    close_response = client.patch(
        f"/v1/cases/{created['id']}/close",
        json={"resolution": "Supplier mitigation plan accepted."},
    )
    assert close_response.status_code == 200
    assert close_response.json()["status"] == "closed"
    assert close_response.json()["closed_at"] is not None

    get_response = client.get(f"/v1/cases/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["close_resolution"] == "Supplier mitigation plan accepted."


def test_case_validation_and_state_machine_rules(client):
    missing_asset_response = client.post(
        "/v1/cases",
        json={"title": "Missing asset", "severity": "medium"},
    )
    assert missing_asset_response.status_code == 422

    invalid_enum_response = client.post(
        "/v1/cases",
        json={**_valid_case_payload(), "severity": "urgent"},
    )
    assert invalid_enum_response.status_code == 422

    create_response = client.post("/v1/cases", json=_valid_case_payload())
    case_id = create_response.json()["id"]

    invalid_transition_response = client.patch(
        f"/v1/cases/{case_id}/escalate",
        json={"note": "Cannot skip triage."},
    )
    assert invalid_transition_response.status_code == 409

    client.patch(
        f"/v1/cases/{case_id}/close",
        json={"resolution": "No action needed."},
    )
    closed_patch_response = client.patch(
        f"/v1/cases/{case_id}",
        json={"priority": "p4"},
    )
    assert closed_patch_response.status_code == 409
