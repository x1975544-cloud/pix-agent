# Security Model

Security is enforced at the boundaries:

- `Settings` reads secrets only from environment or `.env`; source code never
  contains credentials.
- `Workspace` normalizes every path and blocks traversal.
- `ShellPolicy` rejects destructive commands, Git history rewrites, pipelines
  and chaining.
- File tools enforce size limits, binary detection and UTF-8 decoding.
- Child shell processes do not inherit OpenAI/Anthropic/Google API keys.
- `Tracer` redacts sensitive keys and known secret values before persistence.
- Git tools never expose `reset`, `filter-branch`, `reflog delete` or
  destructive `clean`.
