# Railway Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy the full NextMove stack (FastAPI backend + RQ worker + Next.js frontend + PostgreSQL + Redis) to Railway with zero-downtime deploys and automatic migrations on every push.

**Architecture:** Five Railway services in one project — two managed plugins (Postgres, Redis) and three code services (backend API, RQ worker, Next.js frontend). The backend Dockerfile is shared between the API and worker services; they differ only in their start command. Alembic migrations run automatically as a release command before the backend starts.

**Tech Stack:** Railway (PaaS), Docker (backend/worker), Nixpacks (frontend), PostgreSQL 16, Redis 7, FastAPI, Next.js 16

---

## Task 1: Harden the backend Dockerfile

The existing Dockerfile has no CMD — Railway will reject it.

**Files:**
- Modify: `backend/Dockerfile`

**Step 1: Replace the Dockerfile contents**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

> The `alembic upgrade head` in CMD means migrations run on every deploy before traffic is accepted. This is safe because Alembic is idempotent.

**Step 2: Commit**

```bash
git add backend/Dockerfile
git commit -m "deploy: add CMD to backend Dockerfile with migration step"
```

---

## Task 2: Add railway.toml for the backend service

Railway reads `railway.toml` from the service's root. The backend root is `backend/`.

**Files:**
- Create: `backend/railway.toml`

**Step 1: Create the file**

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
healthcheckPath = "/health"
healthcheckTimeout = 30
```

> `healthcheckPath` requires a `/health` endpoint — verified in Task 3.

**Step 2: Commit**

```bash
git add backend/railway.toml
git commit -m "deploy: add backend railway.toml"
```

---

## Task 3: Verify /health endpoint exists in the backend

Railway uses the healthcheck to decide when a deploy is live.

**Files:**
- Read: `backend/app/main.py`

**Step 1: Check if `/health` exists**

Open `backend/app/main.py` and search for `@app.get("/health"`. If it exists, skip to Task 4.

**Step 2: If missing, add it**

Find the FastAPI app instantiation block and add immediately after:

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

**Step 3: Commit if you changed anything**

```bash
git add backend/app/main.py
git commit -m "deploy: add /health endpoint for Railway healthcheck"
```

---

## Task 4: Add railway.toml for the RQ worker service

The worker uses the same Docker image as the backend but runs `rq worker` instead.

**Files:**
- Create: `backend/worker.railway.toml`

> Railway doesn't support multiple `railway.toml` files per directory. The worker is deployed as a **second Railway service** pointing at the same GitHub repo + `backend/` root directory. You override the start command in the Railway UI (see Task 8).

No file needed here — the override is set in the Railway dashboard. Continue to Task 5.

---

## Task 5: Add railway.toml for the frontend

**Files:**
- Create: `frontend/railway.toml`

**Step 1: Create the file**

```toml
[build]
builder = "NIXPACKS"

[deploy]
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
startCommand = "npm run start"
```

**Step 2: Commit**

```bash
git add frontend/railway.toml
git commit -m "deploy: add frontend railway.toml"
```

---

## Task 6: Generate a secure FERNET_KEY for production

The backend warns about the missing `FERNET_KEY`. Generate one now so you have it ready for Task 9.

**Step 1: Run in terminal**

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Step 2: Copy the output** — you'll paste it as an env var in Task 9. It looks like:

```
abc123XYZ...= (44 characters, base64)
```

**Step 3: Also generate a strong JWT secret**

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy that too.

---

## Task 7: Push the repo to GitHub

Railway deploys from GitHub. Skip this task if the repo is already on GitHub.

**Step 1: Create a repo on GitHub**

Go to github.com → New repository → name it `nextmove` → private → no README → Create.

**Step 2: Push**

```bash
git remote add origin git@github.com:YOUR_USERNAME/nextmove.git
git branch -M main
git push -u origin main
```

---

## Task 8: Create the Railway project and services

This is all done in the Railway web UI at railway.app.

**Step 1: Sign up / log in at railway.app**

**Step 2: Create a new project**

Click **New Project** → **Empty Project** → name it `nextmove`.

**Step 3: Add PostgreSQL plugin**

Inside the project → **+ New** → **Database** → **Add PostgreSQL**. Railway provisions it instantly. Click the Postgres service → **Variables** tab → copy the value of `DATABASE_URL` (starts with `postgresql://`).

**Step 4: Add Redis plugin**

**+ New** → **Database** → **Add Redis**. Click the Redis service → **Variables** → copy `REDIS_URL` (starts with `redis://`).

**Step 5: Add the backend API service**

**+ New** → **GitHub Repo** → authorize Railway to access your repo → select `nextmove`.

In the service settings:
- **Root Directory:** `backend`
- **Service Name:** `nextmove-api`
- Leave start command blank (uses Dockerfile CMD)

**Step 6: Add the RQ worker service**

**+ New** → **GitHub Repo** → select `nextmove` again.

In the service settings:
- **Root Directory:** `backend`
- **Service Name:** `nextmove-worker`
- **Start Command:** `rq worker --url $REDIS_URL`

> Railway uses the same Dockerfile but overrides the CMD with your start command.

**Step 7: Add the frontend service**

**+ New** → **GitHub Repo** → select `nextmove`.

In the service settings:
- **Root Directory:** `frontend`
- **Service Name:** `nextmove-frontend`
- Leave start command blank (uses Nixpacks + `npm run start`)

**Step 8: Generate a public domain for the frontend**

Click `nextmove-frontend` service → **Settings** → **Networking** → **Generate Domain**. Copy the URL (e.g. `nextmove-frontend-production.up.railway.app`). You need this for `NEXTAUTH_URL`.

**Step 9: Generate a public domain for the backend API**

Click `nextmove-api` service → **Settings** → **Networking** → **Generate Domain**. Copy it (e.g. `nextmove-api-production.up.railway.app`). You need this for `NEXT_PUBLIC_API_URL` and the Telegram webhook.

---

## Task 9: Set environment variables

All env vars are set per-service in the Railway dashboard under **Variables** tab.

### Backend API + Worker — set on BOTH services

| Variable | Value |
|---|---|
| `DATABASE_URL` | paste from PostgreSQL plugin |
| `REDIS_URL` | paste from Redis plugin |
| `OPENAI_API_KEY` | your OpenAI key |
| `GOOGLE_CLIENT_ID` | from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | from Google Cloud Console |
| `TELEGRAM_BOT_TOKEN` | from @BotFather |
| `JWT_SECRET_KEY` | the hex string from Task 6 |
| `FERNET_KEY` | the Fernet key from Task 6 |
| `WEB_URL` | `https://nextmove-frontend-production.up.railway.app` |
| `TELEGRAM_WEBHOOK_SECRET` | any random string (e.g. `secrets.token_hex(16)`) |

> Tip: In Railway you can click **+ Shared Variables** to define them once and reference in both services.

### Frontend service

| Variable | Value |
|---|---|
| `NEXTAUTH_URL` | `https://nextmove-frontend-production.up.railway.app` |
| `NEXTAUTH_SECRET` | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `NEXT_PUBLIC_API_URL` | `https://nextmove-api-production.up.railway.app` |
| `GOOGLE_CLIENT_ID` | same as backend |
| `GOOGLE_CLIENT_SECRET` | same as backend |

---

## Task 10: Update Google OAuth redirect URIs

Your Google OAuth app needs to know about the new production domain.

**Step 1:** Go to [console.cloud.google.com](https://console.cloud.google.com) → **APIs & Services** → **Credentials** → click your OAuth 2.0 Client.

**Step 2: Add to Authorized redirect URIs:**

```
https://nextmove-frontend-production.up.railway.app/api/auth/callback/google
```

**Step 3:** Save.

---

## Task 11: Register the Telegram webhook

After the backend is live, point Telegram at it.

**Step 1: Run in terminal** (replace placeholders)

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -d "url=https://nextmove-api-production.up.railway.app/telegram/webhook" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

**Step 2: Verify**

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo"
```

Expected response includes `"url": "https://nextmove-api-production.up.railway.app/telegram/webhook"` and `"pending_update_count": 0`.

---

## Task 12: Verify the full deploy

**Step 1: Check backend health**

```bash
curl https://nextmove-api-production.up.railway.app/health
# Expected: {"status":"ok"}
```

**Step 2: Check API docs**

Open `https://nextmove-api-production.up.railway.app/docs` in a browser — FastAPI Swagger UI should load.

**Step 3: Check frontend**

Open `https://nextmove-frontend-production.up.railway.app/login` — the redesigned login page should load.

**Step 4: Test Google login end-to-end**

Click "Continue with Google" → complete OAuth → should land on `/dashboard`.

**Step 5: Check Railway deploy logs**

In Railway dashboard, click each service → **Deployments** → latest deploy → **View Logs**. Look for:
- Backend: `INFO: Application startup complete.`
- Worker: `Worker rq:worker:... started`
- Frontend: `Ready in Xms`

---

## Task 13: Set up auto-deploy on push

Railway auto-deploys on push to `main` by default. Verify this is on.

**Step 1:** Click each service → **Settings** → **Source** → confirm **Watch Paths** and **Branch** = `main`.

From now on: `git push origin main` → Railway rebuilds all three services automatically.

---

## Ongoing: Promote from local to prod

After initial deploy, your workflow is:

```bash
# develop locally
docker compose up

# when ready — push deploys automatically
git push origin main

# check logs if something breaks
railway logs --service nextmove-api
```

Install the Railway CLI for log access:

```bash
npm install -g @railway/cli
railway login
railway link  # link to your project
```
