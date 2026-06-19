import json
from datetime import date

from app.models import Job
from app.wordpress import build_post_content


def make_job(**overrides):
    values = {
        "sermon_date": date(2026, 6, 19),
        "title": "The Good Shepherd",
        "base_filename": "2026_06_19_The_Good_Shepherd",
        "source_wav": "/tmp/source.wav",
        "introduction": "First warm paragraph.\n\nSecond warm paragraph.",
        "mp3_url": "https://files.example/2026/sermon.mp3",
        "transcript_url": "https://files.example/2026/sermon.txt",
        "media_ids_json": json.dumps(
            [
                {
                    "id": 42,
                    "filename": "slide.png",
                    "source_url": "https://wp.example/slide.png",
                    "alt_text": "The Good Shepherd – slide 1",
                }
            ]
        ),
    }
    values.update(overrides)
    return Job(**values)


def test_gutenberg_content_has_all_required_sections():
    content = build_post_content(make_job())
    assert content.count("<!-- wp:paragraph -->") == 3
    assert "<!-- wp:audio -->" in content
    assert "sermon.mp3" in content
    assert "sermon.txt" in content
    assert "<!-- wp:gallery" in content
    assert "wp-image-42" in content


def test_gutenberg_content_escapes_external_values():
    content = build_post_content(
        make_job(
            introduction="A <script>alert(1)</script> thought.",
            media_ids_json="[]",
        )
    )
    assert "<script>" not in content
    assert "&lt;script&gt;" in content
    assert "wp:gallery" not in content

