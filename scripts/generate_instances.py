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
#: ``-batched`` one — so a tool can enter either without the other.
BENCHMARKS = [
    "interval",
    "zonotope",
]

#: The overhead benchmark: a single instance, run once, doing the least a library can do —
#: start up and initialize one zonotope. Its measured time is the fixed per-instance cost
#: (process and library startup) to subtract from every other measurement, so it takes no
#: dimension sweep, no batching, and no repetitions.
OVERHEAD_BENCHMARK = "test"
OVERHEAD_SET = "zonotope"
OVERHEAD_OPERATION = "startup"
OVERHEAD_DIM = 1
OVERHEAD_DEVICE = "cpu"
OVERHEAD_REPETITIONS = 1

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
    {"name": "convHull"},
]

#: How often a tool repeats the operation inside one instance, so a single measurement
#: is an average rather than one noisy sample.
DEFAULT_REPETITIONS = 100

#: Wall-clock cap per instance, in seconds, enforced by the harness. A cap, not a budget:
#: the largest instance a library handles comfortably is a second or two of work, so a tool
#: that needs a minute is out of reach of the comparison and reports `timeout`. Uncapped,
#: one batched instance at the top dimension can hold a worker for days.
DEFAULT_TIMEOUT = 60

#: Semicolon-separated, because ``params`` is JSON and contains commas. Fields are
#: written unquoted so the JSON stays readable: a standard CSV reader still parses it,
#: since a field only counts as quoted when it *starts* with a quote and JSON objects
#: start with ``{``. The cost is that no value may contain a semicolon — the writer
#: raises rather than emitting a file that would parse wrong.
DELIMITER = ";"
#: The columns are the platform's — what to group by, what to call the row, how long to
#: allow it — and ``params`` is the tool's: everything a tool reads lives there, so no
#: field needs a second copy in a column of its own.
HEADER = ["benchmark", "instance", "params", "timeout"]

OUTPUT_FILE = "instances.csv"


def instance_name(operation: str, dim: int, batch_size, device: str) -> str:
    """``<operation>-<n>d[-b<batch>]-<device>``. The batch size is part of the name
    because it is what distinguishes two instances of the same batched benchmark."""
    batch = f"-b{batch_size}" if batch_size is not None else ""
    return f"{operation}-{dim}d{batch}-{device}"


def params_for(representation: str, operation: dict, dim: int, batch_size, device: str,
               repetitions: int) -> dict:
    """The JSON object the tool receives — everything it needs to run the instance, so it
    dispatches on parsed fields instead of splitting the benchmark and instance names.
    ``set`` is the representation without the batched suffix, and ``batch_size`` appears
    only for the batched benchmarks, so its absence is what tells a tool the operation is
    unbatched."""
    params = {"set": representation, "operation": operation["name"], "dim": dim,
              "device": device, "repetition": repetitions}
    if batch_size is not None:
        params["batch_size"] = batch_size
    extra = operation.get("params")
    if extra is not None:
        params.update(extra(dim=dim, batch_size=batch_size, device=device))
    return params


def rows(repetitions: int, timeout: int):
    """Every ``(benchmark, instance, params, timeout)`` row: the overhead instance, then
    each set representation unbatched and batched, and within each operation, dimension,
    batch size, and device — so a cpu/gpu pair sits on adjacent lines."""
    yield [
        OVERHEAD_BENCHMARK,
        instance_name(OVERHEAD_OPERATION, OVERHEAD_DIM, None, OVERHEAD_DEVICE),
        json.dumps({"set": OVERHEAD_SET, "operation": OVERHEAD_OPERATION,
                    "dim": OVERHEAD_DIM, "device": OVERHEAD_DEVICE,
                    "repetition": OVERHEAD_REPETITIONS}),
        timeout,
    ]
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
                                json.dumps(params_for(representation, operation, dim,
                                                      batch_size, device, repetitions)),
                                timeout,
                            ]


def render(repetitions: int, timeout: int) -> str:
    buffer = io.StringIO()
    # quotechar=None so the JSON's own quotes are written through untouched; a value
    # containing the delimiter then raises instead of being silently mangled.
    writer = csv.writer(buffer, delimiter=DELIMITER, lineterminator="\n",
                        quoting=csv.QUOTE_NONE, quotechar=None)
    writer.writerow(HEADER)
    writer.writerows(rows(repetitions, timeout))
    return buffer.getvalue()


def main(argv=None) -> int:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS,
                        help=f"repetitions per instance (default: {DEFAULT_REPETITIONS})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"per-instance wall-clock cap in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--output", default=os.path.join(repo_root, OUTPUT_FILE),
                        help=f"where to write (default: {OUTPUT_FILE} in the repo root)")
    parser.add_argument("--check", action="store_true",
                        help="do not write; exit nonzero if the file is out of date")
    args = parser.parse_args(argv)

    content = render(args.repetitions, args.timeout)
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
