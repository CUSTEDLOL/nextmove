# Dashboard Flow Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Promote the next task immediately after completing the current hero task and replace the generic empty state with a more intentional dashboard fallback.

**Architecture:** Keep the backend as the source of truth for the dashboard queue. After completion, refetch the current `/api/tasks/today` payload and rebuild the hero/secondary stack from that fresh response. Move the dashboard selection logic into a small pure helper so we can cover the promotion behavior with a lightweight Node test.

**Tech Stack:** Next.js App Router, React client components, TypeScript, Node built-in test runner.

---

### Task 1: Dashboard Selection Helper

**Files:**
- Create: `frontend/src/app/dashboard/dashboard-state.ts`
- Test: `frontend/src/app/dashboard/dashboard-state.test.ts`

**Step 1: Write the failing test**

Cover:
- the first active task becomes primary
- when the previous primary is gone, the next task becomes primary
- only three secondary tasks are exposed

**Step 2: Run test to verify it fails**

Run: `node --test frontend/src/app/dashboard/dashboard-state.test.ts`

**Step 3: Write minimal implementation**

Export a helper that derives:
- `primaryTask`
- `secondaryTasks`
- `isQueueEmpty`

**Step 4: Run test to verify it passes**

Run: `node --test frontend/src/app/dashboard/dashboard-state.test.ts`

### Task 2: Refresh Hero Task After Completion

**Files:**
- Modify: `frontend/src/app/dashboard/page.tsx`

**Step 1: Use the helper in the dashboard**

Replace inline primary/secondary selection with the shared helper.

**Step 2: Refetch after completion**

After `completeTask`, refetch the dashboard payload and apply the fresh state instead of only refreshing schedule blocks.

**Step 3: Keep failure behavior safe**

If refresh fails, preserve the optimistic completion state instead of crashing.

### Task 3: Replace the Empty State

**Files:**
- Modify: `frontend/src/app/dashboard/page.tsx`

**Step 1: Replace the generic green success slab**

Build a more intentional “runway clear” card that:
- feels active, not final
- points back to the dump bar
- visually matches the dashboard better

**Step 2: Verify visual spacing**

Keep the component balanced on desktop and mobile widths.

### Task 4: Verification

**Files:**
- Verify: `frontend/src/app/dashboard/page.tsx`
- Verify: `frontend/src/app/dashboard/dashboard-state.ts`
- Verify: `frontend/src/app/dashboard/dashboard-state.test.ts`

**Step 1: Run the focused helper test**

Run: `node --test frontend/src/app/dashboard/dashboard-state.test.ts`

**Step 2: Run lint**

Run: `cd frontend && npm run lint`

**Step 3: Run build**

Run: `cd frontend && npm run build`
