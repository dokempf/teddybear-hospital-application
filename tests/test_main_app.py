from __future__ import annotations


def test_main_app_includes_routes(main_app):
    paths = {route.path for route in main_app.router.routes}
    assert "/token" in paths
    assert "/upload" in paths
    assert "/apply_fracture" in paths
