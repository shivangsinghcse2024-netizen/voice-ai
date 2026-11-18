from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_keys: str = ""
    allowed_hosts: str = "localhost,127.0.0.1"
    allowed_origins: str = ""

    whisper_model: str = "base"
    translation_model: str = "facebook/nllb-200-distilled-600M"
    text_emotion_model: str = "j-hartmann/emotion-english-distilroberta-base"
    text_sentiment_model: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"
    audio_emotion_model: str = "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
    enable_audio_emotion: bool = True

    max_upload_mb: int = 25
    max_audio_seconds: int = 300
    rate_limit: str = "10/minute"
    max_concurrent_jobs: int = 2
    enable_docs: bool = False

    @property
    def key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if len(k.strip()) >= 32]

    @property
    def host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def origin_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
