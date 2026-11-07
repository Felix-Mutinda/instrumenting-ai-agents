"""Entry point.

  python main.py run [INCIDENT]   run one incident (or all), recorded to runs/
  python main.py replay RUN_ID    replay a recorded run, reusing the model's answers
"""

import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

from agent.loop import run_agent  # noqa: E402
from agent.model import ModelClient  # noqa: E402
from replay.record import Recorder, load_run  # noqa: E402
from replay.replay import ReplayModel  # noqa: E402
from telemetry import otel  # noqa: E402

INCIDENTS = yaml.safe_load(Path("incidents.yaml").read_text())


def run(incident_id: str | None) -> None:
    model = ModelClient()
    for incident in INCIDENTS:
        if incident_id and incident["id"] != incident_id:
            continue
        recorder = Recorder(incident, model.model)
        decision = run_agent(incident, model, recorder)
        recorder.decision(decision)
        print(f"{incident['id']}  {decision}")  # the only "log line" the black-box version has
        print(f"  recorded as {recorder.run_id}")


def replay(run_id: str) -> None:
    events = load_run(run_id)
    incident = events[0]["incident"]
    model = ReplayModel(events, ModelClient)
    recorder = Recorder(incident, f"replay of {run_id}", on_tool=model.check_tool)
    decision = run_agent(incident, model, recorder)
    recorder.decision(decision)
    if model.diverged_at is None:
        print("  every tool matched the recording: zero model calls")
    print(f"{incident['id']}  {decision}")
    print(f"  recorded as {recorder.run_id}")


if __name__ == "__main__":
    otel.setup()
    try:
        command = sys.argv[1] if len(sys.argv) > 1 else "run"
        argument = sys.argv[2] if len(sys.argv) > 2 else None
        if command == "replay":
            replay(argument)
        else:
            run(argument or os.getenv("INCIDENT") or None)
    finally:
        otel.shutdown()
