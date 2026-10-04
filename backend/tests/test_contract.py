import importlib.util
from pathlib import Path

from fastapi.routing import APIRoute

from hedgecast.main import create_app

ROOT = Path(__file__).resolve().parents[2]
UNTYPED = {"/api/health", "/api/session"}


def _exporter():
    spec = importlib.util.spec_from_file_location("export_openapi", ROOT / "backend" / "scripts" / "export_openapi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_route_declares_a_response_model():
    app = create_app()
    missing = [
        f"{sorted(route.methods)} {route.path}"
        for route in app.routes
        if isinstance(route, APIRoute) and route.response_model is None and route.path not in UNTYPED
    ]
    assert missing == []


def test_frontend_openapi_is_current():
    exporter = _exporter()
    assert exporter.TARGET.exists(), "Run `make types`."
    assert exporter.TARGET.read_text() == exporter.render(), "The API changed. Run `make types`."
