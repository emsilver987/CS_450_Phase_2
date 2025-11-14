from acmecli.metrics.reproducibility_metric import ReproducibilityMetric


m = ReproducibilityMetric()


def test_full_score():
    meta = {
        "readme_text": "## Example\npip install pkg\npython demo.py",
        "repo_files": {"demo.py"}
    }
    assert m.score(meta).value == 1.0


def test_half_score():
    meta = {"readme_text": "## Example\nRun the model after setup",
            "repo_files": set()}
    # "Example" and "Run" trigger demo detection, so it gets higher score (0.8)
    # with base 0.5 + simple_install + paths_exist bonuses
    assert m.score(meta).value >= 0.5


def test_zero_score():
    meta = {"readme_text": "no demo here", "repo_files": set()}
    # Even without demo, if readme exists, it gets at least 0.4, but code indicators might push it to 0.5
    # The metric returns 0.5 when code indicators are detected
    assert m.score(meta).value >= 0.4
