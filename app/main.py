from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.middleware.sessions import SessionMiddleware

from app.audio import AudioError, commands_available, probe_audio
from app.auth import csrf_token, require_csrf, require_login, verify_login
from app.config import get_settings
from app.database import Database
from app.logging_config import configure_logging
from app.models import Job, JobStatus
from app.pipeline import JobProcessor
from app.utils import build_base_filename, natural_sort_key


settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
settings.ensure_directories()
database = Database(settings)
processor = JobProcessor(settings, database)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


async def worker_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        did_work = await asyncio.to_thread(processor.process_next)
        if not did_work:
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
            except TimeoutError:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.create_schema()
    database.recover_interrupted_jobs()
    app.state.stop_worker = asyncio.Event()
    app.state.worker_task = asyncio.create_task(worker_loop(app.state.stop_worker))
    runtime_issues = settings.validate_runtime()
    if runtime_issues:
        logger.warning("Configuration is incomplete: %s", "; ".join(runtime_issues))
    try:
        yield
    finally:
        app.state.stop_worker.set()
        app.state.worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await app.state.worker_task


app = FastAPI(title="Podcast Processor", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.secure_cookies,
    same_site="lax",
    max_age=60 * 60 * 12,
)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    try:
        too_large = bool(
            content_length
            and int(content_length) > settings.max_upload_mb * 1024 * 1024
        )
    except ValueError:
        too_large = True
    if too_large:
        raise HTTPException(
            status_code=413, detail="Upload is larger than the configured limit"
        )
    return await call_next(request)


def template_context(request: Request, **values) -> dict:
    return {
        "request": request,
        "csrf_token": csrf_token(request),
        "runtime_issues": settings.validate_runtime(),
        **values,
    }


@app.get("/health")
def health() -> dict:
    database.create_schema()
    issues = settings.validate_runtime()
    if not commands_available():
        issues.append("FFmpeg or FFprobe is unavailable")
    return {"status": "ok" if not issues else "degraded", "issues": issues}


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("authenticated"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context=template_context(request, error=""),
    )


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf: str = Form(...),
):
    require_csrf(request, csrf)
    if not verify_login(settings, username, password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=template_context(request, error="Incorrect username or password"),
            status_code=401,
        )
    request.session.clear()
    request.session["authenticated"] = True
    csrf_token(request)
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
def logout(request: Request, csrf: str = Form(...)):
    require_login(request)
    require_csrf(request, csrf)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    require_login(request)
    with database.session_factory() as session:
        jobs = list(session.scalars(select(Job).order_by(Job.created_at.desc()).limit(100)))
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=template_context(request, jobs=jobs),
    )


async def save_upload(upload: UploadFile, destination: Path, remaining: list[int]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            remaining[0] -= len(chunk)
            if remaining[0] < 0:
                output.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Upload exceeds configured limit")
            output.write(chunk)


def safe_slide_name(filename: str, position: int, base_filename: str = "") -> str:
    basename = Path(filename).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(basename).stem).strip("._") or "slide"
    prefix = f"{base_filename}_" if base_filename else ""
    return f"{prefix}{position:04d}_{stem[:120]}.png"


@app.post("/jobs")
async def create_job(
    request: Request,
    sermon_date: date = Form(...),
    title: str = Form(..., min_length=1, max_length=300),
    speaker: str = Form("", max_length=200),
    scripture: str = Form("", max_length=300),
    series: str = Form("", max_length=300),
    csrf: str = Form(...),
    wav: UploadFile = File(...),
    slides: list[UploadFile] = File(default=[]),
):
    require_login(request)
    require_csrf(request, csrf)
    if Path(wav.filename or "").suffix.casefold() != ".wav":
        raise HTTPException(status_code=400, detail="The sermon audio must be a WAV file")

    base_filename = build_base_filename(sermon_date, title.strip())
    destination_mp3 = (
        settings.podcast_dir / str(sermon_date.year) / f"{base_filename}.mp3"
    )
    with database.session_factory() as session:
        existing = session.scalar(select(Job).where(Job.base_filename == base_filename))
    if existing or destination_mp3.exists():
        raise HTTPException(
            status_code=409,
            detail="A sermon with this date and title already exists",
        )

    job = Job(
        id=str(uuid.uuid4()),
        sermon_date=sermon_date,
        title=title.strip(),
        speaker=speaker.strip(),
        scripture=scripture.strip(),
        series=series.strip(),
        base_filename=base_filename,
        source_wav="",
    )
    job_dir = settings.jobs_dir / job.id
    remaining = [settings.max_upload_mb * 1024 * 1024]
    source_wav = job_dir / "source.wav"
    saved_slides: list[str] = []
    try:
        await save_upload(wav, source_wav, remaining)
        probe_audio(source_wav)

        valid_slides = [slide for slide in slides if slide.filename]
        valid_slides.sort(key=lambda item: natural_sort_key(item.filename or ""))
        for position, slide in enumerate(valid_slides, start=1):
            if Path(slide.filename or "").suffix.casefold() != ".png":
                raise HTTPException(status_code=400, detail="Every slide must be a PNG file")
            slide_path = job_dir / "slides" / safe_slide_name(
                slide.filename or "slide.png", position, base_filename
            )
            await save_upload(slide, slide_path, remaining)
            try:
                with Image.open(slide_path) as image:
                    image.verify()
                    if image.format != "PNG":
                        raise HTTPException(status_code=400, detail=f"{slide.filename} is not a PNG")
            except UnidentifiedImageError as error:
                raise HTTPException(status_code=400, detail=f"{slide.filename} is invalid") from error
            saved_slides.append(str(slide_path))
    except (AudioError, ValueError) as error:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise

    job.source_wav = str(source_wav)
    job.slides_json = json.dumps(saved_slides)
    try:
        with database.session_factory.begin() as session:
            session.add(job)
    except IntegrityError as error:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=409, detail="An identical sermon job already exists") from error
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: str):
    require_login(request)
    with database.session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
    return templates.TemplateResponse(
        request=request,
        name="job.html",
        context=template_context(request, job=job),
    )


@app.post("/jobs/{job_id}/retry")
def retry_job(request: Request, job_id: str, csrf: str = Form(...)):
    require_login(request)
    require_csrf(request, csrf)
    with database.session_factory.begin() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status != JobStatus.FAILED.value:
            raise HTTPException(status_code=409, detail="Only failed jobs can be retried")
        if not Path(job.source_wav).exists() and not (
            settings.podcast_dir / str(job.sermon_date.year) / f"{job.base_filename}.mp3"
        ).exists():
            raise HTTPException(status_code=409, detail="The source audio is no longer available")
        job.status = JobStatus.QUEUED.value
        job.error_message = ""
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)
