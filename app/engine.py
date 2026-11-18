import logging
import re

import torch
import whisper
from transformers import pipeline

from .config import Settings
from .schemas import AnalyzeResponse, Score

log = logging.getLogger("engine")
SAMPLE_RATE = 16000

# Whisper language code -> NLLB language code
LANG = {
    "en": "eng_Latn", "hi": "hin_Deva", "es": "spa_Latn", "fr": "fra_Latn",
    "de": "deu_Latn", "ar": "arb_Arab", "zh": "zho_Hans", "ja": "jpn_Jpan",
    "ko": "kor_Hang", "ru": "rus_Cyrl", "pt": "por_Latn", "it": "ita_Latn",
    "bn": "ben_Beng", "ta": "tam_Taml", "te": "tel_Telu", "mr": "mar_Deva",
    "ur": "urd_Arab", "gu": "guj_Gujr", "pa": "pan_Guru", "tr": "tur_Latn",
}


class AudioDecodeError(Exception):
    pass


class AudioTooLong(Exception):
    pass


def split_text(text: str, limit: int = 400) -> list[str]:
    sentences = re.split(r"(?<=[.!?।。！？])\s+", text.strip())
    chunks, cur = [], ""
    for s in sentences:
        while len(s) > limit:  # very long sentence without punctuation
            chunks.append(s[:limit])
            s = s[limit:]
        if len(cur) + len(s) + 1 <= limit:
            cur = f"{cur} {s}".strip()
        else:
            if cur:
                chunks.append(cur)
            cur = s
    if cur:
        chunks.append(cur)
    return chunks


def _scores(out) -> list[Score]:
    if out and isinstance(out[0], list):
        out = out[0]
    out = sorted(out, key=lambda d: d["score"], reverse=True)
    return [Score(label=d["label"], score=round(float(d["score"]), 4)) for d in out]


class Engine:
    def __init__(self, s: Settings):
        self.s = s
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        dev = 0 if self.device == "cuda" else -1
        log.info("Loading models on %s ...", self.device)

        self.whisper = whisper.load_model(s.whisper_model, device=self.device)
        self.translator = pipeline("translation", model=s.translation_model, device=dev)
        self.text_emotion = pipeline(
            "text-classification", model=s.text_emotion_model, top_k=None,
            truncation=True, max_length=512, device=dev)
        self.text_sentiment = pipeline(
            "text-classification", model=s.text_sentiment_model, top_k=None,
            truncation=True, max_length=512, device=dev)
        self.audio_emotion = None
        if s.enable_audio_emotion:
            self.audio_emotion = pipeline("audio-classification", model=s.audio_emotion_model, device=dev)
        log.info("Models ready.")

    def translate(self, text: str, src: str, tgt: str) -> str:
        if not text or src == tgt:
            return text
        parts = self.translator(split_text(text), src_lang=LANG[src], tgt_lang=LANG[tgt], max_length=512)
        return " ".join(p["translation_text"] for p in parts)

    def analyze(self, path, target: str) -> AnalyzeResponse:
        try:
            audio = whisper.load_audio(str(path))  # needs ffmpeg; 16 kHz mono float32
        except Exception as e:
            raise AudioDecodeError("Could not decode audio") from e
        if audio.size == 0:
            raise AudioDecodeError("No audio data")

        duration = audio.size / SAMPLE_RATE
        if duration > self.s.max_audio_seconds:
            raise AudioTooLong()

        result = self.whisper.transcribe(audio, task="transcribe", fp16=(self.device == "cuda"))
        transcript = result["text"].strip()
        lang = result["language"]
        warnings: list[str] = []
        translation = english = sentiment = emotion = voice = None

        if not transcript:
            warnings.append("No speech detected.")
        elif lang not in LANG:
            warnings.append(f"Detected language '{lang}' is not supported for translation/text emotion.")
        else:
            translation = self.translate(transcript, lang, target)
            if lang == "en":
                english = transcript
            elif target == "en":
                english = translation
            else:
                english = self.translate(transcript, lang, "en")
            # Text models are English-only, so they run on the English version.
            sentiment = _scores(self.text_sentiment(english))
            emotion = _scores(self.text_emotion(english))

        if self.audio_emotion is not None and transcript:
            clip = audio[: 30 * SAMPLE_RATE]  # first 30 s keeps it fast
            voice = _scores(self.audio_emotion({"raw": clip, "sampling_rate": SAMPLE_RATE}, top_k=5))

        return AnalyzeResponse(
            duration_seconds=round(duration, 2), detected_language=lang, transcript=transcript,
            target_language=target, translation=translation, text_sentiment=sentiment,
            text_emotion=emotion, voice_emotion=voice, warnings=warnings)
