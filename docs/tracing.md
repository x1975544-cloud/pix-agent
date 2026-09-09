# Tracing and Observability

`Tracer` receives a session id and a list of active secret values. Every event
is redacted recursively before insertion, so keys such as `api_key`, `token`,
`password` and `secret` never reach SQLite. Raw secrets matched by pattern or
literal values are also replaced.

Canonical events include:

`SESSION_STARTED`, `REPOSITORY_ANALYZED`, `PLAN_CREATED`, `CONTEXT_BUILD`,
`LLM_REQUEST`, `LLM_RESPONSE`, `TOOL_CALL`, `TOOL_RESULT`,
`VERIFICATION_STARTED`, `VERIFICATION_FINISHED`, `AGENT_ERROR` and
`AGENT_FINISHED`.

`LLM_RESPONSE` records usage returned by the provider. Token totals can be
aggregated per session without inventing cost when pricing is unknown.
