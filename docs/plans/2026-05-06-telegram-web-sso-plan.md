# Telegram ↔ Web SSO Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let a logged-in web user connect their Telegram account in two taps (no email/code), and show a "Connect Telegram" card in the Settings page; fix the bot menu "Open on web" button to link directly to `/dashboard`.

**Architecture:** Backend mints a short-lived Redis token via `POST /api/telegram/link-token`; the frontend opens `t.me/Bot?start=<token>`; the bot's `/start` handler exchanges the token, writes `telegram_chat_id`, and shows the menu. The old email+code linking path is deleted entirely — unlinked bot users are redirected to the Settings page instead.

**Tech Stack:** FastAPI, python-telegram-bot v20, Redis, Next.js 14, NextAuth, TypeScript

---

## Task 1: Add `telegram_bot_username` to config

**Files:**
- Modify: `backend/app/config.py`

**Step 1: Add the setting**

Open `backend/app/config.py`. Add one line inside the `Settings` class after `telegram_bot_token`:

```python
telegram_bot_username: str = ""
```

**Step 2: Verify it loads**

```bash
cd backend && python -c "from app.config import settings; print(settings.telegram_bot_username)"
```

Expected: prints an empty string (or your bot username if set in `.env`).

**Step 3: Add to `.env.example`**

Add below `TELEGRAM_BOT_TOKEN`:
```
TELEGRAM_BOT_USERNAME=YourBotUsername
```

**Step 4: Commit**

```bash
git add backend/app/config.py .env.example
git commit -m "config: add TELEGRAM_BOT_USERNAME setting"
```

---

## Task 2: Add SSO token helpers to `link_service.py`

**Files:**
- Modify: `backend/app/telegram/link_service.py`
- Create: `backend/tests/test_telegram_sso.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_telegram_sso.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


def _make_redis(data: dict):
    """Return a mock Redis that acts on a plain dict."""
    r = MagicMock()
    r.get = lambda key: data.get(key)
    r.setex = lambda key, ttl, val: data.update({key: val})
    r.delete = lambda key: data.pop(key, None)
    return r


def test_store_web_link_token_returns_token_and_writes_redis():
    store = {}
    with patch("app.telegram.link_service._get_redis", return_value=_make_redis(store)):
        from app.telegram.link_service import store_web_link_token
        token = store_web_link_token("user-uuid-123")
    assert len(token) > 20
    assert f"tgauth:{token}" in store
    assert store[f"tgauth:{token}"] == "user-uuid-123"


def test_consume_web_link_token_returns_user_id_and_deletes_key():
    token = "abc123token"
    store = {f"tgauth:{token}": "user-uuid-456"}
    with patch("app.telegram.link_service._get_redis", return_value=_make_redis(store)):
        from app.telegram.link_service import consume_web_link_token
        result = consume_web_link_token(token, chat_id=999)
    assert result == "user-uuid-456"
    assert f"tgauth:{token}" not in store


def test_consume_web_link_token_returns_none_for_missing_token():
    store = {}
    with patch("app.telegram.link_service._get_redis", return_value=_make_redis(store)):
        from app.telegram.link_service import consume_web_link_token
        result = consume_web_link_token("no-such-token", chat_id=999)
    assert result is None
```

**Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_telegram_sso.py -v
```

Expected: ImportError or AttributeError — functions don't exist yet.

**Step 3: Replace `link_service.py` with the new implementation**

Replace the entire contents of `backend/app/telegram/link_service.py`:

```python
"""
Web → Telegram SSO token service.

Flow:
  1. Logged-in web user hits POST /api/telegram/link-token
     → store_web_link_token() generates a URL-safe token, stores it in
       Redis for 10 minutes keyed to the user's UUID, and returns it.
  2. User opens t.me/Bot?start=<token> and taps Start.
     → consume_web_link_token() validates the token, deletes it, and
       returns the user_id so the bot handler can write telegram_chat_id.
"""
import logging
import secrets

import redis as redis_lib

from app.config import settings

logger = logging.getLogger(__name__)

_TOKEN_TTL = 600  # 10 minutes
_PREFIX = "tgauth:"


def _get_redis() -> redis_lib.Redis:
    return redis_lib.from_url(settings.redis_url, decode_responses=True)


def store_web_link_token(user_id: str) -> str:
    """Mint a one-time SSO token tied to user_id. Returns the token."""
    token = secrets.token_urlsafe(32)
    _get_redis().setex(f"{_PREFIX}{token}", _TOKEN_TTL, user_id)
    return token


def consume_web_link_token(token: str, chat_id: int) -> str | None:
    """
    Exchange a web SSO token for the linked user_id.
    Deletes the token on success (one-time use).
    Returns None if the token is missing or expired.
    chat_id is accepted but not validated here — the caller writes it.
    """
    r = _get_redis()
    user_id = r.get(f"{_PREFIX}{token}")
    if not user_id:
        return None
    r.delete(f"{_PREFIX}{token}")
    return user_id
```

**Step 4: Run tests again**

```bash
cd backend && python -m pytest tests/test_telegram_sso.py -v
```

Expected: 3 tests PASS.

**Step 5: Commit**

```bash
git add backend/app/telegram/link_service.py backend/tests/test_telegram_sso.py
git commit -m "feat: add web→Telegram SSO token helpers"
```

---

## Task 3: Add `/api/telegram/link-token` and `/api/telegram/link-status` endpoints

**Files:**
- Modify: `backend/app/routers/telegram.py`
- Create: `backend/tests/test_telegram_router_sso.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_telegram_router_sso.py`:

```python
import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_current_user
from app.models import User


def _mock_user(linked: bool = False):
    u = User()
    u.id = uuid.uuid4()
    u.email = "test@example.com"
    u.telegram_chat_id = 12345 if linked else None
    return u


def test_link_token_returns_url(monkeypatch):
    user = _mock_user(linked=False)
    app.dependency_overrides[get_current_user] = lambda: user
    with patch("app.telegram.link_service.store_web_link_token", return_value="tok123"):
        with patch("app.config.settings") as mock_settings:
            mock_settings.telegram_bot_username = "NextMoveBot"
            mock_settings.telegram_webhook_secret = ""
            client = TestClient(app)
            res = client.post("/api/telegram/link-token")
    app.dependency_overrides.clear()
    assert res.status_code == 200
    assert "t.me/NextMoveBot?start=tok123" in res.json()["url"]


def test_link_status_unlinked(monkeypatch):
    user = _mock_user(linked=False)
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    res = client.get("/api/telegram/link-status")
    app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json() == {"linked": False}


def test_link_status_linked(monkeypatch):
    user = _mock_user(linked=True)
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    res = client.get("/api/telegram/link-status")
    app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json() == {"linked": True}
```

**Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_telegram_router_sso.py -v
```

Expected: FAIL — endpoints don't exist yet.

**Step 3: Add endpoints to `backend/app/routers/telegram.py`**

Replace the entire file:

```python
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session
from telegram import Update

from app.config import settings
from app.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    from app.telegram.bot import get_application
    body = await request.json()
    application = get_application()
    update = Update.de_json(body, application.bot)
    await application.process_update(update)
    return Response(status_code=200)


@router.post("/link-token")
def create_link_token(current_user: User = Depends(get_current_user)):
    from app.telegram.link_service import store_web_link_token
    token = store_web_link_token(str(current_user.id))
    bot_username = settings.telegram_bot_username
    return {"url": f"https://t.me/{bot_username}?start={token}"}


@router.get("/link-status")
def link_status(current_user: User = Depends(get_current_user)):
    return {"linked": current_user.telegram_chat_id is not None}
```

**Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_telegram_router_sso.py -v
```

Expected: 3 tests PASS.

**Step 5: Commit**

```bash
git add backend/app/routers/telegram.py backend/tests/test_telegram_router_sso.py
git commit -m "feat: add link-token and link-status API endpoints"
```

---

## Task 4: Overhaul the bot `/start` handler

**Files:**
- Modify: `backend/app/telegram/handlers/start.py`

**Step 1: Replace the file entirely**

```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.config import settings
    from app.database import SessionLocal
    from app.models import User
    from app.telegram.handlers.commands import menu_command

    chat_id = update.effective_chat.id
    args = context.args  # tokens passed after /start

    if args:
        token = args[0]
        from app.telegram.link_service import consume_web_link_token
        user_id = consume_web_link_token(token, chat_id)
        if user_id:
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.telegram_chat_id = chat_id
                    db.commit()
            finally:
                db.close()
            await update.message.reply_text(
                "✅ Your account is connected\\! Here's your menu:",
                parse_mode="MarkdownV2",
            )
            await menu_command(update, context)
            return
        await update.message.reply_text(
            "❌ That link has expired\\. Go to Settings in the web app and click *Connect Telegram* again\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🌐 Open Settings", url=f"{settings.web_url}/settings")
            ]])
        )
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()

    if user:
        await menu_command(update, context)
        return

    await update.message.reply_text(
        "👋 Welcome to *NextMove*\\!\n\n"
        "To connect your account, open the web app and click *Connect Telegram* in Settings\\.",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Open NextMove", url=f"{settings.web_url}/settings")
        ]])
    )
```

**Step 2: Manual smoke test**

With the bot running locally:
- Send `/start` as an unlinked user → should see the "Open NextMove" button.
- Send `/start expiredtoken` → should see the "That link has expired" message.

**Step 3: Commit**

```bash
git add backend/app/telegram/handlers/start.py
git commit -m "feat: overhaul /start to handle web SSO token and redirect unlinked users"
```

---

## Task 5: Clean up `message.py` — remove email/code linking path

**Files:**
- Modify: `backend/app/telegram/handlers/message.py`

**Step 1: Remove the unlinked-user email/code branch**

In `handle_message`, the block that starts with `if not user:` currently calls `_handle_link_code` and `_handle_email_link`. Replace that entire block with a simple redirect:

```python
    if not user:
        from app.config import settings
        await update.message.reply_text(
            "👋 Connect your account from the web app to get started\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🌐 Open NextMove", url=f"{settings.web_url}/settings")
            ]])
        )
        return
```

**Step 2: Delete dead functions and imports at the bottom of the file**

Remove:
- `_EMAIL_RE` and `_CODE_RE` constants
- `_looks_like_email()` function
- `_looks_like_link_code()` function
- `_handle_email_link()` function
- `_handle_link_code()` function
- `from app.telegram import link_service` import
- `from app.models import User` import (no longer needed in this file — `_get_user_by_chat_id` uses `SessionLocal` directly)

Keep: `_get_user_by_chat_id` (still used), all linked-user logic below.

**Step 3: Verify the file still imports cleanly**

```bash
cd backend && python -c "from app.telegram.handlers.message import handle_message; print('ok')"
```

Expected: `ok`

**Step 4: Run existing message handler tests**

```bash
cd backend && python -m pytest tests/test_message_handler.py -v
```

Expected: all PASS (or skip if they relied on email flow — update them to expect the redirect response).

**Step 5: Commit**

```bash
git add backend/app/telegram/handlers/message.py
git commit -m "feat: replace email/code linking path with web redirect in message handler"
```

---

## Task 6: Fix dashboard URL in bot menu and remove `/web` command

**Files:**
- Modify: `backend/app/telegram/handlers/commands.py`
- Modify: `backend/app/main.py`

**Step 1: Fix the "Open on web" button URL in `menu_command`**

In `commands.py`, find this line in `menu_command`:

```python
[InlineKeyboardButton("🌐 Open on web", url=settings.web_url)],
```

Change it to:

```python
[InlineKeyboardButton("🌐 Open dashboard", url=f"{settings.web_url}/dashboard")],
```

**Step 2: Delete `web_command` from `commands.py`**

Remove the entire `web_command` function (lines 139–147).

**Step 3: Remove `/web` from bot commands in `main.py`**

In `initialize_telegram_bot`, remove:

```python
BotCommand("web",   "Open NextMove in browser"),
```

**Step 4: Verify import still works**

```bash
cd backend && python -c "from app.telegram.handlers.commands import menu_command; print('ok')"
```

Expected: `ok`

**Step 5: Commit**

```bash
git add backend/app/telegram/handlers/commands.py backend/app/main.py
git commit -m "fix: point bot menu Open button to /dashboard, remove redundant /web command"
```

---

## Task 7: Add Telegram API methods to the frontend

**Files:**
- Modify: `frontend/src/lib/api.ts`

**Step 1: Add two methods to the `api` object**

At the end of the `api` object in `frontend/src/lib/api.ts`, add before the closing `}`:

```typescript
  getTelegramLinkToken: () => authFetch("/api/telegram/link-token", { method: "POST" }),
  getTelegramLinkStatus: () => authFetch("/api/telegram/link-status") as Promise<{ linked: boolean }>,
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add getTelegramLinkToken and getTelegramLinkStatus to API client"
```

---

## Task 8: Add Telegram connection card to the Settings page

**Files:**
- Modify: `frontend/src/app/settings/page.tsx`

**Step 1: Add `telegramLinked` state**

At the top of `SettingsPage`, alongside the existing `settings` state, add:

```typescript
const [telegramLinked, setTelegramLinked] = useState<boolean | null>(null);
const [telegramLoading, setTelegramLoading] = useState(false);
```

**Step 2: Fetch link status on mount**

In the existing `useEffect` that calls `api.getMe()`, also call `getTelegramLinkStatus`:

```typescript
useEffect(() => {
  api.getMe().then(setSettings).catch(() => setSettings(null));
  api.getTelegramLinkStatus()
    .then((res) => setTelegramLinked(res.linked))
    .catch(() => setTelegramLinked(false));
}, []);
```

**Step 3: Add the connect handler**

```typescript
async function connectTelegram() {
  setTelegramLoading(true);
  try {
    const res = await api.getTelegramLinkToken() as { url: string };
    window.open(res.url, "_blank");
  } finally {
    setTelegramLoading(false);
  }
}
```

**Step 4: Add the Telegram card to the JSX**

Insert this card after the Google Calendar card and before the `<div className="flex justify-end">` save button div:

```tsx
<div className="rounded-xl border border-[var(--border)] bg-white p-5 space-y-4">
  <div className="flex items-start justify-between gap-4">
    <div>
      <p className="text-sm font-medium text-gray-900">Telegram Bot</p>
      <p className="text-xs text-gray-500 mt-1">
        Get task nudges and control NextMove directly from Telegram.
      </p>
    </div>
    <span className={`rounded-full px-2 py-1 text-xs font-medium ${
      telegramLinked ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500"
    }`}>
      {telegramLinked === null ? "Checking..." : telegramLinked ? "Connected" : "Not connected"}
    </span>
  </div>
  {!telegramLinked && (
    <button
      onClick={connectTelegram}
      disabled={telegramLoading}
      className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
    >
      {telegramLoading ? "Opening Telegram..." : "Connect Telegram"}
    </button>
  )}
</div>
```

**Step 5: Start the frontend and verify visually**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000/settings`. You should see:
- A "Telegram Bot" card with "Not connected" badge
- A "Connect Telegram" button
- Clicking it should open a new tab to `t.me/<bot>?start=<token>` (or show a network error if the backend isn't running)

**Step 6: Commit**

```bash
git add frontend/src/app/settings/page.tsx
git commit -m "feat: add Telegram connection card to Settings page"
```

---

## Task 9: Set `TELEGRAM_BOT_USERNAME` in your environment

**Step 1: Add to `.env`**

Find your bot username (the one that ends in `Bot` from @BotFather) and add:

```
TELEGRAM_BOT_USERNAME=YourActualBotUsername
```

**Step 2: Restart the backend and verify**

```bash
cd backend && python -c "from app.config import settings; assert settings.telegram_bot_username, 'missing!'; print('ok')"
```

Expected: `ok`

**Step 3: End-to-end test**

1. Log in to the web app
2. Go to Settings → click "Connect Telegram"
3. New tab opens `t.me/<bot>?start=<token>`
4. Tap Start in Telegram
5. Bot replies "Your account is connected!" and shows the menu
6. Refresh Settings — badge should now show "Connected"

---

## Done

All tasks complete. The old email+code linking path is fully removed; web-first SSO via Redis token is the only linking mechanism. Bot-first users are redirected to Settings.
