"""
GitHub API client.
Handles: fetching diff + files, posting PR reviews with inline comments, auto-merge.
"""
import os
import subprocess
import requests

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
REPO         = os.environ.get('REPO', '')        # e.g. "org/repo"
BASE_URL     = 'https://api.github.com'

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept':        'application/vnd.github.v3+json',
    'X-GitHub-Api-Version': '2022-11-28',
}


def get_pr_diff() -> str:
    """Use git to get the diff between base and head — more reliable than API for large diffs."""
    base_sha = os.environ.get('BASE_SHA', 'HEAD~1')
    head_sha = os.environ.get('HEAD_SHA', 'HEAD')
    try:
        result = subprocess.run(
            ['git', 'diff', base_sha, head_sha],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError:
        # Fallback to GitHub API
        return _get_pr_diff_api()


def _get_pr_diff_api() -> str:
    pr_number = os.environ.get('PR_NUMBER', '')
    r = requests.get(
        f'{BASE_URL}/repos/{REPO}/pulls/{pr_number}',
        headers={**HEADERS, 'Accept': 'application/vnd.github.v3.diff'},
        timeout=30
    )
    r.raise_for_status()
    return r.text


def get_pr_files() -> list[str]:
    pr_number = os.environ.get('PR_NUMBER', '')
    r = requests.get(
        f'{BASE_URL}/repos/{REPO}/pulls/{pr_number}/files',
        headers=HEADERS,
        params={'per_page': 100},
        timeout=15
    )
    r.raise_for_status()
    return [f['filename'] for f in r.json()]


def post_review(review: dict) -> None:
    """
    Post a structured review to the PR.
    Maps agent verdict to GitHub review event.
    Only includes inline comments where we have valid file + line references.
    """
    pr_number   = os.environ.get('PR_NUMBER', '')
    verdict_map = {
        'approve':         'APPROVE',
        'request_changes': 'REQUEST_CHANGES',
        'comment':         'COMMENT',
    }

    body = _build_review_body(review)

    # Build inline comments — only include ones with real file paths
    comments = []
    for c in review.get('inline_comments', []):
        if c.get('file') and c.get('line') and isinstance(c.get('line'), int):
            severity_label = {
                'blocking':   '[BLOCKING]',
                'suggestion': '[SUGGESTION]',
                'nit':        '[NIT]',
            }.get(c.get('severity', 'suggestion'), '[REVIEW]')
            comments.append({
                'path':     c['file'],
                'line':     c['line'],
                'side':     'RIGHT',
                'body':     f"{severity_label} {c['comment']}"
            })

    payload = {
        'body':     body,
        'event':    verdict_map.get(review.get('verdict', 'comment'), 'COMMENT'),
        'comments': comments,
    }

    r = requests.post(
        f'{BASE_URL}/repos/{REPO}/pulls/{pr_number}/reviews',
        headers=HEADERS,
        json=payload,
        timeout=20
    )
    r.raise_for_status()
    print(f'[github] Review posted — event: {payload["event"]}, inline comments: {len(comments)}')


def _build_review_body(review: dict) -> str:
    verdict   = review.get('verdict', 'comment')
    confidence = int(review.get('confidence', 0) * 100)
    summary   = review.get('summary', '')
    jira      = review.get('jira_ticket', '')

    verdict_icons = {
        'approve':         'APPROVED',
        'request_changes': 'CHANGES REQUESTED',
        'comment':         'COMMENTED',
    }

    lines = [
        f"## PR Review Agent — {verdict_icons.get(verdict, 'REVIEWED')}",
        f"**Confidence:** {confidence}%"
        + (f" | **Jira:** [{jira}]" if jira else ''),
        f"\n{summary}",
    ]

    # AC coverage table
    ac_items = review.get('ac_coverage', [])
    if ac_items:
        lines.append('\n### Acceptance Criteria')
        for ac in ac_items:
            icon = {'met': 'PASS', 'partial': 'PARTIAL', 'not_met': 'FAIL'}.get(ac.get('status', ''), '?')
            lines.append(f"- `[{icon}]` **{ac.get('criterion', '')}**")
            if ac.get('note'):
                lines.append(f"  - {ac['note']}")

    # Missing items
    missing = review.get('missing_items', [])
    if missing:
        lines.append('\n### Missing Items')
        lines.extend(f'- {m}' for m in missing)

    # Security flags
    security = review.get('security_flags', [])
    if security:
        lines.append('\n### Security Flags')
        lines.extend(f'- {s}' for s in security)

    # Spring-specific issues
    spring = review.get('spring_specific_issues', [])
    if spring:
        lines.append('\n### Spring / JPA Issues')
        lines.extend(f'- {s}' for s in spring)

    # Test coverage gaps
    test_gaps = review.get('test_coverage_gaps', [])
    if test_gaps:
        lines.append('\n### Test Coverage Gaps')
        lines.extend(f'- {t}' for t in test_gaps)

    lines.append(
        '\n---\n*Reviewed by PR Review Agent. '
        'A **CODEOWNER must approve** before this PR can be merged.*'
    )
    return '\n'.join(lines)


def post_comment(message: str) -> None:
    pr_number = os.environ.get('PR_NUMBER', '')
    r = requests.post(
        f'{BASE_URL}/repos/{REPO}/issues/{pr_number}/comments',
        headers=HEADERS,
        json={'body': message},
        timeout=15
    )
    r.raise_for_status()


def get_pr_author() -> str:
    """Return the GitHub login of the PR author."""
    pr_number = os.environ.get('PR_NUMBER', '')
    r = requests.get(
        f'{BASE_URL}/repos/{REPO}/pulls/{pr_number}',
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get('user', {}).get('login', '')


def _parse_codeowners() -> list[str]:
    """
    Parse .github/CODEOWNERS and return a flat list of GitHub logins (without @).
    Handles lines like:  *   @vijay-vj   or   src/  @org/team
    Team handles (org/team) are returned as-is so the caller can decide.
    """
    owners: list[str] = []
    codeowners_path = os.path.join(
        os.environ.get('GITHUB_WORKSPACE', '.'), '.github', 'CODEOWNERS'
    )
    try:
        with open(codeowners_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Each token after the first is an owner
                parts = line.split()
                for part in parts[1:]:
                    login = part.lstrip('@')
                    if login and login not in owners:
                        owners.append(login)
    except FileNotFoundError:
        print('[github] CODEOWNERS file not found — assuming no codeowner restriction')
    return owners


def has_codeowner_approval(codeowners: list[str]) -> bool:
    """
    Return True if at least one CODEOWNER has submitted an APPROVED review
    on the current PR (and that approval has not been dismissed).
    """
    pr_number = os.environ.get('PR_NUMBER', '')
    r = requests.get(
        f'{BASE_URL}/repos/{REPO}/pulls/{pr_number}/reviews',
        headers=HEADERS,
        params={'per_page': 100},
        timeout=15,
    )
    r.raise_for_status()

    # Walk reviews newest-first; track latest state per reviewer
    latest: dict[str, str] = {}
    for review in r.json():
        login = review.get('user', {}).get('login', '')
        state = review.get('state', '')
        if login and login not in latest:
            latest[login] = state

    for owner in codeowners:
        # Skip org/team entries (contain '/') — GitHub handles those server-side
        if '/' in owner:
            continue
        if latest.get(owner) == 'APPROVED':
            print(f'[github] Codeowner approval found from: {owner}')
            return True

    print(f'[github] No codeowner approval yet — codeowners: {codeowners}')
    return False


def auto_merge(reason: str) -> bool:
    """Attempt squash merge. Returns True on success."""
    pr_number = os.environ.get('PR_NUMBER', '')
    pr_title  = os.environ.get('PR_TITLE', f'PR #{pr_number}')
    r = requests.put(
        f'{BASE_URL}/repos/{REPO}/pulls/{pr_number}/merge',
        headers=HEADERS,
        json={
            'merge_method':    'squash',
            'commit_title':    f'Auto-merge: {pr_title}',
            'commit_message':  f'Auto-merged by PR Review Agent\nReason: {reason}',
        },
        timeout=15
    )
    if r.status_code == 200:
        return True
    print(f'[github] Auto-merge failed: {r.status_code} {r.text}')
    return False
