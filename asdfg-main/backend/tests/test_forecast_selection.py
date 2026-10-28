from datetime import datetime, timezone

from backend.app.services.forecast_selection import select_latest_forecast


def test_selects_latest_forecast_before_cutoff():
    target = datetime(2026, 1, 15, 10, tzinfo=timezone.utc)
    cutoff = datetime(2026, 1, 14, 23, 59, tzinfo=timezone.utc)
    forecasts = [
        {"target_time": target, "published_at": datetime(2026, 1, 14, 18, tzinfo=timezone.utc), "forecast_mw": 100},
        {"target_time": target, "published_at": datetime(2026, 1, 14, 22, 30, tzinfo=timezone.utc), "forecast_mw": 110},
        {"target_time": target, "published_at": datetime(2026, 1, 15, 1, tzinfo=timezone.utc), "forecast_mw": 120},
    ]

    selected = select_latest_forecast(forecasts, target, cutoff)

    assert selected["forecast_mw"] == 110


def test_returns_none_when_no_forecast_is_available():
    target = datetime(2026, 1, 15, 10, tzinfo=timezone.utc)
    cutoff = datetime(2026, 1, 14, 23, 59, tzinfo=timezone.utc)

    assert select_latest_forecast([], target, cutoff) is None


def test_rejects_forecast_published_after_the_cutoff():
    target = datetime(2026, 1, 15, 10, tzinfo=timezone.utc)
    cutoff = datetime(2026, 1, 14, 23, 59, tzinfo=timezone.utc)
    forecast = {
        "target_time": target,
        "published_at": datetime(2026, 1, 15, 0, tzinfo=timezone.utc),
        "forecast_mw": 120,
    }

    assert select_latest_forecast([forecast], target, cutoff) is None


def test_selection_compares_timestamp_offsets_as_instants():
    target = datetime.fromisoformat("2026-01-15T10:00:00+00:00")
    cutoff = datetime.fromisoformat("2026-01-14T23:59:00+00:00")
    forecast = {
        "target_time": datetime.fromisoformat("2026-01-15T11:00:00+01:00"),
        "published_at": datetime.fromisoformat("2026-01-15T00:30:00+01:00"),
        "forecast_mw": 120,
    }

    assert select_latest_forecast([forecast], target, cutoff) == forecast
