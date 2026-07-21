"""DeepSeek API wrapper only, no business logic. Swappable if the provider changes.

Thin wrapper only — no prompt construction, no retry logic. Returns the raw
SDK message object (.content, .tool_calls) unshaped; interpretation is the
caller's job (conversation_service.py).
"""

import os

from openai import APIConnectionError, APITimeoutError, OpenAI

REQUEST_TIMEOUT_SECONDS = 30

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
    timeout=REQUEST_TIMEOUT_SECONDS,
)


class LLMUnavailableError(Exception):
    """Raised when the DeepSeek API can't be reached or times out."""


def call_model(messages: list[dict], tools: list[dict]):
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=messages,
            tools=tools,
        )
    except (APIConnectionError, APITimeoutError) as e:
        raise LLMUnavailableError(str(e)) from e
    return response.choices[0].message
