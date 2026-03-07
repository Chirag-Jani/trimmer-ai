# Trimmer — AI Video Clipper

Upload a video, specify how many clips you want, and AI identifies the best moments and trims them into standalone Instagram-ready clips. Clips can be stitched from non-contiguous parts of the video when related content appears at different timestamps.

## Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **ffmpeg** — `brew install ffmpeg`
- **AI provider** (one of):
  - **Gemini API key** (recommended) — free tier works fine
  - **Ollama** with `qwen2.5:7b` — fully local, no API key needed

## Setup

```bash
cd trimmer

cd server
pip install -r requirements.txt
cd ..

cd client
npm install
cd ..
```

Create a `.env` file in the project root:

```env
# "gemini" or "ollama"
AI_PROVIDER=gemini

GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash

OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=qwen2.5:7b

# "base", "small", "medium" — bigger = more accurate but slower first download
WHISPER_MODEL=small
```

## Running

```bash
./start.sh
```

Starts both the backend (port 8000) and frontend (port 3000). Open `http://localhost:3000`.
