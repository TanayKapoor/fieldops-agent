"""DeepSeek API wrapper only, no business logic. Swappable if the provider changes.

Thin wrapper only — no prompt construction, no retry logic. Returns the raw
SDK message object (.content, .tool_calls) unshaped; interpretation is the
caller's job (conversation_service.py).
"""

import os

from openai import OpenAI

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)


def call_model(messages: list[dict], tools: list[dict]):
    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=messages,
        tools=tools,
    )
    return response.choices[0].message
