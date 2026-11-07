"""The agent loop: ask the model, run the tools it asks for, repeat until it answers."""

import json

from agent.tools import SCHEMAS, call_tool
from telemetry.otel import record_tool_result, run_span, step_span, tool_span

MAX_STEPS = 8

SYSTEM = """You are an on-call triage agent. For each alert:
1. Fetch the metric window and check it for anomalies.
2. Look up the runbook.
3. If the data confirms an anomaly, open a ticket. If not, close the alert as a false alarm.
Finish with one line: DECISION: <ticket opened | false alarm | cannot verify> - <reason>."""


def run_agent(incident: dict, model, recorder) -> str:
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": f"Alert {incident['id']}: {incident['alert']}. Metric: {incident['metric']}. "
            f"Window: {incident['start']} to {incident['end']}.",
        },
    ]

    with run_span(incident) as run:
        for step in range(1, MAX_STEPS + 1):
            with step_span(step):
                reply = model.chat(messages, SCHEMAS)
                recorder.model(step, reply)

                calls = reply.pop("tool_calls")
                if calls:
                    reply["tool_calls"] = calls  # only send tool_calls back when there are some
                messages.append(reply)

                if not calls:
                    run.set_attribute("agent.steps", step)
                    return reply["content"]

                for call in calls:
                    name, args = call["function"]["name"], call["function"]["arguments"]
                    with tool_span(name, args) as span:
                        result = call_tool(name, args)
                        record_tool_result(span, result)
                    recorder.tool(step, name, args, result)
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})

        run.set_attribute("agent.steps", MAX_STEPS)
        return "DECISION: cannot verify - step limit reached"
