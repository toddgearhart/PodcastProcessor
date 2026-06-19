from __future__ import annotations

import shutil
import subprocess

import pytest

from app.audio import probe_audio, process_audio


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg is not installed",
)


def make_tone(path, duration=4, volume=0.08):
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}:sample_rate=44100",
            "-af",
            f"volume={volume}",
            "-c:a",
            "pcm_s16le",
            str(path),
        ],
        check=True,
    )


def test_audio_pipeline_creates_compliant_mp3(tmp_path):
    source = tmp_path / "source.wav"
    destination = tmp_path / "finished.mp3"
    make_tone(source)

    result = process_audio(
        source,
        destination,
        title="Test sermon",
        sermon_date="2026-06-19",
    )

    assert destination.exists()
    assert abs(result.integrated_lufs - (-14.0)) <= 0.5
    assert result.true_peak_dbtp <= -1.0
    info = probe_audio(destination)
    assert info.channels == 1
    assert info.sample_rate == 44100


def test_audio_shorter_than_two_seconds_is_rejected(tmp_path):
    source = tmp_path / "short.wav"
    make_tone(source, duration=1)
    with pytest.raises(Exception, match="at least two seconds"):
        probe_audio(source)

