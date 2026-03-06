from faster_whisper import WhisperModel

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = WhisperModel("base", device="cpu", compute_type="int8")
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
