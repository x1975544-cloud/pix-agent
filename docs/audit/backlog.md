# PiX Agent 基线待办

优先级: `P0` 必须先于开放网络使用；`P1` 应在功能合入前完成；`P2` 可以在后续迭代补齐。

## P0

### B001 为 API 增加认证和 workspace 限制

- 给 API 增加 token/API key 认证，至少保护 `/api/agent/*`、`/api/sessions/*`、`/api/traces/*`。
- 移除或限制客户端 `workspace`：推荐只允许预设的 workspace 根或其子目录，不允许调用方随意指向任意本机目录。
- 增加并发 run 上限、单 run 时长上限和客户端断开后的取消机制。
- 在 `docker-compose.yml` 中不要默认暴露无认证 API 到所有网卡。
- 新增认证与部署安全测试。

## P1

### B002 用真实隔离承载不可信代码

- 将 agent run 放入容器/VM 或至少独立的临时用户环境，限制网络和文件系统。
- `run_shell` 文档和 README 改为“进程工具”，不要称其为完整沙箱。
- 补充 Windows 危险命令覆盖，或者明确拒绝在非受控环境启用。
- Shell/verification 子进程只继承最小环境变量，而不只是删除三个 LLM key。

### B003 修复 live trace/stream 架构

- 引入 app 级或 executor 级 session event bus registry，让 `/api/traces/{id}/stream` 能订阅真实活跃 run。
- 如果 session 由普通 `/run` 启动，SSE 应至少周期性检查 DB 状态，而不是挂在一个空 bus 上。
- 客户端断开时取消 thread、清理 subscriber。
- 对 `/run/stream` 增加并发限制，避免每个请求一个不限生命周期 daemon thread。
- 不要逐 token 写 SQLite；流式 token 只发 bus，落库使用聚合事件或关闭 token 持久化。
- 为 SSE 路由和 trace stream 增加集成测试。

### B004 统一并修正测试命令检测

- 合并 `RepositoryAnalyzer` 与 `VerificationEngine` 的检测逻辑。
- 只有 `package.json` 存在 `scripts.test` 时才返回 `npm test`。
- 检查命令存在性，处理 Node/Python 混合仓库。
- 增加针对“无 test script 的 JS 项目”和“有 test script 的 JS 项目”的测试。

### B005 完成语义索引并补齐测试

- 每次索引前清理该 workspace/collection 的旧 chunk，或改为按 revision 重建。
- 限制文件大小、文件数量、chunk 字符/token 长度和 embedding batch 大小。
- 提供索引增量更新与失败恢复策略。
- 保存并关闭 Chroma/embedding client；Docker 安装 `memory` extra。
- 新增 `semantic_search`、indexer、stale chunk 清理、向量查询测试。
- 将配置同步到 `.env.example`、README；把 `REPOSITORY_INDEXED` 加入 canonical event。

### B006 修复 Git path 注入

- `git diff` 的 path filter 前加 `--`，并校验 path 在仓库内。
- 为 path 以 `--` 开头、包含 `..`、指向仓库外等场景增加工具测试。

## P2

### B007 落库 session running 状态

- loop 开始、fix 重跑、异常退出时同步 DB 状态。
- sessions API 与 UI 能显示进行中 run。

### B008 让通用 tool timeout 真正生效

- `Tool.execute()` 或 `_execute_tool()` 用线程/子进程/异步取消方式执行超时。
- 让 MCP adapter 的 `timeout_seconds` 接入基础执行路径。
- 增加超时行为测试。

### B009 收紧存储与 redaction

- 对 `SessionRecord.task`、`final_answer`、`error`、memory content 在落库前做与 tracer 相同的 redaction。
- 对写入 SQLite/Chroma 的 task summary 增加 secret 过滤测试。
- 检查 API 返回内容不暴露内部 secret。

### B010 清理配置与死代码

- 删除或实际使用 `PIX_MAX_VERIFICATION_RETRIES`。
- 同步 `.env.example`、README、architecture docs 与当前实现。
- 更新 canonical event 集合和 observability 文档。

### B011 工程与 CI

- 配置 GitHub Actions/Gitee Actions：pytest、ruff check、ruff format、mypy、npm tsc、npm build。
- 设置覆盖率阈值或至少生成报告。
- 给 web 增加最小自动化测试或 smoke test。
- 将实时 OpenAI smoke test 放入带 secret 的可选 job，不再默认跳过而没有任何运行路径。
- 修复当前工作树的 ruff B905、格式问题与 mypy 7 个错误。
