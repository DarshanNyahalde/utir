from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MetricSummary(BaseModel):
    sample_count: int
    mae_mw: float | None
    rmse_mw: float | None
    bias_mw: float | None
    wape: float | None
    underforecast_rate: float | None
    underforecast_count: int
    overforecast_count: int
    p90_absolute_error_mw: float | None


class DecisionRow(BaseModel):
    target_time: str
    forecast_mw: float | None
    actual_mw: float | None
    forecast_publish_time: str | None
    decision_cutoff: str
    lead_time_hours: float | None
    error_mw: float | None
    absolute_error_mw: float | None
    status: str


class DecisionResponse(BaseModel):
    delivery_date: str
    decision_cutoff: str
    resolution: str
    data_source: str
    rows: list[DecisionRow]
    metrics: MetricSummary
    metadata: dict[str, Any]


class AccuracyResponse(BaseModel):
    date_from: str
    date_to: str
    decision_cutoff: str
    resolution: str
    data_source: str
    metrics: MetricSummary
    rows: list[DecisionRow]
    daily: list[dict[str, Any]]
    hourly: list[dict[str, Any]]
    distribution: list[dict[str, Any]]
    metadata: dict[str, Any]
