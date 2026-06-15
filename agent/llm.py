"""vivo 蓝心大模型 (玄机/xuanji platform) chat model factory.

The vivo AIGC competition endpoint is OpenAI-protocol compatible, so we drive it
with LangChain's ``ChatOpenAI`` pointed at the vivo base URL.

Verified against the platform (2026-06):
    endpoint : https://api-ai.vivo.com.cn/v1/chat/completions
    auth     : Authorization: Bearer <AppKey>     -> api_key=<AppKey>
    models   : Volc-DeepSeek-V3.2 (主力) | Doubao-Seed-2.0-pro/lite/mini | qwen3.5-plus
    extras   : reasoning_effort (minimal|low|medium|high), native `tools` function calling
    request_id query param is OPTIONAL.

Configuration (Backend/.env):
    VIVO_API_KEY            your AppKey (sk-xuanji-...)  -- required, never commit
    VIVO_API_BASE_URL       defaults to the endpoint above
    VIVO_MODEL              defaults to Volc-DeepSeek-V3.2
    VIVO_REASONING_EFFORT   defaults to "low"
"""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

DEFAULT_BASE_URL = "https://api-ai.vivo.com.cn/v1"
DEFAULT_MODEL = "Volc-DeepSeek-V3.2"
DEFAULT_REASONING_EFFORT = "low"

# vivo's allowed reasoning_effort values.
_VALID_EFFORTS = {"minimal", "low", "medium", "high"}


class VivoConfigError(RuntimeError):
    """Raised when the vivo API key is missing or invalid."""


def _resolve_api_key() -> str:
    # Prefer VIVO_API_KEY; fall back to the generic LLM_API_KEY for convenience.
    key = os.getenv("VIVO_API_KEY") or os.getenv("LLM_API_KEY", "")
    if not key or key == "EMPTY":
        raise VivoConfigError(
            "vivo API key 未配置。请在 Backend/.env 中设置 "
            "VIVO_API_KEY=sk-xuanji-...（从 https://aigc.vivo.com.cn/#/platform 获取，切勿提交到 Git）。"
        )
    return key


def get_llm(
    *,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    reasoning_effort: str | None = None,
) -> ChatOpenAI:
    """Build a ``ChatOpenAI`` bound to the vivo BlueLM endpoint.

    Args:
        temperature: Sampling temperature.
        max_tokens: Max tokens in the answer (excludes thinking tokens).
        reasoning_effort: One of minimal/low/medium/high. Defaults to the
            ``VIVO_REASONING_EFFORT`` env var, then ``"low"``. Use ``"high"`` for
            complex planning, ``"minimal"`` for quick intent classification.

    Raises:
        VivoConfigError: If no API key is configured.
    """
    effort = (reasoning_effort or os.getenv("VIVO_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT).lower()
    if effort not in _VALID_EFFORTS:
        effort = DEFAULT_REASONING_EFFORT

    return ChatOpenAI(
        model=os.getenv("VIVO_MODEL", DEFAULT_MODEL),
        base_url=os.getenv("VIVO_API_BASE_URL", DEFAULT_BASE_URL),
        api_key=_resolve_api_key(),
        temperature=temperature,
        max_tokens=max_tokens,
        reasoning_effort=effort,
        # Bounded per-call latency so one slow vivo call can't stall the whole flow.
        timeout=float(os.getenv("VIVO_TIMEOUT", "45")),
        max_retries=int(os.getenv("VIVO_MAX_RETRIES", "1")),
    )
