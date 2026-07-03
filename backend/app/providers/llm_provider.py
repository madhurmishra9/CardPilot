"""LLM provider interface (spec §4-F, Phase 5).

Grounding contract: the model only EXPLAINS numbers the deterministic engines
computed — it never does reward math itself. The chat service passes engine
output as `facts`; providers may rephrase, never recalculate or invent.

Select with CARDPILOT_LLM=none|ollama|anthropic (default none = deterministic
replies, fully offline). Cloud calls are opt-in per §7 privacy rules.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

GROUNDING_SYSTEM_PROMPT = (
    "You are CardPilot's advisory voice. Rephrase the FACTS below into one short, "
    "friendly answer to the user's question. HARD RULES: state ONLY numbers that "
    "appear verbatim in the FACTS; never compute, estimate or recall reward rates, "
    "fees or point values yourself; if the FACTS don't answer the question, say so."
)


class LLMProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def explain(self, question: str, facts: str) -> str:
        """Turn engine-computed facts into a conversational reply."""


class NullProvider(LLMProvider):
    """No LLM: return the deterministic engine summary as-is. Always available."""

    name = "none"

    def explain(self, question: str, facts: str) -> str:
        return facts


class OllamaProvider(LLMProvider):
    """Local model via Ollama — data never leaves the machine."""

    name = "ollama"

    def __init__(self):
        self.base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.model = os.environ.get("CARDPILOT_LLM_MODEL", "llama3.2")

    def explain(self, question: str, facts: str) -> str:
        import httpx
        prompt = (f"{GROUNDING_SYSTEM_PROMPT}\n\nQUESTION: {question}\n\n"
                  f"FACTS:\n{facts}\n\nANSWER:")
        try:
            resp = httpx.post(f"{self.base_url}/api/generate",
                              json={"model": self.model, "prompt": prompt,
                                    "stream": False},
                              timeout=60)
            resp.raise_for_status()
            return resp.json().get("response", "").strip() or facts
        except Exception:
            return facts  # engine facts are always a safe fallback


class AnthropicProvider(LLMProvider):
    """Cloud fallback. Requires ANTHROPIC_API_KEY and explicit opt-in."""

    name = "anthropic"

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = os.environ.get("CARDPILOT_LLM_MODEL", "claude-sonnet-5")

    def explain(self, question: str, facts: str) -> str:
        if not self.api_key:
            return facts
        import httpx
        try:
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": self.api_key,
                         "anthropic-version": "2023-06-01"},
                json={"model": self.model, "max_tokens": 400,
                      "system": GROUNDING_SYSTEM_PROMPT,
                      "messages": [{"role": "user",
                                    "content": f"QUESTION: {question}\n\nFACTS:\n{facts}"}]},
                timeout=60)
            resp.raise_for_status()
            blocks = resp.json().get("content", [])
            text = "".join(b.get("text", "") for b in blocks).strip()
            return text or facts
        except Exception:
            return facts


def get_llm_provider() -> LLMProvider:
    kind = os.environ.get("CARDPILOT_LLM", "none").lower()
    if kind == "ollama":
        return OllamaProvider()
    if kind == "anthropic":
        return AnthropicProvider()
    return NullProvider()
