import json
import logging
import math
import os
import re
import time

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

log = logging.getLogger("segmentation")
logging.basicConfig(level=logging.INFO)

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

MAX_RETRIES = 3
MIN_CLIP_SECONDS = 15
MAX_CLIP_SECONDS = 50
CLIP_COVERAGE_RATIO = 0.6

# Consecutive transcript lines shorter than this gap are merged into one block
_MERGE_GAP_SECONDS = 1.5


def _compress_transcript(transcript: list[dict]) -> list[dict]:
    """Merge consecutive short transcript segments into paragraph-sized blocks."""
    if not transcript:
        return []

    blocks: list[dict] = []
    current = {
        "start": transcript[0]["start"],
        "end": transcript[0]["end"],
        "text": transcript[0]["text"],
    }

    for seg in transcript[1:]:
        gap = seg["start"] - current["end"]
        combined_text = current["text"] + " " + seg["text"]
        combined_dur = seg["end"] - current["start"]

        # Merge if gap is small and combined block stays under ~30s
        if gap <= _MERGE_GAP_SECONDS and combined_dur < 30:
            current["end"] = seg["end"]
            current["text"] = combined_text
        else:
            blocks.append(current)
            current = {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
            }

    blocks.append(current)
    return blocks


def _compute_max_clips(total_duration: float, requested: int) -> int:
    usable = total_duration * CLIP_COVERAGE_RATIO
    max_possible = max(1, math.floor(usable / MIN_CLIP_SECONDS))
    return min(requested, max_possible)


def _build_prompt(transcript_text: str, total_duration: float, count: int) -> str:
    return f"""You are an elite short-form video editor. Create the best possible Instagram Reels from a longer video.

CRITICAL — STITCHING:
A clip can combine MULTIPLE non-contiguous parts of the video into one. If related content is spread across different timestamps, stitch them together. Example: speaker introduces a topic at 0:30 and delivers the punchline at 2:15 — combine both into ONE clip.

If a section works great on its own, keep it as a single continuous segment.

RULES:
1. Each clip = ONE complete story/argument. Viewer must understand it standalone.
2. Segments in a clip must be chronological.
3. Boundaries must align with transcript block boundaries. Use exact start/end times from the blocks below.
4. Total duration per clip: {MIN_CLIP_SECONDS}–{MAX_CLIP_SECONDS}s.
5. No time range in more than one clip.
6. Quality > quantity. If only 1 great clip exists, return 1. Do NOT pad.
7. Skip filler: greetings, outros, repetition, "um", "you know".
8. Specific catchy titles, not "Part 1".

EXAMPLE:
Transcript:
[0.0s - 6.0s] Hey everyone welcome back let us dive in.
[6.0s - 35.0s] Most people think AI will replace all jobs but a MIT study found only 23 percent of tasks can be automated cost-effectively.
[35.0s - 62.0s] Take graphic designers. Everyone thought they were done. But AI handles repetitive resizing while designers focus on creative direction.
[62.0s - 78.0s] The jobs at real risk are not creative ones. It is repetitive data entry and pattern matching.
[78.0s - 90.0s] So be AI-proof. Build critical thinking empathy and complex problem solving.
[90.0s - 100.0s] Drop your thoughts below and hit subscribe.

Output:
[
  {{
    "title": "Why AI Won't Kill 77% of Jobs",
    "segments": [{{"start": 6.0, "end": 35.0}}, {{"start": 62.0, "end": 78.0}}]
  }},
  {{
    "title": "The Graphic Designer Paradox",
    "segments": [{{"start": 35.0, "end": 62.0}}, {{"start": 78.0, "end": 90.0}}]
  }}
]

Clip 1 stitches thesis + risk analysis. Clip 2 stitches example + takeaway. Intro/outro skipped.

VIDEO: {total_duration:.1f}s. Create up to {count} clips.

TRANSCRIPT:
{transcript_text}

Return ONLY a JSON array. No markdown, no explanation.
JSON:"""


def _call_gemini(prompt: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    for attempt in range(3):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=2048,
                ),
            )
            return response.text.strip()
        except Exception as exc:
            if "429" in str(exc) and attempt < 2:
                wait = (attempt + 1) * 10
                log.warning("Gemini 429 — waiting %ds before retry", wait)
                time.sleep(wait)
                continue
            raise

    return ""


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

    compressed = _compress_transcript(transcript)
    log.info(
        "Transcript: %d raw segments → %d compressed blocks",
        len(transcript), len(compressed),
    )

    transcript_text = "\n".join(
        f"[{b['start']:.1f}s - {b['end']:.1f}s] {b['text']}"
        for b in compressed
    )
    prompt = _build_prompt(transcript_text, total_duration, effective_count)
    log.info("Prompt length: %d chars, provider: %s", len(prompt), AI_PROVIDER)

    call_fn = _call_gemini if AI_PROVIDER == "gemini" else _call_ollama

    for attempt in range(MAX_RETRIES):
        try:
            raw = call_fn(prompt)
            log.info("AI response (attempt %d):\n%s", attempt + 1, raw[:500])

            parsed = _parse_json_array(raw)
            validated = _validate_clips(parsed, compressed, effective_count)

            if validated:
                log.info("Validated %d clips", len(validated))
                return validated, adjusted_note

            log.warning("Attempt %d: parsed %d clips but none passed validation", attempt + 1, len(parsed))

        except Exception as exc:
            log.error("Attempt %d failed: %s", attempt + 1, exc)
            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(
                    f"Could not get valid clips after {MAX_RETRIES} attempts "
                    f"({AI_PROVIDER}): {exc}"
                )

    return [], adjusted_note


def _validate_clips(
    raw_clips: list[dict], transcript: list[dict], max_clips: int
) -> list[dict]:
    total_duration = transcript[-1]["end"] if transcript else 0
    used_ranges: list[tuple[float, float]] = []
    validated = []

    for clip in raw_clips:
        title = str(clip.get("title", f"Clip {len(validated) + 1}"))

        raw_segments = clip.get("segments")
        if not raw_segments or not isinstance(raw_segments, list):
            if "start" in clip and "end" in clip:
                raw_segments = [{"start": clip["start"], "end": clip["end"]}]
            else:
                continue

        clean_segs = []
        clip_ok = True
        for seg in raw_segments:
            try:
                s = max(0.0, float(seg["start"]))
                e = min(total_duration, float(seg["end"]))
            except (KeyError, TypeError, ValueError):
                clip_ok = False
                break

            s = _snap_to_transcript(s, transcript, "start")
            e = _snap_to_transcript(e, transcript, "end")

            if e - s < 3:
                clip_ok = False
                break

            for us, ue in used_ranges:
                if not (e <= us or s >= ue):
                    clip_ok = False
                    break
            if not clip_ok:
                break

            clean_segs.append({"start": round(s, 2), "end": round(e, 2)})

        if not clip_ok or not clean_segs:
            continue

        total_clip_dur = sum(seg["end"] - seg["start"] for seg in clean_segs)
        if total_clip_dur < MIN_CLIP_SECONDS or total_clip_dur > MAX_CLIP_SECONDS:
            log.info("Clip '%s' rejected: duration %.1fs", title, total_clip_dur)
            continue

        clean_segs.sort(key=lambda x: x["start"])
        for seg in clean_segs:
            used_ranges.append((seg["start"], seg["end"]))

        validated.append({
            "title": title,
            "segments": clean_segs,
            "duration": round(total_clip_dur, 1),
        })

        if len(validated) >= max_clips:
            break

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
