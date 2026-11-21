---
name: git-commit-rules
description: >-
  Enforces the user's git commit discipline whenever the agent needs to
  stage files and create a git commit. Activate this skill before every
  git add / git commit operation.

---

# Git Commit Rules

Follow every rule below when staging and committing code. No exceptions.

---

## 1. Stage only the relevant files

1. Run `git status` to review all changes.
2. Stage **only** the files that belong to this logical change with
   `git add <path>` (one or more explicit paths).
3. Run `git diff --cached --stat` to verify the staged set.

**Never** use `git add .`, `git add -A`, `git add --all`, or `git add *`.
If you staged a file by mistake, undo it with `git reset HEAD <path>`.

## 2. One commit = one atomic change

Each commit must be atomic, complete, and buildable.

- One indivisible task → one commit.
- Multiple independent tasks → multiple separate commits.
- Never commit code that is known to be broken.
- Never create fix-up commits on a development branch.

### Self-check before committing

> Does this change finish or fix the previous commit?
> If **yes** → `git reset --soft HEAD~1`, amend, and re-commit
> instead of creating a new commit.

Even if two commits are individually clean, the second one "completing"
the first still counts as a fix-up and must be squashed.

### Already-pushed commits

Any history rewrite, `--amend`, or `--force-push` on a pushed branch
requires explicit user approval first. Ask before proceeding.

### Exploratory work

Use `temp/`, `wip/`, or `scratch/` branches for experiments. Never merge
them directly; create a clean branch and re-organize as atomic commits.

## 3. Commit message content

### Subject line

- **Imperative mood**, e.g. "Add …", "Fix …", "Remove …".
- **≤ 72 characters**.
- **No trailing period**.
- Describe the behavior or capability introduced, not the files touched.

### Body

- **Required** unless the subject is completely self-explanatory for a
  simple change.
- Explain the root cause and the reason for this fix / change — why this
  is a bug, why this change is needed.
- **Do NOT**:
  - List changes file-by-file (the diff already shows that).
  - Describe implementation steps that are obvious from the diff.
  - Describe intermediate versions within the same patch
    (e.g. "v2 fixed X").
- Describe only the final state relative to the parent commit.

### Format template

```text
<subject>

<body – why, not how>
```

Separate the subject from the body with one blank line.

## 4. Trust the reader

Assume the reader is a qualified developer familiar with the project.
Do **not** include:

- How to build the project (that belongs in documentation).
- Obvious method descriptions or usage examples.
- "Build succeeded", "all tests pass", or similar — a committed change
  implies it works.

**Only mention non-obvious information:**

- New test commands or tools not yet documented in the project.
- Non-standard configurations required to reproduce results.
- Unusual constraints that affect data interpretation.
