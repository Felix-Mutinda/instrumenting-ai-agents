"""One client for any OpenAI-compatible endpoint (OpenRouter by default)."""

import os

from openai import OpenAI


class ModelClient:
    def __init__(self):
        self.model = os.environ["MODEL"]
        self.client = OpenAI(base_url=os.environ["BASE_URL"], api_key=os.environ["OPENROUTER_API_KEY"])

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        response = self.client.chat.completions.create(model=self.model, messages=messages, tools=tools)
        message = response.choices[0].message
        return {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in (message.tool_calls or [])
            ],
        }
