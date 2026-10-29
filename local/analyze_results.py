#!/usr/bin/env python3
"""Aggregate Lab2 Slurm measurements and plot scaling graphs locally."""
from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    with (args.results / "metrics" / "runs.csv").open(newline="", encoding="utf-8") as file:
        runs = [r for r in csv.DictReader(file) if r["status"] == "COMPLETED" and int(r["repeat"]) > 0 and r["elapsed_seconds"]]
    groups: dict[tuple[str, int, int], list[float]] = defaultdict(list)
    for run in runs:
        groups[(run.get("mode", "simulation"), int(run["nodes"]), int(run["steps"]))].append(float(run["elapsed_seconds"]))
    valid_steps = {
        (mode, steps) for mode, _, steps in groups
        if (mode, 1, steps) in groups and any(other_mode == mode and nodes > 1 and other_steps == steps for other_mode, nodes, other_steps in groups)
    }
    rows = []
    for (mode, nodes, steps), values in sorted(groups.items()):
        if (mode, steps) not in valid_steps:
            # A standalone smoke test has no serial baseline and cannot
            # contribute to a speedup series.
            continue
        median = statistics.median(values)
        base = statistics.median(groups[(mode, 1, steps)])
        speedup = base / median
        rows.append(dict(mode=mode, nodes=nodes, steps=steps, samples=len(values), median_seconds=median,
                         speedup=speedup, efficiency_percent=100 * speedup / nodes))
    if not rows:
        raise SystemExit("No completed measured runs")
    metrics = args.results / "metrics"; figures = args.results / "figures"
    figures.mkdir(exist_ok=True)
    with (metrics / "aggregate.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    for key, title, ylabel, filename in (("median_seconds", "Execution time", "Seconds", "execution_time.png"),
                                         ("speedup", "Speedup", "S(N)", "speedup.png"),
                                         ("efficiency_percent", "Efficiency", "Percent", "efficiency.png")):
        plt.figure(figsize=(7, 4))
        for mode in sorted({r["mode"] for r in rows}):
            points = [r for r in rows if r["mode"] == mode]
            plt.plot([r["nodes"] for r in points], [r[key] for r in points], marker="o", label=mode)
        plt.title(title); plt.xlabel("MPI processes"); plt.ylabel(ylabel); plt.grid(alpha=.3); plt.tight_layout()
        plt.legend()
        plt.savefig(figures / filename, dpi=160); plt.close()
    print(f"Wrote {metrics / 'aggregate.csv'} and scaling figures")


if __name__ == "__main__":
    main()
