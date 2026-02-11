from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from seafileapi.exceptions import ClientHttpError

from backend.seafile.main import Repo, SeafileAPI, parse_response


class DummyResponse:
    def __init__(
        self,
        status_code: int = 200,
        payload: dict | list | str | None = None,
        *,
        text: str | None = None,
        content: bytes | None = None,
    ):
        self.status_code = status_code
        if text is not None:
            self.text = text
            self._json_payload = payload
        elif isinstance(payload, str):
            self.text = payload
            self._json_payload = None
        elif payload is None:
            self.text = "{}"
            self._json_payload = {}
        else:
            self.text = json.dumps(payload)
            self._json_payload = payload
        self.content = content if content is not None else self.text.encode("utf-8")

    def json(self):
        if self._json_payload is not None:
            return self._json_payload
        return json.loads(self.text)


def _make_repo(by_api_token: bool) -> Repo:
    repo = Repo.__new__(Repo)
    repo.server_url = "https://server"
    repo.token = "token"
    repo.repo_id = "repo-1"
    repo.timeout = 5
    repo.headers = {"Authorization": "Bearer token"}
    repo._by_api_token = by_api_token
    return repo


def test_parse_response_success_and_error():
    assert parse_response(DummyResponse(200, {"ok": True})) == {"ok": True}
    with pytest.raises(ConnectionError):
        parse_response(DummyResponse(400, {"error": "nope"}))


def test_repo_init_success_and_server_info_failure(monkeypatch):
    responses = [
        DummyResponse(200, {"version": "12.0.0"}),
        DummyResponse(
            200,
            {
                "repo_id": "r1",
                "repo_name": "name",
                "size": 1,
                "file_count": 2,
                "last_modified": "now",
            },
        ),
    ]
    monkeypatch.setattr(
        "backend.seafile.main.requests.get", lambda *a, **k: responses.pop(0)
    )
    repo = Repo(token="t", server_url="https://server", by_api_token=True, timeout=5)
    assert repo.version == "12.0.0"
    assert repo.repo_id == "r1"
    assert repo.name == "name"

    monkeypatch.setattr(
        "backend.seafile.main.requests.get",
        lambda *a, **k: DummyResponse(500, {"msg": "down"}),
    )
    with pytest.raises(ClientHttpError):
        Repo(token="t", server_url="https://server", by_api_token=True, timeout=5)


def test_repo_auth_and_url_builders():
    repo = _make_repo(by_api_token=True)
    repo.version = "10.0.0"
    repo.auth()
    assert repo.headers["Authorization"].startswith("Token ")
    repo.version = "11.0.0"
    repo.auth()
    assert repo.headers["Authorization"].startswith("Bearer ")
    assert repo._repo_info_url().endswith("/api/v2.1/via-repo-token/repo-info/")
    assert repo._repo_dir_url().endswith("/api/v2.1/via-repo-token/dir/")
    assert repo._repo_file_url().endswith("/api/v2.1/via-repo-token/file/")
    assert repo._repo_upload_link_url().endswith("/api/v2.1/via-repo-token/upload-link/")
    assert repo._repo_download_link_url().endswith(
        "/api/v2.1/via-repo-token/download-link/"
    )

    repo._by_api_token = False
    assert repo._repo_info_url().endswith("/api/v2.1/repos/repo-1/")
    assert repo._repo_dir_url().endswith("/api2/repos/repo-1/dir/")
    assert repo._repo_file_url().endswith("/api/v2.1/repos/repo-1/file/")
    assert repo._repo_upload_link_url().endswith("/api2/repos/repo-1/upload-link/")
    assert repo._repo_download_link_url().endswith("/api2/repos/repo-1/file/")


def test_repo_dir_and_file_ops_by_api_token(monkeypatch):
    repo = _make_repo(by_api_token=True)
    captured: list[tuple[str, dict]] = []

    def fake_get(url, **kwargs):
        captured.append(("get", kwargs))
        if url.endswith("repo-info/"):
            return DummyResponse(200, {"repo_id": "r1"})
        if "dir/" in url:
            return DummyResponse(200, {"dirent_list": [{"name": "x"}]})
        return DummyResponse(200, {"ok": True})

    def fake_post(url, **kwargs):
        captured.append(("post", kwargs))
        return DummyResponse(200, {"ok": True})

    def fake_delete(url, **kwargs):
        captured.append(("delete", kwargs))
        return DummyResponse(200, {"ok": True})

    monkeypatch.setattr("backend.seafile.main.requests.get", fake_get)
    monkeypatch.setattr("backend.seafile.main.requests.post", fake_post)
    monkeypatch.setattr("backend.seafile.main.requests.delete", fake_delete)

    details = repo.get_repo_details()
    assert details["repo_id"] == "r1"
    assert repo.list_dir("/") == [{"name": "x"}]
    repo.create_dir("/p")
    repo.rename_dir("/p", "n")
    repo.delete_dir("/p")
    repo.get_file("/f")
    repo.create_file("/f")
    repo.rename_file("/f", "n")
    repo.delete_file("/f")
    assert any(call[1].get("params") == {"path": "/p"} for call in captured)


def test_repo_dir_and_file_ops_without_api_token(monkeypatch):
    repo = _make_repo(by_api_token=False)
    seen_get_params = []
    seen_post_params = []
    seen_delete_params = []

    def fake_get(url, **kwargs):
        seen_get_params.append(kwargs.get("params"))
        if "file/detail" in url:
            return DummyResponse(200, {"name": "f"})
        return DummyResponse(200, [{"name": "dir"}])

    def fake_post(url, **kwargs):
        seen_post_params.append(kwargs.get("params"))
        return DummyResponse(200, {"ok": True})

    def fake_delete(url, **kwargs):
        seen_delete_params.append(kwargs.get("params"))
        return DummyResponse(200, {"ok": True})

    monkeypatch.setattr("backend.seafile.main.requests.get", fake_get)
    monkeypatch.setattr("backend.seafile.main.requests.post", fake_post)
    monkeypatch.setattr("backend.seafile.main.requests.delete", fake_delete)

    assert repo.list_dir("/") == [{"name": "dir"}]
    repo.create_dir("/p")
    repo.rename_dir("/p", "n")
    repo.delete_dir("/p")
    repo.get_file("/f")
    repo.create_file("/f")
    repo.rename_file("/f", "n")
    repo.delete_file("/f")
    assert {"p": "/p"} in seen_post_params
    assert {"p": "/p"} in seen_delete_params
    assert {"p": "/f"} in seen_get_params


def test_repo_upload_file_success_with_stream_and_path(monkeypatch, tmp_path: Path):
    repo = _make_repo(by_api_token=False)
    temp = tmp_path / "f.bin"
    temp.write_bytes(b"abc")
    called = {"posts": 0}

    monkeypatch.setattr(
        "backend.seafile.main.requests.get",
        lambda *a, **k: DummyResponse(200, payload="\"https://upload\""),
    )

    def fake_post(url, **kwargs):
        called["posts"] += 1
        assert url.endswith("?ret-json=1")
        return DummyResponse(200, [{"name": "ok"}])

    monkeypatch.setattr("backend.seafile.main.requests.post", fake_post)
    assert repo.upload_file("/", BytesIO(b"abc"))["name"] == "ok"
    assert repo.upload_file("/", str(temp))["name"] == "ok"
    assert called["posts"] == 2


def test_repo_upload_file_error(monkeypatch):
    repo = _make_repo(by_api_token=True)
    monkeypatch.setattr(
        "backend.seafile.main.requests.get",
        lambda *a, **k: DummyResponse(200, payload="\"https://upload\""),
    )
    monkeypatch.setattr(
        "backend.seafile.main.requests.post", lambda *a, **k: DummyResponse(500, {})
    )
    with pytest.raises(Exception):
        repo.upload_file("/", BytesIO(b"abc"))


def test_repo_download_file_success_and_error(monkeypatch, tmp_path: Path):
    repo = _make_repo(by_api_token=True)
    calls = {"step": 0}

    def fake_get(url, **kwargs):
        calls["step"] += 1
        if calls["step"] == 1:
            return DummyResponse(200, payload="https://download", text="\"https://download\"")
        return DummyResponse(200, payload={}, content=b"file-data")

    monkeypatch.setattr("backend.seafile.main.requests.get", fake_get)
    out = tmp_path / "download.bin"
    repo.download_file("/f", out)
    assert out.read_bytes() == b"file-data"

    calls["step"] = 0

    def fake_get_error(url, **kwargs):
        calls["step"] += 1
        if calls["step"] == 1:
            return DummyResponse(200, payload="https://download", text="\"https://download\"")
        return DummyResponse(500, payload={}, content=b"")

    monkeypatch.setattr("backend.seafile.main.requests.get", fake_get_error)
    with pytest.raises(Exception):
        repo.download_file("/f", out)


def test_repo_shared_link_creation_paths(monkeypatch):
    repo = _make_repo(by_api_token=False)
    repo.repo_id = "repo-1"

    repo.get_shared_links = lambda path: [
        {
            "is_expired": False,
            "permissions": {
                "can_edit": False,
                "can_download": True,
                "can_upload": False,
            },
            "link": "https://existing",
            "token": "t1",
        }
    ]
    assert repo.create_shared_link("/x") == "https://existing"

    deleted = []
    posted = {}
    repo.get_shared_links = lambda path: [
        {
            "is_expired": False,
            "permissions": {
                "can_edit": True,
                "can_download": True,
                "can_upload": False,
            },
            "link": "https://old",
            "token": "t2",
        }
    ]
    repo.delete_shared_link = lambda token: deleted.append(token)

    def fake_post(url, **kwargs):
        posted["url"] = url
        posted["payload"] = kwargs["json"]
        return DummyResponse(200, {"link": "https://new"})

    monkeypatch.setattr("backend.seafile.main.requests.post", fake_post)
    link = repo.create_shared_link("/x", password="p", expire_days=1)
    assert link == "https://new"
    assert deleted == ["t2"]
    assert posted["payload"]["repo_id"] == "repo-1"
    assert posted["payload"]["password"] == "p"
    assert posted["payload"]["expire_days"] == 1

    repo._by_api_token = True
    repo.get_shared_links = lambda path: None
    posted.clear()
    link = repo.create_shared_link("/x", can_upload=True)
    assert link == "https://new"
    assert "via-repo-token" in posted["url"]
    assert "repo_id" not in posted["payload"]


def test_repo_shared_link_fetch_delete_metadata_and_library(monkeypatch):
    repo = _make_repo(by_api_token=True)
    assert repo.get_shared_links("/x") is None

    repo._by_api_token = False
    monkeypatch.setattr(
        "backend.seafile.main.requests.get",
        lambda *a, **k: DummyResponse(200, [{"link": "x"}]),
    )
    assert repo.get_shared_links("/x")[0]["link"] == "x"

    deleted = {}
    def fake_delete_shared(url, **kwargs):
        deleted["url"] = url
        return DummyResponse(200, {"ok": True})

    monkeypatch.setattr("backend.seafile.main.requests.delete", fake_delete_shared)
    repo.delete_shared_link("token-1")
    assert deleted["url"].endswith("/token-1/")

    monkeypatch.setattr(
        "backend.seafile.main.requests.get",
        lambda *a, **k: DummyResponse(200, {"path": "/base"}),
    )
    assert repo.get_share_link_metadata("https://x/s/abc/")["path"] == "/base"

    repo._by_api_token = True
    with pytest.raises(NotImplementedError):
        repo.get_shared_link_library()

    repo._by_api_token = False
    monkeypatch.setattr(
        "backend.seafile.main.requests.get", lambda *a, **k: DummyResponse(500, {"x": 1})
    )
    with pytest.raises(ConnectionError):
        repo.get_shared_link_library()

    monkeypatch.setattr(
        "backend.seafile.main.requests.get",
        lambda *a, **k: DummyResponse(200, [{"link": "ok"}]),
    )
    assert repo.get_shared_link_library()[0]["link"] == "ok"


def test_repo_upload_file_via_upload_link_success_and_error(monkeypatch, tmp_path: Path):
    repo = _make_repo(by_api_token=False)
    repo.get_share_link_metadata = lambda link: {"path": "/base"}

    monkeypatch.setattr(
        "backend.seafile.main.requests.get",
        lambda *a, **k: DummyResponse(200, {"upload_link": "https://upload"}),
    )
    monkeypatch.setattr(
        "backend.seafile.main.requests.post",
        lambda *a, **k: DummyResponse(200, [{"name": "done"}]),
    )
    assert (
        repo.upload_file_via_upload_link("https://x/s/tok/", "/x", BytesIO(b"f"), "f.png")[
            "name"
        ]
        == "done"
    )

    p = tmp_path / "f.bin"
    p.write_bytes(b"data")
    assert (
        repo.upload_file_via_upload_link("https://x/s/tok/", "/x", str(p), "f.bin")[
            "name"
        ]
        == "done"
    )

    monkeypatch.setattr(
        "backend.seafile.main.requests.post", lambda *a, **k: DummyResponse(500, {"x": 1})
    )
    with pytest.raises(ConnectionError):
        repo.upload_file_via_upload_link("https://x/s/tok/", "/x", BytesIO(b"f"), "f.png")


def test_seafile_api_init_paths(monkeypatch):
    with pytest.raises(ValueError):
        SeafileAPI(server_url="https://server")

    monkeypatch.setattr(
        "backend.seafile.main.requests.get", lambda *a, **k: DummyResponse(500, {"x": 1})
    )
    with pytest.raises(ClientHttpError):
        SeafileAPI(server_url="https://server", login_name="u", password="p")

    monkeypatch.setattr(
        "backend.seafile.main.requests.get",
        lambda *a, **k: DummyResponse(200, {"version": "12.0.0"}),
    )
    api = SeafileAPI(server_url="https://server///", account_token="x" * 40)
    assert api.server_url == "https://server"
    assert api.version == "12.0.0"


def test_seafile_api_repo_obj_and_auth(monkeypatch):
    api = SeafileAPI.__new__(SeafileAPI)
    api.server_url = "https://server"
    api.timeout = 5
    api.version = "10.0.0"
    api.login_name = "u"
    api.password = "p"
    api.headers = None
    api.token = None

    with pytest.raises(AssertionError):
        api._repo_obj("r1")

    monkeypatch.setattr(
        "backend.seafile.main.requests.post",
        lambda *a, **k: DummyResponse(200, {"token": "x" * 40}),
    )
    api.auth()
    assert api.token == "x" * 40
    assert api.headers["Authorization"].startswith("Token ")

    monkeypatch.setattr("backend.seafile.main.Repo", lambda **kwargs: {"repo": kwargs})
    repo_obj = api._repo_obj("r1")
    assert repo_obj["repo"]["repo_id"] == "r1"

    api2 = SeafileAPI.__new__(SeafileAPI)
    api2.server_url = "https://server"
    api2.timeout = 5
    api2.version = "12.0.0"
    api2.headers = None
    api2.token = "x" * 40
    api2.auth()
    assert api2.headers["Authorization"].startswith("Bearer ")

    api3 = SeafileAPI.__new__(SeafileAPI)
    api3.server_url = "https://server"
    api3.timeout = 5
    api3.version = "12.0.0"
    api3.login_name = "u"
    api3.password = "p"
    api3.token = None
    monkeypatch.setattr(
        "backend.seafile.main.requests.post", lambda *a, **k: DummyResponse(500, {"x": 1})
    )
    with pytest.raises(ClientHttpError):
        api3.auth()

    api4 = SeafileAPI.__new__(SeafileAPI)
    api4.server_url = "https://server"
    api4.timeout = 5
    api4.version = "10.0.0"
    api4.login_name = "u"
    api4.password = "p"
    api4.token = None
    monkeypatch.setattr(
        "backend.seafile.main.requests.post",
        lambda *a, **k: DummyResponse(200, {"token": "short"}),
    )
    with pytest.raises(AssertionError):
        api4.auth()


def test_seafile_api_repo_list_get_create_delete(monkeypatch):
    api = SeafileAPI.__new__(SeafileAPI)
    api.server_url = "https://server"
    api.timeout = 5
    api.headers = {"Authorization": "Bearer t"}
    api.token = "x" * 40

    repo_payload = [
        {
            "type": "mine",
            "id": "r1",
            "owner": "o",
            "owner_name": "owner",
            "owner_contact_email": "o@example.com",
            "name": "repo",
            "mtime": 1,
            "modifier_email": "m@example.com",
            "modifier_contact_email": "m@example.com",
            "modifier_name": "mod",
            "mtime_relative": "now",
            "size": 1,
            "size_formatted": "1B",
            "encrypted": False,
            "permission": "rw",
            "virtual": False,
            "root": "/",
            "head_commit_id": "h",
            "version": 1,
            "salt": "s",
            "groupid": None,
        }
    ]
    monkeypatch.setattr(
        "backend.seafile.main.requests.get", lambda *a, **k: DummyResponse(200, repo_payload)
    )
    repos = api.list_repos()
    assert repos[0].id == "r1"

    monkeypatch.setattr(
        "backend.seafile.main.requests.get", lambda *a, **k: DummyResponse(200, {"id": "r1"})
    )
    api._repo_obj = lambda rid: f"repo:{rid}"
    assert api.get_repo("r1") == "repo:r1"

    posted = {}

    def fake_post(url, **kwargs):
        posted["json"] = kwargs["json"]
        return DummyResponse(200, {"repo_id": "r9"})

    monkeypatch.setattr("backend.seafile.main.requests.post", fake_post)
    api._repo_obj = lambda rid: {"id": rid}
    created = api.create_repo("new", passwd="pw", story_id="story")
    assert created["id"] == "r9"
    assert posted["json"]["passwd"] == "pw"
    assert posted["json"]["story_id"] == "story"

    monkeypatch.setattr(
        "backend.seafile.main.requests.post", lambda *a, **k: DummyResponse(500, {"x": 1})
    )
    with pytest.raises(ConnectionError):
        api.create_repo("new")

    deleted = {}
    def fake_delete_repo(url, **kwargs):
        deleted["url"] = url
        return DummyResponse(200, {"ok": True})

    monkeypatch.setattr("backend.seafile.main.requests.delete", fake_delete_repo)
    assert api.delete_repo("r1") is True
    assert deleted["url"].endswith("/api2/repos/r1/")
