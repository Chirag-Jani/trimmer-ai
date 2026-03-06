import os
import subprocess


def extract_audio(video_path: str) -> str:
    audio_path = os.path.splitext(video_path)[0] + ".wav"
    subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            audio_path, "-y",
        ],
        check=True,
        capture_output=True,
    )
    return audio_path


def trim_clip(video_path: str, start: float, end: float, output_path: str) -> str:
    duration = end - start
    subprocess.run(
        [
            "ffmpeg",
            "-ss", str(start),
            "-i", video_path,
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-movflags", "+faststart",
            output_path, "-y",
        ],
        check=True,
        capture_output=True,
    )
    return output_path
