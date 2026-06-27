# Plan: Per-skill Background Review Protection

## Problem

The background self-improvement review fork (`agent/background_review.py`) can call `skill_manage(action="patch"/"edit"/"write_file")` on **any** skill — including bundled skills the user never intended to modify, and custom skills the user maintains manually. This happens silently after every N turns (`_skill_nudge_interval`), with no per-skill opt-out.

Observed damage (2026-06-17): `git-history-rewrite` (bundled), `agora-dev` (custom), and `USER.md` were auto-patched without user consent.

## Goal

Add a config-driven per-skill protection list that blocks **write actions** from the background review fork only. Foreground (normal conversation) `skill_manage` calls remain unaffected.

## Design

### 1. Config key: `skills.review_protected`

```yaml
skills:
  review_protected:
    - git-history-rewrite
    - agora-dev
```

- List of skill names.
- Empty by default (back-compat).
- Read once at review-fork spawn time and passed to the threadlocal.

### 2. Threadlocal guard in `skill_manager_tool.py`

New threadlocal + setter/clearer, mirroring the existing `set_thread_tool_whitelist` pattern from `plugins.py`:

```python
_review_protected_skills = threading.local()

def set_review_protected_skills(names: Set[str]) -> None:
    _review_protected_skills.names = names or None

def clear_review_protected_skills() -> None:
    _review_protected_skills.names = None
```

New guard function next to the existing `_pinned_guard`:

```python
def _review_protected_guard(action: str, name: str) -> Optional[str]:
    protected = getattr(_review_protected_skills, "names", None)
    if not protected:
        return None
    if action not in {"create", "edit", "patch", "write_file", "remove_file"}:
        return None  # view, list, etc. are allowed
    if name in protected:
        return (
            f"Skill '{name}' is protected from background self-improvement review. "
            f"Use skill_manage in a foreground turn to modify it."
        )
    return None
```

### 3. Dispatch integration

In `handle_skill_manage()` (the main dispatch function), after the existing `_pinned_guard(name)` check, add:

```python
_review_protected_block = _review_protected_guard(action, name)
if _review_protected_block:
    return json.dumps({"success": False, "error": _review_protected_block})
```

This needs to fire **before** any write occurs but **after** name validation so the guard gets a clean `name`.

### 4. Review fork activation (`background_review.py`)

Before `review_agent.run_conversation(...)`, read config and set the threadlocal:

```python
# Read protected list from config
_protected_names: Set[str] = set()
try:
    from hermes_cli.config import cfg_get
    _raw = cfg_get("skills.review_protected", [])
    if isinstance(_raw, list):
        _protected_names = {str(n).strip() for n in _raw if str(n).strip()}
except Exception:
    pass

from tools.skill_manager_tool import (
    set_review_protected_skills,
    clear_review_protected_skills,
)
set_review_protected_skills(_protected_names)
try:
    review_agent.run_conversation(...)
finally:
    clear_review_protected_skills()
    clear_thread_tool_whitelist()
```

The `set_review_protected_skills` call sits **inside** the existing `try/finally` that already wraps `clear_thread_tool_whitelist`, so cleanup is guaranteed on both success and exception paths.

### 5. DEFAULT_CONFIG entry (`hermes_cli/config.py`)

Under the `skills:` section in `DEFAULT_CONFIG`:

```python
"skills": {
    # ... existing keys ...
    "review_protected": [],  # list of skill names protected from background review fork
},
```

## Files to Change

| # | File | Change |
|---|------|--------|
| 1 | `tools/skill_manager_tool.py` | Add `_review_protected_skills` threadlocal, `set/clear_review_protected_skills()`, `_review_protected_guard()`, dispatch integration |
| 2 | `agent/background_review.py` | Read config, call `set/clear_review_protected_skills()` around review run |
| 3 | `hermes_cli/config.py` | Add `"review_protected": []` to DEFAULT_CONFIG `skills` section |
| 4 | `tests/tools/test_skill_manager_tool.py` | Test: protected skill patch blocked when threadlocal set; allowed when unset |
| 5 | `tests/run_agent/test_background_review.py` | Test: review fork respects protected list from config |

## Invariants

1. **Foreground never blocked** — threadlocal is only set inside the review fork's daemon thread; the main conversation thread never sets it.
2. **Read-only actions pass** — `skill_view`, `skills_list` etc. are never blocked by the guard (`action` whitelist).
3. **Cleanup guaranteed** — `clear_review_protected_skills()` in the same `finally` block as `clear_thread_tool_whitelist()`.
4. **Back-compat** — empty list (default) → no behavior change.
5. **No API change** — the guard returns a tool-result JSON string with `success: False` + `error`, same shape as `_pinned_guard`.

## Test Plan

### Unit tests (`test_skill_manager_tool.py`)

- `test_review_protected_blocks_patch`: threadlocal set with `"foo"` → `skill_manage(action="patch", name="foo")` → `success: False`
- `test_review_protected_blocks_edit`: same for `action="edit"`
- `test_review_protected_blocks_write_file`: same for `action="write_file"`
- `test_review_protected_allows_view`: `action="view"` on protected skill → succeeds
- `test_review_protected_allows_unprotected`: threadlocal set with `"foo"` → `skill_manage(action="patch", name="bar")` → succeeds
- `test_review_protected_unset_allows_all`: threadlocal not set → all actions succeed

### Integration test (`test_background_review.py`)

- `test_background_review_respects_protected_config`: config has `skills.review_protected: ["test-skill"]` → review fork attempts patch → tool returns refusal message → skill file unchanged on disk

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Review fork wastes tokens trying to patch a protected skill and retrying | The refusal message is clear ("protected from background review"); the review prompt already handles "Nothing to save" gracefully |
| User forgets they added a skill to the list and wonders why it's not improving | Log at INFO when the guard fires |
| Config key misspelled → silently no protection | Log at WARNING when `review_protected` is present but not a list |
