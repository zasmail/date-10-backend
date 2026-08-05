"""Base agent class for specialized section agents."""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel, Field

from anthropic import AsyncAnthropic


class CrossSectionImpact(BaseModel):
    """Impact on another section that the orchestrator needs to propagate."""

    affected_section: str
    impact_type: str  # "date_change", "location_change", "budget_change", etc.
    description: str
    suggested_action: Optional[str] = None


class SectionHandoff(BaseModel):
    """Structured handoff from orchestrator to section agent."""

    section_type: str
    current_state: Dict[str, Any]  # Current section data
    user_request: str
    constraints: List[str] = Field(default_factory=list)  # Cross-section constraints
    related_sections: Dict[str, Any] = Field(
        default_factory=dict
    )  # Relevant data from other sections
    preferences: Optional[Dict[str, Any]] = None  # User preferences


class SectionResult(BaseModel):
    """Structured result from section agent."""

    section_type: str
    updated_state: Dict[str, Any]
    changes_made: List[str]  # Human-readable change descriptions
    cross_section_impacts: List[CrossSectionImpact] = Field(default_factory=list)
    confidence: float = 1.0  # Agent confidence in the update (0-1)
    needs_user_confirmation: bool = False
    confirmation_prompt: Optional[str] = None


class BaseAgent(ABC):
    """Abstract base class for specialized section agents."""

    SECTION_TYPE: str = ""  # Override in subclass
    SYSTEM_PROMPT: str = ""  # Override in subclass
    TOOLS: List[Dict[str, Any]] = []  # Override in subclass

    def __init__(self):
        self.client = AsyncAnthropic()

    def _build_system_prompt(self, handoff: SectionHandoff) -> str:
        """Build context-aware system prompt with section data."""
        constraints_text = (
            "\n".join(f"- {c}" for c in handoff.constraints)
            if handoff.constraints
            else "None"
        )
        related_text = handoff.related_sections if handoff.related_sections else "None"
        prefs_text = (
            handoff.preferences if handoff.preferences else "Default preferences"
        )

        return f"""{self.SYSTEM_PROMPT}

CURRENT SECTION STATE:
{handoff.current_state}

CONSTRAINTS FROM OTHER SECTIONS:
{constraints_text}

RELATED SECTION DATA:
{related_text}

USER PREFERENCES:
{prefs_text}
"""

    @abstractmethod
    async def process(
        self,
        handoff: SectionHandoff,
        messages: List[Dict[str, str]],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a section request with streaming.

        Yields events:
        - {"type": "text", "content": "..."} - Text chunks
        - {"type": "tool_use", "name": "...", "input": {...}} - Tool being used
        - {"type": "tool_result", "result": {...}} - Tool execution result
        - {"type": "section_update", "data": {...}} - Section update
        - {"type": "done", "result": SectionResult} - Final result
        """
        pass

    @abstractmethod
    def execute_tool(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        pass

    def _report_cross_section_impact(
        self,
        affected_section: str,
        impact_type: str,
        description: str,
        suggested_action: Optional[str] = None,
    ) -> CrossSectionImpact:
        """Create a cross-section impact report."""
        return CrossSectionImpact(
            affected_section=affected_section,
            impact_type=impact_type,
            description=description,
            suggested_action=suggested_action,
        )


__all__ = [
    "BaseAgent",
    "SectionHandoff",
    "SectionResult",
    "CrossSectionImpact",
]
