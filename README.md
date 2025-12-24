# Podcast Processor

Automated system for processing sermon audio files and publishing to WordPress.

## Features

- **WAV Upload**: Web interface for uploading WAV audio files
- **Audio Processing**: 
  - Dynamic range compression
  - Loudness normalization to -14 LUFS
  - MP3 conversion at 128kbps stereo
- **Automatic File Management**: 
  - Uploads to FileBrowser organized by year
  - Generates podcast URLs
- **WordPress Integration**: 
  - Creates draft posts automatically
  - Custom post title format: `MM/DD/YYYY | Title | SUNDAY SERVICE`
  - Assigns to "Podcasts" category

## Directory Structure

```
podcast-processor/
├── backend/
│   ├── Dockerfile
│   ├── package.json
│   └── server.js
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── src/
│       └── App.js
├── docker-compose.yml
├── setup.sh
└── README.md
```

## Prerequisites

- Docker and Docker Compose installed
- Linux server with `/mnt/user/appdata/` directory
- FileBrowser instance running
- WordPress site with REST API enabled

## Installation

1. **Clone or download** this repository to your server

2. **Run the setup script**:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Start the application**:
   ```bash
   docker-compose up -d
   ```

4. **Configure credentials** (first time only):
   - Open http://localhost:3000/auth.html in your browser
   - Enter your FileBrowser credentials
   - Enter your WordPress credentials
   - Enter your podcast base URL
   - Click "Test Connection" to verify
   - Click "Save & Continue"

5. **Access the web interface**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:3001

## Configuration

### First-Time Setup

On first run, you must configure your credentials through the web interface:

1. Navigate to http://localhost:3000/auth.html
2. Fill in all required fields:
   - **FileBrowser URL**: Your FileBrowser instance URL
   - **FileBrowser Username**: Admin username
   - **FileBrowser Password**: Admin password
   - **WordPress URL**: Your WordPress site URL
   - **WordPress Username**: Your WordPress username
   - **WordPress Application Password**: Generate from WordPress Admin → Users → Profile → Application Passwords
   - **Podcast Base URL**: Base URL where podcasts will be accessible

3. Click "Test Connection" to verify all credentials work
4. Click "Save & Continue" to store credentials securely

### Credential Storage

- Credentials are stored **encrypted** on the server in `/mnt/user/appdata/podcast-processor/data/credentials.json`
- Passwords are encrypted using AES-256-CBC
- The encryption key is auto-generated on first run (or set via `ENCRYPTION_KEY` environment variable)
- Credentials are **never** stored in code or environment variables visible in docker-compose.yml
- The credentials file is excluded from Git via `.gitignore`

### Updating Credentials

To update your credentials later:
1. Visit http://localhost:3000/auth.html
2. Modify any fields as needed
3. Click "Save & Continue"

All configuration is managed through environment variables in `docker-compose.yml` (for non-sensitive settings only). Sensitive credentials are configured through the web interface.

## Usage

1. Open the web interface at http://localhost:3000
2. Select a date for the sermon
3. Enter the sermon title
4. Upload one or more WAV files
5. Click "Process & Publish"
6. Monitor the real-time status updates
7. Click "Edit Post" to review the WordPress draft

## File Naming

Processed MP3 files are named using the format:
```
YYYY-MM-DD_title.mp3
```

Example: `2025-12-23_sunday_morning_sermon.mp3`

## WordPress Post Format

**Post Title**: `MM/DD/YYYY | Title | SUNDAY SERVICE`

**Example**: `12/23/2025 | Christmas Message | SUNDAY SERVICE`

**Post Content**: 
- Audio player embed
- Download link
- Note about Media-Input-Podcast custom field

## Volume Mounts

Data is persisted in `/mnt/user/appdata/podcast-processor/`:
- `uploads/` - Temporary storage for uploaded WAV files
- `downloads/` - Temporary storage for processed MP3 files
- `logs/` - Application logs

## Troubleshooting

**Check container status**:
```bash
docker-compose ps
```

**View logs**:
```bash
docker-compose logs -f
```

**Restart services**:
```bash
docker-compose restart
```

**Rebuild after code changes**:
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

## Security Notes

- **Credentials are encrypted** using AES-256-CBC encryption on the server
- **Never commit** the `data/credentials.json` file (it's in .gitignore)
- **Application passwords** are recommended for WordPress (not your main password)
- Consider using **HTTPS** in production with a reverse proxy (nginx/Traefik)
- The **encryption key** is auto-generated; you can set a custom one via the `ENCRYPTION_KEY` environment variable
- Credentials are only stored server-side; they never appear in frontend JavaScript or GitHub

## Support

For issues or questions, check the logs:
```bash
docker-compose logs backend
docker-compose logs frontend
```

## License

MIT License
