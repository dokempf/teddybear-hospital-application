from __future__ import annotations

import asyncio

import pytest

from backend.routes.jobqueue import ConfirmJobEnum, Job, JobQueue


def test_queue_order_and_get(mock_storage, make_spooled_temp_file, reset_job_ids):
    async def run():
        queue = JobQueue(results_per_image=1, carrousel_size=2, storage=mock_storage)
        f1 = make_spooled_temp_file()
        f2 = make_spooled_temp_file()
        await f1.write(b"one")
        await f2.write(b"two")
        job1 = Job(
            file=f1,
            owner_ref=1,
            first_name="A",
            last_name="B",
            animal_name="Alpha",
        )
        job2 = Job(
            file=f2,
            owner_ref=2,
            first_name="C",
            last_name="D",
            animal_name="Beta",
        )
        queue.add_job(job1)
        queue.add_job(job2)
        assert queue.get_job() == job1
        assert queue.get_job() == job2
        assert queue.get_job() is None

    asyncio.run(run())


def test_submit_job_invalid_id_raises(mock_storage):
    async def run():
        queue = JobQueue(results_per_image=1, carrousel_size=1, storage=mock_storage)
        with pytest.raises(ValueError):
            await queue.submit_job(99, b"nope")

    asyncio.run(run())


def test_confirm_job_invalid_id_raises(mock_storage, make_spooled_temp_file):
    async def run():
        queue = JobQueue(results_per_image=1, carrousel_size=1, storage=mock_storage)
        f1 = make_spooled_temp_file()
        await f1.write(b"original")
        job = Job(
            file=f1,
            owner_ref=1,
            first_name="Test",
            last_name="User",
            animal_name="Bear",
        )
        queue.add_job(job)
        with pytest.raises(ValueError):
            await queue.confirm_job(999, ConfirmJobEnum.confirm, 0, None)

    asyncio.run(run())


def test_confirm_job_confirm_uploads_and_carousel(
    mock_storage, make_spooled_temp_file, reset_job_ids
):
    async def run():
        queue = JobQueue(results_per_image=1, carrousel_size=1, storage=mock_storage)
        f1 = make_spooled_temp_file()
        await f1.write(b"original")
        job = Job(
            file=f1,
            owner_ref="link",
            first_name="Test",
            last_name="User",
            animal_name="Bear",
        )
        queue.add_job(job)
        await queue.submit_job(job.id, b"result")
        await queue.confirm_job(job.id, ConfirmJobEnum.confirm, 0, None)
        assert len(queue.awaiting_approval) == 0
        assert len(queue.carrousel) == 1
        assert len(mock_storage.uploads) == 2

    asyncio.run(run())


def test_confirm_job_enforces_carousel_size(
    mock_storage, make_spooled_temp_file, reset_job_ids
):
    async def run():
        queue = JobQueue(results_per_image=1, carrousel_size=1, storage=mock_storage)
        for owner in [1, 2]:
            f = make_spooled_temp_file()
            await f.write(b"original")
            job = Job(
                file=f,
                owner_ref=owner,
                first_name="Test",
                last_name="User",
                animal_name="Bear",
            )
            queue.add_job(job)
            await queue.submit_job(job.id, b"result")
            await queue.confirm_job(job.id, ConfirmJobEnum.confirm, 0, None)
        assert len(queue.carrousel) == 1

    asyncio.run(run())


def test_confirm_job_retry_requeues(mock_storage, make_spooled_temp_file, reset_job_ids):
    async def run():
        queue = JobQueue(results_per_image=2, carrousel_size=1, storage=mock_storage)
        f1 = make_spooled_temp_file()
        await f1.write(b"original")
        job = Job(
            file=f1,
            owner_ref=1,
            first_name="Test",
            last_name="User",
            animal_name="Bear",
        )
        queue.add_job(job)
        await queue.submit_job(job.id, b"result")
        await queue.confirm_job(job.id, ConfirmJobEnum.retry, 0, None)
        assert job in queue.queue
        assert job.id in queue.awaiting_approval
        assert job.number_of_results == queue.results_per_image

    asyncio.run(run())

def test_confirm_job_cancel_removes(mock_storage, make_spooled_temp_file, reset_job_ids):
    async def run():
        queue = JobQueue(results_per_image=1, carrousel_size=1, storage=mock_storage)
        f1 = make_spooled_temp_file()
        await f1.write(b"original")
        job = Job(
            file=f1,
            owner_ref=1,
            first_name="Test",
            last_name="User",
            animal_name="Bear",
        )
        queue.add_job(job)
        await queue.submit_job(job.id, b"result")
        await queue.confirm_job(job.id, ConfirmJobEnum.cancel, 0, None)
        assert job not in queue.queue
        assert job.id not in queue.awaiting_approval

    asyncio.run(run())

def test_confirm_job_replaces_image(
    mock_storage, make_upload_file, make_spooled_temp_file, reset_job_ids
):
    async def run():
        queue = JobQueue(results_per_image=1, carrousel_size=1, storage=mock_storage)
        f1 = make_spooled_temp_file()
        await f1.write(b"original")
        job = Job(
            file=f1,
            owner_ref="link",
            first_name="Test",
            last_name="User",
            animal_name="Bear",
        )
        queue.add_job(job)
        await queue.submit_job(job.id, b"old-result")
        replacement = make_upload_file(b"override", "override.png")
        await queue.confirm_job(job.id, ConfirmJobEnum.confirm, 0, replacement)
        uploaded = [u for u in mock_storage.uploads if u["type"] == "xray"][0]
        assert uploaded["filename"] == f"{job.id}_result.png"

    asyncio.run(run())
