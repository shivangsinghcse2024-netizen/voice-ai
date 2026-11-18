import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .config import get_settings
from .engine import LANG, AudioDecodeError, AudioTooLong, Engine
from .schemas import AnalyzeResponse
from .security import is_valid_key, save_upload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.key_list:
        raise RuntimeError("No valid API_KEYS configured (each key must be 32+ chars). See .env.example.")
    app.state.engine = Engine(settings)
    app.state.sem = asyncio.Semaphore(settings.max_concurrent_jobs)
    yield


app = FastAPI(
    title="Voice Translator & Emotion Analyzer",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

CSP = ("default-src 'none'; script-src 'self' https://accounts.google.com https://*.gstatic.com; "
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://accounts.google.com; "
       "connect-src 'self' https://accounts.google.com; "
       "frame-src https://accounts.google.com; "
       "media-src blob; img-src 'self' data: https://*.google.com https://*.gstatic.com; "
       "base-uri 'none'; frame-ancestors 'none'")

@app.middleware("http")
async def guard(request: Request, call_next):
    path = request.url.path
    if path.startswith("/v1/") and request.method != "OPTIONS":
        # Allow /v1/languages without requiring an API key
        if path != "/v1/languages" and not is_valid_key(request.headers.get("x-api-key"), ""):
            return JSONResponse({"detail": "Invalid or missing API key"}, status_code=401)
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > settings.max_upload_mb * 1024 * 1024 * 1_048_576:
            return JSONResponse({"detail": "File too large"}, status_code=413)
    
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if path.startswith("/v1/"):
        response.headers["Cache-Control"] = "no-store"
        if path != "/v1/languages" and not path.startswith(("/docs", "/openapi")):
            response.headers["Content-Security-Policy"] = CSP
    return response


# Added after `guard` so they wrap it (CORS preflight is answered before auth).
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.host_list)
if settings.origin_list:
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.origin_list, allow_methods=["GET", "POST"],
        allow_headers=["X-API-Key", "Content-Type"], allow_credentials=False)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def read_login():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/translator", include_in_schema=False)
async def read_translator():
    return FileResponse(STATIC_DIR / "translator.html")

@app.get("/analytics", include_in_schema=False)
async def read_analytics():
    return FileResponse(STATIC_DIR / "analytics.html")

@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


@app.get("/v1/languages")
async def languages():
    return {"target_languages": sorted(LANG)}


@app.post("/v1/analyze", response_model=AnalyzeResponse)
@limiter.limit(settings.rate_limit)
async def analyze(request: Request, file: UploadFile = File(...), target_language: str = Form("en")):
    target = target_language.strip().lower()
    if target not in LANG:
        raise HTTPException(422, f"Unsupported target_language. Use one of {sorted(LANG)}")

    path = await save_upload(file, settings.max_upload_mb * 1024 * 1024)
    try:
        async with request.app.state.sem:
            return await run_in_threadpool(request.app.state.engine.analyze, path, target)
    except AudioTooLong:
        raise HTTPException(413, f"Audio longer than {settings.max_audio_seconds}s")
    except AudioDecodeError:
        raise HTTPException(422, "Could not read this audio file")
    except HTTPException:
        raise
    except Exception:
        logging.getLogger("api").exception("Processing failed")  # no user content logged
        raise HTTPException(500, "Internal error")
    finally:
        path.unlink(missing_ok=True)  # uploaded audio is always deleted
