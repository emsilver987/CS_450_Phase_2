"""Code quality validation tests"""
from pathlib import Path
import pytest


def test_no_bare_except_clauses():
    """Ensure no bare except clauses exist in test files"""
    bare_excepts = []
    tests_dir = Path(__file__).parent.parent

    for py_file in tests_dir.rglob("*.py"):
        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                # Match bare except: (with optional pass on same line)
                if stripped == 'except:' or stripped.startswith('except: '):
                    file_path = str(py_file.relative_to(tests_dir.parent))
                    bare_excepts.append((file_path, i))

    assert len(bare_excepts) == 0, (
        f"Found {len(bare_excepts)} bare except clauses. "
        f"Use specific exception types instead: {bare_excepts}"
    )

