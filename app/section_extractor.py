import re
import logging
from typing import Dict, List
from .section_mapper import SectionMapper

logger = logging.getLogger("SECTION_EXTRACTOR")

# NEW REGEX:
# Only extract SECTION number — ignore title completely
SECTION_HEADER_REGEX = re.compile(
    r"^\s*SECTION\s*[:\-]\s*(\d+(?:\.\d+)*)",
    re.IGNORECASE | re.MULTILINE
)

# ============================================================
# PARSE FSD SECTION HEADERS
# ============================================================

def parse_fsd_sections(fsd_text: str) -> Dict[str, str]:
    logger.info("🔎 Starting FSD section parsing...")

    # Normalize \r
    fsd_text = fsd_text.replace("\r", "")

    # Force newline before SECTION:
    fsd_text = re.sub(
        r"\s*(?=SECTION\s*[:\-]\s*\d+(?:\.\d+)*)",
        "\n",
        fsd_text
    )

    # Clean multiple empty lines
    fsd_text = re.sub(r"\n{2,}", "\n", fsd_text)

    # Find section headers
    matches = list(SECTION_HEADER_REGEX.finditer(fsd_text))
    logger.info(f"📌 Total SECTION headers detected: {len(matches)}")

    sections: Dict[str, str] = {}

    # Extract content
    for idx, m in enumerate(matches):
        number = m.group(1).strip()        # e.g., "1", "3", "6.5"

        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(fsd_text)
        content = fsd_text[start:end].strip()

        logger.info(
            f"➡ Parsed SECTION {number} (content length={len(content)} chars)"
        )

        # Store content with section number
        sections[number] = content

    logger.info("✔ Completed FSD parsing.")
    return sections

# ============================================================
# APPLY MAPPING (FSD → UDD)
# ============================================================

def extract_relevant_fsd_slice(
    fsd_text: str,
    udd_section: str,
    mapper: SectionMapper
) -> str:

    logger.info(f"\n📘 Extracting FSD slice for UDD section: '{udd_section}'")

    fs_sections = parse_fsd_sections(fsd_text)
    mapped_keys: List[str] = mapper.keywords_for(udd_section)

    logger.info(f"🔗 Mapping lookup for '{udd_section}' → Keys: {mapped_keys}")

    combined = []

    for key in mapped_keys:
        key = key.strip()
        if key in fs_sections:
            logger.info(f"   ✔ Using FSD SECTION {key}")
            preview = fs_sections[key][:200].replace("\n", " ")
            logger.debug(f"     Content preview: {preview}...")
            combined.append(fs_sections[key])
        else:
            logger.warning(f"   ⚠ FSD SECTION {key} not found.")

    if combined:
        total_len = sum(len(c) for c in combined)
        logger.info(f"✔ Final slice assembled for '{udd_section}' ({total_len} chars)")
        return "\n\n".join(combined)

    logger.warning(
        f"⚠ No mapped sections found for '{udd_section}'. "
        f"Returning FULL FSD text."
    )
    return fsd_text
