# PRD — [Feature Name]

**ID:** FEATURE-NNN  
**Status:** Draft | Ready for Implementation | In Progress | Shipped  
**Author:** Claude Chat  
**Created:** YYYY-MM-DD  
**GitHub Issue:** #NNN (created when implementation begins)  
**Branch:** `feature/NNN-short-description` (created when implementation begins)  

---

## 1. Problem Statement

> What is broken or missing? Why does it matter to the user?
> Be specific — describe the symptom, not the solution.

---

## 2. Goal

> One or two sentences. What does success look like from the user's perspective?
> Finish this sentence: "When this is shipped, a user will be able to..."

---

## 3. Background and Context

> Any relevant history, prior attempts, related ADRs, or technical context
> Claude Code needs to understand before reading the acceptance criteria.
> Keep this brief — link to ADRs rather than repeating them.

**Related ADRs:**
- ADR-NNN — [Title]

---

## 4. Acceptance Criteria

> These are the definition of done. Every item must be true before the PR is opened.
> Write each criterion as a checkable statement starting with a verb.

- [ ] AC-1: [Verb] [observable outcome]
- [ ] AC-2: [Verb] [observable outcome]
- [ ] AC-3: [Verb] [observable outcome]

---

## 5. Test Matrix

> One row per test. Claude Code runs every test in this table and reports PASS or FAIL.
> Tests must be specific enough that pass/fail is unambiguous.

| Test ID | Action | Expected Result | Pass Criteria |
|---|---|---|---|
| T-NNN-01 | [Do this] | [See this] | [How to confirm PASS] |
| T-NNN-02 | [Do this] | [See this] | [How to confirm PASS] |
| T-NNN-03 | [Do this] | [See this] | [How to confirm PASS] |

---

## 6. Scope

### In Scope
> Explicit list of files and behaviors this PRD covers.

- `path/to/file.py` — [what changes]
- `path/to/other.py` — [what changes]

### Out of Scope
> Explicit list of things that are NOT part of this PRD, even if related.
> Claude Code must not touch anything listed here.

- [Related thing that will be addressed in a separate PRD]
- [Refactor that is tempting but not part of this fix]

---

## 7. Implementation Notes

> Optional. Hints, constraints, or approach suggestions for Claude Code.
> Do not over-specify — describe the what, not the how, unless there is a specific
> technical constraint that must be respected.

---

## 8. Rollback Plan

> How do we undo this if it breaks something after merge?
> Be specific — file restores, git reverts, service restarts as needed.

1. `git revert <merge-commit-sha>`
2. `git push origin main`
3. Restart Gunicorn: `sudo systemctl restart osiris` (or equivalent)
4. Verify rollback by [specific check]

---

## 9. Definition of Done

A PR for this feature is ready to merge when:

- [ ] All acceptance criteria are met
- [ ] All Test Matrix items are PASS
- [ ] No files outside the In Scope list were modified
- [ ] PR description includes test results for every Test ID
- [ ] PR description includes "Closes #NNN"
- [ ] No secrets, tokens, or credentials appear anywhere in the diff
