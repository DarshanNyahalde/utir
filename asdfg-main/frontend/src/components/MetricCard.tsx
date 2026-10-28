type MetricCardProps = {
  label: string;
  value: string;
  detail?: string;
  tone?: "blue" | "green" | "orange" | "red";
};

export function MetricCard({ label, value, detail, tone = "blue" }: MetricCardProps) {
  return (
    <article className={`metric-card metric-${tone}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {detail && <div className="metric-detail">{detail}</div>}
    </article>
  );
}
