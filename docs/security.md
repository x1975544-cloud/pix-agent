# Security Model

Security is enforced at the boundaries:

- `Settings` reads secrets only from environment or `.env`; source code never
  contains credentials.
- `Workspace` normalizes every path and blocks traversal.
- `ShellPolicy` rejects destructive commands, Git history rewrites, pipelines,
  chaining, shell wrappers and inline interpreter code such as `python -c`.
- `RunShellTool` validates path-like arguments against `Workspace`, uses a
  restricted child environment, enforces a timeout and kills the process tree.
- File tools enforce size limits, binary detection and UTF-8 decoding.
- Child processes do not inherit credentials or interpreter startup hooks such
  as `PYTHONPATH` and `NODE_OPTIONS`.
- `Tracer` redacts sensitive keys and known secret values before persistence.
- Git tools never expose `reset`, `filter-branch`, `reflog delete` or
  destructive `clean`.

## Process boundary limits

`RunShellTool` is defense-in-depth around normal process execution, not an OS
filesystem sandbox. It rejects shell wrappers, direct inline code, and command
arguments that point outside the workspace, but a project command such as
`pytest`, `npm test`, `python script.py` or `node script.js` runs workspace
code with the current user's full filesystem and network permissions. That code
can still open arbitrary files outside the workspace, and static command
validation cannot see inside scripts, modules, symlinks or package lifecycle
hooks.

True isolation requires a container or VM boundary around the whole agent run
and its verification step, not just around `run_shell`. The container must
mount only the trusted workspace (and runtime caches), run as a non-root user,
deny host process/device access, cap CPU/memory/process counts, and make the
workspace filesystem disposable between runs. `run_shell`, automatic
verification and any package manager it invokes should all execute inside that
boundary; terminating a timed-out run should then stop the container/cgroup
instead of relying on host-side process-group cleanup.
