import boto3

def verify_app_logs():
    print("Checking if logs actually reached the AWS source log group...")
    try:
        logs = boto3.client('logs', region_name='us-east-1')
        log_group = '/app/log-anomaly-dev'
        
        streams = logs.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime', 
            descending=True
        )
        
        stream_list = streams.get('logStreams', [])
        if not stream_list:
            print(f"❌ Empty! No Log Streams exist in {log_group}.")
            print("This means 'python scripts/push_live_logs.py' failed or wasn't run.")
            return

        total_events = 0
        for s in stream_list:
            # check if there are stored bytes
            if s.get('storedBytes', 0) > 0:
                print(f"✅ Found stream '{s['logStreamName']}' with {s.get('storedBytes')} bytes of logs.")
                total_events += 1
                
        if total_events > 0:
            print("\n✅ Wait, logs DO exist in the source group! This means the CloudWatch Subscription Filter to trigger Lambda is broken.")
        else:
            print(f"\n❌ Log streams exist, but they are completely empty (0 bytes).")
            print("This means 'python scripts/push_live_logs.py' created the group but failed to push data.")

    except logs.exceptions.ResourceNotFoundException:
        print("❌ Log Group /app/log-anomaly-dev DOES NOT EXIST! The Terraform setup wasn't deployed to this region/account.")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    verify_app_logs()
