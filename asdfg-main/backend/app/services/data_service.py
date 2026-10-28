from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from .elexon_client import ElexonUnavailableError, fetch_elexon_data
from .forecast_selection import select_latest_forecast
from .metrics import add_error_fields
from .normalization import UK_TIMEZONE, normalize_actuals, normalize_forecasts


logger = logging.getLogger(__name__)
MIN_DATE = date(2026, 1, 1)
MAX_DATE = date(2026, 1, 31)
UTC = timezone.utc
_CUTOFF_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class DataUnavailableError(RuntimeError):
    """Raised when required upstream data cannot be loaded or validated."""


def parse_cutoff(delivery_date: date, cutoff: str) -> datetime:
    if not _CUTOFF_PATTERN.fullmatch(cutoff):
        raise ValueError("Decision cutoff must use 24-hour HH:MM format")
    hour, minute = (int(part) for part in cutoff.split(":"))
    local_date = delivery_date - timedelta(days=1)
    local_naive = datetime.combine(local_date, time(hour=hour, minute=minute))
    local_cutoff = local_naive.replace(tzinfo=UK_TIMEZONE, fold=0)
    utc_cutoff = local_cutoff.astimezone(UTC)
    if utc_cutoff.astimezone(UK_TIMEZONE).replace(tzinfo=None) != local_naive:
        raise ValueError("Decision cutoff falls in a non-existent UK daylight-saving time")
    return utc_cutoff


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _forecast_target_for_period(target_time: datetime) -> datetime:
    local_time = target_time.astimezone(UK_TIMEZONE)
    local_hour = local_time.replace(minute=0, second=0, microsecond=0)
    return local_hour.astimezone(UTC)


async def build_rows(
    start: date, end: date, cutoff: str, resolution: str = "half-hourly"
) -> tuple[list[dict], str, dict[str, Any]]:
    if resolution not in {"hourly", "half-hourly"}:
        raise ValueError("resolution must be 'hourly' or 'half-hourly'")
    if start > end:
        raise ValueError("The start date must be on or before the end date")

    try:
        actual_records, forecast_records, cache_status = await fetch_elexon_data(start, end)
        actuals = normalize_actuals(actual_records, resolution)
        forecasts = normalize_forecasts(forecast_records)
        current = datetime.combine(start, time.min, tzinfo=UK_TIMEZONE).astimezone(UTC)
        end_time = datetime.combine(
            end + timedelta(days=1), time.min, tzinfo=UK_TIMEZONE
        ).astimezone(UTC)
        period_size = timedelta(minutes=30) if resolution == "half-hourly" else timedelta(hours=1)
        rows = []

        while current < end_time:
            local_delivery_date = current.astimezone(UK_TIMEZONE).date()
            decision_cutoff = parse_cutoff(local_delivery_date, cutoff)
            forecast_target = _forecast_target_for_period(current)
            selected = select_latest_forecast(forecasts, forecast_target, decision_cutoff)
            actual = actuals.get(current)
            forecast = selected["forecast_mw"] if selected else None
            publish_time = selected["published_at"] if selected else None
            lead_time = (
                round((forecast_target - publish_time).total_seconds() / 3600, 2)
                if publish_time
                else None
            )
            status = (
                "Missing forecast"
                if forecast is None
                else "Missing actual"
                if actual is None
                else "Underforecast"
                if forecast < actual
                else "Overforecast"
                if forecast > actual
                else "On target"
            )
            row = {
                "target_time": _iso_utc(current),
                "forecast_mw": forecast,
                "actual_mw": actual,
                "forecast_publish_time": _iso_utc(publish_time) if publish_time else None,
                "decision_cutoff": _iso_utc(decision_cutoff),
                "lead_time_hours": lead_time,
                "status": status,
            }
            rows.append(add_error_fields(row))
            current += period_size

        metadata = {
            "actual_record_count": len(actual_records),
            "forecast_record_count": len(forecast_records),
            "actual_filter": "fuelType=WIND",
            "timezone": "Europe/London",
            "cache_status": cache_status,
            "normalization": (
                "FUELHH readings retain their 30-minute startTime. Each hourly WINDFOR "
                "forecast is applied to its two half-hourly actual periods."
                if resolution == "half-hourly"
                else "Hourly FUELHH actuals are the arithmetic mean of both "
                "30-minute average-power readings; incomplete hours are excluded."
            ),
        }
        return rows, "Elexon BMRS", metadata
    except (ElexonUnavailableError, ValueError, KeyError, TypeError) as error:
        logger.exception("Could not build normalized Elexon forecast rows")
        raise DataUnavailableError(
            "Elexon FUELHH/WINDFOR data could not be loaded or validated. "
            "Retry after checking the upstream service."
        ) from error


def filter_rows(rows: list[dict], start: date, end: date) -> list[dict]:
    start_time = datetime.combine(start, time.min, tzinfo=UK_TIMEZONE).astimezone(UTC)
    end_time = datetime.combine(
        end + timedelta(days=1), time.min, tzinfo=UK_TIMEZONE
    ).astimezone(UTC)
    return [
        row
        for row in rows
        if start_time
        <= datetime.fromisoformat(row["target_time"].replace("Z", "+00:00"))
        < end_time
    ]
