# Patchwork

**Made by Harth Khalid.**

Patchwork is a full-stack, AI-assisted code review service for GitHub Pull Requests. A GitHub App receives webhooks, enqueues work on Redis, and a worker fetches the PR diff, runs an OpenAI prompt pipeline with **versioned templates**, posts **line-level review comments**, and exposes a **React dashboard** for PR health, **false-positive analytics**, and **developer feedback** that tightens prompts over time.

## Stack test

| Layer | Technology |
| --- | --- |
| API | Python 3.12, FastAPI |
| AI | OpenAI API (`gpt-4o` by default; configurable) |
| Queue + rate limits | Redis (LPUSH/BRPOP queue + sorted-set RPM windows) |
| Persistence | SQLite (async SQLAlchemy) for feedback + analytics |
| UI | React (Vite), nginx in Docker |
| Ops | Docker Compose (api, worker, web, redis) |

## Repository layout

```
PatchWork/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, CORS, /install redirect
│   │   ├── config.py               # Settings (env)
│   │   ├── database.py             # Async SQLAlchemy engine
│   │   ├── models.py               # Feedback, PR runs, star counter
│   │   ├── routers/
│   │   │   ├── webhooks.py         # POST /webhooks/github (GitHub App)
│   │   │   └── api.py              # Dashboard API, stars, feedback, analytics
│   │   └── services/
│   │       ├── github_app.py       # JWT + webhook HMAC
│   │       ├── github_client.py    # Diff + PR review comments
│   │       ├── webhook_queue.py    # Redis queue
│   │       ├── rate_limit.py       # Sliding-window RPM
│   │       ├── prompts.py          # Load versioned YAML prompts
│   │       ├── openai_pipeline.py  # GPT call + confidence filter
│   │       ├── false_positive_tracker.py
│   │       ├── prompt_eval.py      # FP rate vs target (<8%)
│   │       └── pr_processor.py     # End-to-end job
│   ├── prompts/
│   │   ├── v1.yaml
│   │   └── v2.yaml                 # Default: FP-focused
│   ├── worker.py                   # Redis consumer
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   └── requirements.txt
├── frontend/
│   ├── src/                        # Dashboard + feedback UI
│   ├── index.html                  # SEO / Open Graph / Twitter meta
│   ├── nginx.conf                  # Reverse proxy /api → api:8000
│   └── Dockerfile
├── scripts/
│   └── simulate_beta_feedback.py   # 300+ synthetic feedback POSTs
├── docker-compose.yml
├── .env.example
└── README.md
```

## Prompt engineering strategy (versioned + evaluation)

1. **Versioned templates** live under `backend/prompts/v*.yaml`. Each file defines `system`, `user_template`, and metadata. `ACTIVE_PROMPT_VERSION` (default `v2`) selects which file loads at runtime.
2. **False-positive controls in v2**: explicit exclusions (no hypothetical secrets), evidence requirement, severity calibration, JSON-only output, and a **confidence score** per finding.
3. **Post-processing** in `openai_pipeline.py`: drop findings below a confidence threshold; dampen low-severity “info” noise unless confidence is high.
4. **Evaluation** (`prompt_eval.py`, `/api/analytics/prompt-eval`): false positive rate = `false_positive / (false_positive + correct)` on labeled feedback, compared to a **target of 8%** (`meets_target` flag).
5. **Feedback loop**: developers submit “correct” vs “false positive” via `/api/feedback` (dashboard). Aggregate per-repo stats power `/api/analytics/repos` and global `/api/analytics/fp-rate`.
6. **Iteration workflow**: ship `v3.yaml`, bump `ACTIVE_PROMPT_VERSION`, A/B using `prompt_version` on feedback rows, and retire versions that fail the FP target on sufficient sample size.

## Local development

### Prerequisites

- Python 3.12+, Docker / Docker Compose (recommended for full stack)
- OpenAI API key
- (Optional) GitHub App credentials for live webhooks

### Backend only

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
# Redis must be reachable at REDIS_URL (default redis://localhost:6379/0)
set DATABASE_URL=sqlite+aiosqlite:///./patchwork.db
set REDIS_URL=redis://localhost:6379/0
set OPENAI_API_KEY=sk-...
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
cd backend
set REDIS_URL=redis://localhost:6379/0
set DATABASE_URL=sqlite+aiosqlite:///./patchwork.db
set OPENAI_API_KEY=sk-...
python worker.py
```

### Frontend only

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api` and `/install` to `http://localhost:8000` (see `vite.config.ts`).

### Docker Compose (API + worker + Redis + nginx UI)

Create a `.env` file in the project root (Compose reads it for variable substitution). You can start from `.env.example`.

```bash
copy .env.example .env
# Edit .env: set OPENAI_API_KEY and GitHub secrets if testing webhooks
docker compose up --build
```

- Dashboard: `http://localhost:8080`
- API docs: `http://localhost:8000/docs` (or via nginx if you add a route)
- Raw API: `http://localhost:8000`

SQLite and Redis data use named volumes (`patchwork_data`, `redis_data`).

## Environment variables

See `.env.example`. Key variables:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Required for analysis |
| `OPENAI_MODEL` | Default `gpt-4o` |
| `OPENAI_API_BASE_URL` | OpenAI-compatible API root (default `https://api.openai.com/v1`) |
| `GITHUB_APP_ID` | GitHub App ID |
| `GITHUB_WEBHOOK_SECRET` | Verifies `X-Hub-Signature-256` |
| `GITHUB_PRIVATE_KEY` or `GITHUB_PRIVATE_KEY_PATH` | App private key (PEM) |
| `GITHUB_APP_SLUG` | Used by `/install` redirect (`https://github.com/apps/<slug>/installations/new`) |
| `PUBLIC_BASE_URL` | Shown in PR comment footers and badge links |
| `REDIS_URL` | Queue + rate limiting |
| `DATABASE_URL` | Async SQLite URL |
| `ACTIVE_PROMPT_VERSION` | e.g. `v2` |
| `CORS_ORIGINS` | Comma-separated origins for the dashboard |

## Deploying as a GitHub App

1. **Create the App** (GitHub → Settings → Developer settings → GitHub Apps → New GitHub App).
2. **Webhook URL**: `https://<your-public-host>/webhooks/github` (HTTPS required in production).
3. **Webhook secret**: set `GITHUB_WEBHOOK_SECRET` to the same value.
4. **Permissions** (minimum reasonable set for PR review):
   - Repository permissions: **Pull requests** — Read & write (post review comments); **Contents** — Read (diffs); **Metadata** — Read (always on).
   - Optionally **Issues** — Read & write if you want issue comments as fallback when line anchoring fails.
5. **Subscribe to events**:
   - `pull_request` (opened, synchronize, reopened, ready for review)
   - `issue_comment` (optional: re-queue when a comment mentions “patchwork”)
6. **Install** the app on accounts/orgs that should use Patchwork.
7. Set `GITHUB_APP_ID`, private key, and `GITHUB_APP_SLUG` in the environment.

Public URL must match what developers see in PR footers (`PUBLIC_BASE_URL`).

## “Install on GitHub” badge

- **Redirect flow**: `GET /install` → `https://github.com/apps/<GITHUB_APP_SLUG>/installations/new`.
- **SVG badge**: `GET /api/badge/install.svg` (green “install” badge; embed in docs or README).

Example Markdown:

```markdown
[![Install Patchwork](http://localhost:8080/api/badge/install.svg)](http://localhost:8080/install)
```

(Replace host with your production URL.)

## API highlights

| Endpoint | Description |
| --- | --- |
| `POST /webhooks/github` | GitHub App webhooks (signature verified) |
| `GET /api/health` | Liveness |
| `GET /api/stars` | “500+ stars” style counter (seed **512**, demo metric) |
| `POST /api/stars/increment` | Bump counter (demo) |
| `GET /api/analytics/fp-rate` | Global FP rate; `?repo=org/name` for per-repo |
| `GET /api/analytics/repos` | FP rate per repository |
| `GET /api/analytics/prompt-eval` | FP rate + `<8%` target flag for a prompt version |
| `GET /api/prompts/versions` | Available YAML prompt versions |
| `POST /api/feedback` | Label a finding as correct / false positive |
| `GET /api/prs/recent` | Recent PR analysis runs + health scores |

## Simulated beta feedback (300+ events)

With the API running:

```bash
pip install httpx
python scripts/simulate_beta_feedback.py --base-url http://localhost:8000 --count 320
```

Uses concurrent POSTs to `/api/feedback` with mixed verdicts (~22% false positive) to exercise analytics.

## Security notes

- Never commit `.env` or private keys.
- Keep webhook secrets random and rotate if leaked.
- The worker uses installation tokens scoped to each repository installation.

## License

MIT (add a `LICENSE` file if you redistribute).
