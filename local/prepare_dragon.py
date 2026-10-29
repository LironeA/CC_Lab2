#!/usr/bin/env python3
"""Convert the Stanford Dragon PLY to a benchmark-sized STL mesh."""
from __future__ import annotations

import argparse
import gzip
from pathlib import Path

import trimesh


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--faces", type=int, default=120_000)
    args = parser.parse_args()
    if args.faces < 10_000:
        raise SystemExit("Use at least 10,000 faces for a meaningful benchmark")
    if args.source.suffix == ".gz":
        with gzip.open(args.source, "rb") as source:
            mesh = trimesh.load(source, file_type="ply", force="mesh")
    else:
        mesh = trimesh.load(args.source, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        raise SystemExit("Source did not contain one triangular mesh")
    print(f"Source faces: {len(mesh.faces)}")
    simplified = mesh.simplify_quadric_decimation(face_count=args.faces)
    # The scan contains a few sliver facets after decimation; their tiny area
    # would force an impractically small explicit-Euler time step.
    simplified.update_faces(simplified.nondegenerate_faces(height=1e-4))
    simplified.remove_unreferenced_vertices()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    simplified.export(args.output)
    print(f"Wrote {args.output} with {len(simplified.faces)} faces")


if __name__ == "__main__":
    main()
