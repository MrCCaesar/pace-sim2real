"""Convert synchronized, named motor CSV frames to a PACE reference on CPU."""

import argparse
import csv
import json
import math
import os
import tempfile
from ctypes import c_float
from pathlib import Path

import torch


def _columns(header, legs, wheels):
    if not header or len(set(header)) != len(header):
        raise ValueError("Empty or duplicate CSV header")
    indices = {field: i for i, field in enumerate(header)}
    if "time_s" not in indices:
        raise ValueError("Missing time_s")
    recorded = {field.rsplit(".", 1)[0] for field in header if "." in field}
    unknown = recorded.difference(legs, wheels)
    if unknown or not recorded:
        raise ValueError(f"Unknown or empty joint selection: {sorted(unknown)}")
    groups = [[joint for joint in order if joint in recorded] for order in (legs, wheels)]
    signals = {}
    flags = {}
    for names, field, key in zip(groups, ("q", "dq"), ("dof_pos", "dof_vel"), strict=True):
        if names:
            for suffix, output in ((field, key), (field + "_des", "des_" + key)):
                signals[output] = [indices[f"{name}.{suffix}"] for name in names]
            flags.update({name: indices[f"{name}.feedback_valid"] for name in names})
    return groups, signals, flags


def _number(row, col, header, line, *, signal=False):
    try:
        value = float(row[col])
        if math.isfinite(value) and (not signal or math.isfinite(c_float(value).value)):
            return value
    except (ValueError, OverflowError):
        pass
    raise ValueError(f"CSV line {line}: invalid {header[col]}") from None


def _read(path, legs, wheels):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, [])
        groups, signals, flags = _columns(header, legs, wheels)
        values = {key: [] for key in signals}
        times, lines = [], []
        leading = trailing = total = 0
        gap = None
        clock = header.index("time_s")
        for row in reader:
            total += 1
            line = reader.line_num
            if len(row) != len(header):
                raise ValueError(f"CSV line {line}: expected {len(header)} fields, got {len(row)}")
            invalid = []
            for name, col in flags.items():
                if row[col] not in ("0", "1"):
                    raise ValueError(f"CSV line {line}: invalid {header[col]}")
                if row[col] == "0":
                    invalid.append(name)
            if invalid:
                if times:
                    trailing += 1
                    if gap is None:
                        gap = f"CSV line {line}: missing feedback for {', '.join(invalid)}"
                else:
                    leading += 1
                continue
            if gap:
                raise ValueError(gap)
            t = _number(row, clock, header, line)
            if times and t <= times[-1]:
                raise ValueError(f"CSV line {line}: time_s must increase")
            lines.append(line)
            times.append(t)
            for key, cols in signals.items():
                values[key].append([_number(row, col, header, line, signal=True) for col in cols])
    if len(times) < 2:
        raise ValueError("Need at least two fully valid frames")
    data = {key: torch.tensor(rows, dtype=torch.float32) for key, rows in values.items()}
    data["time"] = torch.tensor(times, dtype=torch.float64)
    return data, groups, lines, (total, leading, trailing)


def _save(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent) as stream:
        torch.save(data, stream)
        stream.flush()
        try:
            os.link(stream.name, path)
        except FileExistsError:
            raise ValueError(f"{path} already exists; choose another --output name") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--task", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    from gymnasium.error import Error as GymError

    from pace_sim2real.utils.collection_contracts import resolve_joint_groups
    from pace_sim2real.utils.paths import ISAAC_COLLECTION_FILENAME
    from pace_sim2real.utils.sample_period import load_recording_task, resolve_sample_period

    try:
        cfg = load_recording_task(args.task)
        legs, wheels = resolve_joint_groups(cfg.sim2real)
        data, groups, lines, (total, leading, trailing) = _read(args.csv, legs, wheels)
        task_dt = cfg.sim.dt * cfg.decimation
        dt = resolve_sample_period(data["time"], task_dt, lines)
        output = args.csv.parent / (args.output or ISAAC_COLLECTION_FILENAME)
        _save(output, data)
    except (OSError, ValueError, KeyError, csv.Error, AttributeError, GymError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")
    print(f"Saved {output}: input={total} retained={len(lines)} trimmed_start={leading} trimmed_end={trailing}")
    for field, names in zip(("reference_leg_order", "reference_wheel_order"), groups, strict=True):
        print(f"env.sim2real.{field}={json.dumps(names)}")
    print(f"Control period: {dt!r} s")
    if dt != task_dt:
        print(f"Task default is {task_dt!r} s; for strict fit use env.sim.dt={dt!r} env.decimation=1")


if __name__ == "__main__":
    main()
