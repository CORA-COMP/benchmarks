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
benchmark;instance;repetition;device;params
interval;generateRandom-1d-cpu;100;cpu;{"dim": 1, "device": "cpu"}
zonotope;matMul-500d-gpu;100;gpu;{"dim": 500, "device": "gpu"}
zonotope;minkSum-1000d-cpu;100;cpu;{"dim": 1000, "device": "cpu"}
```

| Column | Meaning |
| --- | --- |
| `benchmark` | The set representation under test. A tool enters one or more of them. |
| `instance` | `<operation>-<n>d-<device>` — the operation, the dimension it runs at, and where it runs. |
| `repetition` | How often the tool repeats the operation *within* the instance, so one measurement averages over repeats rather than timing a single noisy call. |
| `device` | `cpu` or `gpu`. Also in the instance name and in `params`, so it is filterable, readable, and available to a tool that only parses `params`. |
| `params` | JSON object with the operation's arguments: `dim` and `device` today, more for later operations. |

Every column is passed to the tool's `prepare_instance.sh` / `run_instance.sh` in file
order, after the interface version.

## Benchmarks

- `test` — not a set representation. Its operations do nothing, so the time they measure
  is the harness and process overhead, to subtract from the real benchmarks.
- `interval`
- `zonotope`

## Operations

Each is measured at every dimension `n ∈ {1, 2, 5, 10, 50, 100, 500, 1000}` on both
devices. "Random set" always means a non-degenerate set of the requested dimension.

- **`generateRandom`** — initialize a random non-degenerate set of dimension `n` (for a
  zonotope, that means `n` generators).
- **`matMul`** — generate a random `n × n` matrix and a random set of dimension `n`, then
  multiply them.
- **`minkSum`** — generate two random sets of dimension `n`, then add them.

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

To add a benchmark, an operation, or a dimension, edit the corresponding table at the top
of [`scripts/generate_instances.py`](scripts/generate_instances.py) and regenerate. An
operation that needs more than `dim` supplies it from its own `params` function.
