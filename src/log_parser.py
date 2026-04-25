"""
Log Parser — Decodes CloudWatch log events and extracts numeric features.

HOW IT WORKS:
=============
When CloudWatch triggers a Lambda via a Subscription Filter, the event
payload arrives as:

    event["awslogs"]["data"]  →  base64-encoded, gzip-compressed JSON

This module handles the decoding pipeline:
    base64 string → raw bytes → gzip decompress → JSON → log events

Then it extracts NUMERIC FEATURES from each log entry so the ML model
can analyze them:

    Features extracted per log line:
    ┌─────────────────────┬──────────────────────────────────────────┐
    │ response_time_ms    │ How long the request took               │
    │ is_error            │ 1 if status_code >= 500, else 0         │
    │ is_warning          │ 1 if level == "WARN", else 0            │
    │ status_code         │ Raw HTTP status code                    │
    └─────────────────────┴──────────────────────────────────────────┘

WHY THESE FEATURES?
    The Isolation Forest model needs numeric inputs. These four features
    capture the most important signals of anomalous behaviour:
    high latency, server errors, and warning conditions.
"""

import base64
import gzip
import json


def decode_cloudwatch_event(event):
    """
    Decode an AWS CloudWatch Logs subscription filter event.

    CloudWatch sends log data in a specific format:
      1. JSON with key "awslogs" → "data"
      2. The "data" value is base64-encoded
      3. After decoding base64, the bytes are gzip-compressed
      4. After decompressing, we get JSON with "logEvents" array

    Parameters
    ----------
    event : dict
        Raw Lambda event from CloudWatch subscription filter.

    Returns
    -------
    list[dict]
        Parsed log events, each with 'id', 'timestamp', 'message' keys.
    """
    # Step 1: Get the base64-encoded, gzip-compressed payload
    encoded_data = event["awslogs"]["data"]

    # Step 2: Base64 decode → raw gzip bytes
    compressed_bytes = base64.b64decode(encoded_data)

    # Step 3: Gzip decompress → JSON string
    json_string = gzip.decompress(compressed_bytes).decode("utf-8")

    # Step 4: Parse JSON → Python dict
    log_data = json.loads(json_string)

    return log_data.get("logEvents", [])


def parse_log_message(message_str):
    """
    Parse a single log message string into a dict.

    The message field in CloudWatch logEvents is a raw string.
    Our log generator writes JSON, so we parse it back.
    If parsing fails, we return a minimal dict with defaults.

    Parameters
    ----------
    message_str : str
        Raw log message string from CloudWatch.

    Returns
    -------
    dict
        Parsed log entry.
    """
    try:
        return json.loads(message_str)
    except (json.JSONDecodeError, TypeError):
        return {
            "level": "UNKNOWN",
            "status_code": 0,
            "response_time_ms": 0,
        }


def extract_features(log_events):
    """
    Convert raw CloudWatch log events into numeric feature arrays
    for the anomaly detection model.

    Parameters
    ----------
    log_events : list[dict]
        Log events from decode_cloudwatch_event(), each with a 'message' key.

    Returns
    -------
    tuple(list[list[float]], list[dict])
        - features: list of [response_time_ms, is_error, is_warning, status_code]
        - parsed_logs: the parsed log dicts (for reporting anomalies)
    """
    features = []
    parsed_logs = []

    for event in log_events:
        log = parse_log_message(event.get("message", "{}"))
        parsed_logs.append(log)

        feature_vector = [
            float(log.get("response_time_ms", 0)),
            1.0 if log.get("status_code", 200) >= 500 else 0.0,
            1.0 if log.get("level", "") == "WARN" else 0.0,
            float(log.get("status_code", 200)),
        ]
        features.append(feature_vector)

    return features, parsed_logs
