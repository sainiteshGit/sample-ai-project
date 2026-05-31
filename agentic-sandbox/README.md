# Agentic Sandbox — Crawl

Claude/Codex-style live code-execution UI in your terminal. Built on:

- **Microsoft Agent Framework** (Python) — agent runtime
- **Azure OpenAI Responses API** — model + hosted Python sandbox
- **`HostedCodeInterpreterTool`** — MAF's built-in code interpreter (server-side, no infra)
- **`rich`** — terminal panels for live step rendering

## Phase

This is the **Crawl** phase: single-turn CLI, provider-hosted sandbox, no infra to manage.

Next phases (planned):
- **Walk** — multi-turn chat + persistent session + Chainlit web UI
- **Run** — bring-your-own sandbox (Azure Container Apps Dynamic Sessions) for full data residency and custom container images

## Setup

```bash
cd agentic-sandbox
cp .env.template .env   # already filled in for local dev
pip install -r requirements.txt
```

## Run

```bash
python cli.py "Compute the 50th Fibonacci number"
python cli.py "Plot a sine wave from 0 to 2π and save it as sine.png"
python cli.py "Analyze this CSV inline: name,age\nAlice,30\nBob,25 — give me the mean age"
```

Each model step renders as a Claude-style panel:

- 🟦 **You** — your prompt
- 🟩 **Assistant** — model reasoning text
- 🟨 **⚙ Running Python (sandbox)** — syntax-highlighted code being executed
- 🟪 **✓ Result** — sandbox stdout / return value

## Why `HostedCodeInterpreterTool`?

MAF ships several built-in tool types ([docs](https://learn.microsoft.com/en-us/agent-framework/agents/tools/)). The Code Interpreter is **provider-hosted** — the sandbox runs in Azure OpenAI's tenant, no Docker / Firecracker / Container Apps to set up. You get the Claude/Codex experience in ~150 lines.

Trade-off: code runs in Microsoft's tenant, not yours. For data-residency / custom-libs / on-prem requirements, swap the tool out for an ACA Dynamic Sessions function tool in the Run phase.
