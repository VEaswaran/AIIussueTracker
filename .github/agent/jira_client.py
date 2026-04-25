"""
Jira client — extracts story and acceptance criteria from a linked Jira ticket.

Supports ticket keys in PR title or body in formats:
  [PROJ-123]  PROJ-123  (PROJ-123)  Fixes PROJ-123
"""
import os
import re
import requests
from dataclasses import dataclass

JIRA_BASE_URL   = os.environ.get('JIRA_BASE_URL', '').rstrip('/')
JIRA_USER_EMAIL = os.environ.get('JIRA_USER_EMAIL', '')
JIRA_API_TOKEN  = os.environ.get('JIRA_API_TOKEN', '')

# Regex to find Jira issue keys (e.g. PROJ-123, ABC-4567)
JIRA_KEY_PATTERN = re.compile(r'\b([A-Z][A-Z0-9]+-\d+)\b')

# Common field names used for Acceptance Criteria in Jira
AC_FIELD_NAMES = [
    'acceptance criteria',
    'acceptancecriteria',
    'ac',
    'definition of done',
    'dod',
]


@dataclass
class JiraStory:
    key:      str
    summary:  str
    story:    str
    criteria: list[str]
    url:      str


def extract_jira_key(pr_title: str, pr_body: str) -> str | None:
    """Find the first Jira ticket key in the PR title or body."""
    for text in [pr_title, pr_body or '']:
        match = JIRA_KEY_PATTERN.search(text)
        if match:
            return match.group(1)
    return None


def fetch_jira_story(ticket_key: str) -> JiraStory | None:
    """Fetch issue details from Jira REST API v3."""
    if not all([JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN]):
        print('[jira] Jira credentials not configured — skipping story fetch')
        return None

    url = f'{JIRA_BASE_URL}/rest/api/3/issue/{ticket_key}'
    try:
        resp = requests.get(
            url,
            auth=(JIRA_USER_EMAIL, JIRA_API_TOKEN),
            headers={'Accept': 'application/json'},
            timeout=10
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f'[jira] Failed to fetch {ticket_key}: {e}')
        return None

    data   = resp.json()
    fields = data.get('fields', {})

    summary     = fields.get('summary', '')
    description = _extract_text(fields.get('description'))
    criteria    = _extract_ac(fields)

    return JiraStory(
        key=ticket_key,
        summary=summary,
        story=description,
        criteria=criteria,
        url=f'{JIRA_BASE_URL}/browse/{ticket_key}',
    )


def _extract_text(adf_node) -> str:
    """Recursively extract plain text from Atlassian Document Format (ADF)."""
    if adf_node is None:
        return ''
    if isinstance(adf_node, str):
        return adf_node
    if isinstance(adf_node, dict):
        node_type = adf_node.get('type', '')
        if node_type == 'text':
            return adf_node.get('text', '')
        parts = [_extract_text(child) for child in adf_node.get('content', [])]
        separator = '\n' if node_type in ('paragraph', 'bulletList', 'orderedList', 'listItem') else ''
        return separator.join(p for p in parts if p)
    if isinstance(adf_node, list):
        return '\n'.join(_extract_text(item) for item in adf_node)
    return ''


def _extract_ac(fields: dict) -> list[str]:
    """
    Try to find acceptance criteria in:
    1. A dedicated custom field named something like 'Acceptance Criteria'
    2. Bullet points under an '## Acceptance Criteria' heading in the description
    3. Falls back to empty list (reviewer will note AC not found)
    """
    # Strategy 1: look for a custom field with an AC-like name
    for key, value in fields.items():
        if key.startswith('customfield_') and value:
            # Jira stores custom field metadata in 'names' but we don't have
            # it here — check by content heuristic: list-like ADF with bullet items
            text = _extract_text(value)
            if text and len(text) > 20:
                continue

    # Strategy 2: scan description for AC section
    description = _extract_text(fields.get('description'))
    criteria = _parse_ac_from_text(description)
    if criteria:
        return criteria

    # Strategy 3: check all custom fields by extracting text and looking for AC headers
    for key, value in fields.items():
        if not key.startswith('customfield_'):
            continue
        text = _extract_text(value)
        if not text:
            continue
        lower_text = text.lower()
        if any(ac_name in lower_text for ac_name in AC_FIELD_NAMES):
            criteria = _parse_ac_from_text(text)
            if criteria:
                return criteria

    return []


def _parse_ac_from_text(text: str) -> list[str]:
    """Extract bullet-point ACs from plain text, looking for known section headers."""
    if not text:
        return []

    lines  = text.splitlines()
    in_ac  = False
    result = []

    for line in lines:
        stripped = line.strip()
        lower    = stripped.lower()

        # Detect start of AC section
        if any(ac_name in lower for ac_name in AC_FIELD_NAMES):
            in_ac = True
            continue

        # Detect end of AC section (next heading)
        if in_ac and stripped.startswith('#') and stripped not in ['#', '##', '###']:
            in_ac = False

        if in_ac and stripped:
            # Strip bullet markers
            clean = re.sub(r'^[-*•·]\s*', '', stripped)
            clean = re.sub(r'^\d+\.\s*', '', clean)
            if clean and len(clean) > 5:
                result.append(clean)

    return result
