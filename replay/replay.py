"""Replay a recorded run without calling the model.

Tools run for real. While every tool returns what it returned in the recording,
the recorded model replies are still valid, so we reuse them: zero model calls.
The first time a tool returns something different (because you fixed it),
replay switches to the live model from that step on.
"""

import json

from opentelemetry import trace

tracer = trace.get_tracer("triage-agent")


class ReplayModel:
    def __init__(self, events: list[dict], live_model_factory):
        self.replies = [e["reply"] for e in events if e["kind"] == "model"]
        self.tool_results = [e for e in events if e["kind"] == "tool"]
        self.live_model_factory = live_model_factory
        self.live = None
        self.tools_seen = 0
        self.diverged_at = None

    def check_tool(self, event: dict) -> None:
        """Called after each tool runs. Compare it with the recording."""
        if self.live is None:
            recorded = self.tool_results[self.tools_seen] if self.tools_seen < len(self.tool_results) else None
            same = recorded and recorded["name"] == event["name"] and recorded["result"] == event["result"]
            if not same:
                self.diverged_at = event["step"]
                print(f"  tool result changed at step {event['step']} ({event['name']}): switching to the live model")
                self.live = self.live_model_factory()
        self.tools_seen += 1

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        if self.live:
            return self.live.chat(messages, tools)
        reply = self.replies.pop(0)
        with tracer.start_as_current_span("chat (replayed)") as span:
            span.set_attribute("gen_ai.operation.name", "chat")
            span.set_attribute("replay", True)
        return json.loads(json.dumps(reply))  # a copy, so the loop can change it safely
