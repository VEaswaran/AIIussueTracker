"""
PR Classifier — Java/Spring aware.

Determines whether a PR is:
  small  → safe to auto-approve and merge (config, logs, version bumps)
  medium → send to AI review with Jira story context
  large  → flag for mandatory human review
"""
import re
from dataclasses import dataclass

# File extensions considered pure configuration (no logic changes)
SMALL_EXTENSIONS = {
    '.yml', '.yaml', '.properties', '.xml',
    '.json', '.toml', '.env', '.cfg', '.conf'
}

# Files that are always safe regardless of content
SAFE_FILENAMES = {
    'pom.xml', 'build.gradle', 'build.gradle.kts',
    'application.properties', 'application.yml',
    'application-dev.yml', 'application-prod.yml',
    'logback.xml', 'logback-spring.xml',
    '.gitignore', '.gitattributes', 'Dockerfile',
    'docker-compose.yml', 'README.md', 'CHANGELOG.md'
}

# Patterns that identify low-risk additions (log statements, version bumps)
LOG_PATTERN     = re.compile(
    r'^\+\s*(log\.|logger\.|Logger\.|LOG\.|log\.debug|log\.info|log\.warn|log\.error)',
    re.MULTILINE
)
VERSION_PATTERN = re.compile(
    r'^\+.*<version>[\d.]+(-SNAPSHOT)?</version>',
    re.MULTILINE
)

# Java-specific files that always need review (business logic)
ALWAYS_REVIEW_PATTERNS = [
    r'.*Service\.java$',
    r'.*Controller\.java$',
    r'.*Repository\.java$',
    r'.*Entity\.java$',
    r'.*Security.*\.java$',
    r'.*Config\.java$',
    r'.*Filter\.java$',
]

@dataclass
class Classification:
    size:          str   # 'small' | 'medium' | 'large'
    reason:        str
    lines_added:   int
    lines_removed: int
    java_files:    list
    config_files:  list
    has_tests:     bool


def classify_pr(diff: str, files_changed: list[str]) -> Classification:
    lines_added   = sum(1 for l in diff.splitlines()
                        if l.startswith('+') and not l.startswith('+++'))
    lines_removed = sum(1 for l in diff.splitlines()
                        if l.startswith('-') and not l.startswith('---'))
    total_delta   = lines_added + lines_removed

    java_files   = [f for f in files_changed if f.endswith('.java')]
    config_files = [f for f in files_changed
                    if any(f.endswith(ext) for ext in SMALL_EXTENSIONS)
                    or f.split('/')[-1] in SAFE_FILENAMES]
    test_files   = [f for f in java_files
                    if 'test' in f.lower() or 'Test' in f or 'Spec' in f]
    has_tests    = len(test_files) > 0

    # Check for always-review Java files
    needs_review = any(
        re.match(pattern, f)
        for f in java_files
        for pattern in ALWAYS_REVIEW_PATTERNS
    )

    # --- Classification logic ---

    # Small: only config/infra files touched, no Java logic
    only_config = all(
        any(f.endswith(ext) for ext in SMALL_EXTENSIONS)
        or f.split('/')[-1] in SAFE_FILENAMES
        for f in files_changed
    )

    is_log_only     = bool(LOG_PATTERN.search(diff)) and total_delta < 30 and not needs_review
    is_version_bump = bool(VERSION_PATTERN.search(diff)) and total_delta < 20

    if only_config or is_log_only or is_version_bump:
        return Classification(
            size='small',
            reason=_small_reason(only_config, is_log_only, is_version_bump),
            lines_added=lines_added,
            lines_removed=lines_removed,
            java_files=java_files,
            config_files=config_files,
            has_tests=has_tests,
        )

    if total_delta >= 400 or (len(java_files) > 10 and total_delta > 200):
        return Classification(
            size='large',
            reason=f'{total_delta} lines changed across {len(files_changed)} files — manual review required',
            lines_added=lines_added,
            lines_removed=lines_removed,
            java_files=java_files,
            config_files=config_files,
            has_tests=has_tests,
        )

    return Classification(
        size='medium',
        reason=f'{total_delta} lines changed in {len(java_files)} Java file(s) — AI review triggered',
        lines_added=lines_added,
        lines_removed=lines_removed,
        java_files=java_files,
        config_files=config_files,
        has_tests=has_tests,
    )


def _small_reason(only_config, is_log_only, is_version_bump) -> str:
    if is_version_bump:
        return 'version bump only'
    if is_log_only:
        return 'log statement addition only'
    if only_config:
        return 'configuration/infrastructure files only'
    return 'low-risk change'
