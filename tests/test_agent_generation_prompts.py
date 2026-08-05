"""Tests for agent generation-mode prompt detection."""

import pytest
from app.agents.activities_agent import ActivitiesAgent
from app.agents.logistics_agent import LogisticsAgent
from app.agents.base_agent import SectionHandoff


class TestActivitiesAgentModeDetection:
    """Tests for ActivitiesAgent generation mode detection."""

    @pytest.fixture
    def agent(self):
        return ActivitiesAgent()

    def test_generation_mode_with_empty_days(self, agent):
        """Empty days array indicates generation mode."""
        handoff = SectionHandoff(
            section_type="activities",
            current_state={"days": []},
            user_request="Plan activities",
        )
        assert agent._is_generation_mode(handoff) is True

    def test_generation_mode_with_no_days_key(self, agent):
        """Missing days key indicates generation mode."""
        handoff = SectionHandoff(
            section_type="activities",
            current_state={},
            user_request="Plan activities",
        )
        assert agent._is_generation_mode(handoff) is True

    def test_refinement_mode_with_existing_days(self, agent):
        """Populated days array indicates refinement mode."""
        handoff = SectionHandoff(
            section_type="activities",
            current_state={
                "days": [
                    {"day_number": 1, "title": "Day 1", "location": "Beach"}
                ]
            },
            user_request="Add more activities",
        )
        assert agent._is_generation_mode(handoff) is False

    def test_generation_mode_from_constraint_flag(self, agent):
        """is_generation constraint forces generation mode."""
        handoff = SectionHandoff(
            section_type="activities",
            current_state={"days": [{"day_number": 1}]},  # Has days, but...
            user_request="test",
            constraints=["is_generation"],  # Flag overrides
        )
        assert agent._is_generation_mode(handoff) is True

    def test_prompt_uses_generation_mode_when_empty(self, agent):
        """System prompt should use generation prompt for empty state."""
        handoff = SectionHandoff(
            section_type="activities",
            current_state={"days": []},
            user_request="Plan activities",
        )
        prompt = agent._build_system_prompt(handoff)
        # Generation prompt should mention creating activities from scratch
        assert "creating" in prompt.lower() and "activities" in prompt.lower()
        assert "update_activities_section" in prompt

    def test_prompt_uses_refinement_mode_with_days(self, agent):
        """System prompt should use refinement prompt for existing state."""
        handoff = SectionHandoff(
            section_type="activities",
            current_state={"days": [{"day_number": 1, "title": "Day 1"}]},
            user_request="Add more activities",
        )
        prompt = agent._build_system_prompt(handoff)
        assert "activities specialist" in prompt.lower()


class TestLogisticsAgentModeDetection:
    """Tests for LogisticsAgent generation mode detection."""

    @pytest.fixture
    def agent(self):
        return LogisticsAgent()

    def test_generation_mode_with_empty_state(self, agent):
        """Empty logistics state indicates generation mode."""
        handoff = SectionHandoff(
            section_type="logistics",
            current_state={},
            user_request="Create logistics",
        )
        assert agent._is_generation_mode(handoff) is True

    def test_generation_mode_with_empty_arrays(self, agent):
        """Empty arrays in all fields indicates generation mode."""
        handoff = SectionHandoff(
            section_type="logistics",
            current_state={
                "transportation_notes": [],
                "packing_suggestions": [],
                "caveats": [],
            },
            user_request="Create logistics",
        )
        assert agent._is_generation_mode(handoff) is True

    def test_refinement_mode_with_transport_notes(self, agent):
        """Has transportation notes indicates refinement mode."""
        handoff = SectionHandoff(
            section_type="logistics",
            current_state={
                "transportation_notes": ["Rent a car at airport"],
            },
            user_request="Add packing list",
        )
        assert agent._is_generation_mode(handoff) is False

    def test_refinement_mode_with_packing_suggestions(self, agent):
        """Has packing suggestions indicates refinement mode."""
        handoff = SectionHandoff(
            section_type="logistics",
            current_state={
                "packing_suggestions": ["Sunscreen"],
            },
            user_request="Update transport",
        )
        assert agent._is_generation_mode(handoff) is False

    def test_refinement_mode_with_caveats(self, agent):
        """Has caveats indicates refinement mode."""
        handoff = SectionHandoff(
            section_type="logistics",
            current_state={
                "caveats": ["Book early for peak season"],
            },
            user_request="Update packing",
        )
        assert agent._is_generation_mode(handoff) is False

    def test_generation_mode_from_constraint_flag(self, agent):
        """is_generation constraint forces generation mode."""
        handoff = SectionHandoff(
            section_type="logistics",
            current_state={"transportation_notes": ["Has content"]},  # Has content, but...
            user_request="test",
            constraints=["is_generation"],  # Flag overrides
        )
        assert agent._is_generation_mode(handoff) is True

    def test_prompt_uses_generation_mode_when_empty(self, agent):
        """System prompt should use generation prompt for empty state."""
        handoff = SectionHandoff(
            section_type="logistics",
            current_state={},
            user_request="Create logistics",
        )
        prompt = agent._build_system_prompt(handoff)
        assert "CREATING" in prompt

    def test_prompt_uses_refinement_mode_with_content(self, agent):
        """System prompt should use refinement prompt for existing state."""
        handoff = SectionHandoff(
            section_type="logistics",
            current_state={"transportation_notes": ["Rent a car"]},
            user_request="Add visa info",
        )
        prompt = agent._build_system_prompt(handoff)
        assert "logistics" in prompt.lower() and "specialist" in prompt.lower()

    def test_prompt_includes_activities_context(self, agent):
        """System prompt should include activities context for logistics."""
        handoff = SectionHandoff(
            section_type="logistics",
            current_state={},
            user_request="Create logistics",
            related_sections={
                "activities": {
                    "days": [
                        {"day_number": 1, "location": "Tarifa"},
                        {"day_number": 2, "location": "Tangier"},
                    ]
                }
            },
        )
        prompt = agent._build_system_prompt(handoff)
        assert "ACTIVITIES PLANNED: 2 days" in prompt
        assert "Tarifa" in prompt or "Tangier" in prompt


class TestPromptImports:
    """Tests that generation prompts are properly exported."""

    def test_activities_generation_prompt_exists(self):
        """ACTIVITIES_GENERATION_PROMPT should be importable."""
        from app.prompts.agent_prompts import ACTIVITIES_GENERATION_PROMPT
        assert "creating" in ACTIVITIES_GENERATION_PROMPT.lower()
        assert "day" in ACTIVITIES_GENERATION_PROMPT.lower()

    def test_logistics_generation_prompt_exists(self):
        """LOGISTICS_GENERATION_PROMPT should be importable."""
        from app.prompts.agent_prompts import LOGISTICS_GENERATION_PROMPT
        assert "creating" in LOGISTICS_GENERATION_PROMPT.lower()
        assert "overview" in LOGISTICS_GENERATION_PROMPT.lower()

    def test_all_prompts_in_all_list(self):
        """All prompts should be in __all__ for proper export."""
        from app.prompts import agent_prompts
        assert "ACTIVITIES_GENERATION_PROMPT" in agent_prompts.__all__
        assert "LOGISTICS_GENERATION_PROMPT" in agent_prompts.__all__
