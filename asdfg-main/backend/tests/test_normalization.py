import pytest

from backend.app.services.normalization import (
    normalize_actuals,
    normalize_forecasts,
    parse_timestamp,
)


def test_half_hour_actuals_are_averaged_to_hour():
    records = [
        {"startTime": "2026-01-01T10:00:00Z", "generation": 100, "fuelType": "WIND"},
        {"startTime": "2026-01-01T10:30:00Z", "generation": 140, "fuelType": "WIND"},
        {"startTime": "2026-01-01T10:00:00Z", "generation": 999, "fuelType": "SOLAR"},
    ]

    result = normalize_actuals(records)

    assert result[parse_timestamp("2026-01-01T10:00:00Z")] == 120


def test_half_hour_resolution_preserves_timestamps_and_uses_latest_actual_revision():
    records = [
        {
            "startTime": "2026-01-01T10:30:00Z",
            "publishTime": "2026-01-01T11:00:00Z",
            "generation": 140,
            "fuelType": "WIND",
        },
        {
            "startTime": "2026-01-01T10:30:00Z",
            "publishTime": "2026-01-01T12:00:00Z",
            "generation": 160,
            "fuelType": "WIND",
        },
        {
            "startTime": "2026-01-01T10:30:00Z",
            "publishTime": "2026-01-01T13:00:00Z",
            "generation": 900,
            "fuelType": "SOLAR",
        },
    ]

    result = normalize_actuals(records, resolution="half-hourly")

    assert result == {parse_timestamp("2026-01-01T10:30:00Z"): 160}


def test_hourly_actual_is_missing_when_one_half_hour_is_missing():
    records = [
        {
            "startTime": "2026-01-01T10:00:00Z",
            "generation": 100,
            "fuelType": "WIND",
        }
    ]

    assert normalize_actuals(records, resolution="hourly") == {}


def test_conflicting_duplicate_actual_at_same_publication_is_rejected():
    records = [
        {
            "startTime": "2026-01-01T10:00:00Z",
            "publishTime": "2026-01-01T10:30:00Z",
            "generation": 100,
            "fuelType": "WIND",
        },
        {
            "startTime": "2026-01-01T10:00:00Z",
            "publishTime": "2026-01-01T10:30:00Z",
            "generation": 101,
            "fuelType": "WIND",
        },
    ]

    with pytest.raises(ValueError, match="Conflicting FUELHH records"):
        normalize_actuals(records, resolution="half-hourly")


def test_forecast_duplicates_are_deduplicated_and_conflicting_revisions_rejected():
    record = {
        "startTime": "2026-01-01T10:00:00Z",
        "publishTime": "2026-01-01T09:00:00Z",
        "generation": 100,
    }

    assert len(normalize_forecasts([record, record])) == 1
    with pytest.raises(ValueError, match="Conflicting WINDFOR records"):
        normalize_forecasts([record, {**record, "generation": 101}])


def test_timestamps_are_normalized_to_utc():
    assert parse_timestamp("2026-01-15T11:00:00+01:00") == parse_timestamp(
        "2026-01-15T10:00:00Z"
    )
