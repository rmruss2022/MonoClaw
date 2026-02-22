from pathlib import Path

from app.core.settings import settings


def test_request_id_header(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert "x-request-id" in response.headers


def test_admin_log_tail(client):
    log_path = Path(settings.log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text('{"message":"test"}\n', encoding="utf-8")
    response = client.get("/admin/logs/tail?n=5")
    assert response.status_code == 200
    assert response.json()["lines"]
