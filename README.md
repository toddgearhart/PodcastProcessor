# Podcast Processor

A self-hosted sermon workflow for Unraid. Upload a WAV and optional slide PNGs in a browser; the single Docker container masters the audio, transcribes it locally on the CPU, writes the MP3 and transcript into a FileBrowser-served share, and creates a WordPress draft.

## What it produces

For a sermon dated June 19, 2026 titled “The Good Shepherd”:

```text
/podcasts/2026/2026_06_19_The_Good_Shepherd.mp3
/podcasts/2026/2026_06_19_The_Good_Shepherd.txt
```

The WordPress draft contains a generated two-to-three paragraph introduction, an audio player, transcript link, and an ordered slide gallery. It is never automatically published.

## Quick start

1. Build the image:

   ```sh
   docker build -t podcast-processor .
   ```

2. Generate an administrator password hash:

   ```sh
   docker run --rm -it podcast-processor python -m app.password
   ```

3. Copy `.env.example` to `.env` and fill in the hash, a random session secret, OpenAI project API key, WordPress settings, and FileBrowser public URL.

4. Change the `/mnt/user/podcasts` host path in `compose.yaml` to the share already mounted in FileBrowser, then start:

   ```sh
   docker compose up -d --build
   ```

5. Open `http://SERVER-IP:8000`. If there is no HTTPS reverse proxy yet, set `SECURE_COOKIES=false`; return it to `true` when HTTPS is enabled.

The first transcription downloads `medium.en` into `/data/models`. Keep `/data` persistent across container upgrades.

## WordPress preparation

- In WordPress, open **Users → Profile → Application Passwords** for a user allowed to upload media and edit posts.
- Create an Application Password and place its generated value in `WORDPRESS_APPLICATION_PASSWORD`.
- Set `WORDPRESS_CATEGORY_ID` to the numeric sermon category ID, or leave it empty for no fixed category.
- Ensure the REST API endpoints under `/wp-json/wp/v2` are reachable from the container.

## FileBrowser mapping

The processor does not call the FileBrowser API. Both containers must mount the same host share. `PODCAST_PUBLIC_BASE_URL` must be the URL that maps to the root of the processor’s `/podcasts` mount. The application URL-encodes the year and filenames when it builds links.

## Unraid

Build or publish the image, then import [`unraid/podcast-processor.xml`](unraid/podcast-processor.xml) as a user template. The normal Unraid ownership defaults are PUID `99` and PGID `100`. The entrypoint fixes ownership only for `/data`; the existing podcast share’s permissions remain under your control.

Allocate 4–8 CPU threads and 8–16 GB RAM if possible. Only one sermon is processed at a time. There is no GPU requirement.

## Audio and retry behavior

FFmpeg applies moderate speech compression, one-second fades, and two-pass EBU R128 normalization. The finished 128 kbps MP3 must measure −14 LUFS ±0.5 and no higher than −1 dBTP. Files are published by atomic rename.

Interrupted active jobs return to the queue after restart. Failed jobs retain their source files and can be retried from the dashboard. Completed jobs remove their working directory. WordPress media and posts use deterministic slugs so retries reuse existing remote objects.

## Development and tests

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
uvicorn app.main:app --reload
```

FFmpeg and FFprobe must be installed for media tests and local processing.

