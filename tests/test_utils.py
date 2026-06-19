from datetime import date

import pytest

from app.config import Settings
from app.utils import (
    build_base_filename,
    build_public_url,
    natural_sort_key,
    sanitize_title,
)


def test_sanitize_title_is_filesystem_safe():
    assert sanitize_title("  God’s Grace: Part 2! ") == "Gods_Grace_Part_2"


def test_sanitize_title_rejects_empty_ascii_title():
    with pytest.raises(ValueError):
        sanitize_title("---")


def test_base_filename_matches_contract():
    assert (
        build_base_filename(date(2026, 6, 19), "The Good Shepherd")
        == "2026_06_19_The_Good_Shepherd"
    )


def test_natural_slide_sort():
    names = ["slide-10.png", "slide-2.png", "slide-1.png"]
    assert sorted(names, key=natural_sort_key) == [
        "slide-1.png",
        "slide-2.png",
        "slide-10.png",
    ]


def test_public_url_quotes_path_parts():
    assert build_public_url("https://files.example/podcasts/", 2026, "A B.mp3") == (
        "https://files.example/podcasts/2026/A%20B.mp3"
    )


def test_blank_optional_category_from_environment_is_allowed(monkeypatch, tmp_path):
    monkeypatch.setenv("WORDPRESS_CATEGORY_ID", "")
    settings = Settings(data_dir=tmp_path, podcast_dir=tmp_path / "podcasts")
    assert settings.wordpress_category_id is None
