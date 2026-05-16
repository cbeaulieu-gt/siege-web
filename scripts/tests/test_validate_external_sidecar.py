"""Tests for scripts/validate-external-sidecar.sh.

Covers the four validation cases the script is responsible for (the
use-external-sidecar=false short-circuit lives in the composite action wrapper,
not the script, so it is not tested here):

  1. Valid https:// URL → exit 0
  2. Plain http:// URL → exit 1, error mentions "must start with https://"
  3. externalBotApiUrl line missing entirely → exit 1, error mentions "not set"
  4. Malformed scheme (https:/typo) → exit 1, error mentions "must start with https://"
  5. Empty quoted string → exit 1, error mentions "not set"

These tests are a regression catch for #435 / #427: two review iterations
almost let inadvertent regex tweaks through silently because the duplicated
inline steps had no automated coverage.

Usage:
    pytest scripts/tests/ -v
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Resolve the script path relative to the repo root (two levels up from this file:
# scripts/tests/ → scripts/ → repo root).
REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate-external-sidecar.sh"

# Locate bash. On Linux/macOS CI it's always on PATH. On Windows it lives in
# Git Bash; fall back to the canonical Git for Windows path if shutil.which
# returns the WSL relay (which cannot run scripts without a WSL distro).
_BASH_CANDIDATES = [
    shutil.which("bash"),
    r"C:\Program Files\Git\usr\bin\bash.exe",
    r"C:\Git\usr\bin\bash.exe",
]
_BASH = next(
    (
        b
        for b in _BASH_CANDIDATES
        if b and Path(b).exists() and "WindowsApps" not in b and "System32" not in b
    ),
    None,
)

if _BASH is None:
    pytest.skip("bash not available — skipping script tests", allow_module_level=True)


def run_script(param_file: Path) -> subprocess.CompletedProcess:
    """Invoke the validation script against *param_file* and return the result."""
    return subprocess.run(
        [_BASH, str(SCRIPT), str(param_file)],
        capture_output=True,
        text=True,
    )


def write_param_file(tmp_path: Path, content: str) -> Path:
    """Write a minimal .bicepparam file with *content* and return its path."""
    p = tmp_path / "main.test.bicepparam"
    p.write_text(content)
    return p


# ── Case 1: valid https:// URL ────────────────────────────────────────────────


def test_valid_https_url_passes(tmp_path):
    """A correctly set https:// externalBotApiUrl exits 0 (validation passes)."""
    param_file = write_param_file(
        tmp_path,
        "param externalBotApiUrl = 'https://x.example.com'\n",
    )
    result = run_script(param_file)
    assert result.returncode == 0, (
        f"Expected exit 0 for valid https URL.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ── Case 2: plain http:// URL ─────────────────────────────────────────────────


def test_http_url_fails_with_https_message(tmp_path):
    """A plain http:// URL exits 1 and the error mentions 'must start with https://'."""
    param_file = write_param_file(
        tmp_path,
        "param externalBotApiUrl = 'http://insecure.example.com'\n",
    )
    result = run_script(param_file)
    assert result.returncode == 1, (
        f"Expected exit 1 for http:// URL.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "must start with https://" in combined, (
        f"Expected 'must start with https://' in output.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ── Case 3: externalBotApiUrl line missing ────────────────────────────────────


def test_missing_param_line_fails_with_not_set_message(tmp_path):
    """A param file without externalBotApiUrl exits 1 and mentions 'not set'."""
    param_file = write_param_file(
        tmp_path,
        "param environment = 'dev'\nparam appPrefix = 'siege-web'\n",
    )
    result = run_script(param_file)
    assert result.returncode == 1, (
        f"Expected exit 1 for missing externalBotApiUrl.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "not set" in combined, (
        f"Expected 'not set' in output.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ── Case 4: malformed scheme (https:/typo) ────────────────────────────────────


def test_malformed_scheme_fails_with_https_message(tmp_path):
    """A URL with a single-slash typo (https:/typo) exits 1 and mentions 'must start with https://'."""
    param_file = write_param_file(
        tmp_path,
        "param externalBotApiUrl = 'https:/typo'\n",
    )
    result = run_script(param_file)
    assert result.returncode == 1, (
        f"Expected exit 1 for malformed https:/typo URL.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "must start with https://" in combined, (
        f"Expected 'must start with https://' in output.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ── Case 5: empty quoted string ───────────────────────────────────────────────


def test_empty_quoted_string_fails_with_not_set_message(tmp_path):
    """An empty quoted externalBotApiUrl exits 1 and mentions 'not set'."""
    param_file = write_param_file(
        tmp_path,
        "param externalBotApiUrl = ''\n",
    )
    result = run_script(param_file)
    assert result.returncode == 1, (
        f"Expected exit 1 for empty quoted string.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "not set" in combined, (
        f"Expected 'not set' in output.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
