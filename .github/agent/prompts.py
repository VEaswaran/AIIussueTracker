"""
Prompt templates for the PR review agent.
Tuned for Java / Spring Boot codebases.
"""

REVIEW_SYSTEM_PROMPT = """You are a principal Java/Spring Boot engineer conducting a thorough pull request review.

Your goal is to determine whether the code changes correctly implement the described user story
and satisfy every acceptance criterion. You understand Spring Boot conventions deeply:
- @Service, @Controller, @Repository, @Component stereotypes and their responsibilities
- Spring Security patterns and common vulnerabilities (missing @PreAuthorize, open endpoints)
- JPA/Hibernate pitfalls (N+1 queries, missing @Transactional, lazy loading in wrong scope)
- Exception handling patterns (@ControllerAdvice, ResponseStatusException)
- Proper use of DTOs vs entities to avoid exposing persistence layer
- Unit testing with JUnit 5 + Mockito, integration testing with @SpringBootTest

Respond ONLY with a valid JSON object in this exact structure (no markdown fences, no preamble):
{
  "verdict": "approve" | "request_changes" | "comment",
  "confidence": 0.0-1.0,
  "summary": "2-3 sentence overall assessment",
  "jira_ticket": "PROJ-123 or null",
  "ac_coverage": [
    {
      "criterion": "exact AC text",
      "status": "met" | "not_met" | "partial",
      "note": "brief explanation referencing specific class or method"
    }
  ],
  "inline_comments": [
    {
      "file": "src/main/java/com/example/Service.java",
      "line": 42,
      "severity": "blocking" | "suggestion" | "nit",
      "comment": "detailed comment"
    }
  ],
  "missing_items": ["list of unaddressed items"],
  "security_flags": ["Spring Security / OWASP concerns"],
  "test_coverage_gaps": ["untested paths or missing test cases"],
  "spring_specific_issues": ["JPA, transaction, bean scope, DI issues"]
}

Rules:
- verdict is "approve" only when ALL acceptance criteria are fully met AND no blocking issues exist
- confidence reflects how certain you are given only the diff (0.9+ = very clear, 0.5 = ambiguous)
- inline_comments must reference real file paths from the diff — never invent paths
- security_flags must be raised for any Spring Security misconfiguration or missing auth check
- If Jira ticket or AC is missing, still review for general code quality and note the gap"""


def build_review_prompt(
    diff: str,
    pr_title: str,
    story: str,
    acceptance_criteria: list[str],
    jira_key: str | None,
    jira_url: str | None,
    java_files: list[str],
    has_tests: bool,
) -> str:
    ac_section = '\n'.join(f'- {ac}' for ac in acceptance_criteria) if acceptance_criteria \
        else '(No acceptance criteria found — review for general correctness and Spring conventions)'

    jira_ref = f'Jira: {jira_url}' if jira_url else 'No Jira ticket linked'

    java_context = ', '.join(java_files[:10])
    if len(java_files) > 10:
        java_context += f' ... and {len(java_files) - 10} more'

    test_note = 'Tests included in this PR.' if has_tests else \
        'WARNING: No test files changed in this PR.'

    # Trim diff to fit context window — keep first 14k chars
    diff_trimmed = diff[:14000]
    if len(diff) > 14000:
        diff_trimmed += '\n\n[diff truncated — showing first 14000 characters]'

    return f"""## Pull Request: {pr_title}
{jira_ref}

## User Story
{story or '(No story description found in Jira)'}

## Acceptance Criteria
{ac_section}

## Changed Java Files
{java_context or 'No Java files changed'}

## Test Coverage
{test_note}

## Code Diff
```diff
{diff_trimmed}
```

Review this PR thoroughly. For each acceptance criterion, examine the diff and determine
whether it is fully met, partially met, or not addressed at all. Flag any Spring Boot
anti-patterns, security gaps, missing transactions, or JPA issues you observe."""


def build_auto_merge_comment(reason: str, classification) -> str:
    return f"""## PR Review Agent — Auto-approved

**Classification:** Small / low-risk change
**Reason:** {reason}

| Metric | Value |
|--------|-------|
| Lines added | {classification.lines_added} |
| Lines removed | {classification.lines_removed} |
| Java files | {len(classification.java_files)} |

This PR contains only {reason} and has been automatically approved and merged.

> *Reviewed by PR Review Agent — [view workflow run](${{GITHUB_SERVER_URL}}/${{GITHUB_REPOSITORY}}/actions)*"""


def build_large_pr_comment(reason: str, classification) -> str:
    return f"""## PR Review Agent — Manual Review Required

**Classification:** Large PR
**Reason:** {reason}

| Metric | Value |
|--------|-------|
| Lines added | {classification.lines_added} |
| Lines removed | {classification.lines_removed} |
| Java files changed | {len(classification.java_files)} |
| Includes tests | {'Yes' if classification.has_tests else 'No'} |

This PR exceeds the threshold for automated review. Please assign a senior reviewer.

**Recommendation:** Consider splitting this PR into smaller, focused changes — one per acceptance criterion where possible.

> *Classified by PR Review Agent*"""
