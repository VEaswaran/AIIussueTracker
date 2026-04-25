"""
AI reviewer — sends diff + Jira story + AC to GitHub Copilot API
and returns a structured review dict.
"""
import os
import json
import requests

COPILOT_API_TOKEN = os.environ.get('COPILOT_API_TOKEN', '')
COPILOT_ENDPOINT  = 'https://api.githubcopilot.com/chat/completions'


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call the GitHub Copilot chat completions API."""
    if not COPILOT_API_TOKEN:
        raise EnvironmentError('COPILOT_API_TOKEN is not set')

    payload = {
        'model':           'gpt-4o',
        'temperature':     0.1,      # Low temp = more deterministic review
        'max_tokens':      3000,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': user_prompt},
        ],
    }

    r = requests.post(
        COPILOT_ENDPOINT,
        headers={
            'Authorization':          f'Bearer {COPILOT_API_TOKEN}',
            'Content-Type':           'application/json',
            'Copilot-Integration-Id': 'github-actions-pr-review',
        },
        json=payload,
        timeout=60
    )
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']


def run_review(system_prompt: str, user_prompt: str) -> dict:
    """
    Calls the LLM and parses the JSON response.
    Falls back gracefully if parsing fails.
    """
    try:
        raw = call_llm(system_prompt, user_prompt)
    except Exception as e:
        print(f'[reviewer] LLM call failed: {e}')
        return _fallback_review(str(e))

    try:
        result = json.loads(raw)
        # Validate required keys exist
        result.setdefault('verdict',              'comment')
        result.setdefault('confidence',            0.5)
        result.setdefault('summary',              'Review completed.')
        result.setdefault('ac_coverage',          [])
        result.setdefault('inline_comments',      [])
        result.setdefault('missing_items',        [])
        result.setdefault('security_flags',       [])
        result.setdefault('spring_specific_issues', [])
        result.setdefault('test_coverage_gaps',   [])
        return result
    except json.JSONDecodeError as e:
        print(f'[reviewer] JSON parse error: {e}')
        print(f'[reviewer] Raw response: {raw[:500]}')
        return _fallback_review(f'JSON parse failed. Raw: {raw[:300]}')


def _fallback_review(error_detail: str) -> dict:
    return {
        'verdict':               'comment',
        'confidence':            0.0,
        'summary':               'AI review could not be completed. Please review manually.',
        'ac_coverage':           [],
        'inline_comments':       [],
        'missing_items':         [f'Automated review failed: {error_detail}'],
        'security_flags':        [],
        'spring_specific_issues': [],
        'test_coverage_gaps':    [],
    }
