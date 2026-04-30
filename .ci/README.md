# CI Helpers

This directory contains helper scripts used by GitLab CI jobs.

## `junit_report.py`

`junit_report.py` converts tool outputs to JUnit XML so GitLab can display findings in the **Tests** tab.

### Supported modes

- `ruff-check`: build a JUnit report from Ruff check output text
- `ruff-format`: build a JUnit report from Ruff format check output text
- `bandit`: build a per-finding JUnit report from Bandit JSON output
- `pip-audit`: build a per-dependency/per-vulnerability JUnit report from pip-audit JSON output

### Why this exists

- Keep `.gitlab-ci.yml` short and maintainable
- Reuse one implementation for multiple tools
- Ensure consistent JUnit structure across validation jobs

### Typical usage in CI

```bash
python .ci/junit_report.py ruff-check --input ruff.out --xml report-ruff.xml --status "$status"
python .ci/junit_report.py ruff-format --input ruff-format.out --xml report-ruff-format.xml --status "$status"
python .ci/junit_report.py bandit --json report-bandit.json --xml report-bandit.xml
python .ci/junit_report.py pip-audit --json report-pip-audit.json --xml report-pip-audit.xml
```

### Notes

- The script is CI-focused and intentionally lightweight.
- If tool JSON schemas change in future versions, update the corresponding parser mode here.
