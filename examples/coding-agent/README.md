# Coding Agent

The coding agent workflow combines planning, tool execution, verification and
Git:

```bash
cd ../..
bash scripts/demo.sh
```

That command creates a disposable workspace from `examples/demo-project`, which
contains an intentional FizzBuzz bug. The same single-agent loop performs
repository retrieval, file edits, shell tests, automatic verification retries
and final reporting.
