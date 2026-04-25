"""
PR Review Agent — main entry point.

Flow:
  1. Get PR metadata from environment (set by GitHub Actions)
  2. Fetch the git diff and changed file list
  3. Classify the PR (small / medium / large)
  4. If small  → check CODEOWNER gate; auto-merge only if codeowner authored or approved
  5. If medium → run AI review (Jira workflow disabled — no enterprise account)
  6. If large  → post a comment flagging for manual review

CODEOWNER policy:
  - Direct merges to main require CODEOWNER approval (enforced by GitHub branch protection)
  - Agent auto-merge is additionally gated: will not merge unless the PR author IS a
    codeowner OR at least one codeowner has submitted an APPROVED review
"""
import os
import sys

from classifier    import classify_pr
# from jira_client   import extract_jira_key, fetch_jira_story  # Disabled: no Jira enterprise account
from reviewer      import run_review
from prompts       import (
    REVIEW_SYSTEM_PROMPT,
    build_review_prompt,
    build_auto_merge_comment,
    build_large_pr_comment,
)
from github_client import (
    get_pr_diff,
    get_pr_files,
    get_pr_author,
    has_codeowner_approval,
    _parse_codeowners,
    post_review,
    post_comment,
    auto_merge,
)


def main():
    pr_number = os.environ.get('PR_NUMBER', 'unknown')
    pr_title  = os.environ.get('PR_TITLE', '')
    pr_body   = os.environ.get('PR_BODY', '')

    print(f'[agent] Starting review for PR #{pr_number}: {pr_title}')

    # --- Step 1: Fetch diff and file list ---
    try:
        diff  = get_pr_diff()
        files = get_pr_files()
    except Exception as e:
        print(f'[agent] ERROR: could not fetch PR data — {e}')
        sys.exit(1)

    if not diff:
        print('[agent] Empty diff — nothing to review')
        post_comment('PR Review Agent: No diff detected. Nothing to review.')
        sys.exit(0)

    print(f'[agent] Diff: {len(diff)} chars | Files changed: {len(files)}')

    # --- Step 2: Classify ---
    classification = classify_pr(diff, files)
    print(f'[agent] Classification: {classification.size} — {classification.reason}')

    # --- Step 3: Route ---
    if classification.size == 'small':
        _handle_small(classification)

    elif classification.size == 'medium':
        _handle_medium(pr_title, pr_body, diff, classification)

    else:
        _handle_large(classification)


def _handle_small(classification):
    print('[agent] Small PR — reviewing for auto-merge (CODEOWNER gate applies)')

    codeowners = _parse_codeowners()
    author     = get_pr_author()
    print(f'[agent] PR author: {author} | Codeowners: {codeowners}')

    comment = build_auto_merge_comment(classification.reason, classification)
    post_comment(comment)

    # --- CODEOWNER gate ---
    # Auto-merge is allowed only if:
    #   (a) the PR author is themselves a codeowner, OR
    #   (b) at least one codeowner has explicitly approved the PR
    author_is_owner   = author in codeowners
    owner_has_approved = has_codeowner_approval(codeowners)

    if not author_is_owner and not owner_has_approved:
        post_comment(
            '🔒 **PR Review Agent — CODEOWNER approval required**\n\n'
            'This PR looks good and qualifies for auto-merge, but a **CODEOWNER must approve** it first.\n\n'
            f'Required approvers: {", ".join(f"`@{o}`" for o in codeowners if "/" not in o)}\n\n'
            'Once a codeowner approves, re-run this workflow or push a new commit to trigger auto-merge.'
        )
        print('[agent] Auto-merge blocked — waiting for codeowner approval')
        return

    print('[agent] CODEOWNER gate passed — proceeding with auto-merge')
    success = auto_merge(classification.reason)
    if not success:
        post_comment(
            'PR Review Agent: Auto-merge was attempted but failed '
            '(branch protection rules may require manual approval). '
            'This PR has been reviewed and is safe to merge manually.'
        )


def _handle_medium(pr_title, pr_body, diff, classification):
    print('[agent] Medium PR — running AI review (Jira integration disabled)')

    # --- Jira workflow disabled (no Jira enterprise account) ---
    # Uncomment the block below once a Jira account is available and
    # JIRA_BASE_URL / JIRA_USER_EMAIL / JIRA_API_TOKEN secrets are set.
    #
    # jira_key  = extract_jira_key(pr_title, pr_body)
    # jira_data = None
    # story     = ''
    # criteria  = []
    # jira_url  = None
    #
    # if jira_key:
    #     print(f'[agent] Jira ticket found: {jira_key}')
    #     jira_data = fetch_jira_story(jira_key)
    #     if jira_data:
    #         story    = f"{jira_data.summary}\n\n{jira_data.story}"
    #         criteria = jira_data.criteria
    #         jira_url = jira_data.url
    #         print(f'[agent] Loaded {len(criteria)} acceptance criteria from Jira')
    #     else:
    #         print(f'[agent] Could not fetch Jira ticket {jira_key}')
    # else:
    #     print('[agent] No Jira key found in PR title/body — reviewing without story context')

    jira_key = None
    story    = ''
    criteria = []
    jira_url = None
    print('[agent] Reviewing without Jira story context')

    # --- Build and run AI review ---
    user_prompt = build_review_prompt(
        diff=diff,
        pr_title=pr_title,
        story=story,
        acceptance_criteria=criteria,
        jira_key=jira_key,
        jira_url=jira_url,
        java_files=classification.java_files,
        has_tests=classification.has_tests,
    )

    print('[agent] Calling AI reviewer...')
    review = run_review(REVIEW_SYSTEM_PROMPT, user_prompt)
    review['jira_ticket'] = jira_key

    print(f'[agent] Review complete — verdict: {review["verdict"]}, '
          f'confidence: {review["confidence"]:.0%}')

    post_review(review)


def _handle_large(classification):
    print('[agent] Large PR — flagging for manual review')
    comment = build_large_pr_comment(classification.reason, classification)
    post_comment(comment)


if __name__ == '__main__':
    main()
