# Demo Project

A deliberately small FastAPI repository used by `scripts/demo.sh`.

Run the agent from the repository root with:

```bash
uv run pix run --workspace .demo/hello-fastapi "Add a health check endpoint"
```

The demo starts from a clean Git commit, lets the agent inspect files, implement
the endpoint and test it, then optionally commit the result.
