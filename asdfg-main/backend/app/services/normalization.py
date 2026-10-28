from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


UK_TIMEZONE = ZoneInfo("Europe/London")


def parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _generation(record: dict) -> float | None:
    value = record.get("generation")
    if value is None:
        return None
    generation = float(value)
    if not math.isfinite(generation):
        return None
    return generation


def _published_at(record: dict) -> datetime:
    value = record.get("publishTime")
    return parse_timestamp(value) if value else datetime.min.replace(tzinfo=timezone.utc)


def normalize_actuals(
    records: list[dict], resolution: str = "hourly"
) -> dict[datetime, float]:
    if resolution not in {"hourly", "half-hourly"}:
        raise ValueError("resolution must be 'hourly' or 'half-hourly'")

    latest: dict[datetime, tuple[datetime, float]] = {}
    for record in records:
        if record.get("fuelType") != "WIND":
            continue
        start_time = record.get("startTime")
        generation = _generation(record)
        if not start_time or generation is None:
            continue

        timestamp = parse_timestamp(start_time)
        published_at = _published_at(record)
        previous = latest.get(timestamp)
        if previous is None or published_at > previous[0]:
            latest[timestamp] = (published_at, generation)
        elif published_at == previous[0] and generation != previous[1]:
            raise ValueError(
                f"Conflicting FUELHH records for {timestamp.isoformat()} "
                f"published at {published_at.isoformat()}"
            )

    if resolution == "half-hourly":
        return {timestamp: value for timestamp, (_, value) in latest.items()}

    buckets: dict[datetime, dict[datetime, float]] = defaultdict(dict)
    for timestamp, (_, generation) in latest.items():
        local_time = timestamp.astimezone(UK_TIMEZONE)
        hour_start = local_time.replace(minute=0, second=0, microsecond=0)
        bucket_start = hour_start.astimezone(timezone.utc)
        buckets[bucket_start][timestamp] = generation

    normalized: dict[datetime, float] = {}
    for bucket_start, values in buckets.items():
        expected = {bucket_start, bucket_start + timedelta(minutes=30)}
        if set(values) == expected:
            normalized[bucket_start] = round(sum(values.values()) / 2, 2)
    return normalized


def normalize_forecasts(records: list[dict]) -> list[dict]:
    unique: dict[tuple[datetime, datetime], dict] = {}
    for record in records:
        start_time = record.get("startTime")
        publish_time = record.get("publishTime")
        generation = _generation(record)
        if not start_time or not publish_time or generation is None:
            continue

        target_time = parse_timestamp(start_time)
        published_at = parse_timestamp(publish_time)
        key = (target_time, published_at)
        previous = unique.get(key)
        if previous is not None and previous["forecast_mw"] != generation:
            raise ValueError(
                f"Conflicting WINDFOR records for {target_time.isoformat()} "
                f"published at {published_at.isoformat()}"
            )
        unique[key] = {
            "target_time": target_time,
            "published_at": published_at,
            "forecast_mw": generation,
        }
    return list(unique.values())
