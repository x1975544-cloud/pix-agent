# ⚡ PiX Agent

**A Minimal, Extensible & Visual Autonomous Coding Agent Runtime**

一个从零实现的、可扩展、可观测、面向软件工程任务的 Coding Agent Runtime。

`Plan · Reason · Act · Observe · Verify · Commit`

## 项目定位

用户输入“分析这个项目，并帮我增加 JWT 登录功能”后，PiX 会真正执行：

1. 分析 Repository 结构与技术栈
2. 制定执行计划
3. 搜索并阅读相关代码
4. 修改多个文件
5. 运行测试
6. 根据失败结果继续修复
7. 查看 Git Diff
8. 生成 Commit Message 并提交
9. 返回完整执行报告

核心 Agent Runtime 不依赖 LangChain / LangGraph。Agent Loop、Tool Registry、
Context Manager、Memory、Trace 都由本项目自己实现。

## 技术栈

- Python 3.11+ / uv / FastAPI / Pydantic / SQLite / Typer / Rich
- OpenAI Responses API Provider 抽象
- ChromaDB 可选语义检索
- pytest / ruff / mypy
- Next.js / TypeScript / Tailwind CSS
- Docker / docker compose

## 快速开始

```bash
cp .env.example .env
# 在 .env 中设置 OPENAI_API_KEY
uv sync --extra dev
uv run pix "Explain this repository"
```

查看会话和 Trace：

```bash
uv run pix sessions
uv run pix trace <session-id>
```

启动 API 与 Web Dashboard：

```bash
uv run pix serve
cd web
npm install
npm run dev
```

## Demo

```bash
bash scripts/demo.sh
```

脚本会在 `.demo/hello-fastapi` 中准备一个干净的 Git 仓库，然后让 Agent 执行
“Add a health check endpoint”，包含分析、阅读、写文件、测试、验证和提交。

## 主要能力

- 自定义 Agent Loop：最大轮次、超时、重试、取消、错误恢复
- Tool System：统一接口 + JSON Schema
- 文件系统沙箱：路径逃逸、二进制文件、文件大小保护
- Shell 安全策略：禁止危险命令、命令链、管道和 Git 历史改写
- Git Tools：status / diff / log / branch / commit
- Repository Analyzer：自动识别语言、框架、入口、测试命令
- Context Engineering：优先级、Token 预算、旧消息压缩
- Memory：会话短期记忆 + SQLite 长期记忆 + 可选 Chroma 语义检索
- MCP：stdio JSON-RPC Client、Tool Adapter、Registry
- Skills：Markdown 技能加载与注入
- Trace：全事件持久化、Secret 脱敏、Token/Latency
- Evaluation：真实 Benchmark 任务与验证规则

## 测试

```bash
uv sync --extra dev
uv run ruff check pix tests
uv run mypy pix
uv run pytest
```

测试包含单元测试、工具边界测试、持久化与 Trace 测试、API 测试，以及使用
本地脚本化 Provider 的端到端集成测试；后者的测试不需要 API Key。

## 文档

- [Architecture](docs/architecture.md)
- [Agent Loop](docs/agent-loop.md)
- [Tool System](docs/tool-system.md)
- [Context Engineering](docs/context-engineering.md)
- [Memory](docs/memory.md)
- [MCP](docs/mcp.md)
- [Tracing](docs/tracing.md)
- [Security](docs/security.md)
- [Benchmark](docs/benchmark.md)

## 诚实性承诺

Benchmark 数据只来自真实运行，结果存放在 `benchmarks/results/`。没有真实结果
前，README 与 UI 不会发布伪造的通过率、延迟或 Token 数据。

## License

MIT
