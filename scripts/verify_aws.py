import boto3
import json
from datetime import datetime, timedelta

def run_diagnostics():
    print("Running AWS Diagnostic Checks...\n")
    try:
        cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
        logs = boto3.client('logs', region_name='us-east-1')
    except Exception as e:
        print("Failed to initialize boto3. Are your AWS keys set?")
        return

    # 1. Check Custom Metrics
    print("1️⃣  Checking for Custom Metrics in 'LogAnomaly' namespace...")
    try:
        metrics = cloudwatch.list_metrics(Namespace='LogAnomaly')
        if metrics.get('Metrics'):
            print("   ✅ Success: Found metrics populated in AWS:", list(set([m['MetricName'] for m in metrics['Metrics']])))
            
            # Let's check if there are actual data points in the last hour
            stats = cloudwatch.get_metric_statistics(
                Namespace='LogAnomaly',
                MetricName='AnomalyCount',
                StartTime=datetime.utcnow() - timedelta(hours=1),
                EndTime=datetime.utcnow(),
                Period=300,
                Statistics=['Sum']
            )
            datapoints = stats.get('Datapoints', [])
            if datapoints:
                print(f"   ✅ Success: Found {len(datapoints)} datapoints for AnomalyCount. (Grafana should 100% see this!)")
            else:
                print("   ❌ Found the metric name, but 0 datapoints exist in the last hour.")
        else:
            print("   ❌ NO METRICS FOUND. The namespace LogAnomaly doesn't exist yet.")
    except Exception as e:
        print("   ❌ Error connecting to CloudWatch Metrics:", e)

    print("\n2️⃣  Checking AWS Lambda Execution Logs...")
    try:
        log_group = '/aws/lambda/log-anomaly-detector-dev'
        streams_res = logs.describe_log_streams(
            logGroupName=log_group, 
            orderBy='LastEventTime', 
            descending=True, 
            limit=3
        )
        
        streams = streams_res.get('logStreams', [])
        if not streams:
            print("   ❌ NO LOGS. The Lambda Function has literally NEVER executed.")
            print("   This means the log pushing script failed to trigger the Lambda via CloudWatch.")
        else:
            print(f"   ✅ Lambda log group exists. Reading recent logs...")
            
            crashes = []
            anomaly_payloads = 0
            
            for stream in streams:
                events = logs.get_log_events(logGroupName=log_group, logStreamName=stream['logStreamName'], limit=50)
                for event in events['events']:
                    msg = event['message']
                    if "Traceback" in msg or "Task timed out" in msg or "[ERROR]" in msg or "AccessDenied" in msg:
                        crashes.append(msg.strip())
                    if "ANOMALY_DETAIL" in msg:
                        anomaly_payloads += 1
            
            if crashes:
                print("   ❌ LAMBDA CRASHED! Here is the error:")
                for c in crashes:
                    print(f"      {c}")
            else:
                print("   ✅ No crashes detected in recent Lambda logs.")
                print(f"   ✅ Found {anomaly_payloads} anomaly JSON payloads successfully logged for Grafana to query.")
                
    except logs.exceptions.ResourceNotFoundException:
        print("   ❌ Lambda Log Group /aws/lambda/log-anomaly-detector-dev DOES NOT EXIST.")
    except Exception as e:
        print("   ❌ Error checking lambda logs:", e)

    print("\n--------------------------------------------------")
    print("Please copy the output of this script and share it with me!")

if __name__ == "__main__":
    run_diagnostics()
