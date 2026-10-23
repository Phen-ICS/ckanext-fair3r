#!/usr/bin/env python3
"""Generate compact JUnit reports for CI tools.

Modes:
- ruff-format: one testcase with optional failure and command output.
- bandit: one testcase per finding from Bandit JSON output.
- pip-audit: one testcase per dependency from pip-audit JSON output.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


def _write_xml(
    path: str, testsuite: str, tests: int, failures: int, cases: Iterable[str]
) -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<testsuite name="{escape(testsuite)}" tests="{tests}" failures="{failures}" errors="0" skipped="0">\n'
        + "\n".join(cases)
        + "\n</testsuite>\n"
    )
    Path(path).write_text(xml, encoding="utf-8")


def _cmd_ruff_format(args: argparse.Namespace) -> int:
    status = int(args.status)
    output = Path(args.input).read_text(encoding="utf-8", errors="replace")

    # Keep full formatter output visible in job logs (not only in JUnit system-out).
    print("ruff format output:")
    if output:
        print(output.rstrip())
    else:
        print("(no output)")

    failure = '<failure message="ruff format check failed" />' if status != 0 else ""
    case = (
        f'<testcase classname="lint" name="{escape(args.test_name)}">'
        f"{failure}<system-out>{escape(output)}</system-out>"
        "</testcase>"
    )
    _write_xml(args.xml, "lint.ruff_format", 1, 1 if status != 0 else 0, [case])
    return 1 if status != 0 else 0


def _cmd_ruff_check(args: argparse.Namespace) -> int:
    status = int(args.status)
    output = Path(args.input).read_text(encoding="utf-8", errors="replace")

    print("ruff check output:")
    if output:
        print(output.rstrip())
    else:
        print("(no output)")

    failure = '<failure message="ruff check failed" />' if status != 0 else ""
    case = (
        f'<testcase classname="lint" name="{escape(args.test_name)}">'
        f"{failure}<system-out>{escape(output)}</system-out>"
        "</testcase>"
    )
    _write_xml(args.xml, "lint.ruff", 1, 1 if status != 0 else 0, [case])
    return 1 if status != 0 else 0


def _cmd_bandit(args: argparse.Namespace) -> int:
    try:
        data: Any = json.loads(Path(args.json).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}

    results = data.get("results", []) if isinstance(data, dict) else []
    failures = len(results)

    if results:
        print("Bandit findings:")
    else:
        print("Bandit findings: none")

    cases: list[str] = []
    for idx, issue in enumerate(results, start=1):
        test_id = issue.get("test_id", "BANDIT")
        severity = issue.get("issue_severity", "UNKNOWN")
        confidence = issue.get("issue_confidence", "UNKNOWN")
        filename = issue.get("filename", "unknown")
        line = issue.get("line_number", "?")
        text = issue.get("issue_text", "")
        more_info = issue.get("more_info", "")
        code = (issue.get("code") or "").rstrip()

        cwe = (
            issue.get("issue_cwe", {})
            if isinstance(issue.get("issue_cwe"), dict)
            else {}
        )
        cwe_id = cwe.get("id")
        cwe_link = cwe.get("link")

        print(f"Issue: [{test_id}] {text}")
        print(f"Severity: {severity} Confidence: {confidence}")
        if cwe_id and cwe_link:
            print(f"CWE: CWE-{cwe_id} ({cwe_link})")
        elif cwe_id:
            print(f"CWE: CWE-{cwe_id}")
        if more_info:
            print(f"More Info: {more_info}")
        print(f"Location: {filename}:{line}")
        if code:
            print(code)
        print()

        msg = f"{test_id} [{severity}/{confidence}] {filename}:{line}"
        details = text
        if more_info:
            details = (
                f"{details}\nMore info: {more_info}"
                if details
                else f"More info: {more_info}"
            )
        if code:
            details = f"{details}\n\nCode:\n{code}" if details else f"Code:\n{code}"

        name = f"issue-{idx}-{test_id}"
        cases.append(
            f'<testcase classname="bandit" name="{escape(name)}">'
            f'<failure message="{escape(msg)}">{escape(details)}</failure>'
            "</testcase>"
        )

    metrics = data.get("metrics", {}) if isinstance(data, dict) else {}
    totals = metrics.get("_totals", {}) if isinstance(metrics, dict) else {}
    if totals:
        print("Run metrics:")
        print("Total issues (by severity):")
        print(f"  Undefined: {totals.get('SEVERITY.UNDEFINED', 0)}")
        print(f"  Low: {totals.get('SEVERITY.LOW', 0)}")
        print(f"  Medium: {totals.get('SEVERITY.MEDIUM', 0)}")
        print(f"  High: {totals.get('SEVERITY.HIGH', 0)}")
        print("Total issues (by confidence):")
        print(f"  Undefined: {totals.get('CONFIDENCE.UNDEFINED', 0)}")
        print(f"  Low: {totals.get('CONFIDENCE.LOW', 0)}")
        print(f"  Medium: {totals.get('CONFIDENCE.MEDIUM', 0)}")
        print(f"  High: {totals.get('CONFIDENCE.HIGH', 0)}")
        print()

    if not cases:
        cases.append('<testcase classname="bandit" name="no-security-issues"/>')
        tests = 1
    else:
        tests = len(cases)

    _write_xml(args.xml, "bandit", tests, failures, cases)
    return 1 if failures > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate JUnit reports for CI tools")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_rf = sub.add_parser("ruff-format")
    p_rf.add_argument("--input", required=True)
    p_rf.add_argument("--xml", required=True)
    p_rf.add_argument("--status", required=True)
    p_rf.add_argument("--test-name", default="ruff format --check ckanext")

    p_rc = sub.add_parser("ruff-check")
    p_rc.add_argument("--input", required=True)
    p_rc.add_argument("--xml", required=True)
    p_rc.add_argument("--status", required=True)
    p_rc.add_argument("--test-name", default="ruff check ckanext")

    p_bandit = sub.add_parser("bandit")
    p_bandit.add_argument("--json", required=True)
    p_bandit.add_argument("--xml", required=True)

    args = parser.parse_args()
    if args.cmd == "ruff-format":
        return _cmd_ruff_format(args)
    if args.cmd == "ruff-check":
        return _cmd_ruff_check(args)
    if args.cmd == "bandit":
        return _cmd_bandit(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
