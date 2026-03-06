import os
import shutil
import uuid
import threading

from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from services.transcription import transcribe_audio
from services.segmentation import identify_segments
from services.video import extract_audio, trim_clip

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
CLIPS_DIR = os.path.join(os.path.dirname(__file__), "clips")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CLIPS_DIR, exist_ok=True)

jobs: dict[str, dict] = {}


@app.post("/api/upload")
async def upload_video(video: UploadFile, clip_count: int = Form(...)):
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    video_path = os.path.join(job_dir, video.filename)
    with open(video_path, "wb") as f:
        while chunk := await video.read(1024 * 1024):
            f.write(chunk)

    jobs[job_id] = {
        "status": "queued",
        "step": "Upload complete",
        "progress": 5,
        "clips": [],
        "note": None,
        "error": None,
        "video_path": video_path,
        "clip_count": clip_count,
    }

    thread = threading.Thread(target=_process, args=(job_id,), daemon=True)
    thread.start()

    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    job = jobs[job_id]
    return {
        "status": job["status"],
        "step": job["step"],
        "progress": job["progress"],
        "clips": job["clips"],
        "note": job.get("note"),
        "error": job["error"],
    }


@app.get("/api/download/{job_id}/{clip_index}")
async def download_clip(job_id: str, clip_index: int):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    clip_path = os.path.join(CLIPS_DIR, job_id, f"clip_{clip_index + 1}.mp4")
    if not os.path.exists(clip_path):
        raise HTTPException(404, "Clip not found")

    clip_title = "clip"
    for c in jobs[job_id].get("clips", []):
        if c["index"] == clip_index:
            clip_title = c["title"]
            break

    safe_name = "".join(ch if ch.isalnum() or ch in " _-" else "_" for ch in clip_title)
    return FileResponse(
        clip_path,
        media_type="video/mp4",
        filename=f"{safe_name}.mp4",
    )


@app.delete("/api/cleanup/{job_id}")
async def cleanup_job(job_id: str):
    upload_dir = os.path.join(UPLOAD_DIR, job_id)
    clips_dir = os.path.join(CLIPS_DIR, job_id)

    if os.path.isdir(upload_dir):
        shutil.rmtree(upload_dir)
    if os.path.isdir(clips_dir):
        shutil.rmtree(clips_dir)

    jobs.pop(job_id, None)
    return {"ok": True}


def _process(job_id: str):
    job = jobs[job_id]
    try:
        job["status"] = "processing"
        job["step"] = "Extracting audio from video…"
        job["progress"] = 10

        audio_path = extract_audio(job["video_path"])

        job["step"] = "Transcribing audio…"
        job["progress"] = 25

        transcript = transcribe_audio(audio_path)

        if not transcript:
            raise RuntimeError("Transcription returned no text — is the video silent?")

        job["step"] = "AI is analysing content for the best clips…"
        job["progress"] = 55

        segments, note = identify_segments(transcript, job["clip_count"])
        job["note"] = note

        job["step"] = "Trimming clips…"
        job["progress"] = 75

        clips_dir = os.path.join(CLIPS_DIR, job_id)
        os.makedirs(clips_dir, exist_ok=True)

        clips = []
        for i, seg in enumerate(segments):
            clip_path = os.path.join(clips_dir, f"clip_{i + 1}.mp4")
            trim_clip(job["video_path"], seg["start"], seg["end"], clip_path)
            pct = 75 + int(25 * (i + 1) / len(segments))
            job["progress"] = min(pct, 99)
            job["step"] = f"Trimming clip {i + 1}/{len(segments)}…"
            clips.append({
                "index": i,
                "title": seg["title"],
                "start": seg["start"],
                "end": seg["end"],
                "duration": round(seg["end"] - seg["start"], 1),
            })

        job["clips"] = clips
        job["status"] = "complete"
        job["step"] = "Done"
        job["progress"] = 100

        if os.path.exists(audio_path):
            os.remove(audio_path)

    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)
        job["step"] = "Failed"
