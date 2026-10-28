import asyncio
from datetime import date, datetime, timezone

import pytest

from backend.app.services import data_service
from backend.app.services.elexon_client import ElexonUnavailableError


def test_source_failure_is_not_replaced_with_synthetic_rows(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise ElexonUnavailableError("network unavailable")

    monkeypatch.setattr(data_service, "fetch_elexon_data", unavailable)

    with pytest.raises(data_service.DataUnavailableError):
        asyncio.run(data_service.build_rows(date(2026, 1, 15), date(2026, 1, 15), "23:59"))


def _record(start_time, generation):
    return {
        "startTime": start_time,
        "publishTime": "2026-01-16T00:00:00Z",
        "generation": generation,
        "fuelType": "WIND",
    }


def test_build_rows_selects_only_latest_forecast_before_local_cutoff(monkeypatch):
    target = "2026-01-15T00:00:00Z"
    actuals = [
        _record("2026-01-15T00:00:00Z", 100),
        _record("2026-01-15T00:30:00Z", 120),
        _record("2026-01-15T01:00:00Z", 200),
        _record("2026-01-15T01:30:00Z", 220),
    ]
    forecasts = [
        {
            "startTime": target,
            "publishTime": "2026-01-14T22:30:00Z",
            "generation": 90,
        },
        {
            "startTime": target,
            "publishTime": "2026-01-14T23:58:00Z",
            "generation": 110,
        },
        {
            "startTime": target,
            "publishTime": "2026-01-14T23:59:01Z",
            "generation": 150,
        },
        {
            "startTime": "2026-01-15T01:00:00Z",
            "publishTime": "2026-01-15T00:01:00Z",
            "generation": 250,
        },
    ]

    async def fetched(*args, **kwargs):
        return actuals, forecasts, {"FUELHH": "live", "WINDFOR": "live"}

    monkeypatch.setattr(data_service, "fetch_elexon_data", fetched)
    rows, _, _ = asyncio.run(
        data_service.build_rows(
            date(2026, 1, 15), date(2026, 1, 15), "23:59", "half-hourly"
        )
    )

    assert len(rows) == 48
    assert rows[0]["forecast_mw"] == 110
    assert rows[1]["forecast_mw"] == 110
    assert rows[0]["forecast_publish_time"] == "2026-01-14T23:58:00Z"
    assert rows[2]["forecast_mw"] is None
    assert rows[0]["status"] == "Overforecast"
    assert rows[1]["status"] == "Underforecast"
    assert rows[3]["status"] == "Missing forecast"


def test_hourly_rows_average_two_half_hour_actuals_without_summing(monkeypatch):
    actuals = [
        _record("2026-01-15T00:00:00Z", 100),
        _record("2026-01-15T00:30:00Z", 140),
    ]
    forecasts = [
        {
            "startTime": "2026-01-15T00:00:00Z",
            "publishTime": "2026-01-14T23:00:00Z",
            "generation": 130,
        }
    ]

    async def fetched(*args, **kwargs):
        return actuals, forecasts, {"FUELHH": "live", "WINDFOR": "live"}

    monkeypatch.setattr(data_service, "fetch_elexon_data", fetched)
    rows, _, metadata = asyncio.run(
        data_service.build_rows(
            date(2026, 1, 15), date(2026, 1, 15), "23:59", "hourly"
        )
    )

    assert len(rows) == 24
    assert rows[0]["actual_mw"] == 120
    assert rows[0]["forecast_mw"] == 130
    assert rows[1]["actual_mw"] is None
    assert "arithmetic mean" in metadata["normalization"]


def test_cutoff_uses_uk_timezone_with_daylight_saving_transitions():
    spring_cutoff = data_service.parse_cutoff(date(2026, 3, 30), "08:00")
    ambiguous_fall_cutoff = data_service.parse_cutoff(date(2026, 10, 26), "01:30")

    assert spring_cutoff == datetime(2026, 3, 29, 7, tzinfo=timezone.utc)
    assert ambiguous_fall_cutoff == datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc)


def test_cutoff_rejects_nonexistent_local_daylight_saving_time():
    with pytest.raises(ValueError, match="non-existent"):
        data_service.parse_cutoff(date(2026, 3, 30), "01:30")
