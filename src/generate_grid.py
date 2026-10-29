#!/usr/bin/env python3
"""Generate a triangulated, slightly curved plate in ASCII STL format."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def point(x: float, y: float, size: float, amplitude: float) -> tuple[float, float, float]:
    z = amplitude * np.sin(np.pi * x / size) * np.sin(np.pi * y / size)
    return x, y, float(z)


def facet(file, a, b, c) -> None:
    normal = np.cross(np.subtract(b, a), np.subtract(c, a))
    length = np.linalg.norm(normal)
    normal = normal / length if length else np.zeros(3)
    file.write(f"  facet normal {normal[0]:.9g} {normal[1]:.9g} {normal[2]:.9g}\n    outer loop\n")
    for vertex in (a, b, c):
        file.write(f"      vertex {vertex[0]:.9g} {vertex[1]:.9g} {vertex[2]:.9g}\n")
    file.write("    endloop\n  endfacet\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an STL plate for heat-transfer tests")
    parser.add_argument("--output", type=Path, default=Path("data/input/plate.stl"))
    parser.add_argument("--resolution", type=int, default=100, help="cells along each side")
    parser.add_argument("--size", type=float, default=1.0)
    parser.add_argument("--amplitude", type=float, default=0.04)
    args = parser.parse_args()
    if args.resolution < 1 or args.size <= 0:
        raise SystemExit("resolution and size must be positive")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    step = args.size / args.resolution
    with args.output.open("w", encoding="ascii") as file:
        file.write("solid heat_plate\n")
        for row in range(args.resolution):
            for column in range(args.resolution):
                x, y = column * step, row * step
                a = point(x, y, args.size, args.amplitude)
                b = point(x + step, y, args.size, args.amplitude)
                c = point(x + step, y + step, args.size, args.amplitude)
                d = point(x, y + step, args.size, args.amplitude)
                facet(file, a, b, c)
                facet(file, a, c, d)
        file.write("endsolid heat_plate\n")
    print(f"Created {args.output} with {2 * args.resolution ** 2} triangles")


if __name__ == "__main__":
    main()
