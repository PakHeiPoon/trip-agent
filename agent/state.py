"""Shared graph state for the MustStart travel agent.

``messages`` uses LangGraph's ``add_messages`` reducer so each node only returns
its *new* messages while the checkpointer accumulates the full conversation per
``thread_id`` (= the chat session id).

This is intentionally small for 初赛. The 1+N supervisor branch will extend it
with fields like ``user_profile`` (小V记忆), ``current_task``, ``sub_results``.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """State threaded through the travel-planning graph.

    ``messages`` is the persisted user<->管家 history. ``plan`` / ``findings`` are
    transient per-turn scratch (overwritten each turn) for the 1+N supervisor:
    the supervisor picks ``plan`` (specialist ids), the experts node fills
    ``findings``, and the finalize node synthesizes them into one reply.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    # Optional imported community guide (MIP) used as planning context.
    context_guide: Optional[dict[str, Any]]
    # Specialists chosen by the supervisor for the current turn.
    plan: list[str]
    # Per-turn specialist outputs: [{"agent": id, "content": text}].
    findings: list[dict[str, Any]]
    # Per-turn tool-call trace for UI visualization (技术亮点①):
    # [{"agent": id, "tool": name, "args": {...}}]. Reset each turn.
    tool_calls: list[dict[str, Any]]
