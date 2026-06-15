"""Minimal FastAPI server exposing the trip-agent graph as an HTTP API.

Keeps the same contract the MustStart app already uses:
    POST /api/chat  ->  {session_id, reply, guide_json?}

Run locally:   uv run uvicorn server:app --host 0.0.0.0 --port 8000
In Docker:     see Dockerfile
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from agent.graph import graph
from agent.tracing import tracing_status
from prompts.travel_planner_zh import build_context_guide_message

print(tracing_status())

app = FastAPI(title="trip-agent", description="觅途 1+N 旅行 Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话 ID，多轮对话传入")
    context_guide: Optional[dict[str, Any]] = Field(None, description="导入的攻略上下文")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    guide_json: Optional[dict[str, Any]] = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
def chat(req: ChatRequest) -> ChatResponse:
    # NOTE: sync def on purpose — graph.invoke() is blocking, so FastAPI runs this
    # in a threadpool and the event loop (incl. /health) stays responsive.
    sid = req.session_id or str(uuid.uuid4())

    content = req.message
    if req.context_guide:
        ctx = build_context_guide_message(req.context_guide)
        content = f"{ctx}\n\n---\n\n用户的问题：\n{req.message}"

    result = graph.invoke(
        {"messages": [HumanMessage(content=content)]},
        config={"configurable": {"thread_id": sid}},
    )
    text = _message_text(result["messages"][-1])
    return ChatResponse(session_id=sid, reply=_strip_guide(text), guide_json=_parse_guide(text))


def _message_text(message: Any) -> str:
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


def _parse_guide(content: str) -> dict[str, Any] | None:
    match = re.search(r"\[GUIDE_JSON_START\]\s*([\s\S]*?)\s*\[GUIDE_JSON_END\]", content)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return None


def _strip_guide(content: str) -> str:
    return re.sub(r"\[GUIDE_JSON_START\][\s\S]*?\[GUIDE_JSON_END\]", "", content).strip()
