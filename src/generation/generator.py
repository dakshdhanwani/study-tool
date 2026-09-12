"""
Answer generation orchestrator: Gemini API + grounding + citation parsing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import google.generativeai as genai

from src.config import GEMINI_API_KEY, GEMINI_MODEL
from src.generation.prompts import build_context_block, SYSTEM_PROMPT
from src.generation.citation_parser import Citation, extract_answer_and_citations, get_refusal_reason
from src.generation.grounding_check import check_citations_grounded, compute_grounding_score

_CONFIGURED = False


@dataclass
class GenerationResult:
    """Full output of one generation call."""
    answer: str
    citations: list[Citation] = field(default_factory=list)
    is_refusal: bool = False
    refusal_reason: str = ""
    grounding_score: float = 1.0
    grounding_details: list[dict] = field(default_factory=list)
    chunks_used: list[dict] = field(default_factory=list)
    raw_response: str = ""
    model_name: str = ""


def configure_gemini(api_key: Optional[str] = None) -> None:
    """Configure the Gemini SDK. Raises ValueError if no key found."""
    global _CONFIGURED
    key = api_key or GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError(
            "No Gemini API key found. Add GEMINI_API_KEY to your .env file."
        )
    genai.configure(api_key=key)
    _CONFIGURED = True


def generate_answer(
    query: str,
    chunks: list[dict],
    conversation_history: Optional[list[dict]] = None,
    model_name: Optional[str] = None,
) -> GenerationResult:
    """Generate a grounded, citation-annotated answer using Gemini.

    Parameters
    ----------
    query:                The student's question.
    chunks:               Retrieved context chunks (list of dicts).
    conversation_history: Prior turns [{role, content}, ...].
    model_name:           Gemini model override.

    Returns
    -------
    GenerationResult
    """
    global _CONFIGURED
    if not _CONFIGURED:
        configure_gemini()

    effective_model = model_name or GEMINI_MODEL
    context_block = build_context_block(chunks)

    # Build conversation parts for Gemini
    history_parts: list[str] = []
    for msg in (conversation_history or []):
        role_label = "USER" if msg.get("role") == "user" else "ASSISTANT"
        history_parts.append(f"[{role_label}]\n{msg['content']}")

    user_turn = f"[CONTEXT]\n{context_block}\n\n[QUESTION]\n{query}"
    history_parts.append(f"[USER]\n{user_turn}")
    full_prompt = "\n\n".join(history_parts)

    try:
        model = genai.GenerativeModel(
            model_name=effective_model,
            system_instruction=SYSTEM_PROMPT,
        )
        response = model.generate_content(full_prompt)
        raw_text = response.text

    except Exception as exc:
        error_msg = f"ERROR: Gemini API call failed — {type(exc).__name__}: {exc}"
        return GenerationResult(
            answer=error_msg,
            is_refusal=False,
            grounding_score=0.0,
            chunks_used=chunks,
            model_name=effective_model,
        )

    answer, citations, refusal_flag = extract_answer_and_citations(raw_text)

    if refusal_flag:
        reason = get_refusal_reason(raw_text)
        return GenerationResult(
            answer=answer,
            citations=[],
            is_refusal=True,
            refusal_reason=reason,
            grounding_score=1.0,
            chunks_used=chunks,
            raw_response=raw_text,
            model_name=effective_model,
        )

    grounding_details = check_citations_grounded(citations, chunks)
    grounding_score = compute_grounding_score(grounding_details)

    return GenerationResult(
        answer=answer,
        citations=citations,
        is_refusal=False,
        refusal_reason="",
        grounding_score=grounding_score,
        grounding_details=grounding_details,
        chunks_used=chunks,
        raw_response=raw_text,
        model_name=effective_model,
    )
