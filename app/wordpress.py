from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path

import httpx

from app.config import Settings
from app.models import Job
from app.utils import json_list


class WordPressError(RuntimeError):
    pass


class WordPressClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_base = f"{settings.wordpress_url}/wp-json/wp/v2"
        self.auth = (
            settings.wordpress_username,
            settings.wordpress_application_password,
        )

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = httpx.request(
                    method,
                    f"{self.api_base}{path}",
                    auth=self.auth,
                    timeout=120.0,
                    **kwargs,
                )
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise httpx.HTTPStatusError(
                        "Transient WordPress failure", request=response.request, response=response
                    )
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as error:
                last_error = error
                if attempt < 2:
                    time.sleep(2**attempt)
        if isinstance(last_error, httpx.HTTPStatusError):
            detail = last_error.response.text[:1000]
            raise WordPressError(
                f"WordPress returned HTTP {last_error.response.status_code}: {detail}"
            ) from last_error
        raise WordPressError(f"Unable to reach WordPress: {last_error}") from last_error

    def upload_slide(
        self, slide: Path, title: str, position: int, sermon_key: str
    ) -> dict:
        media_slug = re.sub(
            r"[^a-z0-9]+", "-", f"{sermon_key}-{position:04d}".lower()
        ).strip("-")
        existing = self._request(
            "GET",
            "/media",
            params={"slug": media_slug, "per_page": 1, "context": "edit"},
        ).json()
        alt_text = f"{title} – slide {position}"
        if existing:
            media = existing[0]
            return {
                "id": int(media["id"]),
                "filename": slide.name,
                "source_url": media.get("source_url", ""),
                "alt_text": media.get("alt_text") or alt_text,
            }
        response = self._request(
            "POST",
            "/media",
            headers={
                "Content-Disposition": f'attachment; filename="{media_slug}.png"',
                "Content-Type": "image/png",
            },
            content=slide.read_bytes(),
        )
        media = response.json()
        media_id = int(media["id"])
        self._request(
            "POST",
            f"/media/{media_id}",
            json={"alt_text": alt_text, "caption": alt_text, "slug": media_slug},
        )
        return {
            "id": media_id,
            "filename": slide.name,
            "source_url": media.get("source_url", ""),
            "alt_text": alt_text,
        }

    def save_draft(self, job: Job, content: str) -> dict:
        post_slug = re.sub(
            r"[^a-z0-9]+", "-", job.base_filename.lower()
        ).strip("-")
        payload: dict = {
            "title": job.title,
            "content": content,
            "status": "draft",
            "slug": post_slug,
        }
        if self.settings.wordpress_category_id is not None:
            payload["categories"] = [self.settings.wordpress_category_id]
        post_id = job.wordpress_post_id
        if not post_id:
            existing = self._request(
                "GET",
                "/posts",
                params={
                    "slug": post_slug,
                    "status": "draft",
                    "per_page": 1,
                    "context": "edit",
                },
            ).json()
            if existing:
                post_id = int(existing[0]["id"])
        path = f"/posts/{post_id}" if post_id else "/posts"
        response = self._request("POST", path, json=payload)
        return response.json()


def build_post_content(job: Job) -> str:
    paragraphs = [
        "<!-- wp:paragraph -->\n"
        f"<p>{html.escape(paragraph)}</p>\n"
        "<!-- /wp:paragraph -->"
        for paragraph in job.introduction.split("\n\n")
        if paragraph.strip()
    ]
    audio = (
        '<!-- wp:audio -->\n'
        f'<figure class="wp-block-audio"><audio controls src="{html.escape(job.mp3_url, quote=True)}">'
        "</audio></figure>\n<!-- /wp:audio -->"
    )
    transcript = (
        '<!-- wp:paragraph -->\n<p><a href="'
        f'{html.escape(job.transcript_url, quote=True)}">Read or download the transcript</a></p>\n'
        "<!-- /wp:paragraph -->"
    )
    media = json_list(job.media_ids_json)
    gallery = ""
    if media:
        inner = []
        ids = []
        for item in media:
            ids.append(int(item["id"]))
            inner.append(
                '<!-- wp:image {"id":%d,"sizeSlug":"large","linkDestination":"none"} -->\n'
                '<figure class="wp-block-image size-large"><img src="%s" alt="%s" '
                'class="wp-image-%d"/></figure>\n<!-- /wp:image -->'
                % (
                    int(item["id"]),
                    html.escape(item.get("source_url", ""), quote=True),
                    html.escape(item.get("alt_text", ""), quote=True),
                    int(item["id"]),
                )
            )
        gallery = (
            f'<!-- wp:gallery {{"linkTo":"none","ids":{json.dumps(ids)}}} -->\n'
            '<figure class="wp-block-gallery has-nested-images columns-default is-cropped">\n'
            + "\n".join(inner)
            + "\n</figure>\n<!-- /wp:gallery -->"
        )
    return "\n\n".join([*paragraphs, audio, transcript, gallery]).strip()
