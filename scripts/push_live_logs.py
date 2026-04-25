import os
import boto3
import time
import json
import dateutil.parser
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.log_generator import generate_logs

def push_logs():
    print("Generating 150 synthetic logs (15% anomalies)...")
    logs = generate_logs(count=150, anomaly_ratio=0.15)
    
    # Needs to match terraform/variables.tf default region and log group
    client = boto3.client('logs', region_name='us-east-1')
    log_group = '/app/log-anomaly-dev'
    log_stream = f'test-stream-{int(time.time())}'
    
    print(f"Creating log stream {log_stream} in {log_group}...")
    try:
        client.create_log_stream(logGroupName=log_group, logStreamName=log_stream)
    except Exception as e:
        print(f"Error creating stream: {e}")
        return

    log_events = []
    for log_dict in logs:
        dt = dateutil.parser.isoparse(log_dict['timestamp'])
        ts_ms = int(dt.timestamp() * 1000)
        log_events.append({
            'timestamp': ts_ms,
            'message': json.dumps(log_dict)
        })
    
    # CloudWatch requires chronological order
    log_events.sort(key=lambda x: x['timestamp'])
    
    print("Pushing logs to AWS CloudWatch...")
    try:
        # put_log_events accepts up to 10,000 events or 1MB, we only have 150 so we can send in one batch
        response = client.put_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            logEvents=log_events
        )
        print("✅ Successfully pushed logs to CloudWatch!")
        print("Wait ~30 seconds for the Lambda to process them, then refresh Grafana!")
    except Exception as e:
        print(f"Failed to push logs: {e}")

if __name__ == "__main__":
    push_logs()
