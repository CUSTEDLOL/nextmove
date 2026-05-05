# Telegram ↔ Web SSO Design

**Date:** 2026-05-06  
**Status:** Approved

## Problem

- No discovery path from the web app to the Telegram bot.
- The existing email+code linking flow is a dead stub (`send_link_email` only logs; no email is sent).
- The "Open on web" bot button links to the bare root URL, not the dashboard.

## Goals

1. Web-logged-in user can connect Telegram in two taps, no email/code.
2. Bot-first user is redirected to the web app to connect — no separate linking path.
3. Bot menu "Open on web" goes directly to `/dashboard`.
4. Settings page shows Telegram connection status.

## Non-goals

- Full SSO from Telegram → web (user must log in to the web app normally).
- Push notifications or any new bot commands beyond linking.

---

## Architecture

### New backend endpoint

**`POST /api/telegram/link-token`** (JWT-authenticated)
- Generates a 32-char cryptographically random token.
- Stores `tgauth:{token}` → `user_id` in Redis, TTL 600s, one-time use.
- Returns `{ "url": "https://t.me/{BOT_USERNAME}?start={token}" }`.

**`GET /api/telegram/link-status`** (JWT-authenticated)
- Returns `{ "linked": bool }` based on whether `User.telegram_chat_id` is set.

New config key: `telegram_bot_username: str = ""` in `Settings`.

### Bot `/start` handler (replaces current logic)

```
/start <token>  → consume_web_link_token(token, chat_id)
                  → link account → show menu
/start          → already linked → show menu
/start          → not linked → "Connect at [Dashboard]" URL button
```

New helper `consume_web_link_token(token, chat_id)` in `link_service.py`:
- Gets `tgauth:{token}` from Redis → resolves `user_id`
- Writes `telegram_chat_id` to the User row
- Deletes the Redis key

### What gets removed

- `store_link_code`, `verify_and_consume_link_code`, `send_link_email` from `link_service.py`
- Message handler branch that reads a plain email from an unlinked user
- `/web` command (redundant)

### Frontend — Settings page Telegram card

Alongside the Google Calendar card:

- **Not linked:** "Connect Telegram" button → `POST /api/telegram/link-token` → `window.open(url)`
- **Linked:** "Connected" badge (same style as Google Calendar card)

### Bot menu button fix

`menu_command` in `commands.py`: change `url=settings.web_url` → `url=f"{settings.web_url}/dashboard"`.

---

## Data Flow

```
Web (logged in)
  └─ POST /api/telegram/link-token
       └─ Redis: tgauth:{token} → user_id  (10 min TTL)
       └─ returns t.me/Bot?start={token}
  └─ window.open(url)

Telegram app
  └─ /start {token}
       └─ consume_web_link_token(token, chat_id)
            └─ UPDATE users SET telegram_chat_id = chat_id
            └─ DELETE tgauth:{token}
       └─ "You're connected! Here's your menu."
```

---

## Security

- Token is random 32 bytes (URL-safe base64), unguessable.
- One-time use: deleted on first consumption.
- 10-minute TTL: expired tokens auto-deleted by Redis.
- Endpoint requires a valid backend JWT — unauthenticated callers cannot generate tokens.
