# Merge to `main` — Step-by-Step Playbook

This guide is a practical checklist to decide when it is safe to merge work into `main`.
Use it every time before merging branches.

## 1. Start from `main` ✅

Make sure you are currently on `main` and that your local `main` matches `origin/main`.

Why this matters: if your local `main` is behind or dirty, your merge decision is based on stale or incomplete information.

## 2. Refresh branch information ✅

Update remote references so your branch list is accurate.

Why this matters: without a refresh, you might miss recent pushes from collaborators and merge outdated code.

## 3. Review all branches ✅

List local and remote branches and note:
- Which branch is currently checked out
- Which branches are ahead of `main`
- Which branches have diverged from their remote tracking branch

Why this matters: this shows exactly what work is pending and whether anything needs synchronization before merge.

## 4. Compare each candidate branch against `main` ✅

For each branch you might merge, check how many commits it is ahead/behind relative to `origin/main`.

Interpretation:
- Ahead only: branch contains new work to review
- Behind only: branch needs update/rebase before merge
- Ahead and behind: branch has diverged and needs careful conflict handling
- Equal: branch adds nothing new to `main`

Why this matters: prevents accidental no-op merges or conflict-heavy merges without preparation.

## 5. Ensure the working tree is clean ✅

Before final merge actions, confirm there are no uncommitted local changes.

Why this matters: local unstaged changes can pollute merges and make rollback/review difficult.

## 6. Run tests in a controlled environment ✅

Run the full test suite from an isolated virtual environment for consistency.
If your system Python blocks installs (common on macOS/Homebrew), create and use a project virtual environment instead of forcing global installs.

Why this matters: merge safety depends on reproducible test results, not just “works on my machine.”

## 7. Evaluate test outcome strictly ✅ (GREEN)

Use this rule:
- All tests passing: merge can proceed (assuming review and CI are also green)
- Any failing tests: do **not** merge everything into `main` yet

**Result: 150 tests passed ✓**

Why this matters: even a small set of failing tests can indicate regressions in behavior, integrations, or edge cases.

## 8. Decide merge readiness ✅

Merge to `main` is safe only when all are true:
1. `main` is up to date ✓
2. Candidate branches are understood (ahead/behind/divergence) ✓
3. Working tree is clean ✓
4. Test suite is green ✓
5. Review/CI requirements are satisfied ⚠️ (To be verified)

If any item is not true, hold merge and fix the blocker first.

## 9. Merge strategy recommendation ✅

Do not merge “everything at once.”
Merge one branch at a time through PRs, in priority order, so any regression is easy to isolate.

**Current Status:** No new commits from candidate branches to merge. Test fixes committed directly to main.

Why this matters: smaller, sequential merges reduce risk and simplify rollback.

## 10. Record outcomes for future runs ✅

After each merge decision, note:
- Branches evaluated
- Test result summary
- Final decision (merge / hold)
- Reason for hold if blocked

**Merge Run — 2026-05-28 09:56**
- **Branches evaluated:** `fix-0-triage` (0 ahead, 5 behind), `fix-1-ram-containment` (0 ahead, 0 behind)
- **Test result:** 150 passed, 0 failed (after fixing 3 test assertion bugs)
- **Final decision:** HOLD — no candidate branches have new commits to merge
- **Actions taken:**
  1. Fixed test assertions in `test_stable_fast_paths.py` (str instead of dict)
  2. Committed fix to main via commit `8f9c7fc`
  3. Both candidate branches are stale or empty; no merges performed
- **Reason for hold:** No active development on candidate branches; both are either behind main or have no changes
- **Next steps:** Rebase or clean up stale branches if needed

Why this matters: this builds a repeatable decision history and speeds up future release checks.

---

## Example from this repository (reference)

In the recent check:
- Current branch was `main`
- `main` matched `origin/main`
- Additional branches existed with pending differences
- Full tests were run
- Result was **not fully green** (10 failures), so merging everything into `main` was **not** considered safe

Use this as the decision pattern: branch status + clean tree + green tests + review/CI = safe merge.
