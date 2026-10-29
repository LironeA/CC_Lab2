#!/usr/bin/env python3
"""Visualize MPI mesh partitioning, a local adjacency graph and rank load."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np


def face_adjacency(triangles: np.ndarray) -> list[tuple[int, int]]:
    edges: dict[tuple[tuple[float, float, float], tuple[float, float, float]], int] = {}
    pairs: list[tuple[int, int]] = []
    for face, triangle in enumerate(triangles):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((tuple(np.round(triangle[a], 10)), tuple(np.round(triangle[b], 10)))))
            other = edges.pop(key, None)
            if other is None:
                edges[key] = face
            else:
                pairs.append((other, face))
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    data = np.load(args.state)
    triangles = data["triangles"]
    owners = data["owners"]
    centers = triangles.mean(axis=1)
    ranks = int(owners.max()) + 1
    colors = plt.cm.tab10(owners % 10)

    # Mesh decomposition.
    figure = plt.figure(figsize=(8, 6)); axis = figure.add_subplot(projection="3d")
    axis.add_collection3d(Poly3DCollection(triangles, facecolors=colors, linewidths=0))
    axis.auto_scale_xyz(triangles[..., 0].flat, triangles[..., 1].flat, triangles[..., 2].flat)
    axis.set_title("MPI partition of triangular mesh")
    handles = [plt.Line2D([0], [0], color=plt.cm.tab10(rank), lw=5, label=f"rank {rank}") for rank in range(ranks)]
    axis.legend(handles=handles, loc="upper left")
    figure.tight_layout(); figure.savefig(args.output_dir / "mesh_partition.png", dpi=180); plt.close(figure)

    # A readable local adjacency graph near the centre of the surface.
    selected = np.argsort(np.linalg.norm(centers[:, :2] - centers[:, :2].mean(axis=0), axis=1))[:180]
    selected_set = set(map(int, selected))
    figure, axis = plt.subplots(figsize=(7, 6))
    for left, right in face_adjacency(triangles):
        if left in selected_set and right in selected_set:
            axis.plot([centers[left, 0], centers[right, 0]], [centers[left, 1], centers[right, 1]], color="0.65", lw=.45, zorder=1)
    axis.scatter(centers[selected, 0], centers[selected, 1], c=owners[selected], cmap="tab10", s=11, zorder=2)
    axis.set_aspect("equal"); axis.set_title("Local polygon adjacency graph")
    axis.set_xlabel("x"); axis.set_ylabel("y"); figure.tight_layout()
    figure.savefig(args.output_dir / "adjacency_graph.png", dpi=180); plt.close(figure)

    workers = []
    for path in args.worker_dir.glob("rank-*.csv"):
        with path.open(encoding="utf-8", newline="") as file:
            workers.extend(csv.DictReader(file))
    if not workers:
        raise SystemExit("No rank-*.csv files found")
    workers.sort(key=lambda row: int(row["rank"]))
    labels = [f"rank {row['rank']}" for row in workers]
    faces = [int(row["faces"]) for row in workers]
    ghosts = [int(row["ghost_faces"]) for row in workers]
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.bar(labels, faces, label="owned polygons")
    axis.bar(labels, ghosts, bottom=faces, label="ghost polygons")
    axis.set_title("MPI load and ghost-zone size")
    axis.set_ylabel("Polygon count"); axis.legend(); figure.tight_layout()
    figure.savefig(args.output_dir / "load_ghost_distribution.png", dpi=180); plt.close(figure)


if __name__ == "__main__":
    main()
