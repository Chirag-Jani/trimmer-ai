import os

from dotenv import load_dotenv
from faster_whisper import WhisperModel

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


def transcribe_audio(audio_path: str) -> list[dict]:
    model = _get_model()
    segments, _info = model.transcribe(audio_path, beam_size=5)

    transcript = []
    for seg in segments:
        transcript.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })

    return transcript
