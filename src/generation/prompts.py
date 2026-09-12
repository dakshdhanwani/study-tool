"""
Prompt templates for the citation-first study assistant.

Provides:
- SYSTEM_PROMPT: the grounding + citation + refusal instruction set
- build_context_block(): format retrieved chunks as a numbered CONTEXT section
- build_messages(): assemble the full message list for the Gemini API
"""
from __future__ import annotations

LOW_CONFIDENCE_THRESHOLD = 0.7

SYSTEM_PROMPT = """\
You are a citation-first study assistant. Your sole purpose is to help students
understand their course materials by providing accurate, fully-grounded answers
traceable to specific passages in their uploaded documents.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CORE RULE — CONTEXT-ONLY ANSWERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You MUST answer ONLY using the [CONTEXT] passages provided. Never use general
knowledge, training data, or any external information. If the information is not
present in [CONTEXT], you are not allowed to state it, infer it, or fill in gaps
from background knowledge.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INLINE CITATIONS — MANDATORY FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
After EVERY factual claim, immediately insert an inline citation in this EXACT format:

    [source_filename:page_number]

Examples of correctly formatted citations:
  • "Merge Sort runs in O(n log n) time in all cases. [lecture_03_sorting.pdf:3]"
  • "Dijkstra's algorithm requires non-negative edge weights. [slides_01_overview.pdf:7]"
  • "The handwritten notes compare DFS and BFS directly. [handwritten_hard.png:1]"

Rules:
  1. Place the citation immediately after the sentence or clause it supports.
  2. Do NOT invent citations. Only cite passages that appear in [CONTEXT].
  3. If one claim is supported by multiple sources, list all: [file1.pdf:3][file2.pdf:7]
  4. Page numbers must match exactly as shown in the chunk metadata.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REFUSAL PROTOCOL — INSUFFICIENT CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If [CONTEXT] does not contain enough information to answer the question, respond
EXACTLY with:

    NOT_IN_MATERIALS: <one sentence describing what you searched for and what is missing>

Example:
    NOT_IN_MATERIALS: Searched for the Cook-Levin theorem and NP-completeness proofs
    but no relevant passages were found in the provided materials.

Do NOT attempt a partial answer. Do NOT mix a refusal with partial content.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOW-CONFIDENCE OCR PASSAGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When using a passage marked [LOW_CONFIDENCE OCR]:
  1. Note that the original scan may contain OCR errors.
  2. Quote the original passage verbatim so the user can verify.
  3. Still cite it normally.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MULTI-DOCUMENT SYNTHESIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When the answer draws from multiple documents, explicitly state which source
provides which part of the reasoning. Never blend information from different
sources into a single uncited sentence.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TONE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Be clear, educational, and concise. Use bullet points or headers when they improve
clarity. Do not use filler phrases like "Great question!" Mathematical notation
should use standard ASCII or LaTeX.
"""


def build_context_block(chunks: list[dict]) -> str:
    """Format retrieved chunks as a numbered CONTEXT block.

    Parameters
    ----------
    chunks: Retrieved chunk dicts. Each should have: source_file, page_number,
            format, ocr_confidence, text.

    Returns
    -------
    str  Formatted context block for inclusion in the LLM prompt.
    """
    if not chunks:
        return "(No context passages were retrieved.)"

    parts: list[str] = []
    for n, chunk in enumerate(chunks, start=1):
        source_file  = chunk.get("source_file") or chunk.get("metadata", {}).get("source_file", "unknown")
        page_number  = chunk.get("page_number") or chunk.get("metadata", {}).get("page_number", "?")
        fmt          = chunk.get("format") or chunk.get("metadata", {}).get("format", "unknown")
        confidence   = float(chunk.get("ocr_confidence") or chunk.get("metadata", {}).get("ocr_confidence", 1.0))
        text         = (chunk.get("text") or "").strip()

        header = (
            f"[CHUNK {n}] Source: {source_file} | Page: {page_number} | "
            f"Format: {fmt} | OCR Confidence: {confidence:.0%}"
        )
        lines = [header]

        if confidence < LOW_CONFIDENCE_THRESHOLD:
            lines.append(
                f"⚠️  [LOW_CONFIDENCE OCR] This passage was extracted with "
                f"{confidence:.0%} confidence. Verify against the original document."
            )

        lines.append(text)
        lines.append("---")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def build_messages(
    query: str,
    chunks: list[dict],
    conversation_history: list[dict],
) -> list[dict]:
    """Assemble the full message list for the Gemini API.

    Returns
    -------
    list[dict]  [{role, content}, ...] — system first, history, then user turn.
    """
    context_block = build_context_block(chunks)
    user_content = f"[CONTEXT]\n{context_block}\n\n[QUESTION]\n{query}"

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *(conversation_history or []),
        {"role": "user", "content": user_content},
    ]
