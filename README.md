# Smith_Agentic_MCP

MCP server for [Smith_Agentic](https://github.com/AddisonTech/Smith_Agentic). Exposes Smith_Agentic crew runs as tools for Claude Code and Claude Desktop via the Model Context Protocol.

Communicates with Smith_Agentic's FastAPI server over HTTP. No dependency on crewai, Ollama, or any Smith_Agentic internals - just two packages: `mcp` and `httpx`.

---

## Prerequisites

**Smith_Agentic must be running** before this MCP server can do anything:

```bash
cd Smith_Agentic
python ui/server.py
# Smith_Agentic API now available at http://localhost:8765
```

---

## Installation

```bash
git clone https://github.com/AddisonTech/Smith_Agentic_MCP.git
cd Smith_Agentic_MCP
pip install -r requirements.txt
```

---

## Setup

### Claude Code

```bash
claude mcp add smith_agentic python C:/path/to/Smith_Agentic_MCP/server.py
```

Verify it loaded:
```
/mcp
```

### Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "smith_agentic": {
      "command": "python",
      "args": ["C:/path/to/Smith_Agentic_MCP/server.py"]
    }
  }
}
```

Restart Claude Desktop after saving.

> **Virtual environment**: If your dependencies are in a `.venv`, point at that Python directly:
> ```json
> "command": "C:/path/to/Smith_Agentic_MCP/.venv/Scripts/python.exe"
> ```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `SMITH_AGENTIC_URL` | `http://localhost:8765` | Base URL for the Smith_Agentic API server |

Set it if Smith_Agentic is running on a non-default port or a remote host:

```bash
# Claude Code - set in your shell profile or pass inline
SMITH_AGENTIC_URL=http://192.168.1.10:8765 python server.py
```

Or in Claude Desktop config:
```json
{
  "mcpServers": {
    "smith_agentic": {
      "command": "python",
      "args": ["C:/path/to/Smith_Agentic_MCP/server.py"],
      "env": {
        "SMITH_AGENTIC_URL": "http://192.168.1.10:8765"
      }
    }
  }
}
```

---

## Available Tools

| Tool | What it does |
|---|---|
| `check_smith_agentic` | Verify Smith_Agentic is running and Ollama is reachable |
| `list_crews` | Show available crews and their default models |
| `list_models` | Show installed Ollama models |
| `run_crew(goal, crew, model, chain)` | Start a crew run, returns run_id immediately |
| `get_run_status(run_id)` | Poll a run for status and recent output |
| `list_output_files` | List all files in Smith_Agentic's outputs/ |
| `read_output_file(path)` | Read a file from outputs/ (supports subdirectory paths) |

---

## Usage

Once connected, you can ask Claude naturally:

> "Check if Smith_Agentic is running, then start a default crew run: write a Python class for managing a connection pool with retry logic."

Claude will:
1. Call `check_smith_agentic` to confirm the system is ready
2. Call `run_crew` to start the run and get a run_id
3. Call `get_run_status` every 30-60 seconds until status is `completed`
4. Call `list_output_files` to see what was produced
5. Call `read_output_file` to show you the result

### Crew options

| Crew | Use for |
|---|---|
| `default` | General software tasks - specs, code, analysis |
| `plc` | Rockwell/Allen-Bradley Logix PLC programs |
| `react` | Industrial React/MUI HMI components |
| `vision` | Vision_Inspect defect analysis (requires Vision_Inspect on port 8000) |
| `safety` | Validate an existing deliverable - QA, security, deploy checks |
| `ops` | Generate docs and telemetry for an existing deliverable |

### Chain flag

Pass `chain=True` to automatically run the safety and ops crews after the primary crew finishes:

> "Run a default crew on this goal with chain=True: build a Python rate limiter."

The run will execute: `default` → `safety` → `ops`, producing the full set of outputs including QA report, security report, deploy verdict, docs, and telemetry.

---

## Project structure

```
Smith_Agentic_MCP/
├── server.py          # MCP server - all tools defined here
├── requirements.txt   # mcp + httpx only
└── README.md
```
