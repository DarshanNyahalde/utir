export type MetricSummary = {
  sample_count: number;
  mae_mw: number | null;
  rmse_mw: number | null;
  bias_mw: number | null;
  wape: number | null;
  underforecast_rate: number | null;
  underforecast_count: number;
  overforecast_count: number;
  p90_absolute_error_mw: number | null;
};

export type DecisionRow = {
  target_time: string;
  forecast_mw: number | null;
  actual_mw: number | null;
  forecast_publish_time: string | null;
  decision_cutoff: string;
  lead_time_hours: number | null;
  error_mw: number | null;
  absolute_error_mw: number | null;
  status: string;
};

export type DecisionResponse = {
  delivery_date: string;
  decision_cutoff: string;
  resolution: "hourly" | "half-hourly";
  data_source: string;
  rows: DecisionRow[];
  metrics: MetricSummary;
  metadata: Record<string, unknown>;
};

export type AccuracyResponse = {
  date_from: string;
  date_to: string;
  decision_cutoff: string;
  resolution: "hourly" | "half-hourly";
  data_source: string;
  metrics: MetricSummary;
  rows: DecisionRow[];
  daily: Array<Record<string, number | string | null>>;
  hourly: Array<Record<string, number | string | null>>;
  distribution: Array<Record<string, number | string | null>>;
  metadata: Record<string, unknown>;
};
