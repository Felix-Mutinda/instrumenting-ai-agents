"""Tracing setup and the three spans we add by hand.

Auto-instrumentation (OpenInference) creates a span for every model call.
We add the rest: one span for the agent run, one per loop step, one per tool call.
"""

import json
import os
from contextlib import contextmanager

from opentelemetry import trace

tracer = trace.get_tracer("triage-agent")


def setup() -> None:
    if os.getenv("TRACING") != "on":
        return  # no provider: every span below becomes a no-op

    from openinference.instrumentation.openai import OpenAIInstrumentor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": "triage-agent"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))  # reads OTEL_EXPORTER_OTLP_ENDPOINT
    trace.set_tracer_provider(provider)
    OpenAIInstrumentor().instrument(tracer_provider=provider)


def shutdown() -> None:
    provider = trace.get_tracer_provider()
    if hasattr(provider, "shutdown"):
        provider.shutdown()  # flush spans before the process exits


@contextmanager
def run_span(incident: dict):
    with tracer.start_as_current_span("invoke_agent triage_agent") as span:
        span.set_attribute("gen_ai.operation.name", "invoke_agent")
        span.set_attribute("gen_ai.agent.name", "triage_agent")
        span.set_attribute("incident.id", incident["id"])
        span.set_attribute("incident.metric", incident["metric"])
        yield span


@contextmanager
def step_span(index: int):
    with tracer.start_as_current_span("agent.step") as span:
        span.set_attribute("agent.step.index", index)
        yield span


@contextmanager
def tool_span(name: str, arguments: str):
    with tracer.start_as_current_span(f"execute_tool {name}") as span:
        span.set_attribute("gen_ai.operation.name", "execute_tool")
        span.set_attribute("gen_ai.tool.name", name)
        # Arguments are small and safe here. Record what was asked for...
        for key, value in json.loads(arguments or "{}").items():
            span.set_attribute(f"tool.args.{key}", str(value))
        yield span


def record_tool_result(span, result: dict) -> None:
    """...and what came back. (Tools that read data also record which data, as tool.data.*)"""
    if "error" in result:
        span.set_attribute("error.type", "tool_error")
        span.set_status(trace.Status(trace.StatusCode.ERROR, result["error"]))
    for key in ("count", "anomaly", "max_score"):
        if key in result:
            span.set_attribute(f"tool.result.{key}", str(result[key]))
