# 469er-Bot-Creation

# Yin und Yang core (starter)

Small, reviewable, stdlib-only Python core (Python 3.9+, no third-party dependencies).
It is **not** a finished or error-free production AI.

## Roles
- **Yin und Yang** – coordinator: plans, routes only when a specialist is needed.
- **Visionär** – technical right hand/referee: returns several approaches (incl. one unusual option) with benefit, cost, risks, tests and a trade-off note; returns draft/patch suggestions only; cannot approve (approvals are human-only).
- **AniForge** – isolated minimal placeholder; no store/provider/agent references, no shared data.

## Layout (`yinyang_core/`)
`api.py` HTTP · `orchestrator.py` routing/timeouts/retries · `agents/` · `permissions.py` tiers + approvals · `knowledge.py` SQLite · `audit.py` JSONL log (secrets redacted) · `lifecycle.py` start/stop · `providers.py` model interface · `reports.py` weekly report · `app.py` wiring.

## Autonomy tiers
1. Autonomous: read/analyze/plan/propose/report. 2. Bounded checks/tests in isolation. 3. Approval required: file changes, dependency installs, config changes, deploy. 4. Prohibited unless explicitly approved: delete, disclose confidential data, publish, paid actions. Unknown actions are treated as tier 4. Even when approved, this starter **executes none** of tier 3/4 – it only records the decision. No shell commands are run.

## Install / run / test / stop
```
python -m yinyang_core                          # serves http://127.0.0.1:8469 (nothing to pip install)
python -m unittest discover -v                  # tests
```
Stop with Ctrl+C or SIGTERM: new tasks are refused (503), in-flight tasks get `YY_SHUTDOWN_GRACE_S` seconds, then the store closes. Config is read from environment variables (see `.env.example`; it is not auto-loaded). Runtime data goes to `data/` (git-ignored).

## API
- `GET /health` – state, checks, provider (`is_mock`); 503 unless running.
- `POST /tasks` `{"task": "...", "agent": optional}` – without `agent`, Yin und Yang plans and routes.
- `GET /approvals`, `POST /approvals/{id}/decision` `{"decision":"approve|reject","decided_by":"alice","explicit":false}` – agent names are rejected as deciders.
- `POST /reports/weekly` – generate and store a weekly technical report.

```
curl -s localhost:8469/tasks -d '{"task":"find the performance bottleneck in my code"}'
```

## Weekly report / scheduling
`WeeklyReportService.generate()` (also `POST /reports/weekly`) fetches sources from `YY_REPORT_SOURCES` (`name=https://...`, https only, size/time bounded) and stores the report with sources and retrieval timestamps. **Nothing runs weekly yet.** To schedule later, call the endpoint from cron/a systemd timer, e.g. `0 8 * * 1 curl -X POST localhost:8469/reports/weekly`. It never installs or modifies anything.

## Inventory of mocks / placeholders / limits
- Model provider: **mock only** (`MockProvider`); gives no real AI answers. Other names raise an error. No API keys are read.
- Visionär proposals are static templates, not model-generated analysis.
- AniForge is a placeholder; Yin und Yang routing is keyword-based.
- Approvals are in memory (lost on restart); the HTTP API has no authentication – keep it on localhost.
- Task timeouts are cooperative: a timed-out thread cannot be killed, only abandoned.
- Tier 2 isolated test execution is defined but not implemented.
- Knowledge store accepts only explicitly approved entries (Python API; no HTTP endpoint yet); secret detection is pattern-based and best-effort.
