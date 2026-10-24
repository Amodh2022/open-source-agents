"""Offline evals: run the deterministic pipeline on every sample and compare with expectations.

No API key and no network: this is the fast, repeatable half of the evaluation. The other half
(the real agent end to end) runs with `adk eval`; see evals/run_evals.sh.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

from cases import CASES, FAKE_KEY, build_samples, outcome  # noqa: E402

from readme_reviewer.checks import run_deterministic_checks  # noqa: E402
from readme_reviewer.scoring import build_report  # noqa: E402


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("PR_SCOPE", "off")
    from readme_reviewer import links

    monkeypatch.setattr(links, "_fetch_status", lambda url: 200)


@pytest.fixture
def samples(tmp_path):
    build_samples(tmp_path / "generated")
    return tmp_path / "generated"


def report_for(samples, case):
    checks = run_deterministic_checks(str(samples / case["folder"]))["checks"]
    return build_report(checks)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_sample_matches_expected_outcome(samples, case):
    assert outcome(report_for(samples, case), case) == []


def test_committed_samples_contain_no_key_like_text():
    from readme_reviewer.redaction import contains_credential

    for path in (Path(__file__).resolve().parents[1] / "evals" / "samples").rglob("*"):
        if path.is_file():
            assert not contains_credential(path.read_text()), path


def test_fake_key_only_appears_in_generated_leaked_sample(samples):
    holders = {p.parent.name for p in samples.rglob("*") if p.is_file() and FAKE_KEY in p.read_text()}
    assert holders == {"leaked-key-agent"}


def test_key_value_never_appears_in_the_report(samples):
    case = next(c for c in CASES if c["id"] == "leaked_api_key")
    assert FAKE_KEY not in report_for(samples, case).model_dump_json()


def test_scores_are_repeatable(samples):
    case = CASES[1]
    assert report_for(samples, case) == report_for(samples, case)


def test_outcome_helper_reports_mismatches(samples):
    case = dict(CASES[0], expect={"verdict": "needs_changes", "must_fail": ["no_secrets"], "must_pass": []})
    problems = outcome(report_for(samples, CASES[0]), case)
    assert any("verdict" in p for p in problems) and any("no_secrets" in p for p in problems)


def test_eval_threshold_separates_the_cases(samples):
    """If two cases' expected reports were this similar, the ADK eval could not tell them apart."""
    rouge = pytest.importorskip("rouge_score.rouge_scorer")
    scorer = rouge.RougeScorer(["rouge1"])
    threshold = 0.9  # keep in step with evals/test_config.json
    texts = {c["id"]: report_for(samples, c).model_dump_json(indent=2) for c in CASES}
    ids = list(texts)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            assert scorer.score(texts[a], texts[b])["rouge1"].fmeasure < threshold, (a, b)


def test_eval_config_threshold_matches_this_test():
    import json

    config = json.loads((Path(__file__).resolve().parents[1] / "evals" / "test_config.json").read_text())
    assert config["criteria"]["response_match_score"] == 0.9
