from __future__ import annotations

from pathlib import Path

def test_config_loads_and_appends_other(monkeypatch, tmp_path: Path, config_file: Path):
    from backend import config as config_module

    created = {}

    class DummyStorage:
        NAME = "Dummy"

        def __init__(self, **kwargs):
            created.update(kwargs)

    monkeypatch.setattr(config_module, "SeafileStorage", DummyStorage)
    config_text = "\n".join(
        [
            "DEBUG = true",
            "CARROUSEL_SIZE = 5",
            "RESULTS_PER_IMAGE = 3",
            'ANIMAL_TYPES = ["cat"]',
            "",
            "[security]",
            'PASSWORD_HASH = "hash"',
            'ACCESS_TOKEN_EXPIRE_TIME = 10',
            'SECRET_KEY = "secret"',
            'ALGORITHM = "HS256"',
            'TIMEZONE = "UTC"',
            "",
            "[storage]",
            "[[storage.seafile]]",
            'SEAFILE_USERNAME = "user"',
            'SEAFILE_PASSWORD = "pass"',
            'SEAFILE_URL = "https://example.invalid"',
            'SEAFILE_LIBRARY_NAME = "library"',
            "",
        ]
    )
    path = tmp_path / "config.toml"
    path.write_text(config_text, encoding="utf-8")
    cfg = config_module.Config(str(path))

    assert cfg.debug is True
    assert cfg.carrousel_size == 5
    assert cfg.results_per_image == 3
    assert "cat" in cfg.animal_types
    assert "other" in cfg.animal_types
    assert isinstance(cfg.storage[0], DummyStorage)
    assert created["server_url"] == "https://example.invalid"
