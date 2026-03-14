# PRD — Reliable Osiris Startup on macOS

**ID:** FEATURE-003  
**Status:** Ready for Implementation  
**Author:** Claude Chat  
**Created:** 2026-03-14  
**GitHub Issue:** TBD (created by Claude Code when implementation begins)  
**Branch:** TBD (created by Claude Code when implementation begins)  

---

## 1. Problem Statement

Osiris has no reliable, repeatable way to start on macOS. Two problems combine
to cause this:

**Problem 1 — Gunicorn crashes on macOS due to fork safety.**
When Gunicorn starts, it forks worker processes. On macOS, the Objective-C
runtime raises a fatal error if it was initialized in the parent process before
the fork. This causes every worker to be immediately SIGKILL'd in a loop:

```
objc[XXXX]: +[NSMutableString initialize] may have been in progress in another
thread when fork() was called. Crashing instead.
[ERROR] Worker (pid:XXXX) was sent SIGKILL! Perhaps out of memory?
```

The loop continues indefinitely until Gunicorn is manually killed with Ctrl+C.

**Problem 2 — No launch script exists.**
There is no `start.sh`, `Procfile`, or `gunicorn.conf.py` in the repo. Osiris
is started by manually typing a gunicorn command in the terminal each session.
This means the correct flags are never remembered, errors recur, and there is
no consistent way to start, stop, or restart the server.

The current workaround is running Flask's built-in dev server (`python app.py`),
which is single-threaded, not suitable for production, and will freeze during
LLM inference requests because it cannot handle concurrent connections.

---

## 2. Goal

When this is shipped, Osiris can be started, stopped, and restarted with a
single command that works reliably on macOS every time, using a production-grade
server that handles concurrent requests without freezing.

---

## 3. Background and Context

The macOS fork crash has two known fixes:

**Option A — Set `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`**
This environment variable tells macOS to skip the fork safety check. It is
the officially documented workaround for this exact error. Gunicorn continues
to use its default sync workers but the crash is suppressed.

**Option B — Switch to a non-forking worker class**
Gunicorn's `gevent` or `eventlet` worker classes use cooperative multitasking
instead of forking. No child processes are created, so the fork error never
occurs. This requires installing `gevent` as a dependency.

**Chosen approach: Option A** — it requires no new dependencies, is the
documented Apple/Python solution, and keeps the worker model unchanged. It is
implemented by setting the environment variable in a startup script before
Gunicorn is invoked.

The repo currently has no launch script. This PRD adds `start.sh` to the repo
root. It becomes the single canonical way to start Osiris.

**Related ADRs:**
- ADR-001 — Establishes development framework

---

## 4. Acceptance Criteria

- [ ] AC-1: Running `./start.sh` from `~/agent` starts Osiris without any fork crash errors
- [ ] AC-2: Osiris is accessible at `http://localhost:5000` after `./start.sh` completes
- [ ] AC-3: Running `./start.sh` when Osiris is already running stops the old process and starts a fresh one
- [ ] AC-4: The script runs Gunicorn (not Flask's dev server) in the foreground so output is visible
- [ ] AC-5: `start.sh` is executable (`chmod +x`) and committed to the repo
- [ ] AC-6: No worker SIGKILL errors appear in the terminal output during startup
- [ ] AC-7: Osiris can handle a chat message while startup is complete — confirming the server is not frozen

---

## 5. Test Matrix

| Test ID | Action | Expected Result | Pass Criteria |
|---|---|---|---|
| T-003-01 | Run `pkill -f gunicorn` then `./start.sh` from `~/agent` | Gunicorn starts, no objc fork errors | Terminal shows "Booting worker" with no SIGKILL lines |
| T-003-02 | Open browser to `http://localhost:5000` after T-003-01 | Osiris login page loads | Page renders, no connection refused error |
| T-003-03 | Run `./start.sh` while Osiris is already running | Old process killed, new one starts cleanly | No "Address already in use" error |
| T-003-04 | Send a chat message after startup | Osiris responds | Response received, server did not freeze |
| T-003-05 | Check terminal output during startup | No SIGKILL, no objc fork error lines | Clean startup log only |
| T-003-06 | Run `cat start.sh` | Script content is readable and correct | File is plain text, not a socket |
| T-003-07 | Run `ls -la start.sh` | File has execute permission | Permissions show `-rwxr-xr-x` or similar with `x` bit set |

---

## 6. Scope

### In Scope
- `start.sh` — new file at repo root, creates the canonical startup command
- `app.py` — no changes required

### Out of Scope
- `app.py` — do not modify
- `static/index.html` — do not modify
- Installing new Python packages (gevent, eventlet) — Option A requires none
- Creating a launchd service or system daemon — that is a separate future feature
- The frontend refactor (FEATURE-004)

---

## 7. Implementation Notes

The script should:

1. Kill any existing Gunicorn process on port 5000 cleanly before starting
2. Set `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` in the environment
3. Activate the virtual environment at `~/agent/venv`
4. Start Gunicorn with sensible defaults for a single-user home assistant:
   - `--workers 1` — one worker is sufficient; more workers just multiply the fork crash risk
   - `--threads 4` — threads within the single worker handle concurrency without forking
   - `--bind 0.0.0.0:5000` — accessible from any device on the home network
   - `--timeout 300` — LLM inference can take time; default 30s timeout will kill requests mid-stream
5. Run in the foreground (no `--daemon`) so output is visible and Ctrl+C stops it cleanly

The script must use `#!/bin/bash` and be stored at `~/agent/start.sh`.

Example structure (Claude Code should implement this, not copy it verbatim):
```bash
#!/bin/bash
# Kill existing process if running
# Activate venv
# Export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
# Start gunicorn with correct flags
```

---

## 8. Rollback Plan

`start.sh` is a new file. Rolling back means deleting it — the repo returns
to its prior state where Osiris was started manually.

1. `git revert <merge-commit-sha>`
2. `git push origin main`
3. Start Osiris manually in the interim: `python app.py` from `~/agent`

No Gunicorn restart needed — the revert does not affect a running process.

---

## 9. Definition of Done

A PR for this feature is ready to merge when:

- [ ] All acceptance criteria (AC-1 through AC-7) are met
- [ ] All Test Matrix items (T-003-01 through T-003-07) are PASS
- [ ] Only `start.sh` was added — no other files modified
- [ ] PR description includes test results for every Test ID
- [ ] PR description includes "Closes #NNN"
- [ ] No secrets, tokens, or credentials appear anywhere in the diff
