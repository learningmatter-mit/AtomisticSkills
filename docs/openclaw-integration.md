# OpenClaw Integration Guide

[OpenClaw](https://github.com/openclaw/openclaw) is an open-source local AI agent framework that can connect to any LLM backend (Claude, GPT, DeepSeek, etc.) and run autonomous workflows. This guide explains how to wire AtomisticSkills into an OpenClaw session so you can run research workflows over a TUI or Telegram bot.

---

## Prerequisites

- AtomisticSkills cloned and at least one conda environment installed (see `docs/setup.md`)
- OpenClaw installed (`npm install -g openclaw` or equivalent — see the OpenClaw docs)
- `mcporter` CLI installed (used by OpenClaw to manage MCP servers)

---

## 1. Launch OpenClaw in the AtomisticSkills directory

OpenClaw treats the directory you launch it in as its **workspace root**. For AtomisticSkills, launch from the repo:

```bash
cd ~/Documents/AtomisticSkills
openclaw
```

Or equivalently with the explicit flag:

```bash
openclaw --workspace ~/Documents/AtomisticSkills
```

For the TUI interface:

```bash
cd ~/Documents/AtomisticSkills
openclaw tui
```

> **Why this matters:** If you launch from the wrong directory (e.g., `~/.openclaw/workspace`), the agent won't have access to the `.agent/` folder, skills, or research outputs without extra manual setup.

---

## 2. Load Skills, Rules, and Workflows

Once inside the session, tell the agent to load the AtomisticSkills knowledge base into its context:

```
absorb all of /home/<you>/Documents/AtomisticSkills into context. most crucially is the files in /home/<you>/Documents/AtomisticSkills/.agent — target the skills/, workflows/, and rules/ folders within .agent/
```

The agent will read and internalize:
- `.agent/skills/` — all ~60 domain skills (melting point, docking, sorption, fine-tuning, etc.)
- `.agent/workflows/` — high-level research playbooks
- `.agent/rules/` — coding, research, and plotting standards

After this, the agent can discover and execute skills by reading their `SKILL.md` files and running the associated scripts directly.

---

## 3. Register MCP Servers via mcporter

AtomisticSkills' MCP servers (MatGL, MACE, FairChem, etc.) are defined in `mcp_config.json`. Register them with OpenClaw via mcporter:

```
load all mcp tools from the mcp_config.json file in /home/<you>/Documents/AtomisticSkills
```

The agent will use `mcporter config import` to copy the server definitions into `config/mcporter.json` inside the OpenClaw workspace. You can verify with:

```bash
mcporter config list
```

> **Note:** The correct filename is `mcp_config.json` — not `mcp_settings.json`.

After registration, MCP tools are called as `mcporter call <server> <tool>` from within the session.

---

## 4. Connect a Telegram Bot (Optional)

OpenClaw can expose your agent as a Telegram bot for remote interaction. To pair your Telegram account:

1. Message the bot on Telegram: `/start`
2. The bot will reply with your user ID and a pairing code, e.g.:
   ```
   Your Telegram user id: 1234567890
   Pairing code: 7CMR294B
   ```
3. On the machine running OpenClaw, approve the pairing:
   ```bash
   openclaw pairing approve telegram 7CMR294B
   ```

Once paired, you can message the bot to check on long-running jobs, request status updates, or give new instructions — all while a TUI session runs on the machine.

> **TUI and Telegram are separate sessions** — they do not share conversation context. Both have access to the same workspace files and MCP servers, but each has its own message history.

---

## 5. Configure Web Search (Optional)

OpenClaw's web search tool requires a Brave Search API key:

```bash
openclaw configure --section web
# enter your BRAVE_API_KEY when prompted
```

Or set it as an environment variable before launching:

```bash
export BRAVE_API_KEY=your_key_here
openclaw
```

Without this, web search calls will return a `missing_brave_api_key` error.

---

## 6. Running Research Workflows

Once skills and MCP servers are loaded, the agent uses them autonomously. Example prompts that work well:

```
Query 1000 bulk modulus data from Materials Project and train a property predictor using MatGL.
don't stop. don't ask me for questions.
```

```
Calculate the melting point of Ag using the solid-liquid coexistence method.
```

The agent will:
1. Discover the relevant skill by reading `.agent/skills/*/SKILL.md`
2. Run scripts via the appropriate conda env (e.g., `micromamba run -n mace-agent python ...`)
3. Call MCP tools via `mcporter call <server> <tool> <args>`
4. Save outputs to `research/<date>_<description>/`

Background processes are tracked by named sessions (e.g., `lucky-meadow`, `tidal-lagoon`). These continue running even when you're not actively messaging.

---

## 7. Sending Files via Telegram

The agent can attach files (PDFs, images, etc.) directly to Telegram messages. Simply ask:

```
send the bulk modulus report pdf to me on telegram
```

You may occasionally see a media path error in the agent's tool output, but the file typically sends successfully regardless.

---

## 8. Session Persistence

OpenClaw sessions persist as long as you are actively using the TUI or Telegram interface. History will carry over between messages within an ongoing session. Sessions do reset after extended periods of inactivity, at which point the agent will have no memory of prior work.

If you want to be safe across longer gaps, write key milestones into a memory file in the workspace:

```
write a MEMORY.md in the workspace summarizing what we accomplished today
```

On resuming after a reset, point the agent to that file:
```
read ~/.openclaw/workspace/MEMORY.md and resume from where we left off
```

---

## Quick Reference

| Task | Command / Prompt |
|---|---|
| Launch in AtomisticSkills dir | `cd ~/Documents/AtomisticSkills && openclaw tui` |
| Load skills + rules | `absorb all of .../AtomisticSkills ... target skills/, workflows/, rules/` |
| Register MCP servers | `load all mcp tools from mcp_config.json` |
| Verify MCP servers | `mcporter config list` |
| Pair Telegram | `openclaw pairing approve telegram <CODE>` |
| Enable web search | `openclaw configure --section web` |
| Send file via Telegram | Copy to `~/.openclaw/workspace/`, then ask agent to send |
| Check OpenClaw version | `openclaw --version` |
