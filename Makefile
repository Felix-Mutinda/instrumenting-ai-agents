-include .env
export

BACKEND ?= jaeger
LANGFUSE_AUTH := $(shell printf '%s:%s' "$(LANGFUSE_PUBLIC_KEY)" "$(LANGFUSE_SECRET_KEY)" | base64 | tr -d '\n')
export LANGFUSE_AUTH

.PHONY: setup seed up down run replay diff clean

setup:          ## install dependencies
	uv sync

seed:           ## download the NAB series
	uv run python data/seed_nab.py

up:             ## start the Collector (+ Jaeger). BACKEND=jaeger|langfuse
	BACKEND=$(BACKEND) docker compose $(if $(filter jaeger,$(BACKEND)),--profile jaeger) up -d

down:
	docker compose --profile jaeger down

run:            ## run all incidents, or one: make run INCIDENT=inc-103
	uv run python main.py run $(INCIDENT)

replay:         ## replay a recorded run: make replay RUN=<run id>
	uv run python main.py replay $(RUN)

diff:           ## compare two runs: make diff A=<run id> B=<run id>
	uv run python -m replay.diff $(A) $(B)

clean:
	rm -rf runs tickets.jsonl
