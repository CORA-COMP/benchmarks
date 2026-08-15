# CORA-COMP benchmarks

The benchmark catalog for [CORA-COMP](https://github.com/CORA-COMP/cora-eval-platform). A
benchmark submission points the platform at this repository and a commit; the platform reads
`instances.csv` and fans it into one benchmark per distinct `benchmark` value, each owning
its instances.

There are no data files: every instance generates its own sets at run time, so this
repository is the catalog and nothing else.

## `instances.csv`

Semicolon-separated, because `params` is JSON and contains commas. Fields are unquoted so
the JSON stays readable — a standard CSV reader still parses it, since a field only counts
as quoted when it *starts* with a quote. No value may contain a semicolon.

```
benchmark;instance;params
interval;generateRandom-1d-cpu;{"set": "interval", "operation": "generateRandom", "dim": 1, "device": "cpu", "repetition": 100}
zonotope;matMul-500d-gpu;{"set": "zonotope", "operation": "matMul", "dim": 500, "device": "gpu", "repetition": 100}
zonotope-batched;minkSum-1000d-b10-cpu;{"set": "zonotope", "operation": "minkSum", "dim": 1000, "device": "cpu", "repetition": 100, "batch_size": 10}
```

| Column | Meaning |
| --- | --- |
| `benchmark` | The set representation under test, batched or not. A tool enters one or more of them. |
| `instance` | `<operation>-<n>d[-b<batch>]-<device>` — the operation, the dimension it runs at, the batch size for a batched benchmark, and where it runs. |
| `params` | JSON object with everything the tool needs (see below). |

| `params` field | Meaning |
| --- | --- |
| `set` | The set representation to build — the benchmark without its `-batched` suffix. |
| `operation` | What to do with it. |
| `dim` | The dimension `n` to do it at. |
| `device` | `cpu` or `gpu`. |
| `repetition` | How often the tool repeats the operation *within* the instance, so one measurement averages over repeats rather than timing a single noisy call. |
| `batch_size` | Only on the batched benchmarks; its absence is what says the operation is unbatched. |

The two columns are the platform's — what a submission enters and what results are grouped
by — and `params` is the tool's: everything a tool dispatches on is in there, so it never
has to take a name apart. The instance name repeats those facts in a form that is readable
and sortable in the results table, and nothing else does, since a second copy would only be
one more thing to keep in step.

Every column is passed to the tool's `prepare_instance.sh` / `run_instance.sh` in file
order, after the interface version.

## Benchmarks

Each set representation gives two benchmarks — plain and `-batched` — so a library
without a vectorized path can enter one without the other.

- `interval` / `interval-batched`
- `zonotope` / `zonotope-batched`

Plus one that is not a set representation:

- `test` — a single instance, `startup-1d-cpu`, run once. The tool starts up and does the
  least it can: initialize one set of dimension 1, of the representation its `set` names
  (a zonotope). What it measures is therefore the
  fixed per-instance cost — process and library startup — to subtract from every other
  measurement. Enter it alongside whatever else you run.

## Operations

Each is measured at every dimension `n ∈ {1, 2, 5, 10, 50, 100, 500, 1000}` on both
devices, on the `interval` and `zonotope` benchmarks. "Random set" always means a
non-degenerate set of the requested dimension. (`test` runs none of these — see above.)

Only the operation itself is timed. A tool generates the inputs in `prepare_instance.sh`,
which is untimed, and `run_instance.sh` reads them back once and then performs the
operation `repetition` times.

| Operation | Prepared (untimed) | Measured |
| --- | --- | --- |
| `generateRandom` | — | initialize a random set of dimension `n` (for a zonotope, `n` generators) |
| `matMul` | a random `n × n` matrix and a random set of dimension `n` | the multiplication |
| `minkSum` | two random sets of dimension `n` | the addition |
| `convHull` | two random sets of dimension `n` | the convex hull — for a representation that is not closed under it (a zonotope, an interval), the tightest enclosure the representation admits |

`generateRandom` has nothing to prepare because the initialization *is* the operation.

## Batching

On a `-batched` benchmark, every set the operation would have created becomes a batch of
`batch_size` sets of dimension `n`, and the operation is applied to the whole batch in one
call — the vectorized path, rather than a loop over `batch_size` single sets. `matMul`
multiplies the batch by a single random `n × n` matrix; `minkSum` and `convHull` combine
two batches elementwise.

`batch_size` is `10` or `100`, and appears only in the batched benchmarks' `params`, so
its absence is what tells a tool the operation is unbatched (`params.get("batch_size", 1)`
covers both).

## Devices

Every instance exists for both `cpu` and `gpu`. A library with no GPU support should
report `unsupported` for the gpu instances rather than falling back to the CPU, which
would otherwise be recorded as a GPU measurement.

The gpu instances only mean anything on a GPU-capable worker: the platform's Docker
backends pass `--gpus all` into the node container when `COMP_DOCKER_GPU=1` is set on the
backend (or on the remote worker service), and that requires the NVIDIA Container Toolkit
on the host running the containers.

## Regenerating `instances.csv`

The file is the cross product of benchmarks × operations × dimensions, so it is generated
rather than hand-edited:

```bash
python scripts/generate_instances.py            # rewrite instances.csv
python scripts/generate_instances.py --check    # fail if it is out of date
```

To add a set representation, an operation, a dimension, a device, or a batch size, edit
the corresponding table at the top of
[`scripts/generate_instances.py`](scripts/generate_instances.py) and regenerate. An
operation needing more than the common `dim` / `device` / `batch_size` adds a `params`
callable returning those extras.
