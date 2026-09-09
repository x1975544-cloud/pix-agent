# Basic Agent

Use PiX as a general agent runtime against any repository:

```bash
export OPENAI_API_KEY=...
uv run pix run --workspace ./examples/demo-project "Explain this repository"
```

The runtime analyzes manifests and entrypoints, searches and reads code, and
returns an evidence-based final answer.
