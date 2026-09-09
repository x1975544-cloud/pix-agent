# Tool System

Every tool implements `name`, `description`, JSON `parameters` and `run`.
`Tool.execute` converts exceptions into a stable `ToolResult` so the model
always sees a serializable observation instead of an uncaught traceback.

The built-in tools are:

| Tool | Purpose |
| --- | --- |
| `list_directory` | List workspace entries |
| `read_file` | Read UTF-8 text with size/binary guards |
| `write_file` | Write UTF-8 text inside the sandbox |
| `search_code` | Ripgrep with Python fallback |
| `run_shell` | Time-boxed non-shell process execution |
| `git_status` | Branch and working tree |
| `git_diff` | Diff against `HEAD` (or untracked state before first commit) |
| `git_log` | Recent history |
| `git_branch` | Branch listing |
| `git_commit` | Stage and commit with a message |

Safety rules:

- `Workspace.resolve` rejects paths outside the root, including symlink escapes.
- `RunShellTool` runs `subprocess` without a shell and rejects destructive
  commands and command chaining.
- Git tools never expose reset, history rewrite or force-clean operations.
- Tool results returned to storage are redacted by the tracer.
