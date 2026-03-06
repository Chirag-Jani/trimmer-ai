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
MIN_CLIP_SECONDS = 15
MAX_CLIP_SECONDS = 50
CLIP_COVERAGE_RATIO = 0.6


def _compute_max_clips(total_duration: float, requested: int) -> int:
    usable = total_duration * CLIP_COVERAGE_RATIO
    max_possible = max(1, math.floor(usable / MIN_CLIP_SECONDS))
    return min(requested, max_possible)


def _build_prompt(transcript_text: str, total_duration: float, count: int) -> str:
    return f"""You are an elite short-form video editor. Your job: create the most engaging, viral-worthy Instagram Reels from a longer video.

CRITICAL CONCEPT — STITCHING NON-CONTIGUOUS PARTS:
A single clip does NOT have to be one continuous section of the video. You can combine multiple separate parts into one clip if they together tell a more complete or compelling story. Think like a documentary editor:
- Speaker introduces a concept at 0:30, gives an example at 1:45, then delivers the punchline at 3:10? Stitch all three into ONE clip.
- A great point is made at 0:20 but the supporting evidence comes at 2:00? Combine them.
- Of course, if a section already works perfectly on its own, keep it as a single continuous segment.

RULES:
1. Each clip must tell ONE complete, self-contained story/argument. The viewer must understand it without seeing the full video.
2. Segments within a clip must be in chronological order from the video.
3. Every segment boundary must align with a sentence boundary — NEVER cut mid-sentence. Use the exact start/end timestamps from transcript lines.
4. Total duration per clip (sum of all its segments): {MIN_CLIP_SECONDS}–{MAX_CLIP_SECONDS} seconds.
5. A given time range must NOT appear in more than one clip.
6. Quality over quantity. Return UP TO {count} clips, but if only 1 or 2 are genuinely great, return only those. Do NOT pad with mediocre clips.
7. Skip all filler: greetings ("hey guys welcome"), outros ("like and subscribe"), throat-clearing, repetition.
8. Give each clip a specific, catchy title (not generic like "Part 1").

OUTPUT FORMAT — JSON array. Each clip has:
- "title": string — short, specific, catchy
- "segments": array of {{"start": <number>, "end": <number>}} objects

EXAMPLE with a sample transcript:
Transcript:
[0.0s - 6.0s] Hey everyone welcome back let us dive in.
[6.0s - 18.5s] Most people think AI will replace all jobs but a new MIT study says otherwise.
[18.5s - 35.0s] They found only 23 percent of worker tasks can be automated cost-effectively right now.
[35.0s - 48.0s] Let me give you an example. Graphic designers everyone thought they were done right.
[48.0s - 62.0s] But turns out AI handles the repetitive resizing and formatting while designers focus on creative direction and client relationships.
[62.0s - 78.0s] And here is what most people miss. The jobs at real risk are not creative ones. It is repetitive data entry and simple pattern matching.
[78.0s - 90.0s] So the takeaway if you want to be AI-proof build skills machines cannot replicate. Critical thinking empathy complex problem solving.
[90.0s - 100.0s] Drop your thoughts below and hit subscribe.

Good output (2 clips):
[
  {{
    "title": "Why AI Won't Kill 77% of Jobs",
    "segments": [
      {{"start": 6.0, "end": 35.0}},
      {{"start": 62.0, "end": 78.0}}
    ]
  }},
  {{
    "title": "The Graphic Designer Paradox",
    "segments": [
      {{"start": 35.0, "end": 62.0}},
      {{"start": 78.0, "end": 90.0}}
    ]
  }}
]

Why this is good:
- Clip 1 stitches the core thesis (6–35s) with the risk analysis (62–78s) — two non-contiguous parts that together make a complete argument.
- Clip 2 combines the example (35–62s) with the actionable takeaway (78–90s).
- Intro and outro skipped. Each clip is self-contained. Lengths vary. Titles are specific.

BAD output:
[{{"title": "Part 1", "segments": [{{"start": 0, "end": 20}}]}}, {{"title": "Part 2", "segments": [{{"start": 20, "end": 40}}]}}]
This is wrong — sequential equal chunks, generic titles, cuts mid-thought, includes intro.

Now here is the real transcript. Create up to {count} clips.

VIDEO DURATION: {total_duration:.1f}s

TRANSCRIPT:
{transcript_text}

Return ONLY a JSON array. No markdown fences, no explanation, no text before or after.
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
            parsed = _parse_json_array(raw)
            validated = _validate_clips(parsed, transcript, effective_count)
            if validated:
                return validated, adjusted_note
        except Exception as exc:
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
            # Legacy single start/end format fallback
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

            # Check overlap with already-used ranges
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
