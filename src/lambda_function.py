"""
Lambda Function — Entry point for AWS Lambda.

WHAT HAPPENS WHEN THIS RUNS:
=============================
1. CloudWatch detects new log entries in a monitored log group
2. A Subscription Filter sends matching logs to this Lambda
3. The event payload arrives base64-encoded + gzip-compressed
4. Our handler:
   a) Decodes the CloudWatch event → extracts log lines
   b) Parses each log line → extracts numeric features
   c) Loads the pre-trained Isolation Forest model
   d) Runs predictions on the features
   e) For each ANOMALY detected:
      - Writes a detailed JSON report to S3
      - Publishes an alert to SNS (email notification)
   f) Returns a summary of what was processed

AWS ENVIRONMENT VARIABLES (set via Terraform):
  - S3_BUCKET      : Bucket name for anomaly results
  - SNS_TOPIC_ARN  : ARN of the SNS topic for alerts
  - MODEL_PATH     : Path to the model file (default: /opt/model/isolation_forest.joblib)

LAMBDA LAYERS:
  The trained model (.joblib) is deployed as a Lambda Layer,
  which mounts at /opt/ in the Lambda execution environment.
"""

import os
import json
import boto3
from datetime import datetime

from src.log_parser import decode_cloudwatch_event, extract_features
from src.anomaly_model import load_model, predict, anomaly_scores


# ──────────────────────────────────────────────
# Configuration from environment variables
# ──────────────────────────────────────────────
S3_BUCKET = os.environ.get("S3_BUCKET", "log-anomaly-results")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
MODEL_PATH = os.environ.get("MODEL_PATH", "/opt/model/isolation_forest.joblib")

# AWS SDK clients (created outside handler for connection reuse)
s3_client = boto3.client("s3")
sns_client = boto3.client("sns")
cloudwatch_client = boto3.client("cloudwatch")

# Load model once at cold-start (not on every invocation)
# This is a key Lambda optimization — model loading is expensive
_model = None


def get_model():
    """
    Lazy-load the model. On first invocation (cold start), load from disk.
    On subsequent invocations (warm start), reuse the cached model.

    WHY LAZY LOADING?
    Lambda keeps the execution environment alive between invocations.
    By caching the model in a global variable, we avoid the ~200ms
    overhead of loading joblib on every single request.
    """
    global _model
    if _model is None:
        _model = load_model(MODEL_PATH)
    return _model


def handler(event, context):
    """
    AWS Lambda handler — processes CloudWatch log events.

    Parameters
    ----------
    event : dict
        CloudWatch Logs subscription filter event containing:
        {
            "awslogs": {
                "data": "<base64-encoded, gzip-compressed log data>"
            }
        }
    context : LambdaContext
        Runtime information (request ID, time remaining, etc.)

    Returns
    -------
    dict
        Summary of processing results.
    """
    print(f"📨 Received CloudWatch event")

    # ── Step 1: Decode the CloudWatch event ──────────────
    try:
        log_events = decode_cloudwatch_event(event)
        print(f"📋 Decoded {len(log_events)} log events")
    except Exception as e:
        print(f"❌ Failed to decode event: {e}")
        return {"statusCode": 400, "body": f"Decode error: {str(e)}"}

    if not log_events:
        return {"statusCode": 200, "body": "No log events to process"}

    # ── Step 2: Extract features ─────────────────────────
    features, parsed_logs = extract_features(log_events)
    print(f"🔧 Extracted features from {len(features)} logs")

    # ── Step 3: Run anomaly detection ────────────────────
    model = get_model()
    predictions = predict(model, features)
    scores = anomaly_scores(model, features)

    # ── Step 4: Process results ──────────────────────────
    anomalies_found = []
    for i, (pred, score) in enumerate(zip(predictions, scores)):
        if pred == -1:  # Anomaly detected!
            anomaly_detail = {
                "detection_timestamp": datetime.utcnow().isoformat(),
                "anomaly_score": float(score),
                "log_entry": parsed_logs[i],
                "features": {
                    "response_time_ms": features[i][0],
                    "is_error": features[i][1],
                    "is_warning": features[i][2],
                    "status_code": features[i][3],
                },
            }
            anomalies_found.append(anomaly_detail)

    print(f"🔍 Detected {len(anomalies_found)} anomalies out of {len(features)} logs")

    # ── Step 5: Write anomalies to S3 ────────────────────
    if anomalies_found:
        timestamp = datetime.utcnow().strftime("%Y/%m/%d/%H-%M-%S")
        s3_key = f"anomalies/{timestamp}.json"

        report = {
            "processed_at": datetime.utcnow().isoformat(),
            "total_logs": len(log_events),
            "anomalies_detected": len(anomalies_found),
            "anomalies": anomalies_found,
        }

        try:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=json.dumps(report, indent=2),
                ContentType="application/json",
            )
            print(f"📁 Wrote anomaly report to s3://{S3_BUCKET}/{s3_key}")
        except Exception as e:
            print(f"❌ S3 write failed: {e}")

        # ── Step 6: Publish SNS alert ────────────────────
        if SNS_TOPIC_ARN:
            try:
                alert_message = (
                    f"🚨 ANOMALY ALERT\n\n"
                    f"Detected {len(anomalies_found)} anomalies "
                    f"in {len(log_events)} log events.\n\n"
                    f"Details: s3://{S3_BUCKET}/{s3_key}\n\n"
                    f"Top anomaly:\n"
                    f"  Service: {anomalies_found[0]['log_entry'].get('service', 'unknown')}\n"
                    f"  Response time: {anomalies_found[0]['features']['response_time_ms']}ms\n"
                    f"  Status code: {int(anomalies_found[0]['features']['status_code'])}\n"
                )
                sns_client.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Subject="🚨 Log Anomaly Detected",
                    Message=alert_message,
                )
                print(f"📧 Published alert to SNS")
            except Exception as e:
                print(f"❌ SNS publish failed: {e}")

    # ── Step 7: Put CloudWatch Metrics for Grafana ───────
    try:
        # Calculate overall stats for the batch
        total_errors = sum(1 for f in features if f[1] == 1)  # is_error feature
        error_rate = (total_errors / len(features)) * 100 if features else 0
        avg_latency = sum(f[0] for f in features) / len(features) if features else 0

        metric_data = [
            {
                "MetricName": "AnomalyCount",
                "Value": len(anomalies_found),
                "Unit": "Count"
            },
            {
                "MetricName": "ErrorRate",
                "Value": error_rate,
                "Unit": "Percent"
            },
            {
                "MetricName": "ResponseTime",
                "Value": avg_latency,
                "Unit": "Milliseconds"
            }
        ]
        
        # Optionally, for a more accurate ResponseTime distribution in Grafana, 
        # we could push an array of values, but an average works fine for this batch summary.
        cloudwatch_client.put_metric_data(
            Namespace="LogAnomaly",
            MetricData=metric_data
        )
        print("📊 Published metrics to CloudWatch LogAnomaly namespace")
    except Exception as e:
        print(f"❌ Failed to publish CloudWatch metrics: {e}")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "processed": len(log_events),
            "anomalies_detected": len(anomalies_found),
        }),
    }
