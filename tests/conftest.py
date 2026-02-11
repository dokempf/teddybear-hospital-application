from __future__ import annotations

import importlib
from io import BytesIO
from pathlib import Path
from typing import IO

import pytest
from fastapi import FastAPI
from passlib.context import CryptContext
from PIL import Image

from backend.storage import Storage


class MockStorage(Storage):
    NAME = "MockStorage"

    def __init__(self) -> None:
        self.created_links: list[str] = []
        self.uploads: list[dict[str, object]] = []

    def create_storage_for_user(self) -> str:
        link = f"mock://upload/{len(self.created_links)}"
        self.created_links.append(link)
        return link

    def upload_file(
        self, user_ref: int | str, type: str, file_path: Path | IO, filename: str
    ) -> None:
        size = None
        if not hasattr(file_path, "read"):
            with open(file_path, "rb") as handle:
                data = handle.read()
            size = len(data)
        self.uploads.append(
            {
                "user_ref": user_ref,
                "type": type,
                "filename": filename,
                "size": size,
            }
        )


class FakeUploadFile:
    def __init__(self, data: bytes, filename: str = "file.png"):
        self.filename = filename
        self.file = BytesIO(data)

    async def read(self) -> bytes:
        return self.file.read()

    async def seek(self, offset: int) -> int:
        return self.file.seek(offset)


class FakeSpooledTemporaryFile:
    def __init__(self):
        self.wrapped = BytesIO()
        self.closed = False

    @classmethod
    def __class_getitem__(cls, item):
        return cls

    async def write(self, data: bytes) -> int:
        return self.wrapped.write(data)

    async def read(self, n: int = -1) -> bytes:
        return self.wrapped.read(n)

    async def seek(self, offset: int, whence: int = 0) -> int:
        return self.wrapped.seek(offset, whence)

    async def aclose(self) -> None:
        self.closed = True
        self.wrapped.close()


def _make_png_bytes(size=(16, 16), color=(120, 10, 10), mode="RGB") -> bytes:
    img = Image.new(mode, size, color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


TEST_PASSWORD = "secret"
PASSWORD_CONTEXT = CryptContext(schemes=["argon2"], deprecated="auto")


@pytest.fixture()
def test_password() -> str:
    return TEST_PASSWORD


@pytest.fixture(scope="session")
def config_file() -> Path:
    password_hash = PASSWORD_CONTEXT.hash(TEST_PASSWORD)
    config_text = "\n".join(
        [
            "DEBUG = true",
            "CARROUSEL_SIZE = 2",
            "RESULTS_PER_IMAGE = 2",
            'ANIMAL_TYPES = ["bear", "squirrel"]',
            "",
            "[security]",
            f'PASSWORD_HASH = "{password_hash}"',
            'ACCESS_TOKEN_EXPIRE_TIME = 30',
            'SECRET_KEY = "test-secret-key-with-at-least-32-bytes"',
            'ALGORITHM = "HS256"',
            'TIMEZONE = "UTC"',
            "",
            "[storage]",
            "seafile = []",
            "",
        ]
    )
    path = Path(__file__).resolve().parents[1] / "backend" / "config.toml"
    prior = None
    if path.exists():
        prior = path.read_text(encoding="utf-8")
    path.write_text(config_text, encoding="utf-8")
    yield path
    if prior is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(prior, encoding="utf-8")


@pytest.fixture()
def mock_storage() -> MockStorage:
    return MockStorage()


@pytest.fixture(autouse=True)
def patch_spooled_tempfile(monkeypatch: pytest.MonkeyPatch):
    import backend.routes.jobqueue as jobqueue

    monkeypatch.setattr(jobqueue, "SpooledTemporaryFile", FakeSpooledTemporaryFile)


@pytest.fixture()
def api_module(config_file: Path, mock_storage: MockStorage):
    import backend.config as cfg

    cfg = importlib.reload(cfg)
    cfg.config.storage = [mock_storage]

    import backend.routes.api as api
    from backend.routes.jobqueue import JobQueue

    api = importlib.reload(api)
    api.SpooledTemporaryFile = FakeSpooledTemporaryFile
    api.job_queue = JobQueue(
        cfg.config.results_per_image, cfg.config.carrousel_size, mock_storage
    )
    return api


@pytest.fixture()
def app(api_module):
    from backend.routes import fracture_tool4

    app = FastAPI()
    app.include_router(api_module.router)
    app.include_router(fracture_tool4.router)
    return app


@pytest.fixture()
def sample_image_bytes() -> bytes:
    return _make_png_bytes()


@pytest.fixture()
def sample_overlay_bytes() -> bytes:
    return _make_png_bytes(mode="RGBA", color=(10, 10, 10, 180))


@pytest.fixture()
def make_upload_file():
    def _make(data: bytes, filename: str = "file.png") -> FakeUploadFile:
        return FakeUploadFile(data=data, filename=filename)

    return _make


@pytest.fixture()
def make_spooled_temp_file():
    def _make() -> FakeSpooledTemporaryFile:
        return FakeSpooledTemporaryFile()

    return _make


@pytest.fixture()
def reset_job_ids():
    from backend.routes.jobqueue import Job

    Job.c_id = 0
    yield
    Job.c_id = 0


@pytest.fixture()
def main_app(config_file: Path, mock_storage: MockStorage):
    import backend.config as cfg

    cfg = importlib.reload(cfg)
    cfg.config.storage = [mock_storage]

    import backend.routes.api as api

    importlib.reload(api)

    import backend.main as main

    return importlib.reload(main).app
