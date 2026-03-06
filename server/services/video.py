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


def build_clip(video_path: str, segments: list[dict], output_path: str) -> str:
    """Build a clip from one or more segments, stitching if needed."""
    if len(segments) == 1:
        seg = segments[0]
        return _trim_single(video_path, seg["start"], seg["end"], output_path)

    return _stitch_segments(video_path, segments, output_path)


def _trim_single(video_path: str, start: float, end: float, output_path: str) -> str:
    subprocess.run(
        [
            "ffmpeg",
            "-ss", str(start),
            "-i", video_path,
            "-t", str(end - start),
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


def _stitch_segments(
    video_path: str, segments: list[dict], output_path: str
) -> str:
    n = len(segments)
    filter_parts = []

    for i, seg in enumerate(segments):
        filter_parts.append(
            f"[0:v]trim=start={seg['start']}:end={seg['end']},"
            f"setpts=PTS-STARTPTS[v{i}];"
        )
        filter_parts.append(
            f"[0:a]atrim=start={seg['start']}:end={seg['end']},"
            f"asetpts=PTS-STARTPTS[a{i}];"
        )

    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
    filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[v][a]")

    subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-filter_complex", "".join(filter_parts),
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-c:a", "aac",
            "-preset", "fast",
            "-movflags", "+faststart",
            output_path, "-y",
        ],
        check=True,
        capture_output=True,
    )
    return output_path
