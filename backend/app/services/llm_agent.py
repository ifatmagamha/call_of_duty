"""Deprecated compatibility surface.

Clinic recommendations are fully deterministic. Paid inference is available only
through the explicit image, audio, and situation briefing endpoints.
"""

from app.schemas import LLMAgentNote


def generate_critical_llm_note(*_args, **_kwargs) -> LLMAgentNote | None:
    return None
