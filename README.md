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
# Clone and enter the project
cd trimmer

# Install server dependencies
cd server
pip install -r requirements.txt
cd ..

# Install client dependencies
cd client
npm install
cd ..
```

Configure `.env` in the project root:

```env
# "gemini" or "ollama"
AI_PROVIDER=gemini

GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash

OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=qwen2.5:7b
```

## Running

```bash
./start.sh
```

This starts both the backend (port 8000) and frontend (port 3000). Open `http://localhost:3000`.

## How It Works

1. **Upload** — video is saved to `server/uploads/`
2. **Audio extraction** — ffmpeg pulls a 16kHz mono WAV
3. **Transcription** — `faster-whisper` (local, runs on CPU) transcribes with timestamps
4. **AI segmentation** — transcript is sent to Gemini or Ollama to identify the best clip-worthy moments. The AI can combine non-contiguous sections into a single clip when they form a more coherent story together
5. **Trimming/stitching** — ffmpeg trims single-segment clips or uses `filter_complex` to stitch multi-segment clips
6. **Download** — preview and download each clip from the browser

## Project Structure

```
trimmer/
├── start.sh                 # Starts both servers
├── .env                     # AI provider config
├── server/
│   ├── main.py              # FastAPI app
│   ├── requirements.txt
│   └── services/
│       ├── transcription.py # faster-whisper (local)
│       ├── segmentation.py  # Gemini / Ollama clip selection
│       └── video.py         # ffmpeg trim & stitch
└── client/
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx          # React UI
        ├── main.jsx
        └── index.css
```

## Clip Constraints

- Duration per clip: **15–50 seconds** (sum of all segments)
- Clips do not overlap
- AI prioritizes quality over quantity — may return fewer clips than requested if the content doesn't support it
- Uploaded files and generated clips are cleaned up when the user clicks "Start Over"

## Roadmap / Improvements

### Smarter Clipping
- [ ] Multi-pass AI analysis — first pass identifies all topics/themes, second pass groups the best moments per theme into clips
- [ ] Sentiment & energy scoring via audio analysis (pitch, volume, speech pace) to detect high-engagement moments alongside transcript
- [ ] Speaker diarization — detect multiple speakers and create clips per speaker or per dialogue exchange
- [ ] Word-level Whisper timestamps for frame-accurate cuts instead of sentence-level boundaries

### Video Intelligence
- [ ] Auto-generate captions/subtitles burned into each clip (hardcoded SRT)
- [ ] Auto-crop to 9:16 portrait for Reels/Shorts with smart framing around the speaker
- [ ] Scene-change detection — combine with transcript so clips never cut mid visual transition

### Quality of Life
- [ ] In-browser trim handles — fine-tune AI-suggested boundaries before exporting
- [ ] Batch download all clips as a zip
- [ ] SQLite job history — revisit past clips without re-processing
- [ ] SSE for real-time progress instead of polling

### AI Providers
- [ ] Fallback chain — if primary provider fails, auto-retry with secondary
- [ ] Add OpenAI / Claude support as additional provider options
