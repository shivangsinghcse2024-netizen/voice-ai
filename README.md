# Multilingual Voice Translator & Emotion Analyzer

Audio -> Whisper (speech-to-text) -> NLLB (translation) -> emotion/sentiment (text + voice tone). FastAPI backend with a small web UI.

## 1. Prerequisites
- Python 3.10 or 3.11
- ffmpeg (required by Whisper)
  - Windows: `winget install Gyan.FFmpeg`  (restart terminal)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt update && sudo apt install ffmpeg`
- ~6 GB free disk and ~6 GB RAM (models download on first run). First start is slow.

## 2. Install
```bash
cd voice-ai
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install --upgrade pip
# CPU-only PyTorch (smaller). For NVIDIA GPU use the command from pytorch.org instead.
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

## 3. Configure
```bash
cp .env.example .env                # Windows: copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
Paste the generated key into `API_KEYS=` in `.env`. Never commit `.env`.

## 4. Run
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Wait for "Models ready." Then open http://127.0.0.1:8000, paste your API key, upload/record audio, click Analyze.

## 5. Test with curl
```bash
curl -X POST http://127.0.0.1:8000/v1/analyze \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@sample.wav" -F "target_language=hi"
```

## 6. Docker (optional)
```bash
docker build -t voice-ai .
docker run -d --name voice-ai --env-file .env -p 127.0.0.1:8000:8000 voice-ai
```

## 7. Production hardening checklist
1. Put it behind HTTPS (Caddy example below). Never expose plain HTTP to the internet.
2. Set `ALLOWED_HOSTS` to your domain; keep `ENABLE_DOCS=false`.
3. Set the proxy body limit (Caddy: `request_body { max_size 26MB }`, nginx: `client_max_body_size 26m;`).
4. Bind uvicorn to 127.0.0.1 and let only the proxy reach it; use `--proxy-headers` so rate limiting sees real IPs.
5. Use one key per client; rotate by editing `API_KEYS` (comma-separated) and restarting.
6. Keep dependencies updated (`pip list --outdated`, `pip-audit`).
7. Add fail2ban / WAF rules on repeated 401s at the proxy.

Caddyfile:
```
voice.example.com {
    request_body { max_size 26MB }
    reverse_proxy 127.0.0.1:8000
}
```

## Built-in protections
- API key required on /v1/* (constant-time compare), checked before the upload is read
- Per-IP rate limiting, concurrent-job cap, upload size + extension + duration limits
- Uploads go to private temp files and are always deleted; transcripts are never logged
- Trusted-host check, optional strict CORS, CSP/nosniff/frame/HSTS headers, docs off by default
- UI renders results with textContent (no XSS), container runs as non-root

## Limitations
- Text emotion/sentiment models are English-only, so non-English speech is translated to English first.
- Voice-tone emotion model is trained on English speech; treat results for other languages as approximate.
- Emotion detection is probabilistic; do not use it for decisions about people.
- The UI keeps the API key in the page only; for a public product, add real user login instead.

## Troubleshooting
- `ffmpeg not found`: install it and reopen the terminal.
- `No valid API_KEYS`: key missing or under 32 characters.
- Out of memory: set `WHISPER_MODEL=tiny` and `ENABLE_AUDIO_EMOTION=false`.
- 400 Invalid host header: add the host to `ALLOWED_HOSTS`.
