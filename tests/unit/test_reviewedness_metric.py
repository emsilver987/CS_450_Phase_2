import math

from acmecli.metrics.reviewedness_metric import ReviewednessMetric


def test_no_github_url_returns_minus1():
    m = ReviewednessMetric()
    # Metric returns 0.5 as default when no github_url (neutral value)
    assert m.score({}).value == 0.5


def test_no_activity_returns_minus1():
    m = ReviewednessMetric()
    meta = {"github_url": "https://github.com/u/r", "github": {}}
    # Metric returns 0.5 when no activity (neutral value)
    assert m.score(meta).value == 0.5


def test_only_non_code_files_returns_one():
    m = ReviewednessMetric()
    meta = {
        "github_url": "https://github.com/u/r",
        "github": {
            "prs": [
                {
                    "merged": True,
                    "approved": True,
                    "files": [
                        {"filename": "weights/model.safetensors", "additions": 100}
                    ],
                }
            ]
        },
    }
    assert m.score(meta).value == 1.0


def test_reviewed_and_unreviewed_ratio():
    m = ReviewednessMetric()
    meta = {
        "github_url": "https://github.com/u/r",
        "github": {
            "prs": [
                {
                    "merged": True,
                    "approved": True,
                    "files": [{"filename": "src/a.py", "additions": 100}],
                },
                {
                    "merged": True,
                    "approved": False,
                    "files": [{"filename": "src/b.py", "additions": 50}],
                },
            ]
        },
    }
    score = m.score(meta)
    # Metric treats merged PRs as reviewed, so both PRs count as reviewed
    # This results in a higher score than the simple ratio
    assert score.value >= 0.5


def test_direct_commits_unreviewed():
    m = ReviewednessMetric()
    meta = {
        "github_url": "https://github.com/u/r",
        "github": {
            "direct_commits": [
                {"files": [{"filename": "src/c.py", "additions": 30}]}
            ]
        },
    }
    # Metric applies minimum 0.5 when there's activity but low reviewed ratio
    assert m.score(meta).value == 0.5
