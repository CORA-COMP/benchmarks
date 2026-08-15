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
benchmark;instance;repetition;params
interval;generateRandom-1d;100;{"dim": 1}
zonotope;matMul-500d;100;{"dim": 500}
zonotope;minkSum-1000d;100;{"dim": 1000}
```

| Column | Meaning |
| --- | --- |
| `benchmark` | The set representation under test. A tool enters one or more of them. |
| `instance` | `<operation>-<n>d` — the operation and the dimension it runs at. |
| `repetition` | How often the tool repeats the operation *within* the instance, so one measurement averages over repeats rather than timing a single noisy call. |
| `params` | JSON object with the operation's arguments. Currently only `dim`; later operations may take more. |

Every column is passed to the tool's `prepare_instance.sh` / `run_instance.sh` in file
order, after the interface version.

## Benchmarks

- `interval`
- `zonotope`

## Operations

Each is measured at every dimension `n ∈ {1, 2, 5, 10, 50, 100, 500, 1000}`. "Random set"
always means a non-degenerate set of the requested dimension.

- **`generateRandom`** — initialize a random non-degenerate set of dimension `n` (for a
  zonotope, that means `n` generators).
- **`matMul`** — generate a random `n × n` matrix and a random set of dimension `n`, then
  multiply them.
- **`minkSum`** — generate two random sets of dimension `n`, then add them.

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
