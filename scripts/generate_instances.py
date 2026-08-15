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

#: Set representations under test. One benchmark each, so a tool can enter a subset.
BENCHMARKS = [
    "interval",
    "zonotope",
]

#: Dimensions each operation is measured at.
DIMENSIONS = [1, 2, 5, 10, 50, 100, 500, 1000]

#: Operations, each measured at every dimension. ``params`` maps a dimension to the
#: JSON object the tool receives; operations added later may take more than ``dim``.
OPERATIONS = [
    {"name": "generateRandom", "params": lambda dim: {"dim": dim}},
    {"name": "matMul", "params": lambda dim: {"dim": dim}},
    {"name": "minkSum", "params": lambda dim: {"dim": dim}},
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
HEADER = ["benchmark", "instance", "repetition", "params"]

OUTPUT_FILE = "instances.csv"


def instance_name(operation: str, dim: int) -> str:
    return f"{operation}-{dim}d"


def rows(repetitions: int):
    """Every ``(benchmark, instance, repetition, params)`` row, benchmark-major then
    operation then dimension — the order the file is read in."""
    for benchmark in BENCHMARKS:
        for operation in OPERATIONS:
            for dim in DIMENSIONS:
                params = operation["params"](dim)
                yield [
                    benchmark,
                    instance_name(operation["name"], dim),
                    repetitions,
                    json.dumps(params),
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
