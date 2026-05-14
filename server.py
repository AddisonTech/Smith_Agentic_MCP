"""
server.py
MCP server for Smith_Agentic.

Exposes Smith_Agentic crew runs as MCP tools for Claude Code and Claude Desktop.
Communicates with Smith_Agentic's FastAPI server over HTTP - no direct dependency
on crewai, Ollama, or any other Smith_Agentic internals.

Prerequisites:
    Smith_Agentic must be running:
        cd Smith_Agentic
        python ui/server.py

Setup - Claude Code:
    claude mcp add smith_agentic python C:/path/to/Smith_Agentic_MCP/server.py

Setup - Claude Desktop (claude_desktop_config.json):
    {
      "mcpServers": {
        "smith_agentic": {
          "command": "python",
          "args": ["C:/path/to/Smith_Agentic_MCP/server.py"]
        }
      }
    }

Configuration:
    SMITH_AGENTIC_URL   Base URL for the Smith_Agentic API server.
                        Default: http://localhost:8765
"""
from __future__ import annotations

import os

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("SMITH_AGENTIC_URL", "http://localhost:8765").rstrip("/")

mcp = FastMCP("SmithAgentic")

_NOT_RUNNING = (
    f"Smith_Agentic is not running at {BASE_URL}.\n"
    "Start it with:\n"
    "    cd Smith_Agentic\n"
    "    python ui/server.py"
)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get(path: str, timeout: float = 10.0) -> dict:
    try:
        r = httpx.get(f"{BASE_URL}{path}", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        raise RuntimeError(_NOT_RUNNING)
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"HTTP {e.response.status_code}: {e.response.text}")


def _post(path: str, body: dict, timeout: float = 10.0) -> dict:
    try:
        r = httpx.post(f"{BASE_URL}{path}", json=body, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        raise RuntimeError(_NOT_RUNNING)
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"HTTP {e.response.status_code}: {e.response.text}")


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def check_smith_agentic() -> str:
    """
    Check whether Smith_Agentic is running and Ollama is reachable.
    Call this before starting a crew run to confirm the system is ready.
    """
    try:
        data = _get("/api/status")
    except RuntimeError as e:
        return str(e)
    ollama = "online" if data.get("ollama") else "offline - run `ollama serve`"
    return f"Smith_Agentic: online at {BASE_URL}\nOllama: {ollama}"


@mcp.tool()
def list_crews() -> str:
    """
    List available Smith_Agentic crews and the default Ollama model each uses.
    Call this before run_crew() to see what is available.
    """
    try:
        data = _get("/api/crew-defaults")
    except RuntimeError as e:
        return str(e)
    descriptions = {
        "default": "General crew: plan, research, build, critique.",
        "plc":     "Rockwell/Allen-Bradley Logix PLC development.",
        "react":   "Industrial React/MUI HMI development.",
        "vision":  "Vision_Inspect defect analysis (requires Vision_Inspect on port 8000).",
        "safety":  "QA, security, and deployment validation. Reads existing outputs/.",
        "ops":     "Documentation, memory consolidation, and telemetry. Reads existing outputs/.",
    }
    lines = ["Available crews (name → default model):\n"]
    for crew, model in data.items():
        desc = descriptions.get(crew, "")
        lines.append(f"  {crew:<10} {model:<25} {desc}")
    lines.append("\nPass a crew name to run_crew() to start a run.")
    return "\n".join(lines)


@mcp.tool()
def list_models() -> str:
    """List Ollama models currently installed and available for crew runs."""
    try:
        data = _get("/api/models")
    except RuntimeError as e:
        return str(e)
    models = data.get("models", [])
    if not models:
        return "No Ollama models installed. Run `ollama pull qwen2.5:7b`."
    return "Installed Ollama models:\n" + "\n".join(f"  {m}" for m in models)


@mcp.tool()
def run_crew(
    goal: str,
    crew: str = "default",
    model: str | None = None,
    chain: bool = False,
) -> str:
    """
    Start a Smith_Agentic crew run. The run executes in the background on the
    Smith_Agentic server - this call returns immediately with a run_id.

    Args:
        goal:  What you want the crew to accomplish.
        crew:  Which crew to run. Call list_crews() to see options. Default: 'default'.
        model: Ollama model override for this run (e.g. 'qwen2.5:14b').
               Leave empty to use the crew's configured default.
        chain: Set True to automatically run the safety crew then the ops crew
               after the primary crew finishes.

    Returns a run_id string. Call get_run_status(run_id) every 30-60 seconds
    to poll for progress. Crew runs typically take several minutes.
    """
    body: dict = {"goal": goal, "crew": crew, "chain": chain}
    if model:
        body["model"] = model
    try:
        data = _post("/api/run", body)
    except RuntimeError as e:
        return str(e)
    if "error" in data:
        return f"Error: {data['error']}"
    run_id = data["run_id"]
    return (
        f"Run started.\n"
        f"  run_id : {run_id}\n"
        f"  crew   : {crew}\n"
        f"  chain  : {chain}\n"
        f"  goal   : {goal}\n\n"
        f"Call get_run_status('{run_id}') to check progress.\n"
        f"Crew runs take several minutes - poll every 30-60 seconds."
    )


@mcp.tool()
def get_run_status(run_id: str) -> str:
    """
    Get the current status and recent output of a crew run.

    Args:
        run_id: The ID returned by run_crew().

    Status values:
        starting   - crew is initializing
        running    - agents are actively working
        completed  - run finished successfully
        error      - run failed (check output for details)

    When status is 'completed', call list_output_files() then read_output_file()
    to access the results.
    """
    try:
        data = _get(f"/api/run/{run_id}")
    except RuntimeError as e:
        return str(e)
    if "error" in data:
        return f"Run '{run_id}' not found."

    status = data["status"]
    output = data.get("output", [])
    recent = output[-20:]
    files  = data.get("files", [])

    lines = [
        f"status : {status}",
        f"lines  : {len(output)} total (showing last {len(recent)})",
        "",
    ]
    lines.extend(recent)
    if files:
        lines.append(f"\noutput files: {', '.join(files)}")
    if status == "completed":
        lines.append("\nDone. Use list_output_files() and read_output_file() to read results.")
    elif status == "running":
        lines.append("\nStill running. Poll again in 30-60 seconds.")
    elif status == "error":
        lines.append("\nRun failed. Check output above for the error.")
    return "\n".join(lines)


@mcp.tool()
def list_output_files() -> str:
    """
    List all files in Smith_Agentic's outputs/ directory, including subdirectories.
    Call this after a run completes to see what was produced.
    """
    try:
        data = _get("/api/outputs")
    except RuntimeError as e:
        return str(e)
    files = data.get("files", [])
    if not files:
        return "outputs/ is empty. Run a crew first."
    lines = [f"Files in outputs/ ({len(files)} total):"]
    for f in files:
        kb = f["size"] / 1024
        lines.append(f"  {f['path']:<45} {kb:.1f} KB")
    lines.append("\nUse read_output_file(path) to read any of these.")
    return "\n".join(lines)


@mcp.tool()
def read_output_file(path: str) -> str:
    """
    Read a file from Smith_Agentic's outputs/ directory.

    Args:
        path: Relative path to the file (e.g. 'deliverable.md',
              'qa_report.md', 'docs/deliverable_docs.md').
              Call list_output_files() to see what is available.
    """
    try:
        r = httpx.get(f"{BASE_URL}/api/outputs/{path}", timeout=15.0)
        if r.status_code == 403:
            return "Access denied."
        if r.status_code == 404:
            return f"'{path}' not found. Call list_output_files() to see what is available."
        r.raise_for_status()
        content = r.text
        if len(content) > 20_000:
            content = content[:20_000] + "\n\n... (truncated at 20,000 chars)"
        return f"--- {path} ---\n{content}"
    except httpx.ConnectError:
        return _NOT_RUNNING


# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
