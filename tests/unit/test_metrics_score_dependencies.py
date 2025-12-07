"""
Unit tests for score_dependencies metric
"""
import pytest
import tempfile
import os
import json
from unittest.mock import patch, MagicMock


class TestScoreDependencies:
    """Test dependencies scoring"""

    def test_score_dependencies_no_repo_path(self):
        """Test scoring with no repo path"""
        from src.acmecli.metrics.score_dependencies import score_dependencies
        
        context = {}
        result = score_dependencies(context)
        assert result == 0.5

    def test_score_dependencies_nonexistent_path(self):
        """Test scoring with nonexistent path"""
        from src.acmecli.metrics.score_dependencies import score_dependencies
        
        context = {"repo_path": "/nonexistent/path"}
        result = score_dependencies(context)
        assert result == 0.5

    def test_score_dependencies_zero_deps(self):
        """Test scoring with zero dependencies"""
        from src.acmecli.metrics.score_dependencies import score_dependencies
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create empty requirements.txt
            req_file = os.path.join(temp_dir, "requirements.txt")
            with open(req_file, "w") as f:
                f.write("")
            
            context = {"repo_path": temp_dir}
            result = score_dependencies(context)
            assert result == 1.0

    def test_score_dependencies_package_json(self):
        """Test scoring with package.json"""
        from src.acmecli.metrics.score_dependencies import score_dependencies
        
        with tempfile.TemporaryDirectory() as temp_dir:
            pkg_file = os.path.join(temp_dir, "package.json")
            with open(pkg_file, "w") as f:
                json.dump({
                    "dependencies": {"dep1": "1.0.0", "dep2": "2.0.0"},
                    "devDependencies": {"dev1": "1.0.0"}
                }, f)
            
            context = {"repo_path": temp_dir}
            result = score_dependencies(context)
            assert 0.0 <= result <= 1.0

    def test_score_dependencies_requirements_txt(self):
        """Test scoring with requirements.txt"""
        from src.acmecli.metrics.score_dependencies import score_dependencies
        
        with tempfile.TemporaryDirectory() as temp_dir:
            req_file = os.path.join(temp_dir, "requirements.txt")
            with open(req_file, "w") as f:
                f.write("package1==1.0.0\npackage2==2.0.0\n# comment\n")
            
            context = {"repo_path": temp_dir}
            result = score_dependencies(context)
            assert 0.0 <= result <= 1.0

    def test_score_dependencies_many_deps(self):
        """Test scoring with many dependencies"""
        from src.acmecli.metrics.score_dependencies import score_dependencies
        
        with tempfile.TemporaryDirectory() as temp_dir:
            req_file = os.path.join(temp_dir, "requirements.txt")
            with open(req_file, "w") as f:
                # Write 25 dependencies
                for i in range(25):
                    f.write(f"package{i}==1.0.0\n")
            
            context = {"repo_path": temp_dir}
            result = score_dependencies(context)
            assert result < 0.5  # Should be low with many deps

    def test_score_dependencies_with_latency(self):
        """Test scoring with latency measurement"""
        from src.acmecli.metrics.score_dependencies import score_dependencies_with_latency
        
        context = {}
        score, latency = score_dependencies_with_latency(context)
        assert score == 0.5
        assert latency >= 0.0

    def test_score_dependencies_context_object(self):
        """Test scoring with context as object"""
        from src.acmecli.metrics.score_dependencies import score_dependencies
        
        class Context:
            def __init__(self, path):
                self.repo_path = path
        
        with tempfile.TemporaryDirectory() as temp_dir:
            req_file = os.path.join(temp_dir, "requirements.txt")
            with open(req_file, "w") as f:
                f.write("package1==1.0.0\n")
            
            context = Context(temp_dir)
            result = score_dependencies(context)
            assert 0.0 <= result <= 1.0

    def test_score_dependencies_local_path(self):
        """Test scoring with local_path attribute"""
        from src.acmecli.metrics.score_dependencies import score_dependencies
        
        with tempfile.TemporaryDirectory() as temp_dir:
            req_file = os.path.join(temp_dir, "requirements.txt")
            with open(req_file, "w") as f:
                f.write("package1==1.0.0\n")
            
            context = {"local_path": temp_dir}
            result = score_dependencies(context)
            assert 0.0 <= result <= 1.0

    def test_count_deps_package_json_exception(self):
        """Test counting deps when package.json has invalid JSON"""
        from src.acmecli.metrics.score_dependencies import _count_deps
        
        with tempfile.TemporaryDirectory() as temp_dir:
            pkg_file = os.path.join(temp_dir, "package.json")
            with open(pkg_file, "w") as f:
                f.write("invalid json {")
            
            result = _count_deps(temp_dir)
            assert result == 0  # Should fall back to requirements.txt or 0

    def test_count_deps_requirements_txt_exception(self):
        """Test counting deps when requirements.txt read fails"""
        from src.acmecli.metrics.score_dependencies import _count_deps
        
        with tempfile.TemporaryDirectory() as temp_dir:
            req_file = os.path.join(temp_dir, "requirements.txt")
            # Create file but make it unreadable (simulate error)
            with patch('builtins.open', side_effect=IOError("Read error")):
                result = _count_deps(temp_dir)
                assert result == 0

