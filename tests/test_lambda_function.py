"""
Tests for lambda_function.py

WHAT WE'RE TESTING:
  End-to-end Lambda handler with MOCKED AWS services.

  We use `moto` — a library that intercepts boto3 calls and simulates
  AWS services in memory. This means we can test S3 writes and SNS
  publishes WITHOUT needing real AWS credentials or infrastructure.

  moto decorators:
    @mock_aws  — intercepts ALL boto3 calls for the decorated test
"""

import os
import json
import base64
import gzip
import boto3
import pytest
from unittest.mock import patch
from moto import mock_aws

from src.log_generator import generate_logs
from src.anomaly_model import train, save_model


# ──────────────────────────────────────────────
# Test fixtures
# ──────────────────────────────────────────────
def make_cloudwatch_event(log_messages):
    """Build a mock CloudWatch subscription filter event."""
    log_data = {
        "messageType": "DATA_MESSAGE",
        "owner": "123456789012",
        "logGroup": "/aws/lambda/test",
        "logStream": "test-stream",
        "logEvents": [
            {"id": str(i), "timestamp": 1704067200000 + i, "message": msg}
            for i, msg in enumerate(log_messages)
        ],
    }
    json_bytes = json.dumps(log_data).encode("utf-8")
    compressed = gzip.compress(json_bytes)
    encoded = base64.b64encode(compressed).decode("utf-8")
    return {"awslogs": {"data": encoded}}


def make_test_model(tmpdir):
    """Train and save a small test model."""
    logs = generate_logs(count=200, anomaly_ratio=0.05)
    features = [
        [float(l["response_time_ms"]), 1.0 if l["status_code"] >= 500 else 0.0,
         1.0 if l["level"] == "WARN" else 0.0, float(l["status_code"])]
        for l in logs
    ]
    model = train(features)
    model_path = os.path.join(tmpdir, "model.joblib")
    save_model(model, model_path)
    return model_path


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────
class TestLambdaHandler:
    """End-to-end Lambda handler tests with mocked AWS."""

    @mock_aws
    def test_processes_normal_logs(self, tmp_path):
        """Handler should process normal logs without errors."""
        model_path = make_test_model(str(tmp_path))

        # Create mock S3 bucket
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-anomaly-bucket")

        # Create mock SNS topic
        sns = boto3.client("sns", region_name="us-east-1")
        topic = sns.create_topic(Name="test-alerts")
        topic_arn = topic["TopicArn"]

        # Build event with normal logs
        normal_logs = [
            json.dumps({"level": "INFO", "status_code": 200,
                         "response_time_ms": 100, "service": "test",
                         "message": "OK"})
        ]
        event = make_cloudwatch_event(normal_logs)

        # Patch env vars and model path, then import and run
        with patch.dict(os.environ, {
            "S3_BUCKET": "test-anomaly-bucket",
            "SNS_TOPIC_ARN": topic_arn,
            "MODEL_PATH": model_path,
        }):
            # Reset cached model
            import src.lambda_function as lf
            lf._model = None
            lf.S3_BUCKET = "test-anomaly-bucket"
            lf.SNS_TOPIC_ARN = topic_arn
            lf.MODEL_PATH = model_path
            lf.s3_client = s3
            lf.sns_client = sns

            result = lf.handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["processed"] == 1

    @mock_aws
    def test_detects_and_stores_anomaly(self, tmp_path):
        """Anomalous logs should be written to S3 and trigger SNS."""
        model_path = make_test_model(str(tmp_path))

        # Create mock AWS resources
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-anomaly-bucket")
        sns = boto3.client("sns", region_name="us-east-1")
        topic = sns.create_topic(Name="test-alerts")
        topic_arn = topic["TopicArn"]

        # Build event with an obvious anomaly
        anomaly_logs = [
            json.dumps({"level": "ERROR", "status_code": 500,
                         "response_time_ms": 9999, "service": "payment-service",
                         "message": "Database connection timeout"})
        ]
        event = make_cloudwatch_event(anomaly_logs)

        with patch.dict(os.environ, {
            "S3_BUCKET": "test-anomaly-bucket",
            "SNS_TOPIC_ARN": topic_arn,
            "MODEL_PATH": model_path,
        }):
            import src.lambda_function as lf
            lf._model = None
            lf.S3_BUCKET = "test-anomaly-bucket"
            lf.SNS_TOPIC_ARN = topic_arn
            lf.MODEL_PATH = model_path
            lf.s3_client = s3
            lf.sns_client = sns

            result = lf.handler(event, None)

        body = json.loads(result["body"])
        assert body["anomalies_detected"] >= 1

        # Verify S3 has the anomaly report
        objects = s3.list_objects_v2(Bucket="test-anomaly-bucket", Prefix="anomalies/")
        assert objects.get("KeyCount", 0) >= 1

    @mock_aws
    def test_handles_empty_event(self, tmp_path):
        """Empty log events should return gracefully."""
        model_path = make_test_model(str(tmp_path))

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-anomaly-bucket")

        event = make_cloudwatch_event([])

        with patch.dict(os.environ, {
            "S3_BUCKET": "test-anomaly-bucket",
            "MODEL_PATH": model_path,
        }):
            import src.lambda_function as lf
            lf._model = None
            lf.S3_BUCKET = "test-anomaly-bucket"
            lf.MODEL_PATH = model_path
            lf.s3_client = s3

            result = lf.handler(event, None)

        assert result["statusCode"] == 200
