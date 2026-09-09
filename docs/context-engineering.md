# Context Engineering

`ContextManager` assembles system content and history under a token budget.
Content is represented as prioritized `ContextSection`s:

```text
System instructions > task > plan > current tool state >
repository facts > memory > old history
```

`estimate_tokens()` is intentionally deterministic and cheap (roughly four
characters per token), documented as an approximation. `ContextBuilder` keeps
the newest high-value messages and marks truncation. `ContextCompressor` then
summarizes older user/assistant/tool content into compact facts instead of
simply dropping it.

The executor's system prompt includes repository signals, the current plan,
active skills and the verification command, which keeps the model focused on
the concrete workspace rather than generic coding advice.
