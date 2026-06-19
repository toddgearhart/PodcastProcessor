from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.audio import make_transcription_audio, process_audio
from app.config import Settings
from app.database import Database
from app.models import Job, JobStatus
from app.openai_service import generate_introduction
from app.transcription import Transcriber
from app.utils import build_public_url, compact_error, json_list
from app.wordpress import WordPressClient, build_post_content


logger = logging.getLogger(__name__)


class JobProcessor:
    def __init__(self, settings: Settings, database: Database):
        self.settings = settings
        self.database = database
        self.transcriber = Transcriber(settings)

    def claim_next_job(self) -> str | None:
        with self.database.session_factory.begin() as session:
            job = session.scalar(
                select(Job)
                .where(Job.status == JobStatus.QUEUED.value)
                .order_by(Job.created_at)
                .limit(1)
            )
            if job is None:
                return None
            job.status = JobStatus.PROCESSING_AUDIO.value
            job.attempts += 1
            job.error_message = ""
            return job.id

    def set_status(self, job_id: str, status: JobStatus) -> None:
        with self.database.session_factory.begin() as session:
            job = session.get(Job, job_id)
            if job:
                job.status = status.value

    def process_next(self) -> bool:
        job_id = self.claim_next_job()
        if not job_id:
            return False
        try:
            self.process(job_id)
        except Exception as error:
            logger.exception("Job failed", extra={"job_id": job_id})
            with self.database.session_factory.begin() as session:
                job = session.get(Job, job_id)
                if job:
                    job.status = JobStatus.FAILED.value
                    job.error_message = compact_error(error)
        return True

    def process(self, job_id: str) -> None:
        with self.database.session_factory() as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            year_dir = self.settings.podcast_dir / str(job.sermon_date.year)
            mp3_path = year_dir / f"{job.base_filename}.mp3"
            transcript_path = year_dir / f"{job.base_filename}.txt"
            work_dir = Path(job.source_wav).parent
            transcript_audio = work_dir / "transcription.wav"

            if not mp3_path.exists():
                process_audio(
                    Path(job.source_wav),
                    mp3_path,
                    title=job.title,
                    sermon_date=job.sermon_date.isoformat(),
                    speaker=job.speaker,
                    series=job.series,
                )
            job.mp3_url = build_public_url(
                self.settings.podcast_public_base_url,
                job.sermon_date.year,
                mp3_path.name,
            )
            session.commit()

            self.set_status(job_id, JobStatus.TRANSCRIBING)
            if not transcript_path.exists():
                make_transcription_audio(mp3_path, transcript_audio)
                transcript_text = self.transcriber.transcribe(transcript_audio)
                year_dir.mkdir(parents=True, exist_ok=True)
                temporary_text = transcript_path.with_suffix(".txt.partial")
                temporary_text.write_text(transcript_text + "\n", encoding="utf-8")
                temporary_text.replace(transcript_path)
            transcript_audio.unlink(missing_ok=True)
            job.transcript_url = build_public_url(
                self.settings.podcast_public_base_url,
                job.sermon_date.year,
                transcript_path.name,
            )
            session.commit()

            self.set_status(job_id, JobStatus.GENERATING_INTRO)
            if not job.introduction:
                transcript_text = transcript_path.read_text(encoding="utf-8")
                job.introduction = generate_introduction(
                    self.settings, job, transcript_text
                )
                session.commit()

            self.set_status(job_id, JobStatus.UPLOADING_SLIDES)
            wp = WordPressClient(self.settings)
            slides = [Path(path) for path in json_list(job.slides_json)]
            media = json_list(job.media_ids_json)
            uploaded_names = {item["filename"] for item in media}
            for position, slide in enumerate(slides, start=1):
                if slide.name not in uploaded_names:
                    media.append(
                        wp.upload_slide(slide, job.title, position, job.base_filename)
                    )
                    job.media_ids_json = json.dumps(media)
                    session.commit()

            self.set_status(job_id, JobStatus.CREATING_DRAFT)
            content = build_post_content(job)
            post = wp.save_draft(job, content)
            job.wordpress_post_id = int(post["id"])
            job.wordpress_edit_url = (
                f"{self.settings.wordpress_url}/wp-admin/post.php?post={job.wordpress_post_id}&action=edit"
            )
            job.status = JobStatus.SUCCEEDED.value
            job.completed_at = datetime.now(timezone.utc)
            session.commit()

        shutil.rmtree(work_dir, ignore_errors=True)
