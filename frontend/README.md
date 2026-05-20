# NextMove Frontend

Next.js frontend for the NextMove MVP.

## Local Commands

```bash
npm run dev
npm run lint
npm run build
```

## Runtime Expectations

- Backend API expected at `NEXT_PUBLIC_API_URL`
- NextAuth powers credentials login plus Google sign-in
- Google sign-in exchanges the provider token for a backend JWT through `POST /api/auth/google/exchange`

## Current Product Surfaces

- `/dashboard`
  - brain dump
  - primary + secondary tasks
  - upcoming scheduled blocks
- `/tasks`
  - list tasks
  - add task
  - edit/delete task with persistence
- `/calendar`
  - scheduled work blocks
  - deadlines
  - manual calendar events
- `/settings`
  - profile + timezone
  - study window
  - Google calendar connection state
- `/matrix`
  - live task-backed focus matrix
  - drag persistence
  - modal edit persistence
  - capped board with overflow list

## Verification Gate

This repo does not yet have a frontend test runner. Current verification is:

```bash
npm run lint
npm run build
```
