"""Typed, validated readers for the PathSnap trip format.

Format contract:
- .track: longitude, latitude, timestamp_seconds
- .nodes: longitude, latitude; row index is node_id
- .arcs: from_node_id, to_node_id; row index is arc_id
- .route: ordered arc_id sequence

This module deliberately does not align GPS rows to route rows. They represent
different sampling/graph granularities and require a map-matching procedure.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


@dataclass(frozen=True)
class Trip:
    trip_id: str
    split: str
    track: FloatArray
    nodes: FloatArray
    arcs: IntArray
    route: IntArray

    @property
    def gps_lon(self) -> FloatArray:
        return self.track[:, 0]

    @property
    def gps_lat(self) -> FloatArray:
        return self.track[:, 1]

    @property
    def timestamps(self) -> FloatArray:
        return self.track[:, 2]


def _one_file(folder: Path, suffix: str) -> Path:
    matches = sorted(folder.glob(f"*.{suffix}"))
    if len(matches) != 1:
        raise ValueError(
            f"{folder}: expected exactly one .{suffix} file, found {len(matches)}"
        )
    return matches[0]


def _load_matrix(path: Path, columns: int) -> FloatArray:
    try:
        values = np.loadtxt(path, dtype=np.float64, ndmin=2)
    except ValueError as exc:
        raise ValueError(f"Could not parse numeric data in {path}: {exc}") from exc
    if values.ndim != 2 or values.shape[1] != columns:
        raise ValueError(
            f"{path}: expected {columns} columns, got shape {values.shape}"
        )
    if values.shape[0] == 0:
        raise ValueError(f"{path}: file contains no data rows")
    if not np.isfinite(values).all():
        raise ValueError(f"{path}: contains NaN or infinite values")
    return values


def _load_sequence(path: Path) -> IntArray:
    try:
        values = np.asarray(np.loadtxt(path, dtype=np.float64, ndmin=1)).reshape(-1)
    except ValueError as exc:
        raise ValueError(f"Could not parse route IDs in {path}: {exc}") from exc
    if values.size == 0:
        return np.empty(0, dtype=np.int64)
    if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
        raise ValueError(f"{path}: route IDs must be finite integers")
    return values.astype(np.int64)


def load_trip(folder: str | Path, split: str) -> Trip:
    """Load one trip folder and validate all cross-file index relationships."""
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"Trip directory does not exist: {folder}")

    track_path = _one_file(folder, "track")
    nodes_path = _one_file(folder, "nodes")
    arcs_path = _one_file(folder, "arcs")
    route_path = _one_file(folder, "route")

    track = _load_matrix(track_path, 3)
    nodes = _load_matrix(nodes_path, 2)
    arcs_float = _load_matrix(arcs_path, 2)

    if not np.equal(arcs_float, np.floor(arcs_float)).all():
        raise ValueError(f"{arcs_path}: arc endpoints must be integer node IDs")
    arcs = arcs_float.astype(np.int64)
    route = _load_sequence(route_path)

    if (arcs < 0).any() or (arcs >= len(nodes)).any():
        raise ValueError(
            f"{arcs_path}: at least one endpoint is outside [0, {len(nodes) - 1}]"
        )
    if (route < 0).any() or (route >= len(arcs)).any():
        raise ValueError(
            f"{route_path}: at least one arc ID is outside [0, {len(arcs) - 1}]"
        )

    # The source files specify timestamps in seconds. Preserve original row order;
    # report ordering anomalies instead of silently sorting observations.
    if np.any(np.diff(track[:, 2]) < 0):
        raise ValueError(f"{track_path}: timestamps are not non-decreasing")

    return Trip(
        trip_id=folder.name,
        split=split,
        track=track,
        nodes=nodes,
        arcs=arcs,
        route=route,
    )


def iter_trip_folders(dataset_root: str | Path, split: str) -> list[Path]:
    """Return sorted trip directories for a known partition."""
    split_dir = Path(dataset_root) / split
    if not split_dir.is_dir():
        raise FileNotFoundError(f"Partition directory does not exist: {split_dir}")
    return sorted(path for path in split_dir.iterdir() if path.is_dir())


def load_partition(dataset_root: str | Path, split: str) -> list[Trip]:
    """Load every trip in a partition, failing loudly on malformed data."""
    return [
        load_trip(folder, split=split)
        for folder in iter_trip_folders(dataset_root, split)
    ]
