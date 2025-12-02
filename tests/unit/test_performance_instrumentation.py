"""
Unit tests for performance instrumentation
"""
import time
from unittest.mock import patch, MagicMock
import pytest

from src.services.performance.instrumentation import (
    publish_metric,
    measure_operation,
    instrument_latency,
    instrument_bytes,
)


class TestPublishMetric:
    """Test publish_metric function"""

    @patch("src.services.performance.instrumentation.cloudwatch")
    def test_publish_metric_success(self, mock_cloudwatch):
        """Test successful metric publishing"""
        result = publish_metric("TestMetric", 100.0, "Count")

        assert result is True
        mock_cloudwatch.put_metric_data.assert_called_once()

    @patch("src.services.performance.instrumentation.cloudwatch")
    def test_publish_metric_with_dimensions(self, mock_cloudwatch):
        """Test publishing metric with dimensions"""
        dimensions = {"Component": "S3", "Operation": "Download"}
        result = publish_metric("TestMetric", 100.0, "Count", dimensions)

        assert result is True
        call_args = mock_cloudwatch.put_metric_data.call_args
        assert "Dimensions" in call_args[1]["MetricData"][0]

    @patch("src.services.performance.instrumentation.cloudwatch")
    def test_publish_metric_exception(self, mock_cloudwatch):
        """Test handling exception during publishing"""
        mock_cloudwatch.put_metric_data.side_effect = Exception("CloudWatch error")

        result = publish_metric("TestMetric", 100.0, "Count")

        assert result is False


class TestMeasureOperation:
    """Test measure_operation context manager"""

    @patch("src.services.performance.instrumentation.publish_metric")
    def test_measure_operation_success(self, mock_publish):
        """Test measuring operation duration"""
        with measure_operation("TestOperation"):
            time.sleep(0.01)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args.kwargs["metric_name"] == "TestOperation"
        assert call_args.kwargs["value"] > 0  # Duration should be positive

    @patch("src.services.performance.instrumentation.publish_metric")
    def test_measure_operation_with_dimensions(self, mock_publish):
        """Test measuring operation with dimensions"""
        dimensions = {"Component": "S3"}
        with measure_operation("TestOperation", dimensions):
            pass

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args.kwargs["dimensions"] == dimensions

    @patch("src.services.performance.instrumentation.publish_metric")
    def test_measure_operation_with_exception(self, mock_publish):
        """Test measuring operation when exception occurs"""
        try:
            with measure_operation("TestOperation"):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should still publish metric even if exception occurred
        mock_publish.assert_called_once()


class TestInstrumentLatency:
    """Test instrument_latency decorator"""

    @patch("src.services.performance.instrumentation.publish_metric")
    def test_instrument_latency_success(self, mock_publish):
        """Test instrumenting function latency"""
        @instrument_latency("TestFunction")
        def test_func():
            time.sleep(0.01)
            return "result"

        result = test_func()

        assert result == "result"
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args.kwargs["metric_name"] == "TestFunction"
        assert call_args.kwargs["value"] > 0

    @patch("src.services.performance.instrumentation.publish_metric")
    def test_instrument_latency_with_dimensions(self, mock_publish):
        """Test instrumenting latency with dimensions"""
        @instrument_latency("TestFunction", {"Component": "S3"})
        def test_func():
            return "result"

        test_func()

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args.kwargs["dimensions"] == {"Component": "S3"}

    @patch("src.services.performance.instrumentation.publish_metric")
    def test_instrument_latency_with_exception(self, mock_publish):
        """Test instrumenting latency when exception occurs"""
        @instrument_latency("TestFunction")
        def test_func():
            raise ValueError("Test error")

        try:
            test_func()
        except ValueError:
            pass

        # Should still publish metric even if exception occurred
        mock_publish.assert_called_once()


class TestInstrumentBytes:
    """Test instrument_bytes decorator"""

    @patch("src.services.performance.instrumentation.publish_metric")
    def test_instrument_bytes_default(self, mock_publish):
        """Test instrumenting bytes with default function"""
        @instrument_bytes("BytesTransferred")
        def test_func():
            return b"test data"

        result = test_func()

        assert result == b"test data"
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args.kwargs["metric_name"] == "BytesTransferred"
        assert call_args.kwargs["value"] == len(b"test data")

    @patch("src.services.performance.instrumentation.publish_metric")
    def test_instrument_bytes_custom_function(self, mock_publish):
        """Test instrumenting bytes with custom function"""
        @instrument_bytes("BytesTransferred", lambda r: len(r) * 2)
        def test_func():
            return b"test"

        result = test_func()

        assert result == b"test"
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args.kwargs["value"] == 8  # len("test") * 2

    @patch("src.services.performance.instrumentation.publish_metric")
    def test_instrument_bytes_with_dimensions(self, mock_publish):
        """Test instrumenting bytes with dimensions"""
        @instrument_bytes("BytesTransferred", dimensions={"Component": "S3"})
        def test_func():
            return b"data"

        test_func()

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args.kwargs["dimensions"] == {"Component": "S3"}

    @patch("src.services.performance.instrumentation.publish_metric")
    def test_instrument_bytes_no_length(self, mock_publish):
        """Test instrumenting bytes when result has no length"""
        @instrument_bytes("BytesTransferred")
        def test_func():
            return None

        result = test_func()

        assert result is None
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args.kwargs["value"] == 0

    @patch("src.services.performance.instrumentation.publish_metric")
    def test_instrument_bytes_exception(self, mock_publish):
        """Test instrumenting bytes when exception occurs"""
        @instrument_bytes("BytesTransferred", lambda r: r.invalid_attr)
        def test_func():
            return b"data"

        result = test_func()

        assert result == b"data"
        # Should handle exception gracefully - publish_metric should not be called when exception occurs
        mock_publish.assert_not_called()

