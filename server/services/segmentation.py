import json
import math
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

MAX_RETRIES = 3
MIN_CLIP_SECONDS = 10
MAX_CLIP_SECONDS = 90
CLIP_COVERAGE_RATIO = 0.6


def _compute_max_clips(total_duration: float, requested: int) -> int:
    usable = total_duration * CLIP_COVERAGE_RATIO
    max_possible = max(1, math.floor(usable / MIN_CLIP_SECONDS))
    return min(requested, max_possible)


def _build_prompt(transcript_text: str, total_duration: float, count: int) -> str:
    return f"""You are a professional short-form video editor. Your job is to pick the best clips from a longer video for Instagram Reels.

Below is a timestamped transcript. Find up to {count} clips that each work as a standalone, engaging short video.

RULES:
1. Each clip must be a COMPLETE thought — start where a sentence begins, end where the point is fully made. NEVER cut mid-sentence.
2. "start" must equal the start timestamp of a transcript line. "end" must equal the end timestamp of a transcript line.
3. Each clip: {MIN_CLIP_SECONDS}–{MAX_CLIP_SECONDS} seconds.
4. No overlapping clips.
5. Skip filler: greetings ("hey guys"), outros ("like and subscribe"), ums, repetition.
6. Quality over quantity — only return clips that are genuinely interesting. If only 2 good moments exist, return 2.
7. Vary clip lengths — NOT every clip the same duration.

EXAMPLE:
Transcript:
[0.0s - 8.2s] Hey everyone welcome back to the channel.
[8.2s - 22.5s] Most people think AI will replace all jobs but the data shows something completely different.
[22.5s - 45.0s] A recent MIT study found only 23 percent of tasks could be automated cost-effectively. The rest need human judgment creativity and emotional intelligence.
[45.0s - 58.3s] The jobs most at risk are not creative jobs. It is repetitive data entry and simple pattern matching.
[58.3s - 70.0s] So if you want to be AI-proof focus on critical thinking empathy and complex problem solving.
[70.0s - 82.0s] Anyway let me know in the comments and subscribe.

Good output for 2 clips:
[{{"start": 8.2, "end": 45.0, "title": "AI Won't Replace Most Jobs"}}, {{"start": 45.0, "end": 70.0, "title": "How to Be AI-Proof"}}]

Intro (0–8.2s) and outro (70–82s) skipped. Each clip is a complete argument. Lengths differ.

BAD output (NEVER do this):
[{{"start": 0, "end": 15, "title": "Part 1"}}, {{"start": 15, "end": 30, "title": "Part 2"}}]
This is wrong — equal sequential chunks that cut mid-sentence with generic titles.

VIDEO DURATION: {total_duration:.1f}s

TRANSCRIPT:
{transcript_text}

Return ONLY a JSON array. No markdown, no explanation.
JSON:"""


def _call_gemini(prompt: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.3,
            max_output_tokens=2048,
        ),
    )
    return response.text.strip()


def _call_ollama(prompt: str) -> str:
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.4, "num_predict": 2048},
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()


def identify_segments(
    transcript: list[dict], clip_count: int
) -> tuple[list[dict], str | None]:
    total_duration = transcript[-1]["end"] if transcript else 0
    effective_count = _compute_max_clips(total_duration, clip_count)

    adjusted_note = None
    if effective_count < clip_count:
        adjusted_note = (
            f"The video is {total_duration:.0f}s long. Producing {clip_count} "
            f"quality clips isn't feasible without cutting mid-sentence or "
            f"overlapping, so {effective_count} strong clip"
            f"{'s were' if effective_count != 1 else ' was'} generated instead."
        )

    transcript_text = "\n".join(
        f"[{s['start']:.1f}s - {s['end']:.1f}s] {s['text']}"
        for s in transcript
    )
    prompt = _build_prompt(transcript_text, total_duration, effective_count)

    call_fn = _call_gemini if AI_PROVIDER == "gemini" else _call_ollama

    for attempt in range(MAX_RETRIES):
        try:
            raw = call_fn(prompt)
            segments = _parse_json_array(raw)
            validated = _validate_segments(segments, transcript, effective_count)
            if validated:
                return validated, adjusted_note
        except (json.JSONDecodeError, KeyError, ValueError, Exception) as exc:
            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(
                    f"Could not get valid segments after {MAX_RETRIES} attempts "
                    f"({AI_PROVIDER}): {exc}"
                )

    return [], adjusted_note


def _validate_segments(
    raw_segments: list[dict], transcript: list[dict], max_clips: int
) -> list[dict]:
    total_duration = transcript[-1]["end"] if transcript else 0
    validated = []

    for seg in raw_segments:
        try:
            start = max(0.0, float(seg["start"]))
            end = min(total_duration, float(seg["end"]))
        except (KeyError, TypeError, ValueError):
            continue

        duration = end - start
        if duration < MIN_CLIP_SECONDS or duration > MAX_CLIP_SECONDS:
            continue

        start = _snap_to_transcript(start, transcript, "start")
        end = _snap_to_transcript(end, transcript, "end")

        if end - start < MIN_CLIP_SECONDS:
            continue

        overlaps = any(
            not (end <= v["start"] or start >= v["end"]) for v in validated
        )
        if overlaps:
            continue

        validated.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "title": str(seg.get("title", f"Clip {len(validated) + 1}")),
        })
        if len(validated) >= max_clips:
            break

    validated.sort(key=lambda s: s["start"])
    return validated


def _snap_to_transcript(time_val: float, transcript: list[dict], key: str) -> float:
    best = time_val
    best_dist = float("inf")
    for seg in transcript:
        dist = abs(seg[key] - time_val)
        if dist < best_dist:
            best_dist = dist
            best = seg[key]
    return best


def _parse_json_array(text: str) -> list:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise json.JSONDecodeError("No JSON array found", text, 0)
