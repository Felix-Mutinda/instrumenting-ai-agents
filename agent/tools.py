"""The four tools the triage agent can call.

Each tool is a plain Python function plus a JSON schema the model sees.
"""

import csv
import json
import os
import statistics
from datetime import datetime
from pathlib import Path

from opentelemetry import trace

SERIES_DIR = Path(__file__).parent.parent / "data" / "series"
TICKETS = Path(__file__).parent.parent / "tickets.jsonl"
FMT = "%Y-%m-%d %H:%M"


def _load(metric: str) -> list[tuple[datetime, float]]:
    with open(SERIES_DIR / f"{metric}.csv") as f:
        return [(datetime.strptime(r["timestamp"][:16], FMT), float(r["value"])) for r in csv.DictReader(f)]


def _window(metric: str, start: str, end: str) -> list[float]:
    """Return the data points for the requested window."""
    rows = _load(metric)
    t0, t1 = datetime.strptime(start, FMT), datetime.strptime(end, FMT)
    points = [v for t, v in rows if t0 <= t <= t1]

    if not points:
        if os.getenv("TOOL_FIX") == "1":
            # The fix: say there is no data instead of guessing.
            raise ValueError(f"no data for {metric} between {start} and {end}")
        # THE BUG: a "helpful" fallback that quietly uses the latest data instead.
        # The caller is never told: the result looks like the window it asked for.
        last = rows[-1][0]
        t1, t0 = last, last - (t1 - t0)
        points = [v for t, v in rows if t0 <= t <= t1]

    # The tool tells its own span which data it really used. The model never sees this.
    span = trace.get_current_span()
    span.set_attribute("tool.data.start", t0.strftime(FMT))
    span.set_attribute("tool.data.end", t1.strftime(FMT))
    return points


def fetch_metric_window(metric: str, start: str, end: str) -> dict:
    points = _window(metric, start, end)
    return {
        "metric": metric,
        "count": len(points),
        "min": round(min(points), 2),
        "max": round(max(points), 2),
        "mean": round(statistics.mean(points), 2),
    }


def check_anomaly(metric: str, start: str, end: str) -> dict:
    """Compare the window against the whole series; flag points over 3 standard deviations."""
    baseline = [v for _, v in _load(metric)]
    mean, std = statistics.mean(baseline), statistics.pstdev(baseline)
    points = _window(metric, start, end)
    scores = [abs(v - mean) / std for v in points]
    return {
        "metric": metric,
        "anomaly": max(scores) > 3,
        "max_score": round(max(scores), 2),
        "points_over_threshold": sum(s > 3 for s in scores),
    }


RUNBOOKS = {
    "cpu": "CPU alert: confirm the spike in the data, check recent deploys, then open a ticket if sustained.",
    "network": "Network alert: confirm the spike in the data, check for traffic events, then open a ticket if sustained.",
}


def lookup_runbook(metric_type: str) -> dict:
    return {"metric_type": metric_type, "runbook": RUNBOOKS.get(metric_type, "No runbook found.")}


def open_ticket(incident_id: str, severity: str, summary: str) -> dict:
    ticket = {"incident_id": incident_id, "severity": severity, "summary": summary}
    with open(TICKETS, "a") as f:
        f.write(json.dumps(ticket) + "\n")
    return {"opened": True, **ticket}


TOOLS = {
    "fetch_metric_window": fetch_metric_window,
    "check_anomaly": check_anomaly,
    "lookup_runbook": lookup_runbook,
    "open_ticket": open_ticket,
}

_window_args = {
    "type": "object",
    "properties": {
        "metric": {"type": "string"},
        "start": {"type": "string", "description": "YYYY-MM-DD HH:MM"},
        "end": {"type": "string", "description": "YYYY-MM-DD HH:MM"},
    },
    "required": ["metric", "start", "end"],
}


def _schema(name: str, description: str, parameters: dict) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}


SCHEMAS = [
    _schema("fetch_metric_window", "Summary statistics for a metric over a time window.", _window_args),
    _schema("check_anomaly", "Check whether a metric window is anomalous against its history.", _window_args),
    _schema(
        "lookup_runbook",
        "Get the runbook for an alert type.",
        {"type": "object", "properties": {"metric_type": {"type": "string", "enum": ["cpu", "network"]}}, "required": ["metric_type"]},
    ),
    _schema(
        "open_ticket",
        "Open an incident ticket. Only call this when the data confirms an anomaly.",
        {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
                "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                "summary": {"type": "string"},
            },
            "required": ["incident_id", "severity", "summary"],
        },
    ),
]


def call_tool(name: str, arguments: str) -> dict:
    """Run a tool from the model's request. Errors go back to the model as data, not exceptions."""
    try:
        return TOOLS[name](**json.loads(arguments))
    except Exception as e:  # the model should see the failure and decide what to do
        return {"error": str(e)}
