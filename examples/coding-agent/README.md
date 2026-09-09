# Coding Agent

The coding agent workflow combines planning, tool execution, verification and
Git:

```bash
uv run pix run --workspace .demo/hello-fastapi "Add a health check endpoint"
```

The same loop supports bug fixing, test generation and refactoring tasks. All
changes are made through sandboxed tools inside the workspace.
