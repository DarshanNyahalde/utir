export function StatusPill({ status }: { status: string }) {
  const normalized = status.toLowerCase().replaceAll(" ", "-");
  return <span className={`status-pill status-${normalized}`}>{status}</span>;
}
