"""LangSmith tracing helper.

LangSmith auto-instruments LangChain/LangGraph when these env vars are set
(no code wiring needed):

    LANGSMITH_TRACING=true
    LANGSMITH_API_KEY=ls-...
    LANGSMITH_PROJECT=muststart-agent

This module just reports whether tracing is active, so startup logs make it
obvious when traces will (not) show up in the LangSmith dashboard.
"""

from __future__ import annotations

import os


def tracing_enabled() -> bool:
    """True when LangSmith env vars are present and tracing is turned on."""
    flag = os.getenv("LANGSMITH_TRACING", "").strip().lower() in {"true", "1", "yes"}
    return flag and bool(os.getenv("LANGSMITH_API_KEY"))


def tracing_status() -> str:
    """One-line human-readable status for startup logs."""
    if tracing_enabled():
        project = os.getenv("LANGSMITH_PROJECT", "default")
        return f"[tracing] LangSmith ON  -> project={project}"
    return "[tracing] LangSmith OFF (set LANGSMITH_TRACING=true + LANGSMITH_API_KEY to enable)"
