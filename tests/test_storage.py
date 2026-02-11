from __future__ import annotations

from io import BytesIO

import pytest

from backend.storage.storage import SeafileStorage, Storage


class DummyRepo:
    def __init__(self, version="12.0.0"):
        self.version = version
        self.created_dirs: list[str] = []
        self.uploads: list[tuple] = []

    def list_dir(self, path="/"):
        return [{"name": "2"}, {"name": "notes"}]

    def create_dir(self, path: str):
        self.created_dirs.append(path)

    def create_shared_link(self, path: str, can_upload: bool = False) -> str:
        return f"link:{path}:{can_upload}"

    def upload_file(self, path, file_path):
        self.uploads.append(("upload_file", path, file_path))

    def upload_file_via_upload_link(self, link, path, file_path, filename):
        self.uploads.append(("upload_link", link, path, filename, file_path))


class DummyRepoInfo:
    def __init__(self, repo_id: str, name: str):
        self.id = repo_id
        self.name = name


class DummyAPI:
    def __init__(self, *args, **kwargs):
        self.repos = [DummyRepoInfo("r1", "library")]
        self.authed = False

    def auth(self):
        self.authed = True

    def list_repos(self):
        return self.repos

    def get_repo(self, repo_id: str):
        return DummyRepo()

    def create_repo(self, name: str):
        return DummyRepo()


class DummyAPIWithoutRepo(DummyAPI):
    def __init__(self, *args, **kwargs):
        self.repos = []
        self.authed = False


class DummyStorageSubclass(Storage):
    def create_storage_for_user(self) -> str:
        return super().create_storage_for_user()

    def upload_file(self, user_id, type, file_path, filename):
        return super().upload_file(user_id, type, file_path, filename)


def test_seafile_storage_requires_credentials():
    with pytest.raises(ValueError):
        SeafileStorage(server_url="https://example.invalid", library_name="lib")


def test_seafile_storage_initializes_and_creates_dirs(monkeypatch):
    monkeypatch.setattr("backend.storage.storage.SeafileAPI", DummyAPI)

    storage = SeafileStorage(
        server_url="https://example.invalid",
        library_name="library",
        username="user",
        password="pass",
    )
    assert storage._id == 3
    link = storage.create_storage_for_user()
    assert link == "link:/3:True"
    assert storage._repo.created_dirs == ["/3", "/3/normal", "/3/xray"]


def test_storage_abstract_methods_body_executes():
    storage = DummyStorageSubclass()
    assert storage.create_storage_for_user() is None
    assert storage.upload_file(1, "normal", BytesIO(b"x"), "x.png") is None


def test_seafile_storage_upload_file(monkeypatch):
    repo = DummyRepo()
    storage = SeafileStorage.__new__(SeafileStorage)
    storage._repo = repo
    storage._id = 1

    storage.upload_file(1, "normal", BytesIO(b"data"), "file.png")
    storage.upload_file("link", "xray", BytesIO(b"data"), "file.png")

    assert repo.uploads[0][0] == "upload_file"
    assert repo.uploads[0][1] == "/1/normal"
    assert repo.uploads[1][0] == "upload_link"


def test_seafile_storage_repo_token_version_check(monkeypatch):
    monkeypatch.setattr("backend.storage.storage.Repo", lambda **kwargs: DummyRepo("11.0.0"))
    with pytest.raises(ValueError):
        SeafileStorage(
            server_url="https://example.invalid",
            library_name="library",
            repo_token="token",
        )


def test_seafile_storage_create_repo_when_missing(monkeypatch):
    monkeypatch.setattr("backend.storage.storage.SeafileAPI", DummyAPIWithoutRepo)
    storage = SeafileStorage(
        server_url="https://example.invalid",
        library_name="library",
        username="user",
        password="pass",
    )
    assert isinstance(storage._repo, DummyRepo)


def test_seafile_storage_account_token_branch(monkeypatch):
    monkeypatch.setattr("backend.storage.storage.SeafileAPI", DummyAPIWithoutRepo)
    storage = SeafileStorage(
        server_url="https://example.invalid",
        library_name="library",
        account_token="token",
    )
    assert isinstance(storage._repo, DummyRepo)


def test_seafile_storage_account_token_existing_repo(monkeypatch):
    monkeypatch.setattr("backend.storage.storage.SeafileAPI", DummyAPI)
    storage = SeafileStorage(
        server_url="https://example.invalid",
        library_name="library",
        account_token="token",
    )
    assert isinstance(storage._repo, DummyRepo)
