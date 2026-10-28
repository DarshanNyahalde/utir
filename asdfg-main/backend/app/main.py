from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .schemas import AccuracyResponse, DecisionResponse, DecisionRow, MetricSummary
from .services.data_service import (
    DataUnavailableError,
    MAX_DATE,
    MIN_DATE,
    build_rows,
    parse_cutoff,
)
from .services.elexon_client import ElexonUnavailableError, fetch_dataset_preview
from .services.metrics import summarize
from .services.normalization import UK_TIMEZONE, parse_timestamp


logger = logging.getLogger(__name__)
app = FastAPI(title="WindReady API", version="0.2.0")
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "WINDREADY_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/", include_in_schema=False)
async def frontend_index():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "service": "windready-api",
        "message": "Frontend build not found; use the Vite development server.",
    }


def validate_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise HTTPException(
            status_code=400, detail="Use an ISO date such as 2026-01-15"
        ) from error
    if not MIN_DATE <= parsed <= MAX_DATE:
        raise HTTPException(
            status_code=400, detail="The challenge scope is January 2026"
        )
    return parsed


def resolve_cutoff(decision_cutoff: str | None, cutoff: str | None) -> str:
    if decision_cutoff and cutoff and decision_cutoff != cutoff:
        raise HTTPException(
            status_code=400,
            detail="Use either decision_cutoff or cutoff, not conflicting values",
        )
    selected = decision_cutoff or cutoff or "23:59"
    return selected


def validate_cutoff(value: str, delivery_date: date) -> None:
    try:
        parse_cutoff(delivery_date, value)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _decision_response(
    delivery_date: date,
    cutoff: str,
    resolution: str,
    rows: list[dict],
    source: str,
    metadata: dict,
) -> DecisionResponse:
    cutoff_value = rows[0]["decision_cutoff"] if rows else cutoff
    return DecisionResponse(
        delivery_date=delivery_date.isoformat(),
        decision_cutoff=cutoff_value,
        resolution=resolution,
        data_source=source,
        rows=[DecisionRow(**row) for row in rows],
        metrics=MetricSummary(**summarize(rows)),
        metadata=metadata,
    )


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "windready-api", "scope": "January 2026"}


@app.get("/api/dates")
async def dates() -> dict:
    return {"dates": [date(2026, 1, day).isoformat() for day in range(1, 32)]}


@app.get("/api/metadata")
async def metadata() -> dict:
    return {
        "actual_dataset": "FUELHH",
        "forecast_dataset": "WINDFOR",
        "actual_filter": "fuelType=WIND",
        "date_range": {"from": MIN_DATE.isoformat(), "to": MAX_DATE.isoformat()},
        "resolution_options": ["half-hourly", "hourly"],
        "default_resolution": "half-hourly",
        "hourly_aggregation": (
            "Arithmetic mean of both half-hourly average-power readings; "
            "incomplete hours are excluded."
        ),
        "timezone": "Europe/London",
        "default_cutoff": "23:59 UK local time on the day before delivery",
    }


async def dataset_preview(
    dataset: str, date_from: str, date_to: str, limit: int
) -> dict:
    parsed_from = validate_date(date_from)
    parsed_to = validate_date(date_to)
    if parsed_from > parsed_to:
        raise HTTPException(
            status_code=400, detail="The from date must be before the to date"
        )
    try:
        return await fetch_dataset_preview(
            dataset, parsed_from, parsed_to, limit=limit
        )
    except (ElexonUnavailableError, ValueError) as error:
        logger.warning("Elexon %s preview failed: %s", dataset, error)
        raise HTTPException(
            status_code=503, detail=f"Elexon {dataset} data is unavailable"
        ) from error


@app.get("/api/datasets/fuelhh")
async def fuelhh_preview(
    date_from: str = Query("2026-01-15", alias="from"),
    date_to: str = Query("2026-01-15", alias="to"),
    limit: int = Query(25, ge=1, le=100),
) -> dict:
    return await dataset_preview("FUELHH", date_from, date_to, limit)


@app.get("/api/datasets/windfor")
async def windfor_preview(
    date_from: str = Query("2026-01-15", alias="from"),
    date_to: str = Query("2026-01-15", alias="to"),
    limit: int = Query(25, ge=1, le=100),
) -> dict:
    return await dataset_preview("WINDFOR", date_from, date_to, limit)


async def _load_decision_response(
    delivery_date: str,
    decision_cutoff: str | None,
    cutoff: str | None,
    resolution: str,
) -> DecisionResponse:
    parsed_date = validate_date(delivery_date)
    selected_cutoff = resolve_cutoff(decision_cutoff, cutoff)
    validate_cutoff(selected_cutoff, parsed_date)
    try:
        rows, source, data_metadata = await build_rows(
            parsed_date, parsed_date, selected_cutoff, resolution
        )
    except DataUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return _decision_response(
        parsed_date, selected_cutoff, resolution, rows, source, data_metadata
    )


@app.get("/api/decision-view", response_model=DecisionResponse)
async def decision_view(
    delivery_date: str,
    decision_cutoff: str | None = None,
    cutoff: str | None = None,
    resolution: str = Query("half-hourly", pattern="^(half-hourly|hourly)$"),
) -> DecisionResponse:
    return await _load_decision_response(
        delivery_date, decision_cutoff, cutoff, resolution
    )


@app.get("/api/period-details", response_model=DecisionResponse)
async def period_details(
    delivery_date: str,
    decision_cutoff: str | None = None,
    cutoff: str | None = None,
    resolution: str = Query("half-hourly", pattern="^(half-hourly|hourly)$"),
    target_time: str | None = None,
) -> DecisionResponse:
    response = await _load_decision_response(
        delivery_date, decision_cutoff, cutoff, resolution
    )
    if target_time is None:
        return response

    try:
        selected_time = parse_timestamp(target_time)
    except ValueError as error:
        raise HTTPException(
            status_code=400, detail="target_time must be an ISO timestamp"
        ) from error
    selected_rows = [
        row
        for row in response.rows
        if parse_timestamp(row.target_time) == selected_time
    ]
    if not selected_rows:
        raise HTTPException(
            status_code=404, detail="No delivery period matches target_time"
        )
    return DecisionResponse(
        delivery_date=response.delivery_date,
        decision_cutoff=response.decision_cutoff,
        resolution=response.resolution,
        data_source=response.data_source,
        rows=selected_rows,
        metrics=MetricSummary(
            **summarize([row.model_dump() for row in selected_rows])
        ),
        metadata=response.metadata,
    )


@app.get("/api/accuracy", response_model=AccuracyResponse, include_in_schema=False)
@app.get("/api/accuracy-analysis", response_model=AccuracyResponse)
async def accuracy(
    date_from: str | None = None,
    date_to: str | None = None,
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    decision_cutoff: str | None = None,
    cutoff: str | None = None,
    resolution: str = Query("half-hourly", pattern="^(half-hourly|hourly)$"),
) -> AccuracyResponse:
    if date_from and from_date and date_from != from_date:
        raise HTTPException(status_code=400, detail="Conflicting start-date parameters")
    if date_to and to_date and date_to != to_date:
        raise HTTPException(status_code=400, detail="Conflicting end-date parameters")

    parsed_from = validate_date(date_from or from_date or MIN_DATE.isoformat())
    parsed_to = validate_date(date_to or to_date or MAX_DATE.isoformat())
    if parsed_from > parsed_to:
        raise HTTPException(
            status_code=400, detail="The from date must be before the to date"
        )
    selected_cutoff = resolve_cutoff(decision_cutoff, cutoff)
    validate_cutoff(selected_cutoff, parsed_from)
    validate_cutoff(selected_cutoff, parsed_to)

    try:
        rows, source, data_metadata = await build_rows(
            parsed_from, parsed_to, selected_cutoff, resolution
        )
    except DataUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    valid_rows = [row for row in rows if row["error_mw"] is not None]
    daily_groups: dict[str, list[dict]] = defaultdict(list)
    hourly_groups: dict[int, list[dict]] = defaultdict(list)
    for row in valid_rows:
        local_time = parse_timestamp(row["target_time"]).astimezone(UK_TIMEZONE)
        daily_groups[local_time.date().isoformat()].append(row)
        hourly_groups[local_time.hour].append(row)

    daily = [
        {"date": day, **summarize(group)}
        for day, group in sorted(daily_groups.items())
    ]
    hourly = [
        {"hour": hour, **summarize(group)}
        for hour, group in sorted(hourly_groups.items())
    ]
    distribution = [
        {
            "target_time": row["target_time"],
            "error_mw": row["error_mw"],
            "absolute_error_mw": row["absolute_error_mw"],
        }
        for row in valid_rows
    ]
    data_metadata["date_range"] = {
        "from": parsed_from.isoformat(),
        "to": parsed_to.isoformat(),
    }
    data_metadata["decision_cutoff_local"] = selected_cutoff
    data_metadata["cutoff_timezone"] = "Europe/London"
    data_metadata["cutoff_applies_to"] = "the day before each delivery date"
    return AccuracyResponse(
        date_from=parsed_from.isoformat(),
        date_to=parsed_to.isoformat(),
        decision_cutoff=selected_cutoff,
        resolution=resolution,
        data_source=source,
        metrics=MetricSummary(**summarize(rows)),
        rows=[DecisionRow(**row) for row in rows],
        daily=daily,
        hourly=hourly,
        distribution=distribution,
        metadata=data_metadata,
    )
