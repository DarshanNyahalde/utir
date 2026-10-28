from fastapi.testclient import TestClient

from backend.app import main


client = TestClient(main.app)


def test_decision_endpoint_rejects_dates_outside_january():
    response = client.get(
        "/api/decision-view",
        params={"delivery_date": "2026-02-01"},
    )

    assert response.status_code == 400
    assert "January 2026" in response.json()["detail"]


def test_decision_endpoint_validates_cutoff_and_resolution():
    invalid_cutoff = client.get(
        "/api/decision-view",
        params={"delivery_date": "2026-01-15", "decision_cutoff": "25:00"},
    )
    invalid_resolution = client.get(
        "/api/decision-view",
        params={
            "delivery_date": "2026-01-15",
            "decision_cutoff": "12:00",
            "resolution": "quarter-hourly",
        },
    )

    assert invalid_cutoff.status_code == 400
    assert invalid_resolution.status_code == 422


def test_accuracy_endpoint_rejects_out_of_scope_and_reversed_ranges():
    out_of_scope = client.get(
        "/api/accuracy-analysis",
        params={"date_from": "2026-01-01", "date_to": "2026-02-01"},
    )
    reversed_range = client.get(
        "/api/accuracy-analysis",
        params={"date_from": "2026-01-20", "date_to": "2026-01-10"},
    )

    assert out_of_scope.status_code == 400
    assert reversed_range.status_code == 400


def test_period_details_and_decision_view_return_consistent_calculated_metrics(monkeypatch):
    row = {
        "target_time": "2026-01-15T00:00:00Z",
        "forecast_mw": 90,
        "actual_mw": 100,
        "forecast_publish_time": "2026-01-14T23:00:00Z",
        "decision_cutoff": "2026-01-14T23:59:00Z",
        "lead_time_hours": 1,
        "error_mw": -10,
        "absolute_error_mw": 10,
        "status": "Underforecast",
    }

    async def build_rows(*args, **kwargs):
        return [row], "Elexon BMRS", {"cache_status": {"FUELHH": "live"}}

    monkeypatch.setattr(main, "build_rows", build_rows)
    params = {
        "delivery_date": "2026-01-15",
        "decision_cutoff": "23:59",
        "resolution": "half-hourly",
    }

    decision = client.get("/api/decision-view", params=params)
    details = client.get("/api/period-details", params=params)
    one_period = client.get(
        "/api/period-details",
        params={**params, "target_time": "2026-01-15T00:00:00Z"},
    )
    outside_period = client.get(
        "/api/period-details",
        params={**params, "target_time": "2026-01-15T00:30:00Z"},
    )

    assert decision.status_code == 200
    assert details.status_code == 200
    assert one_period.status_code == 200
    assert outside_period.status_code == 404
    payload = decision.json()
    assert payload["decision_cutoff"] == "2026-01-14T23:59:00Z"
    assert payload["metrics"]["mae_mw"] == 10
    assert payload["metrics"]["bias_mw"] == -10
    assert payload["metrics"]["underforecast_count"] == 1
    assert payload["rows"] == details.json()["rows"]
    assert len(one_period.json()["rows"]) == 1
    assert one_period.json()["metrics"]["mae_mw"] == 10
