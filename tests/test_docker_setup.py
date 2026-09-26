from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_exists_and_content():
    dockerfile_path = REPO_ROOT / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile must exist at repository root"

    content = dockerfile_path.read_text(encoding="utf-8")

    # Multi-stage check
    assert "AS builder" in content, "Dockerfile should use multi-stage build"
    assert "AS runner" in content, "Dockerfile should have runner stage"
    assert "python:3.12-slim" in content, "Dockerfile must be based on python:3.12-slim"

    # Security: Non-root user
    assert "USER appuser" in content, "Container must switch to non-root appuser"
    assert "useradd" in content and "appuser" in content

    # Port & Entrypoint
    assert "EXPOSE 9015" in content, "Port 9015 must be exposed"
    assert "uvicorn" in content and "data_recorder.main:app" in content
    assert "--host" in content and "0.0.0.0" in content
    assert "--port" in content and "9015" in content


def test_dockerignore_exists_and_content():
    dockerignore_path = REPO_ROOT / ".dockerignore"
    assert dockerignore_path.exists(), ".dockerignore must exist at repository root"

    content = dockerignore_path.read_text(encoding="utf-8")
    assert ".git" in content
    assert ".venv" in content
    assert "tests" in content
    assert ".env" in content


def test_docker_compose_exists_and_valid():
    compose_path = REPO_ROOT / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml must exist at repository root"

    with compose_path.open(encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    assert "services" in compose, "docker-compose must define services"
    assert "data-recorder" in compose["services"], "Service data-recorder must be configured"

    service = compose["services"]["data-recorder"]
    assert "9015:9015" in service.get("ports", []), "Port 9015:9015 must be mapped"

    # Environment
    assert ".env" in service.get("env_file", []), "Environment should load from .env"

    # Volume mounts
    volumes = service.get("volumes", [])
    assert any("logs" in v for v in volumes), "Volume mount for logs must be present"
    assert any("uploads" in v for v in volumes), "Volume mount for uploads must be present"

    # Networks
    assert "networks" in service, "Service must be connected to network"
    assert "synology_default" in service["networks"] or "default" in service["networks"]
