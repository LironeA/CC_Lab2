#!/usr/bin/env python3
"""Export an NPZ simulation state to legacy VTK with per-triangle temperature."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path, help="final_state.npz from heat_mpi.py")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--field", choices=("temperature", "owners"), default="temperature",
                        help="NPZ cell field to export; owners is written as mpi_rank")
    args = parser.parse_args()

    data = np.load(args.state)
    triangles = np.asarray(data["triangles"], dtype=float)
    values = np.asarray(data[args.field], dtype=float)
    field_name = "mpi_rank" if args.field == "owners" else "temperature"
    if len(triangles) != len(values):
        raise SystemExit("The state has inconsistent triangle and field counts")

    # Keeping each STL triangle's three points avoids tolerance-dependent
    # vertex merging and preserves a one-to-one mapping to temperature cells.
    points = triangles.reshape(-1, 3)
    faces = np.arange(len(points), dtype=np.int64).reshape(-1, 3)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as file:
        file.write("# vtk DataFile Version 3.0\n")
        file.write("Lab2 heat transfer result\nASCII\nDATASET POLYDATA\n")
        file.write(f"POINTS {len(points)} float\n")
        for point in points:
            file.write(f"{point[0]:.9g} {point[1]:.9g} {point[2]:.9g}\n")
        file.write(f"POLYGONS {len(faces)} {len(faces) * 4}\n")
        for face in faces:
            file.write(f"3 {face[0]} {face[1]} {face[2]}\n")
        file.write(f"CELL_DATA {len(values)}\nSCALARS {field_name} float 1\nLOOKUP_TABLE default\n")
        for value in values:
            file.write(f"{value:.9g}\n")
    print(args.output)


if __name__ == "__main__":
    main()
