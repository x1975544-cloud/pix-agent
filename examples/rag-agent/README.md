# RAG-style Repository Agent

Repository facts are stored as long-term memory with SQLite keyword retrieval.
With the optional `memory` extra, ChromaDB plus an embedding provider enables
semantic recall:

```bash
uv sync --extra memory --extra dev
uv run pix run --workspace ./examples/demo-project "Summarize this project from memory"
```

The retrieval engine feeds recent short-term facts and cross-session long-term
matches into the context manager.
