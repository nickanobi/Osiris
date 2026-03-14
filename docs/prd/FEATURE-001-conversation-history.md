# PRD — Conversation History Rendering

**ID:** FEATURE-001  
**Status:** Ready for Implementation  
**Author:** Claude Chat  
**Created:** 2026-03-14  
**GitHub Issue:** TBD (created by Claude Code when implementation begins)  
**Branch:** TBD (created by Claude Code when implementation begins)  

---

## 1. Problem Statement

When a user clicks a topic in the sidebar, the chat view renders blank. The sidebar
correctly displays all topics with accurate message counts, which confirms that
`/api/topics` (GET) is returning data successfully. The failure occurs after the
click — the frontend is not loading and rendering the messages for the selected topic.

The user has no way to return to a previous conversation. Every session effectively
starts fresh despite conversation history being stored correctly on disk.

---

## 2. Goal

When this is shipped, a user will be able to click any topic in the sidebar and
immediately see that conversation's full message history rendered in the chat view.

---

## 3. Background and Context

The backend topic system is intact:

- `load_topics(username)` reads per-user topic files (`topics_<username>.json`)
- `get_active_topic(topics_data, topic_id)` resolves the correct topic by ID
- `GET /api/topics` returns all topics with message counts — this works correctly
- Topics are stored as objects with an `id`, `title`, `messages` array, `created`,
  and `last_active` timestamp

The bug is isolated to the frontend. `static/index.html` contains all JavaScript.
The sidebar populates correctly from `/api/topics`, but the click handler that should
load and render a topic's `messages` array into the chat view is either missing,
not firing, or rendering to the wrong element.

There is no separate API endpoint for fetching a single topic's messages. The
`messages` array is already included in the `/api/topics` GET response — the
frontend just needs to use it.

**Related ADRs:**
- ADR-001 — Establishes development framework

---

## 4. Acceptance Criteria

- [ ] AC-1: Clicking a topic in the sidebar loads that topic's messages into the chat view
- [ ] AC-2: Each message renders with the correct speaker label (user vs Osiris)
- [ ] AC-3: Messages render in chronological order (oldest at top, newest at bottom)
- [ ] AC-4: The selected topic is visually highlighted in the sidebar after click
- [ ] AC-5: Clicking a topic does not trigger a new chat submission or modify any data
- [ ] AC-6: If a topic has zero messages, the chat view renders empty with no error

---

## 5. Test Matrix

| Test ID | Action | Expected Result | Pass Criteria |
|---|---|---|---|
| T-001-01 | Log in and click a topic in the sidebar that has at least 2 messages | Chat view populates with that topic's messages | Messages visible, correct count matches sidebar |
| T-001-02 | Check message order in the rendered chat view | Messages appear oldest-first, newest at bottom | Visual order matches chronological order of stored messages |
| T-001-03 | Check speaker labels on rendered messages | User messages and Osiris messages are visually distinct | Both speaker types render with correct labels/styling |
| T-001-04 | Click a second topic after viewing the first | Chat view clears and loads the second topic's messages | No messages from the first topic remain visible |
| T-001-05 | Click a topic with zero messages | Chat view renders empty, no error message or blank crash | Empty state is clean — no JS console errors |
| T-001-06 | Click the currently active topic | Chat view remains stable, no duplicate messages appear | Idempotent — clicking active topic does not break state |

---

## 6. Scope

### In Scope
- `static/index.html` — locate and fix the topic click handler and message rendering logic

### Out of Scope
- `app.py` — backend is working correctly, do not modify
- `topics_<username>.json` files — data files, do not modify
- Any CSS changes beyond what is required to show speaker labels correctly
- The frontend refactor (breaking index.html into css/ and js/ modules) — that is a
  separate PRD and must not be started here
- The memory perspective bug (FEATURE-002) — separate PRD

---

## 7. Implementation Notes

The `/api/topics` GET response already contains the full `messages` array for each
topic. No new API endpoint is needed. The fix should:

1. Find the sidebar click handler in `static/index.html`
2. Ensure it reads the `messages` array from the already-fetched topics data
   (or re-fetches from `/api/topics` if topics data is not held in memory)
3. Render each message into the chat view, preserving speaker identity and order
4. Clear the chat view before rendering the newly selected topic's messages

Do not add a new Flask route. Do not modify the topics JSON structure.
If the click handler is missing entirely, add one — do not restructure the
surrounding JavaScript beyond what is needed to make the handler work.

---

## 8. Rollback Plan

This change is isolated to one file in the frontend with no backend dependency.

1. `git revert <merge-commit-sha>`
2. `git push origin main`
3. Hard-refresh the browser on any open Osiris tabs (`Cmd+Shift+R`)
4. Verify rollback by confirming the sidebar still shows topics (pre-fix behavior restored)

No Gunicorn restart required — static files are served directly.

---

## 9. Definition of Done

A PR for this feature is ready to merge when:

- [ ] All acceptance criteria (AC-1 through AC-6) are met
- [ ] All Test Matrix items (T-001-01 through T-001-06) are PASS
- [ ] Only `static/index.html` was modified
- [ ] PR description includes test results for every Test ID
- [ ] PR description includes "Closes #NNN"
- [ ] No secrets, tokens, or credentials appear anywhere in the diff
