import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.requests import Request
import uvicorn

from backend import get_runtime_info, run_workflow


app = FastAPI(title="Self-Correcting Multi-Agent App")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")



class RunRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=20000)


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


@app.post("/api/run")
def run_agents(payload: RunRequest):
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Please enter a topic.")

    try:
        return run_workflow(topic)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc





if __name__ == "__main__":
    # DigitalOcean App Platform provides PORT automatically.
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
