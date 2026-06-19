from __future__ import annotations

import re
from pathlib import Path

from faster_whisper import WhisperModel

from app.config import Settings


class Transcriber:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model: WhisperModel | None = None

    def _load_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                self.settings.whisper_model,
                device="cpu",
                compute_type=self.settings.whisper_compute_type,
                cpu_threads=self.settings.whisper_threads,
                download_root=str(self.settings.model_dir),
            )
        return self._model

    def transcribe(self, audio_path: Path) -> str:
        segments, _info = self._load_model().transcribe(
            str(audio_path),
            language="en",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=True,
        )
        texts = [segment.text.strip() for segment in segments if segment.text.strip()]
        transcript = paragraphs_from_segments(texts)
        if not transcript:
            raise RuntimeError("Whisper did not produce a transcript")
        return transcript


def paragraphs_from_segments(segments: list[str], sentences_per_paragraph: int = 5) -> str:
    paragraphs: list[str] = []
    current: list[str] = []
    sentence_count = 0
    for segment in segments:
        cleaned = " ".join(segment.split())
        if not cleaned:
            continue
        current.append(cleaned)
        sentence_count += max(1, len(re.findall(r"[.!?](?:\s|$)", cleaned)))
        if sentence_count >= sentences_per_paragraph:
            paragraphs.append(" ".join(current))
            current = []
            sentence_count = 0
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)

