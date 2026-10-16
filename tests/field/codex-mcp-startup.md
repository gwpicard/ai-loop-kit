# Codex MCP start-up check

On 16 October 2026, Codex CLI 0.162.1 completed two pairs of start-up runs
on macOS against the installed user plugin configuration. The changed
launcher was commit `1a7756c`. Both pairs used the real Codex executable.

## Method

Call `agents.start_session` with backend `codex`, role `reviewer` and the
prompt `Reply STARTUP_OK without using tools.` For the before run, remove
only `--disable plugins --disable apps` from the launch arguments. Keep
`--ignore-user-config`, `--ephemeral` and the kit's sandbox settings in both
runs. Leave the user's config and installed plugins unchanged.

Apply the same diagnostic overrides to both runs:

- `--no-daemon` starts a separate client.
- `--disable hooks` prevents user hooks from running during the check.
- A temporary `model_provider` points to a Python standard-library HTTP
  server on `127.0.0.1`, with `wire_api="responses"` and retries disabled.
- The local server returns Responses streaming events ending in the
  assistant message `STARTUP_OK` and `response.completed`. It makes no
  upstream request. The usage counts below come from this fixture.
- Close standard input, capture standard output and standard error together,
  and allow 50 seconds for each run to finish.

The outer sandbox prevented Codex's app-server client from initialising.
The live runs below used an approved execution outside that outer sandbox;
the kit's child sandbox arguments stayed in place. Neither run timed out.
No paid model request was made.

## First pair: completed runs with the start-up error

The original launch exited with status 0 and emitted this error from the
installed Netlify MCP server:

```text
2026-10-16T18:36:17.906947Z ERROR rmcp::transport::worker: worker quit with fatal: Transport channel closed, when AuthRequired(AuthRequiredError { www_authenticate_header: "Bearer realm=\"MCP Server\", resource_metadata=\"https://netlify-mcp.netlify.app/.well-known/oauth-protected-resource/mcp\"" })
```

Both the original and changed launches emitted these completion events:

```json
{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"STARTUP_OK"}}
{"type":"turn.completed","usage":{"input_tokens":1,"cached_input_tokens":0,"cache_write_input_tokens":0,"output_tokens":1,"reasoning_output_tokens":0}}
```

The changed launch exited with status 0. Its captured output contained no
MCP lines and no `AuthRequired` error. Both runs also reported the same
model-metadata fallback warning for the local fixture's model name.

## Second pair: inspect the actual model request

A second pair also recorded the tool names received by the local HTTP
server. This checks tool exposure even when a server produces no error.
Both runs exited with status 0, returned `STARTUP_OK` and emitted
`turn.completed`.

| Observation | Original launch | Changed launch |
| --- | --- | --- |
| Tool names containing `mcp` | 15 | 0 |
| Of those, `mcp__codex_apps__` tools | 12 | 0 |
| MCP lines in captured output | 0 | 0 |
| `AuthRequired` errors | 0 | 0 |

The original request included `mcp__codex_apps__netlify`,
`mcp__codex_apps__figma` and `mcp__codex_apps__github`. The changed request
contained no MCP tools. The original launch's authentication error did not
recur in this pair, but unrelated tools still reached its model request.

These runs provide live evidence for the attended reviewer path. The
argument regression in `test_agents.py` covers the shared launcher across
builders, reviewers, critics and probes in both modes. This check does not
claim to exercise every role or every possible user configuration live.
