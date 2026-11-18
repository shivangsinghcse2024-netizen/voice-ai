from typing import Optional

from pydantic import BaseModel


class Score(BaseModel):
    label: str
    score: float


class AnalyzeResponse(BaseModel):
    duration_seconds: float
    detected_language: str
    transcript: str
    target_language: str
    translation: Optional[str] = None
    text_sentiment: Optional[list[Score]] = None   # positive / neutral / negative
    text_emotion: Optional[list[Score]] = None     # joy, anger, sadness, ...
    voice_emotion: Optional[list[Score]] = None    # from the tone of the voice itself
    warnings: list[str] = []
