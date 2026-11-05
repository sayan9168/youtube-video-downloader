# 🎬 YouTube Downloader

A self-hosted YouTube downloader with a modern, installable web UI.
Paste a link, pick a quality, watch the live progress bar and save the file —
videos, MP3 audio, whole playlists, subtitles and thumbnails.

Built with **FastAPI** + **yt-dlp** + vanilla JS (no build step, no CDN).

```
FastAPI  ──►  job queue  ──►  yt-dlp (thread)  ──►  ffmpeg  ──►  /api/jobs/{id}/file
                                │
                                └── progress hooks ──► polled by the UI every second
```

---

## ✨ Features

### Core
- **Live download progress** — percentage, speed, ETA, downloaded/total size and playlist entry counter. Downloads run as background jobs, so the page can be closed or reloaded.
- **Playlist support** — list every video in a playlist, pick the ones you want, download them as a single `.zip`.
- **Audio only → MP3** — real MP3 conversion with a selectable bitrate (320 / 256 / 192 / 128 / 96 kbps), plus M4A, Opus and "keep original".
- **Clear format presets** — Best, MP4 (H.264), every available height, MP3, M4A, Subtitles only, or an exact format from the advanced list.
- **Subtitles** — download manual or auto-generated captions as `.srt` / `.vtt` (English, Bengali, Hindi and ~35 more), or embed them into the video file.

### Quality of life
- **Download history** — the last 60 downloads are remembered in `localStorage`, with one-click re-download.
- **Custom file names** — optional name for single videos, subtitle files and playlist archives.
- **Thumbnail download** — one click to save the video thumbnail (proxied, so it always downloads instead of opening).
- **Dark / light theme** — remembers your choice and respects the OS preference on first visit.
- **Bengali UI** — full English ⇄ বাংলা switcher (`EN / বাংলা`) for every label, status and error message.
- **Download queue** — paste any number of links, everything is queued with a concurrency limit, cancellable, retryable and removable.
- **Quality preference** — the last preset/quality/audio settings are restored automatically.

### Ops
- **Docker** — `Dockerfile` + `docker-compose.yml` with ffmpeg included, non-root user and healthcheck.
- **Rate limiting** — dependency-free sliding-window limiter per IP, per endpoint (configurable or switchable off).
- **Trim / cut** — download only a section of a video or audio track (needs ffmpeg).
- **PWA** — installable on Android/iOS/desktop, works offline for the shell, service worker caches the UI.
- **Demo mode** — `DEMO_MODE=1` serves sample data and bundled media so the whole UI can be explored without contacting YouTube.
- **Automatic cleanup** — finished files are deleted from disk after `MAX_FILE_AGE_SECONDS` (default 1 hour).
- **Cloudflare Pages ready** — `python3 scripts/build_pages.py` produces a static `dist/`; the UI asks for the backend URL (gear icon) and remembers it, so the interface can live on Pages while downloads run on your server.

### Not included (yet)
- **Direct streaming to the browser** — downloads are written to disk first, then served with HTTP `Range` support (so seeking/partial downloads still work). Streaming straight from yt-dlp would make accurate progress, zipping, retrying and cancellation unreliable, so it was intentionally left out.

---

## ⚠️ Legal notice

This tool is intended **only for personal, educational and fair-use purposes**.

- Respect YouTube's Terms of Service and the rights of content owners.
- Do not download or redistribute copyrighted content without permission.
- The author is not responsible for misuse.

---

## 🚀 Quick start

### 1. Requirements
- Python **3.10+**
- **ffmpeg** for MP3/M4A conversion, merging and trimming
  ```bash
  # Debian / Ubuntu / Termux
  sudo apt install ffmpeg        # Termux: pkg install ffmpeg
  # macOS
  brew install ffmpeg
  # Windows: download a build and add it to PATH, or just `pip install imageio-ffmpeg`
  ```
  If ffmpeg is missing the app still runs: MP3 conversion, trimming and format
  merging are disabled and the UI shows a warning. `imageio-ffmpeg` (installed
  by default with `requirements.txt`) provides a fallback binary.

### 2. Install & run
```bash
git clone https://github.com/sayan9168/youtube-video-downloader.git
cd youtube-video-downloader

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>.

Try the UI without internet access:
```bash
DEMO_MODE=1 uvicorn app:app --host 0.0.0.0 --port 8000
```

---

## 🐳 Docker

```bash
docker compose up -d --build
# or
docker build -t youtube-downloader .
docker run -d -p 8000:8000 -v "$(pwd)/data:/data" youtube-downloader
```

`docker-compose.yml` ships with sensible defaults; see the environment section
below. Data (temporary downloads) lives in the `./data` volume.

---

## ☁️ Hosting the interface on Cloudflare Pages

Cloudflare Pages is a **static** host: it cannot run Python, `yt-dlp`, `ffmpeg`
or background jobs. So the deployment is split in two:

1. **Interface** (the files in this repo) → Cloudflare Pages, free.
2. **Downloader backend** (this same app) → any machine that can run Python:
   Docker on a VPS, Render, Fly.io, Railway, a Raspberry Pi behind a tunnel…

The UI reads the backend URL at runtime from `/config.js` and from the
**⚙️ settings dialog**, so nothing has to be rebuilt when the backend URL changes.

### Deploy with the Cloudflare dashboard (no CLI)

1. Push this repository to GitHub (it already is).
2. In the Cloudflare dashboard open **Workers & Pages → Create → Pages →
   Connect to Git** and pick the repository.
3. Use these build settings:

   | Setting | Value |
   |---|---|
   | Framework preset | *None* |
   | Build command | `python3 scripts/build_pages.py` |
   | Build output directory | `dist` |
   | Environment variable | `PUBLIC_API_BASE` = `https://your-backend.example.com` (optional) |

   The build script needs nothing but Python 3 — it renders the template
   itself, and uses `jinja2` only when that is already installed.

4. **Save and deploy.** You get `https://<project>.pages.dev`.
5. Open the site. If the backend URL was not set at build time, the amber banner
   asks for it — click **Connect backend**, paste the URL, press **Test
   connection**, then **Save & reload**. The value is stored in `localStorage`.

### Deploy with Wrangler

```bash
python3 scripts/build_pages.py --api-base https://your-backend.example.com
npx wrangler pages deploy dist --project-name youtube-video-downloader
# or simply (wrangler.toml already points at dist):
npx wrangler pages deploy
```

`scripts/build_pages.py` renders the Jinja template, copies `static/`, writes
`dist/config.js` (the backend URL), plus `_headers` (CSP, cache rules,
`no-store` for `config.js`) and `_redirects` (single-page fallback). `dist/` is
git-ignored: it is a build artifact.

### Point the backend at that origin

The API accepts cross-origin calls from any `*.pages.dev` site out of the box
(`CORS_ORIGIN_REGEX`). If you serve the interface from a custom domain, start the
backend with that origin listed:

```bash
CORS_ORIGINS=https://ytd.example.com uvicorn app:app --host 0.0.0.0 --port 8000
# nginx/Caddy in front: TRUST_PROXY_HEADERS=true
```

Finished files stay on the backend, so downloads always come from it — the
browser talks to the backend directly (CORS + `Content-Disposition: attachment`).

> **Note:** Pages cannot proxy long downloads reliably (Workers have CPU,
> subrequest and response-size limits), which is why the UI calls the backend
> directly instead of routing `/api/*` through a Function.

---

## ⚙️ Configuration

All settings are environment variables — nothing needs editing in the code.

| Variable | Default | What it does |
|---|---|---|
| `DOWNLOAD_DIR` | `./downloads` | Where finished files are written (`/data` in Docker) |
| `MAX_CONCURRENT_DOWNLOADS` | `2` | Parallel downloads (queued jobs wait) |
| `MAX_QUEUE_SIZE` | `50` | Max queued/running jobs before new ones are rejected |
| `MAX_PLAYLIST_ENTRIES` | `100` | Playlist items listed/downloadable per playlist |
| `MAX_FILE_AGE_SECONDS` | `3600` | Delete finished files after this many seconds |
| `CLEANUP_INTERVAL_SECONDS` | `60` | How often expired jobs are purged |
| `MAX_FILENAME_LENGTH` | `120` | Truncate long titles/filenames |
| `YTDLP_SOCKET_TIMEOUT` | `30` | yt-dlp network timeout |
| `YTDLP_RETRIES` | `3` | Network retries per download |
| `RATE_LIMIT_ENABLED` | `true` | Enable the per-IP rate limiter |
| `RATE_LIMIT_PER_MINUTE` | `120` | Default limit for API endpoints |
| `RATE_LIMIT_DOWNLOADS_PER_MINUTE` | `30` | Limit for creating new downloads |
| `TRUST_PROXY_HEADERS` | `false` | Use `X-Forwarded-For` for client IPs (behind nginx/Caddy) |
| `CORS_ORIGINS` | *(empty)* | Extra origins allowed to call the API (the static UI on Cloudflare Pages) |
| `CORS_ORIGIN_REGEX` | `https://([a-z0-9-]+\.)*pages\.dev` | Regex for allowed origins; set it to `""` to disable, or narrow it to your own domain |
| `PUBLIC_API_BASE` | *(empty)* | Backend URL advertised in `/config.js` when the UI is hosted elsewhere |
| `FFMPEG_LOCATION` | *(auto)* | Explicit path to ffmpeg (file or directory) |
| `DEMO_MODE` | `false` | Serve bundled sample data instead of YouTube |

---

## 🔌 API

The UI is a thin client over a small JSON API, so you can script it with `curl`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/info` | Video or playlist metadata, formats and subtitles |
| `POST` | `/api/jobs` | Queue one download |
| `POST` | `/api/jobs/batch` | Queue up to 20 URLs in one request |
| `GET` | `/api/jobs` | Queue snapshot (used for polling progress) |
| `GET` | `/api/jobs/{id}` | Status of a single job |
| `POST` | `/api/jobs/{id}/cancel` | Cancel a queued/running job |
| `DELETE` | `/api/jobs/{id}` | Forget a job and delete its files |
| `GET` | `/api/jobs/{id}/file` | Download the result (file or `.zip`) |
| `GET` | `/api/thumbnail?url=&name=` | Save a thumbnail as a file |
| `GET` | `/api/config` | Capabilities and limits |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/download` | Legacy synchronous download (waits for the job) |

<details>
<summary><strong>Example: queue an MP3 and fetch it</strong></summary>

```bash
# 1. inspect the video
curl -s -X POST localhost:8000/api/info \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'

# 2. queue an MP3 download
curl -s -X POST localhost:8000/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ",
       "mode":"audio","audio_format":"mp3","audio_quality":320,
       "filename":"my song"}'

# 3. poll until "completed"
curl -s localhost:8000/api/jobs/<job-id>

# 4. save it
curl -OJ localhost:8000/api/jobs/<job-id>/file
```
</details>

<details>
<summary><strong>Example: download part of a video</strong></summary>

```bash
curl -s -X POST localhost:8000/api/jobs -H 'Content-Type: application/json' -d '{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "mode": "video", "quality": "720",
  "trim_start": 30, "trim_end": 75,
  "filename": "highlight"
}'
```
</details>

---

## 📦 Project structure

```
youtube-video-downloader/
├── app.py                  # FastAPI app: routes, validation, rate limiting
├── config.py               # Environment driven settings + ffmpeg discovery
├── downloader.py           # yt-dlp layer: metadata, formats, progress, files
├── jobs.py                 # In-memory queue, workers, zip packaging, cleanup
├── ratelimit.py            # Dependency free sliding-window limiter
├── demo.py                 # Offline demo mode (sample metadata + media)
├── templates/
│   └── index.html          # Single page UI (i18n via data attributes)
├── static/
│   ├── css/app.css         # Design system, dark/light themes
│   ├── js/app.js           # UI logic, EN/BN dictionary, polling, history
│   ├── sw.js               # Service worker (offline shell)
│   ├── manifest.webmanifest
│   ├── icons/              # PWA icons
│   └── demo/               # Tiny sample media for DEMO_MODE
├── tests/test_app.py       # API + queue tests (no network needed)
├── tests/test_pages_build.py   # Cloudflare Pages build output tests
├── scripts/generate_assets.py  # Regenerate icons / demo media
├── scripts/build_pages.py      # Build the static Cloudflare Pages site (dist/)
├── wrangler.toml           # Pages project settings for the Wrangler CLI
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 🧪 Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

The suite fakes the yt-dlp layer, so it runs offline and covers info parsing,
job lifecycle, progress, zip packaging, cancellation, batch queueing, ffmpeg
guards, validation, SSRF protection on the thumbnail proxy and rate limiting.
`tests/test_pages_build.py` builds the Cloudflare Pages bundle and checks that
the interface, `config.js`, `_headers` and `_redirects` are all present.

---

## 🩺 Troubleshooting

| Symptom | Fix |
|---|---|
| “YouTube error” / “Could not read this video” | Update the extractor: `pip install -U yt-dlp` |
| MP3 button missing or “needs ffmpeg” | Install ffmpeg, or `pip install imageio-ffmpeg`, then restart |
| Downloads fail behind a proxy/VPN | YouTube blocks some data-centre IPs; try another server or a cookie file |
| “Sign in to confirm you're not a bot” | YouTube bot-check — update yt-dlp, or run the app from a residential IP |
| Queue stuck at “In queue” | Check `MAX_CONCURRENT_DOWNLOADS` and the server logs |
| Files disappear | Temporary files are deleted after `MAX_FILE_AGE_SECONDS` |

---

## 🤝 Contributing

Issues and pull requests are welcome. Ideas that would fit nicely next:
scheduled downloads, download statistics, cookie/sign-in support, and a
server-side history that survives restarts.

---

## 📄 License

MIT — free to use and modify.

---

## 🇧🇩 বাংলা সংক্ষেপে

```bash
# ইনস্টল
pip install -r requirements.txt

# চালু করুন (ffmpeg ইনস্টল থাকলে MP3/ট্রিম কাজ করবে)
uvicorn app:app --host 0.0.0.0 --port 8000
```

ব্রাউজারে <http://localhost:8000> খুলুন, লিংক পেস্ট করুন, কোয়ালিটি বেছে নিন
আর ডাউনলোড বাটনে ক্লিক করুন। উপরের ডান দিকের **বাংলা** বাটনে ক্লিক করলে পুরো
ইন্টারফেস বাংলায় হয়ে যাবে। একটি প্লেলিস্ট লিংক দিলে সব ভিডিওর তালিকা দেখাবে —
যেগুলো দরকার শুধু সেগুলো সিলেক্ট করে এক ফাইলে (zip) ডাউনলোড করতে পারবেন।
একাধিক লিংক একসাথে দিতে প্রতিটি লিংক আলাদা লাইনে পেস্ট করুন।

### ☁️ Cloudflare Pages-এ হোস্ট করা

Cloudflare Pages শুধু স্ট্যাটিক ফাইল চালায় — Python, yt-dlp বা ffmpeg চলে না।
তাই দুটি অংশ লাগবে:

1. **ইন্টারফেস** → Cloudflare Pages (ফ্রি)।
2. **ডাউনলোডার ব্যাকএন্ড** → যে কোনো Python হোস্ট (Docker VPS, Render, Fly.io)।

ড্যাশবোর্ডে **Workers & Pages → Create → Pages → Connect to Git** দিয়ে রিপো
যোগ করুন, তারপর:

```
Build command:            python3 scripts/build_pages.py
Build output directory:   dist
Environment variable:     PUBLIC_API_BASE = https://your-backend.example.com  (ঐচ্ছিক)
```

অথবা লোকালি:

```bash
python3 scripts/build_pages.py --api-base https://your-backend.example.com
npx wrangler pages deploy dist --project-name youtube-video-downloader
```

সাইট খোলার পর উপরের ⚙️ বাটনে ক্লিক করে ব্যাকএন্ড URL বসিয়ে **Test connection**
→ **Save & reload** চাপুন (URL ব্রাউজারে সেভ থাকে, রিবিল্ড লাগে না)। ব্যাকএন্ডে
`*.pages.dev` অরিজিন ডিফল্টেই অনুমোদিত; কাস্টম ডোমেইন হলে ব্যাকএন্ড চালান:

```bash
CORS_ORIGINS=https://ytd.example.com uvicorn app:app --host 0.0.0.0 --port 8000
```

শুধু নিজের বা অনুমতি আছে এমন কনটেন্ট ডাউনলোড করুন — কপিরাইট ও ইউটিউবের
শর্তাবলি মানুন।

---

Made with ❤️ by [Sayan Mahata](https://github.com/sayan9168)
