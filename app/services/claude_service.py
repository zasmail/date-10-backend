from typing import Any, AsyncGenerator, Dict, List

from anthropic import AsyncAnthropic

from app.prompts.travel_assistant import build_system_prompt
from app.schemas.preferences import PreferencesData

client = AsyncAnthropic()  # Uses ANTHROPIC_API_KEY env var


async def stream_response(
    messages: List[Dict[str, str]], preferences: PreferencesData
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream Claude response with preferences-aware system prompt."""

    system_prompt = build_system_prompt(preferences)

    async with client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield {"type": "text", "content": text}

        # Get final message for token usage
        final_message = await stream.get_final_message()
        yield {
            "type": "done",
            "usage": {
                "input_tokens": final_message.usage.input_tokens,
                "output_tokens": final_message.usage.output_tokens,
            },
        }
