"""Eval cases: sample projects plus the outcome each one is expected to produce.

Expectations are written from what each sample is *meant* to demonstrate, not copied from a
run. The offline tests (tests/test_evals.py) and the ADK eval set (build_samples.py) share them.
"""

import shutil
from pathlib import Path

SAMPLES = Path(__file__).parent / "samples"
# Assembled from parts so no key-like text is ever committed.
FAKE_KEY = "AIza" + "Q" * 35

CASES = [
    {
        "id": "excellent",
        "folder": "excellent-agent",
        "source": "excellent-agent",
        "expect": {"verdict": "ready", "min_score": 95, "must_fail": [],
                   "must_pass": ["manifest_present", "sections_present", "no_secrets", "folder_name_ok"]},
    },
    {
        "id": "missing_install_steps",
        "folder": "missing-install-agent",
        "source": "missing-install-agent",
        "expect": {"verdict": "needs_changes", "max_score": 84,
                   "must_fail": ["manifest_present", "env_example_present", "sections_present",
                                 "run_command_documented"],
                   "must_pass": ["no_secrets", "folder_name_ok", "sections_not_thin"]},
    },
    {
        "id": "leaked_api_key",
        "folder": "leaked-key-agent",
        "source": "leaked-key-agent",
        "expect": {"verdict": "needs_changes", "must_fail": ["no_secrets"],
                   "must_pass": ["manifest_present", "sections_present", "folder_name_ok"]},
    },
    {
        "id": "wrong_folder_name",
        "folder": "Bad_Name_Agent",
        "source": "excellent-agent",  # identical content, only the folder name is wrong
        "expect": {"verdict": "needs_changes", "must_fail": ["folder_name_ok"],
                   "must_pass": ["manifest_present", "sections_present", "no_secrets"]},
    },
    {
        "id": "minimal_readme",
        "folder": "minimal-agent",
        "source": "minimal-agent",
        "expect": {"verdict": "needs_changes", "max_score": 70,
                   "must_fail": ["manifest_present", "sections_present", "env_example_present",
                                 "run_command_documented", "gitignore_covers_secrets_and_venv"],
                   "must_pass": ["no_secrets", "folder_name_ok"]},
    },
]


def build_samples(dest: Path) -> None:
    """Copy the samples into dest under each case's folder name, filling in the fake key."""
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    for case in CASES:
        target = dest / case["folder"]
        shutil.copytree(SAMPLES / case["source"], target)
        for path in target.rglob("*"):
            if path.is_file():
                text = path.read_text()
                if "{{FAKE_KEY}}" in text:
                    path.write_text(text.replace("{{FAKE_KEY}}", FAKE_KEY))


def outcome(report, case) -> list:
    """Problems found when comparing a ReviewReport with the case's expectations (empty = pass)."""
    expect, problems = case["expect"], []
    failed = {f.id for f in report.failures}
    if report.verdict != expect["verdict"]:
        problems.append(f"verdict {report.verdict}, expected {expect['verdict']}")
    if "min_score" in expect and report.overall_score < expect["min_score"]:
        problems.append(f"score {report.overall_score} below {expect['min_score']}")
    if "max_score" in expect and report.overall_score > expect["max_score"]:
        problems.append(f"score {report.overall_score} above {expect['max_score']}")
    problems += [f"expected {i} to fail" for i in expect["must_fail"] if i not in failed]
    problems += [f"expected {i} to pass" for i in expect["must_pass"] if i in failed]
    if not expect["must_fail"] and report.failures:
        problems.append(f"expected no failures, got {sorted(failed)}")
    return problems
