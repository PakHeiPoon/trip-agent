"""Durable sessions: SqliteSaver keeps thread history across a 'restart'."""

from __future__ import annotations

from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

import agent.graph as g


class _FakeRouter:
    def __init__(self, schema):
        self.schema = schema

    def invoke(self, messages, config=None):
        return self.schema(agents=[], reason="t")  # no specialists -> straight to finalize


class _FakeLLM:
    def with_structured_output(self, schema):
        return _FakeRouter(schema)

    def invoke(self, messages, config=None):
        return AIMessage(content="管家回复")


def test_session_persists_across_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    cfg = {"configurable": {"thread_id": "t1"}}

    with patch("agent.graph.get_llm", lambda **_: _FakeLLM()):
        graph1 = g.build_graph(checkpointer=g._make_checkpointer())
        graph1.invoke({"messages": [HumanMessage(content="第一句")]}, config=cfg)
        graph1.invoke({"messages": [HumanMessage(content="第二句")]}, config=cfg)
        assert len(graph1.get_state(cfg).values["messages"]) == 4

    # Simulate a process/container restart: a brand-new checkpointer on the SAME db file.
    graph2 = g.build_graph(checkpointer=g._make_checkpointer())
    restored = graph2.get_state(cfg).values.get("messages", [])
    assert len(restored) == 4
    assert restored[0].content == "第一句"
