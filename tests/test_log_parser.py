"""
Tests for log_parser.py

WHAT WE'RE TESTING:
  1. decode_cloudwatch_event — Can it correctly decode a base64+gzip payload?
  2. parse_log_message — Does it handle valid JSON and invalid input gracefully?
  3. extract_features — Are numeric features extracted correctly?
"""

import base64
import gzip
import json
import pytest

from src.log_parser import decode_cloudwatch_event, parse_log_message, extract_features


def make_cloudwatch_event(log_messages):
    """
    Helper: Build a realistic CloudWatch subscription filter event.

    This simulates what AWS actually sends to the Lambda:
      1. Create log events with messages
      2. JSON-encode everything
      3. Gzip compress
      4. Base64 encode
    """
    log_data = {
        "messageType": "DATA_MESSAGE",
        "owner": "123456789012",
        "logGroup": "/aws/lambda/test-function",
        "logStream": "2024/01/01/[$LATEST]abc123",
        "logEvents": [
            {"id": str(i), "timestamp": 1704067200000 + i, "message": msg}
            for i, msg in enumerate(log_messages)
        ],
    }
    json_bytes = json.dumps(log_data).encode("utf-8")
    compressed = gzip.compress(json_bytes)
    encoded = base64.b64encode(compressed).decode("utf-8")
    return {"awslogs": {"data": encoded}}


class TestDecodeCloudwatchEvent:
    """Test the CloudWatch event decoding pipeline."""

    def test_decodes_single_log(self):
        """One log message should decode to one event."""
        event = make_cloudwatch_event(['{"level": "INFO", "status_code": 200}'])
        result = decode_cloudwatch_event(event)
        assert len(result) == 1
        assert result[0]["message"] == '{"level": "INFO", "status_code": 200}'

    def test_decodes_multiple_logs(self):
        """Multiple messages should all decode correctly."""
        messages = [
            '{"level": "INFO", "status_code": 200}',
            '{"level": "ERROR", "status_code": 500}',
            '{"level": "WARN", "status_code": 200}',
        ]
        event = make_cloudwatch_event(messages)
        result = decode_cloudwatch_event(event)
        assert len(result) == 3

    def test_preserves_message_content(self):
        """Original message content should be preserved through decode."""
        original = '{"response_time_ms": 5000, "level": "ERROR"}'
        event = make_cloudwatch_event([original])
        result = decode_cloudwatch_event(event)
        assert result[0]["message"] == original


class TestParseLogMessage:
    """Test individual log message parsing."""

    def test_valid_json(self):
        """Valid JSON string should parse correctly."""
        result = parse_log_message('{"level": "INFO", "status_code": 200}')
        assert result["level"] == "INFO"
        assert result["status_code"] == 200

    def test_invalid_json_returns_defaults(self):
        """Invalid JSON should return safe defaults instead of crashing."""
        result = parse_log_message("not valid json")
        assert result["level"] == "UNKNOWN"
        assert result["status_code"] == 0

    def test_none_input(self):
        """None input should be handled gracefully."""
        result = parse_log_message(None)
        assert result["level"] == "UNKNOWN"


class TestExtractFeatures:
    """Test feature extraction from log events."""

    def test_extracts_correct_features(self):
        """Features should match expected values from log content."""
        log_events = [
            {"message": json.dumps({
                "response_time_ms": 150,
                "status_code": 200,
                "level": "INFO",
            })}
        ]
        features, parsed = extract_features(log_events)
        assert len(features) == 1
        assert features[0] == [150.0, 0.0, 0.0, 200.0]

    def test_error_log_features(self):
        """500 error should produce is_error = 1.0."""
        log_events = [
            {"message": json.dumps({
                "response_time_ms": 3000,
                "status_code": 500,
                "level": "ERROR",
            })}
        ]
        features, _ = extract_features(log_events)
        assert features[0][0] == 3000.0   # response_time_ms
        assert features[0][1] == 1.0       # is_error
        assert features[0][3] == 500.0     # status_code

    def test_warning_log_features(self):
        """WARN level should produce is_warning = 1.0."""
        log_events = [
            {"message": json.dumps({
                "response_time_ms": 5000,
                "status_code": 200,
                "level": "WARN",
            })}
        ]
        features, _ = extract_features(log_events)
        assert features[0][2] == 1.0  # is_warning

    def test_multiple_events(self):
        """Should handle multiple events and return matching counts."""
        log_events = [
            {"message": json.dumps({"response_time_ms": 100, "status_code": 200, "level": "INFO"})},
            {"message": json.dumps({"response_time_ms": 5000, "status_code": 500, "level": "ERROR"})},
        ]
        features, parsed = extract_features(log_events)
        assert len(features) == 2
        assert len(parsed) == 2
