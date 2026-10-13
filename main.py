"""FastAPI main application entry point for Bruviti License & Cost Analytics.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List
import logging

from fastapi import FastAPI, Query, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import (
    HealthResponse,
    SummaryResponse,
    ToolMetricsResponse,
    ErrorResponse
)
from app.data_loader import DataLoader, DataLoaderError
from app.organization import UnknownOrganizationError
from app.metrics import MetricsEngine

logger = logging.getLogger("bruviti_analytics")
logging.basicConfig(level=logging.INFO)

# Base directories
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))

# Global data loader instance
data_loader = DataLoader(data_dir=str(DATA_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load and validate datasets on application startup."""
    try:
        data_loader.load_from_directory()
        logger.info("Successfully loaded and validated datasets on startup.")
    except Exception as exc:
        logger.error(f"Startup dataset loading failed: {exc}")
    yield


app = FastAPI(
    title="Bruviti Software License Usage & Cost Analytics API",
    description="REST API for software license usage, cost analytics, and seat optimization",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def validate_query_dates(
    from_str: Optional[str] = Query(None, alias="from", description="Start date YYYY-MM-DD"),
    to_str: Optional[str] = Query(None, alias="to", description="End date YYYY-MM-DD"),
    org: Optional[str] = Query(None, description="Optional organization unit ID")
) -> tuple[date, date, Optional[str]]:
    """Validate query parameters, enforcing YYYY-MM-DD format and chronological order."""
    if from_str is None or from_str.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required query parameter: 'from'"
        )

    if to_str is None or to_str.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required query parameter: 'to'"
        )

    try:
        from_date = datetime.strptime(from_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format for 'from': '{from_str}'. Expected YYYY-MM-DD."
        )

    try:
        to_date = datetime.strptime(to_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format for 'to': '{to_str}'. Expected YYYY-MM-DD."
        )

    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The 'from' date ({from_date}) must be less than or equal to the 'to' date ({to_date})."
        )

    clean_org = org.strip() if org and org.strip() else None
    return from_date, to_date, clean_org


def get_engine() -> MetricsEngine:
    """Dependency that returns the MetricsEngine or raises 503 if data is unready."""
    if not data_loader.is_loaded():
        # Attempt just-in-time reload
        try:
            data_loader.load_from_directory()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service unavailable: dataset loading error - {exc}"
            )
    container = data_loader.get_container()
    return MetricsEngine(container)


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check and readiness status",
    responses={
        200: {"description": "Service is healthy and ready"},
        503: {"description": "Service is unready (datasets not loaded)"}
    }
)
def get_health():
    """Returns status ok only if datasets are loaded and validated."""
    if not data_loader.is_loaded():
        try:
            data_loader.load_from_directory()
        except Exception as exc:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy", "error": str(exc)}
            )
    return {"status": "ok"}


@app.get(
    "/api/summary",
    response_model=SummaryResponse,
    summary="Aggregate license usage and cost summary",
    responses={
        200: {"model": SummaryResponse},
        400: {"model": ErrorResponse, "description": "Invalid date range or format"},
        404: {"model": ErrorResponse, "description": "Unknown organization ID"},
        503: {"model": ErrorResponse, "description": "Service not ready"}
    }
)
def get_summary(
    params: tuple[date, date, Optional[str]] = Depends(validate_query_dates),
    engine: MetricsEngine = Depends(get_engine)
):
    """Calculate overall licensed users, active users, engagement %, spend, and idle spend."""
    from_date, to_date, org = params
    try:
        summary, _ = engine.calculate_metrics(from_date=from_date, to_date=to_date, org=org)
        return summary
    except UnknownOrganizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc)
        )


@app.get(
    "/api/tools",
    response_model=List[ToolMetricsResponse],
    summary="Tool-wise license usage and cost metrics",
    responses={
        200: {"model": List[ToolMetricsResponse]},
        400: {"model": ErrorResponse, "description": "Invalid date range or format"},
        404: {"model": ErrorResponse, "description": "Unknown organization ID"},
        503: {"model": ErrorResponse, "description": "Service not ready"}
    }
)
def get_tools(
    params: tuple[date, date, Optional[str]] = Depends(validate_query_dates),
    engine: MetricsEngine = Depends(get_engine)
):
    """Calculate tool metrics for Tools A through E in canonical order."""
    from_date, to_date, org = params
    try:
        _, tools_metrics = engine.calculate_metrics(from_date=from_date, to_date=to_date, org=org)
        return tools_metrics
    except UnknownOrganizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc)
        )


@app.get("/", summary="Dashboard single-page interface")
def serve_index():
    """Serve the root dashboard HTML page."""
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="index.html not found in templates directory"
        )
    return FileResponse(str(index_file))
