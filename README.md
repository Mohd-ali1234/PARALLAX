# PARALLAX

**A multi-agent customer support desk, running on a local LLM.**

One message goes in. A supervisor decides which specialist should handle it,
the specialist looks things up with its own tools, and the supervisor reviews
the draft before it reaches the customer. Every stage comes back in the
response, so you can see *why* an answer looks the way it does.

> Status: **working pipeline, canned data.** The agents and routing are real.
> The tools return fixed strings rather than touching live systems — the point
> of this build is to prove the wiring, not the integrations.

---

## The pipeline

```
                 Customer message
                        │
                        ▼
              ┌───────────────────┐
              │  Supervisor Agent │
              └─────────┬─────────┘
                        │  1. ROUTE  (which specialist?)
          ┌─────────────┴─────────────┐
          ▼                           ▼
  ┌───────────────┐           ┌───────────────┐
  │  Mobile Agent │           │ Computer Agent│      (or: none →
  └───────┬───────┘           └───────┬───────┘       supervisor
          │  2. DELEGATE (tool loop)  │               answers directly)
   check_device_status          check_warranty
   lookup_data_plan             lookup_driver_updates
   reset_voicemail_pin          run_hardware_diagnostic
          │                           │
          └─────────────┬─────────────┘
                        ▼
              ┌───────────────────┐
              │  Supervisor Agent │  3. REVIEW (check + write final reply)
              └─────────┬─────────┘
                        ▼
                  Final answer
```

All three agents are the same local model with different system prompts and
different tools — which is what an "agent" is. Each can be pointed at its own
model via `PARALLAX_*_MODEL` if you have more than one pulled.

---

## Quick start

You need a local model server. Ollama is the easiest:

```bash
ollama serve
ollama pull qwen2.5-coder:7b       # or qwen2.5:7b, llama3.1, mistral-nemo
```

Then:

```bash
cp .env.example .env

python -m venv .venv
.venv\Scripts\Activate.ps1          # PowerShell; bash: source .venv/Scripts/activate
pip install -e "./backend[dev]"

cd backend
uvicorn parallax.main:app --reload
```

Open **http://localhost:8000/docs** and use *Try it out* on
`POST /api/v1/support/ask` — easier than fighting shell quoting on Windows.

| Endpoint | What it does |
|---|---|
| `POST /api/v1/support/ask` | Send a customer message, get the reply plus the full trace |
| `GET /api/v1/support/agents` | The agents, their models, and the tools each one holds |
| `GET /api/v1/health/live` | Process is up |
| `GET /api/v1/health/ready` | Process is up *and* the model server answers |

---

## What a response looks like

```jsonc
{
  "answer": "Your laptop is still under warranty until 14 March 2027 ...",
  "route":  { "agent": "computer", "reason": "computer", "fallback_used": false },
  "delegate": {
    "agent": "computer",
    "answer": "Yes, your laptop is under warranty until 14 March 2027 ...",  // the draft
    "steps": [
      { "tool": "check_warranty",
        "arguments": "{\"serial_number\": \"5CD1234ABC\"}",
        "result": "Serial 5CD1234ABC: Dell XPS 15 9520 ... ACTIVE until 14 March 2027 ..." }
    ],
    "iterations": 2,
    "stop_reason": "final_answer",
    "model": "qwen2.5-coder:7b"
  },
  "review": { "note": "Reviewed and rewritten.", "changed": true },
  "stages": ["route -> computer", "computer -> 1 tool call(s)", "review -> final answer"],
  "model": "qwen2.5-coder:7b"
}
```

The trace is not decoration. When an answer is wrong you need to know whether
routing, the tool call, or the review is at fault — `stages` tells you which
stage to look at, and `delegate.answer` vs `answer` shows what the review
changed.

---

## Layout

```
backend/
  pyproject.toml            deps, ruff/mypy/pytest config
  src/parallax/
    main.py                 app factory + ASGI entrypoint
    core/                   settings, logging, domain exceptions
    llm/client.py           OpenAI-compatible chat client
    tools/
      base.py               Tool, ToolRegistry, ToolContext
      mobile.py             3 canned mobile tools
      computer.py           3 canned computer tools
    agents/
      base.py               ToolAgent - the tool-calling loop
      mobile.py             prompt + toolset for the mobile specialist
      computer.py           prompt + toolset for the computer specialist
      supervisor.py         route -> delegate -> review
    api/v1/routes/          health, support
    schemas/support.py      request/response models
  tests/                    54 tests, no model server needed
```

Every path in `backend/pyproject.toml` is relative to that file, so `ruff`,
`mypy` and `pytest` are run from `backend/`.

---

## Design notes

**Each specialist holds its own registry.** The mobile agent physically cannot
call `check_warranty`. Routing mistakes stay contained instead of turning into
an agent using the wrong system.

**Routing is a separate stage, not a tool call.** The supervisor could have
been given the specialists as tools. Three explicit stages were chosen instead
because each one is separately visible in the response — which is the whole
point when you are debugging a pipeline.

**Routing degrades rather than fails.** The router reads the model's reply only
when it is unambiguous: the first word if it is a label, otherwise only when
exactly one label appears. `"this is not a computer issue, it is mobile"` is
rejected rather than read backwards, and a keyword net decides instead, with
`fallback_used: true` in the response so you know it happened.

**Model mistakes are fed back; real breakages are raised.** An unknown tool
name or malformed arguments come back to the model as an observation it can
correct. A dead model server raises a 503 — retrying will not help.

**The review can never blank an answer.** If the review call returns nothing,
the specialist's draft is sent as-is.

---

## The local model

The client speaks the OpenAI-compatible `/v1/chat/completions` API, so the
runtime is a config value, not a code change — Ollama, LM Studio, llama.cpp and
vLLM all work. Point `PARALLAX_LLM_BASE_URL` at whichever you run.

**On tool calling.** Some models advertise tool support and then write the call
into the message text instead of the `tool_calls` field. `qwen2.5-coder:7b` does
exactly this. The client recovers those: if the text parses as JSON naming a
tool that was actually offered, it is promoted to a real call. Anything else is
left alone, so a genuine answer is never mistaken for a call. `qwen2.5`,
`llama3.1` and `mistral-nemo` need no such help.

If `steps` comes back empty on a question that clearly needed a lookup, the
model is not really using its tools.

---

## Tests

```bash
cd backend
pytest
```

54 tests, no skips, no model server, no network — every LLM call is stubbed with
scripted turns. What is under test is the pipeline: routing, delegation, tool
error recovery, the iteration cap, review fallbacks, and the HTTP surface.

```bash
ruff check src tests && ruff format --check src tests && mypy
```

---

## Making a tool real

The tools are the only fake part. Each returns a fixed string; replace the body
and nothing else in the pipeline changes:

```python
@registry.tool(name="check_warranty", description="...", parameters={...})
async def check_warranty(ctx: ToolContext, serial_number: str) -> str:
    return await crm.warranty_for(serial_number)     # was: a canned string
```

`ToolContext` is the seam for what a tool is allowed to reach. It carries only a
request id today; a database handle or HTTP client goes there, so adding one is
a change to that class rather than to every tool signature.
