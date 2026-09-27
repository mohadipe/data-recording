"""Tests for PWA Manifest and application touch icons."""

import json
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image

from data_recorder.main import app


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


def test_static_icon_endpoint_http():
    """Verify GET /static/icons/icon-192.png returns 200 and image/png."""
    client = TestClient(app)
    response = client.get("/static/icons/icon-192.png")
    assert response.status_code == 200
    assert "image/png" in response.headers.get("content-type", "")
