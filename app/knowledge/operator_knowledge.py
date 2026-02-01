"""Operator and guide knowledge loader."""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import yaml

from app.schemas.activity import OperatorKnowledgeBase, OperatorKnowledgeEntry

KNOWLEDGE_PATH = Path(__file__).parent / "operators.yaml"


@lru_cache(maxsize=1)
def load_operator_knowledge() -> OperatorKnowledgeBase:
    """Load and validate the operator knowledge base."""
    with open(KNOWLEDGE_PATH) as f:
        data = yaml.safe_load(f)
    return OperatorKnowledgeBase(**data)


def get_operators_for_destination(destination: str) -> List[OperatorKnowledgeEntry]:
    """Get operators for a specific destination."""
    kb = load_operator_knowledge()
    normalized = destination.lower().strip()
    return [op for op in kb.operators if op.destination.lower() == normalized]


def get_operators_by_activity(activity: str) -> List[OperatorKnowledgeEntry]:
    """Get operators offering a specific activity."""
    kb = load_operator_knowledge()
    normalized = activity.lower().strip()
    return [
        op
        for op in kb.operators
        if any(normalized in act.lower() for act in op.activities)
    ]


def format_operators_for_prompt(destination: Optional[str] = None) -> str:
    """Format operator knowledge for system prompt injection."""
    kb = load_operator_knowledge()

    if destination:
        operators = get_operators_for_destination(destination)
    else:
        operators = kb.operators

    lines = ["<operator_knowledge>"]

    current_dest = None
    for op in sorted(operators, key=lambda x: x.destination):
        if op.destination != current_dest:
            if current_dest is not None:
                lines.append("</destination_operators>")
            current_dest = op.destination
            lines.append(f'<destination_operators location="{current_dest}">')

        lines.append(f'  <operator name="{op.name}">')
        lines.append(f'    Activities: {", ".join(op.activities)}')
        lines.append(f"    Specialty: {op.specialty}")
        lines.append(f"    Price: {op.price_range}")
        if op.notes:
            lines.append(f"    Notes: {op.notes}")
        lines.append("  </operator>")

    if current_dest is not None:
        lines.append("</destination_operators>")

    lines.append("</operator_knowledge>")

    return "\n".join(lines)
