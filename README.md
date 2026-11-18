# PathSnap — GPS-to-Road-Network Map Matching

This repository contains the implementation and experiment record for the PathSnap
machine-learning hackathon. The objective is to infer a vehicle's traversed directed
road arcs from a time-ordered GPS trace and the supplied road graph.

## Dataset contract

The current repository dataset contains:

| Partition | Trips | Purpose |
|---|---:|---|
| `Student folder/train` | 80 | Model development and trip-grouped validation |
| `Student folder/student_test` | 10 | Development-time holdout comparison |
| Evaluator test | Not present in this repository snapshot | Final evaluation only; do not use for model selection |

Each trip directory is expected to contain one file of each type:

- `.track`: longitude, latitude, timestamp in seconds (three whitespace-separated columns).
- `.nodes`: longitude, latitude (two columns); row index is the node ID.
- `.arcs`: from-node ID, to-node ID (two integer columns); row index is the arc ID.
- `.route`: ordered sequence of ground-truth arc IDs.

**Important:** GPS observations and route entries are not row-aligned. A route contains
road-arc identifiers, not one label per GPS observation. Any observation-level
supervision must be generated through an explicit, validated map-matching/alignment
procedure. Geographic calculations must use metric coordinates or geodesic distance,
not Euclidean distance directly on longitude/latitude degrees.

## Environment

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Current implementation

### Dataset audit

```bash
python src/dataset_audit.py
```

Writes:
- `reports/trip_audit.csv`
- `reports/dataset_audit_summary.json`
- EDA figures under `reports/figures/`

The audit reports file completeness, dimensions, timestamp characteristics, coordinate
bounds, graph structure, route arc-ID validity, and consecutive-arc continuity. These
are diagnostics; no model performance is inferred from them.

### Validated data reader

`src/data_io.py` provides:
- `load_trip(folder, split)` for one trip.
- `load_partition(dataset_root, split)` for a complete partition.
- Validation of file cardinality, numeric formats, graph endpoint bounds, route arc-ID
  bounds, and timestamp ordering.

It deliberately preserves GPS row order and does not manufacture labels by matching
GPS row indices to route indices.

## Experiment principles

1. Keep all observations from a trip within one partition.
2. Use trip-grouped cross-validation on the 80 training trips.
3. Use the 10 student-test trips only for development-time comparison, not fitting.
4. Do not use evaluator-test information for feature selection, tuning, or model choice.
5. Record random seeds, feature definitions, hyperparameters, runtime, and metrics.
6. Report candidate-generation misses separately: a classifier cannot recover the true
   arc if candidate generation excludes it.
7. Compare per-observation classification with sequence-aware decoding; report route
   continuity and sequence metrics in addition to ordinary classification metrics.
8. Never report results until the corresponding experiment has actually been run.

## Planned milestones

- [x] Dataset audit implementation
- [x] Validated trip data reader
- [ ] Execute audit and inspect data-quality findings
- [x] Implement trip-level exploratory analysis and reference-route map generation
- [ ] Execute EDA locally and inspect generated summaries/maps
- [ ] Metric-coordinate road geometry and candidate generation
- [ ] Validated GPS-to-route supervision/alignment
- [ ] Five-model comparison with trip-grouped validation
- [ ] HMM/Viterbi sequence decoding
- [ ] Bayesian hyperparameter optimisation
- [ ] Final Folium visualisations and technical report

## Reproducibility

Generated reports and figures are derived artifacts. Keep source code, configuration,
and experiment metadata in version control. Do not commit fabricated metrics or
hand-edited experimental outputs.


## Evaluator UI

The React + TypeScript + Tailwind + Leaflet evaluator interface is in `frontend/`.

See [frontend/README.md](frontend/README.md) for setup instructions and the FastAPI
contract. Quick start:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The UI obtains evaluator trip IDs and route predictions from the FastAPI backend at
runtime. It does not hardcode evaluation IDs, predictions, or ground-truth labels.
