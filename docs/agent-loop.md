# Agent Loop

`AgentLoop.run(state)` implements the core loop:

```text
while not finished and iteration < max_iterations:
    context = context_manager.build(state)
    response = provider.generate(context, registry.schemas())
    if response.tool_calls:
        for call in response.tool_calls:
            observation = registry.get(call.name).execute(call.arguments)
            state.add_tool_observation(observation)
    else:
        state.final_answer = response.content
        return
```

The loop also supports:

- max iteration and per-tool/provider timeouts;
- provider retries with backoff for `ProviderError`;
- cancellation through a `threading.Event`;
- unknown tool calls as failed observations the model can recover from;
- event callbacks for context builds, LLM calls and tool results.

After a successful loop, `AgentExecutor` runs the detected verification command
and, if it fails, starts bounded fix passes with the failure fed back to the
model. No commit is forced by the runtime; the model is instructed to commit
only after green checks.
