#!/usr/bin/env python3
"""MPI simulation of heat diffusion between adjacent STL triangles.

Each rank owns a spatially contiguous subset of faces. Temperatures for only
cross-partition neighbours are exchanged at every explicit-Euler time step.
"""
from __future__ import annotations

import argparse
import csv
import socket
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from mpi4py import MPI
from stl import mesh as stl_mesh


def face_geometry(triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centers = triangles.mean(axis=1)
    areas = 0.5 * np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1)
    if np.any(areas <= 0):
        raise ValueError("STL contains a zero-area triangle")
    return centers, areas


def build_edges(triangles: np.ndarray, centers: np.ndarray, conductivity: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return face i, face j and conductance for every shared STL edge."""
    edges: dict[tuple[tuple[float, float, float], tuple[float, float, float]], tuple[int, float]] = {}
    closed_edges: set[tuple[tuple[float, float, float], tuple[float, float, float]]] = set()
    pairs: list[tuple[int, int, float]] = []
    for face, triangle in enumerate(triangles):
        for vertex_a, vertex_b in ((0, 1), (1, 2), (2, 0)):
            a = tuple(np.round(triangle[vertex_a], 10))
            b = tuple(np.round(triangle[vertex_b], 10))
            key = tuple(sorted((a, b)))
            # Some scanned meshes (including decimated Stanford Dragon) have
            # rare non-manifold edges. Retain the first physical face pair;
            # extra incidences are treated as insulated local boundaries.
            if key in closed_edges:
                continue
            edge_length = float(np.linalg.norm(triangle[vertex_b] - triangle[vertex_a]))
            previous = edges.pop(key, None)
            if previous is None:
                edges[key] = (face, edge_length)
            else:
                other, shared_length = previous
                distance = float(np.linalg.norm(centers[face] - centers[other]))
                if distance <= 1e-14:
                    # Degenerate duplicate facets do not define a finite
                    # conductance. Treat this local connection as absent.
                    closed_edges.add(key)
                    continue
                pairs.append((other, face, conductivity * shared_length / distance))
                closed_edges.add(key)
    if not pairs:
        raise ValueError("No adjacent triangle pairs found; check STL topology")
    return (np.asarray([p[0] for p in pairs], dtype=np.int64),
            np.asarray([p[1] for p in pairs], dtype=np.int64),
            np.asarray([p[2] for p in pairs], dtype=np.float64))


def spatial_partition(centers: np.ndarray, ranks: int) -> np.ndarray:
    """Partition ordered centroids along their widest spatial axis."""
    axis = int(np.argmax(np.ptp(centers, axis=0)))
    ordered = np.argsort(centers[:, axis], kind="stable")
    owners = np.empty(len(centers), dtype=np.int32)
    for rank, indices in enumerate(np.array_split(ordered, ranks)):
        owners[indices] = rank
    return owners


def write_vtk(path: Path, triangles: np.ndarray, values: np.ndarray) -> None:
    """Write a ParaView-readable per-triangle temperature field."""
    points = triangles.reshape(-1, 3)
    faces = np.arange(len(points), dtype=np.int64).reshape(-1, 3)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        file.write("# vtk DataFile Version 3.0\nLab2 temperature frame\nASCII\nDATASET POLYDATA\n")
        file.write(f"POINTS {len(points)} float\n")
        for point in points:
            file.write(f"{point[0]:.9g} {point[1]:.9g} {point[2]:.9g}\n")
        file.write(f"POLYGONS {len(faces)} {len(faces) * 4}\n")
        for face in faces:
            file.write(f"3 {face[0]} {face[1]} {face[2]}\n")
        file.write(f"CELL_DATA {len(values)}\nSCALARS temperature float 1\nLOOKUP_TABLE default\n")
        for value in values:
            file.write(f"{value:.9g}\n")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--dt", type=float, default=None, help="Fixed time step; omitted selects a stable step")
    parser.add_argument("--safety", type=float, default=0.45, help="Multiplier for the explicit stability bound")
    parser.add_argument("--initial-temperature", type=float, default=20.0)
    parser.add_argument("--hot-temperature", type=float, default=500.0)
    parser.add_argument("--hot-face", type=int, default=None)
    parser.add_argument("--source-radius", type=float, default=0.0, help="Radius of the fixed hot polygon region")
    parser.add_argument("--save-every", type=int, default=0, help="Write VTK frame every N steps; 0 disables frames")
    parser.add_argument("--conductivity", type=float, default=1.0)
    parser.add_argument("--rho", type=float, default=1.0)
    parser.add_argument("--specific-heat", type=float, default=1.0)
    parser.add_argument("--thickness", type=float, default=1.0)
    parser.add_argument("--debug", action="store_true", help="Print MPI progress checkpoints for diagnostics")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    comm = MPI.COMM_WORLD
    rank, ranks = comm.rank, comm.size
    def debug(message: str) -> None:
        if args.debug:
            print(f"rank={rank}: {message}", flush=True)
    if args.steps < 1 or args.source_radius < 0 or args.save_every < 0 or args.safety <= 0 or args.safety > 1 or min(args.conductivity, args.rho, args.specific_heat, args.thickness) <= 0:
        raise SystemExit("Invalid physical parameters, steps, or safety factor")

    if rank == 0:
        try:
            loaded = stl_mesh.Mesh.from_file(str(args.mesh))
            triangles = np.asarray(loaded.vectors, dtype=np.float64)
            centers, areas = face_geometry(triangles)
            edge_i, edge_j, conductance = build_edges(triangles, centers, args.conductivity)
            owners = spatial_partition(centers, ranks)
            capacity = args.rho * args.specific_heat * args.thickness * areas
            total_conductance = np.zeros(len(areas))
            np.add.at(total_conductance, edge_i, conductance)
            np.add.at(total_conductance, edge_j, conductance)
            stability_dt = float(np.min(capacity / total_conductance))
            dt = args.dt if args.dt is not None else args.safety * stability_dt
            if dt <= 0 or dt > stability_dt * (1 + 1e-12):
                raise ValueError(f"dt={dt} violates explicit stability bound {stability_dt}")
            hot_face = args.hot_face if args.hot_face is not None else int(np.argmin(np.linalg.norm(centers - centers.mean(axis=0), axis=1)))
            if not 0 <= hot_face < len(areas):
                raise ValueError("hot-face is outside mesh face range")
            source_mask = np.linalg.norm(centers - centers[hot_face], axis=1) <= args.source_radius if args.source_radius else np.zeros(len(areas), dtype=bool)
            source_mask[hot_face] = True
            data = dict(triangles=triangles, centers=centers, capacity=capacity, edge_i=edge_i, edge_j=edge_j,
                        conductance=conductance, owners=owners, dt=dt, stability_dt=stability_dt, hot_face=hot_face, source_mask=source_mask)
        except (OSError, ValueError) as error:
            print(f"Cannot prepare mesh: {error}", flush=True)
            comm.Abort(2)
            return
    else:
        data = None
    data = comm.bcast(data, root=0)
    debug("mesh metadata broadcast complete")

    owners = data["owners"]
    owned = np.flatnonzero(owners == rank)
    edge_i, edge_j, conductance = data["edge_i"], data["edge_j"], data["conductance"]
    local_i = owners[edge_i] == rank
    local_j = owners[edge_j] == rank
    internal = local_i & local_j
    cross_for_i = local_i & ~local_j
    cross_for_j = local_j & ~local_i
    send_sets: dict[int, set[int]] = defaultdict(set)
    receive_sets: dict[int, set[int]] = defaultdict(set)
    for a, b in zip(edge_i[cross_for_i], edge_j[cross_for_i]):
        receive_sets[int(owners[b])].add(int(b)); send_sets[int(owners[b])].add(int(a))
    for a, b in zip(edge_i[cross_for_j], edge_j[cross_for_j]):
        receive_sets[int(owners[a])].add(int(a)); send_sets[int(owners[a])].add(int(b))
    send_ids = {peer: np.fromiter(sorted(ids), dtype=np.int64) for peer, ids in send_sets.items()}
    receive_ids = {peer: np.fromiter(sorted(ids), dtype=np.int64) for peer, ids in receive_sets.items()}
    peers = sorted(set(send_ids) | set(receive_ids))

    temperature = np.full(len(owners), args.initial_temperature, dtype=np.float64)
    source_owned = owned[data["source_mask"][owned]]
    temperature[source_owned] = args.hot_temperature
    capacity = data["capacity"]
    local_position = {int(face): position for position, face in enumerate(owned)}
    communication_seconds = compute_seconds = 0.0
    frame_steps: list[int] = []
    frames_dir = args.output_dir / "frames"
    if rank == 0 and args.save_every:
        frames_dir.mkdir(parents=True, exist_ok=True)
        write_vtk(frames_dir / "temperature_000000.vtk", data["triangles"], temperature)
        frame_steps.append(0)
    wall_start = time.perf_counter()
    for step in range(1, args.steps + 1):
        debug("starting ghost exchange")
        exchange_start = time.perf_counter()
        incoming = {peer: np.empty(len(receive_ids.get(peer, ())), dtype=np.float64) for peer in peers}
        requests = [comm.Irecv(incoming[peer], source=peer, tag=17) for peer in peers if len(incoming[peer])]
        requests += [comm.Isend(temperature[send_ids[peer]], dest=peer, tag=17) for peer in peers if len(send_ids.get(peer, ()))]
        MPI.Request.Waitall(requests)
        debug("ghost exchange complete")
        ghost = {int(face): value for peer in peers for face, value in zip(receive_ids.get(peer, ()), incoming[peer])}
        communication_seconds += time.perf_counter() - exchange_start

        compute_start = time.perf_counter()
        flux = np.zeros(len(owned), dtype=np.float64)
        for a, b, k in zip(edge_i[internal], edge_j[internal], conductance[internal]):
            delta = k * (temperature[b] - temperature[a])
            flux[local_position[int(a)]] += delta
            flux[local_position[int(b)]] -= delta
        for a, b, k in zip(edge_i[cross_for_i], edge_j[cross_for_i], conductance[cross_for_i]):
            flux[local_position[int(a)]] += k * (ghost[int(b)] - temperature[a])
        for a, b, k in zip(edge_i[cross_for_j], edge_j[cross_for_j], conductance[cross_for_j]):
            flux[local_position[int(b)]] += k * (ghost[int(a)] - temperature[b])
        temperature[owned] += data["dt"] * flux / capacity[owned]
        temperature[source_owned] = args.hot_temperature
        compute_seconds += time.perf_counter() - compute_start
        debug("temperature update complete")
        if args.save_every and step % args.save_every == 0:
            snapshot = comm.gather((owned, temperature[owned]), root=0)
            if rank == 0:
                field = np.empty(len(owners), dtype=np.float64)
                for faces, values in snapshot:
                    field[faces] = values
                write_vtk(frames_dir / f"temperature_{step:06d}.vtk", data["triangles"], field)
                frame_steps.append(step)

    elapsed = time.perf_counter() - wall_start
    gathered = comm.gather((owned, temperature[owned]), root=0)
    debug("gather complete")
    if rank == 0:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    comm.Barrier()
    worker_path = args.output_dir / "worker"
    worker_path.mkdir(exist_ok=True)
    with (worker_path / f"rank-{rank}.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["hostname", "rank", "faces", "ghost_faces", "internal_edges", "cross_edges", "communication_seconds", "compute_seconds", "elapsed_seconds"])
        writer.writerow([socket.gethostname(), rank, len(owned), sum(len(x) for x in receive_ids.values()), int(internal.sum()), int(cross_for_i.sum() + cross_for_j.sum()), communication_seconds, compute_seconds, elapsed])
    if rank == 0:
        final_temperature = np.empty(len(owners), dtype=np.float64)
        for faces, values in gathered:
            final_temperature[faces] = values
        np.savez_compressed(args.output_dir / "final_state.npz", triangles=data["triangles"], temperature=final_temperature,
                            centers=data["centers"], owners=owners, dt=data["dt"], steps=args.steps, hot_face=data["hot_face"])
        if args.save_every:
            if args.steps not in frame_steps:
                write_vtk(frames_dir / f"temperature_{args.steps:06d}.vtk", data["triangles"], final_temperature)
                frame_steps.append(args.steps)
            pvd = ["<?xml version=\"1.0\"?>", "<VTKFile type=\"Collection\" version=\"0.1\" byte_order=\"LittleEndian\">", "<Collection>"]
            for frame_step in frame_steps:
                pvd.append(f'<DataSet timestep="{frame_step * data["dt"]:.12g}" group="" part="0" file="frames/temperature_{frame_step:06d}.vtk"/>')
            pvd.extend(["</Collection>", "</VTKFile>"])
            (args.output_dir / "temperature_series.pvd").write_text("\n".join(pvd) + "\n", encoding="utf-8")
        energy = float(np.dot(data["capacity"], final_temperature))
        (args.output_dir / "summary.csv").write_text(
            "faces,edges,ranks,steps,dt,stability_dt,hot_face,final_energy,elapsed_seconds\n"
            f"{len(owners)},{len(edge_i)},{ranks},{args.steps},{data['dt']},{data['stability_dt']},{data['hot_face']},{energy},{elapsed}\n",
            encoding="utf-8")
        print(f"faces={len(owners)} edges={len(edge_i)} ranks={ranks} dt={data['dt']:.6g} elapsed={elapsed:.3f}s")


if __name__ == "__main__":
    main()
