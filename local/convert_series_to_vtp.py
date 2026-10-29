#!/usr/bin/env python3
"""Convert legacy VTK temperature frames to XML VTP frames for PVD/ParaView."""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np


def write_vtp(path: Path, triangles: np.ndarray, temperature: np.ndarray) -> None:
    points = triangles.reshape(-1, 3)
    polygons = len(triangles)
    connectivity = np.arange(len(points), dtype=np.int64)
    offsets = np.arange(1, polygons + 1, dtype=np.int64) * 3
    with path.open("w", encoding="utf-8", newline="\n") as file:
        file.write('<?xml version="1.0"?>\n<VTKFile type="PolyData" version="0.1" byte_order="LittleEndian">\n')
        file.write(f'<PolyData><Piece NumberOfPoints="{len(points)}" NumberOfPolys="{polygons}">\n')
        file.write('<Points><DataArray type="Float64" NumberOfComponents="3" format="ascii">\n')
        np.savetxt(file, points, fmt="%.9g")
        file.write('</DataArray></Points>\n<Polys>\n<DataArray type="Int64" Name="connectivity" format="ascii">\n')
        np.savetxt(file, connectivity[None], fmt="%d")
        file.write('</DataArray>\n<DataArray type="Int64" Name="offsets" format="ascii">\n')
        np.savetxt(file, offsets[None], fmt="%d")
        file.write('</DataArray>\n</Polys>\n<CellData Scalars="temperature">\n<DataArray type="Float64" Name="temperature" format="ascii">\n')
        np.savetxt(file, temperature, fmt="%.9g")
        file.write('</DataArray>\n</CellData>\n</Piece></PolyData></VTKFile>\n')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dt", type=float, required=True)
    parser.add_argument("--every", type=int, required=True)
    args = parser.parse_args()
    triangles = np.load(args.state)["triangles"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    steps = []
    for legacy in sorted(args.frames_dir.glob("temperature_*.vtk")):
        step = int(legacy.stem.rsplit("_", 1)[1])
        text = legacy.read_text(encoding="utf-8")
        marker = "LOOKUP_TABLE default\n"
        temperature = np.fromstring(text[text.index(marker) + len(marker):], sep=" ")
        if len(temperature) != len(triangles):
            raise SystemExit(f"Invalid temperature count in {legacy}")
        write_vtp(args.output_dir / f"temperature_{step:06d}.vtp", triangles, temperature)
        steps.append(step)
    lines = ['<?xml version="1.0"?>', '<VTKFile type="Collection" version="0.1" byte_order="LittleEndian">', '<Collection>']
    lines += [f'<DataSet timestep="{step * args.dt:.12g}" group="" part="0" file="frames_vtp/temperature_{step:06d}.vtp"/>' for step in steps]
    lines += ['</Collection>', '</VTKFile>']
    (args.output_dir.parent / "temperature_series_paraview.pvd").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
