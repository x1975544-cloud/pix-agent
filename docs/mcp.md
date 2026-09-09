# MCP

The MCP layer uses the standard stdio JSON-RPC transport. `StdioMCPClient`
performs initialize, `tools/list` and `tools/call`. `MCPToolAdapter` converts
each remote tool into a local `Tool`, and `MCPRegistry` attaches adapted tools
to the main `ToolRegistry` under names like `mcp__server__tool`.

Enable MCP in `.env`:

```dotenv
PIX_ENABLE_MCP=true
PIX_MCP_SERVERS=["filesystem|npx -y @modelcontextprotocol/server-filesystem ./"]
```

The implementation does not bundle third-party MCP servers; it expects a real
server command configured by the user. The first release focuses on the client
and adapter contract, not on shipping server implementations.
