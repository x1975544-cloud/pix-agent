# Benchmark

PiX benchmark tasks are JSON files under `tasks/`. Every task describes a real
workspace, an expected behavior and machine-checkable validation rules. The
directory is intentionally kept for task files; no verified tasks are shipped
with v1.0 yet.

Run them only when an OpenAI-compatible provider is configured:

```bash
export OPENAI_API_KEY=...
pix benchmark benchmarks/tasks
```

Reports are written to `results/` with real timestamps, statuses, validation
output and latency. The repository does not ship fabricated success data; if no
real run has happened, the benchmark section reports that state.
