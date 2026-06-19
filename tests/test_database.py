from datetime import date

from app.config import Settings
from app.database import Database
from app.models import Job, JobStatus


def test_interrupted_jobs_are_requeued(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        podcast_dir=tmp_path / "podcasts",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
    )
    database = Database(settings)
    database.create_schema()
    job = Job(
        sermon_date=date(2026, 6, 19),
        title="Test",
        base_filename="2026_06_19_Test",
        source_wav=str(tmp_path / "source.wav"),
        status=JobStatus.TRANSCRIBING.value,
    )
    with database.session_factory.begin() as session:
        session.add(job)

    database.recover_interrupted_jobs()

    with database.session_factory() as session:
        recovered = session.get(Job, job.id)
        assert recovered.status == JobStatus.QUEUED.value
        assert "restart" in recovered.error_message

