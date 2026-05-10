import asyncio
import time

from yunmon_control_plane.jobs import JobManager, JobStatus


def test_job_run_succeeds():
    manager = JobManager(max_workers=2)

    def _work(ctx):
        ctx.log("step 1")
        ctx.progress(50)
        return {"ok": True}

    job = manager.submit("unit", _work)
    deadline = time.time() + 5
    while time.time() < deadline and manager.get(job.id).status not in {JobStatus.succeeded, JobStatus.failed}:
        time.sleep(0.05)
    final = manager.get(job.id)
    assert final.status is JobStatus.succeeded
    assert final.result == {"ok": True}


def test_job_run_failure_records_error():
    manager = JobManager(max_workers=2)

    def _work(_):
        raise RuntimeError("boom")

    job = manager.submit("unit-fail", _work)
    deadline = time.time() + 5
    while time.time() < deadline and manager.get(job.id).status not in {JobStatus.succeeded, JobStatus.failed}:
        time.sleep(0.05)
    final = manager.get(job.id)
    assert final.status is JobStatus.failed
    assert final.error == "boom"


def test_job_stream_yields_end_event():
    manager = JobManager(max_workers=2)

    def _work(ctx):
        ctx.log("running")
        return "done"

    job = manager.submit("stream", _work)

    async def _collect():
        events = []
        async for event in manager.stream(job.id):
            events.append(event)
            if event["event"] == "end":
                break
        return events

    events = asyncio.run(_collect())
    assert any(e["event"] == "end" for e in events)
