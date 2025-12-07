"""
Unit tests for performance metrics storage service
"""
import os
from unittest.mock import patch, MagicMock, Mock
from decimal import Decimal
from datetime import datetime, timezone
import pytest
from botocore.exceptions import ClientError

from src.services.performance.metrics_storage import (
    store_metrics_in_dynamodb,
    publish_metrics_to_cloudwatch,
    store_and_publish_metrics,
    calculate_percentile,
)


class TestCalculatePercentile:
    """Test calculate_percentile function"""

    def test_calculate_percentile_empty_list(self):
        """Test percentile calculation with empty list"""
        result = calculate_percentile([], 50.0)
        assert result == 0.0

    def test_calculate_percentile_single_value(self):
        """Test percentile calculation with single value"""
        result = calculate_percentile([10.0], 50.0)
        assert result == 10.0

    def test_calculate_percentile_p50(self):
        """Test 50th percentile (median)"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_percentile(values, 50.0)
        assert result == 3.0

    def test_calculate_percentile_p99(self):
        """Test 99th percentile"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_percentile(values, 99.0)
        assert result == pytest.approx(5.0, abs=0.1)

    def test_calculate_percentile_p0(self):
        """Test 0th percentile (minimum)"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_percentile(values, 0.0)
        assert result == 1.0

    def test_calculate_percentile_p100(self):
        """Test 100th percentile (maximum)"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_percentile(values, 100.0)
        assert result == 5.0

    def test_calculate_percentile_interpolation(self):
        """Test percentile interpolation"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_percentile(values, 25.0)
        assert result == 2.0


class TestStoreMetricsInDynamoDB:
    """Test store_metrics_in_dynamodb function"""

    @patch("src.services.performance.metrics_storage.dynamodb")
    def test_store_metrics_empty_list(self, mock_dynamodb):
        """Test storing empty metrics list"""
        result = store_metrics_in_dynamodb([])
        assert result == 0

    @patch("src.services.performance.metrics_storage.dynamodb")
    def test_store_metrics_success(self, mock_dynamodb):
        """Test successful metric storage"""
        mock_table = MagicMock()
        mock_batch_writer = MagicMock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch_writer
        mock_dynamodb.Table.return_value = mock_table

        metrics = [
            {
                "run_id": "test-run-1",
                "client_id": 1,
                "request_latency_ms": 100.5,
                "bytes_transferred": 1024,
                "status_code": 200,
                "timestamp": "2024-01-01T00:00:00Z",
            }
        ]

        result = store_metrics_in_dynamodb(metrics)

        assert result == 1
        mock_batch_writer.put_item.assert_called_once()

    @patch("src.services.performance.metrics_storage.dynamodb")
    def test_store_metrics_multiple(self, mock_dynamodb):
        """Test storing multiple metrics"""
        mock_table = MagicMock()
        mock_batch_writer = MagicMock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch_writer
        mock_dynamodb.Table.return_value = mock_table

        metrics = [
            {
                "run_id": "test-run-1",
                "client_id": i,
                "request_latency_ms": 100.0 + i,
                "bytes_transferred": 1024,
                "status_code": 200,
            }
            for i in range(5)
        ]

        result = store_metrics_in_dynamodb(metrics)

        assert result == 5
        assert mock_batch_writer.put_item.call_count == 5

    @patch("src.services.performance.metrics_storage.dynamodb")
    def test_store_metrics_with_defaults(self, mock_dynamodb):
        """Test storing metrics with default values"""
        mock_table = MagicMock()
        mock_batch_writer = MagicMock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch_writer
        mock_dynamodb.Table.return_value = mock_table

        metrics = [
            {
                "run_id": "test-run-1",
            }
        ]

        result = store_metrics_in_dynamodb(metrics)

        assert result == 1
        call_args = mock_batch_writer.put_item.call_args
        item = call_args[1]["Item"]
        assert item["client_id"] == 0
        assert item["request_latency_ms"] == Decimal("0")
        assert item["bytes_transferred"] == 0
        assert item["status_code"] == 0

    @patch("src.services.performance.metrics_storage.dynamodb")
    def test_store_metrics_client_error_resource_not_found(self, mock_dynamodb):
        """Test handling ResourceNotFoundException"""
        mock_table = MagicMock()
        error_response = {"Error": {"Code": "ResourceNotFoundException"}}
        mock_table.batch_writer.side_effect = ClientError(error_response, "BatchWriteItem")
        mock_dynamodb.Table.return_value = mock_table

        metrics = [
            {
                "run_id": "test-run-1",
                "client_id": 1,
                "request_latency_ms": 100.0,
                "bytes_transferred": 1024,
                "status_code": 200,
            }
        ]

        result = store_metrics_in_dynamodb(metrics)

        assert result == 0

    @patch("src.services.performance.metrics_storage.dynamodb")
    def test_store_metrics_client_error_other(self, mock_dynamodb):
        """Test handling other ClientError"""
        mock_table = MagicMock()
        error_response = {"Error": {"Code": "InternalError"}}
        mock_table.batch_writer.side_effect = ClientError(error_response, "BatchWriteItem")
        mock_dynamodb.Table.return_value = mock_table

        metrics = [
            {
                "run_id": "test-run-1",
                "client_id": 1,
                "request_latency_ms": 100.0,
                "bytes_transferred": 1024,
                "status_code": 200,
            }
        ]

        result = store_metrics_in_dynamodb(metrics)

        assert result == 0

    @patch("src.services.performance.metrics_storage.dynamodb")
    def test_store_metrics_exception_in_batch(self, mock_dynamodb):
        """Test handling exception during batch write"""
        mock_table = MagicMock()
        mock_batch_writer = MagicMock()
        mock_batch_writer.put_item.side_effect = Exception("Batch error")
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch_writer
        mock_dynamodb.Table.return_value = mock_table

        metrics = [
            {
                "run_id": "test-run-1",
                "client_id": 1,
                "request_latency_ms": 100.0,
                "bytes_transferred": 1024,
                "status_code": 200,
            }
        ]

        result = store_metrics_in_dynamodb(metrics)

        assert result == 0


class TestPublishMetricsToCloudWatch:
    """Test publish_metrics_to_cloudwatch function"""

    @patch("src.services.performance.metrics_storage.cloudwatch")
    def test_publish_metrics_empty_list(self, mock_cloudwatch):
        """Test publishing empty metrics list"""
        result = publish_metrics_to_cloudwatch("test-run-1", [], 10.0)
        assert result is False
        mock_cloudwatch.put_metric_data.assert_not_called()

    @patch("src.services.performance.metrics_storage.cloudwatch")
    def test_publish_metrics_success(self, mock_cloudwatch):
        """Test successful metric publishing"""
        metrics = [
            {
                "run_id": "test-run-1",
                "request_latency_ms": 100.0,
                "bytes_transferred": 1024,
                "status_code": 200,
            },
            {
                "run_id": "test-run-1",
                "request_latency_ms": 200.0,
                "bytes_transferred": 2048,
                "status_code": 200,
            },
        ]

        result = publish_metrics_to_cloudwatch("test-run-1", metrics, 1.0)

        assert result is True
        mock_cloudwatch.put_metric_data.assert_called_once()

    @patch("src.services.performance.metrics_storage.cloudwatch")
    def test_publish_metrics_no_successful_requests(self, mock_cloudwatch):
        """Test publishing when no successful requests"""
        metrics = [
            {
                "run_id": "test-run-1",
                "request_latency_ms": 100.0,
                "bytes_transferred": 1024,
                "status_code": 500,
            }
        ]

        result = publish_metrics_to_cloudwatch("test-run-1", metrics, 1.0)

        assert result is False
        mock_cloudwatch.put_metric_data.assert_not_called()

    @patch("src.services.performance.metrics_storage.cloudwatch")
    def test_publish_metrics_client_error(self, mock_cloudwatch):
        """Test handling ClientError during publishing"""
        error_response = {"Error": {"Code": "InternalError"}}
        mock_cloudwatch.put_metric_data.side_effect = ClientError(error_response, "PutMetricData")

        metrics = [
            {
                "run_id": "test-run-1",
                "request_latency_ms": 100.0,
                "bytes_transferred": 1024,
                "status_code": 200,
            }
        ]

        result = publish_metrics_to_cloudwatch("test-run-1", metrics, 1.0)

        assert result is False

    @patch("src.services.performance.metrics_storage.cloudwatch")
    def test_publish_metrics_exception(self, mock_cloudwatch):
        """Test handling exception during publishing"""
        mock_cloudwatch.put_metric_data.side_effect = Exception("Unexpected error")

        metrics = [
            {
                "run_id": "test-run-1",
                "request_latency_ms": 100.0,
                "bytes_transferred": 1024,
                "status_code": 200,
            }
        ]

        result = publish_metrics_to_cloudwatch("test-run-1", metrics, 1.0)

        assert result is False

    @patch("src.services.performance.metrics_storage.cloudwatch")
    def test_publish_metrics_batch_size(self, mock_cloudwatch):
        """Test publishing metrics in batches"""
        # Create 25 metrics to test batching (batch size is 20)
        metrics = [
            {
                "run_id": "test-run-1",
                "request_latency_ms": 100.0,
                "bytes_transferred": 1024,
                "status_code": 200,
            }
            for _ in range(25)
        ]

        result = publish_metrics_to_cloudwatch("test-run-1", metrics, 1.0)

        assert result is True
        # Function aggregates metrics into 6 summary metrics, all fit in one batch
        assert mock_cloudwatch.put_metric_data.call_count == 1

    @patch("src.services.performance.metrics_storage.cloudwatch")
    def test_publish_metrics_zero_duration(self, mock_cloudwatch):
        """Test publishing with zero duration"""
        metrics = [
            {
                "run_id": "test-run-1",
                "request_latency_ms": 100.0,
                "bytes_transferred": 1024,
                "status_code": 200,
            }
        ]

        result = publish_metrics_to_cloudwatch("test-run-1", metrics, 0.0)

        assert result is True
        mock_cloudwatch.put_metric_data.assert_called_once()


class TestStoreAndPublishMetrics:
    """Test store_and_publish_metrics function"""

    @patch("src.services.performance.metrics_storage.publish_metrics_to_cloudwatch")
    @patch("src.services.performance.metrics_storage.store_metrics_in_dynamodb")
    def test_store_and_publish_success(self, mock_store, mock_publish):
        """Test successful store and publish"""
        mock_store.return_value = 5
        mock_publish.return_value = True

        metrics = [
            {
                "run_id": "test-run-1",
                "request_latency_ms": 100.0,
                "bytes_transferred": 1024,
                "status_code": 200,
            }
        ]

        result = store_and_publish_metrics("test-run-1", metrics, 1.0)

        assert result["dynamodb_stored"] == 5
        assert result["cloudwatch_published"] is True
        assert result["total_metrics"] == 1
        mock_store.assert_called_once_with(metrics)
        mock_publish.assert_called_once_with("test-run-1", metrics, 1.0)

    @patch("src.services.performance.metrics_storage.publish_metrics_to_cloudwatch")
    @patch("src.services.performance.metrics_storage.store_metrics_in_dynamodb")
    def test_store_and_publish_partial_failure(self, mock_store, mock_publish):
        """Test store and publish with partial failure"""
        mock_store.return_value = 3
        mock_publish.return_value = False

        metrics = [
            {
                "run_id": "test-run-1",
                "request_latency_ms": 100.0,
                "bytes_transferred": 1024,
                "status_code": 200,
            }
            for _ in range(5)
        ]

        result = store_and_publish_metrics("test-run-1", metrics, 1.0)

        assert result["dynamodb_stored"] == 3
        assert result["cloudwatch_published"] is False
        assert result["total_metrics"] == 5

