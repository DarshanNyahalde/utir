import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AccuracyResponse } from "../types";

function mw(value: unknown) {
  return value === null || value === undefined
    ? "—"
    : `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })} MW`;
}

function DetailTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ payload: Record<string, unknown> }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>
      <span>Mean error <b>{mw(row.bias_mw)}</b></span>
      <span>MAE <b>{mw(row.mae_mw)}</b></span>
      <span>Periods <b>{row.sample_count == null ? "—" : String(row.sample_count)}</b></span>
    </div>
  );
}

function PeriodTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: { target_time: string; error_mw: number | null } }>;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const deliveryTime = new Date(row.target_time).toLocaleString([], {
    timeZone: "Europe/London",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
  return (
    <div className="chart-tooltip">
      <strong>{deliveryTime}</strong>
      <span>Forecast − actual <b>{mw(row.error_mw)}</b></span>
    </div>
  );
}

export function AccuracyCharts({ data }: { data: AccuracyResponse }) {
  const daily = data.daily.map((row) => ({
    date: String(row.date ?? "").slice(5),
    bias_mw: typeof row.bias_mw === "number" ? row.bias_mw : null,
    mae_mw: typeof row.mae_mw === "number" ? row.mae_mw : null,
    sample_count: typeof row.sample_count === "number" ? row.sample_count : null,
  }));
  const hourly = data.hourly.map((row) => ({
    ...row,
    hour: `${String(row.hour).padStart(2, "0")}:00`,
  }));
  const distribution = data.rows
    .filter((row) => row.error_mw !== null)
    .map((row, index) => ({
      period: index + 1,
      target_time: row.target_time,
      error_mw: row.error_mw,
    }));

  return (
    <div className="chart-grid">
      <section className="panel chart-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Daily error · January 2026</span>
            <h3>Mean signed error by day</h3>
            <p className="chart-description">Forecast − actual; positive is overforecast, negative is underforecast.</p>
          </div>
          <span className="chart-key">MW · UK DELIVERY DATE</span>
        </div>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={daily}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ebe5dd" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#89818a" }} />
              <YAxis tick={{ fontSize: 10, fill: "#89818a" }} tickFormatter={(value) => `${Math.round(value / 1000)}k`} />
              <ReferenceLine y={0} stroke="#bcb3ba" />
              <Tooltip content={<DetailTooltip />} />
              <Bar dataKey="bias_mw" name="Mean signed error" radius={[4, 4, 0, 0]}>
                {daily.map((entry) => (
                  <Cell key={String(entry.date)} fill={Number(entry.bias_mw) < 0 ? "#c77d57" : "#568b72"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="panel chart-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Intraday error profile</span>
            <h3>Mean error by UK delivery hour</h3>
            <p className="chart-description">Average signed error across valid matched delivery periods.</p>
          </div>
          <span className="chart-key">FORECAST − ACTUAL</span>
        </div>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={hourly}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ebe5dd" vertical={false} />
              <XAxis dataKey="hour" tick={{ fontSize: 10, fill: "#89818a" }} interval={2} />
              <YAxis tick={{ fontSize: 10, fill: "#89818a" }} tickFormatter={(value) => `${Math.round(value / 1000)}k`} />
              <ReferenceLine y={0} stroke="#bcb3ba" />
              <Tooltip content={<DetailTooltip />} />
              <Line type="monotone" dataKey="bias_mw" name="Mean signed error" stroke="#c77d57" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="panel chart-panel chart-panel-wide">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Delivery-period errors</span>
            <h3>Forecast error across January</h3>
            <p className="chart-description">Each bar is one matched delivery period; orange is underforecast and green is overforecast.</p>
          </div>
          <span className="chart-key">FORECAST − ACTUAL · MW</span>
        </div>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ebe5dd" vertical={false} />
              <XAxis
                dataKey="period"
                tick={{ fontSize: 9, fill: "#89818a" }}
                tickFormatter={(value) => {
                  const row = distribution[Number(value) - 1];
                  if (!row) return "";
                  return new Date(row.target_time).toLocaleDateString([], {
                    timeZone: "Europe/London",
                    day: "2-digit",
                  });
                }}
                interval={data.resolution === "half-hourly" ? 47 : 23}
              />
              <YAxis tick={{ fontSize: 10, fill: "#89818a" }} tickFormatter={(value) => `${Math.round(value / 1000)}k`} />
              <ReferenceLine y={0} stroke="#bcb3ba" />
              <Tooltip content={<PeriodTooltip />} />
              <Bar dataKey="error_mw" name="Signed error" radius={[2, 2, 0, 0]}>
                {distribution.map((entry) => (
                  <Cell key={entry.target_time} fill={Number(entry.error_mw) < 0 ? "#c77d57" : "#568b72"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
