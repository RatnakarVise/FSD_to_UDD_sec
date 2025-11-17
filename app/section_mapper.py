import json
import os
import logging
from typing import Dict, List, Optional
from .config import DEFAULT_MAPPING_PATH

logger = logging.getLogger("SECTION_MAPPER")

class SectionMapper:
    def __init__(self, path: Optional[str] = None):
        self.path = path or DEFAULT_MAPPING_PATH

        logger.info(f"📘 Loading FSD→UDD mapping file: {self.path}")

        if not os.path.exists(self.path):
            logger.error(f"❌ Mapping file not found at: {self.path}")
            raise FileNotFoundError(f"Mapping file not found at: {self.path}")

        with open(self.path, "r", encoding="utf-8") as f:
            self.map: Dict[str, List[str]] = json.load(f)

        logger.info(f"✔ Mapping file loaded. Total UDD keys: {len(self.map)}")

    # ------------------------------------------------------------

    def keywords_for(self, udd_section: str) -> List[str]:
        keys = self.map.get(udd_section, [])

        if keys:
            logger.debug(
                f"🔗 Mapping lookup — UDD '{udd_section}' → FSD keys {keys}"
            )
        else:
            logger.warning(
                f"⚠ No mapping found for UDD section '{udd_section}'. Returning empty list."
            )

        return keys
