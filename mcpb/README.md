# mathguard desktop extension

`manifest.json` and friends for an [MCP Bundle](https://github.com/modelcontextprotocol/mcpb)
(`.mcpb`), which installs the mathguard MCP server in Claude Desktop with one click.
The bundle uses the `uv` runtime, so it stays small and installs `mathguard` from PyPI.

Build it with

```bash
npx @anthropic-ai/mcpb pack mcpb mathguard.mcpb
```

The publish workflow builds it for every release and attaches it to the GitHub release.
The versions in `manifest.json` and `pyproject.toml` must match the package version
(`tests/test_mcpb.py` checks that).
