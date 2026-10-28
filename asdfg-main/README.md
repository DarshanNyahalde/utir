# WindReady

WindReady is a wind-generation market intelligence dashboard for UK electricity procurement teams. It reconstructs the forecast available before a configurable day-ahead decision cutoff, compares that forecast with actual wind generation, and reports forecast error using real Elexon BMRS data.

The interface retains the existing dark-purple hero, light dashboard, and sidebar. The dashboard and API are restricted to January 2026 for this challenge. No sample values or synthetic observations are used.

## 🚀 Live Demo

**AeroWise — Wind Energy Intelligence & Forecast Analytics**

🌐 **Live Website:** https://utir-three.vercel.app

⚙️ **Backend API:** https://utir.onrender.com

📚 **API Documentation:** https://utir.onrender.com/docs

### Features
- Day-ahead wind forecast analysis
- Actual vs. forecast comparison
- Forecast accuracy metrics
- Decision-cutoff-based forecast selection
- Historical error analysis

## Architecture and data flow

```text
React + TypeScript + Vite
        │  JSON requests
        ▼
FastAPI backend
        ├── Elexon BMRS client (FUELHH and WINDFOR)
        ├── UTC/Europe-London timestamp normalization
        ├── Forecast-vintage selection at the buyer cutoff
        ├── 30-minute / hourly alignment
        └── Matched-period metrics and analysis series
```

Only the backend communicates with Elexon. Its in-memory cache reduces repeated source requests and serves the most recently retrieved valid response if an upstream request fails. Cached responses are identified in the API metadata and dashboard. If neither a live nor cached response is available, the API returns an error and the dashboard explains that data could not be loaded.

## Source data and period handling

| Dataset | Purpose | Treatment |
| --- | --- | --- |
| [FUELHH stream](https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream) | Half-hourly actual generation | Request `fuelType=WIND`; match on `startTime`. |
| [WINDFOR stream](https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream) | Published wind generation forecasts | Match delivery periods on `startTime`; select forecast vintage using `publishTime`. |

The backend was checked against the live stream response structure. FUELHH rows contain `startTime`, `publishTime`, `fuelType`, and `generation`; WINDFOR rows contain `startTime`, `publishTime`, and `generation`.

The default resolution is half-hourly: the original FUELHH timestamps are preserved, and each hourly WINDFOR forecast applies to the two half-hourly delivery periods within its hour. An hourly option is available and computes actual average power as the arithmetic mean of both half-hourly readings. It never sums those readings. Incomplete hourly actuals are excluded. Duplicate records use the latest publication; conflicting duplicates at the same publication timestamp are rejected instead of guessed.

All source timestamps are normalized to UTC for joining. The cutoff is interpreted as UK local time (`Europe/London`) on the calendar day before delivery, then converted to UTC. The implementation handles GMT/BST transitions and rejects nonexistent local cutoff times. An ambiguous autumn clock-change time uses the first occurrence of that local time.

## Forecast selection and metrics

For each delivery period:

1. Construct the selected delivery date's periods at the requested resolution.
2. Match forecasts by `startTime` (half-hour periods use the containing hourly forecast).
3. Keep only forecast records whose `publishTime` is at or before the UK-local decision cutoff.
4. Choose the most recently published eligible forecast. A later forecast is never substituted.
5. Match actual wind by delivery `startTime`, then calculate error only when both values are present and finite.

The cutoff time is configurable. The default is 23:59 UK time on the day before delivery; it is a dashboard default, not a claim about a market gate-closure rule.

Metrics use valid matched periods only:

- **Error:** forecast − actual (MW); positive is overforecast, negative is underforecast.
- **Absolute error:** `|forecast − actual|` (MW).
- **MAE:** mean absolute error (MW).
- **Bias / mean error:** mean signed error (MW).
- **RMSE:** square root of mean squared error (MW).
- **P90 absolute error:** nearest-rank 90th percentile of absolute errors (MW).
- **Underforecast periods:** count where forecast < actual; percentage is relative to valid pairs.
- **Overforecast periods:** count where forecast > actual.

Missing forecasts and actuals remain missing and are excluded from metrics. Equal forecast and actual values are classified as “On target.” Empty results are shown as empty states rather than zero-valued measurements.

## Repository structure

```text
backend/app/main.py                      FastAPI routes and request validation
backend/app/schemas.py                   Typed response models
backend/app/services/elexon_client.py    BMRS requests, timeout, and cache
backend/app/services/normalization.py    Record deduplication and timestamp normalization
backend/app/services/forecast_selection.py Cutoff-safe forecast selection
backend/app/services/data_service.py     Delivery-period construction and data alignment
backend/app/services/metrics.py           Error fields and accuracy summaries
backend/tests/                            Selection, time, data, metric, and API tests
frontend/src/App.tsx                      Dashboard state, controls, and views
frontend/src/api.ts                       Frontend API client
frontend/src/components/                 Reusable metric cards, charts, status, and period table
frontend/src/styles.css                  Existing responsive visual design
Dockerfile                                Multi-stage frontend build and FastAPI runtime
docker-compose.yml                        Local frontend/API development services
heroku.yml                                Heroku Container Stack build and web process
.env.example                              Local environment variable template
```

## Requirements

- Python 3.12 or newer
- Node.js 22 and npm
- Docker Desktop / Docker Compose (optional)
- Network access to the public Elexon BMRS API for uncached data

No Elexon API key is required or exposed to the browser.

## Environment variables

Copy `.env.example` to `.env` for Docker Compose, or configure these variables in the respective process environment:

| Variable | Default | Description |
| --- | --- | --- |
| `ELEXON_BASE_URL` | `https://data.elexon.co.uk/bmrs/api/v1` | BMRS API base URL used by the backend. |
| `ELEXON_REQUEST_TIMEOUT_SECONDS` | `20` | HTTP timeout per upstream request. |
| `ELEXON_CACHE_TTL_SECONDS` | `300` | In-memory response cache lifetime; stale valid data can be used on source failure. |
| `WINDREADY_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated browser origins permitted to call the API. |
| `VITE_API_BASE_URL` | empty | Optional backend origin for a separately hosted frontend. Local Vite and combined production use relative `/api` requests. |
| `API_PROXY_TARGET` | `http://api:8000` in Compose; `http://127.0.0.1:8000` otherwise | Vite development/preview proxy target. |
| `PORT` | `8000` | Port used by the Docker production process; hosting services can set this. |

## Run locally

From the repository root, create a Python environment, install backend dependencies, and start FastAPI:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` to FastAPI on port 8000, which is also available directly at <http://localhost:8000>; interactive API documentation is at <http://localhost:8000/docs>.

## Docker

Copy the example environment file, then start the application from the repository root:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open <http://localhost:5173>. Stop the services with `Ctrl+C`; remove the running Compose services with `docker compose down`.

The production Dockerfile builds the React application and serves its static assets from FastAPI in the same container. The application honors the hosting provider's `PORT`. A `heroku.yml` is included for Heroku's Container Stack; the same Dockerfile can be used by other Docker web hosts. The production image build and container startup still need to be run in the target deployment environment before deployment can be considered verified.

## API endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Backend health and January 2026 scope. |
| `GET /api/metadata` | Datasets, resolution choices, timezone, and aggregation method. |
| `GET /api/dates` | Valid January delivery dates. |
| `GET /api/decision-view?delivery_date=2026-01-15&decision_cutoff=23:59&resolution=half-hourly` | Selected forecasts, actuals, metrics, and period rows for one delivery date. |
| `GET /api/period-details?delivery_date=2026-01-15&decision_cutoff=23:59&resolution=half-hourly&target_time=2026-01-15T00:00:00Z` | All period details for one date, or one period when `target_time` is supplied. |
| `GET /api/accuracy-analysis?date_from=2026-01-01&date_to=2026-01-31&decision_cutoff=23:59&resolution=half-hourly` | January summary, daily and intraday errors, per-period errors, and comparison rows. |
| `GET /api/datasets/fuelhh?from=2026-01-15&to=2026-01-15&limit=5` | Small, real FUELHH source preview. |
| `GET /api/datasets/windfor?from=2026-01-15&to=2026-01-15&limit=5` | Small, real WINDFOR source preview. |

Supported `resolution` values are `half-hourly` and `hourly`. Dates outside January 2026, malformed cutoffs, reversed ranges, and unsupported resolutions are rejected with an explicit client error. `/api/accuracy` and the `cutoff`, `from`, and `to` parameter aliases remain available for compatibility.

## Testing and verification

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q backend\tests
.\.venv\Scripts\python.exe -m compileall -q backend
npm run build --prefix frontend
```

The backend tests cover cutoff-safe forecast selection, timestamp matching, duplicate and missing data, hourly aggregation, UK daylight-saving conversion, error metrics and direction counts, API validation, and source-failure behavior.

To check an active local service:

```powershell
curl.exe --fail http://localhost:8000/api/health
curl.exe --fail "http://localhost:8000/api/decision-view?delivery_date=2026-01-15&decision_cutoff=23%3A59&resolution=half-hourly"
curl.exe --fail "http://localhost:8000/api/accuracy-analysis?date_from=2026-01-01&date_to=2026-01-31&decision_cutoff=23%3A59&resolution=half-hourly"
```

## Deployment status

No deployment URL is verified for this working copy:

- Frontend / combined Docker service: **not deployed from this working copy**
- API: **not deployed from this working copy**

For a combined service, deploy the Dockerfile to a Docker-compatible host such as Render or use Heroku's Container Stack with `heroku.yml`; set the service `PORT` and production `WINDREADY_ALLOWED_ORIGINS` as appropriate. For a separately hosted Vercel frontend, set `VITE_API_BASE_URL` to the backend URL and configure the backend's `WINDREADY_ALLOWED_ORIGINS` to include the Vercel origin. Verify `/api/health`, a decision response, and an accuracy response on the deployed service before publishing deployment URLs.

## AI assistance disclosure

AI assistance was used to inspect and improve the existing implementation, including forecast selection, time and resolution handling, metrics, API responses, dashboard wiring, tests, and this documentation. The resulting changes and test outputs should be reviewed by the project owner before submission or deployment.
