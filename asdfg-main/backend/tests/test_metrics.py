from backend.app.services.metrics import add_error_fields, summarize
import math


def test_metric_summary_uses_forecast_minus_actual_error():
    rows = [
        add_error_fields({"forecast_mw": 100, "actual_mw": 110}),
        add_error_fields({"forecast_mw": 200, "actual_mw": 180}),
    ]

    result = summarize(rows)

    assert result["sample_count"] == 2
    assert result["mae_mw"] == 15
    assert result["bias_mw"] == 5
    assert result["underforecast_rate"] == 0.5
    assert result["underforecast_count"] == 1
    assert result["overforecast_count"] == 1
    assert result["p90_absolute_error_mw"] == 20
    assert result["rmse_mw"] == round(math.sqrt(250), 2)


def test_metric_summary_ignores_missing_pairs():
    result = summarize([{"forecast_mw": None, "actual_mw": 100}])

    assert result["sample_count"] == 0
    assert result["mae_mw"] is None


def test_metric_definitions_and_direction_counts_include_only_valid_pairs():
    rows = [
        {"forecast_mw": 97, "actual_mw": 100},
        {"forecast_mw": 104, "actual_mw": 100},
        {"forecast_mw": 100, "actual_mw": 100},
        {"forecast_mw": 110, "actual_mw": 100},
        {"forecast_mw": None, "actual_mw": 100},
        {"forecast_mw": float("nan"), "actual_mw": 100},
    ]

    result = summarize(rows)

    assert result["sample_count"] == 4
    assert result["mae_mw"] == 4.25
    assert result["rmse_mw"] == round(math.sqrt(31.25), 2)
    assert result["bias_mw"] == 2.75
    assert result["p90_absolute_error_mw"] == 10
    assert result["underforecast_count"] == 1
    assert result["overforecast_count"] == 2
    assert result["underforecast_rate"] == 0.25


def test_add_error_fields_uses_forecast_minus_actual_and_does_not_mutate_input():
    row = {"forecast_mw": 95, "actual_mw": 100}

    result = add_error_fields(row)

    assert result["error_mw"] == -5
    assert result["absolute_error_mw"] == 5
    assert "error_mw" not in row
