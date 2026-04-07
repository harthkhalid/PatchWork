# Patchwork

**Made by Harth Khalid.**

## What is Patchwork?

Patchwork helps you review code on **GitHub**. When someone opens or updates a **pull request** (a set of code changes), Patchwork can:

- Read what changed
- Use **OpenAI** to look for security issues, messy code patterns, and slow code
- Leave **comments on exact lines** in the pull request
- Show a **simple web page** with scores, stats, and a way to say “this comment was right” or “this was a false alarm”

You run it on your own computer or server. It talks to GitHub through a small app you install on GitHub.

## What tools does it use?

| Part | What we use |
| --- | --- |
| Server code | Python 3.12 and FastAPI |
| Smart review | OpenAI (default model: `gpt-4o`; you can change it) |
| Waiting line for jobs | Redis |
| Saved data | SQLite (feedback and stats) |
| Web page | React, built with Vite |
| Easy run-everything setup | Docker Compose |

## Folder map (where things live)

```
PatchWork/
├── backend/          # Server: webhooks, API, review logic
├── frontend/         # Dashboard web page
├── scripts/          # Helper scripts (e.g. test feedback)
├── docker-compose.yml
├── .env.example      # Copy to .env and fill in your keys
└── README.md
```

Main server files live under `backend/app/`. Review rules live in `backend/prompts/` as YAML files (`v1.yaml`, `v2.yaml`).

## How do the review rules work?

1. Rules are **text files** in `backend/prompts/`. You can have more than one version (v1, v2, …).
2. Setting **`ACTIVE_PROMPT_VERSION`** picks which file is used (default is `v2`).
3. **v2** is written to cut down **false alarms** (wrong warnings). It asks for proof from the diff and a **confidence** score.
4. After the model answers, code in **`openai_pipeline.py`** drops low-confidence items so fewer noisy comments get posted.
5. We track **false alarm rate** from team feedback. The goal is to stay **under 8%** false alarms on labeled data.
6. Developers use the dashboard or API to mark comments **correct** or **false positive**. That helps you see which prompt version works best.

## Run it on your computer

### What you need

- **Python 3.12+** and **Docker** (Docker is the easiest way to run everything)
- An **OpenAI API key** (from OpenAI’s site)
- Optional: a **GitHub App** if you want real pull requests from GitHub to trigger reviews

### Run only the server (no Docker)

**Terminal 1 — API:**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set DATABASE_URL=sqlite+aiosqlite:///./patchwork.db
set REDIS_URL=redis://localhost:6379/0
set OPENAI_API_KEY=your_key_here
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — worker** (this process does the actual reviews):

```bash
cd backend
.venv\Scripts\activate
set REDIS_URL=redis://localhost:6379/0
set DATABASE_URL=sqlite+aiosqlite:///./patchwork.db
set OPENAI_API_KEY=your_key_here
python worker.py
```

Redis must be running (for example from Docker: `docker run -p 6379:6379 redis`).

### Run only the web page

```bash
cd frontend
npm install
npm run dev
```

The dev server sends `/api` requests to `http://localhost:8000`.

### Run everything with Docker (simplest)

1. Copy `.env.example` to `.env`.
2. Put your **OpenAI** key in `.env`. Add GitHub App values if you use webhooks.
3. Run:

```bash
docker compose up --build
```

Then open:

- **Dashboard:** http://localhost:8080  
- **API help page:** http://localhost:8000/docs  

## Settings in `.env` (short list)

| Name | Plain meaning |
| --- | --- |
| `OPENAI_API_KEY` | Your OpenAI key (needed for reviews) |
| `OPENAI_MODEL` | Which model to call (default `gpt-4o`) |
| `OPENAI_API_BASE_URL` | API web address (default is OpenAI’s) |
| `GITHUB_APP_ID` | Your GitHub App’s ID |
| `GITHUB_WEBHOOK_SECRET` | Secret GitHub sends with webhooks; must match your server |
| `GITHUB_PRIVATE_KEY` or `GITHUB_PRIVATE_KEY_PATH` | Your app’s private key file |
| `GITHUB_APP_SLUG` | Short name in the GitHub app URL |
| `PUBLIC_BASE_URL` | Your site’s public address (used in PR comment links) |
| `REDIS_URL` | Where Redis runs |
| `DATABASE_URL` | Where SQLite file lives |
| `ACTIVE_PROMPT_VERSION` | Which prompt file to use (e.g. `v2`) |
| `CORS_ORIGINS` | Web addresses allowed to call the API from a browser |

Full example: see **`.env.example`**.

## Hook up GitHub (GitHub App)

1. On GitHub: **Settings → Developer settings → GitHub Apps → New GitHub App**.
2. **Webhook URL:** `https://YOUR_DOMAIN/webhooks/github` (use **https** in production).
3. **Webhook secret:** same value you put in `GITHUB_WEBHOOK_SECRET`.
4. **Permissions** (good starting point):
   - **Pull requests:** read and write (to post comments)
   - **Contents:** read (to see code changes)
   - **Metadata:** read (usually on by default)
   - Optional: **Issues** read/write if you want fallback comments on issues
5. **Events to turn on:** pull request (opened, updated, reopened, ready for review). Optional: issue comments if you want comments that say “patchwork” to trigger a new run.
6. **Install** the app on your user or organization.
7. Put `GITHUB_APP_ID`, the private key, and `GITHUB_APP_SLUG` in your `.env`.

Set **`PUBLIC_BASE_URL`** to the same public site people will open from pull request links.

## “Install on GitHub” button

- Visiting **`/install`** sends people to install your GitHub App.
- **`/api/badge/install.svg`** is a small green badge image you can put in docs.

Example (change the host to yours):

```markdown
[![Install Patchwork](https://YOUR_SITE/api/badge/install.svg)](https://YOUR_SITE/install)
```

## Main API paths (for builders)

| Path | What it does |
| --- | --- |
| `POST /webhooks/github` | GitHub sends events here |
| `GET /api/health` | Quick “is the server up?” check |
| `GET /api/stars` | Demo star counter (starts at 512) |
| `POST /api/stars/increment` | Add one to the demo counter |
| `GET /api/analytics/fp-rate` | False alarm rate (add `?repo=org/name` for one repo) |
| `GET /api/analytics/repos` | False alarm rate per repo |
| `GET /api/analytics/prompt-eval` | How a prompt version scores vs the 8% goal |
| `GET /api/prompts/versions` | List prompt versions |
| `POST /api/feedback` | Send “correct” or “false positive” for a finding |
| `GET /api/prs/recent` | Recent review runs and health scores |

## Fake feedback for testing

To load many test labels into the database (needs the API running):

```bash
pip install httpx
python scripts/simulate_beta_feedback.py --base-url http://localhost:8000 --count 320
```

## Stay safe

- Do **not** put `.env` or private keys in Git.
- Use a long random **webhook secret**. Change it if it leaks.
- The worker only uses GitHub’s **installation token** for repos where the app is installed.

## License

MIT. Add a `LICENSE` file if you share the project widely.
