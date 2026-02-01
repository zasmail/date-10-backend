"""Destination knowledge loader and prompt formatter."""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import yaml

from app.knowledge.schemas import Destination, DestinationKnowledgeBase

KNOWLEDGE_PATH = Path(__file__).parent / "destinations.yaml"

# Month number to name mapping
MONTH_NAMES = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


@lru_cache(maxsize=1)
def load_knowledge_base() -> DestinationKnowledgeBase:
    """Load and validate the destination knowledge base from YAML.

    Returns cached result on subsequent calls.
    """
    with open(KNOWLEDGE_PATH) as f:
        data = yaml.safe_load(f)
    return DestinationKnowledgeBase(**data)


def get_destinations_for_month(month: int) -> List[Destination]:
    """Get destinations that have at least one activity in season for the given month.

    Args:
        month: Month number (1-12)

    Returns:
        List of destinations with activities in season for that month
    """
    kb = load_knowledge_base()
    result = []
    for dest in kb.destinations:
        for activity_data in dest.activities.values():
            if month in activity_data.season:
                result.append(dest)
                break
    return result


def _format_months(months: List[int]) -> str:
    """Convert month numbers to readable names."""
    return ", ".join(MONTH_NAMES[m] for m in sorted(months))


def format_knowledge_for_prompt(destinations: Optional[List[Destination]] = None) -> str:
    """Format destination knowledge as XML for system prompt injection.

    Args:
        destinations: Optional list of destinations to format. If None, uses all destinations.

    Returns:
        XML-formatted string suitable for system prompt injection
    """
    if destinations is None:
        kb = load_knowledge_base()
        destinations = kb.destinations

    lines = ["<destination_knowledge>"]

    for dest in destinations:
        lines.append(f'<destination name="{dest.name}" country="{dest.country}">')

        # Activities with seasonality
        lines.append("  <activities>")
        for activity_name, activity_data in dest.activities.items():
            lines.append(f"    <{activity_name}>")
            lines.append(f"      Season: {_format_months(activity_data.season)}")
            if activity_data.reliability:
                lines.append(f"      Reliability: {activity_data.reliability}")
            lines.append(f"      Conditions: {activity_data.conditions}")
            if activity_data.skill_level:
                lines.append(f"      Skill level: {activity_data.skill_level}")
            if activity_data.notes:
                lines.append(f"      Notes: {activity_data.notes}")
            lines.append(f"    </{activity_name}>")
        lines.append("  </activities>")

        # Climate
        lines.append("  <climate>")
        lines.append(f"    Best months: {_format_months(dest.climate.best_months)}")
        temps = ", ".join(f"{k}: {v}°C" for k, v in dest.climate.avg_temp_c.items())
        lines.append(f"    Average temperatures: {temps}")
        if dest.climate.rainy_months:
            lines.append(f"    Rainy months: {_format_months(dest.climate.rainy_months)}")
        lines.append("  </climate>")

        # Logistics
        lines.append("  <logistics>")
        lines.append(f"    Airports: {', '.join(dest.logistics.airports)}")
        lines.append(f"    Getting there: {dest.logistics.from_airport}")
        lines.append(f"    Visa: {dest.logistics.visa}")
        lines.append("  </logistics>")

        # Accommodation
        lines.append("  <accommodation>")
        lines.append(f"    Style: {dest.accommodation.style}")
        lines.append(f"    Budget: {dest.accommodation.budget_range}")
        lines.append(f"    Areas: {', '.join(dest.accommodation.areas)}")
        lines.append("  </accommodation>")

        # Vibe and recommendations
        lines.append(f"  <vibe>{dest.vibe}</vibe>")
        lines.append(f"  <why_go>{dest.why_go}</why_go>")
        lines.append(f"  <why_skip>{dest.why_skip}</why_skip>")

        lines.append("</destination>")

    lines.append("</destination_knowledge>")

    return "\n".join(lines)
