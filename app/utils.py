from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote


def sanitize_title(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    words = re.findall(r"[A-Za-z0-9]+", ascii_title)
    sanitized = "_".join(words)
    if not sanitized:
        raise ValueError("Title must contain at least one letter or number")
    return sanitized[:180]


def build_base_filename(sermon_date, title: str) -> str:
    return f"{sermon_date:%Y_%m_%d}_{sanitize_title(title)}"


def natural_sort_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def build_public_url(base_url: str, year: int, filename: str) -> str:
    encoded_path = "/".join(quote(part) for part in (str(year), filename))
    return f"{base_url.rstrip('/')}/{encoded_path}"


def json_list(value: str) -> list:
    parsed = json.loads(value or "[]")
    return parsed if isinstance(parsed, list) else []


def compact_error(error: Exception, limit: int = 500) -> str:
    message = " ".join(str(error).split()) or error.__class__.__name__
    return message[:limit]


def safe_unlink(path: str | Path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass
