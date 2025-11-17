import logging
from typing import List, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .config import LLM_MODEL
from .rag_loader import RagSection
from .section_extractor import extract_relevant_fsd_slice
from .section_mapper import SectionMapper

logger = logging.getLogger("LLM_ORCHESTRATOR")

SYSTEM_PROMPT = (
    "You are a senior SAP documentation specialist.\n"
    "You generate precise, client-ready text for a Unified Design Document (UDD) based on:\n"
    "1) a Functional Specification (FSD) excerpt,\n"
    "2) a UDD section definition (RAG).\n\n"
    "Rules:\n"
    "- Produce polished, formal, professional language fit for client deliverables.\n"
    "- Follow the section's 'type' and 'fields' instructions strictly (table vs. text).\n"
    "- Do not hallucinate. If something is missing, write [To Be Filled].\n"
    "- Keep each answer self-contained to be pasted directly into the UDD.\n"
    "- Use concise, well-structured prose. Avoid filler.\n"
    "- **Do NOT repeat or rewrite the section title in the output. Only generate the body content.**"
)



# ---------------------------------------------------------
# Build prompt for LLM
# ---------------------------------------------------------

def build_user_prompt(section: RagSection, fs_slice: str) -> str:
    fields_hint = f"\nFields (if table): {section.fields}" if section.fields else ""

    return (
        f"Target UDD Section: {section.name}\n"
        f"Type: {section.type}\n"
        f"Description: {section.description}{fields_hint}\n\n"
        "Authoring Instructions:\n"
        f"{section.prompt}\n\n"
        "Functional Spec Excerpt (FSD):\n"
        f"\"\"\"{fs_slice}\"\"\"\n\n"
        "Now produce only the content for the UDD section above. "
        "If type is 'table', return a clean markdown table with exactly the columns requested. "
        "If a field's value is unknown, use [To Be Filled]."
    )


def ensure_order(rag_sections: List[RagSection]) -> List[RagSection]:
    return rag_sections


# ---------------------------------------------------------
# Create OpenAI LLM
# ---------------------------------------------------------

def make_llm() -> ChatOpenAI:
    logger.info(f"🔧 Initializing LLM with model: {LLM_MODEL}")
    return ChatOpenAI(model=LLM_MODEL, streaming=False)


# ---------------------------------------------------------
# MAIN ORCHESTRATION — Generate all UDD sections
# ---------------------------------------------------------

def generate_udd_sections(
    fsd_text: str,
    rag_sections: List[RagSection],
    mapper: SectionMapper
) -> List[Tuple[str, str]]:

    logger.info("🚀 Starting UDD section generation...")
    logger.info(f"📌 Total RAG sections to process: {len(rag_sections)}")

    llm = make_llm()
    results: List[Tuple[str, str]] = []
    context_snippets: List[str] = []

    ordered = ensure_order(rag_sections)

    for idx, sec in enumerate(ordered, start=1):
        logger.info(f"\n===============================================")
        logger.info(f"📝 [{idx}/{len(ordered)}] Processing UDD Section: {sec.name}")
        logger.info(f"===============================================\n")

        # EXTRACT CORRECT FSD SLICE
        fs_slice = extract_relevant_fsd_slice(fsd_text, sec.name, mapper)

        logger.debug(f"📄 Extracted FSD Slice (length={len(fs_slice)}):\n"
                     f"{fs_slice[:5000]}\n{'...(truncated)' if len(fs_slice)>5000 else ''}")

        # BUILD CONTEXT + PROMPT
        prior_context = "\n\n".join(context_snippets[-3:])
        user_prompt = (
            (f"Context (previous sections):\n{prior_context}\n\n" if prior_context else "")
            + build_user_prompt(sec, fs_slice)
        )

        logger.debug(
            f"🧠 LLM USER PROMPT for section '{sec.name}':\n"
            f"{'-'*50}\n{user_prompt}\n{'-'*50}"
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]

        # -------------------------------------------------------------
        # INVOKE LLM
        # -------------------------------------------------------------
        try:
            logger.info(f"🤖 Invoking LLM for section: {sec.name}")
            resp = llm.invoke(messages)
        except Exception as e:
            logger.error(f"❌ LLM FAILURE for section '{sec.name}': {e}")
            raise

        # PARSE LLM OUTPUT
        content = resp.content.strip() if hasattr(resp, "content") else str(resp)

        logger.debug(
            f"📤 LLM RAW OUTPUT for '{sec.name}' (length={len(content)}):\n"
            f"{content}\n{'='*80}"
        )

        results.append((sec.name, content))
        context_snippets.append(f"[{sec.name}] {content[:1200]}")

    logger.info("🎉 Completed UDD section generation.")
    return results
