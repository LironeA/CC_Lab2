#!/usr/bin/env python3
"""Render the final temperature field from a simulation NPZ file."""
from __future__ import annotations

import argparse
from pathlib import Path
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    data = np.load(args.state)
    triangles, temperature = data["triangles"], data["temperature"]
    normalized = plt.Normalize(float(temperature.min()), float(temperature.max()))
    collection = Poly3DCollection(triangles, facecolors=plt.cm.inferno(normalized(temperature)), linewidths=0)
    figure = plt.figure(figsize=(8, 6)); axis = figure.add_subplot(projection="3d")
    axis.add_collection3d(collection); axis.auto_scale_xyz(triangles[..., 0].flat, triangles[..., 1].flat, triangles[..., 2].flat)
    figure.colorbar(plt.cm.ScalarMappable(norm=normalized, cmap="inferno"), ax=axis, label="Temperature")
    axis.set_title("Temperature on triangular mesh")
    output = args.output or args.state.with_suffix(".png")
    figure.savefig(output, dpi=180, bbox_inches="tight")
    print(output)


if __name__ == "__main__":
    main()
