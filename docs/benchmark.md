# Benchmark

Benchmark tasks are JSON documents under `benchmarks/tasks`. Each task has an
id, category, description, workspace, expected behavior and validation rules.
`BenchmarkRunner` executes tasks against a real provider and applies
machine-checkable validation:

- `file_exists`
- `file_contains`
- `command` exit code

Reports include real timestamps, success rate, latency, tool observations and
token usage where available. Reports are written under `benchmarks/results`.
The repository does not include fabricated numbers; before a real run exists
the benchmark UI and README say no result is published.
