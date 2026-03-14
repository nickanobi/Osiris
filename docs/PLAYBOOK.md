# Osiris Development Playbook
**How we build features using Claude Chat, Claude Code, and GitHub**

---

## The Short Version

Every feature follows the same loop, every time:

```
Claude Chat authors a PRD → commit it to the repo →
Claude Code reads it and implements → PR opened →
human reviews and merges → feature shipped
```

This document explains each step in full so any new Claude Chat session
can pick up exactly where the last one left off.

---

## Part 1 — The Stack and the Repo

### What Osiris Is
A local-first AI home assistant running on a Mac Studio M3 (96GB unified
memory) on the home network. No cloud dependency for core functionality.
Inference runs via Ollama with llama3.1:70b locally.

### The Stack
| Layer | Technology |
|---|---|
| Hardware | Mac Studio M3, 96GB unified memory |
| Inference | Ollama — llama3.1:70b |
| Backend | Flask + Gunicorn (Python) |
| Frontend | static/index.html (monolithic — refactor planned) |
| Storage | JSON files per user |
| Auth | Werkzeug password hashing, Flask sessions |
| Repo | https://github.com/nickanobi/Osiris |
| Mac repo path | ~/agent |

### The Division of Labor
| Tool | Role |
|---|---|
| Claude Chat | Planning, PRD authoring, architectural thinking |
| Claude Code | Reading PRDs, implementing, branching, committing, opening PRs |
| GitHub | Version control, branch protection, PR review, traceability |
| Human | Approving PRs, merging, architectural decisions |

Claude Chat cannot push to GitHub directly (egress proxy blocks api.github.com).
Claude Code runs on the Mac and has full filesystem and git access.

---

## Part 2 — One-Time Setup (Already Done)

This section documents what was set up so it does not need to be repeated.
If starting fresh on a new machine, follow these steps.

### GitHub Repository
- Repo: https://github.com/nickanobi/Osiris (public)
- Branch protection on main — direct pushes rejected, PRs required
- .gitignore protects secrets and local config
- Custom labels configured for Issues

### Folder Structure in the Repo
```
~/agent/
├── AGENTS.md                          ← Claude Code reads this first every session
├── README.md
├── app.py                             ← Flask application
├── static/index.html                  ← Frontend
├── templates/
├── docs/
│   ├── adr/                           ← Architecture Decision Records
│   │   └── ADR-001-*.md
│   └── prd/                           ← Product Requirements Documents
│       ├── TEMPLATE.md                ← Reusable PRD template
│       └── FEATURE-NNN-*.md           ← One file per feature
```

### Claude Code Installation (Mac Studio)
```bash
# Install
curl -fsSL https://claude.ai/install.sh | bash

# Add to PATH (run once, then reload shell)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc

# Verify
claude --version

# Install gh CLI (required for Issue and PR creation)
brew install gh

# Authenticate gh
gh auth login
# Choose: GitHub.com → HTTPS → Login with web browser
```

Claude Code authenticates to Anthropic via your Claude.ai account (Pro or Max).
It connects to Anthropic's cloud for inference — it does NOT use the local
Ollama instance. The local Ollama is what Osiris itself uses at runtime.

### GitHub CLI Authentication
```bash
gh auth login
# Select: GitHub.com → HTTPS → Login with web browser
```

**Never share GitHub tokens in chat.** Claude Code uses `gh` for all GitHub
operations. If `gh` is not installed, install it — do not work around it with
curl + hardcoded tokens.

---

## Part 3 — The Development Loop (Ralph Wiggum Loop)

This is the repeatable process for every feature. Follow it in order.

### Step 1 — Identify the Feature
Features come from one of three sources:
- A known bug (listed in AGENTS.md and the Issues backlog)
- A new capability discussed in Claude Chat
- An item from the planned backlog

Every feature needs a GitHub Issue and a PRD before any code is written.

### Step 2 — Author the PRD in Claude Chat
Claude Chat writes the PRD. The PRD template lives at `docs/prd/TEMPLATE.md`.

A good PRD contains:
- **Problem Statement** — what is broken or missing
- **Goal** — one sentence, user-facing outcome
- **Acceptance Criteria** — checkable, verb-first statements
- **Test Matrix** — specific tests Claude Code will run, with unambiguous pass/fail criteria
- **Scope** — explicit list of files in scope AND explicit out-of-scope items
- **Implementation Notes** — constraints or hints (optional)
- **Rollback Plan** — how to undo the change after merge

Name the file: `docs/prd/FEATURE-NNN-short-description.md`

### Step 3 — Commit the PRD to the Repo
Claude Chat cannot push to GitHub directly. Use the GitHub web UI:

1. Go to https://github.com/nickanobi/Osiris
2. Navigate to `docs/prd/`
3. **Add file → Create new file**
4. Name: `docs/prd/FEATURE-NNN-short-description.md`
5. Paste contents
6. **Select "Create a new branch"** — name it `feature/add-prd-FEATURE-NNN`
7. Open PR → merge
8. On Mac: `git pull origin main`

### Step 4 — Start Claude Code on the Mac
SSH into the Mac or use the local terminal:

```bash
cd ~/agent
claude
```

Claude Code will read AGENTS.md automatically on startup. It knows the
project structure, the branch naming convention, the commit format, and
the loop steps from that file.

### Step 5 — Give Claude Code the Prompt
At the Claude Code `>` prompt, paste:

```
Read AGENTS.md, then read docs/prd/FEATURE-NNN-short-description.md.
Create a GitHub Issue for this feature, then check out a new branch
following the naming convention in AGENTS.md. Implement the fix described
in the PRD. Run every test in the test matrix and report results. Open a
PR when all tests pass.
```

Replace `FEATURE-NNN-short-description` with the actual filename.

### Step 6 — Monitor and Approve
Claude Code will ask for approval before:
- Running bash commands
- Editing files
- Creating Issues and PRs

**Approve:** file reads, bash diagnostics, code edits that match the PRD scope,
git operations, `gh issue create`, `gh pr create`

**Stop and review if:**
- Claude Code proposes editing a file listed in the PRD's Out of Scope section
- Claude Code tries to use a hardcoded token in a curl command instead of `gh`
- Claude Code proposes an architectural change not described in the PRD
- Anything feels surprising or outside the stated scope

If in doubt, hit **No** and come to Claude Chat to discuss before proceeding.

### Step 7 — Review the PR
Claude Code opens the PR. Before merging:

1. Open the PR link it provides
2. Read the diff — check every file changed
3. Confirm only files listed in the PRD's In Scope section were modified
4. Confirm all Test IDs show PASS in the PR description
5. Confirm "Closes #NNN" appears in the PR description
6. Confirm no secrets or tokens appear anywhere in the diff

If the diff looks correct, approve and merge on GitHub.

### Step 8 — Pull and Verify
```bash
cd ~/agent
git checkout main
git pull origin main
```

Restart Gunicorn to pick up any backend changes:
```bash
pkill -f gunicorn
cd ~/agent
source venv/bin/activate
gunicorn --bind 0.0.0.0:5000 app:app
```

Open Osiris in the browser and manually verify the feature works as described
in the PRD's acceptance criteria.

---

## Part 4 — Branch and Commit Conventions

### Branch Names
```
feature/<issue-number>-<short-description>
bugfix/<issue-number>-<short-description>
hotfix/<issue-number>-<short-description>
```

Examples:
```
feature/6-conversation-history-render
bugfix/7-memory-perspective-rewrite
feature/add-prd-feature-001          ← for doc-only PRs
```

All lowercase. Hyphens only. Issue number first after the prefix.

### Commit Messages
```
<what changed> -- Closes #<issue-number>
```

Examples:
```
Fix conversation history blank screen on topic click -- Closes #6
Add messages field to /api/topics response -- Closes #9
```

Present tense. Plain English. Always include the issue reference.

---

## Part 5 — Starting a New Claude Chat Session

When starting fresh in a new Claude Chat, provide this context:

1. Upload the session notes file (if one exists) or paste this document
2. Say: *"We are building Osiris, a local-first AI assistant on a Mac Studio M3.
   The repo is at https://github.com/nickanobi/Osiris. We use Claude Code on the
   Mac to implement features driven by PRDs. Read the playbook and tell me where
   we left off."*
3. Claude Chat will read the playbook, check the known backlog, and be ready
   to author the next PRD

The playbook, AGENTS.md, and the PRD files in the repo are the source of truth.
Chat history is not reliable across sessions — the repo always wins.

---

## Part 6 — Known Gotchas

These have caused failures before. Do not repeat them.

| Gotcha | What happens | Prevention |
|---|---|---|
| Token in chat | GitHub PAT exposed in conversation | Never share tokens in chat. Claude Code uses `gh auth login` |
| Heredoc via SSH paste | Em dashes corrupt, terminator breaks | Use GitHub web UI for doc files, Claude Code for code files |
| GitHub API from Claude Chat | api.github.com is blocked by egress proxy | Claude Chat authors content. Claude Code makes GitHub calls |
| Gunicorn fork crash on macOS | objc fork() error, workers SIGKILL | Use `--worker-class=gthread --workers=1` or run without daemon |
| PRD scope assumptions | PRD said app.py was fine, it needed a 1-line change | Verify backend assumptions against actual code before marking out of scope |
| Port 5000 already in use | New gunicorn fails to bind | `lsof -i :5000` → `kill <PID>` then restart |
| Claude Code editing out-of-scope files | Scope creep, unexpected changes | Read the Out of Scope section carefully before approving edits |
| npm not found | Claude Code install fails | macOS needs Node via `brew install node` OR use the native installer: `curl -fsSL https://claude.ai/install.sh | bash` |

---

## Part 7 — Current Backlog

| ID | Description | Status |
|---|---|---|
| FEATURE-001 | Conversation history renders blank when topic clicked | ✅ Shipped — PR #10 |
| FEATURE-002 | Memory perspective wrong — rewrite_to_third_person() stores user facts as Osiris's own memories | PRD not yet written |
| FEATURE-003 | Frontend refactor — break monolithic index.html into css/ and js/ modules | Blocked until FEATURE-002 ships |

---

## Part 8 — Restarting Osiris (Gunicorn)

```bash
# Find and kill existing process
lsof -i :5000
kill <PID>

# Restart
cd ~/agent
source venv/bin/activate
gunicorn --bind 0.0.0.0:5000 app:app

# If fork errors appear, use gthread worker
gunicorn --bind 0.0.0.0:5000 --worker-class=gthread --workers=1 app:app
```

Hard-refresh the browser after restart: `Cmd+Shift+R`

---

*This document lives at `docs/PLAYBOOK.md` in the repo.*
*It is the first thing to read at the start of any new session.*
*Last updated: March 2026*
