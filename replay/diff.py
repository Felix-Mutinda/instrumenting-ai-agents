"""Show where two recorded runs first differ."""

import sys

from replay.record import load_run


def describe(event: dict) -> str:
    if event["kind"] == "model":
        calls = [c["function"]["name"] for c in event["reply"].get("tool_calls", [])]
        return f"model asks for {calls}" if calls else f"model answers: {event['reply']['content'][:80]}"
    if event["kind"] == "tool":
        return f"{event['name']} -> {event['result']}"
    return event.get("text", "")


def main(a: str, b: str) -> None:
    run_a = [e for e in load_run(a) if e["kind"] != "run"]
    run_b = [e for e in load_run(b) if e["kind"] != "run"]

    for i, (x, y) in enumerate(zip(run_a, run_b)):
        same = x["kind"] == y["kind"] and describe(x) == describe(y)
        mark = "  same " if same else "DIFFERS"
        print(f"{mark}  step {x.get('step', '-')}  {x['kind']}")
        if not same:
            print(f"    A: {describe(x)}")
            print(f"    B: {describe(y)}")
            return
    print("No difference in the shared part of the two runs.")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
