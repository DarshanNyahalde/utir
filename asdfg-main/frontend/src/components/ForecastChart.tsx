import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DecisionRow } from "../types";

function formatHour(value: string) {
  return new Date(value).toLocaleTimeString([], {
    timeZone: "Europe/London",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function ForecastTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ payload: DecisionRow & { forecast: number | null; actual: number | null } }>; label?: string }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const publicationTime = row.forecast_publish_time
    ? new Date(row.forecast_publish_time).toLocaleString([], {
        timeZone: "Europe/London",
        hour: "2-digit",
        minute: "2-digit",
        timeZoneName: "short",
      })
    : "—";
  return <div className="chart-tooltip"><strong>Delivery {label} (UK)</strong><span>Forecast <b>{row.forecast === null ? "—" : `${row.forecast.toLocaleString()} MW`}</b></span><span>Actual <b>{row.actual === null ? "—" : `${row.actual.toLocaleString()} MW`}</b></span><span>Error <b>{row.error_mw === null ? "—" : `${row.error_mw.toLocaleString()} MW`}</b></span><span>Published <b>{publicationTime}</b></span><span>Lead time <b>{row.lead_time_hours === null ? "—" : `${row.lead_time_hours.toFixed(1)}h`}</b></span></div>;
}

export function ForecastChart({ rows }: { rows: DecisionRow[] }) {
  const data = rows.map((row) => ({
    ...row,
    time: formatHour(row.target_time),
    forecast: row.forecast_mw,
    actual: row.actual_mw,
  }));

  return (
    <div className="chart-wrap chart-tall">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#ebe5dd" vertical={false} />
          <XAxis dataKey="time" tick={{ fill: "#89818a", fontSize: 11 }} interval={rows.length > 24 ? 5 : 2} />
          <YAxis tick={{ fill: "#89818a", fontSize: 11 }} tickFormatter={(value) => `${Math.round(value / 1000)}k`} />
          <Tooltip
            content={<ForecastTooltip />}
          />
          <Legend />
          <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#8569b2" strokeWidth={3} dot={false} />
          <Line type="monotone" dataKey="actual" name="Actual" stroke="#568b72" strokeWidth={3} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
