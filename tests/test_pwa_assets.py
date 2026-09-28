"""Tests for PWA Manifest and application touch icons."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.core.database import Base, get_db_session
from data_recorder.main import app


@pytest.fixture
def test_db_session():
    """In-memory SQLite test session."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={
            "schema_translate_map": {"verbrauch": None, "wertpapiere": None}
        },
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(test_db_session: Session):
    """FastAPI TestClient with overridden get_db_session."""
    def override_get_db_session():
        yield test_db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()



def test_manifest_file_structure():
    """Verify manifest.json exists and has standard PWA properties."""
    manifest_path = Path("src/data_recorder/static/manifest.json")
    assert manifest_path.exists(), "static/manifest.json must exist"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["name"]
    assert manifest["short_name"]
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] in ("/wizard", "/")
    assert len(manifest.get("icons", [])) >= 2

    # Check icons listed in manifest
    icon_srcs = [icon["src"] for icon in manifest["icons"]]
    assert any("192" in src for src in icon_srcs)
    assert any("512" in src for src in icon_srcs)


def test_touch_icons_exist_and_valid():
    """Verify icon images exist with appropriate dimensions and valid PNG headers."""
    icons_dir = Path("src/data_recorder/static/icons")
    assert icons_dir.exists(), "static/icons directory must exist"

    icon_192 = icons_dir / "icon-192.png"
    icon_512 = icons_dir / "icon-512.png"
    apple_icon = icons_dir / "apple-touch-icon.png"

    assert icon_192.exists(), "icon-192.png missing"
    assert icon_512.exists(), "icon-512.png missing"
    assert apple_icon.exists(), "apple-touch-icon.png missing"

    with Image.open(icon_192) as img:
        assert img.format == "PNG"
        assert img.size == (192, 192)

    with Image.open(icon_512) as img:
        assert img.format == "PNG"
        assert img.size == (512, 512)

    with Image.open(apple_icon) as img:
        assert img.format == "PNG"
        assert img.size[0] >= 180 and img.size[1] >= 180


def test_manifest_endpoint_http():
    """Verify GET /manifest.json returns 200 and JSON content."""
    client = TestClient(app)
    response = client.get("/manifest.json")
    assert response.status_code == 200
    data = response.json()
    assert data["display"] == "standalone"
    assert data["short_name"] == "Zähler"
    assert "share_target" in data
    st = data["share_target"]
    assert st["action"] == "/wizard/share"
    assert st["method"] == "POST"
    assert st["enctype"] == "multipart/form-data"
    assert "files" in st["params"]
    assert any(f["name"] == "foto" for f in st["params"]["files"])


def test_manifest_share_target_structure():
    """Verify share_target has valid schema and image mime-types."""
    manifest_path = Path("src/data_recorder/static/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "share_target" in manifest
    st = manifest["share_target"]
    assert st["action"] == "/wizard/share"
    assert st["method"].upper() == "POST"
    assert st["enctype"] == "multipart/form-data"
    files = st.get("params", {}).get("files", [])
    assert len(files) >= 1
    foto_param = next((f for f in files if f.get("name") == "foto"), None)
    assert foto_param is not None
    accepts = foto_param.get("accept", [])
    assert "image/*" in accepts
    assert any("heic" in acc for acc in accepts)



def test_static_icon_endpoint_http(client: TestClient):
    """Verify GET /static/icons/icon-192.png returns 200 and image/png."""
    response = client.get("/static/icons/icon-192.png")
    assert response.status_code == 200
    assert "image/png" in response.headers.get("content-type", "")


def test_service_worker_file_exists():
    """Verify sw.js exists in static directory."""
    sw_path = Path("src/data_recorder/static/sw.js")
    assert sw_path.exists(), "static/sw.js must exist"
    content = sw_path.read_text(encoding="utf-8")
    assert "install" in content
    assert "activate" in content
    assert "fetch" in content


def test_service_worker_endpoint_http(client: TestClient):
    """Verify GET /sw.js returns 200, javascript content type, and Service-Worker-Allowed header."""
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "")
    assert response.headers.get("Service-Worker-Allowed") == "/"


def test_base_template_registers_service_worker(client: TestClient):
    """Verify HTML template includes Service Worker registration script."""
    response = client.get("/wizard")
    assert response.status_code == 200
    assert "navigator.serviceWorker.register('/sw.js'" in response.text


