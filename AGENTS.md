# Osiris Project — Session Notes & Remediation Log
**Date:** March 13, 2026  
**Status:** In Progress — Paused for remediation

---

## What We Are Building

### The Vision
Osiris is a local-first AI home assistant running entirely on a home network.
No cloud dependency for core functionality. Accessible from any device on
the home WiFi. Built to be extended over time into specialized domains
(home automation, Node-RED flows, voice control, and others TBD).

### The Stack
- **Hardware:** Mac Studio M3, 96GB unified memory
- **Inference:** Ollama running llama3.1:70b locally
- **Backend:** Flask + Gunicorn (Python)
- **Frontend:** Single-page app (currently monolithic index.html — refactor planned)
- **Storage:** JSON files per user (no database yet)
- **Auth:** Werkzeug password hashing, Flask sessions

### The Long-Term Goal
A structured, professionally developed local AI platform that:
- Runs specialized agents for different domains (home automation, trading, etc.)
- Is built and maintained using proper software engineering practices
- Uses Claude Chat for planning and PRD authoring
- Uses Claude Code for implementation
- Uses GitHub for version control, traceability, and quality gates

---

## How We Intend to Use GitHub

### The Workflow We Established
Every piece of work follows this sequence:

```
1.  Open a GitHub Issue describing what and why
2.  git checkout main
3.  git pull origin main
4.  git checkout -b feature/<issue-number>-<short-description>
5.  Do the work
6.  git add .
7.  git commit -m "description -- Relates to #<issue-number>"
8.  git push origin feature/<issue-number>-<short-description>
9.  Open Pull Request on GitHub
10. Write "Closes #<issue-number>" in PR description
11. Review the diff
12. Merge
13. Delete the branch
14. git checkout main
15. git pull origin main
```

### The Division of Labor
| Tool | Responsibility |
|---|---|
| Claude Chat | Planning, PRD authoring, architectural thinking |
| Claude Code | Implementation, file changes, commits, branch work |
| GitHub | Version control, branch protection, PR review, traceability |
| Mac Studio | Runtime environment, Ollama inference |

### What GitHub Infrastructure We Built Today
- Repository created at https://github.com/nickanobi/Osiris (public)
- Branch protection on main -- direct pushes rejected
- .gitignore protecting all sensitive files
- Initial codebase committed (app.py, static/, templates/, docs/)
- ADR folder structure at docs/adr/
- PRD folder structure at docs/prd/ (planned, not yet committed)
- ADR-001 written and merged via first Pull Request
- GitHub Issues backlog with 4 open items and custom labels
- Fine-grained Personal Access Token (expires August 31, 2026)

---

## What We Were Trying to Accomplish Tonight

### The PRD-Driven Development Loop (Ralph Wiggum Loop)
The goal was to establish a repeatable process where:

1. Claude Chat authors a PRD describing a feature completely
2. The PRD lives in the repo at docs/prd/
3. Claude Code reads the PRD directly from the filesystem
4. Claude Code implements against the PRD on a branch
5. A PR is opened and reviewed against the acceptance criteria
6. Merge closes the GitHub Issue automatically

### The Three Documents We Were Building
1. **AGENTS.md** -- Root-level file Claude Code reads first every session
2. **docs/prd/TEMPLATE.md** -- Reusable PRD template for all future features
3. **docs/prd/FEATURE-001-conversation-history.md** -- First real PRD for the
   conversation history rendering bug

---

## What Failed and Why

### Failure 1 -- Large file creation via SSH heredoc
**What we tried:** Pasting a large heredoc block via PowerShell SSH to create
AGENTS.md directly on the Mac.

**What went wrong:**
- Em dashes (--) corrupted to garbled characters during paste
- PowerShell SSH terminal mangled multi-line heredoc input
- The heredoc terminator (AGENTSEOF) was not recognized cleanly
- Result: broken file, stuck terminal prompt

**Root cause:** PowerShell SSH does not handle large multi-line paste reliably.
Special characters corrupt in transit. Heredocs depend on exact terminator
matching which breaks when content is mangled.

### Failure 2 -- GitHub API access from Claude Chat
**What we tried:** Using the GitHub API directly from Claude Chat's bash
environment to push AGENTS.md to the repo, bypassing the paste problem entirely.

**What went wrong:**
- Claude Chat's bash environment operates behind an egress proxy
- The proxy allowlist only permits specific domains (pypi.org, npmjs.com,
  api.anthropic.com, etc.)
- api.github.com is NOT on the allowlist
- All requests to api.github.com returned HTTP 403 with x-deny-reason:
  host_not_allowed

**Root cause:** Claude Chat's computer use environment is intentionally
network-restricted. It cannot reach GitHub's API. This is by design and
cannot be worked around from within Claude Chat.

### Failure 3 -- Token exposure
**What happened:** A GitHub Personal Access Token was shared in the chat
in an attempt to authenticate the API call. The API call failed regardless,
but the token was exposed in chat history.

**Remediation required:** The exposed token must be revoked immediately at
https://github.com/settings/tokens. A new token should be generated only
when needed and never shared in a chat interface.

---

## Remediation Plan

### Immediate Actions Required
- [ ] Revoke the exposed GitHub token at https://github.com/settings/tokens
- [ ] Generate a new token when needed (do not generate preemptively)

### The File Transfer Problem -- How to Solve It
Claude Chat cannot push to GitHub directly. The correct workflow for
creating files going forward is one of these two approaches:

**Option A -- scp from Windows to Mac (recommended for large files)**
```
1. Claude Chat creates the file and presents it for download
2. You download it to your Windows machine
3. In a local Windows PowerShell (not SSH), run:
   scp C:\Users\YourName\Downloads\filename.md nicksturniolo@192.168.1.92:/Users/nicksturniolo/agent/filename.md
4. In SSH terminal on Mac: git add, commit, push
```

**Option B -- GitHub web UI (for docs and markdown files)**
```
1. Claude Chat creates the file and presents it for download
2. Open the file in Notepad on Windows
3. Go to github.com/nickanobi/Osiris
4. Add file -> Create new file
5. Paste content into the web editor
6. Commit to a branch
7. git pull on Mac to sync
```

**Option C -- Claude Code handles all file creation (preferred long-term)**
```
Claude Code runs directly on the Mac and has full filesystem access.
It does not need files transferred to it -- it reads and writes the repo
directly. For any file that Claude Code needs to create, Claude Chat
authors the content and Claude Code writes it to disk. This is the
intended workflow once Claude Code is configured on the Mac.
```

### Claude Code Setup (Required Before Next Session)
Claude Code needs to be installed and configured on the Mac Studio so it
can read AGENTS.md and PRD files directly from the filesystem. This
eliminates the file transfer problem entirely for implementation work.

Installation steps for next session:
```bash
# On Mac Studio via SSH
npm install -g @anthropic-ai/claude-code
cd ~/agent
claude
```

Claude Code will then be able to:
- Read AGENTS.md directly from ~/agent/
- Read any PRD file from ~/agent/docs/prd/
- Write code, commit, and push without any file transfer needed

---

## What Is Ready to Pick Up Next Session

### Completed Infrastructure
- GitHub repo with branch protection
- .gitignore, README, ADR-001 all merged to main
- Issues backlog with 4 items
- Custom labels configured

### Pending -- Needs to Be Created
The following files were authored but not yet committed to the repo:

**AGENTS.md** (drafted, ready to commit)
Tells Claude Code everything about the project. Needs to be created in
the repo root via scp or GitHub web UI.

**docs/prd/TEMPLATE.md** (not yet drafted)
Reusable PRD template. To be written next session.

**docs/prd/FEATURE-001-conversation-history.md** (not yet drafted)
PRD for the conversation history rendering bug. To be written next session.

### Known Bugs Waiting for PRDs
1. **Conversation history not rendering** -- Sidebar shows stored conversations
   with correct message counts but clicking them shows a blank screen
2. **Memory perspective wrong** -- Osiris stores "I lived in X" and recalls it
   as its own memory rather than the user's fact. rewrite_to_third_person()
   exists but is not working correctly in all cases.

### Frontend Refactor (Planned After Bug Fixes)
The entire frontend lives in one monolithic static/index.html file. This
needs to be broken into a proper structure:
```
static/
├── index.html      # Structure only
├── css/
│   ├── main.css
│   ├── chat.css
│   └── sidebar.css
└── js/
    ├── app.js
    ├── chat.js
    ├── topics.js
    └── memory.js
```
This is its own PRD and its own branch. It will be done after the two
bug fixes are shipped.

---

## Key Decisions Made Today

| Decision | Rationale |
|---|---|
| GitHub public repo | Branch protection requires Team plan for private repos; public is free and the codebase contains no secrets |
| Fine-grained token over classic | GitHub recommendation; scoped to single repo with minimum permissions |
| Token expiry August 31, 2026 | GitHub strongly recommends against non-expiring tokens |
| scp/web UI for file transfer | Claude Chat cannot reach api.github.com due to egress proxy restrictions |
| Fix bugs before frontend refactor | Establishes working baseline to verify against after refactor |
| Claude Code for implementation | Claude Chat plans, Claude Code executes -- clean division of labor |

---

## Next Session Checklist

- [ ] Revoke exposed token
- [ ] Install Claude Code on Mac Studio
- [ ] Commit AGENTS.md to repo (via scp or GitHub web UI)
- [ ] Write docs/prd/TEMPLATE.md
- [ ] Write docs/prd/FEATURE-001-conversation-history.md
- [ ] Create GitHub Issue for conversation history bug (Issue #6)
- [ ] Hand PRD to Claude Code and run the loop for the first time
