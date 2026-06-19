from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


logger = logging.getLogger(__name__)


class AudioError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioInfo:
    duration: float
    sample_rate: int
    channels: int


@dataclass(frozen=True)
class Loudness:
    integrated_lufs: float
    true_peak_dbtp: float


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    logger.debug("Running media command", extra={"command": command[0]})
    try:
        return subprocess.run(command, text=True, capture_output=True, check=True)
    except FileNotFoundError as error:
        raise AudioError(f"Required command is unavailable: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "media command failed")[-2000:]
        raise AudioError(detail) from error


def probe_audio(path: Path) -> AudioInfo:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=sample_rate,channels:format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    try:
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        info = AudioInfo(
            duration=float(payload["format"]["duration"]),
            sample_rate=int(stream["sample_rate"]),
            channels=int(stream["channels"]),
        )
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise AudioError("The WAV does not contain a readable audio stream") from error
    if info.duration < 2.0:
        raise AudioError("Audio must be at least two seconds long")
    return info


def _parse_loudnorm(stderr: str) -> dict[str, str]:
    matches = re.findall(r"\{\s*\"input_i\".*?\}", stderr, flags=re.DOTALL)
    if not matches:
        raise AudioError("FFmpeg did not return loudness measurements")
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError as error:
        raise AudioError("FFmpeg returned invalid loudness measurements") from error


def _base_filters(duration: float) -> str:
    fade_out = max(1.0, duration - 1.0)
    return (
        "acompressor=threshold=0.125:ratio=3:attack=20:release=250:"
        "knee=2.828:link=average:detection=rms,"
        f"afade=t=in:st=0:d=1,afade=t=out:st={fade_out:.6f}:d=1"
    )


def process_audio(
    source: Path,
    destination: Path,
    *,
    title: str,
    sermon_date: str,
    speaker: str = "",
    series: str = "",
) -> Loudness:
    info = probe_audio(source)
    filters = _base_filters(info.duration)
    first_pass = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-i",
            str(source),
            "-af",
            f"{filters},loudnorm=I=-14:TP=-1.5:LRA=7:print_format=json",
            "-f",
            "null",
            "-",
        ]
    )
    measured = _parse_loudnorm(first_pass.stderr)
    normalized = (
        f"{filters},loudnorm=I=-14:TP=-1.5:LRA=7:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:"
        f"measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true:print_format=summary"
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.stem}.partial.mp3")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(source),
        "-af",
        normalized,
        "-c:a",
        "libmp3lame",
        "-ar",
        str(info.sample_rate),
        "-ac",
        str(info.channels),
        "-b:a",
        "128k",
        "-metadata",
        f"title={title}",
        "-metadata",
        f"date={sermon_date}",
    ]
    if speaker:
        command.extend(["-metadata", f"artist={speaker}"])
    if series:
        command.extend(["-metadata", f"album={series}"])
    command.extend([str(temporary)])
    try:
        _run(command)
        loudness = measure_loudness(temporary)
        if abs(loudness.integrated_lufs - (-14.0)) > 0.5:
            raise AudioError(
                f"Finished MP3 measured {loudness.integrated_lufs:.1f} LUFS; expected -14 ±0.5"
            )
        if loudness.true_peak_dbtp > -1.0:
            raise AudioError(
                f"Finished MP3 true peak measured {loudness.true_peak_dbtp:.1f} dBTP; expected ≤ -1.0"
            )
        temporary.replace(destination)
        return loudness
    finally:
        temporary.unlink(missing_ok=True)


def measure_loudness(path: Path) -> Loudness:
    result = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-i",
            str(path),
            "-af",
            "loudnorm=I=-14:TP=-1:LRA=7:print_format=json",
            "-f",
            "null",
            "-",
        ]
    )
    measured = _parse_loudnorm(result.stderr)
    return Loudness(
        integrated_lufs=float(measured["input_i"]),
        true_peak_dbtp=float(measured["input_tp"]),
    )


def make_transcription_audio(source_mp3: Path, destination_wav: Path) -> None:
    destination_wav.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i",
            str(source_mp3),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(destination_wav),
        ]
    )


def commands_available() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
