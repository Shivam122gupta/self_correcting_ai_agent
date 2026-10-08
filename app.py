import logging
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from backend import get_runtime_info, run_workflow

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("app")

app = FastAPI(
    title="Self-Correcting Multi-Agent App",
    docs_url=None,  # Disable Swagger UI in production to avoid endpoint discovery by bots
    redoc_url=None, # Disable ReDoc in production
)

# -----------------------------------------------------------------------------
# 1. Security Headers Middleware
# -----------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# -----------------------------------------------------------------------------
# 2. CORS Middleware
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# -----------------------------------------------------------------------------
# 3. Rate Limiter (Sliding Window in Memory)
# -----------------------------------------------------------------------------
class SimpleRateLimiter:
    """Zero-dependency memory rate limiter for bot & spam protection."""
    def __init__(self, requests_per_minute: int = 5):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)

    def is_rate_limited(self, ip: str) -> bool:
        now = time.time()
        window_start = now - 60
        # Filter timestamps older than 60 seconds
        self.requests[ip] = [ts for ts in self.requests[ip] if ts > window_start]
        if len(self.requests[ip]) >= self.requests_per_minute:
            return True
        self.requests[ip].append(now)
        return False

# Rate limiter instance: Max 5 workflow executions per minute per IP address
run_rate_limiter = SimpleRateLimiter(requests_per_minute=5)

def check_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    if run_rate_limiter.is_rate_limited(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Too many requests. Please wait a minute before trying again.",
            headers={"Retry-After": "60"},
        )

# -----------------------------------------------------------------------------
# 4. Input Payload Validation & Sanitization
# -----------------------------------------------------------------------------
class RunRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=2000, description="Topic to generate workflow for")

    @field_validator("topic")
    @classmethod
    def sanitize_topic(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Topic cannot be empty or blank space.")
        # Strip potential HTML/Script tags for XSS protection
        cleaned = re.sub(r"<[^>]*>", "", cleaned)
        return cleaned

# -----------------------------------------------------------------------------
# 5. Routes
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "runtime": get_runtime_info(),
        },
    )


@app.get("/app", response_class=HTMLResponse)
def workspace(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="workspace.html",
        context={
            "example_topic": "Explain the System Design of Apache Kafka with architecture and component tables",
            "runtime": get_runtime_info(),
        },
    )


@app.api_route("/health", methods=["GET", "HEAD", "POST", "OPTIONS"])
@app.api_route("/ping", methods=["GET", "HEAD", "POST", "OPTIONS"])
def health_check():
    """Health check endpoint for UptimeRobot / uptime monitors to keep server awake 24/7."""
    return {"status": "ok", "healthy": True}


@app.get("/api/config")
def config():
    """Safe runtime information for the UI/demo. Never returns secrets."""
    return get_runtime_info()


@app.post("/api/run", dependencies=[Depends(check_rate_limit)])
async def run_agents(payload: RunRequest):
    topic = payload.topic
    logger.info(f"Processing AI workflow request for topic length: {len(topic)}")

    try:
        # Run heavy synchronous LangGraph AI workflow in async threadpool so it doesn't block server threads
        result = await run_in_threadpool(run_workflow, topic)
        return result
    except Exception as exc:
        logger.error(f"Error executing AI workflow: {exc}", exc_info=True)
        # Return sanitized error message without leaking sensitive internal system paths or API keys
        err_msg = str(exc)
        if "API" in err_msg or "key" in err_msg.lower():
            err_detail = "AI Service temporarily unavailable or rate-limited. Please try again shortly."
        else:
            err_detail = f"Failed to execute workflow: {err_msg[:150]}"
        raise HTTPException(status_code=500, detail=err_detail)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
