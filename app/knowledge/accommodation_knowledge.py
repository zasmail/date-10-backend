"""Accommodation knowledge loader."""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import yaml

from app.schemas.accommodation import AccommodationKnowledgeBase, AccommodationKnowledgeEntry

KNOWLEDGE_PATH = Path(__file__).parent / "accommodations.yaml"


@lru_cache(maxsize=1)
def load_accommodation_knowledge() -> AccommodationKnowledgeBase:
    """Load and validate the accommodation knowledge base."""
    with open(KNOWLEDGE_PATH) as f:
        data = yaml.safe_load(f)
    return AccommodationKnowledgeBase(**data)


def get_accommodations_for_destination(destination: str) -> List[AccommodationKnowledgeEntry]:
    """Get accommodations for a specific destination."""
    kb = load_accommodation_knowledge()
    normalized = destination.lower().strip()
    return [acc for acc in kb.accommodations if acc.destination.lower() == normalized]


def get_accommodations_by_style(style: str) -> List[AccommodationKnowledgeEntry]:
    """Get accommodations matching a style."""
    kb = load_accommodation_knowledge()
    normalized = style.lower().strip()
    return [acc for acc in kb.accommodations if normalized in acc.style.lower()]


def format_accommodations_for_prompt(destination: Optional[str] = None) -> str:
    """Format accommodation knowledge for system prompt injection."""
    kb = load_accommodation_knowledge()

    if destination:
        accommodations = get_accommodations_for_destination(destination)
    else:
        accommodations = kb.accommodations

    lines = ["<accommodation_knowledge>"]

    current_dest = None
    for acc in sorted(accommodations, key=lambda x: x.destination):
        if acc.destination != current_dest:
            if current_dest is not None:
                lines.append("</destination_accommodations>")
            current_dest = acc.destination
            lines.append(f'<destination_accommodations location="{current_dest}">')

        lines.append(f'  <accommodation name="{acc.name}">')
        lines.append(f"    Area: {acc.area}")
        lines.append(f"    Style: {acc.style}")
        lines.append(f"    Price: {acc.price_range}")
        lines.append(f'    Highlights: {", ".join(acc.highlights)}')
        lines.append(f'    Best for: {", ".join(acc.best_for)}')
        lines.append("  </accommodation>")

    if current_dest is not None:
        lines.append("</destination_accommodations>")

    lines.append("</accommodation_knowledge>")

    return "\n".join(lines)
