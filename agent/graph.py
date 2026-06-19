"""1+N multi-Agent travel graph (觅途).

A 总控 supervisor routes each user turn to a subset of specialist Agents
(规划 / 比价 / 应急), the experts contribute their domain opinions, and a
finalize node (the "MustStart旅行管家" persona) synthesizes one coherent reply
plus an optional MIP guide JSON.

    START → supervisor ──(no specialist)──→ finalize → END
                       └──(specialists)───→ experts → finalize → END

Conversation history (user <-> 管家) is persisted per session via the
checkpointer; specialist chatter stays transient (state.findings), so history
stays clean.

Tools are mocked for 初赛 — specialists reason from the conversation. The
``feat/agent-tools`` branch wires real vivo POI / weather / OCR tools.
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Literal

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from agent.llm import get_llm
from agent.state import AgentState
from agent.tools import SPECIALIST_TOOLS
from prompts.agents_zh import (
    SPECIALIST_PROMPTS,
    SUPERVISOR_PROMPT,
    build_expert_context,
    build_finalizer_system,
)

SPECIALISTS = ("planner", "pricing", "contingency")


class RoutePlan(BaseModel):
    """Supervisor's routing decision for one turn."""

    agents: list[Literal["planner", "pricing", "contingency"]] = Field(
        default_factory=list,
        description="需要咨询的专家 id，按顺序；闲聊/纯澄清类问题留空。",
    )
    reason: str = Field(default="", description="一句话路由理由。")


def _text(message: Any) -> str:
    """Extract plain text from a message (content may be str or content blocks)."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return str(content)


def _supervisor(state: AgentState) -> dict:
    """总控：decide which specialists (if any) to consult this turn."""
    router = get_llm(reasoning_effort="minimal").with_structured_output(RoutePlan)
    plan: RoutePlan = router.invoke(
        [SystemMessage(content=SUPERVISOR_PROMPT), *state["messages"]],
        config={"run_name": "supervisor"},
    )
    chosen = [a for a in plan.agents if a in SPECIALISTS]
    return {"plan": chosen, "findings": [], "tool_calls": []}


def _route(state: AgentState) -> Literal["experts", "finalize"]:
    return "experts" if state.get("plan") else "finalize"


def _extract_tool_calls(name: str, messages: list) -> list[dict[str, Any]]:
    """Pull the tools a specialist actually invoked (for UI visualization 技术亮点①)."""
    calls: list[dict[str, Any]] = []
    for m in messages:
        for tc in getattr(m, "tool_calls", None) or []:
            calls.append(
                {"agent": name, "tool": tc.get("name", ""), "args": tc.get("args", {})}
            )
    return calls


def _tool_outputs(messages: list, tool_name: str) -> list[str]:
    """Raw output strings of a given tool from a ReAct agent's message list.

    The react agent's *final* message often summarizes tool output away, so to
    keep jump_ota's real deep-links we read them from the ToolMessage directly.
    """
    return [
        _text(m)
        for m in messages
        if isinstance(m, ToolMessage) and getattr(m, "name", "") == tool_name
    ]


def _run_specialist(
    name: str, history: list, ask: HumanMessage
) -> tuple[str, list[dict[str, Any]]]:
    """Run one specialist → (reply_text, tool_calls). Tool-enabled ones run as a
    ReAct agent (vivo POI / weather / traffic / booking) and we record which tools
    fired; tool-less ones are a plain LLM call (no tool calls)."""
    system = SPECIALIST_PROMPTS[name]
    tools = SPECIALIST_TOOLS.get(name, [])
    try:
        if tools:
            sub = create_react_agent(get_llm(reasoning_effort="minimal"), tools, prompt=system)
            out = sub.invoke(
                {"messages": [*history, ask]},
                # cap the tool loop so a chatty react agent can't run away
                config={"run_name": f"expert:{name}", "recursion_limit": 8},
            )
            final = _text(out["messages"][-1])
            # react agent 收尾常把 jump_ota 的链接 summarize 掉 → 把真实深链原样并回 finding，
            # 这样 _finalize 能确定性地把它们附给用户。
            for booking in _tool_outputs(out["messages"], "jump_ota"):
                if booking and booking not in final:
                    final = f"{final}\n\n{booking}"
            return final, _extract_tool_calls(name, out["messages"])

        resp = get_llm(reasoning_effort="minimal").invoke(
            [SystemMessage(content=system), *history, ask],
            config={"run_name": f"expert:{name}"},
        )
        return _text(resp), []
    except Exception as exc:  # noqa: BLE001 - degrade gracefully so finalize still answers
        return f"（{name} 专家本轮未能给出建议：{type(exc).__name__}）", []


def _experts(state: AgentState) -> dict:
    """专家 Agent：each chosen specialist contributes a domain opinion."""
    history = list(state["messages"])
    ask = HumanMessage(
        content="总控已将本轮任务指派给你。请基于以上对话，只就你负责的领域给出简洁、可执行的专业意见。"
    )
    # Sequential on purpose: vivo's free competition tier throttles concurrent
    # calls, so parallel experts end up SLOWER. Speed comes from reasoning_effort
    # "minimal" on routing/experts instead.
    findings: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    for name in state.get("plan", []):
        content, calls = _run_specialist(name, history, ask)
        findings.append({"agent": name, "content": content})
        tool_calls.extend(calls)
    return {"findings": findings, "tool_calls": tool_calls}


_BOOKING_LINK_RE = re.compile(
    r"\[[^\]]+\]\((https?://[^)\s]*(?:ctrip\.com|fliggy\.com|12306\.cn)[^)\s]*)\)"
)


def _extract_booking_links(findings: list[dict[str, Any]]) -> list[str]:
    """Pull the REAL jump_ota markdown booking links (携程/飞猪/12306) out of the
    specialists' findings, deduped by URL — so we append the actual deep links
    deterministically instead of trusting the finalize LLM (which sometimes
    rewrites them to a homepage or fabricates a fake short link)."""
    links: list[str] = []
    seen: set[str] = set()
    for f in findings:
        for m in _BOOKING_LINK_RE.finditer(f.get("content", "") or ""):
            if m.group(1) not in seen:
                seen.add(m.group(1))
                links.append(m.group(0))
    return links


def _finalize(state: AgentState) -> dict:
    """汇总：synthesize specialist findings into one 管家 reply (+ optional guide JSON)."""
    messages = [SystemMessage(content=build_finalizer_system()), *state["messages"]]
    findings = state.get("findings") or []
    if findings:
        messages.append(SystemMessage(content=build_expert_context(findings)))

    resp = get_llm().invoke(messages, config={"run_name": "finalizer"})
    text = _text(resp)

    # 确定性补真实预订深链：以 jump_ota 在 findings 里给的为准，append 进回复
    # （只补回复里还没出现的，避免重复；这样杜绝 LLM 改写成首页或编造假链接）。
    booking = _extract_booking_links(findings)
    if booking:
        missing = [b for b in booking if b.split("](", 1)[-1].rstrip(")") not in text]
        if missing:
            text = (
                text.rstrip()
                + "\n\n**🔗 一键预订（出发地→目的地 直达）**\n"
                + "\n".join(f"- {b}" for b in missing)
            )
            resp = AIMessage(content=text)
    return {"messages": [resp]}


def build_graph(checkpointer=None):
    """Compile the 1+N supervisor graph."""
    builder = StateGraph(AgentState)
    builder.add_node("supervisor", _supervisor)
    builder.add_node("experts", _experts)
    builder.add_node("finalize", _finalize)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor", _route, {"experts": "experts", "finalize": "finalize"}
    )
    builder.add_edge("experts", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)


def _make_checkpointer() -> SqliteSaver:
    """Durable SQLite checkpointer for the FastAPI path.

    Per-thread (= session_id) conversation history persists across restarts /
    redeploys. In Docker the DB file must sit on a mounted volume (see deploy.sh:
    `-v .../data:/app/data`) so it survives container recreation.
    """
    db_path = Path(os.getenv("CHECKPOINT_DB", "data/checkpoints.sqlite"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrency under the threadpool
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


# Standalone use (FastAPI /api/chat): durable per-session persistence.
graph = build_graph(checkpointer=_make_checkpointer())


def make_graph():
    """Factory for the LangGraph Server / Studio (langgraph.json).

    The server provides its own persistence layer, so the graph must be
    compiled WITHOUT a custom checkpointer here.
    """
    return build_graph(checkpointer=None)
