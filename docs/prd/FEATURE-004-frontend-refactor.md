# PRD — Frontend Refactor: Split Monolithic index.html

**ID:** FEATURE-004  
**Status:** Ready for Implementation  
**Author:** Claude Chat  
**Created:** 2026-03-14  
**GitHub Issue:** TBD (created by Claude Code when implementation begins)  
**Branch:** TBD (created by Claude Code when implementation begins)  

---

## 1. Problem Statement

The entire Osiris frontend — 1,117 lines of HTML, CSS, and JavaScript — lives
in a single file: `static/index.html`. This makes the codebase hard to navigate,
hard to maintain, and hard for Claude Code to work on safely. Any edit requires
loading the entire file, and a mistake anywhere can break everything.

The file currently contains:
- ~465 lines of CSS (lines 7–470, inside a `<style>` block)
- ~580 lines of JavaScript (lines 535–1117, inside a `<script>` block)
- ~65 lines of HTML structure (the actual markup)

---

## 2. Goal

When this is shipped, the frontend is split into separate files by concern.
`index.html` contains only HTML structure. CSS and JavaScript live in their
own files under `static/css/` and `static/js/`. Osiris behaves identically
to before — this is a structural refactor with no functional changes.

---

## 3. Background and Context

The JavaScript functions fall into five logical groups, identified by line number
in the current `index.html`:

| Module | Functions | Lines |
|---|---|---|
| `ui.js` | getTime, removeEmptyState, showEmptyState, addMessage, addStreamingBubble, finalizeStreamingBubble, addThinking, setThinkingStatus, removeThinking, setInputEnabled, updateLimitBar | 556–662 |
| `topics.js` | openTopicsDrawer, closeTopicsDrawer, renderTopicMessages, loadTopics, renderTopics, switchTopic, createTopic, deleteTopic | 664–838 |
| `user.js` | loadUsage, loadCurrentUser, signOut | 840–879 |
| `voice.js` | handleVoiceBtn, enterVoiceMode, exitVoiceMode, updateVoiceModeUI, startRecording, stopRecording, transcribeAndSend, speakResponse | 881–991 |
| `chat.js` | sendMessage, submitMessage, clearChat | 993–1117 |

CSS moves to a single file: `static/css/main.css`

There are no backend changes. Flask serves static files from `static/` already —
no new routes or configuration needed.

**Related ADRs:**
- ADR-001 — Establishes development framework

---

## 4. Acceptance Criteria

- [ ] AC-1: `static/index.html` contains only HTML structure — no `<style>` block, no `<script>` block with application code
- [ ] AC-2: `static/css/main.css` exists and contains all CSS previously in the `<style>` block
- [ ] AC-3: `static/js/ui.js` exists and contains all UI helper functions
- [ ] AC-4: `static/js/topics.js` exists and contains all topic management functions
- [ ] AC-5: `static/js/user.js` exists and contains all user/session functions
- [ ] AC-6: `static/js/voice.js` exists and contains all voice mode functions
- [ ] AC-7: `static/js/chat.js` exists and contains all chat functions
- [ ] AC-8: `index.html` links to `main.css` via `<link>` and loads all JS files via `<script src>` tags
- [ ] AC-9: Osiris loads correctly in the browser after refactor — login page renders, chat works, topics work
- [ ] AC-10: No JavaScript errors appear in the browser console after refactor
- [ ] AC-11: The JS files are loaded in dependency order — `ui.js` before `topics.js`, `topics.js` before `chat.js`

---

## 5. Test Matrix

| Test ID | Action | Expected Result | Pass Criteria |
|---|---|---|---|
| T-004-01 | `cat static/index.html \| grep "<style>"` | No output | `<style>` block is gone |
| T-004-02 | `cat static/index.html \| grep "^    function\|^function"` | No output | No inline JS functions remain |
| T-004-03 | `ls static/css/ static/js/` | All 6 new files present | main.css, ui.js, topics.js, user.js, voice.js, chat.js all exist |
| T-004-04 | `wc -l static/index.html` | Under 100 lines | File is HTML structure only |
| T-004-05 | Open Osiris in browser, open DevTools console | No JS errors on page load | Console shows 0 errors |
| T-004-06 | Log in and send a chat message | Osiris responds normally | Full chat flow works end to end |
| T-004-07 | Click a topic in the sidebar | Conversation history loads | FEATURE-001 fix still works |
| T-004-08 | Tell Osiris "remember that I prefer dark mode" | Stored correctly as third-person | FEATURE-002 fix still works |
| T-004-09 | Open DevTools → Network tab, reload page | CSS and JS files load with HTTP 200 | All 6 static files served correctly |
| T-004-10 | Check `static/index.html` for `<script src>` tags | 5 script tags present, correct order | ui.js, topics.js, user.js, voice.js, chat.js all linked |

---

## 6. Scope

### In Scope
- `static/index.html` — remove `<style>` block, remove `<script>` block, add `<link>` and `<script src>` tags
- `static/css/main.css` — new file, contains extracted CSS
- `static/js/ui.js` — new file
- `static/js/topics.js` — new file
- `static/js/user.js` — new file
- `static/js/voice.js` — new file
- `static/js/chat.js` — new file

### Out of Scope
- `app.py` — do not modify
- Any changes to CSS styles or values — move them exactly, do not redesign
- Any changes to JavaScript logic — move functions exactly, do not refactor their internals
- Adding new features, fixing new bugs, or improving any existing behavior
- Creating a bundler, build step, or npm setup — plain `<script src>` tags only

---

## 7. Implementation Notes

**Move code exactly as-is.** Do not fix, improve, or refactor any CSS or
JavaScript during this move. The goal is a structural change only. Any bugs
that exist before the refactor should still exist after — they will be fixed
in subsequent PRDs. Changing logic during a structural refactor makes it
impossible to know what caused a regression.

**Script loading order matters.** Functions in `topics.js` call functions
defined in `ui.js`. Functions in `chat.js` call functions in `ui.js` and
`topics.js`. Load order in `index.html` must be:

```html
<script src="/static/js/ui.js"></script>
<script src="/static/js/topics.js"></script>
<script src="/static/js/user.js"></script>
<script src="/static/js/voice.js"></script>
<script src="/static/js/chat.js"></script>
```

**Initialization code.** The current `<script>` block likely contains
initialization calls at the bottom (event listeners, `loadTopics()` on
page load, etc.) in addition to function definitions. These should move
to `chat.js` or a dedicated `init` block at the bottom of `chat.js` —
not left floating in `index.html`.

**No module syntax.** Do not use ES6 `import`/`export`. Use plain script
tags. This keeps the setup simple and avoids CORS issues with Flask's
static file serving.

---

## 8. Rollback Plan

All changes are to static frontend files. No backend is affected.

1. `git revert <merge-commit-sha>`
2. `git push origin main`
3. `cd ~/agent && git pull origin main`
4. Hard-refresh browser: `Cmd+Shift+R`
5. Verify rollback: `wc -l static/index.html` should return ~1117

No Gunicorn restart required — static files are served directly and the
running server will pick up the reverted files immediately after the pull.

---

## 9. Definition of Done

A PR for this feature is ready to merge when:

- [ ] All acceptance criteria (AC-1 through AC-11) are met
- [ ] All Test Matrix items (T-004-01 through T-004-10) are PASS
- [ ] Only the files listed in the In Scope section were modified or created
- [ ] PR description includes test results for every Test ID
- [ ] PR description includes "Closes #NNN"
- [ ] No secrets, tokens, or credentials appear anywhere in the diff
- [ ] `app.py` was not touched
