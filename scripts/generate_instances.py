#!/usr/bin/env python3
"""Generate ``instances.csv`` — the competition's benchmark/instance catalog.

The catalog is a cross product: every set representation (benchmark) runs every
operation at every dimension. Editing the three tables below is how the catalog grows;
the file itself is generated, never hand-edited, so the cross product can never go
half-updated.

    python scripts/generate_instances.py            # rewrite instances.csv
    python scripts/generate_instances.py --check    # fail if it is out of date (CI)

Stdlib only, so it runs anywhere without a virtualenv.
"""
import argparse
import csv
import io
import json
import os
import sys

#: Set representations under test. Each yields two benchmarks — the plain one and a
#: ``-batched`` one — so a tool can enter either without the other. ``test`` is not a
#: representation: its operations do nothing, so what it measures is the harness and
#: process overhead to subtract from the others.
BENCHMARKS = [
    "test",
    "interval",
    "zonotope",
]

#: Suffix and sizes of the batched variant, where the operation runs on a batch of sets
#: at once. Absent ``batch_size`` in params means the unbatched benchmark.
BATCHED_SUFFIX = "-batched"
BATCH_SIZES = [10, 100]

#: Dimensions each operation is measured at.
DIMENSIONS = [1, 2, 5, 10, 50, 100, 500, 1000]

#: Where the operation runs. Both are always listed; a library without GPU support
#: reports ``unsupported`` for the gpu instances.
DEVICES = ["cpu", "gpu"]

#: Operations, each measured at every dimension on every device, batched and unbatched.
#: An operation needing more than the common dim/device/batch_size adds a ``params``
#: callable returning those extras (see ``params_for``).
OPERATIONS = [
    {"name": "generateRandom"},
    {"name": "matMul"},
    {"name": "minkSum"},
]

#: How often a tool repeats the operation inside one instance, so a single measurement
#: is an average rather than one noisy sample.
DEFAULT_REPETITIONS = 100

#: Semicolon-separated, because ``params`` is JSON and contains commas. Fields are
#: written unquoted so the JSON stays readable: a standard CSV reader still parses it,
#: since a field only counts as quoted when it *starts* with a quote and JSON objects
#: start with ``{``. The cost is that no value may contain a semicolon — the writer
#: raises rather than emitting a file that would parse wrong.
DELIMITER = ";"
HEADER = ["benchmark", "instance", "repetition", "device", "params"]

OUTPUT_FILE = "instances.csv"


def instance_name(operation: str, dim: int, batch_size, device: str) -> str:
    """``<operation>-<n>d[-b<batch>]-<device>``. The batch size is part of the name
    because it is what distinguishes two instances of the same batched benchmark."""
    batch = f"-b{batch_size}" if batch_size is not None else ""
    return f"{operation}-{dim}d{batch}-{device}"


def params_for(operation: dict, dim: int, batch_size, device: str) -> dict:
    """The JSON object the tool receives. ``batch_size`` appears only for the batched
    benchmarks, so its absence is what tells a tool the operation is unbatched."""
    params = {"dim": dim, "device": device}
    if batch_size is not None:
        params["batch_size"] = batch_size
    extra = operation.get("params")
    if extra is not None:
        params.update(extra(dim=dim, batch_size=batch_size, device=device))
    return params


def rows(repetitions: int):
    """Every ``(benchmark, instance, repetition, device, params)`` row: each set
    representation unbatched, then batched, and within each operation, dimension, batch
    size, and device — so a cpu/gpu pair sits on adjacent lines."""
    for representation in BENCHMARKS:
        for benchmark, batch_sizes in (
            (representation, [None]),
            (representation + BATCHED_SUFFIX, BATCH_SIZES),
        ):
            for operation in OPERATIONS:
                for dim in DIMENSIONS:
                    for batch_size in batch_sizes:
                        for device in DEVICES:
                            yield [
                                benchmark,
                                instance_name(operation["name"], dim, batch_size, device),
                                repetitions,
                                device,
                                json.dumps(params_for(operation, dim, batch_size, device)),
                            ]


def render(repetitions: int) -> str:
    buffer = io.StringIO()
    # quotechar=None so the JSON's own quotes are written through untouched; a value
    # containing the delimiter then raises instead of being silently mangled.
    writer = csv.writer(buffer, delimiter=DELIMITER, lineterminator="\n",
                        quoting=csv.QUOTE_NONE, quotechar=None)
    writer.writerow(HEADER)
    writer.writerows(rows(repetitions))
    return buffer.getvalue()


def main(argv=None) -> int:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS,
                        help=f"repetitions per instance (default: {DEFAULT_REPETITIONS})")
    parser.add_argument("--output", default=os.path.join(repo_root, OUTPUT_FILE),
                        help=f"where to write (default: {OUTPUT_FILE} in the repo root)")
    parser.add_argument("--check", action="store_true",
                        help="do not write; exit nonzero if the file is out of date")
    args = parser.parse_args(argv)

    content = render(args.repetitions)
    if args.check:
        try:
            with open(args.output, encoding="utf-8", newline="") as fh:
                current = fh.read()
        except FileNotFoundError:
            current = None
        if current != content:
            sys.stderr.write(
                f"{args.output} is out of date; run scripts/generate_instances.py\n")
            return 1
        print(f"{args.output} is up to date.")
        return 0

    with open(args.output, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    print(f"Wrote {content.count(chr(10)) - 1} instances to {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
