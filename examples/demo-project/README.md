# Demo Project

A deliberately small FastAPI repository used by the autonomous coding demo.

It contains an intentional bug in `fizzbuzz`: multiples of 15 are checked
last, so they return `"Fizz"` instead of `"FizzBuzz"`. The tests encode the
correct behavior and fail until the implementation is fixed.

Run the full retrieval -> modify -> test -> fix demo from the repository root:

```bash
bash scripts/demo.sh
```

Or prepare a disposable workspace and run it directly:

```bash
uv run python -m pix.demo --prepare --json
```

The demo starts from a clean Git commit, enables offline repository retrieval,
lets the single agent inspect the failing code, edit it, run the test command,
and recover from an automated test failure before it stops.
