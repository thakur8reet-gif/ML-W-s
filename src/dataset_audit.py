from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from tqdm import tqdm

ROOT = Path("Student folder")
OUT = Path("reports")
FIG = OUT / "figures"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

EARTH_RADIUS_M = 6_371_000


def read_numeric(path: Path, expected_cols: int) -> np.ndarray:
    """Read a whitespace-delimited numeric file and enforce its column count."""
    arr = np.loadtxt(path, dtype=float, ndmin=2)
    if arr.ndim != 2 or arr.shape[1] != expected_cols:
        raise ValueError(f"Expected {expected_cols} columns; found shape {arr.shape}")
    return arr


def haversine_m(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = np.radians([lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


def audit_trip(folder: Path, split: str) -> dict:
    trip_id = folder.name
    prefix = folder / trip_id
    paths = {ext: prefix.with_suffix(f".{ext}") for ext in ("track", "nodes", "arcs", "route")}
    missing = [ext for ext, path in paths.items() if not path.is_file()]
    row = {"split": split, "trip_id": trip_id, "missing_files": ",".join(missing)}
    if missing:
        return row

    try:
        track = read_numeric(paths["track"], 3)
        nodes = read_numeric(paths["nodes"], 2)
        arcs_raw = read_numeric(paths["arcs"], 2)
        route_raw = np.loadtxt(paths["route"], dtype=float, ndmin=1).reshape(-1)

        row.update({
            "gps_points": len(track),
            "nodes": len(nodes),
            "arcs": len(arcs_raw),
            "route_steps": len(route_raw),
            "track_nan_values": int(np.isnan(track).sum()),
            "nodes_nan_values": int(np.isnan(nodes).sum()),
            "arcs_nan_values": int(np.isnan(arcs_raw).sum()),
            "route_nan_values": int(np.isnan(route_raw).sum()),
        })

        valid_track = np.isfinite(track).all(axis=1)
        valid_nodes = np.isfinite(nodes).all(axis=1)
        row["invalid_gps_rows"] = int((~valid_track).sum())
        row["invalid_node_rows"] = int((~valid_nodes).sum())

        if len(track) > 0 and valid_track.any():
            t = track[valid_track]
            row.update({
                "lon_min": float(t[:, 0].min()), "lon_max": float(t[:, 0].max()),
                "lat_min": float(t[:, 1].min()), "lat_max": float(t[:, 1].max()),
                "timestamp_start": float(t[:, 2].min()),
                "timestamp_end": float(t[:, 2].max()),
                "timestamp_monotonic": bool(np.all(np.diff(t[:, 2]) >= 0)),
            })
            dt = np.diff(t[:, 2])
            row["timestamp_nonpositive_steps"] = int((dt <= 0).sum())
            row["timestamp_gaps_gt_1_5s"] = int((dt > 1.5).sum())
            row["median_timestamp_step_s"] = float(np.median(dt)) if len(dt) else np.nan
            if len(t) > 1:
                distances = haversine_m(t[:-1, 0], t[:-1, 1], t[1:, 0], t[1:, 1])
                speeds = distances / np.where(dt > 0, dt, np.nan)
                row["median_gps_step_m"] = float(np.nanmedian(distances))
                row["max_gps_speed_mps"] = float(np.nanmax(speeds)) if np.isfinite(speeds).any() else np.nan

        if len(nodes) > 0 and valid_nodes.any():
            n = nodes[valid_nodes]
            row.update({
                "node_lon_min": float(n[:, 0].min()), "node_lon_max": float(n[:, 0].max()),
                "node_lat_min": float(n[:, 1].min()), "node_lat_max": float(n[:, 1].max()),
            })

        # Arc row index is the arc_id; columns are source and destination node IDs.
        arcs = arcs_raw
        integer_arcs = np.isfinite(arcs).all() and np.all(arcs == np.floor(arcs))
        row["arc_ids_integer"] = bool(integer_arcs)
        if integer_arcs:
            edges = arcs.astype(np.int64)
            in_bounds = (edges >= 0).all() and (edges < len(nodes)).all()
            row["arc_endpoints_in_node_bounds"] = bool(in_bounds)
            row["self_loop_arcs"] = int((edges[:, 0] == edges[:, 1]).sum())
            row["duplicate_directed_arcs"] = int(len(edges) - len(np.unique(edges, axis=0)))
            graph = nx.DiGraph()
            graph.add_nodes_from(range(len(nodes)))
            graph.add_edges_from(map(tuple, edges.tolist()))
            row["weakly_connected_components"] = nx.number_weakly_connected_components(graph) if len(graph) else 0
            row["isolated_nodes"] = sum(1 for node in graph if graph.degree(node) == 0)
        else:
            edges = np.empty((0, 2), dtype=np.int64)
            row["arc_endpoints_in_node_bounds"] = False

        # Ground-truth route entries index rows of .arcs; test ID validity and route continuity.
        route_integer = np.isfinite(route_raw).all() and np.all(route_raw == np.floor(route_raw))
        row["route_ids_integer"] = bool(route_integer)
        if route_integer and len(route_raw):
            route_ids = route_raw.astype(np.int64)
            ids_valid = (route_ids >= 0) & (route_ids < len(edges))
            row["route_arc_ids_in_bounds"] = bool(ids_valid.all())
            if ids_valid.all() and len(route_ids) > 1:
                route_edges = edges[route_ids]
                row["route_continuity_fraction"] = float(
                    np.mean(route_edges[:-1, 1] == route_edges[1:, 0])
                )
            else:
                row["route_continuity_fraction"] = 1.0 if len(route_ids) <= 1 and ids_valid.all() else 0.0
        else:
            row["route_arc_ids_in_bounds"] = False
            row["route_continuity_fraction"] = np.nan

        row["status"] = "ok"
    except Exception as exc:
        row["status"] = "error"
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def main():
    records = []
    for split in ("train", "student_test"):
        split_dir = ROOT / split
        if not split_dir.is_dir():
            raise FileNotFoundError(f"Missing dataset partition: {split_dir}")
        trips = sorted(p for p in split_dir.iterdir() if p.is_dir())
        print(f"{split}: found {len(trips)} trip folders")
        for folder in tqdm(trips, desc=f"Auditing {split}"):
            records.append(audit_trip(folder, split))

    df = pd.DataFrame(records).sort_values(["split", "trip_id"])
    csv_path = OUT / "trip_audit.csv"
    df.to_csv(csv_path, index=False)

    numeric = df.select_dtypes(include=[np.number])
    summary = {
        "dataset_root": str(ROOT),
        "trip_count_by_split": df.groupby("split")["trip_id"].count().to_dict(),
        "status_counts": df["status"].value_counts(dropna=False).to_dict() if "status" in df else {},
        "numeric_summary": numeric.describe().replace({np.nan: None}).to_dict(),
        "notes": [
            ".track columns interpreted as longitude, latitude, timestamp seconds.",
            ".nodes columns interpreted as longitude, latitude; row index is node ID.",
            ".arcs columns interpreted as from_node_id, to_node_id; row index is arc_id.",
            ".route values interpreted as ordered arc IDs.",
            "GPS observations are not assumed to align row-for-row with route entries.",
            "Geographic distances use the haversine formula; coordinates remain in lon/lat.",
        ],
    }
    with (OUT / "dataset_audit_summary.json").open("w") as f:
        json.dump(summary, f, indent=2, default=lambda x: None if pd.isna(x) else x)

    # Compact overview plots, separated by partition.
    for column, title, filename in [
        ("gps_points", "GPS observations per trip", "gps_points_per_trip.png"),
        ("nodes", "Road-network nodes per trip", "nodes_per_trip.png"),
        ("arcs", "Directed arcs per trip", "arcs_per_trip.png"),
        ("route_steps", "Ground-truth route steps per trip", "route_steps_per_trip.png"),
        ("route_continuity_fraction", "Ground-truth route continuity", "route_continuity.png"),
        ("timestamp_gaps_gt_1_5s", "GPS timestamp gaps greater than 1.5 seconds", "timestamp_gaps.png"),
    ]:
        if column not in df or df[column].notna().sum() == 0:
            continue
        fig, ax = plt.subplots(figsize=(9, 5))
        for split, part in df.groupby("split"):
            vals = pd.to_numeric(part[column], errors="coerce").dropna()
            if len(vals):
                ax.hist(vals, bins=20, alpha=0.6, label=split)
        ax.set_title(title)
        ax.set_xlabel(column.replace("_", " "))
        ax.set_ylabel("Number of trips")
        ax.legend()
        fig.tight_layout()
        fig.savefig(FIG / filename, dpi=160)
        plt.close(fig)

    print(f"\nSaved: {csv_path}")
    print(f"Saved: {OUT / 'dataset_audit_summary.json'}")
    print(f"Plots: {FIG}")
    print("\nTrips by partition:")
    print(df.groupby("split")["trip_id"].count().to_string())
    print("\nAudit status:")
    print(df.get("status", pd.Series(dtype=str)).value_counts(dropna=False).to_string())
    print("\nKey columns:")
    cols = [c for c in ["split", "trip_id", "gps_points", "nodes", "arcs", "route_steps",
                         "route_continuity_fraction", "status"] if c in df]
    print(df[cols].head(12).to_string(index=False))


if __name__ == "__main__":
    main()
