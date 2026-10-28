from __future__ import annotations

import asyncio
import logging
import os
import time as monotonic_time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx


logger = logging.getLogger(__name__)
BASE_URL = os.getenv("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1").rstrip("/")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("ELEXON_REQUEST_TIMEOUT_SECONDS", "20"))
CACHE_TTL_SECONDS = max(0, int(os.getenv("ELEXON_CACHE_TTL_SECONDS", "300")))
_cache: dict[str, tuple[float, list[dict]]] = {}
_locks: dict[str, asyncio.Lock] = {}


class ElexonUnavailableError(RuntimeError):
    """Raised when Elexon is unavailable and no cached response can be used."""


def _rows(payload: Any) -> list[dict]:
    if isinstance(payload, list) and all(isinstance(row, dict) for row in payload):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        rows = payload["data"]
        if all(isinstance(row, dict) for row in rows):
            return rows
    raise ValueError("Unexpected response structure from Elexon dataset stream")


async def _get(path: str, params: dict[str, str]) -> tuple[list[dict], str]:
    cache_key = f"{path}?{sorted(params.items())}"
    lock = _locks.setdefault(cache_key, asyncio.Lock())
    async with lock:
        cached = _cache.get(cache_key)
        if cached and monotonic_time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
            return cached[1], "cached"

        try:
            timeout = httpx.Timeout(
                REQUEST_TIMEOUT_SECONDS,
                connect=min(REQUEST_TIMEOUT_SECONDS, 5),
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{BASE_URL}{path}", params=params)
                response.raise_for_status()
                result = _rows(response.json())
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("Elexon request failed for %s: %s", path, error)
            if cached:
                logger.info("Using previously retrieved Elexon response for %s", path)
                return cached[1], "stale-cache"
            raise ElexonUnavailableError(
                f"Elexon request failed for {path}"
            ) from error

        _cache[cache_key] = (monotonic_time.monotonic(), result)
        return result, "live"


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _forecast_publish_range(start: date, end: date) -> tuple[str, str]:
    start_time = datetime.combine(
        start - timedelta(days=3), datetime.min.time(), tzinfo=timezone.utc
    )
    end_time = datetime.combine(
        end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
    )
    return _utc_iso(start_time), _utc_iso(end_time)


async def fetch_elexon_data(
    start: date, end: date
) -> tuple[list[dict], list[dict], dict[str, str]]:
    publish_from, publish_to = _forecast_publish_range(start, end)
    actual_result, forecast_result = await asyncio.gather(
        _get(
            "/datasets/FUELHH/stream",
            {
                "settlementDateFrom": start.isoformat(),
                "settlementDateTo": end.isoformat(),
                "fuelType": "WIND",
            },
        ),
        _get(
            "/datasets/WINDFOR/stream",
            {
                "publishDateTimeFrom": publish_from,
                "publishDateTimeTo": publish_to,
            },
        ),
    )
    actuals, actual_cache = actual_result
    forecasts, forecast_cache = forecast_result
    return actuals, forecasts, {"FUELHH": actual_cache, "WINDFOR": forecast_cache}


async def fetch_dataset_preview(
    dataset: str,
    start: date,
    end: date,
    *,
    limit: int = 25,
) -> dict[str, Any]:
    """Fetch a small preview of a real BMRS dataset."""
    if dataset == "FUELHH":
        query = {
            "settlementDateFrom": start.isoformat(),
            "settlementDateTo": end.isoformat(),
            "fuelType": "WIND",
        }
        description = "Half-hourly actual generation filtered to fuelType=WIND"
        rows, cache_status = await _get("/datasets/FUELHH/stream", query)
    elif dataset == "WINDFOR":
        publish_from, publish_to = _forecast_publish_range(start, end)
        query = {
            "publishDateTimeFrom": publish_from,
            "publishDateTimeTo": publish_to,
        }
        description = "Published wind forecasts with target and publication timestamps"
        rows, cache_status = await _get("/datasets/WINDFOR/stream", query)
    else:
        raise ValueError("dataset must be FUELHH or WINDFOR")

    return {
        "dataset": dataset,
        "description": description,
        "source": f"{BASE_URL}/datasets/{dataset}/stream",
        "query": query,
        "returned_rows": len(rows),
        "cache_status": cache_status,
        "rows": rows[:limit],
    }
