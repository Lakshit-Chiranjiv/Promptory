"""
app/main.py

FastAPI application entrypoint.
Creates the app instance, mounts static files, registers all routers,
and ensures DB tables exist on startup.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine
import app.models  # noqa: F401 — must import models so they register with Base.metadata

from app.routes import prompts, versions, test_cases, runs, yaml_io
from app.routes import ui

# Create all tables that don't exist yet — safe to call on every startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Promptory",
    description="Self-hosted prompt version control",
    version="0.1.0",
)

# Serve files from static/ directory at /static URL prefix
app.mount("/static", StaticFiles(directory="static"), name="static")

# JSON API routes
app.include_router(prompts.router)
app.include_router(versions.router)
app.include_router(test_cases.router)
app.include_router(runs.router)
app.include_router(yaml_io.router)

# Browser UI routes (HTML pages) — registered last so /p/ and /v/ don't shadow API routes
app.include_router(ui.router)
