import type { AccuracyResponse, DecisionResponse } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { signal });
  if (!response.ok) {
    let detail = `Request failed with ${response.status}`;
    try {
      const body: { detail?: unknown } = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Keep the HTTP status as the user-facing error when the body is not JSON.
    }
    throw new Error(detail);
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new Error("The API returned an invalid response.");
  }
}

export function getDecisionView(
  date: string,
  decisionCutoff: string,
  resolution: "hourly" | "half-hourly",
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({
    delivery_date: date,
    decision_cutoff: decisionCutoff,
    resolution,
  });
  return request<DecisionResponse>(`/api/decision-view?${params}`, signal);
}

export function getAccuracy(
  decisionCutoff: string,
  resolution: "hourly" | "half-hourly",
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({
    date_from: "2026-01-01",
    date_to: "2026-01-31",
    decision_cutoff: decisionCutoff,
    resolution,
  });
  return request<AccuracyResponse>(`/api/accuracy-analysis?${params}`, signal);
}
