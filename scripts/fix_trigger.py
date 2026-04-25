import boto3

def fix_trigger():
    print("Wiring CloudWatch Logs directly to Lambda...")
    
    try:
        lambda_client = boto3.client('lambda', region_name='us-east-1')
        logs_client = boto3.client('logs', region_name='us-east-1')
    except Exception as e:
        print("❌ Failed to initialize AWS clients:", e)
        return

    # 1. Get lambda ARN
    try:
        lambda_info = lambda_client.get_function(FunctionName='log-anomaly-detector-dev')
        lambda_arn = lambda_info['Configuration']['FunctionArn']
        print(f"✅ Found Lambda ARN: {lambda_arn}")
    except Exception as e:
        print("❌ Cannot find lambda:", e)
        return

    # 2. Add permission for CloudWatch logs to trigger Lambda
    try:
        # We must use the exact 12-digit Account ID
        sts = boto3.client('sts', region_name='us-east-1')
        account_id = sts.get_caller_identity()['Account']
        
        lambda_client.add_permission(
            FunctionName='log-anomaly-detector-dev',
            StatementId='AllowCWInvokeHotfix_V4',
            Action='lambda:InvokeFunction',
            Principal='logs.amazonaws.com',
            SourceArn=f'arn:aws:logs:us-east-1:{account_id}:log-group:/app/log-anomaly-dev:*'
        )
        print("✅ Added trigger permission to Lambda")
    except lambda_client.exceptions.ResourceConflictException:
        print("✅ Lambda trigger permission already exists")
    except Exception as e:
        print("⚠️ Warning adding permission (it might already exist):", e)

    # 3. Add Subscription Filter
    try:
        logs_client.put_subscription_filter(
            logGroupName='/app/log-anomaly-dev',
            filterName='log-anomaly-trigger-dev',
            filterPattern='',
            destinationArn=lambda_arn
        )
        print("✅ Successfully wired CloudWatch Logs to trigger the Lambda!")
    except Exception as e:
        print("❌ Error adding subscription filter:", e)

if __name__ == "__main__":
    fix_trigger()
