"""
Testes unitários para a GitOps Demo API.
Executados no CI antes do build da imagem Docker.
"""

import pytest
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from main import app

client = TestClient(app)


def test_root_returns_200():
    response = client.get("/")
    assert response.status_code == 200


def test_root_contains_app_name():
    response = client.get("/")
    data = response.json()
    assert data["app"] == "gitops-demo"


def test_health_probe():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_readiness_probe():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_info_endpoint():
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "environment" in data
    assert "git_commit" in data
