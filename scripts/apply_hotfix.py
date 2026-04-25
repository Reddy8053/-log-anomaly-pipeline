import boto3
import json
import shutil
import os
import sys

def apply_hotfix():
    print("Applying hotfix directly to AWS...")
    
    # Needs to match terraform/variables.tf default region
    try:
        iam = boto3.client('iam', region_name='us-east-1')
        lambda_client = boto3.client('lambda', region_name='us-east-1')
    except Exception as e:
        print("Failed to initialize AWS clients. Did you export your AWS keys?")
        return

    # 1. Add PutMetricData permission to the existing IAM role
    print("1/2: Upgrading IAM Role permissions...")
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["cloudwatch:PutMetricData"],
            "Resource": "*"
        }]
    }
    try:
        iam.put_role_policy(
            RoleName='log-anomaly-lambda-role-dev',
            PolicyName='AllowPutMetricData',
            PolicyDocument=json.dumps(policy_document)
        )
    except Exception as e:
        print(f"Failed to update IAM policy: {e}")
        return

    # 2. Package and update the Lambda Function code
    print("2/2: Updating Lambda Function code...")
    src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')
    zip_path = os.path.join(os.path.dirname(__file__), 'lambda_package')
    
    try:
        shutil.make_archive(zip_path, 'zip', src_dir)
        with open(f"{zip_path}.zip", 'rb') as f:
            lambda_client.update_function_code(
                FunctionName='log-anomaly-detector-dev',
                ZipFile=f.read()
            )
        os.remove(f"{zip_path}.zip")
    except Exception as e:
        print(f"Failed to update lambda code: {e}")
        return

    print("✅ Hotfix applied successfully!")
    print("\nNext Steps:")
    print("1. Wait ~15 seconds for the Lambda to update.")
    print("2. Run 'python scripts/push_live_logs.py' again to generate new traffic.")
    print("3. Check Grafana!")

if __name__ == "__main__":
    apply_hotfix()
