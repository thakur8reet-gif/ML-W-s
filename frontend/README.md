# PathSnap evaluator UI

React + TypeScript + Vite + Tailwind CSS + Leaflet frontend for the two-laptop
PathSnap evaluation setup.

## Run locally

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open the Vite URL printed in the terminal (normally http://localhost:5173).

Set `VITE_API_BASE_URL` in `.env` to the FastAPI server's reachable address. For
example, when the API runs on another laptop, use that laptop's LAN IP rather than
`localhost`.

Build for deployment:

```bash
npm run build
```

The output is written to `dist/`.

## API contract

The UI expects the following endpoints. The backend team should implement these
routes or agree on equivalent paths and update `src/lib/api.ts`.

### GET /health

```json
{
  "status": "ok",
  "model_name": "team-selected-model",
  "version": "optional-version"
}
```

### GET /api/evaluation/trips

Returns only the ten evaluator-approved trip identifiers. Do not return ground-truth
routes, labels, or any target-derived metadata.

```json
{
  "trips": [
    { "trip_id": "evaluation-trip-id", "label": "Evaluation trip 01" }
  ]
}
```

The list is populated by the backend; the frontend does not hardcode evaluation IDs.

### POST /api/evaluation/predict

Request:

```json
{ "trip_id": "evaluation-trip-id" }
```

Response:

```json
{
  "trip_id": "evaluation-trip-id",
  "gps_trace": [[12.9716, 77.5946], [12.9717, 77.5948]],
  "predicted_route": [[12.9716, 77.5946], [12.9718, 77.5950]],
  "road_network": [
    [[12.9715, 77.5945], [12.9718, 77.5950]]
  ],
  "inference_time_ms": 123.4,
  "decoder": "HMM + Viterbi"
}
```

All coordinates are arrays in **[latitude, longitude]** order. `gps_trace` is the
observed GPS sequence, `predicted_route` is the reconstructed path as ordered
coordinates, and `road_network` is an optional list of coordinate sequences for
the displayed road geometry. `inference_time_ms` and `decoder` are optional
backend-reported metadata.

These are API schema examples, not actual predictions or measured performance.

## Evaluation integrity

- Evaluation trip IDs come from the API; they are not hardcoded in the frontend.
- Predictions are requested from the backend at runtime.
- The evaluator UI does not display reference routes or ground-truth labels.
- Do not add sample predictions or fabricated metrics to the production interface.
