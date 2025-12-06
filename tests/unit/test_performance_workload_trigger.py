"""
Unit tests for performance workload trigger service
"""
import os
from unittest.mock import patch, MagicMock
import pytest

from src.services.performance.workload_trigger import (
    trigger_workload,
    get_workload_status,
    get_load_generator,
    get_latest_workload_metrics,
)


class TestTriggerWorkload:
    """Test trigger_workload function"""

    @patch("src.services.performance.workload_trigger.Thread")
    @patch("src.services.performance.workload_trigger.uuid")
    def test_trigger_workload_default_params(self, mock_uuid, mock_thread):
        """Test triggering workload with default parameters"""
        mock_uuid.uuid4.return_value.hex = "test-run-id"
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        with patch.dict(os.environ, {}, clear=True):
            result = trigger_workload()

        assert "run_id" in result
        assert result["status"] == "started"
        assert "estimated_completion" in result
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    @patch("src.services.performance.workload_trigger.Thread")
    @patch("src.services.performance.workload_trigger.uuid")
    def test_trigger_workload_custom_params(self, mock_uuid, mock_thread):
        """Test triggering workload with custom parameters"""
        mock_uuid.uuid4.return_value.hex = "test-run-id"
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        result = trigger_workload(
            num_clients=50,
            model_id="test-model",
            artifact_id="test-artifact",
            duration_seconds=600,
            base_url="https://test.example.com",
        )

        assert result["status"] == "started"
        mock_thread.assert_called_once()

    @patch("src.services.performance.workload_trigger.Thread")
    @patch("src.services.performance.workload_trigger.uuid")
    def test_trigger_workload_with_env_var(self, mock_uuid, mock_thread):
        """Test triggering workload with API_BASE_URL from environment"""
        mock_uuid.uuid4.return_value.hex = "test-run-id"
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        with patch.dict(
            os.environ, {"API_BASE_URL": "https://env.example.com"}, clear=False
        ):
            result = trigger_workload()

        assert result["status"] == "started"
        mock_thread.assert_called_once()


class TestGetWorkloadStatus:
    """Test get_workload_status function"""

    def test_get_workload_status_existing(self):
        """Test getting status for existing workload"""
        from src.services.performance.workload_trigger import _workload_runs

        # Add a test run
        test_run_id = "test-run-123"
        _workload_runs[test_run_id] = {
            "run_id": test_run_id,
            "status": "running",
            "num_clients": 100,
        }

        result = get_workload_status(test_run_id)

        assert result is not None
        assert result["run_id"] == test_run_id
        assert result["status"] == "running"

        # Cleanup
        _workload_runs.pop(test_run_id, None)

    def test_get_workload_status_nonexistent(self):
        """Test getting status for non-existent workload"""
        result = get_workload_status("non-existent-run")

        assert result is None


class TestGetLoadGenerator:
    """Test get_load_generator function"""

    def test_get_load_generator_existing(self):
        """Test getting load generator for existing run"""
        from src.services.performance.workload_trigger import _load_generators

        test_run_id = "test-run-456"
        mock_generator = MagicMock()
        _load_generators[test_run_id] = mock_generator

        result = get_load_generator(test_run_id)

        assert result is mock_generator

        # Cleanup
        _load_generators.pop(test_run_id, None)

    def test_get_load_generator_nonexistent(self):
        """Test getting load generator for non-existent run"""
        result = get_load_generator("non-existent-run")

        assert result is None


class TestGetLatestWorkloadMetrics:
    """Test get_latest_workload_metrics function"""

    def test_get_latest_metrics_no_runs(self):
        """Test getting latest metrics when no runs exist"""
        result = get_latest_workload_metrics()

        assert result is None

    def test_get_latest_metrics_no_completed_runs(self):
        """Test getting latest metrics when no runs are completed"""
        from src.services.performance.workload_trigger import _workload_runs

        # Add a running run (not completed)
        test_run_id = "test-run-running"
        _workload_runs[test_run_id] = {
            "run_id": test_run_id,
            "status": "running",
        }

        result = get_latest_workload_metrics()

        assert result is None

        # Cleanup
        _workload_runs.pop(test_run_id, None)

    def test_get_latest_metrics_with_completed_run(self):
        """Test getting latest metrics with completed run"""
        from src.services.performance.workload_trigger import _workload_runs

        # Add a completed run with summary
        test_run_id = "test-run-completed"
        _workload_runs[test_run_id] = {
            "run_id": test_run_id,
            "status": "completed",
            "started_at": "2024-01-01T00:00:00Z",
            "completed_at": "2024-01-01T00:00:10Z",
            "summary": {
                "throughput_bps": 1048576,  # 1 MB/s
                "p99_latency_ms": 500.0,
                "mean_latency_ms": 250.0,
                "median_latency_ms": 240.0,
                "successful_requests": 100,
                "total_requests": 100,
            },
        }

        result = get_latest_workload_metrics()

        assert result is not None
        assert result["latest_run_id"] == test_run_id
        assert result["latest_throughput_mbps"] == pytest.approx(1.0, abs=0.1)
        assert result["latest_p99_latency_ms"] == 500.0
        assert result["latest_mean_latency_ms"] == 250.0
        assert result["latest_success_rate"] == 100.0
        assert result["total_runs_completed"] == 1

        # Cleanup
        _workload_runs.pop(test_run_id, None)

    def test_get_latest_metrics_multiple_runs(self):
        """Test getting latest metrics with multiple completed runs"""
        from src.services.performance.workload_trigger import _workload_runs

        # Add older completed run
        old_run_id = "test-run-old"
        _workload_runs[old_run_id] = {
            "run_id": old_run_id,
            "status": "completed",
            "started_at": "2024-01-01T00:00:00Z",
            "completed_at": "2024-01-01T00:00:10Z",
            "summary": {
                "throughput_bps": 524288,
                "p99_latency_ms": 600.0,
                "mean_latency_ms": 300.0,
                "median_latency_ms": 290.0,
                "successful_requests": 50,
                "total_requests": 50,
            },
        }

        # Add newer completed run
        new_run_id = "test-run-new"
        _workload_runs[new_run_id] = {
            "run_id": new_run_id,
            "status": "completed",
            "started_at": "2024-01-01T00:00:20Z",  # Later timestamp
            "completed_at": "2024-01-01T00:00:30Z",
            "summary": {
                "throughput_bps": 1048576,
                "p99_latency_ms": 500.0,
                "mean_latency_ms": 250.0,
                "median_latency_ms": 240.0,
                "successful_requests": 100,
                "total_requests": 100,
            },
        }

        result = get_latest_workload_metrics()

        assert result is not None
        assert result["latest_run_id"] == new_run_id  # Should return newest
        assert result["total_runs_completed"] == 2

        # Cleanup
        _workload_runs.pop(old_run_id, None)
        _workload_runs.pop(new_run_id, None)

    def test_get_latest_metrics_partial_requests(self):
        """Test getting latest metrics with partial success rate"""
        from src.services.performance.workload_trigger import _workload_runs

        test_run_id = "test-run-partial"
        _workload_runs[test_run_id] = {
            "run_id": test_run_id,
            "status": "completed",
            "started_at": "2024-01-01T00:00:00Z",
            "completed_at": "2024-01-01T00:00:10Z",
            "summary": {
                "throughput_bps": 524288,
                "p99_latency_ms": 500.0,
                "mean_latency_ms": 250.0,
                "median_latency_ms": 240.0,
                "successful_requests": 75,
                "total_requests": 100,  # 75% success rate
            },
        }

        result = get_latest_workload_metrics()

        assert result is not None
        assert result["latest_success_rate"] == 75.0

        # Cleanup
        _workload_runs.pop(test_run_id, None)

    def test_get_latest_metrics_zero_total_requests(self):
        """Test getting latest metrics with zero total requests"""
        from src.services.performance.workload_trigger import _workload_runs

        test_run_id = "test-run-zero"
        _workload_runs[test_run_id] = {
            "run_id": test_run_id,
            "status": "completed",
            "started_at": "2024-01-01T00:00:00Z",
            "completed_at": "2024-01-01T00:00:10Z",
            "summary": {
                "throughput_bps": 0,
                "p99_latency_ms": 0.0,
                "mean_latency_ms": 0.0,
                "median_latency_ms": 0.0,
                "successful_requests": 0,
                "total_requests": 0,
            },
        }

        result = get_latest_workload_metrics()

        assert result is not None
        assert result["latest_success_rate"] == 0.0

        # Cleanup
        _workload_runs.pop(test_run_id, None)

    def test_get_latest_metrics_missing_summary(self):
        """Test getting latest metrics when summary is missing"""
        from src.services.performance.workload_trigger import _workload_runs

        test_run_id = "test-run-no-summary"
        _workload_runs[test_run_id] = {
            "run_id": test_run_id,
            "status": "completed",
            "started_at": "2024-01-01T00:00:00Z",
            # No summary field
        }

        result = get_latest_workload_metrics()

        assert result is None

        # Cleanup
        _workload_runs.pop(test_run_id, None)


class TestRunLoadGeneratorAsync:
    """Test _run_load_generator_async function internal behavior"""

    @patch("src.services.performance.load_generator.LoadGenerator")
    @patch("src.services.performance.workload_trigger.asyncio")
    def test_run_load_generator_async_success(
        self, mock_asyncio, mock_load_generator_class
    ):
        """Test successful execution of load generator"""
        from src.services.performance.workload_trigger import (
            _workload_runs,
            _load_generators,
        )

        run_id = "test-run-async"
        _workload_runs[run_id] = {
            "run_id": run_id,
            "status": "started",
        }
        
        mock_loop = MagicMock()
        mock_asyncio.new_event_loop.return_value = mock_loop
        mock_asyncio.set_event_loop = MagicMock()

        mock_generator = MagicMock()
        mock_generator.metrics = [{"latency": 100}]
        mock_generator.get_summary.return_value = {
            "throughput_bps": 1000,
            "p99_latency_ms": 500,
        }
        mock_load_generator_class.return_value = mock_generator

        from src.services.performance.workload_trigger import (
            _run_load_generator_async,
        )

        _run_load_generator_async(
            run_id=run_id,
            base_url="http://test.com",
            num_clients=10,
            model_id="test-model",
            version="main",
            duration_seconds=60,
        )

        assert _workload_runs[run_id]["status"] == "completed"
        assert "completed_at" in _workload_runs[run_id]
        assert "metrics_count" in _workload_runs[run_id]
        assert "summary" in _workload_runs[run_id]
        mock_loop.close.assert_called_once()

        # Cleanup
        _workload_runs.pop(run_id, None)
        _load_generators.pop(run_id, None)

    @patch("src.services.performance.load_generator.LoadGenerator")
    @patch("src.services.performance.workload_trigger.asyncio")
    @patch("src.services.performance.workload_trigger.logger")
    def test_run_load_generator_async_exception(
        self, mock_logger, mock_asyncio, mock_load_generator_class
    ):
        """Test exception handling in load generator"""
        from src.services.performance.workload_trigger import _workload_runs

        run_id = "test-run-exception"
        _workload_runs[run_id] = {
            "run_id": run_id,
            "status": "started",
        }
        
        mock_loop = MagicMock()
        mock_asyncio.new_event_loop.return_value = mock_loop
        mock_asyncio.set_event_loop = MagicMock()

        # Make LoadGenerator raise an exception
        mock_load_generator_class.side_effect = Exception("Test error")

        from src.services.performance.workload_trigger import (
            _run_load_generator_async,
        )

        _run_load_generator_async(
            run_id=run_id,
            base_url="http://test.com",
            num_clients=10,
            model_id="test-model",
            version="main",
            duration_seconds=60,
        )

        assert _workload_runs[run_id]["status"] == "failed"
        assert "error" in _workload_runs[run_id]
        assert _workload_runs[run_id]["error"] == "Test error"
        mock_logger.error.assert_called_once()
        mock_loop.close.assert_called_once()

        # Cleanup
        _workload_runs.pop(run_id, None)

    @patch("src.services.performance.load_generator.LoadGenerator")
    @patch("src.services.performance.workload_trigger.asyncio")
    def test_run_load_generator_async_loop_run_exception(
        self, mock_asyncio, mock_load_generator_class
    ):
        """Test exception during loop.run_until_complete"""
        from src.services.performance.workload_trigger import _workload_runs

        run_id = "test-run-loop-exception"
        _workload_runs[run_id] = {
            "run_id": run_id,
            "status": "started",
        }
        
        mock_loop = MagicMock()
        mock_loop.run_until_complete.side_effect = RuntimeError("Loop error")
        mock_asyncio.new_event_loop.return_value = mock_loop
        mock_asyncio.set_event_loop = MagicMock()
        
        mock_generator = MagicMock()
        mock_load_generator_class.return_value = mock_generator

        from src.services.performance.workload_trigger import (
            _run_load_generator_async,
        )

        _run_load_generator_async(
            run_id=run_id,
            base_url="http://test.com",
            num_clients=10,
            model_id="test-model",
            version="main",
            duration_seconds=60,
        )

        assert _workload_runs[run_id]["status"] == "failed"
        assert "error" in _workload_runs[run_id]
        mock_loop.close.assert_called_once()

        # Cleanup
        _workload_runs.pop(run_id, None)

    @patch("src.services.performance.load_generator.LoadGenerator")
    @patch("src.services.performance.workload_trigger.asyncio")
    def test_run_load_generator_async_missing_run_id(
        self, mock_asyncio, mock_load_generator_class
    ):
        """Test when run_id doesn't exist in _workload_runs"""
        run_id = "test-run-missing"
        # Don't add to _workload_runs

        mock_loop = MagicMock()
        mock_asyncio.new_event_loop.return_value = mock_loop
        mock_asyncio.set_event_loop = MagicMock()

        mock_generator = MagicMock()
        mock_generator.metrics = []
        mock_generator.get_summary.return_value = {}
        mock_load_generator_class.return_value = mock_generator

        from src.services.performance.workload_trigger import (
            _run_load_generator_async,
        )

        # Should not raise exception even if run_id doesn't exist
        _run_load_generator_async(
            run_id=run_id,
            base_url="http://test.com",
            num_clients=10,
            model_id="test-model",
            version="main",
            duration_seconds=60,
        )

        mock_loop.close.assert_called_once()

