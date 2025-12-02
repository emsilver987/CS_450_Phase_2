"""
Unit tests for performance load generator functionality.
These tests verify the core logic of load generation without external dependencies.
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

# Import the load generator once it's implemented
from src.services.performance.load_generator import LoadGenerator, Metric, calculate_latency


class TestLoadGeneratorMetrics:
    """Test metrics collection functions"""
    
    def test_metric_creation(self):
        """Test that metrics can be created with required fields"""
        metric = Metric(
            run_id="test-run-123",
            client_id=1,
            request_latency_ms=100.5,
            bytes_transferred=1024,
            status_code=200,
            timestamp=datetime.now(timezone.utc)
        )
        assert metric.run_id == "test-run-123"
        assert metric.client_id == 1
        assert metric.request_latency_ms == 100.5
    
    def test_latency_calculation(self):
        """Test latency calculation from start and end times"""
        start_time = time.time()
        time.sleep(0.1)  # Simulate 100ms delay
        end_time = time.time()
        
        latency_ms = (end_time - start_time) * 1000
        assert 95 <= latency_ms <= 150  # Allow some tolerance
    
    def test_metric_serialization(self):
        """Test that metrics can be serialized to dict for DynamoDB"""
        metric = Metric(
            run_id="test-run-123",
            client_id=1,
            request_latency_ms=100.5,
            bytes_transferred=1024,
            status_code=200,
            timestamp=datetime.now(timezone.utc)
        )
        metric_dict = metric.to_dict()
        assert isinstance(metric_dict, dict)
        assert "run_id" in metric_dict
        assert "client_id" in metric_dict


class TestLoadGeneratorConcurrency:
    """Test concurrent request handling"""
    
    @pytest.mark.asyncio
    async def test_create_multiple_clients(self):
        """Test that multiple clients can be created concurrently"""
        num_clients = 10
        clients = []
        
        async def create_client(client_id):
            return {"client_id": client_id, "created_at": time.time()}
        
        tasks = [create_client(i) for i in range(num_clients)]
        clients = await asyncio.gather(*tasks)
        
        assert len(clients) == num_clients
        assert all(c["client_id"] == i for i, c in enumerate(clients))
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_tracked_separately(self):
        """Test that concurrent requests are tracked separately"""
        metrics = []
        
        async def mock_request(client_id):
            start = time.time()
            await asyncio.sleep(0.01)  # Simulate request
            end = time.time()
            metrics.append({
                "client_id": client_id,
                "latency_ms": (end - start) * 1000
            })
        
        num_clients = 5
        tasks = [mock_request(i) for i in range(num_clients)]
        await asyncio.gather(*tasks)
        
        assert len(metrics) == num_clients
        assert len(set(m["client_id"] for m in metrics)) == num_clients
    
    @pytest.mark.asyncio
    async def test_all_clients_complete(self):
        """Test that all client requests complete"""
        completed = []
        
        async def mock_request(client_id):
            await asyncio.sleep(0.01)
            completed.append(client_id)
        
        num_clients = 10
        tasks = [mock_request(i) for i in range(num_clients)]
        await asyncio.gather(*tasks)
        
        assert len(completed) == num_clients
        assert set(completed) == set(range(num_clients))


class TestLoadGeneratorErrorHandling:
    """Test error handling in load generator"""
    
    @pytest.mark.asyncio
    async def test_error_tracking(self):
        """Test that errors are tracked correctly"""
        results = []
        
        async def mock_request_with_error(client_id):
            try:
                if client_id % 2 == 0:
                    raise Exception("Simulated error")
                results.append({"client_id": client_id, "status": "success"})
            except Exception as e:
                results.append({"client_id": client_id, "status": "error", "error": str(e)})
        
        num_clients = 5
        tasks = [mock_request_with_error(i) for i in range(num_clients)]
        await asyncio.gather(*tasks)
        
        assert len(results) == num_clients
        errors = [r for r in results if r["status"] == "error"]
        successes = [r for r in results if r["status"] == "success"]
        assert len(errors) > 0
        assert len(successes) > 0
    
    @pytest.mark.asyncio
    async def test_partial_failures_dont_stop_others(self):
        """Test that one client failure doesn't stop others"""
        results = []
        
        async def mock_request(client_id):
            try:
                if client_id == 2:
                    raise Exception("Client 2 failed")
                await asyncio.sleep(0.01)
                results.append({"client_id": client_id, "status": "success"})
            except Exception:
                results.append({"client_id": client_id, "status": "error"})
        
        num_clients = 5
        tasks = [mock_request(i) for i in range(num_clients)]
        await asyncio.gather(*tasks)
        
        # All clients should complete (either success or error)
        assert len(results) == num_clients
        # At least one should succeed
        assert any(r["status"] == "success" for r in results)
        # At least one should error
        assert any(r["status"] == "error" for r in results)


class TestLoadGeneratorStatistics:
    """Test statistics calculations for load generator"""
    
    def test_mean_calculation(self):
        """Test mean latency calculation"""
        latencies = [100.0, 200.0, 300.0, 400.0, 500.0]
        mean = sum(latencies) / len(latencies)
        assert mean == 300.0
    
    def test_median_calculation_odd(self):
        """Test median calculation with odd number of values"""
        latencies = [100.0, 200.0, 300.0, 400.0, 500.0]
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        median = sorted_latencies[n // 2]
        assert median == 300.0
    
    def test_median_calculation_even(self):
        """Test median calculation with even number of values"""
        latencies = [100.0, 200.0, 300.0, 400.0]
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        median = (sorted_latencies[n // 2 - 1] + sorted_latencies[n // 2]) / 2
        assert median == 250.0
    
    def test_percentile_99_calculation(self):
        """Test 99th percentile calculation"""
        # 100 values, 99th percentile should be the 99th value
        latencies = list(range(1, 101))  # 1 to 100
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        percentile_index = int(n * 0.99)
        p99 = sorted_latencies[min(percentile_index, n - 1)]
        assert p99 == 99 or p99 == 100  # Should be close to 99
    
    def test_throughput_calculation(self):
        """Test throughput calculation"""
        total_bytes = 1024 * 100  # 100 KB
        total_time_seconds = 10.0
        throughput_bytes_per_sec = total_bytes / total_time_seconds
        assert throughput_bytes_per_sec == 10240.0
    
    def test_error_rate_calculation(self):
        """Test error rate calculation"""
        total_requests = 100
        successful_requests = 95
        error_rate = (total_requests - successful_requests) / total_requests * 100
        assert error_rate == 5.0


class TestLoadGeneratorClass:
    """Test LoadGenerator class methods"""

    def test_load_generator_initialization(self):
        """Test LoadGenerator initialization"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com",
            num_clients=10,
            model_id="test/model",
            version="main"
        )
        
        assert generator.run_id == "test-run-1"
        assert generator.base_url == "https://api.example.com"
        assert generator.num_clients == 10
        assert generator.model_id == "test/model"
        assert generator.version == "main"
        assert generator.metrics == []
        assert generator.start_time is None
        assert generator.end_time is None

    def test_load_generator_with_duration(self):
        """Test LoadGenerator initialization with duration"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com",
            duration_seconds=60
        )
        
        assert generator.duration_seconds == 60

    def test_load_generator_with_performance_path(self):
        """Test LoadGenerator with performance path"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com",
            use_performance_path=True
        )
        
        assert generator.use_performance_path is True

    def test_get_download_url(self):
        """Test _get_download_url method"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com",
            model_id="test/model",
            version="main"
        )
        
        url = generator._get_download_url()
        assert "models" in url
        assert "test_model" in url
        assert "main" in url

    def test_get_download_url_performance_path(self):
        """Test _get_download_url with performance path"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com",
            model_id="test/model",
            use_performance_path=True
        )
        
        url = generator._get_download_url()
        assert "performance" in url

    def test_get_download_url_sanitization(self):
        """Test URL sanitization in _get_download_url"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com",
            model_id="test/model:version",
            version="main"
        )
        
        url = generator._get_download_url()
        assert ":" not in url
        assert "_" in url

    def test_get_metrics_empty(self):
        """Test get_metrics with no metrics"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com"
        )
        
        metrics = generator.get_metrics()
        assert metrics == []

    def test_get_metrics_with_data(self):
        """Test get_metrics with collected metrics"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com"
        )
        
        metric = Metric(
            run_id="test-run-1",
            client_id=1,
            request_latency_ms=100.0,
            bytes_transferred=1024,
            status_code=200,
            timestamp=datetime.now(timezone.utc)
        )
        generator.metrics.append(metric)
        
        metrics = generator.get_metrics()
        assert len(metrics) == 1
        assert metrics[0]["run_id"] == "test-run-1"
        assert metrics[0]["client_id"] == 1

    def test_get_summary_empty(self):
        """Test get_summary with no metrics"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com"
        )
        
        summary = generator.get_summary()
        assert summary["total_requests"] == 0
        assert summary["successful_requests"] == 0
        assert summary["mean_latency_ms"] == 0

    def test_get_summary_with_metrics(self):
        """Test get_summary with collected metrics"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com"
        )
        
        generator.start_time = time.time()
        generator.end_time = generator.start_time + 1.0
        
        # Add successful metrics
        for i in range(5):
            metric = Metric(
                run_id="test-run-1",
                client_id=i + 1,
                request_latency_ms=100.0 + i * 10,
                bytes_transferred=1024,
                status_code=200,
                timestamp=datetime.now(timezone.utc)
            )
            generator.metrics.append(metric)
        
        # Add failed metric
        failed_metric = Metric(
            run_id="test-run-1",
            client_id=6,
            request_latency_ms=50.0,
            bytes_transferred=0,
            status_code=500,
            timestamp=datetime.now(timezone.utc)
        )
        generator.metrics.append(failed_metric)
        
        summary = generator.get_summary()
        assert summary["total_requests"] == 6
        assert summary["successful_requests"] == 5
        assert summary["failed_requests"] == 1
        assert summary["mean_latency_ms"] > 0
        assert summary["throughput_bps"] > 0

    @pytest.mark.asyncio
    async def test_make_request_success(self):
        """Test _make_request with successful response"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com",
            model_id="test/model"
        )
        
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"test content")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_response)
        
        metric = await generator._make_request(1, mock_session)
        
        assert metric.status_code == 200
        assert metric.bytes_transferred == len(b"test content")
        assert metric.client_id == 1

    @pytest.mark.asyncio
    async def test_make_request_timeout(self):
        """Test _make_request with timeout"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com",
            model_id="test/model"
        )
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=asyncio.TimeoutError())
        
        metric = await generator._make_request(1, mock_session)
        
        assert metric.status_code == 0
        assert metric.bytes_transferred == 0
        assert metric.client_id == 1

    @pytest.mark.asyncio
    async def test_make_request_exception(self):
        """Test _make_request with exception"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com",
            model_id="test/model"
        )
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=Exception("Network error"))
        
        metric = await generator._make_request(1, mock_session)
        
        assert metric.status_code == 0
        assert metric.bytes_transferred == 0

    @pytest.mark.asyncio
    async def test_run_client_single_request(self):
        """Test _run_client without duration (single request)"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com",
            model_id="test/model"
        )
        
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"content")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_response)
        
        await generator._run_client(1, mock_session)
        
        assert len(generator.metrics) == 1

    @pytest.mark.asyncio
    async def test_run_client_with_duration(self):
        """Test _run_client with duration"""
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com",
            model_id="test/model",
            duration_seconds=0.5
        )
        
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"content")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_response)
        
        await generator._run_client(1, mock_session)
        
        # Should make multiple requests within duration
        assert len(generator.metrics) > 1

    @pytest.mark.asyncio
    @patch("src.services.performance.load_generator.store_and_publish_metrics")
    async def test_run_complete(self, mock_store_metrics):
        """Test complete run method"""
        mock_store_metrics.return_value = {
            "dynamodb_stored": 2,
            "cloudwatch_published": True,
            "total_metrics": 2
        }
        
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com",
            model_id="test/model",
            num_clients=2
        )
        
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"content")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_response)
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session_instance
            
            await generator.run()
        
        assert generator.start_time is not None
        assert generator.end_time is not None
        assert len(generator.metrics) == 2
        mock_store_metrics.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.services.performance.load_generator.store_and_publish_metrics")
    async def test_run_metrics_storage_error(self, mock_store_metrics):
        """Test run method handles metrics storage errors"""
        mock_store_metrics.side_effect = Exception("Storage error")
        
        generator = LoadGenerator(
            run_id="test-run-1",
            base_url="https://api.example.com",
            model_id="test/model",
            num_clients=1
        )
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"content")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_response)
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session_instance
            
            # Should not raise exception
            await generator.run()
        
        assert len(generator.metrics) == 1

