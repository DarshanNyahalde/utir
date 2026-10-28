from __future__ import annotations

import math
from statistics import mean
from typing import Iterable


def _valid_rows(rows: Iterable[dict]) -> list[tuple[float, float]]:
    valid = []
    for row in rows:
        forecast = row.get("forecast_mw")
        actual = row.get("actual_mw")
        if forecast is None or actual is None:
            continue
        forecast_value = float(forecast)
        actual_value = float(actual)
        if math.isfinite(forecast_value) and math.isfinite(actual_value):
            valid.append((forecast_value, actual_value))
    return valid


def summarize(rows: Iterable[dict]) -> dict:
    valid = _valid_rows(rows)
    if not valid:
        return {
            "sample_count": 0,
            "mae_mw": None,
            "rmse_mw": None,
            "bias_mw": None,
            "wape": None,
            "underforecast_rate": None,
            "underforecast_count": 0,
            "overforecast_count": 0,
            "p90_absolute_error_mw": None,
        }

    errors = [forecast - actual for forecast, actual in valid]
    absolute_errors = [abs(error) for error in errors]
    total_actual = sum(actual for _, actual in valid)
    sorted_absolute = sorted(absolute_errors)
    p90_index = math.ceil(0.9 * len(sorted_absolute)) - 1
    underforecast_count = sum(error < 0 for error in errors)
    overforecast_count = sum(error > 0 for error in errors)

    return {
        "sample_count": len(valid),
        "mae_mw": round(mean(absolute_errors), 2),
        "rmse_mw": round(math.sqrt(mean(error**2 for error in errors)), 2),
        "bias_mw": round(mean(errors), 2),
        "wape": round(sum(absolute_errors) / total_actual, 4) if total_actual else None,
        "underforecast_rate": round(underforecast_count / len(errors), 4),
        "underforecast_count": underforecast_count,
        "overforecast_count": overforecast_count,
        "p90_absolute_error_mw": round(sorted_absolute[p90_index], 2),
    }


def add_error_fields(row: dict) -> dict:
    result = dict(row)
    forecast = result.get("forecast_mw")
    actual = result.get("actual_mw")
    if forecast is None or actual is None:
        result.update({"error_mw": None, "absolute_error_mw": None})
        return result
    error = float(forecast) - float(actual)
    if not math.isfinite(error):
        result.update({"error_mw": None, "absolute_error_mw": None})
        return result
    result.update({"error_mw": round(error, 2), "absolute_error_mw": round(abs(error), 2)})
    return result
