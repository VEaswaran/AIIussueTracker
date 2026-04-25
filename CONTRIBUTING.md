# Contributing guide

This repo uses an automated PR review agent that reads your Jira story and acceptance criteria
to give you a meaningful review — not just code smell. Follow these guidelines to get the best results.

---

## Before you raise a PR

### 1. Your Jira ticket must have acceptance criteria

The agent fetches your ticket and checks each AC against the code. If they're missing, it can only
do generic code quality review.

**Good Jira description:**
```
## Story
As a customer service agent, I want to search orders by customer email
so that I can resolve support queries quickly.

## Acceptance Criteria
- Given a valid email, the endpoint returns all matching orders sorted by date descending
- Given an invalid email format, the endpoint returns HTTP 400 with a validation error message
- Given an email with no matching orders, the endpoint returns an empty list with HTTP 200
- All search requests must be logged at INFO level with the masked email
- The endpoint must be protected — unauthenticated requests return HTTP 401
```

### 2. Link your ticket in the PR title or body

The agent scans for a Jira key in these formats:

```
[PROJ-123] Add order search endpoint by email     ← PR title
PROJ-123                                           ← anywhere in body
Jira: https://yourorg.atlassian.net/browse/PROJ-123
```

### 3. Keep PRs focused

The agent classifies PRs by size:

| Size | What it means | Agent action |
|------|---------------|--------------|
| Small | Config, logs, version bumps only | Auto-approved and merged |
| Medium | < 400 lines of logic changes | Full AI review with your AC |
| Large | 400+ lines changed | Flagged for senior human review |

**Split large features into per-AC PRs where possible.** One PR per acceptance criterion is ideal.

---

## Raising the PR

1. Use the PR template (auto-loaded) — fill in the Jira key
2. Write a brief summary of what changed and why
3. Check the boxes for testing — the agent will flag missing tests as a gap
4. Push and open the PR — the agent runs within ~2 minutes

---

## Reading the agent review

The agent posts a structured comment with:

```
## PR Review Agent — CHANGES REQUESTED

Confidence: 87% | Jira: PROJ-123

The endpoint is implemented correctly and handles the happy path. However,
the HTTP 400 validation and authentication check (ACs 2 and 5) are not
present in the current diff.

### Acceptance Criteria
- [PASS]    Given a valid email, returns matching orders sorted by date
- [FAIL]    Given invalid email format, returns HTTP 400           ← not implemented
- [PASS]    Given no matching orders, returns empty list + HTTP 200
- [PARTIAL] All requests logged at INFO level                      ← logging added but email not masked
- [FAIL]    Unauthenticated requests return HTTP 401               ← no @PreAuthorize found

### Security Flags
- OrderSearchController.searchByEmail() has no authentication check
```

**Verdict meanings:**

- `APPROVE` — all ACs met, no blocking issues → your human approver can merge
- `CHANGES REQUESTED` — one or more ACs not met or blocking issues found → fix and push
- `COMMENT` — review completed but the agent is uncertain → human judgment needed

---

## After the agent reviews

1. Read each `[FAIL]` and `[PARTIAL]` item
2. Fix the gaps, push to the same branch — the agent re-runs automatically
3. Once the agent approves, your designated human approver does the final check and merges

The agent's review is a **required status check** — the merge button stays locked until it passes.

---

## Questions

Raise an issue in this repo or contact the platform team.
