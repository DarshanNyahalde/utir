import { useEffect, useMemo, useRef, useState } from "react";
import { AccuracyCharts } from "./components/AccuracyCharts";
import { ForecastChart } from "./components/ForecastChart";
import { MetricCard } from "./components/MetricCard";
import { PeriodTable } from "./components/PeriodTable";
import { StatusPill } from "./components/StatusPill";
import { getAccuracy, getDecisionView } from "./api";
import type { AccuracyResponse, DecisionResponse } from "./types";

type Resolution = "hourly" | "half-hourly";

function formatMw(value: number | null | undefined) {
  return value === null || value === undefined
    ? "—"
    : `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} MW`;
}

function formatPercent(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "Not available";
  return new Date(value).toLocaleString([], {
    timeZone: "Europe/London",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

function formatDay(value: string) {
  return new Date(`${value}T12:00:00Z`).toLocaleDateString([], {
    timeZone: "Europe/London",
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function cacheMessage(metadata: Record<string, unknown> | undefined) {
  const cacheStatus = metadata?.cache_status;
  if (!cacheStatus || typeof cacheStatus !== "object") return null;
  const statuses = Object.values(cacheStatus);
  return statuses.includes("stale-cache")
    ? "Elexon is temporarily unavailable; displaying previously retrieved valid data."
    : null;
}

function WindReadyMark({ className = "" }: { className?: string }) {
  return (
    <svg className={`windready-mark ${className}`} viewBox="0 0 100 100" role="img" aria-label="WindReady mark">
      <path className="windready-mark-ring" d="M18 35 A33 33 0 1 1 25 73" />
      <path className="windready-mark-w" d="M25 33 L35 68 L50 44 L65 68 L75 33" />
      <path className="windready-mark-tail" d="M62 74 H79" />
      <circle className="windready-mark-node" cx="79" cy="74" r="2.5" />
    </svg>
  );
}

function App() {
  const [introVisible, setIntroVisible] = useState(true);
  const [activeView, setActiveView] = useState<"decision" | "accuracy">("decision");
  const [deliveryDate, setDeliveryDate] = useState("2026-01-15");
  const [cutoff, setCutoff] = useState("23:59");
  const [resolution, setResolution] = useState<Resolution>("half-hourly");
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [accuracy, setAccuracy] = useState<AccuracyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastDecisionKey = useRef<string | null>(null);
  const lastAccuracyKey = useRef<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setIntroVisible(false), 1550);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (activeView !== "decision") return;
    const requestKey = `${deliveryDate}|${cutoff}|${resolution}`;
    if (lastDecisionKey.current === requestKey) {
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);
    lastDecisionKey.current = null;
    setDecision(null);
    getDecisionView(deliveryDate, cutoff, resolution, controller.signal)
      .then((result) => {
        setDecision(result);
        lastDecisionKey.current = requestKey;
      })
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "Unable to load data");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [activeView, deliveryDate, cutoff, resolution]);

  useEffect(() => {
    if (activeView !== "accuracy") return;
    const requestKey = `${cutoff}|${resolution}`;
    if (lastAccuracyKey.current === requestKey) {
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);
    lastAccuracyKey.current = null;
    setAccuracy(null);
    getAccuracy(cutoff, resolution, controller.signal)
      .then((result) => {
        setAccuracy(result);
        lastAccuracyKey.current = requestKey;
      })
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "Unable to load data");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [activeView, cutoff, resolution]);

  const latestPublish = useMemo(() => {
    const timestamps = decision?.rows
      .map((row) => row.forecast_publish_time)
      .filter((value): value is string => Boolean(value)) ?? [];
    return timestamps.reduce<string | undefined>(
      (latest, value) => (!latest || Date.parse(value) > Date.parse(latest) ? value : latest),
      undefined,
    );
  }, [decision]);

  const decisionCacheNotice = cacheMessage(decision?.metadata);
  const accuracyCacheNotice = cacheMessage(accuracy?.metadata);
  const periodsLabel = resolution === "hourly" ? "hourly" : "half-hourly";

  return (
    <div className={`app-shell ${introVisible ? "is-intro-visible" : ""}`}>
      <div className="intro-screen" aria-hidden={!introVisible}>
        <div className="intro-lockup">
          <WindReadyMark className="intro-mark" />
          <div className="intro-wordmark">WINDREADY</div>
          <div className="intro-rule" />
          <div className="intro-caption">DAY-AHEAD WIND INTELLIGENCE</div>
        </div>
      </div>
      <div className="app-layout">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-mark"><WindReadyMark /></div>
            <div>
              <div className="brand-name">WindReady</div>
              <div className="brand-subtitle">Wind market intelligence</div>
            </div>
          </div>
          <div className="sidebar-label">YOUR WORKSPACE</div>
          <nav className="side-nav" aria-label="Dashboard views">
            <button
              className={activeView === "decision" ? "side-link active" : "side-link"}
              aria-current={activeView === "decision" ? "page" : undefined}
              onClick={() => setActiveView("decision")}
            >
              <span className="side-link-icon">◒</span><span>Decision view</span><span className="side-link-arrow">↗</span>
            </button>
            <button
              className={activeView === "accuracy" ? "side-link active" : "side-link"}
              aria-current={activeView === "accuracy" ? "page" : undefined}
              onClick={() => setActiveView("accuracy")}
            >
              <span className="side-link-icon">⌁</span><span>Accuracy analysis</span><span className="side-link-arrow">↗</span>
            </button>
          </nav>
          <div className="sidebar-bottom">
            <div className="sidebar-label">DATA WORKSPACE</div>
            <div className="sidebar-source">
              <span className="sidebar-source-mark">↗</span>
              <span><strong>Elexon BMRS</strong><small>January 2026 pilot</small></span>
            </div>
            <p>Forecasts reconstructed using only information available before the UK-local decision cutoff.</p>
            <div className="sidebar-version"><span>WINDREADY</span><span>V 0.2</span></div>
          </div>
        </aside>

        <div className="workspace">
          <header className="topbar">
            <div className="breadcrumb">
              <span>Wind intelligence</span><i>/</i>
              <strong>{activeView === "decision" ? "Decision view" : "Accuracy analysis"}</strong>
            </div>
            <div className="topbar-right">
              <span className="historical-mark" />
              <span>Historical pilot</span>
              <span className="topbar-divider" />
              <span className="source-tag">GREAT BRITAIN</span>
            </div>
          </header>

          <main className="content">
            <section className="hero">
              <div className="hero-copy">
                <div className="hero-kicker">
                  <span className="pulse-mark" /> WIND INTELLIGENCE
                  <span className="hero-kicker-line" /> NATIONAL SYSTEM
                </div>
                <h1>See the wind signal<br />before the market moves.</h1>
                <p>Compare the forecast a buyer could actually see with realized generation. A more transparent view of day-ahead uncertainty, built on real system data.</p>
                <div className="hero-footnote">
                  <span className="hero-footnote-icon">↗</span>
                  <span>Forecast vintage selected at your UK-local decision cutoff</span>
                </div>
              </div>
              <div className="hero-note">
                <div className="hero-note-top"><div className="hero-note-label">DATA WINDOW</div><span className="hero-note-chip">PILOT</span></div>
                <strong>01 — 31 <em>JAN</em></strong>
                <span>2026 · National wind generation</span>
                <div className="hero-note-rule" />
                <span className="hero-note-foot">FUELHH actuals <b>+</b> WINDFOR forecasts</span>
              </div>
            </section>

            <section className="control-panel">
              <div className="control-panel-heading">
                <span className="eyebrow">DECISION CONTEXT</span>
                <strong>Set the moment the buyer makes the call</strong>
              </div>
              <div className="control-item">
                <label htmlFor="delivery-date">Delivery date</label>
                <input
                  id="delivery-date"
                  type="date"
                  min="2026-01-01"
                  max="2026-01-31"
                  value={deliveryDate}
                  onChange={(event) => setDeliveryDate(event.target.value)}
                />
              </div>
              <div className="control-item">
                <label htmlFor="cutoff">Decision cutoff <span>(UK local)</span></label>
                <input id="cutoff" type="time" value={cutoff} onChange={(event) => setCutoff(event.target.value)} />
              </div>
              <div className="control-item">
                <label htmlFor="resolution">Delivery resolution</label>
                <select
                  id="resolution"
                  value={resolution}
                  onChange={(event) => {
                    if (event.target.value === "hourly" || event.target.value === "half-hourly") {
                      setResolution(event.target.value);
                    }
                  }}
                >
                  <option value="half-hourly">Half-hourly · 30 min</option>
                  <option value="hourly">Hourly · averaged actuals</option>
                </select>
              </div>
              <div className="control-explainer">
                <span className="info-icon">i</span>
                <span>Delivery date applies to Decision view; Accuracy covers all of January. Cutoff is <b>{cutoff} UK time on the day before each delivery date</b>.</span>
              </div>
            </section>

            {loading && <div className="notice loading" role="status"><span className="loading-spinner" /> Loading verified Elexon data…</div>}
            {error && <div className="notice error" role="alert"><span className="notice-icon">!</span><span>{error}</span></div>}

            {activeView === "decision" && decision && (
              <>
                {decisionCacheNotice && <div className="notice loading">{decisionCacheNotice}</div>}
                <section className="section-intro">
                  <div><span className="eyebrow">01 / DECISION SNAPSHOT</span><h2>{formatDay(decision.delivery_date)}</h2></div>
                  <div className="section-intro-meta">
                    <span className="source-badge"><span className="source-badge-dot" /> {decision.data_source}</span>
                    <span>{decision.rows.length} {periodsLabel} delivery periods</span>
                  </div>
                </section>

                {decision.metrics.sample_count === 0 && (
                  <div className="empty-state" role="status">
                    <strong>No matched forecast and actual periods are available.</strong>
                    <span>Missing values are left blank; no sample or metric values are generated.</span>
                  </div>
                )}

                <section className="summary-row">
                  <MetricCard
                    label="Forecast MAE"
                    value={formatMw(decision.metrics.mae_mw)}
                    detail="Mean |forecast − actual| across valid matched periods"
                    tone="blue"
                  />
                  <MetricCard
                    label="Forecast bias"
                    value={formatMw(decision.metrics.bias_mw)}
                    detail="Mean forecast − actual; positive means overforecast"
                    tone={decision.metrics.bias_mw !== null && decision.metrics.bias_mw < 0 ? "orange" : "green"}
                  />
                  <MetricCard
                    label="Underforecast periods"
                    value={`${decision.metrics.underforecast_count} / ${decision.metrics.sample_count}`}
                    detail={`${formatPercent(decision.metrics.underforecast_rate)} of valid matched periods`}
                    tone="orange"
                  />
                  <MetricCard
                    label="P90 absolute error"
                    value={formatMw(decision.metrics.p90_absolute_error_mw)}
                    detail="Nearest-rank 90th percentile of absolute errors"
                    tone="red"
                  />
                </section>

                <section className="panel main-panel">
                  <div className="panel-heading">
                    <div>
                      <div className="panel-title-row"><span className="eyebrow">Observed vs selected forecast</span><span className="confidence-tag">PRE-CUTOFF VINTAGE</span></div>
                      <h2>Generation profile</h2>
                      <p>
                        Latest selected publication {formatDateTime(latestPublish)}
                        <span className="panel-separator"> · </span>
                        Decision cutoff {formatDateTime(decision.decision_cutoff)}
                      </p>
                    </div>
                    <div className="chart-legend"><span><i className="legend-line forecast-line" /> Forecast</span><span><i className="legend-line actual-line" /> Actual</span></div>
                  </div>
                  <ForecastChart rows={decision.rows} />
                </section>

                <section className="lower-grid">
                  <section className="panel table-panel">
                    <div className="panel-heading compact">
                      <div><span className="eyebrow">Period detail</span><h3>What the buyer could see</h3></div>
                      <span className="table-count">{decision.rows.length} {periodsLabel} periods</span>
                    </div>
                    <PeriodTable rows={decision.rows} />
                  </section>
                  <aside className="panel insight-panel">
                    <span className="eyebrow">Decision note</span>
                    <h3>Use the error as a buffer signal.</h3>
                    <p>Periods where actual wind exceeds the selected forecast are underforecast exposure. This prototype does not convert that exposure to procurement volume or cost because demand and price data are outside scope.</p>
                    <div className="insight-divider" />
                    <div className="mini-stat"><span>Selected resolution</span><strong>{decision.resolution}</strong></div>
                    <div className="mini-stat"><span>Actual dataset</span><strong>FUELHH · WIND</strong></div>
                    <div className="mini-stat"><span>Forecast dataset</span><strong>WINDFOR</strong></div>
                    <div className="mini-stat"><span>Cutoff timezone</span><strong>Europe/London</strong></div>
                  </aside>
                </section>
              </>
            )}

            {activeView === "accuracy" && accuracy && (
              <>
                {accuracyCacheNotice && <div className="notice loading">{accuracyCacheNotice}</div>}
                <section className="section-intro">
                  <div><span className="eyebrow">02 / ACCURACY INTELLIGENCE</span><h2>How reliable was the decision signal?</h2></div>
                  <div className="section-intro-meta">
                    <span>{accuracy.metrics.sample_count.toLocaleString()} valid matched periods</span>
                    <span className="source-badge"><span className="source-badge-dot" /> {accuracy.data_source}</span>
                  </div>
                </section>

                {accuracy.metrics.sample_count === 0 ? (
                  <div className="empty-state" role="status">
                    <strong>No valid forecast and actual pairs were returned for January 2026.</strong>
                    <span>Accuracy charts are omitted until real matched data is available.</span>
                  </div>
                ) : (
                  <>
                    <section className="summary-row accuracy-summary">
                      <MetricCard label="MAE" value={formatMw(accuracy.metrics.mae_mw)} detail="Mean absolute error (MW)" tone="blue" />
                      <MetricCard label="RMSE" value={formatMw(accuracy.metrics.rmse_mw)} detail="Square root of mean squared error (MW)" tone="red" />
                      <MetricCard label="Mean bias" value={formatMw(accuracy.metrics.bias_mw)} detail="Mean forecast − actual (MW)" tone="green" />
                      <MetricCard label="P90 absolute error" value={formatMw(accuracy.metrics.p90_absolute_error_mw)} detail="Nearest-rank 90th percentile (MW)" tone="orange" />
                      <MetricCard label="Valid matched periods" value={accuracy.metrics.sample_count.toLocaleString()} detail={`Of ${accuracy.rows.length.toLocaleString()} ${periodsLabel} periods`} tone="blue" />
                      <MetricCard label="Underforecast periods" value={formatPercent(accuracy.metrics.underforecast_rate)} detail={`${accuracy.metrics.underforecast_count.toLocaleString()} periods where forecast < actual`} tone="orange" />
                    </section>
                    <section className="analysis-callout">
                      <span className="analysis-callout-mark">⌁</span>
                      <div>
                        <strong>Read the shape, not just the score.</strong>
                        <span>All figures below use valid matched Elexon periods and the selected UK-local decision cutoff.</span>
                      </div>
                      <span className="analysis-callout-source">CUTOFF {cutoff} UK</span>
                    </section>
                    <AccuracyCharts data={accuracy} />
                    <section className="panel table-panel accuracy-table-panel">
                      <div className="panel-heading compact">
                        <div><span className="eyebrow">Delivery-period comparison</span><h3>January 2026 periods</h3></div>
                        <span className="table-count">{accuracy.rows.length.toLocaleString()} {periodsLabel} periods</span>
                      </div>
                      <PeriodTable rows={accuracy.rows} />
                    </section>
                  </>
                )}
              </>
            )}
          </main>

          <footer className="footer">
            <span>WindReady · Elexon FUELHH + WINDFOR</span>
            <span>Error = forecast − actual; all generation values are MW.</span>
          </footer>
        </div>
      </div>
    </div>
  );
}

export default App;
