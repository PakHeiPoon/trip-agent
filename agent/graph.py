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

from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
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
    router = get_llm(reasoning_effort="low").with_structured_output(RoutePlan)
    plan: RoutePlan = router.invoke(
        [SystemMessage(content=SUPERVISOR_PROMPT), *state["messages"]],
        config={"run_name": "supervisor"},
    )
    chosen = [a for a in plan.agents if a in SPECIALISTS]
    return {"plan": chosen, "findings": []}


def _route(state: AgentState) -> Literal["experts", "finalize"]:
    return "experts" if state.get("plan") else "finalize"


def _run_specialist(name: str, history: list, ask: HumanMessage) -> str:
    """Run one specialist. Tool-enabled ones run as a ReAct agent (can call vivo
    POI / weather); tool-less ones are a plain LLM call."""
    system = SPECIALIST_PROMPTS[name]
    tools = SPECIALIST_TOOLS.get(name, [])
    if tools:
        sub = create_react_agent(get_llm(reasoning_effort="low"), tools, prompt=system)
        out = sub.invoke(
            {"messages": [*history, ask]}, config={"run_name": f"expert:{name}"}
        )
        return _text(out["messages"][-1])

    resp = get_llm(reasoning_effort="low").invoke(
        [SystemMessage(content=system), *history, ask],
        config={"run_name": f"expert:{name}"},
    )
    return _text(resp)


def _experts(state: AgentState) -> dict:
    """专家 Agent：each chosen specialist contributes a domain opinion."""
    history = list(state["messages"])
    ask = HumanMessage(
        content="总控已将本轮任务指派给你。请基于以上对话，只就你负责的领域给出简洁、可执行的专业意见。"
    )
    findings: list[dict[str, Any]] = [
        {"agent": name, "content": _run_specialist(name, history, ask)}
        for name in state.get("plan", [])
    ]
    return {"findings": findings}


def _finalize(state: AgentState) -> dict:
    """汇总：synthesize specialist findings into one 管家 reply (+ optional guide JSON)."""
    messages = [SystemMessage(content=build_finalizer_system()), *state["messages"]]
    findings = state.get("findings") or []
    if findings:
        messages.append(SystemMessage(content=build_expert_context(findings)))

    resp = get_llm().invoke(messages, config={"run_name": "finalizer"})
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


# Standalone use (FastAPI /api/chat): in-memory persistence.
graph = build_graph(checkpointer=MemorySaver())


def make_graph():
    """Factory for the LangGraph Server / Studio (langgraph.json).

    The server provides its own persistence layer, so the graph must be
    compiled WITHOUT a custom checkpointer here.
    """
    return build_graph(checkpointer=None)
