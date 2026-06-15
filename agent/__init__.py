"""LangGraph agent core for MustStart (觅途).

This package replaces the single-shot LLM call in services/agent_service.py
with a LangGraph graph. For 初赛 it is a minimal single-node planner; it is the
foundation the 1+N supervisor (规划 / 比价 / 预订 / 应急 Agent) will be built on.

Public entry point:
    from agent.graph import graph        # the compiled LangGraph
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# Load Backend/.env so VIVO_* / LANGSMITH_* are available wherever the agent is
# imported (FastAPI startup, pytest, scripts) — independent of the legacy config.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
