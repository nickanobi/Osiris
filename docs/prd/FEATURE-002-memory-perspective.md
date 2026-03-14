# PRD — Memory Perspective and Grammar Fix

**ID:** FEATURE-002  
**Status:** Ready for Implementation  
**Author:** Claude Chat  
**Created:** 2026-03-14  
**GitHub Issue:** TBD (created by Claude Code when implementation begins)  
**Branch:** TBD (created by Claude Code when implementation begins)  

---

## 1. Problem Statement

When a user tells Osiris to remember a fact, `rewrite_to_third_person()` converts
first-person input into third-person facts for storage. The function has two bugs:

**Bug 1 — Only rewrites phrases at the start of the string.**
The function checks `lower.startswith(original)` for each substitution. If the
matched phrase appears anywhere other than position 0, it is not replaced. This
means mid-sentence first-person references are stored verbatim.

Example:
- Input: `"I take my coffee with cream and I prefer oat milk"`
- After stripping "remember that ": `"I take my coffee with cream and I prefer oat milk"`
- `"i "` matches at position 0 → becomes `"the user take my coffee with cream and I prefer oat milk"`
- The second `"I"` is untouched — stored with first-person perspective mid-sentence

**Bug 2 — Subject-verb agreement is broken.**
Simple string substitution replaces `"i "` with `"the user "` without adjusting
the verb. This produces grammatically incorrect facts.

Examples:
- `"I take my coffee with cream"` → `"the user take my coffee with cream"` ✗
- `"I am a software engineer"` → `"the user is a software engineer"` ✓ (handled)
- `"I live in Boston"` → `"the user live in Boston"` ✗
- `"I have two cats"` → `"the user have two cats"` ✗

These malformed facts are stored in `memory_{username}.json` and injected
directly into the system prompt. Osiris reads them as its own stated truths,
which produces confused, incorrect responses about the user.

The existing memory file shows this has already happened:
```json
{
  "id": 1,
  "key": "the_user_take_my",
  "value": "the user take my coffee with cream"
}
```

---

## 2. Goal

When this is shipped, facts stored via "remember that" will be grammatically
correct third-person statements that accurately represent user information,
not Osiris's own memories.

---

## 3. Background and Context

The relevant code path is:

```
handle_memory_commands()          # line 613 in app.py
  → strips "remember that "
  → passes raw_fact to rewrite_to_third_person()
  → stores result in memory["facts"]
  → saves to memory_{username}.json
```

The system prompt builder at line 604 injects stored facts verbatim:
```python
facts = "\n".join(f"- {fact['value']}" for fact in memory["facts"])
base += f"\n\nThings you remember about {display_name}:\n{facts}"
```

So whatever is stored is exactly what Osiris sees as context. Malformed facts
produce malformed behavior.

**Related ADRs:**
- ADR-001 — Establishes development framework

---

## 4. Acceptance Criteria

- [ ] AC-1: "remember that I take my coffee with cream" stores "the user takes my coffee with cream"
- [ ] AC-2: "remember that I am a software engineer" stores "the user is a software engineer"
- [ ] AC-3: "remember that I live in Boston" stores "the user lives in Boston"
- [ ] AC-4: "remember that I have two cats" stores "the user has two cats"
- [ ] AC-5: "remember that my name is Nick" stores "the user's name is Nick"
- [ ] AC-6: "remember that I prefer oat milk and I dislike almond milk" stores a fact with no first-person pronouns remaining
- [ ] AC-7: Facts that contain no first-person language are stored unchanged
- [ ] AC-8: The confirmation message shown to the user reflects the correctly rewritten fact
- [ ] AC-9: Existing malformed facts in memory_{username}.json files are NOT modified by this change — only new facts are affected

---

## 5. Test Matrix

| Test ID | Action | Expected Result | Pass Criteria |
|---|---|---|---|
| T-002-01 | Send "remember that I take my coffee with cream" | Confirmation message contains "the user takes" | Stored fact value contains "takes", not "take" |
| T-002-02 | Send "remember that I am a software engineer" | Stored as "the user is a software engineer" | fact["value"] == "the user is a software engineer" |
| T-002-03 | Send "remember that I live in Boston" | Stored as "the user lives in Boston" | fact["value"] == "the user lives in Boston" |
| T-002-04 | Send "remember that I have two cats" | Stored as "the user has two cats" | fact["value"] == "the user has two cats" |
| T-002-05 | Send "remember that my name is Nick" | Stored as "the user's name is Nick" | fact["value"] == "the user's name is Nick" |
| T-002-06 | Send "remember that I prefer oat milk and I dislike almond milk" | No "I" remains in stored fact | fact["value"] contains no standalone " I " |
| T-002-07 | Send "remember that the meeting is on Friday" | Stored unchanged — no first-person language | fact["value"] == "the meeting is on Friday" |
| T-002-08 | Check memory_{nick1sturn}.json after T-002-01 through T-002-07 | Only new facts added — existing fact id:1 untouched | id:1 value is still "the user take my coffee with cream" |
| T-002-09 | Send "what do you remember" after storing new facts | New facts display correctly, no first-person pronouns visible | All new fact values are third-person |

---

## 6. Scope

### In Scope
- `app.py` — rewrite the `rewrite_to_third_person()` function (lines 281–292)
- `app.py` — no other functions or lines should be modified

### Out of Scope
- `memory_{username}.json` files — do not modify existing stored facts
- `static/index.html` — frontend is not involved
- `handle_memory_commands()` — the calling function is correct, only the rewrite function needs fixing
- `build_system_prompt()` — do not change how facts are injected into the prompt
- Any migration of existing malformed facts — that is a separate decision
- The frontend refactor (FEATURE-003)

---

## 7. Implementation Notes

The current implementation only substitutes at position 0 using `startswith`.
The fix should handle first-person pronouns anywhere in the string, not just
at the start.

**Approach:** Replace all occurrences of first-person words throughout the
string, not just at position 0. Process substitutions in the right order to
avoid double-substitution (e.g., replace "i am" before "i ").

**Subject-verb agreement for "I [verb]":** When "I" is replaced with "the user",
the following verb needs to be adjusted for third-person singular:
- Common irregular verbs must be handled explicitly: have→has, are→is
- Regular verbs need an "s" appended: live→lives, take→takes, prefer→prefers
- Be careful not to double-add "s" to verbs that already end in "s"

**Do not use an external NLP library.** Keep the fix within the Python standard
library. A combination of regex substitution and a verb conjugation lookup
table for common irregular verbs is sufficient.

**Preserve the original casing** of non-pronoun parts of the string where
possible.

---

## 8. Rollback Plan

The change is isolated to one function in `app.py`. No data files are modified.

1. `git revert <merge-commit-sha>`
2. `git push origin main`
3. Restart Gunicorn:
   ```bash
   pkill -f gunicorn
   cd ~/agent && source venv/bin/activate
   gunicorn --bind 0.0.0.0:5000 app:app
   ```
4. Verify rollback: send "remember that I live in Boston" — if it stores
   "the user live in Boston" (broken), rollback succeeded

---

## 9. Definition of Done

A PR for this feature is ready to merge when:

- [ ] All acceptance criteria (AC-1 through AC-9) are met
- [ ] All Test Matrix items (T-002-01 through T-002-09) are PASS
- [ ] Only `app.py` was modified, and only within `rewrite_to_third_person()`
- [ ] PR description includes test results for every Test ID
- [ ] PR description includes "Closes #NNN"
- [ ] No secrets, tokens, or credentials appear anywhere in the diff
- [ ] `memory_{nick1sturn}.json` is unchanged (existing fact id:1 still present)
