# Memory

PiX distinguishes:

- `ShortTermMemory`: session-scoped ring buffer of facts from live messages.
- `LongTermMemory`: cross-session persistent store.
- `RetrievalEngine`: combines both into context-ready results.

The source of truth is SQLite. `MemoryStoreFacade.remember()` writes a row and,
when ChromaDB plus an embedding provider is configured, indexes the same row
for semantic search. Recall uses vector search first and falls back to SQLite
`LIKE` matching, so memory never becomes unavailable just because an optional
dependency is missing.
