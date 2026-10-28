from __future__ import annotations

from datetime import datetime

from .normalization import parse_timestamp


def select_latest_forecast(
    forecasts: list[dict], target_time: datetime, cutoff: datetime
) -> dict | None:
    target_utc = parse_timestamp(target_time)
    cutoff_utc = parse_timestamp(cutoff)
    candidates = [
        forecast
        for forecast in forecasts
        if parse_timestamp(forecast["target_time"]) == target_utc
        and parse_timestamp(forecast["published_at"]) <= cutoff_utc
    ]
    if not candidates:
        return None

    newest_publication = max(parse_timestamp(item["published_at"]) for item in candidates)
    newest = [
        item
        for item in candidates
        if parse_timestamp(item["published_at"]) == newest_publication
    ]
    values = {float(item["forecast_mw"]) for item in newest}
    if len(values) > 1:
        raise ValueError(
            f"Conflicting forecasts for {target_utc.isoformat()} "
            f"published at {newest_publication.isoformat()}"
        )
    return newest[0]
