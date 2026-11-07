"""Record every model reply and tool result of a run to runs/<run_id>.jsonl."""

import json
from datetime import datetime, timezone
from pathlib import Path

RUNS = Path(__file__).parent.parent / "runs"


class Recorder:
    def __init__(self, incident: dict, model_name: str, on_tool=None):
        RUNS.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.run_id = f"{stamp}-{incident['id']}"
        n = 2
        while (RUNS / f"{self.run_id}.jsonl").exists():  # two runs in the same second
            self.run_id = f"{stamp}-{incident['id']}-{n}"
            n += 1
        self.path = RUNS / f"{self.run_id}.jsonl"
        self.on_tool = on_tool  # replay uses this to notice when a tool result changes
        self._write({"kind": "run", "incident": incident, "model": model_name})

    def _write(self, event: dict) -> None:
        with open(self.path, "a") as f:
            f.write(json.dumps(event) + "\n")

    def model(self, step: int, reply: dict) -> None:
        self._write({"kind": "model", "step": step, "reply": reply})

    def tool(self, step: int, name: str, arguments: str, result: dict) -> None:
        event = {"kind": "tool", "step": step, "name": name, "arguments": arguments, "result": result}
        self._write(event)
        if self.on_tool:
            self.on_tool(event)

    def decision(self, text: str) -> None:
        self._write({"kind": "decision", "text": text})


def load_run(run_id: str) -> list[dict]:
    return [json.loads(line) for line in open(RUNS / f"{run_id}.jsonl")]
