import io

from PIL import Image


def _png_bytes(color: tuple[int, int, int] = (180, 20, 20)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_integration_analyze_route_uses_headless_analyzer(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "integration-analyze.db"))

    from apps.api.app import create_app

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.post(
            "/api/v1/analyze",
            data={"image": (io.BytesIO(_png_bytes()), "wound.png")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["analysis_id"]
    assert "is_valid_wound" in payload
    assert "primary_tissue" in payload
    assert "processing_time_ms" in payload
