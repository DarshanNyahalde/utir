import type { DecisionRow } from "../types";
import { StatusPill } from "./StatusPill";

function formatMw(value: number | null) {
  return value === null
    ? "—"
    : `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} MW`;
}

function formatLocalTime(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString([], {
    timeZone: "Europe/London",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export function PeriodTable({ rows }: { rows: DecisionRow[] }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Delivery (UK)</th>
            <th>Forecast</th>
            <th>Actual</th>
            <th title="Forecast minus actual; positive is overforecast.">Signed error</th>
            <th>Absolute error</th>
            <th>Published (UK)</th>
            <th>Lead time</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.target_time}>
              <td>{formatLocalTime(row.target_time)}</td>
              <td>{formatMw(row.forecast_mw)}</td>
              <td>{formatMw(row.actual_mw)}</td>
              <td className={row.error_mw !== null && row.error_mw < 0 ? "negative" : "positive"}>
                {formatMw(row.error_mw)}
              </td>
              <td>{formatMw(row.absolute_error_mw)}</td>
              <td>{formatLocalTime(row.forecast_publish_time)}</td>
              <td>{row.lead_time_hours === null ? "—" : `${row.lead_time_hours.toFixed(1)}h`}</td>
              <td><StatusPill status={row.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
