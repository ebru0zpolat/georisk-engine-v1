import uuid


def test_dashboard_loads(client):
    response = client.get("/")
    assert response.status_code == 200


def test_health_loads(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"api": "ok", "db": "ok"}
    assert "timestamp_utc" in body


def test_request_id_header(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert uuid.UUID(response.headers["x-request-id"])


def test_static_css_loads(client):
    response = client.get("/static/styles.css")
    assert response.status_code == 200


def test_demo_assets(client):
    response = client.get("/v1/demo/assets")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3


def test_demo_run(client):
    response = client.get("/v1/demo/run?asset_id=coastal_industrial_med")
    assert response.status_code == 200


def test_demo_pdf(client):
    response = client.get("/v1/demo/run/pdf?asset_id=coastal_industrial_med")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
