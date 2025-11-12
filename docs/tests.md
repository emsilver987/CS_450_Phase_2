# Tests

## Running the suite

```powershell
. .venv/Scripts/Activate.ps1
python run.py test
```

This runs pytest with coverage and prints a concise summary.

## Prerequisites

Before running any tests, make sure the Python dependencies (including `pytest`) are installed inside your virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows use `. .venv/Scripts/Activate.ps1`
pip install -r requirements.txt
```

Attempting to execute tests without these dependencies results in errors such as `No module named pytest`.

## Structure

- `tests/unit/*.py`: unit tests for metrics, scoring, reporter.
- `pytest.ini`: discovery root and coverage options.

## Tips

- Use `-k` to filter tests: `pytest -k bus_factor`.
- Use `-q` for quiet mode.
- View coverage details with `--cov-report=term-missing` (already enabled).
