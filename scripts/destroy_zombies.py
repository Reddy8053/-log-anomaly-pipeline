import boto3
import time

def destroy_zombies():
    print("Beginning eradication of zombie AWS resources...")
    iam = boto3.client('iam', region_name='us-east-1')
    lambda_client = boto3.client('lambda', region_name='us-east-1')
    s3 = boto3.client('s3', region_name='us-east-1')
    sns = boto3.client('sns', region_name='us-east-1')
    logs = boto3.client('logs', region_name='us-east-1')

    # 1. Destroy Lambda
    try:
        lambda_client.delete_function(FunctionName='log-anomaly-detector-dev')
        print("✅ Deleted Lambda Function")
    except Exception as e: print("⚠️ Lambda:", e)

    # 2. Destroy IAM
    try:
        policies = iam.list_role_policies(RoleName='log-anomaly-lambda-role-dev').get('PolicyNames', [])
        for p in policies:
            iam.delete_role_policy(RoleName='log-anomaly-lambda-role-dev', PolicyName=p)
        iam.delete_role(RoleName='log-anomaly-lambda-role-dev')
        print("✅ Deleted IAM Role and Policies")
    except Exception as e: print("⚠️ IAM:", e)

    # 3. Destroy S3 Bucket
    try:
        bucket_name = 'log-anomaly-results-dev'
        objects = s3.list_objects_v2(Bucket=bucket_name)
        if 'Contents' in objects:
            for obj in objects['Contents']:
                s3.delete_object(Bucket=bucket_name, Key=obj['Key'])
        s3.delete_bucket(Bucket=bucket_name)
        print("✅ Deleted S3 Results Bucket")
    except Exception as e: print("⚠️ S3:", e)

    # 4. Destroy CloudWatch Log Groups
    try:
        logs.delete_log_group(logGroupName='/app/log-anomaly-dev')
        print("✅ Deleted Source Log Group")
    except Exception as e: print("⚠️ Logs:", e)
    try:
        logs.delete_log_group(logGroupName='/aws/lambda/log-anomaly-detector-dev')
        print("✅ Deleted Lambda Log Group")
    except Exception as e: print("⚠️ Logs:", e)

    # 5. Destroy SNS Topic
    try:
        topics = sns.list_topics().get('Topics', [])
        for t in topics:
            if 'anomaly-alerts-dev' in t['TopicArn']:
                sns.delete_topic(TopicArn=t['TopicArn'])
                print("✅ Deleted SNS Topic")
    except Exception as e: print("⚠️ SNS:", e)

    print("\nEnvironment is clean! GitHub Actions Terraform can now run perfectly from scratch.")

if __name__ == "__main__":
    destroy_zombies()
