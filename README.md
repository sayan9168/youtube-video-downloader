# 🎬 YouTube Video Downloader Web App

A clean, modern, and production-ready web application to download YouTube videos and audio in multiple qualities.

Built with **FastAPI** + **yt-dlp** + beautiful dark UI.

---

## ✨ Features

- Paste any YouTube URL (normal videos, Shorts, etc.)
- Fetch video info + thumbnail instantly
- Choose from multiple qualities (1080p, 720p, 480p, audio-only, etc.)
- One-click download
- Fully responsive + dark modern UI
- Automatic temporary file cleanup
- Proper error handling
- Ready for local use or deployment

---

## ⚠️ Important Legal Notice

This tool is intended **only for personal, educational, and fair-use purposes**.

- Always respect YouTube's Terms of Service
- Do **not** download or redistribute copyrighted content without permission
- The developer is not responsible for any misuse of this tool

Use responsibly.

---

## 🛠️ Tech Stack

| Layer       | Technology              |
|-------------|-------------------------|
| Backend     | FastAPI (Python)        |
| Downloader  | yt-dlp                  |
| Frontend    | HTML + Tailwind CSS + Vanilla JS |
| Server      | Uvicorn                 |

---

## 🚀 Quick Start (Local)

### 1. Clone the repository

```bash
git clone https://github.com/sayan9168/youtube-video-downloader.git
cd youtube-video-downloader
```

### 2. Create virtual environment (recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS / Termux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Open in browser: [http://localhost:8000](http://localhost:8000)

---

## 📦 Project Structure

```
youtube-video-downloader/
├── app.py                 # Main FastAPI application
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html         # Frontend UI
├── static/                # (optional static assets)
├── downloads/             # Temporary download folder (auto-created)
├── .gitignore
└── README.md
```

---

## 🌐 Deploy Options

### Option 1: Railway / Render / Fly.io
- Connect this GitHub repo
- Set start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Note: Free tiers have limited bandwidth & may block long downloads

### Option 2: VPS (Recommended for serious use)
```bash
# Install dependencies + run with systemd or pm2/supervisor
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Option 3: Docker (coming soon / easy to add)

---

## 📱 Termux / Android Notes

You can run this on Termux:

```bash
pkg update && pkg install python
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000` in your phone browser.

---

## 🔧 Configuration

You can change these in `app.py`:

- `MAX_FILE_AGE_SECONDS` → how long temporary files are kept
- Default format selection logic
- Port / host

---

## 🤝 Contributing

Feel free to open issues or PRs for improvements (better progress bar, more formats, queue system, etc.).

---

## 📄 License

MIT License — free to use and modify.

---

Made with ❤️ by [Sayan Mahata](https://github.com/sayan9168)
