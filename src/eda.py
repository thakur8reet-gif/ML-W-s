"""Exploratory analysis and first-trip map for PathSnap.

Run from the repository root:
    python src/eda.py

Outputs are derived from the local dataset; this script does not train models or
create GPS-row labels from route positions.
"""
from __future__ import annotations

import json
from pathlib import Path

import folium
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pyproj import Geod
from tqdm import tqdm

from data_io import Trip, iter_trip_folders, load_trip

DATA_ROOT = Path("Student folder")
REPORTS = Path("reports")
FIGURES = REPORTS / "figures"
MAPS = REPORTS / "maps"
GEOD = Geod(ellps="WGS84")


def geodesic_step_distances(track: np.ndarray) -> np.ndarray:
    """Return WGS84 geodesic distances between consecutive GPS observations."""
    if len(track) < 2:
        return np.empty(0, dtype=float)
    _, _, distance = GEOD.inv(
        track[:-1, 0], track[:-1, 1], track[1:, 0], track[1:, 1]
    )
    return np.asarray(distance, dtype=float)


def summarize_trip(trip: Trip) -> dict:
    track = trip.track
    dt = np.diff(track[:, 2])
    distances = geodesic_step_distances(track)
    positive_dt = dt > 0
    speeds = np.divide(
        distances, dt, out=np.full_like(distances, np.nan), where=positive_dt
    )

    route_edges = trip.arcs[trip.route] if len(trip.route) else np.empty((0, 2), dtype=int)
    continuity = (
        float(np.mean(route_edges[:-1, 1] == route_edges[1:, 0]))
        if len(route_edges) > 1 else (1.0 if len(route_edges) == 1 else np.nan)
    )

    return {
        "split": trip.split,
        "trip_id": trip.trip_id,
        "gps_points": len(track),
        "nodes": len(trip.nodes),
        "arcs": len(trip.arcs),
        "route_steps": len(trip.route),
        "track_duration_s": float(track[-1, 2] - track[0, 2]) if len(track) else 0.0,
        "median_timestamp_step_s": float(np.median(dt)) if len(dt) else np.nan,
        "timestamp_gaps_gt_1_5s": int((dt > 1.5).sum()),
        "nonpositive_timestamp_steps": int((dt <= 0).sum()),
        "median_gps_step_m": float(np.median(distances)) if len(distances) else np.nan,
        "p95_gps_step_m": float(np.percentile(distances, 95)) if len(distances) else np.nan,
        "max_speed_mps": float(np.nanmax(speeds)) if np.isfinite(speeds).any() else np.nan,
        "route_continuity_fraction": continuity,
        "route_unique_arc_fraction": (
            float(len(np.unique(trip.route)) / len(trip.route)) if len(trip.route) else np.nan
        ),
        "lon_min": float(track[:, 0].min()),
        "lon_max": float(track[:, 0].max()),
        "lat_min": float(track[:, 1].min()),
        "lat_max": float(track[:, 1].max()),
    }


def save_histogram(df: pd.DataFrame, column: str, title: str, filename: str, bins=20):
    if column not in df or df[column].notna().sum() == 0:
        return
    fig, ax = plt.subplots(figsize=(9, 5))
    for split, part in df.groupby("split"):
        values = pd.to_numeric(part[column], errors="coerce").dropna()
        if len(values):
            ax.hist(values, bins=bins, alpha=0.65, label=split)
    ax.set_title(title)
    ax.set_xlabel(column.replace("_", " "))
    ax.set_ylabel("Trip count")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / filename, dpi=160)
    plt.close(fig)


def build_trip_map(trip: Trip, output: Path):
    """Map GPS, road graph and reference route for one real trip."""
    center = [float(np.mean(trip.track[:, 1])), float(np.mean(trip.track[:, 0]))]
    fmap = folium.Map(location=center, zoom_start=14, tiles="CartoDB positron")

    gps_points = [[float(lat), float(lon)] for lon, lat in trip.track[:, :2]]
    folium.PolyLine(
        gps_points, color="#2563eb", weight=4, opacity=0.9,
        tooltip="Observed GPS trace",
    ).add_to(fmap)
    folium.CircleMarker(
        gps_points[0], radius=5, color="#16a34a", fill=True,
        tooltip="GPS start",
    ).add_to(fmap)
    folium.CircleMarker(
        gps_points[-1], radius=5, color="#dc2626", fill=True,
        tooltip="GPS end",
    ).add_to(fmap)

    # Restrict the displayed road graph to a buffered GPS bounding box so the
    # map remains usable. All route arcs are included even if outside that box.
    lon_min, lon_max = trip.track[:, 0].min(), trip.track[:, 0].max()
    lat_min, lat_max = trip.track[:, 1].min(), trip.track[:, 1].max()
    lon_pad = max((lon_max - lon_min) * 0.15, 0.001)
    lat_pad = max((lat_max - lat_min) * 0.15, 0.001)
    in_view = (
        (trip.nodes[:, 0] >= lon_min - lon_pad)
        & (trip.nodes[:, 0] <= lon_max + lon_pad)
        & (trip.nodes[:, 1] >= lat_min - lat_pad)
        & (trip.nodes[:, 1] <= lat_max + lat_pad)
    )
    view_node_ids = set(np.flatnonzero(in_view).tolist())
    route_ids = set(trip.route.tolist())
    route_edges = trip.arcs[trip.route] if len(trip.route) else np.empty((0, 2), dtype=int)

    road_group = folium.FeatureGroup(name="Road network (local extent)", show=True)
    # Limit background road rendering to 15,000 edges for browser performance.
    edge_ids = [
        i for i, (u, v) in enumerate(trip.arcs)
        if int(u) in view_node_ids and int(v) in view_node_ids and i not in route_ids
    ][:15000]
    for arc_id in edge_ids:
        u, v = trip.arcs[arc_id]
        a, b = trip.nodes[u], trip.nodes[v]
        folium.PolyLine(
            [[float(a[1]), float(a[0])], [float(b[1]), float(b[0])]],
            color="#9ca3af", weight=1, opacity=0.35,
        ).add_to(road_group)
    road_group.add_to(fmap)

    route_group = folium.FeatureGroup(name="Ground-truth route", show=True)
    route_coords = []
    for arc_id in trip.route:
        u, v = trip.arcs[int(arc_id)]
        a, b = trip.nodes[u], trip.nodes[v]
        segment = [[float(a[1]), float(a[0])], [float(b[1]), float(b[0])]]
        route_coords.extend(segment if not route_coords else segment[1:])
    if route_coords:
        folium.PolyLine(
            route_coords, color="#ea580c", weight=5, opacity=0.9,
            tooltip="Reference route from .route arc IDs",
        ).add_to(route_group)
    route_group.add_to(fmap)

    folium.LayerControl(collapsed=False).add_to(fmap)
    fmap.fit_bounds([[float(lat_min), float(lon_min)], [float(lat_max), float(lon_max)]])
    fmap.save(str(output))


def main():
    REPORTS.mkdir(exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)

    summaries = []
    loaded: dict[str, list[Trip]] = {}
    for split in ("train", "student_test"):
        folders = iter_trip_folders(DATA_ROOT, split)
        loaded[split] = []
        print(f"Loading {len(folders)} trips from {split}...")
        for folder in tqdm(folders, desc=split):
            trip = load_trip(folder, split)
            loaded[split].append(trip)
            summaries.append(summarize_trip(trip))

    df = pd.DataFrame(summaries).sort_values(["split", "trip_id"])
    df.to_csv(REPORTS / "eda_trip_summary.csv", index=False)

    # Dataset-level summary: descriptive statistics only, not model metrics.
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    stats = df.groupby("split")[list(numeric_cols)].agg(["count", "mean", "median", "std", "min", "max"])
    stats.to_csv(REPORTS / "eda_numeric_summary.csv")

    summary = {
        "trip_counts": df.groupby("split")["trip_id"].count().to_dict(),
        "total_trips_loaded": int(len(df)),
        "trip_level_columns": list(df.columns),
        "split_numeric_summary": {
            split: {
                col: {
                    "count": int(df.loc[df.split == split, col].count()),
                    "mean": float(df.loc[df.split == split, col].mean()),
                    "median": float(df.loc[df.split == split, col].median()),
                    "std": float(df.loc[df.split == split, col].std()),
                }
                for col in numeric_cols
            }
            for split in df.split.unique()
        },
        "method_notes": [
            "Distances between consecutive GPS fixes use WGS84 geodesics.",
            "The route is visualized by resolving .route arc IDs through .arcs and .nodes.",
            "No GPS observation is assigned a route label by row-index alignment.",
            "The map's background road network is clipped to the GPS bounding box plus a small margin and capped at 15000 arcs.",
            "The route layer includes the complete reference arc sequence.",
        ],
    }
    (REPORTS / "eda_summary.json").write_text(json.dumps(summary, indent=2))

    plots = [
        ("gps_points", "GPS observations per trip", "gps_observations.png"),
        ("track_duration_s", "GPS trace duration per trip", "trip_duration.png"),
        ("nodes", "Road-network nodes per trip", "node_counts.png"),
        ("arcs", "Directed road arcs per trip", "arc_counts.png"),
        ("route_steps", "Reference route length per trip", "route_lengths.png"),
        ("median_gps_step_m", "Median GPS displacement per sample", "gps_step_distance.png"),
        ("timestamp_gaps_gt_1_5s", "GPS timestamp gaps over 1.5 seconds", "gps_timestamp_gaps.png"),
        ("route_continuity_fraction", "Consecutive reference-arc connectivity", "route_continuity.png"),
    ]
    for col, title, filename in plots:
        save_histogram(df, col, title, filename)

    # Use the first training trip in sorted order as a transparent example, not
    # as a claim that it is representative of the entire dataset.
    example = loaded["train"][0]
    map_path = MAPS / f"trip_{example.trip_id}_eda.html"
    build_trip_map(example, map_path)

    print("\nEDA complete.")
    print(f"Trip summary: {REPORTS / 'eda_trip_summary.csv'}")
    print(f"Numeric summary: {REPORTS / 'eda_numeric_summary.csv'}")
    print(f"JSON summary: {REPORTS / 'eda_summary.json'}")
    print(f"Figures: {FIGURES}")
    print(f"Example map: {map_path}")
    print("\nTrip counts:")
    print(df.groupby("split")["trip_id"].count().to_string())
    print("\nSelected medians by split:")
    selected = ["gps_points", "nodes", "arcs", "route_steps", "track_duration_s",
                "median_gps_step_m", "route_continuity_fraction"]
    print(df.groupby("split")[selected].median().round(3).to_string())


if __name__ == "__main__":
    main()
