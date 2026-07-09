"""
SoccerSolver API — entry point.

Run locally (from project root):
    uvicorn backend.main:app --reload

Run inside Docker (WORKDIR = /app/backend):
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import sys
from pathlib import Path

# Ensure the backend/ directory is on sys.path so plain imports
# (e.g.  from routers.search import router) work regardless of
# whether the app is started from the project root or from backend/.
_BACKEND_DIR = Path(__file__).parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(_BACKEND_DIR / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import chat, compare, profile, search

app = FastAPI(
    title="SoccerSolver API",
    description="Player search, profiles, comparisons, and conversational analytics.",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS — allow the Vite dev server and the production Nginx container
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # CRA / alternative dev server
        "http://localhost",       # Nginx in Docker
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
# compare MUST be registered before profile: /players/compare would otherwise
# be matched by profile's /{player_id} path parameter.
app.include_router(search.router,  prefix="/players", tags=["Players"])
app.include_router(compare.router, prefix="/players", tags=["Players"])
app.include_router(profile.router, prefix="/players", tags=["Players"])
app.include_router(chat.router,    prefix="/chat",    tags=["Chat"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Meta"])
def health() -> dict:
    """Liveness probe — returns immediately with no dependencies."""
    return {"status": "ok"}
