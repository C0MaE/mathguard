# Setting up mathguard for an agent

The skill has two parts:

1. **The skill folder** (`skills/mathguard/` in the mathguard repository): tells
   the agent when and how to check maths.
2. **The mathguard tools**: the MCP server `mathguard-mcp`, or the
   `mathguard` command line. The skill works with either.

Requirements: Python 3.10 or newer. The commands below use
[uv](https://docs.astral.sh/uv/) (`uvx`), which downloads and caches mathguard
on first use, so nothing has to be installed by hand. Without uv, install once
with `pip install mathguard`
and use `mathguard-mcp` as the command instead of the `uvx ...` line.

The first start takes up to a minute while uv downloads SymPy; later starts
are fast.

## 1. Install the skill

With the cross-agent [`skills`](https://github.com/vercel-labs/skills) CLI:

```bash
npx skills add C0MaE/mathguard
```

Or copy the folder by hand into the skills directory of your agent:

```bash
git clone --depth 1 https://github.com/C0MaE/mathguard /tmp/mathguard
cp -r /tmp/mathguard/skills/mathguard <skills-dir>/
```

| Agent | Skills directory in a project |
|---|---|
| Claude Code | `.claude/skills/` (or `~/.claude/skills/` for all projects) |
| Cursor | `.cursor/skills/` |
| GitHub Copilot | `.github/skills/` |
| OpenAI Codex and other agents | `.agents/skills/` |

Most agents also have a personal skills folder for all projects, and many read
`.claude/skills/` as well; see the documentation of your agent.

Agents without skill support: paste the body of `SKILL.md` (or the output of
`mathguard prompt`) into the agent's rules or system prompt.

## 2. Connect the MCP server

The server runs locally over stdio. The command is always:

```bash
uvx mathguard mcp
```

### Claude Code

```bash
claude mcp add mathguard -- uvx mathguard mcp
```

Add `--scope user` to use it in every project, or `--scope project` to write it
to `.mcp.json` for your team.

### Claude Desktop, Cursor, Windsurf, Cline and other `mcpServers` clients

Add this to the client's MCP config (Claude Desktop:
`claude_desktop_config.json`; Cursor: `.cursor/mcp.json` or
`~/.cursor/mcp.json`; Windsurf: `~/.codeium/windsurf/mcp_config.json`):

```json
{
  "mcpServers": {
    "mathguard": {
      "command": "uvx",
      "args": ["mathguard", "mcp"]
    }
  }
}
```

### VS Code (GitHub Copilot)

`.vscode/mcp.json`:

```json
{
  "servers": {
    "mathguard": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mathguard", "mcp"]
    }
  }
}
```

### OpenAI Codex

```bash
codex mcp add mathguard -- uvx mathguard mcp
```

### No MCP support

The skill falls back to the command line. Make sure the agent may run
`uvx` (or `mathguard`, if installed with pip) in its shell.

## 3. Check that it works

Ask the agent: *"Use mathguard to check whether (x+1)^2 - (x-1)^2 = 4x + 2."*
It should report the claim as refuted with a counterexample. On the command
line:

```bash
uvx mathguard equal "(x+1)^2 - (x-1)^2" "4x + 2"
```
