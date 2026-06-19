from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import password_hash


_root = Path(tempfile.mkdtemp(prefix="podcast-processor-test-"))
os.environ.update(
    {
        "DATA_DIR": str(_root / "data"),
        "PODCAST_DIR": str(_root / "podcasts"),
        "DATABASE_URL": f"sqlite:///{_root / 'app.db'}",
        "ADMIN_USERNAME": "operator",
        "ADMIN_PASSWORD_HASH": password_hash.hash("test-password"),
        "SESSION_SECRET": "test-session-secret-longer-than-thirty-two-characters",
        "SECURE_COOKIES": "false",
    }
)

from app.main import app  # noqa: E402


def test_health_and_authenticated_dashboard():
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] in {"ok", "degraded"}

        login_page = client.get("/login")
        token = re.search(r'name="csrf" value="([^"]+)"', login_page.text).group(1)
        response = client.post(
            "/login",
            data={
                "username": "operator",
                "password": "test-password",
                "csrf": token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert client.get("/").status_code == 200

