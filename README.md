# Instrumenting AI Agents

Companion code for **Part 1** of the *AI System Design* series: how to see what an AI agent actually did, using OpenTelemetry.

The agent triages monitoring alerts over real AWS CloudWatch data from the [Numenta Anomaly Benchmark](https://github.com/numenta/NAB). It has four tools: fetch a metric window, check it for anomalies, look up a runbook, and open a ticket. One of the three alerts goes wrong, and the article uses the trace to find out why.

## What you need

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Docker
- A free [OpenRouter](https://openrouter.ai) API key (no local model needed)

The free tier allows 50 model requests a day. One incident costs about 4 requests, and replays cost none, so a free key is plenty for everything below.

## Setup

```bash
cp .env.example .env      # add your OpenRouter key
make setup                # install dependencies
make seed                 # download three NAB series into data/series/
```

## 1. The black box

```bash
make run
```

Three alerts, three one-line decisions. The third one (`inc-103`) is closed as a false alarm. Is that right? The output can't tell you.

## 2. Turn tracing on

```bash
make up                         # Collector + Jaeger
make run INCIDENT=inc-103 TRACING=on
```

Open Jaeger at http://localhost:16686 and pick the `triage-agent` service. One run is one tree: the agent run, each step, each model call, each tool call.

Look at the `fetch_metric_window` span. `tool.args.start` says it asked for **25 April**. `tool.data.start` says the data it actually used was from **23–24 April**. The tool had no data for the requested window and quietly fell back to the latest data it had, without telling the agent. The model judged the alert on the wrong day, and only the trace shows it.

## 3. Same trace, different tool

The agent only talks to the Collector. To send the same trace to Langfuse instead, add your Langfuse keys to `.env` and change one word:

```bash
make down
make up BACKEND=langfuse
make run INCIDENT=inc-103 TRACING=on
```

The Collector also removes prompt and completion text before anything leaves your machine, and maps library-specific attribute names to the standard GenAI ones. See `collector/base.yaml`.

## 4. Replay and fix

Every run is recorded to `runs/`. Replaying reruns the tools but reuses the model's recorded answers, so it costs no model requests:

```bash
make replay RUN=<run id from step 2>
```

Now apply the fix (the tool reports missing data instead of falling back) and replay again. When a tool result changes, replay switches to the live model from that point:

```bash
make replay RUN=<same run id> TOOL_FIX=1
make diff A=<original run id> B=<new run id>
```

The diff points at the first thing that changed: the `fetch_metric_window` result.

## Layout

```text
agent/        the loop, the model client and the four tools
telemetry/    tracing setup and the spans added by hand
replay/       record, replay and diff
collector/    Collector config: one shared file plus one per backend
data/         NAB download script
incidents.yaml
```

## Notes

- **The GenAI conventions are not stable yet.** OpenTelemetry's GenAI semantic conventions are still in development status, so attribute names can change. Instrumentation versions are pinned in `pyproject.toml`; the Collector's rename step absorbs drift between libraries.
- **Free models change.** If the model in `.env.example` disappears from OpenRouter, pick another free model that supports tool calling. Results vary between models; the trace is how you see the difference.
- **Prompt data.** Some free providers may use prompts for training. Everything this agent sends is public benchmark data.
- NAB data © Numenta, used under its licence. Code in this repo is MIT.

**Next:** Part 2 gives the agent a searchable knowledge base, and the trace starts showing what it read, not just what it called.
