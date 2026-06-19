from __future__ import annotations

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import Settings
from app.models import Job


class IntroductionResult(BaseModel):
    introduction: str = Field(min_length=300, max_length=2200)


def generate_introduction(settings: Settings, job: Job, transcript: str) -> str:
    client = OpenAI(api_key=settings.openai_api_key, max_retries=2, timeout=120.0)
    metadata = "\n".join(
        value
        for value in [
            f"Title: {job.title}",
            f"Date: {job.sermon_date.isoformat()}",
            f"Speaker: {job.speaker}" if job.speaker else "",
            f"Scripture: {job.scripture}" if job.scripture else "",
            f"Series: {job.series}" if job.series else "",
        ]
        if value
    )
    response = client.responses.parse(
        model=settings.openai_model,
        instructions=(
            "You write warm, welcoming introductions for church sermon posts. "
            "Write 150–250 words in two or three plain-text paragraphs. Ground every "
            "claim in the metadata or transcript. Never invent quotations, events, "
            "scripture references, biographical details, or claims. Do not use headings, "
            "Markdown, or a generic disclaimer. Invite the reader to listen without hype."
        ),
        input=f"SERMON METADATA\n{metadata}\n\nTRANSCRIPT\n{transcript}",
        text_format=IntroductionResult,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("OpenAI returned no structured introduction")
    introduction = parsed.introduction.strip()
    word_count = len(introduction.split())
    if not 130 <= word_count <= 275:
        raise RuntimeError(
            f"OpenAI introduction contained {word_count} words; expected approximately 150–250"
        )
    return introduction

