import os
import re
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .config import DEFAULT_RAG_PATH


# ============================================================
# LOGGER SETUP
# ============================================================

logger = logging.getLogger("RAG_LOADER")


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass
class RagSection:
    name: str
    type: str
    description: str
    prompt: str
    fields: Optional[List[str]] = None


# ============================================================
# INTERNAL PARSER FOR EACH BLOCK
# ============================================================

def _parse_rag_block(block: str) -> RagSection:
    logger.debug("Parsing RAG block:\n" + block[:200] + ("..." if len(block) > 200 else ""))

    lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
    if not lines or not lines[0].startswith("#"):
        logger.error("❌ RAG section invalid — missing '#Section'")
        raise ValueError("RAG section must start with '#Section Name'")

    name = lines[0][1:].strip()
    logger.info(f"➡ Parsing RAG Section: {name}")

    keyvals: Dict[str, Any] = {}
    current_key = None
    current_val_lines: List[str] = []

    def flush_key():
        nonlocal current_key, current_val_lines
        if current_key is not None:
            value = " ".join(current_val_lines).strip()
            keyvals[current_key] = value
            logger.debug(f"   • Key parsed: {current_key} = {value[:100]}")
            current_key = None
            current_val_lines = []

    for ln in lines[1:]:
        if re.match(r"^[a-zA-Z_]+:\s*", ln):
            flush_key()
            k, v = ln.split(":", 1)
            current_key = k.strip()
            current_val_lines = [v.strip()]
        else:
            current_val_lines.append(ln.strip())
    flush_key()

    type_ = keyvals.get("type", "text")
    description = keyvals.get("description", "")
    prompt = keyvals.get("prompt", "")
    fields = None

    # --------------------------------------------------------
    # Parse "fields"
    # --------------------------------------------------------
    if "fields" in keyvals:
        raw = keyvals["fields"]
        logger.debug(f"   • Raw fields string: {raw}")

        m = re.match(r"^\[(.*)\]$", raw)
        if m:
            parts = [p.strip() for p in m.group(1).split(",")]
            fields = [p for p in parts if p]
        else:
            fields = [f.strip() for f in raw.split(",") if f.strip()]

        logger.info(f"   • Parsed fields: {fields}")

    rag_section = RagSection(
        name=name,
        type=type_,
        description=description,
        prompt=prompt,
        fields=fields
    )

    logger.info(f"✔ Completed parsing RAG section: {name}")
    return rag_section


# ============================================================
# PUBLIC LOADER FUNCTION WITH LOGGING
# ============================================================

def load_rag_sections(rag_path: Optional[str]) -> List[RagSection]:

    path = rag_path or DEFAULT_RAG_PATH

    logger.info(f"📘 Loading RAG file from: {path}")

    if not os.path.exists(path):
        logger.error(f"❌ RAG file NOT FOUND at: {path}")
        raise FileNotFoundError(f"RAG file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    logger.debug(f"📄 RAG file raw size: {len(text)} bytes")

    blocks = re.split(r"\n(?=#)", text.strip())
    logger.info(f"📦 Found {len(blocks)} RAG blocks")

    sections = []
    for idx, block in enumerate(blocks):
        if block.strip():
            try:
                section = _parse_rag_block(block)
                sections.append(section)
            except Exception as e:
                logger.exception(f"❌ Error parsing RAG block #{idx + 1}")

    logger.info(f"✅ Total parsed RAG sections: {len(sections)}")

    return sections
