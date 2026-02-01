"""Tests for system prompt generation."""

from app.prompts.travel_assistant import build_system_prompt
from app.schemas.preferences import (
    ActivityPreferences,
    DestinationPreferences,
    PreferencesData,
)


class TestBuildSystemPrompt:
    """Tests for system prompt building."""

    def test_returns_three_blocks(self, sample_preferences: PreferencesData):
        """Should return exactly 3 content blocks."""
        blocks = build_system_prompt(sample_preferences)
        assert len(blocks) == 3, f"Expected 3 blocks, got {len(blocks)}"

    def test_all_blocks_have_cache_control(self, sample_preferences: PreferencesData):
        """All blocks should have cache_control with type 'ephemeral'."""
        blocks = build_system_prompt(sample_preferences)

        for i, block in enumerate(blocks):
            assert "cache_control" in block, f"Block {i} missing cache_control"
            assert block["cache_control"]["type"] == "ephemeral", f"Block {i} wrong cache type"

    def test_all_blocks_are_text_type(self, sample_preferences: PreferencesData):
        """All blocks should be text type."""
        blocks = build_system_prompt(sample_preferences)

        for i, block in enumerate(blocks):
            assert block["type"] == "text", f"Block {i} should be text type"
            assert "text" in block, f"Block {i} missing text content"

    def test_includes_discovery_protocol(self, sample_preferences: PreferencesData):
        """First block should contain the destination discovery protocol."""
        blocks = build_system_prompt(sample_preferences)

        assert "destination_discovery_protocol" in blocks[0]["text"]
        assert "FILTER DESTINATIONS" in blocks[0]["text"]
        assert "EXPLAIN WHY" in blocks[0]["text"]

    def test_includes_destination_knowledge(self, sample_preferences: PreferencesData):
        """Second block should contain destination knowledge."""
        blocks = build_system_prompt(sample_preferences)

        assert "<destination_knowledge>" in blocks[1]["text"]
        assert "</destination_knowledge>" in blocks[1]["text"]
        # Should have at least some destination content
        assert "Tarifa" in blocks[1]["text"] or "Cape Town" in blocks[1]["text"]

    def test_includes_preferences(self, sample_preferences: PreferencesData):
        """Third block should contain user preferences."""
        blocks = build_system_prompt(sample_preferences)

        # Check for bucket list items from sample_preferences
        assert "Tarifa" in blocks[2]["text"]
        assert "Cape Town" in blocks[2]["text"]
        # Check for visited item
        assert "Bali" in blocks[2]["text"]

    def test_includes_activities(self, sample_preferences: PreferencesData):
        """Third block should reference user's preferred activities."""
        blocks = build_system_prompt(sample_preferences)

        assert "kitesurfing" in blocks[2]["text"]
        assert "surfing" in blocks[2]["text"]

    def test_with_empty_preferences(self):
        """Should work with default/empty PreferencesData."""
        prefs = PreferencesData()
        blocks = build_system_prompt(prefs)

        assert len(blocks) == 3
        # Should still have destination knowledge
        assert "<destination_knowledge>" in blocks[1]["text"]
        # Should have default values in preferences
        assert "Not specified" in blocks[2]["text"]

    def test_with_partial_preferences(self):
        """Should work with partially filled preferences."""
        prefs = PreferencesData(
            activities=ActivityPreferences(preferred=["hiking"]),
        )
        blocks = build_system_prompt(prefs)

        assert len(blocks) == 3
        assert "hiking" in blocks[2]["text"]

    def test_block_order_is_correct(self, sample_preferences: PreferencesData):
        """Blocks should be in correct order: instructions, knowledge, preferences."""
        blocks = build_system_prompt(sample_preferences)

        # Block 0: Instructions with discovery protocol
        assert "You are Wanderlust" in blocks[0]["text"]
        assert "destination_discovery_protocol" in blocks[0]["text"]

        # Block 1: Destination knowledge
        assert "<destination_knowledge>" in blocks[1]["text"]

        # Block 2: User preferences
        assert "Travel Profile" in blocks[2]["text"]

    def test_reasonable_size(self, sample_preferences: PreferencesData):
        """Prompt should be reasonably sized (under 60K chars for full prompt)."""
        blocks = build_system_prompt(sample_preferences)

        total_chars = sum(len(b["text"]) for b in blocks)
        # Rough token estimate: 4 chars per token, so 60K chars ~ 15K tokens
        assert total_chars < 60000, f"Prompt too large: {total_chars} chars"

        # Log size for debugging
        print(f"Total prompt size: {total_chars} chars (~{total_chars // 4} tokens)")
        for i, block in enumerate(blocks):
            print(f"  Block {i}: {len(block['text'])} chars")
