from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import BackgroundTasks, HTTPException
from PIL import Image

from backend.routes.jobqueue import ConfirmJobEnum


def _run(coro):
    return asyncio.run(coro)


class DummyRequest:
    def url_for(self, name: str, **kwargs) -> str:
        if name == "get_result_image":
            return f"http://test/results/{kwargs['job_id']}/{kwargs['option']}"
        if name == "get_carousel_image":
            return f"http://test/carousel/{kwargs['index']}/{kwargs['option']}"
        raise AssertionError(f"unknown route name {name}")


def test_login_and_validate_token(api_module, test_password):
    token = _run(api_module.login(test_password))
    assert token.token_type == "bearer"
    assert api_module.validate_token(token.access_token) is True
    with pytest.raises(HTTPException):
        api_module.validate_token("invalid-token")


def test_hash_password(api_module):
    hashed = api_module.hash_password("abc")
    assert isinstance(hashed, str)
    assert hashed != "abc"


def test_login_invalid_password_raises(api_module):
    with pytest.raises(HTTPException) as exc:
        _run(api_module.login("wrong"))
    assert exc.value.status_code == 401


def test_create_upload_get_job_submit_results_and_confirm(
    api_module, sample_image_bytes, mock_storage, make_upload_file, reset_job_ids
):
    upload = _run(
        api_module.create_upload_file(
            file=make_upload_file(sample_image_bytes, "img.png"),
            first_name="Test",
            last_name="User",
            animal_name="Teddy",
            qr_content="qr-link",
            valid=True,
            animal_type="bear",
            broken_bone=False,
        )
    )
    job_id = upload["job_id"]
    assert upload["status"] == "success"

    first = _run(api_module.get_job(valid=True))
    assert first.status_code == 200
    assert first.headers["img_id"] == str(job_id)
    second = _run(api_module.get_job(valid=True))
    assert second.status_code == 200
    none_left = _run(api_module.get_job(valid=True))
    assert none_left.status_code == 204

    submit = _run(
        api_module.conclude_job(
            image_id=job_id,
            result=make_upload_file(sample_image_bytes, "result.png"),
            valid=True,
        )
    )
    assert submit["status"] == "success"

    results = _run(api_module.get_results(valid=True, request=DummyRequest()))
    payload = results.body.decode("utf-8")
    assert str(job_id) in payload

    confirm = _run(
        api_module.confirm_job(
            image_id=job_id,
            choice=0,
            confirm=ConfirmJobEnum.confirm,
            valid=True,
            image=None,
        )
    )
    assert confirm.status_code == 200
    assert len(mock_storage.uploads) == 2


def test_apply_fracture_queue_success_and_errors(
    api_module,
    monkeypatch,
    sample_image_bytes,
    sample_overlay_bytes,
    make_upload_file,
    reset_job_ids,
):
    with pytest.raises(HTTPException) as missing:
        _run(
            api_module.get_fracture_queue(
                valid=True,
                job_id=999,
                choice=0,
                overlay_file=make_upload_file(sample_overlay_bytes, "overlay.png"),
                x=1,
                y=1,
                scale=1.0,
                noise=1,
            )
        )
    assert missing.value.status_code == 404

    created = _run(
        api_module.create_upload_file(
            file=make_upload_file(sample_image_bytes, "img.png"),
            first_name="A",
            last_name="B",
            animal_name="C",
            qr_content="qr",
            valid=True,
            animal_type="other",
            broken_bone=False,
        )
    )
    job_id = created["job_id"]
    _run(api_module.get_job(valid=True))
    _run(
        api_module.conclude_job(
            image_id=job_id,
            result=make_upload_file(sample_image_bytes, "result.png"),
            valid=True,
        )
    )

    with pytest.raises(HTTPException) as invalid_choice:
        _run(
            api_module.get_fracture_queue(
                valid=True,
                job_id=job_id,
                choice=5,
                overlay_file=make_upload_file(sample_overlay_bytes, "overlay.png"),
                x=1,
                y=1,
                scale=1.0,
                noise=1,
            )
        )
    assert invalid_choice.value.status_code == 400

    monkeypatch.setattr(api_module, "apply_fracture", lambda **kwargs: kwargs["img"])
    ok = _run(
        api_module.get_fracture_queue(
            valid=True,
            job_id=job_id,
            choice=0,
            overlay_file=make_upload_file(sample_overlay_bytes, "overlay.png"),
            x=1,
            y=1,
            scale=1.0,
            noise=1,
        )
    )
    assert ok.status_code == 200


def test_result_image_and_carousel_endpoints(
    api_module, sample_image_bytes, mock_storage, make_upload_file, reset_job_ids
):
    created = _run(
        api_module.create_upload_file(
            file=make_upload_file(sample_image_bytes, "img.png"),
            first_name="A",
            last_name="B",
            animal_name="C",
            qr_content="qr",
            valid=True,
            animal_type="bear",
            broken_bone=False,
        )
    )
    job_id = created["job_id"]
    _run(api_module.get_job(valid=True))
    _run(
        api_module.conclude_job(
            image_id=job_id,
            result=make_upload_file(sample_image_bytes, "result.png"),
            valid=True,
        )
    )

    result_img = _run(api_module.get_result_image(job_id=job_id, option="0"))
    assert result_img.status_code == 200
    original_img = _run(api_module.get_result_image(job_id=job_id, option="original"))
    assert original_img.status_code == 200

    _run(
        api_module.confirm_job(
            image_id=job_id,
            choice=0,
            confirm=ConfirmJobEnum.confirm,
            valid=True,
            image=None,
        )
    )
    carousel = _run(api_module.get_carousel_list(request=DummyRequest()))
    body = carousel.body.decode("utf-8")
    assert "/carousel/0/original" in body
    assert "/carousel/0/xray" in body

    xray = _run(api_module.get_carousel_image(index=0, option="xray"))
    assert xray.status_code == 200
    original = _run(api_module.get_carousel_image(index=0, option="original"))
    assert original.status_code == 200
    missing = _run(api_module.get_carousel_image(index=99, option="xray"))
    assert missing.status_code == 404
    assert len(mock_storage.uploads) == 2


def test_qr_routes_and_progress(api_module, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    called = {}

    def fake_get_qrs(n):
        called["n"] = n
        api_module.qr_generation_progress = 100.0
        Path("qr.pdf").write_bytes(b"%PDF-1.4\n%EOF\n")

    monkeypatch.setattr(api_module, "get_qrs", fake_get_qrs)
    background = BackgroundTasks()
    response = api_module.gen_qr_codes(n=2, valid=True, background_tasks=background)
    assert response.status_code == 200
    assert len(background.tasks) == 1
    fake_get_qrs(2)
    assert called["n"] == 2

    progress = api_module.get_qr_progress(valid=True)
    assert progress.status_code == 200
    assert b"100.0" in progress.body

    download = api_module.download_qr_pdf(valid=True)
    assert download.status_code == 200


def test_get_qrs_builds_qr_list(api_module, mock_storage, monkeypatch):
    created_urls = []
    generated = {}

    class FakeQR:
        def __init__(self, **kwargs):
            self.data = None

        def add_data(self, data):
            self.data = data

        def make(self, fit=True):
            return None

        def make_image(self, fill_color, back_color):
            created_urls.append(self.data)
            return object()

        def clear(self):
            return None

    monkeypatch.setattr(api_module.qrcode, "QRCode", FakeQR)
    monkeypatch.setattr(
        api_module, "gen_qr_pdf", lambda qrs: generated.setdefault("count", len(qrs))
    )
    api_module.config.storage = [mock_storage]

    api_module.get_qrs(3)
    assert generated["count"] == 3
    assert len(created_urls) == 3
    assert api_module.qr_generation_progress < 100.0


def test_gen_qr_pdf_multi_page(api_module, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    images = [Image.new("RGB", (2, 2), (i, i, i)) for i in range(40)]
    api_module.gen_qr_pdf(images, size=100)
    assert (tmp_path / "qr.pdf").exists()
    assert api_module.qr_generation_progress == 100.0


def test_animal_types_and_verify_token(api_module):
    assert api_module.verify_token(True) is True
    animal_types = api_module.get_animal_types()
    assert animal_types.status_code == 200
    assert b"other" in animal_types.body
