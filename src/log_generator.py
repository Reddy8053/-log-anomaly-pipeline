"""
Log Generator — Produces realistic synthetic application logs.

HOW IT WORKS:
=============
This module simulates a web application that handles HTTP requests.
Each generated log line is a JSON object with fields you'd see in a real
production system:

  - timestamp   : ISO-8601 date/time
  - level       : INFO, WARN, ERROR
  - service     : which microservice produced the log
  - method      : HTTP method (GET, POST, etc.)
  - path        : API endpoint that was called
  - status_code : HTTP status code (200, 201, 500, etc.)
  - response_time_ms : how long the request took in milliseconds
  - message     : human-readable description

NORMAL vs ANOMALOUS:
  - Normal logs  : response_time 50-200 ms, status 200/201
  - Anomalous    : latency spikes 2000-8000 ms, 500 errors, ERROR bursts
  - ~5% of logs are anomalous by default (controlled by anomaly_ratio)
"""

import json
import random
import argparse
from datetime import datetime, timedelta


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
SERVICES = ["auth-service", "payment-service", "user-service", "order-service"]
ENDPOINTS = ["/api/login", "/api/checkout", "/api/users", "/api/orders", "/api/health"]
METHODS = ["GET", "POST", "PUT", "DELETE"]


def generate_normal_log(ts):
    """
    Generate a single NORMAL log entry.
    - Response time: 50-200 ms (healthy range)
    - Status code: 200 or 201 (success)
    - Level: INFO
    """
    return {
        "timestamp": ts.isoformat(),
        "level": "INFO",
        "service": random.choice(SERVICES),
        "method": random.choice(METHODS),
        "path": random.choice(ENDPOINTS),
        "status_code": random.choice([200, 201]),
        "response_time_ms": random.randint(50, 200),
        "message": "Request processed successfully",
    }


def generate_anomalous_log(ts):
    """
    Generate a single ANOMALOUS log entry.
    Three flavours of anomaly are randomly selected:

    1. Latency spike  — response_time 2000-8000 ms (10-40x normal)
    2. Server error   — HTTP 500 with elevated latency
    3. Error burst    — HTTP 503 Service Unavailable
    """
    anomaly_type = random.choice(["latency_spike", "server_error", "error_burst"])

    if anomaly_type == "latency_spike":
        return {
            "timestamp": ts.isoformat(),
            "level": "WARN",
            "service": random.choice(SERVICES),
            "method": random.choice(METHODS),
            "path": random.choice(ENDPOINTS),
            "status_code": 200,
            "response_time_ms": random.randint(2000, 8000),
            "message": "Request completed but latency exceeded threshold",
        }
    elif anomaly_type == "server_error":
        return {
            "timestamp": ts.isoformat(),
            "level": "ERROR",
            "service": random.choice(SERVICES),
            "method": random.choice(METHODS),
            "path": random.choice(ENDPOINTS),
            "status_code": 500,
            "response_time_ms": random.randint(1000, 5000),
            "message": "Internal server error — database connection timeout",
        }
    else:  # error_burst
        return {
            "timestamp": ts.isoformat(),
            "level": "ERROR",
            "service": random.choice(SERVICES),
            "method": random.choice(METHODS),
            "path": random.choice(ENDPOINTS),
            "status_code": 503,
            "response_time_ms": random.randint(3000, 10000),
            "message": "Service unavailable — upstream dependency failure",
        }


def generate_logs(count=500, anomaly_ratio=0.05):
    """
    Generate a list of log dicts.

    Parameters
    ----------
    count : int
        Total number of log lines to generate.
    anomaly_ratio : float
        Fraction of logs that should be anomalous (default 5%).

    Returns
    -------
    list[dict]
        List of log entries sorted by timestamp.
    """
    logs = []
    start_time = datetime.utcnow() - timedelta(hours=1)

    for i in range(count):
        # Advance timestamp slightly for each log (realistic ordering)
        ts = start_time + timedelta(seconds=i * random.uniform(0.1, 2.0))

        if random.random() < anomaly_ratio:
            logs.append(generate_anomalous_log(ts))
        else:
            logs.append(generate_normal_log(ts))

    return logs


# ──────────────────────────────────────────────
# CLI entry-point
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Generate synthetic application logs")
    parser.add_argument("--count", type=int, default=500, help="Number of log lines")
    parser.add_argument("--anomaly-ratio", type=float, default=0.05, help="Fraction of anomalous logs")
    parser.add_argument("--output", type=str, default=None, help="Output file path (.jsonl)")
    args = parser.parse_args()

    logs = generate_logs(count=args.count, anomaly_ratio=args.anomaly_ratio)

    if args.output:
        import os
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            for log in logs:
                f.write(json.dumps(log) + "\n")
        print(f"✅ Generated {len(logs)} logs → {args.output}")
    else:
        for log in logs:
            print(json.dumps(log))


if __name__ == "__main__":
    main()
