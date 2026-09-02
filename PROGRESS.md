# GitLore Frontend Rework — Progress Log

## Status: Spec Complete / Implementation Not Started

---

## What Has Been Done

### 1. Spec Phase — COMPLETE

All three spec documents are written and saved at:
`c:\GitLore\.kiro\specs\gitlore-frontend-rework\`

---

### `bugfix.md` — Requirements Document ✅

Captures the full problem statement in bug/fix format.

**8 Current Behavior (Defect) clauses:**
- 1.1 — Static two-column layout shown unconditionally on first load with no repos
- 1.2 — Same layout shown even when repos already exist (should skip to chat)
- 1.3 — Query result replaces previous answer (no chat history)
- 1.4 — Loading state is a top-level disconnected skeleton, not inline in thread
- 1.5 — Errors surface as a top-level banner, not inline in the thread
- 1.6 — Repo switching requires a separate always-visible panel
- 1.7 — Only `clarified_question` shown, not the original user message
- 1.8 — Indexing progress = disabled button only, no feedback

**8 Expected Behavior (Correct) clauses:**
- 2.1 — No repos → show focused onboarding screen only
- 2.2 — Repos exist → skip to chat with first repo pre-selected
- 2.3 — Queries append to a persistent chat thread
- 2.4 — In-flight loading shown inline in the thread
- 2.5 — Errors shown inline in the thread
- 2.6 — Repo selector integrated into chat header/toolbar
- 2.7 — Both original message and `clarified_question` visible
- 2.8 — Animated indexing progress, auto-transition to chat on completion

**8 Regression Prevention clauses (3.1–3.8):**
- API call signatures unchanged (`lib/api.js` untouched)
- Dark theme, fonts, CSS design system preserved
- React 19 / Vite 8 / Tailwind 4 unchanged
- Chat history preserved when indexing new repo

---

### `design.md` — Technical Design Document ✅

Covers:
- **Formal bug condition** as pseudocode (`isBugCondition` function)
- **Root cause analysis** — 5 root causes identified
- **2 Correctness Properties** (Property 1: phase-aware rendering, Property 2: preservation)
- **Complete component architecture:**

| Component | Type | Purpose |
|---|---|---|
| `App.jsx` | Rework | Phase orchestrator (`onboarding` / `chat`), `thread` state |
| `OnboardingScreen.jsx` | New | Phase 1 — URL input, animated indexing progress |
| `ChatInterface.jsx` | New | Phase 2 container |
| `ChatHeader.jsx` | New | Repo selector dropdown + Index New Repo button |
| `ChatThread.jsx` | New | Scrollable auto-scroll message list |
| `MessageBubble.jsx` | New | Renders user / assistant / loading / error entries |
| `ChatInput.jsx` | New | Auto-grow textarea, Enter to send |
| `IndexModal.jsx` | New | Modal for indexing while staying in chat |

- **All new CSS classes** for `App.css` (additive only, existing rules untouched)
- **State shape** for `App.jsx`: `phase`, `thread`, `indexError`, etc.
- **ThreadEntry union type**: `user | assistant | loading | error`
- **Testing strategy**: exploratory → fix-check → preservation → unit → PBT → integration

---

### `tasks.md` — Implementation Task List ✅

**30 tasks queued** across 15 numbered groups:

| # | Task | Status |
|---|---|---|
| 1 | Write bug condition exploration tests (expected to FAIL on unfixed code) | ⬜ Not started |
| 2 | Write preservation property tests (expected to PASS on unfixed code) | ⬜ Not started |
| 3.1 | Extend `App.css` with new layout classes (additive) | ⬜ Not started |
| 4.1 | Create `OnboardingScreen.jsx` | ⬜ Not started |
| 5.1 | Create `MessageBubble.jsx` | ⬜ Not started |
| 6.1 | Create `ChatThread.jsx` | ⬜ Not started |
| 7.1 | Create `ChatHeader.jsx` | ⬜ Not started |
| 8.1 | Create `ChatInput.jsx` | ⬜ Not started |
| 9.1 | Create `IndexModal.jsx` | ⬜ Not started |
| 10.1 | Create `ChatInterface.jsx` | ⬜ Not started |
| 11.1–11.6 | Rework `App.jsx` (state → mount → handlers → modal → render) | ⬜ Not started |
| 12.1–12.2 | Re-run both property tests against fixed code | ⬜ Not started |
| 13.1–13.7 | Component unit tests | ⬜ Not started |
| 14.1–14.4 | Property-based tests (thread invariant, phase monotonicity, etc.) | ⬜ Not started |
| 15 | Final checkpoint — full test suite + diff verification | ⬜ Not started |

---

## What Has NOT Been Done Yet

- No source files have been created or modified
- `frontend/src/App.jsx` is still the original two-column layout
- No new components exist yet
- No tests have been written or run
- `App.css` has not been extended

---

## Files Changed So Far

```
c:\GitLore\.kiro\specs\gitlore-frontend-rework\
  ├── .config.kiro     ← created
  ├── bugfix.md        ← created (requirements)
  ├── design.md        ← created (technical design)
  └── tasks.md         ← created (implementation plan)
```

---

## Next Step

Run the task list to begin implementation. Tasks 1–2 write tests first (TDD approach), then tasks 3–11 implement the components, then 12–15 verify everything passes.

To start: tell me "go" or "start implementing".
