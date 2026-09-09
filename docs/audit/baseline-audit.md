# PiX Agent 基线审计

日期: 2026-09-09

审计对象: `main` 分支 `2674f97` 之上的当前工作树。工作树包含未提交改动和新增文件，主要是流式事件总线/SSE、仓库语义索引、本地向量嵌入与 OpenAI 集成测试。本次审计把当前工作树视为项目基线，没有修改任何代码。

## 项目结构概览

- `pix/`: Python agent runtime，约 70 个源文件。
  - `agent/`: 编排器、planner、agent loop、状态。
  - `providers/`, `embedding/`, `indexing/`: LLM、embedding、语义索引抽象。
  - `tools/`, `security.py`: 文件、搜索、Shell、Git、MCP 工具及安全边界。
  - `context/`, `memory/`, `skills/`: 上下文工程、持久记忆、技能注入。
  - `persistence/`, `tracing/`: SQLite 存储和可观测性。
  - `api/`, `cli.py`: FastAPI 和 CLI。
- `web/`: Next.js 16.3.4 仪表盘，包含 dashboard、run、sessions、trace、tools、benchmark、settings。
- `tests/`: 21 个测试文件；`benchmarks/tasks` 目前没有正式任务。
- 文档与部署: `docs/`, `Dockerfile`, `docker-compose.yml`, `Makefile`。

核心架构方向是清楚的: provider-neutral `LLMProvider`、统一 `Tool`、上下文 token budget、SQLite 持久化。代码整体可读，模块边界基本一致，没有发现强依赖 LangChain/LangGraph 的问题。

## 验证结果

| 检查 | 结果 | 说明 |
| --- | --- | --- |
| Python 单元/集成测试 | 50 passed, 2 skipped | `pytest` 收集 52 项；2 项实时 OpenAI 测试在无 `PIX_RUN_LIVE_TESTS=1` 时跳过。运行约 8.2s。 |
| `ruff check pix tests` | 失败 | `pix/embedding/local.py:33` 触发 `B905`，需要显式 `strict=`。 |
| `ruff format --check pix tests` | 失败 | `pix/embedding/__init__.py`、`pix/indexing/chroma_store.py`、`pix/providers/openai.py` 需要格式化。 |
| `mypy pix` | 失败 | 默认配置下，当前 numpy/Chromadb 类型存根与 `python_version = "3.11"` 冲突，检查被 `numpy/__init__.pyi` 阻断。用 `--python-version 3.12` 复核得到 7 个真实类型错误，集中在 `pix/indexing/chroma_store.py` 和 `pix/agent/executor.py:396`。 |
| Web TypeScript | 通过 | `npm exec tsc -- --noEmit` 无错误。 |
| Web 生产构建 | 通过 | 将 Next 配置目录指向临时目录后 `npm run build` 成功；默认环境首次报 `EXDEV`，属于本机 AppData 跨盘问题，不是项目代码错误。 |
| `git diff --check` | 通过 | 无空白错误。 |

注意: 项目没有 web 自动化测试；`web/package.json` 没有 `test` 脚本。Python 没有强制覆盖率阈值，也未配置 CI。

## 关键问题

### P0: HTTP API 无认证，且允许客户端指定任意工作目录

FastAPI 路由没有任何认证、授权或 CSRF 防护，而 `/api/agent/run` 接受客户端提供的 `workspace` 并启动完整 agent。`AgentExecutor.execute()` 直接解析该路径作为沙箱根目录，随后注册可写文件的工具、可运行任意解释器命令的 `run_shell` 和可提交修改的 Git 工具。

相关位置:

- `pix/api/routes/agent.py:42-43`、`pix/api/routes/agent.py:71-72`
- `pix/api/schemas.py:13`
- `pix/agent/executor.py:99-110`
- `pix/agent/executor.py:374-380`
- `docker-compose.yml` 将 API 暴露到宿主机 `8000` 端口。

风险: 只要 API 监听地址对网络或同机其他进程可见，调用者就可以让 agent 在任意本地目录执行代码、读文件、写文件、运行测试和提交 Git，而不需要持有任何凭证。这个风险是设计层面的，不是单纯漏加一个 header。

### P0/P1: Shell 与“沙箱”不是真正的进程安全边界

`RunShellTool` 只是禁用 shell、过滤部分危险字符串并设置工作目录；被执行的 `python`、`node`、`pytest` 等进程仍拥有完整用户权限。LLM 可以写一个 Python 脚本再运行它，从而读取或修改工作区外的文件，也可以访问网络。

相关位置:

- `pix/tools/shell.py:56-93`
- `pix/security.py` 中的 `ShellPolicy`

另外，ShellPolicy 的拒绝规则偏 Unix 风格；Windows 下 `cmd /c rd /s /q ...`、PowerShell `Remove-Item -Recurse` 等命令没有对等的规则覆盖。

结论: 文件工具的 `Workspace` 路径检查是有效的边界；但把 `run_shell` 称为沙箱会高估安全性。真正隔离不可信仓库/模型代码需要容器或 VM。

### P1: `/api/traces/{id}/stream` 收不到任何活跃 run 的事件

`stream_trace` 在自己的 handler 里新建 `EventBus()`，并等待该 bus。普通 `/api/agent/run` 根本没有 event bus；`/api/agent/run/stream` 也只把事件发布到它自己创建的局部 bus，trace stream 无法订阅。因此，对一个正在运行 session 调用 trace stream 时，它只会先输出已经落库的历史事件，然后无限等待，run 结束后也不会结束，因为没有重新检查 DB 状态。

相关位置:

- `pix/api/routes/agent.py:76` 与 `pix/api/routes/agent.py:90`
- `pix/api/routes/traces.py:46`
- `pix/agent/executor.py:75` 和 `pix/agent/executor.py:117`

同一套未提交功能还缺少:

- 客户端断开后的取消或清理路径；每次 `/run/stream` 都会启动 daemon thread，没有并发限制，也没有中止已有 HTTP 请求的机制。
- `EventBus` 的文档写“thread-safe”，但订阅列表没有锁或并发原语。
- 每个 token delta 都通过 `Tracer.sink()` 写 SQLite，流式 token 会被逐条持久化，会造成大量小写入并放大 trace DB。
- `TOKEN` 和 `REPOSITORY_INDEXED` 不在 `pix/tracing/events.py` 的 canonical `EVENT_TYPES` 中，观测 schema 开始漂移。

### P1: JS 项目没有 test script 时仍会检测出 `npm test`

`RepositoryAnalyzer._detect_test_command()` 对任意 `package.json` 都返回 `npm test`，即使 `scripts.test` 不存在；`VerificationEngine.detect_test_command()` 同样无条件返回 `npm test -- --runInBand`。

相关位置:

- `pix/analysis/repository.py:195-206`
- `pix/verification/engine.py:49-51`

风险: agent 在“npm 项目但未定义 test script”上运行自动验证时会执行不存在的命令并报失败，或触发额外安装/重复修复。而且仓库分析器与验证引擎各自维护一套测试命令检测逻辑，容易继续分叉。

### P1: 语义索引功能是未完成、未测试的半成品

本次审计的语义索引位于未提交工作树中，存在多个运行和工程问题:

- 每次 `index_repository()` 都 upsert 当前扫描结果，但从不删除已不存在文件/旧 chunk，重复索引后返回过期搜索结果。
  - `pix/indexing/indexer.py:69-78`
  - `pix/indexing/chroma_store.py:31-38`
- 一次把所有文件读进内存并一次性 embed 全量 chunk，大仓库可能超出 embedding API 批量限制、token 上限或内存；`chunk_document` 只按行分块，不按字符/token 限制，单行大文件可能产生超大 chunk。
- `_build_memory()` 使用 `chromadb.Client()` 的默认内存客户端且没有保存客户端引用或 close 路径；每次 run 都可能重建客户端。
  - `pix/agent/executor.py:393-410`
- 新代码没有测试覆盖：没有 `semantic_search`、`RepositoryIndexer`、Chroma store 或 embedding provider 的单元/集成测试。
- 新配置项没有同步到 `.env.example`、README 或 Docker；Docker 镜像也没有安装 `memory` extra，开启 `PIX_ENABLE_REPOSITORY_INDEX` 会失败。
- 当前工作树无法通过 lint/format/mypy，静态检查失败正是这些新模块引入的。

### P1: Git diff 的 path 参数存在 Git 选项注入窗口

`GitDiffTool` 把模型可控的 `path` 直接追加到 git 命令，且没有用 `--` 分隔 pathspec。例如 `--output=<外部路径>` 可被当作 git 选项，可能让 git 把 diff 写到工作区外；其它选项也可能改变命令语义。

相关位置:

- `pix/tools/git.py:71-80`

应改为 `git diff HEAD --no-color -- <path>`，或先验证 path 在仓库根内。

### P2: Session 状态没有落库为 running

`AgentExecutor.execute()` 创建 session 时状态是 `pending`，loop 内部把内存 `AgentState` 改成 `running`，但只有成功或异常时才会写回 DB。因此 sessions API/仪表盘在长时间 run 期间看不到 `running`，trace 页面也无法可靠判断 session 是否结束。

相关位置:

- `pix/agent/executor.py:119-127`
- `pix/agent/loop.py:65`
- `pix/agent/executor.py:443-453`

### P2: 通用工具超时配置未真正生效

`LoopOptions.tool_timeout` 只被保存，`_execute_tool()` 没有给 `Tool.execute()` 施加超时；MCP adapter 上的 `timeout_seconds` 也没有被基础类使用。当前只有 Shell/Git 各自内置超时，`PIX_TOOL_TIMEOUT` 的承诺名不副实。

相关位置:

- `pix/agent/loop.py:31-37`
- `pix/agent/loop.py:271-294`
- `pix/mcp/adapter.py:17-28`

### P2: 配置漂移和死配置

- `.env.example` 未包含新加的 `PIX_EMBEDDING_PROVIDER`、`PIX_VECTOR_STORE_PATH`、`PIX_CHROMA_COLLECTION`、`PIX_ENABLE_REPOSITORY_INDEX`。
- `PIX_MAX_VERIFICATION_RETRIES` 在 `Settings` 中定义但没有被 executor 使用；executor 用独立的 `auto_fix_attempts`。
- README/architecture docs 未记录当前工作树新增的 SSE、semantic_search 和 embedding provider，行为与文档会继续脱节。

## 测试覆盖缺口

- 没有测试: API SSE 路由、`AgentLoop` 的流式路径、`EventBus`、trace live stream、streaming 断开/取消、Git path 注入、自动验证失败后的 fix loop、session running 状态落库。
- 没有测试: 仓库语义索引、`semantic_search`、Chroma store、embedding provider、索引清理和旧 chunk。
- 实时 OpenAI provider 测试默认跳过；`scripts/e2e_openai.py` 也未纳入 CI。
- 前端没有测试；trace/run 页面没有覆盖流式接口，README roadmap 中的“Interactive web run streaming and live trace playback”仍是后端半成品。

## 结论

当前基线具备清晰的模块化基础，现有 Python 测试也全部通过。真正的问题集中在三个地方: API 与 Shell 的安全边界不足以承担“可远程触发编码 agent”；未提交的 SSE/语义索引功能只有实现、没有完整架构和测试；自动验证与 Git 工具存在会让 agent 产生错误结果或越界行为的具体缺陷。
