from contextlib import asynccontextmanager
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request

from app.db.session import AsyncSessionLocal
from app.routers.admin import router as admin_router
from app.routers import reports, routing
from app.services.safety_dataset_cache import safety_dataset_cache

LOGGER = logging.getLogger(__name__)
_cache_ready = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _cache_ready
    _cache_ready = False

    if "pytest" not in sys.modules:
        try:
            async with AsyncSessionLocal() as session:
                await safety_dataset_cache.warm_cache(session)
            _cache_ready = True
        except Exception as exc:  # pragma: no cover - startup should degrade gracefully
            LOGGER.warning("Safety dataset cache warmup skipped: %s", exc)
    else:
        _cache_ready = True

    yield


app = FastAPI(
    title="WalkSafe API",
    description="Safety-aware pedestrian navigation API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        # ngrok tunnel — update this when your tunnel URL changes.
        "https://unflickering-marissa-lingually.ngrok-free.dev",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "ngrok-skip-browser-warning"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


class NgrokHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response


app.add_middleware(NgrokHeaderMiddleware)

app.include_router(admin_router)
app.include_router(routing.router)
app.include_router(reports.router)


@app.get("/")
async def root():
    return {"message": "WalkSafe API is running", "status": "online"}


@app.get("/ready")
async def readiness():
    """
    Kubernetes/load-balancer style readiness probe.
    Returns 200 when the safety dataset cache is warmed and ready to serve requests.
    Returns 503 during startup warmup.
    """
    if not _cache_ready:
        return JSONResponse(
            status_code=503,
            content={
                "ready": False,
                "reason": "Safety dataset cache warming up",
            },
        )
    return {"ready": True}
